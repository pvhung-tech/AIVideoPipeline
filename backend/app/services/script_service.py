from dataclasses import replace
from pathlib import Path
from typing import Protocol

from app.pipeline.scene_parser import SceneParser
from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import ScriptDocument, ScriptFormat, SubtitleCue
from app.pipeline.subtitle_parser import SubtitleParser
from app.project.errors import ProjectError
from app.project.project_model import Project
from app.repositories.scene_repository import SceneRepository
from app.repositories.script_repository import ScriptRepository


class ActiveProjectProvider(Protocol):
    def getCurrentProject(self) -> Project | None: ...


class ScriptService:
    def __init__(
        self,
        repository: ScriptRepository,
        projectService: ActiveProjectProvider,
        subtitleParser: SubtitleParser,
        sceneParser: SceneParser,
        sceneRepository: SceneRepository,
    ) -> None:
        self.repository = repository
        self.projectService = projectService
        self.subtitleParser = subtitleParser
        self.sceneParser = sceneParser
        self.sceneRepository = sceneRepository

    def importScript(self, sourcePath: Path) -> ScriptDocument:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")

        scriptFormat = self._detectFormat(sourcePath)
        content = self._normalizeContent(self.repository.readSource(sourcePath))
        cues: tuple[SubtitleCue, ...] = ()
        if scriptFormat == ScriptFormat.SRT:
            cues = self.subtitleParser.parse(content)

        scenes = self.sceneParser.parse(scriptFormat, content, cues)
        document = self.repository.saveScript(
            project.path,
            sourcePath,
            scriptFormat,
            content,
            cues,
        )
        self.sceneRepository.saveScenes(project.path, scenes)
        return replace(document, scenes=scenes)

    def _detectFormat(self, sourcePath: Path) -> ScriptFormat:
        extension = sourcePath.suffix.lower().lstrip(".")
        try:
            return ScriptFormat(extension)
        except ValueError as error:
            raise ScriptError(
                "UNSUPPORTED_SCRIPT_FORMAT",
                "Only TXT and SRT script files are supported.",
            ) from error

    def _normalizeContent(self, content: str) -> str:
        normalizedContent = content.replace("\r\n", "\n").replace("\r", "\n")
        if not normalizedContent.strip():
            raise ScriptError("EMPTY_SCRIPT", "The script file is empty.")
        return normalizedContent.rstrip() + "\n"
