import asyncio

import pytest

from app.ai.errors import AIError
from app.ai.models import AIMessage, AIMessageRole, AIRequest, AIResponse
from app.ai.retrying_provider import RetryingAIProvider


class FlakyProvider:
    providerId = "flaky"

    def __init__(self, failures: list[AIError]) -> None:
        self.failures = failures
        self.attempts = 0

    async def generate(self, request: AIRequest) -> AIResponse:
        self.attempts += 1
        if self.failures:
            raise self.failures.pop(0)
        return AIResponse(self.providerId, request.model, "success")


def createRequest() -> AIRequest:
    return AIRequest(
        "model",
        (AIMessage(AIMessageRole.USER, "hello"),),
    )


def testRetryingProviderRetriesTransientErrorsWithBackoff() -> None:
    provider = FlakyProvider(
        [
            AIError("AI_PROVIDER_TIMEOUT", "timeout"),
            AIError("AI_PROVIDER_RATE_LIMITED", "limited"),
        ]
    )
    delays: list[float] = []

    async def recordDelay(delay: float) -> None:
        delays.append(delay)

    retryingProvider = RetryingAIProvider(provider, 3, 0.5, 2, recordDelay)

    response = asyncio.run(retryingProvider.generate(createRequest()))

    assert response.content == "success"
    assert provider.attempts == 3
    assert delays == [0.5, 1.0]


def testRetryingProviderDoesNotRetryPermanentError() -> None:
    provider = FlakyProvider([AIError("AI_MODEL_NOT_FOUND", "missing")])
    retryingProvider = RetryingAIProvider(provider, 3, 0, 0)

    with pytest.raises(AIError) as error:
        asyncio.run(retryingProvider.generate(createRequest()))

    assert error.value.code == "AI_MODEL_NOT_FOUND"
    assert provider.attempts == 1
