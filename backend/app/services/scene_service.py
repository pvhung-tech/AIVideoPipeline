import threading
from dataclasses import replace

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.script_errors import ScriptError
from app.project.errors import ProjectError
from app.repositories.scene_repository import SceneRepository
from app.services.script_service import ActiveProjectProvider

MAX_SCENE_TEXT_LENGTH = 100_000


class SceneService:
    def __init__(
        self,
        repository: SceneRepository,
        projectService: ActiveProjectProvider,
    ) -> None:
        self.repository = repository
        self.projectService = projectService
        self.lock = threading.RLock()

    def listScenes(self) -> SceneCollection:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        with self.lock:
            return self.repository.loadScenes(project.path)

    def updateScene(self, sceneId: str, text: str) -> SceneCollection:
        normalizedText = self._normalizeText(text)
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")

        with self.lock:
            collection = self.repository.loadScenes(project.path)
            matchingScene = next(
                (scene for scene in collection.scenes if scene.id == sceneId), None
            )
            if matchingScene is None:
                raise ScriptError(
                    "SCENE_NOT_FOUND", "The requested scene was not found."
                )
            updatedScenes = tuple(
                replace(scene, text=normalizedText) if scene.id == sceneId else scene
                for scene in collection.scenes
            )
            return self.repository.saveScenes(project.path, updatedScenes)

    def _normalizeText(self, text: str) -> str:
        normalizedText = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalizedText:
            raise ScriptError("INVALID_SCENE_TEXT", "Scene text cannot be empty.")
        if len(normalizedText) > MAX_SCENE_TEXT_LENGTH:
            raise ScriptError(
                "INVALID_SCENE_TEXT",
                "Scene text cannot exceed 100,000 characters.",
            )
        return normalizedText
