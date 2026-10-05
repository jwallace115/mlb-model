# NHL Sim — Fit-Window Ledger

**Rule (A3):** whoever looks at a season appends a row the same day. A season is never
moved back toward PROSPECTIVE.

STATUS values: DISCOVERY, VALIDATION, CONSUMED, PARTIAL, PROSPECTIVE.

| Season  | Engine fit | Engine validate | Engine-vs-Pinnacle looked at | Price-rule or other use | STATUS |
|---------|-----------|-----------------|------------------------------|------------------------|--------|
| 2010-11 | -- | -- | -- | -- | -- |
| 2011-12 | -- | -- | -- | -- | -- |
| 2012-13 | -- | -- | -- | -- | -- |
| 2013-14 | -- | -- | -- | -- | -- |
| 2014-15 | -- | -- | -- | -- | -- |
| 2015-16 | -- | -- | -- | -- | -- |
| 2016-17 | -- | -- | -- | -- | -- |
| 2017-18 | -- | -- | -- | -- | -- |
| 2018-19 | -- | -- | -- | -- | -- |
| 2019-20 | -- | -- | -- | -- | -- |
| 2020-21 | -- | -- | -- | -- | -- |
| 2021-22 | xG v2 fit (S8), shrinkage K/w (S27), constants v2/v5/v7/v8 fit | -- | -- | -- | DISCOVERY |
| 2022-23 | Same fits as 2021-22; engine priced (S41/S50) | Fit-season reports: S42/S44 ML LL 0.6594 vs Pin 0.6568, A1 0.448; S52 8 regimes | Fit-season; LL, Brier, A1, reliability, calibration, regime tests all computed | L-003 EV dev | DISCOVERY |
| 2023-24 | -- | S42/S44/S51: ML LL 0.6646 vs Pin 0.6567, A1 −0.051; Totals LL 0.7004 vs 0.6942; S45 calibration; S48/S52 16 regimes (no BH survivors); C-01 | Realism gate; PREREG_CLV (L-001); A-01..A-06; E-01/E-02 in-play DEV | Heavily used for selection; not OOS for anything regime-shaped | VALIDATION |
| 2024-25 | -- | S48-ML-R6 one-shot (A1 −0.58, 99 picks); V-01 totals | 1,312 games priced with SWAPPED engine 2026-09-30 (logs/cowork_stage/prices2024/); B-01 3-way at the books; E-03 pre-registered on its in-play tape (not run) | EV2 (L-004) price-rule confirmation on 2024-26 | CONSUMED |
| 2025-26 | -- | -- | EV2 (L-004) confirmation consumed it; outcomes seen in aggregate during edge hunt; used for 10-01/10-02 layers picks | NO engine prices exist; engine-vs-Pinnacle relation unseen | PARTIAL |
| 2026-27 | -- | -- | -- | Forward pilot only | PROSPECTIVE |
