# MLB Signal Catalog

Total signals: 116

| Status | Count |
|--------|-------|
| DATA_MISSING | 52 |
| DERIVABLE | 35 |
| READY | 29 |

| Priority | Count |
|----------|-------|
| MEDIUM | 58 |
| LOW | 31 |
| HIGH | 27 |

## Top Priority (HIGH + READY/DERIVABLE)

| ID | Name | Domain | Status | Direction |
|-----|------|--------|--------|----------|
| 1 | xfip_gap | pitching | READY | UNDER |
| 2 | csw_gap | pitching | READY | UNDER |
| 3 | whiff_gap | pitching | READY | UNDER |
| 4 | kbb_gap | pitching | READY | UNDER |
| 5 | combined_pitcher_score | pitching | READY | UNDER |
| 11 | velo_recency_delta | pitching | DERIVABLE | UNDER |
| 37 | high_csw_tight_umpire | interaction | READY | UNDER |
| 40 | flyball_park_hr | interaction | READY | OVER |
| 43 | triple_flyball_park_wind | interaction | READY | OVER |
| 46 | bullpen_xfip_gap | bullpen | READY | UNDER |
| 47 | bullpen_workload_3d | bullpen | DERIVABLE | OVER |
| 48 | bullpen_workload_2d | bullpen | DERIVABLE | OVER |
| 74 | wind_flyball_out | weather | READY | OVER |
| 83 | umpire_over_rate | umpire | READY | OVER |
| 87 | umpire_csw_interaction | umpire | READY | UNDER |

## Full Catalog

| ID | Name | Domain | Family | Direction | Priority | Status |
|-----|------|--------|--------|-----------|----------|--------|
| 1 | xfip_gap | pitching | starter_quality | UNDER | HIGH | READY |
| 2 | csw_gap | pitching | starter_quality | UNDER | HIGH | READY |
| 3 | whiff_gap | pitching | starter_quality | UNDER | HIGH | READY |
| 4 | kbb_gap | pitching | starter_quality | UNDER | HIGH | READY |
| 5 | combined_pitcher_score | pitching | starter_quality | UNDER | HIGH | READY |
| 6 | stuff_plus_gap | pitching | starter_quality | UNDER | HIGH | DATA_MISSING |
| 7 | siera_gap | pitching | starter_quality | UNDER | MEDIUM | READY |
| 8 | pitch_efficiency_gap | pitching | starter_quality | UNDER | MEDIUM | DERIVABLE |
| 9 | groundball_rate_gap | pitching | starter_quality | UNKNOWN | MEDIUM | READY |
| 10 | starter_reliever_gap | pitching | starter_quality | UNDER | MEDIUM | READY |
| 11 | velo_recency_delta | pitching | starter_quality | UNDER | HIGH | DERIVABLE |
| 12 | velo_drop_single | pitching | starter_quality | UNDER | MEDIUM | DERIVABLE |
| 13 | velo_spike_single | pitching | starter_quality | UNDER | MEDIUM | DERIVABLE |
| 14 | spin_rate_recovery | pitching | starter_quality | UNDER | MEDIUM | DATA_MISSING |
| 15 | k_drought_regression | pitching | starter_quality | UNKNOWN | MEDIUM | DERIVABLE |
| 16 | fstrike_gap | pitching | starter_quality | UNDER | MEDIUM | READY |
| 17 | two_start_fatigue | pitching | starter_quality | OVER | MEDIUM | DERIVABLE |
| 18 | high_pitch_count_last | pitching | starter_quality | OVER | MEDIUM | DERIVABLE |
| 19 | high_pitch_count_two_ago | pitching | starter_quality | OVER | LOW | DERIVABLE |
| 20 | long_rest_return | pitching | starter_quality | UNKNOWN | LOW | DERIVABLE |
| 21 | third_start_post_il | pitching | starter_quality | UNKNOWN | MEDIUM | DATA_MISSING |
| 22 | stamina_cliff | pitching | starter_quality | OVER | LOW | DATA_MISSING |
| 23 | first_tto_suppression | pitching | starter_quality | UNDER | HIGH | DATA_MISSING |
| 24 | third_tto_collapse | pitching | starter_quality | OVER | HIGH | DATA_MISSING |
| 25 | hard_hit_suppression | pitching | starter_quality | UNDER | HIGH | DATA_MISSING |
| 26 | barrel_rate_gap | pitching | starter_quality | UNDER | HIGH | DATA_MISSING |
| 27 | contact_suppression_index | pitching | starter_quality | UNDER | MEDIUM | DATA_MISSING |
| 28 | command_collapse_risk | pitching | starter_quality | OVER | MEDIUM | DATA_MISSING |
| 29 | instability_score | pitching | starter_quality | OVER | MEDIUM | DATA_MISSING |
| 30 | chase_rate_mismatch | pitching | starter_quality | UNDER | MEDIUM | DATA_MISSING |
| 31 | repertoire_concentration | pitching | starter_quality | OVER | LOW | DATA_MISSING |
| 32 | babip_regression | pitching | starter_quality | UNKNOWN | LOW | DATA_MISSING |
| 33 | lob_regression | pitching | starter_quality | UNKNOWN | LOW | DATA_MISSING |
| 34 | platoon_punishment | pitching | lineup_shape | OVER | HIGH | DATA_MISSING |
| 35 | pitcher_home_road_gap | pitching | starter_quality | UNKNOWN | LOW | DATA_MISSING |
| 36 | pitcher_day_night_split | pitching | starter_quality | UNKNOWN | LOW | DATA_MISSING |
| 37 | high_csw_tight_umpire | interaction | multi_factor | UNDER | HIGH | READY |
| 38 | strikeout_pitcher_high_swing | interaction | multi_factor | UNDER | MEDIUM | DATA_MISSING |
| 39 | low_k_patient_lineup | interaction | multi_factor | OVER | MEDIUM | DERIVABLE |
| 40 | flyball_park_hr | interaction | multi_factor | OVER | HIGH | READY |
| 41 | flyball_large_park | interaction | multi_factor | UNDER | MEDIUM | READY |
| 42 | high_gb_hr_park | interaction | multi_factor | UNDER | LOW | READY |
| 43 | triple_flyball_park_wind | interaction | multi_factor | OVER | HIGH | READY |
| 44 | walk_compressor | interaction | multi_factor | OVER | MEDIUM | READY |
| 45 | ump_walk_walk_pitcher | interaction | multi_factor | OVER | LOW | DATA_MISSING |
| 46 | bullpen_xfip_gap | bullpen | bullpen_fatigue | UNDER | HIGH | READY |
| 47 | bullpen_workload_3d | bullpen | bullpen_fatigue | OVER | HIGH | DERIVABLE |
| 48 | bullpen_workload_2d | bullpen | bullpen_fatigue | OVER | HIGH | DERIVABLE |
| 49 | bullpen_fatigue_quality | bullpen | bullpen_fatigue | OVER | MEDIUM | DERIVABLE |
| 50 | closer_unavailable | bullpen | bullpen_fatigue | OVER | HIGH | DATA_MISSING |
| 51 | bullpen_3_consecutive | bullpen | bullpen_fatigue | OVER | MEDIUM | DERIVABLE |
| 52 | bullpen_high_leverage_yesterday | bullpen | bullpen_fatigue | OVER | MEDIUM | DATA_MISSING |
| 53 | top_relievers_unavailable | bullpen | bullpen_fatigue | OVER | HIGH | DATA_MISSING |
| 54 | bullpen_handedness_mismatch | bullpen | bullpen_fatigue | OVER | MEDIUM | DATA_MISSING |
| 55 | bullpen_era_xfip_gap | bullpen | bullpen_fatigue | UNKNOWN | LOW | DATA_MISSING |
| 56 | bullpen_walk_spike | bullpen | bullpen_fatigue | OVER | MEDIUM | DERIVABLE |
| 57 | bullpen_k_drop | bullpen | bullpen_fatigue | OVER | MEDIUM | DERIVABLE |
| 58 | bullpen_early_hook_risk | bullpen | bullpen_fatigue | OVER | MEDIUM | DERIVABLE |
| 59 | bullpen_depth_gap | bullpen | bullpen_fatigue | UNDER | LOW | DATA_MISSING |
| 60 | bullpen_fatigue_heat | bullpen | multi_factor | OVER | LOW | DERIVABLE |
| 61 | bullpen_fatigue_low_total | bullpen | multi_factor | OVER | MEDIUM | DERIVABLE |
| 62 | bullpen_meltdown_yesterday | bullpen | bullpen_fatigue | OVER | LOW | DERIVABLE |
| 63 | fatigue_bullpen_dependence | interaction | multi_factor | OVER | MEDIUM | DERIVABLE |
| 64 | day_after_night | schedule | schedule_fatigue | UNDER | MEDIUM | DERIVABLE |
| 65 | getaway_day | schedule | schedule_fatigue | UNDER | MEDIUM | DERIVABLE |
| 66 | cross_country_travel | schedule | schedule_fatigue | OVER | MEDIUM | DERIVABLE |
| 67 | timezone_change | schedule | schedule_fatigue | OVER | MEDIUM | DERIVABLE |
| 68 | extra_innings_yesterday | schedule | schedule_fatigue | OVER | MEDIUM | DERIVABLE |
| 69 | doubleheader_game2 | schedule | schedule_fatigue | OVER | MEDIUM | READY |
| 70 | rest_differential | schedule | schedule_fatigue | UNDER | MEDIUM | READY |
| 71 | compressed_5in4 | schedule | schedule_fatigue | OVER | MEDIUM | DERIVABLE |
| 72 | west_coast_return | schedule | schedule_fatigue | OVER | LOW | DERIVABLE |
| 73 | road_trip_length | schedule | schedule_fatigue | OVER | LOW | DERIVABLE |
| 74 | wind_flyball_out | weather | weather_environment | OVER | HIGH | READY |
| 75 | wind_flyball_in | weather | weather_environment | UNDER | MEDIUM | READY |
| 76 | temperature_power | weather | weather_environment | OVER | MEDIUM | DATA_MISSING |
| 77 | cold_breaking_ball | weather | weather_environment | UNDER | MEDIUM | DATA_MISSING |
| 78 | extreme_heat | weather | weather_environment | OVER | LOW | READY |
| 79 | temp_deviation | weather | weather_environment | UNKNOWN | LOW | DERIVABLE |
| 80 | humidity_carry | weather | weather_environment | OVER | LOW | DATA_MISSING |
| 81 | rain_delay_risk | weather | weather_environment | UNKNOWN | LOW | DATA_MISSING |
| 82 | altitude_weak_bullpen | weather | multi_factor | OVER | LOW | DERIVABLE |
| 83 | umpire_over_rate | umpire | umpire_zone | OVER | HIGH | READY |
| 84 | umpire_k_rate_delta | umpire | umpire_zone | UNDER | MEDIUM | READY |
| 85 | umpire_pitcher_park | umpire | multi_factor | UNDER | MEDIUM | READY |
| 86 | umpire_hitter_park | umpire | multi_factor | OVER | MEDIUM | READY |
| 87 | umpire_csw_interaction | umpire | multi_factor | UNDER | HIGH | READY |
| 88 | umpire_walk_pitcher | umpire | multi_factor | OVER | MEDIUM | DERIVABLE |
| 89 | umpire_zone_variance | umpire | umpire_zone | UNKNOWN | LOW | DATA_MISSING |
| 90 | wrc_gap | lineup | lineup_shape | OVER | MEDIUM | READY |
| 91 | lineup_missing_top_hitter | lineup | lineup_shape | UNDER | HIGH | DATA_MISSING |
| 92 | lineup_hand_cluster | lineup | lineup_shape | OVER | HIGH | DATA_MISSING |
| 93 | lineup_exit_velo_trend | lineup | lineup_shape | OVER | MEDIUM | DATA_MISSING |
| 94 | lineup_depth_score | lineup | lineup_shape | UNKNOWN | MEDIUM | DATA_MISSING |
| 95 | lineup_protection_loss | lineup | lineup_shape | UNDER | MEDIUM | DATA_MISSING |
| 96 | power_density | lineup | lineup_shape | OVER | MEDIUM | DATA_MISSING |
| 97 | contact_vs_k_pitcher | lineup | lineup_shape | OVER | MEDIUM | DATA_MISSING |
| 98 | park_run_factor | park | park_geometry | OVER | MEDIUM | READY |
| 99 | park_hr_factor | park | park_geometry | OVER | MEDIUM | READY |
| 100 | pull_rate_park | park | park_geometry | OVER | LOW | DATA_MISSING |
| 101 | defensive_runs_gap | interaction | other | UNDER | HIGH | DATA_MISSING |
| 102 | infield_defense_gb | interaction | other | UNDER | MEDIUM | DATA_MISSING |
| 103 | catcher_framing_command | interaction | other | UNDER | HIGH | DATA_MISSING |
| 104 | backup_catcher_penalty | interaction | other | OVER | MEDIUM | DATA_MISSING |
| 105 | baserunning_pressure | interaction | other | OVER | MEDIUM | DATA_MISSING |
| 106 | sb_suppression_index | interaction | other | UNDER | LOW | DATA_MISSING |
| 107 | debut_overreaction | interaction | other | UNKNOWN | LOW | DATA_MISSING |
| 108 | tanking_signal | interaction | other | UNKNOWN | LOW | DATA_MISSING |
| 109 | blowout_revenge | interaction | other | OVER | LOW | DERIVABLE |
| 110 | series_scouting_fatigue | interaction | other | OVER | MEDIUM | DERIVABLE |
| 111 | interleague_familiarity | interaction | other | OVER | LOW | DERIVABLE |
| 112 | opener_missequencing | interaction | other | OVER | MEDIUM | DATA_MISSING |
| 113 | new_pitch_introduction | interaction | other | UNKNOWN | LOW | DATA_MISSING |
| 114 | scoring_cluster_variance | interaction | other | UNKNOWN | LOW | DATA_MISSING |
| 115 | release_point_variance | interaction | other | OVER | MEDIUM | DATA_MISSING |
| 116 | age_workload_cliff | pitching | starter_quality | OVER | LOW | DATA_MISSING |

| 117 | adj_k_rate_last3 | pitching | starter_quality | rolling 3-start opp-adjusted K rate | UNDER | HIGH | DERIVABLE | INVESTIGATE |
