import json
import logging
from pathlib import Path
from typing import Any

from app.ai.errors import AIError
from app.ai.prompt_models import PromptTemplate

logger = logging.getLogger(__name__)
PROMPT_SCHEMA_VERSION = 1


class FilePromptRepository:
    def __init__(self, configPath: Path) -> None:
        self.configPath = configPath

    def loadTemplates(self) -> tuple[PromptTemplate, ...]:
        if not self.configPath.is_file():
            raise AIError(
                "PROMPT_CONFIG_NOT_FOUND", "The prompt configuration was not found."
            )
        try:
            data: Any = json.loads(self.configPath.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Prompt configuration must be an object.")
            if int(data["schemaVersion"]) != PROMPT_SCHEMA_VERSION:
                raise ValueError("Unsupported prompt schema version.")
            prompts = data["prompts"]
            if not isinstance(prompts, list):
                raise TypeError("prompts must be a list.")
            if any(not isinstance(prompt, dict) for prompt in prompts):
                raise TypeError("Each prompt must be an object.")
            return tuple(
                PromptTemplate.fromDictionary(prompt)
                for prompt in prompts
                if isinstance(prompt, dict)
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise AIError(
                "INVALID_PROMPT_CONFIG", "The prompt configuration is invalid."
            ) from error
        except OSError as error:
            logger.exception(
                "Failed to read prompt configuration at %s", self.configPath
            )
            raise AIError(
                "PROMPT_CONFIG_READ_FAILED",
                "The prompt configuration could not be read.",
            ) from error
