import re

from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import Scene, ScriptFormat, SubtitleCue


class SceneParser:
    def parse(
        self,
        scriptFormat: ScriptFormat,
        content: str,
        cues: tuple[SubtitleCue, ...],
    ) -> tuple[Scene, ...]:
        if scriptFormat == ScriptFormat.SRT:
            return self._parseSubtitleCues(cues)
        return self._parseText(content)

    def _parseText(self, content: str) -> tuple[Scene, ...]:
        paragraphs = re.split(r"\n\s*\n", content.strip())
        scenes = tuple(
            self._createTextScene(order, paragraph)
            for order, paragraph in enumerate(paragraphs, start=1)
            if paragraph.strip()
        )
        if not scenes:
            raise ScriptError("NO_SCENES_GENERATED", "The script contains no scenes.")
        return scenes

    def _createTextScene(self, order: int, paragraph: str) -> Scene:
        text = "\n".join(line.strip() for line in paragraph.splitlines()).strip()
        return Scene(id=self._sceneId(order), order=order, text=text)

    def _parseSubtitleCues(self, cues: tuple[SubtitleCue, ...]) -> tuple[Scene, ...]:
        if not cues:
            raise ScriptError("NO_SCENES_GENERATED", "The subtitle contains no scenes.")
        return tuple(
            Scene(
                id=self._sceneId(order),
                order=order,
                text=cue.text,
                sourceCueIndexes=(cue.index,),
                startMilliseconds=cue.startMilliseconds,
                endMilliseconds=cue.endMilliseconds,
            )
            for order, cue in enumerate(cues, start=1)
        )

    def _sceneId(self, order: int) -> str:
        return f"scene-{order:04d}"
