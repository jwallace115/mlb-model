# Phase 1 — Path-Tree Foundation: Empirical Bullpen Analysis

**Date:** 2026-04-09
**Data:** pitcher_game_logs.parquet + game_table.parquet + market_snapshots.parquet
**Scope:** 7,366 games (2022-2025) with complete starter + reliever pitcher log data

---

## 1. Data Audit

### Available Data
- **pitcher_game_logs:** 83,042 appearances (19,430 starters, 63,612 relievers) across 2022-2025
- **Per reliever:** game_pk, game_date, season, team, innings_pitched, batters_faced, pitches, runs_allowed, earned_runs, walks, strikeouts, starter_flag, home_away
- **Per game:** actual_total, actual_f5_total, home/away scores, closing lines (4,855 games via market_snapshots)
- **Mean relievers per game:** 6.55

### NOT Available
- Inning of entry for each reliever
- Score differential at entry
- Leverage index
- Save/hold situation flags

### Key Limitation
No inning-level reliever entry data. Game-state branch is approximated from final margin (post-hoc) and starter IP/RA (partial proxy for handoff point). This is sufficient for structural analysis but limits real-time path-tree simulation without play-by-play augmentation.

### Data Join Quality
- 7,366 / 9,715 games (75.8%) matched with complete starter + reliever data on both sides
- Implied reliever RA (actual_total minus starter RA) matches direct reliever RA exactly (mean diff = 0.000), confirming data integrity
- 3,640 games also have DraftKings closing lines for market residual analysis

---

## 2. Usage Tree by Branch

Branch defined by final home margin (home team perspective):

| Branch | N | Pct | Home Rel IP | Away Rel IP | Total Rel IP | Home Relievers | Away Relievers | Rel RA/IP |
|---|---|---|---|---|---|---|---|---|
| BLOWOUT_WIN (+5) | 1,048 | 14.2% | 2.98 | 3.43 | 6.41 | 2.73 | 3.03 | 0.755 |
| COMFORTABLE_WIN (+3-4) | 957 | 13.0% | 3.03 | 2.86 | 5.89 | 3.21 | 2.85 | 0.513 |
| CLOSE_WIN (+1-2) | 1,976 | 26.8% | 3.32 | 2.77 | 6.09 | 3.50 | 3.13 | 0.478 |
| CLOSE_LOSS (-1-2) | 1,453 | 19.7% | 3.54 | 3.42 | 6.97 | 3.58 | 3.71 | 0.452 |
| COMFORTABLE_LOSS (-3-4) | 919 | 12.5% | 3.79 | 3.22 | 7.01 | 3.46 | 3.41 | 0.519 |
| BLOWOUT_LOSS (-5) | 1,013 | 13.8% | 4.14 | 3.16 | 7.30 | 3.43 | 2.80 | 0.732 |

### Key Structural Findings

**Reliever IP increases in losses.** The home team uses 2.98 reliever IP in blowout wins vs 4.14 in blowout losses (+1.16 IP). This reflects earlier starter exits when the home team is behind.

**Blowout games produce 60-65% more reliever RA/IP.** Close games: 0.452-0.478 RA/IP; blowout games: 0.732-0.755 RA/IP. This is a massive rate difference, not just exposure.

**Total reliever IP is highest in losses.** Close losses (6.97 IP) and blowout losses (7.30 IP) vs close wins (6.09 IP). Losing teams burn more bullpen arms.

### Runs Context

| Branch | Actual Total | Starter RA | Reliever RA | Reliever % of Total | F5 Total |
|---|---|---|---|---|---|
| BLOWOUT_WIN | 11.13 | 6.29 | 4.84 | 43.5% | 6.66 |
| COMFORTABLE_WIN | 8.29 | 5.27 | 3.03 | 36.5% | 4.98 |
| CLOSE_WIN | 7.48 | 4.57 | 2.91 | 38.9% | 4.17 |
| CLOSE_LOSS | 7.81 | 4.66 | 3.15 | 40.3% | 4.23 |
| COMFORTABLE_LOSS | 8.86 | 5.22 | 3.64 | 41.1% | 4.93 |
| BLOWOUT_LOSS | 11.51 | 6.17 | 5.34 | 46.4% | 6.29 |

Reliever-phase runs account for 36-46% of total scoring depending on game flow. In blowout losses, relievers allow 5.34 runs per game vs 2.91 in close wins.

---

## 3. Reliever Chain Quality by Branch

Pregame-safe quality proxy: expanding (shifted-by-1) K-rate and ERA per reliever, requiring minimum 5 prior BF.

### Combined (All Relievers)

| Branch | N Apps | Mean K-Rate | Mean ERA | Median ERA |
|---|---|---|---|---|
| BLOWOUT_WIN | 5,965 | 0.231 | 4.97 | 4.21 |
| COMFORTABLE_WIN | 5,752 | 0.248 | 4.30 | 3.87 |
| CLOSE_WIN | 13,031 | 0.256 | 3.99 | 3.75 |
| CLOSE_LOSS | 10,526 | 0.255 | 4.04 | 3.74 |
| COMFORTABLE_LOSS | 6,265 | 0.249 | 4.35 | 3.88 |
| BLOWOUT_LOSS | 6,230 | 0.230 | 4.86 | 4.17 |

### Home Team Relievers

| Branch | N Apps | Mean K-Rate | Mean ERA |
|---|---|---|---|
| BLOWOUT_WIN | 2,839 | 0.243 | 4.29 |
| COMFORTABLE_WIN | 3,055 | 0.263 | 3.89 |
| CLOSE_WIN | 6,887 | 0.265 | 3.81 |
| CLOSE_LOSS | 5,168 | 0.248 | 4.21 |
| COMFORTABLE_LOSS | 3,151 | 0.238 | 4.85 |
| BLOWOUT_LOSS | 3,419 | 0.222 | 5.13 |

### Away Team Relievers

| Branch | N Apps | Mean K-Rate | Mean ERA |
|---|---|---|---|
| BLOWOUT_WIN | 3,126 | 0.219 | 5.58 |
| COMFORTABLE_WIN | 2,697 | 0.230 | 4.76 |
| CLOSE_WIN | 6,144 | 0.246 | 4.19 |
| CLOSE_LOSS | 5,358 | 0.262 | 3.86 |
| COMFORTABLE_LOSS | 3,114 | 0.260 | 3.85 |
| BLOWOUT_LOSS | 2,811 | 0.240 | 4.53 |

### Key Finding: Deployment is Asymmetric and Branch-Dependent

The home team deploys its best relievers (K-rate 0.265, ERA 3.81) in close wins and its worst (K-rate 0.222, ERA 5.13) in blowout losses. The away team mirrors this: best arms (K-rate 0.262, ERA 3.86) in close losses (where they are competitive) and worst (K-rate 0.219, ERA 5.58) in blowout wins (where they are being blown out, throwing mop-up arms).

This is a genuine structural effect. Managers deploy high-leverage arms in competitive situations and mop-up arms in blowout situations.

---

## 4. Reliever-Phase Runs Distribution

| Branch | Mean Rel RA | Std Rel RA | P(RelRA > 5) | P(RelRA > 7) | Mean Total Rel IP |
|---|---|---|---|---|---|
| BLOWOUT_WIN | 4.84 | 3.35 | 37.5% | 18.8% | 6.41 |
| COMFORTABLE_WIN | 3.03 | 2.68 | 15.6% | 6.6% | 5.89 |
| CLOSE_WIN | 2.91 | 2.68 | 15.4% | 6.3% | 6.09 |
| CLOSE_LOSS | 3.15 | 2.86 | 18.9% | 8.3% | 6.97 |
| COMFORTABLE_LOSS | 3.64 | 2.89 | 22.3% | 9.9% | 7.01 |
| BLOWOUT_LOSS | 5.34 | 3.47 | 41.8% | 22.3% | 7.30 |

Blowout games produce extreme reliever scoring at 3x the rate of close games (40% vs 15% chance of 5+ reliever runs). This tail behavior is critical for simulation accuracy.

---

## 5. Blowout Test: Rate vs Exposure Decomposition

| Category | N | Rel IP | Rel RA | RA/IP | Relievers |
|---|---|---|---|---|---|
| CLOSE (margin 1-2) | 3,429 | 6.46 | 3.01 | 0.466 | 6.91 |
| COMFORTABLE (margin 3-4) | 1,876 | 6.44 | 3.33 | 0.517 | 6.46 |
| BLOWOUT (margin 5+) | 2,061 | 6.85 | 5.09 | 0.743 | 5.99 |

### Decomposition

- **Actual blowout reliever RA/game:** 5.09
- **If blowout IP at close-game rate:** 3.19
- **Exposure effect** (extra IP x close rate): **0.18 runs** (9% of gap)
- **Rate effect** (worse pitchers x blowout IP): **1.90 runs** (91% of gap)
- **Total gap:** 2.07 runs

**The effect is overwhelmingly rate-driven, not exposure-driven.** Only 9% of the blowout-vs-close gap is explained by more innings pitched. 91% comes from materially worse relievers being deployed in blowout situations. This confirms genuine structural content in the bullpen deployment tree.

---

## 6. Market Proxy

### Branch Residuals (3,640 games with DK closing lines)

| Branch | N | Close Total | Actual Total | Residual | Late Runs | Rel RA |
|---|---|---|---|---|---|---|
| BLOWOUT_WIN | 539 | 8.38 | 10.86 | +2.47 | 4.47 | 4.70 |
| COMFORTABLE_WIN | 454 | 8.39 | 8.25 | -0.14 | 3.26 | 2.94 |
| CLOSE_WIN | 991 | 8.31 | 7.40 | -0.92 | 3.24 | 2.88 |
| CLOSE_LOSS | 695 | 8.45 | 7.78 | -0.67 | 3.58 | 3.16 |
| COMFORTABLE_LOSS | 454 | 8.44 | 8.92 | +0.48 | 3.92 | 3.67 |
| BLOWOUT_LOSS | 507 | 8.57 | 11.57 | +3.00 | 5.34 | 5.39 |

Overall market residual: mean = +0.449, std = 4.395 (slight over bias in this sample period)

### Pregame Bullpen K-Rate Signal

IP-weighted pregame K-rate (expanding, shifted-by-1) correlations:
- vs actual_total: **r = -0.243**
- vs reliever RA: r = -0.177
- vs market residual: **r = -0.221**

### Quintile Analysis (IP-weighted pregame bullpen K-rate)

| Quintile | N | Mean K-Rate | Actual Total | Residual | Rel RA |
|---|---|---|---|---|---|
| Q1 (weakest BP) | 728 | 0.198 | 10.72 | +2.12 | 4.64 |
| Q2 | 728 | 0.228 | 9.21 | +0.75 | 3.65 |
| Q3 | 728 | 0.244 | 8.78 | +0.35 | 3.58 |
| Q4 | 728 | 0.260 | 8.13 | -0.18 | 3.39 |
| Q5 (strongest BP) | 728 | 0.288 | 7.45 | -0.80 | 3.03 |

**Q1-to-Q5 spread: 3.27 runs actual, 2.92 runs residual.** This is a massive effect. The market does not fully price bullpen quality differences: weak-bullpen games go over by +2.12 runs, strong-bullpen games go under by -0.80 runs.

### Extreme Tails (Bottom 10% vs Top 10%)

- **Bottom 10% (weakest bullpens):** actual total = 10.97, residual = +2.33
- **Top 10% (strongest bullpens):** actual total = 7.30, residual = -0.92
- **Gap: 3.67 runs actual, 3.25 runs residual**

### Relationship to Existing Phase 9 Features

The Phase 9 model includes three bullpen feature sets:
- `high_leverage_available` — binary flag for top-3 closers rested
- `bullpen_delta` — workload delta from prior games
- `bp_delta_exposure` — interaction of delta with starter quality

These features capture **fatigue/availability** but do NOT capture **roster quality** (the K-rate signal measured here). The r = -0.221 correlation with market residual represents a distinct, orthogonal signal that Phase 9 does not currently model. This is the primary opportunity.

---

## 7. Season Stability

| Season | Blowout % | Close % | RA/IP (Blowout) | RA/IP (Close) | Rate Diff |
|---|---|---|---|---|---|
| 2022 | 26.7% | 47.6% | 0.706 | 0.464 | 0.242 |
| 2023 | 27.8% | 46.0% | 0.759 | 0.480 | 0.279 |
| 2024 | 28.7% | 46.5% | 0.708 | 0.467 | 0.240 |
| 2025 | 28.8% | 46.2% | 0.801 | 0.453 | 0.348 |

The blowout-vs-close rate differential is **stable across all four seasons** (range: 0.240-0.348), confirming this is a structural phenomenon, not a seasonal artifact. The branch distribution is also stable (~28% blowout, ~46% close).

---

## 8. Starter Handoff Analysis

| Branch | Home Starter IP | Away Starter IP | Home Starter RA | Away Starter RA |
|---|---|---|---|---|
| BLOWOUT_WIN | 5.71 | 3.97 | 1.31 | 4.98 |
| COMFORTABLE_WIN | 5.54 | 4.61 | 1.60 | 3.67 |
| CLOSE_WIN | 5.40 | 4.98 | 1.97 | 2.61 |
| CLOSE_LOSS | 5.11 | 5.22 | 2.66 | 2.00 |
| COMFORTABLE_LOSS | 4.71 | 5.36 | 3.45 | 1.78 |
| BLOWOUT_LOSS | 4.25 | 5.56 | 4.76 | 1.40 |

Starter IP defines the handoff point. In blowout wins, the opposing starter goes only 3.97 IP (early exit, high RA). In blowout losses, the home starter goes only 4.25 IP. This creates the asymmetric bullpen deployment: the losing team's bullpen is exposed for more innings with worse arms.

The difference in starter IP between blowout win and blowout loss is 1.46 IP for the home team (5.71 vs 4.25). Combined with the away-side inverse pattern, starter performance is the primary determinant of which bullpen path the game enters.

---

## 9. Verdict

### ADVANCE

The branch structure shows **strong empirical content** across all dimensions:

1. **Rate effect dominates (91% of gap).** The blowout-vs-close differential is primarily driven by worse relievers being deployed, not by more innings. This is actionable because pregame roster quality is observable.

2. **Market mispricing is large.** The Q1-to-Q5 bullpen quality spread produces a 2.92-run residual gap against closing lines. The r = -0.221 correlation with market residual is material and orthogonal to existing Phase 9 features.

3. **Effect is seasonally stable.** The rate differential persists across all four seasons (2022-2025) with consistent magnitude.

4. **Novel signal.** Phase 9 captures bullpen fatigue/availability but not roster quality. The IP-weighted pregame K-rate captures a distinct dimension of bullpen strength.

5. **Asymmetric deployment is observable pregame.** Managers predictably deploy best arms in close games and worst in blowouts. If we can predict which path a game will take (via starter quality, lineup strength, and opening lines as a proxy for expected margin), we can model the expected bullpen deployment quality.

### Recommended Next Steps

- **Phase 2A:** Build a pregame bullpen roster quality metric (IP-weighted K-rate of top-5 relievers by leverage history) and test as a standalone Phase 9 feature addition.
- **Phase 2B:** Model expected game-path probability using opening line spread as the primary branching signal (large favorites more likely to enter blowout path).
- **Phase 2C:** Construct a path-weighted expected reliever RA model that integrates branching probabilities with branch-specific reliever quality deployment patterns.
- **Data augmentation:** Consider Retrosheet play-by-play data for inning-level reliever entry (would enable true path-tree simulation rather than branch approximation).
