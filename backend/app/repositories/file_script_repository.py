import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import ScriptDocument, ScriptFormat, SubtitleCue

logger = logging.getLogger(__name__)

MAX_SCRIPT_BYTES = 5 * 1024 * 1024


class FileScriptRepository:
    def readSource(self, sourcePath: Path) -> str:
        resolvedPath = sourcePath.expanduser().resolve()
        if not resolvedPath.is_file():
            raise ScriptError("SCRIPT_FILE_NOT_FOUND", "The script file was not found.")

        try:
            if resolvedPath.stat().st_size > MAX_SCRIPT_BYTES:
                raise ScriptError(
                    "SCRIPT_FILE_TOO_LARGE",
                    "Script files cannot exceed 5 MB.",
                )
            return resolvedPath.read_text(encoding="utf-8-sig")
        except ScriptError:
            raise
        except UnicodeDecodeError as error:
            raise ScriptError(
                "INVALID_SCRIPT_ENCODING", "Script files must use UTF-8 encoding."
            ) from error
        except OSError as error:
            logger.exception("Failed to read script source at %s", resolvedPath)
            raise ScriptError(
                "SCRIPT_READ_FAILED", "The script file could not be read."
            ) from error

    def saveScript(
        self,
        projectPath: Path,
        sourcePath: Path,
        scriptFormat: ScriptFormat,
        content: str,
        cues: tuple[SubtitleCue, ...],
    ) -> ScriptDocument:
        scriptDirectory = projectPath / "script"
        contentPath = scriptDirectory / f"source.{scriptFormat.value}"
        manifestPath = scriptDirectory / "manifest.json"
        importedAt = datetime.now(UTC)
        document = ScriptDocument(
            format=scriptFormat,
            originalPath=sourcePath.expanduser().resolve(),
            contentPath=contentPath,
            importedAt=importedAt,
            characterCount=len(content),
            cues=cues,
        )

        try:
            scriptDirectory.mkdir(parents=True, exist_ok=True)
            self._atomicWrite(contentPath, content)
            manifest = document.toDictionary()
            manifest.pop("cues", None)
            manifest.pop("scenes", None)
            self._atomicWrite(
                manifestPath,
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            )
            self._removeStaleSource(scriptDirectory, scriptFormat)
            return document
        except OSError as error:
            logger.exception("Failed to save script in project %s", projectPath)
            raise ScriptError(
                "SCRIPT_SAVE_FAILED", "The imported script could not be saved."
            ) from error

    def _atomicWrite(self, path: Path, content: str) -> None:
        temporaryPath = path.with_name(f".{path.name}.tmp")
        temporaryPath.write_text(content, encoding="utf-8")
        os.replace(temporaryPath, path)

    def _removeStaleSource(
        self, scriptDirectory: Path, activeFormat: ScriptFormat
    ) -> None:
        for scriptFormat in ScriptFormat:
            if scriptFormat != activeFormat:
                (scriptDirectory / f"source.{scriptFormat.value}").unlink(
                    missing_ok=True
                )
