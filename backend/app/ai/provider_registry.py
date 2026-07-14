import re

from app.ai.errors import AIError
from app.ai.provider import AIProvider

PROVIDER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class AIProviderRegistry:
    def __init__(self, providers: tuple[AIProvider, ...] = ()) -> None:
        self.providers: dict[str, AIProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: AIProvider) -> None:
        providerId = self._normalizeProviderId(provider.providerId)
        if providerId in self.providers:
            raise AIError(
                "AI_PROVIDER_ALREADY_REGISTERED",
                f"AI provider '{providerId}' is already registered.",
            )
        self.providers[providerId] = provider

    def get(self, providerId: str) -> AIProvider:
        normalizedId = self._normalizeProviderId(providerId)
        provider = self.providers.get(normalizedId)
        if provider is None:
            raise AIError(
                "AI_PROVIDER_NOT_FOUND",
                f"AI provider '{normalizedId}' is not registered.",
            )
        return provider

    def listProviderIds(self) -> tuple[str, ...]:
        return tuple(sorted(self.providers))

    def _normalizeProviderId(self, providerId: str) -> str:
        normalizedId = providerId.strip().lower()
        if not PROVIDER_ID_PATTERN.fullmatch(normalizedId):
            raise AIError(
                "INVALID_AI_PROVIDER_ID",
                "AI provider ID must use lowercase letters, numbers, "
                "hyphens, or underscores.",
            )
        return normalizedId
