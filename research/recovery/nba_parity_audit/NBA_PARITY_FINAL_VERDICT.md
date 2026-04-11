# NBA Parity Audit -- Final Verdict

**Date:** 2026-04-11
**Scope:** All live NBA objects vs training/revalidation artifacts

---

## Executive Summary

The NBA core model pipeline is structurally clean with one significant feature parity gap and one stale signal that should be killed.

**Critical findings:**

1. **LOCATION-SPLIT FEATURE GAP (MEDIUM risk):** The Ridge model was trained on location-specific rolling features (home ORtg computed from home games only, away ORtg from away games only) but the live pipeline feeds it overall rolling features (all games regardless of location). This affects 6 of 15 features and the 6 largest model coefficients. Median feature-level difference: 1.8 pts ORtg, translating to ~3-5 pts of prediction noise per game.

2. **ELITE_DEF2_at_ELITE_DEF STILL ACTIVE (HIGH risk):** The archetype revalidation issued a KILL verdict (OOS: 43% hit rate, -18% ROI) but the signal remains active in production code, generating UNDER signals that may be acted upon.

3. **INJURY TRAIN/LIVE ASYMMETRY (MEDIUM risk):** The model was trained with injury_adj=0.0 for all rows, but the live pipeline applies injury adjustments (up to -4.5 pts ORtg). The model has never seen injury-adjusted feature values.

**No RED (broken) issues found.** No equivalent to the MLB FanGraphs lookahead bug.

---

## Recommended Actions (Priority Order)

1. **IMMEDIATE:** Disable ELITE_DEF2_at_ELITE_DEF signal in run_nba.py (comment out or add early return)
2. **SHORT-TERM:** Add location-specific rolling to _build_current_team_states in run_nba.py
3. **SHORT-TERM:** Document injury adjustment as known train/live asymmetry; consider retraining with injury features
4. **HOUSEKEEPING:** Mark nba/models/totals_base_model.pkl and variance_model.pkl as deprecated
5. **MONITORING:** Continue tracking ROAD_WARRIOR live performance (only validated archetype)

---

## Verdict Summary

| Category | Count |
|----------|-------|
| PROVEN LIVE-IDENTICAL | 5 |
| CLEAN BUT NOT LIVE-IDENTICAL | 3 |
| CAVEATED | 3 |
| UNTRUSTED | 2 |
| UNVERIFIABLE | 0 |

Total objects audited: 12 (after merging sub-objects into logical groups)
