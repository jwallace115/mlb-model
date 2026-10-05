# NHL Sim — Fit-Window Ledger

**Rule (A3):** whoever looks at a season appends a row the same day. A season is never
moved back toward PROSPECTIVE.

STATUS values: DISCOVERY, VALIDATION, CONSUMED, PARTIAL, PROSPECTIVE.

| Season    | Engine fit | Engine validate | Engine-vs-Pinnacle looked at                                                                 | Price-rule or other use                              | STATUS      |
|-----------|------------|-----------------|----------------------------------------------------------------------------------------------|------------------------------------------------------|-------------|
| 2010-11   | --         | --              | --                                                                                           | --                                                   | --          |
| 2011-12   | --         | --              | --                                                                                           | --                                                   | --          |
| 2012-13   | --         | --              | --                                                                                           | --                                                   | --          |
| 2013-14   | --         | --              | --                                                                                           | --                                                   | --          |
| 2014-15   | --         | --              | --                                                                                           | --                                                   | --          |
| 2015-16   | --         | --              | --                                                                                           | --                                                   | --          |
| 2016-17   | --         | --              | --                                                                                           | --                                                   | --          |
| 2017-18   | --         | --              | --                                                                                           | --                                                   | --          |
| 2018-19   | --         | --              | --                                                                                           | --                                                   | --          |
| 2019-20   | --         | --              | --                                                                                           | --                                                   | --          |
| 2020-21   | --         | --              | --                                                                                           | --                                                   | --          |
| 2021-22   | xG v2 fit (S8), shrinkage K (S27), carryover w (S27), constants v2/v5/v7/v8 | -- | --                                                                           | --                                                   | DISCOVERY   |
| 2022-23   | xG v2 fit (S8), shrinkage K (S27), carryover w (S27); engine priced (S41/S50) | S42/S44: ML LL 0.6594 vs Pin 0.6568; A1 0.448; S52 8 regimes | Fit-season; LL, Brier, A1, reliability, calibration, regime tests all computed | --                       | DISCOVERY   |
| 2023-24   | --         | S42/S44: ML LL 0.6646 vs Pin 0.6567; A1 -0.051. Totals LL 0.7004 vs 0.6942. S45 calibration. S52 16 regimes, no BH survivors. | S48-ML-R6 A1, 99 picks evaluated; S50 1,312 games re-priced. B-01 3-way. | EV2 price-rule confirmation (consumed 2026-09-30) | CONSUMED    |
| 2024-25   | --         | --              | EV2 price-rule confirmation consumed it (2026-09-30); no engine prices exist; outcomes seen in aggregate | --                                  | PARTIAL     |
| 2025-26   | --         | --              | --                                                                                           | 2026-27 is the current season; 2025-26 actuals are final but no engine work done | PROSPECTIVE |
| 2026-27   | --         | --              | --                                                                                           | Current season                                       | PROSPECTIVE |
