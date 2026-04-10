# S12 Overlay Revalidation on V2 Baseline (Revised)

S12 = avg(home_csw_r5, away_csw_r5) - 5 * avg(home_xfip, away_xfip)
CSW: PIT-safe shift(1).rolling(5) from pitcher_start_metrics_per_start.csv
Valid games: 8137
V2 Model_B mean edge = +0.43 (strong over bias, ~0 under signals at edge<-0.5)
Therefore testing S12 as standalone blind-under filter and V2-over contra-filter.


Active: 2687 / 8137 (33.0%)

### Old (>=8.4468)
Test                                            Season     N   UHit%  U_ROI_a  U_ROI_f |   OHit%  O_ROI_f
--------------------------------------------------------------------------------------------------------------
All games (baseline)                          2022-2024  6055   50.7%    +1.1%    -3.2% |   49.3%    -5.9%
  Overlay ACTIVE (blind under)                2022-2024  2009   50.2%    -0.2%    -4.1% |   49.8%    -4.9%
  Overlay INACTIVE                            2022-2024  4046   51.0%    +1.7%    -2.7% |   49.0%    -6.4%
  V2 over (edge>0.5, all)                     2022-2024  2550                           |   51.8%    -1.1%
  V2 over MINUS overlay-active                2022-2024  1525                           |   52.3%    -0.1%
  COMBINED: active + edge<median              2022-2024   840   51.2%    +1.0%    -2.2% |

All games (baseline)                          2025 OOS  2082   52.8%    +4.8%    +0.9% |   47.2%   -10.0%
  Overlay ACTIVE (blind under)                2025 OOS   678   54.9%    +8.3%    +4.9% |   45.1%   -14.0%
  Overlay INACTIVE                            2025 OOS  1404   51.8%    +3.1%    -1.1% |   48.2%    -8.0%
  V2 over (edge>0.5, all)                     2025 OOS   795                           |   46.0%   -12.3%
  V2 over MINUS overlay-active                2025 OOS   471                           |   47.5%    -9.2%
  COMBINED: active + edge<median              2025 OOS   280   56.0%    +9.9%    +6.9% |


Active: 1634 / 8137 (20.1%)

### New Q80 (>=9.8151)
Test                                            Season     N   UHit%  U_ROI_a  U_ROI_f |   OHit%  O_ROI_f
--------------------------------------------------------------------------------------------------------------
All games (baseline)                          2022-2024  6055   50.7%    +1.1%    -3.2% |   49.3%    -5.9%
  Overlay ACTIVE (blind under)                2022-2024  1211   50.0%    -0.2%    -4.6% |   50.0%    -4.5%
  Overlay INACTIVE                            2022-2024  4844   50.9%    +1.4%    -2.8% |   49.1%    -6.3%
  V2 over (edge>0.5, all)                     2022-2024  2550                           |   51.8%    -1.1%
  V2 over MINUS overlay-active                2022-2024  1911                           |   52.0%    -0.8%
  COMBINED: active + edge<median              2022-2024   476   50.1%    -0.5%    -4.3% |

All games (baseline)                          2025 OOS  2082   52.8%    +4.8%    +0.9% |   47.2%   -10.0%
  Overlay ACTIVE (blind under)                2025 OOS   423   54.3%    +7.5%    +3.7% |   45.7%   -12.8%
  Overlay INACTIVE                            2025 OOS  1659   52.5%    +4.1%    +0.1% |   47.5%    -9.2%
  V2 over (edge>0.5, all)                     2025 OOS   795                           |   46.0%   -12.3%
  V2 over MINUS overlay-active                2025 OOS   582                           |   46.9%   -10.4%
  COMBINED: active + edge<median              2025 OOS   165   53.8%    +4.8%    +2.6% |


## S12 Verdict
OOS 2025 blind-under: active hit=54.3% ROI=+3.7%, inactive hit=52.5% ROI=+0.1%
All games blind-under ROI: +0.9%
Delta (active vs all): +2.9pp

Verdict: **DIMINISHED**