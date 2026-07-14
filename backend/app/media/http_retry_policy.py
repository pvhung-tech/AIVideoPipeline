import random
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


class HttpRetryPolicy:
    def __init__(
        self,
        initialDelaySeconds: float,
        maxDelaySeconds: float,
        jitterRatio: float,
        nowProvider: Callable[[], datetime] | None = None,
        randomProvider: Callable[[], float] | None = None,
    ) -> None:
        if (
            initialDelaySeconds < 0
            or maxDelaySeconds < initialDelaySeconds
            or jitterRatio < 0
            or jitterRatio > 1
        ):
            raise ValueError("HTTP retry settings are invalid.")
        self.initialDelaySeconds = initialDelaySeconds
        self.maxDelaySeconds = maxDelaySeconds
        self.jitterRatio = jitterRatio
        self.nowProvider = nowProvider or (lambda: datetime.now(UTC))
        self.randomProvider = randomProvider or random.random

    def isRetryableStatus(self, statusCode: int) -> bool:
        return statusCode == 429 or statusCode >= 500

    def delay(self, response: httpx.Response, attempt: int) -> float:
        parsedRetryAfter = self._parseRetryAfter(response.headers.get("Retry-After"))
        if parsedRetryAfter is not None:
            return min(parsedRetryAfter, self.maxDelaySeconds)
        reset = self._nonNegativeFloat(response.headers.get("X-RateLimit-Reset"))
        if reset is not None:
            return min(reset, self.maxDelaySeconds)
        return self.fallbackDelay(attempt)

    def fallbackDelay(self, attempt: int) -> float:
        baseDelay = self.initialDelaySeconds * (2**attempt)
        randomValue = min(1.0, max(0.0, self.randomProvider()))
        jitteredDelay = baseDelay * (1 + self.jitterRatio * randomValue)
        return float(min(jitteredDelay, self.maxDelaySeconds))

    def _parseRetryAfter(self, value: str | None) -> float | None:
        seconds = self._nonNegativeFloat(value)
        if seconds is not None:
            return seconds
        if value is None:
            return None
        try:
            retryAt = parsedate_to_datetime(value)
            if retryAt.tzinfo is None:
                retryAt = retryAt.replace(tzinfo=UTC)
            return max(0.0, (retryAt - self.nowProvider()).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None

    def _nonNegativeFloat(self, value: str | None) -> float | None:
        try:
            parsed = float(value) if value is not None else None
        except ValueError:
            return None
        return parsed if parsed is not None and parsed >= 0 else None
