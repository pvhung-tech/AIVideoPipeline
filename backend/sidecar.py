import argparse
import asyncio
import json
import logging
import os
import threading
import time
from collections.abc import Sequence
from typing import Any, NoReturn

logger = logging.getLogger(__name__)
FULL_APP_TIMEOUT_SECONDS = 30.0


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FastAPI desktop sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--parent-pid", default=None, type=int)
    return parser


def runSidecar(arguments: Sequence[str] | None = None) -> None:
    startedAt = time.perf_counter()
    options = buildParser().parse_args(arguments)
    parentPid = options.parent_pid or getParentPidFromEnvironment()

    if parentPid is not None:
        startParentWatchdog(parentPid)

    app = LazyDesktopApp(startedAt)
    import uvicorn

    startupImportSeconds = time.perf_counter() - startedAt
    logger.info("Starting FastAPI desktop sidecar")
    logger.info("SIDECAR_PROCESS_ID=%s", os.getpid())
    logger.info("SIDECAR_STARTUP_IMPORT_SECONDS=%.4f", startupImportSeconds)
    uvicorn.run(
        app,
        host=options.host,
        port=options.port,
        http="h11",
        ws="none",
        loop="asyncio",
        lifespan="on",
        access_log=False,
    )


class LazyDesktopApp:
    def __init__(self, startedAt: float) -> None:
        self._startedAt = startedAt
        self._app: Any | None = None
        self._error: BaseException | None = None
        self._ready = threading.Event()
        self._loader = threading.Thread(
            target=self._loadFullApp,
            name="fastapi-full-app-loader",
            daemon=True,
        )
        self._loader.start()

    def _loadFullApp(self) -> None:
        try:
            from app.main import createApp

            self._app = createApp()
            logger.info(
                "SIDECAR_FULL_APP_READY_SECONDS=%.4f",
                time.perf_counter() - self._startedAt,
            )
        except BaseException as error:
            self._error = error
            logger.exception("FastAPI full app failed to load")
        finally:
            self._ready.set()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            await self._handleLifespan(receive, send)
            return

        if scope["type"] != "http":
            await self._sendJson(
                send,
                404,
                {
                    "success": False,
                    "data": None,
                    "message": "",
                    "error": {"code": "not_found", "message": "Route not found."},
                },
            )
            return

        path = scope.get("path")
        if path == "/api/health":
            await self._sendJson(
                send,
                200,
                {
                    "success": True,
                    "data": {
                        "appName": "AI Video Pipeline Studio",
                        "environment": os.getenv("APP_ENV", "development"),
                        "status": "ok",
                    },
                    "message": "Backend is healthy.",
                    "error": None,
                },
            )
            return

        app = await self._waitForFullApp()
        if app is None:
            await self._sendJson(
                send,
                503,
                {
                    "success": False,
                    "data": None,
                    "message": "",
                    "error": {
                        "code": "backend_starting",
                        "message": "Backend is still starting. Please retry shortly.",
                    },
                },
            )
            return

        await app(scope, receive, send)

    async def _handleLifespan(self, receive: Any, send: Any) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _waitForFullApp(self) -> Any | None:
        if not self._ready.is_set():
            await asyncio.to_thread(self._ready.wait, FULL_APP_TIMEOUT_SECONDS)

        if self._error is not None:
            raise self._error
        return self._app

    async def _sendJson(self, send: Any, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def startParentWatchdog(parentPid: int) -> None:
    target = watchWindowsParentProcess if os.name == "nt" else watchParentProcess
    watcher = threading.Thread(
        target=target,
        args=(parentPid,),
        name="desktop-parent-watchdog",
        daemon=True,
    )
    watcher.start()


def getParentPidFromEnvironment() -> int | None:
    rawParentPid = os.getenv("AI_VIDEO_PIPELINE_PARENT_PID")
    if not rawParentPid:
        return None

    try:
        return int(rawParentPid)
    except ValueError:
        logger.error("Invalid AI_VIDEO_PIPELINE_PARENT_PID value: %s", rawParentPid)
        return None


def watchParentProcess(parentPid: int) -> None:
    while True:
        if not isProcessAlive(parentPid):
            logger.info("Desktop parent process %s exited; stopping sidecar", parentPid)
            terminateCurrentProcess()
        time.sleep(1.0)


def isProcessAlive(processId: int) -> bool:
    if processId <= 0:
        return False

    if os.name == "nt":
        return isWindowsProcessAlive(processId)

    try:
        os.kill(processId, 0)
    except OSError:
        return False
    return True


def watchWindowsParentProcess(parentPid: int) -> None:
    import ctypes

    synchronize = 0x00100000
    infinite = 0xFFFFFFFF
    waitFailed = 0xFFFFFFFF
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(synchronize, False, parentPid)
    if not handle:
        logger.info(
            "Desktop parent process %s is not available; stopping sidecar", parentPid
        )
        terminateCurrentProcess()

    try:
        result = kernel32.WaitForSingleObject(handle, infinite)
    finally:
        kernel32.CloseHandle(handle)

    if result == waitFailed:
        logger.error(
            "Failed while waiting for desktop parent process %s; stopping sidecar",
            parentPid,
        )
    else:
        logger.info("Desktop parent process %s exited; stopping sidecar", parentPid)
    terminateCurrentProcess()


def isWindowsProcessAlive(processId: int) -> bool:
    import ctypes
    from ctypes import wintypes

    processQueryLimitedInformation = 0x1000
    stillActive = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetExitCodeProcess.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(processQueryLimitedInformation, False, processId)
    if not handle:
        return False

    exitCode = wintypes.DWORD()
    try:
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exitCode)):
            return False
        return exitCode.value == stillActive
    finally:
        kernel32.CloseHandle(handle)


def terminateCurrentProcess(exitCode: int = 0) -> NoReturn:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.TerminateProcess.restype = ctypes.c_int
        currentProcess = kernel32.GetCurrentProcess()
        kernel32.TerminateProcess(currentProcess, exitCode)
    os._exit(exitCode)


if __name__ == "__main__":
    runSidecar()
