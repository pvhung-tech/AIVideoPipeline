from datetime import UTC, datetime
from uuid import uuid4

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.script_models import Scene
from app.timeline.models import SubtitleClip, Timeline, TimelineScene

WORDS_PER_SECOND = 2.5
MINIMUM_SCENE_DURATION_MILLISECONDS = 2_000
MAXIMUM_SCENE_DURATION_MILLISECONDS = 30_000


class InitialTimelineService:
    def create(self, scenes: SceneCollection) -> Timeline:
        timestamp = datetime.now(UTC)
        cursor = 0
        timelineScenes: list[TimelineScene] = []
        for scene in scenes.scenes:
            duration = self._sceneDuration(scene)
            end = cursor + duration
            timelineScenes.append(
                TimelineScene(
                    sceneId=scene.id,
                    order=scene.order,
                    startMilliseconds=cursor,
                    endMilliseconds=end,
                    subtitleClips=(
                        SubtitleClip(
                            id=f"subtitle-{scene.id}",
                            text=scene.text,
                            startMilliseconds=cursor,
                            endMilliseconds=end,
                        ),
                    ),
                )
            )
            cursor = end
        return Timeline(
            id=f"timeline-{uuid4()}",
            scenes=tuple(timelineScenes),
            createdAt=timestamp,
            updatedAt=timestamp,
        )

    def _sceneDuration(self, scene: Scene) -> int:
        if scene.startMilliseconds is not None and scene.endMilliseconds is not None:
            return scene.endMilliseconds - scene.startMilliseconds
        estimated = round(len(scene.text.split()) / WORDS_PER_SECOND * 1_000)
        return max(
            MINIMUM_SCENE_DURATION_MILLISECONDS,
            min(estimated, MAXIMUM_SCENE_DURATION_MILLISECONDS),
        )
