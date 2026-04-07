# Command Volatility Regime — Phase 1 Research Report

**Date:** 2026-04-07
**Question:** Does start-to-start command VOLATILITY (instability in walk rate, pitch efficiency) create a distinct distributional state that the market underprices, beyond what command LEVEL (average walk rate) already captures?

---

## Phase 1 — Data Audit

### Sources Used
- `mlb/data/pitcher_game_logs.parquet` — 84,372 rows, 19,732 starter appearances (2022-2026), 741 unique pitchers
- `sim/data/game_table.parquet` — 9,857 games with actual totals
- `sim/data/mlb_historical_closing_lines.parquet` — 3,911 games (2022-2023)
- `sim/data/market_snapshots.parquet` — 4,855 games (2024-2025)
- Combined closing lines: 8,766 games matched to game_table

### Feature Availability
| Feature Family | Source | Status |
|---|---|---|
| Walk rate volatility | pitcher_game_logs (walks, batters_faced) | AVAILABLE |
| Pitch efficiency volatility | pitcher_game_logs (pitches, innings_pitched) | AVAILABLE |
| Zone% volatility | Statcast chunks (31 files, zone col confirmed) | AVAILABLE but not computed (requires ~800MB read) |
| Command floor | Derivable from rolling min/max of walk rate | AVAILABLE |

---

## Phase 2 — Feature Construction

### Method
- Population: starters only, season >= 2022, sorted by (player_id, season, game_date)
- All rolling features shifted by 1 (pregame-safe: uses only prior starts)
- Minimum 5 prior starts required for rolling features
- Final feature set: 13,566 starter appearances with valid rolling5 features

### Features Computed
1. `rolling5_bb_rate_avg` — mean walk rate over last 5 starts (command LEVEL)
2. `rolling5_bb_rate_sd` — std dev of walk rate over last 5 starts (command VOLATILITY)
3. `rolling5_ppi_avg` — mean pitches per inning over last 5 starts
4. `rolling5_ppi_sd` — std dev of pitches per inning over last 5 starts
5. `recent_walk_spike` — 1 if any of last 3 starts had walk_rate > 0.12
6. `command_floor` — max walk rate in last 5 starts (worst recent command)
7. `season_bb_rate` — expanding season mean walk rate (shifted)

### Bucket Definitions
| Bucket | Volatility (bb_rate_sd) | Level (bb_rate_avg) |
|---|---|---|
| LOW / GOOD | <= 0.041 | <= 0.061 |
| MEDIUM / AVERAGE | 0.041 - 0.060 | 0.061 - 0.088 |
| HIGH / POOR | > 0.060 | > 0.088 |

### 3x3 Grid (N per bucket)

| | LOW vol | MEDIUM vol | HIGH vol | Total |
|---|---|---|---|---|
| GOOD command | 2,558 | 1,523 | 442 | 4,523 |
| AVERAGE command | 1,270 | 1,733 | 1,518 | 4,521 |
| POOR command | 694 | 1,266 | 2,562 | 4,522 |
| Total | 4,522 | 4,522 | 4,522 | 13,566 |

### Correlation Between Volatility and Level
- **r = 0.547** — substantial positive correlation
- HIGH volatility breakdown: 56.7% POOR, 33.6% AVERAGE, 9.8% GOOD
- LOW volatility breakdown: 56.6% GOOD, 28.1% AVERAGE, 15.3% POOR
- **PPI volatility correlated with BB volatility at r = 0.279** (partially independent)

**Finding:** Volatility and level are moderately entangled. Over half of HIGH-volatility starts come from POOR-command pitchers. The off-diagonal cells (GOOD command + HIGH vol, POOR command + LOW vol) are small but sufficient for testing (442 and 694).

---

## Phase 3 — Raw Outcome Test

### By Volatility Bucket (unconditional)

| Bucket | N | Runs Allowed | Walks | IP | Early Exit (IP<5) |
|---|---|---|---|---|---|
| LOW | 4,522 | 2.626 | 1.60 | 5.40 | 22.1% |
| MEDIUM | 4,522 | 2.681 | 1.69 | 5.31 | 24.1% |
| HIGH | 4,522 | 2.686 | 1.76 | 5.14 | 27.7% |

Unconditional spread: 0.06 runs between LOW and HIGH. Modest.

### Critical 2x2 Within-Level Comparison

| Level + Vol | N | Runs Allowed | Walks | IP | Early Exit |
|---|---|---|---|---|---|
| GOOD + LOW | 2,558 | 2.633 | 1.44 | 5.46 | 20.4% |
| GOOD + HIGH | 442 | 2.624 | 1.53 | 5.09 | 30.1% |
| AVERAGE + LOW | 1,270 | 2.663 | 1.74 | 5.34 | 24.6% |
| AVERAGE + HIGH | 1,518 | 2.723 | 1.64 | 5.24 | 25.0% |
| POOR + LOW | 694 | 2.532 | 1.93 | 5.27 | 23.6% |
| POOR + HIGH | 2,562 | 2.674 | 1.88 | 5.09 | 28.8% |

**Key finding within GOOD command:** HIGH vol produces nearly identical runs (2.624 vs 2.633) but 10 percentage points more early exits (30.1% vs 20.4%) and 0.37 fewer IP. The runs equalize because volatile good pitchers have good outings mixed with bad ones — the MEAN is flat, but the DISTRIBUTION widens.

**Within POOR command:** HIGH vol produces 0.14 more runs and 5pp more early exits vs LOW vol. Small but directional.

### Interaction Effect Size
- Corr(vol_bucket, runs_allowed): r = 0.012 (p = 0.163, not significant)
- Corr(lvl_bucket, runs_allowed): r = 0.008 (p = 0.367, not significant)
- Partial corr(interaction, runs | main effects): r = 0.003
- **Partial corr(vol, runs | level): r = 0.004**

**Verdict:** Neither volatility nor level has meaningful predictive power for same-start runs allowed. The effect sizes are negligible. This is consistent with the well-known result that single-game pitcher outcomes are extremely noisy.

---

## Phase 4 — Market-Relative Test

### Game-Level Max Volatility vs. Closing Lines (N=3,895)

| Bucket | N | Residual (actual - close) | Over Rate |
|---|---|---|---|
| LOW | 443 | +0.340 | 45.8% |
| MEDIUM | 1,334 | +0.616 | 48.9% |
| HIGH | 2,118 | +0.419 | 46.3% |

### Year-by-Year Residual (HIGH minus LOW)

| Year | HIGH - LOW | Direction |
|---|---|---|
| 2022 | +0.147 | HIGH goes more over |
| 2023 | -0.187 | LOW goes more over |
| 2024 | +0.628 | HIGH goes more over |
| 2025 | -0.436 | LOW goes more over |

**The sign flips every year.** No stable directional signal.

### Within-Level Market Test (OOS 2024-2025, home starter)

| Level + Vol | N | Residual | Over Rate |
|---|---|---|---|
| GOOD + LOW | 422 | +0.409 | 47.4% |
| GOOD + HIGH | 59 | +0.017 | 37.3% |
| AVERAGE + LOW | 189 | +0.638 | 47.6% |
| AVERAGE + HIGH | 203 | +0.562 | 42.9% |
| POOR + LOW | 112 | +0.839 | 51.8% |
| POOR + HIGH | 410 | +0.361 | 47.6% |

**Surprising reversal:** Within every command level, HIGH volatility produces LOWER residuals and LOWER over rates than LOW volatility. This is the opposite of the "volatile pitchers produce chaos / overs" hypothesis. It suggests the market may already overprice volatile pitchers (lines set too low expecting blowups), or the effect is noise.

### Under Hit Rate by Game-Level Max Vol (OOS 2024-2025, non-push)

| Bucket | N | Under Rate |
|---|---|---|
| LOW | 234 | 51.7% |
| MEDIUM | 702 | 50.4% |
| HIGH | 1,084 | 52.4% |

Differences are within noise range (1-2pp). No exploitable spread.

---

## Phase 5 — Signal Interaction Test

### 2026 V1/F5 Signals
- V1 resolved signals: 51 (all UNDER side)
- F5 resolved signals: 52
- **2026 starter volatility features: 0 matched** (season is 11 days old, no starter has 5 prior 2026 starts yet)
- 2026 signal sample is unusable for volatility splits at this time

### 2024-2025 Proxy: Under Hit Rate Within-Level (Home Starter, Non-Push)

| Level + Vol | N | Under Rate |
|---|---|---|
| GOOD + LOW | 406 | 50.7% |
| GOOD + HIGH | 55 | 60.0% |
| AVERAGE + LOW | 183 | 50.8% |
| AVERAGE + HIGH | 189 | 54.0% |
| POOR + LOW | 105 | 44.8% |
| POOR + HIGH | 401 | 51.4% |

The GOOD + HIGH cell (N=55, 60.0% under rate) is suggestive but dangerously small. The POOR + LOW cell shows a below-50% under rate (44.8%), which is the opposite of what we would want.

### S12 Overlay
- 16 of 51 resolved V1 signals had S12 overlay active in 2026
- Cannot split by volatility yet (no 2026 rolling features available)

---

## Phase 6 — Practical Framing

### Assessed Channels

| Channel | Assessment |
|---|---|
| A) Under persistence overlay — low vol strengthens under | No support. LOW vol under rate (51.7%) is not meaningfully higher than baseline. |
| B) F5 under caution flag — high vol weakens F5 trust | Theoretically plausible (high vol -> early exits -> more bullpen exposure in F5), but no market signal confirms it. Early exit rate difference is real (+10pp for GOOD+HIGH vs GOOD+LOW) but does not translate to pricing error. |
| C) Over-side context — high vol widens distribution | Refuted. HIGH vol games actually go UNDER more often vs closing lines in OOS data. |
| D) Context badge only | Only viable option, but effect sizes are too small to matter. |
| E) Close | **Recommended.** |

---

## Decision: CLOSE

### Rationale

1. **Volatility collapses to command level.** Correlation between vol and level is r=0.547. The off-diagonal cells (good command + high vol) are small (N=442 of 13,566 = 3.3%).

2. **No outcome signal.** Partial correlation of volatility with runs allowed, after controlling for level, is r=0.004. Neither volatility nor level predicts same-start runs with meaningful effect size. This is consistent with the fundamental noisiness of single-game pitcher outcomes.

3. **No market signal.** The year-by-year HIGH-LOW residual sign flips every year (+0.15, -0.19, +0.63, -0.44). There is no stable directional mispricing. Within-level market tests show HIGH volatility games going UNDER more often, not over — the opposite of the hypothesis.

4. **Early exit is the one real effect, but it does not translate.** Within GOOD command, HIGH volatility produces 10pp more early exits (30.1% vs 20.4%). This is a genuine distributional signature. However, it does not produce more runs, more overs, or any exploitable market residual.

5. **2026 sample is too thin.** Only 11 days into the season, no starter has enough 2026 starts for rolling features. Even if the signal existed, it would be months before it could be tested live.

### What We Learned
- Walk rate volatility is real but mostly a proxy for being a volatile (read: mediocre) pitcher
- The market appears to already account for (or even overweight) command volatility
- The early-exit channel is real but creates distribution width, not mean shift
- Zone% from Statcast could add a more precise command measure, but given the null results from walk rate volatility, the expected marginal value is low

### Data Available for Future Reference
- `mlb/data/pitcher_game_logs.parquet` — all per-start stats, 2022-2026
- Statcast chunks have pitch-level zone data (zones 1-9 in zone, 11-14 out) if zone% is ever needed
- Feature construction code pattern is documented in this report for reuse
