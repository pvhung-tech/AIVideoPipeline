import json
import logging
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.project.errors import ProjectError
from app.project.project_model import PROJECT_SCHEMA_VERSION, Project

logger = logging.getLogger(__name__)

PROJECT_FILE_NAME = "project.json"
PROJECT_DIRECTORIES = ("script", "media", "cache", "render", "output")


class SQLiteProjectRepository:
    def __init__(self, appDataDirectory: Path) -> None:
        self.appDataDirectory = appDataDirectory
        self.databasePath = appDataDirectory / "app.db"
        self._initializeDatabase()

    def createProject(self, project: Project) -> Project:
        if not project.path.parent.is_dir():
            raise ProjectError(
                "PROJECT_PARENT_NOT_FOUND",
                "The selected parent directory does not exist.",
            )
        if project.path.exists():
            raise ProjectError(
                "PROJECT_ALREADY_EXISTS",
                f"A project directory already exists at {project.path}.",
            )

        projectCreated = False
        try:
            project.path.mkdir()
            projectCreated = True
            for directoryName in PROJECT_DIRECTORIES:
                (project.path / directoryName).mkdir()
            self._writeProjectFile(project)
            self._upsertProject(project)
            return project
        except ProjectError:
            raise
        except (OSError, sqlite3.Error) as error:
            logger.exception("Failed to create project at %s", project.path)
            if projectCreated:
                shutil.rmtree(project.path, ignore_errors=True)
            raise ProjectError(
                "PROJECT_CREATE_FAILED", "The project could not be created."
            ) from error

    def saveProject(self, project: Project) -> Project:
        if not project.path.is_dir():
            raise ProjectError("PROJECT_NOT_FOUND", "The project directory is missing.")

        try:
            self._writeProjectFile(project)
            self._upsertProject(project)
            return project
        except (OSError, sqlite3.Error) as error:
            logger.exception("Failed to save project %s", project.id)
            raise ProjectError(
                "PROJECT_SAVE_FAILED", "The project could not be saved."
            ) from error

    def openProject(self, projectPath: Path) -> Project:
        resolvedPath = projectPath.expanduser().resolve()
        if resolvedPath.name == PROJECT_FILE_NAME:
            resolvedPath = resolvedPath.parent

        project = self._readProjectFile(resolvedPath)
        try:
            self._upsertProject(project)
        except sqlite3.Error as error:
            logger.exception("Failed to update recent project %s", project.id)
            raise ProjectError(
                "PROJECT_OPEN_FAILED", "The project could not be opened."
            ) from error
        return project

    def listRecentProjects(self, limit: int) -> list[Project]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, name, path, created_at, updated_at
                    FROM projects
                    ORDER BY last_opened_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        except sqlite3.Error as error:
            logger.exception("Failed to list recent projects")
            raise ProjectError(
                "RECENT_PROJECTS_FAILED", "Recent projects could not be loaded."
            ) from error

        projects: list[Project] = []
        for row in rows:
            projectPath = Path(str(row["path"]))
            if not (projectPath / PROJECT_FILE_NAME).is_file():
                logger.warning("Skipping missing recent project at %s", projectPath)
                continue
            projects.append(self._projectFromRow(row))
        return projects

    def _initializeDatabase(self) -> None:
        try:
            self.appDataDirectory.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        path TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_opened_at TEXT NOT NULL
                    )
                    """
                )
        except (OSError, sqlite3.Error) as error:
            logger.exception("Failed to initialize project database")
            raise ProjectError(
                "PROJECT_DATABASE_FAILED",
                "The project database could not be initialized.",
            ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.databasePath)
        connection.row_factory = sqlite3.Row
        return connection

    def _writeProjectFile(self, project: Project) -> None:
        projectFile = project.path / PROJECT_FILE_NAME
        temporaryFile = project.path / f".{PROJECT_FILE_NAME}.tmp"
        payload = project.toDictionary()
        payload.pop("path", None)
        temporaryFile.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporaryFile, projectFile)

    def _readProjectFile(self, projectPath: Path) -> Project:
        projectFile = projectPath / PROJECT_FILE_NAME
        if not projectFile.is_file():
            raise ProjectError(
                "PROJECT_NOT_FOUND", f"No project file was found at {projectPath}."
            )

        try:
            data = json.loads(projectFile.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Project data must be an object.")
            project = Project.fromDictionary(data, projectPath)
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            logger.exception("Invalid project file at %s", projectFile)
            raise ProjectError(
                "INVALID_PROJECT_FILE", "The project file is invalid or corrupted."
            ) from error

        if project.schemaVersion != PROJECT_SCHEMA_VERSION:
            raise ProjectError(
                "UNSUPPORTED_PROJECT_VERSION",
                f"Project schema version {project.schemaVersion} is not supported.",
            )
        return project

    def _upsertProject(self, project: Project) -> None:
        timestamp = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    id, name, path, created_at, updated_at, last_opened_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    path = excluded.path,
                    updated_at = excluded.updated_at,
                    last_opened_at = excluded.last_opened_at
                """,
                (
                    project.id,
                    project.name,
                    str(project.path),
                    project.createdAt.isoformat(),
                    project.updatedAt.isoformat(),
                    timestamp,
                ),
            )

    def _projectFromRow(self, row: sqlite3.Row) -> Project:
        return Project(
            id=str(row["id"]),
            name=str(row["name"]),
            path=Path(str(row["path"])),
            createdAt=datetime.fromisoformat(str(row["created_at"])),
            updatedAt=datetime.fromisoformat(str(row["updated_at"])),
        )
