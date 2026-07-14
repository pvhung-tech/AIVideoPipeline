from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.script_models import Scene
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.repositories.file_timeline_repository import FileTimelineRepository
from app.services.timeline_service import TimelineService
from app.timeline.initial_timeline_service import InitialTimelineService
from app.timeline.models import Timeline, TimelineScene
from app.timeline.validation_service import TimelineValidationService


class StubProjectService:
    def __init__(self, project: Project | None) -> None:
        self.project = project

    def getCurrentProject(self) -> Project | None:
        return self.project


class FakeSceneRepository:
    def saveScenes(
        self, projectPath: Path, scenes: tuple[Scene, ...]
    ) -> SceneCollection:
        del projectPath
        return SceneCollection(scenes, datetime.now(UTC))

    def loadScenes(self, projectPath: Path) -> SceneCollection:
        del projectPath
        return SceneCollection((Scene("scene-1", 1, "Scene"),), datetime.now(UTC))


def createProject(tmp_path: Path) -> Project:
    timestamp = datetime.now(UTC)
    return Project("project-1", "Project", tmp_path, timestamp, timestamp)


def createTimeline() -> Timeline:
    timestamp = datetime.now(UTC)
    return Timeline(
        "timeline-1", (TimelineScene("scene-1", 1, 0, 1_000),), timestamp, timestamp
    )


def testTimelineServicePersistsForActiveProject(tmp_path: Path) -> None:
    service = TimelineService(
        FileTimelineRepository(),
        FakeSceneRepository(),
        StubProjectService(createProject(tmp_path)),
        TimelineValidationService(),
        InitialTimelineService(),
    )

    service.saveTimeline(createTimeline())

    assert service.getTimeline().id == "timeline-1"


def testTimelineServiceRequiresActiveProject(tmp_path: Path) -> None:
    service = TimelineService(
        FileTimelineRepository(),
        FakeSceneRepository(),
        StubProjectService(None),
        TimelineValidationService(),
        InitialTimelineService(),
    )

    with pytest.raises(ProjectError) as error:
        service.saveTimeline(createTimeline())

    assert error.value.code == "NO_ACTIVE_PROJECT"
