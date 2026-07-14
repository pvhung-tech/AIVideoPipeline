import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from app.media.errors import MediaError
from app.media.models import (
    MediaSearchItem,
    MediaSearchPage,
    MediaSearchQuery,
    MediaType,
)

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}


class LocalLibraryProvider:
    providerId = "local"

    def __init__(self, libraryPaths: tuple[Path, ...], maxScannedFiles: int) -> None:
        if maxScannedFiles < 1:
            raise ValueError("Maximum scanned files must be positive.")
        self.libraryPaths = tuple(
            dict.fromkeys(path.expanduser().resolve() for path in libraryPaths)
        )
        self.maxScannedFiles = maxScannedFiles

    async def search(self, query: MediaSearchQuery) -> MediaSearchPage:
        return await asyncio.to_thread(self._search, query)

    def _search(self, query: MediaSearchQuery) -> MediaSearchPage:
        roots = self._availableRoots()
        tokens = tuple(re.findall(r"\w+", query.text.casefold()))
        if not tokens:
            raise MediaError(
                "INVALID_MEDIA_QUERY",
                "Media query must contain letters or numbers.",
            )
        matches: list[MediaSearchItem] = []
        matchedIds: set[str] = set()
        scannedFiles = 0
        truncated = False
        for root in roots:
            try:
                for path in root.rglob("*"):
                    if not self._isRegularFile(path):
                        continue
                    scannedFiles += 1
                    if scannedFiles > self.maxScannedFiles:
                        truncated = True
                        break
                    mediaType = self._mediaType(path)
                    if mediaType is None or mediaType not in query.mediaTypes:
                        continue
                    item = self._createItem(root, path, mediaType, tokens, query.text)
                    if item is not None and item.id not in matchedIds:
                        matches.append(item)
                        matchedIds.add(item.id)
            except OSError:
                logger.warning("Unable to scan local media directory %s", root)
            if truncated:
                break

        matches.sort(
            key=lambda item: (
                -item.score,
                -(item.modifiedAt.timestamp() if item.modifiedAt else 0),
                item.sourceUri,
            )
        )
        pageItems = tuple(matches[query.offset : query.offset + query.limit])
        return MediaSearchPage(
            providerId=self.providerId,
            query=query.text,
            totalResults=len(matches),
            offset=query.offset,
            limit=query.limit,
            truncated=truncated,
            items=pageItems,
        )

    def _availableRoots(self) -> tuple[Path, ...]:
        if not self.libraryPaths:
            raise MediaError(
                "MEDIA_LIBRARY_NOT_CONFIGURED",
                "Configure LOCAL_MEDIA_LIBRARY_PATHS before searching local media.",
            )
        roots = tuple(path for path in self.libraryPaths if path.is_dir())
        if not roots:
            raise MediaError(
                "MEDIA_LIBRARY_NOT_FOUND",
                "None of the configured local media directories exist.",
            )
        return roots

    def _mediaType(self, path: Path) -> MediaType | None:
        extension = path.suffix.casefold()
        if extension in IMAGE_EXTENSIONS:
            return MediaType.IMAGE
        if extension in VIDEO_EXTENSIONS:
            return MediaType.VIDEO
        if extension in AUDIO_EXTENSIONS:
            return MediaType.AUDIO
        return None

    def _isRegularFile(self, path: Path) -> bool:
        try:
            return not path.is_symlink() and path.is_file()
        except OSError:
            logger.warning("Unable to inspect local media path %s", path)
            return False

    def _createItem(
        self,
        root: Path,
        path: Path,
        mediaType: MediaType,
        tokens: tuple[str, ...],
        queryText: str,
    ) -> MediaSearchItem | None:
        try:
            resolvedPath = path.resolve()
            if not resolvedPath.is_relative_to(root):
                return None
            relativePath = resolvedPath.relative_to(root)
            candidateText = " ".join(relativePath.with_suffix("").parts).casefold()
            matchedTokens = sum(token in candidateText for token in tokens)
            if matchedTokens == 0:
                return None
            phraseBonus = 1.0 if queryText.casefold() in candidateText else 0.0
            score = round((matchedTokens / len(tokens)) + phraseBonus, 6)
            fileStat = resolvedPath.stat()
            return MediaSearchItem(
                id=self._mediaId(resolvedPath),
                providerId=self.providerId,
                mediaType=mediaType,
                title=resolvedPath.stem,
                sourceUri=resolvedPath.as_uri(),
                previewUri=resolvedPath.as_uri(),
                fileSizeBytes=fileStat.st_size,
                modifiedAt=datetime.fromtimestamp(fileStat.st_mtime, UTC),
                score=score,
                license="local",
            )
        except OSError:
            logger.warning("Unable to inspect local media file %s", path)
            return None

    def _mediaId(self, path: Path) -> str:
        digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
        return f"local-{digest[:24]}"
