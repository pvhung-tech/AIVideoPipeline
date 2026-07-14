import logging
from typing import Any

import httpx

from app.ai.errors import AIError
from app.ai.models import AIRequest, AIResponse, AIUsage

logger = logging.getLogger(__name__)


class OllamaProvider:
    providerId = "ollama"

    def __init__(
        self,
        baseUrl: str,
        timeoutSeconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.baseUrl = baseUrl.rstrip("/")
        self.timeoutSeconds = timeoutSeconds
        self.transport = transport

    async def generate(self, request: AIRequest) -> AIResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.maxOutputTokens,
            },
        }
        if request.responseSchema is not None:
            payload["format"] = request.responseSchema

        try:
            async with httpx.AsyncClient(
                base_url=self.baseUrl,
                timeout=self.timeoutSeconds,
                transport=self.transport,
            ) as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                data: Any = response.json()
        except httpx.TimeoutException as error:
            raise AIError(
                "AI_PROVIDER_TIMEOUT", "Ollama did not respond before the timeout."
            ) from error
        except httpx.ConnectError as error:
            raise AIError(
                "AI_PROVIDER_UNAVAILABLE",
                "Ollama is not available at the configured address.",
            ) from error
        except httpx.HTTPStatusError as error:
            logger.warning("Ollama returned HTTP status %s", error.response.status_code)
            raise self._httpError(error.response.status_code) from error
        except (httpx.RequestError, ValueError) as error:
            logger.exception("Ollama request failed")
            raise AIError(
                "AI_PROVIDER_REQUEST_FAILED", "The Ollama request failed."
            ) from error

        return self._parseResponse(data, request.model)

    def _parseResponse(self, data: Any, requestedModel: str) -> AIResponse:
        if not isinstance(data, dict):
            raise AIError(
                "INVALID_AI_PROVIDER_RESPONSE", "Ollama returned an invalid response."
            )
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise AIError(
                "INVALID_AI_PROVIDER_RESPONSE", "Ollama response content is missing."
            )
        usage = AIUsage(
            inputTokens=self._tokenCount(data.get("prompt_eval_count")),
            outputTokens=self._tokenCount(data.get("eval_count")),
        )
        model = data.get("model")
        return AIResponse(
            providerId=self.providerId,
            model=model if isinstance(model, str) and model.strip() else requestedModel,
            content=message["content"],
            usage=usage,
        )

    def _tokenCount(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _httpError(self, statusCode: int) -> AIError:
        if statusCode == 429:
            return AIError(
                "AI_PROVIDER_RATE_LIMITED", "Ollama rate limit was exceeded."
            )
        if statusCode >= 500:
            return AIError(
                "AI_PROVIDER_REQUEST_FAILED",
                f"Ollama request failed with status {statusCode}.",
            )
        if statusCode == 404:
            return AIError("AI_MODEL_NOT_FOUND", "The Ollama model was not found.")
        return AIError(
            "AI_PROVIDER_REQUEST_REJECTED",
            f"Ollama rejected the request with status {statusCode}.",
        )
