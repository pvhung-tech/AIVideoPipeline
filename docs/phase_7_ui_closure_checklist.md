# Phase 7 UI Closure Checklist

Status: Complete

Last verified: 2026-07-13

This checklist summarizes the Phase 7 UI scope as implemented in the current
codebase. It is intended as the handoff document for moving into Phase 8
Integration, where the same workflow should be hardened with broader real-data
and packaged-desktop checks.

## Exit Criteria

- [x] Provide a production Dashboard that summarizes Project, Script, AI, Media,
      Timeline, and Render readiness.
- [x] Let operators create, open, close, and reopen recent projects from the UI.
- [x] Let operators import TXT/SRT scripts through a native file picker or path
      input and edit generated scenes in the app.
- [x] Let operators run AI scene analysis, inspect description/category/keywords,
      and pass keywords into Media Search.
- [x] Let operators search providers, download media into the project cache, and
      assign cached visual assets to Timeline scenes.
- [x] Let operators generate and edit Timeline v2 scenes, B-roll, Avatar,
      Subtitle, and Local Library music layers.
- [x] Let operators run render preflight, start render jobs, monitor progress,
      cancel, retry/resume, review output playback, and accept/reject outputs.
- [x] Let operators export render queue reports, handoff bundles, import review
      decisions, inspect diagnostics, compare audit reports, and reopen saved
      comparison reports from the Render workspace.
- [x] Provide guided empty/error states for missing project, scenes, AI analysis,
      media cache, timeline, and render preflight readiness.
- [x] Provide Dashboard and next-step handoff navigation across Script, AI,
      Media, Timeline, Render, and Review.
- [x] Surface active render progress on the Dashboard with a direct monitor link.
- [x] Surface latest completed output review status on the Dashboard with direct
      review selection in the Render queue.
- [x] Return from completed Render review decisions back to the Dashboard.
- [x] Surface an all-reviewed Dashboard state with actions for report handoff or
      the next render pass.

## UI Workflow Map

- [x] Dashboard -> Project Manager: create/open/close/recent project actions.
- [x] Dashboard -> Script: import or edit scenes when script data is missing.
- [x] Script -> AI: continue to provider/model analysis after scenes exist.
- [x] AI -> Media: continue to media search with analysis keywords.
- [x] Media -> Timeline: continue after downloading or assigning cached assets.
- [x] Timeline -> Render: continue after timeline/layer edits.
- [x] Render -> Dashboard: return after output review and show latest review
      state.
- [x] Dashboard -> Render queue: open the newest completed output selected for
      playback/review.
- [x] Dashboard -> Render monitor: open active queued/preparing/running/cancelling jobs.
- [x] Dashboard -> Render report area: open report/handoff controls when all
      completed outputs are reviewed.

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

Focused UI coverage currently includes:

- [x] Production Dashboard status and backend health.
- [x] Project Manager create/open/close/recent actions.
- [x] Guided empty states for missing workflow data.
- [x] Script import and scene edit workflow.
- [x] AI batch analysis and keyword-to-media handoff.
- [x] Media search, cache download, and Timeline assignment.
- [x] Render preflight guidance and setup action routing.
- [x] Render output preview, playback metadata, review notes, accept/reject,
      revert, and return-to-Dashboard action.
- [x] Dashboard latest-output review action and all-reviewed completion actions.
- [x] Final handoff walk: Script -> AI -> Media -> Timeline -> Render ->
      Dashboard.
- [x] Render queue review filters, bulk review/revert, search, sorting,
      pagination, report export, handoff bundle, import diagnostics, audit
      history, comparison reports, preview copy/download/print, and pinning.

Real workflow smoke command before final Phase 7 sign-off:

```powershell
cd backend
.\.venv\Scripts\python.exe smoke_e2e_workflow.py
```

This smoke uses the FastAPI app directly to create a project, import TXT,
generate scenes, create a Timeline, run render preflight, and export a small
Draft MP4. It complements the UI test suite by proving the workflow endpoints
behind the screens still compose.

Latest real workflow smoke results:

- [x] Project created in a temporary workspace.
- [x] TXT import produced 2 scenes.
- [x] Timeline generation produced 2 timeline scenes.
- [x] Draft MP4 output created with a non-empty file size.

## Closure Assessment

Phase 7 satisfies the UI exit criterion from `IMPLEMENTATION_PLAN.md`: an
operator can move through the full project-to-review workflow from the desktop
UI without manually calling backend endpoints. The remaining work belongs to
Phase 8 Integration: broader real project data, packaged desktop smoke, and
cross-module error-path hardening.

Recommended closure state: Phase 7 is functionally complete.

## Non-Blocking Follow-Ups

- [ ] Run the same workflow against a packaged desktop installer during Phase 10.
- [ ] Expand Phase 8 real-data coverage with a multi-scene project containing
      image, video, subtitle, and music assets.
- [ ] Add optional visual regression screenshots after the UI stabilizes for
      release branding.
- [ ] Consider splitting the large Render workspace component after Phase 8 if
      further UI work increases maintenance cost.
