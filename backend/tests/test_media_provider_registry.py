import pytest

from app.media.errors import MediaError
from app.media.models import MediaSearchPage, MediaSearchQuery
from app.media.provider_registry import MediaProviderRegistry


class FakeMediaProvider:
    def __init__(self, providerId: str) -> None:
        self._providerId = providerId

    @property
    def providerId(self) -> str:
        return self._providerId

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage:
        return MediaSearchPage(
            self.providerId, query.text, 0, 0, query.limit, False, ()
        )


def testMediaProviderRegistryResolvesProvider() -> None:
    provider = FakeMediaProvider("Local")
    registry = MediaProviderRegistry((provider,))

    resolved = registry.get("LOCAL")

    assert resolved is provider
    assert registry.listProviderIds() == ("local",)


def testMediaProviderRegistryRejectsDuplicates() -> None:
    with pytest.raises(MediaError) as error:
        MediaProviderRegistry((FakeMediaProvider("local"), FakeMediaProvider("LOCAL")))

    assert error.value.code == "MEDIA_PROVIDER_ALREADY_REGISTERED"
