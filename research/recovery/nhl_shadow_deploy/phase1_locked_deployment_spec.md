# NHL Shadow Deployment: Locked Specification

## Date: 2026-04-11
## Object ID: nhl_shadow_aligned_20260411

---

## 1. Model Artifacts

| Component | Path | Status |
|-----------|------|--------|
| Home Ridge Model | research/recovery/nhl_final_alignment/model_A_home.pkl | VERIFIED |
| Away Ridge Model | research/recovery/nhl_final_alignment/model_A_away.pkl | VERIFIED |
| Feature Table | nhl/nhl_feature_table.parquet | EXISTING |
| Canonical Games | nhl/nhl_games_canonical.csv | EXISTING |

## 2. Model Loading Change

**Before:** Pipeline uses fallback cascade:
- REBUILD_HOME = research/recovery/nhl_rebuild/model_A_home.pkl (checked first)
- HOME_PKL = nhl/ridge_home_model.pkl (fallback)

**After:** Pipeline uses final aligned models directly:
- REBUILD_HOME = research/recovery/nhl_final_alignment/model_A_home.pkl
- REBUILD_AWAY = research/recovery/nhl_final_alignment/model_A_away.pkl

## 3. Drift Correction

| Parameter | Old Value | New Value | Rationale |
|-----------|-----------|-----------|-----------|
| VALIDATE_DRIFT | 0.4458 | 0.0 | Aligned model predicts higher natively; OOS bias at 0.0 is -0.14 (near neutral) |

## 4. Edge Threshold

| Parameter | Value | Change |
|-----------|-------|--------|
| THRESHOLD | 0.12 | NO CHANGE |

## 5. Confidence Tiers

| Tier | Edge Requirement | Vol Requirement | Status |
|------|-----------------|-----------------|--------|
| HIGH | edge >= 0.15 | vol_bucket != "high" | ACTIVE (1.0 units) |
| MEDIUM | 0.12 <= edge < 0.15 | -- | SHADOW (0.0 units) |
| LOW | edge < 0.12 | -- | SHADOW (0.0 units) |

## 6. Stop Rules (nhl/data/nhl_stop_rules.json)

Already configured correctly:
- high_tier: active
- medium_tier: shadow
- low_tier: shadow
- evaluation_date: 2026-05-01

## 7. Disabled/Bypassed Components

| Component | Status | Reason |
|-----------|--------|--------|
| MoneyPuck fallback | ALREADY ABSENT | Pipeline uses NHL API only since rebuild |
| Old push corrections (INT_LINE_CORRECTIONS) | RETAINED | Sim-level push adjustment, model-independent |
| Legacy drift 0.4458 | DISABLED | Set to 0.0 |
| Old model paths (nhl_rebuild/) | BYPASSED | New aligned paths take priority |

## 8. New Tracker

File: nhl/logs/nhl_shadow_aligned_2026.json
- Initialized on 2026-04-11
- Pipeline writes aligned-model signals here in addition to nhl_decisions.parquet
- Tracks model_version = "model_A_aligned_v1"

## 9. Monitoring Thresholds

| Metric | Warning | Action |
|--------|---------|--------|
| Pred-vs-actual bias | +/- 0.2 after 50 games | Recalibrate drift |
| Monthly win rate | < 45% | Review model stability |
| HIGH tier WR | < 52% after 50 signals | Consider pausing HIGH tier |
