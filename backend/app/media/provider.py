from typing import Protocol

from app.media.models import MediaSearchPage, MediaSearchQuery


class MediaSearchProvider(Protocol):
    @property
    def providerId(self) -> str: ...

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage: ...
