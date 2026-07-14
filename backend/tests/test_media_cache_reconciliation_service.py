from datetime import UTC, datetime
from pathlib import Path

from app.media.cache_manifest import (
    MediaCacheEntry,
    MediaCacheManifest,
    MediaCacheSource,
)
from app.project.project_model import Project
from app.repositories.file_media_cache_repository import FileMediaCacheRepository
from app.services.media_cache_reconciliation_service import (
    MediaCacheReconciliationService,
)
from app.services.project_service import ProjectService


class FakeProjectRepository:
    def createProject(self, project: Project) -> Project:
        return project

    def saveProject(self, project: Project) -> Project:
        return project

    def openProject(self, projectPath: Path) -> Project:
        raise NotImplementedError

    def listRecentProjects(self, limit: int) -> list[Project]:
        return []


def testCacheReconciliationDetectsAndRepairsDrift(tmp_path: Path) -> None:
    projectPath = tmp_path / "project"
    cacheRoot = projectPath / "cache"
    cacheRoot.mkdir(parents=True)
    referencedPath = cacheRoot / "aa" / "a.jpg"
    referencedPath.parent.mkdir()
    referencedPath.write_bytes(b"referenced")
    orphanPath = cacheRoot / "bb" / "orphan.mp4"
    orphanPath.parent.mkdir()
    orphanPath.write_bytes(b"orphan")
    timestamp = datetime.now(UTC)
    referenced = _entry("a" * 64, "aa/a.jpg", timestamp)
    missing = _entry("b" * 64, "cc/missing.jpg", timestamp)
    repository = FileMediaCacheRepository()
    repository.save(cacheRoot, MediaCacheManifest((referenced, missing)))
    service = MediaCacheReconciliationService(_projectService(projectPath), repository)

    preview = service.reconcile(dryRun=True)

    assert [file.relativePath for file in preview.orphanFiles] == ["bb/orphan.mp4"]
    assert preview.missingEntries == (missing,)
    assert orphanPath.exists()
    assert len(repository.load(cacheRoot).entries) == 2

    result = service.reconcile(dryRun=False)

    assert result.orphanFiles == preview.orphanFiles
    assert not orphanPath.exists()
    assert referencedPath.exists()
    assert repository.load(cacheRoot).entries == (referenced,)


def _entry(contentHash: str, path: str, timestamp: datetime) -> MediaCacheEntry:
    return MediaCacheEntry(
        contentHash,
        path,
        10,
        timestamp,
        timestamp,
        (MediaCacheSource("local", "asset", "file:///asset"),),
    )


def _projectService(projectPath: Path) -> ProjectService:
    service = ProjectService(FakeProjectRepository())
    service.activeProject = Project(
        "project-id",
        "Project",
        projectPath,
        datetime.now(UTC),
        datetime.now(UTC),
    )
    return service
