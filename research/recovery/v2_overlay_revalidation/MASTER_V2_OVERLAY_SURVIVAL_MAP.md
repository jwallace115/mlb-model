# MASTER V2 OVERLAY SURVIVAL MAP

Date: 2026-04-10
Baseline: V2 Model_B (Ridge alpha=50, 14 features, target=market_error)
Train: 2022-2023, Val: 2024, OOS: 2025

## Key Context
V2 Model_B has mean predicted edge of +0.43 runs (strong over bias).
It generates ~900 over signals (edge > 0.5) per season but effectively 0 under signals.
S12 and P09 were originally designed as UNDER amplifiers for V1.
Therefore overlay testing uses: (1) standalone blind-under, (2) V2-over contra-filter,
(3) combined with V2 edge direction.

## Results

| Overlay | Formula | PIT-Safe | Cutoff | OOS Verdict |
|---------|---------|----------|--------|-------------|
| S12 | avg(csw_r5) - 5*avg(xfip) | YES | >= 9.8151 (Q80) | **DIMINISHED** |
| P09 | avg(hh_r5) * park_factor | YES | <= 35.0674 (Q20) | **COLLAPSES** |
| flyball_wind | already in V2 model | YES | >= 0.6900 (Q80) | **SURVIVES** |

## Summary

- SURVIVES: 1
- DIMINISHED: 1
- COLLAPSES: 1

## Per-Overlay Detail

### S12
- Formula: avg(home_csw_r5, away_csw_r5) - 5 * avg(home_xfip, away_xfip)
- Data: pitcher_start_metrics_per_start.csv, csw_r5 = shift(1).rolling(5)
- PIT verified: YES
- OOS blind-under: active hit=54.3%, inactive hit=52.5%
- OOS ROI flat: active=+3.7%, inactive=+0.1%
- Verdict: **DIMINISHED**

### P09
- Formula: avg(home_hh_r5, away_hh_r5) * park_factor_runs
- Data: opponent_adjusted_engine_v2/pitcher_start_performance.parquet
- PIT verified: YES (shift(1).rolling(5, min=3) computed in script)
- OOS blind-under: active hit=50.9%, inactive hit=52.8%
- OOS ROI flat: active=-2.9%, inactive=+0.8%
- Verdict: **COLLAPSES**

### flyball_wind
- Already a continuous feature in V2 (coefficient +0.07)
- Testing discrete overlay on top of model's continuous usage
- OOS V2-over: FW-active hit=49.1%, FW-inactive hit=46.3%
- OOS ROI flat: FW-active=-6.3%, FW-inactive=-11.7%
- Verdict: **SURVIVES**

## Conclusion

Surviving overlays: flyball_wind — consider integration.
Collapsed overlays: P09 — do not integrate.
Diminished overlays: S12 — marginal value, monitor only.