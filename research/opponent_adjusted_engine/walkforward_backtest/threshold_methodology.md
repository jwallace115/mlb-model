# Threshold Methodology — Walk-Forward Backtest

## METHOD A — Expanding-window percentile
- For each game date, compute top-20% threshold (p80)
  using only prior games from the SAME SEASON with adj_k available
- Warmup: minimum 200 games before activating threshold
- During warmup period: signal is UNAVAILABLE (no games flagged)
- This is strictly leakage-safe: only past data used

## METHOD B — Frozen prior-season threshold
- For 2025: use full 2024 p80 = 0.22762
- For 2024: same as METHOD A (no prior season available)
- This simulates how we'd deploy in practice: freeze from prior year

## Why leakage-safe
- METHOD A: each game's threshold uses only strictly prior games
- METHOD B: 2025 threshold frozen from 2024 (entirely out-of-sample)
- Warmup prevents unstable early-season thresholds
- 200-game warmup ≈ first ~5 weeks of season excluded

## Sample counts for thresholding
- 2024: 2231 games with adj_k, first threshold at game ~200
- 2025: 2237 games with adj_k, first threshold at game ~200
