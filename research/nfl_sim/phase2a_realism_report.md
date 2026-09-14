# Phase 2A: Vectorised Play-Level Engine — Realism Report

**Data:** 2021–2024 regular season only (weeks 1–18). **2025 and 2026 were NOT used** in
tables, ratings, or any simulation. The 2025 season is the designated holdout.

---

## 0. Reverts (from edfbf6863)

**Tolerance:** pts/team gate restored to ±1.5 of 22.4 (was incorrectly ±3).

**Matchup mechanism:** Restored success/fail yards split with D6 matchup tilt. The
iter-3 session's "upper-tail compression (p95 27 vs 31)" was a mathematical error:
weighted average of quantile values ≠ quantile of mixture. Verified: mixture p95 = 31.5,
unsplit p95 = 31.0 — no compression.

---

## 1. Drive-Stage Localisation (STEP 1)

### (a) Drive start yardline

Actual mean yl100 = 71.2 (own 29). Sim starts kickoff drives at yl100 = 75 (own 25);
punt and turnover starts are dynamic. Actual p10 = yl100 51 (10% of drives start past
midfield from short punts / turnovers).

### (b) Drive outcome by start-yardline bin (actual 2021–2024)

| Start yl100 | N | P(TD) | P(FG) | P(punt) | P(TO) | P(EOH) |
|-------------|---|-------|-------|---------|-------|--------|
| (0,10] | 130 | 0.669 | 0.215 | 0.000 | 0.023 | 0.038 |
| (10,20] | 330 | 0.391 | 0.342 | 0.091 | 0.055 | 0.088 |
| (20,30] | 384 | 0.430 | 0.385 | 0.013 | 0.029 | 0.107 |
| (30,40] | 10291 | 0.225 | 0.177 | 0.343 | 0.131 | 0.076 |
| (40,50] | 862 | 0.304 | 0.273 | 0.194 | 0.082 | 0.095 |
| (50,60] | 1475 | 0.278 | 0.228 | 0.276 | 0.104 | 0.068 |
| (60,70] | 2149 | 0.234 | 0.203 | 0.361 | 0.105 | 0.054 |
| (70,80] | 3052 | 0.199 | 0.166 | 0.412 | 0.111 | 0.072 |
| (80,90] | 2432 | 0.166 | 0.125 | 0.485 | 0.134 | 0.065 |
| (90,100] | 1465 | 0.170 | 0.096 | 0.474 | 0.129 | 0.098 |

**Sim vs actual overall drive outcomes:**

| Outcome | Actual | Sim | Gap |
|---------|--------|-----|-----|
| P(TD) | 0.227 | 0.204 | −0.023 |
| P(FG att) | 0.180 | 0.166 | −0.014 |
| P(punt) | 0.356 | 0.362 | +0.006 |
| P(TO) | 0.119 | 0.111 | −0.009 |

TD deficit is present at every start-bin → **per-drive compounding, not field position**.

### (d) Red zone

- Actual RZ trips/game: 6.4
- Actual P(off TD | RZ trip): 0.574
- Goal-to-go: yl=1 → 56.3% TD rate; yl=5 → 29.2%; yl=10 → 17.1%

### (e) TD/drive by team quality quintile (pass_off success, actual)

| Quintile | N drives | P(TD) |
|----------|---------|-------|
| Q1 (worst) | 5122 | 0.180 |
| Q2 | 4214 | 0.197 |
| Q3 | 4190 | 0.221 |
| Q4 | 4202 | 0.252 |
| Q5 (best) | 4842 | 0.289 |

Spread: 10.9pp from Q1 to Q5. Before STEP 2, the sim's SD of mean margin was 3.03
vs closing-spread SD 5.68 — **team compression was the dominant divergence**.

### (f) Differentiation (100 games × 500 sims, after STEP 2)

| Metric | Before D6 shift | After D6 shift | Target |
|--------|----------------|----------------|--------|
| SD sim mean margin | 3.03 | **6.23** | spread SD 5.89 |
| SD sim mean total | 2.36 | **5.71** | actual total SD ~13 |
| corr(sim margin, spread) | 0.771 | **0.782** | ≥0.75 |

**Diagnosis:** items (b) and (e) diverge. The TD deficit is per-drive (not field-position)
and team-compressed. This pointed to STEP 2's D6 additive EPA component.

---

## 2. STEP 2: D6 Additive EPA Component

### Mechanism

The fitted slope S = **5.20 yards per EPA unit** (weighted OLS of `yards_gained` on `epa`
within each (down × distance × field_zone) situation bucket, 45 buckets, 2021–2024 PBP).

| Bucket | Slope | N |
|--------|-------|---|
| 1st-long midfield | 6.10 | 25103 |
| 2nd-med midfield | 5.40 | 6575 |
| 3rd-long midfield | 4.53 | 4715 |
| 1st-long rz10 | 2.96 | 1064 |
| 1st-long opp20 | 4.05 | 4234 |

For each play, after the success/fail class draw and quantile yards draw:

    Δ = (off_unit_epa + def_unit_epa − league_epa) × S

(`def_unit_epa` is opponents' EPA against this defense: positive = bad defense.
Additive because both terms measure EPA from the offensive perspective.)

Clamped: shifted yards ≤ yardline_100 (goal-line cap), ≥ −15 pass / −10 rush (floor).

### Results

| Gate | Before | After | Threshold | Status |
|------|--------|-------|-----------|--------|
| corr(sim margin, spread) | 0.771 | **0.782** | ≥0.75 | **PASS** |
| SD sim mean margin | 3.03 | **6.23** | ~6 | improved |
| SD sim mean total | 2.36 | **5.71** | ~13 | improved |
| pts/team | 19.6 | **19.8** | ±1.5 of 22.4 | **FAIL** |
| P(\|margin\|=3) | 9.0% | **8.3%** | ±3pp of 14.5% | **FAIL** |

The D6 additive EPA component **fixed team compression** (SD 3.03 → 6.23, exceeding
closing-spread SD 5.89) and **maintained corr** (0.782). It did NOT close the pts/team
or P(|margin|=3) gaps — those are separate structural residuals.

---

## 3. Residual: What Was Fixed and What Remains

### Fixed this session

1. **Team compression** — SD sim mean margin went from 3.03 to 6.23 (target ~6).
   Root cause was that the only matchup tilt was on success/fail probability (log5);
   per-play yards had no team component. The D6 additive EPA shift (S=5.20, fitted)
   restored team differentiation.

2. **corr with spread** — maintained at 0.782 with the EPA shift, exceeding the ≥0.75
   gate. The corrected sign convention (off + def − league, not off − def) was critical.

### Remains (for Jeff/Cowork to decide whether to proceed to Phase 2B)

1. **pts/team = 19.8 vs 22.4 (gap −2.6, gate ±1.5)** — The 2.6 pts/team gap is from
   TD/drive = 0.204 vs actual 0.229 (−11%) and FG att/game = 3.51 vs 3.92. The
   EPA shift is zero-mean across matchups so it cannot raise the league-average scoring
   level. The gap requires either:
   - A change to the play-level tables (red-zone quantile resolution, more pass/rush
     bins inside the 10)
   - The player-layer contributions (Phase 2B) adding individual skill effects
   - An explicit field-position-aware yards adjustment (not a constant — would need
     a fitted model or finer situational tables)

2. **P(|margin|=3) = 8.3% vs 14.5% (gap −6.2pp, gate ±3pp)** — Follows from the
   FG deficit (3.51 vs 3.92/game). With fewer total FGs, fewer games are decided by
   exactly 3. This is downstream of the TD/drive gap: drives that should reach FG
   range (opp 20–40) are ending in punts or turnovers instead.

---

## 4. Statement on Data Seasons

All tables, ratings, and diagnostics use **2021–2024 regular season data only**
(weeks 1–18). The 2025 season is the designated holdout and was not used in any
table build, rating computation, simulation, or evaluation. The 2026 season does
not exist in the PBP data.

---

## 5. K1 Status

**K1 was NOT run** — two of three pre-K1 gates fail:
- pts/team: 19.8 (need ≥20.9) — **FAIL**
- corr(sim margin, spread): 0.782 (need ≥0.75) — **PASS**
- P(|margin|=3): 8.3% (need ≥11.5%) — **FAIL**

K1 can be run as **provisional** (accepting the pts/team and |margin|=3 failures as
known residuals) if Jeff decides to proceed to Phase 2B anchoring with these documented
limitations. The team-differentiation axis is now calibrated (SD 6.23 vs spread SD 5.89).
