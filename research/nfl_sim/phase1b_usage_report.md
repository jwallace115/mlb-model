# Phase 1B: PIT Player Usage Shares Report

## Algorithm

1. From PBP, build one per-(season, week, game_id, team, player_id) aggregate
   table with raw counts (targets, carries, rec_yards, air_yards, etc.) and a
   parallel per-(season, week, game_id, team) team-totals table. Done once with
   groupby-agg. No .apply(lambda), no per-player loop.
2. PIT accumulation loops over WEEKS (max 22), never over players. For each
   week w, "available" = rows with week < w. Decay weights are a column
   multiply before a groupby-sum. Shares = player weighted count / team
   weighted count. Rates = weighted numerator / weighted denominator.
3. Shrinkage and s-1 prior blend are column arithmetic over the whole table.
4. Grid search calls steps 2-3 twelve times. 2.4s per grid point, 28.7s total.

Total elapsed: 43.5s (load + aggregate + grid + full build + PIT test).

## PIT Definition

Same as team ratings: the row for (season s, week w, player) uses plays from
season s weeks < w plus season s-1 as a prior. Shrink targets are always the
s-1 league mean by position, never the current season's.

PIT test: player 00-0031588 (2023 WR, wk 9), full vs truncated frame (delete
season > 2023 and 2023 week >= 10). All numeric columns equal to 1e-9.

## Chosen Parameters

- share_half_life: 2 games (recent usage matters — unlike team EPA where
  half_life=inf won, share distributions shift with scheme/injury)
- k_share: 20 targets/carries (light shrinkage — shares are more informative
  per observation than EPA)
- Tuned on: 2021-2024 ONLY. No row from 2025 or 2026 touched the tuning.

## Grid Results

| share_half_life | k_share | mean_RMSE | tgt_RMSE | car_RMSE |
|---|---|---|---|---|
| 2 | 20 | 0.1423 | 0.0797 | 0.2049 |
| 4 | 20 | 0.1432 | 0.0797 | 0.2066 |
| 8 | 20 | 0.1442 | 0.0800 | 0.2084 |
| inf | 20 | 0.1458 | 0.0805 | 0.2112 |
| 2 | 50 | 0.1555 | 0.0856 | 0.2255 |
| 4 | 50 | 0.1566 | 0.0859 | 0.2273 |
| 8 | 50 | 0.1575 | 0.0861 | 0.2289 |
| inf | 50 | 0.1588 | 0.0865 | 0.2310 |
| 2 | 100 | 0.1702 | 0.0917 | 0.2487 |
| 4 | 100 | 0.1712 | 0.0920 | 0.2504 |
| 8 | 100 | 0.1719 | 0.0922 | 0.2517 |
| inf | 100 | 0.1729 | 0.0924 | 0.2533 |

Unlike team EPA (flat surface), shares show a clear gradient: shorter decay
and less shrinkage win. This is expected — usage distributions shift with
scheme changes and injuries, and shares carry more signal per play than EPA.

## Check 5: RMSE by Season

| Season | Target RMSE | Carry RMSE |
|---|---|---|
| 2021 | 0.0797 | 0.2187 |
| 2022 | 0.0803 | 0.2040 |
| 2023 | 0.0763 | 0.1953 |
| 2024 | 0.0823 | 0.2004 |

Weeks 1-4 target RMSE: 0.0940
Weeks 5-18 target RMSE: 0.0754

Early-season shares are noisier (less data → more shrinkage → more regression
error). The gap narrows as the season progresses.

## Face Validity: 2024 Week 18

### Top 10 Target Share (by raw target count)

| Player | Team | Pos | Target Share | Targets |
|---|---|---|---|---|
| Malik Nabers | NYG | WR | 0.319 | 164 |
| Ja'Marr Chase | CIN | WR | 0.283 | 161 |
| CeeDee Lamb | DAL | WR | 0.194 | 154 |
| Garrett Wilson | NYJ | WR | 0.208 | 150 |
| Justin Jefferson | MIN | WR | 0.275 | 145 |
| Brock Bowers | LV | TE | 0.230 | 144 |
| Drake London | ATL | WR | 0.288 | 141 |
| Trey McBride | ARI | TE | 0.275 | 136 |
| Jerry Jeudy | CLE | WR | 0.261 | 135 |
| Amon-Ra St. Brown | DET | WR | 0.245 | 134 |

### Top 10 Carry Share (RB only, by raw carry count)

| Player | Team | Carry Share | Carries |
|---|---|---|---|
| Saquon Barkley | PHI | 0.646 | 348 |
| Kyren Williams | LA | 0.687 | 316 |
| Derrick Henry | BAL | 0.589 | 305 |
| Josh Jacobs | GB | 0.588 | 297 |
| Bijan Robinson | ATL | 0.617 | 277 |
| Jonathan Taylor | IND | 0.688 | 271 |
| Chuba Hubbard | CAR | 0.554 | 251 |
| Najee Harris | PIT | 0.424 | 251 |
| Aaron Jones | MIN | 0.583 | 245 |
| Joe Mixon | HOU | 0.668 | 242 |

## Questionable Designations per Season

| Season | Count |
|---|---|
| 2021 | 1,513 |
| 2022 | 1,511 |
| 2023 | 1,583 |
| 2024 | 1,513 |
| 2025 | 1,283 |
| 2026 | 24 |

Note: these are total Questionable designations, not the subset who ended up
inactive. Measuring Questionable-but-inactive requires game-day active lists
which are not in the nflverse injury report.

## Outputs

- `nfl/data/sim/ratings/player_usage_weekly.parquet` (58,364 rows)
- `nfl/data/sim/ratings/active_universe_weekly.parquet` (52,858 rows)
- `nfl/sim/params_v1.json` (updated with `usage` key)

No row from 2025 or 2026 touched the tuning or evaluation.
