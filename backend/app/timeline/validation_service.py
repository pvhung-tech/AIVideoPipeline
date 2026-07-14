import re
from collections.abc import Iterable

from app.pipeline.scene_collection import SceneCollection
from app.timeline.errors import TimelineError
from app.timeline.models import (
    TIMELINE_SCHEMA_VERSION,
    AudioClip,
    MediaClip,
    SubtitleClip,
    Timeline,
    TimelineMediaType,
    TimelineScene,
    VisualClipRole,
)

CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TimelineValidationService:
    def validate(self, timeline: Timeline, scenes: SceneCollection) -> None:
        self._require(
            timeline.schemaVersion == TIMELINE_SCHEMA_VERSION,
            "Unsupported timeline schema version.",
        )
        self._require(bool(timeline.id.strip()), "Timeline ID cannot be empty.")
        self._require(
            bool(timeline.scenes), "Timeline must contain at least one scene."
        )
        self._require(
            timeline.createdAt.tzinfo is not None
            and timeline.updatedAt.tzinfo is not None,
            "Timeline timestamps must include a timezone.",
        )
        self._require(
            timeline.updatedAt >= timeline.createdAt,
            "Timeline update time cannot precede creation time.",
        )

        expectedOrders = tuple(range(1, len(timeline.scenes) + 1))
        self._require(
            tuple(item.order for item in timeline.scenes) == expectedOrders,
            "Timeline scene order must be contiguous.",
        )
        knownSceneIds = {scene.id for scene in scenes.scenes}
        timelineSceneIds = [scene.sceneId for scene in timeline.scenes]
        self._require(
            len(set(timelineSceneIds)) == len(timelineSceneIds),
            "Timeline scene IDs must be unique.",
        )
        self._require(
            all(sceneId in knownSceneIds for sceneId in timelineSceneIds),
            "Timeline references an unknown project scene.",
        )

        previousEnd = 0
        clipIds: set[str] = set()
        for scene in timeline.scenes:
            self._validateScene(scene, previousEnd, clipIds)
            previousEnd = scene.endMilliseconds
        for audioClip in timeline.audioClips:
            self._validateAudioClip(audioClip, timeline.durationMilliseconds, clipIds)
        self._validateLayerOverlaps(timeline.audioClips)

    def _validateScene(
        self, scene: TimelineScene, previousEnd: int, clipIds: set[str]
    ) -> None:
        self._require(
            scene.startMilliseconds >= previousEnd, "Timeline scenes cannot overlap."
        )
        self._require(
            scene.endMilliseconds > scene.startMilliseconds,
            "Timeline scene duration must be positive.",
        )
        for mediaClip in scene.mediaClips:
            self._validateClip(mediaClip, scene, clipIds)
            self._validateMediaClip(mediaClip)
        for subtitleClip in scene.subtitleClips:
            self._validateClip(subtitleClip, scene, clipIds)
            self._require(
                bool(subtitleClip.text.strip()), "Subtitle text cannot be empty."
            )
        self._validateLayerOverlaps(scene.mediaClips)
        self._validateLayerOverlaps(scene.subtitleClips)

    def _validateClip(
        self,
        clip: MediaClip | SubtitleClip,
        scene: TimelineScene,
        clipIds: set[str],
    ) -> None:
        self._require(
            bool(clip.id.strip()) and clip.id not in clipIds,
            "Timeline clip IDs must be non-empty and unique.",
        )
        clipIds.add(clip.id)
        self._require(clip.layer >= 0, "Timeline clip layer cannot be negative.")
        self._require(
            clip.startMilliseconds >= scene.startMilliseconds
            and clip.endMilliseconds <= scene.endMilliseconds,
            "Timeline clips must stay inside their scene.",
        )
        self._require(
            clip.endMilliseconds > clip.startMilliseconds,
            "Timeline clip duration must be positive.",
        )

    def _validateMediaClip(self, clip: MediaClip) -> None:
        self._require(
            CONTENT_HASH_PATTERN.fullmatch(clip.contentHash) is not None,
            "Media content hash must be lowercase SHA-256.",
        )
        self._require(
            clip.mediaType is not TimelineMediaType.AUDIO,
            "Audio cannot be stored on a visual layer.",
        )
        self._require(
            (clip.role is VisualClipRole.BROLL and clip.layer == 0)
            or (clip.role is VisualClipRole.AVATAR and clip.layer == 1),
            "Visual clip role does not match its layer.",
        )
        if clip.mediaType is TimelineMediaType.IMAGE:
            self._require(
                clip.sourceStartMilliseconds is None
                and clip.sourceEndMilliseconds is None,
                "Image clips cannot define a source range.",
            )
            return
        self._require(
            clip.sourceStartMilliseconds is not None
            and clip.sourceEndMilliseconds is not None,
            "Video clips require a source range.",
        )
        assert clip.sourceStartMilliseconds is not None
        assert clip.sourceEndMilliseconds is not None
        sourceDuration = clip.sourceEndMilliseconds - clip.sourceStartMilliseconds
        self._require(
            clip.sourceStartMilliseconds >= 0 and sourceDuration > 0,
            "Video source range is invalid.",
        )
        self._require(
            sourceDuration >= clip.endMilliseconds - clip.startMilliseconds,
            "Video source range is shorter than the timeline clip.",
        )

    def _validateAudioClip(
        self, clip: AudioClip, timelineDuration: int, clipIds: set[str]
    ) -> None:
        self._require(
            bool(clip.id.strip()) and clip.id not in clipIds,
            "Timeline clip IDs must be non-empty and unique.",
        )
        clipIds.add(clip.id)
        self._require(
            CONTENT_HASH_PATTERN.fullmatch(clip.contentHash) is not None,
            "Media content hash must be lowercase SHA-256.",
        )
        self._require(
            0 <= clip.startMilliseconds < clip.endMilliseconds <= timelineDuration,
            "Audio clips must stay inside the timeline.",
        )
        sourceDuration = clip.sourceEndMilliseconds - clip.sourceStartMilliseconds
        self._require(
            clip.sourceStartMilliseconds >= 0 and sourceDuration > 0,
            "Audio source range is invalid.",
        )
        self._require(0 <= clip.volume <= 1, "Audio volume must be between 0 and 1.")
        self._require(
            clip.loop
            or sourceDuration >= clip.endMilliseconds - clip.startMilliseconds,
            "Audio source range is shorter than the timeline clip.",
        )

    def _validateLayerOverlaps(
        self, clips: Iterable[MediaClip | SubtitleClip | AudioClip]
    ) -> None:
        previousEndByLayer: dict[int, int] = {}
        for clip in sorted(
            clips, key=lambda item: (item.layer, item.startMilliseconds)
        ):
            previousEnd = previousEndByLayer.get(clip.layer)
            self._require(
                previousEnd is None or clip.startMilliseconds >= previousEnd,
                "Clips on the same layer cannot overlap.",
            )
            previousEndByLayer[clip.layer] = clip.endMilliseconds

    def _require(self, condition: bool, message: str) -> None:
        if not condition:
            raise TimelineError("INVALID_TIMELINE", message)
