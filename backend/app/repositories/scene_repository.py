from pathlib import Path
from typing import Protocol

from app.pipeline.scene_collection import SceneCollection
from app.pipeline.script_models import Scene


class SceneRepository(Protocol):
    def saveScenes(
        self, projectPath: Path, scenes: tuple[Scene, ...]
    ) -> SceneCollection: ...

    def loadScenes(self, projectPath: Path) -> SceneCollection: ...
