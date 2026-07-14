from typing import Protocol

from app.ai.models import AIRequest, AIResponse


class AIProvider(Protocol):
    @property
    def providerId(self) -> str: ...

    async def generate(self, request: AIRequest) -> AIResponse: ...
