# Flyball*Wind Interaction Overlay on V2 Baseline (Revised)

flyball_wind_interaction is already a continuous feature in the V2 model.
This tests whether discretizing it as an overlay adds value beyond the model's use.
FW is an OVER amplifier (high flyball% in wind = more runs).
Q80 cutoff (2022-2024): >= 0.6900

Active: 1874 / 9490 (19.7%)

### Q80 cutoff (>= 0.6900)
Test                                            Season     N   OHit%  O_ROI_f |   UHit%  U_ROI_f
----------------------------------------------------------------------------------------------------
All games                                     2022-2024  7093   49.3%    -5.9% |   50.7%    -3.2%
  FW active (blind over)                      2022-2024  1420   50.0%    -4.5% |   50.0%    -4.6%
  FW inactive                                 2022-2024  5673   49.1%    -6.2% |   50.9%    -2.9%
  V2 over (edge>0.5, all)                     2022-2024  2893   52.2%    -0.3% |
    + FW active                               2022-2024   735   53.1%    +1.3% |
    + FW inactive                             2022-2024  2158   51.9%    -0.8% |

All games                                     2025 OOS  2397   47.9%    -8.5% |   52.1%    -0.6%
  FW active (blind over)                      2025 OOS   454   48.5%    -7.5% |   51.5%    -1.6%
  FW inactive                                 2025 OOS  1943   47.8%    -8.7% |   52.2%    -0.3%
  V2 over (edge>0.5, all)                     2025 OOS   915   47.0%   -10.4% |
    + FW active                               2025 OOS   225   49.1%    -6.3% |
    + FW inactive                             2025 OOS   690   46.3%   -11.7% |


## Flyball*Wind Verdict
OOS 2025 V2-over: FW-active over hit=49.1% ROI=-6.3%
OOS 2025 V2-over: FW-inactive over hit=46.3% ROI=-11.7%
All V2-over ROI: -10.4%
Delta (FW-active vs all): +4.0pp
Note: flyball_wind is already in V2 as continuous feature (coeff=+0.07).

Verdict: **SURVIVES**