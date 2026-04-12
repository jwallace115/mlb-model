# MLB SIDES PHASE 5 -- EXEC SUMMARY
## SP-LED Timing + MIXED Overlay Hunt

**Date**: 2026-04-12

---

## Branch A: SP-LED Open/Close Timing

**VERDICT: UNVERIFIABLE**

No opening moneyline prices exist in the historical data.
The canonical odds parquet contains only closing prices.
Market snapshots track totals open/noon/5pm/close but no ML open prices.
Cannot test whether SP-LED dogs offer better ROI at open vs close.

---

## Branch B: MIXED Overlay Hunt

### Setup
- MIXED games total: 1231
- Discovery (2022-2023): 540
- Validation (2024): 333
- OOS (2025): 358

### Baseline MIXED Dog Performance
- Discovery dog WR: 0.4889 (implied: 0.4639, resid: +0.0250)
- Discovery ROI: +1.09%

### Overlays Tested (30 total)
Dimensions: total environment, day/night, dog orientation, SP gap,
BP advantage, offense advantage, fav implied tier, rest differential,
plus compound overlays.

### Discovery-Positive (15 overlays, resid > 2%, N >= 30)
```
              label   n   dog_wr  implied_dog  residual   roi_pct
          MIXED_all 540 0.488889     0.463898  0.024991  1.091545
         total_high 188 0.521277     0.463494  0.057783  8.250417
     daynight_night 381 0.498688     0.463823  0.034865  3.131748
           dog_home 226 0.491150     0.463837  0.027313  1.553618
           dog_away 314 0.487261     0.463942  0.023319  0.758970
        sp_gap_wide 176 0.517045     0.463698  0.053348  6.983400
       bp_adv_dog_1 241 0.526971     0.464549  0.062422  8.676999
      off_adv_dog_0 286 0.513986     0.463722  0.050264  6.185726
   fav_imp_moderate 255 0.490196     0.462898  0.027298  1.607843
      fav_imp_heavy 126 0.476190     0.447700  0.028491  2.285714
       dog_rested_0 519 0.493256     0.463872  0.029384  1.987274
    dog_home+bp_adv  73 0.630137     0.465539  0.164598 29.754499
slight_fav+dog_home  66 0.500000     0.478395  0.021605 -0.058824
     bp_adv+off_adv 116 0.491379     0.464062  0.027317  1.647228
       night+bp_adv 180 0.516667     0.464403  0.052264  6.606427
```

### Full Results Table (all periods)
```
                overlay  disc_n  disc_resid  disc_roi  val_n  val_resid  val_roi  oos_n  oos_resid  oos_roi           verdict
        dog_home+bp_adv      73      0.1646     29.75     47     0.0223     0.56     61     0.1562    27.16         CONFIRMED
dog_home+bp_adv+off_adv      29      0.1209     21.38     21     0.0572     7.67      0        NaN      NaN         NO_SIGNAL
           bp_adv_dog_1     241      0.0624      8.68    147     0.0519     6.30    179     0.0416     3.73         CONFIRMED
             total_high     188      0.0578      8.25     89     0.0069    -2.83    132    -0.0037    -5.52 VAL_PASS_OOS_FAIL
            sp_gap_wide     176      0.0533      6.98    115     0.0055    -3.22    119     0.0734    10.96         CONFIRMED
           night+bp_adv     180      0.0523      6.61    109     0.0214     0.01    135     0.0599     7.63         CONFIRMED
          off_adv_dog_0     286      0.0503      6.19    163     0.0027    -3.75    187     0.0423     4.17         CONFIRMED
         daynight_night     381      0.0349      3.13    245     0.0337     2.64    268     0.0533     6.50         CONFIRMED
           dog_rested_0     519      0.0294      1.99    322     0.0173    -0.65    348     0.0368     3.10         CONFIRMED
          fav_imp_heavy     126      0.0285      2.29     75    -0.0353   -11.55     82     0.0270     1.34         DISC_ONLY
       fav_imp_moderate     255      0.0273      1.61    148     0.0179    -0.37    138     0.0295     1.72         CONFIRMED
         bp_adv+off_adv     116      0.0273      1.65     80     0.0479     5.80     77     0.0144    -1.68         CONFIRMED
               dog_home     226      0.0273      1.55    129    -0.0004    -4.12    140     0.1122    18.55         DISC_ONLY
              MIXED_all     540      0.0250      1.09    333     0.0163    -0.90    358     0.0367     3.07         CONFIRMED
               dog_away     314      0.0233      0.76    204     0.0269     1.13    218    -0.0117    -6.87 VAL_PASS_OOS_FAIL
    slight_fav+dog_home      66      0.0216     -0.06     48    -0.0403   -12.33     56     0.0925    13.91         DISC_ONLY
         fav_imp_slight     159      0.0185     -0.68    110     0.0495     5.64    138     0.0497     5.46    WEAK_CONFIRMED
           sp_gap_tight     178      0.0143     -1.28    121     0.0480     5.84    112    -0.0018    -5.30         NO_SIGNAL
              total_mid     209      0.0137     -1.69    138     0.0351     3.01    153     0.0955    15.32    WEAK_CONFIRMED
     low_total+dog_home      65      0.0125     -1.71     42    -0.0108    -6.55     23     0.2319    43.48         NO_SIGNAL
        sp_gap_moderate     186      0.0084     -2.21     97    -0.0103    -6.58    127     0.0364     3.06         NO_SIGNAL
           daynight_day     159      0.0013     -3.80     88    -0.0319   -10.77     90    -0.0125    -7.12         NO_SIGNAL
              total_low     143     -0.0016     -4.25    106    -0.0001    -4.38     73    -0.0134    -7.07         NO_SIGNAL
          off_adv_dog_1     254     -0.0035     -4.64    170     0.0294     1.83    171     0.0306     1.88         NO_SIGNAL
           bp_adv_dog_0     299     -0.0052     -5.02    186    -0.0118    -6.60    179     0.0318     2.41         NO_SIGNAL
       dog_home+off_adv      88     -0.0091     -5.75     61     0.0087    -2.33     60     0.0852    13.32         NO_SIGNAL
      sp_tight+dog_home      87     -0.0266     -9.94     57     0.0606     8.90     48     0.0976    15.29         NO_SIGNAL
           day+dog_home      74     -0.0309    -10.59     31    -0.0128    -6.45     32    -0.0610   -17.08         NO_SIGNAL
           dog_rested_1      21     -0.0836    -21.05      0        NaN      NaN      0        NaN      NaN         NO_SIGNAL
```

### CONFIRMED Overlays (disc + val + OOS all positive residual)
```
         overlay  disc_n  disc_resid  disc_roi  val_n  val_resid  val_roi  oos_n  oos_resid  oos_roi        verdict
 dog_home+bp_adv      73      0.1646     29.75     47     0.0223     0.56     61     0.1562    27.16      CONFIRMED
    bp_adv_dog_1     241      0.0624      8.68    147     0.0519     6.30    179     0.0416     3.73      CONFIRMED
     sp_gap_wide     176      0.0533      6.98    115     0.0055    -3.22    119     0.0734    10.96      CONFIRMED
    night+bp_adv     180      0.0523      6.61    109     0.0214     0.01    135     0.0599     7.63      CONFIRMED
   off_adv_dog_0     286      0.0503      6.19    163     0.0027    -3.75    187     0.0423     4.17      CONFIRMED
  daynight_night     381      0.0349      3.13    245     0.0337     2.64    268     0.0533     6.50      CONFIRMED
    dog_rested_0     519      0.0294      1.99    322     0.0173    -0.65    348     0.0368     3.10      CONFIRMED
fav_imp_moderate     255      0.0273      1.61    148     0.0179    -0.37    138     0.0295     1.72      CONFIRMED
  bp_adv+off_adv     116      0.0273      1.65     80     0.0479     5.80     77     0.0144    -1.68      CONFIRMED
       MIXED_all     540      0.0250      1.09    333     0.0163    -0.90    358     0.0367     3.07      CONFIRMED
  fav_imp_slight     159      0.0185     -0.68    110     0.0495     5.64    138     0.0497     5.46 WEAK_CONFIRMED
       total_mid     209      0.0137     -1.69    138     0.0351     3.01    153     0.0955    15.32 WEAK_CONFIRMED
```
- **dog_home+bp_adv**: disc ROI +29.8%, val ROI +0.6%, OOS ROI +27.2%
- **bp_adv_dog_1**: disc ROI +8.7%, val ROI +6.3%, OOS ROI +3.7%
- **sp_gap_wide**: disc ROI +7.0%, val ROI -3.2%, OOS ROI +11.0%
- **night+bp_adv**: disc ROI +6.6%, val ROI +0.0%, OOS ROI +7.6%
- **off_adv_dog_0**: disc ROI +6.2%, val ROI -3.8%, OOS ROI +4.2%
- **daynight_night**: disc ROI +3.1%, val ROI +2.6%, OOS ROI +6.5%
- **dog_rested_0**: disc ROI +2.0%, val ROI -0.7%, OOS ROI +3.1%
- **fav_imp_moderate**: disc ROI +1.6%, val ROI -0.4%, OOS ROI +1.7%
- **bp_adv+off_adv**: disc ROI +1.6%, val ROI +5.8%, OOS ROI -1.7%
- **MIXED_all**: disc ROI +1.1%, val ROI -0.9%, OOS ROI +3.1%
- **fav_imp_slight**: disc ROI -0.7%, val ROI +5.6%, OOS ROI +5.5%
- **total_mid**: disc ROI -1.7%, val ROI +3.0%, OOS ROI +15.3%

---

## Final Verdict

- **Branch A (SP-LED timing)**: UNVERIFIABLE -- no opening ML prices available.
- **Branch B (MIXED overlays)**: 10 CONFIRMED, 2 WEAK_CONFIRMED.

## Files
- `MLB_SIDES_PHASE5_FINAL_TABLE.csv` -- full overlay results across all periods
- `discovery_results.csv` -- detailed discovery-period results
- `phase5_analysis.py` -- reproducible analysis script
- `MLB_SIDES_PHASE5_EXEC_SUMMARY.md` -- this file