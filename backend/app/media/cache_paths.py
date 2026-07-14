from pathlib import Path

from app.media.cache_manifest import MediaCacheEntry
from app.media.errors import MediaError


def resolveCacheEntryPath(cacheRoot: Path, entry: MediaCacheEntry) -> Path:
    relativePath = Path(entry.relativePath)
    candidate = cacheRoot / relativePath
    path = candidate.resolve()
    if (
        relativePath.is_absolute()
        or _containsSymlink(cacheRoot, relativePath)
        or not path.is_relative_to(cacheRoot.resolve())
    ):
        raise MediaError("INVALID_MEDIA_CACHE_MANIFEST", "Cache entry path is invalid.")
    return path


def _containsSymlink(cacheRoot: Path, relativePath: Path) -> bool:
    candidate = cacheRoot
    for part in relativePath.parts:
        candidate /= part
        if candidate.is_symlink():
            return True
    return False
