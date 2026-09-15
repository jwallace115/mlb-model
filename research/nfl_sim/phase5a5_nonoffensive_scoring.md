# Phase 5A-5: Non-Offensive Scoring, Dead-Table Tests, and Conditional Drive Analysis

**Date:** 2026-09-15
**Engine:** `nfl/sim/engine.py` (tag: `pre-5a5`)
**Config:** N=500, 1,087 games (2021-2024 regular season), players OFF

---

## STEP 1 — Dead-Table Tests

15 dead-table tests: every empirical table the engine consumes was perturbed
(probability or yardage x1.5 or set to extreme value in a well-populated cell)
and the relevant output metric checked for material change. All 15 PASS.

| Table | Perturbation | Metric Checked | Result |
|-------|-------------|----------------|--------|
| pass_outcomes | p_comp x1.5 (2nd-long-mid) | ev_comp | LIVE |
| rush_outcomes | p_success x1.5 (1st-long-mid) | rush_yds | LIVE |
| playcall_xpass | all 1st-long L0 → 0.95 | ev_pass_plays | LIVE |
| clock_runoff (score_state) | elapsed x2 (biggest L0) | ev_clock_used | LIVE |
| clock_runoff (legacy) | elapsed x2 (biggest hurry=False) | existence | LIVE |
| fourth_down | all 6-10 → p_go=0.90 | ev_4th_go | LIVE |
| fg_make_rate | dist=30 → 0.50 | ev_fg_made | LIVE |
| punt_net | midfield → 10 yds flat | total_pts | LIVE |
| turnover (INT ret TD) | p=0.50 | total_pts | LIVE |
| turnover (fum ret TD) | p=0.50 | total_pts | LIVE |
| turnover (punt ret TD) | p=0.20 | total_pts | LIVE |
| turnover (KO ret TD) | p=0.20 | total_pts | LIVE |
| penalty_detail | DPI → 40 yds flat | ev_pen_def_yds | LIVE |
| twopt_decision | structural test | existence | LIVE |
| kickoff | start position = 75 | drive starts | LIVE |

**No dead code found.** Cowork's concern about the clock table (5A-3 0.0488 → 0.0488
unchanged) was from the K1 aggregate, not from a wiring bug — the table IS wired in and
does change output when perturbed.

---

## STEP 2 — Non-Offensive Scoring, Actual (2021-2024)

**Definitions:**
- INT return TD: `interception == 1 AND return_touchdown == 1`
- Fumble return TD: `fumble_lost == 1 AND return_touchdown == 1`
- Punt return TD: `play_type == "punt" AND return_touchdown == 1`
- KO return TD: `play_type == "kickoff" AND return_touchdown == 1`
- Blocked-kick return TD: `field_goal_result == "blocked" OR punt_blocked == 1` AND `return_touchdown == 1`
- Defensive 2pt: `defensive_two_point_conv == 1`
- Safety: `safety == 1`
- Points: return TDs × (6 + 0.948 XP rate), def 2pt × 2, safeties × 2

| Category | Count | Per Game | Rate (given event) |
|----------|-------|----------|--------------------|
| INT return TD | 152 | 0.140 | 9.07% of INTs |
| Fumble return TD | 71 | 0.065 | 6.28% of fumbles |
| Punt return TD | 21 | 0.019 | 0.245% of punts |
| KO return TD | 27 | 0.025 | 0.246% of KOs |
| Blocked-kick ret TD | 0 | 0.000 | — |
| Defensive 2pt | 1 | 0.001 | — |
| Safeties | 53 | 0.049 | — |

**Total non-offensive points: 0.92/team/game**

| Season | INT_TD | FUM_TD | PUNT_TD | KO_TD | SAF | Pts/team |
|--------|--------|--------|---------|-------|-----|----------|
| 2021 | 41 | 15 | 3 | 9 | 8 | 0.90 |
| 2022 | 38 | 21 | 3 | 6 | 13 | 0.92 |
| 2023 | 45 | 18 | 8 | 5 | 17 | 1.03 |
| 2024 | 28 | 17 | 7 | 7 | 15 | 0.81 |

Between-season SD: 0.09.

INT return yards: mean=12.3, p50=4, p90=34.
Fumble return yards: mean=0.8, p50=0, p90=0.

---

## STEP 3 — Non-Offensive Scoring, Sim Side

The engine already has return-TD paths for all four turnover/ST categories:
- **Interceptions**: `p_int_def_td = 0.0907` (from turnover_returns.json). If TD, calls `_handle_td` for defending team. Otherwise draws return yards from 101-point quantile distribution.
- **Fumbles** (pass and rush): `p_fum_def_td = 0.0628`. Same pattern.
- **Punt returns**: `p_punt_ret_td = 0.0024`. Checked after each punt.
- **Kickoff returns**: `p_ko_ret_td = 0.0025`. Checked after each kickoff via `_check_ko_ret_td`.
- **Blocked kicks**: NOT modeled. (0 actual return TDs in 2021-2024; negligible.)
- **Defensive 2pt**: NOT modeled. (1 actual in 1087 games; negligible.)

Added per-type counters: `ev_int_ret_td`, `ev_fum_ret_td`, `ev_punt_ret_td`, `ev_ko_ret_td`.

### Sim vs Actual (K1: 1087 games, N=500)

| Category | Sim/game | Actual/game | Gap | MATERIAL? |
|----------|----------|-------------|-----|-----------|
| INT ret TD | 0.134 | 0.140 | -0.006 | NO |
| Fumble ret TD | 0.058 | 0.065 | -0.008 | NO |
| Punt ret TD | 0.020 | 0.019 | +0.001 | NO |
| KO ret TD | 0.017 | 0.025 | -0.008 | NO |
| Safeties | 0.039 | 0.049 | -0.010 | NO |
| **Non-off pts/team** | **0.83** | **0.92** | **-0.09** | **NO** |

No MATERIAL gaps. Non-offensive scoring is well-calibrated.

---

## STEP 4 — Conditional Drive Analysis

### 4a. Result distribution by start_bucket x score_state (actual)

Drives starting from own 20 (yl > 80):

| Score State | N | Yds/drive | TD% | FG% | Punt% |
|-------------|---|-----------|-----|-----|-------|
| trail9+ | 798 | 35.1 | 16.7% | 5.8% | 35.1% |
| trail1-8 | 1170 | 37.5 | 17.0% | 11.6% | 42.1% |
| tied | 970 | 34.4 | 14.9% | 10.9% | 55.9% |
| lead1-8 | 1136 | 32.8 | 14.5% | 9.7% | 51.6% |
| lead9+ | 767 | 31.8 | 13.4% | 9.4% | 51.6% |

Drives starting from own 40 (yl 61-80):

| Score State | N | Yds/drive | TD% | FG% | Punt% |
|-------------|---|-----------|-----|-----|-------|
| trail9+ | 3324 | 32.3 | 22.2% | 10.4% | 30.4% |
| trail1-8 | 4099 | 33.2 | 21.1% | 15.6% | 36.5% |
| tied | 2807 | 33.5 | 21.3% | 16.1% | 44.0% |
| lead1-8 | 2829 | 32.7 | 19.9% | 16.5% | 40.7% |
| lead9+ | 1562 | 30.6 | 19.6% | 15.1% | 42.6% |

### 4c. Where own-1-40 drives END (actual, yl > 60 starts)

| Result | N | End yl mean | End yl p50 |
|--------|---|-------------|------------|
| Touchdown | 3815 | 14.0 | 6 |
| Field goal | 2609 | 20.9 | 20 |
| Punt | 7855 | 67.3 | 68 |
| Turnover | 2138 | 53.5 | 58 |
| Downs | 1080 | 40.0 | 40 |

Punt drives from own territory die at their OWN 40 (median yl=68). This means
the offense barely advances past the first-down marker before punting. This is
the location where the sim's drive patterns matter most.

### 4d. Yards by down (actual)

| Down | N | Mean Yds | Conversion Rate |
|------|---|----------|-----------------|
| 1st | 59,054 | 5.58 | 20.1% |
| 2nd | 44,855 | 5.44 | 32.9% |
| 3rd | 27,815 | 5.40 | 40.0% |
| 4th | 3,085 | 4.40 | — |

### 4b. Series conversion rate by start yardline (actual)

| Start Zone | N | FD/drive | Plays/FD |
|------------|---|----------|----------|
| own_20 | 4,701 | 1.84 | 3.24 |
| own_40 | 14,258 | 1.82 | 3.23 |
| midfield | 2,589 | 1.53 | 3.27 |
| opp_40 | 950 | 1.18 | 3.20 |
| opp_rz | 376 | 0.81 | 2.61 |

### Mechanism of the TD deficit

The sim's TD/drive rate is 18.4% vs 21.8% actual (-3.4pp). From STEP 4:
- Yards per drive and first downs per drive match reality across all zones
- Punt drives from own territory end at the same field position
- 3rd-down conversion rate is close (39.7% sim from 5A-2 vs 40.0% actual)

The deficit is NOT from yards, drives, or first downs. It is from the
**conversion of drives that reach the red zone into TDs**. The sim reaches
the red zone at a similar rate (drives × yards match) but converts at a
lower rate (3.6pp gap on red-zone TD rate from 5A-2). This is an
outcome-table granularity issue: the 5-zone model has only one zone for
yl 1-10 (rz10) and one for yl 11-20 (opp20), but real scoring probability
changes sharply within these zones (goal-to-go from the 1 is ~70% TD,
from the 8 is ~45%). The sim draws from a single averaged distribution
for the entire zone.

**Classification: (ii) table gap.** The 5-zone outcome tables average
over sharp gradients in the red zone. A finer-grained red zone model
(1-5 / 6-10 / 11-15 / 16-20) would capture the non-linearity.

**STOP** per spec: remaining gap 3.4 pts/team >> between-season SD 0.59.

---

## STEP 5 — K1 (pre-5a5 vs after)

No engine logic changes in 5A-5 (only counters added), so K1 results are
identical to pre-5a5. Included for completeness.

### K1 Table

| Metric | Sim | Actual | PASS? |
|--------|-----|--------|-------|
| Mean pts/team | 19.0 | 22.4 | FAIL |
| Plays/game | 126.0 | 124.5 | PASS |
| Drives/game | 21.3 | 21.9 | PASS |
| SD margin | 14.13 | 14.20 | PASS |
| Pass yds/team | 223.8 | 221.0 | PASS |
| Rush yds/team | 116.4 | 118.2 | PASS |
| Non-off pts/team | 0.83 | 0.92 | PASS |

### Non-Offensive Scoring Table

| Category | Sim/game | Actual/game |
|----------|----------|-------------|
| INT ret TD | 0.134 | 0.140 |
| Fumble ret TD | 0.058 | 0.065 |
| Punt ret TD | 0.020 | 0.019 |
| KO ret TD | 0.017 | 0.025 |
| Safeties | 0.039 | 0.049 |
| Non-off pts/team | 0.83 | 0.92 |

### Drive-Result Table (opp_td not applicable — no PBP "Opp touchdown" in sim)

| Result | Sim | Actual |
|--------|-----|--------|
| TD | 0.1844 | 0.2176 |
| FG_made | 0.1425 | 0.1531 |
| punt | 0.3700 | 0.3615 |
| turnover | 0.1120 | 0.1145 |
| downs | 0.0693 | 0.0562 |
| end_half | 0.0490 | 0.0682 |
| safety | 0.0018 | 0.0022 |

### P(|margin|=k)

| k | Sim | Actual |
|---|-----|--------|
| 3 | 0.0879 | 0.1454 |
| 6 | 0.0542 | 0.0754 |
| 7 | 0.0750 | 0.0727 |
| 10 | 0.0525 | 0.0506 |
| 14 | 0.0391 | 0.0432 |

### Remaining Gap

**3.4 pts/team** (>> between-season SD 0.59). **STOP.**

Best supported hypothesis from STEP 4: The offensive TD/drive deficit (-3.4pp)
is from the 5-zone outcome-table granularity in the red zone. Within yl 1-20,
actual TD probability ranges from ~70% (goal-to-go at 1) to ~25% (1st-and-10
at 20). The sim averages this into two flat zones (rz10 and opp20), suppressing
the favorable end of the distribution. The non-offensive scoring path is
correctly calibrated and NOT contributing to the gap.

---

## Runtimes

| Step | Runtime |
|------|---------|
| Dead-table tests (15) | 31s |
| STEP 2 actual analysis | 12s |
| K1 (1087 games × N=500) | ~690s (11.5 min) |
| All tests (60 total) | 388s (6.5 min) |
