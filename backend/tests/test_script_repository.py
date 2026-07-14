import json
from pathlib import Path

import pytest

from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import ScriptFormat
from app.repositories.file_script_repository import FileScriptRepository


def testFileScriptRepositoryReadsUtf8BomAndSavesManifest(tmp_path: Path) -> None:
    sourcePath = tmp_path / "input.txt"
    sourcePath.write_bytes(b"\xef\xbb\xbfHello\r\nworld")
    projectPath = tmp_path / "project"
    (projectPath / "script").mkdir(parents=True)
    repository = FileScriptRepository()

    content = repository.readSource(sourcePath)
    document = repository.saveScript(
        projectPath,
        sourcePath,
        ScriptFormat.TXT,
        content.replace("\r\n", "\n"),
        (),
    )

    manifest = json.loads((projectPath / "script" / "manifest.json").read_text())
    assert content == "Hello\nworld"
    assert document.format == ScriptFormat.TXT
    assert manifest["format"] == "txt"
    assert (projectPath / "script" / "source.txt").is_file()


def testFileScriptRepositoryRejectsInvalidUtf8(tmp_path: Path) -> None:
    sourcePath = tmp_path / "input.txt"
    sourcePath.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(ScriptError) as error:
        FileScriptRepository().readSource(sourcePath)

    assert error.value.code == "INVALID_SCRIPT_ENCODING"
