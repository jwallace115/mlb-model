# MLB Archetype Engine V1-Lite — Rerun After Source Fix: Report

**Run date:** 2026-04-14
**Pipeline object:** V1-Lite (exact same parameters as prior run)
**Purpose:** Verify home/away flag integrity, rerun all stages, compare to prior

---

## 1. Source Repair Summary

| Metric | Value |
|---|---|
| hitter_game_logs rows | 204,548 |
| H rows before | 102,121 |
| A rows before | 102,427 |
| H rows after | 102,121 |
| A rows after | 102,427 |
| Rows changed | **0** |
| Both-A games (before) | 0 |
| Both-A games (after) | 0 |
| Unresolved rows | 0 (0.00%) |
| Backup created | mlb/data/hitter_game_logs_pre_ha_fix_backup.parquet |

**Diagnosis:** The home_away flag in the source file was already balanced and correct. The prior run's claim of "128K away vs 76K home rows" was a **false diagnosis**. No structural asymmetry exists in the raw source data.

---

## 2. Coverage Change (Prior Run → Rerun)

| Metric | Prior Run | Rerun |
|---|---|---|
| Home lineup coverage | 26.7% | **98.4%** |
| Away lineup coverage | 98.2% | **98.4%** |
| SP coverage (both dims) | (not reported) | 90.4% |
| Discovery games (full coverage) | (not reported) | 2,233 / 4,860 |
| Validation games (full coverage) | (not reported) | 1,242 / 2,427 |
| OOS games (full coverage) | (not reached) | 1,161 / 2,428 |

**Root cause of prior run's low home coverage:** The prior pipeline had a column name bug. The `pitcher_id` column referenced in the starter eval step does not exist in `pitcher_game_logs.parquet` — the correct column is `player_id`. This caused the starter features (sp_bat_miss, sp_command) to be null for all rows processed through the starters groupby. The null SP features caused game-level rows to be dropped during the full-coverage filter (LINEUP_COLS + SP_COLS). The asymmetry in the prior run's reported coverage was an artifact of how nulls were counted, not an actual home_away imbalance.

---

## 3. Tercile Cuts Comparison

| Dimension | Prior Run | Rerun |
|---|---|---|
| Patience lo / hi | 0.07576 / 0.09043 | 0.0729 / 0.0867 (home), 0.0724 / 0.0870 (away) |
| Damage lo / hi | 0.14315 / 0.17030 | 0.1435 / 0.1720 (home), 0.1441 / 0.1697 (away) |
| SP K% lo / hi | 0.18966 / 0.24194 | 0.1902 / 0.2426 (home), 0.1925 / 0.2427 (away) |
| SP BB% lo / hi | 0.06061 / 0.08661 | 0.0627 / 0.0878 (home), 0.0619 / 0.0880 (away) |

Cuts are materially identical — computed from the same 2022-2023 discovery window against the same underlying data, just with different effective sample sizes due to the SP feature fix.

---

## 4. Discovery Results

| Metric | Prior Run | Rerun |
|---|---|---|
| Active cells (n≥20) | (not reported) | 16 / 16 |
| Max \|residual\| | 0.804 | **1.1581** |
| Mean \|residual\| | (not reported) | 0.3347 |
| Pass threshold (≥0.50) | YES | YES |

**Top 10 discovery cells (rerun):**

| Lineup Arch | SP Profile | N | Residual |
|---|---|---|---|
| IMPATIENT_WEAK | WILD_POWER | 53 | −1.158 |
| IMPATIENT_POWER | ELITE | 43 | −0.775 |
| IMPATIENT_WEAK | VULNERABLE | 80 | +0.684 |
| IMPATIENT_POWER | CONTACT | 26 | −0.552 |
| PATIENT_CONTACT | CONTACT | 32 | +0.446 |
| PATIENT_CONTACT | ELITE | 54 | −0.438 |
| PATIENT_DAMAGE | VULNERABLE | 85 | +0.326 |
| PATIENT_DAMAGE | CONTACT | 58 | +0.219 |
| PATIENT_DAMAGE | ELITE | 64 | −0.213 |
| IMPATIENT_WEAK | ELITE | 81 | −0.147 |

Discovery PASSED (threshold 0.50). Directional patterns are economically coherent: impatient lineups score fewer runs against high-K/power pitchers; patient lineups benefit against hittable pitchers.

---

## 5. Validation Results (2024)

| Metric | Prior Run | Rerun |
|---|---|---|
| Validation games (full cov) | (not reported) | 1,242 |
| Cells compared (disc ∩ val) | (not reported) | 15 |
| Directional consistency | **40.0%** | **66.7%** |
| Pass threshold (≥60%) | **FAIL** | **PASS** |

**Change:** Validation flips from FAIL (40%) to PASS (66.7%) once SP features are correctly populated. The prior run's validation failure was driven by the null SP features, not by the signal being absent.

**Top 10 validation cells (rerun):**

| Lineup Arch | SP Profile | N | Residual |
|---|---|---|---|
| PATIENT_DAMAGE | VULNERABLE | 26 | +1.316 |
| PATIENT_CONTACT | WILD_POWER | 20 | −1.054 |
| IMPATIENT_WEAK | ELITE | 49 | −0.896 |
| IMPATIENT_POWER | VULNERABLE | 27 | +0.847 |
| PATIENT_DAMAGE | ELITE | 32 | −0.751 |
| PATIENT_CONTACT | CONTACT | 22 | +0.709 |
| IMPATIENT_WEAK | VULNERABLE | 31 | −0.703 |
| IMPATIENT_POWER | WILD_POWER | 17 | +0.585 |
| IMPATIENT_WEAK | CONTACT | 36 | +0.489 |
| PATIENT_DAMAGE | WILD_POWER | 18 | +0.436 |

---

## 6. OOS Results (2025) — New

| Metric | Value |
|---|---|
| OOS games (full coverage) | 1,161 / 2,428 |
| Cells compared (disc ∩ OOS) | 16 |
| Directional consistency | **43.8%** |
| Pass threshold (≥60%) | **FAIL** |

**Top 10 OOS cells (rerun):**

| Lineup Arch | SP Profile | N | Residual |
|---|---|---|---|
| IMPATIENT_POWER | CONTACT | 18 | +0.911 |
| IMPATIENT_POWER | VULNERABLE | 27 | +0.879 |
| PATIENT_CONTACT | ELITE | 22 | −0.864 |
| PATIENT_DAMAGE | VULNERABLE | 43 | +0.750 |
| IMPATIENT_WEAK | ELITE | 34 | −0.717 |
| PATIENT_CONTACT | WILD_POWER | 30 | −0.509 |
| IMPATIENT_WEAK | CONTACT | 28 | −0.435 |
| IMPATIENT_WEAK | WILD_POWER | 30 | +0.422 |
| PATIENT_CONTACT | VULNERABLE | 28 | −0.401 |
| IMPATIENT_POWER | ELITE | 32 | −0.387 |

OOS dir consistency of 43.8% is below chance (50%). Signal that appeared in discovery and validated weakly in 2024 does not survive into 2025. Several cells flip sign.

---

## 7. Verdict

| | Prior Run | Rerun |
|---|---|---|
| Discovery | PASS | PASS |
| Validation | **FAIL** | **PASS** |
| OOS | Not reached | **FAIL** |
| **Verdict** | **NO-GO** | **NO-GO** |

**Verdict unchanged: NO-GO.**

The rerun reveals that the prior run's FAIL was premature and had the wrong cause (null SP features, not home_away asymmetry). With correct SP features:
- Discovery signal is stronger (max residual 1.158 vs 0.804)
- Validation passes (66.7% vs 40%)
- BUT OOS 2025 fails (43.8% dir consistency)

The true cause of the NO-GO is absence of stable out-of-sample signal, not data corruption.

---

## 8. Self-Audit

- Source repair: CONFIRMED clean (0 rows changed, 0 unresolved, 0 both-A games)
- Coverage: BALANCED (H=98.4%, A=98.4% — symmetric)
- Tercile cuts: CONSISTENT with prior run values
- Lookahead: NONE — all rolling features use shift(1)
- OLS controls: home_ops / away_ops as broad run-scoring controls
- Min cell size: n≥20 discovery, n≥15 validation/OOS
- Directional threshold: 60% (same as prior)
- HARD STOP checks: only-A games=0 (pass), unresolved=0% (pass)

---

## 9. Output Files

| File | Description |
|---|---|
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_REPORT.md | This report |
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_REGISTRY.json | Machine-readable registry |
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_STAGE_TABLES.csv | Per-cell residuals across all 3 stages |
| MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_SELF_AUDIT.md | Self-audit checklist |
| _rerun_results.pkl | Python pickle of results_summary dict |
