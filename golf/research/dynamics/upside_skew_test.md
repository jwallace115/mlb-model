# Upside Skew Decomposition Test

Generated: 2026-03-30T16:46:03

## Verdict: UPSIDE_SKEW_SIGNAL_NULL

## Features
- skew_index_50 = ceiling_rate - blowup_rate (1.0σ threshold)
- tail_balance_50 = top_decile_rate - bottom_decile_rate (field-relative)
- All prior-only, minimum 20 rounds

## Coverage
- Player-events: 28,430
- skew_index_50: 100.0%
- tail_balance_50: 100.0%

## Monotonicity (OOS, skew_index)
- Top 10 (HIGH>=LOW): 1/4 bands
- Top 5 (HIGH>=LOW): 0/4 bands
- Win (HIGH>=LOW): 1/4 bands

## Comparison vs Generic Volatility
- Generic vol: t10=2/4, t5=2/4, win=2/4 (WEAK)
- Skew: t10=1/4, t5=0/4, win=1/4

## Key Answers
1. Does skew outperform generic volatility? No — similar performance
2. Most affected market: Top 10
3. Worth building spike engine: No
