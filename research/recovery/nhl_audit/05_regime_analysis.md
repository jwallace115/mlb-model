# NHL Audit -- Phase 5: Regime Analysis

## Date: 2026-04-10

## Performance by Split/Season

### Historical Performance (from Phase 5 report, flat -110)
| Split | Signals | W-L-P | Hit Rate | ROI |
|-------|---------|-------|----------|-----|
| Validate (2023-24) | 255 | 136-117-2 | 53.75% | +2.60% |
| OOS (2024-25) | 154 | 82-72-0 | 53.25% | +1.65% |
| Combined | 409 | 218-189-2 | 53.55% | +2.25% |

### Live Performance (2025-26 season)
| Month | Signals | W-L | Hit Rate | ROI |
|-------|---------|-----|----------|-----|
| 2026-03 | 42 | 18-24 | 42.9% | -18.2% |
| 2026-04 | 23 | 9-14 | 39.1% | -25.3% |
| Total | 65 | 27-38 | 41.5% | -20.5% |

### Degradation: -11.8 percentage points (53.25% OOS to 41.5% live)

## By Signal Side

| Side | Hist Val | Hist OOS | Live |
|------|----------|----------|------|
| OVER | 53.3% (15) | 54.0% (50) | 40.0% (5) |
| UNDER | 53.8% (240) | 52.9% (104) | 41.7% (60) |

Live is dominated by UNDER signals: 69/74 (93.2%).
The UNDER bias results from the model's frozen features defaulting to
2024-25 league averages combined with a static drift correction calibrated
on 2023-24. If 2025-26 scoring is higher than the model expects, the
lambda projection systematically undershoots, pushing edges toward UNDER.

## By Confidence Tier

| Tier | Hist Val Hit | Hist Val ROI | Live Hit | Live W-L |
|------|-------------|-------------|----------|----------|
| HIGH | 50.0% | -4.55% | 41.7% | 5-7 |
| MEDIUM | 56.2% | +7.25% | 46.9% | 15-17 |
| LOW | 54.4% | +3.85% | 26.7% | 4-11 |

### FINDING F7 -- Tier Inversion in Live

Severity: HIGH

In the historical backtest, MEDIUM tier was the best performer (+7.25% ROI).
In live trading, no tier is profitable:
- HIGH: 41.7% (was 50.0% historically)
- MEDIUM: 46.9% (was 56.2% historically -- 9.3pp drop)
- LOW: 26.7% (was 54.4% historically -- 27.7pp drop)

The LOW tier collapse is particularly severe and suggests the model's
weaker signals are pure noise in the live context.

## Calibration Regime

### FINDING F8 -- Static Drift Correction Misapplied to New Season

Severity: HIGH

The live pipeline uses VALIDATE_DRIFT = 0.4458 as a constant seasonal
drift correction. This was computed from the 2023-24 validate season.

From the Phase 4.5 calibration audit:
- Train drift: -0.0808
- Validate drift: +0.3713
- OOS drift: +0.7706

The drift varies substantially across seasons. The 2024-25 OOS season
required +0.7706 drift, nearly 2x the validate drift. Using +0.4458
for 2025-26 is arbitrary and likely wrong.

The dynamic drift computation in Phase 4.5 uses expanding mean of
actual-vs-predicted residuals within the season. But the live pipeline
does NOT implement this -- it uses the static fallback for all games
because the condition for dynamic computation is never met in practice
(it would require storing model predictions for all prior games).

## Model Bias Analysis (from Phase 3 audit)

### FINDING F9 -- Systematic Under-Projection

The Phase 3 model audit reveals a systematic negative bias:
- OOS Model bias: -0.7864 (model undershoots total by 0.79 goals on average)
- Market bias: -0.1410 (market undershoots by 0.14)
- Raw edge distribution: mean=-0.645, median=-0.666

The model systematically projects lower totals than the market. After
calibration, this is partially corrected, but the correction is season-
specific and may not transfer to 2025-26.

The 90th percentile of raw edge is -0.048 -- even after calibration,
the model almost never projects ABOVE the market. This explains the
extreme UNDER bias in live signals.

## Variance Calibration

From Phase 4.5 diagnostics:
- 3B Variance: FAIL (mean per-game sim std 2.479 vs actual std 2.311)
- 3C Tail P(total >= 7): FAIL (sim 41.75% vs actual 45.66%, diff -3.90pp)
- 3D Market calibration at 6.0 and 6.5: FAIL

The model under-prices over outcomes, especially at 6.0 and 6.5 lines.
This is another contributor to the UNDER bias -- the simulation
systematically underestimates the probability of high-scoring games.

## Verdict

The regime analysis reveals multiple compounding failures:
1. Feature identity gap eliminates 79.4% of discriminative power
2. Static drift correction is miscalibrated for the current season
3. Systematic under-projection bias drives extreme UNDER signal ratio
4. Variance calibration failures compound the directional bias
5. No tier produces profitable results in live operation
