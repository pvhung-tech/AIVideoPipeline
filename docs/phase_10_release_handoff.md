# Phase 10 Release Handoff

Date: 2026-07-14

## Release Candidate

This handoff covers the current Windows release candidate for AI Video Pipeline
Studio `0.1.0`.

## Final Artifacts

| Artifact | Size | Timestamp | SHA-256 |
| --- | ---: | --- | --- |
| `frontend/src-tauri/target/release/bundle/msi/AI Video Pipeline Studio_0.1.0_x64_en-US.msi` | 29,667,328 bytes | 2026-07-14 18:09 | `2A1FE22DA346498733E96D8DE63A588A1DE560CA808728D36C8CB8A1BD305DF7` |
| `frontend/src-tauri/target/release/bundle/nsis/AI Video Pipeline Studio_0.1.0_x64-setup.exe` | 28,359,318 bytes | 2026-07-14 18:10 | `72DD40E0BF603088E8B13B1F9CBCCBCBBABD98C9320E207F005D0D55D13E847A` |

Supporting binaries:

| Artifact | Size | Timestamp | SHA-256 |
| --- | ---: | --- | --- |
| `frontend/src-tauri/target/release/ai-video-pipeline-studio.exe` | 11,855,360 bytes | 2026-07-14 18:10 | `BC283099DA34AF5EBA1E833B4E97C0D72FBB9BFA2CDE4CA66B7350F87E5B2BD4` |
| `frontend/src-tauri/binaries/fastapi-sidecar-x86_64-pc-windows-msvc.exe` | 25,902,746 bytes | 2026-07-14 18:07 | `D7D74BCBA6FBA85C9C7EF1460630D81CAC96722BD4DC87BEE838A1596BDCB58D` |

## Gate Status

| Gate | Status | Evidence |
| --- | --- | --- |
| Full release quality gate | Pass | `scripts/check_all.ps1`: backend ruff/mypy/pytest, media dedup regression, frontend vitest, and frontend build passed. |
| Installer rebuild | Pass | `npm.cmd run tauri:build` produced refreshed MSI and NSIS installers after the desktop launch fix. |
| Revised installed-app startup gate | Pass | NSIS installed-app smoke average `5.5142s`, health OK on every attempt, cleanup completed. |
| Installed desktop launch | Pass | NSIS-installed app launched, stayed alive, spawned the bundled sidecar, and `/api/health` returned `ok` without a manual FastAPI process. |
| Installed render recovery | Pass | NSIS-installed sidecar recovered an interrupted durable render job, resumed it, and completed an MP4 output. |
| Rich workflow smoke | Pass | Created a project, imported 6 scenes, generated a timeline, cached media, rendered MP4, marked output accepted, and exported report/bundle artifacts. |
| Browser visual dashboard check | Partial | Production Dashboard layout rendered in the browser with the expected navigation and workflow cards. Backend fetch showed a browser-only CORS failure because this check runs outside the Tauri desktop shell. |
| Clean-profile native visual check | Pass | Manual confirmation on 2026-07-15: NSIS installer was opened on a clean Windows profile and the native Dashboard rendered correctly. |
| Git release tag | Pass | Git for Windows `2.55.0.windows.2` was installed and annotated tag `v0.1.0-rc1` was created for the release candidate source commit. |
| Packaged sidecar startup tracking | Tracked | Packaged sidecar average `5.8998s`, max `9.492s`; first one-file cold start remains a hardening item. |
| Release notes | Pass | `docs/phase_10_release_notes.md` updated with gate decision, artifacts, smokes, and known risk. |

## Manual QA Checklist

- Install the NSIS setup on a clean Windows user profile.
- Launch the app from the installed shortcut or executable.
- Confirm Dashboard loads without command-line steps.
- Confirm backend health is available through the app and no manual FastAPI
  process is required.
- Create a small project, import TXT or SRT, generate timeline, and run a Draft
  render smoke.
- Open Render workspace and confirm completed output can be reviewed.
- Uninstall the app and confirm the install directory is removed.

## Release Notes For Reviewers

- The first release gate accepts installed-app average startup `<= 6s` with
  healthy responses.
- Strict `max <= 5s` startup remains the long-term target and is intentionally
  tracked as release hardening.
- The next startup hardening spike is non-one-file or onedir sidecar packaging.
- API keys and provider credentials are not included in the release artifacts.

## Final Decision

The build passes the automated release handoff checks under the revised Phase
10 startup gate, the clean-profile native Dashboard visual check has been
manually confirmed, and annotated tag `v0.1.0-rc1` is approved as the first
release candidate tag.
