from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.scene_parser import SceneParser
from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import Scene, ScriptDocument, ScriptFormat, SubtitleCue
from app.pipeline.subtitle_parser import SubtitleParser
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.services.script_service import ScriptService


class StubProjectService:
    def __init__(self, project: Project | None) -> None:
        self.project = project

    def getCurrentProject(self) -> Project | None:
        return self.project


class FakeScriptRepository:
    def __init__(self, content: str) -> None:
        self.content = content
        self.savedFormat: ScriptFormat | None = None
        self.savedCues: tuple[SubtitleCue, ...] = ()

    def readSource(self, _sourcePath: Path) -> str:
        return self.content

    def saveScript(
        self,
        projectPath: Path,
        sourcePath: Path,
        scriptFormat: ScriptFormat,
        content: str,
        cues: tuple[SubtitleCue, ...],
    ) -> ScriptDocument:
        self.savedFormat = scriptFormat
        self.savedCues = cues
        return ScriptDocument(
            format=scriptFormat,
            originalPath=sourcePath,
            contentPath=projectPath / "script" / f"source.{scriptFormat.value}",
            importedAt=datetime.now(UTC),
            characterCount=len(content),
            cues=cues,
        )


class FakeSceneRepository:
    def __init__(self) -> None:
        self.collection: SceneCollection | None = None

    def saveScenes(
        self, projectPath: Path, scenes: tuple[Scene, ...]
    ) -> SceneCollection:
        del projectPath
        self.collection = SceneCollection(scenes=scenes, updatedAt=datetime.now(UTC))
        return self.collection

    def loadScenes(self, projectPath: Path) -> SceneCollection:
        del projectPath
        assert self.collection is not None
        return self.collection


def createProject(tmp_path: Path) -> Project:
    timestamp = datetime.now(UTC)
    return Project("id", "Demo", tmp_path, timestamp, timestamp)


def testScriptServiceImportsAndParsesSrt(tmp_path: Path) -> None:
    repository = FakeScriptRepository("1\r\n00:00:00,000 --> 00:00:01,000\r\nHello\r\n")
    service = ScriptService(
        repository,
        StubProjectService(createProject(tmp_path)),
        SubtitleParser(),
        SceneParser(),
        FakeSceneRepository(),
    )

    document = service.importScript(tmp_path / "input.SRT")

    assert document.format == ScriptFormat.SRT
    assert repository.savedFormat == ScriptFormat.SRT
    assert len(repository.savedCues) == 1
    assert len(document.scenes) == 1
    assert document.scenes[0].startMilliseconds == 0


def testScriptServiceRequiresActiveProject(tmp_path: Path) -> None:
    service = ScriptService(
        FakeScriptRepository("Text"),
        StubProjectService(None),
        SubtitleParser(),
        SceneParser(),
        FakeSceneRepository(),
    )

    with pytest.raises(ProjectError) as error:
        service.importScript(tmp_path / "input.txt")

    assert error.value.code == "NO_ACTIVE_PROJECT"


def testScriptServiceRejectsUnsupportedFormat(tmp_path: Path) -> None:
    service = ScriptService(
        FakeScriptRepository("Text"),
        StubProjectService(createProject(tmp_path)),
        SubtitleParser(),
        SceneParser(),
        FakeSceneRepository(),
    )

    with pytest.raises(ScriptError) as error:
        service.importScript(tmp_path / "input.docx")

    assert error.value.code == "UNSUPPORTED_SCRIPT_FORMAT"
