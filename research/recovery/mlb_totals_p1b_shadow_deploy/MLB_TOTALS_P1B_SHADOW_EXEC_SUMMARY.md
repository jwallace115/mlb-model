# MLB Totals P1B Shadow Deploy — Executive Summary

**Date:** 2026-04-12
**Object ID:** mlb_p1b_coldwarm_earlyheavy_over_v1
**Status:** DEPLOYED (shadow mode)

## What was deployed

A shadow pipeline for the P1B Cold-Warm EARLY_HEAVY FG Over signal.
This signal fires full-game OVER at cold-climate outdoor parks on warm days
(>=75F, June-September) when the F5/FG ratio exceeds 0.5625 and the
FG over price is <= -105.

## Backtest performance (frozen, from P1B build)

| Period          |   N | Win%   | ROI     | CLV     |
|-----------------|-----|--------|---------|---------|
| Discovery 2023  | 204 | 61.27% | +14.87% | +0.0808 |
| Validation 2024 |  90 | 57.78% |  +8.92% | +0.0484 |
| OOS 2025        |  84 | 60.71% | +14.26% | +0.0767 |
| **ALL**         |**378**|**60.32%**|**+13.32%**|**+0.0722**|

## Frozen rules

| Parameter             | Value                              |
|-----------------------|------------------------------------|
| Side                  | Full-game OVER                     |
| Month window          | June-September (6-9)               |
| Cold-climate parks    | 18-team set (BAL BOS CHC CHW CIN CLE COL DET KCR MIN NYM NYY PHI PIT SEA SFG STL WSN) |
| Temperature threshold | Forecast >= 75F                    |
| F5 ratio threshold    | F5_total / FG_total > 0.5625       |
| Price rule            | FG over price <= -105              |

## Infrastructure

| Component          | Path / Detail                                    |
|--------------------|--------------------------------------------------|
| Pipeline script    | `mlb/pipeline/mlb_totals_p1b_shadow.py`          |
| Shadow tracker     | `mlb/logs/mlb_p1b_coldwarm_earlyheavy_over_shadow_2026.json` |
| Frozen spec lock   | `research/recovery/mlb_totals_p1b_shadow_deploy/phase0_frozen_spec_lock.md` |
| Health check       | Added to `shared/health_check.py` shadow_logs list |

## Cron schedule (VM, all times UTC)

| Time (UTC) | Time (ET)  | Job                  |
|------------|------------|----------------------|
| 15:20      | 11:20 AM   | Signal generation    |
| 06:10      |  2:10 AM   | Grading              |

## Data sources

- **Schedule:** MLB Stats API (`statsapi.mlb.com`)
- **FG total + over price:** Line snapshots (`mlb_sim/data/line_snapshots_2026.json`) with fallback to odds API cache (`data/cache/odds_full_YYYY-MM-DD.json`)
- **F5 total:** F5 lines parquet (`mlb_sim_f5/data/f5_lines_2026.parquet`)
- **Temperature:** Open-Meteo via `modules/weather.py`

## Dry run result

- **Date:** 2026-04-12 (April)
- **Result:** 0 signals (month gate correctly blocked: April is outside June-September window)
- **Tracker initialized:** empty signals array, all modes tested (generate, grade, summary)

## Timeline

- **April-May 2026:** Infrastructure burn-in period (0 signals expected; verifies daily cron runs clean)
- **June 1, 2026:** First possible qualifying signals
- **July 2026:** First review gate (after ~30 resolved signals, compare to backtest Win% of 60.32%)
- **Promotion criteria:** 50+ resolved, Win% >= 55%, positive ROI, no systematic temperature drift

## Monitoring rules

1. Health check tracks cron log freshness (26h staleness threshold)
2. Monthly review: compare shadow Win% to backtest baseline
3. Temperature parity: each signal logs `forecast_temp_f` + `weather_source` + `weather_timestamp`
4. No modifications to frozen rules without full revalidation against discovery/validation/OOS periods

## Activation decision

Shadow-only until:
1. Minimum 50 resolved signals
2. Win% >= 55% (allows for regression from 60.32% backtest)
3. ROI positive
4. No temperature source anomalies
5. Manual review of monthly breakdown confirms no single-month concentration
