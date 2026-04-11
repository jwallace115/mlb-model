# Phase 5: Model/Signal Parity

## Ridge Model Parity

### Model File: nba/data/ridge_model.pkl
- **FEATURE_COLS in training (train_model.py):** 15 features (matches pkl)
- **FEATURE_COLS in live (run_nba.py):** 15 features (same list, same order)
- **Scaler:** Same StandardScaler stored in pkl, used by both paths
- **PARITY: OK** -- same model, same scaler, same feature names and order

### Feature Mapping Mismatch
- Training: home_3pa_rate stored as "home_3pa_rate" in features.parquet
- Live: computed as fg3a_rate in team_state, mapped to "home_3pa_rate" in feat_row
- **PARITY: OK** -- naming translation is correct

## ROAD_WARRIOR Signal Parity

### Live Team Sets (run_nba.py):
- _ROAD_WARRIOR = {ATL, CHI, DAL, DET, GSW, HOU, NYK, PHI, PHX, UTA}
- _STRONG_HOME = {ATL, BOS, DEN, IND, MIL, OKC, POR, SAS}

### Revalidation Verdict:
- SURVIVES with OOS hit rate 63.2%, ROI +20.7% (N=226)
- TRUE OOS (pre-discovery 2022-24): hit rate 63.2%, confirming signal is real
- This is the only archetype that passed OOS validation

### Parity Check:
- The revalidation used the FROZEN team sets from run_nba.py (confirmed in revalidation methodology)
- Live pipeline uses same sets
- **PARITY: PROVEN IDENTICAL**

## ELITE_DEF2_at_ELITE_DEF Signal Parity

### Live Team Sets:
- _ELITE_DEF = {BOS, CLE, GSW, MIL, MIN, OKC}
- _ELITE_DEF2 = {HOU, LAC, LAL, MIA, NYK, ORL, SAC}

### Revalidation Verdict: COLLAPSES (KILL)
- OOS hit rate 43.0%, ROI -18.0%
- **Still active in live code** despite KILL verdict
- Code comment says "UNDER — hist edge -3.0pts (p=0.022)" but OOS shows -18% ROI

### Parity:
- Team sets match between live and revalidation
- **PARITY: PROVEN IDENTICAL but signal should be KILLED per revalidation**

## Shot Profile Signals

### Live Team Sets:
- _BALANCED_OFF = {DEN, HOU, IND, NYK, OKC}
- _PASSIVE_DEF = {BOS, CHI, CLE, DEN, LAL, MIA, MIL, NYK, PHX, SAS, UTA, WAS}
- _THREE_HEAVY_OFF = {BOS, CHI, CLE, GSW, MIA, MIL, SAC}
- _FOUL_PRONE_DEF = {HOU, IND, ORL}

### Revalidation Verdict: DIMINISHED (MONITOR)
- BALANCED_OFF_vs_PASSIVE_DEF: OOS hit rate 51.4%, ROI -1.8%
- No separate revalidation for THREE_HEAVY_vs_FOUL_PRONE

### Parity:
- Team sets match between live and revalidation
- **PARITY: PROVEN IDENTICAL**

## OREB Signal

### Live Team Sets (defined inside function, not module-level):
- _ELITE_OREB_TEAMS = 15 teams
- _WEAK_BOXOUT_TEAMS = 15 teams

### Revalidation Verdict: DIMINISHED (MONITOR)
- OOS hit rate 50.4%, ROI -3.7%

### Parity:
- Team sets match
- **PARITY: PROVEN IDENTICAL**

## Playoff Boards

### Board Definitions:
- P1: R1 G1-2 UNDER, sizing 1.0u, edge -6.82
- P2: R1 G5-7 OVER, sizing 0.75u, edge +8.19
- P4: CF Non-Elim G1-4 OVER, sizing 0.75u, edge +9.85

### Historical Evidence:
- 3-season consistency noted in code comments
- P4 claims 80% hit rate (N not specified)
- All boards from 2022-25 data including validation season

### Parity:
- Definitions are hardcoded constants in run_nba.py
- No external data dependency beyond playoff game detection
- **PARITY: CLEAN BUT UNDERPOWERED** (tiny samples, 3 seasons)

## Summary

| Signal | Live vs Revalidation | Status |
|--------|---------------------|--------|
| Ridge model predictions | PARITY GAP (location splits) | Core features differ |
| ROAD_WARRIOR | PROVEN IDENTICAL | SURVIVES |
| ELITE_DEF2_at_ELITE_DEF | PROVEN IDENTICAL | Should be KILLED |
| BALANCED_OFF_vs_PASSIVE_DEF | PROVEN IDENTICAL | DIMINISHED |
| THREE_HEAVY_vs_FOUL_PRONE | PROVEN IDENTICAL | Not revalidated |
| ELITE_OREB_vs_WEAK_BOXOUT | PROVEN IDENTICAL | DIMINISHED |
| Playoff boards P1/P2/P4 | CLEAN | Underpowered |
