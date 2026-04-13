# Phase 0 — Frozen Spec Lock: MLB Totals P1B Cold-Warm EARLY_HEAVY FG Over

**Locked:** 2026-04-12
**Object ID:** mlb_p1b_coldwarm_earlyheavy_over_v1
**Ruleset Version:** frozen_v1

## Decision Gate Source
File: `research/recovery/mlb_totals_p1b_coldwarm_child/MLB_TOTALS_P1B_EXEC_SUMMARY.md`
Meta: `research/recovery/mlb_totals_p1b_coldwarm_child/p1b_meta.json`

## Frozen Rules (do not modify without full revalidation)

| Parameter             | Value                                             |
|-----------------------|---------------------------------------------------|
| Side                  | Full-game OVER                                    |
| Month window          | June through September (month 6-9)                |
| Cold-climate parks    | 18-team set (see below)                           |
| Temperature threshold | Forecast first-pitch temp >= 75 F                 |
| F5 ratio threshold    | F5_total / FG_total > 0.5625                      |
| Price rule            | FG closing over price <= -105                     |

## Frozen Cold-Climate Outdoor Park Set (18 teams)

BAL, BOS, CHC, CHW, CIN, CLE, COL, DET, KCR,
MIN, NYM, NYY, PHI, PIT, SEA, SFG, STL, WSN

Geographic criterion: outdoor stadiums, roughly north of 40 deg N latitude.

## Backtest Results (from exec summary)

| Period          |   N | W-L     | Win%   | ROI     | CLV     |
|-----------------|-----|---------|--------|---------|---------|
| Discovery 2023  | 204 | 125-79  | 61.27% | +14.87% | +0.0808 |
| Validation 2024 |  90 |  52-38  | 57.78% |  +8.92% | +0.0484 |
| OOS 2025        |  84 |  51-33  | 60.71% | +14.26% | +0.0767 |
| **ALL**         |**378**|**228-150**|**60.32%**|**+13.32%**|**+0.0722**|

## f5r_p67 derivation
- p67 of 2023 discovery F5-ratio distribution = 0.5625
- This is the EARLY_HEAVY threshold: games where >56.25% of the total line
  is concentrated in the first 5 innings, indicating an early-heavy scoring path.

## Shadow deployment plan
- Shadow tracker: `mlb/logs/mlb_p1b_coldwarm_earlyheavy_over_shadow_2026.json`
- Pipeline script: `mlb/pipeline/mlb_totals_p1b_shadow.py`
- No qualifying signals expected until June 2026 (month gate)
- April-May: verify infrastructure runs cleanly with 0-signal days
