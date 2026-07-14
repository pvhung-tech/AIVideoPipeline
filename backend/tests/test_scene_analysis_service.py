import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.ai.errors import AIError
from app.ai.models import AIRequest, AIResponse
from app.ai.prompt_manager import PromptManager
from app.ai.prompt_models import PromptTemplate
from app.ai.provider_registry import AIProviderRegistry
from app.ai.scene_analysis_parser import SceneAnalysisParser
from app.pipeline.script_models import Scene
from app.project.project_model import Project
from app.repositories.file_scene_analysis_repository import (
    FileSceneAnalysisRepository,
)
from app.repositories.file_scene_repository import FileSceneRepository
from app.services.scene_analysis_service import SceneAnalysisService


class FakePromptRepository:
    def loadTemplates(self) -> tuple[PromptTemplate, ...]:
        return (
            PromptTemplate(
                id="scene_analysis",
                version=3,
                systemTemplate="Analyze scenes.",
                userTemplate="{contentType}|{language}|{sceneText}",
                requiredVariables=("contentType", "language", "sceneText"),
            ),
        )


class FakeProvider:
    providerId = "ollama"

    def __init__(self) -> None:
        self.request: AIRequest | None = None

    async def generate(self, request: AIRequest) -> AIResponse:
        self.request = request
        if "FAIL" in request.messages[-1].content:
            raise AIError("INVALID_AI_RESPONSE", "Invalid response")
        return AIResponse(
            "ollama",
            request.model,
            '{"description":"A city wakes up.","category":"location",'
            '"keywords":["city sunrise","skyline"]}',
        )


class StubProjectService:
    def __init__(self, project: Project) -> None:
        self.project = project

    def getCurrentProject(self) -> Project:
        return self.project


def testSceneAnalysisServiceAnalyzesAndPersistsScene(tmp_path: Path) -> None:
    timestamp = datetime.now(UTC)
    project = Project("id", "Demo", tmp_path, timestamp, timestamp)
    sceneRepository = FileSceneRepository()
    sceneRepository.saveScenes(tmp_path, (Scene("scene-0001", 1, "City text"),))
    provider = FakeProvider()
    analysisRepository = FileSceneAnalysisRepository()
    service = SceneAnalysisService(
        PromptManager(FakePromptRepository()),
        AIProviderRegistry((provider,)),
        sceneRepository,
        analysisRepository,
        StubProjectService(project),
        SceneAnalysisParser(),
        "ollama",
        {"ollama": "llama-test"},
    )

    result = asyncio.run(
        service.analyzeScene("scene-0001", "documentary", "Vietnamese")
    )

    assert result.category == "location"
    assert result.keywords == ("city sunrise", "skyline")
    assert result.promptVersion == 3
    assert provider.request is not None
    assert provider.request.responseSchema is not None
    assert service.listAnalyses().results == (result,)

    sceneRepository.saveScenes(
        tmp_path,
        (
            Scene("scene-0001", 1, "City text"),
            Scene("scene-0002", 2, "Second city scene"),
        ),
    )
    batch = asyncio.run(service.analyzeAllScenes("documentary", "Vietnamese"))
    assert batch.totalScenes == 2
    assert batch.skippedSceneIds == ("scene-0001",)
    assert [item.sceneId for item in batch.results] == ["scene-0002"]

    sceneRepository.saveScenes(
        tmp_path,
        (
            Scene("scene-0001", 1, "City text"),
            Scene("scene-0002", 2, "FAIL"),
        ),
    )
    partialBatch = asyncio.run(
        service.analyzeAllScenes("documentary", "Vietnamese", reanalyze=True)
    )
    assert [item.sceneId for item in partialBatch.results] == ["scene-0001"]
    assert partialBatch.failures[0].sceneId == "scene-0002"

    sceneRepository.saveScenes(tmp_path, (Scene("scene-0001", 1, "Changed city text"),))
    assert service.listAnalyses().results == ()
