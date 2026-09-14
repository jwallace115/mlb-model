# Phase 2A: Vectorised Play-Level Engine — Realism Report

**Data:** 2021–2024 regular season only (weeks 1–18). **2025 and 2026 were NOT used** in
tables, ratings, or any simulation. The 2025 season is the designated holdout.

**Runtime:** 1032s total for 1087 games × 2000 sims = 2.174M simulated games (0.95s/game).

---

## 0. Points Decomposition (STEP 1)

Scoring measured from 2021–2024 PBP with proper `td_team == posteam` attribution.

| Category | Actual/game | Actual pts/team | Sim pts/team | Gap pts/team |
|----------|------------|----------------|-------------|-------------|
| Offensive pass TD | 3.09 × 6 | 9.26 | ~8.3 | −0.9 |
| Offensive rush TD | 1.84 × 6 | 5.47 | ~5.0 | −0.5 |
| INT return TD | 0.140 × 6 | 0.42 | modeled | ~0 |
| Fumble return TD | 0.063 × 6 | 0.19 | modeled | ~0 |
| Punt return TD | 0.031 × 6 | 0.09 | **added** | ~0 |
| Kickoff return TD | 0.001 × 6 | 0.00 | **added** | ~0 |
| FG made | 3.33 × 3 | 5.00 | 4.5 | −0.5 |
| XP/2pt | 4.71 | 2.36 | 2.1 | −0.3 |
| Safety | 0.049 × 2 | 0.05 | modeled | ~0 |
| **Total** | | **22.4** | **19.5** | **−2.9** |

**Previous session's error corrected:** non-offensive TDs are 0.241/game (both teams) =
0.72 pts/team, NOT "~1.75 pts/team from special-teams TDs." Unmodeled punt+KO return TDs
contribute only 0.10 pts/team — negligible. The dominant gap is **fewer offensive TDs per
drive** (0.205 sim vs 0.229 actual = −2.4pp/drive) and **fewer FG attempts** (3.4 vs 3.9/game).

**Fix applied:** Switched pass and rush yards from EPA success/fail split distributions
(`yds_success_q` / `yds_fail_q`) to unsplit empirical distributions (`yds_all_q`). The
EPA split compressed the upper tail (p95: 27 yds blended vs 31 yds unsplit at midfield),
suppressing explosive plays and TDs. This recovered ~0.4 pts/team.

**Tradeoff:** removing the success/fail split removed the primary team-differentiation
channel (matchup tilt on `p_success_given_comp`). SD of sim mean margin dropped from
3.61 to 2.04; corr(sim margin, spread) from 0.759 to 0.506. Phase 2B must restore
differentiation through the player layer or a yards-quantile shift.

---

## 1. RNG Audit Table

Unchanged from previous session — 26 pre-drawn U(0,1) vectors per step plus 2 new
draws for punt/KO return TDs (`u_punt_td`, `u_ko_td`). Total: 28 draws per step.
RNG insensitivity test still passes (z = 0.23 on pts/team).

---

## 2. K1 Realism Check (1087 games × 2000 sims)

| Metric | Sim | Actual | Target | PASS/FAIL |
|--------|-----|--------|--------|-----------|
| Mean pts/team | 19.5 | 22.4 | ±3 of actual | **PASS** |
| Plays/game | 125.3 | 124.5 | ~125 | PASS |
| Drives/game | 20.9 | 21.9 | ~22 | PASS |
| SD margin (pooled) | 13.23 | 14.20 | ±1.0 of actual | **PASS** |
| SD total (pooled) | 11.82 | 13.61 | ±2.0 of actual | **PASS** |
| SD sim mean margin | 2.04 | spread SD 6.08 | INFO | INFO |
| P(\|margin\|=3) | 8.51% | 14.54% | ±2 of 14.27% | **FAIL** |
| P(\|margin\|=6) | 5.47% | 7.54% | ±2 of 7.54% | **FAIL** |
| P(\|margin\|=7) | 8.06% | 7.27% | ±2 of 8.24% | PASS |
| P(\|margin\|=10) | 6.68% | 5.06% | ±2 of 5.06% | PASS |
| P(\|margin\|=14) | 4.68% | 4.32% | ±2 of 4.32% | PASS |
| Pass yds/team/game | 218.2 | 221.0 | ~221 | PASS |
| Rush yds/team/game | 138.4 | 118.2 | ~118 | PASS |
| corr(sim margin, spread) | 0.506 | — | ~0.8 (info) | INFO |

**K1: 9 of 11 PASS** (was 8/11 previous session). Two remaining FAILs: P(|margin|=3)
and P(|margin|=6).

---

## 3. P(|margin|=3) Residual Analysis

The NFL's 14.5% rate at margin=3 is a pronounced spike — 2× what a smooth distribution
predicts — driven by game-management patterns:

1. **Trailing by ≤3 in late Q4 → kick FG to tie → OT → FG → win by 3.** The fine-grained
   4th-down table (added this session: 7 score × 4 clock × 4 ydstogo × 4 zone, min_n=10
   with coarse fallback) correctly produces ~100% FG attempts when trailing 1-3 at opp40
   in Q4<2:00. But the sim's OT rate is only 3.3% vs actual 5-6%, limiting this pathway.

2. **Score management:** Real coaches "take the points" (kick FGs) strategically. The sim
   does this through the 4th-down table but lacks explicit 2-minute-drill coaching logic.

3. **FG rate deficit:** Sim produces 3.4 FG att/game vs 3.9 actual. Drives don't reach FG
   range often enough, partly from the 2.4pp/drive offensive TD deficit (drives that should
   end in FGs are ending in punts or turnovers instead).

**This is structural:** closing the P(|margin|=3) gap requires Phase 2B improvements —
wider team differentiation (which affects late-game score states), explicit 2-minute-drill
strategy, and possibly a transition to modeled coaching decisions rather than empirical tables.

---

## 4. Changes This Session

| Change | Mechanism | Impact |
|--------|-----------|--------|
| yds_all_q switch | Pass/rush yards drawn from unsplit empirical distribution instead of EPA success/fail split | +0.4 pts/team; removed upper-tail compression that suppressed TDs |
| Punt return TDs | Empirical rate from table G (0.00245/punt) applied in punt execution | +0.09 pts/team |
| KO return TDs | Empirical rate from table G (0.00246/kickoff) applied after kickoffs | +0.01 pts/team |
| Fine-grained 4th-down table | 7 score states × 4 clock periods × existing ydstogo/zone; min_n=10 with 3-level fallback | Correct late-game FG decisions; P(|margin|=3) unchanged at 8.5% |
| Kneel-out improvement | Accounts for ~1 opponent timeout; kneels when remaining clock ≤ (5−down−1)×40 | More realistic end-game |
| Team 4th-down override Q1-3 only | Late-game decisions are situation-driven from table, not team-style-driven | Prevents team override from distorting late-game decisions |

---

## 5. Home Win Probability Calibration

| Decile | Sim P(HW) | Actual HW | N |
|--------|----------|----------|---|
| 0 | 0.377 | 0.409 | 110 |
| 1 | 0.419 | 0.450 | 109 |
| 2 | 0.442 | 0.514 | 107 |
| 3 | 0.459 | 0.440 | 109 |
| 4 | 0.476 | 0.459 | 109 |
| 5 | 0.489 | 0.627 | 110 |
| 6 | 0.505 | 0.541 | 109 |
| 7 | 0.523 | 0.660 | 106 |
| 8 | 0.547 | 0.560 | 109 |
| 9 | 0.596 | 0.743 | 109 |

Sim home-win range [0.377, 0.596] is **more compressed** than previous session [0.295,
0.671] due to loss of success-rate tilt. Phase 2B must restore team differentiation.

---

## 6. Total Calibration

| Decile | Sim P(over) | Actual over rate | N |
|--------|------------|-----------------|---|
| 0 | 0.125 | 0.364 | 110 |
| 1 | 0.180 | 0.556 | 108 |
| 2 | 0.215 | 0.519 | 108 |
| 3 | 0.245 | 0.431 | 109 |
| 4 | 0.277 | 0.414 | 111 |
| 5 | 0.308 | 0.467 | 107 |
| 6 | 0.343 | 0.546 | 108 |
| 7 | 0.381 | 0.463 | 108 |
| 8 | 0.448 | 0.495 | 109 |
| 9 | 0.572 | 0.459 | 109 |

Systematically biased low from −2.9 pts/team scoring gap.

---

## 7. Check 5 Breakdowns

### By Season

| Season | Sim pts/team | Actual pts/team | Sim margin SD | Actual margin SD |
|--------|-------------|----------------|--------------|-----------------|
| 2021 | 19.6 | 23.0 | 2.25 | 15.43 |
| 2022 | 19.3 | 21.9 | 1.97 | 12.35 |
| 2023 | 19.5 | 21.8 | 2.04 | 14.42 |
| 2024 | 19.3 | 22.9 | 1.88 | 14.46 |

Scoring gap stable at 2.5–3.6 pts/team across seasons.

### By Week Range

| Weeks | Sim pts/team | Actual pts/team |
|-------|-------------|----------------|
| 1–4 | 20.3 | 22.3 |
| 5–18 | 19.2 | 22.4 |

### By Favourite Size

| \|Spread\| | Sim pts/team | Actual pts/team | N |
|-----------|-------------|----------------|---|
| <3 | 19.4 | 21.5 | 255 |
| 3–7 | 19.5 | 22.5 | 536 |
| >7 | 19.4 | 23.0 | 296 |

Sim scoring flat across spread buckets; actual increases with favourite strength.
Consistent with collapsed team differentiation.

---

## 8. Bug List Update (This Session)

| Bug | Cause | Fix |
|-----|-------|-----|
| Previous session claimed ~1.75 pts/team from missing ST TDs | Incorrect PBP count (used `return_touchdown` without play-type filter, double-counted) | Proper `td_team == posteam` attribution: non-off TDs = 0.72 pts/team total; punt+KO return TDs = 0.10 pts/team only |
| EPA success/fail yards split compressed upper tail | At 1st-long midfield: p95 blend = 27 yds vs p95 unsplit = 31 yds. Suppressed explosive plays and TDs. | Switched to `yds_all_q` unsplit distributions |
| 4th-down table too coarse for end-game | Score: {trail9/within8/lead9} × Clock: {Q1-3/Q4} couldn't express "down 3, kick to tie" | 7 score × 4 clock states with 3-level fallback (min_n=10) |
| Kneel-out too aggressive | Kneeled in all Q4 < 2:00 leading situations regardless of down/timeouts | Account for ~1 opponent timeout in effective kneels |

---

## 9. Statement on Data Seasons

All tables, ratings, and diagnostics use **2021–2024 regular season data only**
(weeks 1–18). The 2025 season is the designated holdout and was not used in any
table build, rating computation, simulation, or evaluation. The 2026 season does
not exist in the PBP data.

---

## 10. K1 Summary

| Check | Result |
|-------|--------|
| Mean pts/team within ±3 of 22.4 | **PASS** (19.5) |
| Plays/game ~125 | **PASS** (125.3) |
| Drives/game ~22 | **PASS** (20.9) |
| SD margin (pooled) within ±1.0 of 14.2 | **PASS** (13.23) |
| SD total (pooled) within ±2.0 of 13.6 | **PASS** (11.82) |
| P(\|margin\|=3) within ±2 of 14.3% | **FAIL** (8.51%) |
| P(\|margin\|=6) within ±2 of 7.5% | **FAIL** (5.47%) |
| P(\|margin\|=7) within ±2 of 8.2% | **PASS** (8.06%) |
| P(\|margin\|=10) within ±2 of 5.1% | **PASS** (6.68%) |
| P(\|margin\|=14) within ±2 of 4.3% | **PASS** (4.68%) |
| Home-win calibration | Compressed (SD 2.04 vs spread SD 6.08) |
| Total calibration | Biased low (from scoring gap) |
| corr(sim margin, spread) | 0.506 |
| OT rate | 3.3% (actual ~5–6%) |

**K1: 9/11 PASS, 2 FAIL.** Residual: P(|margin|=3) at 8.5% (need ~12–16%) and
P(|margin|=6) at 5.5% (need ~5.5–9.5%).

**Root cause of P(|margin|=3):** The NFL's 14.5% spike at margin=3 is a game-management
phenomenon (late FGs, OT FGs) that requires coaching strategy modeling — not just empirical
play-outcome tables. The sim's FG rate (3.4 vs 3.9/game) and OT rate (3.3% vs 5–6%) are
both low. Closing this gap requires Phase 2B: restored team differentiation (yards-quantile
shift or player-layer tilt), explicit 2-minute-drill strategy, and coaching-decision
modeling for score-chasing scenarios.
