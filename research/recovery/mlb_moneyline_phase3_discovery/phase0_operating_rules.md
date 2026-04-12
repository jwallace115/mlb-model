# Phase 3 Discovery Engine — Operating Rules Memo

## Date Locked: 2026-04-11

## Prior Failures (from Phase 1 + Phase 2)
- V1 FanGraphs tables: CONTAMINATED (future data leakage). No descendants of sim/phase2_build_features.py.
- Lineup features: PERMANENTLY EXCLUDED (not available PIT-safe at prediction time).
- Any feature requiring lineup knowledge is killed.

## Split Definition (LOCKED)
| Period     | Seasons   | Purpose              |
|------------|-----------|----------------------|
| Discovery  | 2022-2023 | Hypothesis testing   |
| Validation | 2024      | Freeze confirmation  |
| OOS        | 2025      | Final economic test  |

## PIT-Safety Rule
All features must use strict `date < game_date` or `shift(1)` within player/team group.
No same-day data. No post-game data applied to same game.

## Universe
Close moneyline games: favorite implied probability 0.512–0.556 (approx -105 to -125).
Both-sides view: either home or away can be fav/dog.

## Economic Test
ROI computed at actual closing ML prices from canonical odds file.
Bet $100 on identified side. Profit = payout - 100. ROI = mean(profit) / 100.

## Minimum N
N >= 150 per discovery period for meaningful signal. Smaller cells noted but not promoted.
