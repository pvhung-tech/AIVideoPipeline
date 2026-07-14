from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.media.cache_manifest import MediaCacheEntry, MediaCacheManifest
from app.media.cache_paths import resolveCacheEntryPath
from app.media.media_fingerprint_service import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.services.script_service import ActiveProjectProvider
from app.timeline.errors import TimelineError
from app.timeline.media_assets import TimelineMediaAsset, TimelineMediaAssetPage
from app.timeline.models import (
    AudioClip,
    MediaClip,
    Timeline,
    TimelineMediaType,
    TimelineScene,
    VisualClipRole,
)


class TimelineProvider(Protocol):
    def getTimeline(self) -> Timeline: ...

    def saveTimeline(self, timeline: Timeline) -> Timeline: ...


class MediaCacheProvider(Protocol):
    def getManifest(self) -> MediaCacheManifest: ...


class TimelineMediaService:
    def __init__(
        self,
        timelineService: TimelineProvider,
        mediaCacheService: MediaCacheProvider,
        projectService: ActiveProjectProvider,
    ) -> None:
        self.timelineService = timelineService
        self.mediaCacheService = mediaCacheService
        self.projectService = projectService

    def listAssets(self) -> tuple[TimelineMediaAsset, ...]:
        return self.listAssetPage(0, None).assets

    def listAssetPage(
        self, offset: int = 0, limit: int | None = None
    ) -> TimelineMediaAssetPage:
        if offset < 0 or (limit is not None and limit <= 0):
            raise TimelineError(
                "INVALID_MEDIA_ASSET_PAGE",
                "Media asset offset and limit must be positive.",
            )
        project = self._requireProject()
        manifestEntries = tuple(
            sorted(
                self.mediaCacheService.getManifest().entries,
                key=lambda entry: entry.lastAccessedAt,
                reverse=True,
            )
        )
        windowEntries = (
            manifestEntries[offset:]
            if limit is None
            else manifestEntries[offset : offset + limit]
        )
        assets = tuple(
            asset
            for asset in (self._toAsset(project, entry) for entry in windowEntries)
            if asset is not None
        )
        return TimelineMediaAssetPage(
            assets,
            offset,
            limit,
            len(manifestEntries),
            offset + len(windowEntries) < len(manifestEntries),
        )

    def assignPrimaryMedia(self, sceneId: str, contentHash: str | None) -> Timeline:
        return self.assignVisualMedia(sceneId, VisualClipRole.BROLL, contentHash)

    def assignVisualMedia(
        self, sceneId: str, role: VisualClipRole, contentHash: str | None
    ) -> Timeline:
        timeline = self.timelineService.getTimeline()
        scene = self._findScene(timeline, sceneId)
        clip = self._createClip(scene, role, contentHash) if contentHash else None
        updatedScene = replace(
            scene,
            mediaClips=tuple(
                (*self._withoutRole(scene, role), *((clip,) if clip else ()))
            ),
        )
        updatedTimeline = replace(
            timeline,
            scenes=tuple(
                updatedScene if item.sceneId == sceneId else item
                for item in timeline.scenes
            ),
            updatedAt=datetime.now(UTC),
        )
        return self.timelineService.saveTimeline(updatedTimeline)

    def assignVisualMediaBatch(
        self, assignments: tuple["VisualMediaAssignment", ...]
    ) -> Timeline:
        if not assignments:
            return self.timelineService.getTimeline()
        self._validateUniqueAssignments(assignments)
        timeline = self.timelineService.getTimeline()
        sceneIds = {scene.sceneId for scene in timeline.scenes}
        missingSceneId = next(
            (
                assignment.sceneId
                for assignment in assignments
                if assignment.sceneId not in sceneIds
            ),
            None,
        )
        if missingSceneId is not None:
            raise TimelineError("TIMELINE_SCENE_NOT_FOUND", "Timeline scene not found.")

        assets = self._assetsByHash()
        assignmentsByScene = self._assignmentsByScene(assignments)
        updatedScenes: list[TimelineScene] = []
        for scene in timeline.scenes:
            updatedScene = scene
            for assignment in assignmentsByScene.get(scene.sceneId, ()):
                clip = (
                    self._createClipFromAsset(
                        updatedScene,
                        assignment.role,
                        self._assetFromMap(assets, assignment.contentHash),
                    )
                    if assignment.contentHash
                    else None
                )
                updatedScene = replace(
                    updatedScene,
                    mediaClips=tuple(
                        (
                            *self._withoutRole(updatedScene, assignment.role),
                            *((clip,) if clip else ()),
                        )
                    ),
                )
            updatedScenes.append(updatedScene)

        return self.timelineService.saveTimeline(
            replace(timeline, scenes=tuple(updatedScenes), updatedAt=datetime.now(UTC))
        )

    def assignMusic(self, contentHash: str | None, volume: float = 0.2) -> Timeline:
        timeline = self.timelineService.getTimeline()
        if contentHash is None:
            updated = replace(timeline, audioClips=(), updatedAt=datetime.now(UTC))
            return self.timelineService.saveTimeline(updated)
        asset = self._findAsset(contentHash)
        if (
            asset.mediaType is not TimelineMediaType.AUDIO
            or "local" not in asset.providerIds
            or asset.durationMilliseconds is None
        ):
            raise TimelineError(
                "INVALID_MUSIC_ASSET",
                "Music must be a local audio asset with verified duration.",
            )
        clip = AudioClip(
            id=f"music-{contentHash[:12]}",
            contentHash=contentHash,
            startMilliseconds=0,
            endMilliseconds=timeline.durationMilliseconds,
            sourceStartMilliseconds=0,
            sourceEndMilliseconds=asset.durationMilliseconds,
            volume=volume,
        )
        return self.timelineService.saveTimeline(
            replace(timeline, audioClips=(clip,), updatedAt=datetime.now(UTC))
        )

    def _createClip(
        self, scene: TimelineScene, role: VisualClipRole, contentHash: str
    ) -> MediaClip:
        asset = self._findAsset(contentHash)
        return self._createClipFromAsset(scene, role, asset)

    def _createClipFromAsset(
        self, scene: TimelineScene, role: VisualClipRole, asset: TimelineMediaAsset
    ) -> MediaClip:
        if asset.mediaType is TimelineMediaType.AUDIO:
            raise TimelineError(
                "UNSUPPORTED_CACHED_MEDIA",
                "Audio cannot be assigned to a visual layer.",
            )
        duration = scene.endMilliseconds - scene.startMilliseconds
        if asset.mediaType is TimelineMediaType.VIDEO and (
            asset.durationMilliseconds is None or asset.durationMilliseconds < duration
        ):
            raise TimelineError(
                "VIDEO_SOURCE_TOO_SHORT",
                "The video is too short or has no verified duration.",
            )
        return MediaClip(
            id=f"{role.value}-{scene.sceneId}-{asset.contentHash[:12]}",
            contentHash=asset.contentHash,
            mediaType=asset.mediaType,
            startMilliseconds=scene.startMilliseconds,
            endMilliseconds=scene.endMilliseconds,
            layer=0 if role is VisualClipRole.BROLL else 1,
            sourceStartMilliseconds=(
                0 if asset.mediaType is TimelineMediaType.VIDEO else None
            ),
            sourceEndMilliseconds=(
                duration if asset.mediaType is TimelineMediaType.VIDEO else None
            ),
            role=role,
        )

    def _findAsset(self, contentHash: str) -> TimelineMediaAsset:
        return self._assetFromMap(self._assetsByHash(), contentHash)

    def _assetsByHash(self) -> dict[str, TimelineMediaAsset]:
        project = self._requireProject()
        assets = (
            self._toAsset(project, entry)
            for entry in self.mediaCacheService.getManifest().entries
        )
        return {asset.contentHash: asset for asset in assets if asset is not None}

    def _assetFromMap(
        self, assets: dict[str, TimelineMediaAsset], contentHash: str
    ) -> TimelineMediaAsset:
        asset = assets.get(contentHash)
        if asset is None:
            raise TimelineError(
                "CACHED_MEDIA_NOT_FOUND", "The selected cached media was not found."
            )
        return asset

    def _validateUniqueAssignments(
        self, assignments: tuple["VisualMediaAssignment", ...]
    ) -> None:
        seen: set[tuple[str, VisualClipRole]] = set()
        for assignment in assignments:
            key = (assignment.sceneId, assignment.role)
            if key in seen:
                raise TimelineError(
                    "DUPLICATE_TIMELINE_MEDIA_ASSIGNMENT",
                    "Each scene and visual role can be assigned only once per batch.",
                )
            seen.add(key)

    def _assignmentsByScene(
        self, assignments: tuple["VisualMediaAssignment", ...]
    ) -> dict[str, tuple["VisualMediaAssignment", ...]]:
        grouped: dict[str, list[VisualMediaAssignment]] = {}
        for assignment in assignments:
            grouped.setdefault(assignment.sceneId, []).append(assignment)
        return {sceneId: tuple(items) for sceneId, items in grouped.items()}

    def trimPrimaryVideo(
        self, sceneId: str, sourceStart: int, sourceEnd: int
    ) -> Timeline:
        return self.trimVisualVideo(
            sceneId, VisualClipRole.BROLL, sourceStart, sourceEnd
        )

    def trimVisualVideo(
        self,
        sceneId: str,
        role: VisualClipRole,
        sourceStart: int,
        sourceEnd: int,
    ) -> Timeline:
        timeline = self.timelineService.getTimeline()
        scene = self._findScene(timeline, sceneId)
        clip = next((item for item in scene.mediaClips if item.role is role), None)
        if clip is None or clip.mediaType is not TimelineMediaType.VIDEO:
            raise TimelineError(
                "TIMELINE_VIDEO_NOT_FOUND", "The scene has no primary video clip."
            )
        asset = next(
            (
                item
                for item in self.listAssets()
                if item.contentHash == clip.contentHash
            ),
            None,
        )
        if asset is None or asset.durationMilliseconds is None:
            raise TimelineError(
                "VIDEO_DURATION_UNAVAILABLE", "Verified video duration is unavailable."
            )
        if sourceStart < 0 or sourceEnd > asset.durationMilliseconds:
            raise TimelineError(
                "INVALID_VIDEO_TRIM", "Video trim range exceeds the source duration."
            )
        updatedClip = replace(
            clip, sourceStartMilliseconds=sourceStart, sourceEndMilliseconds=sourceEnd
        )
        updatedScene = replace(
            scene,
            mediaClips=tuple(
                updatedClip if item.id == clip.id else item for item in scene.mediaClips
            ),
        )
        return self.timelineService.saveTimeline(
            replace(
                timeline,
                scenes=tuple(
                    updatedScene if item.sceneId == sceneId else item
                    for item in timeline.scenes
                ),
                updatedAt=datetime.now(UTC),
            )
        )

    def _toAsset(
        self, project: Project, entry: MediaCacheEntry
    ) -> TimelineMediaAsset | None:
        cacheRoot = project.path / "cache"
        path = resolveCacheEntryPath(cacheRoot, entry)
        mediaType = self._mediaType(path)
        if mediaType is None or not path.is_file():
            return None
        return TimelineMediaAsset(
            contentHash=entry.contentHash,
            mediaType=mediaType,
            fileName=path.name,
            uri=path.as_uri(),
            sizeBytes=entry.sizeBytes,
            providerIds=tuple(sorted({source.providerId for source in entry.sources})),
            durationMilliseconds=entry.durationMilliseconds,
        )

    def _mediaType(self, path: Path) -> TimelineMediaType | None:
        extension = path.suffix.lower()
        if extension in IMAGE_EXTENSIONS:
            return TimelineMediaType.IMAGE
        if extension in VIDEO_EXTENSIONS:
            return TimelineMediaType.VIDEO
        if extension in AUDIO_EXTENSIONS:
            return TimelineMediaType.AUDIO
        return None

    def _withoutRole(
        self, scene: TimelineScene, role: VisualClipRole
    ) -> tuple[MediaClip, ...]:
        return tuple(clip for clip in scene.mediaClips if clip.role is not role)

    def _findScene(self, timeline: Timeline, sceneId: str) -> TimelineScene:
        scene = next(
            (item for item in timeline.scenes if item.sceneId == sceneId), None
        )
        if scene is None:
            raise TimelineError("TIMELINE_SCENE_NOT_FOUND", "Timeline scene not found.")
        return scene

    def _requireProject(self) -> Project:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return project


@dataclass(frozen=True)
class VisualMediaAssignment:
    sceneId: str
    role: VisualClipRole
    contentHash: str | None
