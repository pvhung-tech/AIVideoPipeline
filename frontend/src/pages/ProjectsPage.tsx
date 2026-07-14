import {
  Brain,
  CircleX,
  FileText,
  Film,
  FolderOpen,
  Layers3,
  Library,
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listSceneAnalyses } from "../services/aiClient";
import { getMediaCacheManifest } from "../services/mediaClient";
import {
  closeProject,
  createProject,
  getCurrentProject,
  listRecentProjects,
  openProject,
  type ProjectSummary,
} from "../services/projectClient";
import { listRenderJobs, type RenderJob } from "../services/renderClient";
import { listScriptScenes, type SceneCollection } from "../services/scriptClient";
import { getTimeline, type Timeline } from "../services/timelineClient";

type DashboardStatus = "loading" | "ready" | "error";
const ACTIVE_RENDER_REFRESH_MS = 5000;
const RENDER_MONITOR_PATH = "/render#render-monitor";

interface DashboardState {
  project: ProjectSummary | null;
  recentProjects: ProjectSummary[];
  scenes: SceneCollection | null;
  analysisCount: number;
  timeline: Timeline | null;
  mediaCount: number;
  renderJobs: RenderJob[];
}

const emptyDashboard: DashboardState = {
  project: null,
  recentProjects: [],
  scenes: null,
  analysisCount: 0,
  timeline: null,
  mediaCount: 0,
  renderJobs: [],
};

export function ProjectsPage() {
  const [status, setStatus] = useState<DashboardStatus>("loading");
  const [message, setMessage] = useState("Loading workflow status...");
  const [dashboard, setDashboard] = useState<DashboardState>(emptyDashboard);
  const [newProjectName, setNewProjectName] = useState("");
  const [parentDirectory, setParentDirectory] = useState("");
  const [openProjectPath, setOpenProjectPath] = useState("");
  const [isProjectActionRunning, setIsProjectActionRunning] = useState(false);

  useEffect(() => {
    void loadDashboard();
  }, []);

  useEffect(() => {
    const activeRenderJob = findActiveRenderJob(dashboard.renderJobs);
    if (!activeRenderJob) return;
    const intervalId = window.setInterval(() => {
      void refreshDashboardQuietly();
    }, ACTIVE_RENDER_REFRESH_MS);
    return () => window.clearInterval(intervalId);
  }, [dashboard.renderJobs]);

  async function loadDashboard() {
    setStatus("loading");
    setMessage("Loading workflow status...");
    try {
      const nextDashboard = await readDashboardState();
      setDashboard(nextDashboard);
      setStatus("ready");
      setMessage(
        nextDashboard.project ? "Workflow status ready" : "Open a project to begin",
      );
    } catch (error: unknown) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Dashboard unavailable");
    }
  }

  async function refreshDashboardQuietly() {
    try {
      const nextDashboard = await readDashboardState();
      setDashboard(nextDashboard);
      setStatus("ready");
      setMessage(
        nextDashboard.project
          ? findActiveRenderJob(nextDashboard.renderJobs)
            ? "Render progress updated"
            : "Workflow status ready"
          : "Open a project to begin",
      );
    } catch (error: unknown) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Dashboard unavailable");
    }
  }

  async function readDashboardState(): Promise<DashboardState> {
    const [project, recentProjects] = await Promise.all([
      getCurrentProject(),
      listRecentProjects(),
    ]);
    const [scenes, analyses, timeline, mediaManifest, renderQueue] = project
      ? await Promise.all([
          listScriptScenes().catch(() => null),
          listSceneAnalyses().catch(() => null),
          getTimeline().catch(() => null),
          getMediaCacheManifest().catch(() => null),
          listRenderJobs().catch(() => ({ jobs: [] })),
        ])
      : [null, null, null, null, { jobs: [] }];

    return {
      project,
      recentProjects,
      scenes,
      analysisCount: analyses?.resultCount ?? 0,
      timeline,
      mediaCount: mediaManifest?.entries.length ?? 0,
      renderJobs: renderQueue.jobs,
    };
  }

  const steps = useMemo(() => buildWorkflowSteps(dashboard), [dashboard]);
  const completedSteps = steps.filter((step) => step.state === "complete").length;
  const nextStep = steps.find((step) => step.state !== "complete") ?? steps[steps.length - 1];
  const outputReview = summarizeOutputReview(dashboard.renderJobs);
  const latestCompletedJob = outputReview.latestJob;
  const activeRenderJob = findActiveRenderJob(dashboard.renderJobs);

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runProjectAction(async () => {
      const project = await createProject(
        newProjectName.trim(),
        parentDirectory.trim(),
      );
      setNewProjectName("");
      setParentDirectory("");
      return `Project created: ${project.name}`;
    });
  }

  async function handleOpenProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await openProjectFromPath(openProjectPath);
  }

  async function openProjectFromPath(path: string) {
    await runProjectAction(async () => {
      const project = await openProject(path.trim());
      setOpenProjectPath("");
      return `Project opened: ${project.name}`;
    });
  }

  async function handleCloseProject() {
    if (!dashboard.project) return;
    await runProjectAction(async () => {
      const project = await closeProject();
      return `Project closed: ${project.name}`;
    });
  }

  async function runProjectAction(action: () => Promise<string>) {
    setIsProjectActionRunning(true);
    try {
      const successMessage = await action();
      await loadDashboard();
      setMessage(successMessage);
    } catch (error: unknown) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Project action failed");
    } finally {
      setIsProjectActionRunning(false);
    }
  }

  return (
    <section className="dashboardWorkspace" aria-label="Workflow dashboard">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">Phase 7</p>
          <h2>Production dashboard</h2>
          <p className="timelineMessage" role="status">
            {message}
          </p>
        </div>
        <button className="secondaryButton" onClick={() => void loadDashboard()}>
          Refresh
        </button>
      </header>

      <section className="dashboardSummary" aria-label="Current workflow summary">
        <article className="summaryPanel">
          <span>Project</span>
          <strong>{dashboard.project?.name ?? "No project open"}</strong>
          <small>{dashboard.project?.path ?? "Open or create a project first"}</small>
        </article>
        <article className="summaryPanel">
          <span>Workflow</span>
          <strong>
            {completedSteps} / {steps.length} ready
          </strong>
          <small>{status === "loading" ? "Checking" : nextActionLabel(steps)}</small>
          <Link className="primaryButton summaryAction" to={nextStep.path}>
            Continue: {nextStep.title}
          </Link>
        </article>
        <article
          className={`summaryPanel outputReviewPanel${
            activeRenderJob ? " active" : latestCompletedJob ? " ready" : ""
          }`}
        >
          <span>{activeRenderJob ? "Active render" : "Latest output"}</span>
          <strong>
            {activeRenderJob?.fileName ?? latestCompletedJob?.fileName ?? "No MP4 yet"}
          </strong>
          <small>
            {activeRenderJob
              ? activeRenderStatusLabel(activeRenderJob)
              : outputReview.statusLabel}
          </small>
          {activeRenderJob ? (
            <>
              <div className="activeRenderProgress">
                <progress
                  aria-label="Active render progress"
                  max="100"
                  value={clampPercent(activeRenderJob.progressPercent)}
                />
                <span>{formatPercent(activeRenderJob.progressPercent)}</span>
              </div>
              <p className="activeRenderHint">
                Open Render to monitor progress or cancel the active job.
              </p>
              <Link className="primaryButton summaryAction" to={RENDER_MONITOR_PATH}>
                Monitor render
              </Link>
            </>
          ) : latestCompletedJob ? (
            <>
              <div className="latestOutputBadge" aria-label="Latest completed output">
                Newest output
              </div>
              <div
                className={`latestReviewBadge ${reviewTone(latestCompletedJob)}`}
                aria-label="Latest output review status"
              >
                Latest review: {reviewSummaryText(latestCompletedJob)}
              </div>
              <div className="outputReviewCounts" aria-label="Output review summary">
                <span>Accepted {outputReview.accepted}</span>
                <span>Rejected {outputReview.rejected}</span>
                <span>Not reviewed {outputReview.notReviewed}</span>
              </div>
              {outputReview.allReviewed && (
                <div className="reviewCompletionBanner">
                  <strong>All outputs reviewed</strong>
                  <span>Ready for handoff report or the next render pass.</span>
                </div>
              )}
              {outputReview.allReviewed ? (
                <div className="outputCompletionActions">
                  <Link className="primaryButton summaryAction" to="/render#render-queue">
                    Export review report
                  </Link>
                  <Link className="secondaryButton summaryAction" to="/render">
                    Start next render
                  </Link>
                </div>
              ) : (
                <Link
                  className="primaryButton summaryAction"
                  to={reviewQueuePath(latestCompletedJob)}
                >
                  Review output queue
                </Link>
              )}
            </>
          ) : (
            <Link className="secondaryButton summaryAction" to="/render">
              Open render
            </Link>
          )}
        </article>
      </section>

      <section className="projectManager" aria-label="Project manager">
        <div className="projectManagerHeader">
          <div>
            <h3>Project manager</h3>
            <p>Create a workspace, open an existing one, or close the active project.</p>
          </div>
          <button
            className="secondaryButton"
            disabled={!dashboard.project || isProjectActionRunning}
            onClick={() => void handleCloseProject()}
          >
            <CircleX aria-hidden="true" size={16} />
            Close project
          </button>
        </div>
        <div className="projectManagerGrid">
          <form className="projectManagerForm" onSubmit={handleCreateProject}>
            <h4>Create project</h4>
            <label>
              Project name
              <input
                minLength={1}
                maxLength={120}
                required
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                placeholder="News batch July"
              />
            </label>
            <label>
              Parent folder
              <input
                required
                value={parentDirectory}
                onChange={(event) => setParentDirectory(event.target.value)}
                placeholder="D:\Projects\Videos"
              />
            </label>
            <button
              className="primaryButton"
              disabled={isProjectActionRunning}
              type="submit"
            >
              Create project
            </button>
          </form>

          <form className="projectManagerForm" onSubmit={handleOpenProject}>
            <h4>Open project</h4>
            <label>
              Project folder
              <input
                required
                value={openProjectPath}
                onChange={(event) => setOpenProjectPath(event.target.value)}
                placeholder="D:\Projects\Videos\News batch July"
              />
            </label>
            <button
              className="secondaryButton"
              disabled={isProjectActionRunning}
              type="submit"
            >
              <FolderOpen aria-hidden="true" size={16} />
              Open project
            </button>
          </form>
        </div>
      </section>

      <section className="workflowSteps" aria-label="Production workflow steps">
        {steps.map((step) => (
          <article className={`workflowStep ${step.state}`} key={step.title}>
            <div className="workflowStepIcon">{step.icon}</div>
            <div>
              <div className="workflowStepTitle">
                <h3>{step.title}</h3>
                <span>{step.badge}</span>
              </div>
              <p>{step.detail}</p>
              {step.issue && (
                <div className="workflowGuidance">
                  <strong>{step.issue}</strong>
                  <span>{step.fix}</span>
                </div>
              )}
              <Link className="secondaryButton" to={step.path}>
                {step.action}
              </Link>
            </div>
          </article>
        ))}
      </section>

      {dashboard.recentProjects.length > 0 && (
        <section className="recentProjects" aria-label="Recent projects">
          <h3>Recent projects</h3>
          <div className="recentProjectRows">
            {dashboard.recentProjects.map((project) => (
              <div className="recentProjectRow" key={project.id}>
                <strong>{project.name}</strong>
                <span>{project.path}</span>
                <button
                  className="secondaryButton"
                  disabled={isProjectActionRunning}
                  onClick={() => void openProjectFromPath(project.path)}
                >
                  Open
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}

interface WorkflowStep {
  title: string;
  detail: string;
  badge: string;
  action: string;
  path: string;
  state: "complete" | "current" | "waiting" | "error";
  issue: string | null;
  fix: string;
  icon: ReactNode;
}

function buildWorkflowSteps(dashboard: DashboardState): WorkflowStep[] {
  const hasProject = Boolean(dashboard.project);
  const sceneCount = dashboard.scenes?.sceneCount ?? 0;
  const hasScenes = sceneCount > 0;
  const hasAnalysis = hasScenes && dashboard.analysisCount >= sceneCount;
  const hasTimeline = Boolean(dashboard.timeline);
  const hasMedia = dashboard.mediaCount > 0;
  const completedJobs = dashboard.renderJobs.filter(
    (job) => job.status === "completed",
  );
  const failedJob = dashboard.renderJobs.find((job) => job.status === "failed");
  const activeJob = findActiveRenderJob(dashboard.renderJobs);
  const hasRender = completedJobs.length > 0;

  return [
    {
      title: "Project",
      detail: hasProject
        ? `${dashboard.project?.name} is open`
        : "Choose the working folder for this video batch",
      badge: hasProject ? "Ready" : "Start here",
      action: hasProject ? "Manage project" : "Open projects",
      path: "/projects",
      state: hasProject ? "complete" : "current",
      issue: hasProject ? null : "No active project.",
      fix: "Create a new project or open a recent project to unlock the workflow.",
      icon: <FolderOpen aria-hidden="true" size={20} />,
    },
    {
      title: "Script",
      detail: hasScenes
        ? `${sceneCount} scenes are ready for editing`
        : "Import TXT or SRT, then review the generated scenes",
      badge: hasScenes ? "Ready" : "Needs script",
      action: "Review script",
      path: "/pipeline",
      state: stepState(hasProject, hasScenes),
      issue: hasScenes ? null : "No editable scenes found.",
      fix: hasProject
        ? "Import a TXT or SRT file, then save any scene edits."
        : "Open a project first so script files have a workspace.",
      icon: <FileText aria-hidden="true" size={20} />,
    },
    {
      title: "AI",
      detail: hasAnalysis
        ? `${dashboard.analysisCount} scenes have AI descriptions and keywords`
        : "Run scene analysis to generate media search keywords",
      badge: hasAnalysis ? "Ready" : "Needs analysis",
      action: "Analyze scenes",
      path: "/analysis",
      state: stepState(hasScenes, hasAnalysis),
      issue: hasAnalysis ? null : "Scene analysis is incomplete.",
      fix: hasScenes
        ? "Choose a provider/model and run Analyze all in the AI workspace."
        : "Import script scenes before running AI analysis.",
      icon: <Brain aria-hidden="true" size={20} />,
    },
    {
      title: "Media",
      detail: hasMedia
        ? `${dashboard.mediaCount} cached media assets available`
        : "Search and download visual or music assets from AI keywords",
      badge: hasMedia ? "Ready" : "Needs media",
      action: "Manage media",
      path: "/media",
      state: stepState(hasAnalysis, hasMedia),
      issue: hasMedia ? null : "No cached media assets yet.",
      fix: hasAnalysis
        ? "Use AI keywords in Media Search, download suitable assets, then assign them."
        : "Run AI analysis first so Media Search starts with useful keywords.",
      icon: <Library aria-hidden="true" size={20} />,
    },
    {
      title: "Timeline",
      detail: hasTimeline
        ? `${dashboard.timeline?.scenes.length ?? 0} timeline scenes assembled`
        : "Generate the editable timeline and assign selected media",
      badge: hasTimeline ? "Ready" : "Needs timeline",
      action: "Edit timeline",
      path: "/timeline",
      state: stepState(hasMedia, hasTimeline),
      issue: hasTimeline ? null : "Timeline has not been generated.",
      fix: hasMedia
        ? "Generate the timeline, adjust layers, and confirm media clips."
        : "Download media first so timeline assembly has usable assets.",
      icon: <Layers3 aria-hidden="true" size={20} />,
    },
    {
      title: "Render",
      detail: activeJob
        ? `${activeJob.fileName} is ${activeJob.status}`
        : hasRender
          ? `${completedJobs.length} completed output${completedJobs.length === 1 ? "" : "s"}`
          : "Run preflight and export the MP4",
      badge: failedJob ? "Failed" : activeJob ? "Rendering" : hasRender ? "Ready" : "Needs render",
      action: activeJob ? "Monitor render" : "Open render",
      path: activeJob ? RENDER_MONITOR_PATH : "/render",
      state: failedJob
        ? "error"
        : activeJob
          ? "current"
          : stepState(hasTimeline && hasMedia, hasRender),
      issue: failedJob
        ? failedJob.errorMessage ?? failedJob.errorCode ?? "A render job failed."
        : activeJob
          ? "Render job is in progress."
        : hasRender
          ? null
          : "No completed MP4 output yet.",
      fix: failedJob
        ? "Open Render, review diagnostics, fix preflight issues, then retry."
        : activeJob
          ? "Open Render to monitor progress or cancel the active job."
        : hasTimeline && hasMedia
          ? "Run preflight, choose an export profile, and start render."
          : "Finish Timeline and Media before rendering.",
      icon: <Film aria-hidden="true" size={20} />,
    },
  ];
}

function stepState(
  prerequisiteReady: boolean,
  complete: boolean,
): WorkflowStep["state"] {
  if (complete) return "complete";
  return prerequisiteReady ? "current" : "waiting";
}

function nextActionLabel(steps: WorkflowStep[]): string {
  const next = steps.find((step) => step.state !== "complete");
  return next ? next.detail : "Ready for final review";
}

function findActiveRenderJob(jobs: RenderJob[]): RenderJob | null {
  const activeStatuses = ["running", "preparing", "cancelling", "queued"];
  return (
    activeStatuses
      .map((status) => jobs.find((job) => job.status === status))
      .find((job): job is RenderJob => Boolean(job)) ?? null
  );
}

function activeRenderStatusLabel(job: RenderJob): string {
  if (job.status === "queued") return "Queued for render";
  if (job.status === "preparing") return "Preparing subtitles";
  if (job.status === "cancelling") return `Cancelling ${formatPercent(job.progressPercent)}`;
  return `Rendering ${formatPercent(job.progressPercent)}`;
}

function formatPercent(value: number): string {
  return `${clampPercent(value).toFixed(1)}%`;
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function reviewQueuePath(job: RenderJob): string {
  return `/render?reviewJob=${encodeURIComponent(job.jobId)}#render-queue`;
}

interface OutputReviewSummary {
  latestJob: RenderJob | null;
  total: number;
  accepted: number;
  rejected: number;
  notReviewed: number;
  allReviewed: boolean;
  statusLabel: string;
}

function summarizeOutputReview(jobs: RenderJob[]): OutputReviewSummary {
  const completed = jobs.filter((job) => job.status === "completed" && job.outputPath);
  const latestJob = completed[completed.length - 1] ?? null;
  const accepted = completed.filter((job) => job.review?.status === "accepted").length;
  const rejected = completed.filter((job) => job.review?.status === "rejected").length;
  const notReviewed = completed.filter((job) => !job.review).length;
  const allReviewed = completed.length > 0 && notReviewed === 0;
  return {
    latestJob,
    total: completed.length,
    accepted,
    rejected,
    notReviewed,
    allReviewed,
    statusLabel: allReviewed
      ? `All ${completed.length} output${completed.length === 1 ? "" : "s"} reviewed`
      : latestJob
        ? reviewStatusLabel(latestJob)
        : "Render when ready",
  };
}

function reviewStatusLabel(job: RenderJob): string {
  if (job.review?.status === "accepted") return "Accepted output";
  if (job.review?.status === "rejected") return "Rejected output";
  return "Completed and ready to review";
}

function reviewSummaryText(job: RenderJob): string {
  if (job.review?.status === "accepted") return "Accepted";
  if (job.review?.status === "rejected") return "Rejected";
  return "Not reviewed";
}

function reviewTone(job: RenderJob): string {
  if (job.review?.status === "accepted") return "accepted";
  if (job.review?.status === "rejected") return "rejected";
  return "pending";
}
