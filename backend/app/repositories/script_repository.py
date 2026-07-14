from pathlib import Path
from typing import Protocol

from app.pipeline.script_models import ScriptDocument, ScriptFormat, SubtitleCue


class ScriptRepository(Protocol):
    def readSource(self, sourcePath: Path) -> str: ...

    def saveScript(
        self,
        projectPath: Path,
        sourcePath: Path,
        scriptFormat: ScriptFormat,
        content: str,
        cues: tuple[SubtitleCue, ...],
    ) -> ScriptDocument: ...
