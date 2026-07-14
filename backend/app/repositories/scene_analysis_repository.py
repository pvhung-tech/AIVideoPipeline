from pathlib import Path
from typing import Protocol

from app.ai.scene_analysis_models import (
    SceneAnalysisCollection,
    SceneAnalysisResult,
)


class SceneAnalysisRepository(Protocol):
    def listResults(self, projectPath: Path) -> SceneAnalysisCollection: ...

    def upsertResult(
        self, projectPath: Path, result: SceneAnalysisResult
    ) -> SceneAnalysisCollection: ...
