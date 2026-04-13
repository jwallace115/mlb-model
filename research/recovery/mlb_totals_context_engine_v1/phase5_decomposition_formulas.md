# Phase 5 - Decomposition Formulas
## MLB Totals Context Engine V1
## DISCOVERY DATA ONLY (2022-2023)

### Formula Development Rules
1. All formulas developed using DISCOVERY data only (2022-2023, n=4,860 games)
2. Maximum 3-4 inputs per component
3. Normalization anchored to discovery distribution (5th-95th percentile range)
4. Bucket thresholds set at discovery tertiles (33rd/67th percentile)
5. These formulas and thresholds are FROZEN - not adjusted on validation or OOS

---

### Formula 1: Baseline Run Environment (BRE)

**Inputs (3):**
- park_factor_runs: raw value (94-117 range), from game_table
- lineup_ops: avg(home_obp_r10 + home_slg_r10 + away_obp_r10 + away_slg_r10) / 2, from hitter rolling
- umpire_over_rate: probability umpire calls over, from game_table

**Formula:**
```
BRE = 0.40 * norm(park_factor_runs) + 0.35 * norm(lineup_ops) + 0.25 * norm(umpire_over_rate)
```
Where norm() = percentile rank in [0,100] anchored to discovery 5th-95th percentile.

**Buckets (frozen from discovery):**
- LOW: BRE < 39.41
- MEDIUM: 39.41 <= BRE <= 55.45
- HIGH: BRE > 55.45

**Discovery validation:** corr(BRE, actual_total) = 0.0980

**Rationale:** Park factor is the single strongest structural determinant of run environment. Lineup rolling OPS captures current offensive state. Umpire over-rate adds the officiating layer. Three inputs, no redundancy.

---

### Formula 2: Early Scoring Pressure (ESP)

**Inputs (3):**
- home_sp_fragility: composite of er_per9_r5 (50%), inverted avg_ip_r5 (30%), short_exit_r5 (20%)
- away_sp_fragility: same for away starter
- lineup_ops: same as BRE (opponent quality facing fragile starters)

**SP Fragility Sub-formula:**
```
SP_fragility = 0.50 * norm(er_per9_r5) + 0.30 * (100 - norm(avg_ip_r5)) + 0.20 * norm(short_exit_r5)
```

**Formula:**
```
ESP = 0.50 * avg(home_sp_fragility, away_sp_fragility) + 0.30 * norm(lineup_ops) + 0.20 * BRE
```

**Buckets:**
- LOW: ESP < 36.03
- MEDIUM: 36.03 <= ESP <= 49.89
- HIGH: ESP > 49.89

**Discovery validation:** corr(ESP, actual_f5_total) = 0.0911

---

### Formula 3: Late Scoring Pressure (LSP)

**Inputs (3):**
- home_bp_instability: norm(bp_pit_last3) * 0.60 + (1 - hl_avail) * 100 * 0.40
- away_bp_instability: same for away bullpen
- avg_sp_fragility: fragile starters lead to more bullpen usage and instability

**Formula:**
```
LSP = 0.45 * avg(home_bp_instability, away_bp_instability) + 0.30 * norm(lineup_ops) + 0.25 * avg_sp_fragility
```

**Buckets:**
- LOW: LSP < 43.08
- MEDIUM: 43.08 <= LSP <= 54.37
- HIGH: LSP > 54.37

**Discovery validation:** corr(LSP, late_runs = total - f5_total) = 0.0490

---

### Formula 4: Starter Stability (SS)

**Inputs (3):**
- avg_ip_r5: rolling 5-start average innings pitched (depth)
- k_rate_r5: rolling 5-start strikeout rate (dominance)
- bb_rate_r5: rolling 5-start walk rate (control, inverted)

**Per-Starter Sub-formula:**
```
SP_stability = 0.40 * norm(avg_ip_r5) + 0.35 * norm(k_rate_r5) + 0.25 * (100 - norm(bb_rate_r5))
```

**Formula:**
```
SS = avg(home_sp_stability, away_sp_stability)
BOTH_STABLE_flag = (home_sp_stability > 55) AND (away_sp_stability > 55)
```

**Buckets:**
- FRAGILE: SS < 45.92
- AVERAGE: 45.92 <= SS <= 57.09
- STABLE: SS > 57.09

**Discovery validation:** corr(SS, combined_actual_IP) = 0.2151

---

### Formula 5: Bullpen Stability (BS)

**Inputs (3):**
- rel_last3: relievers used in last 3 games (inverted: more = less stable)
- bp_pit_last3: bullpen pitches in last 3 games (inverted)
- hl_avail: high-leverage closer available (binary)

**Per-Team Sub-formula:**
```
BP_stability = 0.40 * (100 - norm(rel_last3)) + 0.40 * (100 - norm(bp_pit_last3)) + 0.20 * hl_avail * 100
```

**Formula:**
```
BS = avg(home_bp_stability, away_bp_stability)
```

**Buckets:**
- UNSTABLE: BS < 38.86
- NEUTRAL: 38.86 <= BS <= 53.26
- STABLE: BS > 53.26

**Discovery validation:** corr(BS, late_runs) = -0.0494 (expected negative)

---

### Formula 6: Weather and Park Lift (WPL)

**Inputs (3):**
- park_factor_runs: structural park run factor
- temperature: game-day temperature (dome=no effect)
- wind_speed: wind speed (dome=no effect; direction data insufficient for signed effect)

**Formula:**
```
park_deviation = (park_factor_runs - 100) / 3
temp_effect = (temperature - 65) / 10
wind_effect = wind_speed * 0.1  (outdoor only; direction not signed)

WPL = IF dome_or_closed:
    park_deviation
ELSE:
    0.40 * park_deviation + 0.40 * temp_effect + 0.20 * wind_effect
```

**Buckets:**
- SUPPRESSED: WPL < -1.0
- NEUTRAL: -1.0 <= WPL <= 1.0
- LIFTED: WPL > 1.0

**Note:** Wind direction effect is not signed due to missing park bearing data. This is a known limitation. Wind is treated as volatility-additive, not directional. Future research: add CF bearing by stadium to produce signed wind component.

**Discovery validation:** corr(WPL, actual_total) = 0.1542

---

### Formula 7: Total Compression / Volatility State (TCV)

**Inputs (3):**
- sp_variance: avg of norm(ip_std_r5) for both starters (captures start-to-start volatility)
- avg_bp_instability: same as LSP component
- ESP/SS spread: |ESP - SS| as a conflict signal (fragile SP + stable offense = high variance)

**Formula:**
```
TCV = 0.40 * sp_variance + 0.35 * avg_bp_instability + 0.25 * norm(|ESP - SS|)
```

**Buckets:**
- COMPRESSED: TCV < 42.46
- BALANCED: 42.46 <= TCV <= 53.32
- VOLATILE: TCV > 53.32

**Discovery validation:** actual_total std by TCV bucket:
tcv_bucket
low     4.480481
mid     4.505668
high    4.510264

---

### Formula 8: Market Path Shape (MPS)

**Status: DATA-BLOCKED**

Open total lines are unavailable for all seasons (2022-2025). The historical Odds API pull only captured closing snapshots. Without an open-to-close movement, no Market Path Shape can be computed.

For 2024-2025, CLV is available (closing line value = close - decision line) but the decision line itself is also the closing line. This does not provide directional movement data.

**Decision:** MPS output is classified as DATA-BLOCKED. The output stub is preserved in the engine output table with value "DATA-BLOCKED" for all games. This output is reserved for future data collection when opening lines become available.

---

### Frozen Thresholds Summary

| Output | Low Threshold | High Threshold |
|--------|--------------|----------------|
| BRE | < 39.41 | > 55.45 |
| ESP | < 36.03 | > 49.89 |
| LSP | < 43.08 | > 54.37 |
| SS | < 45.92 | > 57.09 |
| BS | < 38.86 | > 53.26 |
| WPL | < -1.0 | > 1.0 |
| TCV | < 42.46 | > 53.32 |
| MPS | DATA-BLOCKED | DATA-BLOCKED |

---

Built: 2026-04-12 | Discovery only: 2022-2023
