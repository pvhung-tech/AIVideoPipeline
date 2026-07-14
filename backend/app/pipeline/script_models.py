from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class ScriptFormat(StrEnum):
    TXT = "txt"
    SRT = "srt"


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    startMilliseconds: int
    endMilliseconds: int
    text: str

    def toDictionary(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "startMilliseconds": self.startMilliseconds,
            "endMilliseconds": self.endMilliseconds,
            "text": self.text,
        }


@dataclass(frozen=True)
class Scene:
    id: str
    order: int
    text: str
    sourceCueIndexes: tuple[int, ...] = ()
    startMilliseconds: int | None = None
    endMilliseconds: int | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "order": self.order,
            "text": self.text,
            "sourceCueIndexes": list(self.sourceCueIndexes),
            "startMilliseconds": self.startMilliseconds,
            "endMilliseconds": self.endMilliseconds,
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "Scene":
        startMilliseconds = data.get("startMilliseconds")
        endMilliseconds = data.get("endMilliseconds")
        return cls(
            id=str(data["id"]),
            order=int(data["order"]),
            text=str(data["text"]),
            sourceCueIndexes=tuple(int(value) for value in data["sourceCueIndexes"]),
            startMilliseconds=(
                int(startMilliseconds) if startMilliseconds is not None else None
            ),
            endMilliseconds=(
                int(endMilliseconds) if endMilliseconds is not None else None
            ),
        )


@dataclass(frozen=True)
class ScriptDocument:
    format: ScriptFormat
    originalPath: Path
    contentPath: Path
    importedAt: datetime
    characterCount: int
    cues: tuple[SubtitleCue, ...] = ()
    scenes: tuple[Scene, ...] = ()

    def toDictionary(self) -> dict[str, Any]:
        return {
            "format": self.format.value,
            "originalPath": str(self.originalPath),
            "contentPath": str(self.contentPath),
            "importedAt": self.importedAt.isoformat(),
            "characterCount": self.characterCount,
            "cueCount": len(self.cues),
            "cues": [cue.toDictionary() for cue in self.cues],
            "sceneCount": len(self.scenes),
            "scenes": [scene.toDictionary() for scene in self.scenes],
        }
