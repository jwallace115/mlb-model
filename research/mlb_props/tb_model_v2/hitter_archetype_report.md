# Hitter Archetype Report

**Method:** KMeans (k=6) on rolling 20-game pregame features
**Features:** ISO, K rate, zero-TB rate, pct 2+ TB, HR rate, XBH rate

## Archetypes Identified

| Archetype | N (approx) | ISO | K Rate | Zero-TB Rate | Pct 2+ TB | Description |
|:----------|---:|---:|---:|---:|---:|:------------|
| low_impact | ~26K | 0.068 | 0.207 | 0.535 | 0.237 | Bottom-order, low power, high zero-TB |
| low_impact_0.0 | ~29K | 0.106 | 0.277 | 0.487 | 0.271 | High-K, low power, still mostly zeros |
| balanced_2 | ~25K | 0.133 | 0.197 | 0.434 | 0.303 | Average contact hitter, moderate power |
| high_K_power | ~22K | 0.177 | 0.299 | 0.434 | 0.329 | Boom-or-bust: high K, moderate ISO |
| elite_power | ~28K | 0.184 | 0.196 | 0.371 | 0.378 | Best contact + power combo |
| elite_power_2.0 | ~14K | 0.226 | 0.238 | 0.394 | 0.375 | Peak power, slightly more K |

## TB Distribution by Archetype

| Archetype | P(TB=0) | P(TB>=2) | P(TB>=3) | P(TB>=4) |
|:----------|---:|---:|---:|---:|
| low_impact | 0.535 | 0.237 | 0.123 | 0.083 |
| low_impact_0.0 | 0.487 | 0.271 | 0.147 | 0.102 |
| balanced_2 | 0.434 | 0.303 | 0.168 | 0.115 |
| high_K_power | 0.434 | 0.329 | 0.197 | 0.145 |
| elite_power | 0.371 | 0.378 | 0.229 | 0.169 |
| elite_power_2.0 | 0.394 | 0.375 | 0.233 | 0.177 |

The spread between archetypes is meaningful: P(TB=0) ranges from 0.371 (elite_power) to 0.535 (low_impact) — a 16.4pp range. P(TB>=2) ranges from 0.237 to 0.378 — a 14.1pp range.
