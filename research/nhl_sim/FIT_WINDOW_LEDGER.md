# NHL Sim — Fit-Window Ledger

**Rule (A3):** whoever looks at a season appends a row the same day. A season is never
moved back toward PROSPECTIVE.

STATUS values: DISCOVERY, VALIDATION, CONSUMED, PARTIAL, PROSPECTIVE.

| Season  | Engine fit | Engine validate | Engine-vs-Pinnacle looked at | Price-rule or other use | STATUS |
|---------|-----------|-----------------|------------------------------|------------------------|--------|
| 2010-11 | Fit window for T=2012 (with 2011-12) | -- | -- | -- | DISCOVERY |
| 2011-12 | Fit window for T=2012 (with 2010-11), T=2013 (with 2012-13) | -- | -- | -- | DISCOVERY |
| 2012-13 | Fit window for T=2013 (with 2011-12), T=2014 (with 2013-14) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6767 vs 0.6692, A1 0.372 p=0.39 | Walk-forward eval D8 | -- | VALIDATION |
| 2013-14 | Fit window for T=2014 (with 2012-13), T=2015 (with 2014-15) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6757 vs 0.6749, A1 0.595 p=0.03 | Walk-forward eval D8 | -- | VALIDATION |
| 2014-15 | Fit window for T=2015 (with 2013-14), T=2016 (with 2015-16) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6747 vs 0.6649, A1 0.165 p=0.56 | Walk-forward eval D8 | -- | VALIDATION |
| 2015-16 | Fit window for T=2016 (with 2014-15), T=2017 (with 2016-17) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6843 vs 0.6774, A1 0.318 p=0.36 | Walk-forward eval D8 | -- | VALIDATION |
| 2016-17 | Fit window for T=2017 (with 2015-16), T=2018 (with 2017-18) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6774 vs 0.6671, A1 -0.014 p=0.97 | Walk-forward eval D8 | -- | VALIDATION |
| 2017-18 | Fit window for T=2018 (with 2016-17), T=2019 (with 2018-19) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6801 vs 0.6681, A1 0.039 p=0.92 | Walk-forward eval D8 | -- | VALIDATION |
| 2018-19 | Fit window for T=2019 (with 2017-18), T=2020 (with 2019-20) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6794 vs 0.6726, A1 0.223 p=0.51 | Walk-forward eval D8 | -- | VALIDATION |
| 2019-20 | Fit window for T=2020 (with 2018-19) | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6811 vs 0.6794, A1 0.473 p=0.14 | Walk-forward eval D8 | -- | VALIDATION |
| 2020-21 | -- | Walk-forward priced and evaluated at the SBRO close (D8): ML LL 0.6701 vs 0.6536, A1 -0.112 p=0.81 | Walk-forward eval D8 | -- | VALIDATION |
| 2021-22 | xG v2 fit (S8), shrinkage K/w (S27), constants v2/v5/v7/v8 fit | -- | -- | -- | DISCOVERY |
| 2022-23 | Same fits as 2021-22; engine priced (S41/S50) | Fit-season reports: S42/S44 ML LL 0.6594 vs Pin 0.6568, A1 0.448; S52 8 regimes | Fit-season; LL, Brier, A1, reliability, calibration, regime tests all computed | L-003 EV dev | DISCOVERY |
| 2023-24 | -- | S42/S44/S51: ML LL 0.6646 vs Pin 0.6567, A1 −0.051; Totals LL 0.7004 vs 0.6942; S45 calibration; S48/S52 16 regimes (no BH survivors); C-01 | Realism gate; PREREG_CLV (L-001); A-01..A-06; E-01/E-02 in-play DEV | Heavily used for selection; not OOS for anything regime-shaped | VALIDATION |
| 2024-25 | -- | S48-ML-R6 one-shot (A1 −0.58, 99 picks); V-01 totals | 1,312 games priced with SWAPPED engine 2026-09-30 (logs/cowork_stage/prices2024/); B-01 3-way at the books; E-03 pre-registered on its in-play tape (not run) | EV2 (L-004) price-rule confirmation on 2024-26 | CONSUMED |
| 2025-26 | -- | -- | EV2 (L-004) confirmation consumed it; outcomes seen in aggregate during edge hunt; used for 10-01/10-02 layers picks | NO engine prices exist; engine-vs-Pinnacle relation unseen | PARTIAL |
| 2026-27 | -- | -- | -- | Forward pilot only | PROSPECTIVE |
