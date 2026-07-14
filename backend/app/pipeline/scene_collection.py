from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.pipeline.script_models import Scene

SCENE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SceneCollection:
    scenes: tuple[Scene, ...]
    updatedAt: datetime
    schemaVersion: int = SCENE_SCHEMA_VERSION

    def toDictionary(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "updatedAt": self.updatedAt.isoformat(),
            "sceneCount": len(self.scenes),
            "scenes": [scene.toDictionary() for scene in self.scenes],
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "SceneCollection":
        return cls(
            scenes=tuple(Scene.fromDictionary(scene) for scene in data["scenes"]),
            updatedAt=datetime.fromisoformat(str(data["updatedAt"])),
            schemaVersion=int(data["schemaVersion"]),
        )
