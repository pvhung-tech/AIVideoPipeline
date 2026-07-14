import {
  CheckCircle2,
  Check,
  Download,
  Film,
  Image,
  Link as LinkIcon,
  RefreshCw,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { FingerprintBackfillStatusChip } from "../components/FingerprintBackfillStatusChip";
import { WorkflowHandoff } from "../components/WorkflowHandoff";
import { WorkspaceGuide } from "../components/WorkspaceGuide";
import {
  cacheMedia,
  getMediaCacheManifest,
  listMediaProviders,
  MediaApiError,
  searchMedia,
  type MediaCacheManifest,
  type MediaProviderError,
  type MediaSearchItem,
  type MediaSearchPage,
  type MediaType,
} from "../services/mediaClient";
import {
  assignTimelineMedia,
  getTimeline,
  getTimelineMediaAssetPage,
  type Timeline,
  TimelineApiError,
  type TimelineMediaAsset,
  type TimelineMediaAssetPage,
  type VisualClipRole,
} from "../services/timelineClient";

type MediaFilter = "all" | MediaType;
type MediaActivityPhase = "search" | "cache" | "assign";
type MediaActivityStatus = "active" | "complete" | "error";
type ProviderSearchStatus = "pending" | "complete" | "error";

interface ProviderSearchProgress {
  providerId: string;
  status: ProviderSearchStatus;
  itemCount: number;
  message: string;
}

interface MediaActivity {
  phase: MediaActivityPhase;
  status: MediaActivityStatus;
  title: string;
  detail: string;
  startedAt: number;
  finishedAt?: number;
  result?: string;
}

const MEDIA_ASSET_PAGE_SIZE = 100;

export function MediaPage() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(
    () => searchParams.get("query") ?? "city skyline",
  );
  const [providerId, setProviderId] = useState("all");
  const [mediaType, setMediaType] = useState<MediaFilter>("all");
  const [providers, setProviders] = useState<string[]>([]);
  const [searchPage, setSearchPage] = useState<MediaSearchPage | null>(null);
  const [manifest, setManifest] = useState<MediaCacheManifest | null>(null);
  const [assets, setAssets] = useState<TimelineMediaAsset[]>([]);
  const [assetPage, setAssetPage] = useState<TimelineMediaAssetPage | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const [role, setRole] = useState<VisualClipRole>("broll");
  const [message, setMessage] = useState("Loading media workspace...");
  const [isSearching, setIsSearching] = useState(false);
  const [providerProgress, setProviderProgress] = useState<ProviderSearchProgress[]>([]);
  const [activeCacheId, setActiveCacheId] = useState<string | null>(null);
  const [isAssigning, setIsAssigning] = useState(false);
  const [activity, setActivity] = useState<MediaActivity | null>(null);
  const [activityElapsedSeconds, setActivityElapsedSeconds] = useState(0);
  const searchRunId = useRef(0);

  const selectedScene = useMemo(
    () => timeline?.scenes.find((scene) => scene.sceneId === selectedSceneId) ?? null,
    [selectedSceneId, timeline],
  );
  const visualAssets = useMemo(
    () => assets.filter((asset) => asset.mediaType !== "audio"),
    [assets],
  );

  useEffect(() => {
    void loadWorkspace();
  }, []);

  useEffect(() => {
    const nextQuery = searchParams.get("query");
    if (nextQuery) {
      setQuery(nextQuery);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!activity || activity.status !== "active") return undefined;
    setActivityElapsedSeconds(0);
    const intervalId = window.setInterval(() => {
      setActivityElapsedSeconds(Math.max(0, Math.floor((Date.now() - activity.startedAt) / 1000)));
    }, 500);
    return () => window.clearInterval(intervalId);
  }, [activity?.startedAt, activity?.status]);

  function startActivity(nextActivity: Omit<MediaActivity, "startedAt" | "status">) {
    setActivity({
      ...nextActivity,
      status: "active",
      startedAt: Date.now(),
    });
  }

  function finishActivity(status: Exclude<MediaActivityStatus, "active">, result: string) {
    setActivity((current) =>
      current
        ? {
            ...current,
            status,
            result,
            finishedAt: Date.now(),
          }
        : current,
    );
  }

  async function loadWorkspace() {
    await Promise.all([loadProviders(), loadCacheWindow(0), loadTimeline()]);
  }

  async function loadProviders() {
    try {
      setProviders(await listMediaProviders());
    } catch {
      setProviders([]);
    }
  }

  async function loadCacheWindow(offset: number) {
    try {
      const [nextManifest, nextAssetPage] = await Promise.all([
        getMediaCacheManifest(),
        getTimelineMediaAssetPage({
          offset,
          limit: MEDIA_ASSET_PAGE_SIZE,
        }),
      ]);
      setManifest(nextManifest);
      setAssetPage(nextAssetPage);
      const nextAssets = offset === 0
        ? nextAssetPage.assets
        : mergeAssets(assets, nextAssetPage.assets);
      setAssets(nextAssets);
      setSelectedHash((current) =>
        nextAssets.some((asset) => asset.contentHash === current)
          ? current
          : (nextAssets[0]?.contentHash ?? null),
      );
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Media cache unavailable");
    }
  }

  async function loadMoreCachedAssets() {
    if (!assetPage?.hasMore) return;
    await loadCacheWindow(assetPage.offset + assetPage.assets.length);
  }

  async function loadTimeline() {
    try {
      const nextTimeline = await getTimeline();
      setTimeline(nextTimeline);
      setSelectedSceneId((current) =>
        nextTimeline.scenes.some((scene) => scene.sceneId === current)
          ? current
          : (nextTimeline.scenes[0]?.sceneId ?? null),
      );
      setMessage("Media workspace ready.");
    } catch (error: unknown) {
      if (
        error instanceof TimelineApiError &&
        error.code === "TIMELINE_NOT_FOUND"
      ) {
        setTimeline(null);
        setSelectedSceneId(null);
        setMessage("Generate a timeline before assigning cached media.");
      } else {
        setMessage(error instanceof Error ? error.message : "Timeline unavailable");
      }
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    const nextSearchRunId = searchRunId.current + 1;
    searchRunId.current = nextSearchRunId;
    setIsSearching(true);
    setMessage("Searching media providers...");
    startActivity({
      phase: "search",
      title: "Searching media",
      detail: `${query.trim()} - ${providerLabel(providerId)} - ${mediaTypeLabel(mediaType)}`,
    });
    try {
      const page = providerId === "all"
        ? await searchAllProvidersIncrementally(query.trim(), nextSearchRunId)
        : await searchSingleProvider(query.trim(), providerId);
      if (nextSearchRunId !== searchRunId.current) return;
      setSearchPage(page);
      setMessage(`Found ${page.items.length} media results.`);
      finishActivity(
        "complete",
        page.items.length ? `${page.items.length} results ready.` : "No matching media found.",
      );
    } catch (error: unknown) {
      if (nextSearchRunId !== searchRunId.current) return;
      const errorMessage = error instanceof Error ? error.message : "Media search failed";
      setMessage(errorMessage);
      finishActivity("error", errorMessage);
    } finally {
      if (nextSearchRunId === searchRunId.current) {
        setIsSearching(false);
      }
    }
  }

  async function searchSingleProvider(searchText: string, selectedProviderId: string) {
    setProviderProgress([
      {
        providerId: selectedProviderId,
        status: "pending",
        itemCount: 0,
        message: "Searching",
      },
    ]);
    const page = await searchMedia({
      query: searchText,
      mediaType,
      providerId: selectedProviderId,
    });
    setProviderProgress([
      {
        providerId: selectedProviderId,
        status: "complete",
        itemCount: page.items.length,
        message: `${page.items.length} ready`,
      },
    ]);
    return page;
  }

  async function searchAllProvidersIncrementally(searchText: string, currentRunId: number) {
    const providerIds = providers.filter((provider) => provider !== "all");
    if (!providerIds.length) {
      return searchMedia({ query: searchText, mediaType, providerId: "all" });
    }
    const pendingProgress = providerIds.map((provider) => ({
      providerId: provider,
      status: "pending" as const,
      itemCount: 0,
      message: "Searching",
    }));
    const completedPages: MediaSearchPage[] = [];
    const providerErrors: MediaProviderError[] = [];
    setProviderProgress(pendingProgress);
    setSearchPage(createCombinedSearchPage(searchText, [], providerErrors));

    await Promise.all(
      providerIds.map(async (nextProviderId) => {
        try {
          const page = await searchMedia({
            query: searchText,
            mediaType,
            providerId: nextProviderId,
            limit: 12,
          });
          completedPages.push(page);
          updateProviderProgress(
            currentRunId,
            nextProviderId,
            "complete",
            page.items.length,
            `${page.items.length} ready`,
          );
        } catch (error: unknown) {
          const providerError = providerErrorFrom(nextProviderId, error);
          providerErrors.push(providerError);
          updateProviderProgress(
            currentRunId,
            nextProviderId,
            "error",
            0,
            providerError.message,
          );
        }
        if (currentRunId === searchRunId.current) {
          setSearchPage(createCombinedSearchPage(searchText, completedPages, providerErrors));
          setMessage(`Showing ${mergeSearchItems(completedPages).length} results while providers finish.`);
        }
      }),
    );
    return createCombinedSearchPage(searchText, completedPages, providerErrors);
  }

  function updateProviderProgress(
    currentRunId: number,
    nextProviderId: string,
    status: ProviderSearchStatus,
    itemCount: number,
    message: string,
  ) {
    if (currentRunId !== searchRunId.current) return;
    setProviderProgress((current) =>
      current.map((progress) =>
        progress.providerId === nextProviderId
          ? { ...progress, status, itemCount, message }
          : progress,
      ),
    );
  }

  async function handleCache(item: MediaSearchItem) {
    setActiveCacheId(item.id);
    startActivity({
      phase: "cache",
      title: "Saving media to cache",
      detail: `${item.title} - ${item.providerId} - ${mediaTypeLabel(item.mediaType)}`,
    });
    try {
      const cached = await cacheMedia(item);
      await loadCacheWindow(0);
      setSelectedHash(cached.contentHash);
      setMessage(cached.duplicate ? "Media already in cache." : "Media downloaded to cache.");
      finishActivity(
        "complete",
        cached.duplicate
          ? `Already cached. ${formatBytes(cached.sizeBytes)} reused.`
          : `Download complete. ${formatBytes(cached.sizeBytes)} saved.`,
      );
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "Media download failed";
      setMessage(errorMessage);
      finishActivity("error", errorMessage);
    } finally {
      setActiveCacheId(null);
    }
  }

  async function handleAssign() {
    if (!selectedSceneId || !selectedHash) return;
    setIsAssigning(true);
    startActivity({
      phase: "assign",
      title: "Assigning media",
      detail: `${selectedScene ? `Scene ${selectedScene.order}` : "Selected scene"} - ${role === "broll" ? "B-roll" : "Avatar"}`,
    });
    try {
      const nextTimeline = await assignTimelineMedia(selectedSceneId, selectedHash, role);
      setTimeline(nextTimeline);
      setMessage(`${role === "broll" ? "B-roll" : "Avatar"} assigned to scene.`);
      finishActivity("complete", `${role === "broll" ? "B-roll" : "Avatar"} assigned.`);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "Media assignment failed";
      setMessage(errorMessage);
      finishActivity("error", errorMessage);
    } finally {
      setIsAssigning(false);
    }
  }

  return (
    <section className="mediaWorkspace" aria-label="Media search workspace">
      <header className="mediaWorkspaceHeader">
        <div>
          <p className="eyebrow">Media</p>
          <h2>Search, download, and assign media</h2>
          <p className="timelineMessage" role="status">
            {message}
          </p>
        </div>
        <div className="workspaceHeaderActions">
          <FingerprintBackfillStatusChip />
          <button className="iconButton" title="Refresh media" onClick={() => void loadWorkspace()}>
            <RefreshCw aria-hidden="true" size={18} />
          </button>
        </div>
      </header>

      <WorkflowHandoff
        current="Media"
        nextLabel="Next: Timeline"
        nextTo="/timeline"
        note="After downloading or assigning media, continue to scene assembly."
      />

      <MediaActivityPanel activity={activity} elapsedSeconds={activityElapsedSeconds} />

      <form className="mediaSearchForm" onSubmit={handleSearch}>
        <label>
          Search keywords
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label>
          Type
          <select value={mediaType} onChange={(event) => setMediaType(event.target.value as MediaFilter)}>
            <option value="all">Images and videos</option>
            <option value="image">Images</option>
            <option value="video">Videos</option>
          </select>
        </label>
        <label>
          Provider
          <select value={providerId} onChange={(event) => setProviderId(event.target.value)}>
            <option value="all">All providers</option>
            {providers.map((provider) => (
              <option key={provider} value={provider}>
                {provider}
              </option>
            ))}
          </select>
        </label>
        <button className="primaryButton" disabled={isSearching} type="submit">
          <Search aria-hidden="true" size={16} />
          {isSearching ? "Searching" : "Search"}
        </button>
      </form>

      {!searchPage && (
        <WorkspaceGuide
          actionLabel="Open AI"
          message="Use AI keywords from analyzed scenes, or type a keyword above and search across available providers."
          title="Start with scene keywords"
          to="/analysis"
        />
      )}
      {searchPage && searchPage.items.length === 0 && (
        <WorkspaceGuide
          actionLabel="Open AI"
          message="Try a broader keyword, change media type/provider, or return to AI analysis for alternate keywords."
          title="No media found for this search"
          to="/analysis"
          tone="warning"
        />
      )}

      <div className="mediaWorkspaceGrid">
        <section className="mediaResultsPanel" aria-label="Search results">
          <PanelHeading
            title="Search results"
            meta={searchPage ? `${searchPage.items.length} shown` : "No search yet"}
          />
          {searchPage?.providerErrors.length ? (
            <div className="mediaProviderErrors">
              {searchPage.providerErrors.map((error) => (
                <span key={`${error.providerId}-${error.code}`}>
                  {error.providerId}: {error.message}
                </span>
              ))}
            </div>
          ) : null}
          {providerProgress.length ? (
            <div className="mediaProviderProgress" aria-label="Provider search progress">
              {providerProgress.map((progress) => (
                <span className={progress.status} key={progress.providerId}>
                  {progress.providerId}: {providerStatusLabel(progress)}
                </span>
              ))}
            </div>
          ) : null}
          <div className="mediaResultGrid">
            {(searchPage?.items ?? []).map((item) => (
              <MediaResultCard
                isCaching={activeCacheId === item.id}
                item={item}
                key={`${item.providerId}-${item.id}`}
                onCache={() => void handleCache(item)}
              />
            ))}
          </div>
        </section>

        <section className="mediaCachePanel" aria-label="Cached media assignment">
          <PanelHeading
            title="Cached media"
            meta={cacheAssetMeta(visualAssets.length, assetPage)}
          />
          {!timeline && (
            <WorkspaceGuide
              actionLabel="Open Timeline"
              message="Generate a timeline before assigning cached media to B-roll or Avatar layers."
              title="Timeline needed for assignment"
              to="/timeline"
              tone="warning"
            />
          )}
          <div className="mediaAssignControls">
            <label>
              Scene
              <select
                disabled={!timeline}
                value={selectedSceneId ?? ""}
                onChange={(event) => setSelectedSceneId(event.target.value || null)}
              >
                <option value="">No timeline scene</option>
                {timeline?.scenes.map((scene) => (
                  <option key={scene.sceneId} value={scene.sceneId}>
                    Scene {scene.order}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Layer
              <select value={role} onChange={(event) => setRole(event.target.value as VisualClipRole)}>
                <option value="broll">B-roll</option>
                <option value="avatar">Avatar</option>
              </select>
            </label>
            <button
              className="primaryButton"
              disabled={!selectedScene || !selectedHash || isAssigning}
              onClick={() => void handleAssign()}
              type="button"
            >
              <Check aria-hidden="true" size={16} />
              {isAssigning ? "Assigning" : "Assign to scene"}
            </button>
          </div>
          <div className="cacheAssetList">
            {visualAssets.map((asset) => (
              <button
                className={`cacheAssetRow${asset.contentHash === selectedHash ? " selected" : ""}`}
                key={asset.contentHash}
                onClick={() => setSelectedHash(asset.contentHash)}
                type="button"
              >
                <AssetIcon mediaType={asset.mediaType} />
                <span>
                  <strong>{asset.fileName}</strong>
                  <small>{formatBytes(asset.sizeBytes)} · {asset.providerIds.join(", ") || "cache"}</small>
                </span>
              </button>
            ))}
            {!visualAssets.length && (
              <WorkspaceGuide
                actionLabel="Open AI"
                message="Download a search result to cache it. AI scene keywords usually produce better first searches."
                title="No cached media yet"
                to="/analysis"
              />
            )}
            {assetPage?.hasMore && (
              <button
                className="secondaryButton"
                onClick={() => void loadMoreCachedAssets()}
                type="button"
              >
                Load more cached media
              </button>
            )}
          </div>
          <p className="cacheSummary">
            Cache size: {formatBytes(manifest?.totalSizeBytes ?? 0)}
          </p>
        </section>
      </div>
    </section>
  );
}

function MediaActivityPanel({
  activity,
  elapsedSeconds,
}: {
  activity: MediaActivity | null;
  elapsedSeconds: number;
}) {
  if (!activity) return null;
  const steps = activitySteps(activity.phase);
  const activeStepIndex = activity.status === "complete"
    ? steps.length - 1
    : activity.status === "error"
      ? Math.min(1, steps.length - 1)
      : activityStepIndex(activity.phase, elapsedSeconds);
  const elapsedLabel = formatElapsed(
    activity.status === "active"
      ? elapsedSeconds
      : Math.max(
          0,
          Math.floor(((activity.finishedAt ?? Date.now()) - activity.startedAt) / 1000),
        ),
  );

  return (
    <section className={`mediaActivityPanel ${activity.status}`} aria-label="Media activity" aria-live="polite">
      <div className="mediaActivitySummary">
        <span className="mediaActivityIcon">
          {activity.status === "complete" ? (
            <CheckCircle2 aria-hidden="true" size={18} />
          ) : (
            <ActivityIcon phase={activity.phase} />
          )}
        </span>
        <span>
          <strong>{activity.title}</strong>
          <small>{activity.detail}</small>
        </span>
      </div>
      <ol className="mediaActivitySteps">
        {steps.map((step, index) => (
          <li
            className={index <= activeStepIndex ? "active" : ""}
            key={step}
          >
            {step}
          </li>
        ))}
      </ol>
      <div className="mediaActivityResult">
        <span>{activity.result ?? (activity.status === "active" ? "Working..." : "Ready.")}</span>
        <small>{elapsedLabel}</small>
      </div>
    </section>
  );
}

function PanelHeading({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="mediaPanelHeading">
      <h3>{title}</h3>
      <span>{meta}</span>
    </div>
  );
}

function MediaResultCard({
  item,
  isCaching,
  onCache,
}: {
  item: MediaSearchItem;
  isCaching: boolean;
  onCache: () => void;
}) {
  return (
    <article className="mediaResultCard">
      <div className="mediaResultPreview">
        {item.previewUri && item.mediaType === "image" ? (
          <img src={item.previewUri} alt="" />
        ) : (
          <AssetIcon mediaType={item.mediaType} />
        )}
      </div>
      <div className="mediaResultBody">
        <strong>{item.title}</strong>
        <span>{item.providerId} · {item.mediaType}</span>
        <small>{item.creator ?? item.license ?? "Media provider result"}</small>
      </div>
      <div className="mediaResultActions">
        {item.sourcePageUri && (
          <a className="secondaryButton" href={item.sourcePageUri} rel="noreferrer" target="_blank">
            <LinkIcon aria-hidden="true" size={14} />
            Source
          </a>
        )}
        <button className="primaryButton" disabled={isCaching} onClick={onCache} type="button">
          <Download aria-hidden="true" size={14} />
          {isCaching ? "Downloading" : "Download"}
        </button>
      </div>
    </article>
  );
}

function AssetIcon({ mediaType }: { mediaType: string }) {
  return mediaType === "image" ? (
    <Image aria-hidden="true" size={20} />
  ) : (
    <Film aria-hidden="true" size={20} />
  );
}

function ActivityIcon({ phase }: { phase: MediaActivityPhase }) {
  if (phase === "search") {
    return <Search aria-hidden="true" size={18} />;
  }
  if (phase === "assign") {
    return <Check aria-hidden="true" size={18} />;
  }
  return <Download aria-hidden="true" size={18} />;
}

function activitySteps(phase: MediaActivityPhase): string[] {
  if (phase === "search") {
    return ["Preparing", "Checking providers", "Results ready"];
  }
  if (phase === "assign") {
    return ["Preparing", "Updating timeline", "Assigned"];
  }
  return ["Preparing", "Downloading", "Checking cache", "Ready"];
}

function activityStepIndex(phase: MediaActivityPhase, elapsedSeconds: number): number {
  if (phase === "cache") {
    if (elapsedSeconds >= 8) return 2;
    if (elapsedSeconds >= 2) return 1;
    return 0;
  }
  if (elapsedSeconds >= 2) return 1;
  return 0;
}

function providerLabel(providerId: string): string {
  return providerId === "all" ? "All providers" : providerId;
}

function createCombinedSearchPage(
  query: string,
  pages: MediaSearchPage[],
  providerErrors: MediaProviderError[],
): MediaSearchPage {
  const items = mergeSearchItems(pages);
  return {
    providerId: "all",
    query,
    totalResults: pages.reduce((total, page) => total + page.totalResults, 0),
    offset: 0,
    limit: 24,
    truncated: pages.some((page) => page.truncated) || providerErrors.length > 0,
    items,
    providerErrors: [...providerErrors],
    deduplication: null,
  };
}

function mergeSearchItems(pages: MediaSearchPage[]): MediaSearchItem[] {
  const seen = new Set<string>();
  const items = pages
    .flatMap((page) => page.items)
    .sort((first, second) => second.score - first.score || first.providerId.localeCompare(second.providerId));
  const merged: MediaSearchItem[] = [];
  for (const item of items) {
    const key = `${item.providerId}:${item.id}:${item.sourceUri}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
    if (merged.length >= 24) break;
  }
  return merged;
}

function providerErrorFrom(providerId: string, error: unknown): MediaProviderError {
  if (error instanceof MediaApiError) {
    return {
      providerId,
      code: error.code,
      message: error.message,
    };
  }
  return {
    providerId,
    code: "MEDIA_PROVIDER_FAILED",
    message: error instanceof Error ? error.message : "Provider search failed.",
  };
}

function providerStatusLabel(progress: ProviderSearchProgress): string {
  if (progress.status === "pending") return "searching";
  if (progress.status === "complete") return `${progress.itemCount} ready`;
  return progress.message;
}

function mergeAssets(
  currentAssets: TimelineMediaAsset[],
  nextAssets: TimelineMediaAsset[],
): TimelineMediaAsset[] {
  const seen = new Set(currentAssets.map((asset) => asset.contentHash));
  return [
    ...currentAssets,
    ...nextAssets.filter((asset) => {
      if (seen.has(asset.contentHash)) return false;
      seen.add(asset.contentHash);
      return true;
    }),
  ];
}

function cacheAssetMeta(
  visibleVisualAssets: number,
  assetPage: TimelineMediaAssetPage | null,
): string {
  if (!assetPage) return `${visibleVisualAssets} visual assets`;
  if (assetPage.totalEntries <= assetPage.assets.length) {
    return `${visibleVisualAssets} visual assets`;
  }
  return `${visibleVisualAssets} shown of ${assetPage.totalEntries} cached entries`;
}

function mediaTypeLabel(mediaType: MediaFilter): string {
  if (mediaType === "all") return "Images and videos";
  return mediaType === "image" ? "Images" : "Videos";
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

function formatBytes(sizeBytes: number): string {
  if (sizeBytes < 1_024) return `${sizeBytes} B`;
  if (sizeBytes < 1_048_576) return `${(sizeBytes / 1_024).toFixed(1)} KB`;
  return `${(sizeBytes / 1_048_576).toFixed(1)} MB`;
}
