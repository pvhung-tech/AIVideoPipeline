import threading
from pathlib import Path

from app.media.cache_manifest import (
    MediaCacheManifest,
    MediaCacheReconciliationResult,
    OrphanCacheFile,
)
from app.media.cache_paths import resolveCacheEntryPath
from app.media.errors import MediaError
from app.repositories.file_media_cache_repository import (
    MANIFEST_FILE_NAME,
    FileMediaCacheRepository,
)
from app.services.project_service import ProjectService


class MediaCacheReconciliationService:
    _lock = threading.RLock()

    def __init__(
        self,
        projectService: ProjectService,
        repository: FileMediaCacheRepository | None = None,
    ) -> None:
        self.projectService = projectService
        self.repository = repository or FileMediaCacheRepository()

    def reconcile(self, dryRun: bool = True) -> MediaCacheReconciliationResult:
        cacheRoot = self._cacheRoot()
        with self._lock:
            manifest = self.repository.load(cacheRoot)
            referencedPaths = {
                resolveCacheEntryPath(cacheRoot, entry): entry
                for entry in manifest.entries
            }
            missingEntries = tuple(
                entry for path, entry in referencedPaths.items() if not path.is_file()
            )
            orphanFiles = self._findOrphans(cacheRoot, set(referencedPaths))
            if not dryRun:
                self._removeOrphans(cacheRoot, orphanFiles)
                missingHashes = {entry.contentHash for entry in missingEntries}
                retained = tuple(
                    entry
                    for entry in manifest.entries
                    if entry.contentHash not in missingHashes
                )
                self.repository.save(cacheRoot, MediaCacheManifest(retained))
        return MediaCacheReconciliationResult(dryRun, orphanFiles, missingEntries)

    def _findOrphans(
        self, cacheRoot: Path, referencedPaths: set[Path]
    ) -> tuple[OrphanCacheFile, ...]:
        if not cacheRoot.is_dir():
            return ()
        orphans: list[OrphanCacheFile] = []
        try:
            for path in cacheRoot.rglob("*"):
                if (
                    path.name == MANIFEST_FILE_NAME
                    or path.is_symlink()
                    or not path.is_file()
                ):
                    continue
                resolvedPath = path.resolve()
                if resolvedPath not in referencedPaths:
                    orphans.append(
                        OrphanCacheFile(
                            resolvedPath.relative_to(cacheRoot).as_posix(),
                            resolvedPath.stat().st_size,
                        )
                    )
        except OSError as error:
            raise MediaError(
                "MEDIA_CACHE_RECONCILIATION_FAILED",
                "Unable to inspect media cache files.",
            ) from error
        return tuple(sorted(orphans, key=lambda item: item.relativePath))

    def _removeOrphans(
        self, cacheRoot: Path, orphanFiles: tuple[OrphanCacheFile, ...]
    ) -> None:
        try:
            for orphan in orphanFiles:
                path = (cacheRoot / orphan.relativePath).resolve()
                if not path.is_relative_to(cacheRoot.resolve()):
                    raise MediaError(
                        "MEDIA_CACHE_RECONCILIATION_FAILED",
                        "Orphan cache path is invalid.",
                    )
                path.unlink(missing_ok=True)
        except OSError as error:
            raise MediaError(
                "MEDIA_CACHE_RECONCILIATION_FAILED",
                "Unable to remove orphan cache files.",
            ) from error

    def _cacheRoot(self) -> Path:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise MediaError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return project.path / "cache"
