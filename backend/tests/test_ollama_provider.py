import asyncio
import json

import httpx
import pytest

from app.ai.errors import AIError
from app.ai.models import AIMessage, AIMessageRole, AIRequest
from app.ai.ollama_provider import OllamaProvider


def testOllamaProviderUsesChatAndStructuredOutput() -> None:
    capturedPayload: dict[str, object] = {}

    def handleRequest(request: httpx.Request) -> httpx.Response:
        capturedPayload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "llama-test",
                "message": {"role": "assistant", "content": '{"ok":true}'},
                "prompt_eval_count": 12,
                "eval_count": 7,
            },
        )

    provider = OllamaProvider(
        "http://ollama.test",
        10,
        transport=httpx.MockTransport(handleRequest),
    )
    request = AIRequest(
        model="llama-test",
        messages=(AIMessage(AIMessageRole.USER, "Analyze"),),
        responseSchema={"type": "object"},
    )

    response = asyncio.run(provider.generate(request))

    assert capturedPayload["stream"] is False
    assert capturedPayload["format"] == {"type": "object"}
    assert response.content == '{"ok":true}'
    assert response.usage is not None
    assert response.usage.totalTokens == 19


def testOllamaProviderMapsConnectionFailure() -> None:
    def handleRequest(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection failed", request=request)

    provider = OllamaProvider(
        "http://ollama.test",
        10,
        transport=httpx.MockTransport(handleRequest),
    )
    request = AIRequest(
        model="model",
        messages=(AIMessage(AIMessageRole.USER, "Analyze"),),
    )

    with pytest.raises(AIError) as error:
        asyncio.run(provider.generate(request))

    assert error.value.code == "AI_PROVIDER_UNAVAILABLE"
