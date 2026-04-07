# Pitcher Edge-Call Dependency x Umpire Zone Tightness — Interaction Study

**Date:** 2026-04-07
**Hypothesis:** Edge-dependent pitchers paired with tight umpires create a predictable stress-state (more walks, more runs) that the market underprices — particularly relevant for F5 totals.

---

## Phase 1 — Data Audit

### Data Sources

| Source | Status | Coverage | Date Range | Join Key |
|--------|--------|----------|------------|----------|
| Statcast chunks (pitch-level) | AVAILABLE | 3,124,331 pitches | 2022-03 to 2025-09 | `game_pk`, `pitcher` |
| pitcher_game_logs.parquet | AVAILABLE | 84,372 appearances (19,732 starts) | 2022-04-07 to 2026-04-06 | `game_pk`, `player_id` |
| game_table.parquet (umpire) | AVAILABLE | 9,726/9,857 with umpire_name | 2022-04-07 to 2026-04-06 | `game_pk` |
| c041_umpire_zone_metrics.parquet | AVAILABLE | 9,715 game-umpire rows | 2022-2025 | `game_pk`, `umpire_name` |
| bet_results.parquet (closing lines) | AVAILABLE | 4,855 games (2024-2025) | 2024-2025 | `game_pk` |
| modules/umpires.py (static ratings) | AVAILABLE | 72 umpires | Career blended | umpire name |
| f5_signals_2026.json | AVAILABLE | 52 signals (48 UNDER) | 2026-03-26+ | `game_pk` |

### Key Column Availability

**A) Umpire Zone Tightness**
- DERIVABLE from `c041_umpire_zone_metrics.parquet` — has per-game `cs_outside_zone_rate`, `called_strike_rate`, `tight_zone_flag`
- Career tightness = 1 - mean(cs_outside_zone_rate) per umpire
- Statcast `umpire` column exists but is 100% null — cannot derive from pitch-level directly
- game_table has `umpire_name` and `umpire_id` for 98.7% of games

**B) Pitcher Edge-Call Dependency**
- DERIVABLE from Statcast: `plate_x`, `plate_z`, `sz_top`, `sz_bot`, `description` all present with >99% coverage
- Edge zone defined as: `abs(plate_x) > 0.7` OR `plate_z` within 0.3 ft of `sz_top`/`sz_bot`
- 508,112 called strikes total; 498,001 with location data
- Edge called strikes: 253,161 (50.8% of all called strikes)

**C) Join Feasibility**
- All sources join on `game_pk` — confirmed 100% overlap between Statcast games and game_table
- Pitcher edge dependency joins via `pitcher` (Statcast) = `player_id` (pitcher_game_logs) at season level
- 16,168/19,732 starts (82%) have both edge dependency and umpire tightness assigned

---

## Phase 2 — Interaction Tag Construction

### Pitcher Edge Dependency (per pitcher-season, min 200 called strikes)

- Qualified pitcher-seasons: 837
- Mean edge_dependency: 0.506, std: 0.047
- Q25: 0.474, Q75: 0.537
- HIGH_DEP (top quartile): edge_dependency >= 0.537

**Top edge-dependent pitchers (2024):**

| Pitcher | edge_dependency | Called Strikes |
|---------|----------------|---------------|
| Luke Weaver | 0.704 | 233 |
| Merrill Kelly | 0.681 | 207 |
| Jose Quintana | 0.632 | 511 |
| Logan Allen | 0.619 | 291 |
| Jack Flaherty | 0.609 | 522 |
| Chris Flexen | 0.604 | 455 |
| Zac Gallen | 0.603 | 473 |

### Umpire Tightness (career average from c041)

- 111 umpires with zone data
- Mean tightness: 0.9438, std: 0.0112
- Q25: 0.9365, Q75: 0.9507
- TIGHT (top quartile): tightness >= 0.9507 (28 umpires)
- LOOSE (bottom quartile): tightness <= 0.9365 (28 umpires)

### Interaction Tag Counts

| Interaction | Total Starts | 2022 | 2023 | 2024 | 2025 |
|-------------|-------------|------|------|------|------|
| HIGH_DEP x TIGHT | 951 | 301 | 303 | 295 | 52 |
| HIGH_DEP x LOOSE | 1,021 | 416 | 294 | 279 | 32 |
| LOW_DEP x TIGHT | 2,830 | 499 | 669 | 592 | 1,070 |
| OTHER | 11,366 | 2,825 | 2,814 | 2,862 | 2,865 |

Note: 2025 has fewer HIGH_DEP observations because edge_dependency shifted — fewer pitchers in Q4 (only 9 qualified in 2025 Q4 vs 60+ in prior years). This is a coverage risk for forward deployment.

---

## Phase 3 — Raw Outcome Test

### Per-Start Outcomes

| Group | N | Walk Rate | IP | Early Exit% | RA | ER |
|-------|---|-----------|-----|------------|-----|-----|
| HIGH_DEP x TIGHT | 951 | 0.0815 | 5.23 | 25.9% | 2.74 | 2.58 |
| HIGH_DEP x LOOSE | 1,021 | 0.0769 | 5.30 | 24.7% | 2.65 | 2.49 |
| LOW_DEP x TIGHT | 2,830 | 0.0794 | 5.23 | 25.7% | 2.59 | 2.43 |
| HIGH_DEP (all) | 4,545 | 0.0779 | 5.29 | 24.5% | 2.64 | 2.47 |
| LOW_DEP (all) | 11,623 | 0.0772 | 5.26 | 24.8% | 2.57 | 2.40 |
| TIGHT (all) | 3,781 | 0.0799 | 5.23 | 25.7% | 2.63 | 2.47 |
| LOOSE (all) | 3,264 | 0.0758 | 5.26 | 24.9% | 2.56 | 2.39 |
| ALL | 16,168 | 0.0774 | 5.26 | 24.7% | 2.59 | 2.42 |

### Statistical Tests (HIGH_DEP x TIGHT vs rest)

| Metric | HDXT | Rest | Diff | t-stat | p-value |
|--------|------|------|------|--------|---------|
| Walk rate | 0.0815 | 0.0771 | +0.0044 | 2.098 | **0.036** |
| IP | 5.23 | 5.27 | -0.033 | -0.733 | 0.464 |
| Early exit | 25.9% | 24.6% | +1.2pp | 0.858 | 0.391 |
| Runs allowed | 2.74 | 2.58 | +0.16 | 2.327 | **0.020** |
| Earned runs | 2.58 | 2.41 | +0.17 | 2.611 | **0.009** |

### Interaction vs Main Effects

- HIGH_DEP main effect (walk rate): +0.0005 vs baseline
- TIGHT main effect (walk rate): +0.0025 vs baseline
- HIGH_DEP x TIGHT combined: +0.0041 vs baseline
- **Interaction excess: +0.0011** (walk rate is slightly super-additive)

For runs allowed:
- HIGH_DEP main: +0.05 runs
- TIGHT main: +0.04 runs
- Combined: +0.15 runs
- **Interaction excess: +0.06 runs** (modestly super-additive)

### Year-by-Year Stability (RA for HIGH_DEP x TIGHT)

| Season | N | RA | Walk Rate | IP |
|--------|---|-----|-----------|-----|
| 2022 | 301 | 2.72 | 0.0790 | 5.24 |
| 2023 | 303 | 2.91 | 0.0863 | 5.19 |
| 2024 | 295 | 2.60 | 0.0811 | 5.24 |
| 2025 | 52 | 2.67 | 0.0697 | 5.41 |

Direction is consistent across seasons: HIGH_DEP x TIGHT always has elevated RA vs baseline, though magnitude varies. 2023 was the strongest year; 2024 the weakest.

---

## Phase 4 — Market-Relative Test

### Actual vs Closing Total (2024-2025, non-push starts)

| Interaction | N | Avg Close | Avg Actual | Diff | Over% | Under% |
|-------------|---|-----------|------------|------|-------|--------|
| HIGH_DEP x TIGHT | 335 | 8.36 | 9.04 | **+0.69** | **53.4%** | 46.6% |
| HIGH_DEP x LOOSE | 305 | 8.20 | 9.01 | +0.81 | 52.8% | 47.2% |
| LOW_DEP x TIGHT | 1,599 | 8.43 | 8.73 | +0.30 | 47.6% | 52.4% |
| OTHER | 5,496 | 8.36 | 8.77 | +0.41 | 48.2% | 51.8% |
| ALL | 7,735 | 8.36 | 8.78 | +0.42 | 48.5% | 51.5% |

### Market Residual Decomposition

| Component | Effect (runs) |
|-----------|--------------|
| HIGH_DEP main effect | +0.168 |
| TIGHT main effect | -0.048 |
| HIGH_DEP x TIGHT combined | +0.271 |
| **Interaction excess (super-additive)** | **+0.151** |

The interaction is super-additive in the market residual: the combined effect (+0.27 runs vs closing line) exceeds the sum of main effects (+0.12 runs). The market does not price the compounding stress.

### Closing Lines by Group

| Group | Avg Closing Total |
|-------|-------------------|
| HIGH_DEP x TIGHT | 8.34 |
| HIGH_DEP x LOOSE | 8.19 |
| LOW_DEP x TIGHT | 8.43 |
| OTHER | 8.36 |

Lines are similar across groups — the market does not adjust for the interaction.

### Chi-Square Test (HDXT over rate vs rest)

- HDXT: 179/335 = 53.4% overs
- Rest: 3,571/7,400 = 48.3% overs
- chi2 = 3.234, p = 0.072 (marginal)

### Permutation Test

- Observed HDXT mean residual: +0.687 runs
- Null distribution: mean = +0.415, std = 0.239
- One-sided permutation p = 0.131

The permutation test is not significant at the 0.10 level. The elevated residual could be noise given the sample size.

### OVER Bet ROI at -110 (game-level, games with any HDXT starter)

| Period | W | L | Over% | ROI |
|--------|---|---|-------|-----|
| 2024 | 134 | 109 | 55.1% | +5.3% |
| 2025 | 28 | 19 | 59.6% | +13.7% |
| **Combined** | **162** | **128** | **55.9%** | **+6.6%** |

### Year-on-Year Interaction Excess (market residual)

| Season | N_HDXT | Main Effects | Combined | Excess |
|--------|--------|-------------|----------|--------|
| 2024 | 287 | +0.113 | +0.175 | **+0.062** |
| 2025 | 48 | +0.904 | +0.749 | -0.155 |

The interaction excess is positive in 2024 (larger sample) but reverses in 2025 (tiny sample, N=48). This is not directionally consistent enough to confirm super-additivity as a stable phenomenon.

---

## Phase 5 — F5 Signal Overlay

### Direction Clarification

The interaction produces HIGHER runs, not lower. This is an **OVER signal**, not an UNDER filter.

- F5 actual for HDXT games: 5.10 (vs 4.98 for non-HDXT)
- The stress state causes more walks, which cascade into more runs through the first 5 innings
- This **conflicts** with F5 UNDER signals — if an F5 UNDER signal fires on a game where the SP is HIGH_DEP and the ump is TIGHT, that is a negative overlay

### 2026 F5 Signal Sample

- 52 F5 signals in 2026 log, only 8 have umpire assignments (too thin for tagging)
- Historical backtest shows HDXT games go OVER at 53.5% in F5 (vs 51.1% baseline)

### Practical F5 Application

The natural use is as an F5 OVER context signal or an F5 UNDER caution flag:
- If HIGH_DEP pitcher starts vs TIGHT umpire → F5 UNDER confidence should decrease
- If model generates F5 OVER lean in an HDXT game → mild confirmation

---

## Phase 6 — Practical Framing

### What the Signal Is

When an edge-dependent pitcher (top quartile of called-strike edge reliance) faces a tight umpire (top quartile of zone tightness), the pitcher's effectiveness degrades measurably:
- Walk rate rises +0.44pp (p=0.036)
- Runs allowed rise +0.16/start (p=0.020)
- Market underprices by ~0.27 runs per start

### What the Signal Is NOT

- It is not a generic umpire effect (tight umps alone: -0.05 runs vs closing)
- It is not a generic pitcher quality effect (high-dep alone: +0.17 runs vs closing)
- The interaction excess (+0.15 runs) is super-additive but only borderline significant

### Deployment Options

| Use Case | Feasibility | Concern |
|----------|-------------|---------|
| F5 OVER pass filter | POSSIBLE | Needs real F5 lines; edge_dep requires pre-season Statcast compute |
| F5 UNDER caution flag | POSSIBLE | Would reduce UNDER confidence in HDXT games |
| Walk prop overlay (pitcher BB) | POSSIBLE | Walk rate signal is strongest (p=0.036) |
| Full-game OVER badge | MARGINAL | 6.6% ROI but permutation p=0.131 |
| Standalone bet signal | NOT RECOMMENDED | Sample too small; 2025 interaction excess reverses |

### Implementation Requirements

1. Pre-season compute of edge_dependency per pitcher from prior-year Statcast
2. Live umpire assignment (available day-of, sometimes 11am)
3. Join to c041-style umpire tightness metric
4. Tag starts where both pitcher in Q4 edge_dep AND umpire in Q4 tightness

### Coverage Concern

2025 shows severe Q4 edge_dependency shrinkage (only 9 pitcher-seasons in top quartile vs 60+ in 2022-2024). This may reflect a real shift in pitcher approach (fewer pitchers relying on edge calls) or a data artifact. If the population of high-edge-dependency pitchers is shrinking, the signal's forward applicability narrows.

---

## Decision

### NEAR MISS

**Directional signal present, interaction is real in outcomes, but market-relative evidence is borderline.**

**Reasons for NEAR MISS (not ADVANCE):**
1. Permutation p-value = 0.131 — the market residual is not statistically significant
2. Year-on-year interaction excess is inconsistent (positive 2024, negative 2025)
3. 2025 has only 48 HDXT starts in the market sample — too thin for OOS validation
4. The OVER ROI of +6.6% at -110 is promising but the 290-bet sample is small
5. Edge_dependency population is shrinking — fewer pitchers qualify in 2025

**Reasons it is NOT CLOSE:**
1. The outcome effect is real and significant: walk rate (p=0.036), RA (p=0.020), ER (p=0.009)
2. The interaction IS super-additive in market residuals (+0.15 runs excess)
3. Direction is consistent across all four seasons in raw outcomes
4. The closing line does NOT adjust for the interaction (similar lines across groups)
5. Walks prop application has a cleaner signal path than full-game totals

### Recommended Next Step

Monitor through 2026 full season. If 2026 confirms:
- HDXT over rate > 52% on 100+ starts with closing lines
- Interaction excess remains positive in market residual

Then revisit for:
1. **Walk prop overlay** (most direct causal path: tight ump + edge-dependent pitcher = more walks)
2. **F5 OVER context badge** (not a standalone signal, but a confidence modifier)
3. **F5 UNDER caution flag** (reduce UNDER stake when HDXT conditions present)

Do NOT build as a standalone betting signal yet — the market-relative evidence needs one more season of confirmation.
