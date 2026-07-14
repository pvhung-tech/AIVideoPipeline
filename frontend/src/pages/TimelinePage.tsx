import { CircleStop, Clock3, DatabaseBackup, Music2, RefreshCw, Save, WandSparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { TimelineMediaPicker } from "../components/TimelineMediaPicker";
import { WorkflowHandoff } from "../components/WorkflowHandoff";
import { WorkspaceGuide } from "../components/WorkspaceGuide";
import {
  assignTimelineMedia,
  assignTimelineMusic,
  backfillVideoMetadata,
  cancelVideoMetadataBackfill,
  generateTimeline,
  getTimeline,
  getTimelineMediaAssets,
  getVideoMetadataBackfillStatus,
  saveTimeline,
  type Timeline,
  TimelineApiError,
  type TimelineMediaAsset,
  type MetadataBackfillJob,
  type TimelineScene,
  type VisualClipRole,
  trimTimelineVideo,
} from "../services/timelineClient";

type LoadState = "loading" | "ready" | "empty" | "error";

export function TimelinePage() {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState("Loading timeline...");
  const [isSaving, setIsSaving] = useState(false);
  const [assets, setAssets] = useState<TimelineMediaAsset[]>([]);
  const [isAssigningMedia, setIsAssigningMedia] = useState(false);
  const [backfillJob, setBackfillJob] = useState<MetadataBackfillJob | null>(null);
  const selectedScene = useMemo(
    () =>
      timeline?.scenes.find((scene) => scene.sceneId === selectedSceneId) ?? null,
    [selectedSceneId, timeline],
  );
  const visualAssets = useMemo(
    () => assets.filter((asset) => asset.mediaType !== "audio"),
    [assets],
  );
  const musicAssets = useMemo(
    () => assets.filter((asset) => asset.mediaType === "audio" && asset.providerIds.includes("local")),
    [assets],
  );

  useEffect(() => {
    void loadTimeline();
    void loadMediaAssets();
    void refreshBackfillStatus();
  }, []);

  useEffect(() => {
    if (!backfillJob || !["queued", "running"].includes(backfillJob.status)) return;
    const timer = window.setInterval(() => void refreshBackfillStatus(), 750);
    return () => window.clearInterval(timer);
  }, [backfillJob?.jobId, backfillJob?.status]);

  async function loadMediaAssets() {
    try {
      setAssets(await getTimelineMediaAssets());
    } catch {
      setAssets([]);
    }
  }

  async function handleMetadataBackfill() {
    try {
      const job = await backfillVideoMetadata();
      setBackfillJob(job);
      setMessage("Video metadata backfill started");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Metadata backfill failed");
    }
  }

  async function refreshBackfillStatus() {
    try {
      const job = await getVideoMetadataBackfillStatus();
      setBackfillJob(job);
      if (job && ["completed", "cancelled", "failed"].includes(job.status)) {
        await loadMediaAssets();
        setMessage(`Metadata backfill ${job.status}: ${job.updatedVideos} updated; ${job.failedCount} failed`);
      }
    } catch {
      setBackfillJob(null);
    }
  }

  async function handleCancelBackfill() {
    try {
      setBackfillJob(await cancelVideoMetadataBackfill());
      setMessage("Cancelling metadata backfill...");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Backfill cancellation failed");
    }
  }

  async function loadTimeline() {
    setLoadState("loading");
    try {
      acceptTimeline(await getTimeline());
      setMessage("Timeline loaded");
    } catch (error: unknown) {
      if (
        error instanceof TimelineApiError &&
        error.code === "TIMELINE_NOT_FOUND"
      ) {
        setLoadState("empty");
        setMessage("Generate a timeline from imported scenes to begin.");
      } else {
        setLoadState("error");
        setMessage(error instanceof Error ? error.message : "Timeline unavailable");
      }
    }
  }

  async function handleGenerate() {
    setLoadState("loading");
    setMessage("Building timeline from scenes...");
    try {
      acceptTimeline(await generateTimeline());
      setMessage("Initial timeline generated");
    } catch (error: unknown) {
      setLoadState("error");
      setMessage(
        error instanceof Error ? error.message : "Timeline generation failed",
      );
    }
  }

  async function handleSave() {
    if (!timeline) return;
    setIsSaving(true);
    try {
      const updated = { ...timeline, updatedAt: new Date().toISOString() };
      acceptTimeline(await saveTimeline(updated));
      setMessage("All timeline changes saved");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Timeline save failed");
    } finally {
      setIsSaving(false);
    }
  }

  function acceptTimeline(nextTimeline: Timeline) {
    setTimeline(nextTimeline);
    setSelectedSceneId((current) =>
      nextTimeline.scenes.some((scene) => scene.sceneId === current)
        ? current
        : (nextTimeline.scenes[0]?.sceneId ?? null),
    );
    setLoadState("ready");
  }

  function updateDuration(durationSeconds: number) {
    if (!timeline || !selectedScene || !Number.isFinite(durationSeconds)) return;
    const requestedDuration = Math.round(durationSeconds * 1_000);
    setTimeline(
      reflowTimeline(
        timeline,
        selectedScene.sceneId,
        Math.max(requestedDuration, getMinimumDuration(selectedScene)),
      ),
    );
  }

  function updateSubtitle(text: string) {
    if (!timeline || !selectedScene) return;
    setTimeline({
      ...timeline,
      scenes: timeline.scenes.map((scene) =>
        scene.sceneId === selectedScene.sceneId
          ? {
              ...scene,
              subtitleClips: scene.subtitleClips.map((clip, index) =>
                index === 0 ? { ...clip, text } : clip,
              ),
            }
          : scene,
      ),
    });
  }

  async function updateVisualMedia(role: VisualClipRole, contentHash: string | null) {
    if (!selectedScene) return;
    setIsAssigningMedia(true);
    try {
      acceptTimeline(await assignTimelineMedia(selectedScene.sceneId, contentHash, role));
      setMessage(contentHash ? `${role} media assigned` : `${role} media removed`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Media assignment failed");
    } finally {
      setIsAssigningMedia(false);
    }
  }

  async function updateVideoTrim(role: VisualClipRole, start: number, end: number) {
    if (!selectedScene) return;
    try {
      acceptTimeline(await trimTimelineVideo(selectedScene.sceneId, start, end, role));
      setMessage("Video source range updated");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Video trim failed");
    }
  }

  async function updateMusic(contentHash: string | null, volume?: number) {
    if (!timeline) return;
    const currentVolume = timeline.audioClips[0]?.volume ?? 0.2;
    try {
      acceptTimeline(await assignTimelineMusic(contentHash, volume ?? currentVolume));
      setMessage(contentHash ? "Background music assigned" : "Background music removed");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Music assignment failed");
    }
  }

  return (
    <section className="timelineWorkspace" aria-label="Timeline editor">
      <header className="timelineToolbar">
        <div>
          <p className="eyebrow">Timeline editor</p>
          <h2>Scene assembly</h2>
          <p className="timelineMessage" role="status">
            {message}
          </p>
        </div>
        <div className="toolbarActions">
          <button
            className="iconButton"
            title="Reload timeline"
            onClick={() => void loadTimeline()}
          >
            <RefreshCw aria-hidden="true" size={18} />
          </button>
          <button className="secondaryButton" onClick={() => void handleGenerate()}>
            <WandSparkles aria-hidden="true" size={17} /> Generate
          </button>
          {backfillJob && ["queued", "running"].includes(backfillJob.status) ? (
            <button className="secondaryButton" onClick={() => void handleCancelBackfill()}>
              <CircleStop aria-hidden="true" size={17} /> Cancel
            </button>
          ) : (
            <button className="secondaryButton" onClick={() => void handleMetadataBackfill()}>
              <DatabaseBackup aria-hidden="true" size={17} /> Backfill
            </button>
          )}
          <button
            className="primaryButton"
            disabled={!timeline || isSaving}
            onClick={() => void handleSave()}
          >
            <Save aria-hidden="true" size={17} /> {isSaving ? "Saving" : "Save"}
          </button>
        </div>
      </header>
      <WorkflowHandoff
        current="Timeline"
        nextLabel="Next: Render"
        nextTo="/render"
        note="Once the timeline and layers look right, run render preflight."
      />
      {backfillJob && ["queued", "running"].includes(backfillJob.status) && (
        <div className="backfillProgress" role="status">
          <progress max="100" value={backfillJob.progressPercent} />
          <span>
            {backfillJob.processedVideos}/{backfillJob.totalVideos} assets
          </span>
        </div>
      )}

      {loadState !== "ready" || !timeline ? (
        <EmptyTimeline state={loadState} message={message} onGenerate={() => void handleGenerate()} />
      ) : (
        <div className="editorGrid">
          <aside className="sceneRail" aria-label="Timeline scenes">
            <div className="railSummary">
              <strong>{timeline.scenes.length} scenes</strong>
              <span>{formatDuration(timeline.durationMilliseconds)}</span>
            </div>
            {timeline.scenes.map((scene) => (
              <button
                className={`sceneRow${scene.sceneId === selectedSceneId ? " selected" : ""}`}
                key={scene.sceneId}
                onClick={() => setSelectedSceneId(scene.sceneId)}
              >
                <span className="sceneNumber">{scene.order}</span>
                <span>
                  <strong>Scene {scene.order}</strong>
                  <small>
                    {formatDuration(scene.endMilliseconds - scene.startMilliseconds)}
                  </small>
                </span>
              </button>
            ))}
          </aside>

          <main className="trackArea">
            <div className="trackHeader">
              <span>Scene track</span>
              <span>
                <Clock3 aria-hidden="true" size={15} />
                {formatDuration(timeline.durationMilliseconds)}
              </span>
            </div>
            <div className="sceneTrack">
              {timeline.scenes.map((scene) => (
                <button
                  className={`sceneBlock${scene.sceneId === selectedSceneId ? " selected" : ""}`}
                  key={scene.sceneId}
                  style={{
                    flexGrow: Math.max(
                      scene.endMilliseconds - scene.startMilliseconds,
                      1,
                    ),
                  }}
                  onClick={() => setSelectedSceneId(scene.sceneId)}
                  title={`Scene ${scene.order}`}
                >
                  <strong>{scene.order}</strong>
                  <span>
                    {formatDuration(scene.endMilliseconds - scene.startMilliseconds)}
                  </span>
                </button>
              ))}
            </div>
            <div className="layerRow">
              <span>B-roll</span>
              <div className={selectedScene?.mediaClips.some((clip) => clip.role === "broll") ? "mediaLayer" : "emptyLayer"}>
                {selectedScene?.mediaClips.some((clip) => clip.role === "broll") ? "B-roll assigned" : "No B-roll"}
              </div>
            </div>
            <div className="layerRow">
              <span>Avatar</span>
              <div className={selectedScene?.mediaClips.some((clip) => clip.role === "avatar") ? "avatarLayer" : "emptyLayer"}>
                {selectedScene?.mediaClips.some((clip) => clip.role === "avatar") ? "Avatar assigned" : "No avatar"}
              </div>
            </div>
            <div className="layerRow">
              <span>Subtitle</span>
              <div className="subtitleLayer">
                {selectedScene?.subtitleClips[0]?.text ?? "No subtitle"}
              </div>
            </div>
            <div className="layerRow">
              <span>Music</span>
              <div className={timeline.audioClips.length ? "musicLayer" : "emptyLayer"}>
                {timeline.audioClips.length ? "Background music assigned" : "No music"}
              </div>
            </div>
          </main>

          <aside className="inspector" aria-label="Scene inspector">
            <p className="eyebrow">Inspector</p>
            <h3>Scene {selectedScene?.order}</h3>
            <TimelineMediaPicker
              title="B-roll"
              assets={visualAssets}
              disabled={isAssigningMedia}
              selectedContentHash={
                selectedScene?.mediaClips.find((clip) => clip.role === "broll")
                  ?.contentHash ?? null
              }
              onSelect={(contentHash) => void updateVisualMedia("broll", contentHash)}
              selectedClip={selectedScene?.mediaClips.find((clip) => clip.role === "broll") ?? null}
              onTrim={(start, end) => void updateVideoTrim("broll", start, end)}
            />
            <TimelineMediaPicker
              title="Avatar"
              assets={visualAssets}
              disabled={isAssigningMedia}
              selectedContentHash={selectedScene?.mediaClips.find((clip) => clip.role === "avatar")?.contentHash ?? null}
              onSelect={(contentHash) => void updateVisualMedia("avatar", contentHash)}
              selectedClip={selectedScene?.mediaClips.find((clip) => clip.role === "avatar") ?? null}
              onTrim={(start, end) => void updateVideoTrim("avatar", start, end)}
            />
            <section className="musicPicker" aria-label="Background music">
              <div className="mediaPickerHeading"><span><Music2 aria-hidden="true" size={15} /> Background music</span></div>
              <label>Local audio<select value={timeline.audioClips[0]?.contentHash ?? ""} onChange={(event) => void updateMusic(event.target.value || null)}><option value="">{musicAssets.length ? "No music" : "No cached local audio"}</option>{musicAssets.map((asset) => <option key={asset.contentHash} value={asset.contentHash}>{asset.fileName}</option>)}</select></label>
              {timeline.audioClips[0] && <label>Volume<input type="range" min="0" max="1" step="0.05" value={timeline.audioClips[0].volume} onChange={(event) => void updateMusic(timeline.audioClips[0].contentHash, Number(event.target.value))} /></label>}
            </section>
            <label>
              Duration (seconds)
              <input
                min={selectedScene ? getMinimumDuration(selectedScene) / 1_000 : 1}
                step="0.1"
                type="number"
                value={
                  selectedScene
                    ? (selectedScene.endMilliseconds -
                        selectedScene.startMilliseconds) /
                      1_000
                    : 0
                }
                onChange={(event) => updateDuration(Number(event.target.value))}
              />
            </label>
            <label>
              Subtitle
              <textarea
                rows={7}
                value={selectedScene?.subtitleClips[0]?.text ?? ""}
                onChange={(event) => updateSubtitle(event.target.value)}
              />
            </label>
            <dl className="sceneFacts">
              <div>
                <dt>Starts</dt>
                <dd>{formatDuration(selectedScene?.startMilliseconds ?? 0)}</dd>
              </div>
              <div>
                <dt>Media clips</dt>
                <dd>{selectedScene?.mediaClips.length ?? 0}</dd>
              </div>
            </dl>
          </aside>
        </div>
      )}
    </section>
  );
}

function EmptyTimeline({
  state,
  message,
  onGenerate,
}: {
  state: LoadState;
  message: string;
  onGenerate: () => void;
}) {
  return (
    <div className="timelineEmpty">
      <WandSparkles aria-hidden="true" size={28} />
      <h3>{state === "loading" ? "Preparing editor" : "No timeline available"}</h3>
      {state === "empty" && (
        <>
          <WorkspaceGuide
            actionLabel="Go to Script"
            message="Import scenes first if this fails, then generate an editable timeline from those scenes."
            title="Generate timeline from scenes"
            to="/pipeline"
            tone="warning"
          />
          <button className="primaryButton" onClick={onGenerate}>
            Generate timeline
          </button>
        </>
      )}
      {state === "error" && (
        <WorkspaceGuide
          actionLabel="Go to Script"
          message={message}
          title="Timeline is not ready"
          to="/pipeline"
          tone="error"
        />
      )}
    </div>
  );
}

function getMinimumDuration(scene: TimelineScene): number {
  const mediaEnd = Math.max(
    0,
    ...scene.mediaClips.map(
      (clip) => clip.endMilliseconds - scene.startMilliseconds,
    ),
  );
  return Math.max(1_000, mediaEnd);
}

function reflowTimeline(
  timeline: Timeline,
  sceneId: string,
  duration: number,
): Timeline {
  let cursor = 0;
  const scenes = timeline.scenes.map((scene) => {
    const oldStart = scene.startMilliseconds;
    const sceneDuration =
      scene.sceneId === sceneId
        ? duration
        : scene.endMilliseconds - oldStart;
    const shift = cursor - oldStart;
    const start = cursor;
    const end = start + sceneDuration;
    cursor = end;
    return {
      ...scene,
      startMilliseconds: start,
      endMilliseconds: end,
      mediaClips: scene.mediaClips.map((clip) => ({
        ...clip,
        startMilliseconds: clip.startMilliseconds + shift,
        endMilliseconds: clip.endMilliseconds + shift,
      })),
      subtitleClips: scene.subtitleClips.map((clip, index) => ({
        ...clip,
        startMilliseconds: clip.startMilliseconds + shift,
        endMilliseconds:
          scene.sceneId === sceneId && index === 0
            ? end
            : clip.endMilliseconds + shift,
      })),
    };
  });
  return {
    ...timeline,
    scenes,
    durationMilliseconds: cursor,
    audioClips: timeline.audioClips.map((clip) => ({ ...clip, endMilliseconds: cursor })),
  };
}

function formatDuration(milliseconds: number): string {
  return `${(Math.round(milliseconds / 100) / 10).toFixed(1)}s`;
}
