# ARCHITECTURE.md

Version: 1.0

Project: AI Video Pipeline Studio

Status: Architecture Baseline

---

# 1. Architecture Philosophy

## Objective

Xây dựng một ứng dụng Desktop chuyên nghiệp để tự động sản xuất video bằng AI.

Kiến trúc phải:

- dễ mở rộng
- dễ bảo trì
- dễ kiểm thử
- độc lập từng module
- hỗ trợ Plugin
- hỗ trợ AI Agent phát triển

Không tối ưu cho MVP bằng cách đánh đổi kiến trúc.

---

# 2. Core Principles

Áp dụng:

- Clean Architecture
- SOLID
- Repository Pattern
- Dependency Injection
- Domain Driven Design (Lite)
- Event Driven Pipeline

---

# 3. High Level Architecture

                        User
                          │
                          ▼
               React + Tauri UI
                          │
                          ▼
                FastAPI Application
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
  Project Engine     AI Engine        Pipeline Engine
        │                 │                  │
        ▼                 ▼                  ▼
 Database          AI Providers      Media Engine
                                           │
                                           ▼
                                   Render Engine
                                           │
                                           ▼
                                        FFmpeg

---

# 4. Technology Stack

Frontend

- React
- TypeScript
- Tauri

Backend

- Python 3.12+
- FastAPI

Database

- SQLite

Video

- FFmpeg

AI

- Gemini
- OpenAI
- Ollama (optional)

Storage

- Local Filesystem

Testing

- Pytest
- Vitest

---

# 5. Folder Structure

AI-Video-Pipeline/

    backend/

        app/

            api/

            services/

            repositories/

            models/

            pipeline/

            ai/

            media/

            render/

            project/

            config/

            utils/

            main.py

    frontend/

        src/

            components/

            pages/

            hooks/

            store/

            services/

            layouts/

            App.tsx

    shared/

    tests/

    assets/

---

# 6. Backend Layers

API Layer

↓

Application Layer

↓

Domain Layer

↓

Infrastructure Layer

---

## API Layer

Chỉ:

- nhận request
- validate
- trả response

Không có business logic.

---

## Application Layer

Điều phối workflow.

Ví dụ

RenderService

ProjectService

MediaSearchService

---

## Domain Layer

Chứa:

- Entity
- Business Rule
- Value Object

Không phụ thuộc framework.

---

## Infrastructure Layer

Bao gồm:

- SQLite
- File Storage
- FFmpeg
- AI SDK
- External APIs

---

# 7. Project Engine

Chịu trách nhiệm:

- Create Project
- Save
- Load
- Auto Save
- Export

Project Structure

project/

    project.json

    script/

    media/

    cache/

    render/

    output/

---

# 8. AI Engine

Nhiệm vụ

- Prompt Management
- Keyword Generation
- Scene Analysis
- Script Analysis
- Retry
- Rate Limit

AI Provider Interface

AIProvider

↓

Gemini

↓

OpenAI

↓

Ollama

Mọi Provider đều implement cùng interface.

---

# 9. Pipeline Engine

Pipeline chuẩn

Script

↓

Scene Detection

↓

Keyword Generation

↓

Media Search

↓

Download

↓

Cache

↓

Compose

↓

Render

↓

Export

Mỗi bước là một module độc lập.

---

# 10. Media Engine

Chức năng

- Search
- Download
- Cache
- Validate
- Metadata

Provider

MediaProvider

↓

Pixabay

↓

Pexels

↓

Local Library

↓

Custom Provider

Không để Provider phụ thuộc nhau.

---

# 11. Avatar Engine

Input

Avatar Video

↓

Lip Sync

↓

Overlay

↓

Position

↓

Export Layer

MVP chỉ hỗ trợ overlay avatar.

Lip Sync nâng cấp sau.

---

# 12. Subtitle Engine

Đầu vào

TXT

↓

SRT

↓

ASS (optional)

↓

Render Layer

Hỗ trợ:

- Font
- Size
- Color
- Shadow
- Outline

---

# 13. Music Engine

Chức năng

- Background Music
- Fade In
- Fade Out
- Loop
- Volume Normalize

---

# 14. Render Engine

Compose

↓

Timeline

↓

FFmpeg Command

↓

Progress

↓

Export

Không sinh command FFmpeg trực tiếp trong UI.

---

# 15. Queue Engine

Render Queue

↓

Task Queue

↓

Worker

↓

Progress

↓

Completed

Thiết kế để sau này mở rộng nhiều Worker.

---

# 16. Database Design

SQLite

Các bảng chính

Project

Scene

Media

Keyword

RenderJob

History

Log

Repository Pattern bắt buộc.

Không truy cập DB trực tiếp từ Service.

---

# 17. Configuration

Tất cả cấu hình

.env

configs/

Không hard-code.

---

# 18. Logging

Mọi module

↓

Logger

↓

File

↓

Console

↓

Future Cloud Logger

Không dùng print().

---

# 19. Error Flow

Module

↓

Exception

↓

Error Handler

↓

Logger

↓

UI Notification

Không swallow exception.

---

# 20. Dependency Rules

UI

↓

Application

↓

Domain

↓

Infrastructure

Không import ngược.

---

# 21. Plugin Architecture

Plugin

↓

Manifest

↓

Loader

↓

Registry

↓

Service

Plugin chỉ giao tiếp qua interface.

Không truy cập trực tiếp module nội bộ.

---

# 22. Event Flow

Ví dụ

Import Script

↓

Scene Generated

↓

Keyword Generated

↓

Media Downloaded

↓

Timeline Built

↓

Render Started

↓

Render Finished

Event giúp giảm coupling.

---

# 23. Thread Model

Main Thread

↓

UI

Background Thread

↓

AI

↓

Download

↓

Render

Không block UI.

---

# 24. Future Scaling

Version 2

- Redis Queue

- PostgreSQL

- Plugin Marketplace

Version 3

- Cloud Rendering

- Multi Machine Rendering

- Team Collaboration

Không thay đổi kiến trúc gốc.

---

# 25. Architecture Decision

Ưu tiên

1. Maintainability
2. Modularity
3. Testability
4. Scalability
5. Performance

Không tối ưu sớm.

---

# 26. Definition of Done

Một module kiến trúc được coi là hoàn thành khi:

- độc lập
- có interface rõ ràng
- có unit test
- không vi phạm RULES.md
- không tạo phụ thuộc vòng
- dễ mở rộng

---

---

# 27. Desktop Sidecar Lifecycle

The desktop runtime owns the local backend process:

```text
React UI
    â†“
Tauri Process Manager
    â†“
Bundled FastAPI Sidecar (127.0.0.1:8765)
```

Tauri starts the self-contained FastAPI binary before the UI becomes available,
waits for the Uvicorn ready signal, and terminates the child process when the
desktop application exits. End users do not need a Python installation.

---

# 28. Project Core Persistence

Project Core follows the required dependency flow:

```text
Projects API
    â†“
ProjectService
    â†“
ProjectRepository
    â†“
SQLite metadata + project.json
```

`project.json` is the portable source of project state and is replaced
atomically on every mutation. SQLite stores the project index and recent-open
ordering in the application data directory. The initial `projects` table uses
the following fields: `id`, `name`, `path`, `created_at`, `updated_at`, and
`last_opened_at`.

Every project directory contains `script`, `media`, `cache`, `render`, and
`output`. Services never access SQLite directly; all persistence is owned by
`SQLiteProjectRepository`.

---

# 29. Script and Scene Flow

The initial Script Engine flow is:

```text
Scripts API
    â†“
ScriptService
    â†“
SubtitleParser (SRT only)
    â†“
FileScriptRepository
    â†“
script/source.* + script/manifest.json
```

Only UTF-8 TXT and SRT files up to 5 MB are accepted. The repository owns file
I/O and atomic replacement; the service owns format selection and workflow;
the parser owns SRT domain validation. Scene splitting and persistence are
described in the next section.

# 30. Scene Persistence

SceneParser converts TXT paragraphs or SRT cues into editable scenes. The
scene list is atomically stored in `script/scenes.json` and retains stable
identity, order, subtitle cue references, and timing during text edits.

# 31. AI Provider Foundation

The AI Engine dependency flow is:

```text
AI API -> SceneAnalysisService -> PromptManager -> PromptRepository
                              -> AIProviderRegistry -> provider adapter
                              -> SceneAnalysisParser
                              -> SceneAnalysisRepository -> script/analysis.json
```

Prompts are versioned and validate placeholders before rendering. Provider
adapters share asynchronous request, response, message, and token-usage models.
Credentials remain outside these contracts and come from environment settings.

# 32. Scene Analysis and Ollama

Ollama uses its local asynchronous chat API with a JSON response schema. The
service owns orchestration, the provider owns HTTP translation, the parser owns
response validation, and the repository owns atomic persistence. Each result
stores a SHA-256 hash of its source scene text; reads exclude stale results when
the scene has since changed.

# 33. Retry and OpenAI Provider

Each provider adapter is wrapped by `RetryingAIProvider`. Retry is limited to
transient timeout, availability, rate-limit, and server errors, using bounded
exponential backoff. Permanent configuration, authentication, model, request,
and response errors fail immediately.

`OpenAIProvider` implements the same provider protocol through the Responses
API and strict JSON schema output. API keys are read only from
`OPENAI_API_KEY`; they are never included in project files or logs.

# 34. Batch Scene Analysis

Batch analysis processes scenes sequentially to respect local compute and
provider rate limits. Valid results are skipped by default for resumability,
while `reanalyze` forces regeneration. Every successful scene is persisted
immediately. Per-scene failures are returned without discarding partial
progress; global provider configuration errors stop the remaining batch early.

# 35. Media Search and Local Library

The initial Media Engine search flow is:

```text
Media API -> MediaSearchService -> MediaProviderRegistry
                                -> MediaSearchProvider
                                -> LocalLibraryProvider -> configured directories
```

Provider contracts expose normalized queries, paginated pages, media types,
stable IDs, source/preview URIs, basic file metadata, and relevance scores.
Local search runs outside the async event loop, ignores symlinks and unsupported
files, prevents resolved paths from escaping configured roots, and bounds the
number of regular files inspected. It does not decode media or read file bodies.

# 36. Pexels Search and Content Cache

Pexels implements the existing `MediaSearchProvider` contract for photos and
videos. Credentials come only from `PEXELS_API_KEY`; errors are normalized
before crossing the provider boundary. Results preserve creator and source-page
metadata required for attribution.

```text
Media Cache API -> MediaCacheService -> active project/cache
                                  -> local file stream or trusted HTTPS stream
                                  -> SHA-256 content address
```

The cache streams data through a bounded temporary file and atomically promotes
it after hashing. The hash is the duplicate key, independent of provider,
source filename, and extension. Local paths are restricted to configured media
roots, while remote Pexels sources and redirect destinations are restricted to
trusted Pexels HTTPS hosts.

# 37. Cache Manifest and Cleanup

Every project cache has an atomically replaced `manifest.json`. Entries retain
the content hash, relative cache path, byte size, creation/access timestamps,
and all known provider sources. Cache hits refresh access time and add source
provenance without duplicating content.

Cleanup is deterministic and project-scoped. It first selects stale, missing,
or expired entries, then removes least-recently-used entries until the configured
size budget is met. The API defaults to dry-run; execution requires an explicit
`dryRun=false`. Manifest paths are resolved and verified inside the active
project cache before deletion.

# 38. Pixabay and Cache Reconciliation

`PixabayProvider` implements the shared photo/video search contract and caches
successful API responses in-process for 24 hours. SafeSearch is always enabled.
Because Pixabay authenticates with a query parameter, HTTP client request logs
are disabled below WARNING to prevent credentials from entering application
logs. Download URLs are restricted to trusted Pixabay HTTPS hosts.

`MediaCacheReconciliationService` compares each project manifest with regular
files below its cache root. It reports unreferenced orphan files and manifest
entries whose files are missing. Dry-run is the default; execution removes only
verified in-root orphan files and atomically prunes missing entries. Symlinks
are ignored during scanning and rejected in manifest paths.

# 39. Pixabay Persistent Search Cache and Retry

Pixabay search responses are atomically persisted below the application data
directory using SHA-256 keys derived from normalized request fields. Credentials
are excluded from both cache keys and files. Entries remain valid for the
configured 24-hour default across backend and desktop restarts; expired files
are pruned lazily when a provider instance first searches.

Pixabay retries only transient connection/timeout failures, HTTP 429, and 5xx
responses. Backoff prefers `Retry-After`, then `X-RateLimit-Reset`, and finally
bounded exponential delay. Attempts and maximum delay are configured and finite;
authentication and request validation failures are never retried.

# 40. Pixabay Jitter and Request Coalescing

Exponential fallback applies bounded positive jitter configured by
`PIXABAY_RETRY_JITTER_RATIO`; explicit provider rate-limit headers are not
shortened. This spreads retries without violating requested cooldown periods.

Pixabay requests are coalesced per normalized persistent-cache key. Concurrent
scenes awaiting the same query/page/media type share one in-flight async task.
The task owns its HTTP client, is shielded from individual caller cancellation,
and removes itself after success, failure, or cancellation. Cache persistence
runs once for the shared result.

# 41. Wikimedia Commons Provider

`WikimediaCommonsProvider` uses the MediaWiki Action API without credentials.
Search is restricted to namespace 6 and combines the search generator with
`imageinfo`, so each response provides source and preview URLs, MIME type, byte
size, timestamp, license, creator, and description-page attribution metadata.
HTML-bearing extended metadata is reduced to text and the first creator link
before crossing the provider boundary.

The adapter accepts image and video MIME types and skips unrelated Commons file
types. It follows MediaWiki continuation until the requested page is filled,
with a ten-batch upper bound. Requests require a configurable identifying
User-Agent containing operator contact information; no placeholder identity is
shipped in production defaults.
Project-cache downloads and redirect destinations are limited to Wikimedia HTTPS
hosts and continue to use the shared SHA-256 manifest pipeline.

# 42. Shared Search Cache and Wikimedia Resilience

Provider-specific search cache repositories define canonical cache keys while
`JsonSearchCacheRepository` owns schema validation, TTL expiry, atomic JSON
replacement, corruption cleanup, and process-level locking. Pixabay retains its
existing repository contract; Wikimedia keys include endpoint, normalized query,
continuation offset, batch size, namespace, and metadata schema version.

`HttpRetryPolicy` centralizes bounded exponential delay, positive jitter,
`Retry-After`, `X-RateLimit-Reset`, and transient-status classification for
Pixabay and Wikimedia. Wikimedia persists only successful responses and treats
cache read/write failures as recoverable diagnostics. Identical in-flight cache
keys share one shielded task and one HTTP client; cancellation by an individual
caller does not cancel provider work used by other callers.

# 43. DVIDS Hub Provider

`DvidsProvider` implements the shared image/video search contract over the
official DVIDS JSON API. Credentials come only from `DVIDS_API_KEY`. The adapter
queries `/search` separately by media type and respects the API's 50-item page
limit. Search results stay lightweight: they return summary metadata and a
backend-only `dvids://asset/...` source token instead of resolving `/asset`
details during search. The Media Cache service resolves that token through the
same DVIDS adapter only when the user chooses to cache/download the asset,
because downloadable original image and MP4 URLs are not part of the search
summary contract.
Video assets expose renditions through `files[].src` with MIME type, dimensions,
byte size, and bitrate. The provider selects the highest-resolution rendition;
video thumbnails are normalized from their nested `url` field.
Selection is constrained by `DVIDS_VIDEO_QUALITY` (`highest`, `1080p`, or
`720p`) and optional `DVIDS_VIDEO_MAX_FILE_SIZE_BYTES`. Resolution modes are
upper bounds and gracefully select a lower available rendition. When a byte
limit is active, unknown-size and oversized files are ineligible. Ties at the
same resolution prefer the larger file as the higher-quality representation.

Normalized results retain creator credit, creator portfolio, timestamp,
thumbnail, DVIDS asset page, and the qualified public-domain notice. API keys
never cross the provider boundary. Project-cache downloads and redirects are
restricted to DVIDS HTTPS domains and its documented original-media CloudFront
distribution.

# 44. DVIDS Persistent Cache and Request Resilience

`DvidsSearchCacheRepository` derives provider-specific keys from endpoint,
non-secret request parameters, and response schema version. It explicitly drops
`api_key` before canonicalization. Both `/search` summaries and `/asset` details
use the shared atomic JSON cache, so a warm query avoids the asset hydration
request fan-out as well as the initial search request.
Search summaries and asset details have independent TTLs. Asset entries default
to one hour and are lazily removed/refetched on access, while search entries
retain the 24-hour default. Asset TTL is constrained not to exceed search TTL;
this refreshes publication status and rendition metadata more frequently without
discarding useful search pagination state.

DVIDS uses `HttpRetryPolicy` for transient connections/timeouts, HTTP 429, and
5xx responses. Delay priority is `Retry-After`, `X-RateLimit-Reset`, then bounded
exponential jitter. Requests are coalesced by persistent-cache key; the shared
task owns its HTTP client and is shielded from individual caller cancellation.
Authentication and validation failures are not retried or cached.

DVIDS asset HTTP 403/404 responses use a separate negative-cache directory and
a five-minute default TTL. The sentinel stores only status metadata and uses the
same secret-free asset key. Negative hits skip unavailable assets while allowing
search hydration to continue. Search authentication errors and transient
failures never enter negative cache. Its TTL must not exceed the positive asset
TTL, bounding how long restored or republished content can remain hidden.

# 45. Multi-Provider Media Ranking and Deduplication

`providerId=all` is a virtual provider resolved by `MediaSearchService`; existing
single-provider behavior and the `local` default remain unchanged. Aggregate
search fans out concurrently to every registered provider with a bounded
per-provider result window of at least five and at most 100 items. Provider failures are isolated and returned as
typed `providerErrors`; aggregate search fails only when every provider fails.

`MediaResultRanker` converts provider-local positions into a comparable score:
75 percent reciprocal rank and 25 percent clamped provider score. Stable ties
use provider and media IDs. Deduplication runs after ranking so the highest-ranked
representative wins. Identity keys include canonical source URL, canonical
source page, and media type/title/file-size metadata when size is known. URL
canonicalization removes fragments and tracking/signature parameters while
preserving query parameters that may identify distinct assets.

Offset/limit slicing occurs after ranking and deduplication. Aggregate
`totalResults` is the pre-deduplication sum reported by successful providers;
`truncated` indicates additional provider data, partial failure, or remaining
ranked items beyond the requested page.

# 46. Project Media Fingerprints

`MediaFingerprintService` enriches content-addressed cache entries without
changing SHA-256 exact deduplication. Images receive a versioned 64-bit dHash
after grayscale normalization to 9x8 pixels. Videos receive a versioned sequence
of up to 12 dHashes from grayscale 9x8 frames sampled every ten seconds by
FFmpeg. Versioned prefixes keep future algorithm migrations explicit.

Fingerprint computation runs outside the manifest lock and is best-effort: a
decoder, timeout, or FFmpeg failure is logged but does not invalidate a verified
cache download. Manifest fields are optional so schema version 1 files remain
readable. When identical content is cached again, entries missing fingerprint
metadata are lazily backfilled while preserving timestamps and source provenance.

# 47. Perceptual Multi-Provider Deduplication

Aggregate search loads one cache-manifest snapshot from the active project and
passes it to `MediaResultRanker`. The ranker builds an in-memory index keyed by
provider/media ID and canonical source URI; search never downloads or decodes
media to perform deduplication. Missing, unavailable, or invalid cache manifests
fall back to the existing URL/page/metadata identity rules.

After score ordering, an image is suppressed when its 64-bit dHash has Hamming
distance at most eight from a retained image. Video sequences must contain the
same number of sampled frames and have average per-frame Hamming distance at
most eight. Comparison is limited to matching media types and algorithm-version
prefixes. The highest-ranked representative is retained, keeping output stable.

# 48. Deduplication Observability and Calibration

Aggregate `MediaSearchPage` responses expose immutable deduplication statistics:
candidate and retained counts, fingerprint coverage, canonical duplicates,
perceptual image/video duplicates, and active thresholds. Single-provider pages
retain `deduplication=null` because cross-provider ranking is not applied.

`MediaFingerprintBenchmark` uses the same production Hamming-distance functions
against a labeled corpus of real local media pairs. It measures every pair once,
sweeps thresholds from zero through 64, and reports confusion counts, precision,
recall, F1, and a recommended threshold for each media-type/category group. Ties
favor precision and then the lower threshold. Corpus media and generated reports
are ignored by Git; only the schema example and deterministic runner are tracked.

# 49. Calibrated Category Thresholds

`BenchmarkCorpusCollector` gathers license-bearing Wikimedia sources with a
policy-compliant User-Agent, bounded image/video sizes, trusted redirect hosts,
and atomic corpus manifests. Each category receives balanced positive pairs from
re-encode, resize, brightness, and crop transformations and negative pairs from
distinct source assets. `provenance.json` preserves source page, creator, and
license metadata; corpus binaries remain outside Git.

`MediaDeduplicationThresholds` validates the versioned configuration in
`configs/media_dedup_thresholds.json`. Aggregate search accepts an optional
`contentCategory`, normalizes it case-insensitively, and selects independent
image/video thresholds. Unknown or omitted categories fall back to eight.
Thresholds used for each request remain visible in deduplication statistics.

# 50. Multi-Source Hard Negatives and Regression Gate

Corpus v2 combines Wikimedia Commons and Pexels sources while preserving each
provider's creator, license, and source-page attribution. Pexels credentials are
sent only in the API Authorization header. Downloads and redirects are bounded
by media size and restricted to provider-owned HTTPS hosts.

Negative generation fingerprints every distinct baseline source in a
category/media group, ranks all compatible cross-source combinations by Hamming
distance, and selects the nearest pairs as hard negatives. Corpus v2 contains
150 pairs per category and 450 hard negatives overall. Pair manifests record
selection distance, provider IDs, and the distinct-source-page label basis.

`media_dedup_approval.json` stores the approved maximum positive distance,
nearest negative distance, hard-negative count, corpus version, provider set,
and precision floor. `check_media_dedup_regression.py` runs in the backend
quality gate. A threshold fails if it falls below approved positive coverage or
reaches the nearest negative, which would introduce a known false positive.

# 51. Manual Hard-Negative Review and Third Video Source

Corpus v3 adds two Pixabay video sources per category alongside four Wikimedia
and two Pexels videos. Provider credentials remain environment-only; provenance
retains the Pixabay Content License, creator, and source page. Video coverage
increases to 30 labeled pairs per category without changing total pair balance.

`prepareHardNegativeReview` selects negative pairs whose measured distance is
within a configurable margin above the active threshold. Its versioned queue
contains both relative media paths, provider IDs, distance, threshold, and an
explicit review state. Reviewers must choose `confirmed_distinct`,
`confirmed_duplicate`, or `excluded` and identify themselves. Atomic apply is
blocked while any item remains pending; accepted decisions update labels or
remove excluded pairs before benchmark and approval regeneration.

An unreviewed corpus is never promoted automatically. Runtime thresholds and
the committed regression approval continue to reference the last fully approved
corpus until review, benchmark, and regression checks all pass.

# 52. Timeline Domain Foundation

Phase 5 stores one versioned `timeline/timeline.json` document inside each
project. Timeline positions use absolute milliseconds. Scenes reference the
canonical Script Engine scene IDs and contain immutable media and subtitle
clips arranged on non-negative layers.

`TimelineValidationService` rejects unknown or overlapping scenes, clips outside
their scene, duplicate clip IDs, same-layer overlap, invalid SHA-256 media
references, and video clips whose source range is too short. `TimelineService`
loads the active project's scene collection before every save and load, then
validates the aggregate before the file repository performs an atomic replace.

Kids Content is outside the active Version 1 scope. Historical benchmark data
may retain that category, but runtime thresholds and approval gates do not.

# 53. Timeline API and Initial Editor

`InitialTimelineService` converts the active project's scene collection into a
continuous timeline. SRT scenes retain their source duration; TXT scenes use a
bounded word-rate estimate. Every initial scene receives one subtitle clip that
covers its full duration.

The FastAPI timeline router exposes `GET /api/timeline`,
`POST /api/timeline/generate`, and `PUT /api/timeline`. Routers only translate
typed requests and responses; generation, validation, and persistence remain in
application services and repositories.

The Tauri React workspace provides a scene-level editor for duration and
subtitle text. Duration changes reflow later scenes and preserve clip-relative
positions. The editor intentionally does not implement rendering or advanced
track operations in Phase 5.

# 54. Cached Media Assignment

`TimelineMediaService` bridges the completed Media Engine cache and Timeline
Engine without copying cache logic into the UI. It lists only supported files
that still exist under the active project's validated cache root. Selection is
stored by SHA-256 content hash, so timeline references remain stable across
provider aliases and cache manifest reloads.

`GET /api/timeline/media-assets` returns selectable image/video assets and
`PUT /api/timeline/scenes/{sceneId}/media` assigns or removes the scene's primary
layer-zero clip. Existing overlay layers remain unchanged. The React inspector
uses these endpoints and never writes media clips directly.

Images and videos initially cover the full scene. Video assignment requires
verified source duration metadata and rejects assets shorter than the scene.

# 55. FFprobe Metadata and Video Trimming

Video cache writes invoke `MediaMetadataService`, resolving FFprobe beside the
configured FFmpeg binary or from `PATH`. Positive duration in milliseconds is
stored as optional, backward-compatible manifest metadata. Probe failures are
logged without discarding the cached file, but unverified or too-short videos
cannot be assigned to a Timeline scene.

The editor exposes source in/out controls for verified videos. Trim updates use
`PUT /api/timeline/scenes/{sceneId}/media-trim`; the service bounds the range by
the probed source duration and the Timeline validator ensures the selected range
is at least as long as the timeline clip.

# 56. Legacy Video Metadata Backfill

`MediaCacheService.backfillVideoMetadata` scans the active project manifest and
probes video and audio entries without duration. Successful updates are committed in
one atomic manifest write; existing metadata is skipped and per-file failures
are reported without aborting the remaining batch. The operation is idempotent
and exposed at `POST /api/media/cache/metadata/backfill` and in the Timeline
toolbar.

# 57. Background Metadata Backfill Jobs

`MediaMetadataBackfillService` runs one idempotent in-memory job per project and
captures the project cache path before starting its worker thread. Project open
starts the job automatically. Manual starts reuse an active job, while status
and cancellation endpoints let the desktop UI poll progress without blocking
FastAPI request handling.

Cancellation is cooperative between FFprobe calls. Successfully probed values
are merged into the latest manifest under the existing cache lock, preserving
cache entries added while the background scan was running. A backend restart
ends in-memory job state safely; the next project open resumes remaining work
because entries with duration metadata are skipped.

# 58. Timeline Schema V2 and Composer Layers

Timeline schema v2 adds explicit `broll` and `avatar` roles to visual clips and
project-wide audio clips for background music. B-roll occupies visual layer 0,
Avatar occupies visual layer 1, subtitles retain their independent scene layer,
and music uses audio layer 0. Validation enforces role/layer consistency, unique
clip IDs, timeline bounds, audio volume from 0 to 1, and valid source ranges.

`Timeline.fromDictionary` migrates schema v1 documents in memory. Existing
layer-zero clips become B-roll, higher visual layers become Avatar, and the new
audio collection starts empty. The next atomic save writes schema v2; unsupported
future schema versions remain rejected.

Local Library recognizes AAC, FLAC, M4A, MP3, OGG, and WAV. Cached audio receives
FFprobe duration metadata and is selectable as music only when its manifest has a
Local source. Music spans the full timeline, loops when shorter than the project,
and stores a normalized volume. `PUT /api/timeline/scenes/{sceneId}/media` accepts
a visual role, while `PUT /api/timeline/music` assigns, updates, or removes music.

# 59. Render Engine Foundation

`RenderService` resolves the active project, Timeline v2 document, and
content-addressed cache manifest before starting FFmpeg. It validates the output
file name, writes to a hidden temporary MP4 beside the final output, and uses an
atomic replace so failed renders do not corrupt the last good file.

Render preflight runs before a synchronous render or durable job is queued. It
requires FFmpeg and FFprobe to be resolvable, rejects non-renderable timelines
with invalid duration, layer, clip, or source-range state, verifies all timeline
media hashes exist in the project cache manifest and filesystem, and confirms
the output directory can be written. Preflight failures return typed render
errors and do not create `render/jobs.json` entries.

`POST /api/render/preflight` exposes the same checks as a grouped status report
without creating a render plan or queue entry. The desktop Render workspace uses
that report to show Tool, Timeline, Media, and Output readiness before enabling
new job submission. Failed groups expose narrow UI actions that either navigate
to the owning workspace or show setup guidance; the UI does not duplicate
backend validation rules.

`FFmpegCommandBuilder` composes an H.264/AAC command from the timeline and a
validated `RenderExportSettings` value object. Resolution, frame rate, x264 CRF,
x264 preset, and audio bitrate remain backend-owned settings, never UI-built
FFmpeg fragments. B-roll clips are scaled and padded to the selected full frame,
Avatar clips are scaled as a lower-right overlay, subtitles are emitted with
`drawtext`, and the first background music clip is trimmed, volume-adjusted, and
looped when needed.

Named render profiles are domain-owned presets: Draft, Standard, High Quality,
and Archive. API requests select a `profileId` and may optionally override
individual fields; if the resolved settings no longer match the named profile,
the persisted job records `profileId=custom` while retaining the exact export
settings used for resume and retry.

The FastAPI render router keeps `POST /api/render` as a synchronous compatibility
path and adds durable job endpoints: `POST /api/render/jobs`,
`GET /api/render/jobs`, `GET /api/render/jobs/{jobId}`,
`POST /api/render/jobs/{jobId}/resume`, and
`POST /api/render/jobs/{jobId}/cancel`.

`RenderJobService` owns a single background worker that processes queued jobs in
creation order. Queue metadata is persisted atomically to `render/jobs.json` in
the active project through `FileRenderJobRepository`. Queued jobs survive backend
restarts. Jobs persist the export settings used at creation. The worker marks a
job `preparing` while it materializes the full render plan, including subtitle
overlay generation or cache lookup, before FFmpeg starts. Jobs found in
`preparing`, `running`, or `cancelling` state after restart are marked `interrupted`; Resume
creates a fresh render plan from the current Timeline and cache state using the
job's resolved output file name and stored export settings, then places the job
back at the end of the active queue.

Each job snapshot may include `RenderDiagnostics`: a sanitized FFmpeg command
summary, the resolved settings snapshot, stderr tail, and render metrics such as
elapsed time, return code, processed duration, progress, and output size. The
diagnostics object is persisted with the queue history and is intentionally a
summary rather than a raw command dump, keeping production reports useful without
overexposing local paths.

Completed job snapshots may include `RenderOutputPreview`. The backend derives
metadata from the render result and export settings, then attempts to create a
small thumbnail under `render/previews/`. Preview generation is best-effort:
thumbnail failure records `thumbnail_unavailable` while preserving duration,
size, resolution, frame rate, and generation timestamp for the Render workspace.
The desktop Render workspace converts completed local output paths to file URIs
for inline MP4 playback and uses the preview thumbnail as the video poster. The
UI does not stream video through FastAPI or duplicate render metadata.

Completed job snapshots may also include `RenderReview` with `accepted` or
`rejected` status, an optional note, and a review timestamp. `POST
/api/render/jobs/{jobId}/review` saves that review state, while `DELETE
/api/render/jobs/{jobId}/review` clears it and returns the job to not-reviewed.
Review mutations are allowed only for completed jobs with an output path and are
stored in `render/jobs.json` with the rest of the durable history. The desktop
Render queue filters accepted, rejected, and not-reviewed jobs locally from the
loaded durable history; filtering, search, sorting, and pagination do not create
separate backend query paths. Bulk review and bulk revert use the same per-job
mutations for each selected completed output, keeping the backend contract narrow
until a larger batch API is justified.

`POST /api/render/jobs/report` exports the loaded durable queue history for
handoff. `RenderJobService` writes CSV or JSON atomically under
`render/reports/` in the active project and returns report metadata, summary
counts, and the local report path. The report includes job status, review status,
review note, output path, profile, duration, size, timestamps, and error fields;
it does not duplicate rendered media. Report export accepts backend-owned
`reviewStatus`, `jobStatus`, `dateFrom`, and `dateTo` filters, applies them
before writing the file, and stores the selected filters in JSON report
metadata. Date filters use each job's `updatedAt` timestamp, with date-only
values treated as whole UTC days. The desktop Render workspace computes small
review and render-status summary dashboards from the loaded queue and passes the
selected report filters to this endpoint. After a report export, the workspace
renders the exact filter snapshot returned by the backend and allows the current
report filter controls to be reset without mutating the generated report file.
Generated report filenames include a bounded filter/date suffix after the
timestamp so files remain sortable while carrying handoff context. The desktop
workspace copies the returned local report path through the webview clipboard API
and does not add another backend command for clipboard access.

`POST /api/render/jobs/report/bundle` applies the same report filters and writes
a handoff directory below `render/reports/bundles/`. The bundle contains CSV and
JSON queue reports, a versioned `manifest.json` with summary counts and paths,
and copied preview thumbnails for filtered jobs whose `RenderOutputPreview`
thumbnail file still exists. Missing thumbnails are omitted from the bundle
manifest rather than failing the package so review handoff can proceed with a
clear thumbnail count. The manifest also contains a reviewer checklist per job,
with default false checks for output viewing, audio, subtitles, visuals, and
metadata. The service creates a sibling ZIP archive from the completed bundle
folder using only standard-library archive support, and the desktop workspace can
open or copy both the folder and archive paths.

`POST /api/render/jobs/report/bundle/import-review` completes the handoff
round-trip by reading a reviewer-updated bundle manifest from the active
project's `render/reports/bundles/` tree. The import path is resolved and
validated inside that project scope before any file read occurs. Only
`accepted` and `rejected` checklist decisions are applied, and only to completed
jobs with output paths. Empty decisions, `not_reviewed`, missing jobs, and
non-reviewable jobs are skipped with per-item reasons in the import summary.
The desktop Render workspace keeps that summary visible as a compact diagnostics
list so reviewers can correct the manifest without inspecting backend logs.
Diagnostics can be filtered by applied or skipped state, and skipped rows can be
copied or exported as CSV from the UI without adding another backend report path.
Every successful import request writes a JSON audit report under
`render/reports/imports/` with the source manifest path, source bundle metadata,
counts, and per-item details. The report is atomically replaced from a temporary
file and its path is returned to the desktop workspace for copy/open actions.
`GET /api/render/jobs/report/bundle/imports` lists those project-scoped audit
reports as summaries sorted by import time. The Render workspace displays that
history so operators can compare multiple imports without manually browsing the
project folder. `POST /api/render/jobs/report/bundle/imports/compare` reads two
audit reports from the same project-scoped import folder and returns only job
decision, applied/skipped state, and skipped-reason differences keyed by job ID.
`POST /api/render/jobs/report/bundle/imports/compare/report` recomputes the same
comparison, applies a backend-owned `all`, `changed`, `added`, or `removed`
change filter, and atomically writes a CSV or JSON handoff artifact under
`render/reports/import-comparisons/`. The desktop comparison view displays the
saved report path for copy/open actions. `GET
/api/render/jobs/report/bundle/imports/compare/reports` scans that
project-scoped folder and returns saved comparison report summaries so the
Render workspace can reopen older handoff files. `POST
/api/render/jobs/report/bundle/imports/compare/reports/preview` resolves one
saved comparison report inside the same folder and returns a bounded table
preview for CSV or JSON files; the desktop UI applies search and summary
filters locally against the loaded history. `POST
/api/render/jobs/report/bundle/imports/compare/reports/pin` persists important
comparison report filenames in
`render/reports/import-comparisons/favorites.json`, allowing the history browser
to sort pinned handoff files first and filter to only pinned reports.
The preview returned by the backend is intentionally bounded and table-shaped;
the desktop workspace can copy, download, or print that current preview client
side without adding a second backend export path.

Job cancellation deletes the temporary MP4. Completed jobs expose final output
metadata, while failed and interrupted jobs keep their error code and message for
polling clients. The queue is durable, but FFmpeg itself is not checkpointed:
resume restarts the render for that output file.

Render job history is capped to the most recent 100 inactive jobs on every queue
write while preserving active queued/preparing/running/cancelling jobs. The cleanup endpoint
can trim inactive history immediately, and retry is an alias for re-queueing a
failed job through the same resume path. The desktop shell exposes a narrow
`open_path` command that only opens existing local paths, allowing the Render
workspace to review the completed MP4 or its output folder without giving the UI
general process execution.

Render start requests accept either the legacy explicit `fileName` or an
`outputNameTemplate`. Template placeholders are limited to `{project}`, `{title}`,
`{date}`, `{time}`, and `{datetime}`. The service resolves and sanitizes the
final MP4 name before output path validation, preventing path traversal while
supporting predictable batch-friendly naming.

# 60. Phase 7 Workflow Dashboard

The desktop dashboard is a UI orchestration layer only. It reads existing
project, script scene, scene analysis, media cache, timeline, and render queue
endpoints, then derives a user-facing workflow checklist locally. It does not
introduce new backend business rules or bypass module-owned validation.
Navigation remains workspace-based: Project, Script, AI, Media, Timeline, and
Render actions link to the existing screens responsible for those domains.
Checklist items may show local issue/fix guidance, but authoritative validation
remains owned by the module endpoints such as Timeline validation and Render
preflight.

Workspace empty/error guides are presentation-only helpers. Script, AI, Media,
Timeline, and Render screens derive them from already-loaded project state,
scene collections, analysis results, cache/timeline availability, and Render
preflight reports. They may navigate to the owning workspace for the next fix,
but they do not create alternate validation paths or persist workflow state.

Workspace handoff controls provide a consistent Dashboard and next-step action
inside Script, AI, Media, Timeline, and Render. These controls are static UI
navigation affordances; the Dashboard remains responsible for dynamic workflow
readiness calculation.

Completed render output summaries on the Dashboard are also derived locally
from the loaded render queue. They expose latest-output review status and
accepted/rejected/not-reviewed counts, then navigate to the Render workspace for
playback or review mutations. The Dashboard does not open files directly or
write review state.
Active render summaries are derived from the same queue snapshot. Queued,
running, and cancelling jobs take priority over latest-output review summaries,
show bounded progress and status labels, and navigate to the Render workspace
for authoritative progress polling and cancellation. The Dashboard does not
cancel jobs or mutate queue state directly.
When an active render is visible, the Dashboard performs a lightweight periodic
refresh of the existing workflow snapshot and stops polling once no active
render remains. Render handoff links may include UI hash anchors such as
`#render-monitor` or `#render-queue`; these anchors are presentation affordances
only and do not change backend contracts.
When the refreshed queue no longer has an active job, the Dashboard falls back
to the latest completed output by queue order, highlights it as the newest
output, and uses review-aware copy for accepted, rejected, or not-reviewed
states. This remains local presentation over durable render history.
Dashboard review handoff may include a `reviewJob` URL query parameter
containing the selected durable render job ID. The Render workspace uses that
parameter only to select the matching loaded queue item on entry; if the job is
missing, it falls back to the existing latest-match selection behavior.
After a Render workspace accept/reject action, the return-to-Dashboard control
is UI-only navigation. The Dashboard reads the same durable queue snapshot and
surfaces the latest completed output's review decision as accepted, rejected, or
not reviewed; it still does not mutate render history directly.
When all completed outputs in that queue snapshot have accepted or rejected
reviews, the Dashboard derives an "all outputs reviewed" presentation state and
offers navigation to the existing Render report/handoff controls or a new render
pass. These are navigation affordances only; report export and render creation
remain owned by the Render workspace and backend Render Engine.

Project Manager controls in the dashboard call the existing Project Core API for
create, open, close, current project, and recent project operations. The UI owns
form state and feedback messages only; project directory creation, validation,
recent ordering, and active-project state remain backend responsibilities.

The Pipeline workspace provides Script Import and Scene Viewer controls over the
existing Script Engine API. React owns only native file-picker selection, path
input, selected-scene state, draft text, and feedback messages. TXT/SRT
validation, scene parsing, stable scene identity, and atomic project persistence
remain backend responsibilities.

The Media workspace coordinates Media Search, Media Cache, and Timeline Media
APIs for non-technical asset selection. React owns query filters, result
selection, cached-asset selection, activity feedback, and assignment feedback
only. Provider ranking, download validation, content hashing, cache
persistence, and Timeline scene validation remain backend responsibilities. The
Media activity panel surfaces search/cache/assign elapsed time and staged
presentation labels without changing backend cache state or retry semantics.
For provider-facing Phase 9 UX, the Media workspace may fan out `all` searches
as individual provider requests and merge completed provider pages locally for
presentation. This keeps previous/partial results visible while slower or
rate-limited providers finish. Backend aggregate search remains the
authoritative API for normalized ranking/dedup contracts; the UI merge is a
responsive preview path, not a replacement for backend media rules.
For cache-heavy projects, `GET /api/timeline/media-assets` supports optional
`offset` and `limit` query parameters. Omitting them preserves the full-list
contract for existing callers. The Media workspace uses a 100-item window and a
load-more action so opening or refreshing the cached media panel does not
resolve and stat every cached file before first paint.
`PUT /api/timeline/media-assignments` provides a batch variant for generated or
bulk workflows that assign B-roll and Avatar clips across many scenes. The
Timeline Media service loads the timeline once, reads the cache manifest once,
validates every scene/role/content hash, rejects duplicate scene-role entries,
and saves one updated timeline. The existing single-scene assignment endpoint
remains the narrow interaction path for manual edits.

The AI Analysis workspace coordinates the existing Script and AI Scene Analysis
APIs. React owns provider/model form state, selected-scene display state, and
navigation from analysis keywords into Media Search. Prompt rendering, provider
selection defaults, retry behavior, stale-analysis filtering, and project
persistence remain owned by the backend AI Engine.

The Settings workspace reads `GET /api/setup/status` as a setup report. The
backend owns environment inspection, Ollama availability checks, model
readiness, and setup hints. API-key values are never returned; the UI only shows
configured/missing state, relevant environment variable names, and non-secret
value previews such as model names or local tool paths.

# 61. Phase 8 Integration Smoke

Phase 8 integration verification composes existing module contracts rather than
adding new production APIs. The rich workflow smoke creates an isolated
temporary project, generates local image/video/audio media with FFmpeg, imports
a multi-scene SRT script, caches local media through the Media Cache API,
assigns B-roll, Avatar, video trim, and music through Timeline APIs, runs Render
preflight and a durable render job, saves a review decision, exports a render
report and handoff bundle, and checks cleanup/reconciliation dry-run paths.

The smoke intentionally uses local generated media so it does not require
network providers or secrets. Provider-live integration remains a separate
Phase 8 activity that should run only when credentials and service availability
are explicitly configured.

The render recovery smoke starts the backend as a real sidecar process, creates
a durable render job through HTTP, terminates the backend while the job is
running, restarts the backend, reopens the project, and verifies that the
persisted queue converts the job to `interrupted`. It then resumes the same job
through the public API and requires the recovered render to complete with an
MP4 output and preview metadata. This exercises durable queue recovery at the
process boundary without introducing a new production endpoint.

The packaged render recovery smoke reuses the same workflow against the bundled
`fastapi-sidecar` executable shipped to Tauri. The smoke selects the runner with
`PHASE8_RECOVERY_SIDECAR_PATH`, uses an isolated app-data directory and local
media library, terminates the packaged listener by port and process image during
an active render, then verifies the same durable queue recovery path after the
packaged sidecar restarts.

The installed app smoke installs the generated NSIS setup into a workspace
temporary directory using silent mode, discovers the installed desktop
executable and sidecar, checks `/api/health` from that installed sidecar, then
reuses the packaged render recovery smoke with `PHASE8_RECOVERY_SIDECAR_PATH`
pointing at the installed sidecar path. A matching MSI smoke path exists for
the generated per-machine MSI package; it pins the WiX `INSTALLDIR` registry
search to an isolated workspace temp directory, performs the same sidecar
health and durable render recovery checks, and restores the previous registry
value after cleanup. Because the MSI is authored with `InstallScope=perMachine`,
that smoke must run from an elevated Administrator terminal. The installer
smokes uninstall and remove temporary install directories after verification.

Packaged desktop smoke remains outside the default quality gate because it
depends on release artifacts and available local ports. It verifies that the
bundled release executable, MSI, NSIS setup, and FastAPI sidecar exist, then
starts the sidecar on a selected loopback port and confirms `/api/health`
returns a healthy response. It does not automate installer UI interaction.

# 62. Phase 9 Performance Baseline

Phase 9 begins with measurement before optimization. The baseline benchmark is a
development script, not a production API. It creates an isolated temporary
project, generates local image/video/avatar/music assets, imports a six-scene
SRT script, caches media through the existing Media Cache API, builds and
assigns Timeline media, runs Render preflight, queues a Draft durable render
job, waits for FFmpeg completion, exports report/bundle artifacts, and runs
cache cleanup/reconciliation dry-runs.

The benchmark records per-step timings with `time.perf_counter()` and writes a
bounded JSON report under `.tmp/phase9-performance-matrix.json`. Rollups group
setup, backend, workflow, cache, and render costs so before/after optimization
changes can be compared without reading raw logs. The benchmark intentionally
uses deterministic local media and TestClient execution; live provider timing
and packaged sidecar startup timing are separate optional measurements because
network and installer environment variance would make the core baseline noisy.
`scripts/benchmark_phase9_media_live.ps1` is the optional live-provider media
probe for Phase 9. It uses configured provider credentials, measures repeated
provider searches, mixed-provider `providerId=all` search, selected-item
cache/download, duplicate cache behavior, cached-media reselection, cache
manifest refresh, and a large-cache ranking/merge sample, then writes a bounded
JSON report under `.tmp/phase9-media-live-search-cache.json`. It is not part of
the deterministic quality gate because network latency, provider rate limits,
and live credentials vary by machine.

The default Phase 9 benchmark runs each scenario in a separate Python process so
FastAPI app-data configuration, repository state, and background workers do not
bleed across measurements. The current matrix varies scene count and cache size:
6, 12, and 24 scene workflows isolate Timeline and FFmpeg command growth, while
28-entry cache scenarios isolate hash/fingerprint/manifest/reconciliation cost.
Generated media remains temporary; per-scenario JSON artifacts are kept below
`.tmp/phase9-performance-scenarios/` for review.

`FFmpegCommandBuilder` deduplicates visual media inputs by content hash, media
type, source start, and source duration before appending command inputs. Reused
image inputs are looped once for the full timeline and each visual clip is
trimmed inside the filter graph to preserve clip-scoped timing. When multiple
clips reuse the same input and visual role, the builder applies the shared
scale/pad/setsar transform once, splits the prepared stream, and then applies
per-clip trim/setpts timing. This keeps FFmpeg argument and input counts flat
when many scenes reuse the same B-roll or Avatar asset, while avoiding repeated
scale/pad work for identical visual transforms.

Render diagnostics include bounded filter-graph metrics in the persisted job
history: filter graph length, filter count, visual filter count, overlay count,
drawtext count, concat count, split count, and trim count. These are summary
numbers only; the raw filter graph and local media paths are not persisted.
Phase 9 uses these metrics to separate command/input fan-out from actual FFmpeg
graph cost. A measured B-roll concat experiment reduced overlay count but
increased render time, so the runtime keeps the simpler overlay graph until
per-filter profiling shows a better optimization target. Follow-up overlay
probes for per-clip `enable`, fixed-position `eval=init`, and scene-window
batching also regressed versus the current linear overlay graph, so they remain
benchmark notes rather than runtime architecture.

The Phase 9 benchmark matrix also includes controlled 24-scene render variants:
no subtitles, ASS subtitle sidecar, pre-rendered subtitle overlay, no avatar,
image-only, video-only, and pre-scaled mixed media. These variants are generated
through the same public project, script, media cache, timeline, and render APIs
as the main benchmark. `RENDER_SUBTITLE_MODE=ass` writes a temporary ASS sidecar
beside the hidden render MP4 and uses one FFmpeg `subtitles` filter instead of
per-cue `drawtext`; `RENDER_SUBTITLE_MODE=prerender` creates or reuses a
transparent `qtrle` subtitle overlay video and overlays it in the main render
command. `RENDER_SUBTITLE_MODE=sendcmd` writes each subtitle cue to a temporary
UTF-8 text file, writes a temporary FFmpeg command file, and uses one named
`drawtext@subtitle` filter that reinitializes `textfile=` at cue boundaries.
Pre-rendered overlays are cached under `render/cache/subtitles/` by a hash of
subtitle text, timing, total timeline duration, and raster settings so repeat
exports with the same subtitles/settings can skip overlay generation. The
default subtitle renderer is `sendcmd`; the previous per-cue `drawtext` renderer
remains available with `RENDER_SUBTITLE_MODE=drawtext` for fallback and
benchmark comparison. Current measurements show ASS/libass reduces filter count
while regressing render time. Cached pre-rendering improves repeat-export queue
time and the main FFmpeg pass, but cold exports still pay the expensive overlay
generation step. The textfile-driven `sendcmd` path improves the measured
24-scene Draft main pass by reducing repeated drawtext filters to one while
keeping subtitle content out of the FFmpeg command parser. Reusing visual
transforms and splitting prepared streams lowers the refreshed full-matrix
default 24-scene Draft render rollup to `6.3251s`, down from the previous
official `8.9683s` sendcmd baseline. Subtitle overlay pre-render uses
`RENDER_SUBTITLE_OVERLAY_FPS`, defaulting to 8 FPS and capped by the export
frame rate, because subtitle overlays are static between text changes and do
not need to be generated at the final video FPS. Avatar removal, image-only media, video-only media, and
pre-scaled media do not materially improve the measured Draft render time.

Render queue creation uses a lightweight render draft so expensive pre-render
work does not block the API request that creates a job. The queue worker
materializes the full render plan, including cold subtitle overlay generation or
cache lookup, before starting the main FFmpeg process. This keeps job creation
responsive while preserving the durable queue model; a job reports `preparing`
with "Preparing subtitles" UI progress while the worker prepares subtitle
overlays.

Fast Preview and Draft render profiles use FFmpeg `fast_bilinear` scale flags
for B-roll and Avatar transforms to favor quick review renders. Standard, High
Quality, Archive, and custom non-preview profiles keep FFmpeg's default scaling
behavior. Fast Preview is a distinct lower-cost review profile at 640x360, 15
FPS, CRF 32, and 96 kbps audio; it does not replace Draft's 854x480, 24 FPS
settings.
Measured visual-background precomposition reduced filter graph size but
regressed main and total render time, so it is not part of the runtime
architecture. Measured Draft encoder preset probes with `superfast` and
`ultrafast` also regressed versus the current `veryfast` Draft preset, so Draft
keeps `veryfast`. A measured default drawtext pixel-format probe that converted
the composed stream to `yuv420p` before subtitle drawing also regressed, so the
runtime keeps RGBA visual composition through `drawtext` and performs the
`yuv420p` conversion only at final output.

Timeline media assignment uses a batch service path for generated workflows.
The Phase 9 48-scene probe reduced `workflow.timeline_assign_media` from about
`2.4551s` with repeated single-scene saves to `0.1228s` with one validated
batch save. The official matrix now shows workflow rollup staying near
`0.5s` from 6 to 24 scenes, leaving render and cache as the dominant remaining
optimization targets.

The benchmark can also vary imported cue length with
`PHASE9_PERF_SCENARIO_DURATION_SECONDS`. That measurement keeps the same public
project, script, cache, timeline, and render APIs while extending generated
video/audio sources to match longer timelines. Current duration-depth probes
show that, after subtitle sendcmd and shared visual transform splitting, Draft
main render time scales more strongly with output duration than overlay count:
48s outputs are roughly equal even when overlay count changes from 14 to 26,
and 96s outputs are roughly equal when overlay count changes from 26 to 50.
Further render optimization should therefore measure duration-proportional
preview/encode policy before reshaping the overlay graph again. The first kept
policy is the Fast Preview profile, which reduced measured 96s and 192s
duration probes by roughly 21% versus Draft while keeping final export profiles
unchanged.
The same benchmark can also run a 300s synthetic target probe. On 2026-07-14,
the 25-scene, 5-minute Draft probe completed the full workflow in `82.714s`
with a `71.279s` main FFmpeg pass, while Fast Preview completed in `58.811s`
with a `47.915s` main FFmpeg pass. Both are well below the PROJECT.md
5-minute-under-10-minute goal on the benchmark machine, so no lower-fidelity
Ultra Fast Preview profile is part of the runtime architecture. Long-duration
synthetic music is generated as compressed audio once timelines exceed 60s so
these probes measure render behavior rather than oversized WAV cache overhead.
A separate 300s Standard-profile probe generates five long provider-style video
clips plus image, avatar, music, and extra cache entries to approximate a richer
final-export project without live provider credentials. That run completed the
full workflow in `130.308s`, with a `89.166s` main FFmpeg pass and 32 manifest
entries. The benchmark worker wait timeout scales with timeline duration so
long Standard/High Quality probes can finish or fail with render diagnostics
instead of hitting the old short-preview deadline.
The benchmark also supports optional live-provider corpus probes. These search
and cache media through the public Media APIs, skip provider videos whose probed
duration is shorter than the scene duration, and can reuse a previous
`liveCorpus.selected` report so Standard and High Quality render exactly the
same media. On 2026-07-14, a 300s real Pexels corpus completed in `240.624s`
for Standard with a `163.276s` main FFmpeg pass, and in `371.978s` for High
Quality with a `330.635s` main FFmpeg pass. Both remain under the 600s product
target, while live search/download/cache time is large enough to make
cache/search responsiveness the next Phase 9 focus.
The first cache/search responsiveness pass adds Media workspace activity
feedback for search, cache download, and assignment. It is intentionally a UI
layer over the existing APIs: elapsed time and staged labels help the operator
understand long provider/cache work while backend services continue to own
provider search, cache manifests, hashing, metadata, and timeline validation.
Media cache responses include bounded timing diagnostics for Phase 9
measurement: source transfer plus SHA-256 streaming time, file-write time,
duplicate/fingerprint checks, metadata probing, manifest commit, and total
cache time. These diagnostics are numeric only and exclude provider secrets,
request headers, and source credentials. The Phase 9 benchmark aggregates them
with provider-search latency and Media workspace refresh timings so cache/search
optimization decisions are based on measured bottlenecks.
Provider cache writes defer perceptual image hash and video fingerprint
generation when the content hash has no existing fingerprint. The request still
streams, hashes, validates, promotes, metadata-probes, and records the manifest
entry before responding; a guarded background worker enriches the manifest with
the fingerprint afterward under the existing cache manifest lock. Local Library
imports keep synchronous fingerprinting so local deduplication feedback remains
immediate.
`MediaFingerprintBackfillService` provides the durable recovery path for cache
entries that still lack fingerprints. It scans the active project's cache
manifest, fingerprints existing image/video files, merges results under the
same manifest lock, and exposes start/status/cancel endpoints. Project open
starts both metadata and fingerprint backfill jobs so interrupted provider
fingerprint work resumes after a backend or desktop restart.
The Media and Settings workspaces surface this recovery path as a compact
duplicate-check status chip. It polls only while a backfill job is queued or
running, shows progress and failed/paused states, and keeps cache enrichment
visible without requiring users to inspect backend logs.
Provider search latency is reduced by issuing independent image/video searches
concurrently inside Pexels, Pixabay, and DVIDS while preserving the existing
multi-provider aggregation contract. DVIDS search now uses true lazy detail:
result pages return summary metadata plus backend-only `dvids://asset/...`
source tokens, and the Media Cache service resolves `/asset` details only when
the operator selects a result to cache. DVIDS detail resolution still uses the
same retry, positive cache, and negative-cache behavior, but moved out of the
search path.
Remote provider cache requests first check the project manifest for an exact
`providerId + mediaId + sourceUri` source match. If the manifest entry's cache
file still exists, Media Cache refreshes `lastAccessedAt` and returns the
existing content-addressed entry without downloading or hashing the remote
source again. Local Library imports deliberately keep the streaming hash path
because a local file can change in place while preserving the same path.
The Render workspace may surface a local Fast Preview suggestion when preflight
reports a long render duration and another profile is selected. This is a UI
hint only: it does not change the selected profile automatically, does not alter
Render preflight semantics, and still sends the same explicit render settings
chosen by the operator.

# End of File
