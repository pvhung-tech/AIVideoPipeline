import hashlib
import logging
from datetime import UTC, datetime

from app.ai.errors import AIError
from app.ai.models import AIRequest
from app.ai.prompt_manager import PromptManager
from app.ai.provider_registry import AIProviderRegistry
from app.ai.scene_analysis_models import (
    SceneAnalysisCollection,
    SceneAnalysisFailure,
    SceneAnalysisResult,
    SceneBatchAnalysisResult,
)
from app.ai.scene_analysis_parser import (
    SCENE_ANALYSIS_RESPONSE_SCHEMA,
    SceneAnalysisParser,
)
from app.pipeline.script_models import Scene
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.repositories.scene_analysis_repository import SceneAnalysisRepository
from app.repositories.scene_repository import SceneRepository
from app.services.script_service import ActiveProjectProvider

logger = logging.getLogger(__name__)

BATCH_FATAL_ERROR_CODES = {
    "AI_PROVIDER_NOT_FOUND",
    "AI_PROVIDER_NOT_CONFIGURED",
    "AI_PROVIDER_AUTHENTICATION_FAILED",
    "AI_MODEL_NOT_FOUND",
    "AI_MODEL_NOT_CONFIGURED",
}


class SceneAnalysisService:
    def __init__(
        self,
        promptManager: PromptManager,
        providerRegistry: AIProviderRegistry,
        sceneRepository: SceneRepository,
        analysisRepository: SceneAnalysisRepository,
        projectService: ActiveProjectProvider,
        parser: SceneAnalysisParser,
        defaultProviderId: str,
        defaultModels: dict[str, str],
    ) -> None:
        self.promptManager = promptManager
        self.providerRegistry = providerRegistry
        self.sceneRepository = sceneRepository
        self.analysisRepository = analysisRepository
        self.projectService = projectService
        self.parser = parser
        self.defaultProviderId = defaultProviderId
        self.defaultModels = defaultModels

    async def analyzeScene(
        self,
        sceneId: str,
        contentType: str,
        language: str,
        providerId: str | None = None,
        model: str | None = None,
    ) -> SceneAnalysisResult:
        project = self._requireProject()
        scenes = self.sceneRepository.loadScenes(project.path).scenes
        scene = next((item for item in scenes if item.id == sceneId), None)
        if scene is None:
            raise AIError("SCENE_NOT_FOUND", "The requested scene was not found.")

        normalizedContentType = self._normalizeInput(contentType, "content type")
        normalizedLanguage = self._normalizeInput(language, "language")
        selectedProviderId, selectedModel = self._resolveProvider(providerId, model)
        return await self._analyze(
            project,
            scene,
            normalizedContentType,
            normalizedLanguage,
            selectedProviderId,
            selectedModel,
        )

    async def analyzeAllScenes(
        self,
        contentType: str,
        language: str,
        providerId: str | None = None,
        model: str | None = None,
        reanalyze: bool = False,
    ) -> SceneBatchAnalysisResult:
        project = self._requireProject()
        scenes = self.sceneRepository.loadScenes(project.path).scenes
        normalizedContentType = self._normalizeInput(contentType, "content type")
        normalizedLanguage = self._normalizeInput(language, "language")
        selectedProviderId, selectedModel = self._resolveProvider(providerId, model)
        currentSceneIds = self._currentAnalyzedSceneIds(project, scenes)

        results: list[SceneAnalysisResult] = []
        failures: list[SceneAnalysisFailure] = []
        skippedSceneIds = [
            scene.id
            for scene in scenes
            if not reanalyze and scene.id in currentSceneIds
        ]
        for sceneIndex, scene in enumerate(scenes):
            if not reanalyze and scene.id in currentSceneIds:
                continue
            try:
                result = await self._analyze(
                    project,
                    scene,
                    normalizedContentType,
                    normalizedLanguage,
                    selectedProviderId,
                    selectedModel,
                )
                results.append(result)
            except AIError as error:
                logger.warning("Scene analysis failed for %s: %s", scene.id, error.code)
                failures.append(
                    SceneAnalysisFailure(scene.id, error.code, error.message)
                )
                if error.code in BATCH_FATAL_ERROR_CODES:
                    failures.extend(
                        SceneAnalysisFailure(item.id, error.code, error.message)
                        for item in scenes[sceneIndex + 1 :]
                        if item.id not in currentSceneIds or reanalyze
                    )
                    break
        return SceneBatchAnalysisResult(
            totalScenes=len(scenes),
            results=tuple(results),
            failures=tuple(failures),
            skippedSceneIds=tuple(skippedSceneIds),
        )

    async def _analyze(
        self,
        project: Project,
        scene: Scene,
        contentType: str,
        language: str,
        providerId: str,
        model: str,
    ) -> SceneAnalysisResult:
        renderedPrompt = self.promptManager.render(
            "scene_analysis",
            {
                "contentType": contentType,
                "language": language,
                "sceneText": scene.text,
            },
        )
        request = AIRequest(
            model=model,
            messages=renderedPrompt.messages,
            responseSchema=SCENE_ANALYSIS_RESPONSE_SCHEMA,
        )
        response = await self.providerRegistry.get(providerId).generate(request)
        parsed = self.parser.parse(response.content)
        result = SceneAnalysisResult(
            sceneId=scene.id,
            sourceTextHash=self._textHash(scene.text),
            description=parsed.description,
            category=parsed.category,
            keywords=parsed.keywords,
            providerId=response.providerId,
            model=response.model,
            promptVersion=renderedPrompt.templateVersion,
            analyzedAt=datetime.now(UTC),
        )
        self.analysisRepository.upsertResult(project.path, result)
        return result

    def _resolveProvider(
        self, providerId: str | None, model: str | None
    ) -> tuple[str, str]:
        selectedProviderId = (providerId or self.defaultProviderId).strip().lower()
        selectedModel = model or self.defaultModels.get(selectedProviderId)
        if selectedModel is None:
            raise AIError(
                "AI_MODEL_NOT_CONFIGURED",
                f"No default model is configured for provider '{selectedProviderId}'.",
            )
        return selectedProviderId, selectedModel

    def _currentAnalyzedSceneIds(
        self, project: Project, scenes: tuple[Scene, ...]
    ) -> set[str]:
        results = self.analysisRepository.listResults(project.path).results
        sceneHashes = {scene.id: self._textHash(scene.text) for scene in scenes}
        return {
            result.sceneId
            for result in results
            if sceneHashes.get(result.sceneId) == result.sourceTextHash
        }

    def listAnalyses(self) -> SceneAnalysisCollection:
        project = self._requireProject()
        collection = self.analysisRepository.listResults(project.path)
        sceneHashes = {
            scene.id: self._textHash(scene.text)
            for scene in self.sceneRepository.loadScenes(project.path).scenes
        }
        currentResults = tuple(
            result
            for result in collection.results
            if sceneHashes.get(result.sceneId) == result.sourceTextHash
        )
        return SceneAnalysisCollection(
            results=currentResults,
            updatedAt=collection.updatedAt,
            schemaVersion=collection.schemaVersion,
        )

    def _requireProject(self) -> Project:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return project

    def _normalizeInput(self, value: str, fieldName: str) -> str:
        normalizedValue = value.strip()
        if not normalizedValue or len(normalizedValue) > 100:
            raise AIError(
                "INVALID_SCENE_ANALYSIS_INPUT",
                f"Scene analysis {fieldName} must contain 1 to 100 characters.",
            )
        return normalizedValue

    def _textHash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
