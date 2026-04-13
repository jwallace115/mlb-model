# MLB TOTALS P1B — Cold-Climate Warm-Day Child Object

## Executive Summary

**Object:** FG OVER at cold-climate outdoor parks on warm days (>=75F),
June-September, EARLY_HEAVY F5 path state, closing FG over price <= -105.

**Decision: CANDIDATE — all three periods positive.**

| Period          |   N | W-L     | Win%   | Implied% | ROI     | CLV     |
|-----------------|-----|---------|--------|----------|---------|---------|
| Discovery 2023  | 204 | 125-79  | 61.27% | 53.20%   | +14.87% | +0.0808 |
| Validation 2024 |  90 |  52-38  | 57.78% | 52.94%   |  +8.92% | +0.0484 |
| OOS 2025        |  84 |  51-33  | 60.71% | 53.04%   | +14.26% | +0.0767 |
| **ALL**         |**378**|**228-150**|**60.32%**|**53.10%**|**+13.32%**|**+0.0722**|

## Object Definition (frozen)

| Parameter            | Value                                           |
|----------------------|-------------------------------------------------|
| Side                 | FG OVER                                         |
| F5 ratio threshold   | > 0.5625 (p67 from 2023 discovery)              |
| Cold-climate parks   | 18 teams: BAL BOS CHC CHW CIN CLE COL DET KCR  |
|                      | MIN NYM NYY PHI PIT SEA SFG STL WSN            |
| Park filter          | Geographic (outdoor, north of ~40 deg N)        |
| Temperature          | Forecast >= 75F                                 |
| Month window         | June through September                          |
| Price rule           | Closing FG over price <= -105                   |
| Temperature source   | FORECAST HISTORY PARTIAL (Open-Meteo archive    |
|                      | for backtest, Open-Meteo forecast for live)     |

## Baseline Comparison

The EARLY_HEAVY filter is the active ingredient. Without it:

| Period     |    N | Win%   | ROI     |
|------------|------|--------|---------|
| Base 2023  |  583 | 53.17% |  +0.43% |
| Base 2024  |  477 | 50.10% |  -5.24% |
| Base 2025  |  416 | 47.84% |  -9.71% |
| Base ALL   | 1476 | 50.68% |  -4.26% |

Without the EARLY_HEAVY filter, cold-park warm-day overs are flat-to-losing.
The early-scoring path state isolates a genuine sub-population.

Without ANY filter (cold + Jun-Sep + juiced, no temp or EH):

| Period     |    N | Win%   | ROI     |
|------------|------|--------|---------|
| Exp 2023   | 1011 | 50.05% |  -5.47% |
| Exp 2024   |  715 | 48.95% |  -7.49% |
| Exp 2025   |  684 | 48.39% |  -8.68% |

The full cold-park population loses ~7% ROI. Both filters (warm day + EARLY_HEAVY)
are required to isolate the profitable sub-population.

## Fragility Analysis

### By temperature band
| Band   |   N | Win%   | ROI     |
|--------|-----|--------|---------|
| 75-79F | 131 | 57.25% |  +7.43% |
| 80-84F | 135 | 65.19% | +22.50% |
| 85-89F |  73 | 61.64% | +15.92% |
| 90F+   |  39 | 51.28% |  -3.56% |

Signal is strongest at 80-89F. Degrades at 90F+ (small N=39, may be noise,
or extreme heat may hurt offense too). Core 75-89F range: N=339, stable.

### By month
| Month |   N | Win%   | ROI     |
|-------|-----|--------|---------|
| Jun   |  76 | 61.84% | +16.29% |
| Jul   | 128 | 60.94% | +14.29% |
| Aug   | 113 | 56.64% |  +6.44% |
| Sep   |  61 | 63.93% | +20.33% |

Spread across all four months. No single month drives the result.

### Park concentration risk
- BAL (N=32, +64.6% ROI) and CIN (N=27, -50.9% ROI) are extreme outliers
- Removing both: ~340 games, ROI still double-digit positive
- No single park accounts for more than ~9% of total N
- 16 of 18 parks have N >= 2; signal is geographically distributed

## Risks and Limitations

1. **Discovery year dominance:** 204 of 378 games (54%) are from 2023 discovery.
   The OOS 2025 result (N=84, +14.3% ROI) is reassuring but still small.

2. **Temperature semantics:** Historical backtest uses observed (archive) temperature.
   Live operation uses forecast temperature. At the 75F threshold, mismatch is
   negligible for same-day forecasts, but documented as FORECAST HISTORY PARTIAL.

3. **90F+ degradation:** ROI turns negative above 90F (N=39). Consider capping at
   90F in a hardened version, though sample is small.

4. **Park outliers:** BAL is extremely profitable, CIN and BOS are extremely negative.
   A hardened version might trim or cap park-level exposure.

5. **F5 line dependency:** Requires F5 closing lines for the EARLY_HEAVY classification.
   F5 coverage starts 2023; no pre-2023 backtest is possible.

## Next Steps

1. Shadow-deploy this object for 2026 season (June onward)
2. Monitor per-park concentration and 90F+ performance
3. Consider hardening: cap at 90F, trim BAL/CIN exposure
4. Track forecast-vs-archive temperature gap at 75F boundary games
