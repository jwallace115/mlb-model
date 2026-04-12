# Phase 0: Locked Archive Basis — Signal B HOME

**Date:** 2026-04-12
**Signal:** F5 Run Line HOME -0.5 (xFIP gap >= 1.5)
**Object ID:** mlb_f5_rl_signal_b_home

---

## Clean Backtest Verdict (PIT-safe, expanding mean)

Source: `research/recovery/signal_b_clean_backtest/SIGNAL_B_CLEAN_BACKTEST_EXEC_SUMMARY.md`

| Metric | Value |
|---|---|
| Total bets | 724 |
| Record | 390W-334L |
| Hit rate | 53.9% |
| Breakeven @ -135 | 57.4% |
| Edge over BE | -3.6pp |
| ROI @ -135 | -6.2% |
| P/L @ -135 | -22.56u |

### Season Breakdown

| Season | N | W-L | Hit Rate | ROI @ -135 |
|---|---|---|---|---|
| 2022 | 199 | 119-80 | 59.8% | +4.1% |
| 2023 | 205 | 100-105 | 48.8% | -15.1% |
| 2024 | 147 | 78-69 | 53.1% | -7.6% |
| 2025 | 173 | 93-80 | 53.8% | -6.4% |

Only 2022 was profitable. Three consecutive losing seasons (2023-2025).

## Live 2026 Shadow Performance

| Metric | Value |
|---|---|
| Signals | 7 |
| Record | 2W-5L |
| Win rate | 28.6% |
| ROI | -48.8% |
| Net units | -1.71u |

## Original Contamination

The original Signal B showed +27.9% ROI. This was contaminated by lookahead bias
in the xFIP calculation (season-end values used for in-season decisions). When
corrected to PIT-safe expanding means with minimum 3 prior starts, the signal
collapses to -6.2% ROI.

## Conclusion

Signal B HOME is unprofitable at every realistic F5 run line price. The archive
is locked. No reactivation without new independent research basis.
