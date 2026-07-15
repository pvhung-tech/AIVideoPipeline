use std::{
    error::Error,
    io,
    path::PathBuf,
    process::Command,
    sync::{Arc, Mutex},
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
const BACKEND_START_TIMEOUT: Duration = Duration::from_secs(45);

struct BackendChild {
    command_child: CommandChild,
    server_pid: Arc<Mutex<Option<u32>>>,
    #[cfg(windows)]
    _job: Option<ProcessJob>,
}

struct BackendProcess(Mutex<Option<BackendChild>>);

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
    let command = command.env(
        "AI_VIDEO_PIPELINE_PARENT_PID",
        std::process::id().to_string(),
    );
    let (mut events, child) = command.spawn()?;
    let sidecar_pid = child.pid();
    #[cfg(windows)]
    let job = match create_process_job(sidecar_pid) {
        Ok(job) => Some(job),
        Err(error) => {
            log::error!("Failed to create FastAPI sidecar process job: {error}");
            None
        }
    };
    let server_pid = Arc::new(Mutex::new(None));
    let event_server_pid = Arc::clone(&server_pid);

    thread::spawn(move || {
        while let Some(event) = tauri::async_runtime::block_on(events.recv()) {
            handle_backend_event(event, &event_server_pid);
        }
    });

    if wait_for_backend_health(BACKEND_START_TIMEOUT) {
        #[cfg(windows)]
        if let Some(job) = &job {
            if let Ok(process) = server_pid.lock() {
                if let Some(pid) = *process {
                    if let Err(error) = assign_process_to_job(job, pid) {
                        log::error!(
                            "Failed to assign FastAPI server process to process job: {error}"
                        );
                    }
                }
            }
        }
        log::info!("FastAPI sidecar is ready on port {BACKEND_PORT}");
        Ok(BackendProcess(Mutex::new(Some(BackendChild {
            command_child: child,
            server_pid,
            #[cfg(windows)]
            _job: job,
        }))))
    } else {
        let _ = child.kill();
        Err(io::Error::new(
            io::ErrorKind::TimedOut,
            "FastAPI sidecar did not become healthy within 45 seconds",
        )
        .into())
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

fn handle_backend_event(event: CommandEvent, server_pid: &Arc<Mutex<Option<u32>>>) {
    match event {
        CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
            let line = String::from_utf8_lossy(&bytes);
            log::info!(target: "fastapi_sidecar", "{}", line.trim());

            if let Some(pid) = parse_sidecar_process_id(&line) {
                if let Ok(mut process) = server_pid.lock() {
                    *process = Some(pid);
                }
            }
        }
        CommandEvent::Error(message) => {
            log::error!(target: "fastapi_sidecar", "{message}");
        }
        CommandEvent::Terminated(payload) => {
            let message = format!("FastAPI sidecar exited with code {:?}", payload.code);
            log::error!(target: "fastapi_sidecar", "{message}");
        }
        _ => {}
    }
}

fn wait_for_backend_health(timeout: Duration) -> bool {
    let started = std::time::Instant::now();
    while started.elapsed() < timeout {
        if backend_health_check() {
            return true;
        }
        thread::sleep(Duration::from_millis(100));
    }
    false
}

fn backend_health_check() -> bool {
    use std::io::{Read, Write};
    use std::net::TcpStream;

    let Ok(mut stream) = TcpStream::connect(format!("{BACKEND_HOST}:{BACKEND_PORT}")) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: {BACKEND_HOST}:{BACKEND_PORT}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    response.starts_with("HTTP/1.1 200")
        && (response.contains("\"status\": \"ok\"") || response.contains("\"status\":\"ok\""))
}

fn parse_sidecar_process_id(line: &str) -> Option<u32> {
    line.split("SIDECAR_PROCESS_ID=")
        .nth(1)?
        .split_whitespace()
        .next()?
        .parse()
        .ok()
}

#[cfg(windows)]
struct ProcessJob(windows_sys::Win32::Foundation::HANDLE);

#[cfg(windows)]
unsafe impl Send for ProcessJob {}

#[cfg(windows)]
impl Drop for ProcessJob {
    fn drop(&mut self) {
        use windows_sys::Win32::Foundation::CloseHandle;

        unsafe {
            let _ = CloseHandle(self.0);
        }
    }
}

#[cfg(windows)]
fn create_process_job(sidecar_pid: u32) -> io::Result<ProcessJob> {
    use windows_sys::Win32::{
        Foundation::CloseHandle,
        System::JobObjects::{
            CreateJobObjectW, JobObjectExtendedLimitInformation, SetInformationJobObject,
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        },
    };

    unsafe {
        let job_handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job_handle.is_null() {
            return Err(io::Error::last_os_error());
        }

        let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let configured = SetInformationJobObject(
            job_handle,
            JobObjectExtendedLimitInformation,
            &limits as *const _ as *const _,
            std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        );
        if configured == 0 {
            let error = io::Error::last_os_error();
            let _ = CloseHandle(job_handle);
            return Err(error);
        }

        let job = ProcessJob(job_handle);
        assign_process_to_job(&job, sidecar_pid)?;

        log::info!("FastAPI sidecar process job created");
        Ok(job)
    }
}

#[cfg(windows)]
fn assign_process_to_job(job: &ProcessJob, process_id: u32) -> io::Result<()> {
    use windows_sys::Win32::{
        Foundation::CloseHandle,
        System::{
            JobObjects::AssignProcessToJobObject,
            Threading::{OpenProcess, PROCESS_SET_QUOTA, PROCESS_TERMINATE},
        },
    };

    unsafe {
        let process_handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, 0, process_id);
        if process_handle.is_null() {
            return Err(io::Error::last_os_error());
        }

        let assigned = AssignProcessToJobObject(job.0, process_handle);
        let error = io::Error::last_os_error();
        let _ = CloseHandle(process_handle);

        if assigned == 0 {
            Err(error)
        } else {
            log::info!("FastAPI sidecar process {process_id} assigned to process job");
            Ok(())
        }
    }
}

fn stop_backend(app_handle: &tauri::AppHandle) {
    let state = app_handle.state::<BackendProcess>();
    let Ok(mut process) = state.0.lock() else {
        log::error!("FastAPI sidecar state lock is poisoned");
        return;
    };

    if let Some(child) = process.take() {
        if let Ok(server_pid) = child.server_pid.lock() {
            if let Some(pid) = *server_pid {
                terminate_server_process(pid);
            }
        }

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
    use super::parse_sidecar_process_id;

    #[test]
    fn parses_sidecar_process_id() {
        assert_eq!(
            parse_sidecar_process_id("INFO sidecar SIDECAR_PROCESS_ID=12345"),
            Some(12345)
        );
    }
}
