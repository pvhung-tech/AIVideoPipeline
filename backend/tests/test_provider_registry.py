import asyncio

import pytest

from app.ai.errors import AIError
from app.ai.models import AIMessage, AIMessageRole, AIRequest, AIResponse, AIUsage
from app.ai.provider_registry import AIProviderRegistry


class FakeProvider:
    def __init__(self, providerId: str) -> None:
        self._providerId = providerId

    @property
    def providerId(self) -> str:
        return self._providerId

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(self.providerId, request.model, "Generated response")


def testProviderRegistryResolvesAndCallsProvider() -> None:
    registry = AIProviderRegistry((FakeProvider("OpenAI"), FakeProvider("ollama")))
    request = AIRequest(
        model="test-model",
        messages=(AIMessage(AIMessageRole.USER, "Hello"),),
    )

    response = asyncio.run(registry.get("OPENAI").generate(request))

    assert registry.listProviderIds() == ("ollama", "openai")
    assert response.content == "Generated response"
    assert response.model == "test-model"


def testProviderRegistryRejectsDuplicateProvider() -> None:
    with pytest.raises(AIError) as error:
        AIProviderRegistry((FakeProvider("gemini"), FakeProvider("GEMINI")))

    assert error.value.code == "AI_PROVIDER_ALREADY_REGISTERED"


def testProviderRegistryRejectsMissingProvider() -> None:
    registry = AIProviderRegistry()

    with pytest.raises(AIError) as error:
        registry.get("openai")

    assert error.value.code == "AI_PROVIDER_NOT_FOUND"


def testAIContractsRejectInvalidValues() -> None:
    message = AIMessage(AIMessageRole.USER, "Hello")

    with pytest.raises(AIError):
        AIRequest("", (message,))
    with pytest.raises(AIError):
        AIRequest("model", (message,), temperature=3)
    with pytest.raises(AIError):
        AIUsage(-1, 0)
    with pytest.raises(AIError):
        AIResponse("openai", "model", "")
