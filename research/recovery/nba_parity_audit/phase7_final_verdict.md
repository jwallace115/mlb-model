# Phase 7: Final Verdict

## Object-Level Verdicts

### 1. Ridge Model (nba/data/ridge_model.pkl)
**CAVEATED**
- The model file itself is clean: RidgeCV alpha=0.1, 15 features, trained on 2022-24.
- The CAVEAT: 6 of 15 features (ortg, drtg, pace x home/away) are computed differently in training vs live. Training uses location-specific rolling (home/away split); live uses overall rolling. These 6 features carry the largest model coefficients. Median feature-level difference: 1.8 pts, which translates to ~3-5 pts of prediction noise per game.
- This is NOT a bug -- it is a design gap in the live pipeline that was never implemented.

### 2. Feature Computation (nba/modules/features.py)
**PROVEN LIVE-IDENTICAL** (for itself)
- shift(1) correct, no lookahead, proper blending, location-specific rolling
- This module is only used for TRAINING feature computation
- The live pipeline in run_nba.py reimplements feature computation (correctly for 9/15 features, with the location-split gap for 6/15)

### 3. ROAD_WARRIOR_at_STRONG_HOME
**PROVEN LIVE-IDENTICAL**
- Team sets match between live code and revalidation
- SURVIVES OOS revalidation (63.2% hit rate, +20.7% ROI, N=226)
- Only archetype that passed TRUE OOS testing

### 4. ELITE_DEF2_at_ELITE_DEF
**PROVEN LIVE-IDENTICAL but UNTRUSTED**
- Team sets match between live and revalidation
- COLLAPSES in OOS (43.0% hit rate, -18.0% ROI)
- Still active in production code despite KILL verdict from revalidation
- Should be disabled immediately

### 5. BALANCED_OFF_vs_PASSIVE_DEF
**PROVEN LIVE-IDENTICAL**
- Team sets match
- DIMINISHED in OOS (51.4%, -1.8% ROI) -- at breakeven
- Signal is context-only, not bet-worthy as standalone

### 6. ELITE_OREB_vs_WEAK_BOXOUT
**PROVEN LIVE-IDENTICAL**
- Team sets match
- DIMINISHED in OOS (50.4%, -3.7% ROI)
- Used only as amplifier for venue signal, not standalone -- acceptable

### 7. THREE_HEAVY_vs_FOUL_PRONE
**CLEAN BUT NOT LIVE-IDENTICAL**
- Team sets are frozen but were not separately revalidated in the archetype audit
- No OOS performance data available
- Low risk: generates UNDER signals that are CONTEXT_ONLY, never standalone bets

### 8. Playoff Boards (P1, P2, P4)
**CAVEATED**
- Definitions are clean and internally consistent
- Historical evidence spans only 3 seasons with tiny samples (exact N not documented per board)
- P1 early-series correction (-6.0 pts for G1-2) is a hard-coded calibration fix
- Finals modifier (-0.25u) based on N=17 games
- Underpowered but structurally sound

### 9. Playoff Series Blend
**CLEAN BUT NOT LIVE-IDENTICAL**
- Blend weight ramp (0, 0.35, 0.60, 0.80, 1.00 by game) calibrated from 2025 shadow run
- Cannot verify on VM -- requires live playoff data
- Logic is clean in code review

### 10. Injury Adjustments
**CLEAN BUT NOT LIVE-IDENTICAL**
- Flat 1.5 pts/100 ORtg per Out/Doubtful player, capped at 4.5
- Training data has injury_adj=0.0 for all rows (disabled for historical)
- Live applies injury adjustment on top of features trained without it
- This creates a train/live asymmetry: model has never seen injury-adjusted ORtg values
- Impact is bounded (max -4.5 pts ORtg, coefficient ~1.8 = max ~8 pts total shift)

### 11. nba/models/totals_base_model.pkl
**UNTRUSTED**
- Orphan file not used by live pipeline
- Different feature set (20 features vs 15), different alpha (500 vs 0.1)
- Should be documented as deprecated

### 12. nba/models/variance_model.pkl
**UNTRUSTED**
- Orphan file not used by live pipeline
- Should be documented as deprecated

## Summary Table

| Object | Verdict | Key Issue |
|--------|---------|-----------|
| Ridge model pkl | CAVEATED | Feature parity gap (location splits) |
| features.py (training) | PROVEN LIVE-IDENTICAL | Clean, correct |
| ROAD_WARRIOR signal | PROVEN LIVE-IDENTICAL | Only surviving archetype |
| ELITE_DEF2 signal | PROVEN LIVE-IDENTICAL, UNTRUSTED | KILL verdict, still active |
| BALANCED_OFF signal | PROVEN LIVE-IDENTICAL | DIMINISHED, context-only |
| OREB signal | PROVEN LIVE-IDENTICAL | DIMINISHED, amplifier only |
| THREE_HEAVY signal | CLEAN BUT NOT LIVE-IDENTICAL | Not revalidated separately |
| Playoff boards | CAVEATED | Underpowered samples |
| Playoff series blend | CLEAN BUT NOT LIVE-IDENTICAL | Cannot verify on VM |
| Injury adjustments | CLEAN BUT NOT LIVE-IDENTICAL | Train/live asymmetry |
| totals_base_model.pkl | UNTRUSTED | Orphan, not used |
| variance_model.pkl | UNTRUSTED | Orphan, not used |
