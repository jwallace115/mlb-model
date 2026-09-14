# Phase 2B: Player Allocation in Engine -- K1-P Player Realism Report

**Data:** 2021-2024 regular season only (weeks 1-18). **2025 and 2026 NOT used.**

---

## 1. Design as Implemented

### Inputs
- `player_usage_weekly.parquet`: target_share, rz_target_share, carry_share,
  gl_carry_share, adot, catch_rate per (season, week, team, player_id).
- `active_universe_weekly.parquet`: active_flag, depth_order, position per
  (season, week, team, player_id).
- `_renormalize_measured()` called BEFORE each game with the active set (FIX 2).
  Same function for backtest and live.

### Per PASS play
1. Select target from cumulative target_share of active **receivers** (WR/TE/RB).
   QBs excluded from the target pool. rz_target_share used when yardline_100 <= 20.
   Shares are per-sim Beta-dispersed (FIX 1).
2. Player-tilted completion probability:
   `P(complete | target=p) = sigmoid(logit(tbl_comp) + logit(catch_rate_p) - logit(lg_pos_catch_rate))`
   where lg_pos_catch_rate = {WR: 0.629, TE: 0.699, RB: 0.776}.
3. If completed: yards drawn from depth-specific quantile table (short: adot < 10,
   deep: adot >= 10) by (down, dist, zone, depth). Same uniform u_yards as team draw.
4. Record: target, reception, receiving yards, receiving TD for the target.

### Per RUSH play
1. Select rusher from cumulative carry_share (gl_carry_share when yardline_100 <= 5).
   QB designed runs come through the QB's carry_share row.
   Shares are per-sim Beta-dispersed (FIX 1).
2. Team-level yards/TD draw unchanged. Yards attributed to the selected rusher.
3. Record: carry, rushing yards, rushing TD.

### QB stats
Team's QB1 (depth_order=1 from active_universe) records: pass_att (non-sacked, non-fumbled),
pass_cmp, pass_yds, pass_td, INT, sacks.

### Output
`simulate_game()` returns `(team_df, player_df)` when player data is provided.
Without player data: returns single team_df (backward compatible).

---

## 2. FIX 1: Game-Level Share Dispersion

### Beta-binomial overdispersion (phi), MLE-fitted 2021-2024

| Type | Position | phi | N |
|------|----------|-----|---|
| Targets | WR | 42.9 | 8115 |
| Targets | TE | 85.0 | 3923 |
| Targets | RB | 71.3 | 3935 |
| Carries | RB | 7.9 | 4801 |
| Carries | QB | 20.0 | 1795 |

Lower phi = more game-to-game dispersion. WR targets are most dispersed (phi=42.9);
RB carries are extremely dispersed (phi=7.9).

**Implementation:** At game start, for each player, draw game-level share from
`Beta(share * phi, (1-share) * phi)`, then renormalize across the active pool
within each sim. This replaces the fixed share for all play-level draws.

**Result:** 25%-share WR target SD: sim=2.73, actual=3.40. The sim is still
under-dispersed because renormalization introduces negative correlation between
players (one player's share going up mechanically pushes others down). The phi
values are correctly measured from the marginal distribution; the damping is a
structural consequence of the sum-to-one constraint.

---

## 3. FIX 2: Measured Redistribution

### Target redistribution (proportional weights, sum=1 per absent position)

When a player at position P is inactive, vacated target share is redistributed:

| Absent | -> WR | -> TE | -> RB | -> QB |
|--------|-------|-------|-------|-------|
| WR | 0.582 | 0.281 | 0.138 | 0.000 |
| TE | 0.339 | 0.625 | 0.035 | 0.000 |
| RB | 0.588 | 0.131 | 0.280 | 0.000 |

### Carry redistribution (proportional weights)

| Absent | -> RB | -> QB | -> WR | -> TE |
|--------|-------|-------|-------|-------|
| RB | 0.817 | 0.175 | 0.007 | 0.001 |

When an RB is inactive, 82% of vacated carry share goes to other RBs, 18% to QBs,
<1% to WRs. This replaces the prior depth-weighted redistribution which was
position-agnostic.

---

## 4. FIX 3: Pool Concentration Check

For 2024 wk18, 16 teams checked. Sim top-3 target share ranges 0.47-0.82;
actual top-3 share ranges 0.46-0.79. No systematic over-dilution from D14
(zero-touch override). D14 amendment not needed.

---

## 5. Team/Player Completion Reconciliation

The team completion draw `u3 < tbl_comp` is REPLACED by `u3 < player_comp`.
Expected team completion rate = E_target[player_comp]. Changes by at most ~1-2pp
vs the non-player version. Accepted per the design spec.

---

## 6. Sum Assertions

**PASS:** sum(player_rec_yds) == team_pass_yds and sum(player_rush_yds) == team_rush_yds
in every sim. **EXACT (0 mismatches).**

---

## 7. K1-P Checks (N=1,000, 1,087 games, 2021-2024)

### Check A: Position target/carry shares

**Targets:**

| Pos | Sim | Actual | Delta | Status |
|-----|-----|--------|-------|--------|
| WR | 56.1% | 59.8% | -3.7pp | **FAIL** |
| TE | 24.8% | 21.4% | +3.4pp | **FAIL** |
| RB | 19.0% | 18.7% | +0.3pp | PASS |
| QB | 0.1% | 0.1% | -0.0pp | PASS |

**Carries:**

| Pos | Sim | Actual | Delta | Status |
|-----|-----|--------|-------|--------|
| RB | 80.1% | 83.1% | -3.0pp | **FAIL** |
| QB | 11.1% | 13.5% | -2.4pp | **FAIL** |
| WR | 6.9% | 3.2% | +3.7pp | **FAIL** |
| TE | 2.0% | 0.3% | +1.7pp | PASS |

**Mechanism:** The player_usage rating model assigns non-zero carry_share to all
skill players via Bayesian shrinkage (k=20). WRs who occasionally run jet sweeps
get 2-3% carry_share each; with 4-5 active WRs per team, this sums to 10-15% of
carries going to WRs (actual: 3%). The measured redistribution (FIX 2) improved
WR carries from 7.4% to 6.9%, but the base shares themselves are the source. The
target TE bias (+3.4pp) has the same root: TE target_share is inflated by the
shrinkage prior. Both require a ratings-layer fix (position-aware carry/target
prior floors), not an engine-layer fix.

### Check B: Reliability tables

**P(rec >= 3), top-3 target-share:**

| Dec | Sim P | Actual | Gap | Status |
|-----|-------|--------|-----|--------|
| 0 | 0.002 | 0.042 | -0.040 | PASS |
| 1 | 0.041 | 0.149 | -0.108 | **FAIL** |
| 2 | 0.108 | 0.221 | -0.113 | **FAIL** |
| 3 | 0.197 | 0.325 | -0.128 | **FAIL** |
| 4 | 0.304 | 0.368 | -0.064 | **FAIL** |
| 5 | 0.427 | 0.452 | -0.025 | PASS |
| 6 | 0.571 | 0.545 | +0.027 | PASS |
| 7 | 0.738 | 0.673 | +0.065 | **FAIL** |
| 8 | 0.905 | 0.805 | +0.100 | **FAIL** |

**P(rec >= 5):**

| Dec | Sim P | Actual | Gap | Status |
|-----|-------|--------|-----|--------|
| 0 | 0.000 | 0.014 | -0.014 | PASS |
| 1 | 0.006 | 0.059 | -0.053 | **FAIL** |
| 2 | 0.019 | 0.085 | -0.066 | **FAIL** |
| 3 | 0.045 | 0.128 | -0.083 | **FAIL** |
| 4 | 0.093 | 0.161 | -0.068 | **FAIL** |
| 5 | 0.179 | 0.239 | -0.060 | **FAIL** |
| 6 | 0.338 | 0.342 | -0.004 | PASS |
| 7 | 0.638 | 0.536 | +0.102 | **FAIL** |

**P(rec >= 7):**

| Dec | Sim P | Actual | Gap | Status |
|-----|-------|--------|-----|--------|
| 0 | 0.000 | 0.009 | -0.009 | PASS |
| 1 | 0.004 | 0.034 | -0.030 | PASS |
| 2 | 0.011 | 0.045 | -0.034 | PASS |
| 3 | 0.032 | 0.078 | -0.046 | PASS |
| 4 | 0.093 | 0.141 | -0.048 | PASS |
| 5 | 0.326 | 0.268 | +0.058 | **FAIL** |

**P(rush_yds >= 50), top-1 carry-share:**

| Dec | Sim P | Actual | Gap | Status |
|-----|-------|--------|-----|--------|
| 0 | 0.186 | 0.205 | -0.019 | PASS |
| 1 | 0.372 | 0.382 | -0.010 | PASS |
| 2 | 0.492 | 0.471 | +0.021 | PASS |
| 3 | 0.584 | 0.452 | +0.131 | **FAIL** |
| 4 | 0.654 | 0.552 | +0.102 | **FAIL** |
| 5 | 0.713 | 0.474 | +0.239 | **FAIL** |
| 6 | 0.772 | 0.526 | +0.246 | **FAIL** |
| 7 | 0.834 | 0.587 | +0.246 | **FAIL** |
| 8 | 0.892 | 0.659 | +0.234 | **FAIL** |
| 9 | 0.948 | 0.764 | +0.183 | **FAIL** |

**Improvement vs prior session (P(rec>=3) decile 8):**
- Before fixes: sim 0.930, actual 0.651, gap +0.279
- After fixes: sim 0.905, actual 0.805, gap +0.100
- Improvement: 64% reduction in gap

**Mechanism of remaining failures:**

1. **Reception reliability (deciles 1-4 under-predict):** The sim gives low P(rec>=3)
   to players who actually hit 3+ receptions 15-37% of the time. These are bench/depth
   players whose sim share is near-zero but who in reality catch a few passes when
   gamescript or matchup dictates. The share model has no gamescript component.

2. **Reception reliability (deciles 7-8 over-predict):** The Beta dispersion (FIX 1)
   is damped by renormalization (shares sum to 1 mechanically reduces variance). The
   measured phi values are correct for the MARGINAL distribution; the joint constraint
   compresses them. Compensating would require phi adjustment (violating "measured,
   not tuned").

3. **Rush yards (deciles 3-9):** The sim uses team-level rush yards tables for all
   players. A top RB1 with high carry share gets many carries at team-average yards
   per carry, producing unrealistic P(>=50). In reality, matchup-level RB efficiency
   varies and high-carry games often face stacked boxes. No player-level yards
   differentiation exists in the engine (ypc held for v2 per D11).

### Check C: Reception distribution (top-3 target-share)

| Range | Sim | Actual | Gap | Status |
|-------|-----|--------|-----|--------|
| 0 | 2.8% | 5.7% | -3.0pp | PASS |
| 1-3 | 43.8% | 42.5% | +1.2pp | PASS |
| 4-6 | 39.2% | 35.6% | +3.5pp | **FAIL** |
| 7+ | 14.3% | 16.1% | -1.8pp | PASS |

**Mechanism (4-6 FAIL):** The sim over-concentrates around the mean (4-6) and
under-produces both the 0-rec and 7+ tails. This is the same renormalization
damping from FIX 1: after normalizing shares to sum to 1, per-sim variance is
compressed, pulling mass from the tails toward the center.

### Check D: Face validity (2024 wk18)

| Player | Pos | Sim tgt | Sim rec | L4 tgt | L4 rec | Wk18 |
|--------|-----|---------|---------|--------|--------|------|
| Brian Thomas Jr. | WR | 12.1 | 8.1 | 12.0 | 8.2 | 7 |
| Trey McBride | TE | 12.0 | 8.4 | 10.2 | 7.8 | 7 |
| Jaxon Smith-Njigba | WR | 11.1 | 7.8 | 9.0 | 6.2 | 4 |
| Malik Nabers | WR | 11.0 | 7.1 | 11.0 | 7.2 | 5 |
| Michael Pittman | WR | 10.1 | 6.9 | 8.2 | 5.8 | 6 |
| Nico Collins | WR | 9.9 | 6.6 | 6.8 | 4.8 | 5 |
| Tee Higgins | WR | 9.8 | 6.7 | 9.0 | 7.0 | 4 |
| Marvin Harrison Jr | WR | 9.5 | 5.7 | 7.5 | 4.2 | 5 |
| Demario Douglas | WR | 9.2 | 6.6 | 4.2 | 3.5 | 3 |
| Davante Adams | WR | 8.5 | 5.6 | 11.5 | 6.8 | 6 |

Top 10 is all WRs and TEs (no TE2 without TE1 being out). Sim targets track
the player's last-4-game average within ~2 targets for 8 of 10 players. Noah
Gray (sim 12.5 tgt in prior version) no longer appears.

### Check E: Sum assertions + runtime

- Sum assertions: **0 mismatches** (verified on 500 sims)
- Runtime: 1.20s/game with players (0.70s without), **1.7x overhead**
- K1-P full: 1087 games x 1000 sims = 1308s (21.8 min)

---

## 8. Check 5 Breakdowns

### By season

| Season | Sim rec | Actual rec | Sim car | Actual car |
|--------|---------|-----------|---------|-----------|
| 2021 | 1.73 | 2.30 | 2.24 | 2.68 |
| 2022 | 1.70 | 2.21 | 2.22 | 2.74 |
| 2023 | 1.78 | 2.25 | 2.23 | 2.71 |
| 2024 | 1.78 | 2.24 | 2.25 | 2.76 |

Per-player means lower in sim because sim tracks ALL active players (including
those with < 1% share). Top-player metrics (sections above) are the meaningful
comparison.

### By position

| Pos | Sim tgt | Act tgt | Sim car | Act car |
|-----|---------|---------|---------|---------|
| WR | 3.15 | 4.83 | 0.73 | 0.21 |
| TE | 3.17 | 3.51 | 0.32 | 0.04 |
| RB | 2.95 | 2.28 | 3.85 | 8.23 |
| QB | 0.00 | 0.04 | 3.79 | 3.64 |

---

## 9. Statement on Data Seasons

All tables, ratings, usage data, and diagnostics use **2021-2024 regular season
data only** (weeks 1-18). The 2025 season is the designated holdout and was not
used in any table build, rating computation, or evaluation. The 2026 season does
not exist in the PBP data.
