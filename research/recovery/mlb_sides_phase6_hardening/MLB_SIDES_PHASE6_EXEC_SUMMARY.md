# MLB SIDES PHASE 6 -- EXEC SUMMARY
## Forensic Hardening of MIXED Survivors

**Date**: 2026-04-12

---

## Objects Under Test
1. **bp_adv_dog**: MIXED + dog bullpen ERA better than favorite's
2. **night_dog**: MIXED + night game (local start >= 5pm)

---

## Phase 1: Bullpen PIT-Safety Audit
- Source: pitcher_game_logs.parquet, starter_flag==0
- Rolling: shift(1).expanding().sum(), min 10 IP
- 5 worked examples: ALL MATCH = True
- Opener contamination: 238 appearances (0.37%)
- **PIT VERDICT: PIT-SAFE AND LIVE-FEASIBLE**

---

## Results Summary

| Object | Disc N | Disc Resid | Disc ROI | Val N | Val Resid | Val ROI | OOS N | OOS Resid | OOS ROI | Verdict |
|--------|--------|-----------|----------|-------|----------|---------|-------|----------|---------|---------|
| bp_adv_dog | 241 | +0.0624 | +8.68% | 147 | +0.0519 | +6.30% | 179 | +0.0416 | +3.73% | GO -- SHADOW |
| night_dog | 381 | +0.0349 | +3.13% | 245 | +0.0337 | +2.64% | 268 | +0.0533 | +6.50% | GO -- SHADOW |

---

## Key Findings

### Survivors (2)
- **bp_adv_dog**: OOS resid +0.0416, OOS ROI +3.73%
- **night_dog**: OOS resid +0.0533, OOS ROI +6.50%

---

## Files
- `phase0_exact_object_lock.md` -- object definitions
- `phase1_bullpen_pit_audit.md` -- PIT safety audit
- `phase2_historical_rebuild.md` -- match rebuild by split
- `phase3_fragility_audit.md` -- concentration tests
- `phase4_microband_stability.md` -- price band stability
- `phase5_distinctness.md` -- overlap/nesting
- `phase6_proxy_risk.md` -- proxy risk audit
- `phase7_live_feasibility.md` -- live computation check
- `phase89_shadow_specs.md` -- shadow specifications
- `phase10_go_nogo.md` -- final verdicts
- `MLB_SIDES_PHASE6_FINAL_TABLE.csv` -- results table
- `MLB_SIDES_PHASE6_EXEC_SUMMARY.md` -- this file