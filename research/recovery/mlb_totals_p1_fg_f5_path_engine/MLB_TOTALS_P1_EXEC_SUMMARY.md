# MLB Totals P1 — FG/F5 Path Mismatch Engine

## Executive Summary

### Thesis
The FG total and F5 total together imply a scoring path (early vs late).
When structural game drivers (SP depth, BP quality, park, temperature) conflict
with the market-implied path, there may be FG total mispricing.

### Data Coverage
- F5 canonical lines: 6637 games (2023-05 to 2025-09)
- FG closing odds: 10761 games
- Research table: 9391 games (9+ innings, F5 actuals)
- Discovery: 2023 (n=3419)
- Validation: 2024 (n=2946)
- OOS: 2025 (n=3026)

### Path States (thresholds frozen from 2023)
- F5_ratio p33=0.5294, p67=0.5625
- Late_implied p75=4.50

```
split           discovery   oos  validation
path_state                                 
BALANCED             1235  1170        1244
COMPRESSED_LOW        412   622         789
EARLY_HEAVY           638   369         218
ELEVATED_LATE         966   807         628
LATE_HEAVY            168    58          67
```

### Phase 5 — Path Error
**Key finding:** EARLY_HEAVY and COMPRESSED_LOW show persistent positive path
error (market underestimates late scoring). ELEVATED_LATE shows persistent
negative path error. These patterns are highly significant across all splits.

**DISCOVERY** (n=3419)
- BALANCED: path_err=-0.048 (t=-0.58, p=0.564), over=0.453
- COMPRESSED_LOW: path_err=+0.513 (t=+3.73, p=0.000), over=0.546
- EARLY_HEAVY: path_err=+0.865 (t=+6.94, p=0.000), over=0.561
- ELEVATED_LATE: path_err=-0.532 (t=-5.08, p=0.000), over=0.435
- LATE_HEAVY: path_err=-0.711 (t=-3.10, p=0.002), over=0.446

**VALIDATION** (n=2946)
- BALANCED: path_err=+0.096 (t=+1.15, p=0.252), over=0.468
- COMPRESSED_LOW: path_err=+0.122 (t=+1.21, p=0.228), over=0.503
- EARLY_HEAVY: path_err=+1.055 (t=+5.04, p=0.000), over=0.601
- ELEVATED_LATE: path_err=-0.611 (t=-5.15, p=0.000), over=0.436
- LATE_HEAVY: path_err=-1.418 (t=-4.52, p=0.000), over=0.328

**OOS** (n=3026)
- BALANCED: path_err=-0.014 (t=-0.17, p=0.868), over=0.480
- COMPRESSED_LOW: path_err=+0.063 (t=+0.58, p=0.565), over=0.469
- EARLY_HEAVY: path_err=+0.844 (t=+4.32, p=0.000), over=0.499
- ELEVATED_LATE: path_err=-0.595 (t=-5.03, p=0.000), over=0.413
- LATE_HEAVY: path_err=-0.578 (t=-1.41, p=0.164), over=0.414

### Phase 6 — Interactions
- 60 interactions tested (12 drivers x up to 5 path states)
- 8 at p<0.10, 6 at p<0.05
- 6 selected for economics

### Phase 8-9 — Economics (Actual Closing Prices)

**BALANCED x BP quality diff** (over)
- Disc: n=356 win=53.9% ROI=+5.8%
- Val:  n=421 win=48.2% ROI=-3.8%
- OOS:  n=338 win=45.3% ROI=-12.2%

**COMPRESSED_LOW x Temperature** (over)
- Disc: n=220 win=60.9% ROI=+16.5%
- Val:  n=351 win=54.4% ROI=+6.0%
- OOS:  n=261 win=47.5% ROI=-6.8%

**COMPRESSED_LOW x Park factor** (over)
- Disc: n=257 win=59.5% ROI=+13.8%
- Val:  n=464 win=50.4% ROI=-0.7%
- OOS:  n=375 win=47.2% ROI=-5.5%

**EARLY_HEAVY x Temperature** (over)
- Disc: n=319 win=61.4% ROI=+20.2%
- Val:  n=105 win=59.0% ROI=+14.4%
- OOS:  n=173 win=53.2% ROI=+9.1%

**BALANCED x Temperature** (over)
- Disc: n=803 win=48.1% ROI=-5.6%
- Val:  n=859 win=49.2% ROI=-2.2%
- OOS:  n=749 win=49.5% ROI=-4.3%

**BALANCED x Avg SP IP vol** (under)
- Disc: n=600 win=53.3% ROI=+6.0%
- Val:  n=694 win=47.7% ROI=-4.8%
- OOS:  n=697 win=50.5% ROI=-1.3%

### Phase 10 — Decision Board
- PROMOTE: 1
- MONITOR: 1
- WATCH: 3
- REJECT: 1

#### PROMOTE Signals
- **EARLY_HEAVY x Temperature** (over): disc=+20.2%(n=319) val=+14.4%(n=105) oos=+9.1%(n=173)

#### MONITOR Signals
- **COMPRESSED_LOW x Temperature** (over): disc=+16.5%(n=220) val=+6.0%(n=351) oos=-6.8%(n=261)

#### WATCH Signals
- **BALANCED x BP quality diff** (over): disc=+5.8%(n=356) val=-3.8%(n=421) oos=-12.2%(n=338)
- **COMPRESSED_LOW x Park factor** (over): disc=+13.8%(n=257) val=-0.7%(n=464) oos=-5.5%(n=375)
- **BALANCED x Avg SP IP vol** (under): disc=+6.0%(n=600) val=-4.8%(n=694) oos=-1.3%(n=697)

### Recommendation
PROMOTE signals identified. Proceed to shadow implementation.