# TB Props — Pre-Model Diagnostics Report

**Date:** 2026-03-27
**Source:** `research/mlb_props/tb_props/tb_props_dataset.parquet`
**Records:** 32,756 across 9 bookmakers, 2024-2025 seasons

---

## Executive Summary

| Diagnostic | Conclusion |
|:-----------|:-----------|
| Bookmaker split | Overpricing bias is **market-wide**, not driven by one book. FanDuel and BetOnline both show actual < implied on Over side. BetOnline 2.5 line shows the largest edge (-12.2pp) with positive Under ROI (+16%). |
| Odds bucket | **No** — Under ROI is **negative in every bucket** with meaningful sample size. The two-sided book sample is too small (N=412 at 1.5, N=41 at 2.5) to draw reliable conclusions. |
| Narrative buckets | **No bucket exceeds 7pp edge.** Bucket B (top-order power) shows the most lift vs baseline (+4.6pp at 1.5, +6.3pp at 2.5) but remains below the 7pp threshold. Under ROI is negative everywhere. |
| Zero-TB pricing | The market **overprices** P(TB=0), not underprices it. Actual P(TB=0) = 40.1% vs implied 48.3% (two-sided books). Under 0.5 ROI = -12.6%. The "nothing happens" outcome is already priced too high. |

---

## Diagnostic 1 — Edge by Bookmaker

Only 3 book-line combinations meet the N >= 500 threshold.

| bookmaker | line | N | actual_over | implied_over | edge | under_roi |
|:----------|-----:|-----:|---------:|----------:|------:|----------:|
| fanduel | 1.5 | 5,844 | 0.3595 | 0.4077 | -0.0482 | N/A* |
| fanduel | 2.5 | 5,534 | 0.2136 | 0.2423 | -0.0287 | N/A* |
| betonlineag | 2.5 | 578 | 0.1886 | 0.3104 | -0.1218 | +0.16 |

*FanDuel records have Over odds only (no Under odds available), so Under ROI cannot be computed.

**Key observations:**
- The edge is **negative** (actual Over rate < implied Over rate) across all qualifying books, confirming the bias is market-wide
- BetOnline at the 2.5 line shows the largest edge at -12.2pp with a positive Under ROI of +16%
- FanDuel shows -4.8pp at 1.5 and -2.9pp at 2.5
- The direction is consistent: books systematically overprice the Over on TB props

**Data limitation:** FanDuel (62% of dataset) provides only Over odds. BetMGM and DraftKings have ~1,700 records each but don't reach N=500 at any single line. The bookmaker split is therefore dominated by FanDuel with only one BetOnline comparison available.

---

## Diagnostic 2 — Edge by Odds Bucket (Under Side)

Restricted to records with Under odds available (N=4,781 total; N=412 at 1.5, N=41 at 2.5).

| line | odds_bucket | N | actual_over | implied_over | edge | under_roi |
|-----:|:------------|----:|--------:|----------:|------:|----------:|
| 1.5 | -110 or better | 25 | 0.5600 | 0.6017 | -0.0417 | -0.0467 |
| 1.5 | -111 to -125 | 16 | 0.6875 | 0.5256 | +0.1619 | -0.4341 |
| 1.5 | -126 to -140 | 25 | 0.5200 | 0.5051 | +0.0149 | -0.1620 |
| 1.5 | worse than -140 | 346 | 0.3468 | 0.3974 | -0.0506 | -0.0423 |
| 2.5 | -110 or better | 8 | 0.7500 | 0.6153 | +0.1347 | -0.4875 |
| 2.5 | -111 to -125 | 2 | 1.0000 | 0.5236 | +0.4764 | -1.0000 |
| 2.5 | -126 to -140 | 3 | 0.6667 | 0.5049 | +0.1618 | -0.4286 |
| 2.5 | worse than -140 | 28 | 0.2857 | 0.2834 | +0.0024 | -0.1215 |

**Key observations:**
- Under ROI is **negative in every bucket**
- The only bucket with meaningful sample size is 1.5 / worse than -140 (N=346): edge = -5.1pp, Under ROI = -4.2%
- Buckets with "positive edge" (e.g., -111 to -125 at 1.5) have N=16 or fewer — pure noise
- **Critical limitation:** The two-sided odds subsample is only 14.6% of the dataset, and it skews toward smaller books (Bovada, BetMGM, DraftKings). This diagnostic is inconclusive due to insufficient sample size at the line level.

---

## Diagnostic 3 — Public Narrative Buckets

| bucket | line | N | actual_over | implied_over | edge | under_roi | lift_vs_baseline |
|:-------|-----:|-----:|--------:|----------:|------:|----------:|----------:|
| A: Power + HR park | 1.5 | 129 | 0.3953 | 0.4403 | -0.0450 | -0.1978 | +0.0062 |
| A: Power + HR park | 2.5 | 119 | 0.2689 | 0.2891 | -0.0202 | -1.0000 | +0.0166 |
| B: Top-order power | 1.5 | 777 | 0.4672 | 0.4724 | -0.0052 | -0.2200 | +0.0460 |
| B: Top-order power | 2.5 | 750 | 0.3413 | 0.3151 | +0.0262 | -0.4543 | +0.0630 |
| C: Elite name | 1.5 | 2,185 | 0.3963 | 0.4540 | -0.0577 | -0.1614 | -0.0064 |
| C: Elite name | 2.5 | 2,061 | 0.2494 | 0.2927 | -0.0433 | -0.3507 | -0.0065 |

**Baselines:** 1.5 edge = -5.12pp | 2.5 edge = -3.68pp

**Key observations:**
- **No bucket exceeds 7pp edge** — the highest lift vs baseline is Bucket B at 2.5 (+6.3pp), but the raw edge is only +2.6pp and Under ROI is deeply negative (-45.4%)
- Bucket B (top-order power, ISO > 0.180, slots 1-4) shows the most lift, suggesting the market prices these players closer to fair — which actually means *less* overpricing of the Over, not more
- Bucket C (elite name, slots 1-3) shows edge *worse* than baseline — the market is slightly more accurate for these players, not less
- Bucket A (power + HR park) has small sample (N=129/119) and shows minimal lift
- **Under ROI is negative in every narrative bucket** — no profitable betting angle exists here

---

## Diagnostic 4 — P(TB = 0) Mispricing

| Metric | Value |
|:-------|------:|
| Records at 0.5 line | 6,275 |
| Records with Under odds | 4,268 |
| Actual P(TB = 0) | 40.13% |
| Implied P(TB = 0) — two-sided books | 48.31% |
| Implied P(TB = 0) — all books (approx) | 41.37% |
| Difference (two-sided) | -8.18pp |
| Difference (all, approx) | -1.25pp |
| Under 0.5 ROI | -12.63% |

**Key observations:**
- The market **overprices** P(TB=0), the exact opposite of what would make Under 0.5 profitable
- Two-sided books price P(TB=0) at 48.3% vs actual 40.1% — this is vig-inflated but directionally clear: the market expects more zero-TB games than actually occur
- The -12.6% Under ROI confirms there is no edge on the Under 0.5 side
- The "nothing happens" outcome is already priced too high by the market; bettors are *not* systematically overlooking it

---

## Answers to Key Questions

### 1. Is the bias driven by one book or market-wide?
**Market-wide.** Both FanDuel (N=5,844 at 1.5) and BetOnline (N=578 at 2.5) show actual Over rates below implied Over rates. The direction is consistent: books overprice the Over on TB props. However, FanDuel dominates the sample (62%) and other books lack sufficient volume at individual lines.

### 2. Does Under ROI turn positive in any odds bucket?
**No.** Under ROI is negative in every odds bucket with meaningful sample size. The two-sided odds subsample (N=4,781) is too small to draw reliable bucket-level conclusions, especially at the 2.5 line where the largest bucket has only N=28.

### 3. Do any public-narrative buckets show edge > 7pp?
**No.** The maximum lift vs baseline is +6.3pp (Bucket B at 2.5), but the raw edge is only +2.6pp. No bucket approaches the 7pp threshold. Under ROI is negative in all buckets.

### 4. Is P(TB = 0) underpriced?
**No — it is overpriced.** The market implies P(TB=0) = 48.3% vs actual 40.1%. Under 0.5 ROI = -12.6%. There is no edge on the zero-TB outcome.

### 5. Verdict

**INVESTIGATE FURTHER**

Rationale:
- The Over-side overpricing bias is real and market-wide (-3pp to -12pp depending on book and line)
- However, **Under ROI is negative everywhere** due to vig — the raw edge exists but doesn't survive the juice
- The one bright spot is BetOnline 2.5 Under ROI at +16% (N=578), but this is a single book/line combination
- The narrative bucket analysis shows the bias is not concentrated in "public favorite" situations
- Before shelving entirely, investigate whether:
  - Combining the Over-side bias with additional predictive features (pitcher quality, platoon matchups) can push edge past vig
  - The BetOnline 2.5 finding replicates in 2026 data
  - A model targeting *which* players' TB props are most mispriced could generate sufficient edge
- The zero-TB angle is a dead end — shelve that sub-hypothesis

---

## Supporting Files

| File | Description |
|:-----|:------------|
| `tb_diag_bookmaker_split.parquet` | Diagnostic 1 results |
| `tb_diag_odds_buckets.parquet` | Diagnostic 2 results |
| `tb_diag_narrative_buckets.parquet` | Diagnostic 3 results |
| `tb_diag_zero_tb.parquet` | Diagnostic 4 results |
