# Phase 9 Optimization Checklist

Status: Complete

Last verified: 2026-07-14

Phase 9 starts with measurement before optimization. The first gate is a
repeatable local benchmark for workflow, render, and cache behavior using
generated media and no external provider credentials. The first targeted
optimization removes FFmpeg visual input fan-out when many timeline scenes reuse
the same cached media.

## Measurement Scope

- [x] Workflow baseline from project creation through script import, scene load,
      timeline generation, and media assignment.
- [x] Cache baseline for Local Library imports, duplicate content hit, manifest
      load, cleanup dry-run, and reconciliation dry-run.
- [x] Render baseline for preflight, durable job queueing, FFmpeg completion,
      output preview metadata, report export, and handoff bundle export.
- [x] Scene-count and cache-size matrix for 6, 12, and 24 scene workflows and
      4-entry versus 28-entry cache manifests.
- [x] JSON benchmark output written to `.tmp/phase9-performance-matrix.json`.

## Benchmark Command

```powershell
.\scripts\benchmark_phase9_performance.ps1
```

The benchmark uses isolated temporary projects and generated local media. Each
scenario runs in a separate Python process to avoid app configuration and worker
state leaking between measurements. Rendered MP4s and project workspaces are
temporary; the JSON result keeps timings, output size, render diagnostics, and
rollups for comparison.

## Matrix Baseline

Latest official full matrix run: 2026-07-13 with textfile-driven `sendcmd`
subtitles as the default, subtitle overlay pre-render defaulting to 8 FPS,
Draft and Fast Preview profile scaling with `fast_bilinear`, repeated visual
transforms split after one shared scale/pad step, and the Fast Preview profile
included as a controlled variant. Timeline media assignment uses the batch
assignment API so visual media for many scenes is validated and saved in one
timeline mutation.

| Scenario | Scenes | Cache entries | Total | Workflow | Cache | Render | FFmpeg args | FFmpeg inputs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_6_scenes_4_cache` | 6 | 4 | `7.536s` | `0.4668s` | `0.9807s` | `2.6802s` | 59 | 5 |
| `scene_scale_12_scenes` | 12 | 4 | `8.725s` | `0.4761s` | `0.9919s` | `3.8729s` | 59 | 5 |
| `scene_scale_24_scenes` | 24 | 4 | `11.332s` | `0.4843s` | `1.0545s` | `6.4503s` | 59 | 5 |
| `cache_scale_28_entries` | 6 | 28 | `9.196s` | `0.5939s` | `2.4544s` | `2.7133s` | 59 | 5 |
| `mixed_24_scenes_28_cache` | 24 | 28 | `12.75s` | `0.5655s` | `2.385s` | `6.3992s` | 59 | 5 |
| `variant_24_fast_preview_profile` | 24 | 4 | `10.011s` | `0.5187s` | `1.0136s` | `5.1952s` | 59 | 5 |

Current read: after visual input reuse and visual transform splitting, FFmpeg
argument and input counts stay flat across scene-count growth while repeated
scale/pad work is shared for reused media. Textfile-driven `sendcmd` subtitles
keep the default subtitle graph at one drawtext filter, and transform splitting
lowered the official 24-scene render rollup from `8.9683s` to the current
`6.4503s` range. Batch timeline media assignment lowered the 24-scene workflow
rollup from `1.6735s` to `0.5264s` and keeps workflow timing almost flat across
6, 12, and 24 scenes. Render still remains the dominant rollup as scene count
rises, while larger cache manifests mainly increase cache write, cleanup, and
reconciliation time. Fast Preview reduces the same 24-scene render rollup to
`5.1952s` when speed matters more than review fidelity. This table is the
current official Phase 9 matrix baseline for follow-up optimization comparisons.

## Render Input Reuse Benchmark

Historical run: 2026-07-13

| Scenario | Scenes | Cache entries | Total | Workflow | Cache | Render | FFmpeg args | FFmpeg inputs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_6_scenes_4_cache` | 6 | 4 | `9.68s` | `0.8145s` | `1.0729s` | `4.2348s` | 59 | 5 |
| `scene_scale_12_scenes` | 12 | 4 | `12.842s` | `1.1361s` | `1.0808s` | `7.2052s` | 59 | 5 |
| `scene_scale_24_scenes` | 24 | 4 | `19.073s` | `1.6937s` | `1.0227s` | `12.81s` | 59 | 5 |
| `cache_scale_28_entries` | 6 | 28 | `10.958s` | `0.96s` | `2.5053s` | `4.0424s` | 59 | 5 |
| `mixed_24_scenes_28_cache` | 24 | 28 | `20.399s` | `1.6904s` | `2.4483s` | `12.6839s` | 59 | 5 |

Result: the targeted command-growth issue is removed. FFmpeg argument count and
input count now stay flat across the measured scene-count matrix because shared
image/video assets are appended once and reused by per-clip filters. Each reused
clip is still trimmed independently inside the filter graph so visual timing
remains clip-scoped. Render duration still grows with timeline length, so the
next render optimization should measure filter graph and overlay-chain cost
rather than input fan-out.

## Filter Graph Detail Benchmark

Historical run: 2026-07-13

| Scenario | Scenes | Render | Filter graph length | Filters | Visual filters | Overlays | Drawtext | Concat |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_6_scenes_4_cache` | 6 | `4.0445s` | 3022 | 25 | 9 | 8 | 6 | 0 |
| `scene_scale_12_scenes` | 12 | `6.8052s` | 5577 | 43 | 15 | 14 | 12 | 0 |
| `scene_scale_24_scenes` | 24 | `12.5177s` | 10725 | 79 | 27 | 26 | 24 | 0 |
| `cache_scale_28_entries` | 6 | `3.8222s` | 3022 | 25 | 9 | 8 | 6 | 0 |
| `mixed_24_scenes_28_cache` | 24 | `12.3246s` | 10725 | 79 | 27 | 26 | 24 | 0 |

Read: filter graph size, visual filters, overlays, and drawtext all scale with
scene count. A measured B-roll concat experiment reduced 24-scene overlays from
26 to 2 and filters from 79 to 55, but render time regressed from roughly
`12.0s` to `15.1s` in the same benchmark shape. That optimization was not kept.
The next useful render work should profile per-filter CPU cost, especially
scaling/trim/drawtext and repeated source decoding, instead of assuming overlay
count alone is the root cause.

## Controlled Render Variants

Latest run: 2026-07-13

All variants below use 24 scenes and a 4-entry cache. They isolate one render
factor at a time while keeping the same Draft profile and generated local media.

| Scenario | Variant | Render | Filters | Visual filters | Overlays | Drawtext | Split | FFmpeg args | FFmpeg inputs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `scene_scale_24_scenes` | default sendcmd subtitles | `6.093s` | 62 | 27 | 26 | 1 | 3 | 59 | 5 |
| `variant_24_drawtext_subtitles` | drawtext fallback | `8.780s` | 85 | 27 | 26 | 24 | 3 | 59 | 5 |
| `variant_24_no_subtitles` | no subtitles | `5.885s` | 61 | 27 | 26 | 0 | 3 | 59 | 5 |
| `variant_24_sendcmd_subtitles` | explicit sendcmd subtitles | `5.875s` | 62 | 27 | 26 | 1 | 3 | 59 | 5 |
| `variant_24_ass_subtitles` | ASS subtitles | `10.651s` | 62 | 27 | 26 | 0 | 3 | 59 | 5 |
| `variant_24_prerendered_subtitles` | pre-rendered subtitle overlay | `6.380s` | 63 | 28 | 27 | 0 | 3 | 61 | 6 |
| `variant_24_prerendered_subtitles_cached` | cached pre-rendered overlay | `6.313s` | 63 | 28 | 27 | 0 | 3 | 61 | 6 |
| `variant_24_no_avatar` | no avatar | `5.976s` | 56 | 25 | 24 | 1 | 2 | 53 | 4 |
| `variant_24_image_only` | image only | `5.764s` | 60 | 27 | 26 | 1 | 2 | 53 | 4 |
| `variant_24_video_only` | video only | `6.182s` | 60 | 27 | 26 | 1 | 2 | 53 | 4 |
| `variant_24_pre_scaled_media` | pre-scaled mixed media | `5.977s` | 62 | 27 | 26 | 1 | 3 | 59 | 5 |
| `variant_24_fast_preview_profile` | Fast Preview profile | `4.852s` | 62 | 27 | 26 | 1 | 3 | 59 | 5 |

Read: after Draft fast scaling, `sendcmd` textfile subtitles, and shared visual
transform splitting, the default subtitle path is now close to the no-subtitle
path. The explicit drawtext fallback remains slower because it restores 24
per-cue drawtext filters. ASS still regresses despite removing `drawtext`.
Pre-rendered subtitle overlays still move work into preparation; the cached
main FFmpeg pass is close to default, but the full cached scenario includes the
warmup render in its render rollup. Removing avatar, using only images, using
only video, or generating pre-scaled B-roll media still does not materially
improve the measured render time versus the current mixed baseline.
Fast Preview is the only controlled variant in this run that materially lowers
the main 24-scene FFmpeg pass without changing timeline composition semantics.

## B-roll Scale/Pad No-op Experiment

Targeted run: 2026-07-13

| Scenario | Main FFmpeg | Filter graph length | Filters | Drawtext | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| `variant_24_pre_scaled_media` official baseline | `11.691s` | 10725 | 79 | 24 | Keep as baseline. |
| `variant_24_pre_scaled_media_noop_scale_probe` | `13.227s` | 8733 | 79 | 24 | Regressed despite shorter graph. |
| `variant_24_pre_scaled_media_noop_format_probe` | `14.059s` | 9021 | 79 | 24 | Regressed further after explicit RGBA normalization. |

Read: removing scale/pad from exact-size B-roll is not a useful optimization on
the current benchmark. The likely cost shifted into FFmpeg's internal format or
overlay conversion path, so the implementation was not kept. Future work should
benchmark a different composition strategy, such as scene-segment precomposition
or a cached visual background track, instead of only shrinking filter text.

## Draft Fast Scaler Optimization

Targeted run: 2026-07-13

The Draft profile now adds `flags=fast_bilinear` to B-roll and avatar scale
filters. Standard, High Quality, Archive, and custom non-Draft settings keep
FFmpeg's default scaler behavior so review/export quality is not changed.

| Scenario | Main FFmpeg | Render rollup | Filter graph length | Filters | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| `scene_scale_24_scenes` official baseline | `14.114s` | `14.5896s` | 10725 | 79 | Baseline mixed 24-scene Draft render. |
| `variant_24_draft_fast_scaler_probe` | `12.872s` | `13.2487s` | 11245 | 79 | Kept for Draft profile. |

Read: the filter graph is slightly longer because each scale filter now carries
an explicit scaler flag, but the main FFmpeg pass improves by roughly 8.8% on
the targeted mixed 24-scene Draft scenario. This is a profile-scoped speed
optimization, not a quality-preserving change for final export profiles.

Full matrix follow-up: after keeping Draft fast scaling, the official
`scene_scale_24_scenes` run recorded `9.564s` main FFmpeg and `9.8666s` render
rollup. This replaces the pre-fast-scaler `14.114s`/`14.5896s` baseline for
future Phase 9 comparisons.

## Visual Background Precomposition Experiment

Targeted run: 2026-07-13

| Scenario | Main FFmpeg | Worker wait | Preparing | Filter graph length | Filters | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `scene_scale_24_scenes` official baseline | `9.564s` | n/a | about `0.260s` | 11245 | 79 | Keep as baseline. |
| `variant_24_visual_precomposed_probe` | `10.235s` | `15.3091s` | about `5.2497s` | 5066 | 27 | Rejected. |

Read: precomposing B-roll and Avatar into a visual background shortened the
main filter graph and removed the main-pass overlay chain, but it did not
improve the main FFmpeg pass and added a large preparation window for the
background render. The implementation was not kept to avoid dead code. The next
main-render optimization should focus on subtitle/default drawtext cost or
direct encoder/profile tuning rather than visual-background precomposition.

## Draft Encoder Preset Experiment

Targeted run: 2026-07-13

| Scenario | Main FFmpeg | Render rollup | Output size | Encoder preset | Read |
| --- | ---: | ---: | ---: | --- | --- |
| `scene_scale_24_scenes` official baseline | `9.564s` | `9.8666s` | 961737 bytes | `veryfast` | Keep as baseline. |
| `variant_24_draft_profile_superfast_probe` | `11.944s` | `12.3194s` | 1061691 bytes | `superfast` | Rejected. |
| `variant_24_draft_profile_ultrafast_probe` | `11.776s` | `12.1683s` | 1506524 bytes | `ultrafast` | Rejected. |

Read: switching the Draft profile encoder preset from `veryfast` to faster x264
presets does not improve this 24-scene workload. The main pass slows down and
output size increases, especially with `ultrafast`. The runtime keeps Draft on
`veryfast`. Benchmark-only custom preset probes are still useful for future
experiments, but the current bottleneck is not solved by simply moving to a
faster x264 preset.

## Sendcmd Textfile Subtitle Default

Targeted and full-matrix runs: 2026-07-13

| Scenario | Main FFmpeg | Render rollup | Filter graph length | Filters | Drawtext | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `scene_scale_24_scenes` previous official drawtext baseline | `9.564s` | `9.8666s` | 11245 | 79 | 24 | Historical baseline. |
| `variant_24_drawtext_subtitles_probe` | `11.335s` | `11.6593s` | 11245 | 79 | 24 | Explicit fallback path. |
| `variant_24_sendcmd_textfile_subtitles_probe` | `8.649s` | `9.0129s` | 6642 | 56 | 1 | Promoted to default. |
| `scene_scale_24_scenes` full matrix default | `8.619s` | `8.9683s` | 6642 | 56 | 1 | New official baseline. |
| `variant_24_drawtext_subtitles` full matrix fallback | `11.407s` | `11.728s` | 11245 | 79 | 24 | Fallback comparison. |

Read: the default subtitle renderer now uses `RENDER_SUBTITLE_MODE=sendcmd`.
The renderer writes each subtitle cue into a temporary UTF-8 text file and uses
a temporary FFmpeg command file to reinitialize one named
`drawtext@subtitle` filter with `textfile=` at cue boundaries. This avoids
putting subtitle text through the FFmpeg command parser, so apostrophes, percent
signs, colons, quotes, line breaks, and Unicode text stay in ordinary text
files. The default path reduces the 24-scene subtitle graph from 24 drawtext
filters to 1 and improves the official full-matrix 24-scene render rollup from
the previous `9.8666s` to `8.9683s`. The old per-cue drawtext renderer remains
available with `RENDER_SUBTITLE_MODE=drawtext` for fallback and comparisons.

## Visual Transform Split Optimization

Targeted and full-matrix runs: 2026-07-13

| Scenario | Main FFmpeg | Render rollup | Filter graph length | Filters | Split | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `scene_scale_24_scenes` previous sendcmd baseline | `8.619s` | `8.9683s` | 6642 | 56 | 0 | Historical baseline. |
| `variant_24_visual_transform_split_probe` | `6.053s` | `6.4294s` | 4601 | 62 | 3 | Promoted to default. |
| `scene_scale_24_scenes` full matrix default | `5.969s` | `6.3251s` | 4601 | 62 | 3 | New official baseline. |

Read: the command builder now groups repeated visual inputs by input index and
visual role, applies the role-specific scale/pad/setsar transform once, then
uses FFmpeg `split` to feed per-clip trim/setpts filters. This keeps each
timeline clip independently timed while avoiding repeated scale/pad work for
the same cached B-roll, video, or Avatar media. Filter count increases because
split and timing are separate filters, but filter graph text is shorter and the
measured 24-scene Draft main pass improves by roughly `2.65s` versus the
previous sendcmd baseline.

## Overlay Chain Follow-up Experiments

Targeted runs: 2026-07-13

| Scenario | Main FFmpeg | Render rollup | Filter graph length | Filters | Overlays | Read |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `scene_scale_24_scenes` official baseline | `5.969s` | `6.3251s` | 4601 | 62 | 26 | Keep as baseline. |
| `variant_24_overlay_enable_probe` | `6.069s` | `6.4191s` | 5472 | 62 | 26 | Rejected; longer graph and no speed gain. |
| `variant_24_scene_window_batching_probe` | `8.668s` | `9.0225s` | 7119 | 88 | 26 | Rejected; concat/base split/extra trims outweighed shorter per-scene overlay depth. |
| `variant_24_overlay_eval_init_probe` | `6.068s` | `6.4351s` | 4861 | 62 | 26 | Rejected; fixed-position expression initialization did not improve the pass. |
| `overlay_depth_48_scenes` | `10.732s` | `11.1095s` | 8129 | 110 | 50 | Measurement only; confirms remaining render cost scales with scene/overlay count. |

Read: after transform splitting, simple overlay-chain tweaks are not currently
better than the linear overlay graph. Adding `enable=between(...)` and
`eval=init` both add filter text without reducing measured render time.
Scene-window batching inside one filter graph reduces the conceptual overlay
depth per scene, but the extra base splits, trims, and concat filter make it
slower on the deterministic 24-scene workload. The next useful render work
should measure a different dimension, such as output duration/scene assignment
API cost, or prototype a cached visual track only if it can avoid the expensive
preparation window seen in earlier visual precomposition.

## Timeline Assignment Batch Optimization

Targeted and full-matrix runs: 2026-07-13

| Scenario | Scenes | Timeline assignment | Workflow rollup | Total | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| `overlay_depth_48_scenes` previous per-scene assignment | 48 | `2.4551s` | `2.8337s` | `18.299s` | Historical 48-scene workflow measurement. |
| `timeline_assignment_batch_48_scenes_probe` | 48 | `0.1228s` | `0.5626s` | `16.13s` | Promoted to benchmark/default workflow. |
| `scene_scale_24_scenes` previous full matrix | 24 | about `1.2994s` | `1.6735s` | `12.483s` | Historical full-matrix workflow baseline. |
| `scene_scale_24_scenes` full matrix with batch assignment | 24 | about `0.104s` | `0.5264s` | `11.147s` | New official baseline. |

Read: the benchmark and API now use `PUT /api/timeline/media-assignments` to
apply many B-roll/Avatar assignments in one Timeline mutation. The service loads
the current timeline once, reads the cache manifest once, validates all scene
and asset references, and saves once. The older per-scene API remains available
for interactive single-scene edits. This removes the benchmark's repeated
load/validate/save cost and keeps workflow timing nearly flat as scene count
grows through the official matrix.

## Render Duration vs Overlay Depth Benchmark

Targeted run: 2026-07-13

The Phase 9 benchmark now accepts `PHASE9_PERF_SCENARIO_DURATION_SECONDS` so a
scenario can keep scene count fixed while lengthening each imported SRT cue. The
generated video and music assets are extended to match the requested timeline
length, and the result JSON records `timelineDurationSeconds` for comparison.

| Scenario | Scenes | Seconds/scene | Timeline | Main FFmpeg | Render rollup | Filters | Overlays | Read |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `duration_depth_24x2` | 24 | 2 | 48s | `6.064s` | `6.4098s` | 62 | 26 | Baseline same shape as official 24-scene matrix. |
| `duration_depth_12x4` | 12 | 4 | 48s | `6.295s` | `6.6478s` | 38 | 14 | Same output duration with fewer overlays was not faster. |
| `duration_depth_24x4` | 24 | 4 | 96s | `11.045s` | `11.3787s` | 62 | 26 | Same overlay count with double duration nearly doubled main render time. |
| `duration_depth_48x2` | 48 | 2 | 96s | `10.951s` | `11.3617s` | 110 | 50 | Same output duration with many more overlays matched the 24x4 render time. |
| `duration_depth_24x8` | 24 | 8 | 192s | `21.021s` | `21.3723s` | 62 | 26 | Longer output continues near-linear duration scaling. |

Read: after subtitle sendcmd and shared visual transforms, the remaining Draft
render bottleneck is dominated by output duration/encode work more than overlay
graph depth on this deterministic mixed-media benchmark. At the same 48s output,
reducing overlays from 26 to 14 did not improve render time. At the same 96s
output, increasing overlays from 26 to 50 did not materially increase render
time. The next optimization should therefore target duration-proportional work:
Draft preview FPS/resolution policy, lower-cost visual/audio preview settings,
or a separate fast-preview profile, rather than more overlay graph reshaping.

## Fast Preview Profile Optimization

Targeted run: 2026-07-13

The Render Engine now exposes a named `Fast Preview` profile for quick review
passes on long timelines. It keeps Draft unchanged for existing review quality,
then adds an explicit lower-cost profile at 640x360, 15 FPS, CRF 32, veryfast
x264, and 96 kbps audio. Like Draft, it uses `fast_bilinear` scaling because it
is a speed-oriented preview profile, not a final export profile.

| Scenario | Profile | Timeline | Resolution/FPS | Main FFmpeg | Render rollup | Output size | Read |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| `duration_depth_24x4` | Draft | 96s | 854x480 / 24 FPS | `11.045s` | `11.3787s` | 1717271 bytes | Baseline. |
| `duration_policy_24x4_fast_preview` | Fast Preview | 96s | 640x360 / 15 FPS | `8.643s` | `8.9773s` | 1268841 bytes | Kept; about 21.7% faster main pass. |
| `duration_depth_24x8` | Draft | 192s | 854x480 / 24 FPS | `21.021s` | `21.3723s` | 3422051 bytes | Baseline. |
| `duration_policy_24x8_fast_preview` | Fast Preview | 192s | 640x360 / 15 FPS | `16.504s` | `16.8742s` | 2524743 bytes | Kept; about 21.5% faster main pass. |
| `scene_scale_24_scenes` full matrix | Draft | 48s | 854x480 / 24 FPS | `6.093s` | `6.4503s` | 864598 bytes | Official matrix baseline. |
| `variant_24_fast_preview_profile` full matrix | Fast Preview | 48s | 640x360 / 15 FPS | `4.852s` | `5.1952s` | 640762 bytes | Kept; about 20.4% faster main pass. |

Read: Fast Preview directly attacks the duration-proportional cost identified
by the previous benchmark. It improves both 96s and 192s long-output probes by
roughly the same percentage, which is the shape we want for review renders. It
does not replace Draft, Standard, High Quality, or Archive; operators can choose
it when speed matters more than review fidelity.

## Five-Minute Preview Target Probe

Targeted run: 2026-07-14

PROJECT.md sets the product target that a 5-minute video should render in less
than 10 minutes. This probe uses the deterministic Phase 9 synthetic workflow
with 25 SRT scenes at 12 seconds each, producing a 300-second timeline through
the same public script, cache, timeline, preflight, render queue, report, and
bundle APIs. Long synthetic music is generated as compressed audio so the probe
measures render duration instead of inflated WAV cache overhead.

| Scenario | Profile | Timeline | Resolution/FPS | Main FFmpeg | Render rollup | Total workflow | Output size | Read |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `duration_target_5min_draft` | Draft | 300s | 854x480 / 24 FPS | `71.279s` | `71.7219s` | `82.714s` | 3342667 bytes | Passes the 10-minute product target with wide headroom. |
| `duration_target_5min_fast_preview` | Fast Preview | 300s | 640x360 / 15 FPS | `47.915s` | `48.294s` | `58.811s` | 3141662 bytes | Faster review path; about 32.8% faster main pass than Draft. |

Read: both preview-oriented profiles are far below the 600-second target on the
current deterministic benchmark machine. Fast Preview is useful for long review
loops, but the data does not justify adding an even lower-fidelity `Ultra Fast
Preview` profile yet. Keep the profile set stable until a real-world 5-minute
corpus or slower packaged-machine smoke shows the current profiles approaching
the target.

## Five-Minute Standard Export Probe

Targeted run: 2026-07-14

This follow-up keeps the same 300-second target length but exercises the final
export path with the `Standard` profile: 1920x1080, 30 FPS, CRF 18, `medium`
x264, and 192 kbps audio. The benchmark fixture generates five distinct
provider-style long video clips, one image, one avatar overlay, one compressed
music bed, and 24 extra cache entries. The media is still deterministic and
local so the result is repeatable without live provider credentials, but the
cache and render shape is closer to a real project than the earlier preview
probe.

| Scenario | Profile | Timeline | Cache entries | Inputs | Filters | Main FFmpeg | Render rollup | Total workflow | Output size | Read |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `duration_target_5min_realistic_standard` | Standard | 300s | 32 | 8 | 70 | `89.166s` | `89.5884s` | `130.308s` | 65646716 bytes | Passes the 10-minute product target with wide headroom. |

Read: Standard final export remains comfortably below the PROJECT.md target on
this benchmark machine. The full workflow includes about `30.704s` of synthetic
asset generation that an already-cached real project would not pay during the
render action. The measured render path itself is about `89.6s`, leaving more
than eight minutes of headroom against the 600-second target. The next useful
measurement is therefore not another lower-quality preview profile; it is a
real-media corpus or packaged desktop run that removes synthetic fixture bias.

## Five-Minute Real Provider Corpus Probe

Targeted run: 2026-07-14

The live-provider probe uses the same Phase 9 workflow but searches and caches
real provider media through `/api/media/search` and `/api/media/cache` before
Timeline assignment. Because no reusable provider-video cache was present in
the workspace or app-data folders, the run created a fresh corpus using the
configured provider credentials. The selected corpus contains four Pexels
videos and two Pexels images for query `city documentary`; videos shorter than
the 12-second scene duration are cached but excluded from assignment. The High
Quality run reloads the `liveCorpus.selected` list from the Standard JSON
report so both profiles render the same media sources.

| Scenario | Profile | Timeline | Live media | Inputs | Filters | Cache rollup | Main FFmpeg | Render rollup | Total workflow | Output size | Read |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `duration_target_5min_real_provider_standard` | Standard | 300s | 4 videos / 2 images | 7 | 68 | `66.5759s` | `163.276s` | `163.6913s` | `240.624s` | 276774887 bytes | Passes the 10-minute target. |
| `duration_target_5min_real_provider_high_quality` | High Quality | 300s | 4 videos / 2 images | 7 | 68 | `30.4111s` | `330.635s` | `331.0295s` | `371.978s` | 368183453 bytes | Passes the 10-minute target with less headroom. |

Read: real provider media is heavier than generated fixtures, especially when
the selected source videos are 1080p/4K. Even so, Standard finishes in about
4.0 minutes end-to-end and High Quality in about 6.2 minutes end-to-end, both
under the 600-second PROJECT.md target. Final export optimization is therefore
not the immediate Phase 9 bottleneck for the target machine. The stronger next
signal is cache/search responsiveness: live corpus creation took `66.5759s`
when searching/downloading/selecting media, and the UI should make that work
visible, resumable, and less repetitive before further encoder tuning.

## Media Search and Cache UX First Pass

Targeted update: 2026-07-14

The first non-render Phase 9 change keeps the existing Media Search, Media
Cache, and Timeline Media APIs unchanged and improves the Media workspace
feedback loop. Search, cache download, and assignment now share a lightweight
activity panel with elapsed time, current action, staged progress labels, and a
completion/error result. Backend services remain authoritative for provider
requests, download validation, content hashing, manifest writes, and timeline
assignment; the panel is presentation-only so it cannot drift cache state.

Read: this addresses the immediate user-facing gap found by the live-provider
corpus probe. Long media searches and downloads no longer appear as a single
static status line, and the existing backend contracts remain stable for the
next deeper cache/search measurements.

## Media Search and Cache Timing Breakdown

Targeted run: 2026-07-14

Cache responses now include bounded timing diagnostics for benchmark and debug
use. The diagnostics expose provider ID, duplicate state, byte size, source
transfer plus SHA-256 streaming time, file-write time, duplicate/fingerprint
checks, metadata probe time, manifest commit time, and total cache time. They do
not include source URLs, local paths beyond the existing cached path field, API
keys, request headers, or provider credentials.

The deterministic local baseline keeps network variance out of the first read:

| Scenario | Cache writes | Total cache rollup | Source transfer | SHA-256 | File write | Duplicate check | Fingerprint | Metadata | Manifest | Read |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline_6_scenes_4_cache` | 5 including duplicate | `1.0428s` | `0.0482s` | `0.0167s` | `0.0026s` | `0.1031s` | `0.3749s` | `0.3653s` | `0.0272s` | Local fingerprint and metadata probe dominate cache work; manifest writes are small. |

A small live Pexels probe measured provider latency, cache write, and the UI
refresh calls that MediaPage performs after a download:

| Probe | Count | Total | Average | Max | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| Provider search | 2 | `2.296s` | `1.148s` | `1.1849s` | Search latency is visible but not the largest cost in this probe. |
| Cache write | 3 | `8.935s` | `2.9783s` | `3.9217s` | Download/cache write dominates the live media path. |
| UI refresh | 3 | `0.2343s` | `0.0781s` | `0.1063s` | Cache manifest plus Timeline media asset refresh is not currently the bottleneck. |

Live cache diagnostics for the three Pexels assets totalled `3.9228s` source
transfer, `4.426s` fingerprinting, `0.508s` metadata probing, `0.0188s`
manifest commit, and `8.9102s` total cache service time. The next optimization
target should therefore be media fingerprint/cache-write cost and possibly
backgrounding or reusing fingerprints for provider assets, not frontend refresh
or manifest writes.

## Provider Fingerprint Deferral

Targeted update: 2026-07-14

Provider downloads now avoid blocking the `/api/media/cache` request on
perceptual image hash or video fingerprint generation when the manifest does
not already contain a fingerprint for that content hash. The file is still
streamed, SHA-256 hashed, validated, atomically promoted, metadata-probed when
needed, and written to the manifest before the response returns. Fingerprint
enrichment then runs in a guarded background worker keyed by cache root and
content hash, merging the fingerprint into the manifest under the existing
manifest lock. Local Library imports keep synchronous fingerprinting so local
deduplication behavior and existing tests remain stable.

Small live Pexels probe before and after deferral:

| Probe | Before | After | Change | Read |
| --- | ---: | ---: | ---: | --- |
| Cache write total, 3 provider assets | `8.935s` | `4.8342s` | `-45.9%` | Main user-visible download/cache wait is nearly halved. |
| Average cache write | `2.9783s` | `1.6114s` | `-45.9%` | Improvement tracks removed request-path fingerprint work. |
| Request-path fingerprint time | `4.426s` | `0.0s` | removed | Three provider fingerprints were deferred. |
| Source transfer | `3.9228s` | `4.1735s` | network variance | Transfer is now the dominant live cache cost. |
| UI refresh average | `0.0781s` | `0.073s` | unchanged | Frontend refresh remains small. |

Read: fingerprint deferral is the first kept Media optimization because it
directly targets the measured bottleneck without weakening cache hashing,
provider trust validation, atomic file promotion, or manifest persistence.
Remaining provider cache time is mostly network/source transfer and video
duration probing. Fingerprints deferred by an interrupted short-lived worker are
recovered by the durable fingerprint backfill job described below.

## Durable Fingerprint Backfill

Targeted update: 2026-07-14

Deferred provider fingerprints now have an explicit recovery path. Media Cache
can scan the active project manifest for cached images and videos whose
perceptual hash or video fingerprint is missing, fingerprint each existing
cache file, and merge the result back into `cache/manifest.json` under the
existing manifest lock. A `MediaFingerprintBackfillService` owns one job per
project, exposes progress/cancel/status, and is started automatically when a
project is opened so interrupted provider fingerprint work can resume after a
backend or desktop restart.

API surface:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/media/cache/fingerprints/backfill` | Start or reuse the active project's fingerprint backfill job. |
| `GET /api/media/cache/fingerprints/backfill/status` | Return queued/running/completed/cancelled/failed status and counts. |
| `POST /api/media/cache/fingerprints/backfill/cancel` | Request cancellation for the active project's job. |

Read: this closes the reliability gap introduced by provider fingerprint
deferral. Cache writes stay fast, while near-duplicate deduplication can recover
missing fingerprints for old cache entries and provider downloads interrupted
before the short-lived background worker finished.

UI status: Media and Settings now include a compact `Duplicate check` chip that
reads the durable backfill status endpoint, polls only while enrichment is
queued or running, and surfaces ready, paused, failed, and progress states in
the app.

## Provider Search Concurrency

Targeted update: 2026-07-14

Mixed image/video provider searches were reviewed after fingerprint enrichment
became visible in the UI. The cross-provider search service already fans out
registered providers concurrently, so the next safe latency target was inside
individual providers. Pexels, Pixabay, and DVIDS now run independent media-type
lookups concurrently for mixed image/video queries. DVIDS also hydrates asset
details with a bounded concurrency limit of five requests so per-asset detail
lookups do not serialize a full result page.

Follow-up DVIDS optimization first kept the public search response shape
unchanged but avoided resolving asset details for results outside the requested
page. DVIDS then moved to true lazy detail: search now returns summary metadata
plus a backend-only `dvids://asset/...` source token, and Media Cache resolves
`/asset` details only when the operator selects a result to download. This keeps
the detail cache, negative cache, and retry behavior intact while removing
eager `/asset` calls from the search path.

Verification:

| Probe | Result | Read |
| --- | ---: | --- |
| Provider concurrency unit tests | Pexels, Pixabay, and DVIDS passed | Tests assert overlapping image/video requests and bounded DVIDS asset hydration while preserving result order. |
| Local Phase 9 gate `phase9_media_provider_concurrency_local_gate` | `7.559s` total, cache rollup `0.9816s`, workflow rollup `0.503s` | Local workflow/cache/render behavior remains stable after provider changes. |
| Live workflow probe | Pexels filled the 2 video + 1 image corpus | Provider search averaged `1.1104s`, cache write averaged `1.6368s`, and UI refresh averaged `0.0949s`. |
| Search-only mixed provider probe | Pexels `1.268s`, Pixabay `3.3889s`, DVIDS `17.4154s` | DVIDS is the clear live search latency outlier for `image+video` limit 10. Pixabay hit one 429 retry during this run. |
| Search-only mixed provider probe after demand-sized DVIDS hydration | Pexels `1.3305s`, Pixabay `3.3212s`, DVIDS `10.2036s` | DVIDS improved by about 41% for `image+video` limit 10. Pixabay hit one 429 retry during this run. |
| DVIDS lazy-detail live smoke | Search `2.8325s`, 10 items, total results 79; selected-item cache `5.0425s`, 3,036,952 bytes | DVIDS search now returns `dvids://asset/...` summary results and resolves/downloads the real asset only when caching the selected item. |

Read: provider latency is now structurally improved for mixed searches without
changing public API contracts. The live follow-up shows cache refresh UI is not
the next bottleneck: it remains below `0.15s` per refresh in this probe. Further
Media optimization should next compare repeated-query cache hits and provider
result streaming only if product UX still needs DVIDS to feel closer to
Pexels/Pixabay under high latency; cache refresh UI is still not the measured
bottleneck.

## Repeated Search and Mixed Provider Probe

Targeted run: 2026-07-14

`scripts/benchmark_phase9_media_live.ps1` records the optional live-provider
search/cache probe to `.tmp/phase9-media-live-search-cache.json`. It uses
configured provider credentials, so it remains outside the deterministic quality
gate. The first run used query `city documentary`, mixed image/video results,
and limit 10.

| Probe | Cold | Warm | Read |
| --- | ---: | ---: | --- |
| Pexels repeated search | `1.2926s` | `0.9579s` | Pexels remains network-bound; there is no persistent search cache signal here. |
| Pixabay repeated search | `5.0401s` failed with 429 | `1.3517s` | Rate-limit variance is still visible, but the repeated request recovered. |
| DVIDS repeated search | `2.3459s` | `0.0843s` | Persistent search cache plus lazy detail makes repeated DVIDS browsing effectively local. |
| Mixed `providerId=all` | `5.7242s` | `0.9486s` | Warm mixed search is bounded by provider latency, not ranking/merge. |
| Estimated mixed ranking/merge overhead | n/a | `0.0s` | Ranking/dedup is not the next measured bottleneck for this result size. |
| Selected-item DVIDS cache | `4.197s` | duplicate `3.3751s` | Source transfer dominates both first download and duplicate cache attempt. |
| Cache manifest refresh | n/a | `0.0319s` | UI/cache refresh is still small. |
| Selected-item DVIDS cache after source-hit fast path | `4.4567s` | duplicate `0.0403s` | Exact remote source matches now return the manifest entry without repeat remote download or hashing. |

Read: after lazy DVIDS detail, repeated search cache hits are working and
mixed-provider ranking/merge is not the limiting cost in this probe. The
measured duplicate cache bottleneck has been removed for remote providers:
when the exact same provider/media/source is already in the manifest and the
file still exists, the cache service refreshes access time and returns the
existing entry. The live DVIDS duplicate path dropped from `3.3751s` to
`0.0403s`, with duplicate `sourceTransferSeconds` now `0.0s`. Local Library
imports still rehash to detect files that changed in place.

Follow-up mixed-provider UX run after duplicate-cache fast path:

| Probe | Result | Read |
| --- | ---: | --- |
| Pexels repeated search | cold `1.5766s`, warm `1.0136s` | Still network-bound; no local persistent search-cache signal. |
| Pixabay repeated search | cold `5.2578s` failed 429, warm `2.8077s` | Rate-limit variance is the largest visible provider issue in this run. |
| DVIDS repeated search | cold `2.4485s`, warm `0.1051s` | Persistent cache plus lazy detail remains effectively local after warmup. |
| Mixed `providerId=all`, limit 10 | cold `2.9982s`, warm `1.032s` | Warm mixed UX is bounded by the slowest live provider, not local merge. |
| Cached-media reselect, 3 items | average `0.0569s`, max `0.0659s` | Re-selecting already cached DVIDS/Pexels/Pixabay media is now quick enough for UI flow. |
| Cache refresh, 3 entries | average `0.021s`, max `0.0667s` | Small-cache UI refresh is not a bottleneck. |
| Cache refresh, 250 entries | average `0.0336s`, max `0.0378s` | Manifest list/read remains small even after a larger project-cache sample. |
| Mixed `providerId=all`, limit 40, 250 cache entries | cold `5.9899s`, warm `1.1447s` | Larger result pages still mainly expose provider latency. |
| Synthetic ranking/merge, 120 candidates and 250 cache entries | `0.0321s` | Local ranking, fingerprint index build, and dedup are not the next optimization target at this scale. |

Read: the duplicate-cache fix moved cached media selection out of the critical
path. Cache refresh and ranking/merge stay below a tenth of a second in this
sample, including a 250-entry manifest. The next measured Media optimization
candidate is provider-facing UX: surfacing cached/stale results while slow or
rate-limited providers finish, or adding clearer partial-result feedback for
Pixabay/DVIDS variance.

Provider-facing UX update: the Media workspace now treats `All providers` as a
responsive UI fan-out. It starts individual provider searches, updates the
result grid as each provider returns, and shows per-provider pending, ready, or
error chips. A provider that is still waiting or rate-limited no longer blocks
already-available Pexels/Pixabay/Wikimedia/DVIDS results from being shown and
downloaded. This is intentionally a UI responsiveness layer over existing
Media Search APIs; backend aggregate ranking/dedup contracts remain unchanged.

Large-cache Media workspace refresh probe: `backend/benchmark_phase9_media_live.py`
now records `workspaceRefreshByCacheSize` for cache manifests seeded at
configurable sizes through `PHASE9_MEDIA_LIVE_REFRESH_CACHE_SIZES`. The probe
measures the same refresh chain used by `MediaPage`: cache manifest read,
timeline media asset list, and the UI-side visual asset projection.

Targeted run: 2026-07-14, cache sizes `250,1000,2500`, output
`.tmp/phase9-media-live-cache-refresh-large.json`. Provider calls were
unavailable during this run, so the provider rows are not used for decisions;
the seeded cache refresh measurements are still valid for the local large-cache
path.

| Cache entries | Workspace refresh avg | Manifest avg | Timeline assets avg | UI projection avg | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| 250 | `0.5839s` | `0.0279s` | `0.5516s` | `0.0004s` | Noticeably larger than manifest-only refresh, but still tolerable. |
| 1000 | `2.1905s` | `0.0892s` | `2.0829s` | `0.0023s` | Large-cache Media refresh becomes visible to the user. |
| 2500 | `5.0913s` | `0.1841s` | `4.8649s` | `0.0034s` | Timeline media asset construction is the clear bottleneck. |

Read: the earlier 250-entry manifest-only measurement understated the UX cost
because Media workspace also calls `/api/timeline/media-assets`. The frontend
projection work is negligible; the expensive path is backend asset listing,
which resolves every cache entry path and checks file/media type on every
refresh. The next measured Media optimization should target cached or indexed
timeline media asset listing, pagination/windowing for the cached media panel,
or avoiding a full asset refresh after unrelated provider search state changes.

Windowed cached-media panel update: `/api/timeline/media-assets` now accepts
`offset` and `limit` while preserving the old full-list behavior when no
pagination parameters are supplied. Media workspace requests the first 100
cached assets, sorts recent cache access first, and exposes a "Load more cached
media" action for large project caches. This keeps initial refresh bounded by
the visible window while assignment, Timeline, and legacy full-list callers can
continue to use existing contracts.

Targeted follow-up run: 2026-07-14, cache sizes `250,1000,2500`, output
`.tmp/phase9-media-live-cache-refresh-windowed.json`.

| Cache entries | Before avg | Windowed avg | Timeline assets avg | Read |
| --- | ---: | ---: | ---: | --- |
| 250 | `0.5839s` | `0.2565s` | `0.2325s` | First cached panel page is about 56% faster. |
| 1000 | `2.1905s` | `0.3107s` | `0.2381s` | First refresh no longer scales with the full cache. |
| 2500 | `5.0913s` | `0.4653s` | `0.2874s` | Meets the Phase 9 first-paint target below `0.5s`. |

Read: windowing is the right first optimization for cache-heavy Media UX. The
remaining growth at 2500 entries comes mostly from reading the manifest itself,
not statting every asset. Further optimization should only add an indexed asset
store if real projects exceed this cache size enough for manifest read to become
visible again.

## Drawtext Pixel Format Experiment

Targeted run: 2026-07-13

| Scenario | Main FFmpeg | Render rollup | Filter graph length | Filters | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| `scene_scale_24_scenes` official baseline | `9.564s` | `9.8666s` | 11245 | 79 | Keep as baseline. |
| `variant_24_drawtext_yuv_probe` | `11.750s` | `12.0979s` | 11288 | 80 | Rejected. |

Read: converting the composed video stream to `yuv420p` once before the
default per-cue `drawtext` chain did not reduce subtitle cost. It added one
filter, slightly lengthened the graph, and regressed the measured main FFmpeg
pass by about `2.186s` versus the official mixed 24-scene baseline. The runtime
keeps the existing RGBA composition through `drawtext` and converts to
`yuv420p` only at the final output step.

## Subtitle Overlay Background Preparation

Latest targeted and full-matrix runs: 2026-07-13

Cold subtitle pre-render now runs inside the render queue worker instead of the
request that creates the job. The public queue request creates a validated
render draft and returns quickly; the worker then prepares the full render plan,
including subtitle overlay generation/cache lookup, before starting FFmpeg.

| Scenario | Queue request | Worker wait | Main FFmpeg | Read |
| --- | ---: | ---: | ---: | --- |
| `variant_24_prerendered_subtitles` | `0.0298s` | `20.6285s` | `10.682s` | Cold overlay generation moved off request path. |
| `variant_24_prerendered_subtitles_cached` warmup | `0.0375s` | `20.894s` | n/a | First render populates subtitle overlay cache. |
| `variant_24_prerendered_subtitles_cached` cache hit | `0.0321s` | `10.4517s` | `10.408s` | Repeat export skips overlay generation. |
| `variant_24_prerendered_subtitles_status_probe` | `0.0322s` | `20.6394s` | `10.336s` | Polling observed `preparing` for about `10.475s`, then `running` for about `10.1474s`. |
| `variant_24_prerendered_subtitles_12fps_probe` | `0.0402s` | `17.2677s` | `10.246s` | Subtitle overlay defaults to 12 FPS; `preparing` dropped to about `7.1298s`. |
| `variant_24_prerendered_subtitles_8fps_probe` | `0.0307s` | `14.0809s` | `9.639s` | `preparing` dropped to about `4.4451s`; timing granularity is about `125ms`. |
| `variant_24_prerendered_subtitles_6fps_probe` | `0.0348s` | `13.5625s` | `9.591s` | `preparing` dropped to about `4.1929s`; extra gain over 8 FPS is small while timing granularity worsens to about `167ms`. |
| `variant_24_prerendered_subtitles` full matrix, 8 FPS | `0.0521s` | `16.8171s` | `10.816s` | Official matrix baseline observed `preparing` for about `6.1237s`. |
| `variant_24_prerendered_subtitles_cached` cache hit full matrix, 8 FPS | `0.0261s` | `8.2417s` | `8.202s` | Repeat export skips cold overlay generation in the official matrix run. |

Read: moving cold pre-render into worker fixes render request latency without
reducing cold total job time. The cached path now has the useful shape for
repeat exports: request latency stays low and worker time is close to the main
FFmpeg pass. The queue now exposes a distinct `preparing` status with
"Preparing subtitles" UI copy while the worker generates or resolves the
subtitle overlay before FFmpeg progress begins. The benchmark status probe
captures status samples in the benchmark JSON so this preparation window is
visible in performance reports even though durable render history still records
the final job status after completion.

## Subtitle Overlay FPS Optimization

Cold subtitle pre-render now renders the transparent subtitle overlay at
`RENDER_SUBTITLE_OVERLAY_FPS`, defaulting to 8 FPS and capped by the export
frame rate. The main render still exports at the selected profile FPS while
FFmpeg repeats subtitle overlay frames between subtitle changes. The cache key
includes the overlay FPS so older 24 FPS or 12 FPS overlay caches are not reused
for the new lower-FPS renderer. In the 24-scene Draft probe, 8 FPS reduced the
visible `preparing` window from about `10.475s` to about `4.4451s`. A 6 FPS
probe only reduced `preparing` to about `4.1929s`, so 8 FPS is the better
default because it keeps subtitle timing granularity near `125ms` while
capturing most of the performance gain. The full matrix run is noisier than the
single-scenario probe and observed about `6.1237s` of cold `preparing`, but it
still becomes the official baseline because it measures the same workload shape
as the rest of Phase 9.

## Optimization Candidates

- [x] Render: reuse duplicate visual inputs in FFmpeg command construction for
      24+ scene timelines before changing profiles or command composition.
- [x] Render: inspect filter graph and overlay-chain cost for 24+ scene
      timelines now that input fan-out is flat.
- [x] Render: benchmark controlled 24-scene variants for no subtitles, no
      avatar, image-only, video-only, and pre-scaled media.
- [x] Render: add ASS/subtitle sidecar benchmark path. It reduces filter count
      but is slower than drawtext on the current local benchmark, so drawtext
      remains the default.
- [x] Render: try true subtitle pre-render into a transparent video overlay.
      Main FFmpeg render improves, but overlay generation makes total render
      rollup slower than drawtext.
- [x] Render: cache subtitle pre-render overlays by timeline/settings hash.
      Cache hits remove almost all pre-render queue cost for repeated exports,
      but cold exports still need the expensive overlay generation step.
- [x] Render: move cold subtitle pre-render into the render queue worker so job
      creation is no longer blocked by overlay generation.
- [x] Render: expose worker preparation progress/status before reconsidering
      pre-render as a default render path.
- [x] Render: lower cold subtitle overlay pre-render FPS by default and include
      that FPS in the subtitle overlay cache key.
- [x] Render: benchmark a guarded no-op scale/pad path for already matching
      B-roll dimensions. It regressed versus baseline, so it was rejected.
- [x] Render: use FFmpeg `fast_bilinear` scaling for Draft profile only. The
      targeted mixed 24-scene main render improved from `14.114s` to `12.872s`.
- [x] Render: benchmark visual background precomposition for the 24-scene main
      pass. It reduced filter graph length but regressed main FFmpeg and total
      worker time, so it was rejected.
- [x] Render: benchmark Draft encoder presets `superfast` and `ultrafast`.
      Both regressed versus `veryfast`, so Draft keeps `veryfast`.
- [x] Render: harden `sendcmd` subtitles with per-cue text files, then promote
      it to the default subtitle renderer. The old per-cue drawtext path remains
      available through `RENDER_SUBTITLE_MODE=drawtext`.
- [x] Render: share repeated visual scale/pad transforms and split the prepared
      stream into per-clip timing filters. The official 24-scene Draft render
      rollup improved from `8.9683s` to `6.3251s`.
- [x] Render: benchmark overlay follow-ups after transform splitting:
      `enable=between(...)`, scene-window batching, and fixed-position
      `eval=init`. All regressed versus the current linear overlay baseline, so
      none were kept.
- [x] Workflow: batch Timeline media assignment so generated workflows can
      assign B-roll and Avatar media for many scenes with one validated save.
      The 48-scene assignment probe dropped from `2.4551s` to `0.1228s`.
- [x] Render: benchmark a default drawtext pixel-format optimization by
      converting to `yuv420p` before subtitle drawing. It regressed versus the
      current baseline, so the existing final-output conversion remains.
- [x] Cache: separate source transfer, SHA-256 hash, file write, duplicate
      checks, fingerprinting, metadata, and manifest commit timing in cache
      diagnostics.
- [x] Cache: short-circuit exact remote source duplicates from the manifest
      when the cached file still exists, avoiding repeat provider download and
      hashing.
- [x] Media UX: benchmark repeated mixed-provider search, cached-media
      reselection, cache refresh, and ranking/merge with a larger cache
      manifest after the duplicate-cache fast path.
- [x] Media UX: show provider-facing partial results and per-provider
      pending/error status for `All providers` searches so slow or rate-limited
      providers do not block ready results.
- [x] Media UX: measure full Media workspace cache refresh at larger cache
      sizes. The 2500-entry probe shows `/api/timeline/media-assets` dominates
      refresh time while manifest read and frontend projection remain small.
- [x] Media UX: optimize large-cache timeline media asset listing with a
      windowed cached media panel. The 2500-entry first refresh dropped from
      `5.0913s` to `0.4653s`.
- [x] Workflow: measure scene/timeline operations at 50+ scenes before changing
      repository persistence. Batch assignment removed the clearest 48-scene
      workflow bottleneck without changing repository storage.
- [x] Startup: move packaged sidecar startup timing to Phase 10 release
      validation and CI hardening. The measurement depends on release artifacts
      and installed-app context, while Phase 9 runtime workflow/render/cache
      targets are already benchmarked and met.

## Guardrails

- Do not optimize without a before/after benchmark artifact.
- Keep the default benchmark deterministic and credential-free.
- Treat live provider timing as a separate optional benchmark because network
      variance would make the local baseline noisy.
- Keep output JSON small enough to compare in review; do not persist generated
      media in the benchmark result.

## Phase 9 Closure Decision

Closure date: 2026-07-14

Required to close Phase 9:

- [x] Deterministic workflow/render/cache matrix exists and is documented.
- [x] Render command growth, subtitle cost, repeated visual transforms, and
      timeline assignment bottlenecks were measured and optimized or rejected
      with benchmark evidence.
- [x] Five-minute Draft, Fast Preview, Standard, and real-provider Standard/High
      Quality probes remain under the PROJECT.md target of rendering a
      five-minute video in under 10 minutes on the benchmark machine.
- [x] Media provider latency, duplicate cache, background fingerprint
      enrichment, durable fingerprint recovery, partial provider results, and
      large-cache Media workspace refresh were measured and optimized.
- [x] The largest remaining measured Media UX issue, 2500-entry cached media
      refresh, dropped from `5.0913s` to `0.4653s` first refresh with windowing.
- [x] Documentation and implementation plan reflect the kept optimizations and
      rejected experiments.

Moved to Phase 10 / CI hardening:

- Packaged sidecar startup timing and installed-app startup budget tracking.
  This should run against release artifacts and installer output, so it belongs
  with release validation rather than core runtime optimization.
- Recurring scheduled performance regression gates for the Phase 9 benchmark
  matrix. The scripts and baselines exist; wiring them into CI is release
  hardening work.
- Optional provider-live trend dashboards. Live provider timing is useful but
  network-dependent, so it should stay outside deterministic release gates.

Read: Phase 9 is closed. The project is ready to enter Phase 10 Release with
performance baselines, release-validation startup timing, packaging checks,
installer smokes, and release notes as the next focus.
