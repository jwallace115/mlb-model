# MLB Totals P1 — FG/F5 Path Mismatch Engine

## Executive Summary

### Thesis
The FG total and F5 total together imply a scoring path (early vs late).
When structural game drivers (SP depth, BP quality, park) conflict with
the market-implied path, there may be FG total mispricing.

### Data Coverage
- F5 canonical lines: 6638 games (2023-05 to 2025-09)
- FG closing odds with prices: 11263 games
- Research table (merged, 9+ innings): 7555 games
- Discovery: 2023 only (n=2773)
- Validation: 2024 (n=2389)
- OOS: 2025 (n=2393)

### Path States (thresholds frozen from 2023)
- F5_ratio p33=0.5294, p67=0.5625
- Late_implied p75=4.50

```
split           discovery  oos  validation
path_state                                
BALANCED              977  911        1002
COMPRESSED_LOW        344  512         617
EARLY_HEAVY           520  287         182
ELEVATED_LATE         796  632         526
LATE_HEAVY            136   51          62
```

### Phase 5 — Path Error
Is the market systematically wrong about early/late split?

**DISCOVERY** (n=2773)
- BALANCED: path_err=-0.039 (t=-0.42, p=0.676), FG over rate=0.456
- COMPRESSED_LOW: path_err=+0.574 (t=+3.76, p=0.000), FG over rate=0.558
- EARLY_HEAVY: path_err=+0.870 (t=+6.41, p=0.000), FG over rate=0.573
- ELEVATED_LATE: path_err=-0.509 (t=-4.37, p=0.000), FG over rate=0.436
- LATE_HEAVY: path_err=-0.496 (t=-1.86, p=0.065), FG over rate=0.456

**VALIDATION** (n=2389)
- BALANCED: path_err=+0.053 (t=+0.57, p=0.571), FG over rate=0.469
- COMPRESSED_LOW: path_err=+0.128 (t=+1.13, p=0.257), FG over rate=0.499
- EARLY_HEAVY: path_err=+1.179 (t=+5.00, p=0.000), FG over rate=0.604
- ELEVATED_LATE: path_err=-0.695 (t=-5.37, p=0.000), FG over rate=0.428
- LATE_HEAVY: path_err=-1.363 (t=-4.11, p=0.000), FG over rate=0.355

**OOS** (n=2393)
- BALANCED: path_err=+0.033 (t=+0.34, p=0.735), FG over rate=0.481
- COMPRESSED_LOW: path_err=+0.033 (t=+0.28, p=0.782), FG over rate=0.469
- EARLY_HEAVY: path_err=+0.902 (t=+4.18, p=0.000), FG over rate=0.516
- ELEVATED_LATE: path_err=-0.613 (t=-4.51, p=0.000), FG over rate=0.407
- LATE_HEAVY: path_err=-0.471 (t=-1.05, p=0.297), FG over rate=0.412

### Phase 6 — Interactions
- 10 interactions tested
- 2 at p<0.10, 1 at p<0.05

### Phase 8-9 — Economics (Actual Closing Prices)

**COMPRESSED_LOW x Temperature** (over)
- Discovery: n=182 win=60.4% ROI=+15.8%
- Validation: n=277 win=54.5% ROI=+5.8%
- OOS: n=239 win=47.7% ROI=-6.1%

**LATE_HEAVY x Temperature** (over)
- Discovery: n=81 win=48.1% ROI=-0.3%
- Validation: n=38 win=44.7% ROI=-11.6%
- OOS: n=27 win=48.1% ROI=-4.2%

### Phase 10 — Decision Board
- PROMOTE: 0
- MONITOR: 1
- WATCH: 0
- REJECT: 1

#### MONITOR Signals
- **COMPRESSED_LOW x Temperature** (over): disc=+15.8% val=+5.8% oos=-6.1%

### Recommendation
MONITOR signals show disc+val persistence but fail OOS.
Continue data collection; do not deploy live.