from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import Scene
from app.project.project_model import Project
from app.services.scene_service import SceneService


class StubProjectService:
    def __init__(self, project: Project | None) -> None:
        self.project = project

    def getCurrentProject(self) -> Project | None:
        return self.project


class FakeSceneRepository:
    def __init__(self, scenes: tuple[Scene, ...]) -> None:
        self.collection = SceneCollection(scenes, datetime.now(UTC))

    def saveScenes(
        self, projectPath: Path, scenes: tuple[Scene, ...]
    ) -> SceneCollection:
        del projectPath
        self.collection = SceneCollection(scenes, datetime.now(UTC))
        return self.collection

    def loadScenes(self, projectPath: Path) -> SceneCollection:
        del projectPath
        return self.collection


def createProject(tmp_path: Path) -> Project:
    timestamp = datetime.now(UTC)
    return Project("id", "Demo", tmp_path, timestamp, timestamp)


def testSceneServiceUpdatesSceneText(tmp_path: Path) -> None:
    repository = FakeSceneRepository((Scene("scene-0001", 1, "Before"),))
    service = SceneService(repository, StubProjectService(createProject(tmp_path)))

    collection = service.updateScene("scene-0001", "  After\r\nline  ")

    assert collection.scenes[0].text == "After\nline"


def testSceneServiceRejectsUnknownScene(tmp_path: Path) -> None:
    repository = FakeSceneRepository((Scene("scene-0001", 1, "Text"),))
    service = SceneService(repository, StubProjectService(createProject(tmp_path)))

    with pytest.raises(ScriptError) as error:
        service.updateScene("missing", "Updated")

    assert error.value.code == "SCENE_NOT_FOUND"


def testSceneServiceAllowsIdempotentUpdate(tmp_path: Path) -> None:
    repository = FakeSceneRepository((Scene("scene-0001", 1, "Text"),))
    service = SceneService(repository, StubProjectService(createProject(tmp_path)))

    collection = service.updateScene("scene-0001", "Text")

    assert collection.scenes[0].text == "Text"
