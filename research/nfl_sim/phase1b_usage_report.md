# Phase 1B: PIT Player Usage Shares Report (FIX pass)

## Algorithm

Vectorised: loop over weeks (max 22), not players. Decay weights are column
multiply before groupby-sum. Shares = player / team, then shrinkage, then
renormalisation to sum=1 per (season, week, team).

Runtimes: aggregates 1.1s, grid (12 pts) 53.2s, extension (6 pts) 26.6s,
full build 5.6s, total 103.7s. ~4.4s per grid point.

## FIX 1: Share Renormalisation

Before fix: 2024 wk18 target_share sums ranged 1.16–1.75 per team (shrinkage
toward position prior inflated total mass). Carry shares 0.63–1.14.

After fix: every (season, week, team) with at least one played player sums
to 1.0 within 1e-6 for all four share columns. Assertion: PASS.

## FIX 2: Injury Join

Before fix: 17 non-Active rows across 5 seasons. Join failed because players
designated Out almost always have roster status INA/RES (807 INA, 303 RES,
1 ACT for 2024 Out players), so filtering to status==ACT first excluded them.

After fix: active universe built from ALL rostered skill players. inactive_flag
if roster status != ACT OR injury report_status in (Out, Doubtful). Now 39,283
inactive rows. Out counts per season (assertion >= 200): 2021=323, 2022=384,
2023=329, 2024=353, 2025=452. PASS.

Questionable-but-inactive: snap_counts table uses player NAMES (not gsis_id),
preventing a clean gsis_id join. UNVERIFIED — requires a fuzzy name match or
pfr_player_id crosswalk. Reported as total Questionable designations instead:
2021=1,513; 2022=1,511; 2023=1,583; 2024=1,513; 2025=1,283.

## FIX 3: 32-Team Player Universe

2026 wk2: 32 teams, 922 players. Every RB/WR/TE/QB on the weekly roster gets
a row (prior-only if no plays yet). Assertion: PASS.

Rate attributes changed from previous file because the larger roster universe
changes team-total denominators. This is an expected consequence of FIX 3, not
a regression. Share columns changed by design (FIX 1 renormalisation).

## PIT Definition

Same as team ratings: (season s, week w, player) uses plays from s weeks < w
plus s-1 as prior. Shrink targets are s-1 league mean by position.

PIT test: player 00-0031588 at both week 9 and week 10 (truncation boundary).
All numeric columns equal to 1e-9. PASS.

## Chosen Parameters

- share_half_life: **1 game** (most recent game dominates)
- k_share: **5** targets/carries (minimal shrinkage)
- Grid: 12-point base + 6-point pre-declared extension (boundary winner triggered)
- Combined 16 points evaluated. Chosen point is on the BOUNDARY of the extended
  grid. The monotone surface toward shorter decay and less shrinkage suggests the
  optimal point may be outside the grid (half_life < 1 game or k < 5), but this
  is the pre-declared limit — no further extension.
- Tuned on 2021–2024 ONLY. No row from 2025 or 2026 touched the tuning.

## Grid Results (16 points, sorted by RMSE)

| share_half_life | k_share | mean_RMSE | tgt_RMSE | car_RMSE |
|---|---|---|---|---|
| 1 | 5 | 0.2100 | 0.1035 | 0.3165 |
| 2 | 5 | 0.2112 | 0.1039 | 0.3184 |
| 1 | 10 | 0.2133 | 0.1055 | 0.3211 |
| 2 | 10 | 0.2144 | 0.1058 | 0.3229 |
| 1 | 20 | 0.2176 | 0.1079 | 0.3273 |
| 2 | 20 | 0.2186 | 0.1083 | 0.3289 |
| 4 | 20 | 0.2195 | 0.1087 | 0.3303 |
| 8 | 20 | 0.2201 | 0.1090 | 0.3312 |
| inf | 20 | 0.2208 | 0.1093 | 0.3322 |
| 2 | 50 | 0.2260 | 0.1124 | 0.3396 |
| 4 | 50 | 0.2267 | 0.1127 | 0.3407 |
| 8 | 50 | 0.2271 | 0.1129 | 0.3414 |
| inf | 50 | 0.2276 | 0.1131 | 0.3422 |
| 2 | 100 | 0.2326 | 0.1158 | 0.3495 |
| 4 | 100 | 0.2331 | 0.1160 | 0.3503 |
| 8 | 100 | 0.2335 | 0.1161 | 0.3508 |

## Renormalisation Example

ATL 2023 wk 9: RB 00-0030968 (Cordarrelle Patterson) designated Out.
Before renormalisation: carry shares distributed across 27 players (~0.026–0.130).
After renormalisation: Out player share = 0.0, RB carry shares sum = 1.000000.
Redistribution weighted by 1/depth_order (next man up gets more).

## Check 5: RMSE by Season

| Season | Target RMSE | Carry RMSE |
|---|---|---|
| 2021 | 0.1039 | 0.3243 |
| 2022 | 0.1036 | 0.3134 |
| 2023 | 0.1006 | 0.3131 |
| 2024 | 0.1060 | 0.3148 |

Weeks 1–4 target RMSE: 0.1112
Weeks 5–18 target RMSE: 0.1013

## Face Validity: 2024 Week 18 (Shares)

### Top 10 Target Share

| Player | Team | Pos | Target Share | Targets |
|---|---|---|---|---|
| Puka Nacua | LA | WR | 0.273 | 107 |
| Brian Thomas Jr. | JAX | WR | 0.201 | 124 |
| Malik Nabers | NYG | WR | 0.193 | 164 |
| A.J. Brown | PHI | WR | 0.183 | 97 |
| Trey McBride | ARI | TE | 0.165 | 136 |
| DeVonta Smith | PHI | WR | 0.164 | 90 |
| Ja'Marr Chase | CIN | WR | 0.164 | 161 |
| Justin Jefferson | MIN | WR | 0.158 | 145 |
| Zay Flowers | BAL | WR | 0.155 | 115 |
| Drake London | ATL | WR | 0.154 | 141 |

### Top 10 RB Carry Share

| Player | Team | Carry Share | Carries |
|---|---|---|---|
| Kyren Williams | LA | 0.275 | 316 |
| Chase Brown | CIN | 0.270 | 230 |
| Rico Dowdle | DAL | 0.270 | 213 |
| Tyrone Tracy Jr. | NYG | 0.264 | 178 |
| Jonathan Taylor | IND | 0.263 | 271 |
| Saquon Barkley | PHI | 0.236 | 348 |
| Jahmyr Gibbs | DET | 0.231 | 227 |
| Aaron Jones | MIN | 0.216 | 245 |
| Bijan Robinson | ATL | 0.215 | 277 |
| Josh Jacobs | GB | 0.211 | 297 |

## Outputs

- `nfl/data/sim/ratings/player_usage_weekly.parquet` (86,112 rows)
- `nfl/data/sim/ratings/active_universe_weekly.parquet` (92,124 rows)
- `nfl/sim/params_v1.json` (usage key updated with 16-row grid)

No row from 2025 or 2026 touched tuning.
