import re

from app.pipeline.script_errors import ScriptError
from app.pipeline.script_models import SubtitleCue

TIMESTAMP_PATTERN = re.compile(
    r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
    r"\s+-->\s+"
    r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})(?:\s+.*)?$"
)


class SubtitleParser:
    def parse(self, content: str) -> tuple[SubtitleCue, ...]:
        normalizedContent = content.replace("\r\n", "\n").replace("\r", "\n")
        blocks = re.split(r"\n\s*\n", normalizedContent.strip())
        if not normalizedContent.strip():
            raise ScriptError("EMPTY_SCRIPT", "The subtitle file is empty.")

        cues: list[SubtitleCue] = []
        previousStart = -1
        for expectedIndex, block in enumerate(blocks, start=1):
            cue = self._parseBlock(block, expectedIndex)
            if cue.startMilliseconds < previousStart:
                raise ScriptError(
                    "INVALID_SRT_ORDER",
                    f"Subtitle cue {cue.index} starts before the previous cue.",
                )
            cues.append(cue)
            previousStart = cue.startMilliseconds
        return tuple(cues)

    def _parseBlock(self, block: str, expectedIndex: int) -> SubtitleCue:
        lines = block.splitlines()
        if len(lines) < 3:
            raise ScriptError(
                "INVALID_SRT_BLOCK",
                f"Subtitle block {expectedIndex} is incomplete.",
            )

        cueIndex = self._parseIndex(lines[0], expectedIndex)
        startMilliseconds, endMilliseconds = self._parseTimestamp(lines[1], cueIndex)
        text = "\n".join(lines[2:]).strip()
        if not text:
            raise ScriptError(
                "INVALID_SRT_TEXT", f"Subtitle cue {cueIndex} has no text."
            )
        return SubtitleCue(
            index=cueIndex,
            startMilliseconds=startMilliseconds,
            endMilliseconds=endMilliseconds,
            text=text,
        )

    def _parseIndex(self, value: str, expectedIndex: int) -> int:
        try:
            cueIndex = int(value.strip())
        except ValueError as error:
            raise ScriptError(
                "INVALID_SRT_INDEX",
                f"Subtitle block {expectedIndex} has an invalid index.",
            ) from error
        if cueIndex != expectedIndex:
            raise ScriptError(
                "INVALID_SRT_INDEX",
                f"Expected subtitle index {expectedIndex}, found {cueIndex}.",
            )
        return cueIndex

    def _parseTimestamp(self, value: str, cueIndex: int) -> tuple[int, int]:
        match = TIMESTAMP_PATTERN.match(value.strip())
        if not match:
            raise ScriptError(
                "INVALID_SRT_TIMESTAMP",
                f"Subtitle cue {cueIndex} has an invalid timestamp.",
            )

        parts = tuple(int(part) for part in match.groups())
        startMilliseconds = self._toMilliseconds(parts[:4])
        endMilliseconds = self._toMilliseconds(parts[4:])
        if endMilliseconds <= startMilliseconds:
            raise ScriptError(
                "INVALID_SRT_DURATION",
                f"Subtitle cue {cueIndex} must end after it starts.",
            )
        return startMilliseconds, endMilliseconds

    def _toMilliseconds(self, parts: tuple[int, ...]) -> int:
        hours, minutes, seconds, milliseconds = parts
        return (((hours * 60) + minutes) * 60 + seconds) * 1000 + milliseconds
