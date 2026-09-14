# Phase 5A: Engine Repair

**Date:** 2026-09-15
**Engine file:** `nfl/sim/engine.py` (pre-5A tag: `pre-5a-engine`)

---

## FIX 1 -- Termination

**What was wrong:** `max_steps=500` with batch-wide `continue` statements left ~36% of sims
unfinished. Two `continue` paths (line 868: time_up handling; line 891: kneeling) skipped
ALL sims when ANY sim hit those conditions, burning play-steps for sims that could still
play. This caused games to reach the step cap with clock remaining.

**Evidence:** Cowork audit measured 1,095/3,000 unfinished sims and 82 ties without OT
in the MNF sample.

**What changed:**
- Removed both batch-wide `continue` statements
- Time-up handling now falls through to play execution; non-time-up sims play normally
- Kneeling sims excluded from the playing set via mask, not via continue
- Safety cap raised to 800 and hitting it raises `RuntimeError` (not a silent return)
- Added `game_over` and `clock_remaining` columns to `team_df`

**Test T1:** 5 games x 3 seeds x N=2,000, players on and off: all `game_over` True;
`clock_remaining == 0` for all non-OT sims; zero ties without OT; overall tie rate 0.90%.
Runtime: ~20s.

---

## FIX 2 -- Reproducible Seeds

**What was wrong:** Seeds derived from `hash((game_id, 42)) % (2**31)`. Python's `hash()`
is salted since 3.3 and differs across processes.

**What changed:** Created `nfl/sim/seed_util.py` with `stable_seed()` using `zlib.crc32`
of the canonical `repr()`. Replaced all 7 call sites: engine.py, diagnostics.py, anchor.py,
calibration.py, run_calibration.py, run_cal_players.py, run_week.py.

**Test T2:** Same game/seed in two separate subprocesses: all columns byte-identical.
Runtime: ~5s.

---

## FIX 3 -- No Future Information in Engine Context

**What was wrong:** `lg_pace = tend["pace_sec"].mean()` and `lg_4th_go =
tend["fourth_down_go_rate"].mean()` averaged over ALL rows in the tendencies frame,
including future seasons/weeks.

**Audit of all `ctx[...]` assignments:**
- `lb` (league baselines): uses `season - 1` -- PIT by construction
- Team ratings (`t{i}_pass_success`, `t{i}_sack_rate`, etc.): lookup by exact
  `(team, season, week)` -- PIT by construction in ratings.py
- Team tendencies (`t{i}_proe`, `t{i}_pace`, `t{i}_4th_go`): lookup by exact
  `(team, season, week)` -- PIT
- Situational PROE: same PIT lookup
- Kicker: same PIT lookup
- **`lg_pace`**: averaged over ALL tend rows -- NOT PIT (FIXED)
- **`lg_4th_go`**: averaged over ALL tend rows -- NOT PIT (FIXED)

**What changed:** Filtered `tend` to `(season == s-1) OR (season == s AND week < w)` before
computing the league averages.

**Test T3:** Context built with full frames vs truncated-tend frames: `lg_pace` and
`lg_4th_go` identical; all team ratings identical (team_r not truncated).

---

## FIX 4 -- Player Layer Allocation-Only

**What was wrong:** Two outcome-shaping paths in the player layer:
1. Completion probability tilted by player catch_rate via logit-additive shift
   (lines 1278-1284): changed the binary completion decision
2. Depth-split pass yards tables (lines 1427-1440): changed the yards drawn for
   completions based on receiver aDOT

Same game, same seed: total 31.0 without players vs 41.5 with (10 pts difference).

**What changed (D19):** Removed both paths. Completion uses team-level `tbl_comp` in
both modes. Yards drawn from pooled `pa_yds_succ`/`pa_yds_fail` in both modes. Player
attributes (shares, aDOT, catch_rate) are used ONLY for allocation: which player caught
it, which player carried it.

**Test T4:** N=4,000, same seed/offsets: |mean margin diff| < 2*SE (PASS); |mean total
diff| < 2*SE (PASS); KS test home/away scores p > 0.05 (PASS).

---

## FIX 5 -- Situational Tendency Keys

**What was wrong (Bug 14, already fixed in Phase 2A):** Engine built keys as "1.0_short_..."
but table had "1_short_...". The entire play-call table was dead code for all prior iterations.
Bug 14 was fixed in Phase 2A iteration 6.

**What changed in 5A:** Added a fallback counter to the engine to track how often the
level-0 (finest) bucket misses and falls back to coarser levels. Added the counter as
`team_df.attrs["playcall_fallback_count"]`.

**Test T5:** Fallback rate < 2% of total plays (actual: 0.75%). All table keys have integer
down format (no "1.0" style). Remaining fallbacks are from genuinely thin table cells
(4th-down with rare score states, <20 observations in 2021-2024 data).

---

## FIX 6 -- Rules

### 6a: PAT Decision from 2pt Table
**Was:** Always XP. **Fixed:** Reads `twopt_decision.parquet` for P(2pt) by (quarter, score
state). 2pt conversion from `twopt_conv_rate` scalar. Q4 trailing: ~34% attempt rate.

### 6b: Overtime by Season and Season Type
**Was:** Any OT TD ends game (pre-2025 rule only); no postseason handling; ties always allowed.
**Fixed:** Added `season_type` parameter ("REG"/"POST"). Pre-2025 REG: first-possession TD
ends game. 2025+ REG and POST: both teams possess regardless of first result, then sudden death.
POST: no ties; additional 10-minute periods until resolved. Matching FGs in postseason OT
reset possession tracking for another round.

### 6c: Opening Possession Random
**Was:** Away team always receives (`poss = np.ones(N)`). **Fixed:** Coin flip per sim
(`u_coin >= 0.5`). Second-half kickoff to the team that did NOT receive opening.

### 6d: Kickoff Start Position from Table
**Was:** Hardcoded `yl = 75`. **Fixed:** Reads from `kickoff.parquet` per season. Currently
75 for all seasons (table placeholder), but the engine now uses the table value.

### 6e: Negative Yards in Stat Accumulation
**Was:** `np.maximum(nc_yds, 0)` clipped negative yards to 0 in pass_yds and rush_yds.
**Fixed:** Removed clip; negative yards (sacks, losses) reduce team yard totals.

### 6f: Punt Touchback Branch
**Was:** `if new_yl < 1: new_yl = 80` was unreachable (preceded by `np.clip(..., 1, 99)`).
**Removed:** Dead code deleted. Touchbacks are already encoded in the punt net yards
distribution from `tables.py`.

**Test T6:** Postseason 2023 at N=2,000: 0 ties (PASS). Score variety > 15 unique values
(2pt working). No ties without OT flag.

---

## FIX 7 -- Offset-Response Continuity

**What was wrong:** Mean margin was a staircase in the anchoring offset, with 2-6 pt jumps
at N=4,000. Root cause: the EPA shift adds a CONSTANT to every play's yards. When this
constant crosses a half-integer boundary, many plays simultaneously round to the next
integer, causing a discrete jump in first-down rate and scoring.

**What changed:** Two fixes:
1. **Float game state (yl, dist, yards):** Changed yardline and distance-to-go from int16
   to float32. Yard gains stored as floats with no rounding. First-down checks, TD checks,
   and field-position updates all use float arithmetic. Player stats use `round()` for
   integer counting only.
2. **Stochastic rounding of EPA shift:** Instead of adding the same constant shift to every
   play, each play gets `floor(shift)` or `ceil(shift)` with `P(ceil) = fractional part`.
   Added dedicated `u_epa_pass` and `u_epa_rush` uniform draws per step for the dithering.
   E[shift_per_play] = shift exactly; plays cross rounding boundaries at different offset
   values, preventing synchronised jumps.

**Pre-fix sweep:** max adjacent jump = 4.43 (staircase with 5 plateaus).
**Post-fix sweep:** max adjacent jump = 0.55, zero reversals > 0.3, monotone non-decreasing.

**Test T7:** Sweep -1.0 to +1.0 in 0.05 steps, N=4,000: max |delta margin| = 0.55 <= 0.75
(PASS). Monotone with 0 reversals > 0.3 (PASS).

---

## T7 Sweep Table (post-fix)

| dh | margin | total | delta_m |
|------|--------|-------|---------|
| -1.00 | -1.28 | 32.2 | +0.000 |
| -0.95 | -0.96 | 32.3 | +0.321 |
| -0.90 | -0.58 | 32.6 | +0.383 |
| -0.85 | -0.25 | 32.7 | +0.325 |
| -0.80 | +0.06 | 33.0 | +0.310 |
| -0.75 | +0.14 | 33.2 | +0.083 |
| -0.70 | +0.48 | 33.4 | +0.336 |
| -0.65 | +0.82 | 33.6 | +0.343 |
| -0.60 | +1.25 | 33.8 | +0.428 |
| -0.55 | +1.55 | 34.1 | +0.304 |
| -0.50 | +1.86 | 34.5 | +0.305 |
| -0.45 | +2.15 | 34.8 | +0.298 |
| -0.40 | +2.62 | 34.9 | +0.462 |
| -0.35 | +3.16 | 35.2 | +0.546 |
| -0.30 | +3.56 | 35.5 | +0.394 |
| -0.25 | +4.01 | 35.7 | +0.451 |
| -0.20 | +4.37 | 36.1 | +0.359 |
| -0.15 | +4.77 | 36.4 | +0.399 |
| -0.10 | +5.15 | 36.5 | +0.381 |
| -0.05 | +5.63 | 36.9 | +0.480 |
| +0.00 | +5.98 | 37.1 | +0.352 |
| +0.05 | +6.06 | 37.3 | +0.077 |
| +0.10 | +6.36 | 37.8 | +0.302 |
| +0.15 | +6.74 | 38.1 | +0.380 |
| +0.20 | +7.21 | 38.5 | +0.476 |
| +0.25 | +7.56 | 38.6 | +0.348 |
| +0.30 | +8.02 | 39.0 | +0.459 |
| +0.35 | +8.47 | 39.2 | +0.450 |
| +0.40 | +8.87 | 39.6 | +0.398 |
| +0.45 | +9.13 | 39.8 | +0.257 |
| +0.50 | +9.67 | 40.1 | +0.543 |
| +0.55 | +10.02 | 40.5 | +0.348 |
| +0.60 | +10.38 | 40.4 | +0.360 |
| +0.65 | +10.64 | 40.8 | +0.259 |
| +0.70 | +10.97 | 41.1 | +0.334 |
| +0.75 | +11.21 | 41.5 | +0.239 |
| +0.80 | +11.60 | 41.7 | +0.390 |
| +0.85 | +11.88 | 42.0 | +0.287 |
| +0.90 | +12.38 | 42.3 | +0.497 |
| +0.95 | +12.89 | 42.6 | +0.508 |
| +1.00 | +13.15 | 42.9 | +0.256 |

Max |delta_m|: 0.546. Reversals > 0.3: 0.

---

## K1 Realism Check (Step 8, post-5A)

**Config:** N=500, 1,087 games, 2021-2024 regular season. Players OFF.
**Runtime:** 482s (0.44s/game).

### K1 Table (5A vs D15)

| Metric | 5A | D15 | Actual | PASS? |
|--------|-----|-----|--------|-------|
| Mean pts/team | 18.9 | 19.5 | 22.4 | FAIL |
| Plays/game | 125.9 | 125.9 | 124.5 | PASS |
| Drives/game | 21.2 | 21.4 | 21.9 | PASS |
| SD margin (pooled) | 14.13 | 14.06 | 14.20 | PASS |
| SD total (pooled) | 12.17 | 12.30 | 13.61 | PASS |
| P(|margin|=3) | 7.86% | 8.45% | 14.54% | FAIL |
| P(|margin|=6) | 5.14% | 5.07% | 7.54% | FAIL |
| P(|margin|=7) | 6.79% | 7.59% | 7.27% | PASS |
| P(|margin|=10) | 5.57% | 6.20% | 5.06% | PASS |
| P(|margin|=14) | 4.09% | 4.57% | 4.32% | PASS |
| Pass yds/team | 222.8 | 227.5 | 221.0 | PASS |
| Rush yds/team | 116.8 | 123.9 | 118.2 | PASS |
| corr(sim, spread) | 0.800 | 0.769 | - | INFO |
| Tie rate | 0.90% | - | ~0.4% | PASS (<=1%) |
| OT rate | 3.25% | - | ~3% | PASS |

**Same 3 lines fail as D15:** pts/team (-3.5, was -2.9), P(|m|=3) (-6.7pp), P(|m|=6) (-2.4pp).
The pts/team deficit is slightly larger (18.9 vs 19.5) due to FIX 6e (negative yards no longer
clipped) and FIX 4 (player catch_rate tilt removed). Key-number mass still under-generated.
These are downstream of the league-level calibration issue identified in D15; D7 anchoring
corrects the mean.

**New pass lines:** Pass yds/team improved to 222.8 (from 227.5), closer to actual 221.0.
This is from FIX 6e (sack/loss yards now properly reduce pass yds) and FIX 4 (no depth-table
yard shaping). Rush yds improved to 116.8 (from 123.9), closer to actual 118.2.

**New line passing:** corr(sim, spread) improved to 0.800 (from 0.769). SD margin pooled
maintained at 14.13 (was 14.06, actual 14.20). Tie rate 0.90% <= 1% gate.

---

## Runtimes

| Step | Runtime |
|------|---------|
| T1 (5 games x 3 seeds x N=2k, on/off) | ~20s |
| T2 (subprocess reproducibility) | ~5s |
| T7 (41-point sweep, N=4k) | ~92s |
| K1 backtest (1087 games x N=500) | 482s (8.0 min) |
| Full test suite (22 tests) | 159s (2.7 min) |
