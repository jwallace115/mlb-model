# Golf Finish Engine — Final Report

Generated: 2026-03-30T13:31:39

## 1. Data Foundation
- 32,000 golfer-events (2020-2025)
- 50 features per golfer-event
- 5 markets: make_cut, top_20, top_10, top_5, win

## 2. Engine Stack
- **Engine A (Cut):** Logistic/GBM/Shrinkage -> champion selected by OOS Brier
- **Engine B (Mean):** Ridge regression on finish percentile
- **Engine C (Variance):** Ridge regression on event score SD
- **Engine D (Simulator):** 20000 Monte Carlo sims per event, 4-round with cut
- **Engine E (Calibration):** Isotonic/Platt per market

## 3. Market Validation (OOS 2024-2025)

| Market | Threshold | N | Hit Rate | ROI | CLV | Stable |
|--------|-----------|---|----------|-----|-----|--------|
| top_20 | 4% | 3204 | 17.2% | -13.8% | -- | -- |
| top_20 | 6% | 2455 | 16.8% | -12.6% | -- | -- |
| top_20 | 8% | 1767 | 15.8% | -13.0% | -- | -- |
| top_10 | 4% | 2989 | 6.6% | -16.9% | -- | -- |
| top_10 | 6% | 1602 | 5.9% | -16.7% | -- | -- |
| top_10 | 8% | 582 | 4.8% | -31.1% | -- | -- |
| top_5 | 4% | 1452 | 3.2% | -12.0% | -- | -- |
| top_5 | 6% | 324 | 4.6% | -5.8% | -- | -- |
| top_5 | 8% | 91 | 6.6% | -35.9% | -- | -- |
| make_cut | 4% | 899 | 74.5% | -1.8% | -- | -- |
| make_cut | 6% | 636 | 75.9% | -2.4% | -- | -- |
| make_cut | 8% | 419 | 80.7% | +0.8% | -- | -- |
| win | 4% | 9 | 0.0% | -100.0% | -- | -- |
| win | 6% | 0 | 0.0% | +0.0% | -- | -- |
| win | 8% | 0 | 0.0% | +0.0% | -- | -- |

## 4. Final Verdict

**INSUFFICIENT_EDGE**
No market/threshold passes deployment gates.