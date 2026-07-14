from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.ai.scene_analysis_models import (
    SceneAnalysisCollection,
    SceneAnalysisResult,
    SceneBatchAnalysisResult,
)
from app.config.dependencies import getSceneAnalysisService
from app.main import createApp


class FakeSceneAnalysisService:
    def __init__(self) -> None:
        self.result = SceneAnalysisResult(
            sceneId="scene-0001",
            sourceTextHash="0" * 64,
            description="A city wakes up.",
            category="location",
            keywords=("city", "sunrise"),
            providerId="ollama",
            model="test-model",
            promptVersion=1,
            analyzedAt=datetime.now(UTC),
        )

    async def analyzeScene(
        self,
        sceneId: str,
        contentType: str,
        language: str,
        providerId: str | None = None,
        model: str | None = None,
    ) -> SceneAnalysisResult:
        del sceneId, contentType, language, providerId, model
        return self.result

    def listAnalyses(self) -> SceneAnalysisCollection:
        return SceneAnalysisCollection((self.result,), datetime.now(UTC))

    async def analyzeAllScenes(
        self,
        contentType: str,
        language: str,
        providerId: str | None = None,
        model: str | None = None,
        reanalyze: bool = False,
    ) -> SceneBatchAnalysisResult:
        del contentType, language, providerId, model, reanalyze
        return SceneBatchAnalysisResult(1, (self.result,), (), ())


def testAIEndpointsAnalyzeAndListScenes() -> None:
    app = createApp()
    app.dependency_overrides[getSceneAnalysisService] = FakeSceneAnalysisService
    client = TestClient(app)

    analyzeResponse = client.post(
        "/api/ai/scenes/scene-0001/analyze",
        json={"contentType": "documentary", "language": "Vietnamese"},
    )
    listResponse = client.get("/api/ai/scenes/analysis")
    batchResponse = client.post(
        "/api/ai/scenes/analyze",
        json={"providerId": "ollama", "reanalyze": True},
    )

    assert analyzeResponse.status_code == 200
    assert analyzeResponse.json()["data"]["keywords"] == ["city", "sunrise"]
    assert listResponse.status_code == 200
    assert listResponse.json()["data"]["resultCount"] == 1
    assert batchResponse.status_code == 200
    assert batchResponse.json()["data"]["successCount"] == 1
