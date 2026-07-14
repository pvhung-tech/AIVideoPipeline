import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise RuntimeError("FFmpeg and FFprobe must be available on PATH.")

    backendPath = Path(__file__).resolve().parent
    sidecarPath = resolveSidecarPath()
    port = int(os.environ.get("PHASE8_RECOVERY_PORT", findFreePort()))

    with tempfile.TemporaryDirectory(
        prefix="phase8-render-recovery-", ignore_cleanup_errors=True
    ) as workspace:
        workspacePath = Path(workspace)
        libraryPath = workspacePath / "library"
        appDataPath = workspacePath / "app-data"
        projectParent = workspacePath / "projects"
        libraryPath.mkdir(parents=True, exist_ok=True)
        projectParent.mkdir(parents=True, exist_ok=True)

        assets = createAssets(Path(ffmpeg), libraryPath)
        scriptPath = workspacePath / "episode.srt"
        scriptPath.write_text(buildSrt(), encoding="utf-8")

        environment = os.environ.copy()
        environment["APP_DATA_DIR"] = str(appDataPath)
        environment["FFMPEG_PATH"] = ffmpeg
        environment["FFPROBE_PATH"] = ffprobe
        environment["LOCAL_MEDIA_LIBRARY_PATHS"] = str(libraryPath)
        environment["MEDIA_CACHE_MAX_FILE_SIZE_BYTES"] = str(160 * 1024 * 1024)

        server = BackendServer(
            backendPath, environment, port, workspacePath, sidecarPath
        )
        server.start()
        try:
            project = unwrap(
                request(
                    "POST",
                    port,
                    "/api/projects",
                    {
                        "name": "Phase 8 Render Recovery",
                        "parentDirectory": str(projectParent),
                    },
                ),
                "create project",
            )
            unwrap(
                request("POST", port, "/api/scripts/import", {"path": str(scriptPath)}),
                "import recovery script",
            )
            prepareTimeline(port, assets)
            job = unwrap(
                request(
                    "POST",
                    port,
                    "/api/render/jobs",
                    {
                        "profileId": "standard",
                        "outputNameTemplate": "phase8-recovery-{datetime}.mp4",
                    },
                ),
                "start durable render job",
            )
            runningJob = waitForStatus(port, job["jobId"], {"running"}, 45)
            if runningJob["status"] != "running":
                raise RuntimeError("Render job did not reach running state.")
        finally:
            server.stop()

        restarted = BackendServer(
            backendPath, environment, port, workspacePath, sidecarPath
        )
        restarted.start()
        try:
            unwrap(
                request(
                    "POST",
                    port,
                    "/api/projects/open",
                    {"path": str(project["path"])},
                ),
                "open project after restart",
            )
            interruptedJob = waitForStatus(
                port, job["jobId"], {"interrupted", "completed", "failed"}, 30
            )
            if interruptedJob["status"] != "interrupted":
                raise RuntimeError(
                    "Expected interrupted job after backend restart, got "
                    f"{interruptedJob['status']}: {json.dumps(interruptedJob)}"
                )
            if interruptedJob.get("errorCode") != "RENDER_INTERRUPTED":
                raise RuntimeError(
                    "Interrupted job did not persist restart diagnostics."
                )

            resumedJob = unwrap(
                request("POST", port, f"/api/render/jobs/{job['jobId']}/resume"),
                "resume interrupted render job",
            )
            if resumedJob["status"] != "queued":
                raise RuntimeError(f"Expected resumed job queued, got {resumedJob}")

            completedJob = waitForStatus(port, job["jobId"], {"completed"}, 240)
            outputPath = Path(str(completedJob["outputPath"]))
            if not outputPath.is_file() or outputPath.stat().st_size <= 0:
                raise RuntimeError(f"Recovered render output is missing: {outputPath}")
            if not completedJob.get("preview"):
                raise RuntimeError("Recovered render did not persist preview metadata.")

            queue = unwrap(request("GET", port, "/api/render/jobs"), "list render jobs")
        finally:
            restarted.stop()

        print(
            json.dumps(
                {
                    "runner": str(sidecarPath) if sidecarPath else "dev-sidecar.py",
                    "projectPath": project["path"],
                    "jobId": job["jobId"],
                    "interruptedStatus": interruptedJob["status"],
                    "resumedStatus": resumedJob["status"],
                    "finalStatus": completedJob["status"],
                    "outputPath": str(outputPath),
                    "outputSizeBytes": outputPath.stat().st_size,
                    "queueJobCount": len(queue["jobs"]),
                },
                indent=2,
            )
        )


class BackendServer:
    def __init__(
        self,
        backendPath: Path,
        environment: dict[str, str],
        port: int,
        logPath: Path,
        sidecarPath: Path | None,
    ) -> None:
        self.backendPath = backendPath
        self.environment = environment
        self.port = port
        self.logPath = logPath
        self.sidecarPath = sidecarPath
        self.process: subprocess.Popen[str] | None = None
        self.stdout: Any | None = None
        self.stderr: Any | None = None

    def start(self) -> None:
        stdoutPath = self.logPath / f"backend-{self.port}-stdout.log"
        stderrPath = self.logPath / f"backend-{self.port}-stderr.log"
        self.stdout = stdoutPath.open("a", encoding="utf-8")
        self.stderr = stderrPath.open("a", encoding="utf-8")
        command = self._command()
        self.process = subprocess.Popen(
            command,
            cwd=self._workingDirectory(),
            env=self.environment,
            stdout=self.stdout,
            stderr=self.stderr,
            text=True,
        )
        waitForHealth(self.port, self.process, stderrPath)

    def _command(self) -> list[str]:
        if self.sidecarPath is not None:
            return [
                str(self.sidecarPath),
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ]
        return [
            sys.executable,
            "sidecar.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
        ]

    def _workingDirectory(self) -> Path:
        if self.sidecarPath is not None:
            return self.sidecarPath.parent
        return self.backendPath

    def stop(self) -> None:
        if self.process is None:
            return
        try:
            if self.sidecarPath is not None:
                forceClosePackagedSidecar(self.port, self.sidecarPath.name)
            if self.process.poll() is None:
                if self.sidecarPath is not None:
                    terminateProcessTree(self.process)
                else:
                    self.process.kill()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=15)
        finally:
            waitForPortClosed(self.port)
            if self.stdout is not None:
                self.stdout.close()
            if self.stderr is not None:
                self.stderr.close()


def prepareTimeline(port: int, assets: dict[str, Path]) -> None:
    cached = {
        name: unwrap(
            request(
                "POST",
                port,
                "/api/media/cache",
                {
                    "providerId": "local",
                    "mediaId": name,
                    "sourceUri": path.as_uri(),
                    "fileName": path.name,
                },
            ),
            f"cache {name}",
        )
        for name, path in assets.items()
    }
    timeline = unwrap(
        request("POST", port, "/api/timeline/generate"), "generate timeline"
    )
    sceneIds = [scene["sceneId"] for scene in timeline["scenes"]]
    for index, sceneId in enumerate(sceneIds):
        visual = cached["clip"] if index % 2 else cached["image"]
        unwrap(
            request(
                "PUT",
                port,
                f"/api/timeline/scenes/{sceneId}/media",
                {"contentHash": visual["contentHash"], "role": "broll"},
            ),
            f"assign broll scene {index + 1}",
        )
    unwrap(
        request(
            "PUT",
            port,
            "/api/timeline/music",
            {"contentHash": cached["music"]["contentHash"], "volume": 0.2},
        ),
        "assign music",
    )


def createAssets(ffmpeg: Path, libraryPath: Path) -> dict[str, Path]:
    imagePath = libraryPath / "recovery-image.png"
    videoPath = libraryPath / "recovery-clip.mp4"
    musicPath = libraryPath / "recovery-music.wav"
    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x183a59:s=1280x720",
        "-frames:v",
        "1",
        str(imagePath),
    )
    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30:duration=60",
        "-pix_fmt",
        "yuv420p",
        str(videoPath),
    )
    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=330:duration=60",
        "-ac",
        "2",
        str(musicPath),
    )
    return {"image": imagePath, "clip": videoPath, "music": musicPath}


def buildSrt() -> str:
    cues = [
        ("00:00:00,000", "00:00:10,000", "Recovery smoke opening scene."),
        ("00:00:10,000", "00:00:20,000", "Motion media keeps render active."),
        ("00:00:20,000", "00:00:30,000", "Queue state should persist safely."),
        ("00:00:30,000", "00:00:40,000", "Backend restart interrupts the job."),
        ("00:00:40,000", "00:00:50,000", "Resume requeues the same output."),
        ("00:00:50,000", "00:01:00,000", "Final output confirms recovery."),
    ]
    return "\n".join(
        f"{index}\n{start} --> {end}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, start=1)
    )


def waitForStatus(
    port: int, jobId: str, statuses: set[str], timeoutSeconds: int
) -> dict[str, Any]:
    deadline = time.monotonic() + timeoutSeconds
    lastJob: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        lastJob = unwrap(
            request("GET", port, f"/api/render/jobs/{jobId}"), "poll render job"
        )
        if lastJob["status"] in statuses:
            return lastJob
        if lastJob["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(f"Render job stopped early: {json.dumps(lastJob)}")
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {statuses}: {json.dumps(lastJob)}")


def waitForHealth(port: int, process: subprocess.Popen[str], stderrPath: Path) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = stderrPath.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"Backend exited before health check:\n{stderr}")
        try:
            payload = request("GET", port, "/api/health")
            if payload.get("success") and payload.get("data", {}).get("status") == "ok":
                return
        except RuntimeError:
            time.sleep(0.25)
    raise RuntimeError(f"Backend did not become healthy on port {port}.")


def request(
    method: str, port: int, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    requestObject = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(requestObject, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            return json.loads(error.read().decode("utf-8"))
        except json.JSONDecodeError as parseError:
            raise RuntimeError(
                f"{method} {path} failed with HTTP {error.code}"
            ) from parseError
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{method} {path} failed: {error}") from error


def unwrap(payload: dict[str, Any], action: str) -> Any:
    if not payload.get("success"):
        raise RuntimeError(f"{action} failed: {json.dumps(payload)}")
    return payload["data"]


def run(executable: Path, *args: str) -> None:
    completed = subprocess.run(
        (str(executable), *args),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {executable.name} {' '.join(args)}\n{completed.stderr}"
        )


def terminateProcessTree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        return
    process.terminate()


def terminatePortListener(port: int) -> None:
    if os.name != "nt":
        return
    pids = set(portListenerPids(port))
    for pid in pids:
        terminatePidWindows(pid)
        subprocess.run(
            ["taskkill", "/PID", pid, "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
    stopPowerShellPortListeners(port)
    terminateCommandLinePortProcesses(port)


def portListenerPids(port: int) -> list[str]:
    pids: list[str] = []
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        check=False,
        capture_output=True,
        text=True,
    )
    for line in completed.stdout.splitlines():
        if f":{port}" not in line or "LISTENING" not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        pids.append(parts[-1])
    pids.extend(powerShellPortListenerPids(port))
    return pids


def powerShellPortListenerPids(port: int) -> list[str]:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                f"Get-NetTCPConnection -LocalPort {port} -State Listen "
                "| Select-Object -ExpandProperty OwningProcess"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def stopPowerShellPortListeners(port: int) -> None:
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "$ErrorActionPreference='SilentlyContinue'; "
                f"Get-NetTCPConnection -LocalPort {port} "
                "| Select-Object -ExpandProperty OwningProcess -Unique "
                "| ForEach-Object { Stop-Process -Id $_ -Force }"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def terminateCommandLinePortProcesses(port: int) -> None:
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "$ErrorActionPreference='SilentlyContinue'; "
                f"$pattern='*--port*{port}*'; "
                "Get-CimInstance Win32_Process "
                "| Where-Object { $_.CommandLine -like $pattern } "
                "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def terminateImageName(imageName: str) -> None:
    if os.name != "nt":
        return
    subprocess.run(
        ["taskkill", "/IM", imageName, "/T", "/F"],
        check=False,
        capture_output=True,
        text=True,
    )


def terminatePidWindows(pid: str) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        processTerminate = 0x0001
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(processTerminate, False, int(pid))
        if handle:
            try:
                kernel32.TerminateProcess(handle, 1)
            finally:
                kernel32.CloseHandle(handle)
    except (OSError, ValueError):
        return


def forceClosePackagedSidecar(port: int, imageName: str) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        terminatePortListener(port)
        terminateImageName(imageName)
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=1
            ):
                time.sleep(0.25)
        except OSError:
            return


def waitForPortClosed(port: int) -> None:
    deadline = time.monotonic() + 45
    activePids: list[str] = []
    while time.monotonic() < deadline:
        try:
            activePids = portListenerPids(port)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=1
            ):
                time.sleep(0.25)
        except OSError:
            return
    raise RuntimeError(
        f"Backend still responds on port {port} after stop. Listener PIDs: {activePids}"
    )


def findFreePort() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def resolveSidecarPath() -> Path | None:
    configuredPath = os.environ.get("PHASE8_RECOVERY_SIDECAR_PATH")
    if not configuredPath:
        return None
    sidecarPath = Path(configuredPath).expanduser().resolve()
    if not sidecarPath.is_file():
        raise RuntimeError(f"Packaged sidecar was not found: {sidecarPath}")
    return sidecarPath


if __name__ == "__main__":
    main()
