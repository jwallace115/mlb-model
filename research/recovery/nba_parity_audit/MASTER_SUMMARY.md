# NBA Parity Audit -- Master Summary

**Date:** 2026-04-11
**Auditor:** Claude Code

---

## Files Produced

| File | Contents |
|------|----------|
| phase1_authoritative_objects.md | Core model, archetype teams, playoff boards |
| phase2_live_object_specs.md | Live pipeline entry points, feature computation, prediction |
| phase3_feature_parity.md | Feature-by-feature training vs live comparison |
| phase4_feature_parity_test.md | Quantified feature gaps, VM limitations |
| phase5_model_signal_parity.md | Model file parity, archetype signal parity |
| phase6_cache_stale_state.md | File ages, frozen lists, orphan files |
| phase7_final_verdict.md | Per-object verdicts with rationale |
| NBA_PARITY_FINAL_VERDICT.md | Executive summary and recommended actions |
| nba_parity_verdicts.csv | Machine-readable verdict table |

---

## Key Findings

### 1. Feature Parity Gap (MEDIUM risk)
The live pipeline (run_nba.py _build_current_team_states) does NOT compute location-specific rolling features. The training pipeline (features.py) does, and 96% of training games used location-split ORtg/DRtg/pace. The 6 affected features (ortg, drtg, pace x home/away) carry the largest Ridge coefficients. Quantified impact: median 1.8 pts ORtg difference per game, translating to ~3-5 pts of prediction noise.

### 2. Stale Kill Signal (HIGH risk)
ELITE_DEF2_at_ELITE_DEF was revalidated on 2026-04-10 and received a KILL verdict (OOS: 43% hit, -18% ROI). The signal remains active in production. This is the highest-priority fix.

### 3. Injury Asymmetry (MEDIUM risk)
Training features have injury_adj=0.0 throughout. Live pipeline applies up to -4.5 pts ORtg injury adjustment. Model has never seen injury-adjusted values during training.

### 4. Orphan Model Files (LOW risk)
nba/models/totals_base_model.pkl (20 features, alpha=500) and variance_model.pkl exist but are NOT used by the live pipeline. These should be documented as deprecated to avoid confusion.

### 5. Archetype Contamination (LOW risk, bounded)
All archetype team sets were derived from data including the 2024-25 validation season. This is contamination but is bounded because archetypes modify signal context/confidence, not model predictions directly. Only ROAD_WARRIOR survived TRUE OOS testing.

---

## Overall Assessment

The NBA model pipeline is structurally sound. The core Ridge model, feature engineering logic, simulation, and results tracking are all clean. The feature parity gap (location splits) is the most impactful finding but can be remediated by adding ~30 lines of location-split code to the live pipeline. The stale ELITE_DEF2 signal is a one-line fix (disable it).

No production-breaking issues. No data integrity problems. No lookahead contamination in the core model.
