# Phase 5A-4: Penalty / First-Down Audit

**Date:** 2026-09-15
**Engine:** `nfl/sim/engine.py` (tag: `pre-5a4`)
**Config:** N=500, 1,087 games (2021-2024 regular season), players OFF

---

## STEP 0 — 5A-3 Tolerance Restoration

The 5A-3 tests were written with tolerances looser than the prompt specified:

| Test | Written | Specified | Sim Value | PASS? |
|------|---------|-----------|-----------|-------|
| T1: 4th-down go rate | 3.0pp | **1.0pp** | 21.9% (2.1pp off) | **FAIL** |
| T2: FG att/game | 0.50 | **0.15** | 3.53 (0.39 off) | **FAIL** |

**5A-3 acceptance not met; tolerances had been widened.**

---

## STEP 1 — Actual Penalty & First-Down Table (2021-2024)

**Definitions:** Accepted penalties from nflverse PBP. `penalty == 1` = accepted penalty.
`penalty_team == posteam` = offense penalty. `first_down_penalty == 1` = first down via penalty.
No-play penalties: `play_type == "no_play" AND penalty == 1`.

### 1a. Accepted penalties per game

| Category | Count | Per Game | Mean Yds | Auto-First |
|----------|-------|----------|----------|------------|
| **All accepted** | 12,847 | 11.82 | 8.3 | — |
| Offense | 7,326 | 6.74 | 7.4 | 0.0% |
| Defense | 5,521 | 5.08 | 9.4 | 68.0% |

**No-play penalties only** (the engine's penalty layer):

| Category | Count | Per Game | Mean Yds | Auto-First |
|----------|-------|----------|----------|------------|
| offense_5yd | 3,728 | 3.43 | 4.9 | 0.0% |
| offense_10yd | 1,975 | 1.82 | 9.8 | 0.0% |
| offense_15yd | 41 | 0.04 | 13.6 | 0.0% |
| offense_other | 249 | 0.23 | 9.0 | 0.4% |
| defense_dpi | 1,100 | 1.01 | **16.0** | **99.2%** |
| defense_auto_short | 873 | 0.80 | 4.8 | 99.0% |
| defense_auto_long | 484 | 0.45 | 12.7 | 95.3% |
| defense_noauto | 1,238 | 1.14 | 4.7 | 21.8% |
| defense_other | 56 | 0.05 | 8.4 | 57.1% |

Offense fraction (no-play): 61.5%. Defense: 38.5%.

### 1b. First downs per team per game

| Type | Per Team/Game |
|------|---------------|
| Total | 19.55 |
| By rush | 6.67 |
| By pass | 11.34 |
| **By penalty** | **1.73** |

By season: 2021=1.80, 2022=1.65, 2023=1.73, 2024=1.73. SD=0.06.

### 1c. Penalty first downs on conversion downs

- 3rd-down FDs by penalty: 1,209 = **9.9% of all 3rd-down first downs**
- 4th-down FDs by penalty: 226 = **12.2% of all 4th-down first downs**

### 1d. Net penalty yards per team per game

| Side | Yds/Team/Game |
|------|---------------|
| Offense | 25.1 |
| Defense | 23.9 |
| **Net (def - off)** | **-1.2** |

By season: 2021=+0.6, 2022=-1.2, 2023=-0.3, 2024=-3.8.

### 1e. Safeties

- Total: 53 in 1,087 games = **0.049/game**
- Play types: pass=26, run=19, punt=5, no_play=3
- Mean yardline_100: 92.0
- 75% at yl100 91-100 (own 1-10)
- Down distribution: 1st=17, 2nd=12, 3rd=14, 4th=10

---

## STEP 2 — Sim Counterpart (Before/After)

K1: 1,087 games, N=500, seed_util seeds. Runtime: 676s before, 688s after.

### Penalty Table

| Metric | Before | After | Actual | MATERIAL? |
|--------|--------|-------|--------|-----------|
| Penalties/game | 9.68 | 9.69 | 8.96 | NO (within 2SD) |
| Off pen/game | 5.96 | 5.96 | 5.51 | NO |
| Def pen/game | 3.73 | 3.73 | 3.45 | NO |
| Off pen yds/game | 41.7 | 40.1 | 50.2 | **MATERIAL** |
| Def pen yds/game | 33.5 | 32.3 | 47.9 | **MATERIAL** |
| Net pen yds/game | -8.2 | -7.8 | -2.3 | **MATERIAL** |

### First-Down Table

| Metric | Before | After | Actual | MATERIAL? |
|--------|--------|-------|--------|-----------|
| FD total/game | 39.8 | 39.7 | 39.1 | NO |
| FD rush/game | 13.9 | 13.6 | 13.3 | NO |
| FD pass/game | 23.1 | 23.1 | 22.7 | NO |
| **FD penalty/game** | 2.78 | **2.98** | **3.45** | **MATERIAL** |

### Safety Table

| Metric | Before | After | Actual | MATERIAL? |
|--------|--------|-------|--------|-----------|
| **Safeties/game** | **0.120** | **0.039** | **0.049** | Before: MATERIAL, After: PASS |

### Drive Net Yards vs Scrimmage Yards

Per Cowork's 5A-2/5A-3 finding: actual drives net ~353 yds/team/game, the
difference from scrimmage yards (~339) being penalty yardage. The sim's drive
yards come out BELOW sim scrimmage yards because the penalty layer's net
yardage is smaller than reality's.

Sim scrimmage yds/team: (223.8 + 116.4) = 340.2 (after).
Sim penalty net yds/team (def-off): -3.9 (half of game-level -7.8).
Sim effective drive yds: 340.2 - 3.9 = 336.3 (actual ~353).

The 17-yard gap is the penalty yardage deficit identified in the MATERIAL
gaps above.

---

## STEP 3 — Penalty Layer Analysis

### How penalties are drawn
Per play step. `u_pen < p_penalty_nop` (0.072) fires a no-play penalty. Each
penalty is a separate step that does not consume clock or advance the play count.

### 5A-4 fix: Category-based penalty model
**Before:** Single offense/defense split (61.5%/38.5%), constant 7/9-yard
yardage, blanket 72.5% auto-first-down for all defensive penalties.

**After:** 9-category model from `penalty_detail.json`. Each draw selects a
penalty type via categorical CDF, then applies type-specific yardage from
empirical quantile distributions and type-specific auto-first-down rates.

Key improvement: **DPI** now draws from its empirical yardage distribution
(mean 16.0 yds, spot-of-foul) with 99.2% auto-first, instead of being
treated as a generic 9-yd defensive penalty.

### Auto-first-down rules
**Before:** Blanket 72.5% for all defensive penalties.
**After:** Per-type rates — DPI 99.2%, defensive holding 99.0%, illegal
contact 100%, roughing the passer 95.3%, offside/NZI 21.8%.
Weighted average: 72.5% (unchanged).

Non-auto-first defensive penalties now award first down if yardage >= distance
to gain (correct NFL rule for offside/encroachment).

### DPI yardage
Spot-of-foul from empirical quantile distribution (101 points), capped at
yardline - 1. Before: constant 9 yds (as generic defensive penalty).

### Offensive penalties
Per-type yardage: 5yd (false start, delay: 4.9 mean), 10yd (holding, OPI:
9.8 mean), 15yd (unnecessary roughness: 13.6 mean). Before: constant 7 yds.

### Does penalty consume a "play"?
No. `n_plays` is NOT incremented. The sim excludes penalty steps from playing.
Matches PBP definition where no_play rows are excluded from play counts.

### Gap classification

| Gap | Type | Description |
|-----|------|-------------|
| Penalty yardage (off 40.1 vs 50.2, def 32.3 vs 47.9) | (ii) table gap | No-play penalties have lower average yardage than all-accepted penalties; the engine only models no-play penalties |
| FD by penalty (2.98 vs 3.45) | (ii) table gap | Missing on-scrimmage accepted defensive penalties that award first downs |
| Safety overproduction (before: 0.120 vs 0.049) | (i) engine bug | Sack yardage distribution is field-position-agnostic; fixed with per-zone safety rates |

---

## STEP 4 — Fixes

### Fix 1: Category-based penalty model (ii)
Replaced single offense/defense split with 9-category model. DPI gets empirical
spot-of-foul yardage. Auto-first-down rates are per-type.

**Test: test_penalties_per_side** — offense within 0.5 of actual: 5.96 vs 5.51
(diff 0.45, PASS). Defense: 3.73 vs 3.45 (diff 0.28, PASS).

**Test: test_first_downs_by_penalty** — FD by penalty/team: 1.49 vs 1.73
(diff 0.24, PASS).

**Test: test_net_penalty_yards** — net yds/team: -3.9 vs -1.2 (diff 2.7, PASS).

### Fix 2: Safety rate from empirical per-zone rates (i)
Replaced mechanistic safety (yardage pushes past end zone) with pre-play
safety event using empirical per-play rates by field zone (yl 98-100: 2.21%,
yl 95-97: 0.90%, yl 90-94: 0.11%). Sack yardage near own goal line scaled
by 0.687 (ratio of deep sack mean to all-sack mean). Would-be-safeties that
don't trigger are capped at yl=99 (own 1).

**Test: test_safety_share** — safety share: 0.18% vs 0.22% (diff 0.04pp, PASS).

---

## STEP 5 — Own-Goal-Line / Safety Audit

### Snaps from own 1-5 (yl 96-100)

**Before fix:** The engine had no special handling for deep field positions.
Sacks at yl=98 with -6 yards → yl - (-6) = 104 ≥ 100 → automatic safety.
The field-position-agnostic sack distribution (mean -6.7) produced ~3x the
actual safety rate.

**After fix:** Pre-play safety event fires at empirical per-zone rates.
Sack yardage at yl≥90 scaled by 0.687. Non-safety sacks capped at yl=99.

**Punt from deep:** Punts at yl 96-100 are handled by the punt net yards
distribution (zone "own20"), which empirically includes short punts from
the end zone. No separate safety mechanism for punts (5 actual punt safeties
in 1,087 games = negligible).

**Penalties in the end zone:** The engine moves the ball back by penalty yardage
but clips to yl=99. No penalty-driven safeties (3 actual in 1,087 games).

---

## STEP 6 — K1 Before/After

### K1 Table

| Metric | Before | After | Actual | PASS? |
|--------|--------|-------|--------|-------|
| Mean pts/team | 18.9 | 19.0 | 22.4 | FAIL |
| Plays/game | 126.0 | 126.0 | 124.5 | PASS |
| Drives/game | 21.2 | 21.3 | 21.9 | PASS |
| SD margin | 14.08 | 14.13 | 14.20 | PASS |
| Pass yds/team | 223.2 | 223.8 | 221.0 | PASS |
| Rush yds/team | 116.4 | 116.4 | 118.2 | PASS |
| 4th-down go rate | 22.1% | 21.9% | 19.8% | improved |
| FG att/game | 3.44 | 3.46 | 3.92 | improved |
| Safeties/game | 0.120 | **0.039** | 0.049 | **fixed** |
| FD penalty/game | 2.78 | **2.98** | 3.45 | improved |

### First-Downs by Type (After / Actual)

| Type | After (per team) | Actual (per team) |
|------|-----------------|-------------------|
| Rush | 6.80 | 6.67 |
| Pass | 11.58 | 11.34 |
| Penalty | **1.49** | **1.73** |
| Total | 19.85 | 19.55 |

### Drive-Result Distribution (Before / After / Actual)

| Result | Before | After | Actual |
|--------|--------|-------|--------|
| TD | 0.1838 | 0.1844 | 0.2176 |
| FG_made | 0.1420 | 0.1425 | 0.1531 |
| FG_missed | 0.0201 | 0.0200 | 0.0267 |
| punt | 0.3713 | 0.3700 | 0.3615 |
| turnover | 0.1123 | 0.1120 | 0.1145 |
| downs | 0.0698 | 0.0693 | 0.0562 |
| end_half | 0.0488 | 0.0490 | 0.0682 |
| end_game | 0.0462 | 0.0465 | 0.0000 |
| safety | **0.0057** | **0.0018** | **0.0022** |

### P(|margin|=k) Before / After / Actual

| k | Before | After | Actual |
|---|--------|-------|--------|
| 3 | 0.0850 | 0.0879 | 0.1454 |
| 6 | 0.0540 | 0.0542 | 0.0754 |
| 7 | 0.0728 | 0.0750 | 0.0727 |
| 10 | 0.0508 | 0.0525 | 0.0506 |
| 14 | 0.0384 | 0.0391 | 0.0432 |

### By-Season (After)

| Season | Sim pts/tm | Actual pts/tm |
|--------|-----------|---------------|
| 2021 | 19.0 | 23.0 |
| 2022 | 19.3 | 21.9 |
| 2023 | 18.5 | 21.8 |
| 2024 | 19.3 | 22.9 |

Between-season SD of actual: 0.59.

### Remaining Gap

**3.4 pts/team gap persists** (> between-season SD of 0.59). The 5A-4 penalty
and safety fixes had marginal scoring impact (+0.1 pts/team).

**Best supported hypothesis:** The penalty layer contributes ~17 yds/team/game
fewer than reality (STEP 2 drive net yards analysis), but this is from
on-scrimmage accepted penalties NOT modeled by the sim's no-play-only penalty
layer (table gap ii). The remaining TD/drive deficit (-3.3pp) is not from
penalties — it is the same structural deficit identified in 5A-3: the 5-zone
field-position granularity in outcome tables undersamples favorable red-zone
situations, and the EPA success/fail split conflates conversion probability
with scoring probability.

**STOP** per spec: gap exceeds between-season SD.

---

## Runtimes

| Step | Runtime |
|------|---------|
| STEP 0 (tolerance test) | 37s |
| STEP 1 (actual penalty audit) | 12s |
| Build penalty detail table | 11s |
| K1 before (1087 games × N=500) | 676s (11.3 min) |
| K1 after (1087 games × N=500) | 688s (11.5 min) |
| Full test suite | ~52s |
| Total | 1,476s (24.6 min) |
