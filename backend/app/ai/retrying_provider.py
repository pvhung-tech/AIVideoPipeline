import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.ai.errors import AIError
from app.ai.models import AIRequest, AIResponse
from app.ai.provider import AIProvider

logger = logging.getLogger(__name__)

RETRYABLE_AI_ERROR_CODES = {
    "AI_PROVIDER_TIMEOUT",
    "AI_PROVIDER_UNAVAILABLE",
    "AI_PROVIDER_RATE_LIMITED",
    "AI_PROVIDER_REQUEST_FAILED",
}

SleepFunction = Callable[[float], Awaitable[None]]


class RetryingAIProvider:
    def __init__(
        self,
        provider: AIProvider,
        maxAttempts: int,
        initialDelaySeconds: float,
        maxDelaySeconds: float,
        sleep: SleepFunction = asyncio.sleep,
    ) -> None:
        if maxAttempts < 1:
            raise ValueError("Retry attempts must be positive.")
        if initialDelaySeconds < 0 or maxDelaySeconds < initialDelaySeconds:
            raise ValueError("Retry delays are invalid.")
        self.provider = provider
        self.maxAttempts = maxAttempts
        self.initialDelaySeconds = initialDelaySeconds
        self.maxDelaySeconds = maxDelaySeconds
        self.sleep = sleep

    @property
    def providerId(self) -> str:
        return self.provider.providerId

    async def generate(self, request: AIRequest) -> AIResponse:
        delaySeconds = self.initialDelaySeconds
        for attempt in range(1, self.maxAttempts + 1):
            try:
                return await self.provider.generate(request)
            except AIError as error:
                if not self._shouldRetry(error, attempt):
                    raise
                logger.warning(
                    "Retrying AI provider %s after %s (attempt %s/%s)",
                    self.providerId,
                    error.code,
                    attempt,
                    self.maxAttempts,
                )
                await self.sleep(delaySeconds)
                delaySeconds = min(delaySeconds * 2, self.maxDelaySeconds)
        raise RuntimeError("Retry loop completed without a result.")

    def _shouldRetry(self, error: AIError, attempt: int) -> bool:
        return error.code in RETRYABLE_AI_ERROR_CODES and attempt < self.maxAttempts
