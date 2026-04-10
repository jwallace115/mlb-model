# MLB Side Engine -- Phase 4: Pick'em Mechanism Audit

Generated: 2026-04-10 17:01

```
========================================================================
PHASE 4: PICK'EM MECHANISM AUDIT
========================================================================

Dataset: 9500 games | Train: 4711 | Val: 2392 | OOS: 2397
Model A coefficients (standardized):
  sp_xfip_diff                  : -0.2834
  wrc_diff                      : +0.2181
  bp_xfip_diff                  : -0.1314
  umpire_over_rate              : -0.0483
  rest_diff                     : -0.0460
  wind_factor_effective         : -0.0360
  temperature                   : +0.0341
  total_line                    : +0.0266
  park_factor_runs              : +0.0115

========================================================================
SECTION 1: PICK'EM SURVIVOR SUBSETS
========================================================================

Subset                                  N    HW%    Mkt    Mdl  Brier_M Brier_Mkt    Delta
------------------------------------------------------------------------------------------
A: All pick'em                        971  0.503  0.501  0.498  0.24782   0.25076 -0.00294
B: Pick'em + model home UV            470  0.564  0.500  0.550  0.24657   0.25198 -0.00541
C: Pick'em + top 50% |disagree|       485  0.534  0.501  0.495  0.24679   0.25086 -0.00406

Per-season: Pick'em + model home UV
  Season       N    HW%    Mkt    ROI%
  2024       219  0.562  0.499    +7.7%
  2025       251  0.566  0.501    +8.3%

========================================================================
SECTION 2: PRICE-ZONE DECOMPOSITION
========================================================================

Zone                          N    HW%    Mkt    Mdl  Brier_D    ROI%
------------------------------------------------------------------------
Home fav -110/-105          240  0.446  0.519  0.508 +0.00212    -5.9%
Slight home -105/-100       314  0.535  0.506  0.499 -0.00384    +5.9%
Slight away +100/+105       252  0.520  0.492  0.493 -0.00656   +18.2%
Away fav +105/+110          165  0.497  0.481  0.489 -0.00305   +11.9%

Per-season by zone:
  Home fav -110/-105:
    2024: N=  93, HW%=0.409, ROI=-3.5%
    2025: N= 147, HW%=0.469, ROI=-7.5%
  Slight home -105/-100:
    2024: N= 183, HW%=0.508, ROI=+13.9%
    2025: N= 131, HW%=0.573, ROI=-5.3%
  Slight away +100/+105:
    2024: N= 125, HW%=0.520, ROI=+23.7%
    2025: N= 127, HW%=0.520, ROI=+12.8%
  Away fav +105/+110:
    2024: N=  70, HW%=0.429, ROI=-1.3%
    2025: N=  95, HW%=0.547, ROI=+21.6%

========================================================================
SECTION 3: FEATURE ATTRIBUTION (DROP-COLUMN IMPORTANCE)
========================================================================

Baseline pick'em Brier delta (model - market): -0.002940
  Model Brier: 0.247817, Market Brier: 0.250757

Family                Brier w/o  Delta w/o     Change Verdict        
------------------------------------------------------------------------
Bullpen                0.250198  -0.000560  +0.002380 KEY DRIVER     
SP quality             0.248691  -0.002066  +0.000874 CONTRIBUTOR    
Offense                0.248310  -0.002447  +0.000493 CONTRIBUTOR    
Total line             0.247891  -0.002866  +0.000074 NEGLIGIBLE     
Park                   0.247795  -0.002962  -0.000022 NEGLIGIBLE     
Weather                0.247621  -0.003137  -0.000197 NEGLIGIBLE     
Rest                   0.247568  -0.003190  -0.000250 NEGLIGIBLE     
Umpire                 0.247568  -0.003190  -0.000250 NEGLIGIBLE     

Top contributing families: Bullpen, SP quality, Offense

========================================================================
SECTION 4: MARKET COMPRESSION TEST
========================================================================

Variance comparison within pick'em games:
  Model p_home variance:  0.004218 (std=0.0649)
  Market p_home variance: 0.000190 (std=0.0138)
  Ratio (model/market):   22.18x

  Model range: [0.313, 0.689]
  Market range: [0.476, 0.524]

Model confidence split within pick'em:
  Bucket                        N    HW%    Mkt    Mdl  Brier_D
-----------------------------------------------------------------
  High (|p-0.5|>0.04)         522  0.502  0.501  0.496 -0.00400
  Low (|p-0.5|<=0.04)         449  0.503  0.502  0.501 -0.00171

Calibration by model prediction quintile (pick'em games):
    Q     N   Pred  Actual     Gap
    0   195  0.407   0.451  +0.045
    1   194  0.464   0.428  -0.036
    2   194  0.499   0.510  +0.011
    3   194  0.533   0.541  +0.008
    4   194  0.588   0.582  -0.006

========================================================================
SECTION 5: CORRECTION-DIRECTION DECOMPOSITION
========================================================================

Subset                                  N    HW%    Mkt    Mdl  Brier_D    ROI%
--------------------------------------------------------------------------------
A) Home-undervalued (dis>0)           470  0.564  0.500  0.550 -0.00541    +8.0%
B) Away-undervalued (dis<0)           501  0.445  0.503  0.449 -0.00062    +6.4%
C) Top |disagree| (>median)           485  0.534  0.501  0.495 -0.00406    +9.2%
D) Bottom |disagree| (<=med)          486  0.471  0.501  0.501 -0.00182    +5.2%

Per-season: Home-UV vs Away-UV within pick'em
  2024: HomeUV N=219, HW%=0.562, ROI=+7.7% | AwayUV N=252, AW%=0.591, ROI=+13.5%
  2025: HomeUV N=251, HW%=0.566, ROI=+8.3% | AwayUV N=249, AW%=0.518, ROI=-0.8%

Key question: Direction or Magnitude?
  DIRECTION dominates: home-undervalued drives the edge, away-UV does not
  Home-UV Brier delta: -0.005413, Away-UV: -0.000621, Top |dis|: -0.004065, Bottom |dis|: -0.001818

========================================================================
SECTION 6: FILTER CANDIDATE SEARCH
========================================================================

Base population: Pick'em + model undervaluation, N=470

  Filter: Offense (wrc_diff), median=0.40
  Half                          N    HW%    Mkt  Brier_D    ROI%    2024    2025
  --------------------------------------------------------------------------------
  Low half                    238  0.546  0.499 -0.00115    +4.7%   +1.0%   +8.3%
  High half                   232  0.582  0.501 -0.00979   +11.4%  +15.3%   +8.3%

  Filter: Weather (temperature), median=72.00
  Half                          N    HW%    Mkt  Brier_D    ROI%    2024    2025
  --------------------------------------------------------------------------------
  Low half                    278  0.561  0.500 -0.00696    +7.5%   +5.1%   +9.5%
  High half                   192  0.568  0.501 -0.00317    +8.7%  +11.1%   +6.4%

  Filter: SP quality (sp_xfip_diff), median=-0.12
  Half                          N    HW%    Mkt  Brier_D    ROI%    2024    2025
  --------------------------------------------------------------------------------
  Low half                    235  0.570  0.502 -0.00674    +8.9%   +5.0%  +12.4%
  High half                   235  0.557  0.499 -0.00409    +7.2%  +10.5%   +4.4%

  Filter: Bullpen (bp_xfip_diff), median=-0.01
  Half                          N    HW%    Mkt  Brier_D    ROI%    2024    2025
  --------------------------------------------------------------------------------
  Low half                    237  0.586  0.501 -0.00852   +11.8%   +9.0%  +13.8%
  High half                   233  0.541  0.499 -0.00226    +4.2%   +6.7%   +1.4%

--- Best Filter Candidates (N>=100, stable across seasons, ROI>3%) ---
  Bullpen Low half: N=237, ROI=+11.8%, 2024=+9.0%, 2025=+13.8%
  Offense High half: N=232, ROI=+11.4%, 2024=+15.3%, 2025=+8.3%
  SP quality Low half: N=235, ROI=+8.9%, 2024=+5.0%, 2025=+12.4%
  Weather High half: N=192, ROI=+8.7%, 2024=+11.1%, 2025=+6.4%
  Weather Low half: N=278, ROI=+7.5%, 2024=+5.1%, 2025=+9.5%
  SP quality High half: N=235, ROI=+7.2%, 2024=+10.5%, 2025=+4.4%
  Offense Low half: N=238, ROI=+4.7%, 2024=+1.0%, 2025=+8.3%
  Bullpen High half: N=233, ROI=+4.2%, 2024=+6.7%, 2025=+1.4%

========================================================================
SECTION 7: DEPLOYABILITY ASSESSMENT
========================================================================

Object                                            N    ROI%    2024    2025 Status            
----------------------------------------------------------------------------------------------------
Pick'em + Home UV (base signal)                 470   +8.0%   +7.7%   +8.3% SHADOW-ONLY       
Pick'em + Away UV (mirror signal)               501   +6.4%  +13.5%   -0.8% INFRASTRUCTURE    
Pick'em + Smart direction (all)                 971   +7.2%  +10.8%   +3.8% SHADOW-ONLY       
Pick'em + Top 50% |disagree| + smart            485   +9.2%   +4.8%  +13.0% SHADOW-ONLY       
Pick'em + HomeUV + Bullpen Low half             237  +11.8%   +9.0%  +13.8% SHADOW-ONLY       

Deployability legend:
  DEPLOYABLE   = Live betting ready (none qualify yet — need live season)
  SHADOW-ONLY  = Log picks in 2026 shadow, do not bet real money
  INFRASTRUCTURE = Feeds into future model versions
  DEAD         = Negative expected value, discard

========================================================================
FINAL SUMMARY & EVALUATION
========================================================================

1. PRICE ZONE RESULTS:
   Home fav -110/-105: N=240, HW%=0.446, Brier delta=+0.00212, ROI=-5.9%
   Slight home -105/-100: N=314, HW%=0.535, Brier delta=-0.00384, ROI=+5.9%
   Slight away +100/+105: N=252, HW%=0.520, Brier delta=-0.00656, ROI=+18.2%
   Away fav +105/+110: N=165, HW%=0.497, Brier delta=-0.00305, ROI=+11.9%

2. FEATURE ATTRIBUTION RANKING:
   1. Bullpen         delta change=+0.002380
   2. SP quality      delta change=+0.000874
   3. Offense         delta change=+0.000493
   4. Total line      delta change=+0.000074
   5. Park            delta change=-0.000022
   6. Weather         delta change=-0.000197
   7. Rest            delta change=-0.000250
   8. Umpire          delta change=-0.000250

3. MARKET COMPRESSION FINDING:
   Model variance in pick'em: 0.004218 (std=0.0649)
   Market variance in pick'em: 0.000190 (std=0.0138)
   Model is 22.2x wider than market in pick'em games.
   Compression effect: YES

4. DIRECTION vs MAGNITUDE:
   Home-UV Brier delta: -0.005413
   Away-UV Brier delta: -0.000621
   Top |disagree| delta: -0.004065
   Bottom |disagree| delta: -0.001818
   Answer: DIRECTION (HOME) — home-undervaluation drives the edge

5. BEST FILTER CANDIDATE:
   Bullpen Low half: N=237, ROI=+11.8%, stable=True

6. DEPLOYABILITY VERDICT:
   4 object(s) qualify for SHADOW-ONLY:
     - Pick'em + Home UV (base signal) (ROI=+8.0%)
     - Pick'em + Smart direction (all) (ROI=+7.2%)
     - Pick'em + Top 50% |disagree| + smart (ROI=+9.2%)
     - Pick'em + HomeUV + Bullpen Low half (ROI=+11.8%)
   None qualify for DEPLOYABLE — need live 2026 season shadow validation

--- FOUR EVALUATION QUESTIONS ---

Q1: Is the pick'em edge real or a statistical artifact?

    Pick'em+HomeUV: HW%=0.564, N=470, SE=0.0229, z-score=2.79
    LIKELY REAL — z=2.79 exceeds 2.0 threshold, plus stable across 2024/2025

Q2: What mechanism creates the edge?
    Primary driver: Bullpen (delta change=+0.002380)
    The model spreads its predictions wider than the market (22.2x variance).
    In pick'em games, the market compresses all prices near 0.500.
    When the model's feature-driven estimate disagrees with this compression,
    it captures real directional information that the market's tight pricing misses.

Q3: Can it be deployed profitably?
    Not yet. Best signal (Pick'em+HomeUV) shows ROI=+8.0% over V+O,
    but needs live 2026 shadow validation before real-money deployment.
    The ~235-bet-per-season volume is sufficient for evaluation within one season.

Q4: What should happen next?
    1. SHADOW: Log pick'em+UV picks daily in 2026 shadow pipeline
    2. THRESHOLD: Monitor top-30% disagreement tier for acceleration
    3. EVALUATE: After 200+ graded picks, run significance test
    4. DEPLOY or KILL: If z>2.0 and ROI>3% after shadow, promote to live
```
