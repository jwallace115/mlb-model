# DEPLOYMENT RECOMMENDATION

## Summary

The clean V1 model eliminates lookahead contamination from the original V1 Ridge model.
All pitcher features (xFIP, K%, BB%, avg_ip), offense (wRC+), bullpen (FIP), and flyball 
interaction are now computed using strict point-in-time expanding means with shift(1).

## OOS (2025) Performance at p>0.57

- Bets: 55
- Win Rate: 45.5%
- ROI @ -110: -13.2%
- Profitable: NO

## Recommendations

### 1. REPLACE contaminated V1 model with clean V1
**Priority: CRITICAL**

The contaminated model uses future information. Even if its backtest numbers look better,
they are dishonest. The clean model is the only valid baseline.

Action: Copy `research/recovery/v1_clean_model/v1_ridge_clean.pkl` to `sim/data/phase9_baseline_model.pkl`

### 2. REPLACE feature_table.parquet with clean features
**Priority: CRITICAL**

Action: Copy `research/recovery/v1_clean_features/baseball_features_pit_v1.parquet` to replace 
or augment `sim/data/feature_table.parquet`

### 3. UPDATE sim_projections.py to use PIT feature computation
**Priority: HIGH**

The daily pipeline in `modules/sim_projections.py` currently calls FanGraphs API for 
season-aggregate stats. It must be updated to use the PIT methodology (expanding game logs).

### 4. RE-RUN all downstream pipelines
**Priority: HIGH**

All V1-dependent objects (S12 overlay, shadow signals, etc.) must be re-evaluated 
with clean V1 inputs.

### 5. INVESTIGATE further — clean V1 not profitable OOS
**Priority: MEDIUM**

The clean model is not profitable OOS, suggesting the original model's apparent edge was largely driven by lookahead bias. Consider whether additional genuinely predictive features can be found, or whether the current architecture has reached its honest ceiling.

## Objects to Keep / Replace / Retire

| Object | Action | Reason |
|--------|--------|--------|
| V1 Ridge model | REPLACE | Contaminated with lookahead |
| feature_table.parquet | REPLACE | Contains contaminated features |
| phase9_baseline_model.pkl | REPLACE | Built on contaminated features |
| sim_projections.py | UPDATE | Must use PIT computation method |
| Park/weather/umpire features | KEEP | Already clean (static or game-day) |
| Bullpen availability features | KEEP | Already uses shift(1) |
| Shadow log history | RETIRE | Generated from contaminated model |
| Market snapshots | KEEP | Independent of model |
