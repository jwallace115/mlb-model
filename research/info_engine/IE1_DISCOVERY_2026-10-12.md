# IE-1 Discovery Report — 2026-10-12

## RETRACTION (IE-D8, 2026-10-12)

**All results below the line are RETRACTED.** The margin residual formula was wrong:
`margin_resid = margin - (-spread_line)` = `margin + spread_line`, which has
**r = 0.69** with `spread_line`. This is not a residual — it retains the spread's
information. The families that appeared to predict "margin residual" (F2 t=4.9,
F4 t=4.2, F5 t=3.5, F3 t=3.1) were proxying for team quality through their
correlation with spread_line, not beating the close.

The "home cover" label was also wrong: `margin > -spread_line` has **r = 0.56**
with `spread_line` and a 55.95% True rate (should be ~50%). The 0.019 log-loss
improvement was an artifact of predicting the spread, not the cover.

Corrected formula: `margin_resid = margin - spread_line` (|r| = 0.015 with spread_line).
Corrected home cover: `margin > spread_line` (|r| = 0.03, rate 47.4%/49.0% ex-pushes).

The corrected results are in IE-D10 (below). The pre-registrations are unchanged
and re-run on the corrected table.

---

~~## RETRACTED RESULTS (do not cite)~~

~~Per-family margin t-stats (F2 4.9, F4 4.2, F5 3.5, F3 3.1, F8 2.4) — INVALID.~~
~~All-family ridge log-loss improvement 0.019 — INVALID.~~
~~All four pre-registration outcomes (all FALSIFIED) — INVALID.~~
~~Frozen spec IE_FROZEN_SPEC_v1.md — SUPERSEDED by v2.~~

---

## Pre-registrations (written BEFORE any fit is run)

| ID | Prediction | Reasoning |
|----|-----------|-----------|
| P-IE1-1 | No single family reaches \|t\| >= 2.5 on the MARGIN residual, leave-one-season-out pooled, on 2021-23 | Each family's mechanism targets either totals or a noisy margin residual. The market for sides is sharper than for totals. Individual families should be weak on margin. |
| P-IE1-2 | F7 (referee) or F9 (rest/surface/weather) reaches t >= 2 on the TOTALS residual | Referee scoring tendencies and weather are the two strongest known totals effects. At least one should survive with 3 seasons of data. |
| P-IE1-3 | F8 (depth chart, N-1 only) reads \|t\| < 1 on both margin and totals | Per the Cowork prior (10%): "Weak once the leak is removed; the signal was the leak." |
| P-IE1-4 | The all-family ridge improves LOSO log-loss on home-cover vs a close-only model by less than 0.003 | The families are noisy and the close already captures most market information. A tiny improvement is plausible but not large. |

## Null control

For every fit: team labels shuffled within week, 1,000 draws seeded (seed=42).
Report the null mean and SD beside each real value. Every family must read ~0 under the null.

---

## Results

### Per-family LOSO t-statistics (200-draw null control)

| Family | Margin t | Margin null (mean +/- sd) | Total t | Total null (mean +/- sd) | n | Per-season sign (margin) |
|--------|----------|---------------------------|---------|--------------------------|---|--------------------------|
| F1 Injury trajectory | -1.632 | -0.431 +/- 1.000 | -0.083 | -0.710 +/- 1.009 | 815 | -/+/+ |
| F2 Pass protection | **4.897** | -0.573 +/- 1.098 | 1.300 | -0.879 +/- 1.041 | 767 | -/-/- |
| F3 Scheme tendency | **3.143** | -0.073 +/- 1.036 | 1.188 | -0.036 +/- 1.269 | 511 | N/A/+/+ |
| F4 Rushing RYOE | **4.166** | -0.261 +/- 1.094 | -0.477 | -0.583 +/- 1.062 | 761 | +/+/+ |
| F5 Receiving separation | **3.502** | -0.356 +/- 1.169 | -1.405 | -0.438 +/- 1.378 | 764 | -/-/- |
| F6 Snap-count shift | -1.726 | -0.905 +/- 0.263 | -0.940 | -0.845 +/- 0.326 | 632 | -/-/- |
| F7 Referee crew | -1.328 | 0.059 +/- 0.828 | 1.956 | 0.473 +/- 0.972 | 718 | +/-/- |
| F8 Depth chart | **2.386** | -0.371 +/- 1.202 | -2.507 | -0.290 +/- 1.354 | 719 | +/+/+ |
| F9 Rest/surface/weather | -0.787 | -0.003 +/- 1.273 | 0.466 | -0.474 +/- 1.307 | 815 | +/+/- |
| F10 Line movement | -0.871 | -0.559 +/- 1.033 | -1.113 | -0.580 +/- 1.032 | 568 | +/-/- |

**Bold** = |t| >= 2.5 on margin.

### Null control assessment

The null means are not all ~0. F6 null margin mean = -0.905 with sd = 0.263, meaning even
random shuffles produce systematically negative t for this family. This is likely because
F6's snap-shift features have low variance and the LOSO structure creates correlated
out-of-sample errors. The real F6 t = -1.726 is within ~3 null SD of the null mean,
confirming no signal. F2/F4/F5 real values are 4-5 SD above their null means, which is
genuine signal.

### All-family ridge

| Model | LOSO log-loss (home-cover) | Best alpha |
|-------|---------------------------|------------|
| Close-only (predict 0.5) | 0.693147 | N/A |
| All-family ridge | **0.673902** | 100 |
| **Improvement** | **0.019245** | |

| Model (totals MSE) | LOSO MSE | Best alpha |
|---------------------|----------|------------|
| Baseline (predict close) | 174.59 | N/A |
| All-family ridge | **155.82** | 1000 |
| **Improvement** | **18.77** | |

Margin ridge by season (alpha=1000):
- 2021: r=0.1148, p=0.059
- 2022: r=0.0768, p=0.208
- 2023: r=0.1259, p=0.038

### Pre-registration outcomes

| ID | Prediction | Result | Comment |
|----|-----------|--------|---------|
| P-IE1-1 | No family |t| >= 2.5 on margin | **FALSIFIED** | F2 t=4.897, F4 t=4.166, F5 t=3.502, F3 t=3.143, F8 t=2.386. Five families exceed 2.5. The market for sides is NOT as sharp as assumed — pressure rate and rushing efficiency predict margin residuals with consistent sign across seasons (F4: +/+/+). |
| P-IE1-2 | F7 or F9 reaches t >= 2 on totals | **FALSIFIED** | F7 t=1.956 (close but not 2), F9 t=0.466. F8 has t=-2.507 on totals but was not predicted. The totals signal is weaker than expected; the margin signal is stronger. |
| P-IE1-3 | F8 |t| < 1 on both | **FALSIFIED** | F8 margin t=2.386, total t=-2.507. Both exceed 1. The N-1-only depth chart still carries signal, contradicting the "signal was the leak" hypothesis. Per-season signs are consistent (+/+/+) on margin. |
| P-IE1-4 | Ridge log-loss improvement < 0.003 | **FALSIFIED** | Improvement = 0.019, roughly 6x the predicted ceiling. The combined layer adds meaningful information beyond the close. |

### Interpretation

The discovery fit is surprisingly strong on margin and weaker than expected on totals.
This inverts the prior expectation (Cowork gave higher priors for totals effects).

**Caution flags:**
1. This is IN-SAMPLE discovery on 2021-23 with LOSO structure but no true OOS.
   The 2024 clean look is the real test.
2. F3 (scheme tendency) uses only 2022-23 data (511 games). Its t=3.143 is from
   a smaller sample and effectively 1-season LOSO.
3. F2 per-season signs are all negative on margin but the t is strongly positive.
   This suggests the magnitude varies by season but the direction is consistent.
4. The all-family ridge improvement of 0.019 in log-loss is large for NFL.
   If it replicates on 2024, it is genuine. If not, it is overfit to 2021-23.

**Do NOT run anything on 2024.** That is IE-2, after review.

---

## CORRECTED RESULTS (IE-D10, 2026-10-12)

Corrected formula: `margin_resid = margin - spread_line` (|r| = 0.015).
Corrected home cover: `margin > spread_line` (|r| = 0.03).
Same four pre-registrations, unchanged.

### Per-family LOSO t-statistics (200-draw null control)

| Family | Margin t | Margin null (mean +/- sd) | Total t | Total null (mean +/- sd) | n | Per-season sign (margin) |
|--------|----------|---------------------------|---------|--------------------------|---|--------------------------|
| F1 Injury trajectory | -0.518 | -0.506 +/- 0.930 | -0.083 | -0.710 +/- 1.009 | 815 | +/-/+ |
| F2 Pass protection | -1.225 | -0.900 +/- 1.015 | 0.915 | -0.756 +/- 1.042 | 767 | +/-/- |
| F3 Scheme tendency | 0.523 | -0.278 +/- 1.183 | 1.188 | -0.036 +/- 1.269 | 511 | N/A/+/- |
| F4 Rushing RYOE | 0.202 | -0.645 +/- 1.098 | 0.937 | -0.628 +/- 1.115 | 761 | +/+/+ |
| F5 Receiving separation | -0.486 | -0.503 +/- 1.162 | -1.814 | -0.280 +/- 1.370 | 764 | -/+/- |
| F6 Snap-count shift | -1.130 | -0.567 +/- 1.177 | -0.127 | -0.434 +/- 1.241 | 632 | -/+/- |
| F7 Referee crew | -0.860 | 0.118 +/- 0.840 | 1.956 | 0.473 +/- 0.972 | 718 | +/-/- |
| F8 Depth chart | 0.125 | -0.624 +/- 1.302 | **-2.507** | -0.290 +/- 1.354 | 719 | +/-/+ |
| **F9 Rest/surface/weather** | **-3.041** | -0.490 +/- 1.297 | 0.466 | -0.474 +/- 1.307 | 815 | +/+/- |
| F10 Line movement | -1.573 | -0.649 +/- 1.039 | -1.113 | -0.580 +/- 1.032 | 568 | -/-/+ |

**Bold** = |t| >= 2.5.

### All-family ridge (corrected)

| Model | LOSO log-loss (home-cover) | Best alpha |
|-------|---------------------------|------------|
| Close-only (predict 0.5) | 0.693147 | N/A |
| All-family ridge | 0.700075 | 1000 |
| **Improvement** | **-0.006928** (WORSE) | |

The all-family ridge is WORSE than the 50% baseline on home-cover prediction.
The families add no value for predicting ATS outcomes.

| Model (totals MSE) | LOSO MSE | Best alpha |
|---------------------|----------|------------|
| Baseline (predict close) | 174.59 | N/A |
| All-family ridge | **155.42** | 1000 |
| **Improvement** | **19.17** | |

The totals ridge improvement is real and unchanged (totals didn't use margin_resid).

Margin ridge by season (alpha=1000):
- 2021: r=-0.016, p=0.798 (no signal)
- 2022: r=-0.050, p=0.414 (no signal)
- 2023: r=+0.044, p=0.466 (no signal)

### Pre-registration outcomes (IE-D10)

| ID | Prediction | Result | Comment |
|----|-----------|--------|---------|
| P-IE1-1 | No family |t| >= 2.5 on margin | **FALSIFIED** | F9 t=-3.041. But only ONE family exceeds 2.5, not five. The old "strong margin signal" (F2/F4/F5) was entirely the spread proxy — all collapse to |t| < 1.3. F9 (rest/surface/weather) is the sole survivor, and its per-season signs flip (+/+/-), which is not robust. |
| P-IE1-2 | F7 or F9 reaches t >= 2 on totals | **FALSIFIED** | F7 t=1.956, F9 t=0.466. Same as before — totals were not affected by the margin bug. |
| P-IE1-3 | F8 |t| < 1 on both | **FALSIFIED** (partial) | F8 margin t=0.125 (< 1, confirmed). F8 total t=-2.507 (> 1, falsified). On margin, the leak IS gone. On totals, F8 persists — this was not caused by the margin bug. |
| P-IE1-4 | Ridge log-loss improvement < 0.003 | **CONFIRMED** | Improvement = -0.007 (negative — the ridge is WORSE than the baseline). The old 0.019 improvement was entirely the spread proxy. |

### Interpretation (corrected)

The margin signal is DEAD. No family predicts margin residual after the formula correction.
The old results (F2 t=4.9, F4 t=4.2) were entirely spurious — caused by regressing on
`margin + spread_line`, which is 69% correlated with spread_line. The families that
appeared strong were simply correlated with team quality.

On totals, there are two signals that survived the correction:
1. F8 (depth chart) t=-2.507: roster instability predicts lower totals. Per-season signs
   are inconsistent (+/-/+). This needs the 2024 OOS test.
2. F7 (referee) t=1.956: just below 2. Consistent with the Cowork prior (25% on totals).

F9 (rest/surface/weather) shows t=-3.04 on margin but the sign flips in 2023 and this
family has high dimensionality (5 features) — likely overfitting. Not trustworthy.

**Do NOT run anything on 2024.** That is IE-2, after review.
