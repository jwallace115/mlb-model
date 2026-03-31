# MLB Signal Scanner Report
Scanner run: 2024-2025 full-game totals
Games: 4666 non-push | Signals: 25

## Expected Directions
| Signal | Name | Direction |
|--------|------|----------|
| S01 | kbb_gap | UNDER |
| S02 | csw_gap | UNDER |
| S03 | xfip_gap | UNDER |
| S04 | velo_delta | UNDER |
| S05 | whiff_gap | UNDER |
| S06 | pitch_efficiency | UNDER |
| S07 | gb_gap | FLAT |
| S08 | starter_reliever_gap | UNDER |
| S09 | k_drought | OVER |
| S10 | tstart_fatigue | OVER |
| S11 | umpire_command | UNDER |
| S12 | combined_pitcher_score | UNDER |
| S13 | walk_compressor | OVER |
| S14 | count_exploit | FLAT |
| S15 | bullpen_xfip_gap | UNDER |
| S16 | bullpen_workload | UNDER |
| S17 | bullpen_fatigue | OVER |
| S18 | flyball_park | OVER |
| S19 | wind_flyball | OVER |
| S20 | day_after_night | UNDER |
| S21 | rest_diff | UNDER |
| S22 | wrc_gap | OVER |
| S23 | k_drought_regression | FLAT |
| S24 | interleague | OVER |
| S25 | blowout_revenge | OVER |

## Full Results (sorted by pooled p-value)
| Signal | Name | p_pool | Coef | Dir | Perm% | xFIP_corr | Verdict |
|--------|------|--------|------|-----|-------|-----------|--------|
| S12 | combined_pitcher_score | 0.0000 | 0.02698 | CORRECT | 100 | -0.025 | **CANDIDATE** |
| S23 | k_drought_regression | 0.0142 | -0.01605 | FLAT | 72 | 0.021 | **MARGINAL** |
| S18 | flyball_park | 0.0634 | 0.01215 | WRONG | 13 | -0.119 | **MARGINAL** |
| S21 | rest_diff | 0.0811 | 0.01142 | CORRECT | 45 | 0.043 | **MARGINAL** |
| S13 | walk_compressor | 0.1176 | -0.01024 | CORRECT | 97 | 0.027 | **MARGINAL** |
| S04 | velo_delta | 0.1297 | 0.00992 | CORRECT | 84 | 0.023 | **MARGINAL** |
| S19 | wind_flyball | 0.1527 | 0.00936 | WRONG | 9 | 0.032 | **MARGINAL** |
| S15 | bullpen_xfip_gap | 0.1980 | 0.00843 | CORRECT | 94 | 0.261 | **MARGINAL** |
| S20 | day_after_night | 0.2128 | 0.00816 | CORRECT | 78 | -0.021 | **MARGINAL** |
| S10 | tstart_fatigue | 0.2174 | 0.00807 | WRONG | 5 | -0.030 | **NO_SIGNAL** |
| S14 | count_exploit | 0.2383 | -0.00772 | FLAT | 14 | 0.000 | **NO_SIGNAL** |
| S02 | csw_gap | 0.3782 | 0.00804 | CORRECT | 94 | 0.389 | **NO_SIGNAL** |
| S05 | whiff_gap | 0.3826 | 0.00796 | CORRECT | 93 | 0.428 | **NO_SIGNAL** |
| S11 | umpire_command | 0.4437 | -0.00501 | WRONG | 64 | -0.010 | **MARGINAL** |
| S09 | k_drought | 0.5352 | 0.00558 | WRONG | 47 | -0.004 | **NO_SIGNAL** |
| S24 | interleague | 0.5444 | -0.00397 | CORRECT | 88 | 0.005 | **NO_SIGNAL** |
| S01 | kbb_gap | 0.5713 | 0.00489 | CORRECT | 94 | 0.493 | **NO_SIGNAL** |
| S16 | bullpen_workload | 0.6701 | 0.00279 | CORRECT | 50 | -0.019 | **NO_SIGNAL** |
| S08 | starter_reliever_gap | 0.7484 | -0.00210 | WRONG | 43 | 0.983 | **NO_SIGNAL** |
| S06 | pitch_efficiency | 0.8834 | 0.00127 | CORRECT | 60 | 0.133 | **MARGINAL** |
| S03 | xfip_gap | 0.9372 | -0.00052 | WRONG | 55 | 1.000 | **NO_SIGNAL** |
| S22 | wrc_gap | 0.9595 | 0.00033 | WRONG | 12 | 0.212 | **NO_SIGNAL** |
| S17 | bullpen_fatigue | 0.9774 | 0.00019 | WRONG | 58 | -0.014 | **NO_SIGNAL** |
| S07 | gb_gap | 0.9920 | 0.00009 | FLAT | 82 | 0.059 | **NO_SIGNAL** |
| S25 | blowout_revenge | N/A | N/A | LOW_COVERAGE | N/A | N/A | **NO_SIGNAL** |

## Candidates
### S12: combined_pitcher_score
- Pooled: coef=0.02698, p=0.0000
- 2025: coef=0.02711, p=0.0032
- Permutation: 100%
- xFIP correlation: -0.025 (independent)

## Independence Check
| Signal | xFIP Correlation | Dependent? |
|--------|-----------------|------------|
| xfip_gap | 1.000 | YES |
| starter_reliever_gap | 0.983 | YES |
| kbb_gap | 0.493 | no |
| whiff_gap | 0.428 | no |
| csw_gap | 0.389 | no |
| bullpen_xfip_gap | 0.261 | no |
| wrc_gap | 0.212 | no |
| pitch_efficiency | 0.133 | no |
| gb_gap | 0.059 | no |
| rest_diff | 0.043 | no |
| wind_flyball | 0.032 | no |
| walk_compressor | 0.027 | no |
| velo_delta | 0.023 | no |
| k_drought_regression | 0.021 | no |
| interleague | 0.005 | no |
| count_exploit | 0.000 | no |
| k_drought | -0.004 | no |
| umpire_command | -0.010 | no |
| bullpen_fatigue | -0.014 | no |
| bullpen_workload | -0.019 | no |
| day_after_night | -0.021 | no |
| combined_pitcher_score | -0.025 | no |
| tstart_fatigue | -0.030 | no |
| flyball_park | -0.119 | no |
| blowout_revenge | N/A | no |

## Coverage Issues
- kbb_gap: 57.5% coverage
- csw_gap: 51.5% coverage
- whiff_gap: 51.5% coverage
- pitch_efficiency: 57.5% coverage
- gb_gap: 57.5% coverage
- k_drought: 52.9% coverage


## S12 Over Symmetry Test
- Top 20% UNDER ROI: +5.8%
- Bottom 20% OVER ROI: -0.7%
- Ratio: 0.12
- **Verdict: ASYMMETRIC**

## S12 × V1 Interaction
- B (V1 only): ROI=+16.6%
- C (S12 only): ROI=+7.3%
- D (V1+S12): ROI=+19.0%
- **Verdict: AMPLIFIER**


## S12 Model Error Reduction Test

| Group | N | MAE | Brier | mean p_under | mean actual |
|-------|---|-----|-------|-------------|-------------|
| G1: All games | 3913 | 0.4904 | 0.2470 | 0.5226 | 0.5170 |
| G2: V1 p_under>0.57 | 984 | 0.4719 | 0.2395 | 0.6233 | 0.6108 |
| G3: V1>0.57 + S12 top20 | 242 | 0.4707 | 0.2377 | 0.6220 | 0.6240 |
| G4: V1>0.57 + S12 NOT top20 | 742 | 0.4722 | 0.2401 | 0.6237 | 0.6065 |

**Bias correction verdict: CONFIRMED**

**Market structure check: WARNING**

- Closing total: G3=8.13 vs G4=8.90 (diff=-0.77)
- Under price: G3=-102.1 vs G4=-101.9 (diff=-0.2)


## Marginal Signal Triage

### Precheck — Signal Distribution
| Signal | N | Mean | Std | p10 | p50 | p90 | Flag |
|--------|---|------|-----|-----|-----|-----|------|
| S13 | 4666 | 0.1597 | 0.0471 | 0.1040 | 0.1570 | 0.2166 |  |
| S15 | 4666 | 0.0000 | 0.1241 | -0.1625 | 0.0020 | 0.1590 |  |
| S04 | 4666 | 0.0043 | 0.5771 | -0.6833 | 0.0000 | 0.6789 |  |
| S20 | 4666 | 0.5084 | 0.5000 | 0.0000 | 1.0000 | 1.0000 |  |

### Test 1 — Extremes

### Verdicts
| Signal | Name | Extreme | Direction | Market Corr | Verdict | Reason |
|--------|------|---------|-----------|-------------|---------|--------|
| S13 | walk_compressor | no | CONSISTENT | CLEAN (+0.127) | **SHELVE** | no extreme bucket (best resid=-0.022) |
| S15 | bullpen_xfip_gap | YES | CONSISTENT | PARTIAL (-0.242) | **PROMOTE** | all gates passed |
| S04 | velo_delta | no | CONSISTENT | CLEAN (+0.009) | **SHELVE** | no extreme bucket (best resid=-0.023) |
| S20 | day_after_night | no | CONSISTENT | CLEAN (+0.072) | **SHELVE** | no extreme bucket (best resid=-0.024) |


## Phase 2-5 Data Signal Triage

Base dataset: 4666 non-push games

### Coverage
- D01 drs_gap: 100% — testable
- D02 infield_drs_gap: 0% — skipped (low coverage)
- D03 outfield_drs_gap: 0% — skipped (low coverage)
- B01 sprint_speed_gap: 0% — skipped (low coverage)
- B02 bsr_gap: 0% — skipped (low coverage)
- B03 sb_success_gap: 97% — testable
- C01 home_catcher_framing: 0% — skipped (low coverage)
- C02 framing_gap: 0% — skipped (low coverage)
- C03 framing_interaction: 0% — skipped (low coverage)
- L01 lineup_wrc_gap: 100% — testable
- L02 lineup_top3_obp_gap: 0% — skipped (low coverage)
- L03 lineup_hand_mismatch: 0% — skipped (low coverage)

### Results
| Signal | Name | Verdict | Reason |
|--------|------|---------|--------|
| D01 | drs_gap | **PROMOTE** | all gates passed |
| D02 | infield_drs_gap | SKIPPED | insufficient coverage |
| D03 | outfield_drs_gap | SKIPPED | insufficient coverage |
| B01 | sprint_speed_gap | SKIPPED | insufficient coverage |
| B02 | bsr_gap | SKIPPED | insufficient coverage |
| B03 | sb_success_gap | **SHELVE** | no extreme bucket; direction MIXED |
| C01 | home_catcher_framing | SKIPPED | insufficient coverage |
| C02 | framing_gap | SKIPPED | insufficient coverage |
| C03 | framing_interaction | SKIPPED | insufficient coverage |
| L01 | lineup_wrc_gap | **SHELVE** | no extreme bucket; direction MIXED |
| L02 | lineup_top3_obp_gap | SKIPPED | insufficient coverage |
| L03 | lineup_hand_mismatch | SKIPPED | insufficient coverage |

**Promoted: 1**


## Statcast Pitch-Level Signal Triage

Statcast coverage: 755/4666 games (16.2%) with both starters

### Results
| Signal | Name | Verdict | Reason |
|--------|------|---------|--------|
| P01 | hard_hit_gap | **SHELVE** | dir=MIXED |
| P02 | barrel_gap | **SHELVE** | dir=MIXED |
| P03 | chase_gap | **PROMOTE** | all gates passed |
| P04 | zone_gap | **SHELVE** | dir=MIXED |
| P05 | whiff_gap | **SHELVE** | dir=MIXED |
| P06 | exit_velo_gap | **PROMOTE** | all gates passed |
| P07 | spin_drop_home | **SKIP** | N=0 too low |
| P08 | extension_gap | **PROMOTE** | all gates passed |
| P09 | hard_hit_x_park | **PROMOTE** | all gates passed |
| P10 | whiff_x_csw | **PROMOTE** | all gates passed |

**Promoted: 5**


## Statcast Coverage Bias Audit

Group A (with Statcast): 755 | Group B (without): 3911
Severe bias detected: NO

Bootstrap verdicts:
- P10 (whiff_x_csw): see console
- P03 (chase_gap): see console


## Bullpen Fatigue + Schedule Triage

Base dataset: 4855 games (2024-2025), 4666 non-push
Baseline: mean_error=+0.442, under_rate=50.9%

### Feature Coverage
| Feature | N | Coverage |
|---------|---|----------|
| bullpen_ip_last2days_home | 4827 | 99.4% |
| bullpen_ip_last2days_away | 4826 | 99.4% |
| bullpen_ip_last3days_home | 4827 | 99.4% |
| bullpen_ip_last3days_away | 4826 | 99.4% |
| closer_used_last2days_home | 4827 | 99.4% |
| closer_used_last2days_away | 4826 | 99.4% |
| days_rest_home | 4855 | 100.0% |
| days_rest_away | 4855 | 100.0% |
| road_trip_game_num_away | 4855 | 100.0% |
| timezone_change_away | 4855 | 100.0% |

### Signal Definitions
| Signal | Formula | Hypothesis |
|--------|---------|-----------|
| BF01 | bp_ip_last2d_away − bp_ip_last2d_home | OVER (away fatigue) |
| BF02 | closer_used_last2d_away flag | OVER (closer unavail) |
| BF03 | bp_ip_last3d_home / season_avg_daily_bp_ip | OVER (home BP taxed) |
| ST01 | days_rest_home − days_rest_away | UNKNOWN |
| ST02 | road_trip_game_num_away ≥ 6 | UNDER |
| ST03 | timezone_change_away ≥ 2 | UNDER |

### Triage Results (residual = bucket error − baseline error)
| Signal | Name | N | Best Bucket | Resid | Under% | Mkt Corr | Year Stable | Verdict |
|--------|------|---|-------------|-------|--------|----------|-------------|---------|
| BF01 | bullpen_ip_gap_2d | 4611 | bot_20 | +0.091 | 51.4% | -0.051 | STABLE — but slopes p>0.43 | **SHELVE** |
| BF02 | closer_unavail_away | 4637 | flag=0 | +0.084 | 49.8% | -0.001 | UNSTABLE — flips 2024→2025 | **SHELVE** |
| BF03 | bp_workload_3d_home | 4638 | top_20 | -0.087 | 52.7% | +0.041 | UNSTABLE — 2024 resid=-0.26, 2025 resid=+0.04 | **SHELVE** |
| ST01 | rest_gap | 4666 | top_20 | -0.244 | 55.0% | -0.009 | UNSTABLE — N=200, slope flips sign | **SHELVE** |
| ST02 | road_trip_6plus_away | 4666 | flag=1 | -0.276 | 53.4% | +0.039 | **STABLE** — 2024 resid=-0.20, 2025 resid=-0.35 | **PROMOTE** |
| ST03 | tz_change_2plus_away | 4666 | flag=1 | +0.140 | 46.5% | -0.007 | UNSTABLE — flips 2024→2025 | **SHELVE** |

**Promoted: 1 (ST02)**

### ST02 Statistical Tests
- t-test: t=−2.529, p=0.0115
- Permutation (10K): obs_diff=−0.367, perm%=0.5% (99.5th percentile)
- Direction: long road trips → UNDER (games go under by 0.28 runs more than baseline)
- Consistent both years: 2024 resid=−0.20, 2025 resid=−0.35

### Year-by-Year Detail

**BF01: bullpen_ip_gap_2d**
| Year | N | Slope | p-value | Top20 Resid | Bot20 Resid |
|------|---|-------|---------|-------------|-------------|
| 2024 | 2400 | +0.023 | 0.436 | +0.124 | +0.037 |
| 2025 | 2400 | +0.019 | 0.552 | -0.045 | +0.135 |
Note: OLS slopes positive (favoring OVER hyp) but p>0.43 — no signal.

**BF02: closer_unavail_away**
| Year | Flag=1 N | Flag=1 Resid | Flag=1 Under% | Flag=0 N | Flag=0 Resid | Flag=0 Under% |
|------|----------|-------------|--------------|----------|-------------|--------------|
| 2024 | 1212 | +0.033 | 48.8% | 1114 | -0.085 | 51.3% |
| 2025 | 1167 | -0.127 | 54.8% | 1144 | +0.249 | 48.3% |
Note: Direction flips — closer used → OVER in 2024, UNDER in 2025. No stable signal.

**BF03: bp_workload_3d_home**
| Year | N | Slope | p-value | Top20 Resid | Bot20 Resid |
|------|---|-------|---------|-------------|-------------|
| 2024 | 2411 | -0.059 | 0.557 | -0.263 | +0.250 |
| 2025 | 2416 | -0.122 | 0.259 | +0.044 | +0.151 |
Note: 2024 top20 shows strong UNDER resid (-0.26) but 2025 is flat (+0.04). Not stable.

**ST01: rest_gap**
| Year | N | Slope | p-value | Top20 Resid | Bot20 Resid |
|------|---|-------|---------|-------------|-------------|
| 2024 | 2427 | -0.470 | 0.130 | -0.860 | -0.002 |
| 2025 | 2428 | -0.117 | 0.742 | +0.458 | +0.023 |
Note: 93% of games have rest_gap=0 (both teams on 1 day rest). Top/bot 20% N=200 only. Slope flips direction. No signal.

**ST02: road_trip_6plus_away** ← PROMOTED
| Year | Flag=1 N | Flag=1 Resid | Flag=1 Under% | Flag=0 N | Flag=0 Resid | Flag=0 Under% |
|------|----------|-------------|--------------|----------|-------------|--------------|
| 2024 | 611 | -0.203 | 51.4% | 1816 | +0.068 | 49.7% |
| 2025 | 597 | -0.350 | 55.6% | 1831 | +0.114 | 50.5% |
Note: Consistent UNDER residual both years, strengthening 2024→2025. 25% prevalence.

**ST03: tz_change_2plus_away**
| Year | Flag=1 N | Flag=1 Resid | Flag=1 Under% | Flag=0 N | Flag=0 Resid | Flag=0 Under% |
|------|----------|-------------|--------------|----------|-------------|--------------|
| 2024 | 163 | -0.065 | 52.8% | 2264 | +0.005 | 49.9% |
| 2025 | 173 | +0.139 | 40.7% | 2255 | -0.011 | 52.6% |
Note: 2024 slight UNDER, 2025 flips to OVER. Small N (336 pooled). No signal.



## Umpire Interaction Triage

Dataset: 4855 games (2024-2025), 4666 non-push

### Field Mapping

| Requested Field | Available Field | Notes |
|----------------|----------------|-------|
| umpire_bb_rate | **MISSING** | Not in UMPIRE_RATINGS or feature_table |
| umpire_k_rate | umpire_k_rate | k_tendency from UMPIRE_RATINGS, additive adjustment |
| umpire_historical_over_rate | umpire_over_rate | runs_factor from UMPIRE_RATINGS, multiplicative (~0.92–1.06) |
| umpire_historical_runs_per_game | derived from umpire_over_rate | runs_factor IS the runs-per-game ratio |
| avg_sp_csw_pct | avg_sp_k_pct | (home_sp_k_pct + away_sp_k_pct)/2 — K% proxy for CSW |
| avg_sp_bb_rate | avg_sp_bb_pct | (home_sp_bb_pct + away_sp_bb_pct)/2 |

### Signals Skipped
- **U01 (ump_walk_rate)**: CANNOT BUILD — umpire_bb_rate not available
- **U05 (ump_walk_pitcher)**: CANNOT BUILD — umpire_bb_rate not available

### Data Integrity
umpire_over_rate and umpire_k_rate are static per-umpire career ratings
from the UMPIRE_RATINGS dict, assigned pregame. Not post-game corrected.

### Signal Definitions (as built)

| Signal | Formula | Direction |
|--------|---------|-----------|
| U02 | umpire_k_rate − 0.00024 | UNDER |
| U03 | umpire_over_rate − 1.0 | OVER (positive → OVER) |
| U04 | umpire_k_rate × avg_sp_k_pct | UNDER (tight ump × command SP) |
| U06 | umpire_over_rate / 0.9995 | OVER (high → OVER) |

### Triage Results

| Signal | Name | Best 10% Bucket | N | Resid | ROI | Stability | Mkt Corr | Verdict |
|--------|------|----------------|---|-------|-----|-----------|----------|---------|
| U02 | ump_k_rate | top_10 | 410 | -0.0278 | -5.0% | MIXED | CLEAN (-0.043) | **SHELVE** |
| U03 | ump_over_under_bias | bot_10 | 466 | -0.0275 | -5.0% | MIXED | CLEAN (0.045) | **SHELVE** |
| U04 | ump_csw_interaction | top_10 | 461 | -0.0267 | -4.8% | MIXED | CLEAN (-0.043) | **SHELVE** |
| U06 | ump_runs_factor | bot_10 | 466 | -0.0275 | -5.0% | MIXED | CLEAN (0.045) | **SHELVE** |

### Year Detail

| Signal | 2024 Coef | 2024 p | 2025 Coef | 2025 p | Consistent? |
|--------|----------|--------|----------|--------|------------|
| U02 | -0.45636 | 0.7944 | +1.06443 | 0.5813 | MIXED |
| U03 | +0.71593 | 0.4620 | -0.69699 | 0.5089 | MIXED |
| U04 | -0.64799 | 0.9341 | +3.79215 | 0.6596 | MIXED |
| U06 | +0.71555 | 0.4620 | -0.69662 | 0.5089 | MIXED |

### Extreme Bucket Detail

**U02: ump_k_rate**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 410 | -0.0278 | 0.498 | -5.0% |
| top_20 | 466 | -0.0275 | 0.498 | -5.0% |
| bot_10 | 519 | -0.0240 | 0.497 | -5.1% |
| bot_20 | 4200 | -0.0087 | 0.510 | -2.5% |

**U03: ump_over_under_bias**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 355 | -0.0256 | 0.496 | -5.4% |
| top_20 | 671 | -0.0106 | 0.516 | -1.6% |
| bot_10 | 466 | -0.0275 | 0.498 | -5.0% |
| bot_20 | 3995 | -0.0106 | 0.508 | -3.0% |

**U04: ump_csw_interaction**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 461 | -0.0267 | 0.499 | -4.8% |
| top_20 | 466 | -0.0275 | 0.498 | -5.0% |
| bot_10 | 467 | -0.0247 | 0.495 | -5.6% |
| bot_20 | 4200 | -0.0087 | 0.510 | -2.5% |

**U06: ump_runs_factor**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 355 | -0.0256 | 0.496 | -5.4% |
| top_20 | 671 | -0.0106 | 0.516 | -1.6% |
| bot_10 | 466 | -0.0275 | 0.498 | -5.0% |
| bot_20 | 3995 | -0.0106 | 0.508 | -3.0% |

### Summary

**Promoted: 0** | Shelved: 4 | Skipped (missing data): 2

No umpire signals passed all three promotion gates.
The umpire ratings in UMPIRE_RATINGS are already incorporated into the V1 simulation
model via the runs_factor and k_tendency fields. The market appears to price umpire
effects adequately — no residual signal remains in the extreme buckets.



## Weather Interaction Triage

Dataset: 4855 games (2024-2025), 4666 non-push

### Field Mapping

| Requested Field | Actual Field | Status |
|----------------|-------------|--------|
| wind_speed | wind_speed | FOUND |
| wind_out_flag | N/A | MISSING — derived from wind_factor_effective > 0 |
| wind_in_flag | N/A | MISSING — derived from wind_factor_effective < 0 |
| temperature | temperature | FOUND |
| humidity_pct | N/A | MISSING — not in feature_table or game_table |
| park_hr_factor | park_factor_hr | FOUND (as park_factor_hr) |
| avg_sp_fb_rate | N/A | MISSING — sp_gb_pct is all NaN; using 1 - avg_sp_gb_proxy |
| avg_sp_breaking_ball_pct | N/A | MISSING — no pitch-type breakdown in feature_table |
| park_seasonal_avg_temp | N/A | MISSING — not precomputed |

### Signals Skipped / Modified
- **W07 (humidity_carry)**: CANNOT BUILD — humidity_pct not available
- **W01 (wind_out_flyball)**: MODIFIED — avg_sp_fb_rate not available; using wind_factor_effective clipped >0 as proxy (already encodes wind × park geometry)
- **W02 (wind_in_flyball)**: MODIFIED — same proxy approach, negative wind_factor_effective
- **W04 (cold_breaking)**: MODIFIED — avg_sp_breaking_ball_pct not available; using max(0, 60-temp) as cold factor only

### Data Integrity
- temperature, wind_speed, wind_direction: Open-Meteo forecast (pre-game). Confirmed pregame.
- wind_factor_effective: derived from wind_speed × cos(wind_dir - cf_bearing). Pre-game.
- park_avg_temp: derived from dataset mean per park_id (static, not post-game).

### Signal Definitions (as built)

| Signal | Formula | Direction | Note |
|--------|---------|-----------|------|
| W01 | see code | OVER | wind_factor_effective clipped >0 |
| W02 | see code | UNDER | -wind_factor_effective clipped >0 |
| W03 | see code | OVER (high dev) | temp - park_avg_temp |
| W04 | see code | OVER | max(0, 60-temp); no breaking_ball_pct available |
| W05 | see code | OVER | binary: temp >= 95°F |
| W06 | see code | OVER | wind_speed × park_hr_factor × wind_out_flag |

### Triage Results

| Signal | Name | Best 10% Bucket | N | Resid | ROI | Stability | Mkt Corr | Verdict |
|--------|------|----------------|---|-------|-----|-----------|----------|---------|
| W01 | wind_out_proxy | bot_10 | 2774 | -0.0099 | -3.0% | MIXED | CLEAN (0.062) | **SHELVE** |
| W02 | wind_in_proxy | bot_10 | 2999 | -0.0195 | -4.2% | MIXED | CLEAN (-0.110) | **SHELVE** |
| W03 | temp_deviation | bot_10 | 460 | -0.0165 | -2.5% | MIXED | PARTIAL (0.247) | **SHELVE** |
| W04 | cold_factor | bot_10 | 4151 | -0.0112 | -3.1% | MIXED | CLEAN (-0.135) | **SHELVE** |
| W05 | extreme_heat | flag=1 | 26 | -0.2407 | -48.6% | CONSISTENT | CLEAN (0.080) | **SHELVE** |
| W06 | wind_park_geometry | top_10 | 469 | -0.0134 | -3.9% | MIXED | CLEAN (0.109) | **SHELVE** |

### Year Detail

| Signal | 2024 Coef | 2024 p | 2025 Coef | 2025 p | Consistent? |
|--------|----------|--------|----------|--------|------------|
| W01 | +0.00165 | 0.4907 | -0.00148 | 0.6223 | MIXED |
| W02 | +0.00472 | 0.1411 | -0.00526 | 0.1947 | MIXED |
| W03 | -0.00159 | 0.1601 | +0.00054 | 0.6228 | MIXED |
| W04 | +0.00458 | 0.2382 | -0.00354 | 0.2819 | MIXED |
| W05 | -0.18366 | 0.2463 | -0.26242 | 0.0311 | CONSISTENT |
| W06 | +0.00076 | 0.7005 | -0.00115 | 0.6453 | MIXED |

### Extreme Bucket Detail

**W01: wind_out_proxy**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 469 | -0.0072 | 0.510 | -2.7% |
| top_20 | 933 | -0.0072 | 0.512 | -2.2% |
| bot_10 | 2774 | -0.0099 | 0.508 | -3.0% |
| bot_20 | 2774 | -0.0099 | 0.508 | -3.0% |

**W02: wind_in_proxy**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 464 | -0.0010 | 0.522 | -0.4% |
| top_20 | 932 | -0.0098 | 0.511 | -2.5% |
| bot_10 | 2999 | -0.0195 | 0.502 | -4.2% |
| bot_20 | 2999 | -0.0195 | 0.502 | -4.2% |

**W03: temp_deviation**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 472 | -0.0082 | 0.506 | -3.3% |
| top_20 | 936 | -0.0278 | 0.489 | -6.6% |
| bot_10 | 460 | -0.0165 | 0.511 | -2.5% |
| bot_20 | 928 | +0.0036 | 0.527 | +0.6% |

**W04: cold_factor**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 461 | +0.0041 | 0.527 | +0.6% |
| top_20 | 515 | -0.0055 | 0.520 | -0.7% |
| bot_10 | 4151 | -0.0112 | 0.508 | -3.1% |
| bot_20 | 4151 | -0.0112 | 0.508 | -3.1% |

**W05: extreme_heat**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| flag=1 | 26 | -0.2407 | 0.269 | -48.6% |
| flag=0 | 4640 | -0.0093 | 0.511 | -2.5% |

**W06: wind_park_geometry**
| Bucket | N | Resid | Under% | ROI |
|--------|---|-------|--------|-----|
| top_10 | 469 | -0.0134 | 0.503 | -3.9% |
| top_20 | 936 | -0.0072 | 0.511 | -2.5% |
| bot_10 | 2774 | -0.0099 | 0.508 | -3.0% |
| bot_20 | 2774 | -0.0099 | 0.508 | -3.0% |

### Summary

**Promoted: 0** | Shelved: 6 | Skipped (missing data): 1 (W07)

No weather signals passed all three promotion gates.
Weather effects (temperature, wind) are already in the V1 simulation model
via wind_factor_effective and temperature features. The market prices these
factors into totals efficiently — no residual exploitable signal remains.

