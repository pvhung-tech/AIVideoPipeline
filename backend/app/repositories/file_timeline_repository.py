import json
import logging
import os
from pathlib import Path
from typing import Any

from app.timeline.errors import TimelineError
from app.timeline.models import Timeline

logger = logging.getLogger(__name__)


class FileTimelineRepository:
    def saveTimeline(self, projectPath: Path, timeline: Timeline) -> Timeline:
        timelinePath = self._timelinePath(projectPath)
        temporaryPath = timelinePath.with_name(f".{timelinePath.name}.tmp")
        try:
            timelinePath.parent.mkdir(parents=True, exist_ok=True)
            temporaryPath.write_text(
                json.dumps(timeline.toDictionary(), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporaryPath, timelinePath)
            return timeline
        except OSError as error:
            logger.exception("Failed to save timeline in project %s", projectPath)
            raise TimelineError(
                "TIMELINE_SAVE_FAILED", "The timeline could not be saved."
            ) from error

    def loadTimeline(self, projectPath: Path) -> Timeline:
        timelinePath = self._timelinePath(projectPath)
        if not timelinePath.is_file():
            raise TimelineError(
                "TIMELINE_NOT_FOUND", "The project does not have a saved timeline."
            )
        try:
            data: Any = json.loads(timelinePath.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Timeline document must be an object.")
            return Timeline.fromDictionary(data)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise TimelineError(
                "INVALID_TIMELINE_FILE", "The saved timeline is invalid."
            ) from error
        except OSError as error:
            logger.exception("Failed to load timeline from project %s", projectPath)
            raise TimelineError(
                "TIMELINE_READ_FAILED", "The timeline could not be read."
            ) from error

    def _timelinePath(self, projectPath: Path) -> Path:
        return projectPath / "timeline" / "timeline.json"
