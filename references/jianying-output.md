# Optional Jianying draft output

The adapter uses the third-party [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft) API. It creates a **new** draft from the same evidence-gated selection plan; it does not load/decrypt an existing draft, edit a live project, or automate app export. It does not provide CapCut output.

This is an experimental integration. File-level checks and adapter contract tests are different from a real library/app acceptance test. Opening, playing and editing the generated draft in the target Jianying version has not completed end-to-end acceptance. Do not claim app compatibility or real-library end-to-end validation from these tests.

After installing optional dependencies in the active Python environment:

```bash
python3 scripts/jianying.py /path/to/private-project --draft-root /path/to/draft-output --name tennis-8plus
```

The saved project threshold is used unless explicitly overridden. The canvas defaults to the selected source’s displayed resolution, matching the default MP4 export. Use `--resolution source` or omit it; pass `--resolution 2560x1440` only for an explicit 2K request. Mixed source dimensions need separate exports or a user-chosen combined canvas, using the same choice for the MP4 and draft. For each selected rally, the draft references the original video and writes independent source/target time ranges on one video track. Embedded audio uses normal volume and speed. Original sources must stay available at their recorded paths.

Use a user-identified Jianying draft directory if it is discoverable and writable under existing authorization; create only a new uniquely named draft. Do not guess a CapCut folder or overwrite existing drafts. If the actual app directory cannot be established, generate in a separate export folder and explain that the folder has not yet been registered with the app. A disk folder being generated does not prove it appears on the home screen.

The adapter checks segment count, source trims, contiguous target placement and total duration, and saves `tenniscut-manifest.json` beside `draft_content.json`. It records `app_open_verified: false`. To mark acceptance in a delivery report, actually open the generated draft in the user's target Jianying version, check media resolution, track clips, source sound, trims and normal playback. Do not infer acceptance from JSON validity alone.

Current upstream guidance distinguishes generating new drafts, reading newer encrypted templates, and automating app export; support differs by version/platform. See the [upstream compatibility notes](https://github.com/GuanYixuan/pyJianYingDraft#跨平台兼容性). No automatic export is promised here. HDR appearance may differ from the FFmpeg SDR output and must be checked in the app.

If generation or app acceptance fails, retain the MP4 and reviewed ledger; explain the draft blocker and preserve `generate_jianying_draft: true` rather than silently changing the user's choice. No CapCut fallback is requested.
