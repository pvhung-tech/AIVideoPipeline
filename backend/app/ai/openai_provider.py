import logging
from typing import Any

import httpx

from app.ai.errors import AIError
from app.ai.models import AIRequest, AIResponse, AIUsage

logger = logging.getLogger(__name__)


class OpenAIProvider:
    providerId = "openai"

    def __init__(
        self,
        apiKey: str | None,
        baseUrl: str,
        timeoutSeconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.apiKey = apiKey.strip() if apiKey else None
        self.baseUrl = baseUrl.rstrip("/")
        self.timeoutSeconds = timeoutSeconds
        self.transport = transport

    async def generate(self, request: AIRequest) -> AIResponse:
        if self.apiKey is None:
            raise AIError(
                "AI_PROVIDER_NOT_CONFIGURED",
                "OpenAI is not configured. Set OPENAI_API_KEY.",
            )
        payload = self._buildPayload(request)
        headers = {"Authorization": f"Bearer {self.apiKey}"}
        try:
            async with httpx.AsyncClient(
                base_url=self.baseUrl,
                timeout=self.timeoutSeconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    "/v1/responses", json=payload, headers=headers
                )
                response.raise_for_status()
                data: Any = response.json()
        except httpx.TimeoutException as error:
            raise AIError(
                "AI_PROVIDER_TIMEOUT", "OpenAI did not respond before the timeout."
            ) from error
        except httpx.ConnectError as error:
            raise AIError(
                "AI_PROVIDER_UNAVAILABLE", "OpenAI is currently unavailable."
            ) from error
        except httpx.HTTPStatusError as error:
            raise self._httpError(error.response.status_code) from error
        except (httpx.RequestError, ValueError) as error:
            logger.exception("OpenAI request failed")
            raise AIError(
                "AI_PROVIDER_REQUEST_FAILED", "The OpenAI request failed."
            ) from error
        return self._parseResponse(data, request.model)

    def _buildPayload(self, request: AIRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "input": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "max_output_tokens": request.maxOutputTokens,
        }
        if request.responseSchema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "scene_analysis",
                    "strict": True,
                    "schema": request.responseSchema,
                }
            }
        return payload

    def _parseResponse(self, data: Any, requestedModel: str) -> AIResponse:
        if not isinstance(data, dict):
            raise AIError(
                "INVALID_AI_PROVIDER_RESPONSE", "OpenAI returned an invalid response."
            )
        content = self._extractOutputText(data)
        usageData = data.get("usage")
        usage = self._parseUsage(usageData)
        model = data.get("model")
        responseId = data.get("id")
        metadata = {"responseId": responseId} if isinstance(responseId, str) else None
        return AIResponse(
            providerId=self.providerId,
            model=model if isinstance(model, str) and model.strip() else requestedModel,
            content=content,
            usage=usage,
            metadata=metadata,
        )

    def _extractOutputText(self, data: dict[str, Any]) -> str:
        outputText = data.get("output_text")
        if isinstance(outputText, str) and outputText.strip():
            return outputText
        output = data.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or not isinstance(
                    item.get("content"), list
                ):
                    continue
                for contentItem in item["content"]:
                    if (
                        isinstance(contentItem, dict)
                        and contentItem.get("type") == "output_text"
                    ):
                        text = contentItem.get("text")
                        if isinstance(text, str) and text.strip():
                            return text
        raise AIError(
            "INVALID_AI_PROVIDER_RESPONSE", "OpenAI response content is missing."
        )

    def _parseUsage(self, usageData: Any) -> AIUsage | None:
        if not isinstance(usageData, dict):
            return None
        return AIUsage(
            inputTokens=self._tokenCount(usageData.get("input_tokens")),
            outputTokens=self._tokenCount(usageData.get("output_tokens")),
        )

    def _tokenCount(self, value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _httpError(self, statusCode: int) -> AIError:
        if statusCode in (401, 403):
            return AIError(
                "AI_PROVIDER_AUTHENTICATION_FAILED",
                "OpenAI authentication failed.",
            )
        if statusCode == 429:
            return AIError(
                "AI_PROVIDER_RATE_LIMITED", "OpenAI rate limit was exceeded."
            )
        if statusCode >= 500:
            return AIError(
                "AI_PROVIDER_REQUEST_FAILED",
                f"OpenAI request failed with status {statusCode}.",
            )
        return AIError(
            "AI_PROVIDER_REQUEST_REJECTED",
            f"OpenAI rejected the request with status {statusCode}.",
        )
