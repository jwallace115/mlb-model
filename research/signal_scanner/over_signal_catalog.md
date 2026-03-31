# OVER Signal Catalog — MLB Totals

Total signals: 119 (after dedup from 200 raw ideas)
Source A: 100 signals (Claude-generated)
Source B: 100 signals (ChatGPT-generated)
After dedup: 119 unique signals

## Summary

| Domain | Count |
|--------|-------|
| pitcher_volatility | 20 |
| bullpen_cascade | 19 |
| contact_amplification | 16 |
| player_interaction | 16 |
| defensive_instability | 11 |
| hr_cluster | 9 |
| environment | 8 |
| run_cascade | 8 |
| run_sequencing | 7 |
| pitch_mix | 5 |

| Data Status | Count |
|-------------|-------|
| DATA_MISSING | 77 |
| DERIVABLE | 32 |
| READY | 10 |

| Priority | Count |
|----------|-------|
| LOW | 49 |
| MEDIUM | 48 |
| HIGH | 22 |

## TOP 20 — Next Scanner Wave Candidates

### HIGH + READY (8 signals)

| ID | Name | Formula |
|----|------|---------|
| OV016 | high_pitch_count_fatigue | pitcher_pitches_2starts_ago / 100 |
| OV019 | era_spike_recent | pitcher_ERA_last2 - pitcher_ERA_season |
| OV041 | short_starter_x_weak_bullpen | (5 - starter_avg_IP_last5) * bullpen_xFIP |
| OV043 | high_leverage_bullpen_overuse | bullpen_high_leverage_IP_last3d |
| OV050 | short_starter_x_extra_innings_yesterday | max(0, prev_game_innings - 9) * (5 - starter_avg_IP) |
| OV051 | bullpen_era_xfip_gap | bullpen_xFIP - bullpen_ERA |
| OV100 | combined_bullpen_workload_both | home_bullpen_IP_last3d + away_bullpen_IP_last3d |
| OV115 | pitcher_pitch_count_per_ip_x_patient | pitcher_pitches_per_inning * lineup_bb_rate |

### HIGH + DERIVABLE (13 signals)

| ID | Name | Formula |
|----|------|---------|
| OV001 | bb_rate_x_hard_hit | pitcher_bb_rate * pitcher_hard_hit_rate_allowed |
| OV002 | xera_era_gap | pitcher_xERA - pitcher_ERA |
| OV006 | whip_era_gap | pitcher_WHIP - (pitcher_ERA / 4.5) |
| OV010 | high_csw_high_hard_hit | pitcher_CSW_pct * pitcher_hard_hit_rate_allowed |
| OV020 | command_pitcher_x_patient_lineup | -1 * pitcher_bb_rate * lineup_bb_rate |
| OV021 | low_k_x_high_contact_lineup | (1 - pitcher_k_rate) * lineup_contact_rate |
| OV033 | barrel_x_barrel | lineup_barrel_rate * pitcher_barrel_rate_allowed |
| OV076 | strand_rate_regression | pitcher_strand_rate_rolling - pitcher_xStrand |
| OV078 | walk_power_lineup | lineup_bb_rate * lineup_ISO |
| OV083 | high_whip_x_patient_lineup | pitcher_WHIP * lineup_bb_rate |
| OV093 | high_obp_lineup_x_high_bb_pitcher | lineup_OBP * pitcher_bb_rate |
| OV110 | era_xera_gap_x_contact_lineup | (pitcher_xERA - pitcher_ERA) * lineup_contact_rate |
| OV114 | high_obp_team_x_bullpen_bb | lineup_OBP * opp_bullpen_bb_rate |

## Pitcher Volatility (20 signals)

### OV001: bb_rate_x_hard_hit
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_bb_rate * pitcher_hard_hit_rate_allowed`
- **Required Inputs**: pitcher_bb_rate, pitcher_hard_hit_rate_allowed
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV002: xera_era_gap
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_xERA - pitcher_ERA`
- **Required Inputs**: pitcher_ERA, pitcher_xERA
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV003: spin_rate_instability
- **Domain**: pitcher_volatility
- **Formula**: `std(pitcher_spin_rate_last3)`
- **Required Inputs**: pitcher_spin_rate per start (Statcast)
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV004: velo_decline_bb_rise
- **Domain**: pitcher_volatility
- **Formula**: `(pitcher_velo_season - pitcher_velo_last3) * pitcher_bb_rate_last3`
- **Required Inputs**: pitcher_avg_velo per start, pitcher_bb_rate_last3
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV006: whip_era_gap
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_WHIP - (pitcher_ERA / 4.5)`
- **Required Inputs**: pitcher_WHIP, pitcher_ERA
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV007: il_return_first_start
- **Domain**: pitcher_volatility
- **Formula**: `flag: first_start_after_IL AND IL_days >= 10`
- **Required Inputs**: IL stint dates, game schedule
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV009: il_return_velo_loss
- **Domain**: pitcher_volatility
- **Formula**: `(pitcher_velo_pre_IL - pitcher_velo_post_IL) * flag_IL_return`
- **Required Inputs**: pitcher_avg_velo pre/post IL, IL dates
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV010: high_csw_high_hard_hit
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_CSW_pct * pitcher_hard_hit_rate_allowed`
- **Required Inputs**: pitcher_CSW_pct, pitcher_hard_hit_rate_allowed
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV014: low_swstr_low_csw
- **Domain**: pitcher_volatility
- **Formula**: `-1 * (pitcher_SwStr_pct + pitcher_called_strike_pct)`
- **Required Inputs**: pitcher_SwStr_pct, pitcher_called_strike_pct (Statcast)
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV016: high_pitch_count_fatigue
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_pitches_2starts_ago / 100`
- **Required Inputs**: pitcher pitch counts per start
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

### OV019: era_spike_recent
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_ERA_last2 - pitcher_ERA_season`
- **Required Inputs**: pitcher ER, IP per start
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

### OV030: soft_contact_regression
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_season_soft_contact_pct - pitcher_career_soft_contact_pct`
- **Required Inputs**: soft_contact_rate rolling (Statcast)
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV055: starter_third_inning_weakness
- **Domain**: pitcher_volatility
- **Formula**: `starter_3rd_inning_ERA - starter_overall_ERA`
- **Required Inputs**: pitcher inning-level splits
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV079: first_pitch_strike_collapse
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_f_strike_pct_season - pitcher_f_strike_pct_last3`
- **Required Inputs**: pitcher first-pitch-strike per start
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV085: k_improvement_hard_contact_stable
- **Domain**: pitcher_volatility
- **Formula**: `(pitcher_k_rate_last5 - pitcher_k_rate_season) * pitcher_hard_hit_rate_stable_flag`
- **Required Inputs**: pitcher_k_rate rolling, pitcher_hard_hit_rate rolling
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV089: post_allstar_first_start
- **Domain**: pitcher_volatility
- **Formula**: `flag: first_start_after_allstar_break`
- **Required Inputs**: ASB dates, game schedule
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DERIVABLE

### OV092: triple_decline_pitcher
- **Domain**: pitcher_volatility
- **Formula**: `(velo_season - velo_last3) + (spin_season - spin_last3) + (hard_hit_last3 - hard_hit_season)`
- **Required Inputs**: pitcher velo, spin, hard_hit per start (Statcast)
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV110: era_xera_gap_x_contact_lineup
- **Domain**: pitcher_volatility
- **Formula**: `(pitcher_xERA - pitcher_ERA) * lineup_contact_rate`
- **Required Inputs**: pitcher_ERA, pitcher_xERA, lineup_contact_rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV111: velo_decline_x_power_lineup
- **Domain**: pitcher_volatility
- **Formula**: `(pitcher_velo_season - pitcher_velo_last3) * lineup_ISO`
- **Required Inputs**: pitcher velo trend, lineup ISO
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV115: pitcher_pitch_count_per_ip_x_patient
- **Domain**: pitcher_volatility
- **Formula**: `pitcher_pitches_per_inning * lineup_bb_rate`
- **Required Inputs**: pitcher pitches/inning, lineup BB rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

## Pitch Mix (5 signals)

### OV005: pitch_mix_fastball_shift
- **Domain**: pitch_mix
- **Formula**: `pitcher_FF_pct_last3 - pitcher_FF_pct_season`
- **Required Inputs**: pitch_type_pct per start (Statcast)
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV012: slider_disappearance
- **Domain**: pitch_mix
- **Formula**: `pitcher_SL_pct_season - pitcher_SL_pct_last_start`
- **Required Inputs**: pitch_type_pct per start (Statcast)
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV103: slider_pitcher_x_slider_damage
- **Domain**: pitch_mix
- **Formula**: `pitcher_SL_pct * lineup_SL_wOBA`
- **Required Inputs**: pitcher_SL_pct, lineup_slider_wOBA (pitch-type)
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV104: sinker_pitcher_x_sinker_damage
- **Domain**: pitch_mix
- **Formula**: `pitcher_SI_pct * lineup_SI_wOBA`
- **Required Inputs**: pitcher_SI_pct, lineup_sinker_wOBA (pitch-type)
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV105: limited_pitch_variety_x_contact
- **Domain**: pitch_mix
- **Formula**: `(1 / pitcher_unique_pitch_types) * lineup_contact_rate`
- **Required Inputs**: pitcher pitch type count, lineup_contact_rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

## Contact Amplification (16 signals)

### OV008: gb_pitcher_x_pull_power_lineup
- **Domain**: contact_amplification
- **Formula**: `pitcher_GB_pct * lineup_pull_rate`
- **Required Inputs**: pitcher_GB_pct, lineup_pull_rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV021: low_k_x_high_contact_lineup
- **Domain**: contact_amplification
- **Formula**: `(1 - pitcher_k_rate) * lineup_contact_rate`
- **Required Inputs**: pitcher_k_rate, lineup_contact_rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV024: low_k_x_high_babip_lineup
- **Domain**: contact_amplification
- **Formula**: `(1 - pitcher_k_rate) * lineup_babip_rolling`
- **Required Inputs**: pitcher_k_rate, lineup_BABIP
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV025: sinker_pitcher_x_launch_angle_lineup
- **Domain**: contact_amplification
- **Formula**: `pitcher_sinker_pct * lineup_avg_launch_angle`
- **Required Inputs**: pitcher_sinker_pct, lineup_avg_launch_angle
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV026: ff_pitcher_x_ff_damage_lineup
- **Domain**: contact_amplification
- **Formula**: `pitcher_FF_pct * lineup_FF_wOBA`
- **Required Inputs**: pitcher_FF_pct, lineup_FF_wOBA (pitch-type wOBA)
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV028: low_chase_pitcher_x_patient_lineup
- **Domain**: contact_amplification
- **Formula**: `(1 - pitcher_o_swing_pct) * lineup_bb_rate`
- **Required Inputs**: pitcher_chase_rate (Statcast), lineup_bb_rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV029: high_zone_pitcher_x_zone_damage_lineup
- **Domain**: contact_amplification
- **Formula**: `pitcher_zone_rate * lineup_zone_contact_wOBA`
- **Required Inputs**: pitcher_zone_rate (Statcast), lineup_zone_contact_rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV031: pull_lineup_x_no_shift
- **Domain**: contact_amplification
- **Formula**: `lineup_pull_pct (post-2023 only)`
- **Required Inputs**: lineup_pull_pct
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV032: gb_lineup_x_fb_pitcher
- **Domain**: contact_amplification
- **Formula**: `lineup_GB_pct * pitcher_FB_pct`
- **Required Inputs**: lineup_GB_pct, pitcher_FB_pct
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV034: chase_pitcher_x_chase_lineup
- **Domain**: contact_amplification
- **Formula**: `pitcher_chase_rate * lineup_chase_rate`
- **Required Inputs**: pitcher_chase_rate, lineup_o_swing_pct (Statcast)
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV039: exit_velo_mismatch
- **Domain**: contact_amplification
- **Formula**: `lineup_avg_exit_velo - pitcher_expected_exit_velo`
- **Required Inputs**: lineup_avg_exit_velo, pitcher_xEV (Statcast)
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV040: contact_pitcher_x_oppo_lineup
- **Domain**: contact_amplification
- **Formula**: `(1 - pitcher_k_rate) * lineup_oppo_hit_pct`
- **Required Inputs**: pitcher_k_rate, lineup_oppo_hit_rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV063: shift_ban_x_pull_lineup
- **Domain**: contact_amplification
- **Formula**: `lineup_pull_pct (post-2023 flag)`
- **Required Inputs**: lineup_pull_pct, year >= 2023
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV101: hard_hit_pitcher_x_fb_hitters
- **Domain**: contact_amplification
- **Formula**: `pitcher_hard_hit_rate_allowed * lineup_FB_pct`
- **Required Inputs**: pitcher_hard_hit_rate (Statcast), lineup_FB_pct
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV102: babip_x_babip
- **Domain**: contact_amplification
- **Formula**: `pitcher_BABIP_allowed * lineup_BABIP`
- **Required Inputs**: pitcher_BABIP, lineup_BABIP
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV106: pitcher_high_ld_rate_x_contact
- **Domain**: contact_amplification
- **Formula**: `pitcher_LD_pct * lineup_contact_rate`
- **Required Inputs**: pitcher_LD_pct, lineup_contact_rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

## Run Sequencing (7 signals)

### OV011: third_time_through_exposure
- **Domain**: run_sequencing
- **Formula**: `pitcher_TTO3_OPS - pitcher_TTO1_OPS`
- **Required Inputs**: pitcher times-through-order splits
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV076: strand_rate_regression
- **Domain**: run_sequencing
- **Formula**: `pitcher_strand_rate_rolling - pitcher_xStrand`
- **Required Inputs**: pitcher LOB%, expected strand rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV077: blown_save_cluster
- **Domain**: run_sequencing
- **Formula**: `team_blown_save_rate_last10`
- **Required Inputs**: team blown_save per game rolling
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV080: risp_matchup_cluster
- **Domain**: run_sequencing
- **Formula**: `lineup_BA_RISP * (-1 * pitcher_ERA_RISP)`
- **Required Inputs**: pitcher RISP splits, lineup RISP splits
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV081: high_lob_scoring_team
- **Domain**: run_sequencing
- **Formula**: `team_LOB_pct * team_runs_per_game`
- **Required Inputs**: team_LOB_pct, team_runs_per_game
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DERIVABLE

### OV084: high_variance_team_x_pitcher
- **Domain**: run_sequencing
- **Formula**: `team_runs_std_dev * pitcher_game_score_std_dev`
- **Required Inputs**: team_runs_std, pitcher_game_score_std
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV107: pitcher_poor_stretch_x_high_obp
- **Domain**: run_sequencing
- **Formula**: `pitcher_stretch_ERA_diff * lineup_OBP`
- **Required Inputs**: pitcher set/stretch splits, lineup_OBP
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

## Hr Cluster (9 signals)

### OV013: hr_fb_spike_recent
- **Domain**: hr_cluster
- **Formula**: `pitcher_HR_FB_last3 - pitcher_HR_FB_season`
- **Required Inputs**: pitcher HR, FB per start
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV033: barrel_x_barrel
- **Domain**: hr_cluster
- **Formula**: `lineup_barrel_rate * pitcher_barrel_rate_allowed`
- **Required Inputs**: lineup_barrel_rate, pitcher_barrel_rate_allowed (Statcast)
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV038: hr_suppression_regression
- **Domain**: hr_cluster
- **Formula**: `(league_avg_HR_FB - pitcher_HR_FB_rate) * lineup_FB_rate`
- **Required Inputs**: pitcher_HR_FB_rate, lineup_FB_rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV066: pull_lineup_x_short_porch
- **Domain**: hr_cluster
- **Formula**: `lineup_pull_pct * park_short_porch_factor`
- **Required Inputs**: lineup_pull_pct, park_LF_RF_distance
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV067: fb_pitcher_x_hr_park
- **Domain**: hr_cluster
- **Formula**: `pitcher_FB_pct * park_hr_factor`
- **Required Inputs**: pitcher_FB_pct, park_factor_hr
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DATA_MISSING

### OV068: barrel_x_babip_lucky_pitcher
- **Domain**: hr_cluster
- **Formula**: `lineup_barrel_rate * (pitcher_xBA - pitcher_BA_allowed)`
- **Required Inputs**: lineup_barrel_rate, pitcher_xBA, pitcher_BA
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV073: dual_flyball_starters
- **Domain**: hr_cluster
- **Formula**: `home_sp_FB_pct * away_sp_FB_pct`
- **Required Inputs**: home_sp_FB_pct, away_sp_FB_pct
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV075: career_hr_fb_spike
- **Domain**: hr_cluster
- **Formula**: `pitcher_HR_FB_rolling - pitcher_HR_FB_career`
- **Required Inputs**: pitcher HR/FB per start, career HR/FB
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV096: high_hr_high_k_lineup
- **Domain**: hr_cluster
- **Formula**: `lineup_HR_rate * lineup_K_rate`
- **Required Inputs**: lineup_HR_rate, lineup_K_rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DERIVABLE

## Player Interaction (16 signals)

### OV015: post_trade_first_start
- **Domain**: player_interaction
- **Formula**: `flag: first_start_new_team after trade`
- **Required Inputs**: trade dates, pitcher roster transactions
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV018: low_extension_x_high_ev_lineup
- **Domain**: player_interaction
- **Formula**: `-1 * pitcher_extension * lineup_avg_exit_velo`
- **Required Inputs**: pitcher_extension (Statcast), lineup_avg_exit_velo
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV020: command_pitcher_x_patient_lineup
- **Domain**: player_interaction
- **Formula**: `-1 * pitcher_bb_rate * lineup_bb_rate`
- **Required Inputs**: pitcher_bb_rate, lineup_bb_rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV027: cutter_pitcher_x_opp_hand_lineup
- **Domain**: player_interaction
- **Formula**: `pitcher_cutter_pct * lineup_opp_hand_pct`
- **Required Inputs**: pitcher_cutter_pct, lineup_handedness
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV035: high_velo_x_velo_damage_lineup
- **Domain**: player_interaction
- **Formula**: `pitcher_avg_velo * lineup_velo_damage_wOBA`
- **Required Inputs**: pitcher_avg_velo, lineup_wOBA_vs_velo_bin
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV071: first_matchup_familiarity_gap
- **Domain**: player_interaction
- **Formula**: `flag: pitcher_first_time_facing_lineup_this_season`
- **Required Inputs**: pitcher-lineup matchup history
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV074: low_spin_pitcher_x_spin_vuln_lineup
- **Domain**: player_interaction
- **Formula**: `(-1 * pitcher_spin_rate_FF) * lineup_low_spin_wOBA`
- **Required Inputs**: pitcher_spin_rate (Statcast), lineup_spin_wOBA
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV082: oppo_field_x_inside_pitcher
- **Domain**: player_interaction
- **Formula**: `lineup_oppo_hit_rate * pitcher_inside_pitch_pct`
- **Required Inputs**: lineup_oppo_rate, pitcher_location_pct
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV086: lefty_lineup_x_lhp_platoon_vuln
- **Domain**: player_interaction
- **Formula**: `pitcher_LHB_wOBA * lineup_LHB_pct (when pitcher is LHP)`
- **Required Inputs**: pitcher LHB splits, lineup handedness
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV087: first_series_matchup
- **Domain**: player_interaction
- **Formula**: `flag: first_series_between_teams_this_season`
- **Required Inputs**: schedule, matchup history
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DERIVABLE

### OV088: hot_lineup_x_rested_pitcher
- **Domain**: player_interaction
- **Formula**: `lineup_runs_last7 * pitcher_days_rest`
- **Required Inputs**: lineup_runs_rolling, pitcher_days_rest
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV090: fast_lineup_x_poor_pickoff
- **Domain**: player_interaction
- **Formula**: `lineup_avg_sprint_speed * (-1 * pitcher_pickoff_rate)`
- **Required Inputs**: lineup_sprint_speed (Statcast), pitcher_pickoff_rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV097: new_catcher_pairing
- **Domain**: player_interaction
- **Formula**: `flag: pitcher_first_start_with_catcher`
- **Required Inputs**: pitcher-catcher pairing history
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV098: pitch_type_dominance_mismatch
- **Domain**: player_interaction
- **Formula**: `lineup_wOBA_vs_pitcher_primary_pitch`
- **Required Inputs**: pitcher primary pitch type, lineup pitch-type wOBA
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV099: aggressive_manager_x_weak_catcher
- **Domain**: player_interaction
- **Formula**: `manager_SB_rate * (-1 * catcher_pop_time)`
- **Required Inputs**: manager_run_game_rate, catcher_pop_time
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV118: pitcher_wild_pitch_x_aggressive_runners
- **Domain**: player_interaction
- **Formula**: `pitcher_WP_rate * opp_SB_attempt_rate`
- **Required Inputs**: pitcher wild pitch rate, team SB rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

## Environment (8 signals)

### OV017: fb_pitcher_x_wind_out
- **Domain**: environment
- **Formula**: `pitcher_FB_pct * wind_factor_effective (when > 0)`
- **Required Inputs**: pitcher_FB_pct, wind_factor_effective
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV036: gb_pitcher_x_fast_surface
- **Domain**: environment
- **Formula**: `pitcher_GB_pct * park_surface_speed_rating`
- **Required Inputs**: pitcher_GB_pct, park_surface_type
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV037: popup_pitcher_x_small_foul
- **Domain**: environment
- **Formula**: `pitcher_IFFB_pct * (1 / park_foul_territory_area)`
- **Required Inputs**: pitcher_IFFB_pct, park_foul_territory
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV069: altitude_x_high_ev_lineup
- **Domain**: environment
- **Formula**: `park_altitude * lineup_avg_exit_velo`
- **Required Inputs**: park_altitude (COL flag), lineup_exit_velo
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV070: fb_pitcher_x_wind_out_large_park
- **Domain**: environment
- **Formula**: `pitcher_FB_pct * wind_factor_effective * (1 / park_hr_factor)`
- **Required Inputs**: pitcher_FB_pct, wind_factor_effective, park_hr_factor
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV072: cold_end_hr_park
- **Domain**: environment
- **Formula**: `(temperature_today - temperature_last7d_avg) * park_hr_factor`
- **Required Inputs**: temperature, temperature_rolling, park_hr_factor
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DERIVABLE

### OV116: warm_weather_x_fb_pitchers
- **Domain**: environment
- **Formula**: `max(0, temperature - 80) * avg_sp_FB_pct`
- **Required Inputs**: temperature, pitcher FB pct
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV117: day_game_x_fb_pitchers
- **Domain**: environment
- **Formula**: `day_game_flag * avg_sp_FB_pct`
- **Required Inputs**: game_time, pitcher FB pct
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

## Defensive Instability (11 signals)

### OV022: gb_pitcher_x_poor_infield
- **Domain**: defensive_instability
- **Formula**: `pitcher_GB_pct * (-1 * team_infield_DRS)`
- **Required Inputs**: pitcher_GB_pct, team_infield_DRS
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV023: fb_pitcher_x_poor_outfield
- **Domain**: defensive_instability
- **Formula**: `pitcher_FB_pct * (-1 * team_outfield_DRS)`
- **Required Inputs**: pitcher_FB_pct, team_outfield_DRS
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV056: poor_infield_x_gb_environment
- **Domain**: defensive_instability
- **Formula**: `combined_GB_pct * (-1 * team_infield_DRS)`
- **Required Inputs**: pitcher_GB_pct, team_infield_DRS
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV057: error_prone_x_high_whip
- **Domain**: defensive_instability
- **Formula**: `team_error_rate * pitcher_WHIP`
- **Required Inputs**: team_error_rate, pitcher_WHIP
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV058: weak_of_arm_x_aggressive_runners
- **Domain**: defensive_instability
- **Formula**: `(-1 * outfield_arm_rating) * opp_SB_attempt_rate`
- **Required Inputs**: outfield_arm_rating, opp_SB_rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV059: corner_defense_x_pull_pitcher
- **Domain**: defensive_instability
- **Formula**: `(-1 * corner_infield_DRS) * pitcher_pull_GB_pct`
- **Required Inputs**: corner_IF_DRS, pitcher_pull_GB_pct
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV060: poor_framing_x_borderline_pitcher
- **Domain**: defensive_instability
- **Formula**: `(-1 * catcher_framing_runs) * pitcher_zone_edge_pct`
- **Required Inputs**: catcher_framing_runs, pitcher_zone_rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV061: weak_catcher_arm_x_steal_team
- **Domain**: defensive_instability
- **Formula**: `(-1 * catcher_CS_pct) * opp_SB_attempt_rate`
- **Required Inputs**: catcher_caught_stealing_pct, opp_SB_rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV062: weak_cf_x_gap_hitters
- **Domain**: defensive_instability
- **Formula**: `(-1 * CF_range_rating) * lineup_doubles_rate`
- **Required Inputs**: CF_range, lineup_doubles_rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV064: poor_defense_x_extras_prob
- **Domain**: defensive_instability
- **Formula**: `(-1 * team_defensive_rating) * game_extras_probability`
- **Required Inputs**: team_DRS, game_spread_implied
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV065: defensive_downgrade_rest_day
- **Domain**: defensive_instability
- **Formula**: `flag: primary_IF_sitting AND backup_DRS < primary_DRS`
- **Required Inputs**: lineup vs standard lineup, player DRS
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

## Bullpen Cascade (19 signals)

### OV041: short_starter_x_weak_bullpen
- **Domain**: bullpen_cascade
- **Formula**: `(5 - starter_avg_IP_last5) * bullpen_xFIP`
- **Required Inputs**: starter_avg_IP_last5, bullpen_xFIP
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

### OV042: bullpen_low_strand_x_baserunner_starter
- **Domain**: bullpen_cascade
- **Formula**: `(1 - bullpen_strand_rate) * starter_WHIP`
- **Required Inputs**: bullpen_strand_rate, starter_WHIP
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV043: high_leverage_bullpen_overuse
- **Domain**: bullpen_cascade
- **Formula**: `bullpen_high_leverage_IP_last3d`
- **Required Inputs**: bullpen_usage per day, leverage index
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

### OV044: bullpen_bb_x_patient_lineup
- **Domain**: bullpen_cascade
- **Formula**: `bullpen_bb_rate_last7 * lineup_bb_rate`
- **Required Inputs**: bullpen_bb_rate_rolling, lineup_bb_rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV045: bullpen_hard_hit_spike
- **Domain**: bullpen_cascade
- **Formula**: `bullpen_hard_hit_rate_last7 - bullpen_hard_hit_rate_season`
- **Required Inputs**: bullpen_hard_hit_rate per game
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV046: bullpen_handedness_mismatch
- **Domain**: bullpen_cascade
- **Formula**: `abs(bullpen_available_LHP_pct - lineup_LHB_pct)`
- **Required Inputs**: bullpen_handedness_available, lineup_handedness
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV047: doubleheader_game2_bullpen
- **Domain**: bullpen_cascade
- **Formula**: `flag: game_2_doubleheader * bullpen_IP_game1`
- **Required Inputs**: doubleheader_flag, bullpen_IP_game1
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: READY

### OV048: opener_weak_follower
- **Domain**: bullpen_cascade
- **Formula**: `opener_flag * follower_xFIP`
- **Required Inputs**: opener_flag, follower_pitcher_xFIP
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV049: bullpen_k_rate_collapse
- **Domain**: bullpen_cascade
- **Formula**: `bullpen_k_rate_season - bullpen_k_rate_last10d`
- **Required Inputs**: bullpen_K per game rolling
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV050: short_starter_x_extra_innings_yesterday
- **Domain**: bullpen_cascade
- **Formula**: `max(0, prev_game_innings - 9) * (5 - starter_avg_IP)`
- **Required Inputs**: prev_game_innings, starter_avg_IP
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

### OV051: bullpen_era_xfip_gap
- **Domain**: bullpen_cascade
- **Formula**: `bullpen_xFIP - bullpen_ERA`
- **Required Inputs**: bullpen_ERA, bullpen_xFIP
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

### OV052: weak_closer_x_close_game
- **Domain**: bullpen_cascade
- **Formula**: `closer_xFIP * game_close_probability`
- **Required Inputs**: closer_xFIP, game_spread_implied
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV053: road_trip_bullpen_fatigue
- **Domain**: bullpen_cascade
- **Formula**: `road_trip_game_num * bullpen_IP_cumulative_trip`
- **Required Inputs**: road_trip_game_num, bullpen_IP per game
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV054: bullpen_inherited_runner_scoring
- **Domain**: bullpen_cascade
- **Formula**: `bullpen_IR_scored_pct_last10`
- **Required Inputs**: bullpen inherited runners scored per game
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DATA_MISSING

### OV091: september_bullpen_depth_gap
- **Domain**: bullpen_cascade
- **Formula**: `home_roster_depth - away_roster_depth (September only)`
- **Required Inputs**: roster_depth_metric, month
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV094: away_fragile_starter_x_home_strong_bp
- **Domain**: bullpen_cascade
- **Formula**: `away_sp_xFIP * (-1 * home_bullpen_xFIP)`
- **Required Inputs**: away_sp_xFIP, home_bullpen_xFIP
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: READY

### OV100: combined_bullpen_workload_both
- **Domain**: bullpen_cascade
- **Formula**: `home_bullpen_IP_last3d + away_bullpen_IP_last3d`
- **Required Inputs**: bullpen_IP per day per team
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: READY

### OV112: bullpen_k_collapse_x_contact_lineup
- **Domain**: bullpen_cascade
- **Formula**: `(bullpen_k_season - bullpen_k_last7) * lineup_contact_rate`
- **Required Inputs**: bullpen K rate rolling, lineup contact rate
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV113: bullpen_hr_prone_x_hr_park
- **Domain**: bullpen_cascade
- **Formula**: `bullpen_HR_rate * park_hr_factor`
- **Required Inputs**: bullpen HR rate, park_factor_hr
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

## Run Cascade (8 signals)

### OV078: walk_power_lineup
- **Domain**: run_cascade
- **Formula**: `lineup_bb_rate * lineup_ISO`
- **Required Inputs**: lineup_bb_rate, lineup_ISO
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV083: high_whip_x_patient_lineup
- **Domain**: run_cascade
- **Formula**: `pitcher_WHIP * lineup_bb_rate`
- **Required Inputs**: pitcher_WHIP, lineup_bb_rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV093: high_obp_lineup_x_high_bb_pitcher
- **Domain**: run_cascade
- **Formula**: `lineup_OBP * pitcher_bb_rate`
- **Required Inputs**: lineup_OBP, pitcher_bb_rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV108: early_scoring_team_x_volatile_sp
- **Domain**: run_cascade
- **Formula**: `team_first3_inning_runs * pitcher_game_score_std`
- **Required Inputs**: team early-inning runs, pitcher game score variance
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV109: team_vs_bullpen_x_weak_bp
- **Domain**: run_cascade
- **Formula**: `team_runs_vs_bullpen * opp_bullpen_xFIP`
- **Required Inputs**: team scoring vs bullpen, opponent bullpen xFIP
- **Direction**: OVER
- **Priority**: MEDIUM
- **Data Status**: DERIVABLE

### OV114: high_obp_team_x_bullpen_bb
- **Domain**: run_cascade
- **Formula**: `lineup_OBP * opp_bullpen_bb_rate`
- **Required Inputs**: lineup OBP, bullpen BB rate
- **Direction**: OVER
- **Priority**: HIGH
- **Data Status**: DERIVABLE

### OV119: fast_runners_x_contact_pitcher
- **Domain**: run_cascade
- **Formula**: `lineup_sprint_speed * (1 - pitcher_k_rate)`
- **Required Inputs**: lineup sprint speed (Statcast), pitcher K rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

### OV120: team_strong_hitter_counts_x_wild_pitcher
- **Domain**: run_cascade
- **Formula**: `team_hitter_count_wOBA * pitcher_bb_rate`
- **Required Inputs**: team hitter count splits, pitcher BB rate
- **Direction**: OVER
- **Priority**: LOW
- **Data Status**: DATA_MISSING

