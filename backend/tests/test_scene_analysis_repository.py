from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.ai.errors import AIError
from app.ai.scene_analysis_models import SceneAnalysisResult
from app.repositories.file_scene_analysis_repository import (
    FileSceneAnalysisRepository,
)


def createResult(sceneId: str, description: str) -> SceneAnalysisResult:
    return SceneAnalysisResult(
        sceneId=sceneId,
        sourceTextHash="0" * 64,
        description=description,
        category="location",
        keywords=("city", "sunrise"),
        providerId="ollama",
        model="test-model",
        promptVersion=1,
        analyzedAt=datetime.now(UTC),
    )


def testSceneAnalysisRepositoryUpsertsResults(tmp_path: Path) -> None:
    repository = FileSceneAnalysisRepository()

    repository.upsertResult(tmp_path, createResult("scene-0002", "Second"))
    repository.upsertResult(tmp_path, createResult("scene-0001", "Before"))
    collection = repository.upsertResult(tmp_path, createResult("scene-0001", "After"))

    assert [result.sceneId for result in collection.results] == [
        "scene-0001",
        "scene-0002",
    ]
    assert collection.results[0].description == "After"
    assert (tmp_path / "script" / "analysis.json").is_file()


def testSceneAnalysisRepositoryRejectsInvalidFile(tmp_path: Path) -> None:
    scriptDirectory = tmp_path / "script"
    scriptDirectory.mkdir()
    (scriptDirectory / "analysis.json").write_text(
        '{"schemaVersion":1,"updatedAt":"bad","results":[]}',
        encoding="utf-8",
    )

    with pytest.raises(AIError) as error:
        FileSceneAnalysisRepository().listResults(tmp_path)

    assert error.value.code == "INVALID_SCENE_ANALYSIS_FILE"
