import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.errors import AIError
from app.ai.scene_analysis_models import (
    SCENE_ANALYSIS_SCHEMA_VERSION,
    SceneAnalysisCollection,
    SceneAnalysisResult,
)

logger = logging.getLogger(__name__)


class FileSceneAnalysisRepository:
    def __init__(self) -> None:
        self.lock = threading.RLock()

    def listResults(self, projectPath: Path) -> SceneAnalysisCollection:
        with self.lock:
            return self._load(projectPath)

    def upsertResult(
        self, projectPath: Path, result: SceneAnalysisResult
    ) -> SceneAnalysisCollection:
        with self.lock:
            collection = self._load(projectPath)
            indexedResults = {item.sceneId: item for item in collection.results}
            indexedResults[result.sceneId] = result
            results = tuple(
                indexedResults[sceneId] for sceneId in sorted(indexedResults)
            )
            updatedCollection = SceneAnalysisCollection(results, datetime.now(UTC))
            self._save(projectPath, updatedCollection)
            return updatedCollection

    def _load(self, projectPath: Path) -> SceneAnalysisCollection:
        analysisPath = self._analysisPath(projectPath)
        if not analysisPath.is_file():
            return SceneAnalysisCollection((), datetime.now(UTC))
        try:
            data: Any = json.loads(analysisPath.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Analysis document must be an object.")
            collection = SceneAnalysisCollection.fromDictionary(data)
            self._validateCollection(collection)
            return collection
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise AIError(
                "INVALID_SCENE_ANALYSIS_FILE",
                "The saved scene analysis is invalid.",
            ) from error
        except OSError as error:
            logger.exception("Failed to load scene analysis from %s", projectPath)
            raise AIError(
                "SCENE_ANALYSIS_READ_FAILED",
                "The scene analysis could not be read.",
            ) from error

    def _save(self, projectPath: Path, collection: SceneAnalysisCollection) -> None:
        analysisPath = self._analysisPath(projectPath)
        try:
            analysisPath.parent.mkdir(parents=True, exist_ok=True)
            temporaryPath = analysisPath.with_name(f".{analysisPath.name}.tmp")
            temporaryPath.write_text(
                json.dumps(collection.toDictionary(), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporaryPath, analysisPath)
        except OSError as error:
            logger.exception("Failed to save scene analysis in %s", projectPath)
            raise AIError(
                "SCENE_ANALYSIS_SAVE_FAILED",
                "The scene analysis could not be saved.",
            ) from error

    def _validateCollection(self, collection: SceneAnalysisCollection) -> None:
        if collection.schemaVersion != SCENE_ANALYSIS_SCHEMA_VERSION:
            raise ValueError("Unsupported scene analysis schema version.")
        sceneIds = [result.sceneId for result in collection.results]
        if len(sceneIds) != len(set(sceneIds)):
            raise ValueError("Scene analysis IDs must be unique.")
        if any(not sceneId.strip() for sceneId in sceneIds):
            raise ValueError("Scene analysis ID cannot be empty.")

    def _analysisPath(self, projectPath: Path) -> Path:
        return projectPath / "script" / "analysis.json"
