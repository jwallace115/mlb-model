# Team Totals Signal — Logic Audit

**Date:** 2026-04-10
**File:** `mlb/pipeline/team_total_signal.py`
**Status:** DEGRADED / OVERFIRING — needs fix before any live deployment

---

## Phase 1: Formula & Constants

```
fair_home = closing_total * 0.5015 - 0.248 + (away_SP_era - 4.50) * 0.621
fair_away = closing_total * 0.4985         + (home_SP_era - 4.50) * 0.621
gap = posted - fair
Signal fires when |gap| > 0.25
```

| Constant | Value | Notes |
|---|---|---|
| HOME_SHARE | 0.5015 | Empirical home-team run share |
| TRUNCATION_ADJ | 0.248 | Corrects home rounding bias in market lines |
| LEAGUE_AVG_ERA | 4.50 | Approximate 2022-2025 league starter ERA |
| SP_INNINGS_FACTOR | 0.621 | ERA-to-runs conversion (roughly IP/9 scaling) |
| GAP_THRESHOLD | 0.25 | Minimum gap to fire |

All constants are frozen from Phase 6 research. No runtime recalibration.

---

## Phase 2: PIT / Degradation Audit

### Input 1: Team total market lines
- **Source:** `pull_team_totals.py` via Odds API `team_totals` market, `regions=us`.
- **Line type:** Consensus (median) across US books at pull time. These are NOT closing prices — they are snapshot prices captured at ~7:30 AM ET. For shadow purposes this is acceptable, but for ROI computation it would need closing-price alignment.
- **PIT-safe:** Yes — lines are fetched fresh daily, not carried forward.

### Input 2: Full-game closing total
- **Source:** Synthetic — `closing_total = posted_home + posted_away`. This is NOT an independent market total; it is the sum of team total lines.
- **Impact:** When team totals are internally consistent (both teams from same book), this is fine. When they diverge across books (different median), the sum may not match any real full-game total. Moderate concern.

### Input 3: Starter identity
- **Source:** MLB Stats API `probablePitcher` hydration — correct, PIT-safe.
- **Working:** Yes, clean rows show correct pitcher names.

### Input 4: Starter ERA
- **Source:** `pitcher_game_logs.parquet`, expanding ERA with `shift(1)` (pregame-safe).
- **PIT-safe:** Yes — shift(1) ensures only pre-game data is used.
- **CRITICAL PROBLEM:** At season start (1-2 starts), ERA is wildly unstable. Observed values:
  - Slade Cecconi: ERA = 0.00 (1 start, 0 ER) -> sp_adj = -2.795
  - Bryce Elder: ERA = 13.17 (1 start, blown up) -> sp_adj = +5.385
  - These create gaps of +/- 4-5 runs — far beyond any real market inefficiency.

### Input 5: Park/context
- None used. No park factor, no weather, no handedness.

### Degraded mode
- 9/16 records (56%) are degraded (missing ERA for one or both starters).
- Degraded rows correctly set `sp_adj = 0.0` for missing pitchers — the formula falls back to league average ERA (4.50), which neutralizes the SP adjustment.
- **However:** Degraded rows still fire signals (8/9 degraded rows fired). The base_gap alone (from HOME_SHARE + TRUNCATION_ADJ math) can exceed 0.25, so degraded rows fire on line structure alone, not starter quality.

---

## Phase 3: Gap Decomposition

### Home gap
| Component | Mean | Std |
|---|---|---|
| base_gap (line math) | +0.580 | 0.384 |
| sp_contribution | -0.210 | 1.975 |
| total_gap | +0.370 | 1.987 |

**96.4% of gap variance comes from the SP adjustment, not from line math.**

### Away gap
| Component | Mean | Std |
|---|---|---|
| base_gap (line math) | -0.332 | 0.384 |
| sp_contribution | +0.112 | 1.527 |
| total_gap | -0.220 | 1.495 |

**94.1% of gap variance comes from the SP adjustment.**

### Interpretation
The base_gap has low variance (std=0.38) because team totals mostly sum to round numbers and HOME_SHARE is near 0.50. The SP adjustment dominates gap magnitude entirely. When ERA is stable (mid-season, 15+ starts), this is the intended behavior. **At 1-2 starts, the SP adjustment is noise amplified by the 0.621 factor.**

### Extreme cases observed (2026-04-10)
- ATL (Elder ERA=13.17): gap_home = -4.649 (fired H_OVER)
- PHI (Luzardo ERA=0.00): gap_home = +3.531 (fired H_UNDER)
- CIN (Burns ERA=11.25): gap_home = -3.456 (fired H_OVER)

A gap of 3-5 runs implies the market is wrong by 3-5 runs on a team total — this is economically implausible. The market already prices in starter quality.

---

## Phase 4: Early-Season Volume

| Date | Records | Fired | Fire Rate |
|---|---|---|---|
| 2026-04-09 | 5 | 4 | 80% |
| 2026-04-10 | 11 | 11 | 100% |
| **Total** | **16** | **15** | **93.8%** |

**93.8% fire rate is pathological.** A well-calibrated signal should fire on 15-25% of games. The signal is triggering on nearly every game.

### Root cause
Two compounding issues:
1. **Degraded rows (56%):** With sp_adj=0, the base_gap mean is +0.58 for home — above the 0.25 threshold by default. The TRUNCATION_ADJ (0.248) shifts the fair_home value down, making posted_home systematically appear "too high" relative to fair.
2. **Clean rows with extreme ERA (44%):** After 1-2 starts, ERA swings of 0-13 create sp_adj values of +/- 2-5 runs, overwhelming the 0.25 threshold.

---

## Phase 5: Thin-Sample Analysis

| Class | Fired | Resolved | Record | Hit Rate |
|---|---|---|---|---|
| Degraded | 8 | 4 | 4W-1L | 80% |
| Clean | 7 | 0 | — | — |

**Sample size is far too small (5 resolved games) for any statistical inference.** The 80% degraded hit rate is meaningless with n=5.

Average |gap| for fired signals: 0.697 (all degraded, since only degraded games have been graded so far).

---

## Phase 6: Economic Validity

### Grading logic
- Grading uses `actual_home_runs` vs `posted_home_total` — **correct**, grades against team scores, not full-game totals.
- Actual scores sourced from `game_table.parquet` via `game_pk` lookup — correct.

### Price data
- **No price keys exist in the shadow log.** The log stores line values but not over/under prices (juice).
- `pull_team_totals.py` does capture `over_price` and `under_price` per book in the `home_books`/`away_books` arrays, but these are stored in `team_totals_2026.json` (the raw pull file), not propagated to the shadow signal log.
- **ROI cannot be computed with real prices** from the shadow log alone. Would need to join back to the raw pull data.
- Even if prices were available, they are snapshot prices (~7:30 AM), not closing prices. True ROI would require closing-price capture.

### Missing: away_tt_over
- Code explicitly suppresses `away_tt_over` with comment "52-54% in research, below threshold." This is correct discipline.

---

## Phase 7: Verdict

### Classification: DEGRADED / OVERFIRING

### Critical Issues

1. **93.8% fire rate is pathological.** The signal fires on nearly every game, providing no selectivity. A signal that fires on everything is not a signal.

2. **ERA instability at 1-2 starts creates economically implausible gaps (3-5 runs).** The market already incorporates starter quality; claiming a 4-run mispricing on a team total is not credible.

3. **56% degraded mode rate.** More than half of records lack starter ERA data, and these degraded rows still fire due to the structural bias in base_gap.

4. **No price data in shadow log.** ROI cannot be computed, so there is no economic validation possible from this log alone.

### Moderate Issues

5. **Closing total is synthetic (home + away team totals summed).** Not independently sourced from the full-game market. Could diverge from true market total.

6. **No minimum-starts gate.** ERA is used from the first available start regardless of sample size. A 1-start ERA has no predictive value.

7. **No early-season suppression.** The signal should not fire until starters have 4-5+ starts of ERA history.

### What's Working

- PIT safety is correct throughout: `shift(1)` on ERA, fresh daily line pulls, probablePitcher from MLB API.
- Grading logic is correct (team scores vs team total lines).
- Degraded mode correctly zeroes SP adjustment for missing pitchers.
- away_tt_over correctly suppressed per research.
- Deduplication and append logic is sound.

### Recommended Fixes (not implemented — audit only)

1. Add `MIN_STARTS = 4` gate: if a pitcher has fewer than 4 starts in the expanding ERA, fall back to LEAGUE_AVG_ERA.
2. Cap ERA input to [2.0, 8.0] range to prevent extreme sp_adj values.
3. Add early-season suppression: do not fire TT signals before April 20 (or until median pitcher in the log has 3+ starts).
4. Propagate over/under prices from pull data to shadow log for ROI computation.
5. Consider sourcing closing total independently from the full-game totals market rather than summing team totals.
