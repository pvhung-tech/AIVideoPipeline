import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise RuntimeError("FFmpeg and FFprobe must be available on PATH.")

    with tempfile.TemporaryDirectory(
        prefix="e2e-workflow-smoke-", ignore_cleanup_errors=True
    ) as workspace:
        workspacePath = Path(workspace)
        appDataPath = workspacePath / "app-data"
        projectParent = workspacePath / "projects"
        projectParent.mkdir(parents=True, exist_ok=True)
        scriptPath = workspacePath / "input.txt"
        scriptPath.write_text(
            "Opening scene for a short workflow smoke test.\n\n"
            "Closing scene with subtitles and a quick render check.\n",
            encoding="utf-8",
        )

        os.environ["APP_DATA_DIR"] = str(appDataPath)
        os.environ["FFMPEG_PATH"] = ffmpeg

        from fastapi.testclient import TestClient

        from app.main import createApp

        with TestClient(createApp()) as client:
            project = unwrap(
                client.post(
                    "/api/projects",
                    json={
                        "name": "E2E Workflow Smoke",
                        "parentDirectory": str(projectParent),
                    },
                ),
                "create project",
            )
            imported = unwrap(
                client.post("/api/scripts/import", json={"path": str(scriptPath)}),
                "import script",
            )
            scenes = unwrap(client.get("/api/scripts/scenes"), "list scenes")
            timeline = unwrap(
                client.post("/api/timeline/generate"), "generate timeline"
            )
            preflight = unwrap(
                client.post(
                    "/api/render/preflight",
                    json={
                        "profileId": "draft",
                        "outputNameTemplate": "e2e-smoke-{datetime}.mp4",
                    },
                ),
                "render preflight",
            )
            if preflight["ready"] is not True:
                raise RuntimeError(f"Render preflight failed: {json.dumps(preflight)}")
            rendered = unwrap(
                client.post(
                    "/api/render",
                    json={
                        "profileId": "draft",
                        "outputNameTemplate": "e2e-smoke-{datetime}.mp4",
                    },
                ),
                "render draft mp4",
            )
        outputPath = Path(str(rendered["outputPath"]))
        if not outputPath.is_file() or outputPath.stat().st_size <= 0:
            raise RuntimeError(f"Rendered MP4 is missing or empty: {outputPath}")

        print(
            json.dumps(
                {
                    "projectPath": project["path"],
                    "sceneCount": scenes["sceneCount"],
                    "importedSceneCount": imported["sceneCount"],
                    "timelineScenes": len(timeline["scenes"]),
                    "outputPath": str(outputPath),
                    "outputSizeBytes": outputPath.stat().st_size,
                },
                indent=2,
            )
        )


def unwrap(response: Any, action: str) -> Any:
    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError(f"{action} did not return JSON: {response.text}") from error
    if response.status_code >= 400 or not payload.get("success"):
        raise RuntimeError(f"{action} failed: {json.dumps(payload)}")
    return payload["data"]


if __name__ == "__main__":
    main()
