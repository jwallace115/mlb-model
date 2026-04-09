# Phase 6 — Multi-Factor Team Total Pricing Engine

**Date:** 2026-04-09
**Verdict: ADVANCE** -- posted team total lines available (4,488 games, 2023-2025), SP-driven signal reaches 56-58% hit rate vs real posted lines, stable across both OOS seasons.

---

## Part 1 — Data Availability

### Posted Team Total Lines (Odds API historical)

| Metric | Value |
|--------|-------|
| Total records pulled | 5,842 |
| OK (lines present) | 4,488 |
| No market | 1,354 |
| Date range | 2023-08-14 to 2025-09-28 |
| Books >= 3 (liquid) | 3,910 |
| Books >= 5 (thick) | 3,664 |

**By year:**

| Year | Games | Thick (5+ books) | Median books |
|------|-------|-------------------|--------------|
| 2023 | 520 | 395 | 8 |
| 2024 | 1,998 | 1,642 | 6 |
| 2025 | 1,970 | 1,627 | 5 |

Team total markets are well-covered by major US books. The existing `team_totals_historical.parquet` provides real snapshot-level lines with book-count metadata. Thick-market subsample (books >= 3) yields 3,468 games after joining with feature table and closing game totals.

Naive 50/50 split diverges from posted home TT by > 0.25 runs in 48.9% of games -- the market already prices asymmetric team totals. This means the fair-value model must beat the posted line, not just the naive split.

---

## Part 2 — Fair Value Model Architecture

### Components

**Layer 1 -- Naive 50/50:** `team_runs = closing_total / 2`

**Layer 2 -- Empirical scoring share:** Overall home share = 0.5015 (nearly symmetric). Band-level shares show a pattern: home share declines as totals rise (0.53 at low totals, 0.43 at 11+). Global share used for simplicity.

**Layer 3 -- Truncation adjustment:** Home team does not bat in bottom of 9th when leading.
- Home win rate: 53.2%
- Runs per half-inning: 0.467
- Truncation estimate: 0.248 runs subtracted from home expected runs

**Layer 4 -- Starter quality:**
- League avg xFIP: 4.231
- Avg SP innings: 5.59 -> innings_factor = 0.621
- Home adjustment: `(opp_away_SP_xfip - 4.231) * 0.621`
- Away adjustment: `(opp_home_SP_xfip - 4.231) * 0.621`

**Layer 5 -- Park factor:** Applied as `(park_factor/100 - 1) * base_runs`. Adds marginal noise; dropped from best configuration.

### Final formula (Layer 4):
```
fair_home = closing_total * 0.5015 - 0.248 + (away_SP_xfip - 4.231) * 0.621
fair_away = closing_total * 0.4985         + (home_SP_xfip - 4.231) * 0.621
```

---

## Part 3 — Ablation (MAE vs actual team runs, N=4,855)

| Layer | Home MAE | Away MAE | Avg MAE | Home RMSE | Away RMSE |
|-------|----------|----------|---------|-----------|-----------|
| L1 Naive 50/50 | 2.364 | 2.509 | 2.437 | 3.072 | 3.222 |
| L2 Empirical share | 2.366 | 2.508 | 2.437 | 3.071 | 3.223 |
| L3 + Truncation | 2.356 | 2.508 | 2.432 | 3.099 | 3.223 |
| L4 + Starter | **2.334** | **2.491** | **2.412** | **3.070** | **3.203** |
| L5 + Park | 2.348 | 2.504 | 2.426 | 3.085 | 3.212 |

**Best layer: L4 (truncation + starter).** Avg MAE drops 0.025 runs vs naive. Park factor adds noise and is excluded.

Season stability: L4 improvement is consistent (2024: -0.027, 2025: -0.021 vs naive).

---

## Part 4 — Market Gap

### Derived gap (naive 50/50 as proxy)
- Home gap: mean = +0.236 (driven by truncation constant)
- Away gap: mean = +0.012 (nearly zero)

### Gap vs real posted lines (books >= 3)
- Posted home TT vs fair: mean gap = +0.097 (market already partially prices truncation)
- Posted away TT vs fair: mean gap = -0.250 (market over-adjusts away totals downward)

The market prices some asymmetry but the model finds residual mispricing, particularly when SP quality diverges from league average.

---

## Part 5 — Directional Signal

### Against real posted team total lines (books >= 3, N=3,468 base)

**Home UNDER (posted line > fair value):**

| Threshold | N | Hit Rate | ROI @-110 | 2024 | 2025 |
|-----------|---|----------|-----------|------|------|
| > 0.15 | 1,731 | 55.7% | +6.4% | 55.5% / +6.0% | 56.0% / +6.9% |
| > 0.25 | 1,473 | 55.9% | +6.7% | 55.4% / +5.8% | 56.4% / +7.7% |
| > 0.35 | 1,237 | 55.1% | +5.3% | 54.9% / +4.9% | 55.3% / +5.7% |
| > 0.50 | 896 | 56.1% | +7.2% | 56.5% / +7.9% | 55.7% / +6.4% |

**Away UNDER (posted line > fair value):**

| Threshold | N | Hit Rate | ROI @-110 | 2024 | 2025 |
|-----------|---|----------|-----------|------|------|
| > 0.15 | 912 | 56.4% | +7.6% | 54.2% / +3.4% | 58.9% / +12.5% |
| > 0.25 | 717 | 58.0% | +10.8% | 56.9% / +8.6% | 59.3% / +13.3% |
| > 0.35 | 511 | 58.9% | +12.5% | 59.1% / +12.8% | 58.7% / +12.1% |
| > 0.50 | 318 | 56.9% | +8.7% | 58.2% / +11.2% | 55.1% / +5.3% |

**Home OVER (posted line < fair value):**

| Threshold | N | Hit Rate | ROI @-110 |
|-----------|---|----------|-----------|
| > 0.15 | 979 | 56.4% | +7.6% |
| > 0.25 | 771 | 57.1% | +8.9% |
| > 0.35 | 614 | 55.4% | +5.7% |
| > 0.50 | 376 | 57.2% | +9.2% |

**Away OVER (posted line < fair value):**

| Threshold | N | Hit Rate | ROI @-110 |
|-----------|---|----------|-----------|
| > 0.15 | 1,832 | 52.7% | +0.7% |
| > 0.25 | 1,612 | 53.6% | +2.3% |
| > 0.35 | 1,376 | 54.5% | +4.1% |
| > 0.50 | 1,031 | 54.0% | +3.1% |

### Unconditional baselines (posted lines, all games):
- Home UNDER: 51.4%, ROI = -1.9%
- Away UNDER: 51.5%, ROI = -1.7%

All filtered signals beat the unconditional baseline by 4-7 percentage points.

---

## Part 6 — Component Attribution

### Decomposition of signal

| Component | Home contribution | Away contribution |
|-----------|-------------------|-------------------|
| Truncation (constant) | 0.236 runs | 0.000 runs |
| SP adjustment (variable) | mean 0.000, std 0.309 | mean 0.000, std 0.306 |

### Isolated component signals (vs real posted lines)

**Truncation-only (no SP adjustment):**
- Home UNDER gap > 0.15: N=1,781, hit = 53.5%, ROI = +2.0%
- Home UNDER gap > 0.25: N=1,261, hit = 53.4%, ROI = +1.9%

**SP-only (no truncation):**
- Home UNDER gap > 0.25: N=912, hit = 56.0%, ROI = +7.0%
- Away UNDER gap > 0.25: N=699, hit = 57.8%, ROI = +10.3%
- Away UNDER gap > 0.35: N=487, hit = 58.7%, ROI = +12.1%

**Combined (truncation + SP aligned):**
- Home UNDER gap > 0.25 + SP < 0: N=888, hit = 56.8%, ROI = +8.4%
- Away UNDER gap > 0.25 + SP < 0: N=492, hit = 61.6%, ROI = +17.6%
- Away UNDER gap > 0.35 + SP < 0: N=333, hit = 64.3%, ROI = +22.7%

**Key finding:** The SP component is the primary signal driver. Truncation alone yields only +2% ROI (marginal). SP quality divergence vs posted lines produces 56-58% hit rates independently. When both components align, the combined signal is strongest (especially away under at 61-64%).

### Correlation check
- corr(gap_home, scoring_miss): -0.0949
- corr(gap_away, scoring_miss): -0.1043
- Direction: Correct for both (larger gap -> actual scores lower relative to posted line)

---

## Part 7 — Framing and Deployment Readiness

### Signal summary

| Signal | N/season | Hit rate | ROI @-110 | Season stability |
|--------|----------|----------|-----------|------------------|
| Home UNDER gap > 0.25 | ~735 | 55.9% | +6.7% | 2024: +5.8%, 2025: +7.7% |
| Away UNDER gap > 0.25 | ~360 | 58.0% | +10.8% | 2024: +8.6%, 2025: +13.3% |
| Home OVER gap > 0.25 | ~385 | 57.1% | +8.9% | Not split-tested |
| Combined away gap>0.25 + SP<0 | ~250 | 61.6% | +17.6% | Needs OOS validation |

### Strengths
1. **Real posted lines used as the benchmark.** Signal is not against a naive proxy.
2. **SP component drives the signal**, not a static truncation constant. This means the engine is finding genuine per-game mispricing.
3. **Season-stable:** Both 2024 and 2025 show positive ROI at all tested thresholds for home under and away under.
4. **Large sample sizes:** 700-1,700 bets per threshold, sufficient for statistical confidence.
5. **Correct correlation sign:** gap predicts scoring miss direction (r = -0.10).

### Weaknesses / Cautions
1. **No juice adjustment.** All ROI computed at flat -110. Real posted prices (home_over_price, away_under_price) would reduce effective ROI.
2. **Snapshot timing.** TT lines are T-1h snapshots; closing lines may differ.
3. **No wRC+ or offense adjustment.** Only SP xFIP used. Adding offense quality could sharpen but also risks overfitting.
4. **Park factor degraded signal.** Suggests park effects are already priced into posted TT lines.
5. **Away OVER signal is weak** (52-54% hit rate). The engine is asymmetric -- better at identifying unders than overs.

### Recommended configuration for shadow deployment

```
Signal:   away_UNDER when gap_away > 0.25 AND sp_component_away < 0
          home_UNDER when gap_home > 0.25
          home_OVER  when gap_home < -0.25
Threshold: 0.25 runs (balance of volume and accuracy)
Market:   posted team total lines (books >= 3)
Expected: ~3-5 plays per day, 55-58% hit rate aggregate
```

### Next steps
1. Shadow-deploy this engine alongside existing full-game model in 2026 season
2. Capture real-time posted TT lines via Odds API team_totals market
3. Track actual vs fair gap and hit rates on live plays
4. After 200+ graded plays: evaluate whether combined ROI clears +3% at actual posted juice
5. If validated, integrate as a standalone team-total card in push_results output
