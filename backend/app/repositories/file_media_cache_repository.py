import json
import os
import threading
from pathlib import Path
from uuid import uuid4

from app.media.cache_manifest import MediaCacheManifest
from app.media.errors import MediaError

MANIFEST_FILE_NAME = "manifest.json"


class FileMediaCacheRepository:
    _lock = threading.RLock()

    def load(self, cacheRoot: Path) -> MediaCacheManifest:
        manifestPath = cacheRoot / MANIFEST_FILE_NAME
        with self._lock:
            if not manifestPath.exists():
                return MediaCacheManifest(())
            try:
                data = json.loads(manifestPath.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise MediaError(
                    "INVALID_MEDIA_CACHE_MANIFEST",
                    "Media cache manifest could not be read.",
                ) from error
            return MediaCacheManifest.fromDictionary(data)

    def save(self, cacheRoot: Path, manifest: MediaCacheManifest) -> None:
        cacheRoot.mkdir(parents=True, exist_ok=True)
        manifestPath = cacheRoot / MANIFEST_FILE_NAME
        temporaryPath = cacheRoot / f".{uuid4().hex}.manifest.tmp"
        with self._lock:
            try:
                temporaryPath.write_text(
                    json.dumps(
                        manifest.toDictionary(),
                        ensure_ascii=True,
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                os.replace(temporaryPath, manifestPath)
            except OSError as error:
                raise MediaError(
                    "MEDIA_CACHE_MANIFEST_WRITE_FAILED",
                    "Unable to write media cache manifest.",
                ) from error
            finally:
                temporaryPath.unlink(missing_ok=True)
