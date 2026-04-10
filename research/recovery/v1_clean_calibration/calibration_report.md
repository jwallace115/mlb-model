# V1 Clean Calibration Report

## Calibration Table

               n  actual_rate    mean_p
p_bucket                               
(0.0, 0.4]    97     0.525773  0.369559
(0.4, 0.45]  188     0.489362  0.427632
(0.45, 0.5]  243     0.489712  0.474209
(0.5, 0.55]  171     0.491228  0.523271
(0.55, 0.6]   67     0.462687  0.571305
(0.6, 0.65]   13     0.384615  0.620717
(0.65, 0.7]    2     1.000000  0.662558
(0.7, 1.0]     2     1.000000  0.907250

## Brier Score: 0.2550

## Optimal Threshold (Val 2024): p > 0.64
- Val ROI: -4.5%
- OOS ROI: -4.5% (8 bets)

## Does p_under > 0.57 still work?
See backtest results. The threshold was optimized on validation data.
