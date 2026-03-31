# TB Model v2 — Archetype Interaction Engine Report

**Date:** 2026-03-27
**Status:** Research prototype — NOT deployed
**Output:** `research/mlb_props/tb_model_v2/`

---

## Executive Summary

| Question | Answer |
|:---------|:-------|
| Did hitter archetypes improve prediction? | **No.** +0.0000 to -0.0008 AUC lift. |
| Did pitcher archetypes improve prediction? | **No.** -0.0002 to +0.0007 AUC lift. |
| Did interaction improve the model? | **No.** Full interaction model (43 features) performs at or slightly below v1 baseline (16 features). |
| Which combinations matter most? | Descriptively interesting but not predictively useful beyond the continuous features already in v1. |
| Does v2 improve backtests? | **No.** V2 edge and win rates are identical to v1 within rounding. |

**Verdict: SHELVE ARCHETYPE ENGINE**

---

## 1. Model Architecture

### Hitter Archetypes (6 clusters via KMeans)

| Archetype | Key Profile | P(TB=0) | P(TB>=2) |
|:----------|:------------|---:|---:|
| low_impact | ISO 0.068, K% 20.7%, slot ~7 | 0.535 | 0.237 |
| low_impact_0.0 | ISO 0.106, K% 27.7% | 0.487 | 0.271 |
| balanced_2 | ISO 0.133, K% 19.7% | 0.434 | 0.303 |
| high_K_power | ISO 0.177, K% 29.9% | 0.434 | 0.329 |
| elite_power | ISO 0.184, K% 19.6% | 0.371 | 0.378 |
| elite_power_2.0 | ISO 0.226, K% 23.8% | 0.394 | 0.375 |

Hitter archetype spread: P(TB=0) ranges 0.371–0.535 (16.4pp). Meaningful descriptively.

### Pitcher Archetypes (6 clusters via KMeans)

| Archetype | Key Profile | Batter P(TB=0) | Batter P(TB>=2) |
|:----------|:------------|---:|---:|
| power_arm | Whiff 28.5%, K% 26.7% | 0.466 | 0.299 |
| barrel_suppressor | Barrel 2.8%, HH 33.6% | 0.455 | 0.308 |
| gb_suppressor | GB% 43.0% | 0.445 | 0.313 |
| contact_mgr | Whiff 22.8%, K% 19.9% | 0.428 | 0.328 |
| flyball_damage | Barrel 5.4%, HH 41.0% | 0.431 | 0.330 |

Pitcher archetype spread: P(TB=0) ranges 0.428–0.466 (**only 3.8pp**). Much narrower than hitter archetypes.

---

## 2. Model Comparison (AUC on 2025 Validation)

### P(TB = 0)

| Model | Features | AUC | vs Baseline |
|:------|---:|---:|---:|
| **A: Baseline (v1)** | 16 | **0.6182** | — |
| B: + Hitter archetypes | 22 | 0.6179 | **-0.0003** |
| C: + Pitcher archetypes | 22 | 0.6180 | -0.0002 |
| D: Full interaction | 43 | 0.6174 | **-0.0008** |

### P(TB >= 2)

| Model | Features | AUC | vs Baseline |
|:------|---:|---:|---:|
| **A: Baseline (v1)** | 16 | 0.6079 | — |
| B: + Hitter archetypes | 22 | 0.6080 | +0.0001 |
| C: + Pitcher archetypes | 22 | 0.6086 | **+0.0007** |
| D: Full interaction | 43 | 0.6084 | +0.0005 |

### P(TB >= 3)

| Model | Features | AUC | vs Baseline |
|:------|---:|---:|---:|
| **A: Baseline (v1)** | 16 | **0.6120** | — |
| B: + Hitter archetypes | 22 | 0.6114 | -0.0006 |
| C: + Pitcher archetypes | 22 | 0.6109 | -0.0011 |
| D: Full interaction | 43 | 0.6119 | -0.0001 |

**The full interaction model (43 features) never beats the 16-feature v1 baseline by more than 0.0005 AUC on any target. On 2 of 3 targets, it is worse.**

---

## 3. Why Archetypes Don't Help

### The continuous features already capture the archetype information

The v1 baseline includes `h_zero_tb_rate`, `h_iso`, `h_slg`, `h_k_rate`, `p_barrel_rate`, `p_hard_hit_rate`, `p_whiff_rate` — the same inputs used to define the archetypes. A GBT with 300 trees and depth 4 can already learn arbitrary nonlinear interactions between these continuous features. Adding discrete cluster labels provides no new information.

### Feature importance confirms archetypes are ignored

In the full v2 model, the top 10 features are all continuous v1-era features. No archetype dummy or interaction term appears in the top 10 for any target. The GBT correctly assigns near-zero importance to the archetype labels.

| Rank | Feature | Importance (tb_zero) |
|---:|:--------|---:|
| 1 | h_zero_tb_season | 0.3385 |
| 2 | batting_order_slot | 0.1548 |
| 3 | h_zero_tb_rate | 0.1110 |
| 4 | h_pct_2plus | 0.0476 |
| 5 | p_whiff_rate | 0.0440 |
| 6 | h_k_rate | 0.0423 |
| 7 | h_tb_var | 0.0383 |
| 8 | h_slg | 0.0341 |
| 9 | p_hard_hit_rate | 0.0287 |
| 10 | ondeck_woba_proxy | 0.0270 |

### Pitcher archetype spread is too narrow

The maximum P(TB=0) difference between pitcher archetypes is only 3.8pp (power_arm 0.466 vs contact_mgr 0.428). For P(TB>=2) it's only 3.1pp. This is not enough to meaningfully shift probabilities beyond what the continuous pitcher features already capture.

By contrast, hitter archetypes span 16.4pp on P(TB=0) — but this spread is already captured by `h_zero_tb_rate` and `h_iso`, which are the top features.

---

## 4. Interaction Matrix — Descriptively Interesting

### Strongest Under-Leaning Cells (highest P(TB=0))

| Hitter | Pitcher | N | P(TB=0) | P(TB>=2) |
|:-------|:--------|---:|---:|---:|
| low_impact | power_arm | 3,606 | 0.556 | 0.221 |
| low_impact | barrel_suppressor | 3,134 | 0.546 | 0.231 |
| low_impact | gb_suppressor | 1,856 | 0.580 | 0.213 |

### Strongest Over-Leaning Cells (highest P(TB>=2))

| Hitter | Pitcher | N | P(TB=0) | P(TB>=2) |
|:-------|:--------|---:|---:|---:|
| elite_power | contact_mgr_3.0 | 3,728 | 0.347 | 0.414 |
| elite_power | contact_mgr | 3,649 | 0.343 | 0.411 |
| elite_power_2.0 | contact_mgr_3.0 | 1,999 | 0.386 | 0.401 |

These match intuition (weak hitters vs power arms = zeros; elite power vs contact managers = XBH). But the GBT already learns this from the continuous features without needing explicit archetype labels.

---

## 5. Backtest Comparison (v2 vs v1)

### Under 1.5 TB — All Books

| Edge Threshold | v2 N | v2 Win | v1 N | v1 Win |
|---:|---:|---:|---:|---:|
| >= 0.03 | 4,689 | 0.631 | 4,664 | 0.628 |
| >= 0.05 | 3,935 | 0.624 | 3,927 | 0.626 |
| >= 0.07 | 2,980 | 0.617 | 3,005 | 0.618 |
| >= 0.10 | 1,670 | 0.603 | 1,640 | 0.601 |

### Under 2.5 TB — All Books

| Edge Threshold | v2 N | v2 Win | v1 N | v1 Win |
|---:|---:|---:|---:|---:|
| >= 0.03 | 3,829 | 0.768 | 3,859 | 0.768 |
| >= 0.05 | 2,885 | 0.763 | 2,885 | 0.765 |
| >= 0.07 | 1,929 | 0.752 | 1,942 | 0.748 |
| >= 0.10 | 968 | 0.729 | 978 | 0.731 |

**V2 and v1 produce virtually identical backtest results at every threshold.** The archetype engine adds no market edge.

---

## 6. Answers to Key Questions

### 1. Did hitter archetypes improve prediction beyond v1?
**No.** Adding 6 hitter archetype dummies produced -0.0003 to +0.0001 AUC lift (within noise). The continuous features (ISO, K rate, zero-TB rate) already encode the same information.

### 2. Did pitcher archetypes improve prediction beyond v1?
**No.** Adding 6 pitcher archetype dummies produced -0.0011 to +0.0007 AUC lift. The best case (+0.0007 on tb_over_1_5) is marginal and not consistent across targets.

### 3. Did hitter × pitcher interaction materially improve the model?
**No.** The full interaction model (43 features) is at or below the 16-feature baseline on all three targets. The GBT's tree structure already captures nonlinear interactions between the continuous features.

### 4. Which archetype combinations matter most?
Descriptively: low_impact × power_arm (56% zero-TB) and elite_power × contact_mgr (41% Over 1.5) are the extreme cells. But these are perfectly predicted by the continuous features without archetype labels.

### 5. Does v2 improve Under 1.5 or Under 2.5 backtests?
**No.** Win rates at every edge threshold are within 0.3pp of v1 — indistinguishable.

---

## 7. Verdict

### SHELVE ARCHETYPE ENGINE

The archetype approach is a dead end for this problem. The v1 continuous-feature backbone (zero_tb_rate, ISO, K rate, pitcher whiff/barrel rates) already captures all the information that discrete archetypes encode. Adding 27 archetype and interaction features to 16 baseline features produces zero improvement on any metric.

### Why this happened

1. **GBT already handles interactions.** A tree-based model with depth 4 can learn `if (ISO > 0.18 AND whiff_rate > 0.27)` directly. Discretizing into archetype labels loses precision without adding information.

2. **Pitcher archetypes are too homogeneous.** The 3.8pp P(TB=0) spread between pitcher types is too narrow to create meaningful interaction effects beyond what the continuous metrics capture.

3. **The TB distribution is fundamentally noisy.** A single plate appearance has enormous variance. Archetypes can describe population-level tendencies, but the per-PA signal-to-noise ratio is too low for categorical groupings to improve on the continuous rolling averages.

### What to try instead (if continuing TB research)

1. **Platoon splits** — batter hand × pitcher hand interaction (available in hitter game logs, not yet used)
2. **Pitch-mix features** — fastball/breaking/offspeed exposure rates if available
3. **Count-level modeling** — if pitch-by-pitch data exists, model at the AB level rather than PA level
4. **Ensemble stacking** — combine the v1 probability model with a separate model for P(XBH | hit) to improve tail prediction

None of these are archetype-based — they represent genuinely new information sources rather than repackaging existing features.

---

## Output Files

| File | Description |
|:-----|:------------|
| `tb_model_v2_dataset.parquet` | Full modeling table (201,605 rows) |
| `hitter_archetypes.parquet` | Hitter archetype profiles |
| `pitcher_archetypes.parquet` | Pitcher archetype profiles |
| `archetype_interaction_matrix.parquet` | Full H × P interaction matrix |
| `model_predictions_v2.parquet` | 2025 validation predictions (v1 + v2) |
| `model_backtest_v2.parquet` | Market backtest by book |
| `model_comparison.parquet` | A/B/C/D model comparison |
| `source_audit.md` | Data source audit |
| `hitter_archetype_report.md` | Hitter archetype details |
| `pitcher_archetype_report.md` | Pitcher archetype details |
| `tb_model_v2_report.md` | This report |
