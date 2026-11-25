---
name: tenniscut
description: Screen fixed-camera tennis footage for continuous rallies meeting a combined racket-contact threshold, retain reviewable per-contact evidence, and export or revise local FFmpeg highlights, with optional Jianying draft output. Use for long-rally tennis cuts and timestamp-based corrections; not a general video editor or an automatic ball tracker.
---

# tenniscut

Produce a local highlight video and an auditable rally ledger. The agent reviews pixels; the bundled CLI handles media, evidence checks, edits, caching, and export. It does **not** recognize hits or detect new feeds automatically.

Use the user's counting convention. Default: each actual racket contact by either player counts once, including the opening racket feed. A new ball/feed starts a new rally. Bounces, hand tosses, missed swings, and neighboring courts do not count. Confirm a genuinely ambiguous counting preference once, not on every run.

## Fast source intake — act before preparation

A bare `tenniscut` starts a new task. First choose a source folder, then the exact video file(s), then unanswered editing settings. Historical paths are suggestions only; do not silently reuse old footage. An explicit continuation/correction resumes its project without reopening intake. Current exact paths/filenames or “all videos in this folder” already answer file selection.

Keep this stage lightweight. Use the following next action immediately after each answer:

| Current input | Next action |
| --- | --- |
| No source | Show one native question offering a previously used folder as an explicit choice plus another path/client picker. Read picker-specific instructions only if needed. |
| Directory supplied/selected | Run only `python3 scripts/select_source.py inspect DIR`, then immediately show the returned video filenames as a choice. No analysis or other preparation between listing and the question. |
| Exact file(s) selected | Run `python3 scripts/session.py inspect PROJECT --intake-only` with current explicit overrides, then immediately show all unanswered editing settings together. |
| Settings submitted or both supplied explicitly | Persist confirmed choices, then perform dependency checks, source probing/hashing and initialization. |

Before the video-choice card, use metadata only: filenames, sizes and modification dates; no ffprobe duration, full-file hash, old task inspection, dependency checks, installation, broad searches, or loading review/draft references. Before the settings card, `--intake-only` reads preferences without discovering media tools/packages. Do not delay either card for a progress-only reply or unrelated calls. Keep the first question in the same turn as its required lightweight read. A failed listing needs access/error handling, not a wider scan.

Aim to complete source selection within 60 seconds of assistant/host time; this is a UX target, not a guaranteed SLA. User response time and permission waits are separate. Record invocation/folder/files/settings/analysis/export milestones when available, preferably in an already needed call; do not add clock calls before a question. Missing timestamps remain unknown. A millisecond listing benchmark does not measure model/host round-trip latency. If intake is slow, measure those intervals rather than repeating setup checks.

At first intake say briefly: “不用上传原视频，选择本机文件夹或告诉我路径即可；抽帧和剪辑在本机执行，供助手分析的截图可能交由模型服务处理。” Verify actual local access; a remote runtime may need a mount or optional upload. A folder picker does not grant filesystem permissions, and cancellation authorizes no scan. See [source selection](references/source-selection.md) only for picker/fallback details.

## Editing settings and natural language

Default choices: minimum combined contacts **8** (6 / 8 / 10 / custom positive integer), also generate Jianying draft **no**. Every new task asks these two settings; no asking-frequency question is shown. Ask all unanswered settings in one native question-tool call; use a concise text fallback if unavailable. Respect the tool's option limits and built-in custom answer. A preselected value or silence is not an answer. No CapCut setting is offered.

Current explicit instructions override confirmed project choices, remembered preferences, then defaults. “8拍以上” means >=8; “超过8拍” means >=9. Preserve custom counts, resolution, draft requests and corrections stated in natural language; do not ask users to repeat them with a button. Pass startup overrides to `inspect --intake-only --threshold N --jianying yes/no`. Clarify genuinely ambiguous counting conventions, such as counting only one player's hits.

Every new task shows unanswered choices using the last saved values as suggestions, even if an old profile contains `ask_every_time: false`. Both explicit current values need no duplicate card. Persist the two submitted choices; the legacy `ask_every_time` field is fixed to true for compatibility. Current-task corrections/retries reuse the snapshot via `inspect --resume --intake-only`. A partial answer asks only the missing setting. See [startup options](references/setup-and-options.md) for persistence and post-answer dependency checks. Install missing tools only within actual authorization; verify requested Jianying dependencies before a long analysis and never silently drop that output.

## Environment and project

Run commands from this skill's directory, or use absolute paths to its script. Python 3.9+, Pillow 10.1+, FFmpeg with libx264, and ffprobe are required. HDR sources also need zscale and tonemap. No video-editor account or API key is required by the base scripts.

```bash
python3 scripts/tenniscut.py doctor
python3 scripts/tenniscut.py init /path/to/private-project /path/to/video1.mov /path/to/video2.mov
```

Use the returned source IDs. Keep project files and media out of the public skill repository. Scripts do not upload media; viewing images with a hosted agent uses that agent's image-processing service and is not fully offline analysis.

## Discover candidates economically

For a full source, start with low-density overview frames. The end value must not exceed the probed source duration.

```bash
python3 scripts/tenniscut.py extract /path/to/private-project --source SOURCE_ID --start 0 --end 1800 --fps 0.25 --purpose overview --sheet-frames 20
```

Open the generated sheets. Overview evidence finds candidates; it cannot establish hit counts or continuity. Do not pretend an overview or a successful extraction is a complete visual review.

Use **adaptive visual navigation** as the default analysis workflow: sparse overview → classify activity and state changes → request intermediate frames only where needed → dense evidence for plausible kept rallies. Follow the state/skip rules in [the review protocol](references/review-protocol.md#adaptive-visual-navigation). The agent chooses the next windows; the CLI does not automatically recognize idle periods or contacts. Audio pre-screening is not a prerequisite or the default candidate gate.

Separate extraction from viewing: preparing a cached frame set does not mean every frame needs to be presented. Open selected overview sheets first; use observed state transitions to choose follow-up windows instead of automatically expanding every active block to 1–2 fps. Unknown gaps remain unknown; duration, sparse poses and audio peaks do not establish eligibility or exclusion. Clearly separate short feeds can be explicitly excluded during discovery without a dense contact ledger.

Before retaining a candidate, inspect full displayed frames at 2 fps or higher across its complete selected interval. Review sheets are limited to six frames. Open individual larger images when a small ball, distant racket, or ball-in-hand matters. Use denser short windows and separate player crops around ambiguous events; crop coordinates refer to the autorotated source. Do not replace whole-court continuity review with player crops or weaken evidence gates to make the experiment faster.

```bash
python3 scripts/tenniscut.py extract /path/to/private-project --source SOURCE_ID --start 471 --end 500.5 --fps 2 --purpose review
python3 scripts/tenniscut.py extract /path/to/private-project --source SOURCE_ID --start 477 --end 481 --fps 10 --purpose review
```

For several candidate windows from one source, prefer one bounded `extract-batch` invocation. Its JSON input is a list such as `[{"start": 91, "end": 113}, {"start": 315, "end": 318, "fps": 10}]`. It reuses the same in-process source verification, checks file identity between windows and rehashes at the end; it still verifies cached image hashes. The default 600-frame limit covers the whole batch, not each window.

```bash
python3 scripts/tenniscut.py extract-batch /path/to/private-project --source SOURCE_ID --windows /path/to/windows.json
python3 scripts/tenniscut.py review-sheets /path/to/private-project --manifest /path/to/private-project/cache/frames/SET/frames.json --region X,Y,W,H --region X,Y,W,H
```

`review-sheets` reuses existing full-frame evidence and places the full court beside up to two player crops in six-frame sheets. Choose rectangles from an inspected cached frame; coordinates are in that cached image’s pixels. It does not decode the source again, add contact evidence or mark anything viewed. Open a larger original when the combined sheet is insufficient. Save reviewed frame IDs and decisions once; resume from that checkpoint instead of reopening clear, unchanged intervals.

The extraction manifest stores **actual decoded source PTS**, not `frame_index / fps`. Use its source times. Query only relevant ID/time/path fields with a short helper rather than loading the entire evidence registry into model context. The default frame budget prevents unintentionally dense full-source extraction; increase it only when needed.

## Reduce visual work without weakening kept-rally checks

Use discovery to reject clearly separate short feeds before requesting dense candidate evidence; an exclusion reason is sufficient, and does not require constructing a complete confirmed-contact ledger for the rejected interval. Do not turn a long active drill into full-block 1–2 fps review. Review candidate windows in chronological batches and save decisions/actually opened sheet IDs after each batch, rather than reopening clear windows when context changes.

The deliverable is threshold selection. Once N actual alternating contacts are confirmed inside one ball, the count can remain a documented lower bound; do not keep counting every extra stroke solely to obtain an exact total. Still inspect full-frame coverage across the complete retained interval, including its tail, for a reset and the real endpoint. If later discovery reveals a reset, split/review the affected ball and invalidate the merged count. A threshold-sized list of guessed contacts is never acceptable.

Choose player crops tightly from an inspected full frame so the distant racket/ball is readable. Add short dense windows only when ambiguity changes inclusion or continuity; an uncertain extra contact above an already confirmed threshold does not need frame-by-frame counting. If an interval cannot be resolved after targeted inspection, explicitly exclude it conservatively and explain why; do not count poses as hits. Report that this may miss qualifying rallies.

After the first representative review batch, use actual review time and remaining work to update the user if the task is trending long. Do not promise a minutes-long full edit based on extraction/render speed. This remains model-assisted screenshot review, not an automatic trained tennis detector.

Log actual source-frame presentations separately for overview, navigation and dense review, plus sheets opened and repeated views. Report the total, not only the reduction in dense frames. Record cache reuse, source familiarity and conservative exclusions when comparing runs; one familiar five-minute experiment is not an independent accuracy evaluation or a fixed speedup guarantee.

## Establish separate rallies before counting

Read [the review protocol](references/review-protocol.md) before annotating tennis footage. Establish one ball from start to finish, then count that ball's contacts. Explicitly inspect intervals between contacts for a new feed. A long-looking segment or a prior high count does not establish continuity.

Create a draft candidate:

```bash
python3 scripts/tenniscut.py add /path/to/private-project --id r001 --source SOURCE_ID --start 478.5 --end 500.5
```

Edit `rallies.json` only after inspecting the corresponding evidence. Follow [the record format](references/record-format.md). Record each contact's source time, player side, status, and evidence IDs. Store reviewed full-frame coverage and start/end evidence. Describe why continuity is confirmed. Use uncertain status or an explicit exclusion when evidence does not support inclusion. Never bulk-mark frames as viewed before opening them.

A claimed confirmed lower bound is valid only inside a confirmed single rally. Legacy records containing only start/end/total counts must be imported as drafts and reviewed; a previous count of 14 does not bypass the new-feed check.

## Resolve uncertain candidates in the conversation

The default deliverables are the highlight MP4 and, when requested, a Jianying draft. HTML review is paused: do not prepare or deliver a review page, request browser choices, or start a local review service unless the user explicitly asks to resume it.

Finish count, continuity and boundary checks yourself using the evidence protocol. When footage remains ambiguous, describe the relevant candidate and source timestamp briefly in the conversation; ask only a necessary question. Never invent contacts or treat a keep preference as proof of eligibility. Unresolved candidates still block a claimed complete export; a partial export requires the user's requested scope and must be labeled partial.

The paused HTML review experiment is excluded from this core install. Its source is preserved in the separate development archive; no review page or local server is part of the default workflow.

## Select and export

```bash
python3 scripts/tenniscut.py validate /path/to/private-project 
python3 scripts/tenniscut.py plan /path/to/private-project 
python3 scripts/tenniscut.py render /path/to/private-project --out /path/to/exports/highlights.mp4
```

The validator checks recorded evidence and annotations. It cannot tell whether an agent misread a racket contact or falsely confirmed a boundary. Resolve failed gates before export. A deliberately incomplete export requires `--allow-pending` and must be reported as partial.

By default, preserve the selected source’s displayed pixel dimensions (accounting for rotation) for both the MP4 and Jianying canvas. Omit `--resolution` or use `--resolution source`; do not carry a past task’s 2K request into a new task. An explicit current request such as 2K uses `--resolution 2560x1440`. If selected sources differ in dimensions, ask whether to export them separately at their own sizes or combine them on an explicitly chosen canvas; do not silently pick a size. This is not an additional startup question when the default applies.

Export keeps normal speed and source audio, uses chronological source order, letterboxes instead of stretching, and tone-maps recognized HLG/PQ to SDR. Sources without audio receive documented silence. Outputs are regular files: MP4, immutable export manifest and CSV time map. No HTML is generated by default; `render --viewer` explicitly opts into the legacy local viewer. Do not describe an MP4 as an editable draft.

Open fresh exported frames at edited boundaries; verify expected source content and cut placement. The CLI also validates final frame count, duration, dimensions, and complete decoding. Report these technical checks separately from tennis-recognition quality. Do not promise a measured accuracy rate without a human-labeled evaluation.

## Optional Jianying draft

When the saved choice requests a Jianying draft, additionally follow [Jianying output](references/jianying-output.md) after the selection plan is validated. Use the same selected independent rallies, source trims and output order. Never substitute a single flattened MP4 for the promised per-rally editable timeline. Use a new draft name. Report file-generation checks separately from actual target-app acceptance; a generated folder is not proof that it opens or appears in the app. If the optional output is blocked, keep the user's requested setting and explain the blocker alongside the MP4 result.

## Correct without restarting

Use the **manifest of the exact video the user watched**; subsequent revisions may shift timestamps.

```bash
python3 scripts/tenniscut.py locate /path/to/exports/highlights.manifest.json --time 00:25
python3 scripts/tenniscut.py revise /path/to/private-project --id r001 --start 478.5 --reason 'Previous interval included a short point before a new feed'
```

`revise` preserves history and invalidates the review. Reinspect only affected candidates, update contacts/evidence, and export to a new filename. For a merged candidate, split it into independent candidates or trim it to the valid rally. Explicitly exclude the short rally if retaining it in the review ledger. Every candidate has a stable ID and revision number; export manifests retain their original time mapping.

Render caches include source SHA-256, interval, output parameters, FFmpeg version, and pipeline version, and verify cached file hashes. Unchanged material is reused; a file merely named `002.mp4` is never sufficient evidence of a cache match.

Keep requested source files and prior deliverables intact. Deliver the actual output files and their exact locations; use a stable user-chosen export directory when available.

Keep source-derived screenshots, video posters and private task records outside the public skill package.
