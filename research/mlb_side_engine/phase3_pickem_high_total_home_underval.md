# MLB Side Engine -- Phase 3: Pick'em + High-Total Home Undervaluation

Generated: 2026-04-10 16:49

```
Rolling 3-start ERA coverage: home=6544/9500, away=8652/9500
======================================================================
PHASE 1: CANDIDATE SUBSETS A-D
======================================================================

### Candidate Subsets -- OOS 2025
                label    N actual_HW% market_HW% model_HW%   edge  brier_d  ROI% ROI_2025  N_2025
  A: Home undervalued 1115      0.571      0.524     0.576  0.048 -0.00393 +4.4%    +4.4%    1115
   B: Pick'em+home_uv  251      0.566      0.501     0.554  0.065 -0.00878 +8.3%    +8.3%     251
C: High-total+home_uv  185      0.492      0.487     0.544  0.004 +0.00158 -4.3%    -4.3%     185
D: Pick'em+HT+home_uv   41      0.561      0.500     0.548  0.061 -0.00683 +7.7%    +7.7%      41
        Baseline: All 2397      0.544      0.532     0.527  0.012 -0.00197 -1.8%    -1.8%    2397
        Pick'em (all)  500      0.524      0.502     0.501  0.022 -0.00401 -0.1%    -0.1%     500
     High-total (all)  381      0.472      0.491     0.493 -0.019 -0.00424 -7.1%    -7.1%     381

### Candidate Subsets -- Val+OOS 2024-25
                label    N actual_HW% market_HW% model_HW%   edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
  A: Home undervalued 2264      0.564      0.525     0.574  0.039 -0.00290  +2.8%    +1.3%    1149    +4.4%    1115
   B: Pick'em+home_uv  470      0.564      0.500     0.550  0.064 -0.00541  +8.0%    +7.7%     219    +8.3%     251
C: High-total+home_uv  313      0.505      0.493     0.544  0.012 -0.00161  -0.8%    +4.2%     128    -4.3%     185
D: Pick'em+HT+home_uv   62      0.597      0.498     0.548  0.099 -0.01133 +15.0%   +29.1%      21    +7.7%      41
        Baseline: All 4789      0.534      0.531     0.527  0.002 -0.00161  -3.7%    -5.6%    2392    -1.8%    2397
        Pick'em (all)  971      0.503      0.501     0.498  0.001 -0.00294  -4.1%    -8.4%     471    -0.1%     500
     High-total (all)  641      0.476      0.494     0.494 -0.018 -0.00512  -6.3%    -5.0%     260    -7.1%     381

======================================================================
PHASE 2: THRESHOLD LADDER
======================================================================

--- Pick'em+home_uv ---

### Pick'em+home_uv -- OOS
          label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2025  N_2025
   All(>=0.000) 251      0.566      0.501     0.554 0.065 -0.00878  +8.3%    +8.3%     251
Top30%(>=0.070)  76      0.684      0.500     0.602 0.184 -0.02582 +31.2%   +31.2%      76
Top20%(>=0.083)  51      0.686      0.499     0.614 0.187 -0.02823 +31.8%   +31.8%      51
Top10%(>=0.109)  26      0.654      0.504     0.637 0.150 -0.02369 +24.7%   +24.7%      26
 Top5%(>=0.125)  13      0.769      0.500     0.649 0.270 -0.05412 +47.6%   +47.6%      13

### Pick'em+home_uv -- V+O
          label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
   All(>=0.000) 470      0.564      0.500     0.550 0.064 -0.00541  +8.0%    +7.7%     219    +8.3%     251
Top30%(>=0.066) 141      0.617      0.499     0.597 0.118 -0.01336 +18.2%    +0.6%      55   +29.5%      86
Top20%(>=0.080)  94      0.628      0.498     0.609 0.130 -0.01583 +20.2%    +8.5%      37   +27.8%      57
Top10%(>=0.104)  47      0.596      0.501     0.631 0.095 -0.00932 +13.7%    +6.8%      16   +17.3%      31
 Top5%(>=0.125)  24      0.667      0.500     0.646 0.167 -0.02609 +27.6%                0   +41.1%      15

--- High-total+home_uv ---

### High-total+home_uv -- OOS
          label   N actual_HW% market_HW% model_HW%   edge  brier_d   ROI% ROI_2025  N_2025
   All(>=0.000) 185      0.492      0.487     0.544  0.004 +0.00158  -4.3%    -4.3%     185
Top30%(>=0.073)  56      0.536      0.486     0.607  0.050 +0.00655 +11.0%   +11.0%      56
Top20%(>=0.100)  37      0.432      0.468     0.608 -0.036 +0.02368  -8.7%    -8.7%      37
Top10%(>=0.125)  19      0.474      0.445     0.610  0.029 +0.01319 +11.1%   +11.1%      19
 Top5%(>=0.142)  10      0.500      0.410     0.605  0.090 -0.00028 +32.9%   +32.9%      10

### High-total+home_uv -- V+O
          label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
   All(>=0.000) 313      0.505      0.493     0.544 0.012 -0.00161  -0.8%    +4.2%     128    -4.3%     185
Top30%(>=0.070)  94      0.574      0.487     0.596 0.088 -0.00387 +18.2%   +30.9%      36   +10.3%      58
Top20%(>=0.087)  63      0.524      0.480     0.605 0.044 +0.00516  +8.7%   +27.8%      19    +0.5%      44
Top10%(>=0.115)  32      0.500      0.459     0.607 0.041 +0.00735 +10.0%                0    +8.5%      26
 Top5%(>=0.132)  16      0.562      0.443     0.616 0.120 -0.00977 +34.5%                0   +27.5%      15

--- Pick'em+HT+home_uv ---

### Pick'em+HT+home_uv -- OOS
          label  N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2025  N_2025
   All(>=0.000) 41      0.561      0.500     0.548 0.061 -0.00683  +7.7%    +7.7%      41
Top30%(>=0.064) 13      0.692      0.491     0.587 0.202 -0.02262 +35.7%   +35.7%      13
Top20%(>=0.076)  9      0.556      0.492     0.600 0.063 -0.00207  +8.9%                0
Top10%(>=0.116)  5      0.600      0.496     0.620 0.104 -0.01319 +18.1%                0
 Top5%(>=0.125)  3      0.667      0.494     0.622 0.172 -0.02984 +30.8%                0

### Pick'em+HT+home_uv -- V+O
          label  N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
   All(>=0.000) 62      0.597      0.498     0.548 0.099 -0.01133 +15.0%   +29.1%      21    +7.7%      41
Top30%(>=0.075) 19      0.684      0.492     0.594 0.192 -0.02470 +33.0%                0   +24.2%      11
Top20%(>=0.087) 13      0.615      0.493     0.604 0.123 -0.01408 +19.4%                0                0
Top10%(>=0.115)  7      0.571      0.496     0.619 0.076 -0.00702 +11.4%                0                0
 Top5%(>=0.125)  4      0.750      0.497     0.624 0.253 -0.04958 +45.4%                0                0

======================================================================
PHASE 3: OVERLAY TESTS
======================================================================

==================================================
Context: Pick'em+home_uv (N=470)
==================================================

### A) SP Quality (Pick'em+home_uv)
    label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
HomeSPadv 105      0.533      0.502     0.580 0.031 +0.00056  +1.6%   -13.1%      50   +15.0%      55
  Neutral 310      0.565      0.500     0.543 0.065 -0.00675  +8.2%   +13.8%     147    +3.3%     163
AwaySPadv  55      0.618      0.498     0.533 0.120 -0.00926 +19.1%   +14.5%      22   +22.1%      33

  B) SP Recent Form (N with data: 301)

### B) SP Form (Pick'em+home_uv)
         label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
   HomeFormAdv  87      0.575      0.501     0.550 0.074 -0.00757 +10.0%   +13.8%      42    +6.5%      45
       Neutral 112      0.518      0.502     0.548 0.016 -0.00079  -1.2%    -3.0%      61    +1.0%      51
   AwayFormAdv 102      0.647      0.500     0.552 0.147 -0.01621 +24.0%   +37.0%      42   +14.9%      60
 HomeSP<3.5ERA 103      0.553      0.501     0.547 0.052 -0.00104  +5.8%    +7.1%      59    +4.0%      44
HomeSP>=3.5ERA 198      0.591      0.501     0.552 0.090 -0.01158 +13.1%   +17.9%      86    +9.5%     112

### C) Bullpen (Pick'em+home_uv)
    label   N actual_HW% market_HW% model_HW%   edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
HomeBPadv   6      0.667      0.503     0.615  0.163 -0.03142 +23.8%                0                0
  Neutral 462      0.563      0.500     0.549  0.063 -0.00528  +7.9%    +7.4%     218    +8.4%     244
AwayBPadv   2      0.500      0.505     0.550 -0.005 +0.04232  -8.3%                0                0

### D) Rest (Pick'em+home_uv)
       label   N actual_HW% market_HW% model_HW%  edge  brier_d  ROI% ROI_2024  N_2024 ROI_2025  N_2025
HomeMoreRest  11      0.545      0.497     0.525 0.048 +0.00876 +5.3%                0                0
   EqualRest 444      0.565      0.500     0.551 0.065 -0.00598 +8.2%    +7.0%     206    +9.3%     238
AwayMoreRest  15      0.533      0.496     0.547 0.038 +0.00086 +3.8%                0                0

==================================================
Context: High-total+home_uv (N=313)
==================================================

### A) SP Quality (High-total+home_uv)
    label   N actual_HW% market_HW% model_HW%   edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
HomeSPadv 103      0.563      0.552     0.626  0.011 +0.00210  -0.4%    -0.6%      41    -0.2%      62
  Neutral 163      0.509      0.488     0.531  0.021 -0.00311  +2.0%    +5.2%      77    -0.9%      86
AwaySPadv  47      0.362      0.380     0.413 -0.019 -0.00457 -11.5%   +16.5%      10   -19.0%      37

  B) SP Recent Form (N with data: 198)

### B) SP Form (High-total+home_uv)
         label   N actual_HW% market_HW% model_HW%  edge  brier_d  ROI% ROI_2024  N_2024 ROI_2025  N_2025
   HomeFormAdv  63      0.556      0.530     0.573 0.025 -0.00204 +2.5%    -7.8%      29   +11.2%      34
       Neutral  66      0.561      0.507     0.557 0.054 -0.00688 +7.7%   +12.8%      35    +2.0%      31
   AwayFormAdv  69      0.493      0.458     0.503 0.034 -0.00188 +3.1%   +12.7%      28    -3.5%      41
 HomeSP<3.5ERA  56      0.554      0.518     0.559 0.036 +0.00121 +3.9%   +15.1%      30    -9.0%      26
HomeSP>=3.5ERA 142      0.528      0.489     0.537 0.039 -0.00549 +4.7%    +2.0%      62    +6.7%      80

### C) Bullpen (High-total+home_uv)
    label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
  Neutral 305      0.505      0.495     0.547 0.010 -0.00236  -1.4%    +2.3%     121    -3.8%     184
AwayBPadv   8      0.500      0.421     0.456 0.079 +0.02683 +20.2%                0                0

### D) Rest (High-total+home_uv)
       label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
HomeMoreRest   9      0.778      0.476     0.516 0.302 -0.01193 +57.3%                0                0
   EqualRest 289      0.495      0.492     0.543 0.003 -0.00086  -2.8%    -0.7%     116    -4.2%     173
AwayMoreRest  15      0.533      0.517     0.591 0.016 -0.00985  +2.7%                0                0

======================================================================
PHASE 4: INTERACTION TESTS
======================================================================

### Interactions (V+O 2024-25)
             label   N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025
  Pk+HUV+HomeSPadv 105      0.533      0.502     0.580 0.031 +0.00056  +1.6%   -13.1%      50   +15.0%      55
  HT+HUV+HomeSPadv 103      0.563      0.552     0.626 0.011 +0.00210  -0.4%    -0.6%      41    -0.2%      62
  Pk+HUV+HomeBPadv   6      0.667      0.503     0.615 0.163 -0.03142 +23.8%                0                0
HT+HUV+HSPform<3.5  63      0.524      0.513     0.557 0.010 +0.00168  -0.0%   +15.7%      34   -18.5%      29
Pk+HUV+HSPform<3.5 108      0.546      0.501     0.547 0.045 -0.00107  +4.5%    +6.8%      61    +1.6%      47

### Interactions OOS (2025)
           label  N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2025  N_2025
Pk+HUV+HomeSPadv 55      0.600      0.502     0.584 0.098 -0.00939 +15.0%   +15.0%      55
HT+HUV+HomeSPadv 62      0.581      0.552     0.636 0.028 +0.01126  -0.2%    -0.2%      62

======================================================================
PHASE 5: DIRECTIONAL ROBUSTNESS
======================================================================

### Away-Undervalued Analogs (V+O)
           label    N actual_AW% market_AW% model_AW%   edge  brier_d  ROI% ROI_2024  N_2024 ROI_2025  N_2025
   Away_uv (all) 2525      0.493      0.463     0.515  0.030 -0.00045 +2.3%    +4.4%    1243    +0.2%    1282
      Pk+away_uv  501      0.555      0.497     0.551  0.057 -0.00062 +6.4%   +13.5%     252    -0.8%     249
      HT+away_uv  328      0.552      0.505     0.554  0.047 -0.00847 +7.6%    +8.1%     132    +7.2%     196
   Pk+HT+away_uv   71      0.507      0.499     0.549  0.008 -0.00125 -3.2%   +10.7%      26   -11.2%      45
Pk+AUV+AwaySPadv  190      0.547      0.500     0.573  0.047 -0.00065 +4.4%   +11.1%      95    -2.3%      95
HT+AUV+AwaySPadv  151      0.556      0.566     0.627 -0.009 -0.00556 -3.9%    -5.1%      63    -3.0%      88

--- Home vs Away Direct Comparison ---
  Pick'em     : HOME-UV ROI=+8.0% edge=+0.064 N=470 | AWAY-UV ROI=+6.4% edge=+0.057 N=501
  High-total  : HOME-UV ROI=-0.8% edge=+0.012 N=313 | AWAY-UV ROI=+7.6% edge=+0.047 N=328
  All         : HOME-UV ROI=+2.8% edge=+0.039 N=2264 | AWAY-UV ROI=+2.3% edge=+0.030 N=2525

======================================================================
PHASE 6: INFORMATION GAIN SUMMARY
======================================================================

### Information Gain (V+O)
           label    N actual_HW% market_HW% model_HW%  edge  brier_d   ROI% ROI_2024  N_2024 ROI_2025  N_2025        flag
   Baseline: All 4789      0.534      0.531     0.527 0.002 -0.00161  -3.7%    -5.6%    2392    -1.8%    2397          OK
      A: Home_uv 2264      0.564      0.525     0.574 0.039 -0.00290  +2.8%    +1.3%    1149    +4.4%    1115          OK
       B: Pk+HUV  470      0.564      0.500     0.550 0.064 -0.00541  +8.0%    +7.7%     219    +8.3%     251          OK
       C: HT+HUV  313      0.505      0.493     0.544 0.012 -0.00161  -0.8%    +4.2%     128    -4.3%     185          OK
    D: Pk+HT+HUV   62      0.597      0.498     0.548 0.099 -0.01133 +15.0%   +29.1%      21    +7.7%      41 EXPLORATORY
Pk+HUV+HomeSPadv  105      0.533      0.502     0.580 0.031 +0.00056  +1.6%   -13.1%      50   +15.0%      55 EXPLORATORY
HT+HUV+HomeSPadv  103      0.563      0.552     0.626 0.011 +0.00210  -0.4%    -0.6%      41    -0.2%      62 EXPLORATORY

--- Calibration ---

  B: Pk+HUV:
    Q     N    Pred     Act     Gap
    0    94   0.503   0.596  +0.093
    1    94   0.525   0.532  +0.007
    2    94   0.545   0.521  -0.023
    3    94   0.568   0.532  -0.036
    4    94   0.611   0.638  +0.027

  C: HT+HUV:
    Q     N    Pred     Act     Gap
    0    63   0.398   0.333  -0.064
    1    62   0.492   0.581  +0.088
    2    63   0.546   0.460  -0.085
    3    62   0.599   0.516  -0.083
    4    63   0.687   0.635  -0.052

======================================================================
PHASE 7: VERDICT
======================================================================

--- Key Evidence ---
Pick'em+HUV (V+O): N=470, HW%=0.564, Mkt=0.500, edge=+0.064, ROI=+8.0%
High-total+HUV (V+O): N=313, HW%=0.505, Mkt=0.493, edge=+0.012, ROI=-0.8%
Pick'em+HUV (OOS): N=251, ROI=+8.3%
High-total+HUV (OOS): N=185, ROI=-4.3%

--- Per-Season ---
  Pk+HUV:
    2024: N=219, HW%=0.562, Mkt=0.499, edge=+0.062, ROI=+7.7%
    2025: N=251, HW%=0.566, Mkt=0.501, edge=+0.065, ROI=+8.3%
  HT+HUV:
    2024: N=128, HW%=0.523, Mkt=0.500, edge=+0.023, ROI=+4.2%
    2025: N=185, HW%=0.492, Mkt=0.487, edge=+0.004, ROI=-4.3%

--- Directional ---
Pk: HOME-UV=+8.0% N=470 | AWAY-UV=+6.4% N=501
HT: HOME-UV=-0.8% N=313 | AWAY-UV=+7.6% N=328

--- Criteria ---
  Stable edge (all seasons +): YES ([np.float64(7.718574237010787), np.float64(8.304207330712439)])
  N >= 200:                     YES
  Economics (ROI>2%):           YES
  Direction (home>away):        NO

VERDICT: NEAR MISS
Passing: 3/4
Failing: direction_confirmed

--- Reasoning ---
Pick'em+home-undervalued is the strongest signal.
  Actual HW% consistently exceeds market-implied in pick'em games where model favors home.
  Real-price ROI of +8.0% over 2 seasons (470 bets) survives vig.
  High-total+HUV shows negative ROI -- does NOT confirm as standalone signal.
  SP quality overlay strengthens signal but reduces N below 200 threshold.
  Bullpen overlay is mixed -- no consistent improvement.
```
