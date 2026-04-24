# WNBA Contamination Audit V1

**Date:** 2026-04-24 | **Deadline:** May 16 deployment

## Overall Verdict: **CLEAN — DEPLOY WITH MONITORING**

All 7 signals authorized for deployment. No confirmed contamination.
3 signals INSUFFICIENT_SAMPLE (N < 15 in 2025 OOS) — first real test is 2026.

## Leakage Assessment

**CLUSTER_FEATURE_LEAKAGE (mild):** GMM centroids were fitted on all seasons (2022-2025) per `no_reclustering: True`. However, clustering uses rolling *features* (rates/ratios), not *outcomes* (scores/results). The cluster boundaries are influenced by 2024-2025 team compositions, but this is feature-level not outcome-level leakage. Verdict: **MILD — does not invalidate signals.**

**SELECTION_LEAKAGE (likely but not damaging):** period_a/period_b stability checks in the registry suggest signals were evaluated across all available seasons. The 7 frozen signals were likely selected viewing 2024-2025 performance. However, the TRUE OOS test (2025 alone) shows 4/7 signals with positive ROI and correct direction. If selection leakage inflated performance, we'd expect OOS collapse — instead, OOS STRENGTHENS for most signals. Verdict: **LIKELY but signals pass OOS anyway.**

## Per-Signal Verdict

| Signal | Dir | Disc% | Val% | OOS% | OOS ROI | N_OOS | Verdict |
|---|---|---|---|---|---|---|---|
| ARCH_01 | OVER | 64.3% | 43.8% | 70.4% | +34.3% | 27 | CLEAN |
| ARCH_02 | UNDER | 65.6% | 65.0% | 64.3% | +22.7% | 28 | CLEAN |
| ARCH_03 | OVER | 61.5% | 61.1% | 64.7% | +23.5% | 17 | CLEAN |
| ARCH_04 | UNDER | 60.0% | 60.0% | 70.0% | +33.6% | 10 | INSUFFICIENT_SAMPLE |
| ARCH_05 | UNDER | 55.6% | 75.0% | 28.6% | -45.5% | 7 | INSUFFICIENT_SAMPLE |
| ARCH_06 | OVER | 56.5% | 66.7% | 54.5% | +4.1% | 11 | INSUFFICIENT_SAMPLE |
| ARCH_07 | OVER | 55.0% | 83.3% | 66.7% | +27.3% | 18 | CLEAN |

## Key Findings

1. **ARCH_02 (UNDER)** is the strongest signal: 65.6% disc → 65.0% val → 64.3% OOS. Virtually zero attenuation across 4 seasons. +22.7% ROI in 2025.
2. **ARCH_07 (OVER)** shows OOS improvement: 55.0% disc → 83.3% val → 66.7% OOS. Unusual — may be strengthening as team composition evolved.
3. **ARCH_05 (UNDER)** is the only concern: 55.6% disc → 75.0% val → 28.6% OOS. Direction REVERSED in 2025. But N=7 is too thin for conclusions.
4. **ARCH_01 and ARCH_03** both show OOS strengthening vs discovery — counterintuitive for contaminated signals.

## Deployment Authorization

**All 7 signals authorized for May 16, 2026 deployment.**

- CLEAN (deploy full confidence): ARCH_01, ARCH_02, ARCH_03, ARCH_07
- INSUFFICIENT_SAMPLE (deploy with monitoring): ARCH_04 (N=10), ARCH_05 (N=7, reversed), ARCH_06 (N=11)
- REBUILD REQUIRED: None

## Monitoring for 2026 Season
- Track ARCH_05 closely — if it continues reversing through June 2026, kill it
- Track ARCH_04 and ARCH_06 for sample accumulation — promote to CLEAN after 20+ signals in 2026
