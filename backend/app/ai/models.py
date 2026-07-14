from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.ai.errors import AIError


class AIMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class AIMessage:
    role: AIMessageRole
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise AIError("INVALID_AI_MESSAGE", "AI message content cannot be empty.")


@dataclass(frozen=True)
class AIRequest:
    model: str
    messages: tuple[AIMessage, ...]
    temperature: float = 0.2
    maxOutputTokens: int = 2048
    responseSchema: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise AIError("INVALID_AI_REQUEST", "AI model cannot be empty.")
        if not self.messages:
            raise AIError("INVALID_AI_REQUEST", "AI request requires a message.")
        if self.temperature < 0 or self.temperature > 2:
            raise AIError(
                "INVALID_AI_REQUEST", "AI temperature must be between 0 and 2."
            )
        if self.maxOutputTokens < 1:
            raise AIError(
                "INVALID_AI_REQUEST", "Maximum output tokens must be positive."
            )


@dataclass(frozen=True)
class AIUsage:
    inputTokens: int
    outputTokens: int

    def __post_init__(self) -> None:
        if self.inputTokens < 0 or self.outputTokens < 0:
            raise AIError("INVALID_AI_USAGE", "AI token usage cannot be negative.")

    @property
    def totalTokens(self) -> int:
        return self.inputTokens + self.outputTokens


@dataclass(frozen=True)
class AIResponse:
    providerId: str
    model: str
    content: str
    usage: AIUsage | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.providerId.strip() or not self.model.strip():
            raise AIError(
                "INVALID_AI_RESPONSE", "AI response provider and model are required."
            )
        if not self.content.strip():
            raise AIError("INVALID_AI_RESPONSE", "AI response cannot be empty.")
