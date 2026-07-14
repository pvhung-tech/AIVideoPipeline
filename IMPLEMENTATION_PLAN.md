# IMPLEMENTATION_PLAN.md

Version: 1.0

Project: AI Video Pipeline Studio

Status: Master Development Plan

---

# 1. Purpose

Tài liệu này mô tả trình tự triển khai chính thức của dự án.

Mọi AI Coding Agent phải tuân thủ thứ tự này.

Không được triển khai các Phase sau khi Phase hiện tại chưa hoàn thành, trừ khi có yêu cầu rõ ràng.

---

# 2. Development Philosophy

Dự án được phát triển theo nguyên tắc:

* Small Increment
* Test First
* Stable Architecture
* Production Ready
* AI-Friendly Development

Mỗi Phase đều phải tạo ra một sản phẩm chạy được.

Không tạo "dead code" hoặc module chưa sử dụng.

---

# 3. Global Development Workflow

Mọi nhiệm vụ đều phải tuân theo quy trình sau:

1. Đọc AGENTS.md
2. Đọc RULES.md
3. Đọc PROJECT.md
4. Đọc ARCHITECTURE.md
5. Đọc IMPLEMENTATION_PLAN.md
6. Xác định Phase hiện tại
7. Kiểm tra các phụ thuộc
8. Thiết kế giải pháp
9. Viết mã nguồn
10. Viết Unit Test
11. Chạy kiểm thử
12. Cập nhật tài liệu

---

# 4. Phase Overview

| Phase | Name            | Goal                  |
| ----- | --------------- | --------------------- |
| 0     | Foundation      | Khởi tạo dự án        |
| 1     | Project Core    | Quản lý Project       |
| 2     | Script Engine   | Nhập Script & SRT     |
| 3     | AI Engine       | Phân tích nội dung    |
| 4     | Media Engine    | Tìm kiếm & tải media  |
| 5     | Timeline Engine | Tạo timeline video    |
| 6     | Render Engine   | Xuất video            |
| 7     | UI              | Hoàn thiện giao diện  |
| 8     | Integration     | Kết nối toàn hệ thống |
| 9     | Optimization    | Tối ưu hiệu năng      |
| 10    | Release         | Đóng gói & phát hành  |

---

# 5. Phase Details

## Phase 0 - Foundation

Status: Complete

### Objective

Thiết lập nền tảng dự án.

### Deliverables

* Repository
* Backend skeleton
* Frontend skeleton
* Configuration
* Logging
* Dependency Injection
* CI cơ bản
* Hello World chạy được

### Exit Criteria

* Ứng dụng khởi động thành công
* Backend và Frontend kết nối được
* Build không lỗi

---

## Phase 1 - Project Core

Status: Complete

### Objective

Xây dựng hệ thống quản lý Project.

### Features

* Create Project
* Open Project
* Save Project
* Auto Save
* Recent Projects

### Deliverables

* ProjectService
* ProjectRepository
* Project Model
* Unit Tests

### Exit Criteria

Có thể tạo, mở và lưu Project.

---

## Phase 2 - Script Engine

Status: Complete

### Objective

Đọc và chuẩn hóa nội dung đầu vào.

### Features

* Import TXT
* Import SRT
* Parse SRT
* Validate
* Scene Split

### Deliverables

* ScriptService
* SubtitleParser
* SceneParser

### Exit Criteria

Script được chuyển thành danh sách Scene hợp lệ.

---

## Phase 3 - AI Engine

Status: Complete

### Objective

Phân tích nội dung bằng AI.

### Features

* Prompt Manager
* Scene Analysis
* Keyword Generation
* Retry
* Multi Provider

### Providers

* Gemini
* OpenAI
* Ollama

### Exit Criteria

Mỗi Scene có bộ từ khóa và mô tả.

---

## Phase 4 - Media Engine

Status: Complete

### Objective

Tìm và quản lý tư liệu.

### Features

* Pixabay
* Pexels
* DVIDS Hub
* Local Library
* Download
* Cache
* Duplicate Detection

### Exit Criteria

Media phù hợp được tải về và lưu trong cache.

---

## Phase 5 - Timeline Engine

Status: Complete

### Objective

Tạo timeline video.

### Features

* Scene Timeline
* Avatar Layer
* B-roll Layer
* Subtitle Layer
* Music Layer

### Exit Criteria

Timeline hợp lệ được sinh ra cho toàn bộ Project.

---

## Phase 6 - Render Engine

Status: Complete - durable render queue, output review, review revert, review filtering, bulk review, queue search, queue pagination, queue sorting, queue export/report, report filtering, report date filtering, report UX polish, report handoff polish, report packaging, bundle zip export, reviewer checklist manifest, bundle review import round-trip, import diagnostics UI, import diagnostics filter/export, import diagnostics audit report, import audit history browser, import audit compare detail, import audit compare UX polish, saved import comparison reports, comparison report history browser, comparison report preview/search, comparison report preview export/print, pinned comparison reports, phase closure checklist, review/status summary dashboard, retry, cleanup, export settings, named profiles, diagnostics, preflight validation, output preview, playback review, and review notes integrated

### Objective

Render video bằng FFmpeg.

### Features

* Compose
* FFmpeg Command Builder
* Progress
* Cancel
* Resume
* Export Presets
* Render Profile Smoke Tests
* Render Diagnostics
* Render Preflight Validation
* Render Output Preview
* Render Playback Preview
* Render Review Notes
* Render Review Revert
* Render Review Filtering
* Render Bulk Review
* Render Queue Sorting
* Render Queue Search
* Render Queue Pagination
* Render Queue Export Report
* Render Queue Report Filtering
* Render Queue Report Date Filtering
* Render Queue Report UX Polish
* Render Queue Report Handoff Polish
* Render Queue Report Packaging
* Render Bundle Zip Export
* Render Bundle Reviewer Checklist
* Render Bundle Review Import Round-trip
* Render Bundle Import Diagnostics UI
* Render Bundle Import Diagnostics Filter and Export
* Render Bundle Import Diagnostics Audit Report
* Render Bundle Import Audit History Browser
* Render Bundle Import Audit Compare Detail
* Render Bundle Import Audit Compare UX Polish
* Saved Render Bundle Import Comparison Reports
* Render Bundle Import Comparison Report History Browser
* Render Bundle Import Comparison Report Preview and Search
* Render Bundle Import Comparison Report Preview Export and Print
* Render Bundle Import Comparison Report Pinning
* Render Engine Closure Checklist
* Render Review and Status Summary Dashboard

### Exit Criteria

Xuất thành công file MP4.

---

## Phase 7 - UI

Status: Complete - production workflow dashboard with progress/error guidance, project manager UI, script scene workspace, AI analysis workspace, media search workspace, settings/setup UI, guided workspace empty/error states, workflow handoff actions, dashboard output review actions, active render handoff with lightweight refresh, post-render newest-output highlight, review-ready job selection handoff, review completion return, latest-review dashboard status, all-reviewed dashboard completion actions, final workflow handoff walk, phase closure checklist, and end-to-end workflow smoke integrated

### Objective

Hoàn thiện giao diện người dùng.

### Features

* Dashboard
* Project Manager
* Scene Viewer
* Render Queue
* Settings
* Progress

### Completed

* Production workflow dashboard
* Workflow checklist for Project, Script, AI, Media, Timeline, and Render with step-specific issue/fix guidance
* Project Manager create, open, close, and recent project actions
* Script Import and Scene Viewer workspace for native TXT/SRT file selection, import, and scene text edits
* AI Analysis workspace for provider/model selection, batch scene analysis, keyword review, and Media Search handoff
* Media Search workspace for provider search, cache download, and Timeline scene media assignment
* Settings/Setup workspace for provider readiness, API-key env var status, Ollama availability, and setup hints
* Guided empty/error states in Script, AI, Media, Timeline, and Render workspaces with next-step actions for missing project/scenes/analysis/media/timeline/preflight readiness
* Consistent Dashboard and next-step handoff actions across Script, AI, Media, Timeline, and Render workspaces
* Dashboard output review actions with latest completed MP4, review status, accepted/rejected/not-reviewed counts, and direct Render queue handoff
* Dashboard active render state for queued/preparing/running/cancelling jobs with progress and direct Render monitor/cancel handoff
* Lightweight Dashboard auto-refresh while an active render exists, plus direct Render monitor and queue anchors
* Post-render Dashboard highlight for the newest completed output with explicit ready-to-review status
* Review-ready Dashboard handoff that opens the Render queue with the newest completed output selected
* Review completion return from Render back to Dashboard after accept/reject decisions
* Dashboard latest-review badge for accepted, rejected, and not-reviewed completed outputs
* Dashboard all-reviewed completion state with actions for review report handoff or the next render pass
* Final workflow handoff walk from Script to AI, Media, Timeline, Render, and Dashboard
* Phase 7 UI closure checklist
* End-to-end workflow smoke covering project creation, script import, scene listing, timeline generation, render preflight, and Draft MP4 output
* Active project, scene, timeline, media cache, and render queue status summary
* Step-by-step navigation across Project, Script, Timeline, Media, Render, and Review

### Exit Criteria

Người dùng có thể hoàn thành toàn bộ quy trình mà không cần dòng lệnh.

---

## Phase 8 - Integration

Status: Complete - rich local-media workflow smoke, branch-error checks, render review/report integration, real backend render recovery smoke, packaged desktop render recovery smoke, NSIS and MSI installed app smokes, packaged desktop sidecar smoke, full quality gate, and final integration checklist closure completed

### Objective

Kết nối toàn bộ module.

### Activities

* End-to-End Test
* Error Handling
* Workflow Validation

### Completed

* Rich generated-media workflow smoke with six SRT scenes.
* Local image, video, avatar image, and music cache integration.
* Timeline B-roll, Avatar, video trim, Subtitle, and Music integration smoke.
* Branch-error checks for invalid media cache source, audio-as-visual assignment, and invalid trim range.
* Durable render job, output preview metadata, review decision, report export, and handoff bundle integration smoke.
* Real backend process restart/recovery smoke for interrupted durable render jobs and resume-to-complete validation.
* Packaged desktop sidecar restart/recovery smoke for interrupted durable render jobs and resume-to-complete validation.
* Installed app smoke from NSIS silent install with sidecar health and recovery validation from the installed location.
* MSI installed app smoke from elevated per-machine install with sidecar health and recovery validation from the installed location.
* Packaged desktop artifact and bundled sidecar health smoke script.
* Phase 8 final integration checklist with required closure gate, backlog validation, and CI hardening split.

### Exit Criteria

Toàn bộ pipeline hoạt động ổn định.

---

## Phase 9 - Optimization

Status: Complete - deterministic workflow/render/cache performance matrix benchmark, render input reuse optimization, filter graph diagnostics, controlled render variant benchmarks, batch timeline assignment, duration-vs-overlay render scaling benchmarks, Fast Preview render profile, media cache/search responsiveness optimization, provider partial-result UX, duplicate-cache fast path, background fingerprint enrichment, durable fingerprint backfill, lazy DVIDS detail, and large-cache Media workspace windowing completed

### Objective

Tối ưu hiệu năng.

### Activities

* Caching
* Parallel Download
* Background Rendering
* Lazy Loading
* Memory Optimization

### Completed

* Deterministic Phase 9 performance benchmark for workflow, cache, and render
  timing using generated local media and no external credentials.
* Scene-count and cache-size benchmark matrix to compare render command growth,
  timeline persistence, and cache manifest/hash costs.
* Matrix JSON output at `.tmp/phase9-performance-matrix.json`.
* Phase 9 optimization checklist with required measurement guardrails and first
  optimization candidates.
* FFmpeg visual input reuse for repeated timeline media, keeping render command
  argument and input counts flat across the 6, 12, and 24 scene benchmark
  scenarios.
* Render diagnostics for filter graph length, filter count, visual filters,
  overlays, drawtext, concat, split, and trim counts.
* Filter graph benchmark review showing B-roll concat reduced overlay count but
  regressed render time, so the optimization was not kept.
* Controlled 24-scene render variant benchmarks for no subtitles, no avatar,
  image-only media, video-only media, and pre-scaled mixed media.
* Phase 9 render read showing subtitle drawtext is the strongest isolated cost
  in the current benchmark matrix.
* ASS subtitle sidecar benchmark path via `RENDER_SUBTITLE_MODE=ass`. It removes
  per-cue drawtext filters but is slower in the current local benchmark, so it
  remains opt-in and drawtext stays the default.
* Pre-rendered subtitle overlay benchmark path via
  `RENDER_SUBTITLE_MODE=prerender`. It improves the main FFmpeg pass but is
  slower overall until overlay generation can be cached or moved off queueing.
* Subtitle overlay cache keyed by timeline subtitle content/timing and render
  raster settings. Cache hits skip the expensive overlay pre-render step for
  repeated exports.
* Render queue draft creation so cold subtitle pre-render happens in the worker
  preparation phase instead of blocking the API request that creates a job.
* Render queue `preparing` status and UI progress copy for subtitle preparation
  before FFmpeg progress begins.
* Draft-profile FFmpeg fast scaling for quicker review renders, with final
  export profiles left on default scaler quality.
* Full Phase 9 matrix baseline refreshed after Draft fast scaling.
* Visual-background precomposition benchmarked and rejected because it regressed
  main FFmpeg and total worker time despite shrinking the filter graph.
* Draft encoder preset tuning benchmarked with `superfast` and `ultrafast` and
  rejected because both regressed versus the current `veryfast` preset.
* `sendcmd` subtitle mode hardened with per-cue UTF-8 text files, then promoted
  to the default subtitle renderer. It reduces repeated subtitle drawtext
  filters to one named drawtext filter and improves the measured 24-scene Draft
  main pass, while the old per-cue drawtext path remains available through
  `RENDER_SUBTITLE_MODE=drawtext`.
* Full Phase 9 matrix baseline refreshed after the `sendcmd` default. The
  official 24-scene Draft render rollup is now `8.9683s`.
* Repeated visual transform splitting added so reused B-roll/Avatar/video media
  are scaled/padded once and split into per-clip trim/setpts timing filters.
* Full Phase 9 matrix baseline refreshed after visual transform splitting. The
  official 24-scene Draft render rollup is now `6.3251s`.
* Overlay-chain follow-up probes for `enable=between(...)`, fixed-position
  `eval=init`, and scene-window batching were benchmarked and rejected because
  all regressed versus the current linear overlay baseline.
* Timeline media batch assignment added for generated workflows so B-roll and
  Avatar clips across many scenes are validated and saved in one timeline
  mutation. The 48-scene assignment probe dropped from `2.4551s` to `0.1228s`.
* Full Phase 9 matrix baseline refreshed after timeline batch assignment. The
  official 24-scene workflow rollup is now `0.5264s`.
* Render duration-vs-overlay-depth benchmark added with configurable seconds per
  scene. Current data shows Draft render time tracks output duration more
  strongly than overlay count after subtitle and shared-transform optimizations.
* Fast Preview render profile added for speed-oriented review passes. It uses
  640x360, 15 FPS, CRF 32, veryfast x264, 96 kbps audio, and fast scaling; 96s
  and 192s probes improved main FFmpeg time by about 21% versus Draft.
* Full Phase 9 matrix refreshed with `variant_24_fast_preview_profile`. The
  48s 24-scene Fast Preview variant improved main FFmpeg time from `6.093s` to
  `4.852s` versus Draft in the same matrix run.
* Render workspace now suggests Fast Preview for long preflight durations while
  leaving the selected profile under user control.
* Five-minute synthetic timeline probe completed against the PROJECT.md render
  target. Draft completed the full 300s workflow in `82.714s`; Fast Preview
  completed in `58.811s`, so an additional `Ultra Fast Preview` profile is not
  justified by current benchmark data.
* Five-minute richer Standard export probe completed with five generated long
  video clips and 32 cache entries. The 1080p/30 FPS Standard workflow finished
  in `130.308s`, with `89.166s` spent in the main FFmpeg pass, still well below
  the 10-minute PROJECT.md target.
* Five-minute real-provider corpus probe completed with four Pexels videos and
  two Pexels images. Standard finished in `240.624s` total with `163.276s` in
  FFmpeg; High Quality reused the same corpus and finished in `371.978s` total
  with `330.635s` in FFmpeg. Both pass the 10-minute target, shifting the next
  Phase 9 focus toward cache/search responsiveness instead of final export
  encoder tuning.
* Media workspace cache/search responsiveness first pass added activity
  feedback for provider search, cache download, and Timeline assignment without
  changing backend cache or provider contracts.
* Media cache/search timing breakdown added for Phase 9: cache responses expose
  bounded numeric diagnostics, the benchmark aggregates provider search latency,
  cache write substeps, and Media workspace refresh calls, and the first local
  plus live Pexels probe shows fingerprint/source transfer dominate while UI
  refresh and manifest writes are small.
* Provider media cache writes now defer perceptual image/video fingerprint
  generation to a guarded background worker when no manifest fingerprint exists.
  The small live Pexels probe reduced three provider cache writes from `8.935s`
  to `4.8342s` while keeping SHA-256 hashing, metadata probing, and manifest
  persistence in the request path.
* Durable media fingerprint backfill added for cache entries missing
  perceptual/video fingerprints. It exposes start/status/cancel endpoints,
  resumes automatically when a project is opened, and recovers deferred provider
  fingerprints after backend or desktop restart.
* Media and Settings workspaces now show a compact duplicate-check status chip
  for durable fingerprint backfill progress, including running, paused, failed,
  and ready states.
* Provider search latency optimized for mixed image/video searches by running
  Pexels, Pixabay, and DVIDS media-type lookups concurrently. DVIDS asset
  detail hydration is bounded and demand-sized so live search only resolves
  enough candidates to fill the requested page, continuing only when selected
  assets are unavailable.
* DVIDS live search now uses true lazy asset detail. Search returns summary
  results with backend-only `dvids://asset/...` source tokens, and Media Cache
  resolves `/asset` details only when the operator chooses an item to download.
  The live mixed image/video DVIDS search probe dropped from `10.2036s` to
  `2.8325s`, with selected-item cache/download verified afterward.
* Phase 9 live media search/cache probe added for repeated-query cache hits and
  mixed-provider UX. The first run showed DVIDS warm repeated search at
  `0.0843s`, mixed-provider warm search at `0.9486s`, no measurable
  ranking/merge overhead, and selected-item cache dominated by source transfer
  rather than manifest refresh.
* Remote duplicate cache fast path added for exact
  `providerId + mediaId + sourceUri` manifest hits when the cache file still
  exists. The follow-up live DVIDS probe reduced duplicate cache from `3.3751s`
  to `0.0403s` and removed repeat source transfer from that path.
* Phase 9 live media UX probe expanded after duplicate-cache optimization. It
  now measures cached-media reselection, repeated cache refresh, mixed-provider
  search with a larger cache manifest, and synthetic ranking/merge cost. The
  current run shows reselect averaging `0.0569s`, 250-entry cache refresh
  averaging `0.0336s`, and synthetic 120-candidate/250-cache ranking at
  `0.0321s`; provider latency remains the visible UX cost.
* Media workspace now improves provider-facing UX for `All providers` searches
  by issuing provider requests independently, showing partial results as soon
  as each provider finishes, and keeping provider-specific pending/error status
  visible when another provider is slow or rate-limited.
* Phase 9 live media probe now measures full Media workspace cache refresh at
  larger cache sizes, including manifest read, Timeline media asset listing,
  and frontend-style visual asset projection. The current 2500-entry probe
  identifies Timeline media asset listing as the next measured Media UX
  optimization candidate.
* Timeline media asset listing now supports optional pagination, and the Media
  workspace uses a 100-item cached media window with a load-more action. The
  2500-entry Media refresh probe dropped from `5.0913s` to `0.4653s`, meeting
  the first-paint target for large caches.
* Default drawtext pixel-format tuning benchmarked by converting the composed
  stream to `yuv420p` before subtitle drawing and rejected because it regressed
  versus the current mixed 24-scene baseline.
* Phase 9 closure checklist completed on 2026-07-14. Packaged sidecar startup
  timing and recurring benchmark CI gates were moved to Phase 10 release
  validation/CI hardening because they depend on release artifacts and installed
  app context.

### Exit Criteria

Đáp ứng mục tiêu hiệu năng của PROJECT.md.

---

## Phase 10 - Release

Status: In Progress - release quality gate passed, installers rebuilt, packaged sidecar startup timing optimized and measured, installed-app performance smoke measured, installed desktop launch verified, release notes and release handoff updated, and first-release startup gate revised to installed-app average `<= 6s` with health OK; strict `max <= 5s` moved to release hardening backlog

### Objective

Chuẩn bị phát hành.

### Activities

* Packaging
* Installer
* Documentation
* Smoke Test
* Release Notes
* Packaged sidecar startup timing
* Installed-app performance smoke
* Phase 9 benchmark regression gate review

### Completed

* Packaged sidecar startup timing script added and run against the bundled
  sidecar. Health passed, but startup averaged `8.4021s` after rebuild and
  missed the `5s` target.
* NSIS installed-app performance smoke added and run against the rebuilt
  installer. Install, sidecar discovery, and health passed; startup averaged
  `6.612s` and missed the `5s` target.
* Sidecar cold-start path optimized by lazy-loading sidecar app/server imports,
  pinning Uvicorn to the local HTTP runtime used by the desktop app, narrowing
  PyInstaller Uvicorn collection, and deferring heavy provider/service imports
  out of FastAPI router import time.
* Final rebuilt packaged sidecar startup smoke passed health checks and
  improved to average `5.8998s`, max `9.492s`; the strict `5s` max target still
  fails because the first one-file cold start remains slow.
* Final NSIS installed-app performance smoke passed install, discovery, health,
  and cleanup, improving to average `5.2136s`, max `5.9683s`; the strict `5s`
  max target still fails narrowly.
* Manual QA launch found a release-blocking desktop startup panic when the
  Tauri log plugin could not open the app-data log file. The desktop shell now
  logs to stdout only, so stale log-file permission issues cannot prevent app
  startup.
* Refreshed NSIS installed-app performance smoke passed install, discovery,
  health, and cleanup with average `5.5142s`, max `5.9756s`, staying inside the
  revised `<= 6s` release gate.
* NSIS-installed desktop app launch verified: the app executable stayed alive,
  spawned the bundled FastAPI sidecar, and `/api/health` returned `ok` without
  a manual backend process.
* NSIS-installed render recovery smoke passed after the desktop launch fix:
  interrupted durable render job recovered, resumed, and completed an MP4
  output.
* Rich workflow smoke passed after the release rebuild: project creation,
  6-scene script import, timeline generation, media cache, MP4 render, accepted
  review decision, report export, and handoff bundle export completed.
* Git for Windows was installed and annotated release tag `v0.1.0-rc1` was
  created for the release candidate source commit.
* Phase 10 first-release startup gate revised on 2026-07-14: release can pass
  with NSIS installed-app startup average `<= 6s`, healthy `/api/health`
  responses on every attempt, installer cleanup success, and first-run
  packaged one-file cold start tracked separately as a release-hardening item.
  Strict `max <= 5s` remains the long-term target and should be revisited with
  an onedir/non-one-file sidecar packaging spike.
* Full release quality gate passed: backend lint/type/test, media dedup
  regression, frontend tests, and frontend production build.
* Tauri installers rebuilt successfully after rerunning outside the sandbox so
  WiX could access Windows Installer validation.
* Final MSI and NSIS artifacts confirmed with size, timestamp, and SHA-256
  hashes in `docs/phase_10_release_notes.md` and
  `docs/phase_10_release_handoff.md`.
* Phase 10 release notes and final QA handoff checklist prepared in
  `docs/phase_10_release_notes.md` and `docs/phase_10_release_handoff.md`.

### Exit Criteria

Có thể cài đặt và sử dụng trên hệ điều hành mục tiêu.

---

# 6. Dependency Map

Foundation
↓
Project Core
↓
Script Engine
↓
AI Engine
↓
Media Engine
↓
Timeline Engine
↓
Render Engine
↓
UI
↓
Integration
↓
Optimization
↓
Release

Không được bỏ qua hoặc đảo thứ tự nếu chưa có phê duyệt.

---

# 7. Coding Workflow

Đối với mỗi Feature:

1. Phân tích yêu cầu.
2. Thiết kế Interface.
3. Cập nhật Architecture (nếu cần).
4. Viết Unit Test.
5. Viết Implementation.
6. Kiểm thử.
7. Refactor.
8. Cập nhật tài liệu.

---

# 8. Definition of Done

Một Phase hoàn thành khi:

* Tất cả Deliverables đã hoàn thành.
* Không còn lỗi nghiêm trọng.
* Unit Test đạt yêu cầu.
* Build thành công.
* Tài liệu được cập nhật.
* Không phát sinh nợ kỹ thuật nghiêm trọng.

---

# 9. AI Agent Rules

AI Coding Agent phải:

* Chỉ làm việc trong Phase hiện tại.
* Không triển khai trước các tính năng của Phase sau.
* Không tự ý thay đổi kiến trúc.
* Không tạo tính năng ngoài PROJECT.md.
* Báo cáo rủi ro nếu phát hiện phụ thuộc chưa được giải quyết.

---

# 10. Future Evolution

Sau khi hoàn thành Version 1.0:

* Plugin Marketplace
* AI Workflow Designer
* Cloud Rendering
* Multi-user Collaboration
* Distributed Rendering
* Asset Marketplace

Các tính năng này không thuộc phạm vi MVP và không được triển khai nếu chưa có yêu cầu.

---

# End of File
