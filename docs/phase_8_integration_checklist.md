# Phase 8 Integration Checklist

Status: Complete

Last verified: 2026-07-13

This checklist tracks integration hardening after Phase 7 UI closure. The goal
is to prove that completed modules compose reliably across project, script,
media, timeline, render, review, report, and desktop packaging paths.

## Closure Decision

Phase 8 is closed. The required integration gate is the deterministic local
workflow plus desktop packaging and installed-app recovery coverage listed
below. That gate proves the complete project -> script -> media -> timeline ->
render -> review/report pipeline works without external credentials and that
durable render recovery works across dev backend, packaged sidecar, NSIS install,
and MSI install paths.

Credential-backed live provider checks and larger real-media corpora are not
required to close Phase 8 because they depend on external services, local asset
approval, and API availability. They are tracked as follow-up validation work.

## Current Integration Coverage

- [x] Basic API workflow smoke from project creation through Draft MP4 render.
- [x] Rich API workflow smoke with six SRT scenes and multiple local media
      assets.
- [x] Local media cache integration for generated image, video, avatar image,
      and music assets.
- [x] Timeline integration for B-roll, Avatar, video trim, subtitle, and music
      layers.
- [x] Branch-error checks for untrusted local cache source, audio assigned as
      visual media, and invalid video trim.
- [x] Render preflight, durable render job, job polling, output preview metadata,
      review decision, JSON report export, and handoff bundle export in one
      workflow.
- [x] Real backend process restart/recovery smoke for a running durable render
      job, including interrupted-state restoration, resume, completed output,
      and preview metadata.
- [x] Packaged desktop sidecar restart/recovery smoke using the bundled
      `fastapi-sidecar` executable, including interrupted-state restoration,
      resume, and completed output.
- [x] Installed app smoke using the NSIS installer in silent mode, validating
      installed app and sidecar files, FastAPI health, and durable render
      recovery from the installed sidecar location.
- [x] MSI installed app smoke using the generated per-machine MSI from an
      elevated Administrator terminal, validating isolated temporary
      `INSTALLDIR`, installed sidecar health, and durable render recovery from
      the installed sidecar location.
- [x] Media cache cleanup and reconciliation dry-run checks after render.
- [x] Packaged desktop artifact smoke for release executable, MSI, NSIS setup,
      bundled sidecar, and FastAPI health response.

## Smoke Commands

Basic workflow smoke:

```powershell
cd backend
.\.venv\Scripts\python.exe smoke_e2e_workflow.py
```

Rich Phase 8 workflow smoke:

```powershell
.\scripts\smoke_phase8_rich_workflow.ps1
```

Render queue restart/recovery smoke against a real backend process:

```powershell
.\scripts\smoke_phase8_render_recovery.ps1
```

Render queue restart/recovery smoke against the packaged desktop sidecar:

```powershell
.\scripts\smoke_phase8_packaged_render_recovery.ps1
```

Installed app smoke from the NSIS installer:

```powershell
.\scripts\smoke_phase8_installed_app.ps1
```

Installed app smoke from the MSI installer:

```powershell
.\scripts\smoke_phase8_installed_app_msi.ps1
```

The MSI package is authored as a per-machine installer, so this command must be
run from an elevated Administrator terminal.

Packaged desktop smoke after a Tauri release build:

```powershell
.\scripts\smoke_desktop_package.ps1
```

If `127.0.0.1:8765` is already occupied by a running backend or desktop app,
use a temporary port for the sidecar health check:

```powershell
.\scripts\smoke_desktop_package.ps1 -Port 9876
```

## Latest Results

- [x] Rich Phase 8 workflow smoke passed with 6 imported scenes, 4 cached media
      entries, 6 timeline scenes, accepted render review, JSON report, and
      handoff bundle.
- [x] Packaged desktop smoke passed on port 9876 with bundled sidecar health
      `ok`.
- [x] Render queue restart/recovery smoke passed by killing a running backend,
      reopening the project after restart, restoring the job as `interrupted`,
      resuming it, and completing the output MP4.
- [x] Packaged sidecar restart/recovery smoke passed with the bundled
      `fastapi-sidecar-x86_64-pc-windows-msvc.exe`, restoring an interrupted
      render job and completing the resumed MP4.
- [x] Installed app smoke passed from a silent NSIS install into `.tmp`,
      returning sidecar health `ok` and completing the recovered render job.
- [x] MSI installed app smoke passed from an elevated Administrator terminal,
      returning installed sidecar health `ok`, restoring job
      `606a37a5290a42d785bb8eab631fee71` as `interrupted`, resuming it, and
      completing output `phase8-recovery-20260713-061151.mp4`
      (`28,696,044` bytes).

## Required To Close Phase 8

- [x] Rich deterministic end-to-end workflow smoke with generated local media.
- [x] Branch-error validation across media, timeline, preflight, and render
      handoff paths.
- [x] Durable render restart/recovery smoke against a real backend process.
- [x] Durable render restart/recovery smoke against the packaged Tauri sidecar.
- [x] Installed-app smoke from NSIS with installed sidecar health and render
      recovery.
- [x] Installed-app smoke from MSI with installed sidecar health and render
      recovery.
- [x] Packaged desktop artifact smoke after fresh release build.
- [x] Full project quality gate after final checklist update.

## Backlog Validation

- [ ] Add a broader integration fixture with real user-like media files after a
      stable local corpus is approved.
- [ ] Exercise live provider integration selectively when Pexels, Pixabay,
      Wikimedia, DVIDS, OpenAI, and Ollama credentials/services are available.

## CI Hardening

- [ ] Convert the highest-value deterministic smoke checks into optional CI jobs
      gated by local FFmpeg and packaging availability.
- [ ] Keep installer smoke checks manual or release-machine-only unless CI gains
      Windows packaging, UAC/elevation, and artifact retention support.

## Notes

The rich smoke uses generated local media instead of network providers so it is
deterministic and does not require API keys. Video perceptual fingerprinting is
best-effort; a warning in that subsystem should not fail the smoke as long as
cache, timeline, preflight, render, review, and report outputs are valid.
