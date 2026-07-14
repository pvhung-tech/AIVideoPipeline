import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { useAppStore } from "./store/appStore";

const renderPreflightMock = vi.hoisted(() => vi.fn());
const renderJobsMock = vi.hoisted(() => vi.fn());
const clipboardWriteTextMock = vi.hoisted(() => vi.fn(() => Promise.resolve()));
const createObjectUrlMock = vi.hoisted(() => vi.fn(() => "blob:render-export"));
const revokeObjectUrlMock = vi.hoisted(() => vi.fn());
const anchorClickMock = vi.hoisted(() => vi.fn());
const printMock = vi.hoisted(() => vi.fn());
const selectScriptFileMock = vi.hoisted(() =>
  vi.fn(() => Promise.resolve("D:\\Scripts\\episode.srt")),
);
const mediaSearchMock = vi.hoisted(() => vi.fn());
const projectClientState = vi.hoisted(() => ({
  currentProject: {
    id: "project-1",
    name: "Demo Project",
    path: "C:\\project",
    createdAt: "2026-07-11T00:00:00Z",
    updatedAt: "2026-07-11T00:00:00Z",
    schemaVersion: 1,
  } as {
    id: string;
    name: string;
    path: string;
    createdAt: string;
    updatedAt: string;
    schemaVersion: number;
  } | null,
  recentProjects: [
    {
      id: "project-1",
      name: "Demo Project",
      path: "C:\\project",
      createdAt: "2026-07-11T00:00:00Z",
      updatedAt: "2026-07-11T00:00:00Z",
      schemaVersion: 1,
    },
  ],
}));
const scriptClientState = vi.hoisted(() => ({
  collection: {
    schemaVersion: 1,
    sceneCount: 1,
    updatedAt: "2026-07-11T00:00:00Z",
    scenes: [
      {
        id: "scene-1",
        order: 1,
        text: "Opening subtitle",
        startMilliseconds: 0,
        endMilliseconds: 3000,
      },
    ],
  },
}));
const aiClientState = vi.hoisted(() => ({
  analyses: [
    {
      sceneId: "scene-1",
      sourceTextHash: "c".repeat(64),
      description: "A city skyline establishing shot for the opening scene.",
      category: "news",
      keywords: ["city skyline", "urban sunrise"],
      providerId: "ollama",
      model: "llama3.2",
      promptVersion: 1,
      analyzedAt: "2026-07-12T00:00:00Z",
    },
  ],
}));
const mediaClientState = vi.hoisted(() => ({
  assets: [
    {
      contentHash: "a".repeat(64),
      mediaType: "image",
      fileName: "cached.jpg",
      uri: "file:///cache/cached.jpg",
      sizeBytes: 1024,
      providerIds: ["pexels"],
      durationMilliseconds: null,
    },
  ],
  manifest: {
    schemaVersion: 1,
    totalSizeBytes: 1024,
    entries: [
      {
        contentHash: "a".repeat(64),
        relativePath: "aa/cached.jpg",
        sizeBytes: 1024,
        durationMilliseconds: null,
      },
    ],
  },
  fingerprintBackfillJob: {
    jobId: "fingerprint-job-1",
    projectId: "project-1",
    status: "completed",
    totalMedia: 1,
    processedMedia: 1,
    progressPercent: 100,
    updatedMedia: 0,
    skippedMedia: 1,
    failedCount: 0,
    failedContentHashes: [],
    errorMessage: null,
  } as {
    jobId: string;
    projectId: string;
    status: "queued" | "running" | "completed" | "cancelled" | "failed";
    totalMedia: number;
    processedMedia: number;
    progressPercent: number;
    updatedMedia: number;
    skippedMedia: number;
    failedCount: number;
    failedContentHashes: string[];
    errorMessage: string | null;
  } | null,
}));
const timelineClientState = vi.hoisted(() => ({
  timeline: {
    schemaVersion: 2,
    id: "timeline-1",
    createdAt: "2026-07-02T00:00:00Z",
    updatedAt: "2026-07-02T00:00:00Z",
    durationMilliseconds: 3000,
    audioClips: [],
    scenes: [
      {
        sceneId: "scene-1",
        order: 1,
        startMilliseconds: 0,
        endMilliseconds: 3000,
        mediaClips: [] as Array<
          Record<string, unknown> & { role: "broll" | "avatar" }
        >,
        subtitleClips: [
          {
            id: "subtitle-scene-1",
            text: "Opening subtitle",
            startMilliseconds: 0,
            endMilliseconds: 3000,
            layer: 0,
          },
        ],
      },
    ],
  },
}));

vi.mock("./services/healthClient", () => ({
  getBackendHealth: () =>
    Promise.resolve({
      appName: "AI Video Pipeline Studio",
      environment: "development",
      status: "ok",
    }),
}));

vi.mock("./services/projectClient", () => ({
  getCurrentProject: () => Promise.resolve(projectClientState.currentProject),
  listRecentProjects: () => Promise.resolve(projectClientState.recentProjects),
  createProject: (name: string, parentDirectory: string) => {
    const project = {
      id: "created-project",
      name,
      path: `${parentDirectory}\\${name}`,
      createdAt: "2026-07-12T00:00:00Z",
      updatedAt: "2026-07-12T00:00:00Z",
      schemaVersion: 1,
    };
    projectClientState.currentProject = project;
    projectClientState.recentProjects = [project, ...projectClientState.recentProjects];
    return Promise.resolve(project);
  },
  openProject: (path: string) => {
    const project =
      projectClientState.recentProjects.find((item) => item.path === path) ?? {
        id: "opened-project",
        name: "Opened Project",
        path,
        createdAt: "2026-07-12T00:00:00Z",
        updatedAt: "2026-07-12T00:00:00Z",
        schemaVersion: 1,
      };
    projectClientState.currentProject = project;
    return Promise.resolve(project);
  },
  closeProject: () => {
    const project = projectClientState.currentProject ?? projectClientState.recentProjects[0];
    projectClientState.currentProject = null;
    return Promise.resolve(project);
  },
}));

vi.mock("./services/scriptClient", () => ({
  importScript: (path: string) => {
    const document = {
      format: path.toLowerCase().endsWith(".srt") ? "srt" : "txt",
      originalPath: path,
      contentPath: "C:\\project\\script\\source.srt",
      importedAt: "2026-07-12T00:00:00Z",
      characterCount: 42,
      cueCount: 2,
      sceneCount: 2,
      scenes: [
        {
          id: "scene-1",
          order: 1,
          text: "Imported opening",
          startMilliseconds: 0,
          endMilliseconds: 2000,
        },
        {
          id: "scene-2",
          order: 2,
          text: "Imported closing",
          startMilliseconds: 2000,
          endMilliseconds: 4000,
        },
      ],
    };
    scriptClientState.collection = {
      schemaVersion: 1,
      sceneCount: document.sceneCount,
      updatedAt: document.importedAt,
      scenes: document.scenes,
    };
    return Promise.resolve(document);
  },
  listScriptScenes: () => Promise.resolve(scriptClientState.collection),
  updateScriptScene: (sceneId: string, text: string) => {
    scriptClientState.collection = {
      ...scriptClientState.collection,
      updatedAt: "2026-07-12T00:01:00Z",
      scenes: scriptClientState.collection.scenes.map((scene) =>
        scene.id === sceneId ? { ...scene, text } : scene,
      ),
    };
    return Promise.resolve(scriptClientState.collection);
  },
}));

vi.mock("./services/aiClient", () => ({
  listSceneAnalyses: () =>
    Promise.resolve({
      schemaVersion: 1,
      updatedAt: "2026-07-12T00:00:00Z",
      resultCount: aiClientState.analyses.length,
      results: aiClientState.analyses,
    }),
  analyzeScenesBatch: (options: { providerId: string; model: string }) => {
    aiClientState.analyses = scriptClientState.collection.scenes.map((scene) => ({
      sceneId: scene.id,
      sourceTextHash: "d".repeat(64),
      description: `Analysis for ${scene.text}`,
      category: "documentary",
      keywords: scene.id === "scene-1"
        ? ["city skyline", "urban sunrise"]
        : ["closing scene", "final shot"],
      providerId: options.providerId,
      model: options.model,
      promptVersion: 1,
      analyzedAt: "2026-07-12T00:02:00Z",
    }));
    return Promise.resolve({
      totalScenes: scriptClientState.collection.scenes.length,
      successCount: aiClientState.analyses.length,
      failureCount: 0,
      skippedCount: 0,
      results: aiClientState.analyses,
      failures: [],
      skippedSceneIds: [],
    });
  },
}));

vi.mock("./services/setupClient", () => ({
  getSetupStatus: () =>
    Promise.resolve({
      providers: [
        {
          id: "ollama",
          label: "Ollama",
          status: "ready",
          configured: true,
          message: "Ollama is ready with llama3.2.",
          hint: "You can use Ollama for local scene analysis.",
          envVar: "OLLAMA_MODEL",
          valuePreview: "llama3.2",
        },
        {
          id: "openai",
          label: "OpenAI",
          status: "missing_key",
          configured: false,
          message: "OpenAI key is not configured.",
          hint: "Set OPENAI_API_KEY in the environment, restart the desktop app, then refresh setup.",
          envVar: "OPENAI_API_KEY",
          valuePreview: "gpt-5-mini",
        },
      ],
      apiKeys: [
        {
          id: "openai",
          label: "OpenAI API key",
          status: "missing_key",
          configured: false,
          message: "OpenAI API key is not configured.",
          hint: "Set OPENAI_API_KEY, restart the app, then refresh setup.",
          envVar: "OPENAI_API_KEY",
          valuePreview: null,
        },
      ],
      tools: [
        {
          id: "wikimedia-user-agent",
          label: "Wikimedia User-Agent",
          status: "configured",
          configured: true,
          message: "Wikimedia User-Agent is configured.",
          hint: "Live Wikimedia searches can run.",
          envVar: "WIKIMEDIA_USER_AGENT",
          valuePreview: null,
        },
      ],
    }),
}));

vi.mock("./services/mediaClient", () => ({
  MediaApiError: class MediaApiError extends Error {
    constructor(
      public readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  listMediaProviders: () =>
    Promise.resolve(["local", "pexels", "pixabay", "wikimedia", "dvids"]),
  searchMedia: mediaSearchMock,
  cacheMedia: () => {
    const cached = {
      mediaId: "pexels-photo-1",
      providerId: "pexels",
      contentHash: "b".repeat(64),
      path: "C:\\project\\cache\\bb\\downloaded.jpg",
      uri: "file:///cache/downloaded.jpg",
      sizeBytes: 4096,
      duplicate: false,
    };
    mediaClientState.assets = [
      ...mediaClientState.assets,
      {
        contentHash: cached.contentHash,
        mediaType: "image",
        fileName: "downloaded.jpg",
        uri: cached.uri,
        sizeBytes: cached.sizeBytes,
        providerIds: ["pexels"],
        durationMilliseconds: null,
      },
    ];
    mediaClientState.manifest = {
      schemaVersion: 1,
      totalSizeBytes: 5120,
      entries: [
        ...mediaClientState.manifest.entries,
        {
          contentHash: cached.contentHash,
          relativePath: "bb/downloaded.jpg",
          sizeBytes: cached.sizeBytes,
          durationMilliseconds: null,
        },
      ],
    };
    return Promise.resolve(cached);
  },
  getMediaCacheManifest: () => Promise.resolve(mediaClientState.manifest),
  getMediaFingerprintBackfillStatus: () =>
    Promise.resolve(mediaClientState.fingerprintBackfillJob),
  backfillMediaFingerprints: () =>
    Promise.resolve(mediaClientState.fingerprintBackfillJob),
  cancelMediaFingerprintBackfill: () =>
    Promise.resolve(mediaClientState.fingerprintBackfillJob),
}));

vi.mock("./services/timelineClient", () => {
  class TimelineApiError extends Error {
    code = "TIMELINE_NOT_FOUND";
  }

  return {
    TimelineApiError,
    getTimeline: () => {
      if (!timelineClientState.timeline) {
        return Promise.reject(new TimelineApiError("Timeline not found"));
      }
      return Promise.resolve(timelineClientState.timeline);
    },
  generateTimeline: vi.fn(),
  saveTimeline: vi.fn(),
  assignTimelineMedia: (
    sceneId: string,
    contentHash: string | null,
    role: "broll" | "avatar",
  ) => {
    timelineClientState.timeline = {
      ...timelineClientState.timeline,
      scenes: timelineClientState.timeline.scenes.map((scene) =>
        scene.sceneId === sceneId
          ? {
              ...scene,
              mediaClips: contentHash
                ? [
                    ...scene.mediaClips.filter((clip) => clip.role !== role),
                    {
                      id: `${role}-${sceneId}`,
                      contentHash,
                      mediaType: "image",
                      startMilliseconds: scene.startMilliseconds,
                      endMilliseconds: scene.endMilliseconds,
                      layer: role === "broll" ? 0 : 1,
                      sourceStartMilliseconds: null,
                      sourceEndMilliseconds: null,
                      role,
                    },
                  ]
                : scene.mediaClips.filter((clip) => clip.role !== role),
            }
          : scene,
      ),
    };
    return Promise.resolve(timelineClientState.timeline);
  },
  assignTimelineMusic: vi.fn(),
  trimTimelineVideo: vi.fn(),
  backfillVideoMetadata: vi.fn(),
  getTimelineMediaAssetPage: () =>
    Promise.resolve({
      assets: mediaClientState.assets,
      offset: 0,
      limit: 100,
      totalEntries: mediaClientState.assets.length,
      hasMore: false,
    }),
  getTimelineMediaAssets: () => Promise.resolve(mediaClientState.assets),
  };
});

vi.mock("./services/renderClient", () => ({
  RenderApiError: class RenderApiError extends Error {
    code = "RENDER_FAILED";
  },
  listRenderJobs: () =>
    Promise.resolve({
      jobs: renderJobsMock(),
    }),
  listRenderProfiles: () =>
    Promise.resolve({
      profiles: [
        {
          profileId: "fast_preview",
          name: "Fast Preview",
          settings: {
            profileId: "fast_preview",
            width: 640,
            height: 360,
            frameRate: 15,
            crf: 32,
            encoderPreset: "veryfast",
            audioBitrateKbps: 96,
          },
        },
        {
          profileId: "standard",
          name: "Standard",
          settings: {
            profileId: "standard",
            width: 1920,
            height: 1080,
            frameRate: 30,
            crf: 18,
            encoderPreset: "medium",
            audioBitrateKbps: 192,
          },
        },
      ],
    }),
  checkRenderPreflight: renderPreflightMock,
  startRenderJob: () =>
    Promise.resolve({
      jobId: "job-1",
      projectId: "project-1",
      fileName: "rendered.mp4",
      status: "completed",
      progressPercent: 100,
      processedMilliseconds: 3000,
      durationMilliseconds: 3000,
      outputPath: "C:\\project\\output\\rendered.mp4",
      sizeBytes: 2048,
      errorCode: null,
      errorMessage: null,
      exportSettings: {
        profileId: "standard",
        width: 1920,
        height: 1080,
        frameRate: 30,
        crf: 18,
        encoderPreset: "medium",
        audioBitrateKbps: 192,
      },
      outputNameTemplate: "{project}-{datetime}.mp4",
      diagnostics: {
        commandSummary: {
          commandAvailable: true,
          executable: "ffmpeg.exe",
          inputCount: 1,
          videoCodec: "libx264",
          encoderPreset: "medium",
        },
        settingsSnapshot: {
          profileId: "standard",
          width: 1920,
          height: 1080,
        },
        metrics: {
          status: "completed",
          elapsedMilliseconds: 1000,
          returnCode: 0,
        },
        stderrTail: null,
      },
      preview: {
        thumbnailPath: "C:\\project\\render\\previews\\job-1.jpg",
        thumbnailUri: "file:///C:/project/render/previews/job-1.jpg",
        durationMilliseconds: 3000,
        sizeBytes: 2048,
        width: 1920,
        height: 1080,
        frameRate: 30,
        generatedAt: "2026-07-10T00:00:00+00:00",
        status: "available",
        errorMessage: null,
      },
      review: null,
    }),
  reviewRenderJob: (
    jobId: string,
    status: "accepted" | "rejected",
    note: string | null,
  ) => {
    const source = (
      renderJobsMock() as Array<{ jobId: string } & Record<string, unknown>>
    ).find((item) => item.jobId === jobId);
    const fileName =
      typeof source?.fileName === "string" ? source.fileName : "rendered.mp4";
    const outputPath =
      typeof source?.outputPath === "string"
        ? source.outputPath
        : "C:\\project\\output\\rendered.mp4";
    return Promise.resolve({
      ...(source ?? {}),
      jobId,
      projectId: "project-1",
      fileName,
      status: "completed",
      progressPercent: 100,
      processedMilliseconds: 3000,
      durationMilliseconds: 3000,
      outputPath,
      sizeBytes: 2048,
      errorCode: null,
      errorMessage: null,
      exportSettings: {
        profileId: "standard",
        width: 1920,
        height: 1080,
        frameRate: 30,
        crf: 18,
        encoderPreset: "medium",
        audioBitrateKbps: 192,
      },
      outputNameTemplate: "{project}-{datetime}.mp4",
      diagnostics: null,
      preview: {
        thumbnailPath: "C:\\project\\render\\previews\\job-1.jpg",
        thumbnailUri: "file:///C:/project/render/previews/job-1.jpg",
        durationMilliseconds: 3000,
        sizeBytes: 2048,
        width: 1920,
        height: 1080,
        frameRate: 30,
        generatedAt: "2026-07-10T00:00:00+00:00",
        status: "available",
        errorMessage: null,
      },
      review: {
        status,
        note,
        reviewedAt: "2026-07-10T00:01:00+00:00",
      },
    });
  },
  clearRenderJobReview: (jobId: string) => {
    const source = (
      renderJobsMock() as Array<{ jobId: string } & Record<string, unknown>>
    ).find((item) => item.jobId === jobId);
    return Promise.resolve({
      ...(source ?? {}),
      jobId,
      projectId: "project-1",
      fileName: typeof source?.fileName === "string" ? source.fileName : "rendered.mp4",
      status: "completed",
      progressPercent: 100,
      processedMilliseconds: 3000,
      durationMilliseconds: 3000,
      outputPath:
        typeof source?.outputPath === "string"
          ? source.outputPath
          : "C:\\project\\output\\rendered.mp4",
      sizeBytes: 2048,
      errorCode: null,
      errorMessage: null,
      exportSettings: {
        profileId: "standard",
        width: 1920,
        height: 1080,
        frameRate: 30,
        crf: 18,
        encoderPreset: "medium",
        audioBitrateKbps: 192,
      },
      outputNameTemplate: "{project}-{datetime}.mp4",
      diagnostics: null,
      preview: null,
      review: null,
    });
  },
  getRenderJob: vi.fn(),
  cancelRenderJob: vi.fn(),
  resumeRenderJob: vi.fn(),
  retryRenderJob: vi.fn(),
  cleanupRenderJobs: () =>
    Promise.resolve({
      jobs: [],
    }),
  exportRenderQueueReport: (
    format: "csv" | "json",
    reviewStatus = "all",
    jobStatus = "all",
    dateFrom: string | null = null,
    dateTo: string | null = null,
  ) =>
    Promise.resolve({
      format,
      reportPath: `C:\\project\\render\\reports\\render-queue-report.${format}`,
      jobCount: 2,
      generatedAt: "2026-07-10T00:02:00+00:00",
      summary: {
        total: 2,
        accepted: 1,
        rejected: 0,
        notReviewed: 1,
        completed: 2,
        failed: 0,
      },
      filters: { reviewStatus, jobStatus, dateFrom, dateTo },
    }),
  exportRenderQueueHandoffBundle: (
    reviewStatus = "all",
    jobStatus = "all",
    dateFrom: string | null = null,
    dateTo: string | null = null,
  ) =>
    Promise.resolve({
      bundlePath: "C:\\project\\render\\reports\\bundles\\bundle",
      archivePath: "C:\\project\\render\\reports\\bundles\\bundle.zip",
      manifestPath: "C:\\project\\render\\reports\\bundles\\bundle\\manifest.json",
      csvReportPath:
        "C:\\project\\render\\reports\\bundles\\bundle\\render-queue-report.csv",
      jsonReportPath:
        "C:\\project\\render\\reports\\bundles\\bundle\\render-queue-report.json",
      jobCount: 2,
      thumbnailCount: 1,
      generatedAt: "2026-07-10T00:02:00+00:00",
      summary: {
        total: 2,
        accepted: 1,
        rejected: 0,
        notReviewed: 1,
        completed: 2,
        failed: 0,
      },
      filters: { reviewStatus, jobStatus, dateFrom, dateTo },
    }),
  importRenderBundleReviews: (manifestPath: string) =>
    Promise.resolve({
      manifestPath,
      reportPath:
        "C:\\project\\render\\reports\\imports\\render-bundle-import.json",
      applied: 1,
      skipped: 1,
      accepted: 1,
      rejected: 0,
      details: [
        {
          jobId: "job-completed",
          status: "applied",
          decision: "accepted",
          reason: null,
        },
        {
          jobId: "job-pending",
          status: "skipped",
          decision: "not_reviewed",
          reason: "Decision is not accepted or rejected.",
        },
      ],
    }),
  listRenderBundleImportReports: () =>
    Promise.resolve({
      reports: [
        {
          reportPath:
            "C:\\project\\render\\reports\\imports\\render-bundle-import.json",
          importedAt: "2026-07-10T00:03:00+00:00",
          manifestPath:
            "C:\\project\\render\\reports\\bundles\\bundle\\manifest.json",
          sourceBundlePath: "C:\\project\\render\\reports\\bundles\\bundle",
          sourceGeneratedAt: "2026-07-10T00:02:00+00:00",
          applied: 1,
          skipped: 1,
          accepted: 1,
          rejected: 0,
          detailCount: 2,
        },
        {
          reportPath:
            "C:\\project\\render\\reports\\imports\\render-bundle-import-old.json",
          importedAt: "2026-07-10T00:01:00+00:00",
          manifestPath:
            "C:\\project\\render\\reports\\bundles\\bundle\\manifest.json",
          sourceBundlePath: "C:\\project\\render\\reports\\bundles\\bundle",
          sourceGeneratedAt: "2026-07-10T00:00:00+00:00",
          applied: 0,
          skipped: 2,
          accepted: 0,
          rejected: 0,
          detailCount: 2,
        },
      ],
    }),
  compareRenderBundleImportReports: (
    baseReportPath: string,
    compareReportPath: string,
  ) =>
    Promise.resolve({
      baseReport: {
        reportPath: baseReportPath,
        importedAt: "2026-07-10T00:01:00+00:00",
        manifestPath: null,
        sourceBundlePath: null,
        sourceGeneratedAt: null,
        applied: 0,
        skipped: 2,
        accepted: 0,
        rejected: 0,
        detailCount: 2,
      },
      compareReport: {
        reportPath: compareReportPath,
        importedAt: "2026-07-10T00:03:00+00:00",
        manifestPath: null,
        sourceBundlePath: null,
        sourceGeneratedAt: null,
        applied: 1,
        skipped: 1,
        accepted: 1,
        rejected: 0,
        detailCount: 2,
      },
      differenceCount: 3,
      differences: [
        {
          jobId: "job-pending",
          changeType: "changed",
          base: {
            jobId: "job-pending",
            status: "skipped",
            decision: "not_reviewed",
            reason: "Decision is not accepted or rejected.",
          },
          compare: {
            jobId: "job-pending",
            status: "skipped",
            decision: "rejected",
            reason: "Render job is not reviewable.",
          },
        },
        {
          jobId: "job-added",
          changeType: "added",
          base: null,
          compare: {
            jobId: "job-added",
            status: "applied",
            decision: "accepted",
            reason: null,
          },
        },
        {
          jobId: "job-removed",
          changeType: "removed",
          base: {
            jobId: "job-removed",
            status: "skipped",
            decision: "rejected",
            reason: "Render job was not found in this project.",
          },
          compare: null,
        },
      ],
    }),
  exportRenderBundleImportComparisonReport: (
    baseReportPath: string,
    compareReportPath: string,
    format: "csv" | "json",
    changeFilter: "all" | "changed" | "added" | "removed",
  ) =>
    Promise.resolve({
      format,
      reportPath: `C:\\project\\render\\reports\\import-comparisons\\render-import-comparison-${changeFilter}.${format}`,
      generatedAt: "2026-07-10T00:04:00+00:00",
      changeFilter,
      differenceCount: changeFilter === "all" ? 3 : 1,
      baseReport: { reportPath: baseReportPath },
      compareReport: { reportPath: compareReportPath },
    }),
  listRenderBundleImportComparisonReports: () =>
    Promise.resolve({
      reports: [
        {
          reportPath:
            "C:\\project\\render\\reports\\import-comparisons\\render-import-comparison-history.csv",
          format: "csv",
          generatedAt: "2026-07-10T00:04:00+00:00",
          changeFilter: "added",
          differenceCount: 1,
          baseReportPath: null,
          compareReportPath: null,
          pinned: false,
        },
      ],
    }),
  previewRenderBundleImportComparisonReport: (reportPath: string) =>
    Promise.resolve({
      report: {
        reportPath,
        format: "csv",
        generatedAt: "2026-07-10T00:04:00+00:00",
        changeFilter: "added",
        differenceCount: 1,
        baseReportPath: null,
        compareReportPath: null,
        pinned: false,
      },
      columns: [
        "jobId",
        "changeType",
        "baseStatus",
        "baseDecision",
        "baseReason",
        "compareStatus",
        "compareDecision",
        "compareReason",
      ],
      rows: [
        {
          jobId: "job-added",
          changeType: "added",
          baseStatus: "",
          baseDecision: "",
          baseReason: "",
          compareStatus: "applied",
          compareDecision: "accepted",
          compareReason: "",
        },
      ],
      totalRows: 1,
      truncated: false,
    }),
  pinRenderBundleImportComparisonReport: (
    reportPath: string,
    pinned: boolean,
  ) =>
    Promise.resolve({
      reportPath,
      pinned,
      pinnedCount: pinned ? 1 : 0,
    }),
}));

const passedPreflightReport = {
      ready: true,
      outputFileName: "rendered.mp4",
      durationMilliseconds: 3000,
      groups: [
        {
          group: "Tool",
          status: "passed",
          checks: [
            {
              code: "FFMPEG_AVAILABLE",
              message: "FFmpeg is available.",
              status: "passed",
            },
          ],
        },
        {
          group: "Timeline",
          status: "passed",
          checks: [
            {
              code: "TIMELINE_RENDERABLE",
              message: "Timeline duration and layers are renderable.",
              status: "passed",
            },
          ],
        },
        {
          group: "Media",
          status: "passed",
          checks: [
            {
              code: "MEDIA_ASSETS_AVAILABLE",
              message: "Timeline media assets are available in project cache.",
              status: "passed",
            },
          ],
        },
        {
          group: "Output",
          status: "passed",
          checks: [
            {
              code: "OUTPUT_WRITABLE",
              message: "Render output location is writable.",
              status: "passed",
            },
          ],
        },
      ],
    };

vi.mock("./services/desktopClient", () => ({
  openDesktopPath: vi.fn(),
  selectScriptFile: selectScriptFileMock,
}));

function renderJobFixture(overrides: Record<string, unknown> = {}) {
  return {
    jobId: "job-fixture",
    projectId: "project-1",
    fileName: "fixture.mp4",
    status: "completed",
    progressPercent: 100,
    processedMilliseconds: 3000,
    durationMilliseconds: 3000,
    outputPath: "C:\\project\\output\\fixture.mp4",
    sizeBytes: 2048,
    errorCode: null,
    errorMessage: null,
    exportSettings: {
      profileId: "standard",
      width: 1920,
      height: 1080,
      frameRate: 30,
      crf: 18,
      encoderPreset: "medium",
      audioBitrateKbps: 192,
    },
    outputNameTemplate: "{project}-{datetime}.mp4",
    diagnostics: null,
    preview: null,
    review: null,
    ...overrides,
  };
}

function mediaSearchPage(overrides: Record<string, unknown> = {}) {
  return {
    providerId: "all",
    query: "city skyline",
    totalResults: 1,
    offset: 0,
    limit: 24,
    truncated: false,
    providerErrors: [],
    deduplication: {
      totalCandidates: 1,
      retainedItems: 1,
      fingerprintedCandidates: 0,
      canonicalDuplicates: 0,
      perceptualImageDuplicates: 0,
      perceptualVideoDuplicates: 0,
      imageHammingThreshold: 8,
      videoAverageHammingThreshold: 8,
    },
    items: [
      {
        id: "pexels-photo-1",
        providerId: "pexels",
        mediaType: "image",
        title: "City skyline at sunrise",
        sourceUri: "https://images.pexels.com/photos/1/original.jpg",
        previewUri: "https://images.pexels.com/photos/1/preview.jpg",
        fileSizeBytes: 4096,
        modifiedAt: null,
        score: 1,
        license: "Pexels License",
        sourcePageUri: "https://www.pexels.com/photo/1",
        creator: "Pexels contributor",
        creatorUri: null,
      },
    ],
    ...overrides,
  };
}

describe("App", () => {
  beforeEach(() => {
    useAppStore.setState({ healthState: { status: "loading" } });
    projectClientState.currentProject = {
      id: "project-1",
      name: "Demo Project",
      path: "C:\\project",
      createdAt: "2026-07-11T00:00:00Z",
      updatedAt: "2026-07-11T00:00:00Z",
      schemaVersion: 1,
    };
    projectClientState.recentProjects = [projectClientState.currentProject];
    scriptClientState.collection = {
      schemaVersion: 1,
      sceneCount: 1,
      updatedAt: "2026-07-11T00:00:00Z",
      scenes: [
        {
          id: "scene-1",
          order: 1,
          text: "Opening subtitle",
          startMilliseconds: 0,
          endMilliseconds: 3000,
        },
      ],
    };
    aiClientState.analyses = [
      {
        sceneId: "scene-1",
        sourceTextHash: "c".repeat(64),
        description: "A city skyline establishing shot for the opening scene.",
        category: "news",
        keywords: ["city skyline", "urban sunrise"],
        providerId: "ollama",
        model: "llama3.2",
        promptVersion: 1,
        analyzedAt: "2026-07-12T00:00:00Z",
      },
    ];
    mediaClientState.assets = [
      {
        contentHash: "a".repeat(64),
        mediaType: "image",
        fileName: "cached.jpg",
        uri: "file:///cache/cached.jpg",
        sizeBytes: 1024,
        providerIds: ["pexels"],
        durationMilliseconds: null,
      },
    ];
    mediaClientState.manifest = {
      schemaVersion: 1,
      totalSizeBytes: 1024,
      entries: [
        {
          contentHash: "a".repeat(64),
          relativePath: "aa/cached.jpg",
          sizeBytes: 1024,
          durationMilliseconds: null,
        },
      ],
    };
    mediaClientState.fingerprintBackfillJob = {
      jobId: "fingerprint-job-1",
      projectId: "project-1",
      status: "completed",
      totalMedia: 1,
      processedMedia: 1,
      progressPercent: 100,
      updatedMedia: 0,
      skippedMedia: 1,
      failedCount: 0,
      failedContentHashes: [],
      errorMessage: null,
    };
    timelineClientState.timeline = {
      schemaVersion: 2,
      id: "timeline-1",
      createdAt: "2026-07-02T00:00:00Z",
      updatedAt: "2026-07-02T00:00:00Z",
      durationMilliseconds: 3000,
      audioClips: [],
      scenes: [
        {
          sceneId: "scene-1",
          order: 1,
          startMilliseconds: 0,
          endMilliseconds: 3000,
          mediaClips: [] as Array<
            Record<string, unknown> & { role: "broll" | "avatar" }
          >,
          subtitleClips: [
            {
              id: "subtitle-scene-1",
              text: "Opening subtitle",
              startMilliseconds: 0,
              endMilliseconds: 3000,
              layer: 0,
            },
          ],
        },
      ],
    };
    renderPreflightMock.mockResolvedValue(passedPreflightReport);
    renderJobsMock.mockReturnValue([]);
    mediaSearchMock.mockResolvedValue(mediaSearchPage());
    mediaSearchMock.mockClear();
    clipboardWriteTextMock.mockClear();
    createObjectUrlMock.mockClear();
    revokeObjectUrlMock.mockClear();
    anchorClickMock.mockClear();
    printMock.mockClear();
    selectScriptFileMock.mockResolvedValue("D:\\Scripts\\episode.srt");
    selectScriptFileMock.mockClear();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: clipboardWriteTextMock },
    });
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectUrlMock,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrlMock,
    });
    Object.defineProperty(HTMLAnchorElement.prototype, "click", {
      configurable: true,
      value: anchorClickMock,
    });
    Object.defineProperty(window, "print", {
      configurable: true,
      value: printMock,
    });
  });

  it("renders the production dashboard and backend status", async () => {
    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Production dashboard" })).toBeInTheDocument();
    expect((await screen.findAllByText("Demo Project")).length).toBeGreaterThan(0);
    expect(screen.getByText("5 / 6 ready")).toBeInTheDocument();
    expect(screen.getAllByText("AI").length).toBeGreaterThan(0);
    expect(screen.getByText("No completed MP4 output yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Run preflight, choose an export profile, and start render."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Continue: Render/ })).toHaveAttribute(
      "href",
      "/render",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveClass("active");
    expect(
      await screen.findByText("AI Video Pipeline Studio: ok"),
    ).toBeInTheDocument();
  });

  it("shows workflow error guidance for a failed render job", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "failed-render",
        fileName: "failed.mp4",
        status: "failed",
        outputPath: null,
        errorCode: "RENDER_FAILED",
        errorMessage: "FFmpeg exited before producing output.",
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("FFmpeg exited before producing output."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Open Render, review diagnostics, fix preflight issues, then retry."),
    ).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows dashboard output review actions after completed renders", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "accepted-output",
        fileName: "accepted.mp4",
        review: {
          status: "accepted",
          note: "Approved",
          reviewedAt: "2026-07-10T00:01:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "rejected-output",
        fileName: "rejected.mp4",
        review: {
          status: "rejected",
          note: "Needs fix",
          reviewedAt: "2026-07-10T00:02:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "pending-output",
        fileName: "pending-review.mp4",
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("pending-review.mp4")).toBeInTheDocument();
    expect(screen.getByText("Completed and ready to review")).toBeInTheDocument();
    expect(screen.getByText("Newest output")).toBeInTheDocument();
    expect(screen.getByText("Latest review: Not reviewed")).toBeInTheDocument();
    expect(screen.getByText("Accepted 1")).toBeInTheDocument();
    expect(screen.getByText("Rejected 1")).toBeInTheDocument();
    expect(screen.getByText("Not reviewed 1")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Review output queue" }),
    ).toHaveAttribute("href", "/render?reviewJob=pending-output#render-queue");
  });

  it("shows dashboard completion actions when every output is reviewed", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "accepted-output",
        fileName: "accepted.mp4",
        review: {
          status: "accepted",
          note: "Approved",
          reviewedAt: "2026-07-10T00:01:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "rejected-output",
        fileName: "rejected.mp4",
        review: {
          status: "rejected",
          note: "Needs fix",
          reviewedAt: "2026-07-10T00:02:00+00:00",
        },
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("rejected.mp4")).toBeInTheDocument();
    expect(screen.getByText("All 2 outputs reviewed")).toBeInTheDocument();
    expect(screen.getByText("All outputs reviewed")).toBeInTheDocument();
    expect(
      screen.getByText("Ready for handoff report or the next render pass."),
    ).toBeInTheDocument();
    expect(screen.getByText("Latest review: Rejected")).toBeInTheDocument();
    expect(screen.getByText("Not reviewed 0")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Export review report" })).toHaveAttribute(
      "href",
      "/render#render-queue",
    );
    expect(screen.getByRole("link", { name: "Start next render" })).toHaveAttribute(
      "href",
      "/render",
    );
  });

  it("walks the final workflow handoff from script to review dashboard", async () => {
    render(
      <MemoryRouter initialEntries={["/pipeline"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Import and edit scenes" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: /Next: AI analysis/ }));
    expect(await screen.findByRole("heading", { name: "Analyze scenes and prepare media keywords" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: /Next: Media search/ }));
    expect(await screen.findByRole("heading", { name: "Search, download, and assign media" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: /Next: Timeline/ }));
    expect(await screen.findByRole("heading", { name: "Scene assembly" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: /Next: Render/ }));
    expect(await screen.findByRole("heading", { name: "MP4 render" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Review dashboard" }));
    expect(await screen.findByRole("heading", { name: "Production dashboard" })).toBeInTheDocument();
  });

  it("shows dashboard active render progress and handoff", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "running-render",
        fileName: "running-output.mp4",
        status: "running",
        progressPercent: 42.5,
        processedMilliseconds: 1275,
        durationMilliseconds: 3000,
        outputPath: null,
        sizeBytes: null,
        review: null,
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("running-output.mp4")).toBeInTheDocument();
    expect(screen.getByText("Rendering 42.5%")).toBeInTheDocument();
    expect(screen.getByLabelText("Active render progress")).toHaveAttribute(
      "value",
      "42.5",
    );
    expect(
      screen.getAllByText("Open Render to monitor progress or cancel the active job.")
        .length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Monitor render")[0]).toHaveAttribute(
      "href",
      "/render#render-monitor",
    );
  });

  it("shows dashboard subtitle preparation progress", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "preparing-render",
        fileName: "subtitle-prep.mp4",
        status: "preparing",
        progressPercent: 1,
        processedMilliseconds: 0,
        durationMilliseconds: 3000,
        outputPath: null,
        sizeBytes: null,
        review: null,
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("subtitle-prep.mp4")).toBeInTheDocument();
    expect(screen.getByText("Preparing subtitles")).toBeInTheDocument();
    expect(screen.getByLabelText("Active render progress")).toHaveAttribute(
      "value",
      "1",
    );
  });

  it("manages projects from the dashboard", async () => {
    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Project manager")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "Created Project" },
    });
    fireEvent.change(screen.getByLabelText("Parent folder"), {
      target: { value: "D:\\Projects\\Videos" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(
      await screen.findByText("Project created: Created Project"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Created Project").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Close project" }));
    expect(
      await screen.findByText("Project closed: Created Project"),
    ).toBeInTheDocument();
    expect(screen.getByText("No project open")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Open" })[0]);
    expect(
      await screen.findByText("Project opened: Created Project"),
    ).toBeInTheDocument();
  });

  it("searches, downloads, and assigns media from the media workspace", async () => {
    render(
      <MemoryRouter initialEntries={["/media"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Search, download, and assign media",
      }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Duplicate check ready" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Media" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: /Next: Timeline/ })).toHaveAttribute(
      "href",
      "/timeline",
    );
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("City skyline at sunrise")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    expect(await screen.findByText("Media downloaded to cache.")).toBeInTheDocument();
    expect(await screen.findByText(/Download complete/)).toBeInTheDocument();
    expect(await screen.findByText("downloaded.jpg")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Assign to scene" }));
    expect(await screen.findByText("B-roll assigned to scene.")).toBeInTheDocument();
    expect(
      await screen.findByText("AI Video Pipeline Studio: ok"),
    ).toBeInTheDocument();
  });

  it("shows provider partial results while another provider is still pending", async () => {
    let rejectPixabay: (error: Error) => void = () => undefined;
    const pixabaySearch = new Promise((_, reject) => {
      rejectPixabay = reject;
    });
    mediaSearchMock.mockImplementation((options: { providerId: string }) => {
      if (options.providerId === "pexels") {
        return Promise.resolve(mediaSearchPage({ providerId: "pexels" }));
      }
      if (options.providerId === "pixabay") {
        return pixabaySearch;
      }
      return Promise.resolve(
        mediaSearchPage({
          providerId: options.providerId,
          totalResults: 0,
          items: [],
        }),
      );
    });

    render(
      <MemoryRouter initialEntries={["/media"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Search" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("City skyline at sunrise")).toBeInTheDocument();
    expect(screen.getByText("pixabay: searching")).toBeInTheDocument();

    rejectPixabay(new Error("Pixabay rate limit was exceeded."));

    expect(
      await screen.findAllByText("pixabay: Pixabay rate limit was exceeded."),
    ).toHaveLength(2);
    expect(screen.getByText("City skyline at sunrise")).toBeInTheDocument();
  });

  it("runs AI scene analysis and sends keywords into media search", async () => {
    render(
      <MemoryRouter initialEntries={["/analysis"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Analyze scenes and prepare media keywords",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "AI" })).toHaveClass("active");
    expect(
      screen.getByRole("link", { name: /Next: Media search/ }),
    ).toHaveAttribute("href", "/media");
    expect(
      await screen.findByText(
        "A city skyline establishing shot for the opening scene.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("news").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "city skyline" })).toHaveAttribute(
      "href",
      "/media?query=city%20skyline",
    );

    fireEvent.click(screen.getByRole("button", { name: "Analyze all" }));

    expect(
      await screen.findByText("Analyzed 1 scenes, skipped 0, failed 0."),
    ).toBeInTheDocument();
    expect((await screen.findAllByText("documentary")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("link", { name: "city skyline" }));

    expect(
      await screen.findByRole("heading", {
        name: "Search, download, and assign media",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Search keywords")).toHaveValue("city skyline");
  });

  it("shows setup status and provider configuration hints", async () => {
    mediaClientState.fingerprintBackfillJob = {
      jobId: "fingerprint-job-running",
      projectId: "project-1",
      status: "running",
      totalMedia: 12,
      processedMedia: 5,
      progressPercent: 42,
      updatedMedia: 4,
      skippedMedia: 1,
      failedCount: 0,
      failedContentHashes: [],
      errorMessage: null,
    };

    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Setup providers and runtime checks",
      }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Duplicate check 42%" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toHaveClass("active");
    expect(await screen.findByText("Ollama is ready with llama3.2.")).toBeInTheDocument();
    expect(screen.getAllByText("OPENAI_API_KEY").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "Set OPENAI_API_KEY in the environment, restart the desktop app, then refresh setup.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("imports a script and edits scenes in the pipeline workspace", async () => {
    render(
      <MemoryRouter initialEntries={["/pipeline"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Import and edit scenes" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pipeline" })).toHaveClass("active");
    expect(
      screen.getByRole("link", { name: /Next: AI analysis/ }),
    ).toHaveAttribute("href", "/analysis");
    expect(await screen.findByDisplayValue("Opening subtitle")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Choose file" }));
    expect(selectScriptFileMock).toHaveBeenCalled();
    expect(await screen.findByText("Script file selected.")).toBeInTheDocument();
    expect(screen.getByLabelText("TXT or SRT file path")).toHaveValue(
      "D:\\Scripts\\episode.srt",
    );
    fireEvent.click(screen.getByRole("button", { name: "Import script" }));

    expect(await screen.findByText("Imported 2 SRT scenes.")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("Imported opening")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Scene 2/ }));
    expect(await screen.findByDisplayValue("Imported closing")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Scene text"), {
      target: { value: "Edited imported closing" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save scene" }));

    expect(await screen.findByText("Scene 2 saved.")).toBeInTheDocument();
    expect(
      await screen.findByDisplayValue("Edited imported closing"),
    ).toBeInTheDocument();
  });

  it("renders the timeline editor and scene data", async () => {
    render(
      <MemoryRouter initialEntries={["/timeline"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Scene assembly" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Timeline" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: /Next: Render/ })).toHaveAttribute(
      "href",
      "/render",
    );
    expect((await screen.findAllByText("Opening subtitle")).length).toBe(2);
    expect(
      (await screen.findAllByRole("option", { name: /cached\.jpg/ })).length,
    ).toBe(2);
  });

  it("shows guided empty states for missing workflow data", async () => {
    scriptClientState.collection = {
      schemaVersion: 1,
      sceneCount: 0,
      updatedAt: "2026-07-12T00:00:00Z",
      scenes: [],
    };
    aiClientState.analyses = [];

    const { unmount } = render(
      <MemoryRouter initialEntries={["/analysis"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Import scenes before AI analysis"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Go to Script/ })).toHaveAttribute(
      "href",
      "/pipeline",
    );

    unmount();
    mediaClientState.assets = [];
    mediaClientState.manifest = {
      schemaVersion: 1,
      totalSizeBytes: 0,
      entries: [],
    };
    timelineClientState.timeline = null as unknown as typeof timelineClientState.timeline;

    const mediaView = render(
      <MemoryRouter initialEntries={["/media"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Timeline needed for assignment")).toBeInTheDocument();
    expect(screen.getByText("No cached media yet")).toBeInTheDocument();

    mediaView.unmount();
    render(
      <MemoryRouter initialEntries={["/timeline"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Generate timeline from scenes")).toBeInTheDocument();
  });

  it("renders the render workspace", async () => {
    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "MP4 render" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Render" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: /Review dashboard/ })).toHaveAttribute(
      "href",
      "/projects",
    );
    expect(screen.getByRole("button", { name: /Render MP4/ })).toBeInTheDocument();
    expect(await screen.findByText("Preflight")).toBeInTheDocument();
  });

  it("shows guided render preflight actions", async () => {
    renderPreflightMock.mockResolvedValueOnce({
      ...passedPreflightReport,
      ready: false,
      groups: passedPreflightReport.groups.map((group) =>
        group.group === "Media"
          ? {
              ...group,
              status: "failed",
              checks: [
                {
                  code: "MEDIA_MISSING",
                  message: "Timeline media asset is missing from cache.",
                  status: "failed",
                },
              ],
            }
          : group,
      ),
    });

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Media needs attention")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open Media/ })).toHaveAttribute(
      "href",
      "/media",
    );
  });

  it("suggests Fast Preview for long render timelines without changing automatically", async () => {
    renderPreflightMock.mockResolvedValue({
      ...passedPreflightReport,
      durationMilliseconds: 120_000,
    });

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Long timeline detected")).toBeInTheDocument();
    const profileSelect = screen.getByLabelText("Profile") as HTMLSelectElement;
    expect(profileSelect.value).toBe("standard");

    fireEvent.click(screen.getByRole("button", { name: "Use Fast Preview" }));

    expect(profileSelect.value).toBe("fast_preview");
    expect(screen.getByLabelText("Resolution")).toHaveValue("640x360");
    expect(screen.getByLabelText("FPS")).toHaveValue("15");
  });

  it("shows render output preview after a completed job", async () => {
    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /Render MP4/ }));

    expect(await screen.findByLabelText("Rendered MP4 playback")).toHaveAttribute(
      "src",
      "file:///C:/project/output/rendered.mp4",
    );
    expect(await screen.findByAltText("Render preview thumbnail")).toBeInTheDocument();
    expect(
      await screen.findByText("1920x1080, 30 FPS, 0:03, 2.0 KB"),
    ).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Review notes"), {
      target: { value: "Looks ready." },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }));

    expect((await screen.findAllByText("Accepted")).length).toBeGreaterThan(0);
    expect(await screen.findByDisplayValue("Looks ready.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Return to Dashboard" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Revert review" }));

    expect((await screen.findAllByText("Not reviewed")).length).toBeGreaterThan(0);
  });

  it("returns to the dashboard after a reviewed render output", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "accepted-return",
        fileName: "accepted-return.mp4",
        review: {
          status: "accepted",
          note: "Approved",
          reviewedAt: "2026-07-10T00:01:00+00:00",
        },
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/render?reviewJob=accepted-return#render-queue"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Return to Dashboard" }));

    expect(await screen.findByText("Production dashboard")).toBeInTheDocument();
    expect(await screen.findByText("accepted-return.mp4")).toBeInTheDocument();
    expect(screen.getByText("Latest review: Accepted")).toBeInTheDocument();
  });

  it("opens the requested render job for dashboard review handoff", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "target-review",
        fileName: "target-review.mp4",
        outputPath: "C:\\project\\output\\target-review.mp4",
      }),
      renderJobFixture({
        jobId: "later-output",
        fileName: "later-output.mp4",
        outputPath: "C:\\project\\output\\later-output.mp4",
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/render?reviewJob=target-review#render-queue"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Ready to review target-review.mp4"),
    ).toBeInTheDocument();
    expect(await screen.findByText("C:\\project\\output\\target-review.mp4")).toBeInTheDocument();
  });

  it("filters render queue by review status", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "accepted-job",
        fileName: "accepted.mp4",
        review: {
          status: "accepted",
          note: "Approved",
          reviewedAt: "2026-07-10T00:01:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "rejected-job",
        fileName: "rejected.mp4",
        review: {
          status: "rejected",
          note: "Needs fix",
          reviewedAt: "2026-07-10T00:02:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "not-reviewed-job",
        fileName: "not-reviewed.mp4",
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("accepted.mp4")).toBeInTheDocument();
    expect(screen.getByText("rejected.mp4")).toBeInTheDocument();
    expect(screen.getByText("not-reviewed.mp4")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Accepted 1/ }));
    expect(screen.getByText("accepted.mp4")).toBeInTheDocument();
    expect(screen.queryByText("rejected.mp4")).not.toBeInTheDocument();
    expect(screen.queryByText("not-reviewed.mp4")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Rejected 1/ }));
    expect(screen.queryByText("accepted.mp4")).not.toBeInTheDocument();
    expect(screen.getByText("rejected.mp4")).toBeInTheDocument();
    expect(screen.queryByText("not-reviewed.mp4")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Not reviewed 1/ }));
    expect(screen.queryByText("accepted.mp4")).not.toBeInTheDocument();
    expect(screen.queryByText("rejected.mp4")).not.toBeInTheDocument();
    expect(screen.getByText("not-reviewed.mp4")).toBeInTheDocument();
  });

  it("sorts the render queue and bulk reviews visible outputs", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "accepted-job",
        fileName: "accepted.mp4",
        review: {
          status: "accepted",
          note: "Approved",
          reviewedAt: "2026-07-10T00:01:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "rejected-job",
        fileName: "rejected.mp4",
        review: {
          status: "rejected",
          note: "Needs fix",
          reviewedAt: "2026-07-10T00:02:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "not-reviewed-job",
        fileName: "not-reviewed.mp4",
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("not-reviewed.mp4")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Sort"), {
      target: { value: "oldest" },
    });
    const queueButtons = screen
      .getAllByRole("button")
      .filter((button) => button.textContent?.includes(".mp4"));
    expect(queueButtons[0]).toHaveTextContent("accepted.mp4");

    fireEvent.click(screen.getByRole("button", { name: /Not reviewed 1/ }));
    fireEvent.click(screen.getByRole("button", { name: "Select visible" }));
    fireEvent.click(screen.getByRole("button", { name: "Accept selected" }));

    expect(await screen.findByText("No render jobs match this queue view.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Accepted 2/ }));
    expect(await screen.findByText("not-reviewed.mp4")).toBeInTheDocument();
    expect((await screen.findAllByText("Accepted")).length).toBeGreaterThan(0);
  });

  it("bulk reverts reviewed render outputs", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "accepted-job",
        fileName: "accepted.mp4",
        review: {
          status: "accepted",
          note: "Approved",
          reviewedAt: "2026-07-10T00:01:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "rejected-job",
        fileName: "rejected.mp4",
        review: {
          status: "rejected",
          note: "Needs fix",
          reviewedAt: "2026-07-10T00:02:00+00:00",
        },
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("accepted.mp4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Select visible" }));
    fireEvent.click(screen.getByRole("button", { name: "Revert selected" }));

    expect(await screen.findByText("2 render reviews reverted.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Not reviewed 2/ }));
    expect(await screen.findByText("accepted.mp4")).toBeInTheDocument();
    expect(screen.getByText("rejected.mp4")).toBeInTheDocument();
  });

  it("exports a render queue report for handoff", async () => {
    renderJobsMock.mockReturnValue([
      renderJobFixture({
        jobId: "accepted-job",
        fileName: "accepted.mp4",
        review: {
          status: "accepted",
          note: "Approved",
          reviewedAt: "2026-07-10T00:01:00+00:00",
        },
      }),
      renderJobFixture({
        jobId: "not-reviewed-job",
        fileName: "not-reviewed.mp4",
      }),
    ]);

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Accepted outputs")).toBeInTheDocument();
    expect(screen.getByText("Not reviewed outputs")).toBeInTheDocument();
    expect(screen.getByText("Completed jobs")).toBeInTheDocument();
    expect(screen.getByText("Failed jobs")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Review"), {
      target: { value: "accepted" },
    });
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "completed" },
    });
    fireEvent.change(screen.getByLabelText("From"), {
      target: { value: "2026-07-10" },
    });
    fireEvent.change(screen.getByLabelText("To"), {
      target: { value: "2026-07-10" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    expect(
      await screen.findByText("Render queue CSV report exported with 2 jobs."),
    ).toBeInTheDocument();
    expect(screen.getByText("CSV · 2 jobs")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Last export: Review Accepted, Status Completed, Date 2026-07-10 to 2026-07-10",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open report" })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Copy path" })).not.toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Copy path" }));

    expect(clipboardWriteTextMock).toHaveBeenCalledWith(
      "C:\\project\\render\\reports\\render-queue-report.csv",
    );
    expect(await screen.findByText("Render report path copied.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create bundle" }));

    expect(
      await screen.findByText(
        "Render handoff bundle created with 2 jobs and 1 thumbnails.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Bundle: 2 jobs, 1 thumbnails, zip ready"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Manifest path")).toHaveValue(
      "C:\\project\\render\\reports\\bundles\\bundle\\manifest.json",
    );
    expect(screen.getByRole("button", { name: "Open bundle" })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Open zip" })).not.toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Import reviews" }),
    ).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Import reviews" }));
    expect(
      await screen.findByText(
        "Imported 1 render reviews (1 accepted, 0 rejected).",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Review import: 1 applied, 1 skipped")).toBeInTheDocument();
    expect(screen.getByText("Import diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Import audit history")).toBeInTheDocument();
    expect(screen.getByText("2 reports")).toBeInTheDocument();
    expect(
      screen.getAllByText(
        "C:\\project\\render\\reports\\imports\\render-bundle-import.json",
      ).length,
    ).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Compare reports" }));
    expect(
      await screen.findByText("Compared import reports: 3 differences."),
    ).toBeInTheDocument();
    expect(screen.getByText("Comparison: 3 differences")).toBeInTheDocument();
    expect(screen.getAllByText("job-pending").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Changed").length).toBeGreaterThan(0);
    expect(screen.getByText("Comparison report history")).toBeInTheDocument();
    expect(
      screen.getByText(
        "C:\\project\\render\\reports\\import-comparisons\\render-import-comparison-history.csv",
      ),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search reports"), {
      target: { value: "history" },
    });
    expect(screen.getByText("1 / 1 reports")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Format"), {
      target: { value: "json" },
    });
    expect(
      screen.getByText("No comparison reports match this view."),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Format"), {
      target: { value: "csv" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("Preview CSV")).toBeInTheDocument();
    expect(screen.getAllByText("job-added").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Copy preview CSV" }));
    expect(clipboardWriteTextMock).toHaveBeenLastCalledWith(
      'jobId,changeType,baseStatus,baseDecision,baseReason,compareStatus,compareDecision,compareReason\n"job-added","added","","","","applied","accepted",""',
    );
    expect(
      await screen.findByText("Comparison preview CSV copied."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Download preview CSV" }));
    expect(anchorClickMock).toHaveBeenCalled();
    expect(
      await screen.findByText("Comparison preview CSV downloaded."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Print preview" }));
    expect(printMock).toHaveBeenCalled();
    expect(
      await screen.findByText("Comparison preview sent to print."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Pinned only"));
    expect(
      screen.getByText("No comparison reports match this view."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Pinned only"));
    fireEvent.click(screen.getByRole("button", { name: "Pin" }));
    expect(
      await screen.findByText("Comparison report pinned."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Status Skipped, Decision Rejected, Reason Render job is not reviewable.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("job-added").length).toBeGreaterThan(0);
    expect(screen.getByText("job-removed")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Difference filter"), {
      target: { value: "added" },
    });
    expect(screen.getByText("1 visible")).toBeInTheDocument();
    expect(screen.getAllByText("job-added").length).toBeGreaterThan(0);
    expect(screen.queryByText("job-removed")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Export diff CSV" }));
    expect(
      await screen.findByText(
        "Saved 1 added comparison differences as CSV.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Saved CSV report")).toBeInTheDocument();
    expect(
      screen.getByText(
        "C:\\project\\render\\reports\\import-comparisons\\render-import-comparison-added.csv",
      ),
    ).toBeInTheDocument();
    const copyReportButtons = screen.getAllByRole("button", {
      name: "Copy report",
    });
    fireEvent.click(copyReportButtons[copyReportButtons.length - 2]);
    expect(clipboardWriteTextMock).toHaveBeenLastCalledWith(
      "C:\\project\\render\\reports\\import-comparisons\\render-import-comparison-added.csv",
    );
    expect(
      await screen.findByText("Render import comparison report path copied."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Export diff JSON" }));
    expect(
      await screen.findByText(
        "Saved 1 added comparison differences as JSON.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Saved JSON report")).toBeInTheDocument();
    expect(screen.getByLabelText("Import diagnostics filter")).toHaveValue(
      "skipped",
    );
    expect(screen.getAllByText("job-pending").length).toBeGreaterThan(0);
    expect(
      screen.getByText("Decision is not accepted or rejected."),
    ).toBeInTheDocument();
    expect(screen.queryByText("job-completed")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Import diagnostics filter"), {
      target: { value: "all" },
    });
    expect(screen.getByText("job-completed")).toBeInTheDocument();
    expect(screen.getByText("Applied to render history.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy skipped" }));
    expect(clipboardWriteTextMock).toHaveBeenLastCalledWith(
      'jobId,status,decision,reason\n"job-pending","skipped","not_reviewed","Decision is not accepted or rejected."',
    );
    expect(
      await screen.findByText("Copied 1 skipped import diagnostics."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy import report" }));
    expect(clipboardWriteTextMock).toHaveBeenLastCalledWith(
      "C:\\project\\render\\reports\\imports\\render-bundle-import.json",
    );
    expect(
      await screen.findByText("Render import diagnostics report path copied."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Copy report" })[0]);
    expect(clipboardWriteTextMock).toHaveBeenLastCalledWith(
      "C:\\project\\render\\reports\\imports\\render-bundle-import.json",
    );
    expect(
      await screen.findByText("Render import history report path copied."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy bundle path" }));
    expect(clipboardWriteTextMock).toHaveBeenCalledWith(
      "C:\\project\\render\\reports\\bundles\\bundle",
    );
    expect(
      await screen.findByText("Render handoff bundle path copied."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy zip path" }));
    expect(clipboardWriteTextMock).toHaveBeenCalledWith(
      "C:\\project\\render\\reports\\bundles\\bundle.zip",
    );
    expect(
      await screen.findByText("Render handoff bundle zip path copied."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));

    expect(await screen.findByText("Render report filters reset.")).toBeInTheDocument();
    expect(screen.getByLabelText("Review")).toHaveValue("all");
    expect(screen.getByLabelText("Status")).toHaveValue("all");
    expect(screen.getByLabelText("From")).toHaveValue("");
    expect(screen.getByLabelText("To")).toHaveValue("");
  }, 10000);

  it("searches and paginates the render queue", async () => {
    renderJobsMock.mockReturnValue(
      Array.from({ length: 12 }, (_, index) =>
        renderJobFixture({
          jobId: `batch-${index + 1}`,
          fileName: `batch-${String(index + 1).padStart(2, "0")}.mp4`,
        }),
      ),
    );

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("batch-12.mp4")).toBeInTheDocument();
    expect(screen.getByText("Showing 1-10 of 12")).toBeInTheDocument();
    expect(screen.queryByText("batch-02.mp4")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("batch-02.mp4")).toBeInTheDocument();
    expect(screen.getByText("Showing 11-12 of 12")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search"), {
      target: { value: "batch-01" },
    });
    expect(await screen.findByText("batch-01.mp4")).toBeInTheDocument();
    expect(screen.getByText("Showing 1-1 of 1")).toBeInTheDocument();
    expect(screen.queryByText("batch-12.mp4")).not.toBeInTheDocument();
  });

  it("shows a tool setup action from render preflight", async () => {
    renderPreflightMock.mockResolvedValueOnce({
      ...passedPreflightReport,
      ready: false,
      groups: passedPreflightReport.groups.map((group) =>
        group.group === "Tool"
          ? {
              ...group,
              status: "failed",
              checks: [
                {
                  code: "FFPROBE_NOT_FOUND",
                  message: "FFprobe is not configured.",
                  status: "failed",
                },
              ],
            }
          : group,
      ),
    });

    render(
      <MemoryRouter initialEntries={["/render"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Setup hint" }));

    expect(await screen.findByText("Tool setup")).toBeInTheDocument();
  });
});
