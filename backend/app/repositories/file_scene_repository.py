import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.pipeline.scene_collection import SCENE_SCHEMA_VERSION, SceneCollection
from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import Scene

logger = logging.getLogger(__name__)


class FileSceneRepository:
    def saveScenes(
        self, projectPath: Path, scenes: tuple[Scene, ...]
    ) -> SceneCollection:
        collection = SceneCollection(scenes=scenes, updatedAt=datetime.now(UTC))
        scenesPath = self._scenesPath(projectPath)
        try:
            scenesPath.parent.mkdir(parents=True, exist_ok=True)
            temporaryPath = scenesPath.with_name(f".{scenesPath.name}.tmp")
            temporaryPath.write_text(
                json.dumps(collection.toDictionary(), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporaryPath, scenesPath)
            return collection
        except OSError as error:
            logger.exception("Failed to save scenes in project %s", projectPath)
            raise ScriptError(
                "SCENES_SAVE_FAILED", "The scene list could not be saved."
            ) from error

    def loadScenes(self, projectPath: Path) -> SceneCollection:
        scenesPath = self._scenesPath(projectPath)
        if not scenesPath.is_file():
            raise ScriptError(
                "SCENES_NOT_FOUND", "Import a script before accessing scenes."
            )
        try:
            data: Any = json.loads(scenesPath.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Scene document must be an object.")
            collection = SceneCollection.fromDictionary(data)
            self._validateCollection(collection)
            return collection
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ScriptError(
                "INVALID_SCENES_FILE", "The saved scene list is invalid."
            ) from error
        except OSError as error:
            logger.exception("Failed to load scenes from project %s", projectPath)
            raise ScriptError(
                "SCENES_READ_FAILED", "The scene list could not be read."
            ) from error

    def _validateCollection(self, collection: SceneCollection) -> None:
        if collection.schemaVersion != SCENE_SCHEMA_VERSION:
            raise ValueError("Unsupported scene schema version.")
        if not collection.scenes:
            raise ValueError("Scene list cannot be empty.")
        expectedOrders = tuple(range(1, len(collection.scenes) + 1))
        actualOrders = tuple(scene.order for scene in collection.scenes)
        if actualOrders != expectedOrders:
            raise ValueError("Scene order must be contiguous.")
        if len({scene.id for scene in collection.scenes}) != len(collection.scenes):
            raise ValueError("Scene IDs must be unique.")
        if any(not scene.text.strip() for scene in collection.scenes):
            raise ValueError("Scene text cannot be empty.")

    def _scenesPath(self, projectPath: Path) -> Path:
        return projectPath / "script" / "scenes.json"
