use std::{
    error::Error,
    io,
    path::PathBuf,
    process::Command,
    sync::{mpsc, Mutex},
    thread,
    time::Duration,
};

use tauri::{App, Manager, RunEvent};
use tauri_plugin_log::{Target, TargetKind};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: &str = "8765";
const BACKEND_START_TIMEOUT: Duration = Duration::from_secs(15);

struct BackendChild {
    command_child: CommandChild,
    server_pid: u32,
}

struct BackendProcess(Mutex<Option<BackendChild>>);

enum StartupSignal {
    Ready(u32),
    Failed(String),
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::new()
                .targets([Target::new(TargetKind::Stdout)])
                .build(),
        )
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![open_path])
        .setup(|app| {
            let backend_process = start_backend(app)?;
            app.manage(backend_process);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build AI Video Pipeline Studio");

    app.run(|app_handle, event| match event {
        RunEvent::ExitRequested { .. } | RunEvent::Exit => stop_backend(app_handle),
        _ => {}
    });
}

fn start_backend(app: &mut App) -> Result<BackendProcess, Box<dyn Error>> {
    let command = app.shell().sidecar("fastapi-sidecar")?.args([
        "--host",
        BACKEND_HOST,
        "--port",
        BACKEND_PORT,
    ]);
    let (mut events, child) = command.spawn()?;
    let (startup_sender, startup_receiver) = mpsc::sync_channel(1);

    thread::spawn(move || {
        let mut startup_sender = Some(startup_sender);
        let mut server_pid = None;

        while let Some(event) = tauri::async_runtime::block_on(events.recv()) {
            handle_backend_event(event, &mut startup_sender, &mut server_pid);
        }
    });

    match startup_receiver.recv_timeout(BACKEND_START_TIMEOUT) {
        Ok(StartupSignal::Ready(server_pid)) => {
            log::info!("FastAPI sidecar is ready on port {BACKEND_PORT}");
            Ok(BackendProcess(Mutex::new(Some(BackendChild {
                command_child: child,
                server_pid,
            }))))
        }
        Ok(StartupSignal::Failed(message)) => {
            let _ = child.kill();
            Err(io::Error::other(message).into())
        }
        Err(_) => {
            let _ = child.kill();
            Err(io::Error::new(
                io::ErrorKind::TimedOut,
                "FastAPI sidecar did not become ready within 15 seconds",
            )
            .into())
        }
    }
}

#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    let target = PathBuf::from(path);
    if !target.exists() {
        return Err("Output path does not exist.".into());
    }
    open_existing_path(target).map_err(|error| error.to_string())
}

#[cfg(windows)]
fn open_existing_path(path: PathBuf) -> io::Result<()> {
    Command::new("explorer.exe").arg(path).spawn()?;
    Ok(())
}

#[cfg(target_os = "macos")]
fn open_existing_path(path: PathBuf) -> io::Result<()> {
    Command::new("open").arg(path).spawn()?;
    Ok(())
}

#[cfg(all(unix, not(target_os = "macos")))]
fn open_existing_path(path: PathBuf) -> io::Result<()> {
    Command::new("xdg-open").arg(path).spawn()?;
    Ok(())
}

fn handle_backend_event(
    event: CommandEvent,
    startup_sender: &mut Option<mpsc::SyncSender<StartupSignal>>,
    server_pid: &mut Option<u32>,
) {
    match event {
        CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
            let line = String::from_utf8_lossy(&bytes);
            log::info!(target: "fastapi_sidecar", "{}", line.trim());

            if let Some(pid) = parse_sidecar_process_id(&line) {
                *server_pid = Some(pid);
            }

            if is_backend_ready_line(&line) {
                match *server_pid {
                    Some(pid) => send_startup_signal(startup_sender, StartupSignal::Ready(pid)),
                    None => send_startup_signal(
                        startup_sender,
                        StartupSignal::Failed(
                            "FastAPI sidecar did not report its process ID".into(),
                        ),
                    ),
                }
            }
        }
        CommandEvent::Error(message) => {
            log::error!(target: "fastapi_sidecar", "{message}");
            send_startup_signal(startup_sender, StartupSignal::Failed(message));
        }
        CommandEvent::Terminated(payload) => {
            let message = format!("FastAPI sidecar exited with code {:?}", payload.code);
            log::error!(target: "fastapi_sidecar", "{message}");
            send_startup_signal(startup_sender, StartupSignal::Failed(message));
        }
        _ => {}
    }
}

fn send_startup_signal(
    startup_sender: &mut Option<mpsc::SyncSender<StartupSignal>>,
    signal: StartupSignal,
) {
    if let Some(sender) = startup_sender.take() {
        let _ = sender.send(signal);
    }
}

fn is_backend_ready_line(line: &str) -> bool {
    line.contains("Uvicorn running on")
}

fn parse_sidecar_process_id(line: &str) -> Option<u32> {
    line.split("SIDECAR_PROCESS_ID=")
        .nth(1)?
        .split_whitespace()
        .next()?
        .parse()
        .ok()
}

fn stop_backend(app_handle: &tauri::AppHandle) {
    let state = app_handle.state::<BackendProcess>();
    let Ok(mut process) = state.0.lock() else {
        log::error!("FastAPI sidecar state lock is poisoned");
        return;
    };

    if let Some(child) = process.take() {
        terminate_server_process(child.server_pid);

        if let Err(error) = child.command_child.kill() {
            log::error!("Failed to stop FastAPI sidecar: {error}");
        } else {
            log::info!("FastAPI sidecar stopped");
        }
    }
}

#[cfg(windows)]
fn terminate_server_process(server_pid: u32) {
    use windows_sys::Win32::{
        Foundation::CloseHandle,
        System::Threading::{OpenProcess, TerminateProcess, PROCESS_TERMINATE},
    };

    // The PID comes from the sidecar itself. PyInstaller one-file mode creates
    // a server child process that is not terminated when its bootloader exits.
    unsafe {
        let process_handle = OpenProcess(PROCESS_TERMINATE, 0, server_pid);
        if process_handle.is_null() {
            log::error!(
                "Failed to open FastAPI server process: {}",
                io::Error::last_os_error()
            );
            return;
        }

        let terminated = TerminateProcess(process_handle, 0);
        let terminate_error = io::Error::last_os_error();
        let _ = CloseHandle(process_handle);

        if terminated == 0 {
            log::error!("Failed to terminate FastAPI server process: {terminate_error}");
        } else {
            log::info!("FastAPI server process stopped");
        }
    }
}

#[cfg(not(windows))]
fn terminate_server_process(_server_pid: u32) {}

#[cfg(test)]
mod tests {
    use super::{is_backend_ready_line, parse_sidecar_process_id};

    #[test]
    fn detects_uvicorn_ready_message() {
        assert!(is_backend_ready_line(
            "INFO: Uvicorn running on http://127.0.0.1:8765"
        ));
    }

    #[test]
    fn ignores_unrelated_backend_output() {
        assert!(!is_backend_ready_line(
            "INFO: Application startup complete."
        ));
    }

    #[test]
    fn parses_sidecar_process_id() {
        assert_eq!(
            parse_sidecar_process_id("INFO sidecar SIDECAR_PROCESS_ID=12345"),
            Some(12345)
        );
    }
}
