# NHL Audit -- Phase 6: Trust Classification

## Date: 2026-04-10

## Object Trust Matrix

### RESEARCH PIPELINE OBJECTS

| Object | Class | Trust | Notes |
|--------|-------|-------|-------|
| phase1_build_canonical.py | Data ETL | TRUSTED | Clean multi-source merge with audit trail |
| nhl_games_canonical.csv | Data | TRUSTED | 6506 games, 98.8% market coverage, OT/SO tracked |
| phase3_build_features_and_ridge.py | Feature + Model | CONDITIONAL | Rolling features are PIT-safe; league avg prior has minor lookahead (F1) |
| nhl_feature_table.parquet | Features | CONDITIONAL | Valid for historical seasons; F1 affects early-season games |
| ridge_home_model.pkl | Model | TRUSTED (in context) | Valid Ridge model, alpha selected on validate, not overfit |
| ridge_away_model.pkl | Model | TRUSTED (in context) | Same as above |
| phase4_sim.py | Simulation | TRUSTED | Standard independent Poisson, correctly implemented |
| phase45_calibration.py | Calibration | CONDITIONAL | Dynamic drift is PIT-safe in backtest; static fallback is arbitrary |
| phase5_market_architecture.py | Economics | CONDITIONAL | Flat -110 assumption; actual prices not used |

### LIVE PIPELINE OBJECTS

| Object | Class | Trust | Notes |
|--------|-------|-------|-------|
| nhl_daily_pipeline.py | Live Pipeline | FAILED | 79.4% of features frozen at prior (F3) |
| nhl_refresh_canonical.py | Data Refresh | TRUSTED | Correctly extends canonical with new games |
| extend_canonical_2526.py | Data Extension | TRUSTED | Correct schema, handles missing MoneyPuck |
| nhl_decisions.parquet | Signals | CONTAMINATED | Historical signals graded against actuals; live signals invalid due to F3 |
| nhl_performance_report.txt | Report | MISLEADING | Reports historical ROI that is irrelevant to live system |

### RESEARCH OBJECTS (not deployed)

| Object | Class | Trust | Notes |
|--------|-------|-------|-------|
| research_archetypes/* | Research | NOT DEPLOYED | 6-phase archetype study, never integrated |

## Finding Summary

| ID | Finding | Severity | Impact |
|----|---------|----------|--------|
| F1 | League avg shrinkage uses full-season data (minor lookahead) | LOW | ~0.5-1pp ROI bias in early-season games |
| F2 | OT/SO goals in rolling features | LOW | Negligible (~3.6% of scoring) |
| F3 | CRITICAL: 79.4% of features frozen at league prior in live | CRITICAL | Model degenerates to ~20% of trained capability |
| F4 | Flat -110 price assumption in backtest | LOW-MOD | Optimistic bias when juice varies |
| F5 | No actual-price ROI tracking | MODERATE | Cannot assess true live economics |
| F6 | Closing vs opening line economics | LOW | Small effect, partially tracked via CLV |
| F7 | Tier inversion in live (all tiers losing) | HIGH | No tier selection can save the current system |
| F8 | Static drift correction misapplied to new season | HIGH | Drift varies 3x across seasons |
| F9 | Systematic under-projection bias | HIGH | Drives 93% UNDER signal ratio |

## Classification Legend
- TRUSTED: Object is sound for its intended purpose
- CONDITIONAL: Object has known limitations but is usable with caveats
- FAILED: Object does not function as intended; outputs are unreliable
- CONTAMINATED: Contains mix of valid and invalid data
- MISLEADING: Presents information that could lead to wrong conclusions
