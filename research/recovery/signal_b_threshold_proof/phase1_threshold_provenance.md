# Phase 1: Threshold Provenance Trace

**Date:** 2026-04-12

---

## Chronological Chain

### Event 1: Original Research (pre-2026-03-25)
- **File:** `research/f5_runline/run_f5_runline_research.py` line 176
- **Threshold:** `xfip_gap >= 1.0`
- **Data source:** `sim_inputs_historical_2022_2024.parquet` + `sim_inputs_2025.parquet`
- **xFIP type:** Season-final FanGraphs (STATIC per pitcher per season — confirmed)
- **Result:** +27.9% pooled ROI, +29.1% 2025 OOS
- **Assessment:** CONTAMINATED — end-of-season xFIP lookahead inflates hit rate

### Event 2: Deployment (2026-03-25, commit 32c687d9)
- **File:** `mlb_sim/pipeline/f5_runline_signal_generator.py` line 28
- **Threshold:** `XFIP_GAP_THRESHOLD = 1.0`
- **Docstring:** "xFIP mismatch >= 1.0, home side"
- **Source:** Directly adopted the research threshold without adjustment

### Event 3: Operational Triage (pre-2026-04-11)
- **File:** `research/recovery/mlb_operational_triage.md` section B5
- **Quote:** "The threshold (xFIP gap >= 1.0) was not validated with PIT-clean data
  but is a simple gap rule, not a fitted model."
- **Assessment:** Flagged the gap but kept 1.0 as "reasonable heuristic"

### Event 4: V1 Dependency Revalidation (pre-2026-04-11)
- **File:** `research/recovery/v1_dependency_revalidation/object2_f5_runline.md`
- **Data source:** PIT-safe features (`baseball_features_pit_v1.parquet`) — CONFIRMED
  xFIP varies game-to-game with expanding means, properly lagged
- **Key finding:** PIT FIP gap analysis at multiple thresholds:
  - gap >= 1.0: under rate 50.3% (2024), 53.1% (2025) — BORDERLINE
  - gap >= 1.5: under rate 59.4% (2024), 60.0% (2025) — STRONG, STABLE
- **Verdict at the time:** "SURVIVES" (noted 1.0 is heuristic, ROI may be inflated)

### Event 5: Reset Audit / State Map (2026-04-11)
- **Files:**
  - `research/recovery/site_reset/02_state_map.md` line 15
  - `research/recovery/site_reset/03_tracker_reset_plan.md` line 20
- **Directive:** Change threshold to 1.5
- **Reasoning:** 1.0 was borderline in PIT-clean data; 1.5 showed consistent 59-60%
  under rate across both seasons

### Event 6: Totals Reset Audit / Phase 3 Classifications (2026-04-11)
- **File:** `research/recovery/mlb_totals_reset_audit/PHASE3_CLASSIFICATIONS.md` (D3)
- **Text:** "Threshold: xFIP gap >= 1.0. Pooled ROI +27.9% (N=335, 2024-2025)."
- **Note:** This document records the ORIGINAL threshold. The 1.5 directive came
  from the state map, not the classification itself.

### Event 7: Signal B Reactivation Audit (2026-04-12)
- **File:** `research/recovery/signal_b_reactivation/phase0_locked_spec.md`
- **Finding:** Code was STILL at 1.0 — the reset audit directive was never implemented
- **Action:** Changed code to 1.5 (uncommitted working tree edit)
- **Status:** Changed to SHADOW pending 30+ signals at new threshold

### Event 8: Current State (2026-04-12)
- **Committed code (HEAD):** `XFIP_GAP_THRESHOLD = 1.0`
- **Working tree (uncommitted):** `XFIP_GAP_THRESHOLD = 1.5`
- **Live signal log:** 7 entries, 6 at gap < 1.5 (would not fire at new threshold)
- **Only 1 signal (2026-04-05, gap=1.503)** qualifies under 1.5 threshold

---

## Key Insight

The 1.0 threshold was NEVER supported by PIT-clean evidence. It was:
1. Chosen as a round-number heuristic in original research
2. Validated only against season-final xFIP (contaminated)
3. Showed only ~51% under rate in PIT-clean revalidation (coin flip)

The 1.5 threshold IS supported by PIT-clean evidence:
1. 59.4% under rate in 2024 PIT data
2. 60.0% under rate in 2025 PIT data
3. Stable across both OOS seasons
4. Derived from the V1 dependency revalidation (the only PIT-clean test of this signal)
