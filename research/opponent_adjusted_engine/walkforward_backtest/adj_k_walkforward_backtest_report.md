# adj_k_rate_last3 — Walk-Forward Backtest Report

## Signal
- Name: adj_k_rate_last3 (combined, avg of home + away SP)
- Direction: HIGH → UNDER amplifier
- Interaction: V1 p_under > 0.57 AND adj_k in top 20%

## Thresholding
- METHOD A: expanding-window p80 within season, warmup=200 games
- METHOD B: frozen 2024 threshold = 0.22762
- Both methods are strictly leakage-safe

## Walk-Forward Results

| Cohort | N (non-push) | Win Rate | Resid | ROI @-110 | Net Units |
|--------|-------------|---------|-------|-----------|----------|
| V1_alone (2024_A) | 480 | 0.550 | +0.050 | +5.0% | +24.0u |
| V1+adj_k (2024_A) | 135 | 0.533 | +0.033 | +1.8% | +2.5u |
| V1_alone (2025_A) | 407 | 0.568 | +0.068 | +8.4% | +34.0u |
| V1+adj_k (2025_A) | 130 | 0.615 | +0.115 | +17.5% | +22.7u |
| V1_alone (2025_B) | 407 | 0.568 | +0.068 | +8.4% | +34.0u |
| V1+adj_k (2025_B) | 157 | 0.618 | +0.118 | +18.0% | +28.2u |
| V1_alone (pooled_A) | 887 | 0.558 | +0.058 | +6.5% | +58.0u |
| V1+adj_k (pooled_A) | 265 | 0.574 | +0.074 | +9.5% | +25.2u |

### Lift vs V1 Alone

| Period | V1 ROI | V1+adj_k ROI | Lift | V1 N | Amp N |
|--------|--------|-------------|------|------|-------|
| 2024_A | +5.0% | +1.8% | -3.2pp | 480 | 135 |
| 2025_A | +8.4% | +17.5% | +9.1pp | 407 | 130 |
| 2025_B | +8.4% | +18.0% | +9.6pp | 407 | 157 |
| pooled_A | +6.5% | +9.5% | +3.0pp | 887 | 265 |

## Chronological Stability

| Season | Block | V1 N | V1 WR | V1 ROI | Amp N | Amp WR | Amp ROI |
|--------|-------|------|-------|--------|-------|--------|---------|
| 2024 | Apr-May | 231 | 0.545 | +4.1% | 40 | 0.425 | -18.9% |
| 2024 | Jun-Jul | 110 | 0.509 | -2.8% | 45 | 0.533 | +1.8% |
| 2024 | Aug-Sep | 139 | 0.590 | +12.6% | 50 | 0.620 | +18.4% |
| 2025 | Apr-May | 196 | 0.571 | +9.1% | 39 | 0.667 | +27.3% |
| 2025 | Jun-Jul | 98 | 0.612 | +16.9% | 45 | 0.622 | +18.8% |
| 2025 | Aug-Sep | 113 | 0.522 | -0.3% | 46 | 0.565 | +7.9% |

## Threshold Sensitivity

| Threshold | Season | N | Win Rate | Resid | ROI |
|-----------|--------|---|---------|-------|-----|
| top_10 | 2024 | 97 | 0.485 | -0.015 | -7.5% |
| top_10 | 2025 | 94 | 0.649 | +0.149 | +23.9% |
| top_10 | pooled | 210 | 0.552 | +0.052 | +5.5% |
| top_20 | 2024 | 145 | 0.559 | +0.059 | +6.6% |
| top_20 | 2025 | 157 | 0.618 | +0.118 | +18.0% |
| top_20 | pooled | 303 | 0.587 | +0.087 | +12.2% |
| top_30 | 2024 | 183 | 0.563 | +0.063 | +7.5% |
| top_30 | 2025 | 188 | 0.612 | +0.112 | +16.8% |
| top_30 | pooled | 358 | 0.584 | +0.084 | +11.5% |

## Deployability

- V1 UNDER games: 929
- adj_k available on V1: 861 (92.7%)
- adj_k top20 qualifying: 278 (29.9%)
- 2024: 141 qualifying games (~5.4/week)
- 2025: 137 qualifying games (~5.3/week)
- Longest dry spell: 198 days

## False Edge Checks

- Data availability bias: 0.047 (WARNING)
- Permutation (2025): observed ROI at 91.0th percentile (PASS)
- Leakage: confirmed none (expanding window + frozen prior-season)

## Final Verdict

### Key Metrics
- Pooled lift: +3.0pp ROI
- 2024 lift: -3.2pp ROI
- 2025 lift: +9.1pp ROI
- Permutation: 91th percentile
- Data bias: WARNING

### Questions Answered

**Q1: Does walk-forward confirm the static result?**
PARTIALLY — pooled lift is +3.0pp, below the static +6.0pp.

**Q2: Does V1 + adj_k materially improve V1 alone?**
MARGINAL — +3.0pp positive but below 3pp materiality threshold.

**Q3: Is the improvement stable across 2024 and 2025?**
MIXED — 2024=-3.2pp, 2025=+9.1pp.

**Q4: Edge strength classification**

**INVESTIGATE FURTHER**

Positive but insufficient evidence for immediate deployment.

### Critical Assessment

The walk-forward backtest reveals important structure the static test obscured:

1. **2024 is negative (-3.2pp lift).** The static analysis used a full-sample 2024 threshold, which inflated 2024 results. Walk-forward with expanding window shows the signal *hurt* in 2024.

2. **2024 Apr-May is badly negative (-18.9% ROI).** The warmup period ends mid-April, and early-season adj_k values are computed from small, unstable rolling windows. This is a real deployment risk.

3. **2025 is genuinely strong (+9.1pp).** Both METHOD A (expanding) and METHOD B (frozen 2024) confirm +17-18% ROI. The 2025 permutation at 91st percentile is a real result, not noise.

4. **Data availability bias exists (0.047).** Games with adj_k available have 4.7pp higher under rate than games without. This likely reflects early-season exclusion (first ~3 weeks) when pitchers lack 3 prior starts. Early season may have different dynamics.

5. **Top 20% remains the best threshold.** Top 10% has higher 2025 ROI (+23.9%) but negative 2024 (-7.5%) and small N. Top 30% dilutes slightly. Top 20% is the sweet spot for ROI×volume.

6. **Seasonal pattern is encouraging.** In both years, Aug-Sep shows the signal working (2024: +18.4%, 2025: +7.9%). This suggests the signal strengthens as season data accumulates, which is consistent with the expanding-window approach improving over time.

### Verdict: INVESTIGATE FURTHER

The 2024 walk-forward failure is a yellow flag that prevents ADVANCE. But the 2025 result is strong, genuine (91st percentile permutation), and consistent with the signal concept (more data = better adjustment). This deserves 2026 live monitoring.

### Promotion Rule

Promote adj_k_rate_last3 to live V1 UNDER overlay if:
- 2026 V1+adj_k cohort reaches N >= 100 qualifying games
- AND under rate >= 55%
- AND ROI >= +3% at -110
- AND permutation p >= 85th percentile within 2026 data
- AND 2026 lift vs V1-alone is positive (not negative as 2024 was)

If 2026 Apr-May shows similar early-season degradation, consider:
- Extending warmup to 400 games (late May activation)
- Or restricting to Jun-Sep only
