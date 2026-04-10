# Team Total Signal Identity Audit

**Date:** 2026-04-10
**Verdict: NEVER-MATCHED**

---

## Executive Summary

The live TT signal (`mlb/pipeline/team_total_signal.py`) was **never the same object** as any of the backtests that produced the claimed 56-58% hit rates. Three distinct methodologies exist in the codebase, none of which are equivalent. The live signal uses ERA where the backtest used xFIP, with a different league-average baseline. Additionally, the Phase 6 backtest that generated the published claims used **end-of-season look-ahead xFIP** (confirmed: within-pitcher-season std = 0.0000 for all 490 pitchers tested), inflating reported hit rates.

---

## Phase 1: Code Path Comparison

Three distinct TT objects exist in the codebase:

### Object A: Phase 6 Report (`research/mlb_distribution/phase6_team_total_engine.md`)
- **Formula:** `fair_home = closing_total * 0.5015 - 0.248 + (away_SP_xFIP - 4.231) * 0.621`
- **SP metric:** xFIP (skill-based, FIP denominator)
- **Baseline:** 4.231 (league-average xFIP)
- **Data source:** `team_totals_historical.parquet`, books >= 3, joined with `feature_table.parquet`
- **xFIP source:** `feature_table` -- **END-OF-SEASON LOOK-AHEAD** (confirmed constant within season)
- **Claims:** Away UNDER gap>0.25: 58.0% hit rate, +10.8% ROI; Home UNDER gap>0.25: 55.9%, +6.7% ROI
- **No surviving Python script** -- only the markdown report exists

### Object B: Backtest v1/v2 (`research/team_totals/run_tt_research_v2.py`)
- **Methodology:** Monte Carlo simulation (20k draws) with S2 starter-path model + negative binomial
- **SP metric:** xFIP (from `sim_inputs` parquet)
- **Signal logic:** Identifies "suppressed team" (lower expected runs from simulation), bets that team's TT under
- **Threshold:** `run_gap >= 0.75` (simulation-derived gap between per-team expected runs)
- **Completely different from the formula** -- uses simulated distributions, not a linear fair-value model

### Object C: Live Signal (`mlb/pipeline/team_total_signal.py`)
- **Formula:** `fair_home = closing_total * 0.5015 - 0.248 + (away_SP_ERA - 4.50) * 0.621`
- **SP metric:** ERA (results-based, from `pitcher_game_logs`)
- **Baseline:** 4.50 (league-average ERA)
- **ERA computation:** PIT-safe expanding mean with shift(1)
- **Starter source:** MLB Stats API `probablePitcher`
- **Degraded mode:** Falls back to league-average ERA (4.50) when pitcher unknown
- **Prices:** NOT logged

### Key Differences

| Parameter | Phase 6 Report | Live Signal | Delta |
|-----------|---------------|-------------|-------|
| SP metric | xFIP | ERA | Different stat |
| League baseline | 4.231 | 4.50 | +0.269 |
| SP source | feature_table (look-ahead) | PGL (PIT-safe) | Different data |
| Starter ID | feature_table | MLB API probablePitcher | Different source |
| Books filter | >= 3 | none | Missing filter |
| Prices logged | no (flat -110) | no | -- |

---

## Phase 2: Live Formula Applied Historically

Applied the exact live formula (ERA-based, baseline 4.50) to 2022-2025 canonical odds data with PIT-safe expanding ERA from pitcher_game_logs.

### Results (non-degraded games only, both SP ERA available)

| Season | N | H_UNDER N | H_UNDER Win% | H_UNDER ROI | A_UNDER N | A_UNDER Win% | A_UNDER ROI |
|--------|---|-----------|-------------|-------------|-----------|-------------|-------------|
| 2023 | 466 | 317 | 53.0% | +1.2% | 199 | 46.2% | -11.7% |
| 2024 | 1,775 | 1,190 | 51.3% | -2.0% | 777 | 51.4% | -2.0% |
| 2025 | 1,708 | 1,219 | 50.8% | -3.1% | 723 | 53.4% | +1.9% |
| **ALL** | **3,949** | **2,726** | **51.3%** | **-2.1%** | **1,699** | **51.6%** | **-1.5%** |

**The live formula is unprofitable.** Home UNDER ROI = -2.1%, Away UNDER ROI = -1.5%. Both near chance.

### Fire Rate Problem

The live formula fires on ~69% of games for H_UNDER and ~43% for A_UNDER. The Phase 6 report showed ~54% and ~29% respectively. The ERA-based formula fires far too often because ERA has higher variance and a higher baseline than xFIP, meaning more pitchers deviate from 4.50 than from 4.231.

### No Improvement by Start Count

| Min Starts | H_UNDER ROI | A_UNDER ROI |
|------------|-------------|-------------|
| >= 1 | -2.1% | -1.5% |
| >= 5 | -2.4% | -0.9% |
| >= 10 | -3.6% | -1.0% |

More starts = slightly worse ROI. No minimum-start gate fixes this.

---

## Phase 3: Look-Ahead Confirmation

The Phase 6 report's xFIP values from `feature_table.parquet` are **definitively end-of-season look-ahead**:

- Within-pitcher-season standard deviation of xFIP: **0.0000**
- All 490 pitchers with 10+ starts have **exactly constant xFIP** throughout the season
- This means April games use September xFIP values

**Impact:** The Phase 6 report's 56-58% claims were generated with future information. The true PIT-safe hit rates would be lower.

When I reproduce the Phase 6 formula with the same look-ahead xFIP against canonical odds (larger sample):

| Signal | N | Win% | ROI |
|--------|---|------|-----|
| H_UNDER | 2,972 | 53.7% | +2.5% |
| A_UNDER | 1,560 | 53.4% | +1.9% |
| H_OVER | 760 | 45.8% | -12.6% |

These are lower than the report's claims (55.9% / 58.0%), likely because:
1. Different TT line source (canonical odds vs team_totals_historical)
2. No books >= 3 filter applied
3. Canonical odds may use different snapshot timing

Even with end-of-season look-ahead xFIP, the reproduced results are marginal (+2.5% / +1.9% ROI), well below the claimed +6.7% / +10.8%.

---

## Phase 4: Price Consistency

| Source | Prices Available | ROI Method |
|--------|-----------------|------------|
| Phase 6 report | Real TT prices exist but NOT used | Flat -110 |
| Backtest v1/v2 | Real TT prices in dataset | Flat -110 (roi_110 function) |
| Live signal | NO prices logged | N/A |

### Actual TT Juice

| Source | Mean Under Price | Implied Prob | Break-Even Win% |
|--------|-----------------|--------------|-----------------|
| Research historical | -44 American | 52.6% | 52.6% |
| Canonical odds | -57 American | 53.3% | 53.3% |

At actual TT juice (~53% break-even), the reproduced xFIP results (53.4-53.7% win rate) are barely profitable. The ERA-based live results (51.3-51.6%) are clearly unprofitable.

---

## Phase 5: Verdict

### Classification: NEVER-MATCHED

The live TT signal was never the same object as the backtest that generated the 56-58% claims. Specifically:

1. **SP metric substitution:** xFIP was replaced with ERA. These are fundamentally different statistics -- xFIP is a skill estimator (normalizes HR/FB), ERA includes luck and defense. The replacement was not validated.

2. **Baseline substitution:** 4.231 (xFIP mean) was replaced with 4.50 (ERA mean). This shifts the SP adjustment term, changing which games fire.

3. **Look-ahead contamination:** The Phase 6 backtest used end-of-season xFIP as if it were available pregame. The published hit rates are inflated.

4. **Separate research branch:** The backtest scripts in `research/team_totals/` use Monte Carlo simulation, not the formula. They were a parallel research effort that was never connected to the live signal.

5. **Historical proof:** When the live ERA formula is applied historically, it produces -2.1% ROI (H_UNDER) and -1.5% ROI (A_UNDER) -- indistinguishable from chance.

### Risk Assessment

The live TT signal is currently running in shadow mode. Based on this audit:
- The signal has no validated edge
- The formula was never backtested in its current form
- It fires on ~69% of games (far too broad to be selective)
- No prices are captured, making future grading incomplete
