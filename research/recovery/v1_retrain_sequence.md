# V1 Ridge Retrain Sequence

**Date:** 2026-04-10
**Prerequisite:** PIT-clean feature table built (see v1_clean_rebuild_plan.md)

---

## Sequence Overview

1. Build PIT-clean feature table
2. Merge with clean features (bullpen shift(1), park, weather, umpire, schedule)
3. Retrain Ridge with alpha sweep
4. Evaluate against contaminated V1 (expect worse in-sample, that is correct)
5. Run honest OOS backtest against real closing lines
6. If OOS is viable: swap model pkl
7. Cascade: retrain S2, re-derive S12/F5 thresholds

---

## Step 1: Build PIT Feature Table

**Script:** `research/recovery/v1_clean_features/build_v1_pit_features.py`

```
Input:
  - mlb/data/pitcher_game_logs.parquet (84,669 rows)
  - sim/data/game_table.parquet (9,715 games)
  - research/mlb_side_engine/clean_features/baseball_features_pit.parquet (existing)
  - sim/data/bullpen_features.parquet (existing, shift(1) clean)

Output:
  - research/recovery/v1_clean_features/v1_feature_table_pit.parquet
```

New features to add (beyond what side engine already built):
- `home_sp_k_pct_pit`, `away_sp_k_pct_pit`
- `home_sp_bb_pct_pit`, `away_sp_bb_pct_pit`
- `home_sp_avg_ip_pit`, `away_sp_avg_ip_pit`
- `fb_proxy_pit` (optional: fly_outs / (fly_outs + ground_outs))

Reuse from existing side engine build:
- `home_sp_fip_pit`, `away_sp_fip_pit`
- `home_bp_fip_pit`, `away_bp_fip_pit`
- `home_offense_rpg_pit`, `away_offense_rpg_pit`

Reuse from existing feature_table (clean columns only):
- `park_factor_runs`, `park_factor_hr`
- `temperature`, `wind_factor_effective`
- `umpire_over_rate`
- `home_rest_days`, `away_rest_days`
- `doubleheader_flag`

Reuse from existing bullpen_features.parquet:
- `home_high_leverage_avail`, `away_high_leverage_avail`

Compute new derived features:
- `home_bullpen_delta_pit = home_sp_fip_pit - home_bp_fip_pit`
- `away_bullpen_delta_pit = away_sp_fip_pit - away_bp_fip_pit`
- `home_bp_delta_exposure_pit = home_bullpen_delta_pit * (9 - home_sp_avg_ip_pit)`
- `away_bp_delta_exposure_pit = away_bullpen_delta_pit * (9 - away_sp_avg_ip_pit)`
- `flyball_wind_pit = fb_proxy_pit * wind_factor_effective` (optional)

---

## Step 2: Validate Feature Table

Before training, run these checks:

### 2a. Coverage gate
```
For each season (2022-2025):
  - SP FIP fill rate >= 75% (May-Oct)
  - BP FIP fill rate >= 90%
  - Offense RPG fill rate >= 95%
  - Total usable rows (no NaN in any feature) >= 6,000 across 4 seasons
```

### 2b. Divergence check
```
For 20 random mid-season games:
  - PIT sp_fip != contaminated sp_xfip (they MUST differ)
  - PIT offense_rpg != contaminated wrc_plus (they MUST differ)
  - Typical delta: 0.1-0.5 for SP, 10-30 for offense metric
```

### 2c. Correlation sanity
```
- corr(sp_fip_pit, actual_total) should be positive (higher FIP = more runs)
- corr(offense_rpg_pit, actual_total) should be positive
- corr(bp_fip_pit, actual_total) should be positive
- All correlations should be WEAKER than contaminated version (less lookahead signal)
```

---

## Step 3: Retrain Ridge

**Script:** `research/recovery/v1_clean_features/retrain_v1_pit.py`

### 3a. Feature set definition
```python
PIT_FEATURES = [
    "home_sp_fip_pit", "away_sp_fip_pit",
    "home_sp_k_pct_pit", "away_sp_k_pct_pit",
    "home_sp_bb_pct_pit", "away_sp_bb_pct_pit",
    "home_sp_avg_ip_pit", "away_sp_avg_ip_pit",
    "home_offense_rpg_pit", "away_offense_rpg_pit",
    "park_factor_runs", "park_factor_hr",
    "temperature", "wind_factor_effective",
    "umpire_over_rate",
    "home_rest_days", "away_rest_days",
    "doubleheader_flag",
    # flyball_wind_pit — include in ablation, may not survive
    "home_high_leverage_avail", "away_high_leverage_avail",
    "home_bullpen_delta_pit", "away_bullpen_delta_pit",
    "home_bp_delta_exposure_pit", "away_bp_delta_exposure_pit",
]
```

### 3b. Train/validate/OOS split
- **Train:** 2022 + 2023 (same as contaminated V1)
- **Validate:** 2024 (same as contaminated V1)
- **OOS:** 2025 (same as contaminated V1)

### 3c. Alpha sweep
```python
alphas = [10, 25, 50, 75, 100, 150, 200, 300, 500]
# Expect optimal alpha to be HIGHER than 50 (more regularization needed
# because PIT features are noisier than contaminated features)
```

### 3d. Metrics to record
For each alpha, record:
- Train RMSE, R-squared
- Validate RMSE, R-squared
- OOS RMSE, R-squared
- Sigma (std of residuals on validate set)
- Feature coefficients

### 3e. Ablation
Run with and without:
- flyball_wind_pit (may not survive)
- bullpen_delta_pit features (survived in Phase 8 with contaminated data — check PIT)
- high_leverage_avail (was clean in Phase 8 — should survive)

---

## Step 4: Honest OOS Backtest

**Must use real closing lines** (from `sim/data/market_snapshots.parquet`).

### 4a. Edge calculation
```
For each 2025 game:
  fair_total = PIT Ridge mean prediction
  edge = fair_total - closing_line (for UNDER: edge = closing_line - fair_total)
  p_under = P(total < closing_line) from sim with PIT sigma
```

### 4b. Report metrics
- ROI at various thresholds (edge >= 0.5/1.0/1.5, P >= 0.55/0.57/0.60)
- Compare to contaminated V1 OOS results:
  - Contaminated 2025 OOS: -0.3% ROI (Phase 8 trimmed)
  - Contaminated STRONG tier 2025: +2.3% ROI
- If PIT model 2025 OOS ROI is within 3pp of contaminated: ACCEPTABLE
- If PIT model 2025 OOS ROI is > 3pp worse: investigate before deploying

### 4c. Directional hit rate
- % of games where model correctly predicts over/under
- Should be > 50% at all confidence thresholds
- Compare to contaminated V1 directional accuracy

---

## Step 5: Model Swap (if Step 4 passes)

### 5a. Save new model
```
sim/data/phase9_baseline_model_pit.pkl  (new)
sim/data/phase9_baseline_model_contaminated.pkl  (rename old)
sim/data/phase9_baseline_model.pkl  (copy of _pit)
```

### 5b. Update sigma
```
config.py: Update sigma from 4.361 to new PIT sigma (expect 4.4-4.6)
```

### 5c. Update sim_projections.py
```
If feature names changed (e.g., fip_pit instead of xfip):
  Update the feature vector assembly in sim_project_game()
  Map live FG xFIP to the fip_pit slot (or use live FIP if available)
```

---

## Step 6: Cascade Retrains

### 6a. S2 Starter Path Model
- Replace `sp_xfip` with `sp_fip_pit` in sim_inputs
- Retrain S2 on 2022-2023, evaluate on 2024
- Compare path accuracy to contaminated S2
- Save new starter_path_model.pkl

### 6b. S12 Overlay Cutoff
- Recompute S12 values using PIT xFIP proxy
- Re-derive P80 cutoff from 2024 PIT data
- Update s12_overlay_config.json

### 6c. F5 Thresholds
- Re-run F5 threshold sweep using PIT V1 probabilities
- May need to adjust 0.57 threshold

### 6d. F5 Run Line
- Validate xFIP gap >= 1.0 threshold against PIT FIP gap
- Adjust if FIP gap distribution differs materially from xFIP gap

---

## Timeline Estimate

| Step | Effort | Dependency |
|------|--------|------------|
| Build PIT features (K%, BB%, avg_ip) | 2-3 hours | None |
| Assemble V1 feature table | 1-2 hours | Step 1 |
| Validate | 1 hour | Step 2 |
| Retrain Ridge + ablation | 2-3 hours | Step 3 |
| OOS backtest | 1-2 hours | Step 4 |
| Model swap | 30 min | Step 5 |
| S2 retrain | 1-2 hours | Step 6 |
| S12/F5 re-derive | 1-2 hours | Step 7 |
| **Total** | **~10-15 hours** | **1-2 days** |

---

## Go/No-Go Criteria

**GO** (swap to PIT model):
- 2025 OOS ROI within 3pp of contaminated V1
- Directional accuracy > 50% at P >= 0.55
- Sigma increase < 0.5 (from 4.361)
- No feature with coefficient sign flip vs contaminated model

**NO-GO** (keep contaminated V1 live, continue research):
- 2025 OOS ROI > 5pp worse than contaminated V1
- Sigma > 5.0 (model too noisy to generate signals)
- Directional accuracy < 50% (model is not predictive)

**PARTIAL** (swap model but tighten thresholds):
- 2025 OOS ROI 3-5pp worse
- Raise minimum edge threshold from 0.5 to 1.0
- Raise minimum P threshold from 0.55 to 0.57
