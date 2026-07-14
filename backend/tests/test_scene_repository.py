from pathlib import Path

import pytest

from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import Scene
from app.repositories.file_scene_repository import FileSceneRepository


def testFileSceneRepositorySavesAndLoadsScenes(tmp_path: Path) -> None:
    repository = FileSceneRepository()
    scenes = (Scene("scene-0001", 1, "Editable text"),)

    saved = repository.saveScenes(tmp_path, scenes)
    loaded = repository.loadScenes(tmp_path)

    assert saved.schemaVersion == 1
    assert loaded.scenes == scenes
    assert (tmp_path / "script" / "scenes.json").is_file()


def testFileSceneRepositoryRejectsInvalidDocument(tmp_path: Path) -> None:
    scriptDirectory = tmp_path / "script"
    scriptDirectory.mkdir()
    (scriptDirectory / "scenes.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ScriptError) as error:
        FileSceneRepository().loadScenes(tmp_path)

    assert error.value.code == "INVALID_SCENES_FILE"
