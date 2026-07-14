from pathlib import Path
from typing import Protocol

from app.timeline.models import Timeline


class TimelineRepository(Protocol):
    def saveTimeline(self, projectPath: Path, timeline: Timeline) -> Timeline: ...

    def loadTimeline(self, projectPath: Path) -> Timeline: ...
