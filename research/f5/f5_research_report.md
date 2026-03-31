# F5 Under Research Report

## 1. Dataset Summary

| Source | 2024 | 2025 | Notes |
|--------|------|------|-------|
| F5 lines | 1,588 (PARTIAL — 77.7% coverage) | 1,708 | Snapshot T−1h, FanDuel 84% primary |
| F5 actuals | 99.9% | 100% | From feature_table |
| V1 p_under | Derived from frozen S3 sim_results | Derived | 1 − p_over_line (20K draws) |
| S3 projections | 83.4% | 84.6% | Per-team mu/std/path probs |
| **Usable joined** | **1,588** | **1,708** | **3,296 total** |

p_under distribution: 2024 mean=0.518 std=0.076, 2025 mean=0.529 std=0.080.
Signal trigger rates: p>0.57 → 23.4% (2024), 27.9% (2025). p>0.60 → 13.6%, 17.1%.

---

## 2. Core Results — Signals A, B, C

### All books (books_count >= 1)

| Metric | A: Game Under | B: F5 Under | C: F5 p>0.60 |
|--------|--------------|-------------|---------------|
| N | 807 | 807 | 458 |
| Win% | 62.3% | 58.6% | 60.0% |
| ROI | +17.7% | +11.9% | +14.4% |
| Net units | +143.2u | +96.1u | +66.1u |

### Books >= 2

| Metric | A: Game Under | B: F5 Under | C: F5 p>0.60 |
|--------|--------------|-------------|---------------|
| N | 742 | 742 | 426 |
| Win% | 62.9% | 60.2% | 60.9% |
| ROI | +18.8% | +14.9% | +16.3% |
| Net units | +139.4u | +110.5u | +69.5u |

Signal A (game under) outperforms Signal B (F5 under) by ~6pp ROI.
F5 under is profitable but not superior to the full-game bet.

---

## 3. Diagnostic Signals D and E

**Signal D (CSW-filtered F5 under, p>0.57, suppressing CSW >= Q50):**
N=394, win%=57.4%, ROI=+9.5%. CSW filter does NOT improve over unfiltered Signal B (+11.9%).

**Signal E (Combined game + F5, 2u per signal):**
N=807, ROI=+14.8% on 2u, net=+239.3u. Both legs win together 46.2% of the time.

---

## 4. Rounding Artifact Controls

**Control A — Pricing error (DIAGNOSTIC APPROXIMATE):**
s3_implied_f5 = (mu_home + mu_away) × 0.56. Signal B mean pricing_error = −0.036 (near zero).
Not systematically positive — edge is not from market over-setting F5 lines.

**Control B — Implied probability baseline:**
Signal B actual win rate: 58.6%. Bin-weighted baseline: 54.0%.
Signal B exceeds baseline by +4.6pp — genuine signal, not line-level artifact.

**Control C — Half-line sensitivity:**
- .0 lines: N=28, win%=34.6%, ROI=−31.5% (THIN — only 28 games)
- .5 lines: N=779, win%=59.4%, ROI=+13.5%

96.5% of signal games land on .5 lines (predominantly 4.5). The .0 line sample is too thin to interpret. Edge concentrates in .5 lines because that IS the F5 market — 66.5% of all games have f5_line=4.5. Not a rounding artifact.

---

## 5. Diagnostic Tests

### 5A — Threshold Sensitivity

| Threshold | N | Win% | 95% Wilson CI | ROI |
|-----------|---|------|---------------|-----|
| 0.54 | 1,262 | 55.0% | [52.2–57.7] | +4.9% |
| 0.55 | 1,099 | 55.7% | [52.7–58.6] | +6.3% |
| 0.56 | 948 | 56.9% | [53.7–60.0] | +8.6% |
| 0.57 | 804 | 58.6% | [55.2–62.0] | +11.8% |
| 0.58 | 664 | 59.5% | [55.7–63.2] | +13.6% |
| 0.59 | 555 | 59.9% | [55.7–63.9] | +14.2% |
| 0.60 | 458 | 60.0% | [55.4–64.3] | +14.4% |

Monotonically increasing win% and ROI from 0.54 to 0.60.
No threshold spike — smooth gradient consistent with real signal.

### 5B — Temporal Split

| Season | H1 ROI | H1 net | H2 ROI | H2 net | Concentrated? |
|--------|--------|--------|--------|--------|---------------|
| 2024 (PARTIAL) | +7.9% | +14.5u | +8.4% | +15.5u | No |
| 2025 | +17.3% | +37.8u | +12.8% | +28.2u | No |

Remarkably even half-splits. No half-concentration flag.

### 5C — Season Standalone

| Signal | 2024 (PARTIAL) | 2025 | Pooled |
|--------|----------------|------|--------|
| B (p>0.57) | N=368, 56.7%, +8.2% | N=439, 60.3%, +15.0% | N=807, 58.6%, +11.9% |
| C (p>0.60) | N=209, 56.7%, +8.3% | N=249, 62.7%, +19.6% | N=458, 60.0%, +14.4% |

Both seasons positive. 2025 stronger than 2024 but same direction. Not MIXED.

### 5D — CSW Quartile Analysis

| Quartile | N | Win% | ROI |
|----------|---|------|-----|
| Q1 (low) | 191 | 55.3% | +5.5% |
| Q2 | 222 | 63.8% | +21.7% |
| Q3 | 204 | 58.8% | +12.3% |
| Q4 (>=29.3) | 190 | 55.8% | +6.5% |

Hypothesis that edge concentrates in Q3/Q4 is **not supported**. Q2 is the strongest bin.
CSW quartile does not add useful filtering for F5 — consistent with Signal D underperforming B.

### 5E — Line-Band Analysis

| F5 line | Signal N | Win% | ROI | Unsignaled under rate |
|---------|----------|------|-----|----------------------|
| <=4.0 | 96 | 55.2% | +5.4% | 47.4% |
| 4.5 | 567 | 58.4% | +11.4% | 48.8% |
| >=5.0 | 144 | 62.0% | +18.1% | 49.6% |

Signal separation over unsignaled games: +7.8pp at f5_line=4.5, +12.4pp at >=5.0.
Unsignaled baseline near 48-50% across all bands — signal consistently lifts above.

### 5F — Permutation Test

| Season | Actual ROI | Shuffled mean | Shuffled std | Percentile |
|--------|-----------|---------------|-------------|------------|
| 2024 (PARTIAL) | +8.2% | −4.0% | 4.9% | **99%** |
| 2025 | +15.0% | −0.6% | 3.9% | **100%** |

Both seasons pass top 10% comfortably. The signal is not noise.

### 5G — F5 vs Full-Game Outcome Relationship

| Outcome | N | % |
|---------|---|---|
| Both WIN | 373 | 46.2% |
| Both LOSS | 215 | 26.6% |
| F5 WIN / Game LOSS | 70 | 8.7% |
| F5 LOSS / Game WIN | 96 | 11.9% |
| Any PUSH | 53 | 6.6% |

Agreement rate: 78.0% (moderate correlation).
Independent rate: 22.0%.

F5 and full-game outcomes are correlated but not redundant. 22% of non-push games diverge — enough independence for Signal E (combined) to add diversification, but not enough to justify F5 as a standalone replacement.

---

## 6. Signal C Standalone

| Period | N | Win% | ROI | Net |
|--------|---|------|-----|-----|
| 2024 (PARTIAL) | 209 | 56.7% | +8.3% | +17.3u |
| 2025 | 249 | 62.7% | +19.6% | +48.8u |
| Pooled | 458 | 60.0% | +14.4% | +66.1u |

Signal C is the strongest F5 expression. 2025 standalone at +19.6% ROI.

---

## 7. 2024 vs 2025 Standalone (Signal B)

| Period | N | Win% | ROI | Net |
|--------|---|------|-----|-----|
| 2024 (PARTIAL) | 368 | 56.7% | +8.2% | +30.1u |
| 2025 | 439 | 60.3% | +15.0% | +66.0u |

Same direction. 2025 stronger by ~7pp but both clearly positive.
Not classified MIXED.

---

## 8. Decision Criteria

| Criterion | Result | Status |
|-----------|--------|--------|
| ROI >= 3% pooled | +11.9% | **PASS** |
| N >= 200 | 807 | **PASS** |
| 2025 standalone ROI positive | +15.0% | **PASS** |
| Permutation top 10% both seasons | 99%/100% | **PASS** |
| Rounding controls clean | +4.6pp over baseline | **PASS** |
| Not MIXED across seasons | Same direction | **PASS** |

**All 6 criteria met. Signal B advances.**

---

## Interpretation Notes

1. **F5 under works, but full-game under is better.** Signal A outperforms Signal B by ~6pp ROI on the same games. F5 is a weaker expression of the same underlying edge.

2. **Signal E (combined) is the interesting finding.** At +14.8% ROI on 2u with +239.3u net, betting both legs simultaneously captures more total profit than either leg alone. The 78% agreement rate means correlated wins amplify, while the 22% independence provides some loss cushion.

3. **CSW filtering destroys rather than helps.** Signal D underperforms Signal B. The CSW quartile analysis shows no monotonic pattern — the F5 edge is not driven by pitcher quality stratification.

4. **The f5_line >= 5.0 band is strongest** (+18.1% ROI, 62.0% win%). Higher F5 lines create more room for the under to hit. But N=144 is modest.

5. **Threshold sensitivity is clean.** Monotonic improvement from 0.54 to 0.60 with no spike — this is a real gradient, not a threshold artifact.
