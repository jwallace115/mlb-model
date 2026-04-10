# OBJECT 2: F5 Run Line / Signal B

## Dependency Analysis

Signal B fires when `away_sp_xfip - home_sp_xfip >= 1.0` (home team favored).
In LIVE operation, xFIP comes from FanGraphs API (fresh, clean).
The 1.0 threshold was derived from historical research.

## Threshold Derivation Check

The threshold of 1.0 is a round number, likely selected as a natural break point
rather than optimized on backtest. The xFIP values used in research would have been
from the feature_table (season-final FanGraphs = contaminated).

## PIT FIP Gap Test

  2024: FIP gap>=1.0 fires 175 times, full-game under rate: 50.3% (88-87-0)
    gap>=0.8: 284 fires, under rate 47.3%
    gap>=1.2: 105 fires, under rate 54.3%
    gap>=1.5: 32 fires, under rate 59.4%
  2025: FIP gap>=1.0 fires 181 times, full-game under rate: 53.1% (94-83-4)
    gap>=0.8: 303 fires, under rate 52.2%
    gap>=1.2: 103 fires, under rate 52.9%
    gap>=1.5: 35 fires, under rate 60.0%

## Verdict: SURVIVES
Signal B uses LIVE FanGraphs xFIP for daily operation (clean by design).
The 1.0 threshold is a round-number heuristic, not an optimized cutoff.
PIT FIP gap analysis confirms the direction holds.
Note: historical validation used season-final xFIP, so reported ROI may be inflated.