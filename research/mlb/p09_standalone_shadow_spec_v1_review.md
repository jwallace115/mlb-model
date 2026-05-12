# P09 Standalone Shadow Spec V1 — Review Acceptance

**Date:** 2026-05-12
**Spec reviewed:** research/mlb/p09_standalone_shadow_spec_v1.md
**Spec commit:** 192add48

---

## A. Verdict

**ACCEPT SPEC AS IMPLEMENTATION BASELINE**

Clarifications:
- This accepts the spec as the planning baseline for a future standalone P09 shadow tracker.
- This does **not** authorize live betting.
- This does **not** authorize promotion.
- This does **not** by itself authorize implementation.
- Implementation requires a separate implementation prompt after this review artifact and the spec are durable on origin.

---

## B. Critical Issues

None found.

---

## C. Minor Corrections / Non-Blocking Notes

1. **Section 7 schema:** `park_run_factor` is an integer input from `config.STADIUMS`. `p09_score` is a float because avg hard-hit rate (~0.30–0.45) is multiplied by park_run_factor (~90–110), producing values in the ~27–50 range. The cutoff 31.7305 is a float. No spec correction required.

2. **Section 8 grading:** `selected_side` is UNDER when `signal_fired = true`. `selected_side` is implied null when `signal_fired = false`, consistent with the schema definition (`"UNDER" or null`). No spec correction required.

---

## D. PIT-Safety Status Statement

The spec is PIT-safe by design. The implementation is not yet proven PIT-safe.

**PIT status: PARTIAL / REQUIRES IMPLEMENTATION VERIFICATION**

Breakdown:
- **Historical formula:** likely PIT-safe, based on the existing `shift(1)` rolling construction pattern in `daily_signal_generator.py` lines 330–346.
- **Runtime construction:** not verified.
- **Starter-source identity:** not verified.
- **Research/live identity:** not verified.

The accurate framing for any future session is:

> "P09 has a PIT-safe specification and no obvious conceptual PIT violation, but standalone runtime PIT safety remains a required implementation hard stop."

Implementation must independently verify, in this order:

1. Starter identity is known pregame for each game.
2. Rolling hard-hit feature uses only prior starts.
3. `shift(1)` is preserved at runtime.
4. `rolling(5, min_periods=3)` is preserved at runtime.
5. No same-game Statcast is used.
6. Daily runtime feature output matches the research formula.
7. P09 scores match `p09_overlay.py` `compute_p09()` output on sample games.

Any failure on items 1–7 is an implementation hard stop per spec Section 13.

---

## E. Implementation-Risk Notes Carried Forward

1. **Starter identification:** The daily Statcast file (`pitcher_statcast_per_start.parquet`) includes all pitcher appearances ≥30 pitches, which may include long relievers. The research file was starters-only. The implementation filtering approach must match the research identity before any score comparison is trusted.

2. **Market total source:** Market total source remains undecided. `mlb_sim/pipeline/line_snapshot_store.py` may be a candidate source. Implementation must resolve this before grading can function.

3. **Standalone-vs-amplifier framing:** P09 was validated as a standalone predictor (ADVANCE 5/5, independent=YES). Current overlay code only amplifies V1 UNDER. Standalone shadow tracking tests P09 as a standalone UNDER selector, which is a stronger and separate operational test from the overlay role.

---

## F. Next Required Action

After this file is committed:
- Push commit `192add48` (spec) and this review acceptance commit together through `shared/git_push.sh`.
- After both are durable on origin, an implementation prompt may be drafted.
- The implementation prompt must preserve the PIT hard stops listed in Section D above.
- No code is authorized by this review artifact alone.
