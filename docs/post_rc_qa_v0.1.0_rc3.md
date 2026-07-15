# Post-RC QA: v0.1.0-rc3

Date: 2026-07-15

Release: https://github.com/pvhung-tech/AIVideoPipeline/releases/tag/v0.1.0-rc3

## Scope

This pass tracks the lifecycle fix after the published `v0.1.0-rc2` artifacts
showed an installed NSIS smoke ambiguity: a direct sidecar health probe could
leave a PyInstaller sidecar process behind and make the desktop lifecycle check
look dirty.

## Local Fix Before Publishing

The desktop app now passes its process ID to the FastAPI sidecar through both
`--parent-pid` and `AI_VIDEO_PIPELINE_PARENT_PID`. The sidecar uses a Windows
parent-process wait handle and terminates itself when the desktop parent exits.
The Tauri shutdown path also terminates both the FastAPI server child and the
PyInstaller sidecar process.

The installed-app smoke scripts now clean direct health-probe sidecars by exact
sidecar executable path before checking whether the desktop-managed sidecar was
cleaned up. This prevents a standalone probe process from being counted as a
desktop lifecycle leak.

## Local Artifact Verification

| Artifact | Size | SHA-256 | Result |
| --- | ---: | --- | --- |
| `AI Video Pipeline Studio_0.1.0_x64-setup.exe` | 28,372,370 bytes | `31D468466D5AB1E21B7D5B11E0F4AAA7EFA6FAB8979F00E44BF5D1A17D6A6E53` | Pass |
| `AI Video Pipeline Studio_0.1.0_x64_en-US.msi` | 29,675,520 bytes | `4736C46CA2D6E21A009BB099E3450944EA852B580002E171E55C7E5957176A28` | Pass |
| `ai-video-pipeline-studio.exe` | 11,876,864 bytes | `7D5CF240A9DCFB06CFED1D8677A1F5346A9F8280CE4EB5112BFF21C660394FA3` | Pass |
| `fastapi-sidecar-x86_64-pc-windows-msvc.exe` | 25,907,615 bytes | `94F8DB2C3BE0FC991CAF3699BCC80380DFB249CB891E305C4530E8A93C129E81` | Pass |

## Local NSIS Installed Smoke

Source artifact:
`frontend/src-tauri/target/release/bundle/nsis/AI Video Pipeline Studio_0.1.0_x64-setup.exe`

| Check | Result | Evidence |
| --- | --- | --- |
| Silent install to temporary directory | Pass | Installer exited successfully and installed `ai-video-pipeline-studio.exe` plus `fastapi-sidecar.exe`. |
| Installed sidecar health | Pass | Direct installed sidecar `/api/health` returned `ok`; the direct probe was cleaned by exact executable path before app lifecycle checks. |
| Render recovery from installed sidecar | Pass | Interrupted durable render job recovered from `interrupted` to `queued`, resumed, and completed. |
| Render output | Pass | Recovery smoke produced `phase8-recovery-20260715-071208.mp4` with size `28,250,581` bytes. |
| Native app launch sidecar health | Pass | Starting installed `ai-video-pipeline-studio.exe` exposed healthy FastAPI on `127.0.0.1:8765`. |
| App stop sidecar lifecycle | Pass | After stopping the installed app process and waiting 8 seconds, no installed sidecar process remained and `127.0.0.1:8765` was not listening. |
| Temporary cleanup | Pass | NSIS uninstall exited `0`; no app or sidecar process remained. |

## Local Performance Smoke

`scripts/smoke_phase10_installed_app_performance.ps1` passed the revised Phase
10 installed-app startup gate with 5 attempts:

| Metric | Value |
| --- | ---: |
| Average startup | `3.9878s` |
| Max startup | `5.1149s` |
| Revised average target `<= 6s` | Pass |
| Strict max target `<= 5s` | Needs hardening backlog |

## Full Quality Gate

`scripts/check_all.ps1` passed when pytest was given a workspace-local
`--basetemp` because the default Windows profile temp directory was not
readable in this session.

- Backend `ruff check`: pass.
- Backend `mypy`: pass, 171 source files.
- Backend `pytest`: 236 passed.
- Media deduplication regression: 10 groups passed at precision `>= 1.000`.
- Frontend `vitest`: 27 passed.
- Frontend production build: pass.

## Post-Publish Verification

Published release:
https://github.com/pvhung-tech/AIVideoPipeline/releases/tag/v0.1.0-rc3

| Artifact | Size | SHA-256 | Result |
| --- | ---: | --- | --- |
| `AI.Video.Pipeline.Studio_0.1.0_x64-setup.exe` | 28,372,370 bytes | `31D468466D5AB1E21B7D5B11E0F4AAA7EFA6FAB8979F00E44BF5D1A17D6A6E53` | Pass |
| `AI.Video.Pipeline.Studio_0.1.0_x64_en-US.msi` | 29,675,520 bytes | `4736C46CA2D6E21A009BB099E3450944EA852B580002E171E55C7E5957176A28` | Pass |

## NSIS Published Artifact Smoke

Source artifact:
`.tmp/post-rc-qa-downloads-v0.1.0-rc3/AI.Video.Pipeline.Studio_0.1.0_x64-setup.exe`

| Check | Result | Evidence |
| --- | --- | --- |
| Silent install to temporary directory | Pass | Installer exited successfully and installed `ai-video-pipeline-studio.exe` plus `fastapi-sidecar.exe`. |
| Installed sidecar health | Pass | Direct installed sidecar `/api/health` returned `ok`; the direct probe was cleaned before desktop lifecycle checks. |
| Render recovery from installed sidecar | Pass | Interrupted durable render job recovered from `interrupted` to `queued`, resumed, and completed. |
| Render output | Pass | Recovery smoke produced `phase8-recovery-20260715-072913.mp4` with size `28,250,581` bytes. |
| Native app launch sidecar health | Pass | Starting installed `ai-video-pipeline-studio.exe` exposed healthy FastAPI on `127.0.0.1:8765`. |
| App stop sidecar lifecycle | Pass | After stopping the installed app process and waiting 8 seconds, no installed sidecar process remained and `127.0.0.1:8765` was not listening. |
| Temporary cleanup | Pass | NSIS uninstall exited `0`; no app or sidecar process remained. |

## MSI Published Artifact Smoke

The MSI artifact downloaded and passed hash verification. Administrator
PowerShell smoke installed the MSI, returned sidecar health `ok`, recovered an
interrupted durable render job, and produced
`phase8-recovery-20260715-073515.mp4` with size `28,250,581` bytes.

| Check | Result | Evidence |
| --- | --- | --- |
| Per-machine MSI install from elevated PowerShell | Pass | MSI installed to `.tmp/phase8-installed-app-msi-smoke/7c782fe31dc14ad2b12f36ed0cd0fba2`. |
| Installed sidecar health | Pass | `/api/health` returned `ok`. |
| Render recovery from installed sidecar | Pass | Interrupted durable render job recovered from `interrupted` to `queued`, resumed, and completed. |
| Render output | Pass | Recovery smoke produced `phase8-recovery-20260715-073515.mp4` with size `28,250,581` bytes. |

## QA Decision

`v0.1.0-rc3` passes the post-publish NSIS and MSI install smokes, render
recovery checks, sidecar health checks, and NSIS lifecycle cleanup check. This
candidate is approved as the current stable-release candidate, with the strict
startup max `<= 5s` item remaining in the release-hardening backlog.
