# Project and record format (version 1)

A project is a private local folder, separate from this public skill:

```text
settings.json      Confirmed project snapshot: minimum contacts, Jianying output and asking preference
project.json       Source paths, SHA-256 and probe metadata; frame evidence registry
rallies.json       Editable, source-time review records and correction history
plan.json          Last selection plan; regenerate after annotation changes
cache/frames/     JPEGs, source PTS manifests, sheets and local decoder logs
cache/render/     Hashed encoded segments and cache records
```

Python and FFmpeg arguments are passed as arrays, not shell strings. Paths may contain spaces and apostrophes. Absolute source paths occur in private project records only. Local decoder logs may contain original camera metadata; do not publish them.

## Source timing

Source seconds are relative to the container's start time, matching FFmpeg input seeking. Extraction preserves input PTS, records actual sampled frames, and subtracts the container origin. VFR evidence therefore need not fall at exact multiples of the requested sampling interval. End times are exclusive. FFmpeg autorotates images; crop coordinates use the displayed orientation.

For export, durations are rounded **down** to whole output frames. The manifest preserves the requested end and the rendered end. Export refuses quantization that would remove a confirmed contact. Allow enough reviewed padding after the final contact.

## Rally object

`add` creates a draft. The following illustrates a two-contact annotation; it would not meet a ten-contact threshold. Replace evidence IDs with real IDs from an extraction manifest; this example is not executable ground truth.

```json
{
  "id": "r001",
  "revision": 1,
  "source_id": "SOURCE_ID",
  "start": 10.0,
  "end": 12.0,
  "status": "reviewed",
  "contacts": [
    {"time": 10.15, "side": "near", "status": "confirmed", "evidence_ids": ["SET_ID:1"]},
    {"time": 11.1, "side": "far", "status": "confirmed", "evidence_ids": ["SET_ID:3"]}
  ],
  "resets": [],
  "uncertainties": [],
  "continuity": {
    "confirmed": true,
    "note": "Reviewed the complete interval and checked both players for another feed.",
    "reviewed_evidence_ids": ["SET_ID:1", "SET_ID:2", "SET_ID:3", "SET_ID:4", "SET_ID:5"],
    "start_evidence_ids": ["SET_ID:1"],
    "end_evidence_ids": ["SET_ID:5"]
  },
  "history": []
}
```

Statuses: `draft`, `reviewed`, `excluded`. Exclusion requires `exclusion_reason`. Confirmed contacts require side `near` or `far`; uncertain contacts may use `unknown`. Contacts must be chronological, within the interval, and confirmed adjacent events must alternate sides. An uncertain event can occupy the missing position in an incomplete contact sequence.

`minimum_contacts` for agent evidence review is calculated from confirmed event records, never accepted as a manually supplied scalar. The explicitly user-driven human review path below is recorded separately. Uncertain additional contacts do not count. Any unresolved rally-level uncertainty blocks export eligibility.

## Evidence

Each evidence record is registered by `extract`, with ID, relative image path, SHA-256, source ID, actual source time, image dimensions, purpose, sampling fps and optional crop. Only `review` evidence at 2 fps or above is accepted for contact/boundary gates. Overview frames remain useful for discovery.

Continuity needs full-frame evidence near both ends (within 0.75 seconds) and no sampled coverage gap above 0.76 seconds. Contact evidence must be within 0.6 seconds of its recorded event. These are mechanical coverage tolerances, **not proof of an actual contact**, and can require denser extraction for sparse VFR sources. Cropped player images supplement, rather than replace, full-frame coverage.

When using a code helper to collect IDs from a manifest, do so only after reviewing those images. Filling the arrays is an attestation by the reviewing agent; the script cannot verify that viewing actually happened.

## Corrections and exports

Use `revise` instead of silently changing boundaries of a reviewed record. It increments the revision, saves a previous snapshot and reason, and returns the candidate to draft. It removes out-of-range contacts and invalidates continuity review. Reinspect and finish the record before re-exporting.

An export writes:

- `.mp4`: regular file, normal speed, source audio or silence for a silent source.
- `.manifest.json`: export-time mapping and decision snapshot, source hashes, annotation hashes, revisions, parameters and technical checks.
- `.csv`: per-rally source/output mapping.
- `.html`: local video viewer with clickable rally rows, only with explicit `render --viewer`.

`locate` reads this export snapshot, not mutable project records. Use the exact old manifest when correcting an old video's timestamp. Never assume timestamps remain stable after a prior clip was trimmed.

The exported manifest establishes candidate selection coverage only. It does not establish that every qualifying rally in an entire source was discovered. It also does not independently prove visual counting accuracy.
