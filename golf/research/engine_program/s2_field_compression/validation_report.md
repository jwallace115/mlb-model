# S2 Field Compression Engine — Validation Report

Generated: 2026-03-30T19:53:18

## Classification: STANDALONE

## Feature Definitions
- **skill_proxy**: 0.8 * top_20_prob + 0.2 * win_prob
- **field_skill_std**: std of skill_proxy across field
- **field_entropy**: Shannon entropy of normalized skill weights
- **elite_density**: fraction of field within 50% of best skill_proxy
- **gap_best_to_20th**: skill_proxy(rank 1) - skill_proxy(rank 20)
- **gap_20th_to_60th**: skill_proxy(rank 20) - skill_proxy(rank 60)
- **top_heaviness**: mean(top 10) - mean(ranks 30-60)
- **compression_index**: equal-weight mean of z-scored components (higher = more compressed)

## Frozen Thresholds (2020-2022)
- COMPRESSED: compression_index >= 0.219
- NEUTRAL: -0.102 to 0.219
- STRATIFIED: < -0.102
- Elite density median: 0.1250
- Gap 1-to-20 median: 0.245945

## Structural Patterns (OOS)
- Compressed → more longshot T20: FAIL (0.116 vs 0.138)
- Compressed → more longshot T10: FAIL (0.055 vs 0.056)
- Stratified → higher fav win: PASS (0.0632 vs 0.0211)
- Stratified → higher T5 concentration: PASS (0.208 vs 0.139)

Patterns passing: 2/4

## OOS Overlay Results (threshold=4%)

| Market | Filter | N | Hit Rate | ROI |
|--------|--------|---|----------|-----|
| make_cut | BASELINE | 801 | 75.2% | -1.7% |
| make_cut | COMPRESSED | 266 | 74.1% | -2.6% |
| make_cut | STRATIFIED | 432 | 77.1% | -0.6% |
| top_20 | BASELINE | 750 | 38.4% | -1.4% |
| top_20 | COMPRESSED | 324 | 33.0% | -1.6% |
| top_20 | STRATIFIED | 294 | 43.9% | -4.6% |
| top_10 | BASELINE | 263 | 30.0% | -12.8% |
| top_10 | COMPRESSED | 106 | 19.8% | -29.3% |
| top_10 | STRATIFIED | 125 | 38.4% | -10.7% |
| top_5 | BASELINE | 72 | 33.3% | +10.8% |
| top_5 | COMPRESSED | 21 | 23.8% | +18.8% |
| top_5 | STRATIFIED | 41 | 46.3% | +33.8% |
| win | BASELINE | 2 | 50.0% | +7.0% |
| win | COMPRESSED | 0 | 0.0% | +0.0% |
| win | STRATIFIED | 2 | 50.0% | +7.0% |

## Final Answers
1. Most affected market: top_20
2. Exploitable on its own: Yes
3. Useful as context filter: Yes
4. Path for Top 20: see overlay table above
