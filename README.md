# AI Video Pipeline Studio

AI Video Pipeline Studio is a desktop application foundation for an AI-powered video production pipeline.

## Phase 0 Status

This repository currently contains the initial project skeleton:

- FastAPI backend foundation
- React + TypeScript frontend foundation
- Tauri desktop shell configuration
- Self-contained FastAPI sidecar managed by Tauri
- Client-side routing and Zustand state management
- Basic health-check flow between frontend and backend

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:createApp --factory --reload
```

Or from the repository root:

```powershell
.\scripts\install_backend.ps1
.\scripts\dev_backend.ps1
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Or from the repository root:

```powershell
.\scripts\dev_frontend.ps1
```

## Desktop

```powershell
cd frontend
npm run tauri:dev
```

The desktop commands build the FastAPI sidecar before starting Tauri. They require:

- The backend virtual environment with development dependencies installed
- Rust and Cargo
- Visual Studio Build Tools with the C++ workload on Windows

The packaged desktop application starts FastAPI automatically on
`http://127.0.0.1:8765` and stops it when the application exits.

## Desktop Workflow Dashboard

Phase 7 starts with a production dashboard at `/projects`. It reads the active
project, imported scenes, timeline, media cache, and render queue, then shows the
current production steps in order: Project, Script, AI, Media, Timeline, and
Render. Each step includes the current issue, a suggested fix, and a link to the
workspace that resolves the next missing item, so operators can continue the
workflow without remembering backend endpoints or command-line checks.

The same dashboard now includes Project Manager controls for creating a project,
opening an existing project by folder path, closing the active project, and
opening recent projects with one click. The dashboard refreshes after each
project action so the workflow status always reflects the active project.
When completed MP4 outputs exist, the dashboard also turns the latest output
summary into a review action with accepted, rejected, and not-reviewed counts,
linking directly into the Render queue for playback and review decisions.
If a render job is queued, running, or cancelling, the same summary area
prioritizes that active job, shows its progress, and links to the Render
workspace so operators can monitor or cancel without hunting through the queue.
While an active render remains in the queue, the dashboard refreshes that
workflow snapshot every few seconds and stops once the job leaves the active
state. Monitor links open the Render progress/cancel area directly, while review
links jump to the queue list.
After the active job completes, the dashboard highlights the latest completed
MP4 as the newest output. Unreviewed outputs use the explicit "completed and
ready to review" status so the next review action is visible without opening the
Render queue first.
The review action also carries the latest output's job ID into the Render
workspace, so the queue opens with that output selected for playback, notes, and
accept/reject review.
After an output is accepted or rejected in the Render workspace, operators can
return directly to the Dashboard. The Dashboard shows the latest completed
output's review state as accepted, rejected, or not reviewed so the production
status is visible without reopening the queue.
When every completed output has a review decision, the Dashboard switches the
latest-output card to an "all outputs reviewed" state with quick actions to
open the Render report/handoff area or start the next render pass.

The Pipeline workspace at `/pipeline` now gives non-technical users the Script
Import and Scene Viewer flow directly in the desktop UI. Operators can enter a
TXT or SRT file path or choose one through the native desktop file picker,
import it into the active project, review the generated scene list, select a
scene, and save scene text edits without calling the Script API manually.

The Media workspace at `/media` provides the next non-technical production
step. Operators can search Local Library and online providers, download a result
into the active project cache, review cached visual assets, then assign one to a
Timeline scene as B-roll or Avatar media without manually calling Media or
Timeline endpoints.

The AI Analysis workspace at `/analysis` exposes the completed Scene Analysis
engine to non-technical operators. It lets them choose provider and model, run a
batch analysis for all imported scenes, inspect each scene's description,
category, and keywords, then jump directly into Media Search with a selected
keyword prefilled.

The Settings workspace at `/settings` gives operators a read-only setup report
for AI providers, API-key environment variables, Ollama availability, and
runtime tooling hints. Secret values are never returned to the UI; the screen
shows only whether each key is configured and which environment variable should
be set before restarting the desktop app.

Script, AI, Media, Timeline, and Render workspaces now include guided empty and
error states. When required data is missing, each workspace names the missing
step and links to the next screen to fix it, such as importing scenes, running
AI analysis, downloading media, generating a timeline, or resolving Render
preflight groups.

## Project Core API

Phase 1 provides local project lifecycle endpoints:

```text
POST /api/projects
POST /api/projects/open
GET  /api/projects/current
PUT  /api/projects/current
POST /api/projects/close
GET  /api/projects/recent
```

Each project contains an atomically written `project.json` and the directories
`script`, `media`, `cache`, `render`, and `output`. Project metadata and recent
project ordering are stored in SQLite under the application data directory.
Every mutation is persisted immediately, which provides the Phase 1 auto-save
behavior.

## Script and Scene API

Phase 2 imports and validates UTF-8 TXT and SRT files into the active project:

```text
POST /api/scripts/import
```

Request body:

```json
{
  "path": "C:\\path\\to\\script.srt"
}
```

Imported content is normalized and written atomically to `script/source.txt`
or `script/source.srt`. `script/manifest.json` records source metadata. SRT
validation covers cue numbering, timestamps, positive duration, ordering,
multiline text, UTF-8 encoding, and the 5 MB file limit.

Import also creates `script/scenes.json`. TXT paragraphs become scenes, while
each SRT cue becomes a timed scene. Scenes can be read and edited through:

```text
GET /api/scripts/scenes
PUT /api/scripts/scenes/{sceneId}
```

The update body is `{ "text": "Updated scene text" }`. Scene IDs, ordering,
source cue references, and timing remain stable when text is edited.

## AI Foundation

The first Phase 3 increment defines a provider-neutral asynchronous AI
contract and a provider registry. No provider SDK or network integration is
included yet. Prompt templates are versioned in `configs/prompts.json` and are
rendered by `PromptManager`, which rejects missing, unknown, or unsafe template
variables. Override the bundled prompt file with `PROMPT_CONFIG_PATH` when
developing or testing custom templates.

### Scene Analysis with Ollama

Ollama is the first provider adapter. It uses the local `/api/chat` endpoint
with structured JSON output and does not require an API key. Configure it with:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
AI_REQUEST_TIMEOUT_SECONDS=120
```

After importing a script, analyze and read scene results through:

```text
POST /api/ai/scenes/{sceneId}/analyze
GET  /api/ai/scenes/analysis
```

The POST body accepts optional `providerId` and `model`, plus `contentType` and
`language`. Results are stored atomically in `script/analysis.json` and contain
description, category, keywords, provider/model metadata, prompt version, and
a source-text hash. Results automatically become stale when scene text changes.
See the official [Ollama chat API](https://docs.ollama.com/api/chat) and
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
documentation for the underlying local API.

### Retry and OpenAI

Provider calls use bounded exponential backoff for transient timeouts,
connection failures, rate limits, and server failures. Authentication errors,
missing models, rejected requests, and invalid responses are not retried.
Configure retry behavior with:

```text
AI_MAX_ATTEMPTS=3
AI_RETRY_INITIAL_DELAY_SECONDS=1
AI_RETRY_MAX_DELAY_SECONDS=8
```

OpenAI is the second provider and uses the Responses API with strict structured
JSON output. It is optional and remains disabled until `OPENAI_API_KEY` is set:

```text
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com
OPENAI_MODEL=gpt-5-mini
```

Select it per request with `"providerId": "openai"`; omitting `model` uses
`OPENAI_MODEL`. See the official [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
and [structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

Analyze every scene sequentially with:

```text
POST /api/ai/scenes/analyze
```

The batch endpoint accepts the same provider, model, content type, and language
fields as single-scene analysis. Valid existing results are skipped by default
so interrupted batches can resume. Set `"reanalyze": true` to regenerate every
scene. Each success is persisted immediately; the response reports successful,
failed, and skipped scene IDs without discarding partial progress.

On this Windows machine Ollama is configured for CPU execution with the user
environment variables `OLLAMA_LLM_LIBRARY=cpu` and `CUDA_VISIBLE_DEVICES=-1`
because the installed NVIDIA driver cannot run Ollama's bundled CUDA PTX.

## Media Search and Cache

Phase 4 provides provider-neutral search contracts, a provider registry, Local
Library search, Pexels/Pixabay/Wikimedia Commons image and video search, and a
content-addressed project cache. Configure one or more local roots using the platform path separator
(`;` on Windows):

```text
LOCAL_MEDIA_LIBRARY_PATHS=D:\Media\Videos;D:\Media\Images
LOCAL_MEDIA_MAX_SCANNED_FILES=50000
MEDIA_CACHE_MAX_FILE_SIZE_BYTES=2147483648
MEDIA_CACHE_MAX_TOTAL_SIZE_BYTES=10737418240
MEDIA_CACHE_MAX_AGE_DAYS=30
MEDIA_DOWNLOAD_TIMEOUT_SECONDS=300
PEXELS_API_KEY=your-key
DVIDS_API_KEY=your-key
DVIDS_VIDEO_QUALITY=highest
DVIDS_VIDEO_MAX_FILE_SIZE_BYTES=0
DVIDS_MAX_ATTEMPTS=3
DVIDS_RETRY_INITIAL_DELAY_SECONDS=1
DVIDS_RETRY_MAX_DELAY_SECONDS=60
DVIDS_RETRY_JITTER_RATIO=0.25
DVIDS_SEARCH_CACHE_TTL_SECONDS=86400
DVIDS_ASSET_CACHE_TTL_SECONDS=3600
DVIDS_NEGATIVE_CACHE_TTL_SECONDS=300
PIXABAY_API_KEY=your-key
PIXABAY_MAX_ATTEMPTS=3
PIXABAY_RETRY_INITIAL_DELAY_SECONDS=1
PIXABAY_RETRY_MAX_DELAY_SECONDS=60
PIXABAY_RETRY_JITTER_RATIO=0.25
PIXABAY_SEARCH_CACHE_TTL_SECONDS=86400
WIKIMEDIA_COMMONS_BASE_URL=https://commons.wikimedia.org
WIKIMEDIA_USER_AGENT=AI-Video-Pipeline-Studio/0.1.0 (https://your-project-url; you@example.com)
WIKIMEDIA_MAX_ATTEMPTS=3
WIKIMEDIA_RETRY_INITIAL_DELAY_SECONDS=1
WIKIMEDIA_RETRY_MAX_DELAY_SECONDS=60
WIKIMEDIA_RETRY_JITTER_RATIO=0.25
WIKIMEDIA_SEARCH_CACHE_TTL_SECONDS=86400
```

Search and inspect registered providers through:

```text
GET /api/media/search?query=city&mediaType=image&limit=50&offset=0
GET /api/media/search?query=city&providerId=all&limit=50&offset=0
GET /api/media/providers
POST /api/media/cache
GET /api/media/cache
POST /api/media/cache/cleanup
POST /api/media/cache/reconcile
```

Select Pexels with `providerId=pexels`; its key is sent only in the Pexels
`Authorization` header. Results include creator and source-page metadata so the
UI can link to Pexels and credit contributors. Repeat `mediaType` for multiple
types.

Use `providerId=all` to search Local Library, Pexels, Pixabay, Wikimedia, and
DVIDS concurrently. Results are ranked from provider result position and
normalized provider score, then deduplicated by canonical source URL, canonical
source page, and a conservative media-type/title/file-size fingerprint. Tracking
and signed URL parameters are ignored while identity-bearing query parameters
are preserved. Partial failures appear in `providerErrors`; search succeeds if
at least one provider succeeds. `totalResults` is the sum of provider totals
before cross-provider deduplication.

Select DVIDS Hub with `providerId=dvids`. Register an API application with
DVIDS and set `DVIDS_API_KEY`; credentials are used only for DVIDS API calls.
Search first retrieves image/video summaries, then loads each selected asset to
obtain its original image or MP4 URL. Results preserve creator credit and the
DVIDS asset page. Content is labeled `Public Domain unless otherwise specified`;
the source page remains authoritative for individual copyright exceptions.
Video renditions use the DVIDS `files[].src` schema; the provider selects the
best eligible rendition and reports its exact byte size. Set
`DVIDS_VIDEO_QUALITY` to `highest`, `1080p`, or `720p`; capped modes choose the
best rendition at or below that height. `DVIDS_VIDEO_MAX_FILE_SIZE_BYTES=0`
means unlimited. A positive value excludes files larger than the limit and
files whose size is unknown.

DVIDS persists successful responses below the application data directory.
Search summaries default to 24 hours, while asset details default to one hour
so removed or changed media is refreshed sooner. The asset TTL must not exceed
the search TTL. Cache keys exclude `DVIDS_API_KEY`. Transient
connection failures, HTTP 429, and 5xx responses use bounded retries; delay
prefers `Retry-After`, then `X-RateLimit-Reset`, then exponential backoff with
jitter. Concurrent identical endpoint requests share one shielded task.
Asset-only HTTP 403/404 responses are cached separately for five minutes. A
negative hit skips that asset and continues to the next search result without
repeating the unavailable request. Authentication failures from `/search`,
rate limits, and server errors are never negative-cached.

Select Pixabay with `providerId=pixabay`. Successful API responses are cached
for 24 hours under the application data directory and survive backend/desktop
restarts. Cache keys are hashes of normalized requests and never contain the API
key. Expired entries are pruned when a provider instance starts serving search.

Pixabay retries bounded transient failures. Delay priority is `Retry-After`,
then `X-RateLimit-Reset`, then exponential backoff, always capped by
`PIXABAY_RETRY_MAX_DELAY_SECONDS`. SafeSearch is enabled, and the HTTP client
logger stays at WARNING so query-string credentials do not enter application
logs. Assets are downloaded into project cache rather than permanently
hotlinked.

Exponential fallback adds configurable positive jitter to spread retries across
workers; provider-specified rate-limit delays are preserved exactly. Concurrent
identical searches are coalesced by persistent cache key, so all waiting scenes
share one shielded provider request. Different query/page/type combinations
remain independent.

Select Wikimedia Commons with `providerId=wikimedia`. It requires no API key,
but `WIKIMEDIA_USER_AGENT` must identify the application and include a real
contact URL or email as required by Wikimedia's robot policy.
Search is restricted to the File namespace and normalizes images and videos,
including creator, license, source page, original URL, and preview URL. Unsupported
audio and document results are skipped, and scanning is capped at ten API batches.
Original files and redirects must remain on trusted Wikimedia HTTPS hosts.
Successful Commons API responses are persisted for 24 hours below the application
data directory. Retry delay prefers `Retry-After`, then `X-RateLimit-Reset`, then
bounded exponential backoff with jitter. Concurrent requests sharing endpoint,
query, offset, batch size, and metadata schema use one shielded HTTP task.

Caching requires an open project. Files are streamed into a temporary file,
hashed with SHA-256, and atomically stored under `cache/<prefix>/<hash>.<ext>`.
Identical bytes reuse the existing cache entry even when source names or file
extensions differ. Local sources must be inside configured library roots;
remote downloads must remain on trusted HTTPS hosts for their selected provider,
including the DVIDS media distribution host.

Each project stores cache metadata atomically in `cache/manifest.json`, including
content hash, relative path, size, timestamps, all known source records, and
optional perceptual fingerprints. Images use a 64-bit difference hash. Videos
use up to 12 difference hashes sampled every ten seconds through FFmpeg. Set
`FFMPEG_PATH` when FFmpeg is not available on `PATH`; fingerprint failures are
logged without failing an otherwise valid cache download. Existing manifest
entries are backfilled when the same content is cached again.
Multi-provider ranking uses these cached fingerprints after URL and metadata
normalization. Images within 8 differing dHash bits are treated as duplicates.
Videos must have the same number of sampled frames and an average distance of
at most 8 bits. Uncached results retain the existing URL/metadata behavior and
do not trigger downloads during search.
Aggregate search responses include `deduplication` statistics with candidate,
retained, fingerprinted, canonical duplicate, perceptual image duplicate, and
perceptual video duplicate counts plus the active thresholds.
Cleanup removes missing or expired entries first, then the least recently used
entries until the size limit is met. Cleanup requests default to `dryRun=true`;
send `dryRun=false` explicitly to delete files and update the manifest.

Reconciliation compares the manifest with actual cache files. It reports orphan
files and entries whose file is missing. It also defaults to dry-run; execution
deletes orphan files and removes missing entries from the manifest. Symlinks are
never followed or deleted.

## Media Dedup Benchmark

Keep licensed benchmark files in the ignored `benchmark-media/` directory and
copy `configs/media_dedup_benchmark.example.json` to a corpus manifest. Label
each pair with `mediaType`, `category`, both relative paths, and
`expectedDuplicate`. Run the benchmark from `backend`:

```powershell
.\.venv\Scripts\python.exe benchmark_media_dedup.py ..\configs\media_dedup_benchmark.json
```

The JSON report records each measured Hamming distance and recommends the
0-64 threshold with the best F1 score for every media-type/category group. Ties
prefer higher precision and then the lower, more conservative threshold. Video
pairs with different sampled-frame counts remain non-matches. A useful corpus
should contain re-encodes, resizes, brightness/color changes, crops, unrelated
lookalikes, static scenes, and clips with shared intros.

Collect the versioned Wikimedia/Pexels corpus with a descriptive
`WIKIMEDIA_USER_AGENT` and `PEXELS_API_KEY` configured:

```powershell
cd backend
.\.venv\Scripts\python.exe collect_media_dedup_corpus.py ..\benchmark-media\corpus-v2 --pairs-per-category 150
.\.venv\Scripts\python.exe benchmark_media_dedup.py ..\benchmark-media\corpus-v2\benchmark.json --output ..\benchmark-media\corpus-v2\report.json
```

Corpus v2 is a historical benchmark containing 900 labeled pairs across six
categories, including Kids. Kids is no longer part of the active product scope;
runtime thresholds and the approval gate cover News, Documentary, History,
Education, and Podcast.
Every category includes Wikimedia and Pexels sources. Source attribution and
licenses are retained in `provenance.json`. The approved thresholds are versioned in
`configs/media_dedup_thresholds.json`. Pass `contentCategory` to aggregate media
search to select a calibrated image/video threshold; omitted or unknown
categories use the conservative default of eight.

`scripts/check_backend.ps1` also runs the committed approval gate. It verifies
all 10 active category/media groups remain above approved recall coverage and below
the nearest hard-negative distance, preventing threshold changes that reduce
the approved precision floor.

Corpus v3 extends every category to eight video sources: four Wikimedia, two
Pexels, and two Pixabay. It keeps 150 pairs per category while increasing video
coverage from 16 to 30 pairs. Prepare and inspect near-threshold hard negatives:

```powershell
cd backend
.\.venv\Scripts\python.exe review_media_hard_negatives.py prepare ..\benchmark-media\corpus-v3\benchmark.json ..\benchmark-media\corpus-v3\review-queue.json --thresholds ..\configs\media_dedup_thresholds.json --margin 5
.\.venv\Scripts\python.exe review_media_hard_negatives.py status ..\benchmark-media\corpus-v3\review-queue.json
.\.venv\Scripts\python.exe review_media_hard_negatives.py apply ..\benchmark-media\corpus-v3\review-queue.json
```

For every queue item, inspect both files and replace `pending` with
`confirmed_distinct`, `confirmed_duplicate`, or `excluded`; also set
`reviewedBy` and optional notes. Apply is atomic and refuses incomplete queues.
Corpus v3 review completed with three `confirmed_distinct` decisions and no
pending items. Its reviewed benchmark now backs the runtime thresholds and
committed approval baseline.

## Timeline Foundation

Phase 5 begins with project-scoped Timeline models, validation, and atomic JSON
persistence. Timeline scenes reference imported scene IDs; media and subtitle
clips use absolute milliseconds and independent layers. The validator enforces
scene and clip boundaries, layer overlap rules, media hashes, and video source
duration before `timeline/timeline.json` is written.

After importing a TXT or SRT script, create and edit the initial timeline through
the desktop Timeline workspace. The corresponding API supports loading at
`GET /api/timeline`, generation at `POST /api/timeline/generate`, and validated
replacement at `PUT /api/timeline`.

Cached image and video files can be assigned from the Timeline inspector. The
picker loads `GET /api/timeline/media-assets`; selecting or clearing an asset
updates the primary scene clip through
`PUT /api/timeline/scenes/{sceneId}/media`. Timeline files retain the cache
content hash rather than a provider URL.

Timeline schema v2 exposes separate B-roll and Avatar selectors for each scene,
keeps subtitle editing on its own track, and adds project-wide background music.
Music accepts cached Local Library audio in AAC, FLAC, M4A, MP3, OGG, or WAV
format, loops across the timeline, and provides a normalized volume control.
Existing schema v1 timelines migrate automatically when loaded and are written
as v2 on their next save.

Cached videos are inspected with FFprobe. Set `FFMPEG_PATH` to an FFmpeg binary
whose directory also contains FFprobe, or make both tools available on `PATH`.
Verified duration enables source in/out trimming in the Timeline inspector.
Opening a project automatically starts a background scan for legacy cached
videos. The Timeline toolbar shows progress and supports cooperative cancellation;
its Backfill command can safely resume remaining files. Completed probes are
preserved and unreadable files are reported without stopping the batch.

## Render Engine

Phase 6 renders the active Timeline v2 document into an MP4 file through FFmpeg.
Set `FFMPEG_PATH` to a concrete FFmpeg binary when it is not available on
`PATH`. FFprobe must also be available beside that binary or on `PATH`. Before a
job is queued, render preflight verifies FFmpeg/FFprobe availability, timeline
duration and layer consistency, referenced cache assets, and write access to the
active project's `output` directory. Failed preflight checks return clear API
errors without adding a durable queue entry.

The render service writes atomically into the active project's `output`
directory after preflight succeeds.

```text
POST /api/render/preflight
POST /api/render/jobs
GET  /api/render/jobs
GET  /api/render/jobs/{jobId}
POST /api/render/jobs/{jobId}/resume
POST /api/render/jobs/{jobId}/retry
POST /api/render/jobs/{jobId}/cancel
POST /api/render/jobs/{jobId}/review
DELETE /api/render/jobs/{jobId}/review
POST /api/render/jobs/report
POST /api/render/jobs/report/bundle
POST /api/render/jobs/report/bundle/import-review
GET  /api/render/jobs/report/bundle/imports
POST /api/render/jobs/report/bundle/imports/compare
POST /api/render/jobs/report/bundle/imports/compare/report
GET  /api/render/jobs/report/bundle/imports/compare/reports
POST /api/render/jobs/report/bundle/imports/compare/reports/preview
POST /api/render/jobs/report/bundle/imports/compare/reports/pin
POST /api/render/jobs/cleanup
```

Request body:

```json
{
  "profileId": "standard",
  "outputNameTemplate": "{project}-{datetime}.mp4",
  "width": 1920,
  "height": 1080,
  "frameRate": 30,
  "crf": 18,
  "encoderPreset": "medium",
  "audioBitrateKbps": 192
}
```

`fileName` remains accepted for compatibility. New requests can use
`outputNameTemplate` with `{project}`, `{title}`, `{date}`, `{time}`, and
`{datetime}` placeholders; the resolved name is sanitized and written as an MP4
inside the active project's `output` directory.

The composer creates an H.264/AAC MP4 from configurable export settings.
`GET /api/render/profiles` returns named profiles for the UI:

- `draft`: 854x480, 24 FPS, CRF 28, `veryfast`, 128 kbps audio.
- `standard`: 1920x1080, 30 FPS, CRF 18, `medium`, 192 kbps audio.
- `high_quality`: 1920x1080, 30 FPS, CRF 16, `slow`, 256 kbps audio.
- `archive`: 3840x2160, 30 FPS, CRF 14, `slower`, 320 kbps audio.

Explicit width, height, frame rate, CRF, preset, or bitrate fields can override
the selected profile; the persisted job then records the resolved settings as
`custom`. B-roll fills the selected frame, Avatar clips are overlaid in the
lower-right corner, subtitles use the timeline text, and Local Library music is
trimmed or looped across the project. Supported x264 presets are `ultrafast`,
`superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, and
`veryslow`. When `RENDER_SUBTITLE_MODE=prerender`, subtitle overlay generation
uses `RENDER_SUBTITLE_OVERLAY_FPS`, defaulting to 8 FPS and capped by the
selected render FPS, so cold subtitle preparation does less duplicate frame
work before FFmpeg starts the final MP4 pass.
The desktop Render workspace starts background jobs, polls progress, displays
the durable project queue, and can cancel queued, preparing, or running work.
Queue metadata is stored atomically in `render/jobs.json`. The queue shows
`preparing` as "Preparing subtitles" while subtitle overlays are generated or
loaded before FFmpeg progress starts. If the backend exits while a job is
preparing or running, the next queue load marks it as `interrupted`; Resume rebuilds
the FFmpeg plan from the current Timeline/cache and queues that output again.
Queued jobs survive backend restarts and continue in creation order.
The workspace also shows a preflight report grouped by Tool, Timeline, Media,
and Output, and blocks new render jobs until all groups pass. Failed groups
include quick actions: Tool shows FFmpeg/FFprobe setup guidance, Timeline opens
the Timeline workspace, Media opens the media assignment workspace, and Output
opens the active project workspace.
Completed jobs also persist a lightweight output preview. The backend writes a
best-effort thumbnail to `render/previews/{jobId}.jpg` and stores output
duration, size, resolution, frame rate, and preview generation time in
`render/jobs.json`. Thumbnail generation failures do not fail the completed job;
the Render workspace still shows the saved metadata for quick review.
When an output MP4 path is available, the Render workspace also shows an inline
playback panel using that file, with the generated thumbnail as the poster and
the same metadata beside it.
Completed outputs can be marked `accepted` or `rejected` with an optional
review note. The review is saved into the durable job history so the decision
survives backend and desktop restarts. The Render workspace queue can filter
history by accepted, rejected, or not-reviewed outputs for faster review passes.
It can also sort the visible queue and bulk mark selected completed outputs as
accepted or rejected through the same durable review endpoint. Large histories
can be searched and paged in the desktop queue without changing the durable
render API. A saved review can be reverted through
`DELETE /api/render/jobs/{jobId}/review`, returning the job to the not-reviewed
state while keeping the render output and diagnostics intact.
For handoff, `POST /api/render/jobs/report` exports the durable queue history as
CSV or JSON under `render/reports/`, including output paths, review state, notes,
profile, duration, size, status, and error fields. The optional request filters
`reviewStatus` (`all`, `accepted`, `rejected`, `not_reviewed`) and `jobStatus`
(`all`, `queued`, `preparing`, `running`, `cancelling`, `completed`,
`cancelled`, `failed`, `interrupted`) limit the exported rows. `dateFrom` and
`dateTo` optionally limit
the report by each job's `updatedAt` timestamp; date-only values include the
whole UTC day. All filters are persisted into JSON report metadata. The desktop
Render workspace shows accepted, rejected, not-reviewed, and render-status
summary counts, can export either format with those filters, and can open the
generated report or its containing folder. After export, the workspace shows the
exact filters and date range used for the generated report, and the filter panel
can be reset to the default all-history view. Report filenames include a readable
filter/date suffix when filters are active, and the workspace can copy the local
report path for handoff notes or external review trackers. For batch review,
`POST /api/render/jobs/report/bundle` creates a handoff folder under
`render/reports/bundles/` using the same filters. Each bundle contains
`render-queue-report.csv`, `render-queue-report.json`, a `manifest.json` summary,
and a `thumbnails/` folder with any available output preview thumbnails copied
from completed jobs. The manifest also includes a reviewer checklist for each
job with audio, subtitle, visual, metadata, and final-decision fields. A `.zip`
archive is created beside the bundle folder for transfer. The Render workspace
can create the bundle, open its folder or zip archive, and copy either path.
When a reviewer updates `manifest.json`, `POST
/api/render/jobs/report/bundle/import-review` reads that manifest back from the
active project's bundle folder and applies only `accepted` or `rejected`
decisions to completed render jobs. Blank, `not_reviewed`, missing, or
non-reviewable jobs are skipped and reported in the import summary. The Render
workspace also shows per-item import diagnostics so reviewers can see each
applied or skipped job ID, decision, and correction reason. Skipped diagnostics
can be filtered, copied, or downloaded as CSV for quick manifest correction.
Each import also writes a JSON audit report under `render/reports/imports/`
and returns that path to the Render workspace for copy/open actions. The
workspace lists prior import audit reports so multiple review-bundle imports can
be compared by timestamp and applied/skipped counts. Operators can select two
audit reports and compare job decision or skipped-reason changes side by side.
The comparison view can filter changed, added, or removed job rows and save the
currently visible diff as CSV or JSON under
`render/reports/import-comparisons/` for reviewer handoff. Saved comparison
reports are also listed back in the Render workspace so prior handoff files can
be searched, filtered, previewed, opened, or copied without manually browsing
the project folder. Important comparison reports can be pinned; pins are stored
project-side in `render/reports/import-comparisons/favorites.json` and pinned
reports sort above the rest of the history. The comparison report preview also
supports quick handoff actions directly from the preview view: copy the visible
CSV, download it as a local CSV file, or print the preview table.
Completed, failed, cancelled, and interrupted history is capped to the latest
100 records whenever the queue is saved. `POST /api/render/jobs/cleanup` can
trim history immediately while preserving active queued/running jobs. Retry is
a quick alias for re-queueing a failed job.
`POST /api/render` remains available as a synchronous compatibility path.

The desktop Render workspace can open the rendered MP4 or its containing folder
through the Tauri shell after a job completes.

Each render job persists a compact diagnostics report in history. The report
captures a sanitized FFmpeg command summary, the resolved profile/settings
snapshot, render metrics such as elapsed time, return code, processed duration,
output size, and the last stderr characters from FFmpeg when available. This
keeps failed renders debuggable after a backend restart without storing a full
raw command line.

Run a small real FFmpeg/FFprobe smoke render for every named profile from
`backend`. The smoke also creates and asserts a non-empty preview thumbnail for
each successful output:

```powershell
.\.venv\Scripts\python.exe smoke_render_profiles.py
```

Run a small end-to-end workflow smoke from project creation through TXT import,
scene listing, timeline generation, render preflight, and Draft MP4 output:

```powershell
cd backend
.\.venv\Scripts\python.exe smoke_e2e_workflow.py
```

The Phase 6 closure checklist is tracked in
`docs/phase_6_render_engine_checklist.md`.
The Phase 7 UI closure checklist is tracked in
`docs/phase_7_ui_closure_checklist.md`.

Phase 8 adds integration smoke checks that use richer generated local media and
packaged desktop artifacts:

```powershell
.\scripts\smoke_phase8_rich_workflow.ps1
.\scripts\smoke_phase8_render_recovery.ps1
.\scripts\smoke_phase8_packaged_render_recovery.ps1
.\scripts\smoke_phase8_installed_app.ps1
.\scripts\smoke_phase8_installed_app_msi.ps1
.\scripts\smoke_desktop_package.ps1
```

The MSI installed-app smoke uses the per-machine MSI package and must be run
from an elevated Administrator terminal. The NSIS installed-app smoke can run
silently in the workspace temp directory without that elevation requirement.

If a running backend already owns port 8765, the packaged smoke can check the
bundled sidecar on another port:

```powershell
.\scripts\smoke_desktop_package.ps1 -Port 9876
```

The Phase 8 integration checklist is tracked in
`docs/phase_8_integration_checklist.md`.

Phase 9 starts with a deterministic performance baseline for workflow, render,
and cache timing:

```powershell
.\scripts\benchmark_phase9_performance.ps1
```

The benchmark report is written to `.tmp\phase9-performance-matrix.json`.
The Phase 9 optimization checklist is tracked in
`docs/phase_9_optimization_checklist.md`.
The first render optimization reuses duplicate visual FFmpeg inputs so repeated
scene media no longer increases command input count.
Render diagnostics also summarize filter graph length and filter counts so
24+ scene render cost can be reviewed without storing raw local paths.
The matrix includes controlled render variants such as no subtitles, ASS
subtitle sidecar, pre-rendered subtitle overlay, no avatar, image-only,
video-only, and pre-scaled media for isolating FFmpeg costs.
`RENDER_SUBTITLE_MODE=ass` can be used to benchmark the ASS path, and
`RENDER_SUBTITLE_MODE=prerender` can be used to benchmark a transparent subtitle
overlay video. Pre-rendered overlays are cached per project by subtitle
timeline/settings hash for repeat exports. Drawtext remains the default because
the current local matrix shows ASS increasing render time and cold pre-rendering
increasing total render rollup despite improving the main FFmpeg pass.
Cold subtitle pre-render runs in the render queue worker, so creating a render
job remains responsive even when the worker still needs to generate the cached
overlay before FFmpeg starts.

## Quality Checks

```powershell
.\scripts\check_all.ps1
```

If PowerShell blocks local scripts, run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\check_all.ps1
```

The CI workflow runs backend lint/type-check/test and frontend test/build.
