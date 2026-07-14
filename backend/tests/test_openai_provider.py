import asyncio
import json

import httpx
import pytest

from app.ai.errors import AIError
from app.ai.models import AIMessage, AIMessageRole, AIRequest
from app.ai.openai_provider import OpenAIProvider


def createRequest() -> AIRequest:
    return AIRequest(
        model="gpt-test",
        messages=(AIMessage(AIMessageRole.USER, "Analyze"),),
        responseSchema={"type": "object"},
    )


def testOpenAIProviderUsesResponsesStructuredOutput() -> None:
    capturedPayload: dict[str, object] = {}
    capturedAuthorization = ""

    def handleRequest(request: httpx.Request) -> httpx.Response:
        nonlocal capturedAuthorization
        capturedPayload.update(json.loads(request.content))
        capturedAuthorization = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "id": "resp_123",
                "model": "gpt-test",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"description":"scene"}',
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = OpenAIProvider(
        "secret-key",
        "https://api.openai.test",
        10,
        httpx.MockTransport(handleRequest),
    )

    response = asyncio.run(provider.generate(createRequest()))

    assert capturedAuthorization == "Bearer secret-key"
    assert capturedPayload["model"] == "gpt-test"
    textConfig = capturedPayload["text"]
    assert isinstance(textConfig, dict)
    formatConfig = textConfig["format"]
    assert isinstance(formatConfig, dict)
    assert formatConfig["type"] == "json_schema"
    assert response.content == '{"description":"scene"}'
    assert response.usage is not None
    assert response.usage.totalTokens == 15


def testOpenAIProviderRequiresApiKey() -> None:
    provider = OpenAIProvider(None, "https://api.openai.com", 10)

    with pytest.raises(AIError) as error:
        asyncio.run(provider.generate(createRequest()))

    assert error.value.code == "AI_PROVIDER_NOT_CONFIGURED"


def testOpenAIProviderMapsRateLimit() -> None:
    def handleRequest(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "limited"}})

    provider = OpenAIProvider(
        "secret-key",
        "https://api.openai.test",
        10,
        httpx.MockTransport(handleRequest),
    )

    with pytest.raises(AIError) as error:
        asyncio.run(provider.generate(createRequest()))

    assert error.value.code == "AI_PROVIDER_RATE_LIMITED"
