# Phase 2 — Market Structure Tests

**Date:** 2026-04-08
**Dataset:** 4,855 games with closing lines (2024-2025), 3,365 games with team total lines (2024-2025)

---

## Test A — Home 9th-Inning Truncation

### Mechanism

When the home team leads after the top of the 9th, the bottom of the 9th is not played. This removes ~0.5 expected runs from the game total. The question: does the totals market correctly price this asymmetry?

### Data

- Source: `sim/data/game_table.parquet` joined to `sim/data/market_snapshots.parquet`
- No moneyline data available; used actual outcome (home win/loss) as post-hoc split and scoring patterns as pre-game proxy
- Restricted to 9-inning games (N=4,423 of 4,855 with closing lines)

### Results at Closing Total = 8.5

| Metric | Home Win (N=706) | Home Loss (N=566) | All (N=1,272) |
|--------|------------------|--------------------|---------------|
| Mean actual total | 8.407 | 9.359 | 8.830 |
| OVER rate | 45.8% | 52.8% | 48.9% |
| UNDER rate | 54.3% | 47.2% | 51.1% |

**Difference in mean total: 0.95 runs** (home losses produce nearly 1 full run more).
Chi-square test: p = 0.014 (statistically significant).

### Results at Closing Total = 9.0

| Metric | Home Win (N=346) | Home Loss (N=312) | All (N=658) |
|--------|------------------|--------------------|-------------|
| Mean actual total | 9.130 | 9.420 | 9.267 |
| OVER rate | 39.3% | 45.2% | 42.1% |
| UNDER rate | 48.6% | 44.9% | 46.8% |
| Push rate | 12.1% | 9.9% | 11.1% |

Smaller gap (0.29 runs) at 9.0, consistent with integer push absorption.

### Season Stability

| Season | Line | HW-HL Total Gap |
|--------|------|-----------------|
| 2024 | 8.5 | 0.936 |
| 2025 | 8.5 | 0.972 |
| 2024 | 9.0 | 0.519 |
| 2025 | 9.0 | 0.102 |

The 8.5 effect is stable across seasons. The 9.0 effect is noisier due to push dynamics and smaller N.

### Margin Analysis (8.5 line)

| Outcome Type | N | Mean Total | OVER Rate |
|--------------|---|------------|-----------|
| Walkoff (margin=1) | 194 | 6.96 | 33.5% |
| Close home win (margin 1-2) | 314 | 6.98 | 31.2% |
| Blowout home win (margin 3+) | 392 | 9.55 | 57.4% |
| Non-walkoff home win (margin 2+) | 512 | 8.96 | 50.4% |

Close/walkoff home wins strongly suppress totals. Blowout home wins still produce overs because the scoring dominance more than offsets the missing half-inning.

### Truncation Pattern Across All Closing Totals

| Total | N | OVER (HW) | OVER (HL) | Gap |
|-------|---|-----------|-----------|-----|
| 7.0 | 211 | 37.5% | 36.1% | -1.4pp |
| 7.5 | 836 | 45.3% | 54.6% | +9.3pp |
| 8.0 | 780 | 44.9% | 43.8% | -1.0pp |
| 8.5 | 1,272 | 45.8% | 52.8% | +7.1pp |
| 9.0 | 658 | 39.3% | 45.2% | +5.9pp |
| 9.5 | 347 | 45.3% | 53.7% | +8.4pp |
| 10.0 | 80 | 41.0% | 51.2% | +10.2pp |
| 10.5 | 87 | 43.9% | 54.3% | +10.4pp |

The gap is consistently positive (home losses go over more) at every half-run total above 7.0. It widens at higher totals, consistent with the truncation mechanism (more expected scoring = more value lost from a missing half-inning).

### Away Favorite Control (8.5 line)

| Group | N | Mean Total | OVER Rate |
|-------|---|------------|-----------|
| Away blowout (margin <= -3) | 328 | 10.79 | 65.9% |
| Home blowout (margin >= 3) | 392 | 9.55 | 57.4% |
| Close games (|margin| <= 1) | 327 | 6.92 | 34.6% |

Away blowouts produce 1.2 runs more than home blowouts at the same closing total, because away blowouts include the full bottom of the 9th (home team bats trailing, all outs recorded).

### Test A Verdict

**The truncation effect is real and statistically significant.** Home wins produce ~0.95 fewer total runs than home losses at the same closing total (8.5). However, this is a **post-hoc split** — the market knows the home win probability and should already price it. The exploitable question is whether the market *correctly weights* the truncation conditional on observable pre-game factors. This feeds directly into Test B.

---

## Test B — Cross-Market Consistency Triangle

### Triangle Test: Team Total Sum vs Game Total

Team total data was available from `research/team_totals/data/team_totals_results.parquet` (3,365 games with both home/away TT lines and actual scores).

**Core finding: TT sum is consistently below the game total.**

| Closing Total | N | TT Sum | Game Total | Gap |
|---------------|---|--------|------------|-----|
| ~7.0 | 186 | 6.80 | 7.00 | -0.20 |
| ~7.5 | 672 | 7.24 | 7.50 | -0.26 |
| ~8.0 | 623 | 7.61 | 8.00 | -0.40 |
| ~8.5 | 962 | 8.02 | 8.50 | -0.48 |
| ~9.0 | 505 | 8.58 | 9.00 | -0.42 |
| ~9.5 | 227 | 9.05 | 9.50 | -0.45 |
| ~10.0 | 46 | 9.33 | 10.00 | -0.67 |

**Mean gap: -0.42 runs.** The most common gaps are -0.5 (44% of games) and 0.0 (27% of games). This gap is the market's built-in vig/truncation buffer — the team totals are set conservatively relative to the game total.

### Home Scoring Share

| Closing Total | N | Implied Home Share (from TT) | Actual Home Share | Difference |
|---------------|---|------------------------------|-------------------|------------|
| ~7.5 | 672 | 0.5109 | 0.5213 | +0.0104 |
| ~8.0 | 623 | 0.5136 | 0.5024 | -0.0112 |
| ~8.5 | 962 | 0.5126 | 0.5204 | +0.0078 |
| ~9.0 | 505 | 0.5064 | 0.5155 | +0.0091 |
| ~9.5 | 227 | 0.5024 | 0.5047 | +0.0023 |

The market correctly prices home share as slightly above 50% (0.509 average implied). Actual home share is 0.514 — a +0.005 residual the market leaves on the table. Small but consistent.

Overall home share (all 9-inning games): **0.5136** (t=3.26, p=0.001). Statistically significant but only 1.4pp above 50%.

### Home Share Correlation with Total

Pearson r = -0.063 (p < 0.001). As closing total rises, home share falls. At low totals (~7.0), home share is 0.542; at high totals (~10.5), it drops to 0.476. This is consistent with: low-total games are pitcher-driven, home pitching advantage + truncation elevates home share; high-total games are often driven by away-team offense.

### The Exploitable Signal: Home TT Under When Home Favored

When the market sets home TT > away TT (home team favored), the home TT systematically goes under:

| Group | N | Home TT OVER | Away TT OVER |
|-------|---|--------------|--------------|
| Home TT > Away TT (home favored) | 1,166 | 46.2% | 49.3% |
| Equal TT | 1,375 | 51.0% | 49.4% |
| Home TT < Away TT (away favored) | 824 | 50.9% | 47.3% |

**Home TT UNDER rate when home favored: 53.8% (p = 0.005, binomial test).**
Mirror test (away TT UNDER when away favored): 52.7% (p = 0.067, weaker but directionally consistent).

This is the truncation mechanism from Test A surfacing in the team totals market: the market sets the home TT based on expected scoring but does not fully discount for the probability that the bottom of the 9th will not be played.

### Season Stability

| Season | N (home favored) | Home TT UNDER Rate |
|--------|------------------|--------------------|
| 2024 | 568 | 53.4% |
| 2025 | 598 | 54.2% |

Stable across both seasons.

### Simulated ROI

Flat-betting home TT UNDER when home TT > away TT, at -110 juice:

| Season | Bets | W-L | ROI |
|--------|------|-----|-----|
| 2024 | 568 | 303-265 | +1.84% |
| 2025 | 598 | 324-274 | +3.44% |
| **Combined** | **1,166** | **627-539** | **+2.66%** |

Profit: +31.0 units on 1,166 bets.

### Home TT Under by Closing Total (Home Favored)

| Total Band | N | Home TT UNDER Rate |
|------------|---|--------------------|
| ~7.0 | 53 | 60.4% |
| ~7.5 | 169 | 47.9% |
| ~8.0 | 270 | 56.7% |
| ~8.5 | 457 | 53.4% |
| ~9.0 | 137 | 51.1% |
| ~9.5 | 42 | 64.3% |

Signal is noisy by total band but present across most levels. Best at extreme totals (7.0, 9.5+) where the favorite/truncation dynamic is strongest.

### Test B Verdict

**The triangle gap is real and structural.** Team total sums understate the game total by ~0.4-0.5 runs. More importantly, the home TT is mispriced when the home team is favored: the market does not fully discount the bottom-9th truncation probability. The home TT UNDER hits 53.8% in these spots, producing +2.66% ROI at -110 across 1,166 bets over two seasons. The signal is statistically significant (p = 0.005) and stable across seasons.

---

## Combined Findings

Tests A and B are measuring the same structural feature from different angles:

1. **Test A** (game totals): Home wins suppress actual totals by ~1 run vs home losses at the same closing line. The game total market appears to price this approximately correctly in aggregate (overall OVER/UNDER rates near 50%).

2. **Test B** (team totals): The team totals market does NOT fully price the truncation. When the home team is favored, the home TT is set too high — the missing bottom-9th probability is under-discounted. This creates a 53.8% UNDER rate, above the 52.4% breakeven at -110.

The key insight is that the **game total market** absorbs truncation reasonably well (it is the most liquid MLB market), but the **team total sub-market** leaks edge because the home/away split does not correctly condition on the truncation probability.

---

## Final Questions

### 1. Which test provides the faster path to real edge?

**Test B — the home TT under signal.** It is already actionable: bet home TT UNDER when the market sets home TT > away TT. The hit rate (53.8%), statistical significance (p = 0.005), season stability (53.4% in 2024, 54.2% in 2025), and simulated ROI (+2.66% at -110) all clear the bar for a live shadow test. No model changes are needed — this is a pure market-structure filter.

Test A provides the theoretical foundation but does not translate directly into a game-total bet because the game total market prices the truncation approximately correctly in aggregate.

### 2. Which test feeds the next engine build?

**Both, but in different ways.**

- **Test B** feeds immediately into a team-total shadow engine. The signal is simple (home TT > away TT → bet home TT UNDER) and can be layered with existing model outputs (SP quality, park factor) to filter for the strongest spots.

- **Test A** feeds into the simulation engine as a calibration check. The Phase 9 sim currently treats all half-innings symmetrically. Adding a conditional truncation layer (suppress the bottom-9th draw when the simulated home team leads) would improve the sim's score distribution and reduce systematic bias in close-game scenarios. This is a longer build but improves the core engine.

**Recommended next step:** Build a home TT UNDER shadow logger that fires on home-favored games and tracks hit rate alongside the existing game-total shadow. Run for 2-3 weeks before sizing live.
