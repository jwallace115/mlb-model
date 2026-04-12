# Phase 4: Manual Examples — 2026 Live Signals

**Date:** 2026-04-12

---

## All 7 Signals in the Tracker (f5_runline_2026.parquet)

| # | Date | Matchup | Home xFIP | Away xFIP | Gap | >= 1.5? | Result |
|---|------|---------|-----------|-----------|-----|---------|--------|
| 1 | 2026-03-30 | COL@TOR | 4.250 | 5.330 | 1.080 | NO | LOSS |
| 2 | 2026-04-01 | OAK@ATL | 3.331 | 4.336 | 1.005 | NO | WIN |
| 3 | 2026-04-04 | SDP@BOS | 3.854 | 4.984 | 1.130 | NO | LOSS |
| 4 | 2026-04-05 | SDP@BOS | 3.504 | 5.007 | 1.503 | YES | LOSS |
| 5 | 2026-04-06 | SDP@PIT | 4.077 | 5.285 | 1.208 | NO | LOSS |
| 6 | 2026-04-07 | SDP@PIT | 3.115 | 4.124 | 1.009 | NO | WIN |
| 7 | 2026-04-10 | TEX@LAD | 3.900 | 4.974 | 1.074 | NO | LOSS |

## xFIP Source Verification

All 7 signals used xFIP from the LIVE pipeline:
- `generate_signals()` calls `modules.pitchers.get_pitcher_metrics()`
- This pulls from `pitcher_db`, which is populated by the FanGraphs API
  at model run time (7 AM daily via launchd)
- xFIP values vary by day (confirmed: BOS home starter had 3.854 on 4/4
  and 3.504 on 4/5 — different starters, as expected)

**No contamination in live signals.** The xFIP source chain is:
FanGraphs API -> pitcher_db -> get_pitcher_metrics() -> signal generator

## Threshold Impact

| Threshold | Signals | W-L | Record |
|-----------|---------|-----|--------|
| >= 1.0 (old) | 7 | 2-5 | -28.6% ROI |
| >= 1.5 (new) | 1 | 0-1 | -100% ROI (N=1, meaningless) |

At the old 1.0 threshold: 6 of 7 signals (86%) would be EXCLUDED by the
1.5 threshold. The sample is too small to draw conclusions, but the
2-5 record at 1.0 is consistent with the PIT revalidation finding that
gap >= 1.0 is borderline (~50% hit rate).

## Key Observation

The 2026-04-05 signal (gap=1.503) is the ONLY one that would fire at 1.5.
It lost. With N=1, this tells us nothing about the threshold's merit.
The evidence for 1.5 comes from the PIT-clean backtest (N=32-35 per season),
not from 2026 live data.
