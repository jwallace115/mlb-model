# MLB Moneyline Phase 2 Deep Decomposition — Executive Summary

## Date: 2026-04-11

## Phase 1 Recap
Phase 1 tested structural axes. **0/8 survived.** Closing lines efficiently price schedule.

## Phase 2 Thesis
PIT-safe rolling pitcher/team features to find close-game mispricing.

## Data
- Close-game universe (A-C): 5242 games
- DISC: 2679 (2022-23), VAL: 1285 (2024), OOS: 1278 (2025)

## Feature Families
1. SP form divergence (expanding vs rolling-3 ERA/FIP/K%/BB%)
2. SP mismatch (fav declining + dog improving)
3. Bullpen workload/ERA mismatch
4. Team momentum (rolling 5/10/20 run differential)
5. SP reputation trap (elite long + poor recent)
6. Interactions: SP+RD5, SP+BP, triple mismatch, fav confirming

## Keep/Kill Board

| Strategy | Decision | Disc N | Disc Resid | Val N | Val Resid | OOS N | OOS Resid |
|----------|----------|--------|------------|-------|-----------|-------|-----------|
| Fav SP declining + Dog SP improving | WATCH | 346 | -0.0403 | 156 | +0.0404 | 152 | +0.0047 |
| SP ERA mismatch favors dog | KILL | 724 | -0.0325 | 327 | +0.0252 | 322 | -0.0148 |
| Fav SP materially declining (div<-0.5) | KILL | 573 | -0.0519 | 245 | +0.0390 | 248 | -0.0369 |
| Dog SP materially improving (div>0.5) | WATCH | 503 | -0.0272 | 263 | +0.0340 | 205 | +0.0504 |
| Fav SP rep trap (long<3.5 short>4.5) | KILL | 65 | -0.0098 | 35 | +0.0750 | 35 | +0.0778 |
| Fav BP overworked + Dog BP fresh | KILL | 82 | -0.0527 | 44 | +0.0042 | 36 | -0.0231 |
| BP workload mismatch favors dog | WATCH | 775 | -0.0019 | 406 | +0.0210 | 333 | +0.0219 |
| Fav BP recent blowup (short>>long) | KILL | 670 | -0.0125 | 346 | -0.0271 | 327 | +0.0227 |
| Dog better recent form (RD5) | WATCH | 1402 | +0.0013 | 687 | -0.0130 | 716 | +0.0411 |
| Fav SP improving + Dog SP declining (fav) | KILL | 362 | -0.0241 | 168 | +0.0064 | 160 | -0.0444 |
| Fav hot streak RD5>1.5 (fav) | KILL | 899 | -0.0072 | 416 | -0.0219 | 440 | -0.0024 |
| Fav SP elite+confirming (fav) | KILL | 248 | -0.0054 | 133 | -0.0105 | 137 | -0.0221 |
| INT1: SP+RD5 mismatch (dog) | WATCH | 326 | -0.0543 | 151 | +0.0210 | 141 | +0.0417 |
| INT2: SP+BP mismatch (dog) | WATCH | 256 | -0.0461 | 138 | +0.0178 | 127 | +0.0038 |
| INT3: Fav rep trap + dog form (dog) | KILL | 39 | -0.1117 | 29 | -0.0590 | 21 | +0.0563 |
| INT4: Triple mismatch SP+BP+RD5 (dog) | WATCH | 124 | -0.0562 | 70 | +0.0429 | 60 | +0.0142 |
| INT5: Fav SP improving + hot streak (fav) | WATCH | 272 | +0.0336 | 141 | +0.0065 | 125 | -0.0948 |

**KEEP: 0 | WATCH: 8 | KILL: 9**

### Watch-List (need 2026 data)
- **Fav SP declining + Dog SP improving**: D=-0.0403, V=+0.0404, O=+0.0047
- **Dog SP materially improving (div>0.5)**: D=-0.0272, V=+0.0340, O=+0.0504
- **BP workload mismatch favors dog**: D=-0.0019, V=+0.0210, O=+0.0219
- **Dog better recent form (RD5)**: D=+0.0013, V=-0.0130, O=+0.0411
- **INT1: SP+RD5 mismatch (dog)**: D=-0.0543, V=+0.0210, O=+0.0417
- **INT2: SP+BP mismatch (dog)**: D=-0.0461, V=+0.0178, O=+0.0038
- **INT4: Triple mismatch SP+BP+RD5 (dog)**: D=-0.0562, V=+0.0429, O=+0.0142
- **INT5: Fav SP improving + hot streak (fav)**: D=+0.0336, V=+0.0065, O=-0.0948

## Structural Conclusion
MLB closing moneylines are extremely well-calibrated. Even with PIT-safe
rolling SP quality, bullpen fatigue, and team momentum features,
no strategy produces durable positive residuals across all three gates.
The market efficiently incorporates pitcher form, bullpen workload,
and team momentum into closing prices.

This confirms and extends Phase 1: MLB moneylines at close leave
minimal systematic edge for flat-bet strategies.

## Methodology
- All features PIT-safe: shift(1) + expanding/rolling within season
- No lineup features, no FanGraphs aggregates, no model outputs
- Closing prices from DK canonical archive
- ROI at actual American odds
- Min N=150 for KEEP; durability requires >=3/4 seasons same-sign