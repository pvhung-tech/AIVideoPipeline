import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

T = TypeVar("T")


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise RuntimeError("FFmpeg and FFprobe must be available on PATH.")

    benchmark = Phase9Benchmark(Path(ffmpeg))
    childScenario = scenarioFromEnvironment()
    if childScenario is not None:
        result = benchmark.runScenario(childScenario)
    else:
        result = runMatrixSubprocesses(defaultScenarios())
    outputPath = writeResult(result)
    result["benchmarkReportPath"] = str(outputPath)
    outputPath.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


class Phase9Benchmark:
    def __init__(self, ffmpeg: Path) -> None:
        self.ffmpeg = ffmpeg
        self.timings: dict[str, float] = {}

    def runScenario(self, scenario: "BenchmarkScenario") -> dict[str, Any]:
        startedAt = time.time()
        self.timings = {}
        with tempfile.TemporaryDirectory(
            prefix="phase9-performance-", ignore_cleanup_errors=True
        ) as workspace:
            workspacePath = Path(workspace)
            libraryPath = workspacePath / "library"
            appDataPath = workspacePath / "app-data"
            projectParent = workspacePath / "projects"
            libraryPath.mkdir(parents=True, exist_ok=True)
            projectParent.mkdir(parents=True, exist_ok=True)

            assets = self.measure(
                "setup.generate_assets",
                lambda: createAssets(libraryPath, scenario),
            )
            extraAssets = self.measure(
                "setup.generate_extra_cache_assets",
                lambda: createExtraCacheAssets(libraryPath, scenario.extraCacheEntries),
            )
            scriptPath = workspacePath / "episode.srt"
            scriptPath.write_text(
                buildSrt(scenario.sceneCount, scenario.sceneDurationSeconds),
                encoding="utf-8",
            )

            previousEnvironment = captureEnvironment()
            os.environ["APP_DATA_DIR"] = str(appDataPath)
            os.environ["FFMPEG_PATH"] = str(self.ffmpeg)
            os.environ["LOCAL_MEDIA_LIBRARY_PATHS"] = str(libraryPath)
            os.environ["MEDIA_CACHE_MAX_FILE_SIZE_BYTES"] = str(
                mediaCacheLimitBytes(scenario)
            )
            os.environ["RENDER_SUBTITLE_MODE"] = subtitleModeForVariant(
                scenario.renderVariant
            )
            if isLiveProviderCorpusVariant(scenario.renderVariant):
                os.environ.setdefault("DVIDS_VIDEO_QUALITY", "720p")
                os.environ.setdefault(
                    "DVIDS_VIDEO_MAX_FILE_SIZE_BYTES", str(80 * 1024 * 1024)
                )

            try:
                from fastapi.testclient import TestClient

                from app.main import createApp

                app = self.measure("backend.create_app", createApp)
                with self.measuredContext("backend.test_client"):
                    client = TestClient(app)
                    client.__enter__()
                try:
                    result = self.runWorkflow(
                        client, projectParent, scriptPath, assets, extraAssets, scenario
                    )
                finally:
                    with self.measuredContext("backend.test_client_close"):
                        client.__exit__(None, None, None)
            finally:
                restoreEnvironment(previousEnvironment)

            result["workspaceSummary"] = {
                "assetCount": len(assets),
                "extraCacheAssetCount": len(extraAssets),
                "generatedAssetBytes": sum(
                    path.stat().st_size for path in (*assets.values(), *extraAssets)
                ),
                "artifactsRetained": False,
            }
            result["scenario"] = scenario.toDictionary()
            result["startedAtEpochSeconds"] = startedAt
            result["durationSeconds"] = round(time.time() - startedAt, 3)
            result["timings"] = self.timings
            result["rollups"] = rollupTimings(self.timings)
            return result

    def runWorkflow(
        self,
        client: Any,
        projectParent: Path,
        scriptPath: Path,
        assets: dict[str, Path],
        extraAssets: tuple[Path, ...],
        scenario: "BenchmarkScenario",
    ) -> dict[str, Any]:
        project = self.measure(
            "workflow.project_create",
            lambda: unwrap(
                client.post(
                    "/api/projects",
                    json={
                        "name": "Phase 9 Performance Baseline",
                        "parentDirectory": str(projectParent),
                    },
                ),
                "create project",
            ),
        )
        imported = self.measure(
            "workflow.script_import",
            lambda: unwrap(
                client.post("/api/scripts/import", json={"path": str(scriptPath)}),
                "import SRT script",
            ),
        )
        scenes = self.measure(
            "workflow.scene_list",
            lambda: unwrap(client.get("/api/scripts/scenes"), "list scenes"),
        )
        providers = self.measure(
            "workflow.provider_list",
            lambda: unwrap(client.get("/api/media/providers"), "list providers"),
        )
        if "local" not in providers["providers"]:
            raise RuntimeError("Local provider is not registered.")

        cached: dict[str, dict[str, Any]] = {}
        for name, path in assets.items():
            cached[name] = self.measure(
                f"cache.write_{name}",
                partial(cacheLocalMedia, client, name, path),
            )
        liveCorpus = self.measure(
            "cache.write_live_provider_corpus",
            lambda: cacheLiveProviderCorpus(client, scenario),
        )
        cached.update(liveCorpus["cached"])
        extraCached = self.measure(
            "cache.write_extra_entries",
            lambda: cacheExtraMedia(client, extraAssets),
        )
        duplicate = self.measure(
            "cache.duplicate_hit",
            lambda: unwrap(
                client.post(
                    "/api/media/cache",
                    json={
                        "providerId": "local",
                        "mediaId": "image-duplicate",
                        "sourceUri": assets["image"].as_uri(),
                        "fileName": assets["image"].name,
                    },
                ),
                "cache duplicate image",
            ),
        )
        manifest = self.measure(
            "cache.manifest_load",
            lambda: unwrap(client.get("/api/media/cache"), "load cache manifest"),
        )

        timeline = self.measure(
            "workflow.timeline_generate",
            lambda: unwrap(client.post("/api/timeline/generate"), "generate timeline"),
        )
        self.measure(
            "workflow.timeline_assign_media",
            lambda: assignTimelineMedia(client, timeline, cached, scenario),
        )
        timeline = self.measure(
            "workflow.timeline_load",
            lambda: unwrap(client.get("/api/timeline"), "load timeline"),
        )

        preflight = self.measure(
            "render.preflight",
            lambda: unwrap(
                client.post(
                    "/api/render/preflight",
                    json=renderPayload(scenario, "phase9-baseline-{datetime}.mp4"),
                ),
                "render preflight",
            ),
        )
        if preflight["ready"] is not True:
            raise RuntimeError(f"Render preflight failed: {json.dumps(preflight)}")

        job = self.measure(
            "render.queue_job",
            lambda: unwrap(
                client.post(
                    "/api/render/jobs",
                    json=renderPayload(scenario, "phase9-baseline-{datetime}.mp4"),
                ),
                "start render job",
            ),
        )
        completedJob = self.measure(
            "render.wait_for_completion",
            lambda: waitForJob(client, job["jobId"], waitTimeoutSeconds(scenario)),
        )
        outputPath = Path(str(completedJob["outputPath"]))
        if not outputPath.is_file() or outputPath.stat().st_size <= 0:
            raise RuntimeError(f"Rendered MP4 is missing or empty: {outputPath}")
        warmupJobId: str | None = None
        warmupOutputPath: str | None = None
        if scenario.renderVariant == "prerendered_subtitles_cached":
            warmupJobId = str(completedJob["jobId"])
            warmupOutputPath = str(outputPath)
            cachedJob = self.measure(
                "render.cached_queue_job",
                lambda: unwrap(
                    client.post(
                        "/api/render/jobs",
                        json=renderPayload(scenario, "phase9-cached-{datetime}.mp4"),
                    ),
                    "start cached render job",
                ),
            )
            completedJob = self.measure(
                "render.cached_wait_for_completion",
                lambda: waitForJob(
                    client, cachedJob["jobId"], waitTimeoutSeconds(scenario)
                ),
            )
            outputPath = Path(str(completedJob["outputPath"]))
            if not outputPath.is_file() or outputPath.stat().st_size <= 0:
                raise RuntimeError(f"Cached rendered MP4 is missing: {outputPath}")

        report = self.measure(
            "render.report_json",
            lambda: unwrap(
                client.post("/api/render/jobs/report", json={"format": "json"}),
                "export render report",
            ),
        )
        bundle = self.measure(
            "render.bundle_json",
            lambda: unwrap(
                client.post("/api/render/jobs/report/bundle", json={"format": "json"}),
                "export handoff bundle",
            ),
        )
        cleanup = self.measure(
            "cache.cleanup_dry_run",
            lambda: unwrap(
                client.post("/api/media/cache/cleanup", json={"dryRun": True}),
                "preview media cleanup",
            ),
        )
        reconcile = self.measure(
            "cache.reconcile_dry_run",
            lambda: unwrap(
                client.post("/api/media/cache/reconcile", json={"dryRun": True}),
                "preview media reconciliation",
            ),
        )

        return {
            "benchmark": "phase9.workflow_render_cache.scenario",
            "scenarioName": scenario.name,
            "projectPath": project["path"],
            "sceneCount": scenes["sceneCount"],
            "timelineDurationSeconds": scenario.sceneCount
            * scenario.sceneDurationSeconds,
            "importedSceneCount": imported["sceneCount"],
            "timelineScenes": len(timeline["scenes"]),
            "cacheEntryCount": len(manifest["entries"]),
            "extraCacheEntryCount": len(extraCached),
            "duplicateCacheHit": bool(duplicate["duplicate"]),
            "cacheDiagnosticsSummary": summarizeCachedMediaDiagnostics(
                (*cached.values(), *extraCached, duplicate)
            ),
            "outputPath": str(outputPath),
            "outputSizeBytes": outputPath.stat().st_size,
            "renderJobId": completedJob["jobId"],
            "warmupRenderJobId": warmupJobId,
            "warmupOutputPath": warmupOutputPath,
            "renderStatus": completedJob["status"],
            "renderStatusSamples": completedJob.get("_statusSamples", ()),
            "renderStatusSummary": summarizeStatusSamples(
                completedJob.get("_statusSamples", ())
            ),
            "renderDiagnostics": completedJob.get("diagnostics"),
            "previewAvailable": bool(completedJob.get("preview")),
            "reportPath": report["reportPath"],
            "bundlePath": bundle["bundlePath"],
            "cleanupDryRunRemoved": cleanup["removedCount"],
            "reconcileOrphans": len(reconcile["orphanFiles"]),
            "liveCorpus": liveCorpus["summary"],
        }

    def measure(self, name: str, action: Callable[[], T]) -> T:
        started = time.perf_counter()
        try:
            return action()
        finally:
            self.timings[name] = round(time.perf_counter() - started, 4)

    def measuredContext(self, name: str) -> "MeasuredContext":
        return MeasuredContext(self.timings, name)


class MeasuredContext:
    def __init__(self, timings: dict[str, float], name: str) -> None:
        self.timings = timings
        self.name = name
        self.started = 0.0

    def __enter__(self) -> None:
        self.started = time.perf_counter()

    def __exit__(self, *_args: object) -> None:
        self.timings[self.name] = round(time.perf_counter() - self.started, 4)


@dataclass(frozen=True)
class BenchmarkScenario:
    name: str
    sceneCount: int
    extraCacheEntries: int
    renderVariant: str = "mixed"
    sceneDurationSeconds: int = 2

    def toDictionary(self) -> dict[str, int | str]:
        return {
            "name": self.name,
            "sceneCount": self.sceneCount,
            "extraCacheEntries": self.extraCacheEntries,
            "renderVariant": self.renderVariant,
            "sceneDurationSeconds": self.sceneDurationSeconds,
        }


def defaultScenarios() -> tuple[BenchmarkScenario, ...]:
    return (
        BenchmarkScenario("baseline_6_scenes_4_cache", 6, 0),
        BenchmarkScenario("scene_scale_12_scenes", 12, 0),
        BenchmarkScenario("scene_scale_24_scenes", 24, 0),
        BenchmarkScenario("cache_scale_28_entries", 6, 24),
        BenchmarkScenario("mixed_24_scenes_28_cache", 24, 24),
        BenchmarkScenario("variant_24_drawtext_subtitles", 24, 0, "drawtext_subtitles"),
        BenchmarkScenario("variant_24_no_subtitles", 24, 0, "no_subtitles"),
        BenchmarkScenario("variant_24_sendcmd_subtitles", 24, 0, "sendcmd_subtitles"),
        BenchmarkScenario("variant_24_ass_subtitles", 24, 0, "ass_subtitles"),
        BenchmarkScenario(
            "variant_24_prerendered_subtitles", 24, 0, "prerendered_subtitles"
        ),
        BenchmarkScenario(
            "variant_24_prerendered_subtitles_cached",
            24,
            0,
            "prerendered_subtitles_cached",
        ),
        BenchmarkScenario("variant_24_no_avatar", 24, 0, "no_avatar"),
        BenchmarkScenario("variant_24_image_only", 24, 0, "image_only"),
        BenchmarkScenario("variant_24_video_only", 24, 0, "video_only"),
        BenchmarkScenario("variant_24_pre_scaled_media", 24, 0, "pre_scaled"),
        BenchmarkScenario("variant_24_fast_preview_profile", 24, 0, "fast_preview"),
    )


def scenarioFromEnvironment() -> BenchmarkScenario | None:
    name = os.environ.get("PHASE9_PERF_SCENARIO_NAME")
    if not name:
        return None
    return BenchmarkScenario(
        name,
        int(os.environ["PHASE9_PERF_SCENARIO_SCENES"]),
        int(os.environ["PHASE9_PERF_SCENARIO_EXTRA_CACHE"]),
        os.environ.get("PHASE9_PERF_SCENARIO_VARIANT", "mixed"),
        int(os.environ.get("PHASE9_PERF_SCENARIO_DURATION_SECONDS", "2")),
    )


def runMatrixSubprocesses(scenarios: tuple[BenchmarkScenario, ...]) -> dict[str, Any]:
    startedAt = time.time()
    root = Path(__file__).resolve().parents[1]
    outputDirectory = root / ".tmp" / "phase9-performance-scenarios"
    outputDirectory.mkdir(parents=True, exist_ok=True)
    results = [
        runScenarioSubprocess(scenario, outputDirectory) for scenario in scenarios
    ]
    return {
        "benchmark": "phase9.workflow_render_cache.matrix",
        "startedAtEpochSeconds": startedAt,
        "durationSeconds": round(time.time() - startedAt, 3),
        "scenarioCount": len(results),
        "scenarios": results,
        "comparison": compareScenarios(results),
    }


def runScenarioSubprocess(
    scenario: BenchmarkScenario, outputDirectory: Path
) -> dict[str, Any]:
    outputPath = outputDirectory / f"{scenario.name}.json"
    environment = os.environ.copy()
    environment["PHASE9_PERF_SCENARIO_NAME"] = scenario.name
    environment["PHASE9_PERF_SCENARIO_SCENES"] = str(scenario.sceneCount)
    environment["PHASE9_PERF_SCENARIO_EXTRA_CACHE"] = str(scenario.extraCacheEntries)
    environment["PHASE9_PERF_SCENARIO_VARIANT"] = scenario.renderVariant
    environment["PHASE9_PERF_SCENARIO_DURATION_SECONDS"] = str(
        scenario.sceneDurationSeconds
    )
    environment["PHASE9_PERF_OUTPUT"] = str(outputPath)
    completed = subprocess.run(
        (sys.executable, str(Path(__file__).resolve())),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Phase 9 benchmark scenario failed: "
            f"{scenario.name}\n{completed.stdout}\n{completed.stderr}"
        )
    return json.loads(outputPath.read_text(encoding="utf-8"))


def createAssets(libraryPath: Path, scenario: BenchmarkScenario) -> dict[str, Path]:
    imagePath = libraryPath / "city-image.png"
    avatarPath = libraryPath / "avatar-overlay.png"
    videoPath = libraryPath / "city-clip.mp4"
    timelineDurationSeconds = scenario.sceneCount * scenario.sceneDurationSeconds
    musicPath = libraryPath / (
        "music-bed.mp3" if timelineDurationSeconds > 60 else "music-bed.wav"
    )
    brollSize = "854x480" if scenario.renderVariant == "pre_scaled" else "640x360"
    sourceVideoDurationSeconds = max(3, scenario.sceneDurationSeconds)
    musicDurationSeconds = max(14, timelineDurationSeconds + 2)
    if isRealisticMediaVariant(scenario.renderVariant):
        sourceVideoDurationSeconds = max(60, scenario.sceneDurationSeconds * 6)
    runFfmpeg(
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x2f6f8f:s={brollSize}",
        "-frames:v",
        "1",
        str(imagePath),
    )
    runFfmpeg(
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0xf2c94c:s=240x240",
        "-frames:v",
        "1",
        str(avatarPath),
    )
    if isRealisticMediaVariant(scenario.renderVariant):
        videoAssets = createLongVideoAssets(
            libraryPath, brollSize, sourceVideoDurationSeconds
        )
    else:
        runFfmpeg(
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={brollSize}:rate=24:duration={sourceVideoDurationSeconds}",
            "-pix_fmt",
            "yuv420p",
            str(videoPath),
        )
        videoAssets = {"clip": videoPath}
    runFfmpeg(
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={musicDurationSeconds}",
        "-ac",
        "2",
        *musicEncodingArguments(musicPath),
        str(musicPath),
    )
    return {
        "image": imagePath,
        "avatar": avatarPath,
        "music": musicPath,
        **videoAssets,
    }


def createLongVideoAssets(
    libraryPath: Path, brollSize: str, durationSeconds: int
) -> dict[str, Path]:
    assets: dict[str, Path] = {}
    colors = ("0x345995", "0x03cea4", "0xfb4d3d", "0xca1551", "0xfde74c")
    for index, color in enumerate(colors):
        name = "clip" if index == 0 else f"clip_{index}"
        path = libraryPath / f"provider-style-{name}.mp4"
        runFfmpeg(
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={brollSize}:r=30:d={durationSeconds}",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=s={brollSize}:r=30:d={durationSeconds}",
            "-filter_complex",
            "[0:v][1:v]blend=all_mode=overlay:all_opacity=0.28,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            str(path),
        )
        assets[name] = path
    return assets


def mediaCacheLimitBytes(scenario: BenchmarkScenario) -> int:
    timelineDurationSeconds = scenario.sceneCount * scenario.sceneDurationSeconds
    if isLiveProviderCorpusVariant(scenario.renderVariant):
        return max(120 * 1024 * 1024, timelineDurationSeconds * 768 * 1024)
    return max(50 * 1024 * 1024, timelineDurationSeconds * 512 * 1024)


def musicEncodingArguments(path: Path) -> tuple[str, ...]:
    if path.suffix.lower() == ".mp3":
        return ("-codec:a", "libmp3lame", "-q:a", "4")
    return ()


def createExtraCacheAssets(libraryPath: Path, count: int) -> tuple[Path, ...]:
    assets = []
    for index in range(count):
        path = libraryPath / f"extra-cache-{index:03d}.bmp"
        path.write_bytes(buildBmp(index))
        assets.append(path)
    return tuple(assets)


def buildBmp(index: int) -> bytes:
    width = 2
    height = 2
    rowSize = 8
    pixelDataSize = rowSize * height
    fileSize = 54 + pixelDataSize
    color = bytes(((index * 37) % 256, (index * 73) % 256, (index * 109) % 256))
    row = color * width + b"\x00\x00"
    pixelData = row * height
    return (
        b"BM"
        + fileSize.to_bytes(4, "little")
        + b"\x00\x00\x00\x00"
        + (54).to_bytes(4, "little")
        + (40).to_bytes(4, "little")
        + width.to_bytes(4, "little")
        + height.to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (24).to_bytes(2, "little")
        + (0).to_bytes(4, "little")
        + pixelDataSize.to_bytes(4, "little")
        + (2835).to_bytes(4, "little")
        + (2835).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + pixelData
    )


def assignTimelineMedia(
    client: Any,
    timeline: dict[str, Any],
    cached: dict[str, dict[str, Any]],
    scenario: BenchmarkScenario,
) -> None:
    sceneIds = [scene["sceneId"] for scene in timeline["scenes"]]
    assignments: list[dict[str, str]] = []
    for index, sceneId in enumerate(sceneIds):
        visual = visualForScene(index, cached, scenario.renderVariant)
        assignments.append(
            {
                "sceneId": sceneId,
                "contentHash": visual["contentHash"],
                "role": "broll",
            }
        )
        if scenario.renderVariant != "no_avatar" and index in (0, 3):
            assignments.append(
                {
                    "sceneId": sceneId,
                    "contentHash": cached["avatar"]["contentHash"],
                    "role": "avatar",
                }
            )
    unwrap(
        client.put(
            "/api/timeline/media-assignments", json={"assignments": assignments}
        ),
        "assign timeline visual media",
    )
    if scenario.renderVariant == "no_subtitles":
        timeline = unwrap(
            client.get("/api/timeline"), "load timeline for subtitle trim"
        )
        for scene in timeline["scenes"]:
            scene["subtitleClips"] = []
        unwrap(
            client.put("/api/timeline", json=timeline),
            "save timeline without subtitles",
        )
    unwrap(
        client.put(
            "/api/timeline/music",
            json={"contentHash": cached["music"]["contentHash"], "volume": 0.25},
        ),
        "assign music",
    )


def visualForScene(
    index: int, cached: dict[str, dict[str, Any]], renderVariant: str
) -> dict[str, Any]:
    if renderVariant == "image_only":
        return cached["image"]
    if renderVariant == "video_only":
        return cached["clip"]
    if isLiveProviderCorpusVariant(renderVariant):
        videoNames = sorted(name for name in cached if name.startswith("live_video_"))
        if videoNames:
            return cached[videoNames[index % len(videoNames)]]
    if isRealisticMediaVariant(renderVariant):
        videoNames = ("clip", "clip_1", "clip_2", "clip_3", "clip_4")
        return cached[videoNames[index % len(videoNames)]]
    return cached["clip"] if index in (1, 4) else cached["image"]


def renderPayload(
    scenario: BenchmarkScenario, outputNameTemplate: str
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "profileId": profileIdForVariant(scenario.renderVariant),
        "outputNameTemplate": outputNameTemplate,
    }
    preset = encoderPresetForVariant(scenario.renderVariant)
    if preset is not None:
        payload["encoderPreset"] = preset
    return payload


def profileIdForVariant(renderVariant: str) -> str:
    if renderVariant == "fast_preview":
        return "fast_preview"
    if renderVariant in {"standard", "realistic_standard"}:
        return "standard"
    if renderVariant == "real_provider_standard":
        return "standard"
    if renderVariant == "real_provider_high_quality":
        return "high_quality"
    return "draft"


def encoderPresetForVariant(renderVariant: str) -> str | None:
    if renderVariant == "draft_superfast":
        return "superfast"
    if renderVariant == "draft_ultrafast":
        return "ultrafast"
    return None


def cacheLocalMedia(client: Any, mediaName: str, path: Path) -> dict[str, Any]:
    return unwrap(
        client.post(
            "/api/media/cache",
            json={
                "providerId": "local",
                "mediaId": mediaName,
                "sourceUri": path.as_uri(),
                "fileName": path.name,
            },
        ),
        f"cache {mediaName}",
    )


def cacheExtraMedia(client: Any, paths: tuple[Path, ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        cacheLocalMedia(client, f"extra-cache-{index:03d}", path)
        for index, path in enumerate(paths)
    )


def cacheLiveProviderCorpus(
    client: Any, scenario: BenchmarkScenario
) -> dict[str, Any]:
    if not isLiveProviderCorpusVariant(scenario.renderVariant):
        return {"cached": {}, "summary": {"enabled": False}}
    providers = tuple(
        provider.strip().lower()
        for provider in os.environ.get(
            "PHASE9_PERF_LIVE_PROVIDERS", "pexels,pixabay,wikimedia,dvids"
        ).split(",")
        if provider.strip()
    )
    query = os.environ.get("PHASE9_PERF_LIVE_QUERY", "city documentary")
    targetVideos = int(os.environ.get("PHASE9_PERF_LIVE_TARGET_VIDEOS", "4"))
    targetImages = int(os.environ.get("PHASE9_PERF_LIVE_TARGET_IMAGES", "2"))
    minVideoDurationMilliseconds = scenario.sceneDurationSeconds * 1000
    cached: dict[str, dict[str, Any]] = {}
    selected: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    measurements: list[dict[str, Any]] = []
    sourceReportPath = os.environ.get("PHASE9_PERF_LIVE_CORPUS_SOURCE")
    if sourceReportPath:
        return cacheLiveProviderCorpusFromReport(
            client, Path(sourceReportPath), minVideoDurationMilliseconds
        )
    cacheLiveItems(
        client,
        providers,
        query,
        "video",
        targetVideos,
        "live_video",
        cached,
        selected,
        errors,
        minVideoDurationMilliseconds,
        measurements,
    )
    cacheLiveItems(
        client,
        providers,
        query,
        "image",
        targetImages,
        "live_image",
        cached,
        selected,
        errors,
        0,
        measurements,
    )
    if countCachedPrefix(cached, "live_video") < 2:
        raise RuntimeError(
            "Live provider corpus requires at least two cached videos; "
            f"cached {len(cached)} items with errors: {json.dumps(errors)}"
        )
    return {
        "cached": cached,
        "summary": {
            "enabled": True,
            "query": query,
            "providers": providers,
            "selected": selected,
            "errors": errors,
            "measurements": measurements,
            "measurementSummary": summarizeMediaMeasurements(measurements),
        },
    }


def cacheLiveProviderCorpusFromReport(
    client: Any, sourceReportPath: Path, minVideoDurationMilliseconds: int
) -> dict[str, Any]:
    report = json.loads(sourceReportPath.read_text(encoding="utf-8"))
    sourceSummary = report.get("liveCorpus") or {}
    cached: dict[str, dict[str, Any]] = {}
    selected: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    measurements: list[dict[str, Any]] = []
    for item in sourceSummary.get("selected", ()):
        name = str(item["name"])
        try:
            started = time.perf_counter()
            cachedItem = cacheSearchItem(client, name, item)
            measurements.append(
                cacheMeasurement(
                    "cache_write",
                    item,
                    name,
                    time.perf_counter() - started,
                    cachedItem,
                )
            )
            measurements.append(refreshMediaWorkspaceState(client, name))
            if item.get("mediaType") == "video" and not cachedVideoHasMinimumDuration(
                client, cachedItem, minVideoDurationMilliseconds
            ):
                errors.append(
                    {
                        "providerId": str(item.get("providerId")),
                        "mediaType": "video",
                        "mediaId": str(item.get("mediaId") or item.get("id")),
                        "error": "Cached video is shorter than the scene.",
                    }
                )
                continue
            cached[name] = cachedItem
            selected.append(item)
        except RuntimeError as error:
            errors.append(
                {
                    "providerId": str(item.get("providerId")),
                    "mediaType": str(item.get("mediaType")),
                    "mediaId": str(item.get("mediaId") or item.get("id")),
                    "error": str(error),
                }
            )
    if countCachedPrefix(cached, "live_video") < 2:
        raise RuntimeError(
            "Live provider corpus source did not provide two usable videos: "
            f"{json.dumps(errors)}"
        )
    return {
        "cached": cached,
        "summary": {
            "enabled": True,
            "sourceReportPath": str(sourceReportPath),
            "selected": selected,
            "errors": errors,
            "measurements": measurements,
            "measurementSummary": summarizeMediaMeasurements(measurements),
        },
    }


def cacheLiveItems(
    client: Any,
    providers: tuple[str, ...],
    query: str,
    mediaType: str,
    targetCount: int,
    namePrefix: str,
    cached: dict[str, dict[str, Any]],
    selected: list[dict[str, Any]],
    errors: list[dict[str, str]],
    minDurationMilliseconds: int,
    measurements: list[dict[str, Any]],
) -> None:
    for provider in providers:
        if countCachedPrefix(cached, namePrefix) >= targetCount:
            return
        try:
            started = time.perf_counter()
            page = unwrap(
                client.get(
                    "/api/media/search",
                    params={
                        "query": query,
                        "providerId": provider,
                        "mediaType": mediaType,
                        "limit": 10,
                    },
                ),
                f"search {provider} {mediaType}",
            )
            measurements.append(
                {
                    "phase": "provider_search",
                    "providerId": provider,
                    "mediaType": mediaType,
                    "elapsedSeconds": round(time.perf_counter() - started, 4),
                    "itemCount": len(page.get("items", ())),
                    "providerErrorCount": len(page.get("providerErrors", ())),
                }
            )
        except RuntimeError as error:
            errors.append(
                {"providerId": provider, "mediaType": mediaType, "error": str(error)}
            )
            continue
        for item in page.get("items", ()):
            if item.get("mediaType") != mediaType:
                continue
            name = f"{namePrefix}_{countCachedPrefix(cached, namePrefix)}"
            try:
                started = time.perf_counter()
                cachedItem = cacheSearchItem(client, name, item)
                measurements.append(
                    cacheMeasurement(
                        "cache_write",
                        item,
                        name,
                        time.perf_counter() - started,
                        cachedItem,
                    )
                )
                measurements.append(refreshMediaWorkspaceState(client, name))
                if mediaType == "video" and not cachedVideoHasMinimumDuration(
                    client, cachedItem, minDurationMilliseconds
                ):
                    errors.append(
                        {
                            "providerId": str(item.get("providerId")),
                            "mediaType": mediaType,
                            "mediaId": str(item.get("id")),
                            "error": "Cached video is shorter than the scene.",
                        }
                    )
                    continue
                cached[name] = cachedItem
                selected.append(
                    {
                        "name": name,
                        "providerId": item.get("providerId"),
                        "mediaId": item.get("id"),
                        "mediaType": item.get("mediaType"),
                        "title": item.get("title"),
                        "sourceUri": item.get("sourceUri"),
                    }
                )
            except RuntimeError as error:
                errors.append(
                    {
                        "providerId": str(item.get("providerId")),
                        "mediaType": mediaType,
                        "mediaId": str(item.get("id")),
                        "error": str(error),
                    }
                )
                continue
            if countCachedPrefix(cached, namePrefix) >= targetCount:
                return


def countCachedPrefix(cached: dict[str, dict[str, Any]], prefix: str) -> int:
    return sum(1 for key in cached if key.startswith(f"{prefix}_"))


def cacheSearchItem(
    client: Any, mediaName: str, item: dict[str, Any]
) -> dict[str, Any]:
    sourceUri = str(item["sourceUri"])
    mediaId = str(item.get("id") or item.get("mediaId"))
    return unwrap(
        client.post(
            "/api/media/cache",
            json={
                "providerId": item["providerId"],
                "mediaId": mediaId,
                "sourceUri": sourceUri,
                "fileName": fileNameForSearchItem(mediaName, sourceUri),
            },
        ),
        f"cache live provider media {mediaName}",
    )


def cacheMeasurement(
    phase: str,
    item: dict[str, Any],
    mediaName: str,
    elapsedSeconds: float,
    cachedItem: dict[str, Any],
) -> dict[str, Any]:
    diagnostics = cachedItem.get("diagnostics") or {}
    return {
        "phase": phase,
        "name": mediaName,
        "providerId": item.get("providerId"),
        "mediaType": item.get("mediaType"),
        "mediaId": item.get("id") or item.get("mediaId"),
        "elapsedSeconds": round(elapsedSeconds, 4),
        "sizeBytes": cachedItem.get("sizeBytes"),
        "duplicate": bool(cachedItem.get("duplicate")),
        "diagnostics": diagnostics,
    }


def refreshMediaWorkspaceState(client: Any, mediaName: str) -> dict[str, Any]:
    started = time.perf_counter()
    manifestStarted = time.perf_counter()
    manifest = unwrap(client.get("/api/media/cache"), "refresh media cache manifest")
    manifestSeconds = time.perf_counter() - manifestStarted
    assetsStarted = time.perf_counter()
    assets = unwrap(client.get("/api/timeline/media-assets"), "refresh media assets")
    assetsSeconds = time.perf_counter() - assetsStarted
    return {
        "phase": "ui_refresh",
        "name": mediaName,
        "elapsedSeconds": round(time.perf_counter() - started, 4),
        "manifestSeconds": round(manifestSeconds, 4),
        "timelineAssetsSeconds": round(assetsSeconds, 4),
        "cacheEntryCount": len(manifest.get("entries", ())),
        "assetCount": len(assets.get("assets", ())),
    }


def summarizeMediaMeasurements(
    measurements: list[dict[str, Any]],
) -> dict[str, Any]:
    phases = sorted({str(item.get("phase")) for item in measurements})
    summary: dict[str, Any] = {
        "count": len(measurements),
        "byPhase": {
            phase: summarizeElapsed(
                [
                    float(item.get("elapsedSeconds") or 0)
                    for item in measurements
                    if item.get("phase") == phase
                ]
            )
            for phase in phases
        },
    }
    cacheDiagnostics = [
        item.get("diagnostics") or {}
        for item in measurements
        if item.get("phase") == "cache_write"
    ]
    summary["cacheDiagnostics"] = {
        field: round(sum(float(item.get(field) or 0) for item in cacheDiagnostics), 4)
        for field in (
            "sourceTransferSeconds",
            "sourceHashSeconds",
            "sourceFileWriteSeconds",
            "duplicateCheckSeconds",
            "fingerprintSeconds",
            "metadataSeconds",
            "manifestSeconds",
            "totalSeconds",
        )
    }
    summary["cacheDiagnostics"]["fingerprintDeferredCount"] = sum(
        1 for item in cacheDiagnostics if item.get("fingerprintDeferred")
    )
    return summary


def summarizeCachedMediaDiagnostics(
    cachedItems: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    diagnostics = [
        item.get("diagnostics") or {}
        for item in cachedItems
        if item.get("diagnostics") is not None
    ]
    byProvider = sorted(
        {str(item.get("providerId")) for item in cachedItems if item.get("providerId")}
    )
    return {
        "count": len(diagnostics),
        "providerIds": byProvider,
        "duplicateCount": sum(1 for item in cachedItems if item.get("duplicate")),
        "totalSizeBytes": sum(int(item.get("sizeBytes") or 0) for item in cachedItems),
        "totals": {
            field: round(sum(float(item.get(field) or 0) for item in diagnostics), 4)
            for field in (
                "sourceTransferSeconds",
                "sourceHashSeconds",
                "sourceFileWriteSeconds",
                "duplicateCheckSeconds",
                "fingerprintSeconds",
                "metadataSeconds",
                "manifestSeconds",
                "totalSeconds",
            )
        },
        "fingerprintDeferredCount": sum(
            1 for item in diagnostics if item.get("fingerprintDeferred")
        ),
        "maxima": {
            field: round(
                max((float(item.get(field) or 0) for item in diagnostics), default=0.0),
                4,
            )
            for field in (
                "sourceTransferSeconds",
                "fingerprintSeconds",
                "metadataSeconds",
                "manifestSeconds",
                "totalSeconds",
            )
        },
    }


def summarizeElapsed(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "totalSeconds": 0.0, "maxSeconds": 0.0}
    return {
        "count": len(values),
        "totalSeconds": round(sum(values), 4),
        "maxSeconds": round(max(values), 4),
        "averageSeconds": round(sum(values) / len(values), 4),
    }


def fileNameForSearchItem(mediaName: str, sourceUri: str) -> str:
    suffix = Path(urlparse(sourceUri).path).suffix.lower()
    if not suffix or len(suffix) > 8:
        suffix = ".mp4" if "video" in mediaName else ".jpg"
    return f"{mediaName}{suffix}"


def cachedVideoHasMinimumDuration(
    client: Any, cachedItem: dict[str, Any], minDurationMilliseconds: int
) -> bool:
    manifest = unwrap(client.get("/api/media/cache"), "load live cache manifest")
    entry = next(
        (
            item
            for item in manifest.get("entries", ())
            if item.get("contentHash") == cachedItem.get("contentHash")
        ),
        None,
    )
    duration = int((entry or {}).get("durationMilliseconds") or 0)
    return duration >= minDurationMilliseconds


def buildSrt(sceneCount: int, sceneDurationSeconds: int = 2) -> str:
    cues = tuple(
        (
            formatSrtTimestamp(index * sceneDurationSeconds),
            formatSrtTimestamp((index + 1) * sceneDurationSeconds),
            f"Performance benchmark scene {index + 1} with visual cue.",
        )
        for index in range(sceneCount)
    )
    return "\n".join(
        f"{index}\n{start} --> {end}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, start=1)
    )


def formatSrtTimestamp(seconds: int) -> str:
    minutes, second = divmod(seconds, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}:{second:02d},000"


def waitForJob(client: Any, jobId: str, timeoutSeconds: int = 90) -> Any:
    deadline = time.monotonic() + timeoutSeconds
    samples: list[dict[str, float | str]] = []
    while time.monotonic() < deadline:
        job = unwrap(client.get(f"/api/render/jobs/{jobId}"), "poll render job")
        samples.append(
            {
                "atSeconds": round(time.monotonic(), 4),
                "status": str(job["status"]),
                "progressPercent": float(job.get("progressPercent") or 0.0),
            }
        )
        if job["status"] == "completed":
            job["_statusSamples"] = normalizeStatusSamples(samples)
            return job
        if job["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(f"Render job did not complete: {json.dumps(job)}")
        time.sleep(0.25)
    raise RuntimeError(f"Render job timed out: {jobId}")


def waitTimeoutSeconds(scenario: BenchmarkScenario) -> int:
    timelineDurationSeconds = scenario.sceneCount * scenario.sceneDurationSeconds
    return max(90, timelineDurationSeconds * 3)


def normalizeStatusSamples(
    samples: list[dict[str, float | str]],
) -> tuple[dict[str, float | str], ...]:
    if not samples:
        return ()
    firstAt = float(samples[0]["atSeconds"])
    return tuple(
        {
            "elapsedSeconds": round(float(sample["atSeconds"]) - firstAt, 4),
            "status": str(sample["status"]),
            "progressPercent": float(sample["progressPercent"]),
        }
        for sample in samples
    )


def summarizeStatusSamples(samples: Any) -> dict[str, Any]:
    if not samples:
        return {"counts": {}, "estimatedDurations": {}, "firstStatus": None}
    counts: dict[str, int] = {}
    durations: dict[str, float] = {}
    previous = samples[0]
    for sample in samples:
        status = str(sample["status"])
        counts[status] = counts.get(status, 0) + 1
    for sample in samples[1:]:
        status = str(previous["status"])
        delta = float(sample["elapsedSeconds"]) - float(previous["elapsedSeconds"])
        durations[status] = round(durations.get(status, 0.0) + max(0.0, delta), 4)
        previous = sample
    return {
        "counts": counts,
        "estimatedDurations": durations,
        "firstStatus": str(samples[0]["status"]),
        "lastStatus": str(samples[-1]["status"]),
        "sampleCount": len(samples),
    }


def rollupTimings(timings: dict[str, float]) -> dict[str, float]:
    prefixes = ("setup", "backend", "workflow", "cache", "render")
    return {
        prefix: round(
            sum(value for name, value in timings.items() if name.startswith(prefix)),
            4,
        )
        for prefix in prefixes
    }


def compareScenarios(results: list[dict[str, Any]]) -> dict[str, Any]:
    def commandSummary(result: dict[str, Any]) -> dict[str, Any]:
        return (result.get("renderDiagnostics") or {}).get("commandSummary") or {}

    def renderMetrics(result: dict[str, Any]) -> dict[str, Any]:
        return (result.get("renderDiagnostics") or {}).get("metrics") or {}

    def settingsSnapshot(result: dict[str, Any]) -> dict[str, Any]:
        return (result.get("renderDiagnostics") or {}).get("settingsSnapshot") or {}

    compact = [
        {
            "name": result["scenarioName"],
            "sceneCount": result["sceneCount"],
            "sceneDurationSeconds": (result.get("scenario") or {}).get(
                "sceneDurationSeconds", 2
            ),
            "timelineDurationSeconds": result.get("timelineDurationSeconds"),
            "cacheEntryCount": result["cacheEntryCount"],
            "renderVariant": (result.get("scenario") or {}).get(
                "renderVariant", "mixed"
            ),
            "profileId": settingsSnapshot(result).get("profileId"),
            "width": settingsSnapshot(result).get("width"),
            "height": settingsSnapshot(result).get("height"),
            "frameRate": settingsSnapshot(result).get("frameRate"),
            "durationSeconds": result["durationSeconds"],
            "rollups": result["rollups"],
            "cachedQueueSeconds": result["timings"].get("render.cached_queue_job"),
            "cachedWaitSeconds": result["timings"].get(
                "render.cached_wait_for_completion"
            ),
            "renderElapsedMilliseconds": renderMetrics(result).get(
                "elapsedMilliseconds"
            ),
            "ffmpegArgumentCount": commandSummary(result).get("argumentCount"),
            "ffmpegInputCount": commandSummary(result).get("inputCount"),
            "filterGraphLength": commandSummary(result).get("filterGraphLength"),
            "filterCount": commandSummary(result).get("filterCount"),
            "visualFilterCount": commandSummary(result).get("visualFilterCount"),
            "overlayFilterCount": commandSummary(result).get("overlayFilterCount"),
            "drawtextFilterCount": commandSummary(result).get("drawtextFilterCount"),
            "subtitleFileFilterCount": commandSummary(result).get(
                "subtitleFileFilterCount"
            ),
            "subtitleOverlayFilterCount": commandSummary(result).get(
                "subtitleOverlayFilterCount"
            ),
            "concatFilterCount": commandSummary(result).get("concatFilterCount"),
            "splitFilterCount": commandSummary(result).get("splitFilterCount"),
        }
        for result in results
    ]
    slowest = max(compact, key=lambda item: float(item["durationSeconds"]))
    return {
        "summary": compact,
        "slowestScenario": slowest["name"],
        "dominantRollupsByScenario": {
            item["name"]: max(
                item["rollups"].items(), key=lambda rollup: float(rollup[1])
            )[0]
            for item in compact
        },
    }


def writeResult(result: dict[str, Any]) -> Path:
    root = Path(__file__).resolve().parents[1]
    outputPath = Path(
        os.environ.get(
            "PHASE9_PERF_OUTPUT",
            root / ".tmp" / "phase9-performance-baseline.json",
        )
    )
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    outputPath.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return outputPath


def captureEnvironment() -> dict[str, str | None]:
    names = (
        "APP_DATA_DIR",
        "FFMPEG_PATH",
        "LOCAL_MEDIA_LIBRARY_PATHS",
        "MEDIA_CACHE_MAX_FILE_SIZE_BYTES",
        "RENDER_SUBTITLE_MODE",
        "DVIDS_VIDEO_QUALITY",
        "DVIDS_VIDEO_MAX_FILE_SIZE_BYTES",
    )
    return {name: os.environ.get(name) for name in names}


def subtitleModeForVariant(renderVariant: str) -> str:
    if renderVariant == "drawtext_subtitles":
        return "drawtext"
    if renderVariant == "sendcmd_subtitles":
        return "sendcmd"
    if renderVariant == "ass_subtitles":
        return "ass"
    if renderVariant in {"prerendered_subtitles", "prerendered_subtitles_cached"}:
        return "prerender"
    return "sendcmd"


def isRealisticMediaVariant(renderVariant: str) -> bool:
    return renderVariant == "realistic_standard"


def isLiveProviderCorpusVariant(renderVariant: str) -> bool:
    return renderVariant in {"real_provider_standard", "real_provider_high_quality"}


def restoreEnvironment(previous: dict[str, str | None]) -> None:
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def runFfmpeg(*args: str) -> None:
    completed = subprocess.run(
        ("ffmpeg", *args),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"FFmpeg command failed: {' '.join(args)}\n{completed.stderr}"
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
