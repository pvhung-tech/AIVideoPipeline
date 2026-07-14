from typing import Protocol

from app.ai.prompt_models import PromptTemplate


class PromptRepository(Protocol):
    def loadTemplates(self) -> tuple[PromptTemplate, ...]: ...
