from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    path: Path
    createdAt: datetime
    updatedAt: datetime
    schemaVersion: int = PROJECT_SCHEMA_VERSION

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": str(self.path),
            "createdAt": self.createdAt.isoformat(),
            "updatedAt": self.updatedAt.isoformat(),
            "schemaVersion": self.schemaVersion,
        }

    @classmethod
    def fromDictionary(cls, data: dict[str, Any], projectPath: Path) -> "Project":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            path=projectPath,
            createdAt=datetime.fromisoformat(str(data["createdAt"])),
            updatedAt=datetime.fromisoformat(str(data["updatedAt"])),
            schemaVersion=int(data["schemaVersion"]),
        )
