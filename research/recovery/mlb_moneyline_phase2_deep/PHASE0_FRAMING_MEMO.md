# MLB Moneyline Phase 2 Deep — Framing Memo

## Phase 1 Failure Summary
Phase 1 tested structural/schedule axes (home/away, day/night, rest, price bands)
against MLB closing moneylines across 2022-2025.
**Result: ZERO strategies survived disc->val->OOS.**

## Phase 2 Thesis
Can PIT-safe rolling pitcher/team performance features identify close-game
mispricing that structural axes cannot?

## Data Integrity
- Features built ONLY from pitcher_game_logs + game_table
- ALL use shift(1) + expanding/rolling within season
- NO lineup features, NO FanGraphs aggregates, NO model outputs
- Closing prices from canonical DK odds archive
