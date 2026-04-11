# NBA Damage Map — Object-Level Trust Classification

**Date:** 2026-04-10

## Color Legend
- GREEN: Clean, no issues found
- YELLOW: Minor concerns, acceptable for production
- ORANGE: Significant concerns, needs remediation
- RED: Broken, stop using immediately

---

## Core Model Pipeline

| Object | Color | Finding |
|--------|-------|---------|
| nba/modules/features.py | GREEN | shift(1) correct; no lookahead; proper blending |
| nba/modules/fetch_box_stats.py | GREEN | Per-game Oliver possession; no external data |
| nba/modules/fetch_games.py | GREEN | Clean NBA API fetch + cache |
| nba/train_model.py | GREEN | Clean 2022-24 train, 2024-25 val; RidgeCV |
| nba/backtest.py | GREEN | No market economics; honest diagnostics |
| nba/phase4b.py | GREEN | True OOS test (no retraining) |
| nba/modules/simulate.py | GREEN | Correct MC; proper sigma; no shortcuts |
| nba/phase5.py | GREEN | Simulation calibration; honest reporting |
| nba/phase6.py | GREEN | H1 model OOS test |
| nba/config.py | YELLOW | Global sigma may not fit all matchups |

## Data Files

| Object | Color | Finding |
|--------|-------|---------|
| nba/data/features.parquet | GREEN | 3690 games; proper shift(1) rolling |
| nba/data/box_stats.parquet | GREEN | 7380 team-games; per-game stats |
| nba/data/games.parquet | GREEN | Clean canonical game table |
| nba/data/nba_historical_closing_lines.parquet | GREEN | 3685 real closing lines |
| nba/data/ridge_model.pkl | YELLOW | Trained 2022-24 only; OOS stable |
| nba/data/h1_ridge_model.pkl | YELLOW | Same caveat as full-game model |
| nba/data/nba_results_log.parquet | GREEN | 164 honest live results |
| nba/data/nba_market_snapshots.parquet | YELLOW | All prices -110 (synthetic) |

## Live Pipeline

| Object | Color | Finding |
|--------|-------|---------|
| nba/run_nba.py (base model path) | GREEN | Features match training; correct live rolling |
| nba/run_nba.py (archetype signals) | ORANGE | Team sets derived from 2024-25 val data |
| nba/run_nba.py (playoff boards) | ORANGE | 3-season, tiny samples; underpowered |
| nba/phase6_shadow.py | YELLOW | Correctly tracked; -110 synthetic |
| nba/segment_overlay.py | GREEN | Failing segment correctly disabled |

## Signal Discovery / Research

| Object | Color | Finding |
|--------|-------|---------|
| nba/analysis/*.parquet | ORANGE | All include 2024-25 validation in discovery |
| research/nba_backwards_discovery.txt | YELLOW | Full-data scan, but found nothing actionable |
| research/nba/schedule_fatigue/ | GREEN | 0/7 signals passed permutation tests (correct) |
| nba/docs/nba_small_edge_postmortem.md | GREEN | Honest postmortem; correctly declared unprofitable |
| nba/phase7b/ | GREEN | Honest reconciliation of conflicting ROI numbers |

## Archetype Team Sets (all in run_nba.py)

| Set | Color | Issue |
|-----|-------|-------|
| _ELITE_DEF / _ELITE_DEF2 | ORANGE | Derived from 3-season data including validation |
| _ROAD_WARRIOR / _STRONG_HOME | ORANGE | Same contamination; pruned with 2025-26 live data |
| _BALANCED_OFF / _PASSIVE_DEF | ORANGE | Same contamination |
| _THREE_HEAVY_OFF / _FOUL_PRONE_DEF | ORANGE | Same contamination |
| _ELITE_OREB_TEAMS / _WEAK_BOXOUT_TEAMS | ORANGE | Same contamination |
| _CORE_AWAY / _CORE_HOME | ORANGE | Subset of venue signal; tiny N=40 |

## Shadow Logs

| Object | Color | Performance |
|--------|-------|-------------|
| nba_phase6_rs_shadow.parquet | YELLOW | 18 graded: 8W-10L (44.4%), shadow only |
| nba_signal_log.parquet | ORANGE | 35 bets on contaminated archetype signals |
| nba_small_edge_shadow.parquet | GREEN | Legacy; correctly declared unprofitable |

---

## Summary Statistics

- GREEN objects: 20
- YELLOW objects: 7
- ORANGE objects: 12
- RED objects: 0

**Bottom line:** The NBA core model pipeline is clean. The archetype/signal
overlay layer has validation contamination but is bounded in impact because
these signals modify context/confidence, not model predictions directly.
No RED issues found — no equivalent to the MLB FanGraphs lookahead bug.
