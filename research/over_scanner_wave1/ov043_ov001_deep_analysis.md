# Deep Analysis — OV043 and OV001

Dataset: 4855 games (2024-2025), 4666 non-push
V1 OVER-lean (p_under<0.45): N=1205, over%=0.520, ROI=-0.8%

---
## OV043: bullpen_overuse (combined BP IP last 3d)

### Test 1 — Season Stability

| Year | Coefficient | p-value | R² |
|------|-----------|---------|-----|
| 2024 | +0.00017 | 0.2084 | 0.000652 |
| 2025 | +0.00009 | 0.4923 | 0.000194 |

Verdict: **STABLE**

### Test 2 — Decile Structure

| Decile | N | Mean | Resid | Over% | ROI |
|--------|---|------|-------|-------|-----|
| 0 | 468 | 220.3739 | -0.0406 | 0.459 | -12.3% |
| 1 | 470 | 292.3702 | -0.0085 | 0.491 | -6.2% |
| 2 | 476 | 315.2458 | -0.0441 | 0.456 | -13.0% |
| 3 | 482 | 333.7282 | +0.0228 | 0.523 | -0.2% |
| 4 | 439 | 350.3235 | -0.0011 | 0.499 | -4.8% |
| 5 | 495 | 367.6828 | -0.0354 | 0.465 | -11.3% |
| 6 | 456 | 386.2259 | +0.0219 | 0.522 | -0.4% |
| 7 | 461 | 406.9783 | -0.0163 | 0.484 | -7.7% |
| 8 | 462 | 434.9957 | -0.0087 | 0.491 | -6.2% |
| 9 | 457 | 492.6433 | +0.0208 | 0.521 | -0.6% |

Gradient: **tail-only** (top3 avg=-0.0014, mid=+0.0021, bot3=-0.0311)

### Test 3 — Threshold Sensitivity

**Standalone:**
| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|-------|-------|-----|----------|----------|
| top_10 | 457 | 0.521 | +0.021 | -0.6% | +4.4% | -5.4% |
| top_20 | 919 | 0.506 | +0.006 | -3.4% | -0.5% | -6.2% |
| top_30 | 1380 | 0.499 | -0.001 | -4.8% | -1.0% | -8.4% |

**V1 OVER-lean interaction:**
| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|-------|-------|-----|----------|----------|
| top_10 | 121 | 0.562 | +0.062 | +7.3% | +14.5% | +1.2% |
| top_20 | 240 | 0.517 | +0.017 | -1.4% | +2.4% | -4.5% |
| top_30 | 362 | 0.500 | +0.000 | -4.5% | +1.6% | -9.2% |

### Test 4 — Robustness Controls

- Coefficient: +0.00013
- p-value: 0.1780
- Verdict: **NOT ROBUST**

### Test 5 — Market Awareness

- corr(signal, closing_total): r=0.0739
- Avg closing total — top 20%: 8.48, rest: 8.38, diff: +0.10
- Market **mostly misses** this signal

---
## OV001: bb_x_hard_hit (avg SP BB% × SP HH%)

### Test 1 — Season Stability

| Year | Coefficient | p-value | R² |
|------|-----------|---------|-----|
| 2024 | -0.84485 | 0.4687 | 0.000217 |
| 2025 | +0.25082 | 0.8275 | 0.000020 |

Verdict: **MIXED**

### Test 2 — Decile Structure

| Decile | N | Mean | Resid | Over% | ROI |
|--------|---|------|-------|-------|-----|
| 0 | 467 | 0.0109 | -0.0203 | 0.480 | -8.4% |
| 1 | 467 | 0.0179 | +0.0332 | 0.533 | +1.8% |
| 2 | 466 | 0.0232 | -0.0193 | 0.481 | -8.2% |
| 3 | 467 | 0.0265 | -0.0203 | 0.480 | -8.4% |
| 4 | 466 | 0.0287 | +0.0000 | 0.500 | -4.5% |
| 5 | 467 | 0.0305 | -0.0225 | 0.478 | -8.8% |
| 6 | 466 | 0.0324 | -0.0279 | 0.472 | -9.9% |
| 7 | 467 | 0.0344 | -0.0139 | 0.486 | -7.2% |
| 8 | 466 | 0.0368 | +0.0129 | 0.513 | -2.1% |
| 9 | 467 | 0.0413 | -0.0139 | 0.486 | -7.2% |

Gradient: **noisy** (top3 avg=-0.0050, mid=-0.0177, bot3=-0.0022)

### Test 3 — Threshold Sensitivity

**Standalone:**
| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|-------|-------|-----|----------|----------|
| top_10 | 467 | 0.486 | -0.014 | -7.2% | -4.5% | -8.5% |
| top_20 | 933 | 0.499 | -0.001 | -4.6% | -2.2% | -6.2% |
| top_30 | 1400 | 0.495 | -0.005 | -5.5% | -7.1% | -4.4% |

**V1 OVER-lean interaction:**
| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|-------|-------|-----|----------|----------|
| top_10 | 121 | 0.479 | -0.021 | -8.5% | -22.4% | -3.5% |
| top_20 | 241 | 0.552 | +0.052 | +5.4% | +13.2% | +1.0% |
| top_30 | 362 | 0.544 | +0.044 | +3.9% | +9.9% | +0.4% |

### Test 4 — Robustness Controls

- Coefficient: -1.38603
- p-value: 0.0955
- Verdict: **ROBUST**

### Test 5 — Market Awareness

- corr(signal, closing_total): r=0.0336
- Avg closing total — top 20%: 8.54, rest: 8.36, diff: +0.18
- Market **partially prices** this signal

---
## Test 6 — V1 Interaction (Walk-Forward)

Warmup: first 50 V1 OVER-lean games per season

| Cohort | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|--------|---|-------|-------|-----|----------|----------|
| A: V1 OVER-lean alone | 1205 | 0.520 | +0.020 | -0.8% | +4.7% | -5.6% |
| B: V1 + OV043 top10 | 168 | 0.542 | +0.042 | +3.4% | +4.1% | +2.6% |
| C: V1 + OV043 top20 | 271 | 0.517 | +0.017 | -1.4% | +5.4% | -8.0% |
| D: V1 + OV043 top30 | 384 | 0.508 | +0.008 | -3.1% | +2.3% | -7.8% |
| E: V1 + OV001 top10 | 122 | 0.541 | +0.041 | +3.3% | +6.9% | +0.8% |
| F: V1 + OV001 top20 | 226 | 0.558 | +0.058 | +6.4% | +18.6% | -2.4% |
| G: V1 + OV001 top30 | 340 | 0.547 | +0.047 | +4.4% | +11.9% | -1.1% |
| H: V1 + OV043+OV001 top20 | 58 | 0.569 | +0.069 | +8.6% | +25.1% | -7.8% |

---
## Test 7 — Independence

- corr(OV043, OV001): r=-0.0074, p=0.6062
- **INDEPENDENT** (r < 0.30)
- Joint OLS: OV043 coef=+0.00013 (p=0.1774), OV001 coef=-0.38614 (p=0.6353)
- R²=0.000423
- Both carry independent info: **NO**

---
## Test 8 — Permutation (2025)

**OV043** (top 20%, walk-forward):
- N=137, obs over%=0.482, obs ROI=-8.0%
- Permutation: median=-6.6%, p5=-17.9%, p95=+7.3%
- Percentile: 44% (FAIL)

**OV001** (top 20%, walk-forward):
- N=131, obs over%=0.511, obs ROI=-2.4%
- Permutation: median=-5.3%, p5=-17.0%, p95=+7.9%
- Percentile: 70% (FAIL)

---
## Test 9 — Availability Bias

**OV043:**
| Group | N | Over% | Avg Close | ROI |
|-------|---|-------|-----------|-----|
| Available | 1205 | 0.520 | 9.14 | -0.8% |

Bias: 0.000 (CLEAN)

**OV001:**
| Group | N | Over% | Avg Close | ROI |
|-------|---|-------|-----------|-----|
| Available | 1205 | 0.520 | 9.14 | -0.8% |

Bias: 0.000 (CLEAN)

---
## Final Verdict

### OV043: bullpen_overuse (combined BP IP last 3d)

| Criterion | Result |
|-----------|--------|
| Season stability | MIXED |
| Walk-forward V1 top20 ROI | -1.4% (N=271) |
| V1 lift | -0.6pp |
| Market awareness | r=0.034 |

**Verdict: SHELVE**
- Role: No deployment value
- Viable cohort: ~135 games/season in V1+OV043 top20

### OV001: bb_x_hard_hit (avg SP BB% × SP HH%)

| Criterion | Result |
|-----------|--------|
| Season stability | MIXED |
| Walk-forward V1 top20 ROI | +6.4% (N=226) |
| V1 lift | +7.3pp |
| Market awareness | r=0.034 |

**Verdict: ADVANCE**
- Role: V1 OVER-lean amplifier
- Viable cohort: ~113 games/season in V1+OV001 top20

### Combined OV043 + OV001

- V1 + both top20: N=58, over%=0.569, ROI=+8.6%
- Independence: r=-0.0074 (independent)

---
## Critical Assessment

### Walk-forward reveals the truth

The static scanner (Step 4 of Wave 1) showed +8.1pp lift for OV043 and +6.2pp for OV001. Walk-forward with expanding thresholds paints a sharply different picture:

| Signal | Static Lift | Walk-Forward Top20 Lift | 2024 WF | 2025 WF |
|--------|------------|------------------------|---------|---------|
| OV043 | +8.1pp | **-0.6pp** | +5.4% | **-8.0%** |
| OV001 | +6.2pp | **+7.3pp** | +18.6% | **-2.4%** |

### OV043 is dead

Walk-forward OV043 top20 produces -1.4% ROI (worse than V1 baseline). The 2025 result is -8.0%. Permutation at 44th percentile = pure noise. The static result was inflated by lookahead in the threshold. **SHELVE confirmed.**

### OV001 is one-year-driven

Walk-forward OV001 top20 shows +6.4% ROI pooled, which looks promising. But:
- **2024: +18.6%** — very strong
- **2025: -2.4%** — negative
- Permutation 2025: 70th percentile — FAIL (below 85% gate)

This is a 2024-only effect. The +7.3pp pooled lift is entirely carried by 2024. The 2025 walk-forward is worse than V1 baseline.

### Both permutation tests fail

Neither signal reaches the 85th percentile permutation threshold in 2025:
- OV043: 44th percentile (noise)
- OV001: 70th percentile (suggestive but insufficient)

### Neither signal is robust in OLS

- OV043: p=0.178 after controls (NOT ROBUST)
- OV001: p=0.096 after controls (marginally ROBUST, but the coefficient is **negative** — meaning higher BB×HH actually predicts UNDER, not OVER, after controlling for xFIP and closing total)

### The OV001 coefficient direction is concerning

In the robustness OLS, OV001 has coefficient **-1.386** (p=0.096). This means after controlling for pitcher quality (xFIP) and market line, higher BB×HH predicts **lower** over probability. The positive V1 interaction in 2024 may be an artifact of OV001 correlating with V1 OVER-lean selection rather than independently predicting OVER.

### Revised Verdicts

**OV043: SHELVE**
- Walk-forward kills the static signal
- 2025 is negative, permutation fails
- No standalone or interaction value

**OV001: INVESTIGATE (downgraded from ADVANCE)**
- Walk-forward pooled is positive (+6.4%) but 2025 is negative
- Permutation fails at 70th percentile
- Robustness coefficient points in wrong direction
- 2024 result is strong enough to monitor in 2026, but NOT deploy

### Deployment Recommendation

Neither signal is ready for deployment. The OVER side of MLB totals remains significantly harder than UNDER:
- V1 OVER-lean baseline is -0.8% ROI (already negative)
- No tested amplifier produces year-stable, permutation-passing improvement
- The market appears to price OVER environments more efficiently than UNDER environments

### Next Steps
1. Monitor OV001 in 2026 shadow mode — if 2026 V1+OV001 top20 over% ≥ 54% at N≥50, revisit
2. OV043: no further work
3. Consider whether the OVER signal search should pivot to entirely different mechanisms (e.g., game-state dynamics, in-play events) rather than pregame pitcher/bullpen features

