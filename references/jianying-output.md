# Optional Jianying draft output

The adapter uses the third-party [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft) API. It creates a **new** draft from the same evidence-gated selection plan; it does not load/decrypt an existing draft, edit a live project, or automate app export. It does not provide CapCut output.

This is an experimental integration. File-level checks and adapter contract tests are different from a real library/app acceptance test. Opening, playing and editing the generated draft in the target Jianying version has not completed end-to-end acceptance. Do not claim app compatibility or real-library end-to-end validation from these tests.

## Discover before long analysis

Only after the user has answered intake and requested a draft, prepare optional dependencies and run:

```bash
python3 scripts/jianying.py --discover --check-write
```

Discovery first revalidates the saved root, then inspects the current OS's standard Jianying location. macOS includes `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft`; Windows uses `%LOCALAPPDATA%/JianyingPro/User Data/Projects/com.lveditor.draft`. These are candidates, not universally correct paths. Search is bounded to 128 immediate entries per root and does not scan the whole home. It checks the root index or existing draft-file pairs; it never modifies those files. `--check-write` creates and removes only a fresh temporary probe. Without it, discovery is read-only and reports writability as unknown.

Inspect `attempts`, `status` and `warnings`. Permission denied, missing, unverified structure and multiple matches are different outcomes. A scan limit or corrupt index is not evidence that a new app version hides its drafts. Do not silently switch away from a failing explicit user root. If no root is selected, inspect Jianying's draft-storage setting through available app UI, or a known app configuration file, within actual host access; then inspect the returned directory. Avoid broad configuration/drive searches, CapCut paths and changing app storage settings. If UI/paths are inaccessible, report that exact limitation and ask for the configured location. Multiple verified roots need a user selection. This preparation follows the two-question intake and does not delay video selection.

For a configured custom root:

```bash
python3 scripts/jianying.py --discover --draft-root /path/to/configured-root --check-write
python3 scripts/jianying.py --remember-root --draft-root /path/to/configured-root
```

Remember only a verified, writable chosen root. It is saved separately from intake choices in `jianying.json` beside preferences; `TENNISCUT_JIANYING_PROFILE` can supply a writable private file. Saving failure must be reported, never described as successful memory. Revalidation happens on each reuse. No private directory profiles belong in a release.

## Generate and accept in the app

After plan validation, omit `--draft-root` to use the selected verified root:

```bash
python3 scripts/jianying.py /path/to/private-project --name tennis-8plus-unique
```

Or pass the verified custom root explicitly. Automatic selection fails clearly rather than choosing an export directory itself. Only after discovery/configuration checks actually fail, an explicitly explained export-only fallback can use `--draft-root /path/to/draft-output`. That produces files but does not establish that the application registered or accepts them. An empty root is not automatically remembered as verified.

The saved project threshold is used unless explicitly overridden. The canvas defaults to the selected source’s displayed resolution, matching the default MP4 export. Use `--resolution source` or omit it; pass `--resolution 2560x1440` only for an explicit 2K request. Mixed source dimensions need separate exports or a user-chosen combined canvas, using the same choice for the MP4 and draft. For each selected rally, the draft references the original video and writes independent source/target time ranges on one video track. Embedded audio uses normal volume and speed. Original sources must stay available at their recorded paths.

Create only a uniquely named new draft. Never overwrite existing drafts, transplant identifiers from existing projects, or edit `root_meta_info.json` to force registration while the editor may be using it. Merely copying a directory is not proof that it appears on the home screen.

The adapter checks independent segments, source trims, contiguous target placement and duration. Its manifest and result distinguish `files_generated` from `placed_in_verified_root`. Both retain `app_open_verified: false`. Directory verification means filesystem evidence only, not library/app compatibility.

Use the host's available native app tools to open Jianying and find the new draft, refreshing the home view when needed without closing unsaved work. Then open the draft and check source media availability, separate clips and trims, canvas, source sound, normal speed and playback. Only observed success supports an app-acceptance claim in the delivery report. If no app tools are available, request necessary user assistance rather than inventing a version restriction. Report separately: files generated; placed in a verified root; appeared in the app; opened and played. Never mark app acceptance from JSON validity, a folder listing or a user's keep preference. An opening failure needs its actual symptom/version and preserved files, not repeated blind index edits.

Current upstream guidance distinguishes generating new drafts, reading newer encrypted templates, and automating app export; support differs by version/platform. See the [upstream compatibility notes](https://github.com/GuanYixuan/pyJianYingDraft#跨平台兼容性). No automatic export is promised here. HDR appearance may differ from the FFmpeg SDR output and must be checked in the app.

If generation or app acceptance fails, retain the MP4 and reviewed ledger; explain the draft blocker and preserve `generate_jianying_draft: true` rather than silently changing the user's choice. No CapCut fallback is requested.
