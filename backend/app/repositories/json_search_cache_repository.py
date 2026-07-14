import hashlib
import json
import logging
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.media.errors import MediaError

logger = logging.getLogger(__name__)
CACHE_SCHEMA_VERSION = 1


class JsonSearchCacheRepository:
    _lock = threading.RLock()

    def __init__(self, cacheDirectory: Path, providerName: str) -> None:
        self.cacheDirectory = cacheDirectory.expanduser().resolve()
        self.providerName = providerName
        self.errorPrefix = providerName.upper().replace(" ", "_")

    def get(
        self, cacheKey: str, now: datetime, ttlSeconds: int
    ) -> dict[str, Any] | None:
        path = self._path(cacheKey)
        with self._lock:
            if not path.exists():
                return None
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cachedAt, response = self._parse(data)
                if now - cachedAt >= timedelta(seconds=ttlSeconds):
                    path.unlink(missing_ok=True)
                    return None
                return response
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
                self._discardInvalid(path)
                if isinstance(error, OSError):
                    raise MediaError(
                        f"{self.errorPrefix}_SEARCH_CACHE_READ_FAILED",
                        f"Unable to read {self.providerName} search cache.",
                    ) from error
                return None

    def set(self, cacheKey: str, response: dict[str, Any], now: datetime) -> None:
        self.cacheDirectory.mkdir(parents=True, exist_ok=True)
        targetPath = self._path(cacheKey)
        temporaryPath = self.cacheDirectory / f".{uuid4().hex}.tmp"
        payload = {
            "schemaVersion": CACHE_SCHEMA_VERSION,
            "cachedAt": now.astimezone(UTC).isoformat(),
            "response": response,
        }
        with self._lock:
            try:
                temporaryPath.write_text(
                    json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
                    encoding="utf-8",
                )
                os.replace(temporaryPath, targetPath)
            except (OSError, TypeError, ValueError) as error:
                raise MediaError(
                    f"{self.errorPrefix}_SEARCH_CACHE_WRITE_FAILED",
                    f"Unable to write {self.providerName} search cache.",
                ) from error
            finally:
                temporaryPath.unlink(missing_ok=True)

    def pruneExpired(self, now: datetime, ttlSeconds: int) -> None:
        if not self.cacheDirectory.is_dir():
            return
        with self._lock:
            for path in self.cacheDirectory.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    cachedAt, _response = self._parse(data)
                    if now - cachedAt >= timedelta(seconds=ttlSeconds):
                        path.unlink(missing_ok=True)
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                    self._discardInvalid(path)

    def hashKey(self, fields: dict[str, Any]) -> str:
        canonical = json.dumps(
            fields, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _path(self, cacheKey: str) -> Path:
        if len(cacheKey) != 64 or any(
            character not in "0123456789abcdef" for character in cacheKey
        ):
            raise ValueError(f"{self.providerName} search cache key is invalid.")
        return self.cacheDirectory / f"{cacheKey}.json"

    def _parse(self, data: Any) -> tuple[datetime, dict[str, Any]]:
        if (
            not isinstance(data, dict)
            or data.get("schemaVersion") != CACHE_SCHEMA_VERSION
        ):
            raise ValueError
        cachedAt = datetime.fromisoformat(str(data.get("cachedAt")))
        response = data.get("response")
        if cachedAt.tzinfo is None or not isinstance(response, dict):
            raise ValueError
        return cachedAt.astimezone(UTC), response

    def _discardInvalid(self, path: Path) -> None:
        logger.warning(
            "Discarding invalid %s search cache file %s", self.providerName, path
        )
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Unable to remove invalid search cache file %s", path)
