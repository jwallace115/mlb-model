# MLB Monthly ROI Backtest — 2022-2025 (V1 Model Retroactive)

**Date:** 2026-03-29
**Model:** Phase 9 Ridge (25 features, alpha=50, sigma=4.361)
**Note:** Bullpen delta/exposure features set to 0 for all games (not available in feature_table).
Flyball×wind interaction reconstructed. This gives approximate but not exact Phase 9 predictions.
Published validation ROI (+20.9%/+23.8%) was on 2024 OOS with real closing lines — differences expected.

## Seasonal Arc (ROI by month × unit size, N≥10 only)

| Unit | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |
|------|-----|-----|-----|-----|-----|-----|-----|-----|
| 0.5u | — | +10.4% | +15.6% | −14.8% | +23.9% | +12.4% | +13.4% | — |
| 1.0u | +4.1% | −5.0% | −1.3% | +1.6% | +8.6% | −3.2% | +22.8% | −4.6% |

## August Deep Dive

| Season | 0.5u ROI (N) | 1.0u ROI (N) |
|--------|-------------|-------------|
| 2022 | +23.5% (17) | +6.9% (25) |
| 2023 | −18.2% (21) | +4.5% (42) |
| 2024 | +6.9% (25) | −7.0% (39) |
| 2025 | +71.8% (10) | −15.2% (36) |

- **0.5u August:** SAMPLE_NOISE (negative 1/4 seasons)
- **1.0u August:** CONSISTENT weakness (negative 2/4 seasons)

## Overall

| Unit | N | Record | Win% | ROI | Best Month | Worst Month |
|------|---|--------|------|-----|------------|-------------|
| 0.5u | 411 | 232-164-15 | 58.6% | +7.8% | Jul (+23.9%) | Jun (−14.8%) |
| 1.0u | 1,004 | 540-424-40 | 56.0% | +2.7% | Sep (+22.8%) | Apr (−5.0%) |

## Cross-check vs Published Validation
- p_under > 0.57: ROI=+4.2% (all seasons), 2025 OOS=+7.6%
- p_under > 0.60: ROI=+2.7% (all seasons), 2025 OOS=+4.1%
- Published: +20.9% / +23.8% on 2024 OOS with real DK/FD lines
- Gap explained by: (1) bullpen features zeroed out, (2) 2022-2023 dilution, (3) push-as-loss convention
