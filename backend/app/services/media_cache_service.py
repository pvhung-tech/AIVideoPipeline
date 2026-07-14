import asyncio
import hashlib
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import ParseResult, unquote, urlparse
from uuid import uuid4

import httpx

from app.media.cache_manifest import (
    MediaCacheCleanupResult,
    MediaCacheEntry,
    MediaCacheManifest,
    MediaCacheSource,
    MediaFingerprintBackfillResult,
    MediaMetadataBackfillResult,
)
from app.media.cache_models import CachedMedia, MediaCacheDiagnostics
from app.media.cache_paths import resolveCacheEntryPath
from app.media.errors import MediaError
from app.media.media_fingerprint_service import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    MediaFingerprints,
    MediaFingerprintService,
)
from app.media.media_metadata_service import MediaMetadataService
from app.repositories.file_media_cache_repository import FileMediaCacheRepository
from app.services.project_service import ProjectService

CHUNK_SIZE = 1024 * 1024
PEXELS_HOST_SUFFIXES = (".pexels.com",)
PIXABAY_HOST_SUFFIXES = (".pixabay.com",)
WIKIMEDIA_HOST_SUFFIXES = (".wikimedia.org",)
DVIDS_HOST_SUFFIXES = (".dvidshub.net",)
DVIDS_CLOUDFRONT_HOSTS = ("d34w7g4gy10iej.cloudfront.net",)
REMOTE_PROVIDER_IDS = {"pexels", "pixabay", "wikimedia", "dvids"}
logger = logging.getLogger(__name__)


class DvidsSourceResolver(Protocol):
    async def resolveAssetSource(self, sourceUri: str) -> str: ...


class MediaCacheService:
    _manifestLock = threading.RLock()
    _fingerprintBackfillLock = threading.Lock()
    _fingerprintBackfillKeys: set[tuple[str, str]] = set()

    def __init__(
        self,
        projectService: ProjectService,
        localLibraryPaths: tuple[Path, ...],
        maxFileSizeBytes: int,
        timeoutSeconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        maxTotalSizeBytes: int = 10 * 1024 * 1024 * 1024,
        maxAgeDays: int = 30,
        repository: FileMediaCacheRepository | None = None,
        fingerprintService: MediaFingerprintService | None = None,
        metadataService: MediaMetadataService | None = None,
        dvidsSourceResolver: DvidsSourceResolver | None = None,
    ) -> None:
        if (
            maxFileSizeBytes < 1
            or timeoutSeconds <= 0
            or maxTotalSizeBytes < 0
            or maxAgeDays < 0
        ):
            raise ValueError("Media cache limits must be positive.")
        self.projectService = projectService
        self.localLibraryPaths = tuple(
            path.expanduser().resolve() for path in localLibraryPaths
        )
        self.maxFileSizeBytes = maxFileSizeBytes
        self.timeoutSeconds = timeoutSeconds
        self.maxTotalSizeBytes = maxTotalSizeBytes
        self.maxAgeDays = maxAgeDays
        self.transport = transport
        self.repository = repository or FileMediaCacheRepository()
        self.fingerprintService = fingerprintService or MediaFingerprintService()
        self.metadataService = metadataService or MediaMetadataService()
        self.dvidsSourceResolver = dvidsSourceResolver

    async def cache(
        self, providerId: str, mediaId: str, sourceUri: str, fileName: str | None
    ) -> CachedMedia:
        totalStarted = time.perf_counter()
        timings: dict[str, float] = {
            "sourceHashSeconds": 0.0,
            "sourceFileWriteSeconds": 0.0,
        }
        provider = providerId.strip().lower()
        if not mediaId.strip():
            raise MediaError("INVALID_MEDIA_ID", "Media ID cannot be empty.")
        project = self.projectService.getCurrentProject()
        if project is None:
            raise MediaError("NO_ACTIVE_PROJECT", "No project is currently open.")
        cacheRoot = project.path / "cache"
        cacheRoot.mkdir(parents=True, exist_ok=True)
        sourceHit = self._sourceCacheHit(cacheRoot, provider, mediaId, sourceUri)
        if sourceHit is not None:
            return sourceHit
        extension = self._extension(fileName, sourceUri)
        temporaryPath = cacheRoot / f".{uuid4().hex}.part"
        try:
            sourceStarted = time.perf_counter()
            digest, size = await self._writeSource(
                provider, sourceUri, temporaryPath, timings
            )
            timings["sourceTransferSeconds"] = self._elapsed(sourceStarted)
            digestDirectory = cacheRoot / digest[:2]
            duplicateStarted = time.perf_counter()
            wasPresent = bool(tuple(digestDirectory.glob(f"{digest}.*")))
            hasFingerprints = self._hasFingerprints(cacheRoot, digest)
            timings["duplicateCheckSeconds"] = self._elapsed(duplicateStarted)
            fingerprintDeferred = self._shouldDeferFingerprint(
                provider, hasFingerprints
            )
            fingerprintStarted = time.perf_counter()
            fingerprints = (
                MediaFingerprints()
                if fingerprintDeferred
                else await self._fingerprint(
                    temporaryPath, wasPresent and hasFingerprints, extension
                )
            )
            timings["fingerprintSeconds"] = self._elapsed(fingerprintStarted)
            metadataStarted = time.perf_counter()
            durationMilliseconds = await self._probeDuration(
                temporaryPath, extension, wasPresent
            )
            timings["metadataSeconds"] = self._elapsed(metadataStarted)
            manifestStarted = time.perf_counter()
            with self._manifestLock:
                existingPaths = tuple(digestDirectory.glob(f"{digest}.*"))
                targetPath = (
                    existingPaths[0]
                    if existingPaths
                    else digestDirectory / f"{digest}{extension}"
                )
                duplicate = bool(existingPaths)
                if duplicate:
                    temporaryPath.unlink(missing_ok=True)
                else:
                    targetPath.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(temporaryPath, targetPath)
                try:
                    self._recordEntry(
                        cacheRoot,
                        targetPath,
                        digest,
                        size,
                        MediaCacheSource(provider, mediaId, sourceUri),
                        fingerprints,
                        durationMilliseconds,
                    )
                except MediaError:
                    if not duplicate:
                        targetPath.unlink(missing_ok=True)
                    raise
            timings["manifestSeconds"] = self._elapsed(manifestStarted)
            if fingerprintDeferred:
                self._scheduleFingerprintBackfill(
                    cacheRoot, targetPath, digest, extension
                )
            diagnostics = MediaCacheDiagnostics(
                providerId=provider,
                duplicate=duplicate,
                sizeBytes=size,
                sourceTransferSeconds=timings.get("sourceTransferSeconds", 0.0),
                sourceHashSeconds=round(timings["sourceHashSeconds"], 4),
                sourceFileWriteSeconds=round(timings["sourceFileWriteSeconds"], 4),
                duplicateCheckSeconds=timings.get("duplicateCheckSeconds", 0.0),
                fingerprintSeconds=timings.get("fingerprintSeconds", 0.0),
                metadataSeconds=timings.get("metadataSeconds", 0.0),
                manifestSeconds=timings.get("manifestSeconds", 0.0),
                totalSeconds=self._elapsed(totalStarted),
                fingerprintDeferred=fingerprintDeferred,
            )
            return CachedMedia(
                mediaId, provider, digest, targetPath, size, duplicate, diagnostics
            )
        except OSError as error:
            raise MediaError(
                "MEDIA_CACHE_WRITE_FAILED", "Unable to write media cache."
            ) from error
        finally:
            temporaryPath.unlink(missing_ok=True)

    def getManifest(self) -> MediaCacheManifest:
        cacheRoot = self._cacheRoot()
        with self._manifestLock:
            return self.repository.load(cacheRoot)

    def cleanup(
        self,
        dryRun: bool = True,
        maxTotalSizeBytes: int | None = None,
        maxAgeDays: int | None = None,
    ) -> MediaCacheCleanupResult:
        sizeLimit = (
            self.maxTotalSizeBytes if maxTotalSizeBytes is None else maxTotalSizeBytes
        )
        ageLimit = self.maxAgeDays if maxAgeDays is None else maxAgeDays
        if sizeLimit < 0 or ageLimit < 0:
            raise MediaError(
                "INVALID_MEDIA_CACHE_POLICY", "Cache cleanup limits cannot be negative."
            )
        cacheRoot = self._cacheRoot()
        with self._manifestLock:
            manifest = self.repository.load(cacheRoot)
            removed = self._cleanupCandidates(cacheRoot, manifest, sizeLimit, ageLimit)
            retained = tuple(
                entry for entry in manifest.entries if entry not in removed
            )
            if not dryRun:
                self._removeEntries(cacheRoot, removed)
                self.repository.save(cacheRoot, MediaCacheManifest(retained))
        return MediaCacheCleanupResult(
            dryRun=dryRun,
            removedEntries=removed,
            remainingEntries=len(retained),
            remainingSizeBytes=sum(entry.sizeBytes for entry in retained),
        )

    def backfillVideoMetadata(
        self,
        cacheRoot: Path | None = None,
        progress: Callable[[int, int, int, int, tuple[str, ...]], None] | None = None,
        isCancelled: Callable[[], bool] | None = None,
    ) -> MediaMetadataBackfillResult:
        root = cacheRoot or self._cacheRoot()
        with self._manifestLock:
            entries = self.repository.load(root).entries
        videos = tuple(
            entry
            for entry in entries
            if self._entryPath(root, entry).suffix.lower()
            in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
        )
        durations: dict[str, int] = {}
        skipped = 0
        failed: list[str] = []
        processed = 0
        if progress:
            progress(0, len(videos), 0, 0, ())
        for entry in videos:
            if isCancelled and isCancelled():
                break
            if entry.durationMilliseconds is not None:
                skipped += 1
            else:
                self._probeBackfillEntry(root, entry, durations, failed)
            processed += 1
            if progress:
                progress(processed, len(videos), len(durations), skipped, tuple(failed))
        self._mergeBackfillDurations(root, durations)
        return MediaMetadataBackfillResult(
            len(videos), len(durations), skipped, tuple(failed)
        )

    def backfillMissingFingerprints(
        self,
        cacheRoot: Path | None = None,
        progress: Callable[[int, int, int, int, tuple[str, ...]], None] | None = None,
        isCancelled: Callable[[], bool] | None = None,
    ) -> MediaFingerprintBackfillResult:
        root = cacheRoot or self._cacheRoot()
        with self._manifestLock:
            entries = self.repository.load(root).entries
        candidates = tuple(
            entry for entry in entries if self._needsFingerprint(root, entry)
        )
        updated = 0
        skipped = 0
        failed: list[str] = []
        processed = 0
        if progress:
            progress(0, len(candidates), 0, 0, ())
        for entry in candidates:
            if isCancelled and isCancelled():
                break
            if self._backfillFingerprintEntry(root, entry, failed):
                updated += 1
            else:
                skipped += 1
            processed += 1
            if progress:
                progress(processed, len(candidates), updated, skipped, tuple(failed))
        return MediaFingerprintBackfillResult(
            len(candidates), updated, skipped, tuple(failed)
        )

    def _needsFingerprint(self, cacheRoot: Path, entry: MediaCacheEntry) -> bool:
        path = self._entryPath(cacheRoot, entry)
        extension = path.suffix.lower()
        if extension in IMAGE_EXTENSIONS:
            return entry.perceptualHash is None and path.is_file()
        if extension in VIDEO_EXTENSIONS:
            return entry.videoFingerprint is None and path.is_file()
        return False

    def _backfillFingerprintEntry(
        self, cacheRoot: Path, entry: MediaCacheEntry, failed: list[str]
    ) -> bool:
        path = self._entryPath(cacheRoot, entry)
        if not path.is_file():
            return False
        try:
            fingerprints = self.fingerprintService.fingerprint(path, path.suffix)
            return self._mergeFingerprints(cacheRoot, entry.contentHash, fingerprints)
        except MediaError as error:
            logger.warning(
                "Media fingerprint backfill failed for %s: %s",
                entry.contentHash,
                error.code,
            )
            failed.append(entry.contentHash)
            return False

    def _probeBackfillEntry(
        self,
        cacheRoot: Path,
        entry: MediaCacheEntry,
        durations: dict[str, int],
        failed: list[str],
    ) -> None:
        try:
            durations[entry.contentHash] = (
                self.metadataService.probeDurationMilliseconds(
                    self._entryPath(cacheRoot, entry)
                )
            )
        except MediaError as error:
            logger.warning(
                "Video metadata backfill failed for %s: %s",
                entry.contentHash,
                error.code,
            )
            failed.append(entry.contentHash)

    def _mergeBackfillDurations(
        self, cacheRoot: Path, durations: dict[str, int]
    ) -> None:
        if not durations:
            return
        with self._manifestLock:
            manifest = self.repository.load(cacheRoot)
            entries = tuple(
                (
                    replace(entry, durationMilliseconds=durations[entry.contentHash])
                    if entry.durationMilliseconds is None
                    and entry.contentHash in durations
                    else entry
                )
                for entry in manifest.entries
            )
            self.repository.save(cacheRoot, MediaCacheManifest(entries))

    def _mergeFingerprints(
        self, cacheRoot: Path, digest: str, fingerprints: MediaFingerprints
    ) -> bool:
        if not fingerprints.perceptualHash and not fingerprints.videoFingerprint:
            return False
        with self._manifestLock:
            manifest = self.repository.load(cacheRoot)
            changed = False
            entries: list[MediaCacheEntry] = []
            for entry in manifest.entries:
                if entry.contentHash != digest:
                    entries.append(entry)
                    continue
                perceptualHash = entry.perceptualHash or fingerprints.perceptualHash
                videoFingerprint = (
                    entry.videoFingerprint or fingerprints.videoFingerprint
                )
                changed = changed or (
                    perceptualHash != entry.perceptualHash
                    or videoFingerprint != entry.videoFingerprint
                )
                entries.append(
                    replace(
                        entry,
                        perceptualHash=perceptualHash,
                        videoFingerprint=videoFingerprint,
                    )
                )
            if changed:
                self.repository.save(cacheRoot, MediaCacheManifest(tuple(entries)))
            return changed

    def _recordEntry(
        self,
        cacheRoot: Path,
        targetPath: Path,
        digest: str,
        size: int,
        source: MediaCacheSource,
        fingerprints: MediaFingerprints,
        durationMilliseconds: int | None,
    ) -> None:
        manifest = self.repository.load(cacheRoot)
        timestamp = datetime.now(UTC)
        existing = next(
            (entry for entry in manifest.entries if entry.contentHash == digest), None
        )
        if existing is None:
            updated = MediaCacheEntry(
                contentHash=digest,
                relativePath=targetPath.relative_to(cacheRoot).as_posix(),
                sizeBytes=size,
                createdAt=timestamp,
                lastAccessedAt=timestamp,
                sources=(source,),
                perceptualHash=fingerprints.perceptualHash,
                videoFingerprint=fingerprints.videoFingerprint,
                durationMilliseconds=durationMilliseconds,
            )
        else:
            sources = existing.sources
            if source not in sources:
                sources += (source,)
            updated = replace(
                existing,
                lastAccessedAt=timestamp,
                sources=sources,
                perceptualHash=existing.perceptualHash or fingerprints.perceptualHash,
                videoFingerprint=(
                    existing.videoFingerprint or fingerprints.videoFingerprint
                ),
                durationMilliseconds=existing.durationMilliseconds
                or durationMilliseconds,
            )
        entries = tuple(
            sorted(
                (
                    updated if entry.contentHash == digest else entry
                    for entry in manifest.entries
                ),
                key=lambda entry: entry.contentHash,
            )
        )
        if existing is None:
            entries = tuple(
                sorted((*entries, updated), key=lambda entry: entry.contentHash)
            )
        self.repository.save(cacheRoot, MediaCacheManifest(entries))

    def _sourceCacheHit(
        self, cacheRoot: Path, providerId: str, mediaId: str, sourceUri: str
    ) -> CachedMedia | None:
        if providerId not in REMOTE_PROVIDER_IDS:
            return None
        started = time.perf_counter()
        with self._manifestLock:
            manifest = self.repository.load(cacheRoot)
            hit = next(
                (
                    entry
                    for entry in manifest.entries
                    if any(
                        source.providerId == providerId
                        and source.mediaId == mediaId
                        and source.sourceUri == sourceUri
                        for source in entry.sources
                    )
                ),
                None,
            )
            if hit is None:
                return None
            path = self._entryPath(cacheRoot, hit)
            if not path.is_file():
                return None
            timestamp = datetime.now(UTC)
            entries = tuple(
                replace(entry, lastAccessedAt=timestamp)
                if entry.contentHash == hit.contentHash
                else entry
                for entry in manifest.entries
            )
            self.repository.save(cacheRoot, MediaCacheManifest(entries))
        diagnostics = MediaCacheDiagnostics(
            providerId=providerId,
            duplicate=True,
            sizeBytes=hit.sizeBytes,
            sourceTransferSeconds=0.0,
            sourceHashSeconds=0.0,
            sourceFileWriteSeconds=0.0,
            duplicateCheckSeconds=0.0,
            fingerprintSeconds=0.0,
            metadataSeconds=0.0,
            manifestSeconds=self._elapsed(started),
            totalSeconds=self._elapsed(started),
            fingerprintDeferred=False,
        )
        return CachedMedia(
            mediaId,
            providerId,
            hit.contentHash,
            path,
            hit.sizeBytes,
            True,
            diagnostics,
        )

    async def _probeDuration(
        self, path: Path, extension: str, duplicate: bool
    ) -> int | None:
        if extension not in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS or duplicate:
            return None
        try:
            return await asyncio.to_thread(
                self.metadataService.probeDurationMilliseconds, path
            )
        except MediaError as error:
            logger.warning(
                "Media metadata unavailable for %s: %s", path.name, error.code
            )
            return None

    def _hasFingerprints(self, cacheRoot: Path, digest: str) -> bool:
        with self._manifestLock:
            entry = next(
                (
                    item
                    for item in self.repository.load(cacheRoot).entries
                    if item.contentHash == digest
                ),
                None,
            )
        return bool(entry and (entry.perceptualHash or entry.videoFingerprint))

    async def _fingerprint(
        self, targetPath: Path, duplicate: bool, extension: str
    ) -> MediaFingerprints:
        if duplicate:
            return MediaFingerprints()
        try:
            return await asyncio.to_thread(
                self.fingerprintService.fingerprint, targetPath, extension
            )
        except MediaError as error:
            logger.warning(
                "Media fingerprint unavailable for %s: %s",
                targetPath.name,
                error.code,
            )
            return MediaFingerprints()

    def _shouldDeferFingerprint(self, providerId: str, hasFingerprints: bool) -> bool:
        return providerId in REMOTE_PROVIDER_IDS and not hasFingerprints

    def _scheduleFingerprintBackfill(
        self, cacheRoot: Path, targetPath: Path, digest: str, extension: str
    ) -> None:
        key = (str(cacheRoot.resolve()), digest)
        with self._fingerprintBackfillLock:
            if key in self._fingerprintBackfillKeys:
                return
            self._fingerprintBackfillKeys.add(key)
        worker = threading.Thread(
            target=self._runFingerprintBackfill,
            args=(key, cacheRoot, targetPath, digest, extension),
            daemon=True,
            name=f"media-fingerprint-{digest[:8]}",
        )
        worker.start()

    def _runFingerprintBackfill(
        self,
        key: tuple[str, str],
        cacheRoot: Path,
        targetPath: Path,
        digest: str,
        extension: str,
    ) -> None:
        try:
            if not targetPath.is_file():
                return
            fingerprints = self.fingerprintService.fingerprint(targetPath, extension)
            self._mergeFingerprints(cacheRoot, digest, fingerprints)
        except MediaError as error:
            logger.warning(
                "Background media fingerprint unavailable for %s: %s",
                digest,
                error.code,
            )
        finally:
            with self._fingerprintBackfillLock:
                self._fingerprintBackfillKeys.discard(key)

    def _cleanupCandidates(
        self,
        cacheRoot: Path,
        manifest: MediaCacheManifest,
        sizeLimit: int,
        ageLimit: int,
    ) -> tuple[MediaCacheEntry, ...]:
        cutoff = datetime.now(UTC) - timedelta(days=ageLimit)
        removed = {
            entry
            for entry in manifest.entries
            if not self._entryPath(cacheRoot, entry).is_file()
            or entry.lastAccessedAt < cutoff
        }
        retained = [entry for entry in manifest.entries if entry not in removed]
        retainedSize = sum(entry.sizeBytes for entry in retained)
        for entry in sorted(retained, key=lambda item: item.lastAccessedAt):
            if retainedSize <= sizeLimit:
                break
            removed.add(entry)
            retainedSize -= entry.sizeBytes
        return tuple(sorted(removed, key=lambda entry: entry.lastAccessedAt))

    def _removeEntries(
        self, cacheRoot: Path, entries: tuple[MediaCacheEntry, ...]
    ) -> None:
        try:
            for entry in entries:
                path = self._entryPath(cacheRoot, entry)
                path.unlink(missing_ok=True)
        except OSError as error:
            raise MediaError(
                "MEDIA_CACHE_CLEANUP_FAILED", "Unable to clean media cache."
            ) from error

    def _entryPath(self, cacheRoot: Path, entry: MediaCacheEntry) -> Path:
        return resolveCacheEntryPath(cacheRoot, entry)

    def _cacheRoot(self) -> Path:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise MediaError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return project.path / "cache"

    async def _writeSource(
        self,
        providerId: str,
        sourceUri: str,
        temporaryPath: Path,
        timings: dict[str, float],
    ) -> tuple[str, int]:
        parsed = urlparse(sourceUri)
        if providerId == "local":
            sourcePath = self._validateLocalPath(parsed)
            return await asyncio.to_thread(
                self._copyLocal, sourcePath, temporaryPath, timings
            )
        if providerId == "pexels":
            self._validatePexelsUri(parsed)
            return await self._downloadRemote(
                sourceUri, temporaryPath, "pexels", timings
            )
        if providerId == "pixabay":
            self._validatePixabayUri(parsed)
            return await self._downloadRemote(
                sourceUri, temporaryPath, providerId, timings
            )
        if providerId == "wikimedia":
            self._validateWikimediaUri(parsed)
            return await self._downloadRemote(
                sourceUri, temporaryPath, providerId, timings
            )
        if providerId == "dvids":
            if parsed.scheme == "dvids":
                sourceUri = await self._resolveDvidsLazySource(sourceUri)
                parsed = urlparse(sourceUri)
            self._validateDvidsUri(parsed)
            return await self._downloadRemote(
                sourceUri, temporaryPath, providerId, timings
            )
        raise MediaError(
            "MEDIA_PROVIDER_NOT_CACHEABLE",
            f"Media provider '{providerId}' does not support caching.",
        )

    async def _resolveDvidsLazySource(self, sourceUri: str) -> str:
        if self.dvidsSourceResolver is None:
            raise MediaError(
                "MEDIA_PROVIDER_NOT_CONFIGURED",
                "DVIDS detail resolver is not configured.",
            )
        return await self.dvidsSourceResolver.resolveAssetSource(sourceUri)

    def _copyLocal(
        self, sourcePath: Path, temporaryPath: Path, timings: dict[str, float]
    ) -> tuple[str, int]:
        try:
            with sourcePath.open("rb") as source, temporaryPath.open("xb") as target:
                return self._copyAndHash(source, target, timings)
        except FileNotFoundError as error:
            raise MediaError(
                "MEDIA_SOURCE_NOT_FOUND", "Local media source was not found."
            ) from error

    async def _downloadRemote(
        self,
        sourceUri: str,
        temporaryPath: Path,
        providerId: str = "pexels",
        timings: dict[str, float] | None = None,
    ) -> tuple[str, int]:
        timingTarget = timings if timings is not None else {}
        digest = hashlib.sha256()
        size = 0
        try:
            async with httpx.AsyncClient(
                timeout=self.timeoutSeconds,
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                async with client.stream("GET", sourceUri) as response:
                    response.raise_for_status()
                    finalUri = urlparse(str(response.url))
                    if providerId == "pixabay":
                        self._validatePixabayUri(finalUri)
                    elif providerId == "wikimedia":
                        self._validateWikimediaUri(finalUri)
                    elif providerId == "dvids":
                        self._validateDvidsUri(finalUri)
                    else:
                        self._validatePexelsUri(finalUri)
                    declaredSize = self._contentLength(
                        response.headers.get("content-length")
                    )
                    if (
                        declaredSize is not None
                        and declaredSize > self.maxFileSizeBytes
                    ):
                        raise self._tooLarge()
                    with temporaryPath.open("xb") as target:
                        async for chunk in response.aiter_bytes(CHUNK_SIZE):
                            size += len(chunk)
                            if size > self.maxFileSizeBytes:
                                raise self._tooLarge()
                            hashStarted = time.perf_counter()
                            digest.update(chunk)
                            timingTarget["sourceHashSeconds"] = (
                                timingTarget.get("sourceHashSeconds", 0.0)
                                + time.perf_counter()
                                - hashStarted
                            )
                            writeStarted = time.perf_counter()
                            target.write(chunk)
                            timingTarget["sourceFileWriteSeconds"] = (
                                timingTarget.get("sourceFileWriteSeconds", 0.0)
                                + time.perf_counter()
                                - writeStarted
                            )
        except httpx.TimeoutException as error:
            raise MediaError(
                "MEDIA_DOWNLOAD_TIMEOUT", "Media download timed out."
            ) from error
        except httpx.HTTPStatusError as error:
            raise MediaError(
                "MEDIA_DOWNLOAD_FAILED",
                f"Media download failed with status {error.response.status_code}.",
            ) from error
        except httpx.RequestError as error:
            raise MediaError(
                "MEDIA_DOWNLOAD_FAILED", "Media download failed."
            ) from error
        return digest.hexdigest(), size

    def _copyAndHash(
        self, source: BinaryIO, target: BinaryIO, timings: dict[str, float]
    ) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        while chunk := source.read(CHUNK_SIZE):
            size += len(chunk)
            if size > self.maxFileSizeBytes:
                raise self._tooLarge()
            hashStarted = time.perf_counter()
            digest.update(chunk)
            timings["sourceHashSeconds"] = (
                timings.get("sourceHashSeconds", 0.0)
                + time.perf_counter()
                - hashStarted
            )
            writeStarted = time.perf_counter()
            target.write(chunk)
            timings["sourceFileWriteSeconds"] = (
                timings.get("sourceFileWriteSeconds", 0.0)
                + time.perf_counter()
                - writeStarted
            )
        return digest.hexdigest(), size

    def _validateLocalPath(self, parsed: ParseResult) -> Path:
        if parsed.scheme != "file":
            raise MediaError(
                "INVALID_MEDIA_SOURCE", "Local media source must use a file URI."
            )
        path = Path(
            unquote(parsed.path.lstrip("/"))
            if os.name == "nt"
            else unquote(parsed.path)
        ).resolve()
        if not self.localLibraryPaths or not any(
            path.is_relative_to(root) for root in self.localLibraryPaths
        ):
            raise MediaError(
                "INVALID_MEDIA_SOURCE",
                "Local media source is outside configured libraries.",
            )
        return path

    def _validatePexelsUri(self, parsed: ParseResult) -> None:
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not any(
            host.endswith(suffix) for suffix in PEXELS_HOST_SUFFIXES
        ):
            raise MediaError(
                "INVALID_MEDIA_SOURCE", "Pexels media source is not trusted."
            )

    def _validatePixabayUri(self, parsed: ParseResult) -> None:
        host = (parsed.hostname or "").lower()
        trusted = host == "pixabay.com" or any(
            host.endswith(suffix) for suffix in PIXABAY_HOST_SUFFIXES
        )
        if parsed.scheme != "https" or not trusted:
            raise MediaError(
                "INVALID_MEDIA_SOURCE", "Pixabay media source is not trusted."
            )

    def _validateWikimediaUri(self, parsed: ParseResult) -> None:
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not any(
            host.endswith(suffix) for suffix in WIKIMEDIA_HOST_SUFFIXES
        ):
            raise MediaError(
                "INVALID_MEDIA_SOURCE", "Wikimedia media source is not trusted."
            )

    def _validateDvidsUri(self, parsed: ParseResult) -> None:
        host = (parsed.hostname or "").lower()
        trusted = host in DVIDS_CLOUDFRONT_HOSTS or any(
            host.endswith(suffix) for suffix in DVIDS_HOST_SUFFIXES
        )
        if parsed.scheme != "https" or not trusted:
            raise MediaError(
                "INVALID_MEDIA_SOURCE", "DVIDS media source is not trusted."
            )

    def _extension(self, fileName: str | None, sourceUri: str) -> str:
        candidate = Path(fileName or urlparse(sourceUri).path).suffix.lower()
        if candidate and len(candidate) <= 10 and candidate[1:].isalnum():
            return candidate
        return ".bin"

    def _contentLength(self, value: str | None) -> int | None:
        try:
            return int(value) if value is not None else None
        except ValueError:
            return None

    def _tooLarge(self) -> MediaError:
        return MediaError(
            "MEDIA_FILE_TOO_LARGE", "Media file exceeds the configured cache limit."
        )

    def _elapsed(self, started: float) -> float:
        return round(time.perf_counter() - started, 4)
