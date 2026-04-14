# MLB Archetype Engine V1-Lite — Full Report
Build date: 2026-04-14

## Executive Summary
**Verdict: NO-GO**
Discovery showed signal but validation failed directional consistency.

## Phase 0: Field Lineage Audit
| Source | Rows | Coverage |
|--------|------|----------|
| hitter_game_logs | 204,548 | walks/PA/AB/2B/3B/HR/batting_order_position all present |
| pitcher_game_logs | 85,142 | strikeouts/walks/batters_faced/starter_flag all present |
| game_table | 9,902 | actual_total/home_score/away_score/teams all present |

**All required dimensions buildable. PIT-safe with shift(1). No excluded sources touched.**

## Phase 1: Lineup State
- **PATIENCE**: Rolling 15-game BB/PA, shift(1), min 10 games
  - Discovery tercile cuts: LOW < 0.0758 | HIGH > 0.0904
- **DAMAGE**: Rolling 15-game ISO=(2B+2*3B+3*HR)/AB, shift(1), min 10 games
  - Discovery tercile cuts: LOW < 0.1431 | HIGH > 0.1703
- **CONCENTRATION**: Rolling 15-game mean Gini(batting slot hits), shift(1)
  - Discovery tercile cuts: LOW < 0.5018 | HIGH > 0.5382

**Archetype labels**: PATIENT_DAMAGE | PATIENT_CONTACT | IMPATIENT_POWER | IMPATIENT_WEAK | MIXED

## Phase 2: Starter Direct-Eval
- **BAT-MISS**: Rolling 5-start K/BF, shift(1), min 3 starts
  - Discovery tercile cuts: LOW < 0.1897 | HIGH > 0.2419
- **COMMAND**: Rolling 5-start BB/BF, shift(1), min 3 starts
  - Discovery tercile cuts: LOW < 0.0606 | HIGH > 0.0866

**SP Profile labels**: ELITE | WILD_POWER | CONTACT | VULNERABLE | AVERAGE

## Phase 3: Game Table
- Joined hitter lineup state × opposing starter profile per game
- Starters derived from pitcher_game_logs (starter_flag=1)
- No starter IDs in game_table — derived correctly from source

## Phase 4: Discovery Interaction Test (2022-2023)
- Discovery game-halves: 14,234
- Grand mean runs scored: 4.525
- Max |interaction residual|: 0.804
- Max |residual| in adequate-N cells (n≥50): 0.804
- Adequate-N cells: 25/25
- **DISCOVERY: PASS**

### Interaction Table (Discovery)
| Lineup | SP Profile | Actual | Expected | Residual | N | LowN |
|--------|------------|--------|----------|----------|---|------|
| PATIENT_CONTACT | ELITE | 5.130 | 4.327 | +0.804 | 115 | no |
| IMPATIENT_POWER | WILD_POWER | 4.944 | 4.412 | +0.532 | 126 | no |
| PATIENT_DAMAGE | CONTACT | 5.064 | 4.735 | +0.329 | 203 | no |
| PATIENT_DAMAGE | ELITE | 5.072 | 4.817 | +0.255 | 307 | no |
| MIXED | VULNERABLE | 4.786 | 4.607 | +0.179 | 1010 | no |
| IMPATIENT_WEAK | AVERAGE | 4.772 | 4.607 | +0.165 | 1250 | no |
| IMPATIENT_WEAK | WILD_POWER | 4.667 | 4.562 | +0.105 | 189 | no |
| IMPATIENT_POWER | AVERAGE | 4.548 | 4.457 | +0.090 | 546 | no |
| MIXED | CONTACT | 4.370 | 4.306 | +0.064 | 828 | no |
| PATIENT_CONTACT | CONTACT | 4.301 | 4.245 | +0.056 | 93 | no |
| PATIENT_CONTACT | VULNERABLE | 4.600 | 4.547 | +0.053 | 125 | no |
| PATIENT_DAMAGE | AVERAGE | 4.911 | 4.868 | +0.044 | 1141 | no |
| MIXED | WILD_POWER | 4.431 | 4.393 | +0.038 | 752 | no |
| MIXED | ELITE | 4.365 | 4.388 | -0.022 | 953 | no |
| MIXED | AVERAGE | 4.383 | 4.438 | -0.056 | 4265 | no |
| PATIENT_CONTACT | AVERAGE | 4.272 | 4.378 | -0.106 | 552 | no |
| IMPATIENT_WEAK | VULNERABLE | 4.650 | 4.776 | -0.126 | 340 | no |
| IMPATIENT_POWER | VULNERABLE | 4.434 | 4.626 | -0.192 | 136 | no |
| IMPATIENT_POWER | CONTACT | 4.131 | 4.325 | -0.194 | 107 | no |
| PATIENT_DAMAGE | WILD_POWER | 4.512 | 4.822 | -0.310 | 244 | no |
| IMPATIENT_WEAK | ELITE | 4.162 | 4.556 | -0.394 | 240 | no |
| IMPATIENT_WEAK | CONTACT | 4.073 | 4.474 | -0.401 | 245 | no |
| PATIENT_CONTACT | WILD_POWER | 3.908 | 4.332 | -0.424 | 109 | no |
| PATIENT_DAMAGE | VULNERABLE | 4.586 | 5.037 | -0.451 | 251 | no |
| IMPATIENT_POWER | ELITE | 3.757 | 4.406 | -0.649 | 107 | no |

## Phase 5: Validation (2024)
- Validation game-halves: 7,748
- Directional consistency vs discovery: 40.0%
- Max valid residual: 1.031
- **VALIDATION: FAIL**

### Interaction Table (Validation)
| Lineup | SP Profile | Actual | Expected | Residual | N |
|--------|------------|--------|----------|----------|---|
| PATIENT_CONTACT | WILD_POWER | 5.364 | 4.332 | +1.031 | 55 |
| IMPATIENT_POWER | CONTACT | 5.238 | 4.325 | +0.914 | 63 |
| PATIENT_CONTACT | CONTACT | 4.522 | 4.245 | +0.277 | 46 |
| IMPATIENT_POWER | ELITE | 4.649 | 4.406 | +0.243 | 114 |
| IMPATIENT_POWER | VULNERABLE | 4.817 | 4.626 | +0.190 | 109 |
| PATIENT_CONTACT | ELITE | 4.506 | 4.327 | +0.179 | 83 |
| IMPATIENT_POWER | AVERAGE | 4.598 | 4.457 | +0.141 | 480 |
| MIXED | ELITE | 4.504 | 4.388 | +0.116 | 534 |
| PATIENT_DAMAGE | CONTACT | 4.830 | 4.735 | +0.095 | 53 |
| MIXED | WILD_POWER | 4.488 | 4.393 | +0.095 | 428 |
| PATIENT_CONTACT | AVERAGE | 4.461 | 4.378 | +0.084 | 373 |
| PATIENT_DAMAGE | VULNERABLE | 5.056 | 5.037 | +0.020 | 71 |
| MIXED | AVERAGE | 4.456 | 4.438 | +0.017 | 2488 |
| MIXED | CONTACT | 4.307 | 4.306 | +0.002 | 319 |
| PATIENT_DAMAGE | AVERAGE | 4.862 | 4.868 | -0.005 | 421 |
| MIXED | VULNERABLE | 4.584 | 4.607 | -0.023 | 553 |
| IMPATIENT_WEAK | CONTACT | 4.325 | 4.474 | -0.149 | 83 |
| PATIENT_DAMAGE | ELITE | 4.594 | 4.817 | -0.222 | 106 |
| IMPATIENT_WEAK | AVERAGE | 4.129 | 4.607 | -0.478 | 682 |
| IMPATIENT_WEAK | WILD_POWER | 3.991 | 4.562 | -0.571 | 110 |
| IMPATIENT_WEAK | VULNERABLE | 4.052 | 4.776 | -0.724 | 154 |
| PATIENT_CONTACT | VULNERABLE | 3.768 | 4.547 | -0.778 | 95 |
| IMPATIENT_POWER | WILD_POWER | 3.617 | 4.412 | -0.795 | 94 |
| PATIENT_DAMAGE | WILD_POWER | 3.945 | 4.822 | -0.877 | 91 |
| IMPATIENT_WEAK | ELITE | 3.678 | 4.556 | -0.878 | 143 |

## Phase 7: Final Verdict
**NO-GO**
Discovery showed signal but validation failed directional consistency.

---
PIT-safety confirmed | Discovery cuts frozen | Excluded sources avoided