# First-Inning Scoring Model — Phase 1 Audit & Baseline

**Date:** 2026-04-06
**Scope:** 2024-2025 only (4,361 games). No 2022-2023 backfill.
**Method:** Logistic regression, chronological 70/30 split.

---

## Target Audit

| Target | Status | Source | Coverage |
|--------|--------|--------|----------|
| top1_scored | AVAILABLE | `research/yrfi/data/yrfi_actuals.parquet` → `first_inning_runs_away > 0` | 4,361 games |
| bot1_scored | AVAILABLE | Same file → `first_inning_runs_home > 0` | 4,361 games |

**Base rates (full dataset):**
- Top-of-1st scoring (away): **26.9%**
- Bottom-of-1st scoring (home): **30.1%**
- YRFI (any first-inning run): **48.5%**

---

## Feature Audit

| Family | Status | Columns Used | Coverage |
|--------|--------|-------------|----------|
| A: Top-of-order (broad) | AVAILABLE | team_obp/slg/iso rolling 15 | 74.4% |
| A: Top-of-order (micro) | AVAILABLE | top3_obp/slg/iso/k_rate rolling 15 | 74.4% |
| B: Starter quality (broad) | AVAILABLE | era/k9/bb9/hr9 rolling 5 starts | 68.5% |
| B: Starter early-inning (micro) | PARTIAL | pitcher_woba_tto1_rolling (PROXY) | 69.2% |
| C: Handedness/platoon | AVAILABLE | top3_platoon_frac | 75.6% |
| D: HR environment | AVAILABLE | park_factor_hr, temp, wind, dome | 100% |

**Important caveat on Family B (micro):** `pitcher_woba_tto1_rolling` measures
first-time-through-order wOBA across batters 1-9 in their first plate appearance.
This is NOT inning-1-specific. A pitcher may face only 3-4 batters in the first
inning, while TTO1 covers all 9. It is a proxy, not a true first-inning stat.

---

## Train/Test Split

- Train: 3,052 games (2024-03-28 to 2025-06-10)
- Test: 1,309 games (2025-06-10 to 2025-09-28)
- After dropping nulls: ~700-725 per model (due to early-season rolling window warmup)

---

## Side-Level Results

### TOP1 (Away scores in top of 1st)

| Metric | Broad | Micro | Delta |
|--------|-------|-------|-------|
| N test | 724 | 694 | |
| Base rate | 0.261 | 0.255 | |
| AUC | 0.5253 | **0.5543** | +0.029 |
| Log loss improvement | -0.55% | **+0.19%** | +0.74pp |
| Brier improvement | -0.64% | **+0.26%** | +0.90pp |
| Top-decile hit rate | 0.315 | **0.343** | +0.028 |
| Top-decile lift | 1.21x | **1.34x** | +0.14x |
| Top-quintile lift | 0.98x | **1.30x** | +0.33x |

**Broad TOP1 is worse than naive** (negative Brier improvement). It has no
discriminative power beyond the base rate. Micro TOP1 shows marginal improvement.

Top 3 Micro TOP1 coefficients (standardized):
1. `away_t3_slg_r15` (-0.33) — higher SLG = less likely to score?? Counterintuitive sign.
2. `away_t3_iso_r15` (+0.25) — higher ISO = more likely to score. Expected.
3. `home_sp_tto1` (+0.18) — higher TTO1 wOBA = more runs allowed. Expected.

The SLG/ISO sign conflict suggests multicollinearity between SLG and ISO (ISO = SLG - AVG).
This is a feature engineering issue, not a real signal.

### BOT1 (Home scores in bottom of 1st)

| Metric | Broad | Micro | Delta |
|--------|-------|-------|-------|
| N test | 725 | 702 | |
| Base rate | 0.308 | 0.308 | |
| AUC | **0.5644** | 0.5485 | -0.016 |
| Log loss improvement | **+0.65%** | +0.38% | -0.27pp |
| Brier improvement | **+0.80%** | +0.50% | -0.30pp |
| Top-decile hit rate | 0.356 | **0.408** | +0.052 |
| Top-decile lift | 1.16x | **1.33x** | +0.17x |
| Top-quintile lift | **1.32x** | 1.24x | -0.08x |

Broad BOT1 has slightly better AUC and Brier, but Micro BOT1 has better top-decile
concentration. Mixed result — neither clearly dominates.

Top 3 Micro BOT1 coefficients:
1. `home_t3_iso_r15` (+0.41) — higher ISO = more scoring. Expected.
2. `home_t3_slg_r15` (-0.38) — same SLG/ISO collinearity issue.
3. `wind_speed` (+0.12) — more wind = more scoring. Expected.

---

## YRFI Combination

p(YRFI) = 1 - (1 - p_top1) * (1 - p_bot1)

| Metric | Broad (N=697) | Micro (N=645) | Delta |
|--------|--------------|--------------|-------|
| Base rate | 0.476 | 0.474 | |
| AUC | 0.5528 | 0.5560 | +0.003 |
| Brier improvement | +0.56% | +0.93% | +0.37pp |
| Log loss improvement | +0.40% | +0.68% | +0.28pp |
| Top-decile YRFI rate | 0.543 (1.14x) | 0.569 (1.20x) | +0.026 |
| Top-quintile YRFI rate | 0.536 (1.12x) | 0.543 (1.14x) | +0.007 |
| **Bottom-decile YRFI rate** | 0.429 | **0.385** | -0.044 |

Calibration (micro, quintiles):
- Q0 (lowest predicted): pred=0.429, actual=0.419
- Q1: pred=0.468, actual=0.442
- Q2: pred=0.490, actual=0.434
- Q3: pred=0.511, actual=0.535
- Q4 (highest predicted): pred=0.553, actual=0.543

Calibration is reasonable across buckets. No dramatic miscalibration.

---

## Honest Assessment

### Does top-of-order concentration add anything beyond broad team offense?

**Marginally, yes — but not enough to justify the branch.**

The micro model edges the broad model on:
- TOP1 AUC (+0.029) and top-decile lift (+0.14x)
- YRFI top-decile lift (+0.06x)
- NRFI bottom-decile rate (38.5% vs 42.9% — a meaningful 4.4pp difference)

But:
- **All Brier improvements are under 1%** across both models. This is noise-level.
- **All AUCs are in the 0.52-0.56 range** — barely above coin flip (0.50).
- **Top-decile lifts of 1.20-1.34x** sound decent but translate to going from
  ~27% to ~34% scoring rate. That's a real spread but not actionable against
  vig-laden YRFI markets (typically -115 to -125).
- The SLG/ISO coefficient sign conflict in both micro models suggests the
  "positional" signal is partly an artifact of correlated features, not genuine
  top-of-order concentration insight.
- **Platoon features** (`plat_frac`) do not appear in any model's top 5
  coefficients. The Phase C finding (platoon features flip OOS) appears to
  hold even in the first-inning scope.
- **TTO1** appears as a meaningful TOP1 coefficient (+0.18) but its absence
  from the BOT1 model suggests it's helping with one side only.

### Hard stop thresholds

| Criterion | Threshold | Result | Status |
|-----------|-----------|--------|--------|
| Top-decile lift | > 1.15x | 1.20x (YRFI micro) | PASS (barely) |
| Top-decile lift | > 1.10x | 1.14x (YRFI broad) | PASS (barely) |
| Brier improvement | > 5% | 0.93% (best) | **FAIL** |
| Training N after nulls | > 2,000 | ~1,440-1,520 | **BELOW target but not blocking** |

The Brier improvement threshold of 5% is not met by either model. The top-decile
lift barely clears the 1.10x minimum. This is a weak signal.

---

## Verdict

**The micro baseline does not materially outperform the broad baseline.**

The differences are real but small:
- YRFI AUC: +0.003 (micro over broad)
- YRFI Brier improvement: +0.37pp
- YRFI top-decile lift: +0.06x

These are within noise range for N=645-697 test samples. A bootstrap confidence
interval on the AUC difference would almost certainly span zero.

The one potentially useful finding: **bottom-decile NRFI identification**. The micro
model's bottom decile shows 38.5% YRFI rate vs 47.4% base — an 8.9pp suppression.
If NRFI markets are priced at ~50% implied, this could represent a small edge. But
this needs validation on out-of-sample data (2022-2023 backfill) before acting on it.

---

## Recommended Next Steps

1. **Do NOT deploy** either model as a signal generator. The signal is too weak
   for production use.

2. **Consider 2022-2023 backfill** (~5,300 API calls) to test whether the bottom-decile
   NRFI finding persists out of sample. If it does, it might support a narrow
   NRFI-fade signal (suppress YRFI plays in the bottom decile).

3. **Fix SLG/ISO collinearity** — drop SLG and keep ISO only, or use a composite
   (OPS or wOBA). The current model is fighting itself on these two features.

4. **If backfill confirms NRFI bottom-decile finding:** build a simple 3-bucket
   classifier (GREEN/YELLOW/RED) and use it as a filter on YRFI/NRFI parlay
   candidates, not as a standalone signal.

5. **Do NOT pursue** platoon features further in this scope. They contribute nothing.
