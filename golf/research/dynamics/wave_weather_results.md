# Wave Weather Engine Results

## Verdict: WAVE_WEATHER_SIGNAL_CONFIRMED

## Data
- Player-round draw records: 67,323
- Player-tournament records: 34,053
- OOS test set: 8,990 (2024-2025)
- Tee-wave data: 100% coverage

## Wave Differential Stats
- Mean PM-AM differential: 0.24 strokes
- Std: 0.87
- Events with >2 stroke imbalance: 48/259

## OOS Results by Draw-Edge Quintile
Q1 (worst draw) -> Q5 (best draw)
- P(cut): Q1=0.480, Q5=0.630, diff=+0.150
- P(top_20): Q1=0.146, Q5=0.215, diff=+0.070
- Monotonic: Yes

## Regression (OOS)
- draw_edge coefficient: +0.358
- p-value: 0.0000

## Wave differential distribution
- 10th pct: -0.84
- 90th pct: +1.27
