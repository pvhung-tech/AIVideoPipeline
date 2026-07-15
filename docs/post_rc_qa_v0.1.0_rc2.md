# Post-RC QA: v0.1.0-rc2

Date: 2026-07-15

Release: https://github.com/pvhung-tech/AIVideoPipeline/releases/tag/v0.1.0-rc2

## Scope

This post-RC pass verifies the published GitHub Release artifacts rather than
the local build outputs.

## Artifact Download Verification

| Artifact | Size | SHA-256 | Result |
| --- | ---: | --- | --- |
| `AI.Video.Pipeline.Studio_0.1.0_x64-setup.exe` | 28,367,474 bytes | `80C624D953D811DC8291D5D51034F1AF36A1DED86D17C2163499C9FA657E4B33` | Pass |
| `AI.Video.Pipeline.Studio_0.1.0_x64_en-US.msi` | 29,675,520 bytes | `5AA8B11924F8DE3444E2CDB2EFBE6BA7896883317563FC4F297E7C46E9EC2442` | Pass |

## NSIS Published Artifact Smoke

Source artifact:
`.tmp/post-rc-qa-downloads-v0.1.0-rc2/AI.Video.Pipeline.Studio_0.1.0_x64-setup.exe`

| Check | Result | Evidence |
| --- | --- | --- |
| Silent install to temporary directory | Pass | Installer exited successfully and installed `ai-video-pipeline-studio.exe` plus `fastapi-sidecar.exe`. |
| Installed sidecar health | Pass | Direct installed sidecar `/api/health` returned `ok`. |
| Render recovery from installed sidecar | Pass | Interrupted durable render job recovered from `interrupted` to `queued`, resumed, and completed. |
| Render output | Pass | Recovery smoke produced `phase8-recovery-20260715-051657.mp4` with size `28,250,581` bytes. |
| Native app launch sidecar health | Pass | Starting installed `ai-video-pipeline-studio.exe` exposed healthy FastAPI on `127.0.0.1:8765`. |
| App stop sidecar lifecycle | Fail | After stopping the installed app process, an installed `fastapi-sidecar.exe` process remained under the temporary install directory. Port `127.0.0.1:8765` was no longer listening, but the process did not exit within the smoke wait window. |
| Temporary cleanup | Pass after forced cleanup | Remaining installed sidecar process was stopped manually, NSIS uninstall exited `0`, and no app or sidecar process remained. |

## MSI Published Artifact Smoke

The MSI artifact downloaded and passed hash verification. Full MSI install
smoke was not run in this session because the current terminal is not elevated
and the MSI package is per-machine. Run the MSI smoke from an Administrator
PowerShell session using the downloaded RC2 MSI artifact.

## QA Decision

Do not promote `v0.1.0-rc2` to stable yet.

The published artifacts are present and the install, health, and render
recovery paths are functional, but the NSIS post-publish lifecycle smoke found
an installed sidecar process left behind after direct app termination. This
should be investigated and fixed or explicitly accepted before stable release.

