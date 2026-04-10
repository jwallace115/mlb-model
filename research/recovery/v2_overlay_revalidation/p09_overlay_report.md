# P09 Overlay Revalidation on V2 Baseline (Revised)

P09 = avg(home_hh_r5, away_hh_r5) * park_factor_runs
Hard-hit: PIT-safe shift(1).rolling(5, min=3) computed in this script
Valid games: 7754
P09 fires when BELOW cutoff (low hard-hit = under lean)


Active: 430 / 7754 (5.5%)

### Old (<=31.7305)
Test                                            Season     N   UHit%  U_ROI_a  U_ROI_f |   OHit%  O_ROI_f
--------------------------------------------------------------------------------------------------------------
All games (baseline)                          2022-2024  5656   50.0%    -0.2%    -4.5% |   50.0%    -4.6%
  Overlay ACTIVE (blind under)                2022-2024   370   52.3%    +4.6%    -0.2% |   47.7%    -8.9%
  Overlay INACTIVE                            2022-2024  5286   49.9%    -0.5%    -4.8% |   50.1%    -4.3%
  V2 over (edge>0.5, all)                     2022-2024  2431                           |   52.6%    +0.4%
  V2 over MINUS overlay-active                2022-2024  2265                           |   52.6%    +0.4%
  COMBINED: active + edge<median              2022-2024   182   55.1%    +7.0%    +5.1% |

All games (baseline)                          2025 OOS  2098   52.6%    +4.4%    +0.4% |   47.4%    -9.5%
  Overlay ACTIVE (blind under)                2025 OOS    60   57.9%   +14.9%   +10.5% |   42.1%   -19.6%
  Overlay INACTIVE                            2025 OOS  2038   52.4%    +4.1%    +0.1% |   47.6%    -9.2%
  V2 over (edge>0.5, all)                     2025 OOS   819                           |   47.2%    -9.9%
  V2 over MINUS overlay-active                2025 OOS   799                           |   47.4%    -9.6%
  COMBINED: active + edge<median              2025 OOS    34   59.4%   +18.3%   +13.4% |


Active: 1372 / 7754 (17.7%)

### New Q20 (<=35.0674)
Test                                            Season     N   UHit%  U_ROI_a  U_ROI_f |   OHit%  O_ROI_f
--------------------------------------------------------------------------------------------------------------
All games (baseline)                          2022-2024  5656   50.0%    -0.2%    -4.5% |   50.0%    -4.6%
  Overlay ACTIVE (blind under)                2022-2024  1132   50.7%    +1.6%    -3.1% |   49.3%    -6.0%
  Overlay INACTIVE                            2022-2024  4524   49.8%    -0.7%    -4.9% |   50.2%    -4.2%
  V2 over (edge>0.5, all)                     2022-2024  2431                           |   52.6%    +0.4%
  V2 over MINUS overlay-active                2022-2024  1956                           |   52.5%    +0.2%
  COMBINED: active + edge<median              2022-2024   561   53.6%    +5.6%    +2.3% |

All games (baseline)                          2025 OOS  2098   52.6%    +4.4%    +0.4% |   47.4%    -9.5%
  Overlay ACTIVE (blind under)                2025 OOS   240   50.9%    -0.3%    -2.9% |   49.1%    -6.2%
  Overlay INACTIVE                            2025 OOS  1858   52.8%    +5.0%    +0.8% |   47.2%    -9.9%
  V2 over (edge>0.5, all)                     2025 OOS   819                           |   47.2%    -9.9%
  V2 over MINUS overlay-active                2025 OOS   727                           |   46.9%   -10.4%
  COMBINED: active + edge<median              2025 OOS   120   51.7%    +1.1%    -1.3% |


## P09 Verdict
OOS 2025 blind-under: active hit=50.9% ROI=-2.9%, inactive hit=52.8% ROI=+0.8%
All games blind-under ROI: +0.4%
Delta (active vs all): -3.3pp

Verdict: **COLLAPSES**