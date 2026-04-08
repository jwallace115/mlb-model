# NCAAF Base Spread Engine — Phase 2 Results

**Date:** 2026-04-08

**Model:** Ridge regression (alpha=100)

**Features:** 15

**Train:** 1484 games (2022-2023)
**Validate:** 752 games (2024)
**OOS:** 762 games (2025)

---

## Feature Coefficients

| Feature | Coefficient |
|---------|------------|
| diff_prior_sp | +3.7024 |
| diff_prior_sp_def | -2.8972 |
| diff_talent | +2.7635 |
| diff_rolling_margin_3g | +2.4939 |
| diff_rolling_ppa_off | +2.2270 |
| diff_returning_ppa | +1.9591 |
| diff_prior_sp_off | +1.7705 |
| diff_prior_ppa_def | +0.9211 |
| week | -0.6339 |
| conf_game | -0.5507 |
| diff_rolling_ppa_def | -0.5497 |
| home_flag | +0.4565 |
| diff_prior_ppa_off | -0.1842 |
| diff_portal_net_stars | -0.1549 |
| diff_new_coach | -0.0318 |
| intercept | +4.0317 |

---

## Primary Metrics

| Split | N | MAE | RMSE | Corr(pred,actual) | Corr(pred,spread) | Market MAE | MAE vs Market |
|-------|---|-----|------|-------------------|-------------------|------------|--------------|
| Train | 1484 | 12.79 | 16.10 | 0.5978 | 0.9025 | 12.01 | +0.78 |
| Validate | 752 | 13.38 | 17.01 | 0.5509 | 0.8681 | 12.22 | +1.16 |
| OOS | 762 | 13.23 | 16.82 | 0.5765 | 0.8558 | 11.87 | +1.36 |

---

## ATS Analysis (OOS 2025)

| Edge Threshold | N Bets | Wins | Hit Rate | ROI (-110) |
|----------------|--------|------|----------|------------|
| >= 0 | 762 | 381 | 0.500 | -9.1% |
| >= 1 | 662 | 330 | 0.498 | -9.4% |
| >= 2 | 576 | 285 | 0.495 | -10.0% |
| >= 3 | 487 | 238 | 0.489 | -11.1% |

### ATS by Split

| Split | Edge Threshold | N Bets | Wins | Hit Rate | ROI (-110) |
|-------|----------------|--------|------|----------|------------|
| Train | >= 0 | 1484 | 754 | 0.508 | -7.6% |
| Train | >= 1 | 1287 | 653 | 0.507 | -7.7% |
| Train | >= 2 | 1087 | 556 | 0.512 | -6.9% |
| Train | >= 3 | 889 | 442 | 0.497 | -9.6% |
| Validate | >= 0 | 752 | 376 | 0.499 | -9.2% |
| Validate | >= 1 | 673 | 336 | 0.500 | -9.1% |
| Validate | >= 2 | 573 | 274 | 0.479 | -12.9% |
| Validate | >= 3 | 482 | 236 | 0.489 | -11.2% |
| OOS | >= 0 | 762 | 381 | 0.500 | -9.1% |
| OOS | >= 1 | 662 | 330 | 0.498 | -9.4% |
| OOS | >= 2 | 576 | 285 | 0.495 | -10.0% |
| OOS | >= 3 | 487 | 238 | 0.489 | -11.1% |

---

## Calibration by Spread Bucket

| Bucket | N | Mean Pred | Mean Actual | Mean Market | Pred-Actual |
|--------|---|-----------|-------------|-------------|-------------|
| <-21 | 336 | 21.5 | 29.2 | 29.0 | -7.7 |
| -21:-14 | 338 | 13.3 | 16.1 | 17.0 | -2.8 |
| -14:-7 | 475 | 8.2 | 10.2 | 10.0 | -2.0 |
| -7:-3 | 456 | 3.9 | 5.9 | 4.7 | -2.0 |
| -3:3 | 532 | 0.5 | -0.2 | -0.1 | +0.7 |
| 3:7 | 325 | -2.9 | -4.2 | -5.1 | +1.3 |
| 7:14 | 328 | -7.0 | -11.0 | -10.3 | +4.0 |
| 14:21 | 131 | -11.1 | -18.3 | -17.0 | +7.2 |
| >21 | 77 | -18.3 | -22.3 | -25.7 | +3.9 |

---

## Season Stability

| Season | N | MAE | Correlation |
|--------|---|-----|------------|
| 2022 | 734 | 12.95 | 0.5800 |
| 2023 | 750 | 12.63 | 0.6150 |
| 2024 | 752 | 13.38 | 0.5509 |
| 2025 | 762 | 13.23 | 0.5765 |

---

## Splits

| Split | N | MAE | Correlation |
|-------|---|-----|------------|
| Home (non-neutral) | 739 | 13.25 | 0.5785 |
| Neutral | 23 | 12.45 | 0.4047 |
| Both P5 | 331 | 12.28 | 0.5668 |
| Both G5 | 319 | 13.84 | 0.4140 |
| P5 vs G5 | 112 | 14.32 | 0.6767 |
| Favorites (spread < -3) | 407 | 13.15 | 0.4279 |
| Pick'em (-3 to 3) | 132 | 11.82 | 0.0682 |
| Underdogs (spread > 3) | 223 | 14.21 | 0.1652 |
| Weeks 1-4 | 195 | 13.70 | 0.6164 |
| Weeks 5+ | 567 | 13.07 | 0.5422 |
| Conference | 548 | 13.06 | 0.5063 |
| Non-Conference | 214 | 13.68 | 0.6361 |

---

## Verdict

**ADVANCE**

OOS MAE=13.23 (< 14), Corr=0.5765 (> 0.40), season MAE range 12.63-13.38 (stable). Engine meets all thresholds for overlay development.
