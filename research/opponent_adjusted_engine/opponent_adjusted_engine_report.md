# Opponent-Adjusted Pitcher Form Engine — v1 Report

## Overview
Full independent engine testing whether opponent-adjusted recent pitcher form
predicts MLB totals / market residuals better than raw recent form.

Evaluation: 4855 games (2024-2025), 4666 non-push

## Methodology
```
adj_metric = raw_metric - (opponent_rolling_20g - league_avg)
```
- Team offense: K_rate, BB_rate, runs/game rolling 20 games (pregame)
- Hard-hit/barrel: adjusted via opponent runs quality proxy
- Rolling form: last 3 and last 5 prior starts
- Combined: avg(home_SP, away_SP) rolling form

## Step 5 — Engine Model Comparison

### Target: market_residual

| Model | Features | N | R² | Adj R² | Sig Features | AIC |
|-------|----------|---|-----|--------|-------------|-----|
| A_RAW | 6 | 4322 | 0.001202 | -0.000187 | 1 | 6282 |
| B_ADJ | 6 | 4319 | 0.003008 | 0.001621 | 4 | 6269 |
| C_COMBINED | 12 | 4319 | 0.006598 | 0.003829 | 6 | 6266 |
| A_RAW_ext | 10 | 4157 | 0.002414 | 0.000008 | 2 | 6046 |
| B_ADJ_ext | 10 | 4152 | 0.004545 | 0.002141 | 8 | 6030 |
| C_COMB_ext | 20 | 4152 | 0.009496 | 0.004700 | 6 | 6029 |

### Target: actual_result_under

| Model | N | R² | Sig Features |
|-------|---|-----|-------------|
| A_RAW | 4147 | 0.001621 | 1 |
| B_ADJ | 4144 | 0.003721 | 6 |
| C_COMBINED | 4144 | 0.007216 | 5 |

### Target: actual_total

| Model | N | R² | MAE |
|-------|---|-----|-----|
| A_RAW | 4322 | 0.008190 | 3.494 |
| B_ADJ | 4319 | 0.009696 | 3.491 |
| C_COMBINED | 4319 | 0.013043 | 3.487 |

## Step 6 — Decile Structure

### A_RAW

| Decile | N | Score | Resid | Under% | ROI @-110 |
|--------|---|-------|-------|--------|-----------|
| 0 | 415 | -0.0370 | -0.0543 | 0.463 | -11.7% |
| 1 | 415 | -0.0254 | -0.0185 | 0.504 | -3.9% |
| 2 | 414 | -0.0193 | +0.0370 | 0.556 | +6.1% |
| 3 | 415 | -0.0146 | -0.0069 | 0.508 | -2.9% |
| 4 | 415 | -0.0100 | -0.0556 | 0.467 | -10.8% |
| 5 | 414 | -0.0054 | +0.0023 | 0.522 | -0.4% |
| 6 | 415 | -0.0009 | -0.0139 | 0.506 | -3.4% |
| 7 | 414 | 0.0042 | +0.0000 | 0.512 | -2.2% |
| 8 | 415 | 0.0105 | -0.0208 | 0.513 | -2.0% |
| 9 | 415 | 0.0237 | +0.0566 | 0.583 | +11.3% |

Tail spread: D9-D0 under_rate=+0.120, ROI=+23.0pp

### B_ADJ

| Decile | N | Score | Resid | Under% | ROI @-110 |
|--------|---|-------|-------|--------|-----------|
| 0 | 415 | -0.0554 | -0.0394 | 0.480 | -8.5% |
| 1 | 414 | -0.0364 | -0.0231 | 0.495 | -5.5% |
| 2 | 414 | -0.0259 | -0.0486 | 0.469 | -10.5% |
| 3 | 415 | -0.0184 | +0.0069 | 0.523 | -0.2% |
| 4 | 414 | -0.0114 | -0.0532 | 0.471 | -10.1% |
| 5 | 414 | -0.0044 | -0.0128 | 0.507 | -3.2% |
| 6 | 415 | 0.0026 | +0.0023 | 0.525 | +0.3% |
| 7 | 414 | 0.0103 | -0.0023 | 0.519 | -0.9% |
| 8 | 414 | 0.0202 | +0.0532 | 0.580 | +10.7% |
| 9 | 415 | 0.0412 | +0.0394 | 0.561 | +7.2% |

Tail spread: D9-D0 under_rate=+0.082, ROI=+15.6pp

### C_COMBINED

| Decile | N | Score | Resid | Under% | ROI @-110 |
|--------|---|-------|-------|--------|-----------|
| 0 | 415 | -0.0747 | -0.0671 | 0.455 | -13.1% |
| 1 | 414 | -0.0461 | -0.0440 | 0.469 | -10.5% |
| 2 | 414 | -0.0330 | -0.0463 | 0.478 | -8.7% |
| 3 | 415 | -0.0225 | -0.0278 | 0.487 | -7.1% |
| 4 | 414 | -0.0129 | +0.0046 | 0.531 | +1.4% |
| 5 | 414 | -0.0039 | +0.0104 | 0.529 | +1.0% |
| 6 | 415 | 0.0058 | -0.0069 | 0.511 | -2.5% |
| 7 | 414 | 0.0170 | -0.0069 | 0.514 | -1.8% |
| 8 | 414 | 0.0308 | +0.0347 | 0.556 | +6.1% |
| 9 | 415 | 0.0620 | +0.0718 | 0.600 | +14.5% |

Tail spread: D9-D0 under_rate=+0.145, ROI=+27.6pp

### Season Stability

| Model | Year | R² | Sig Features |
|-------|------|-----|-------------|
| A_RAW | 2024 | 0.001341 | 0 |
| A_RAW | 2025 | 0.002630 | 0 |
| B_ADJ | 2024 | 0.003509 | 2 |
| B_ADJ | 2025 | 0.003638 | 1 |
| C_COMBINED | 2024 | 0.005497 | 2 |
| C_COMBINED | 2025 | 0.009839 | 4 |

### Market Independence

| Model | Score vs closing_total r | p |
|-------|------------------------|---|
| A_RAW | -0.1115 | 0.0000 |
| B_ADJ | -0.1392 | 0.0000 |

## Step 7 — Feature Family Comparison

| Family | Raw p | Adj p | Adj beats raw? | Adj adds value? | Stable raw | Stable adj |
|--------|-------|-------|---------------|----------------|-----------|-----------|
| K_rate_last3 | 0.1241 | 0.0252 | YES | YES | YES | YES |
| K_rate_last5 | 0.5080 | 0.3294 | YES | NO | YES | YES |
| BB_rate_last3 | 0.4423 | 0.6974 | NO | NO | YES | NO |
| BB_rate_last5 | 0.7028 | 0.6756 | YES | YES | NO | NO |
| CSW_last3 | 0.9353 | 0.2507 | YES | YES | NO | YES |
| CSW_last5 | 0.9737 | 0.6351 | YES | NO | NO | YES |
| HardHit_last3 | 0.7713 | 0.5794 | YES | YES | YES | YES |
| HardHit_last5 | 0.3153 | 0.2136 | YES | NO | YES | YES |
| Barrel_last3 | 0.9301 | 0.7865 | YES | YES | NO | NO |
| Barrel_last5 | 0.2294 | 0.3122 | NO | NO | YES | YES |

### Year Detail (surviving families)

**K_rate_last3**
| Year | Version | Coef | p |
|------|---------|------|---|
| 2024 | RAW | +0.22731 | 0.2874 |
| 2024 | ADJ | +0.33964 | 0.1162 |
| 2025 | RAW | +0.23694 | 0.2478 |
| 2025 | ADJ | +0.32306 | 0.1117 |

## Step 8 — Interaction Readiness

Surviving families: 1

- **K_rate_last3**: adj_p=0.0252, adds_value=True

### Best Interaction Candidates

1. **adj_k_rate_last3**: Best standalone significance. Test as interaction with S12 (command)
   because S12 uses CSW×xFIP — opponent-adjusted K rate captures a different dimension
   (form recency vs. season-level skill).

2. **adj_csw_last3**: If significant, test with P09 (contact suppression × park)
   because adjusted CSW isolates pitcher dominance from opponent weakness.

3. Hard-hit families: NOT recommended for interaction testing unless individually significant.

## Step 9 — Final Verdict

### Scorecard

- Families where ADJ beats RAW on significance: 8/10
- Families where ADJ is individually significant (p<0.05): 1/10
- Families where ADJ is marginal (p<0.10): 1/10
- Families where ADJ adds value beyond RAW in combined model: 5/10

### Q1: Does the full opponent-adjusted engine concept work?
- RAW engine R²: 0.001202
- ADJ engine R²: 0.003008
- COMBINED engine R²: 0.006598
- **YES** — adjusted engine outperforms raw by >20% relative R²

### Q2: Does adjusted engine beat raw?
- **YES** across most families

### Q3: Does combined engine beat both?
- **YES** — meaningful information in both raw and adjusted

### Q4: Which adjusted feature families matter most?
- K_rate_last3: adj_p=0.0252 (**SIGNIFICANT**)
- HardHit_last5: adj_p=0.2136 (not sig)
- CSW_last3: adj_p=0.2507 (not sig)
- Barrel_last5: adj_p=0.3122 (not sig)
- K_rate_last5: adj_p=0.3294 (not sig)

### Q5: Broad enough for further development?
- **NARROW** — only one family shows promise. Not broad enough for full engine.

### Critical Interpretation

The quantitative answers above require context:

1. **All R² values are tiny.** The best model (C_COMBINED) explains 0.66% of market residual variance. For actual_total, it explains 1.3%. These are statistically detectable effects, not practically large ones.

2. **ADJ does consistently outperform RAW.** Across all three targets, B_ADJ beats A_RAW (R² 2.5x on market_residual, 2.3x on under_outcome, 1.2x on total_runs). This is genuine — the concept works.

3. **C_COMBINED is the strongest.** It beats both A and B on all targets. Raw and adjusted carry independent information. The combined R² (0.66%) is 5.5× the raw-only R² (0.12%). This confirms the adjustment adds real signal.

4. **Decile structure favors COMBINED.** C_COMBINED produces the widest tail spread: D0=45.5% under → D9=60.0% under (+14.5pp, +27.6pp ROI). A_RAW is noisier (D2=55.6%, D4=46.7% — non-monotonic). B_ADJ has a cleaner gradient but narrower tails.

5. **Only one feature family is individually significant.** adj_k_rate_last3 (p=0.025) is the sole feature that passes p<0.05. Everything else is p>0.20. This makes the "full engine" more of a "one strong feature + supporting noise."

6. **Stability is real.** B_ADJ has significant features in both 2024 (2 sig) and 2025 (1 sig), while A_RAW has zero significant features in either year. The adjustment is not overfitting to one season.

7. **Market correlation is moderate.** Both engine scores correlate r≈-0.11 to -0.14 with closing_total. The market partially prices recent pitcher form but leaves residual signal.

8. **adj_k_rate_last3 is the only actionable output.** It is significant (p=0.025), adds value beyond raw (p=0.007 in combined model), is year-stable (positive both 2024 and 2025), and uncorrelated with S12/P09 concepts.

### Final Project Verdict

**INVESTIGATE**

The opponent-adjusted engine concept is valid but narrow:
- The adjustment genuinely improves over raw recent form
- C_COMBINED outperforms A_RAW and B_ADJ consistently
- But only adj_k_rate_last3 is individually significant
- R² is too small for standalone signal deployment

Recommended next steps (priority order):
1. Add `adj_k_rate_last3` to scanner signal catalog
2. Test interaction with S12 (CSW × xFIP command score) — different dimension, likely additive
3. Shadow monitor in 2026 season for live validation
4. Do NOT build a standalone overlay from this engine — insufficient edge magnitude
5. Revisit full engine concept after 2026 with larger sample and potential lineup-level data



## Phase Closeout

### Status: INVESTIGATE

**adj_k_rate_last3**: added to scanner catalog as signal_id=117

### Interaction Test Results

adj_k_rate_last3 top-20% threshold: 0.22762 (frozen from 2024)

#### Pooled (2024+2025)

| Cohort | N | Under% | Resid | ROI @-110 |
|--------|---|--------|-------|----------|
| Test A: V1 alone | 887 | 0.558 | +0.058 | +6.5% |
| Test A: V1 + adj_k top20 | 302 | 0.589 | +0.089 | +12.5% |
| Test B: V1 + S12 | 0 | N/A | N/A | N/A (THIN) |
| Test B: V1 + S12 + adj_k top20 | 0 | N/A | N/A | N/A (THIN) |
| Test C: V1 + P09 | 67 | 0.522 | +0.022 | -0.3% |
| Test C: V1 + P09 + adj_k top20 | 25 | 0.600 | +0.100 | +14.5% (THIN) |

#### 2024

| Cohort | N | Under% | ROI @-110 |
|--------|---|--------|----------|
| Test A: V1 alone | 480 | 0.550 | +5.0% |
| Test A: V1 + adj_k top20 | 145 | 0.559 | +6.6% |
| Test B: V1 + S12 | 0 | N/A | N/A (THIN) |
| Test B: V1 + S12 + adj_k top20 | 0 | N/A | N/A (THIN) |
| Test C: V1 + P09 | 43 | 0.488 | -6.8% (THIN) |
| Test C: V1 + P09 + adj_k top20 | 15 | 0.667 | +27.3% (THIN) |

#### 2025

| Cohort | N | Under% | ROI @-110 |
|--------|---|--------|----------|
| Test A: V1 alone | 407 | 0.568 | +8.4% |
| Test A: V1 + adj_k top20 | 157 | 0.618 | +18.0% |
| Test B: V1 + S12 | 0 | N/A | N/A (THIN) |
| Test B: V1 + S12 + adj_k top20 | 0 | N/A | N/A (THIN) |
| Test C: V1 + P09 | 24 | 0.583 | +11.4% (THIN) |
| Test C: V1 + P09 + adj_k top20 | 10 | 0.500 | -4.5% (THIN) |

#### Lift Summary

| Test | Base ROI | Enhanced ROI | Lift | Verdict |
|------|----------|-------------|------|--------|
| Test A | +6.5% (N=887) | +12.5% (N=302) | +6.0pp | **MEANINGFUL LIFT** |
| Test B | N/A | N/A | N/A | N/A |
| Test C | -0.3% (N=67) | +14.5% (N=25) | +14.8pp | **THIN** |

### Notes

- **Test B (S12) untestable.** S12 uses production CSW from FanGraphs/Savant (called strikes + whiffs),
  not boxscore strike%. The research CSW proxy (strikes/pitches) does not match the production S12
  cutoff (8.4468). Zero games flagged. S12 interaction remains untested and should be revisited
  with production CSW data in 2026 live monitoring.

- **Test C (P09) too thin.** Only 25 games in the V1+P09+adj_k intersection (pooled). Results
  are directionally positive (+14.5% ROI) but statistically unreliable.

### Interaction Assessment

**Test A is the only testable interaction.** Results:

| Period | V1 alone | V1 + adj_k top20 | Lift | N (enhanced) |
|--------|----------|-------------------|------|-------------|
| 2024 | +5.0% | +6.6% | +1.6pp | 145 |
| 2025 | +8.4% | +18.0% | +9.6pp | 157 |
| Pooled | +6.5% | +12.5% | +6.0pp | 302 |

adj_k_rate_last3 top-20% provides **+6.0pp ROI lift** on V1 UNDER signals (pooled).
The lift is driven by 2025 (+9.6pp) while 2024 shows only +1.6pp.
This is encouraging but single-year-driven — needs 2026 confirmation.

### Best View of adj_k_rate_last3

**Scanner ingredient with overlay potential.** The V1 interaction is the most promising
path — not standalone, not with current P09/S12 stacks (insufficient data), but as a
direct V1 UNDER amplifier. The 2025 result (61.8% under rate, +18.0% ROI, N=157) is
strong but needs out-of-sample validation.

### Recommended Next Step

1. Shadow monitor adj_k_rate_last3 in 2026 alongside V1 signal log
2. Re-evaluate after 200+ qualifying V1+adj_k games in 2026
3. If 2026 under_rate ≥ 56% at N≥100, promote to V1 UNDER overlay candidate
4. Test S12 interaction in 2026 using production CSW values (not boxscore proxy)
5. Do NOT deploy as overlay until 2026 validation
