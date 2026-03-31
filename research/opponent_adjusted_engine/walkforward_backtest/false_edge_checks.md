# False Edge Checks

## 7.1 Data Availability Bias
- adj_k AVAILABLE: N=819, WR=0.562, ROI=+7.2%, avg_close=7.68
- adj_k UNAVAILABLE: N=68, WR=0.515, ROI=-1.7%, avg_close=8.08

Bias: 0.047 (BIASED)

## 7.2 Permutation Check (2025)
- N flagged: 130
- Observed ROI: +17.5%
- Permutation median: +8.7%
- Observed percentile: 91.0%
- PASS: observed is above 90th percentile

## 7.3 Leakage Confirmation
- METHOD A: expanding-window with 200-game warmup, verified per-game
- METHOD B: frozen from 2024 (entirely out-of-sample for 2025)
- No future data used in any threshold computation
