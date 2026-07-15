# Post-RC QA: v0.1.0-rc1

Date: 2026-07-15

Release: https://github.com/pvhung-tech/AIVideoPipeline/releases/tag/v0.1.0-rc1

## Scope

This post-RC pass verifies the published GitHub Release artifacts rather than
the local build outputs.

## Artifact Download Verification

| Artifact | Size | SHA-256 | Result |
| --- | ---: | --- | --- |
| `AI.Video.Pipeline.Studio_0.1.0_x64_en-US.msi` | 29,667,328 bytes | `2A1FE22DA346498733E96D8DE63A588A1DE560CA808728D36C8CB8A1BD305DF7` | Pass |
| `AI.Video.Pipeline.Studio_0.1.0_x64-setup.exe` | 28,359,318 bytes | `72DD40E0BF603088E8B13B1F9CBCCBCBBABD98C9320E207F005D0D55D13E847A` | Pass |

## NSIS Published Artifact Smoke

Source artifact:
`.tmp/post-rc-qa-downloads/AI.Video.Pipeline.Studio_0.1.0_x64-setup.exe`

| Check | Result | Evidence |
| --- | --- | --- |
| Silent install to temporary directory | Pass | Installer exited successfully and installed `ai-video-pipeline-studio.exe` plus `fastapi-sidecar.exe`. |
| Installed sidecar health | Pass | `/api/health` returned `ok` from the installed sidecar. |
| Startup timing | Needs review | 3 attempts averaged `7.0716s`; samples were `9.35s`, `6.5299s`, and `5.3348s`. This is above the revised first-release average target of `<= 6s`. |
| Native app launch sidecar health | Pass | Starting installed `ai-video-pipeline-studio.exe` exposed healthy FastAPI on `127.0.0.1:8765`. |
| App stop sidecar lifecycle | Needs review | After stopping the app process directly, two installed `fastapi-sidecar` processes remained and kept port `8765` open until they were manually stopped. |
| Temporary process cleanup | Pass after manual cleanup | Remaining sidecar processes were stopped and the temporary install directory was removed. |

## MSI Published Artifact Smoke

The MSI artifact downloaded and passed hash verification. Full MSI install smoke
was not run in this session because the current terminal is not elevated and the
MSI package is per-machine. Run this from an Administrator PowerShell session on
a separate Windows profile or machine.

## Separate Profile / Machine Status

The clean Windows profile Dashboard visual check was manually confirmed before
publishing RC1. This post-RC automated pass was run from the current machine and
profile, so a true separate-machine download/install smoke remains pending.

## QA Decision

Do not promote `v0.1.0-rc1` to stable yet. The published artifacts are present
and functional enough for RC distribution, but post-RC QA found two items that
should be reviewed before stable:

- Published NSIS startup average exceeded the revised `<= 6s` gate in this run.
- Direct app process termination did not shut down the spawned sidecar processes.

## Follow-Up Local Fix Validation

Date: 2026-07-15

A follow-up local build added Windows Job Object ownership for the FastAPI
sidecar process tree. This keeps the PyInstaller bootloader and server child in
the same OS-managed job as the desktop app, so sidecar processes are cleaned up
even when the app process is terminated externally.

Rebuilt local artifacts:

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `frontend/src-tauri/target/release/bundle/msi/AI Video Pipeline Studio_0.1.0_x64_en-US.msi` | 29,667,328 bytes | `54947E1476F38C91EBAD36E9F36D33F4A9EF62C24D87BFFAE59E593E35E8B926` |
| `frontend/src-tauri/target/release/bundle/nsis/AI Video Pipeline Studio_0.1.0_x64-setup.exe` | 28,361,068 bytes | `0957D9C229BF078D597E44A6FB6062BBB64019646918F96F1D34A302DB497105` |
| `frontend/src-tauri/target/release/ai-video-pipeline-studio.exe` | 11,850,752 bytes | `333953D5413C4D6D1C42CA89E294B8CB6F79BC236ACC1B388BFBDC63DCDCB069` |
| `frontend/src-tauri/binaries/fastapi-sidecar-x86_64-pc-windows-msvc.exe` | 25,901,477 bytes | `274AA9386F723E2C00C02F5F403184766CCE18646DD41D1525A3C8DBABC4BC1D` |

Follow-up validation:

| Check | Result | Evidence |
| --- | --- | --- |
| Rust format and tests | Pass | `cargo fmt` and `cargo test --manifest-path frontend/src-tauri/Cargo.toml`: 3 passed. |
| Tauri installer rebuild | Pass | `npm.cmd run tauri:build` rebuilt sidecar, frontend, app executable, MSI, and NSIS bundles. |
| NSIS installed sidecar health | Pass | Installed sidecar returned `/api/health` status `ok`. |
| NSIS startup timing | Needs review | 3 attempts averaged `7.9177s`; samples were `10.7671s`, `6.5055s`, and `6.4804s`. |
| Installed app lifecycle after external termination | Pass | Starting installed app exposed healthy FastAPI on `127.0.0.1:8765`; after terminating the app process, no installed `fastapi-sidecar` processes remained and port `8765` was no longer listening. |
| MSI installed smoke | Pending | Current terminal is not elevated. Run MSI smoke from Administrator PowerShell or a separate QA machine/profile. |

This follow-up build resolves the sidecar orphan issue found in the published
RC1 artifact. Startup performance remains the active post-RC hardening item
before promoting a stable release or publishing a refreshed RC.
