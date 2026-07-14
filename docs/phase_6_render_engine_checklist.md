# Phase 6 Render Engine Closure Checklist

Status: Complete

Last verified: 2026-07-11

This checklist summarizes the Phase 6 Render Engine scope as implemented in the
current codebase. It is intended as the handoff document for deciding whether
Phase 6 can be closed and the project can move into Phase 7 UI completion and
Phase 8 end-to-end integration hardening.

## Exit Criteria

- [x] Render the active Timeline v2 document to MP4 through FFmpeg.
- [x] Validate FFmpeg and FFprobe availability before queueing work.
- [x] Validate timeline duration, layers, source ranges, media files, and output
      writability before queueing work.
- [x] Compose B-roll, Avatar, Subtitle, and Music layers into H.264/AAC output.
- [x] Persist render job queue metadata in the active project.
- [x] Support progress polling, cancel, retry, resume, and durable queue recovery
      after backend restart.
- [x] Persist diagnostics that help debug failed renders without storing raw
      sensitive command details.
- [x] Generate output preview metadata and best-effort thumbnails for completed
      renders.
- [x] Provide desktop playback review for completed MP4 outputs.
- [x] Support accepted/rejected review notes, review filtering, bulk review, and
      review revert.
- [x] Support queue search, sorting, pagination, cleanup, and history capping.
- [x] Support named export profiles and custom export settings.
- [x] Export render queue reports in CSV and JSON with review, status, and date
      filters.
- [x] Package handoff bundles with CSV/JSON reports, thumbnails, manifest, and
      reviewer checklist.
- [x] Import reviewer checklist decisions back into render history.
- [x] Store import diagnostics audit reports and browse prior import history.
- [x] Compare two import audit reports and save comparison reports as CSV/JSON.
- [x] Browse, search, preview, copy, open, pin, download, and print saved
      comparison reports.

## Implemented API Surface

- [x] `POST /api/render/preflight`
- [x] `POST /api/render`
- [x] `POST /api/render/jobs`
- [x] `GET /api/render/jobs`
- [x] `GET /api/render/jobs/{jobId}`
- [x] `POST /api/render/jobs/{jobId}/resume`
- [x] `POST /api/render/jobs/{jobId}/retry`
- [x] `POST /api/render/jobs/{jobId}/cancel`
- [x] `POST /api/render/jobs/{jobId}/review`
- [x] `DELETE /api/render/jobs/{jobId}/review`
- [x] `POST /api/render/jobs/report`
- [x] `POST /api/render/jobs/report/bundle`
- [x] `POST /api/render/jobs/report/bundle/import-review`
- [x] `GET /api/render/jobs/report/bundle/imports`
- [x] `POST /api/render/jobs/report/bundle/imports/compare`
- [x] `POST /api/render/jobs/report/bundle/imports/compare/report`
- [x] `GET /api/render/jobs/report/bundle/imports/compare/reports`
- [x] `POST /api/render/jobs/report/bundle/imports/compare/reports/preview`
- [x] `POST /api/render/jobs/report/bundle/imports/compare/reports/pin`
- [x] `POST /api/render/jobs/cleanup`

## Verification Evidence

Quality gate command:

```powershell
$env:TMP='D:\Projects\AI Video Pipeline Studio\.tmp'; $env:TEMP='D:\Projects\AI Video Pipeline Studio\.tmp'; New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null; powershell.exe -ExecutionPolicy Bypass -File .\scripts\check_all.ps1
```

Expected coverage from that gate:

- [x] Backend Ruff lint.
- [x] Backend Mypy type checking.
- [x] Backend Pytest suite.
- [x] Media deduplication regression gate.
- [x] Frontend Vitest suite.
- [x] Frontend TypeScript and production Vite build.

Focused render-related tests currently cover:

- [x] FFmpeg command builder.
- [x] Render service and render API.
- [x] Durable render job service and repository.
- [x] Render output preview and preview thumbnail assertion for successful small
      FFmpeg renders.
- [x] Render queue filtering, sorting, pagination, bulk review, revert, export,
      report bundles, import diagnostics, comparison reports, pin/favorite, and
      preview copy/download/print UI.

Additional real media smoke command before final Phase 6 sign-off:

```powershell
cd backend
.\.venv\Scripts\python.exe smoke_render_profiles.py
```

This command is intentionally separate from `scripts/check_all.ps1` because it
requires local FFmpeg/FFprobe availability and performs real render work for
each named profile.

## Closure Assessment

Phase 6 satisfies the Render Engine exit criterion from
`IMPLEMENTATION_PLAN.md`: the application can export MP4 output through FFmpeg.
The implementation now also includes the operational pieces needed for real
review workflows: durable jobs, diagnostics, output preview, reviewer decisions,
handoff reports, review bundles, import audit history, comparison reports, and
favorite comparison reports.

Recommended closure state: Phase 6 is functionally complete. The current
quality gate passed, and the real profile smoke command completed successfully
on this machine with FFmpeg/FFprobe available.

Latest real profile smoke results:

- [x] Draft: MP4 output and preview thumbnail created.
- [x] Standard: MP4 output and preview thumbnail created.
- [x] High Quality: MP4 output and preview thumbnail created.
- [x] Archive: MP4 output and preview thumbnail created.

## Non-Blocking Follow-Ups

- [ ] Run a fresh installer build on the release machine before Phase 10.
- [ ] Run a complete script-to-render user journey during Phase 8 Integration.
- [ ] Polish the broader application navigation and screen density during Phase
      7 UI rather than expanding Render Engine contracts further.
- [ ] Decide whether real profile smoke renders should become optional CI jobs
      or remain local release checks.
