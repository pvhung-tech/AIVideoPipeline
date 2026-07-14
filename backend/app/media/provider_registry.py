import re

from app.media.errors import MediaError
from app.media.provider import MediaSearchProvider

PROVIDER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class MediaProviderRegistry:
    def __init__(self, providers: tuple[MediaSearchProvider, ...] = ()) -> None:
        self.providers: dict[str, MediaSearchProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: MediaSearchProvider) -> None:
        providerId = self._normalizeProviderId(provider.providerId)
        if providerId in self.providers:
            raise MediaError(
                "MEDIA_PROVIDER_ALREADY_REGISTERED",
                f"Media provider '{providerId}' is already registered.",
            )
        self.providers[providerId] = provider

    def get(self, providerId: str) -> MediaSearchProvider:
        normalizedId = self._normalizeProviderId(providerId)
        provider = self.providers.get(normalizedId)
        if provider is None:
            raise MediaError(
                "MEDIA_PROVIDER_NOT_FOUND",
                f"Media provider '{normalizedId}' is not registered.",
            )
        return provider

    def listProviderIds(self) -> tuple[str, ...]:
        return tuple(sorted(self.providers))

    def _normalizeProviderId(self, providerId: str) -> str:
        normalizedId = providerId.strip().lower()
        if not PROVIDER_ID_PATTERN.fullmatch(normalizedId):
            raise MediaError(
                "INVALID_MEDIA_PROVIDER_ID", "Media provider ID is invalid."
            )
        return normalizedId
