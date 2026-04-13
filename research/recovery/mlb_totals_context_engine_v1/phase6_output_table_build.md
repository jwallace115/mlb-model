# Phase 6 - Engine Output Table Build
## MLB Totals Context Engine V1

### Summary
Frozen formulas from Phase 5 (discovery-derived) applied to all seasons.

**Output:** research/recovery/mlb_totals_context_engine_v1/context_engine_output_table.parquet
**Rows:** 9,715 (2022-2025)
**Columns:** 35

### Output Columns
- Continuous scores: bre, esp, lsp, ss, bs, wpl, tcv (all 0-100 range except wpl which is signed)
- Bucket labels: bre_label, esp_label, lsp_label, ss_label, bs_label, wpl_label, tcv_label, mps_label
- Sub-scores: home_sp_stability, away_sp_stability, home_bp_stability, away_bp_stability
- Binary: both_stable_flag
- Market: market_close_total, market_clv
- Outcomes: actual_total, actual_f5_total
- Context: park_factor_runs, temperature, wind_speed, is_dome_or_closed, umpire_over_rate

### Label Distributions (Discovery 2022-2023)
bre_label
MEDIUM    1622
LOW       1619
HIGH      1619

ss_label
AVERAGE    1622
FRAGILE    1619
STABLE     1619

### Formula Application
All normalizations anchored to discovery distribution stats (FROZEN). No retraining or threshold adjustment on validation or OOS. The same formula coefficients, normalization bounds, and bucket thresholds computed on 2022-2023 data are applied identically to 2024 and 2025 games.

Built: 2026-04-12
