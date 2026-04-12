# ADJ Family — PIT-Safety + Identity Audit

**Date:** 2026-04-12
**Scope:** All 5 ADJ shadow signals (ADJ_CONTACT, ADJ_HH, adj_k_rate_last3, ADJ_BB_RATE, ADJ_RUN_SUPP)

---

## Bottom Line

The ADJ family is **PIT-SAFE** (no lookahead contamination) but suffers from an
**identity mismatch**: the live shadow code tests a STANDALONE version (combined > 0)
while the original research validated a V1-INTERACTION version (requiring p_under > 0.57).
These are different objects with different expected performance. The standalone version
was already tested separately and classified as DIMINISHED for all five signals.

Additionally, the feature source is **FROZEN at end-of-2025** and not updating with
2026 starts, and the `correct` field in the tracker is never populated. The
`v1_direction_context` is always "NONE", making V1-interaction analysis impossible
from the tracker.

---

## PIT-Safety Verdict: PASS

| Check | Result |
|-------|--------|
| Rolling features use shift(1) | YES — `shift(1).rolling(w, min_periods=minp).mean()` |
| Team expectations use lagged rolling | YES — `shift(1).rolling(20, min_periods=10).mean()` |
| Per-start data from boxscores | YES — individual game JSON extracts |
| No season-level FG aggregates in features | YES — feature_table.parquet imported but unused |
| No future data leakage | YES — all joins on game_pk with pre-game data only |

---

## Identity Audit: MISMATCH CONFIRMED

| Dimension | Research (validated) | Live Shadow (running) |
|-----------|--------------------|-----------------------|
| Gate | V1 p_under > 0.57 + metric threshold | combined > 0 only |
| Sample per year | ~50-130 | ~400-1000 |
| Expected ROI | +14% to +33% (interaction lift) | -3.6% to -0.6% (standalone) |
| Feature freshness | Per-game rolling | Frozen at 2025-09-28 |
| V1 context | Required for firing | Logged as "NONE" |

---

## 2026 Shadow Performance (standalone, through 2026-04-11)

| Signal | N_fav | N_resolved | Hit% | Standalone Backtest Hit% | Delta |
|--------|-------|------------|------|--------------------------|-------|
| ADJ_CONTACT | 92 | 63 | 55.6% | 51.2% | +4.4pp |
| ADJ_HH | 47 | 33 | 63.6% | 51.1% | +12.5pp |
| adj_k_rate_last3 | 38 | 28 | 60.7% | 52.1% | +8.6pp |
| ADJ_BB_RATE | 26 | 16 | 50.0% | 50.6% | -0.6pp |
| ADJ_RUN_SUPP | 55 | 32 | 59.4% | 51.5% | +7.9pp |

Note: 2026 N values are non-push resolved counts. Early-season samples are small;
ADJ_HH 63.6% has 95% CI approximately 46%-79% at N=33.

---

## Tracker Issues Found

1. **`correct` field**: Never populated (None for all 820 records). Must compute manually.
2. **`v1_direction_context`**: Always "NONE". V1 projections not being passed through.
3. **Feature staleness**: Parquet ends 2025-09-28. Using frozen end-of-season values.
   - 368/729 pitchers have 2025 data
   - 142/729 have only 2024 data
   - 219/729 have only pre-2024 data (retired/minors)

---

## Recommendations

### Immediate (no code changes needed)
1. **Continue shadow monitoring** all 5 ADJ signals — early 2026 rates are above standalone backtest
2. **Review ADJ_HH at N=50** (est. late April) as previously planned
3. **Do not activate any ADJ signal** in overlay — identity mismatch means research ROI figures do not apply

### If ADJ_HH sustains 60%+ at N=50
1. Build a 2026-refreshed feature pipeline (re-run build_v2.py with 2026 boxscores)
2. Consider re-implementing V1-interaction gate in shadow to test Object A properly
3. Populate `correct` field and pass V1 projections through to tracker

### If ADJ_HH regresses below 55% at N=50
1. Classify all ADJ signals as KILL
2. The frozen feature source and identity mismatch make further monitoring unproductive

---

## File Inventory

| File | Purpose |
|------|---------|
| phase1_research_definition_lock.md | Original research vs standalone rebuild comparison |
| phase2_live_code_lock.md | Live shadow code analysis |
| phase3_pit_safety_lineage.md | Feature construction audit |
| phase4_identity_check.md | Three-object identity comparison |
| phase5_tracker_interpretability.md | Shadow tracker issues and 2026 results |
| phase6_manual_examples.md | Game-level verification examples |
| adj_family_audit_table.csv | Machine-readable signal table |
