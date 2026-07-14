import threading

from app.project.errors import ProjectError
from app.project.project_model import Project
from app.repositories.scene_repository import SceneRepository
from app.repositories.timeline_repository import TimelineRepository
from app.services.script_service import ActiveProjectProvider
from app.timeline.initial_timeline_service import InitialTimelineService
from app.timeline.models import Timeline
from app.timeline.validation_service import TimelineValidationService


class TimelineService:
    def __init__(
        self,
        repository: TimelineRepository,
        sceneRepository: SceneRepository,
        projectService: ActiveProjectProvider,
        validator: TimelineValidationService,
        initialTimelineService: InitialTimelineService,
    ) -> None:
        self.repository = repository
        self.sceneRepository = sceneRepository
        self.projectService = projectService
        self.validator = validator
        self.initialTimelineService = initialTimelineService
        self.lock = threading.RLock()

    def saveTimeline(self, timeline: Timeline) -> Timeline:
        project = self._requireProject()
        with self.lock:
            scenes = self.sceneRepository.loadScenes(project.path)
            self.validator.validate(timeline, scenes)
            return self.repository.saveTimeline(project.path, timeline)

    def getTimeline(self) -> Timeline:
        project = self._requireProject()
        with self.lock:
            timeline = self.repository.loadTimeline(project.path)
            scenes = self.sceneRepository.loadScenes(project.path)
            self.validator.validate(timeline, scenes)
            return timeline

    def createInitialTimeline(self) -> Timeline:
        project = self._requireProject()
        with self.lock:
            scenes = self.sceneRepository.loadScenes(project.path)
            timeline = self.initialTimelineService.create(scenes)
            self.validator.validate(timeline, scenes)
            return self.repository.saveTimeline(project.path, timeline)

    def _requireProject(self) -> Project:
        project = self.projectService.getCurrentProject()
        if project is None:
            raise ProjectError("NO_ACTIVE_PROJECT", "No project is currently open.")
        return project
