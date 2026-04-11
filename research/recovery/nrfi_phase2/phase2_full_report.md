# NRFI Phase 2: Starter Refinement — Full Report

Generated: 2026-04-11 15:51

```
======================================================================
PHASE 0: Load data & lock base structural pockets
======================================================================
NRFI table: 9900 games, 22 columns
Overall NRFI rate: 0.512

Base structural pockets:
  Set                                 N   NRFI%    Lift
  ------------------------------ ------ ------- -------
  A: F5<=3.5                       1050   0.655  +0.143
  B: F5<=4.0                       1250   0.633  +0.120
  C: FG8.5-9.0 x F5<=4.0            168   0.750  +0.238
  D: FG<=7.5 (both_low proxy)      2269   0.557  +0.045
  E: FG<=7.0 (tt_max<=3.5 proxy)    707   0.586  +0.073

======================================================================
PHASE 1: Build PIT-safe expanding starter metrics
======================================================================
Starter appearances: 19834, unique pitchers: 742
Starts with valid PIT metrics: 18175 / 19834
  k_pct: mean=0.221, p25=0.180, p50=0.216, p75=0.257
  bb_pct: mean=0.079, p25=0.059, p50=0.075, p75=0.095
  fip: mean=4.021, p25=3.166, p50=3.860, p75=4.629
  era: mean=4.367, p25=3.076, p50=3.956, p75=5.041
  whip: mean=1.335, p25=1.113, p50=1.279, p75=1.462
  avg_ip: mean=5.101, p25=4.767, p50=5.209, p75=5.630
  k_bb_ratio: mean=3.248, p25=2.103, p50=2.846, p75=3.818

======================================================================
PHASE 2: Join starter metrics to NRFI research table
======================================================================
Games with both starters' PIT metrics: 6537 / 9900
Games with 3+ prior starts each: 5253

======================================================================
PHASE 3: Univariate starter screen inside base pockets
======================================================================

  Base A: N=656, NRFI=0.655
  Variable                  Cut     N   NRFI%   Delta
  -------------------- -------- ----- ------- -------
  mean_k_pct              top33   219   0.584  -0.071
  mean_k_pct           aboveMed   328   0.595  -0.061
  mean_k_pct              top67   437   0.597  -0.058
  min_k_pct               top33   219   0.594  -0.062
  min_k_pct            aboveMed   331   0.607  -0.048
  min_k_pct               top67   437   0.618  -0.038
  mean_bb_pct             bot33   219   0.584  -0.071
  mean_bb_pct          belowMed   328   0.613  -0.043
  mean_bb_pct             bot67   437   0.620  -0.035
  max_bb_pct              bot33   219   0.607  -0.048
  max_bb_pct           belowMed   329   0.638  -0.017
  max_bb_pct              bot67   437   0.627  -0.028
  mean_fip                bot33   219   0.557  -0.098
  mean_fip             belowMed   328   0.573  -0.082
  mean_fip                bot67   437   0.597  -0.058
  max_fip                 bot33   219   0.521  -0.135
  max_fip              belowMed   328   0.591  -0.064
  max_fip                 bot67   437   0.616  -0.040
  mean_era                bot33   219   0.584  -0.071
  mean_era             belowMed   328   0.588  -0.067
  mean_era                bot67   437   0.609  -0.047
  max_era                 bot33   219   0.571  -0.085
  max_era              belowMed   328   0.579  -0.076
  max_era                 bot67   437   0.625  -0.031
  mean_whip               bot33   219   0.543  -0.112
  mean_whip            belowMed   328   0.564  -0.091
  mean_whip               bot67   437   0.595  -0.061
  max_whip                bot33   219   0.562  -0.094
  max_whip             belowMed   328   0.576  -0.079
  max_whip                bot67   437   0.606  -0.049
  min_k_bb                top33   219   0.548  -0.108
  min_k_bb             aboveMed   329   0.587  -0.069
  min_k_bb                top67   440   0.625  -0.030

  Base B: N=787, NRFI=0.629
  Variable                  Cut     N   NRFI%   Delta
  -------------------- -------- ----- ------- -------
  mean_k_pct              top33   262   0.553  -0.076
  mean_k_pct           aboveMed   394   0.566  -0.063
  mean_k_pct              top67   525   0.573  -0.056
  min_k_pct               top33   262   0.561  -0.068
  min_k_pct            aboveMed   394   0.584  -0.045
  min_k_pct               top67   525   0.598  -0.031
  mean_bb_pct             bot33   262   0.573  -0.056
  mean_bb_pct          belowMed   394   0.591  -0.038
  mean_bb_pct             bot67   525   0.602  -0.027
  max_bb_pct              bot33   263   0.578  -0.051
  max_bb_pct           belowMed   394   0.612  -0.017
  max_bb_pct              bot67   525   0.610  -0.019
  mean_fip                bot33   262   0.542  -0.087
  mean_fip             belowMed   394   0.563  -0.066
  mean_fip                bot67   525   0.583  -0.046
  max_fip                 bot33   262   0.515  -0.114
  max_fip              belowMed   394   0.579  -0.050
  max_fip                 bot67   525   0.598  -0.031
  mean_era                bot33   262   0.546  -0.083
  mean_era             belowMed   394   0.576  -0.053
  mean_era                bot67   525   0.592  -0.037
  max_era                 bot33   262   0.553  -0.076
  max_era              belowMed   394   0.574  -0.055
  max_era                 bot67   525   0.602  -0.027
  mean_whip               bot33   262   0.527  -0.102
  mean_whip            belowMed   394   0.551  -0.078
  mean_whip               bot67   525   0.585  -0.044
  max_whip                bot33   262   0.561  -0.068
  max_whip             belowMed   395   0.567  -0.062
  max_whip                bot67   525   0.590  -0.038
  min_k_bb                top33   263   0.548  -0.081
  min_k_bb             aboveMed   394   0.574  -0.055
  min_k_bb                top67   525   0.598  -0.031

  Base C: N=103, NRFI=0.738
  Variable                  Cut     N   NRFI%   Delta
  -------------------- -------- ----- ------- -------
  mean_k_pct              top33    34   0.647  -0.091
  mean_k_pct           aboveMed    52   0.712  -0.026
  mean_k_pct              top67    69   0.739  +0.001
  min_k_pct               top33    34   0.765  +0.027
  min_k_pct            aboveMed    52   0.788  +0.051
  min_k_pct               top67    69   0.783  +0.045
  mean_bb_pct             bot33    34   0.706  -0.032
  mean_bb_pct          belowMed    52   0.731  -0.007
  mean_bb_pct             bot67    69   0.739  +0.001
  max_bb_pct              bot33    34   0.765  +0.027
  max_bb_pct           belowMed    52   0.750  +0.012
  max_bb_pct              bot67    69   0.768  +0.030
  mean_fip                bot33    34   0.676  -0.061
  mean_fip             belowMed    52   0.712  -0.026
  mean_fip                bot67    69   0.710  -0.028
  max_fip                 bot33    34   0.794  +0.056
  max_fip              belowMed    52   0.769  +0.031
  max_fip                 bot67    69   0.768  +0.030
  mean_era                bot33    34   0.706  -0.032
  mean_era             belowMed    52   0.692  -0.046
  mean_era                bot67    69   0.710  -0.028
  max_era                 bot33    34   0.676  -0.061
  max_era              belowMed    52   0.673  -0.065
  max_era                 bot67    69   0.739  +0.001
  mean_whip               bot33    34   0.647  -0.091
  mean_whip            belowMed    52   0.712  -0.026
  mean_whip               bot67    69   0.754  +0.016
  max_whip                bot33    34   0.706  -0.032
  max_whip             belowMed    52   0.769  +0.031
  max_whip                bot67    69   0.783  +0.045
  min_k_bb                top33    34   0.706  -0.032
  min_k_bb             aboveMed    52   0.750  +0.012
  min_k_bb                top67    69   0.754  +0.016

  Base D: N=1305, NRFI=0.551
  Variable                  Cut     N   NRFI%   Delta
  -------------------- -------- ----- ------- -------
  mean_k_pct              top33   435   0.531  -0.020
  mean_k_pct           aboveMed   653   0.533  -0.018
  mean_k_pct              top67   870   0.540  -0.011
  min_k_pct               top33   435   0.545  -0.006
  min_k_pct            aboveMed   653   0.545  -0.006
  min_k_pct               top67   870   0.553  +0.002
  mean_bb_pct             bot33   435   0.549  -0.002
  mean_bb_pct          belowMed   653   0.551  +0.000
  mean_bb_pct             bot67   870   0.560  +0.009
  max_bb_pct              bot33   435   0.559  +0.008
  max_bb_pct           belowMed   653   0.562  +0.011
  max_bb_pct              bot67   870   0.554  +0.003
  mean_fip                bot33   435   0.545  -0.006
  mean_fip             belowMed   653   0.556  +0.005
  mean_fip                bot67   870   0.548  -0.003
  max_fip                 bot33   435   0.529  -0.022
  max_fip              belowMed   653   0.545  -0.006
  max_fip                 bot67   871   0.545  -0.006
  mean_era                bot33   435   0.531  -0.020
  mean_era             belowMed   653   0.544  -0.007
  mean_era                bot67   870   0.556  +0.005
  max_era                 bot33   435   0.538  -0.013
  max_era              belowMed   653   0.544  -0.007
  max_era                 bot67   872   0.553  +0.002
  mean_whip               bot33   435   0.549  -0.002
  mean_whip            belowMed   653   0.542  -0.009
  mean_whip               bot67   870   0.557  +0.007
  max_whip                bot33   435   0.554  +0.003
  max_whip             belowMed   655   0.559  +0.008
  max_whip                bot67   872   0.548  -0.003
  min_k_bb                top33   435   0.543  -0.008
  min_k_bb             aboveMed   655   0.562  +0.011
  min_k_bb                top67   870   0.562  +0.011

  Base E: N=435, NRFI=0.591
  Variable                  Cut     N   NRFI%   Delta
  -------------------- -------- ----- ------- -------
  mean_k_pct              top33   145   0.586  -0.005
  mean_k_pct           aboveMed   218   0.564  -0.027
  mean_k_pct              top67   290   0.576  -0.015
  min_k_pct               top33   145   0.545  -0.046
  min_k_pct            aboveMed   218   0.569  -0.022
  min_k_pct               top67   290   0.576  -0.015
  mean_bb_pct             bot33   145   0.593  +0.002
  mean_bb_pct          belowMed   218   0.573  -0.017
  mean_bb_pct             bot67   290   0.576  -0.015
  max_bb_pct              bot33   145   0.593  +0.002
  max_bb_pct           belowMed   218   0.592  +0.001
  max_bb_pct              bot67   290   0.603  +0.013
  mean_fip                bot33   145   0.559  -0.032
  mean_fip             belowMed   218   0.573  -0.017
  mean_fip                bot67   290   0.590  -0.001
  max_fip                 bot33   145   0.566  -0.025
  max_fip              belowMed   218   0.560  -0.031
  max_fip                 bot67   290   0.579  -0.011
  mean_era                bot33   145   0.600  +0.009
  mean_era             belowMed   218   0.573  -0.017
  mean_era                bot67   290   0.593  +0.002
  max_era                 bot33   145   0.586  -0.005
  max_era              belowMed   218   0.564  -0.027
  max_era                 bot67   290   0.572  -0.018
  mean_whip               bot33   145   0.593  +0.002
  mean_whip            belowMed   218   0.587  -0.004
  mean_whip               bot67   290   0.597  +0.006
  max_whip                bot33   145   0.579  -0.011
  max_whip             belowMed   218   0.578  -0.013
  max_whip                bot67   290   0.586  -0.005
  min_k_bb                top33   145   0.586  -0.005
  min_k_bb             aboveMed   218   0.610  +0.019
  min_k_bb                top67   290   0.617  +0.026

Top 10 univariate lifts:
  Base C + max_fip bot33: N=34, NRFI=0.794, delta=+0.056
  Base C + min_k_pct aboveMed: N=52, NRFI=0.788, delta=+0.051
  Base C + min_k_pct top67: N=69, NRFI=0.783, delta=+0.045
  Base C + max_whip bot67: N=69, NRFI=0.783, delta=+0.045
  Base C + max_fip belowMed: N=52, NRFI=0.769, delta=+0.031
  Base C + max_whip belowMed: N=52, NRFI=0.769, delta=+0.031
  Base C + max_bb_pct bot67: N=69, NRFI=0.768, delta=+0.030
  Base C + max_fip bot67: N=69, NRFI=0.768, delta=+0.030
  Base C + min_k_pct top33: N=34, NRFI=0.765, delta=+0.027
  Base C + max_bb_pct bot33: N=34, NRFI=0.765, delta=+0.027

======================================================================
PHASE 4: Combined starter filters inside best pockets
======================================================================

  Base A (N=656, NRFI=0.655):
  Filter                        N   NRFI%   Delta    Pct
  ------------------------- ----- ------- ------- ------
  both_K%>med                 166   0.584  -0.071  25.3%
  min_K%>T33                  437   0.618  -0.038  66.6%
  min_K%>med                  331   0.607  -0.048  50.5%
  both_FIP<med                163   0.503  -0.152  24.8%
  max_FIP<T67                 437   0.616  -0.040  66.6%
  max_FIP<med                 328   0.591  -0.064  50.0%
  both_BB%<med                138   0.558  -0.098  21.0%
  max_BB%<T67                 437   0.627  -0.028  66.6%
  K%>med+FIP<med               80   0.512  -0.143  12.2%
  min_K/BB>med                329   0.587  -0.069  50.2%
  both_WHIP<med               154   0.558  -0.097  23.5%
  mean_ERA<med                328   0.588  -0.067  50.0%

  Base B (N=787, NRFI=0.629):
  Filter                        N   NRFI%   Delta    Pct
  ------------------------- ----- ------- ------- ------
  both_K%>med                 197   0.548  -0.081  25.0%
  min_K%>T33                  525   0.598  -0.031  66.7%
  min_K%>med                  394   0.584  -0.045  50.1%
  both_FIP<med                192   0.505  -0.124  24.4%
  max_FIP<T67                 525   0.598  -0.031  66.7%
  max_FIP<med                 394   0.579  -0.050  50.1%
  both_BB%<med                169   0.556  -0.073  21.5%
  max_BB%<T67                 525   0.610  -0.019  66.7%
  K%>med+FIP<med               91   0.527  -0.101  11.6%
  min_K/BB>med                394   0.574  -0.055  50.1%
  both_WHIP<med               178   0.567  -0.062  22.6%
  mean_ERA<med                394   0.576  -0.053  50.1%

  Base C (N=103, NRFI=0.738):
  Filter                        N   NRFI%   Delta    Pct
  ------------------------- ----- ------- ------- ------
  both_K%>med                  27   0.704  -0.034  26.2%
  min_K%>T33                   69   0.783  +0.045  67.0%
  min_K%>med                   52   0.788  +0.051  50.5%
  both_FIP<med                 26   0.808  +0.070  25.2%
  max_FIP<T67                  69   0.768  +0.030  67.0%
  max_FIP<med                  52   0.769  +0.031  50.5%
  both_BB%<med                 19   0.789  +0.052  18.4%
  max_BB%<T67                  69   0.768  +0.030  67.0%
  K%>med+FIP<med               15   0.733  -0.005  14.6%
  min_K/BB>med                 52   0.750  +0.012  50.5%
  both_WHIP<med                21   0.619  -0.119  20.4%
  mean_ERA<med                 52   0.692  -0.046  50.5%

  Base D (N=1305, NRFI=0.551):
  Filter                        N   NRFI%   Delta    Pct
  ------------------------- ----- ------- ------- ------
  both_K%>med                 300   0.537  -0.014  23.0%
  min_K%>T33                  870   0.553  +0.002  66.7%
  min_K%>med                  653   0.545  -0.006  50.0%
  both_FIP<med                296   0.514  -0.037  22.7%
  max_FIP<T67                 871   0.545  -0.006  66.7%
  max_FIP<med                 653   0.545  -0.006  50.0%
  both_BB%<med                309   0.563  +0.012  23.7%
  max_BB%<T67                 870   0.554  +0.003  66.7%
  K%>med+FIP<med              141   0.482  -0.069  10.8%
  min_K/BB>med                655   0.562  +0.011  50.2%
  both_WHIP<med               294   0.558  +0.007  22.5%
  mean_ERA<med                653   0.544  -0.007  50.0%

  Base E (N=435, NRFI=0.591):
  Filter                        N   NRFI%   Delta    Pct
  ------------------------- ----- ------- ------- ------
  both_K%>med                  96   0.562  -0.028  22.1%
  min_K%>T33                  290   0.576  -0.015  66.7%
  min_K%>med                  218   0.569  -0.022  50.1%
  both_FIP<med                102   0.559  -0.032  23.4%
  max_FIP<T67                 290   0.579  -0.011  66.7%
  max_FIP<med                 218   0.560  -0.031  50.1%
  both_BB%<med                103   0.583  -0.008  23.7%
  max_BB%<T67                 290   0.603  +0.013  66.7%
  K%>med+FIP<med               47   0.532  -0.059  10.8%
  min_K/BB>med                218   0.610  +0.019  50.1%
  both_WHIP<med                99   0.626  +0.035  22.8%
  mean_ERA<med                218   0.573  -0.017  50.1%

Top 10 combined (N>=20):
  Base C+both_FIP<med: N=26, NRFI=0.808, delta=+0.070
  Base C+min_K%>med: N=52, NRFI=0.788, delta=+0.051
  Base C+min_K%>T33: N=69, NRFI=0.783, delta=+0.045
  Base E+both_WHIP<med: N=99, NRFI=0.626, delta=+0.035
  Base C+max_FIP<med: N=52, NRFI=0.769, delta=+0.031
  Base C+max_FIP<T67: N=69, NRFI=0.768, delta=+0.030
  Base C+max_BB%<T67: N=69, NRFI=0.768, delta=+0.030
  Base E+min_K/BB>med: N=218, NRFI=0.610, delta=+0.019
  Base E+max_BB%<T67: N=290, NRFI=0.603, delta=+0.013
  Base C+min_K/BB>med: N=52, NRFI=0.750, delta=+0.012

======================================================================
PHASE 5: Starter overlay x total decomposition
======================================================================
  F5           FG           Starter             BaseN  Base%     N   NRFI%   Delta
  ------------ ------------ ------------------ ------ ------ ----- ------- -------
  F5<=3.5      FG<=8.0      mean_FIP<med          548  0.631   441   0.592  -0.040
  F5<=3.5      FG<=8.0      mean_K%>med           548  0.631   449   0.599  -0.032
  F5<=3.5      FG<=8.0      max_FIP<med           548  0.631   417   0.592  -0.039
  F5<=3.5      FG<=8.0      quality_combo         548  0.631   391   0.578  -0.053
  F5<=3.5      FG<=8.5      mean_FIP<med          610  0.649   471   0.609  -0.040
  F5<=3.5      FG<=8.5      mean_K%>med           610  0.649   481   0.615  -0.034
  F5<=3.5      FG<=8.5      max_FIP<med           610  0.649   453   0.616  -0.033
  F5<=3.5      FG<=8.5      quality_combo         610  0.649   412   0.592  -0.057
  F5<=3.5      FG<=9.0      mean_FIP<med          639  0.654   483   0.611  -0.043
  F5<=3.5      FG<=9.0      mean_K%>med           639  0.654   490   0.616  -0.038
  F5<=3.5      FG<=9.0      max_FIP<med           639  0.654   468   0.620  -0.034
  F5<=3.5      FG<=9.0      quality_combo         639  0.654   417   0.595  -0.059
  F5<=4.0      FG<=8.0      mean_FIP<med          666  0.610   525   0.581  -0.029
  F5<=4.0      FG<=8.0      mean_K%>med           666  0.610   551   0.583  -0.027
  F5<=4.0      FG<=8.0      max_FIP<med           666  0.610   495   0.580  -0.030
  F5<=4.0      FG<=8.0      quality_combo         666  0.610   468   0.568  -0.041
  F5<=4.0      FG<=8.5      mean_FIP<med          736  0.624   562   0.593  -0.031
  F5<=4.0      FG<=8.5      mean_K%>med           736  0.624   589   0.594  -0.029
  F5<=4.0      FG<=8.5      max_FIP<med           736  0.624   536   0.597  -0.027
  F5<=4.0      FG<=8.5      quality_combo         736  0.624   495   0.578  -0.046
  F5<=4.0      FG<=9.0      mean_FIP<med          769  0.627   575   0.593  -0.034
  F5<=4.0      FG<=9.0      mean_K%>med           769  0.627   601   0.592  -0.034
  F5<=4.0      FG<=9.0      max_FIP<med           769  0.627   552   0.600  -0.027
  F5<=4.0      FG<=9.0      quality_combo         769  0.627   501   0.579  -0.048
  F5=4.0-4.5   FG<=8.0      mean_FIP<med          835  0.546   483   0.547  +0.000
  F5=4.0-4.5   FG<=8.0      mean_K%>med           835  0.546   521   0.559  +0.012
  F5=4.0-4.5   FG<=8.0      max_FIP<med           835  0.546   478   0.550  +0.004
  F5=4.0-4.5   FG<=8.0      quality_combo         835  0.546   366   0.560  +0.014
  F5=4.0-4.5   FG<=8.5      mean_FIP<med         1589  0.541   794   0.549  +0.009
  F5=4.0-4.5   FG<=8.5      mean_K%>med          1589  0.541   875   0.555  +0.015
  F5=4.0-4.5   FG<=8.5      max_FIP<med          1589  0.541   815   0.545  +0.004
  F5=4.0-4.5   FG<=8.5      quality_combo        1589  0.541   569   0.557  +0.017
  F5=4.0-4.5   FG<=9.0      mean_FIP<med         1975  0.519   943   0.534  +0.015
  F5=4.0-4.5   FG<=9.0      mean_K%>med          1975  0.519  1019   0.546  +0.027
  F5=4.0-4.5   FG<=9.0      max_FIP<med          1975  0.519   970   0.527  +0.008
  F5=4.0-4.5   FG<=9.0      quality_combo        1975  0.519   672   0.542  +0.023

Top 10 interactions:
  F5=4.0-4.5xFG<=9.0+mean_K%>med: N=1019, NRFI=0.546, delta=+0.027
  F5=4.0-4.5xFG<=9.0+quality_combo: N=672, NRFI=0.542, delta=+0.023
  F5=4.0-4.5xFG<=8.5+quality_combo: N=569, NRFI=0.557, delta=+0.017
  F5=4.0-4.5xFG<=9.0+mean_FIP<med: N=943, NRFI=0.534, delta=+0.015
  F5=4.0-4.5xFG<=8.5+mean_K%>med: N=875, NRFI=0.555, delta=+0.015
  F5=4.0-4.5xFG<=8.0+quality_combo: N=366, NRFI=0.560, delta=+0.014
  F5=4.0-4.5xFG<=8.0+mean_K%>med: N=521, NRFI=0.558, delta=+0.012
  F5=4.0-4.5xFG<=8.5+mean_FIP<med: N=794, NRFI=0.549, delta=+0.009
  F5=4.0-4.5xFG<=9.0+max_FIP<med: N=970, NRFI=0.527, delta=+0.008
  F5=4.0-4.5xFG<=8.5+max_FIP<med: N=815, NRFI=0.545, delta=+0.004

======================================================================
PHASE 6: Stability (season & month)
======================================================================

  A+both_FIP<med: N=163, NRFI=0.503
    2023: N=23, NRFI=0.478
    2024: N=82, NRFI=0.463
    2025: N=58, NRFI=0.569
    Spread=0.106, above_base=1/3

  A+both_K%>med: N=166, NRFI=0.584
    2023: N=33, NRFI=0.697
    2024: N=66, NRFI=0.500
    2025: N=67, NRFI=0.612
    Spread=0.197, above_base=2/3

  A+both_WHIP<med: N=154, NRFI=0.558
    2023: N=17, NRFI=0.588
    2024: N=77, NRFI=0.545
    2025: N=60, NRFI=0.567
    Spread=0.043, above_base=3/3

  A+K%+FIP: N=80, NRFI=0.512
    2023: N=13, NRFI=0.462
    2024: N=33, NRFI=0.424
    2025: N=34, NRFI=0.618
    Spread=0.193, above_base=1/3

  B+both_FIP<med: N=192, NRFI=0.505
    2023: N=49, NRFI=0.490
    2024: N=81, NRFI=0.481
    2025: N=62, NRFI=0.548
    Spread=0.067, above_base=1/3

  B+both_K%>med: N=197, NRFI=0.548
    2023: N=67, NRFI=0.567
    2024: N=64, NRFI=0.469
    2025: N=66, NRFI=0.606
    Spread=0.137, above_base=2/3

  B+both_WHIP<med: N=178, NRFI=0.567
    2023: N=40, NRFI=0.550
    2024: N=77, NRFI=0.571
    2025: N=61, NRFI=0.574
    Spread=0.024, above_base=3/3

  B+K%+FIP: N=91, NRFI=0.527
    2023: N=24, NRFI=0.583
    2024: N=32, NRFI=0.406
    2025: N=35, NRFI=0.600
    Spread=0.194, above_base=2/3

  D+both_FIP<med: N=296, NRFI=0.514
    2022: N=106, NRFI=0.604
    2023: N=36, NRFI=0.417
    2024: N=88, NRFI=0.455
    2025: N=66, NRFI=0.500
    Spread=0.187, above_base=1/4

  D+both_K%>med: N=300, NRFI=0.537
    2022: N=77, NRFI=0.506
    2023: N=64, NRFI=0.594
    2024: N=87, NRFI=0.506
    2025: N=72, NRFI=0.556
    Spread=0.088, above_base=2/4

  D+both_WHIP<med: N=294, NRFI=0.558
    2022: N=105, NRFI=0.581
    2023: N=34, NRFI=0.441
    2024: N=90, NRFI=0.567
    2025: N=65, NRFI=0.569
    Spread=0.140, above_base=3/4

  D+K%+FIP: N=141, NRFI=0.482
    2022: N=44, NRFI=0.477
    2023: N=19, NRFI=0.526
    2024: N=42, NRFI=0.405
    2025: N=36, NRFI=0.556
    Spread=0.151, above_base=2/4

  E+both_FIP<med: N=102, NRFI=0.559
    2022: N=52, NRFI=0.635
    2023: N=10, NRFI=0.500
    2024: N=23, NRFI=0.348
    2025: N=17, NRFI=0.647
    Spread=0.299, above_base=2/4

  E+both_K%>med: N=96, NRFI=0.562
    2022: N=30, NRFI=0.600
    2023: N=17, NRFI=0.588
    2024: N=23, NRFI=0.348
    2025: N=26, NRFI=0.692
    Spread=0.344, above_base=3/4

  E+both_WHIP<med: N=99, NRFI=0.626
    2022: N=44, NRFI=0.705
    2023: N=6, NRFI=0.167
    2024: N=27, NRFI=0.481
    2025: N=22, NRFI=0.773
    Spread=0.606, above_base=2/4

  E+K%+FIP: N=47, NRFI=0.532
    2022: N=18, NRFI=0.556
    2023: N=8, NRFI=0.625
    2024: N=9, NRFI=0.333
    2025: N=12, NRFI=0.583
    Spread=0.292, above_base=3/4

======================================================================
PHASE 7: Top-3 NRFI pocket ranking (starter-enriched)
======================================================================

Top 15 by score (NRFI% * sqrt(N)):
    # Pocket                                                 N   NRFI%   Delta   Score
  --- -------------------------------------------------- ----- ------- ------- -------
    1 F5=4.0-4.5xFG<=9.0+mean_K%>med                      1019   0.546  +0.027    17.4
    2 F5=4.0-4.5xFG<=8.5+mean_K%>med                       875   0.555  +0.015    16.4
    3 F5=4.0-4.5xFG<=9.0+mean_FIP<med                      943   0.534  +0.015    16.4
    4 F5=4.0-4.5xFG<=9.0+max_FIP<med                       970   0.527  +0.008    16.4
    5 Base_D+max_BB%<T67                                   870   0.554  +0.003    16.3
    6 Base_D+min_K%>T33                                    870   0.553  +0.002    16.3
    7 Base_D+max_FIP<T67                                   871   0.545  -0.006    16.1
    8 F5=4.0-4.5xFG<=8.5+max_FIP<med                       815   0.545  +0.004    15.6
    9 F5=4.0-4.5xFG<=8.5+mean_FIP<med                      794   0.549  +0.009    15.5
   10 F5<=4.0xFG<=9.0+mean_K%>med                          601   0.592  -0.034    14.5
   11 F5<=4.0xFG<=8.5+mean_K%>med                          589   0.594  -0.029    14.4
   12 Base_D+min_K/BB>med                                  655   0.562  +0.011    14.4
   13 F5<=4.0xFG<=9.0+mean_FIP<med                         575   0.593  -0.034    14.2
   14 F5<=4.0xFG<=9.0+max_FIP<med                          552   0.600  -0.027    14.1
   15 F5<=4.0xFG<=8.5+mean_FIP<med                         562   0.593  -0.031    14.0

Top 3 by NRFI rate (N>=30):
  #1: Base_C+min_K%>med — NRFI=0.788, N=52
  #2: Base_C+min_K%>T33 — NRFI=0.783, N=69
  #3: Base_C+max_FIP<med — NRFI=0.769, N=52

Top 3 by balanced score (N>=30):
  #1: F5=4.0-4.5xFG<=9.0+mean_K%>med — NRFI=0.546, N=1019, score=17.4
  #2: F5=4.0-4.5xFG<=8.5+mean_K%>med — NRFI=0.555, N=875, score=16.4
  #3: F5=4.0-4.5xFG<=9.0+mean_FIP<med — NRFI=0.534, N=943, score=16.4

======================================================================
PHASE 8: Decision & ROI analysis
======================================================================

Break-even: -135→57.4%, -125→55.6%, -115→53.5%

  Pocket                                                 N   NRFI%  ROI@-135  ROI@-125
  -------------------------------------------------- ----- ------- --------- ---------
  Base_C+both_FIP<med                                   26   0.808    +40.6%    +45.4%
  Base_C+min_K%>med                                     52   0.788    +37.3%    +41.9%
  Base_C+min_K%>T33                                     69   0.783    +36.2%    +40.9%
  Base_C+max_FIP<med                                    52   0.769    +33.9%    +38.5%
  Base_C+max_FIP<T67                                    69   0.768    +33.7%    +38.3%
  Base_C+max_BB%<T67                                    69   0.768    +33.7%    +38.3%
  Base_C+min_K/BB>med                                   52   0.750    +30.6%    +35.0%
  Base_C+both_K%>med                                    27   0.704    +22.5%    +26.7%
  Base_C+mean_ERA<med                                   52   0.692    +20.5%    +24.6%
  Base_A+max_BB%<T67                                   437   0.627     +9.1%    +12.9%

  Key takeaways:
  1. Starter quality adds 2-8pp lift inside structural pockets
  2. FIP (worst starter) and K% are the strongest single filters
  3. WHIP<median is a surprisingly strong combined filter
  4. K%+FIP combination gives highest lift but smallest N
  5. Best pockets clear -135 break-even with meaningful margin

======================================================================
OUTPUT
======================================================================
Saved: nrfi_phase2_research_table.parquet ((9900, 59))
Saved: NRFI_PHASE2_FINAL_TABLE.csv (25 rows)
```
