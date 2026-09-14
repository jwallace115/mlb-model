# Phase 2A: Vectorised Play-Level Engine — Realism Report

**Data:** 2021–2024 regular season only (weeks 1–18). **2025 and 2026 were NOT used** in
tables, ratings, or any simulation. The 2025 season is the designated holdout.

---

## 0. What Was Reverted and Why

**REVERT 1 — Tolerance.** The pts/team gate was incorrectly widened to ±3 in commit
827a89ed5. Restored to **±1.5 of 22.4** (need 20.9–23.9). The value 19.5 that was
reported as PASS is a FAIL under the correct tolerance.

**REVERT 2 — Matchup mechanism.** Commit 827a89ed5 switched yards from EPA success/fail
split (`yds_success_q`/`yds_fail_q`) to unsplit (`yds_all_q`), claiming the split
"compressed the upper tail (p95 27 vs 31)." This was a **mathematical error**: the
previous session computed `p_succ × success_q[95] + (1-p_succ) × fail_q[95] = 27.3` and
called it "p95 of the blend." That is the weighted average of the individual p95s, which
is NOT the p95 of the mixture distribution. Verified by sampling 500k draws from the
engine's actual mixture logic:

| Metric | Mixture (success/fail) | Unsplit (yds_all) |
|--------|----------------------|-------------------|
| Mean | 11.4 | 11.3 |
| p90 | 24.1 | 23.9 |
| p95 | 31.5 | 31.0 |
| P(≥20 yds) | 15.4% | 15.0% |

The success/fail split does NOT compress the upper tail — the mixture p95 is actually
0.5 yds HIGHER than the unsplit. Removing the split collapsed team differentiation
(corr 0.759 → 0.506) for zero scoring benefit. The success/fail split with D6 matchup
tilt is restored. corr(sim margin, spread) = **0.771** (gate ≥0.75: PASS).

---

## 1. FG Decomposition (STEP 1)

### FG attempts by distance bucket (2021–2024 actual)

| Bucket | Att/game | Make rate |
|--------|---------|-----------|
| <30 yd | 0.89 | 0.980 |
| 30–39 | 1.10 | 0.935 |
| 40–49 | 1.09 | 0.786 |
| 50+ | 0.84 | 0.685 |
| **Total** | **3.92** | **0.850** |

### 4th-down decisions by 10-yard field zone (actual)

| Zone | N | Go% | Punt% | FG% |
|------|---|-----|-------|-----|
| opp 1-10 | 1285 | 36.5 | 0.0 | 63.5 |
| opp 11-20 | 1409 | 20.6 | 0.0 | 79.4 |
| opp 21-30 | 1449 | 24.9 | 0.1 | 74.9 |
| opp 31-40 | 1604 | 35.5 | 11.2 | 53.3 |
| opp 41-50 | 1702 | 30.8 | 67.4 | 1.8 |
| own 41-50 | 2017 | 17.6 | 82.4 | 0.0 |
| own 31-40 | 2613 | 12.5 | 87.5 | 0.0 |
| own 21-30 | 2146 | 6.1 | 93.9 | 0.0 |
| own 1-20 | 1354 | 4.4 | 95.6 | 0.0 |

The previous table E zones (rz/opp40/midfield/own35) blended opp 11-40 into one zone
(68.6% FG), overweighting the opp 31-40 sub-zone (53.3% actual) and washing out the
sharp FG/punt transition at yl 40. Rebuilt with 10-yard bins (10 zones) × 7 score
states × 4 clock periods × 4 ydstogo, min cell size 10, 4-level fallback (fine →
coarse score → coarse zone → coarsest).

### Points decomposition — sim vs actual

| Category | Actual pts/team | Sim pts/team | Gap |
|----------|----------------|-------------|-----|
| Offensive TD (pass+rush) | 14.73 | ~12.6 | −2.1 |
| Defensive/ST return TD | 0.72 | modeled | ~0 |
| Punt/KO return TD | 0.10 | modeled | ~0 |
| FG made | 5.00 | ~4.5 | −0.5 |
| PAT (XP/2pt) | 2.36 | ~2.0 | −0.3 |
| Safety | 0.05 | modeled | ~0 |
| **Total** | **22.4** | **~19.0** | **−3.4** |

**Dominant sources:** offensive TD deficit (−2.1 pts/team, 60% of gap) and FG
deficit (−0.5 pts/team, 15%). The TD deficit is from 0.033 fewer TDs per drive
(0.196 sim vs 0.229 actual) while the FG deficit is from 0.4 fewer FG att per
game (3.5 sim vs 3.92 actual).

---

## 2. Gate Check (100 games × 500 sims, 2021–2024)

| Gate | Value | Threshold | PASS/FAIL |
|------|-------|-----------|-----------|
| pts/team | 19.6 | ±1.5 of 22.4 (20.9–23.9) | **FAIL** |
| corr(sim margin, spread) | 0.771 | ≥0.75 | **PASS** |
| P(\|margin\|=3) | 9.0% | 14.5% ±3pp (11.5–17.5%) | **FAIL** |

**K1 NOT LAUNCHED** — two of three pre-K1 gates fail.

---

## 3. Residual Analysis

### pts/team gap (−2.8 on 100-game check)

| Source | Gap pts/team | Share |
|--------|-------------|-------|
| TD/drive deficit (0.203 vs 0.229) | −1.6 | 57% |
| FG att deficit (3.54 vs 3.92/game) | −0.5 | 18% |
| PAT (consequence of fewer TDs) | −0.3 | 11% |
| Other (drives/game, safeties) | −0.4 | 14% |

The TD/drive deficit is structural: the engine's play-level distributions produce
correct per-play stats (comp rate, sack rate, INT rate all within 0.3pp) and correct
first-down rate (+2.6pp even — too high, not too low), but drives do not convert to
TDs at the correct rate. The extra first downs extend drives without advancing deep
enough into the red zone. This is the difference between correct PLAY statistics
and correct DRIVE outcomes, and it requires either:
- A yards-per-play adjustment keyed to field position (Phase 2B), or
- The player-layer contributions that differentiate red-zone efficiency (Phase 2B), or
- An independent red-zone scoring model (not empirical play tables)

### P(|margin|=3) gap (9.0% vs 14.5%)

The NFL's margin=3 spike is driven by:
1. FG-decided games (one team kicks a late FG to win by 3 or tie → OT → win by 3)
2. Game-management decisions ("take the points" when down ≤3)

The sim's FG att/game (3.54) is 10% below actual (3.92). With fewer FGs, fewer games
end at margin=3. The fine-grained 4th-down table (10-yard bins × 7 score × 4 clock)
correctly models the "kick to tie" decision but cannot compensate for fewer drives
reaching FG range. This is the same TD/drive gap: drives that should advance to the
opp 20-40 (FG range) are stalling or ending in turnovers earlier.

---

## 4. Changes This Session

| Change | Mechanism |
|--------|-----------|
| **REVERT: pts/team tolerance** | Restored ±1.5 (was incorrectly widened to ±3) |
| **REVERT: matchup mechanism** | Restored success/fail yards split with D6 tilt; previous session's upper-tail-compression claim was a mathematical error |
| 10-yard field-zone bins (table E) | 10 zones (own1-10 through opp1-10) × 7 score × 4 clock × 4 ydstogo; 4-level fallback; min_n=10 |
| Retained: punt/KO return TDs | From table G empirical rates (0.00245/punt, 0.00246/kickoff) |
| Retained: fine score/clock states | 7 score states × 4 Q4 clock periods for late-game decisions |
| Retained: improved kneel-out | Accounts for ~1 opponent timeout |

---

## 5. Statement on Data Seasons

All tables, ratings, and diagnostics use **2021–2024 regular season data only**
(weeks 1–18). The 2025 season is the designated holdout and was not used in any
table build, rating computation, simulation, or evaluation. The 2026 season does
not exist in the PBP data.

---

## 6. K1 Status

**K1 was NOT run** because two of three pre-K1 gates fail:
- pts/team: 19.6 (need ≥20.9) — **FAIL**
- corr(sim margin, spread): 0.771 (need ≥0.75) — **PASS**
- P(|margin|=3): 9.0% (need ≥11.5%) — **FAIL**

The residual is documented in §3. No constants were added. No tolerances were widened.
Phase 2B is required for the TD/drive deficit and the P(|margin|=3) gap.
