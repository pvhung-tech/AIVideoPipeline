import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise RuntimeError("FFmpeg and FFprobe must be available on PATH.")

    with tempfile.TemporaryDirectory(
        prefix="phase8-rich-workflow-", ignore_cleanup_errors=True
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

        os.environ["APP_DATA_DIR"] = str(appDataPath)
        os.environ["FFMPEG_PATH"] = ffmpeg
        os.environ["LOCAL_MEDIA_LIBRARY_PATHS"] = str(libraryPath)
        os.environ["MEDIA_CACHE_MAX_FILE_SIZE_BYTES"] = str(50 * 1024 * 1024)

        from fastapi.testclient import TestClient

        from app.main import createApp

        with TestClient(createApp()) as client:
            project = unwrap(
                client.post(
                    "/api/projects",
                    json={
                        "name": "Phase 8 Rich Workflow",
                        "parentDirectory": str(projectParent),
                    },
                ),
                "create project",
            )
            imported = unwrap(
                client.post("/api/scripts/import", json={"path": str(scriptPath)}),
                "import SRT script",
            )
            scenes = unwrap(client.get("/api/scripts/scenes"), "list scenes")
            if scenes["sceneCount"] != 6:
                raise RuntimeError(f"Expected 6 scenes, found {scenes['sceneCount']}.")
            unwrap(
                client.put(
                    f"/api/scripts/scenes/{scenes['scenes'][2]['id']}",
                    json={"text": "Updated integration scene with a clearer visual cue."},
                ),
                "update scene text",
            )

            providers = unwrap(client.get("/api/media/providers"), "list providers")
            if "local" not in providers["providers"]:
                raise RuntimeError("Local provider is not registered.")

            cached = {
                name: unwrap(
                    client.post(
                        "/api/media/cache",
                        json={
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

            expectError(
                client.post(
                    "/api/media/cache",
                    json={
                        "providerId": "local",
                        "mediaId": "outside-library",
                        "sourceUri": (workspacePath / "outside.jpg").as_uri(),
                        "fileName": "outside.jpg",
                    },
                ),
                "INVALID_MEDIA_SOURCE",
                "reject outside-library media cache",
            )

            manifest = unwrap(client.get("/api/media/cache"), "load cache manifest")
            cacheEntryCount = len(manifest["entries"])
            if cacheEntryCount < 4:
                raise RuntimeError("Expected cached image, video, avatar, and audio.")

            timeline = unwrap(client.post("/api/timeline/generate"), "generate timeline")
            sceneIds = [scene["sceneId"] for scene in timeline["scenes"]]
            videoSceneId = sceneIds[1]
            for index, sceneId in enumerate(sceneIds):
                visual = cached["clip"] if index in (1, 4) else cached["image"]
                unwrap(
                    client.put(
                        f"/api/timeline/scenes/{sceneId}/media",
                        json={"contentHash": visual["contentHash"], "role": "broll"},
                    ),
                    f"assign broll scene {index + 1}",
                )
                if index in (0, 3):
                    unwrap(
                        client.put(
                            f"/api/timeline/scenes/{sceneId}/media",
                            json={
                                "contentHash": cached["avatar"]["contentHash"],
                                "role": "avatar",
                            },
                        ),
                        f"assign avatar scene {index + 1}",
                    )

            unwrap(
                client.put(
                    "/api/timeline/music",
                    json={"contentHash": cached["music"]["contentHash"], "volume": 0.25},
                ),
                "assign music",
            )
            expectError(
                client.put(
                    f"/api/timeline/scenes/{sceneIds[0]}/media",
                    json={"contentHash": cached["music"]["contentHash"], "role": "broll"},
                ),
                "UNSUPPORTED_CACHED_MEDIA",
                "reject audio as visual media",
            )
            expectError(
                client.put(
                    f"/api/timeline/scenes/{videoSceneId}/media-trim",
                    json={
                        "sourceStartMilliseconds": 0,
                        "sourceEndMilliseconds": 999_000,
                        "role": "broll",
                    },
                ),
                "INVALID_VIDEO_TRIM",
                "reject invalid video trim",
            )
            unwrap(
                client.put(
                    f"/api/timeline/scenes/{videoSceneId}/media-trim",
                    json={
                        "sourceStartMilliseconds": 0,
                        "sourceEndMilliseconds": 2_000,
                        "role": "broll",
                    },
                ),
                "apply valid video trim",
            )

            timeline = unwrap(client.get("/api/timeline"), "load timeline")
            if not timeline["audioClips"]:
                raise RuntimeError("Expected background music on the timeline.")
            preflight = unwrap(
                client.post(
                    "/api/render/preflight",
                    json={
                        "profileId": "draft",
                        "outputNameTemplate": "phase8-rich-{datetime}.mp4",
                    },
                ),
                "render preflight",
            )
            if preflight["ready"] is not True:
                raise RuntimeError(f"Render preflight failed: {json.dumps(preflight)}")

            job = unwrap(
                client.post(
                    "/api/render/jobs",
                    json={
                        "profileId": "draft",
                        "outputNameTemplate": "phase8-rich-{datetime}.mp4",
                    },
                ),
                "start render job",
            )
            completedJob = waitForJob(client, job["jobId"])
            outputPath = Path(str(completedJob["outputPath"]))
            if not outputPath.is_file() or outputPath.stat().st_size <= 0:
                raise RuntimeError(f"Rendered MP4 is missing or empty: {outputPath}")
            if not completedJob.get("preview"):
                raise RuntimeError("Completed render did not persist preview metadata.")

            reviewed = unwrap(
                client.post(
                    f"/api/render/jobs/{completedJob['jobId']}/review",
                    json={"status": "accepted", "note": "Phase 8 rich smoke accepted."},
                ),
                "review completed job",
            )
            if reviewed["review"]["status"] != "accepted":
                raise RuntimeError("Render review was not saved.")

            report = unwrap(
                client.post(
                    "/api/render/jobs/report",
                    json={"format": "json", "reviewStatus": "accepted"},
                ),
                "export render report",
            )
            bundle = unwrap(
                client.post(
                    "/api/render/jobs/report/bundle",
                    json={"format": "json", "reviewStatus": "accepted"},
                ),
                "export handoff bundle",
            )
            cleanupPreview = unwrap(
                client.post("/api/media/cache/cleanup", json={"dryRun": True}),
                "preview media cleanup",
            )
            reconcilePreview = unwrap(
                client.post("/api/media/cache/reconcile", json={"dryRun": True}),
                "preview media reconciliation",
            )

        print(
            json.dumps(
                {
                    "projectPath": project["path"],
                    "importedSceneCount": imported["sceneCount"],
                    "timelineScenes": len(timeline["scenes"]),
                    "cacheEntryCount": cacheEntryCount,
                    "outputPath": str(outputPath),
                    "outputSizeBytes": outputPath.stat().st_size,
                    "reviewStatus": reviewed["review"]["status"],
                    "reportPath": report["reportPath"],
                    "bundlePath": bundle["bundlePath"],
                    "cleanupDryRunEntries": cleanupPreview["remainingEntries"],
                    "reconcileOrphans": len(reconcilePreview["orphanFiles"]),
                },
                indent=2,
            )
        )


def createAssets(ffmpeg: Path, libraryPath: Path) -> dict[str, Path]:
    imagePath = libraryPath / "city-image.png"
    avatarPath = libraryPath / "avatar-overlay.png"
    videoPath = libraryPath / "city-clip.mp4"
    musicPath = libraryPath / "music-bed.wav"
    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x2f6f8f:s=640x360",
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
        "color=c=0xf2c94c:s=240x240",
        "-frames:v",
        "1",
        str(avatarPath),
    )
    run(
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=24:duration=3",
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
        "sine=frequency=440:duration=14",
        "-ac",
        "2",
        str(musicPath),
    )
    return {
        "image": imagePath,
        "avatar": avatarPath,
        "clip": videoPath,
        "music": musicPath,
    }


def buildSrt() -> str:
    cues = [
        ("00:00:00,000", "00:00:02,000", "Opening skyline establishes the story."),
        ("00:00:02,000", "00:00:04,000", "A short motion clip introduces the place."),
        ("00:00:04,000", "00:00:06,000", "Narration explains the main event."),
        ("00:00:06,000", "00:00:08,000", "Avatar overlay adds presenter context."),
        ("00:00:08,000", "00:00:10,000", "Second motion shot reinforces the detail."),
        ("00:00:10,000", "00:00:12,000", "Closing line prepares the final review."),
    ]
    blocks = [
        f"{index}\n{start} --> {end}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, start=1)
    ]
    return "\n".join(blocks)


def run(executable: Path, *args: str) -> None:
    completed = subprocess.run(
        (str(executable), *args),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {executable.name} {' '.join(args)}\n{completed.stderr}"
        )


def waitForJob(client: Any, jobId: str) -> Any:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        job = unwrap(client.get(f"/api/render/jobs/{jobId}"), "poll render job")
        if job["status"] == "completed":
            return job
        if job["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(f"Render job did not complete: {json.dumps(job)}")
        time.sleep(0.25)
    raise RuntimeError(f"Render job timed out: {jobId}")


def unwrap(response: Any, action: str) -> Any:
    payload = parseJson(response, action)
    if response.status_code >= 400 or not payload.get("success"):
        raise RuntimeError(f"{action} failed: {json.dumps(payload)}")
    return payload["data"]


def expectError(response: Any, code: str, action: str) -> None:
    payload = parseJson(response, action)
    actualCode = (payload.get("error") or {}).get("code")
    if response.status_code < 400 or actualCode != code:
        raise RuntimeError(
            f"{action} expected {code}, got {response.status_code}: {json.dumps(payload)}"
        )


def parseJson(response: Any, action: str) -> Any:
    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError(f"{action} did not return JSON: {response.text}") from error


if __name__ == "__main__":
    main()
