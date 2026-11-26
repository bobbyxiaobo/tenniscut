# 0.7.1-beta.1

- Added bounded Jianying draft-root discovery: explicit user root, revalidated saved location, then OS-specific Jianying candidates. The macOS candidate was located successfully in a read-only local check; no private draft content is distributed.
- Missing, denied, ambiguous and unverified directory outcomes are reported separately. A temporary write probe is opt-in; shared indexes and existing drafts are never edited by discovery.
- Added explicit verified-root memory, separate from intake preferences. Automatic generation uses one verified writable root or stops with actionable discovery instructions; export-only fallback requires an explicit destination.
- Draft receipts distinguish generated files from placement in a verified root. Neither claims app registration or successful playback. The workflow now checks the configured app location before asking the user, and calls for opening/playback acceptance with available host tools.
- Added regression tests for discovery, write denial, stale saved paths, ambiguity, explicit-path failure, preservation of existing files and automatic-generation receipts.

This update does not add automatic GUI control or prove compatibility with every Jianying version. WorkBuddy end-to-end operation and target-app opening/playback remain unverified. It does not change rally-recognition logic or performance claims. MIT License, copyright 2026 YE BO.

Previous release notes follow.

# 0.7.0-beta.1

This Beta supports fixed-camera tennis footage through a local agent workflow. It exports MP4 highlights, a per-contact evidence ledger, export manifests and CSV time maps, with optional experimental Jianying draft output. Original resolution, normal speed and source sound remain the defaults.

## Changes

- New tasks ask only minimum contacts and whether to generate a Jianying draft. The old asking-frequency preference cannot suppress these questions. Explicit natural-language answers are not asked again.
- Folder intake reads metadata only. `session.py inspect --intake-only` defers dependency discovery until after choices are displayed.
- The skill's launcher prompt now matches the two-question flow.
- Jianying CLI errors now report the original problem as JSON rather than failing again because `sys` was undefined. Regression coverage includes an unwritable draft folder.
- MIT License, copyright 2026 YE BO.
- Added WorkBuddy local-import guidance and an explicit unverified status. GitHub publication is separate from WorkBuddy marketplace submission; model behavior, permissions and interaction controls vary by host.
- The default install archive excludes the paused HTML review experiment. The separate development archive retains its source and tests.

## Validation and limits

The development Python suite ran 93 tests: 92 passed and one optional localhost HTTP test was skipped. Real FFmpeg integration tests were enabled, including timestamps, frame counts, audio alignment, export and incremental cache reuse. These tests do not measure tennis-recognition accuracy.

A new project generated 75 overview frames across a five-minute fixed-camera window and 64 dense review frames around one positive candidate. Neither source-frame nor encoded-segment cache was imported. It exported a 27-second 1080p original-audio clip with zero render cache hits; full decode and two output boundary images were checked. Total wall time was 266.551 seconds. The source was familiar, the tool environment was already installed and the operating-system disk cache was not cleared. Selection was not exhaustive across the five-minute window. This is a pipeline smoke test, not a full five-minute selection benchmark, clean-machine test, independent accuracy study, or proof that a new 27-minute video finishes in 33 minutes.

A second source was inspected without imported caches, but overview images showed repeated camera tracking/panning. It was not treated as a fixed-camera speed benchmark and no count/export claim was made.

Known remaining validation: independent human-labeled footage for precision, recall and wrong rally merges; a full-length fixed-camera run without prior analysis caches; clean-machine installation; real folder-picker acceptance across clients/platforms; and opening/playing/editing generated drafts in the target Jianying version. Current empirical environment is macOS. Screenshot analysis can still be wrong even when evidence-format checks pass, and conservative exclusions can miss qualifying rallies.

Original footage, screenshots, analysis projects, output clips and machine-specific logs are private and excluded from both release archives. No GitHub publication has been performed by preparing this release.
