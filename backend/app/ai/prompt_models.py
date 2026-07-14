from dataclasses import dataclass
from typing import Any

from app.ai.models import AIMessage, AIMessageRole


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: int
    systemTemplate: str
    userTemplate: str
    requiredVariables: tuple[str, ...]

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "PromptTemplate":
        variables = data["requiredVariables"]
        if not isinstance(variables, list):
            raise TypeError("requiredVariables must be a list.")
        return cls(
            id=str(data["id"]),
            version=int(data["version"]),
            systemTemplate=str(data["systemTemplate"]),
            userTemplate=str(data["userTemplate"]),
            requiredVariables=tuple(str(value) for value in variables),
        )


@dataclass(frozen=True)
class RenderedPrompt:
    templateId: str
    templateVersion: int
    messages: tuple[AIMessage, ...]

    @classmethod
    def create(
        cls, template: PromptTemplate, systemPrompt: str, userPrompt: str
    ) -> "RenderedPrompt":
        return cls(
            templateId=template.id,
            templateVersion=template.version,
            messages=(
                AIMessage(AIMessageRole.SYSTEM, systemPrompt),
                AIMessage(AIMessageRole.USER, userPrompt),
            ),
        )
