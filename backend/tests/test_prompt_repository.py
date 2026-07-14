from pathlib import Path

import pytest

from app.ai.errors import AIError
from app.repositories.file_prompt_repository import FilePromptRepository


def testFilePromptRepositoryRejectsUnknownSchema(tmp_path: Path) -> None:
    configPath = tmp_path / "prompts.json"
    configPath.write_text('{"schemaVersion": 2, "prompts": []}', encoding="utf-8")

    with pytest.raises(AIError) as error:
        FilePromptRepository(configPath).loadTemplates()

    assert error.value.code == "INVALID_PROMPT_CONFIG"


def testFilePromptRepositoryRejectsNonObjectPrompt(tmp_path: Path) -> None:
    configPath = tmp_path / "prompts.json"
    configPath.write_text(
        '{"schemaVersion": 1, "prompts": ["invalid"]}', encoding="utf-8"
    )

    with pytest.raises(AIError) as error:
        FilePromptRepository(configPath).loadTemplates()

    assert error.value.code == "INVALID_PROMPT_CONFIG"
