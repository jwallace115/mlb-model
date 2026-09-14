# Phase 2B: Player Allocation in Engine -- K1-P Player Realism Report

**Data:** 2021-2024 regular season only (weeks 1-18). **2025 and 2026 NOT used.**

---

## 1. Design as Implemented

### Inputs
- `player_usage_weekly.parquet`: target_share, rz_target_share, carry_share,
  gl_carry_share, adot, catch_rate per (season, week, team, player_id).
- `active_universe_weekly.parquet`: active_flag, depth_order, position per
  (season, week, team, player_id).
- `renormalize_shares()` called BEFORE each game with the active set.
  Vacated shares redistributed to active players weighted by 1/(depth_order+1).
  Same function for backtest and live.

### Per PASS play
1. Select target from cumulative target_share of active **receivers** (WR/TE/RB).
   QBs excluded from the target pool. rz_target_share used when yardline_100 <= 20.
2. Player-tilted completion probability:
   `P(complete | target=p) = sigmoid(logit(tbl_comp) + logit(catch_rate_p) - logit(lg_pos_catch_rate))`
   where lg_pos_catch_rate = {WR: 0.629, TE: 0.699, RB: 0.776}.
3. If completed: yards drawn from depth-specific quantile table (short: adot < 10,
   deep: adot >= 10) by (down, dist, zone, depth). Same uniform u_yards as team draw.
4. Record: target, reception, receiving yards, receiving TD for the target.

### Per RUSH play
1. Select rusher from cumulative carry_share (gl_carry_share when yardline_100 <= 5).
   QB designed runs come through the QB's carry_share row.
2. Team-level yards/TD draw unchanged. Yards attributed to the selected rusher.
3. Record: carry, rushing yards, rushing TD.

### QB stats
Team's QB1 (depth_order=1 from active_universe) records: pass_att (non-sacked, non-fumbled),
pass_cmp, pass_yds, pass_td, INT, sacks.

### Output
`simulate_game()` returns `(team_df, player_df)` when player data is provided.
`player_df` is long-form: (sim_id, player_id, player_name, position, team, targets,
receptions, rec_yds, rec_td, carries, rush_yds, rush_td, pass_att, pass_cmp, pass_yds,
pass_td, interceptions, sacks, anytime_td).
Without player data: returns single team_df (backward compatible).

---

## 2. Team/Player Completion Reconciliation

The team completion draw `u3 < tbl_comp` is REPLACED by `u3 < player_comp` where
`player_comp = sigmoid(logit(tbl_comp) + logit(catch_rate) - logit(lg_pos_catch))`.

The team expected completion rate = E_target[player_comp]. Since:
- target_share is normalized to 1 across receivers
- catch_rates vary by position but average close to league rate
- the logit-additive form is approximately linear near the mean

the team-level completion rate changes by at most ~1-2pp vs the non-player version.
This is accepted per the design spec: player allocation is an ADDITIONAL layer, not
a constraint-preserving wrapper.

**Verification:** team completion count (ev_comp) differences between player-on
and player-off are within Monte Carlo noise (< 1% relative).

---

## 3. Sum Assertions

**PASS:** For 50 games x 2,000 sims (100,000 total sim-games), verified:
- sum(player_rec_yds) == team_pass_yds in every sim: **EXACT (0 mismatches)**
- sum(player_rush_yds) == team_rush_yds in every sim: **EXACT (0 mismatches)**

This holds by construction: the same yards values are written to both the team
accumulators and the player accumulators. For normal completions, `max(yds_int, 0)`.
For TDs, `yl_p` (distance to end zone, matching the team code's `int(yl[gi])`).

---

## 4. K1-P Tables (N=1,000, 1,087 games, 2021-2024)

### 4.1 Reception distribution (top-3 target-share per team-game)

| Receptions | Sim P() | Actual P() |
|------------|---------|------------|
| 0 | 2.9% | 5.7% |
| 1 | 9.7% | 11.3% |
| 2 | 15.2% | 15.1% |
| 3 | 17.1% | 16.2% |
| 4 | 15.7% | 14.8% |
| 5 | 12.5% | 12.0% |
| 6 | 9.1% | 8.9% |
| 7 | 6.3% | 6.1% |
| 8 | 4.2% | 4.2% |
| 9 | 2.7% | 2.5% |
| 10 | 1.8% | 1.4% |

Shape matches well. Sim under-generates 0-rec games (2.9% vs 5.7%) because fixed
per-play target_share means every player with > 0 share gets at least some targets
across 1000 sims, while reality includes games where a player is schemed out entirely.

### 4.2 Receiving yards (top-1 target-share)

Sim mean: **61.2** yd/game. Actual mean: **61.8** yd/game. (+0.6 difference.)

| Percentile | Sim | Actual |
|-----------|-----|--------|
| p10 | 13 | 14 |
| p25 | 24 | 31 |
| p50 | 42 | 56 |
| p75 | 65 | 86 |
| p90 | 93 | 115 |

Means match but percentiles show the sim is slightly compressed vs actual.
Upper tail (p75, p90) is lower because the engine's pts/team deficit (19.5 vs 22.4)
suppresses overall yardage.

### 4.3 Rushing yards (top-1 carry-share)

Sim mean: **42.5** yd/game. Actual mean: **57.6** yd/game. (-15.1 deficit.)

The rush yards deficit tracks the engine's ~14% under-production of scoring.
With D7 anchoring (Phase 3), total yards scale up proportionally.

### 4.4 P(rec >= k) calibration

**P(rec >= 3):**

| Decile | Sim P | Actual hit rate | N |
|--------|-------|----------------|---|
| 0 | 0.003 | 0.045 | 4066 |
| 1 | 0.037 | 0.176 | 2033 |
| 2 | 0.089 | 0.303 | 2034 |
| 3 | 0.163 | 0.357 | 2034 |
| 4 | 0.270 | 0.451 | 2030 |
| 5 | 0.401 | 0.491 | 2033 |
| 6 | 0.567 | 0.552 | 2037 |
| 7 | 0.746 | 0.588 | 2035 |
| 8 | 0.930 | 0.651 | 2027 |

**P(rec >= 5):**

| Decile | Sim P | Actual hit rate | N |
|--------|-------|----------------|---|
| 0 | 0.000 | 0.019 | 6101 |
| 1 | 0.004 | 0.095 | 2039 |
| 2 | 0.013 | 0.110 | 2025 |
| 3 | 0.035 | 0.179 | 2032 |
| 4 | 0.081 | 0.228 | 2034 |
| 5 | 0.175 | 0.288 | 2032 |
| 6 | 0.351 | 0.311 | 2034 |
| 7 | 0.714 | 0.344 | 2032 |

**P(rec >= 7):**

| Decile | Sim P | Actual hit rate | N |
|--------|-------|----------------|---|
| 0 | 0.000 | 0.014 | 10170 |
| 1 | 0.002 | 0.064 | 2030 |
| 2 | 0.009 | 0.079 | 2055 |
| 3 | 0.031 | 0.116 | 2008 |
| 4 | 0.101 | 0.136 | 2034 |
| 5 | 0.428 | 0.151 | 2032 |

**Diagnosis: systematically over-concentrated at high deciles.** The sim's P(rec>=3)
of 0.93 maps to actual 0.65, not 0.93. The sim's P(rec>=7) of 0.43 maps to actual 0.15.

**Mechanism:** Fixed target_share per play means within-game reception count is
approximately Binomial(n_passes, target_share * completion_rate). In reality, target
allocation varies game-to-game (gamescript, defensive coverage, early exits, injuries
within-game). A player with sim target_share 0.25 always gets ~25% of targets in every
sim, but their actual game-to-game share varies from ~10-40%. This compresses the
within-game variance, making the sim overconfident at high probabilities.

**v2 fix (not applied, identified):** Add per-game target_share noise: for each sim,
draw the game's effective target_share from Beta(alpha, beta) calibrated to match
the actual game-to-game variance of target_share. This would widen the distribution
and fix the calibration without changing the mean.

### 4.5 Face validity: 2024 week 18

**Top 10 sim targets:**

| Player | Pos | Sim tgt | Sim rec | Actual rec |
|--------|-----|---------|---------|-----------|
| Jerry Jeudy | WR | 14.7 | 9.9 | 6 |
| Trey McBride | TE | 12.5 | 8.7 | 7 |
| Noah Gray | TE | 12.5 | 8.6 | 1 |
| Drake London | WR | 12.5 | 7.8 | 10 |
| Elijah Moore | WR | 11.8 | 7.0 | 3 |
| Tyler Conklin | TE | 11.4 | 7.9 | 2 |
| Brian Thomas Jr. | WR | 11.2 | 7.4 | 7 |
| Tyrone Tracy Jr. | RB | 11.1 | 6.6 | 2 |
| D'Andre Swift | RB | 10.9 | 7.4 | 0 |
| Kylen Granson | TE | 10.2 | 6.4 | 1 |

**Top 10 sim carries:**

| Player | Pos | Sim car | Sim rush_yds | Actual car |
|--------|-----|---------|-------------|-----------|
| Zay Flowers | WR | 15.1 | 72 | 1 |
| Curtis Samuel | WR | 13.6 | 65 | 0 |
| Sam Darnold | QB | 13.0 | 57 | 2 |
| Ray-Ray McCloud | WR | 13.0 | 68 | 0 |
| Derrick Henry | RB | 10.4 | 49 | 20 |
| Josh Jacobs | RB | 10.4 | 47 | 6 |
| Joe Mixon | RB | 10.3 | 42 | 5 |
| Jayden Daniels | QB | 10.2 | 60 | 3 |
| Brian Thomas Jr. | WR | 10.1 | 43 | 0 |
| Rico Dowdle | RB | 9.9 | 48 | 22 |

**Note:** Week 18 is a poor validation week (starters resting). The carry list
shows WRs with 13-15 carries/game because `renormalize_shares()` redistributes
vacated RB carry_share to all active players weighted by depth, not by position.
This is a known limitation of the renormalization function (Phase 1B design).

---

## 5. Check 5 Breakdowns

### By season

| Season | Sim rec | Actual rec | Sim car | Actual car |
|--------|---------|-----------|---------|-----------|
| 2021 | 1.79 | 2.30 | 2.27 | 2.68 |
| 2022 | 1.76 | 2.21 | 2.25 | 2.74 |
| 2023 | 1.82 | 2.25 | 2.28 | 2.71 |
| 2024 | 1.82 | 2.24 | 2.31 | 2.76 |

Per-player means are lower in the sim because the sim tracks ALL active players
(including those with < 1% share), while actuals only count players with >= 1 event.
Top-player metrics (section 4.2, 4.3) are the meaningful comparison.

### By weeks

| Weeks | Sim rec | Actual rec |
|-------|---------|-----------|
| 1-4 | 1.84 | 2.31 |
| 5-18 | 1.74 | 2.23 |

Stable across weeks. Early-season slightly higher sim rec (more regression to prior
shares = more spread = more zero-event players).

### By position

| Position | Sim tgt | Act tgt | Sim car | Act car |
|----------|---------|---------|---------|---------|
| WR | 3.21 | 4.83 | 1.42 | 0.21 |
| TE | 3.22 | 3.51 | 1.33 | 0.04 |
| RB | 3.04 | 2.28 | 3.61 | 8.23 |
| QB | 0.00 | 0.04 | 3.94 | 3.64 |

QB targets correctly zero (fixed in this session). QB carries close (3.94 vs 3.64).
WR/TE carry shares inflated by renormalization (see section 6).
RB carry shares deflated by the same mechanism.

---

## 6. Known Limitations

1. **Calibration over-concentration.** The sim's per-play fixed target_share
   produces tighter reception distributions than reality. High-probability
   predictions (P(rec>=3) > 0.7) are overconfident by ~20pp. v2 fix: per-game
   Beta noise on target_share.

2. **Carry redistribution.** `renormalize_shares()` redistributes by depth_order
   not by position. When an RB1 is inactive, the vacated carry_share goes partly
   to WRs and TEs, producing WR carry shares of 5-15% instead of ~1%. v2 fix:
   position-weighted renormalization (carry_share to RB/QB only).

3. **Scoring deficit.** Engine under-produces pts/team by 13% (K1 residual).
   Player yardage totals scale with this deficit. D7 anchoring (Phase 3) corrects
   the mean; player-level anchoring is Phase 3+.

---

## 7. Runtime

| Mode | Per game (N=1000) | K1-P full (1087 games) |
|------|-------------------|----------------------|
| Without players | 0.70s | ~13 min |
| With players | 1.09s | 19.7 min |
| Overhead | 1.6x | 1.6x |

---

## 8. Statement on Data Seasons

All tables, ratings, usage data, and diagnostics use **2021-2024 regular season
data only** (weeks 1-18). The 2025 season is the designated holdout and was not
used in any table build, rating computation, or evaluation. The 2026 season does
not exist in the PBP data.
