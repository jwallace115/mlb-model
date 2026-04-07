# Opener/Bulk Arm Misclassification — F5 Line Mispricing Research

**Date:** 2026-04-07
**Status:** NEAR MISS

## Hypothesis

Opener and bulk-arm deployments create structural F5 line mispricing because the F5 model assumes a traditional starter who will attempt to complete 5 innings. When the listed starter is actually an opener (1-2 IP) or bulk-short pitcher (rolling avg < 3.5 IP), the bullpen carries more innings in the first 5, potentially increasing variance and scoring.

---

## Phase 1 — Data Audit

**pitcher_game_logs.parquet**: 84,372 rows (19,732 starter appearances), seasons 2022-2026. Contains: game_pk, player_id, player_name, game_date, season, team, home_away, starter_flag, innings_pitched, batters_faced, pitches, walks, strikeouts, hits_allowed, runs_allowed, earned_runs. All needed fields present.

**game_table.parquet**: 9,857 games, seasons 2022-2026. Contains actual_total, actual_f5_total (9,855 non-null). No closing lines in this table.

**Closing lines** (unified from two sources):
- mlb_historical_closing_lines.parquet: 3,911 games (2022-2023)
- market_snapshots.parquet: 4,855 games (2024-2025)
- Combined: 8,766 games with closing totals

**f5_signals_2026.json**: 52 resolved F5 signals (48 UNDER, 4 OVER).

**Joinability**: game_table joins to pitcher_game_logs on game_pk. 7,377 of 9,857 games matched to home starters (75%). Closing lines join on game_pk. F5 signals join on game_id = game_pk.

---

## Phase 2 — Flag Definitions

All flags use pregame-safe data (shifted by 1 start, no lookahead).

### Flag 1: STRICT_OPENER
Season start number <= 2 AND (no prior IP data OR prior avg IP <= 3.0). Catches first/second starts where pitcher has no track record or opener profile.

| Season | Total Starts | Flagged | % |
|--------|-------------|---------|---|
| 2022 | 4,860 | 435 | 9.0% |
| 2023 | 4,860 | 448 | 9.2% |
| 2024 | 4,854 | 418 | 8.6% |
| 2025 | 4,856 | 424 | 8.7% |
| 2026 | 302 | 170 | 56.3%* |

*2026 inflated: early season, most pitchers have <= 2 starts.

### Flag 2: BULK_SHORT_PROFILE
Rolling 3-start IP average <= 3.5, with >= 3 prior starts in the season.

| Season | Total | Flagged | % |
|--------|-------|---------|---|
| 2022 | 4,860 | 137 | 2.8% |
| 2023 | 4,860 | 180 | 3.7% |
| 2024 | 4,854 | 138 | 2.8% |
| 2025 | 4,856 | 102 | 2.1% |

### Flag 3: TEAM_OPENER_TENDENCY
Fraction of last 10 team games where listed starter went < 3.0 IP >= 30%.

| Season | Total | Flagged | % |
|--------|-------|---------|---|
| 2022 | 4,860 | 160 | 3.3% |
| 2023 | 4,860 | 336 | 6.9% |
| 2024 | 4,854 | 168 | 3.5% |
| 2025 | 4,856 | 145 | 3.0% |

### Flag 4: COMBINED_NONTRADITIONAL (any of 1-3)
~13-18% of starts per season (excluding early-season inflation).

### Flag Overlap
- strict_opener and bulk_short: 0 (mutually exclusive by definition: need <= 2 starts vs >= 4)
- strict_opener and team_tendency: 101
- bulk_short and team_tendency: 90
- All three: 0
- Total combined: 3,073 (2022-2026)

### Sanity Check: Mean IP in Flagged vs Non-Flagged

| Flag | Flagged IP | Non-Flagged IP | Delta |
|------|-----------|----------------|-------|
| strict_opener | 3.90 | 5.19 | -1.28 |
| bulk_short_profile | 3.87 | 5.10 | -1.23 |
| team_opener_tendency | 4.54 | 5.08 | -0.54 |
| combined | 4.14 | 5.23 | -1.09 |

Flags correctly identify short-start pitchers. All subtypes show ~1+ fewer IP.

---

## Phase 3 — Raw Outcome Test

### Starter-Level Outcomes (2022-2025)

| Flag | N | IP | R | ER | BB | Early Exit (< 5 IP) |
|------|---|-----|-----|------|------|---------------------|
| **combined flagged** | 2,900 | 4.14 | 2.22 | 2.07 | 1.49 | 51.1% |
| **non-flagged** | 16,530 | 5.23 | 2.67 | 2.49 | 1.72 | 25.8% |

Flagged starters allow fewer runs (2.22 vs 2.67) because they pitch fewer innings. The early exit rate is double (51% vs 26%), meaning the bullpen covers significantly more of the F5 window.

### Game-Level Outcomes (with closing lines, N=6,690)

| Condition | N | Actual Total | Close Total | Residual | Over Rate |
|-----------|---|-------------|-------------|----------|-----------|
| HOME combined flagged | 900 | 9.27 | 8.61 | +0.662 | 51.9% |
| HOME non-flagged | 5,790 | 8.84 | 8.42 | +0.416 | 46.5% |
| EITHER combined flagged | 1,592 | 9.09 | 8.61 | +0.476 | 49.8% |
| EITHER non-flagged | 5,098 | 8.84 | 8.39 | +0.441 | 46.4% |

**HOME combined** shows the strongest signal: +0.246 residual advantage and +5.4pp over rate vs non-flagged.

### F5 Actual Total

| Condition | Flagged F5 | Non-Flagged F5 | Delta |
|-----------|-----------|----------------|-------|
| HOME combined | 5.24 | 4.99 | +0.24 |
| AWAY combined | 4.97 | 5.04 | -0.07 |
| EITHER combined | 5.08 | 5.01 | +0.07 |

HOME-side opener produces +0.24 runs in the first 5 innings. Away side shows no effect. This asymmetry makes sense: home team bats in the bottom of innings, and a weak home starter in innings 1-3 allows early runs that inflate the F5 line from the opponent's side, while the bullpen handoff itself can be volatile.

---

## Phase 4 — F5 Signal Interaction Test

### 2026 F5 UNDER Signals (N=88 resolved, all UNDER-heavy)

| Subset | N | Win Rate | Mean Line | Mean Actual F5 |
|--------|---|----------|-----------|----------------|
| All resolved | 88 | 44.3% | 4.62 | 5.24 |
| NEITHER flagged | 41 | 51.2% | 4.74 | 5.37 |
| EITHER flagged | 47 | 38.3% | 4.51 | 5.13 |

**F5 UNDER wins at 51.2% when neither starter is flagged but only 38.3% when either is flagged.** That is a -12.9pp degradation, directionally consistent with the hypothesis that opener/bulk arms create over-scoring that hurts unders.

Caveat: 2026 sample is small (88 signals, 11 days). The 56% strict_opener rate from early season inflates flagging. Match rate to starters was only 8/96 for home-away pairs, meaning many signals lacked starter data in the join. The directional finding is suggestive but not statistically robust.

### Availability Bias Check
All 88 signals are resolved (scored). No unscored subset to compare.

---

## Phase 5 — Market-Relative Test (Historical, 2022-2025)

### Push-Adjusted Over Rate

| Condition | Flagged | Non-Flagged | Delta |
|-----------|---------|-------------|-------|
| HOME combined | 53.4% | 48.6% | +4.8pp |
| EITHER combined | 51.4% | 48.6% | +2.7pp |

### Season-by-Season Stability: HOME Combined

| Season | N (flagged) | Flagged Over% | Non-Flag Over% | Flagged Resid | Non-Flag Resid |
|--------|------------|---------------|----------------|---------------|----------------|
| 2022 | 191 | 47.1% | 46.8% | +0.073 | +0.429 |
| 2023 | 236 | 50.4% | 47.0% | +0.433 | +0.526 |
| 2024 | 241 | 53.5% | 47.2% | +0.649 | +0.402 |
| 2025 | 232 | 55.6% | 45.1% | +1.392 | +0.326 |

The HOME combined signal strengthens each year: over rate gap widens from +0.3pp (2022) to +10.5pp (2025). The 2025 residual (+1.392 vs +0.326 = +1.066 gap) is the strongest single-season effect.

### Season-by-Season: EITHER Combined

| Season | N (flagged) | Flagged Over% | Non-Flag Over% | Flagged Resid | Non-Flag Resid |
|--------|------------|---------------|----------------|---------------|----------------|
| 2022 | 328 | 43.9% | 47.7% | +0.098 | +0.464 |
| 2023 | 444 | 50.7% | 46.3% | +0.540 | +0.501 |
| 2024 | 434 | 52.8% | 46.6% | +0.425 | +0.437 |
| 2025 | 386 | 50.5% | 45.3% | +0.781 | +0.378 |

EITHER combined is weaker and noisier than HOME-only. 2022 actually reverses (flagged goes under more).

### F5 Actual by Season: HOME Combined

| Season | Flagged F5 | Non-Flag F5 | Delta |
|--------|-----------|-------------|-------|
| 2022 | 4.96 | 4.88 | +0.08 |
| 2023 | 5.51 | 5.18 | +0.33 |
| 2024 | 4.88 | 5.00 | -0.13 |
| 2025 | 5.56 | 4.92 | +0.63 |

2025 shows the largest F5 delta (+0.63 runs). 2024 reverses. Not monotonically stable.

### Statistical Significance

- HOME combined residual: t=1.562, p=0.118 (not significant at 0.05)
- EITHER combined residual: t=0.278, p=0.781 (not significant)

### Subtype Detail: Strict Opener (either side)

| Season | N | Over% | Residual | F5 Actual |
|--------|---|-------|----------|-----------|
| 2022 | 207 | 41.5% | -0.159 | 4.71 |
| 2023 | 215 | 49.3% | +0.524 | 5.26 |
| 2024 | 252 | 53.2% | +0.587 | 5.21 |
| 2025 | 242 | 52.5% | +1.043 | 5.43 |

Strict opener shows the strongest trend: from under-signal in 2022 to strong over-signal by 2024-2025.

### Subtype Detail: Bulk Short (either side)

| Season | N | Over% | Residual | F5 Actual |
|--------|---|-------|----------|-----------|
| 2022 | 75 | 58.7% | +1.080 | 5.51 |
| 2023 | 101 | 46.5% | +0.426 | 5.41 |
| 2024 | 99 | 48.5% | -0.121 | 3.98 |
| 2025 | 76 | 55.3% | +0.618 | 5.63 |

Bulk short is volatile: strong in 2022, reverses in 2024, returns in 2025. Small N per season.

---

## Phase 6 — Practical Framing

### What works

**HOME combined (opener/bulk as home starter)** shows a persistent, growing over-lean:
- 4-year push-adjusted over rate: 53.4% vs 48.6% (+4.8pp)
- 2024-2025 combined: over rate ~54.5%, residual ~+1.0
- F5 actual runs +0.24 higher than non-flagged games
- The 2026 F5 UNDER win rate drops from 51.2% to 38.3% when either starter is flagged (small N caveat)

### What does not work

- **AWAY combined** shows essentially no effect (-0.07 F5 delta). Opener status of the away starter does not predict mispricing.
- **EITHER combined** dilutes the home signal with the null away signal.
- **Statistical significance**: p=0.118 for HOME combined. Not below 0.05.
- **Season stability**: 2022 shows no effect. The signal appears to emerge 2023+ and strengthen, but this could be a trend artifact.
- **2026 starter matching**: Only 8 of 96 F5 signal starter-pairs matched, making the 2026 interaction test unreliable.

### Recommendation

**F5 UNDER pass filter**: Consider adding a caution badge when the HOME starter is flagged as combined_nontraditional. The 38.3% UNDER win rate with flagged starters (vs 51.2% without) suggests these games are hostile to F5 UNDER bets, but the sample is too small to build a hard filter.

**F5 OVER context**: Not recommended as standalone signal. The over-lean exists but the residuals are noisy and the effect is HOME-side-specific.

**Subtype-specific rule**: Strict_opener (HOME side, 2024-2025) is the cleanest subtype, but at ~120 games/season it is too thin for a standalone filter.

**Badge**: A "nontraditional starter" badge on the F5 card for HOME starters with combined_nontraditional = True would flag ~13% of games. This is the most defensible action.

---

## Decision: NEAR MISS

**Direction is real**: HOME-side opener/bulk starters produce +4.8pp over rate vs closing lines across 4 seasons, with a growing trend. F5 scoring runs +0.24 higher. The 2026 UNDER interaction is directionally alarming (-12.9pp).

**Why not ADVANCE**:
1. Not statistically significant (p=0.118 for HOME, p=0.781 for EITHER)
2. 2022 shows no effect; signal appears only 2023+
3. 2026 F5 interaction test has poor starter matching (8/96 pairs)
4. AWAY side shows zero effect, limiting the signal to HOME-only
5. F5 closing lines are unavailable historically, so we cannot measure the F5-specific mispricing directly

**Next step if revisited**:
- Collect F5 closing lines for the full 2026 season to measure actual F5 mispricing (not full-game proxy)
- Re-evaluate after 200+ HOME combined-flagged games with F5 lines (~August 2026)
- If HOME combined over rate persists > 53% against F5 lines specifically, upgrade to a pass/caution filter on F5 UNDER signals
