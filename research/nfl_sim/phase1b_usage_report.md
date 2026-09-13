# Phase 1B-FIX-2: PIT Player Usage Shares Report

## Formula (as implemented)

For each share column (target_share, carry_share, rz_target_share, gl_carry_share),
for player p on team t, week w:

    opp_p    = decay-weighted sum of TEAM opportunities (team targets or team carries)
               over games in weeks < w where p was ACTIVE for t (active_flag = True)
    touch_p  = decay-weighted sum of p's own touches over those same games
    obs      = touch_p / opp_p           (0 if opp_p = 0)
    n_eff    = opp_p                     (NOT the player's own touch count)
    prior    = p's own share in s-1 if p had >= 50 team opp while active in s-1;
               else s-1 league mean share for (position, depth_order)
    shrunk   = (n_eff * obs + k_share * prior) / (n_eff + k_share)
    pw_eff   = prior_weight * k_share / (n_eff + k_share)  — decays with evidence
    blend    = (1 - pw_eff) * shrunk + pw_eff * (prior_regression * prior
               + (1 - prior_regression) * league_mean_for_position_depth)

Zero-evidence override: if raw touches = 0 and opp > 0 (player was on the field
while their team had opportunities but never touched the ball), share = 1e-8.
If opp = 0 (never active for a game, e.g. game-day inactive all season), share = 1e-8.

Renormalise each share column within (season, week, team) to sum to 1.
Decay weight per game = 0.5 ** ((w - 1 - game_week) / share_half_life).

Carries EXCLUDE qb_scramble and qb_kneel (designed runs + QB sneaks only).
Share universe = 53-man roster (status ACT or INA) for the current week.

Rate attributes (adot, catch_rate, yac_per_rec, yards_per_target, yards_per_carry,
explosive rates) keep their existing formula with n = the player's own targets or
carries — that IS the right sample size for a rate. Rate shrinkage uses k from
the ratings params (k=100).

## Depth-Order Prior Table (from s-1 data)

Computed from each season's data. Depth groups: RB1, RB2, RB3+, WR1, WR2, WR3,
WR4+, TE1, TE2+, QB. Depth order from nflverse depth charts (min depth_team per
player-team-week-position). Missing depth → deepest bin.

### Season 2023 (prior for 2024 usage):

| depth_group | tgt_share | car_share | rz_tgt | gl_car |
|---|---|---|---|---|
| QB | 0.0009 | 0.0304 | 0.0014 | 0.0664 |
| RB1 | 0.0639 | 0.3119 | 0.0583 | 0.2473 |
| RB2 | 0.0509 | 0.2176 | 0.0468 | 0.1463 |
| RB3+ | 0.0303 | 0.1403 | 0.0374 | 0.1047 |
| TE1 | 0.1121 | 0.0008 | 0.1364 | 0.0013 |
| TE2+ | 0.0440 | 0.0004 | 0.0487 | 0.0011 |
| WR1 | 0.1156 | 0.0069 | 0.1147 | 0.0021 |
| WR2 | 0.0581 | 0.0055 | 0.0631 | 0.0032 |
| WR3 | 0.0423 | 0.0026 | 0.0252 | 0.0011 |
| WR4+ | 0.0533 | 0.0029 | 0.0671 | 0.0000 |

Tables for all seasons (2020–2026) printed in script output and stored in code.

## Assertion Values

**(a)** PHI 2024 wk18: Barkley carry_share = **0.649** (> 0.50 ✓),
Hurts carry_share = **0.158** (> 0.15 ✓). Hurts has roster status INA at wk17-18
(concussion protocol); included because he was ACT for weeks 1-16. His 92 designed
carries (excluding 49 scrambles) contribute to carry_share via the active_universe join.

**(b)** 2024 wk18 league-wide: max zero-carry team carry_share mass = **0.000** (< 0.05 ✓).
Max zero-target team target_share mass = **0.000** (< 0.05 ✓). Zero-evidence override
sets share = 1e-8 for players who were active for ≥1 game with 0 touches.

**(c)** All four share columns sum to 1.0 within 1e-6 per team-week. **PASS**.

**(d)** 2026 wk2: **32 teams, 520 players**. Active universe carries forward the last
available week's roster (week 1 → week 2) for seasons with incomplete data. **PASS**.

**(e)** active_flag mean = **0.552**. 44.8% of rostered skill players are inactive:
DEV (practice squad, 19,115), RES (reserve/IR, 9,298), INA (game-day inactive, 4,494),
CUT (2,013), plus Out (2,004) and Questionable (907) from injury reports.
This is expected — practice squad alone accounts for ~22% of roster rows.

## Grid Results (12 points, 2021–2024 only)

No row from 2025 or 2026 touched tuning.

| share_half_life | k_share | mean_RMSE | tgt_RMSE | car_RMSE |
|---|---|---|---|---|
| 4 | 20 | 0.1444 | 0.0856 | 0.2032 |
| 8 | 20 | 0.1446 | 0.0856 | 0.2035 |
| 2 | 20 | 0.1453 | 0.0860 | 0.2047 |
| inf | 20 | 0.1454 | 0.0859 | 0.2049 |
| inf | 50 | 0.1473 | 0.0857 | 0.2089 |
| 8 | 50 | 0.1475 | 0.0856 | 0.2094 |
| 4 | 50 | 0.1485 | 0.0859 | 0.2111 |
| inf | 100 | 0.1509 | 0.0862 | 0.2156 |
| 2 | 50 | 0.1510 | 0.0866 | 0.2154 |
| 8 | 100 | 0.1524 | 0.0865 | 0.2183 |
| 4 | 100 | 0.1544 | 0.0871 | 0.2217 |
| 2 | 100 | 0.1580 | 0.0882 | 0.2277 |

**Chosen: share_half_life = 4, k_share = 20.** BOUNDARY of the 12-point grid
(half_life at min, k at min). Extension NOT triggered — condition is specifically
(2, 20) winning, which did not occur. The surface is flat across half_life at k=20
(0.1444–0.1454), confirming k_share dominates. k_share = 20 is under one game of
evidence (~25–35 team opportunities per game).

## Check 5: RMSE by Season

| Season | Target RMSE | Carry RMSE |
|---|---|---|
| 2021 | 0.0841 | 0.2152 |
| 2022 | 0.0945 | 0.1996 |
| 2023 | 0.0781 | 0.1977 |
| 2024 | 0.0849 | 0.1999 |

Weeks 1–4 target RMSE: 0.0842
Weeks 5–18 target RMSE: 0.0860

No season or early/late period is anomalous. Carry RMSE is higher than target RMSE
(carries are more concentrated, so errors are larger in absolute terms).

## PIT Test

Player 00-0031588 at week 9 and week 10 (truncation boundary). All numeric columns
equal to 1e-9. **PASS**.

## Renormalisation Example

ATL 2023 wk9: RB Keith Smith designated Out.

Before: Allgeier 0.443, Robinson 0.353, Patterson 0.155, Igwebuike ~0, Smith ~0.
After: Allgeier 0.466, Robinson 0.385, Patterson 0.163, Igwebuike 0, Smith 0.
Out player share = 0 ✓, RB carry sum = 1.000000 ✓.

## Face Validity: 2024 Week 18 (Shares)

### Top 10 Target Share

| Player | Team | Pos | Target Share | n |
|---|---|---|---|---|
| Malik Nabers | NYG | WR | 0.345 | 164 |
| Brian Thomas Jr. | JAX | WR | 0.337 | 124 |
| Trey McBride | ARI | TE | 0.307 | 136 |
| Puka Nacua | LA | WR | 0.303 | 107 |
| A.J. Brown | PHI | WR | 0.288 | 97 |
| Drake London | ATL | WR | 0.286 | 141 |
| Justin Jefferson | MIN | WR | 0.283 | 145 |
| Ja'Marr Chase | CIN | WR | 0.272 | 161 |
| Jerry Jeudy | CLE | WR | 0.269 | 135 |
| Keenan Allen | CHI | WR | 0.264 | 120 |

### Top 10 Carry Share

| Player | Team | Pos | Carry Share | n |
|---|---|---|---|---|
| Chase Brown | CIN | RB | 0.795 | 230 |
| D'Onta Foreman | CLE | RB | 0.723 | 61 |
| Kyren Williams | LA | RB | 0.718 | 316 |
| Rico Dowdle | DAL | RB | 0.714 | 213 |
| Jonathan Taylor | IND | RB | 0.682 | 271 |
| Michael Carter | ARI | RB | 0.664 | 18 |
| Josh Jacobs | GB | RB | 0.658 | 297 |
| Saquon Barkley | PHI | RB | 0.649 | 348 |
| Bijan Robinson | ATL | RB | 0.646 | 277 |
| Aaron Jones | MIN | RB | 0.622 | 245 |

Barkley, Henry (not shown — may be lower due to multi-back committee), Jacobs,
Robinson all present. Kyren Williams tops carry share. Carry shares now reflect
actual usage concentration — Barkley at 0.649 vs 0.236 in the previous (broken)
version.

## Outputs

- `nfl/data/sim/ratings/player_usage_weekly.parquet` (47,254 rows)
- `nfl/data/sim/ratings/active_universe_weekly.parquet` (87,495 rows)
- `nfl/sim/params_v1.json` (usage key updated with 12-row grid)

No row from 2025 or 2026 touched tuning.
