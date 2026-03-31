# Data Quality Report — V2 Engine

## Dataset Size
- Total games: 4855
- 2024: 2427
- 2025: 2428

## Coverage of Adjusted Metrics

| Feature | Available | Coverage |
|---------|-----------|----------|
| adj_bb_rate_last3_away | 4648 | 95.7% |
| adj_bb_rate_last3_home | 4665 | 96.1% |
| adj_bb_rate_last5_away | 4565 | 94.0% |
| adj_bb_rate_last5_home | 4589 | 94.5% |
| adj_contact_rate_last3_away | 4648 | 95.7% |
| adj_contact_rate_last3_home | 4665 | 96.1% |
| adj_contact_rate_last5_away | 4565 | 94.0% |
| adj_contact_rate_last5_home | 4589 | 94.5% |
| adj_hard_hit_last3_away | 4571 | 94.2% |
| adj_hard_hit_last3_home | 4557 | 93.9% |
| adj_hard_hit_last5_away | 4513 | 93.0% |
| adj_hard_hit_last5_home | 4512 | 92.9% |
| adj_k_rate_last3_away | 4648 | 95.7% |
| adj_k_rate_last3_home | 4665 | 96.1% |
| adj_k_rate_last5_away | 4565 | 94.0% |
| adj_k_rate_last5_home | 4589 | 94.5% |
| adj_run_suppression_last3_away | 4648 | 95.7% |
| adj_run_suppression_last3_home | 4665 | 96.1% |
| adj_run_suppression_last5_away | 4565 | 94.0% |
| adj_run_suppression_last5_home | 4589 | 94.5% |

## Missing Recent Form
- Games with ALL adjusted features missing: 10 (0.2%)
- Games with ANY adjusted feature missing: 701 (14.4%)

## Pitchers Per Season
- 2024: 369 unique starters, avg 13.2 starts each
- 2025: 368 unique starters, avg 13.2 starts each

## Adjusted Metric Distributions (2024+2025)

| Metric | Mean | Std | p10 | p50 | p90 |
|--------|------|-----|-----|-----|-----|
| adj_k_rate | -0.0325 | 0.1087 | -0.1660 | -0.0390 | 0.1102 |
| adj_bb_rate | -0.0136 | 0.0669 | -0.0898 | -0.0232 | 0.0713 |
| adj_contact_rate | 0.0141 | 0.1024 | -0.1131 | 0.0200 | 0.1368 |
| adj_hard_hit_rate | -0.0047 | 0.1382 | -0.1826 | 0.0007 | 0.1699 |
| adj_run_suppression | -0.0347 | 2.4113 | -3.3611 | 0.3204 | 2.7917 |
