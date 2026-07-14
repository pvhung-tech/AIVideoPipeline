from dataclasses import dataclass
from datetime import datetime
from string import hexdigits
from typing import Any

SCENE_ANALYSIS_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SceneAnalysisResult:
    sceneId: str
    sourceTextHash: str
    description: str
    category: str
    keywords: tuple[str, ...]
    providerId: str
    model: str
    promptVersion: int
    analyzedAt: datetime

    def __post_init__(self) -> None:
        requiredValues = (
            self.sceneId,
            self.sourceTextHash,
            self.description,
            self.category,
            self.providerId,
            self.model,
        )
        if any(not value.strip() for value in requiredValues):
            raise ValueError("Scene analysis fields cannot be empty.")
        if len(self.sourceTextHash) != 64 or any(
            character not in hexdigits for character in self.sourceTextHash
        ):
            raise ValueError("Scene analysis source hash is invalid.")
        if self.promptVersion < 1:
            raise ValueError("Prompt version must be positive.")
        if not 1 <= len(self.keywords) <= 12:
            raise ValueError("Scene analysis requires 1 to 12 keywords.")
        normalizedKeywords = [keyword.strip().casefold() for keyword in self.keywords]
        if any(not keyword for keyword in normalizedKeywords):
            raise ValueError("Scene analysis keywords cannot be empty.")
        if len(normalizedKeywords) != len(set(normalizedKeywords)):
            raise ValueError("Scene analysis keywords must be unique.")

    def toDictionary(self) -> dict[str, Any]:
        return {
            "sceneId": self.sceneId,
            "sourceTextHash": self.sourceTextHash,
            "description": self.description,
            "category": self.category,
            "keywords": list(self.keywords),
            "providerId": self.providerId,
            "model": self.model,
            "promptVersion": self.promptVersion,
            "analyzedAt": self.analyzedAt.isoformat(),
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "SceneAnalysisResult":
        keywords = data["keywords"]
        if not isinstance(keywords, list):
            raise TypeError("keywords must be a list.")
        return cls(
            sceneId=str(data["sceneId"]),
            sourceTextHash=str(data["sourceTextHash"]),
            description=str(data["description"]),
            category=str(data["category"]),
            keywords=tuple(str(keyword) for keyword in keywords),
            providerId=str(data["providerId"]),
            model=str(data["model"]),
            promptVersion=int(data["promptVersion"]),
            analyzedAt=datetime.fromisoformat(str(data["analyzedAt"])),
        )


@dataclass(frozen=True)
class SceneAnalysisCollection:
    results: tuple[SceneAnalysisResult, ...]
    updatedAt: datetime
    schemaVersion: int = SCENE_ANALYSIS_SCHEMA_VERSION

    def toDictionary(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "updatedAt": self.updatedAt.isoformat(),
            "resultCount": len(self.results),
            "results": [result.toDictionary() for result in self.results],
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "SceneAnalysisCollection":
        results = data["results"]
        if not isinstance(results, list):
            raise TypeError("results must be a list.")
        if any(not isinstance(result, dict) for result in results):
            raise TypeError("Each scene analysis result must be an object.")
        return cls(
            results=tuple(
                SceneAnalysisResult.fromDictionary(result)
                for result in results
                if isinstance(result, dict)
            ),
            updatedAt=datetime.fromisoformat(str(data["updatedAt"])),
            schemaVersion=int(data["schemaVersion"]),
        )


@dataclass(frozen=True)
class SceneAnalysisFailure:
    sceneId: str
    code: str
    message: str

    def toDictionary(self) -> dict[str, str]:
        return {
            "sceneId": self.sceneId,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class SceneBatchAnalysisResult:
    totalScenes: int
    results: tuple[SceneAnalysisResult, ...]
    failures: tuple[SceneAnalysisFailure, ...]
    skippedSceneIds: tuple[str, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {
            "totalScenes": self.totalScenes,
            "successCount": len(self.results),
            "failureCount": len(self.failures),
            "skippedCount": len(self.skippedSceneIds),
            "results": [result.toDictionary() for result in self.results],
            "failures": [failure.toDictionary() for failure in self.failures],
            "skippedSceneIds": list(self.skippedSceneIds),
        }
