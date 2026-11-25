# Visual review protocol

This is an agent-assisted review workflow, not a trained automatic tennis counter. Dense image sampling and formal evidence fields can still accompany a wrong visual interpretation. The fields support audit and correction; they do not certify truth.

## Identify boundaries

Start from a candidate with a little context before its first contact and after the point ends. Check both players and the full court, including the intervals between obvious strokes.

Look for ball-in-hand, release of a new ball, pickup, a failed return, ball in net, a player leaving a ready posture, and a ball path that cannot be the previous return. A short interval between feeds does not join them into one rally. A long pause during a high lob does not necessarily split a rally. Do not classify continuity using a universal maximum inter-hit gap.

The opening racket feed counts as the first contact under the default rule. `resets` records a **subsequent** new feed within the candidate, not its opening feed. A candidate with a subsequent feed must be split.

## Record contacts

For each event, correlate racket motion with incoming/outgoing ball evidence across adjacent frames. A preparation pose or follow-through alone is not proof of a racket-ball contact. Sound can help locate an event but a peak can come from a bounce or neighboring court.

Record approximate source seconds and near/far side for confirmed contacts. Do not invent decimal precision: a time is a locator, not a frame-perfect physical measurement. If uncertain, keep an uncertain event and an explanation. Count only confirmed contacts. Where an uncertain event makes a decision or continuity unresolved, also add it to the rally's `uncertainties`; that blocks inclusion until resolved or explicitly excluded.

Count contacts and check continuity together in one chronological pass through each full candidate. After counting, revisit suspected feeds, ambiguous contacts and boundary evidence; do not automatically reopen every clear frame for another complete pass. Inspect all proposed kept rallies, not just ones near the threshold. Legacy high counts are not exemptions.

## Threshold-first lower bounds

After confirming the requested minimum inside one continuous ball, a documented lower-bound count is sufficient. The remaining full interval still requires continuity and boundary inspection, but exact counting of every additional stroke is optional. Do not extract dense evidence merely to distinguish, for example, 12 from 13 when either satisfies a 6-contact threshold. This does not permit unconfirmed early contacts or skipping a later new-feed check.

Clearly short, separate points can be explicitly excluded during discovery without dense reconstruction. Use more evidence when the decision itself is ambiguous. Make exclusions auditable and disclose potential missed qualifying rallies rather than implying exhaustive discovery.

## Adaptive visual navigation

Prefer state-guided requests over uniform dense review. This is an agent decision process using the existing `extract` / `extract-batch` tools, not a new automatic recognizer.

1. **Sparse discovery:** start with roughly one frame every four seconds. An eight-second navigation pass can reduce an initial batch where appropriate, but it cannot certify that no point occurred in a gap. Backfill active or uncertain gaps; use shorter intervals for fast play. These are starting rates, not universal tennis timing rules.
2. **Classify observed state:** note idle/pickup, serve preparation, possible live rally, clear point end/reset, or unknown. Record source times, actually viewed IDs and the next windows to inspect in a project checkpoint. Preparation and recovery poses alone do not prove racket contact.
3. **Skip idle carefully:** after observing pickup/walking, inspect a later frame, for example four to eight seconds ahead. If preparation or play appears, backfill toward the last observed idle state to find the change. Do not infer that the preceding seconds were idle from one pickup frame, and do not label an unseen gap continuously idle just because its endpoints look similar. If uncertainty can hide a qualifying rally, inspect it or document an explicit conservative omission.
4. **Find independent balls before counting:** use only the needed intermediate overview frames (often 0.5–1 fps near a transition) to locate serves, fresh feeds, net faults and pickups. Clearly separate short points need no complete dense contact ledger. A long active drill is not one rally; repeated ready postures can hide multiple new serves. If navigation remains ambiguous, escalate the affected interval rather than excluding it solely because it looks short.
5. **Dense review for inclusion:** inspect full-frame evidence at least 2 fps throughout every proposed retained interval. Review sheets contain at most six frames; retain start/end and per-contact evidence as usual. The lower bound may stop at the requested threshold, but tail continuity and the actual endpoint still require review. Navigation does not satisfy these gates.
6. **Resolve only decision-changing doubts:** around a questionable contact or reset, inspect a short 8–15 fps window with full frames and readable player crops. Do not add dense windows merely to count optional extra strokes above an established threshold. If the ball remains occluded or too small after targeted inspection, record uncertainty or explicitly exclude with a reason and disclose possible missed qualifying rallies.

Frame generation and image presentation are different costs. Reuse existing cached originals for navigation/crops; show only requested frames, then checkpoint decisions so clear intervals are not repeatedly reopened. No frame becomes "viewed" merely because a helper collected its ID.

Actual source PTS are written into `frames.json`. Do not infer source time from an image filename. Source time, current project time, and an old export's time are different coordinates.

## Keep review effort bounded

- Start with low-density discovery. A long active training block may contain many short points; split candidate boundaries before requesting dense evidence for the whole block. If needed, use intermediate-density overview frames as navigation only. Duration and sound alone never establish eligibility.
- Batch candidate extraction with `extract-batch`; use short dense windows only where the actual contact or reset is unclear. Raising the threshold does not require regenerating already reviewed evidence or recounting unchanged rallies.
- Use `review-sheets` to show full-court context alongside both player regions from existing frames. These layouts supplement the same registered originals; no additional source decode or automatic viewing attestation occurs.
- Keep a project checkpoint of actual opened sheets/IDs, resolved candidates and remaining questions. Reuse clear decisions while source identity and annotations remain unchanged.
- Separate setup time, extraction time, visual review effort and export time when reporting performance. A batch microbenchmark is not a measured end-to-end speedup or an accuracy score.
- Count actual source-frame presentations across overview, navigation and dense review, including repeated views; count sheets separately. Crops beside a source frame are supplemental views, not new independent source timestamps. Record unique evidence IDs separately rather than substituting them for the actual viewing workload.

The initial adaptive experiment used familiar, cached five-minute footage and conservative exclusions. It does not establish cold-start performance, independent recall or a guaranteed speedup. Do not tune on an old positive then present agreement with that same record as independent accuracy proof.

## Review modes

A conservative selection can omit uncertain candidates. Mark them explicitly excluded with a reason so the report explains the omission. An unfinished draft is different: default export stops until it is reviewed or explicitly excluded. `--allow-pending` produces an explicitly partial export.

The CLI gates require reviewed evidence covering the interval, nearby boundary evidence, and nearby evidence for each confirmed contact. They cannot establish that those frames were actually viewed or that an annotation is truthful.

## Evaluation before claiming reliability

Use human-labeled clips not already used to tune the workflow. Include feeds in quick succession, net faults, high lobs, missed swings, pickups, neighboring court activity, and counts around the chosen threshold. Measure:

- Selection precision: qualifying kept rallies / all kept rallies.
- Selection recall: qualifying kept rallies / all qualifying rallies in the evaluation footage.
- Boundary errors: wrong merges/splits, separately from contact count errors.
- Review effort: images actually opened, review time, and task usage when available.

A software regression that rejects an annotated `resets` entry does not prove automatic detection of that feed. The included synthetic tests deliberately distinguish these claims. No accuracy percentage is established in version 0.1.0.
