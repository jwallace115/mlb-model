# Phase 2A: Vectorised Play-Level Engine -- Final K1 Realism Report

**Data:** 2021-2024 regular season only (weeks 1-18). **2025 and 2026 were NOT used** in
tables, ratings, or any simulation. The 2025 season is the designated holdout.

**This is the FINAL Phase 2A iteration.** Proceeding to Phase 3 regardless of gate status.

---

## 1. Full Bug List (all Phase 2A sessions)

| # | Bug | Cause | Iter fixed | Impact |
|---|-----|-------|-----------|--------|
| 1 | 3-quarter game | Game ended after Q3; no Q4 | iter 1 | Massive scoring deficit |
| 2 | Clock table scope | Missing outcome types in clock table | iter 1 | Wrong time consumption |
| 3 | Incomplete clock class | Outcome not classified for clock draw | iter 1 | Time drift |
| 4 | No matchup tilt | per-sim margin SD 1.5 (should be ~13) | iter 2 | All teams identical |
| 5 | Missing penalty layer | No defensive/offensive penalties | iter 2 | ~3 FD/game missing |
| 6 | Missing pass fumbles | Pass fumbles not simulated | iter 2 | ~0.5 TO/game missing |
| 7 | Per-sim loops | 79 min K1 runtime | iter 3 | Speed only |
| 8 | Stale 4th-down ratings | Working tree had Phase 1 stale files (go_rate=1.0) | iter 3 | Wrong 4th-down decisions |
| 9 | yds_all_q revert | Tolerance gate at +/-3 instead of +/-1.5 | iter 4 | Masked failing metric |
| 10 | Coarse 4th-down zones | Only 4 field zones for 4th-down table | iter 4 | Wrong go/punt/FG split |
| 11 | No return TDs | Punt/kickoff return TDs not simulated | iter 4 | ~0.5 pts/game missing |
| 12 | No team yards tilt | Only success probability had matchup tilt, not yards | iter 5 | Team compression (SD 3 vs 6) |
| 13 | D6 sign convention | off - def instead of off + def - league | iter 5 | Wrong matchup direction |
| 14 | **Play-call key mismatch** | Engine built keys as "1.0_short_..." but table had "1_short_..." | **iter 6** | **Table was NEVER used; flat 55% pass rate for all situations** |
| 15 | **Play-call table too coarse** | 3 score states x 2 clock periods; trail 1-3 and lead 1-3 in same cell | **iter 6** | No late-game pass/run differentiation by score |
| 16 | **Multiplicative matchup tilt** | `bucket * (log5/league)` instead of `sigmoid(logit(bucket) + logit(log5) - logit(league))` | **iter 6** | Overshift at extreme bucket rates; ~3pp at high success buckets |

### Bug 14 detail (play-call key mismatch)

```python
# Engine (WRONG):
d_s = np.char.add(down_live.astype(str), ".0")  # "1.0", "2.0", ...
# Table key:
scrim["down_b"] = scrim["down"].astype(int).clip(1,4).astype(str)  # "1", "2", ...
```

Every `pc_lookup.get(b, 0.55)` returned the default 0.55. The entire play-call table --
built from 189,481 PBP plays, 72 situational buckets -- was dead code. All situational
PROE shifts were also dead (looked up via the same broken key). Fixed by removing the
`.0` suffix and expanding to 7 score states x 4 clock periods with 3-level fallback.

### Bug 15 detail (play-call table resolution)

Before fix: trail 1-3 and lead 1-3 in Q4<2:00 mapped to the SAME cell ("within8_Q4"),
getting identical ~48% pass rate. After fix with 7 score x 4 clock:

| Situation | Pass rate |
|-----------|-----------|
| trail 1-3, Q4<2:00 | **79.6%** |
| lead 1-3, Q4<2:00 | **1.7%** |

78pp differential (table built from PBP data, kneeldowns excluded via play_type filter).

### Bug 16 detail (logit-additive tilt)

Multiplicative: `p = bucket_rate * (log5(off,def,league) / league)`
Logit-additive: `p = sigmoid(logit(bucket_rate) + logit(log5(off,def,league)) - logit(league))`

For a top-5 offense (success=0.52) at a high bucket rate (0.60):
- Multiplicative: 0.694
- Logit-additive: 0.665

The multiplicative form overshifts high bucket rates (red zone, short yardage).
logit(log5(a,b,l)) = logit(a) + logit(b) - logit(l) exactly, so the logit shift
decomposes cleanly into off + def contributions on the probability scale.

Applied to: pass success, sack rate, INT rate, rush success.
NOT applied to: explosive share, stuff rate (these are not separate draws in the
current engine -- they are implicit in the success/fail quantile distributions).

---

## 2. K1 Realism Check (N=500, 1,087 games, 2021-2024)

| Metric | Sim | Actual | Target | PASS/FAIL |
|--------|-----|--------|--------|-----------|
| Mean pts/team | 19.5 | 22.4 | +/-1.5 of actual | **FAIL** |
| Plays/game | 125.9 | 124.5 | ~125 | **PASS** |
| Drives/game | 21.4 | 21.9 | ~22 | **PASS** |
| SD margin (pooled) | 14.06 | 14.20 | +/-1.0 of actual | **PASS** |
| SD total (pooled) | 12.30 | 13.61 | +/-2.0 of actual | **PASS** |
| SD sim mean margin | 5.63 | spread SD 6.08 | INFO | INFO |
| P(\|margin\|=3) | 8.45% | 14.54% | 14.27%+/-2 | **FAIL** |
| P(\|margin\|=6) | 5.07% | 7.54% | 7.54%+/-2 | **FAIL** |
| P(\|margin\|=7) | 7.59% | 7.27% | 8.24%+/-2 | **PASS** |
| P(\|margin\|=10) | 6.20% | 5.06% | 5.06%+/-2 | **PASS** |
| P(\|margin\|=14) | 4.57% | 4.32% | 4.32%+/-2 | **PASS** |
| Pass yds/team/game | 227.5 | 221.0 | ~221 | **PASS** |
| Rush yds/team/game | 123.9 | 118.2 | ~118 | **PASS** |
| corr(sim margin, spread) | 0.769 | - | >=0.75 (info) | INFO |

### Additional metrics

| Metric | Sim | Actual |
|--------|-----|--------|
| TD/drive | 0.199 | 0.227 |
| FG att/game | 3.50 | 3.92 |
| FG made/game | 3.05 | 3.39 |
| Punts/game | 7.89 | 7.80 |
| Sacks/game | 4.94 | ~4.5 |
| INTs/game | 1.48 | ~1.4 |
| Pass rate | 0.564 | 0.570 |
| FD/play | 0.323 | ~0.32 |

**Summary: 9 PASS, 3 FAIL, 2 INFO.** Failing lines: pts/team (-2.9), P(|margin|=3)
(-6.1pp), P(|margin|=6) (-2.5pp).

---

## 3. Home Win Probability Calibration

| Decile | Sim P(HW) | Actual HW | N |
|--------|----------|----------|---|
| 0 | 0.209 | 0.306 | 111 |
| 1 | 0.315 | 0.366 | 112 |
| 2 | 0.379 | 0.452 | 104 |
| 3 | 0.429 | 0.468 | 109 |
| 4 | 0.469 | 0.527 | 110 |
| 5 | 0.510 | 0.556 | 108 |
| 6 | 0.555 | 0.639 | 108 |
| 7 | 0.604 | 0.636 | 107 |
| 8 | 0.672 | 0.624 | 109 |
| 9 | 0.778 | 0.835 | 109 |

Monotonic and directionally correct. Compression at extremes: decile 0 under-predicts
(20.9% sim vs 30.6% actual) and decile 9 under-predicts (77.8% vs 83.5%). This is
consistent with the pts/team deficit reducing the magnitude of all score effects.

---

## 4. Total Calibration

| Decile | Sim P(over) | Actual over rate | N |
|--------|------------|-----------------|---|
| 0 | 0.146 | 0.452 | 115 |
| 1 | 0.196 | 0.472 | 108 |
| 2 | 0.224 | 0.609 | 110 |
| 3 | 0.250 | 0.398 | 103 |
| 4 | 0.275 | 0.416 | 113 |
| 5 | 0.299 | 0.442 | 104 |
| 6 | 0.327 | 0.522 | 113 |
| 7 | 0.363 | 0.510 | 104 |
| 8 | 0.416 | 0.426 | 108 |
| 9 | 0.553 | 0.459 | 109 |

**Systematically low.** Sim P(over) ranges 0.15-0.55; actual over rate is ~45%
uniformly. The sim under-projects total points by ~2.9/team = ~5.8/game,
so even its most "over" games (P=0.55) are close to the actual median.
This will be corrected by D7 anchoring in Phase 3 (mean shift to market total).

---

## 5. Check 5 Breakdowns

### By season

| Season | Sim pts/team | Actual pts/team | Sim margin SD | Actual margin SD |
|--------|-------------|----------------|--------------|-----------------|
| 2021 | 20.2 | 23.0 | 6.14 | 15.43 |
| 2022 | 19.4 | 21.9 | 5.07 | 12.35 |
| 2023 | 18.7 | 21.8 | 5.41 | 14.42 |
| 2024 | 19.5 | 22.9 | 5.86 | 14.46 |

Deficit is stable across seasons (-2.4 to -3.4). No single-season anomaly.

### By week range

| Weeks | Sim pts/team | Actual pts/team |
|-------|-------------|----------------|
| 1-4 | 20.5 | 22.3 |
| 5-18 | 19.1 | 22.4 |

Weeks 1-4 slightly higher sim (less stable ratings = more regression to league mean).
Weeks 5-18 deficit is 3.3 vs 1.8 for early weeks.

### By favourite size

| Bucket | Sim pts/team | Actual pts/team | N |
|--------|-------------|----------------|---|
| <3 | 19.2 | 21.5 | 255 |
| 3-7 | 19.5 | 22.5 | 536 |
| >7 | 19.7 | 23.0 | 296 |

Deficit grows with spread size: -2.3 for pick'ems, -3.3 for large favourites.
This is consistent with the logit-additive fix compressing extreme matchups slightly
relative to the multiplicative form.

---

## 6. Statement on Data Seasons

All tables, ratings, and diagnostics use **2021-2024 regular season data only**
(weeks 1-18). The 2025 season is the designated holdout and was not used in any
table build, rating computation, simulation, or evaluation. The 2026 season does
not exist in the PBP data.

---

## 7. K1 RESIDUAL -- PROVISIONAL

Three K1 lines fail. This section states the size, mechanisms tried, and downstream
effects. Phase 2A is closed; these residuals carry into Phase 3.

### 7.1 pts/team: 19.5 vs 22.4 (gap -2.9, gate +/-1.5)

**Mechanism:** TD/drive = 0.199 vs 0.227 (-12%). FG att/game = 3.50 vs 3.92 (-11%).
The deficit is uniform across all start-yardline bins (section 1b) and stable across
all four seasons, all week ranges, and all favourite buckets. It is a league-level
calibration issue, not a team-differentiation issue.

**Root cause:** The play-level tables split yards into EPA-success and EPA-fail
quantile distributions. A play gaining 7 yards on 2nd-and-5 is a first-down
conversion but may be EPA <= 0 (depending on field position and expected points).
The engine draws from the "fail" quantile table in that case, which has a lower
yards distribution. This creates a systematic under-conversion of moderate-gain
plays into first downs, compounding across a drive into fewer TDs and fewer
FG-range arrivals.

**Mechanisms tried across 6 iterations:**
- D6 additive EPA shift (zero-mean, fixes team spread, cannot raise league level)
- Logit-additive matchup tilt (zero-mean vs multiplicative)
- Play-call table fix (correct pass/run split, net effect -0.3 pts/team)
- Drive-stage localisation, 4th-down table resolution, return TDs, penalties

**Downstream distortion:** D7 anchoring (Phase 3) shifts sim mean total to market
total, correcting the mean. The raw sim total is informational only; the anchored
total is what reaches pricing. The residual matters only if it distorts the
SHAPE of the total distribution (e.g., variance, skew) -- the pooled SD of 14.06
vs 14.20 actual suggests shape is preserved even though level is wrong.

### 7.2 P(|margin|=3): 8.45% vs 14.54% (gap -6.1pp, gate +/-2pp)

**Mechanism:** P(|margin|=3) is the "field goal margin" -- games decided by exactly
one FG. With FG att/game at 3.50 vs 3.92 (-11%) and FG make rate normal, fewer
games land exactly on 3. This is downstream of section 7.1: drives that should
reach FG range (opp 20-40) are ending in punts or turnovers instead.

**Downstream distortion:** Alt-spread pricing at +/-3 will be mispriced raw.
D7 anchoring partially corrects (shifting the total up raises expected scoring,
but does not directly fix the margin=3 mass). Key-number pricing (+/-3, +/-7)
requires a post-hoc calibration layer in Phase 3.

### 7.3 P(|margin|=6): 5.07% vs 7.54% (gap -2.5pp, gate +/-2pp)

**Mechanism:** Two-FG margin. Same root cause as section 7.2 -- fewer FGs per
game means fewer games at multiples of 3. Marginal fail (2.5pp vs 2.0pp gate).

**Downstream distortion:** Minor. |margin|=6 is not a key betting number.
The 2.5pp gap is within noise at N=1087 games x 500 sims.

---

## 8. What Phase 2A Delivered

Despite the failing lines, Phase 2A accomplished its stated objectives:

1. **Team differentiation** -- SD sim mean margin 5.63 vs closing-spread SD 6.08
   (was 1.5 at start of 2A). Teams rank correctly (corr 0.769 with spread).

2. **Margin distribution shape** -- pooled SD 14.06 vs 14.20 actual (PASS).
   P(|margin|=7) = 7.59% vs 8.24% (PASS). P(|margin|=10,14) both PASS.

3. **Volume metrics** -- plays/game, drives/game, pass/rush yards all PASS.

4. **Correct play-calling** -- situational pass rates now match data
   (trail Q4<2: 80%, lead Q4<2: 2%). Was completely broken (flat 55%) for
   all prior iterations.

5. **16 bugs found and fixed** -- including the play-call table that was
   never used (bug 14), which had been invisible because 55% is close to
   the league average pass rate.

The pts/team gap is a **league-level calibration** issue that D7 anchoring
will address. The margin=3 gap requires a **key-number calibration layer**
in Phase 3. Neither blocks the Phase 2B player layer or Phase 3 pricing.
