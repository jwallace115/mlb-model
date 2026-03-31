# OVER Scanner Wave 1 — Report

Dataset: 4855 games (2024-2025), 4666 non-push
V1 OVER-lean (p_under<0.45): N=1205, over%=0.520, ROI=-0.8%

## Standalone Triage

| Signal | Name | Best Bucket | N | Over% | ROI | Stable | Corr | Verdict |
|--------|------|------------|---|-------|-----|--------|------|---------|
| OV016 | high_pitch_count_fatigue | bot_10 | 476 | 0.546 | +4.3% | STABLE | CLEAN(-0.137) | **PROMOTE** |
| OV019 | era_spike_recent | top_10 | 463 | 0.518 | -1.0% | STABLE | CLEAN(0.063) | **SHELVE** |
| OV041 | short_starter_x_weak_bullpen | top_20 | 938 | 0.505 | -3.5% | STABLE | CLEAN(0.115) | **SHELVE** |
| OV043 | high_leverage_bullpen_overuse | top_10 | 457 | 0.521 | -0.6% | STABLE | CLEAN(0.074) | **PROMOTE** |
| OV050 | short_starter_x_extra_innings | bot_10 | 4427 | 0.492 | -6.1% | STABLE | CLEAN(0.012) | **PROMOTE** |
| OV051 | bullpen_xfip_deviation | bot_20 | 943 | 0.486 | -7.3% | MIXED | PARTIAL(0.264) | **SHELVE** |
| OV100 | combined_bullpen_workload | bot_10 | 497 | 0.513 | -2.0% | MIXED | CLEAN(0.038) | **INVESTIGATE** |
| OV115 | pitch_count_x_patient | bot_10 | 470 | 0.509 | -2.9% | STABLE | CLEAN(-0.015) | **SHELVE** |
| OV001 | bb_x_hard_hit | bot_20 | 940 | 0.507 | -3.1% | MIXED | CLEAN(0.034) | **SHELVE** |
| OV021 | low_k_x_contact | top_20 | 930 | 0.524 | -0.0% | STABLE | PARTIAL(0.268) | **INVESTIGATE** |

## V1 OVER-Lean Interaction

| Signal | Name | Bucket | N | Over% | ROI | V1 ROI | Lift | 2024 | 2025 |
|--------|------|--------|---|-------|-----|--------|------|------|------|
| OV043 | high_leverage_bullpen_overuse | fav_10 | 121 | 0.562 | +7.3% | -0.8% | +8.1pp | +7.8 | +7.0 |
| OV016 | high_pitch_count_fatigue | fav_20 | 227 | 0.559 | +6.8% | -0.8% | +7.6pp | -3.7 | +10.8 |
| OV001 | bb_x_hard_hit | fav_20 | 241 | 0.552 | +5.4% | -0.8% | +6.2pp | +8.8 | +8.4 |
| OV019 | era_spike_recent | fav_10 | 121 | 0.545 | +4.1% | -0.8% | +5.0pp | +4.4 | +2.5 |
| OV050 | short_starter_x_extra_innings | fav_10 | 70 | 0.529 | +0.9% | -0.8% | +1.7pp | +3.5 | +1.0 |
| OV041 | short_starter_x_weak_bullpen | fav_20 | 241 | 0.515 | -1.8% | -0.8% | -1.0pp | +1.1 | +4.0 |
| OV100 | combined_bullpen_workload | fav_30 | 360 | 0.514 | -1.9% | -0.8% | -1.1pp | +3.5 | -7.0 |
| OV115 | pitch_count_x_patient | fav_30 | 362 | 0.511 | -2.4% | -0.8% | -1.6pp | +0.4 | +2.5 |
| OV021 | low_k_x_contact | fav_30 | 362 | 0.506 | -3.5% | -0.8% | -2.7pp | -1.8 | -5.3 |
| OV051 | bullpen_xfip_deviation | fav_10 | 118 | 0.500 | -4.5% | -0.8% | -3.7pp | -2.5 | +4.1 |

## Leaderboard

| Rank | Signal | Standalone | V1 Lift | V1 N | Stable | Corr | Rec |
|------|--------|-----------|---------|------|--------|------|-----|
| 1 | OV043 (high_leverage_bullpen_overuse) | -0.6% | +8.1pp | 121 | STABLE | CLEAN | **PROMOTE** |
| 2 | OV016 (high_pitch_count_fatigue) | +4.3% | +7.6pp | 227 | STABLE | CLEAN | **PROMOTE** |
| 3 | OV001 (bb_x_hard_hit) | -3.1% | +6.2pp | 241 | MIXED | CLEAN | **PROMOTE** |
| 4 | OV019 (era_spike_recent) | -1.0% | +5.0pp | 121 | STABLE | CLEAN | **PROMOTE** |
| 5 | OV050 (short_starter_x_extra_innings) | -6.1% | +1.7pp | 70 | STABLE | CLEAN | **PROMOTE** |
| 6 | OV041 (short_starter_x_weak_bullpen) | -3.5% | -1.0pp | 241 | STABLE | CLEAN | **SHELVE** |
| 7 | OV100 (combined_bullpen_workload) | -2.0% | -1.1pp | 360 | MIXED | CLEAN | **HOLD** |
| 8 | OV115 (pitch_count_x_patient) | -2.9% | -1.6pp | 362 | STABLE | CLEAN | **SHELVE** |
| 9 | OV021 (low_k_x_contact) | -0.0% | -2.7pp | 362 | STABLE | PARTIAL | **HOLD** |
| 10 | OV051 (bullpen_xfip_deviation) | -7.3% | -3.7pp | 118 | MIXED | PARTIAL | **SHELVE** |

## Safety Checks

### OV043: high_leverage_bullpen_overuse
- Available: N=1205, over%=0.520, ROI=-0.8%
- Tail OK: N=121
- Direction OK: 2024=+7.8pp, 2025=+7.0pp

### OV016: high_pitch_count_fatigue
- Available: N=1205, over%=0.520, ROI=-0.8%
- Tail OK: N=227
- **REVERSAL**: 2024=-3.7pp, 2025=+10.8pp

### OV001: bb_x_hard_hit
- Available: N=1205, over%=0.520, ROI=-0.8%
- Tail OK: N=241
- Direction OK: 2024=+8.8pp, 2025=+8.4pp

## Final Answers

### Q1: Standalone value?
- PROMOTE: OV016 high_pitch_count_fatigue, OV043 high_leverage_bullpen_overuse, OV050 short_starter_x_extra_innings
- INVESTIGATE: OV100 combined_bullpen_workload, OV021 low_k_x_contact
- SHELVE: OV019 era_spike_recent, OV041 short_starter_x_weak_bullpen, OV051 bullpen_xfip_deviation, OV115 pitch_count_x_patient, OV001 bb_x_hard_hit

### Q2: V1 OVER-lean amplifiers?
- OV043 (high_leverage_bullpen_overuse): +8.1pp, N=121
- OV016 (high_pitch_count_fatigue): +7.6pp, N=227
- OV001 (bb_x_hard_hit): +6.2pp, N=241
- OV019 (era_spike_recent): +5.0pp, N=121

### Q3: Strongest interaction candidate?
- **OV043 (high_leverage_bullpen_overuse)**: +8.1pp lift

## Recommended Next Deep Analysis Candidates

1. **OV043 (high_leverage_bullpen_overuse)** — V1 lift +8.1pp, standalone -0.6%, STABLE
2. **OV016 (high_pitch_count_fatigue)** — V1 lift +7.6pp, standalone +4.3%, STABLE
3. **OV001 (bb_x_hard_hit)** — V1 lift +6.2pp, standalone -3.1%, MIXED


## Critical Assessment

### Year-Level Stability (V1 OVER-lean top-20% interaction)

| Signal | Pooled Lift | 2024 Lift | 2025 Lift | Assessment |
|--------|------------|----------|----------|------------|
| **OV043** bullpen_overuse | **+8.1pp** | **+7.8pp** | **+7.0pp** | **STABLE — best candidate** |
| **OV001** bb_x_hard_hit | **+6.2pp** | **+8.8pp** | **+8.4pp** | **STABLE — strong both years** |
| OV016 pitch_count_fatigue | +7.6pp | -3.7pp | +10.8pp | MIXED — 2024 negative |
| OV019 era_spike_recent | +5.0pp | +4.4pp | +2.5pp | Stable direction, modest lift |

### Top 3 Candidates After Critical Filtering

**1. OV043 (high_leverage_bullpen_overuse)** — Best overall
- V1 OVER-lean + top-10% bullpen workload: +8.1pp lift, N=121
- Year-stable: +7.8pp (2024) / +7.0pp (2025)
- Market CLEAN (r=0.074)
- Mechanism: heavily-used bullpens behind V1 OVER-lean environments create late-inning scoring cascades
- Concern: N=121 is adequate but not large; top-10% bucket

**2. OV001 (bb_x_hard_hit)** — Most stable
- V1 OVER-lean + top-20% BB×HH interaction: +6.2pp lift, N=241
- Year-stable: +8.8pp (2024) / +8.4pp (2025) — remarkably consistent
- Market CLEAN (r=0.034)
- Mechanism: walk-prone pitchers who also allow hard contact create compounding baserunner cascades
- Concern: standalone MIXED direction, but V1 interaction is the target use case
- Largest N of any candidate (241 pooled)

**3. OV019 (era_spike_recent)** — Supporting evidence
- V1 OVER-lean + top-10% recent ERA spike: +5.0pp lift, N=121
- Stable: +4.4pp / +2.5pp — positive both years but 2025 is weaker
- Market CLEAN (r=0.063)
- Mechanism: pitchers whose recent ERA has spiked vs season baseline are regression-flagged

### Signals Definitively Shelved

| Signal | Why |
|--------|-----|
| OV041 short_starter_x_weak_bp | Negative V1 lift (-1.0pp) |
| OV050 extra_innings_yesterday | Only 247 nonzero games; too sparse |
| OV051 bullpen_xfip_deviation | Negative V1 lift (-3.7pp), MIXED stability, PARTIAL corr |
| OV100 bullpen_workload_both | Negative V1 lift (-1.1pp), MIXED stability |
| OV115 pitch_count_x_patient | Negative V1 lift (-1.6pp) |
| OV021 low_k_x_contact | Negative V1 lift (-2.7pp), PARTIAL market corr |
| OV016 pitch_count_fatigue | Year-MIXED (2024 = -3.7pp) despite strong pooled number |

### Recommended Next Deep Analysis Candidates

1. **OV043 (high_leverage_bullpen_overuse)** — Stable +7-8pp lift both years, CLEAN market, clear mechanism
2. **OV001 (bb_x_hard_hit)** — Most stable (+8.8/+8.4pp), largest N (241), independent from market
3. **OV019 (era_spike_recent)** — Supporting candidate if OV043/OV001 confirm in deep analysis
