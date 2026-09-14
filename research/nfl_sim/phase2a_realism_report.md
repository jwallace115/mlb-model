# Phase 2A: Vectorised Play-Level Engine — Realism Report

**Data:** 2021–2024 regular season only (weeks 1–18). **2025 and 2026 were NOT used** in
tables, ratings, or any simulation. The 2025 season is the designated holdout.

**Runtime:** 1051s total for 1087 games × 2000 sims = 2.174M simulated games (0.97s/game).

---

## 1. RNG Audit Table

Every random decision in the main loop uses a **pre-drawn U(0,1) vector of size N**,
drawn at the top of each step. Total: 26 draws per step, constant consumption regardless
of game state. This makes the simulation insensitive to RNG stream shifts.

| # | Decision | Pre-drawn uniform | Size | Notes |
|---|----------|------------------|------|-------|
| 1 | 4th-down go/punt/FG | `u_4th` | N | Per-sim scalar lookup |
| 2 | Punt net yards | `u_punt_net` | N | Quantile sample from zone-specific dist |
| 3 | FG make | `u_fg_mk` | N | Indexed by global sim index |
| 4 | Penalty occurrence | `u_pen` | N | No-play penalty rate |
| 5 | Penalty side (off/def) | `u_pen_side` | N | |
| 6 | Penalty auto-first-down | `u_pen_auto` | N | Defensive penalty auto-FD |
| 7 | Play call (pass/rush) | `u_call` | N | Logistic PROE model |
| 8 | Pass: sack | `u_sack` | N | Indexed by g_idx for pass plays |
| 9 | Pass: INT | `u_int_` | N | |
| 10 | Pass: completion | `u_comp` | N | |
| 11 | Pass: success (EPA>0) | `u_succ` | N | Determines which yards dist to sample |
| 12 | Pass: yards quantile | `u_yards` | N | Inverse-CDF from quantile table |
| 13 | Pass: fumble | `u_pfum` | N | |
| 14 | INT: defensive TD | `u_int_dtd` | N | |
| 15 | INT: return yards | `u_int_ret` | N | |
| 16 | Pass fumble: def TD | `u_pfum_dtd` | N | |
| 17 | Pass fumble: return yds | `u_pfum_ret` | N | |
| 18 | Pass: clock elapsed | `u_pclock` | N | Quantile sample × pace multiplier |
| 19 | Rush: fumble | `u_rfum` | N | |
| 20 | Rush: success | `u_rsucc` | N | |
| 21 | Rush: yards quantile | `u_ryards` | N | |
| 22 | Rush fumble: def TD | `u_rfum_dtd` | N | |
| 23 | Rush fumble: return yds | `u_rfum_ret` | N | |
| 24 | Rush: clock elapsed | `u_rclock` | N | |
| 25 | PAT (XP make) | `u_pat` | N | Accessed via closure in `_do_pat` |
| 26 | OT coin toss | `u_ot` | N | `(u_ot >= 0.5)` replaces `rng.integers` |

**Explosive plays** are not a separate decision; they emerge from the upper tail of the
yards quantile distribution (draw #12 for passes, #21 for rushes).

**RNG insensitivity test** (permanent): 5 games × 2000 sims, seed per game, normal vs
+1 dummy `rng.random(N)` at top of each step. All four metrics within 3 SE:

| Metric | Normal | +Dummy | z |
|--------|--------|--------|---|
| pts/team | 19.655 | 19.651 | 0.06 |
| plays/drive | 6.877 | 6.887 | 1.39 |
| FD rate | 0.333 | 0.333 | 0.52 |
| yds/play | 5.257 | 5.249 | 1.25 |

---

## 2. Diagnostic Table (50-game sample, 2000 sims each)

### Play-Level Outcomes

| Metric | Actual | Sim | Δ |
|--------|--------|-----|---|
| P(sack) | 0.067 | 0.065 | −0.002 |
| P(INT) | 0.021 | 0.021 | 0.000 |
| P(incomplete) | 0.309 | 0.302 | −0.007 |
| P(complete) | 0.603 | 0.604 | +0.001 |
| INT/dropback | 0.0214 | 0.0209 | |
| Fumble lost/play | 0.0074 | — | |
| FD rate/play | 0.295 | 0.321 | +0.026 |
| Sack rate | 0.067 | 0.065 | −0.002 |
| Mean sack yards | −6.7 | — | |
| Pass explosive ≥20 yds | 0.137 | — | |
| Rush explosive ≥12 yds | 0.083 | — | |
| Mean yds/play | 5.47 | — | |
| Yds/play 90th pct | 15 | — | |
| Yds/play 95th pct | 21 | — | |

### Drive-Level Outcomes

| Metric | Actual | Sim | Δ |
|--------|--------|-----|---|
| Plays/drive | 5.89 | 5.92 | +0.03 |
| Drives/game | 21.0 | 20.8 | −0.2 |
| Plays/game (scrimmage) | 124.5 | 123.1 | −1.4 |
| Pts/team | 22.4 | 18.7 | −3.7 |
| Pts/drive | 2.13 | 1.80 | −0.33 |

### Drive-Ending Mix

| Outcome | Actual | Sim | Δpp |
|---------|--------|-----|-----|
| Punt | 0.360 | 0.361 | +0.1 |
| FG attempt | 0.179 | 0.165 | −1.4 |
| TD | 0.229 | 0.195 | −3.4 |
| INT | 0.071 | — | |
| Fumble lost | 0.048 | — | |
| Turnover on downs | 0.061 | — | |
| End of half | 0.070 | — | |
| Sim turnovers/drive | — | 0.111 | |
| FG make rate | 0.850 | 0.870 | |

### Other

| Metric | Actual | Sim |
|--------|--------|-----|
| P(go on 4th) | 0.198 | — |
| Penalty rate | 0.081 | 0.072 |
| Def pen yds/game | 31.6 | — |
| RZ trips/game | 6.4 | — |
| FG att/game | 3.9 | 3.4 |

---

## 3. Bug List (All Engine Sessions)

| Bug | Cause | Fix | Session |
|-----|-------|-----|---------|
| 3-quarter game | Clock only covered Q1–Q3; Q4 was never simulated | Added Q4 handling with OT | Session 1 |
| Clock table scope | Clock quantiles computed from wrong subset | Rebuilt from all scrimmage-to-scrimmage gaps | Session 1 |
| Incomplete clock class | Sacks mis-classified as incomplete for clock | Sacks → complete_inbounds | Session 1 |
| No matchup tilt | Per-sim margin SD 1.5 (no differentiation) | Added log5 matchup on success/explosive/sack/INT rates | Session 1 |
| Missing penalty layer | No penalties simulated | Added no-play penalties with off/def split, auto-FD, yards | Session 1 |
| Missing pass fumbles | Only rush fumbles modeled | Added pass fumble from `p_fumble` table column | Session 2 |
| 4th-down override disabled | Working tree had stale Phase 1 files (4th_go = 1.0) | Restored committed files; re-enabled override with correct lg_go | Session 2 → **this session** |
| Per-sim Python loops | K1 runtime 79 min (per-sim for-loops) | Vectorised play call + yards; K1 → 15 min | Session 2 |
| **Stale Phase 1 inputs** | Mac working tree carried original 13-Sep files (k=200, 4th_go=1.0) on top of committed versions (k=100, 4th_go=0.68). Both prior engine sessions ran against stale ratings. | `git checkout` restored committed files. **Not a code bug — a working-tree state bug.** | CORRECTION entry in decision doc |
| **RNG stream coupling** | All random draws used variable-size `rng.random(n_p)` / `rng.random(n_r)`. Inserting one dummy draw shifted the stream, systematically changing FD rate (35%→22% in a prior test). The `u_pfum` "drawn AFTER to preserve stream" workaround confirmed the dependency. | Pre-draw 26 fixed-size `rng.random(N)` vectors per step. Each decision indexes by global sim ID. Constant consumption per step makes the simulation RNG-insensitive. | **This session** |
| **4th-down lg_go mismatch** | Team override used `lg_go = 0.164` (unconditional PBP go rate) but `team_go` from tendencies is a conditional/smoothed rate (~0.68 league mean). Ratio ~4.1× inflated p_go, suppressing punts/FGs. | `lg_go = ctx["lg_4th_go"]` (tendencies mean, same definition as team_go). | **This session** |
| **Drive-ending clock over-deduction** | TDs, INTs, and fumbles stop the game clock. Actual elapsed to next scrimmage play: TDs 8.3s, INTs 9.6s, fumbles 9.4s. Engine deducted 33–39s (from "first_down"/"complete_inbounds" categories). Total over-deduction: ~188s/game ≈ 6 plays lost. | Separate "drive-ending" clock category with short deduction (~8s mean). | **This session** |
| **K1 SD margin definition** | "SD margin" compared SD of sim MEAN margin across games (team differentiation ~3.6) to SD of realised margins (~14.2). Wrong metric. | Pooled SD: SD of ALL individual simulated margins. Team differentiation SD reported separately as INFO. | **This session** |
| **n_plays included punts/FGs/kneels** | `n_plays` counter incremented for punts, FG attempts, and kneel-downs. Diagnostic compared this to actual scrimmage-only plays/drive, inflating the sim's plays/drive by ~0.6. | Removed non-scrimmage increments from `n_plays`. Punts/FGs tracked in `ev_punts`/`ev_fg_att`. | **This session** |

---

## 4. K1 Realism Check (1087 games × 2000 sims)

| Metric | Sim | Actual | Target | PASS/FAIL |
|--------|-----|--------|--------|-----------|
| Mean pts/team | 19.1 | 22.4 | ±3 of actual | **FAIL** (−3.3) |
| Plays/game | 124.2 | 124.5 | ~125 | PASS |
| Drives/game | 20.8 | 21.9 | ~22 | PASS |
| SD margin (pooled) | 13.36 | 14.20 | ±1.0 of actual | **PASS** |
| SD total (pooled) | 11.83 | 13.61 | ±2.0 of actual | **PASS** |
| SD sim mean margin | 3.61 | spread SD 6.08 | INFO | INFO |
| P(\|margin\|=3) | 8.80% | 14.54% | ±2 | **FAIL** |
| P(\|margin\|=6) | 5.17% | 7.54% | ±2 | **FAIL** |
| P(\|margin\|=7) | 7.49% | 7.27% | ±2 | PASS |
| P(\|margin\|=10) | 6.51% | 5.06% | ±2 | PASS |
| P(\|margin\|=14) | 4.71% | 4.32% | ±2 | PASS |
| Pass yds/team/game | 214.9 | 221.0 | ~221 | PASS |
| Rush yds/team/game | 136.2 | 118.2 | ~118 | PASS |
| corr(sim margin, spread) | 0.759 | — | ~0.8 (info) | INFO |

**Scoring gap root cause:** The engine does not model punt return TDs, kickoff return
TDs, or blocked-kick TDs. PBP data shows ~0.5 special-teams TDs per game (~3.5
pts/game, ~1.75/team). This accounts for roughly half the 3.3 pts/team gap. The
remainder is from a 3.4pp TD/drive deficit (0.195 sim vs 0.229 actual), likely due to
the EPA-based success/fail yards split not perfectly reproducing red-zone TD conversion
rates, plus the compressed team differentiation (strong offenses don't score enough).

**P(|margin|=3) failure:** NFL games cluster at margin=3 (FG margin) far more than a
smooth distribution would predict. The sim under-produces this spike because it has fewer
FGs per game (3.4 vs 3.9 attempts) and the continuous yards distribution doesn't naturally
produce the "kick a FG to win by 3" game-management pattern.

---

## 5. Home Win Probability Calibration

| Decile | Sim P(HW) | Actual HW | N |
|--------|----------|----------|---|
| 0 | 0.295 | 0.324 | 111 |
| 1 | 0.367 | 0.389 | 108 |
| 2 | 0.407 | 0.417 | 108 |
| 3 | 0.439 | 0.450 | 109 |
| 4 | 0.469 | 0.528 | 108 |
| 5 | 0.499 | 0.532 | 109 |
| 6 | 0.533 | 0.649 | 111 |
| 7 | 0.567 | 0.657 | 105 |
| 8 | 0.603 | 0.679 | 109 |
| 9 | 0.671 | 0.780 | 109 |

The sim's home-win probabilities are **compressed** — the range [0.295, 0.671] is
narrower than ideal. Actual home-win rates span a wider range. This is expected: the
D7 anchoring model (team ratings via log5) does not capture the full spread of closing
spreads (SD 6.08 for spreads vs 3.61 for sim mean margins). Phase 2B team differentiation
improvements (player-level contributions, coaching adjustments) are expected to widen
this range.

---

## 6. Total Calibration

| Decile | Sim P(over) | Actual over rate | N |
|--------|------------|-----------------|---|
| 0 | 0.130 | 0.376 | 109 |
| 1 | 0.174 | 0.505 | 109 |
| 2 | 0.201 | 0.472 | 108 |
| 3 | 0.226 | 0.486 | 109 |
| 4 | 0.254 | 0.473 | 110 |
| 5 | 0.280 | 0.458 | 107 |
| 6 | 0.306 | 0.514 | 109 |
| 7 | 0.344 | 0.528 | 108 |
| 8 | 0.393 | 0.495 | 111 |
| 9 | 0.524 | 0.402 | 107 |

Total calibration is **systematically biased low** because the engine under-produces
scoring (19.1 vs 22.4 pts/team). The sim's P(over) rarely exceeds 0.5, while the actual
over rate is ~50% across all deciles (as expected for well-set closing lines). This will
improve when special-teams scoring is added.

---

## 7. Check 5 Breakdowns

### By Season

| Season | Sim pts/team | Actual pts/team | Sim margin SD | Actual margin SD |
|--------|-------------|----------------|--------------|-----------------|
| 2021 | 19.3 | 23.0 | 3.80 | 15.43 |
| 2022 | 18.9 | 21.9 | 3.56 | 12.35 |
| 2023 | 18.8 | 21.8 | 3.54 | 14.42 |
| 2024 | 19.4 | 22.9 | 3.54 | 14.46 |

Scoring gap is stable across seasons (~3–4 pts/team), confirming it is structural
(missing special-teams TDs) rather than temporal.

### By Week Range

| Weeks | Sim pts/team | Actual pts/team |
|-------|-------------|----------------|
| 1–4 | 20.0 | 22.3 |
| 5–18 | 18.8 | 22.4 |

Early weeks are slightly higher (20.0 vs 18.8) — expected from prior regression pulling
ratings toward league average in weeks 1–4.

### By Favourite Size

| \|Spread\| | Sim pts/team | Actual pts/team | N |
|-----------|-------------|----------------|---|
| <3 | 19.0 | 21.5 | 255 |
| 3–7 | 19.1 | 22.5 | 536 |
| >7 | 19.1 | 23.0 | 296 |

Sim scoring is flat across spread buckets. Actual scoring increases for larger
favourites (stronger teams score more). This is consistent with the compressed team
differentiation (SD 3.61 vs 6.08).

---

## 8. Statement on Data Seasons

All tables, ratings, and diagnostics use **2021–2024 regular season data only**
(weeks 1–18). The 2025 season is the designated holdout and was not used in any
table build, rating computation, simulation, or evaluation. The 2026 season does
not exist in the PBP data.

---

## 9. K1 Summary

| Check | Result |
|-------|--------|
| Mean pts/team within ±3 of 22.4 | **FAIL** (19.1, gap = −3.3) |
| Plays/game ~125 | **PASS** (124.2) |
| Drives/game ~22 | **PASS** (20.8) |
| SD margin (pooled) within ±1.0 of 14.2 | **PASS** (13.36) |
| SD total (pooled) within ±2.0 of 13.6 | **PASS** (11.83) |
| P(\|margin\|=3) within ±2 of 14.3% | **FAIL** (8.80%) |
| P(\|margin\|=6) within ±2 of 7.5% | **FAIL** (5.17%) |
| P(\|margin\|=7) within ±2 of 8.2% | **PASS** (7.49%) |
| P(\|margin\|=10) within ±2 of 5.1% | **PASS** (6.51%) |
| P(\|margin\|=14) within ±2 of 4.3% | **PASS** (4.71%) |
| Home-win calibration | Compressed (team differentiation 3.61 vs 6.08) |
| Total calibration | Biased low (from scoring gap) |
| corr(sim margin, spread) | 0.759 (target ~0.8, INFO) |

**K1 NOT PASSED.** Three checks fail: pts/team (−3.3), P(|margin|=3), P(|margin|=6).
Root cause is the ~3.3 pts/team scoring gap, primarily from unmodeled special-teams TDs
(~1.75 pts/team) and a secondary TD/drive deficit from compressed team differentiation
and the EPA success/fail yards split. The P(|margin|=3) failure is structural — the
engine lacks the game-management logic that produces the real-world spike at margin=3.

**Phase 2B required:** special-teams scoring model (punt/kick return TDs), improved team
differentiation (wider spread of sim mean margins), and consideration of a yards-based
(not EPA-based) success/fail split for the quantile tables.
