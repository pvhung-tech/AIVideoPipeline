from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

TIMELINE_SCHEMA_VERSION = 2


class TimelineMediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class VisualClipRole(StrEnum):
    BROLL = "broll"
    AVATAR = "avatar"


@dataclass(frozen=True)
class MediaClip:
    id: str
    contentHash: str
    mediaType: TimelineMediaType
    startMilliseconds: int
    endMilliseconds: int
    layer: int = 0
    sourceStartMilliseconds: int | None = None
    sourceEndMilliseconds: int | None = None
    role: VisualClipRole = VisualClipRole.BROLL

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "contentHash": self.contentHash,
            "mediaType": self.mediaType.value,
            "startMilliseconds": self.startMilliseconds,
            "endMilliseconds": self.endMilliseconds,
            "layer": self.layer,
            "sourceStartMilliseconds": self.sourceStartMilliseconds,
            "sourceEndMilliseconds": self.sourceEndMilliseconds,
            "role": self.role.value,
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "MediaClip":
        sourceStart = data.get("sourceStartMilliseconds")
        sourceEnd = data.get("sourceEndMilliseconds")
        return cls(
            id=str(data["id"]),
            contentHash=str(data["contentHash"]),
            mediaType=TimelineMediaType(str(data["mediaType"])),
            startMilliseconds=int(data["startMilliseconds"]),
            endMilliseconds=int(data["endMilliseconds"]),
            layer=int(data.get("layer", 0)),
            sourceStartMilliseconds=(
                int(sourceStart) if sourceStart is not None else None
            ),
            sourceEndMilliseconds=int(sourceEnd) if sourceEnd is not None else None,
            role=VisualClipRole(
                str(
                    data.get(
                        "role",
                        "broll" if int(data.get("layer", 0)) == 0 else "avatar",
                    )
                )
            ),
        )


@dataclass(frozen=True)
class AudioClip:
    id: str
    contentHash: str
    startMilliseconds: int
    endMilliseconds: int
    sourceStartMilliseconds: int
    sourceEndMilliseconds: int
    volume: float = 0.2
    loop: bool = True
    layer: int = 0

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "contentHash": self.contentHash,
            "startMilliseconds": self.startMilliseconds,
            "endMilliseconds": self.endMilliseconds,
            "sourceStartMilliseconds": self.sourceStartMilliseconds,
            "sourceEndMilliseconds": self.sourceEndMilliseconds,
            "volume": self.volume,
            "loop": self.loop,
            "layer": self.layer,
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "AudioClip":
        return cls(
            id=str(data["id"]),
            contentHash=str(data["contentHash"]),
            startMilliseconds=int(data["startMilliseconds"]),
            endMilliseconds=int(data["endMilliseconds"]),
            sourceStartMilliseconds=int(data["sourceStartMilliseconds"]),
            sourceEndMilliseconds=int(data["sourceEndMilliseconds"]),
            volume=float(data.get("volume", 0.2)),
            loop=bool(data.get("loop", True)),
            layer=int(data.get("layer", 0)),
        )


@dataclass(frozen=True)
class SubtitleClip:
    id: str
    text: str
    startMilliseconds: int
    endMilliseconds: int
    layer: int = 0

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "startMilliseconds": self.startMilliseconds,
            "endMilliseconds": self.endMilliseconds,
            "layer": self.layer,
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "SubtitleClip":
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            startMilliseconds=int(data["startMilliseconds"]),
            endMilliseconds=int(data["endMilliseconds"]),
            layer=int(data.get("layer", 0)),
        )


@dataclass(frozen=True)
class TimelineScene:
    sceneId: str
    order: int
    startMilliseconds: int
    endMilliseconds: int
    mediaClips: tuple[MediaClip, ...] = ()
    subtitleClips: tuple[SubtitleClip, ...] = ()

    def toDictionary(self) -> dict[str, Any]:
        return {
            "sceneId": self.sceneId,
            "order": self.order,
            "startMilliseconds": self.startMilliseconds,
            "endMilliseconds": self.endMilliseconds,
            "mediaClips": [clip.toDictionary() for clip in self.mediaClips],
            "subtitleClips": [clip.toDictionary() for clip in self.subtitleClips],
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "TimelineScene":
        return cls(
            sceneId=str(data["sceneId"]),
            order=int(data["order"]),
            startMilliseconds=int(data["startMilliseconds"]),
            endMilliseconds=int(data["endMilliseconds"]),
            mediaClips=tuple(
                MediaClip.fromDictionary(item) for item in data.get("mediaClips", [])
            ),
            subtitleClips=tuple(
                SubtitleClip.fromDictionary(item)
                for item in data.get("subtitleClips", [])
            ),
        )


@dataclass(frozen=True)
class Timeline:
    id: str
    scenes: tuple[TimelineScene, ...]
    createdAt: datetime
    updatedAt: datetime
    schemaVersion: int = TIMELINE_SCHEMA_VERSION
    audioClips: tuple[AudioClip, ...] = ()

    @property
    def durationMilliseconds(self) -> int:
        return max((scene.endMilliseconds for scene in self.scenes), default=0)

    def toDictionary(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "id": self.id,
            "createdAt": self.createdAt.isoformat(),
            "updatedAt": self.updatedAt.isoformat(),
            "durationMilliseconds": self.durationMilliseconds,
            "scenes": [scene.toDictionary() for scene in self.scenes],
            "audioClips": [clip.toDictionary() for clip in self.audioClips],
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any]) -> "Timeline":
        schemaVersion = int(data["schemaVersion"])
        if schemaVersion not in (1, TIMELINE_SCHEMA_VERSION):
            raise ValueError("Unsupported timeline schema version.")
        return cls(
            id=str(data["id"]),
            scenes=tuple(TimelineScene.fromDictionary(item) for item in data["scenes"]),
            createdAt=datetime.fromisoformat(str(data["createdAt"])),
            updatedAt=datetime.fromisoformat(str(data["updatedAt"])),
            schemaVersion=TIMELINE_SCHEMA_VERSION,
            audioClips=tuple(
                AudioClip.fromDictionary(item) for item in data.get("audioClips", [])
            ),
        )
