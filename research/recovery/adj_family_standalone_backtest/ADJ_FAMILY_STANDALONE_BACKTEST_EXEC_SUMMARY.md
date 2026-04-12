# ADJ Family Standalone Clean Backtest — Executive Summary

**Generated:** 2026-04-12
**Temporal Split:** Discovery 2022-2023 | Validation 2024 | OOS 2025
**Total games with dual-starter ADJ features + closing odds:** 9521

## Signal Definitions (locked from shadow_signals.py)

Each ADJ metric is a rolling 3-start opponent-adjusted value per pitcher.
For each game: `combined = (home_val + away_val) / 2`
Signal fires when `combined > 0` → bet direction: **UNDER** at closing under price.

| Signal | Metric | Meaning when > 0 |
|--------|--------|-------------------|
| ADJ_K_RATE | adj_k_rate_last3 | Both pitchers striking out more than opponent-expected |
| ADJ_CONTACT | adj_contact_rate_last3 | Both pitchers suppressing contact below opponent-expected |
| ADJ_HH | adj_hard_hit_last3 | Both pitchers suppressing hard contact below league avg |
| ADJ_BB_RATE | adj_bb_rate_last3 | Both pitchers walking fewer than opponent-expected |
| ADJ_RUN_SUPP | adj_run_suppression_last3 | Both pitchers suppressing runs below opponent-expected |

## Results Table

| Signal | Split | Bets | W | L | Push | Win% | ROI% | Units |
|--------|-------|------|---|---|------|------|------|-------|
| ADJ_BB_RATE | ALL | 2133 | 1116 | 1017 | 90 | 52.3 | 0.1 | 1.5 |
| ADJ_BB_RATE | DISC | 955 | 487 | 468 | 32 | 51.0 | -2.3 | -21.9 |
| ADJ_BB_RATE | OOS | 602 | 319 | 283 | 30 | 53.0 | 1.1 | 6.4 |
| ADJ_BB_RATE | VAL | 576 | 310 | 266 | 28 | 53.8 | 3.0 | 17.0 |
| ADJ_CONTACT | ALL | 5100 | 2596 | 2504 | 216 | 50.9 | -2.7 | -135.4 |
| ADJ_CONTACT | DISC | 2376 | 1178 | 1198 | 101 | 49.6 | -4.9 | -117.1 |
| ADJ_CONTACT | OOS | 1388 | 735 | 653 | 56 | 53.0 | 1.0 | 14.1 |
| ADJ_CONTACT | VAL | 1336 | 683 | 653 | 59 | 51.1 | -2.4 | -32.4 |
| ADJ_HH | ALL | 3964 | 2040 | 1924 | 185 | 51.5 | -1.6 | -65.1 |
| ADJ_HH | DISC | 2016 | 1038 | 978 | 102 | 51.5 | -1.3 | -27.1 |
| ADJ_HH | OOS | 850 | 453 | 397 | 34 | 53.3 | 1.4 | 12.3 |
| ADJ_HH | VAL | 1098 | 549 | 549 | 49 | 50.0 | -4.6 | -50.3 |
| ADJ_K_RATE | ALL | 2015 | 1030 | 985 | 86 | 51.1 | -2.4 | -47.6 |
| ADJ_K_RATE | DISC | 926 | 453 | 473 | 33 | 48.9 | -6.1 | -56.6 |
| ADJ_K_RATE | OOS | 551 | 296 | 255 | 27 | 53.7 | 2.1 | 11.5 |
| ADJ_K_RATE | VAL | 538 | 281 | 257 | 26 | 52.2 | -0.5 | -2.4 |
| ADJ_RUN_SUPP | ALL | 4148 | 2123 | 2025 | 178 | 51.2 | -2.1 | -86.8 |
| ADJ_RUN_SUPP | DISC | 1935 | 970 | 965 | 81 | 50.1 | -3.8 | -74.4 |
| ADJ_RUN_SUPP | OOS | 1125 | 613 | 512 | 41 | 54.5 | 4.0 | 44.6 |
| ADJ_RUN_SUPP | VAL | 1088 | 540 | 548 | 56 | 49.6 | -5.2 | -57.1 |

## Baseline (bet under blindly on all games)

| Split | Bets | Win% | ROI% |
|-------|------|------|------|
| DISC | 4521 | 50.9 | -2.3 |
| VAL | 2282 | 50.3 | -4.0 |
| OOS | 2293 | 52.2 | -0.5 |
| ALL | 9096 | 51.1 | -2.3 |

## Decisions

| Signal | DISC ROI% | VAL ROI% | OOS ROI% | Decision |
|--------|-----------|----------|----------|----------|
| ADJ_K_RATE | -6.1 | -0.5 | +2.1 | **WEAK-RETAIN** |
| ADJ_CONTACT | -4.9 | -2.4 | +1.0 | **WEAK-RETAIN** |
| ADJ_HH | -1.3 | -4.6 | +1.4 | **WEAK-RETAIN** |
| ADJ_BB_RATE | -2.3 | +3.0 | +1.1 | **RETAIN** |
| ADJ_RUN_SUPP | -3.8 | -5.2 | +4.0 | **WEAK-RETAIN** |

## Combined Signal (all 5 fire simultaneously)

| Split | Bets | Win% | ROI% |
|-------|------|------|------|
| DISC | 60 | 35.0 | -32.9 |
| VAL | 44 | 54.5 | +4.3 |
| OOS | 34 | 61.8 | +17.4 |
| ALL | 138 | 47.8 | -8.6 |

Small sample (34 OOS bets) but striking 61.8% win rate and +17.4% ROI in OOS.

## Key Observations

1. **All 5 signals are OOS-positive** (2025): ROI ranges from +1.0% (ADJ_CONTACT) to +4.0% (ADJ_RUN_SUPP).
2. **All 5 signals are discovery-negative** (2022-2023): ROI ranges from -1.3% (ADJ_HH) to -6.1% (ADJ_K_RATE).
3. **Baseline context matters**: blind-under ROI was -0.5% in 2025 vs -2.3% in 2022-2023 and -4.0% in 2024. The 2025 under market was favorable.
4. **OOS lift over baseline**: ADJ_RUN_SUPP provides +4.5pp lift over baseline (-0.5% to +4.0%), ADJ_K_RATE +2.6pp, ADJ_BB_RATE +1.6pp. Modest but consistent.
5. **ADJ_BB_RATE is the only clean RETAIN**: positive in both VAL (+3.0%) and OOS (+1.1%), only signal with VAL+OOS alignment.
6. **High firing rates dilute edge**: ADJ_CONTACT fires on 64% of games, ADJ_RUN_SUPP on 52%. These are not selective filters.
7. **Reversed discovery-to-OOS pattern is suspicious**: every signal flips sign from DISC to OOS. Could reflect 2025 market regime rather than genuine signal improvement.

## Methodology Notes

- Feature source: `research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet`
- Features are rolling 3-start values computed PRIOR to each game (no look-ahead)
- Closing odds from `mlb_sim/data/mlb_odds_closing_canonical.parquet` (best under price across books)
- ROI computed at actual closing American odds, risk $1/bet, profit = decimal payout on wins
- Pushes excluded from bet count and ROI
- No production files modified