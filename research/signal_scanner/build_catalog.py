#!/usr/bin/env python3
"""
Build unified MLB signal catalog from Sources A (ChatGPT), B (Claude), C (new).
Deduplicates, structures, tags data status and priority.
"""

from pathlib import Path
import pandas as pd

OUT = Path("/Users/jw115/mlb-model/research/signal_scanner")

# Available pipeline data for status tagging
READY_FIELDS = {
    "sp_xfip", "sp_siera", "sp_csw_pct", "sp_whiff_pct", "sp_fstrike_pct",
    "sp_k_pct", "sp_bb_pct", "sp_gb_pct", "sp_avg_ip", "sp_throws",
    "bp_xfip", "wrc_plus", "park_factor_runs", "park_factor_hr",
    "temperature", "wind_speed", "wind_direction", "wind_factor_effective",
    "umpire_k_rate", "umpire_over_rate", "rest_days", "game_hour_utc",
    "doubleheader_flag", "roof_status", "actual_total", "close_total",
}
DERIVABLE_FIELDS = {
    "fb_velo", "fb_velo_r3", "fb_velo_r5", "velo_trend", "velo_season",
    "csw_r5", "whiff_r5", "f_strike_r5", "k_count", "bb_count",
    "total_pitches", "batters_faced", "innings_pitched", "pitches",
    "strikeouts", "walks", "ground_outs", "fly_outs", "air_outs",
    "hits_allowed", "runs_allowed", "earned_runs", "home_runs_allowed",
    "game_date", "season", "home_away", "opponent", "team",
    "starter_flag", "pitcher_hand",
}

signals = []
sid = 0

def add(name, domain, family, formula, inputs, direction, priority, status, variants=""):
    global sid
    sid += 1
    signals.append({
        "signal_id": sid, "signal_name": name, "domain": domain,
        "correlation_family": family, "formula": formula,
        "required_inputs": inputs, "direction": direction,
        "priority": priority, "data_status": status, "variants": variants,
    })

# ═══════════════════════════════════════════════
# PITCHING — STARTER QUALITY
# ═══════════════════════════════════════════════

add("xfip_gap", "pitching", "starter_quality",
    "away_sp_xfip - home_sp_xfip", "ft:sp_xfip", "UNDER", "HIGH", "READY",
    "A1(kbb subset), B58, C_implicit. Already deployed as F5 RL Signal B")

add("csw_gap", "pitching", "starter_quality",
    "home_sp_csw - away_sp_csw", "si:sp_csw_pct, csw:csw_r5", "UNDER", "HIGH", "READY",
    "A2, B_implicit. Core V1 feature")

add("whiff_gap", "pitching", "starter_quality",
    "home_sp_whiff - away_sp_whiff", "si:sp_whiff_pct, csw:whiff_r5", "UNDER", "HIGH", "READY",
    "A2 subset. Tested in F5 RL Signal C")

add("kbb_gap", "pitching", "starter_quality",
    "home_sp_kbb - away_sp_kbb", "ft:sp_k_pct,sp_bb_pct", "UNDER", "HIGH", "READY",
    "A1. Derivable from K% and BB%")

add("combined_pitcher_score", "pitching", "starter_quality",
    "(avg_csw) - 5*(avg_xfip)", "si:sp_csw_pct,sp_xfip", "UNDER", "HIGH", "READY",
    "Scanner S12. VALIDATED — deployed as overlay")

add("stuff_plus_gap", "pitching", "starter_quality",
    "home_stuff+ - away_stuff+", "statcast:stuff_plus", "UNDER", "HIGH", "DATA_MISSING",
    "A3. Requires Stuff+ from FanGraphs Pitch Models or Statcast")

add("siera_gap", "pitching", "starter_quality",
    "away_sp_siera - home_sp_siera", "ft:sp_siera", "UNDER", "MEDIUM", "READY",
    "Implicit in A1. SIERA in pipeline")

add("pitch_efficiency_gap", "pitching", "starter_quality",
    "home_pitches_per_pa - away_pitches_per_pa", "pgl:pitches,batters_faced", "UNDER", "MEDIUM", "DERIVABLE",
    "A8. Derivable from game logs")

add("groundball_rate_gap", "pitching", "starter_quality",
    "home_sp_gb - away_sp_gb", "ft:sp_gb_pct", "UNKNOWN", "MEDIUM", "READY",
    "A38/B14/B21 base. GB effects context-dependent")

add("starter_reliever_gap", "pitching", "starter_quality",
    "(away_sp_xfip - away_bp_xfip) - (home_sp_xfip - home_bp_xfip)", "ft:sp_xfip,bp_xfip", "UNDER", "MEDIUM", "READY",
    "B58. F5 vs full-game divergence signal")

# ═══ PITCHING — FORM/RECENCY ═══

add("velo_recency_delta", "pitching", "starter_quality",
    "(home_velo_last3 - home_velo_season) - (away_velo_last3 - away_velo_season)",
    "csw:fb_velo_r3,fb_velo_season", "UNDER", "HIGH", "DERIVABLE",
    "A4, B5. Scanner S04 — MARGINAL, correct direction")

add("velo_drop_single", "pitching", "starter_quality",
    "sp_velo_last1 - sp_velo_season", "csw:fb_velo", "UNDER", "MEDIUM", "DERIVABLE",
    "C7. Single-start velocity drop")

add("velo_spike_single", "pitching", "starter_quality",
    "sp_velo_last1 - sp_velo_season (positive)", "csw:fb_velo", "UNDER", "MEDIUM", "DERIVABLE",
    "C8. Single-start velocity gain")

add("spin_rate_recovery", "pitching", "starter_quality",
    "spin_last3 - spin_season", "statcast:release_spin_rate", "UNDER", "MEDIUM", "DATA_MISSING",
    "B94. Requires pitch-level spin from Statcast")

add("k_drought_regression", "pitching", "starter_quality",
    "(k_rate_last5 - k_rate_season) when CSW holds", "csw:csw_r5, pgl:K,BF", "UNKNOWN", "MEDIUM", "DERIVABLE",
    "B96. Scanner S23 — FLAT direction")

add("fstrike_gap", "pitching", "starter_quality",
    "home_fstrike - away_fstrike", "csw:f_strike_r5", "UNDER", "MEDIUM", "READY",
    "Implicit in B92. F-strike% in pipeline")

# ═══ PITCHING — FATIGUE/WORKLOAD ═══

add("two_start_fatigue", "pitching", "starter_quality",
    "2nd_start_7d * ip_first_start", "pgl:game_date,innings_pitched", "OVER", "MEDIUM", "DERIVABLE",
    "B22, B74, C11. Short rest signal")

add("high_pitch_count_last", "pitching", "starter_quality",
    "pitches_last >= 105", "csw:total_pitches", "OVER", "MEDIUM", "DERIVABLE",
    "C12. High workload carryover")

add("high_pitch_count_two_ago", "pitching", "starter_quality",
    "pitches_2ago >= 105", "csw:total_pitches", "OVER", "LOW", "DERIVABLE",
    "C13. Lagged workload")

add("long_rest_return", "pitching", "starter_quality",
    "days_rest >= 8", "pgl:game_date", "UNKNOWN", "LOW", "DERIVABLE",
    "C10. Rust vs recovery")

add("third_start_post_il", "pitching", "starter_quality",
    "is_3rd_start_after_IL", "roster:IL_data", "UNKNOWN", "MEDIUM", "DATA_MISSING",
    "C9. Requires IL transaction data")

add("stamina_cliff", "pitching", "starter_quality",
    "(pitch_count_last5 - season_avg) * manager_hook", "csw:total_pitches", "OVER", "LOW", "DATA_MISSING",
    "B1. Manager hook tendency unavailable")

# ═══ PITCHING — TTO/SEQUENCING ═══

add("first_tto_suppression", "pitching", "starter_quality",
    "1st_tto_woba - overall_woba", "statcast:tto_splits", "UNDER", "HIGH", "DATA_MISSING",
    "A6, B4. F5-specific value. Requires TTO splits")

add("third_tto_collapse", "pitching", "starter_quality",
    "3rd_tto_woba - 1st_tto_woba", "statcast:tto_splits", "OVER", "HIGH", "DATA_MISSING",
    "A7, B52. Full-game decay signal")

# ═══ PITCHING — CONTACT QUALITY ═══

add("hard_hit_suppression", "pitching", "starter_quality",
    "opp_hard_hit - sp_hard_hit_allowed", "statcast:hard_hit_rate", "UNDER", "HIGH", "DATA_MISSING",
    "A5, B11. Requires Statcast batted ball data")

add("barrel_rate_gap", "pitching", "starter_quality",
    "sp_barrel_allowed - opp_barrel_rate", "statcast:barrel_rate", "UNDER", "HIGH", "DATA_MISSING",
    "A22, B11. Requires Statcast")

add("contact_suppression_index", "pitching", "starter_quality",
    "csw / hard_hit_allowed", "si:csw + statcast:hard_hit", "UNDER", "MEDIUM", "DATA_MISSING",
    "A51. Partial — CSW available, hard_hit needs Statcast")

# ═══ PITCHING — COMMAND/CONTROL ═══

add("command_collapse_risk", "pitching", "starter_quality",
    "bb_pct / zone_pct", "ft:bb_pct + statcast:zone_pct", "OVER", "MEDIUM", "DATA_MISSING",
    "A9. Zone% needs Statcast")

add("instability_score", "pitching", "starter_quality",
    "bb_pct * hard_hit_allowed", "ft:bb_pct + statcast", "OVER", "MEDIUM", "DATA_MISSING",
    "A10, A50. Interaction of walk rate and contact quality")

add("chase_rate_mismatch", "pitching", "starter_quality",
    "pitcher_o_swing - opp_o_swing", "statcast:o_swing", "UNDER", "MEDIUM", "DATA_MISSING",
    "B20. Requires O-Swing% from Statcast")

add("repertoire_concentration", "pitching", "starter_quality",
    "1 - pitch_entropy", "statcast:pitch_type_pct", "OVER", "LOW", "DATA_MISSING",
    "B39, A46. Requires pitch usage data")

add("babip_regression", "pitching", "starter_quality",
    "sp_babip - sp_career_babip", "fangraphs:babip", "UNKNOWN", "LOW", "DATA_MISSING",
    "C19. Requires BABIP splits")

add("lob_regression", "pitching", "starter_quality",
    "strand_rate - xstrand_rate", "fangraphs:strand_rate", "UNKNOWN", "LOW", "DATA_MISSING",
    "C20, B35. Requires strand rate data")

# ═══ PITCHING — SPLITS ═══

add("platoon_punishment", "pitching", "lineup_shape",
    "lineup_same_hand_pct * pitcher_platoon_split", "lineup+splits", "OVER", "HIGH", "DATA_MISSING",
    "B2, A47, A48, C16, C94. Requires lineup composition + platoon splits")

add("pitcher_home_road_gap", "pitching", "starter_quality",
    "sp_era_home - sp_era_road", "splits:home/road", "UNKNOWN", "LOW", "DATA_MISSING",
    "C15. Requires home/road split data")

add("pitcher_day_night_split", "pitching", "starter_quality",
    "sp_era_day - sp_era_night", "splits:day/night", "UNKNOWN", "LOW", "DATA_MISSING",
    "C14. Requires day/night splits")

# ═══ PITCHING — INTERACTIONS ═══

add("high_csw_tight_umpire", "interaction", "multi_factor",
    "sp_csw * umpire_k_rate", "si:csw + ft:umpire_k_rate", "UNDER", "HIGH", "READY",
    "C3, B6, B19, B62. Scanner S11 variant")

add("strikeout_pitcher_high_swing", "interaction", "multi_factor",
    "sp_k_rate * opp_swing_rate", "ft:k_pct + statcast:swing_rate", "UNDER", "MEDIUM", "DATA_MISSING",
    "C4. Requires team swing rate")

add("low_k_patient_lineup", "interaction", "multi_factor",
    "(1/sp_k_rate) * opp_bb_rate", "ft:k_pct,bb_pct", "OVER", "MEDIUM", "DERIVABLE",
    "C5. Derivable from existing K% and BB%")

add("flyball_park_hr", "interaction", "multi_factor",
    "sp_fb_rate * park_hr_factor", "ft:gb_pct,park_factor_hr", "OVER", "HIGH", "READY",
    "A38, B36, C17. Scanner S18")

add("flyball_large_park", "interaction", "multi_factor",
    "sp_fb_rate * (1/park_hr_factor)", "ft:gb_pct,park_factor_hr", "UNDER", "MEDIUM", "READY",
    "C18. Inverse of flyball_park_hr")

add("high_gb_hr_park", "interaction", "multi_factor",
    "sp_gb_rate * park_hr_factor", "ft:gb_pct,park_factor_hr", "UNDER", "LOW", "READY",
    "C17. GB pitcher in HR park — mixed effect")

add("triple_flyball_park_wind", "interaction", "multi_factor",
    "sp_fb_rate * park_hr * wind_out", "ft:gb_pct,park_factor_hr,wind", "OVER", "HIGH", "READY",
    "C97, B36. Triple interaction")

add("walk_compressor", "interaction", "multi_factor",
    "(sp_bb_h + sp_bb_a) * ump_ball_rate", "ft:bb_pct,umpire_over_rate", "OVER", "MEDIUM", "READY",
    "Scanner S13 — MARGINAL. B41, C98")

add("ump_walk_walk_pitcher", "interaction", "multi_factor",
    "ump_bb_rate * sp_bb_rate * opp_obp", "ft:umpire,bb_pct + statcast:obp", "OVER", "LOW", "DATA_MISSING",
    "C98. Requires team OBP")

# ═══ BULLPEN ═══

add("bullpen_xfip_gap", "bullpen", "bullpen_fatigue",
    "away_bp_xfip - home_bp_xfip", "ft:bp_xfip", "UNDER", "HIGH", "READY",
    "A12, Scanner S15. SHELVED — p=0.20, absorbed by total")

add("bullpen_workload_3d", "bullpen", "bullpen_fatigue",
    "away_bp_ip_3d - home_bp_ip_3d", "pgl:reliever IP by date", "OVER", "HIGH", "DERIVABLE",
    "A13, B3, C21. Scanner S16")

add("bullpen_workload_2d", "bullpen", "bullpen_fatigue",
    "bp_pitches_2d / bp_season_avg_daily", "pgl:reliever pitches", "OVER", "HIGH", "DERIVABLE",
    "C22. Normalized recent usage")

add("bullpen_fatigue_quality", "bullpen", "bullpen_fatigue",
    "bp_ip_2d * bp_era", "pgl+ft:bp_xfip", "OVER", "MEDIUM", "DERIVABLE",
    "A18, Scanner S17")

add("closer_unavailable", "bullpen", "bullpen_fatigue",
    "closer_pitches_last2d > threshold", "pgl:closer identification", "OVER", "HIGH", "DATA_MISSING",
    "A15, B25, C24. Requires closer ID + usage tracking")

add("bullpen_3_consecutive", "bullpen", "bullpen_fatigue",
    "bp_used_3_straight_games flag", "pgl:game dates", "OVER", "MEDIUM", "DERIVABLE",
    "C23. Derivable from game logs")

add("bullpen_high_leverage_yesterday", "bullpen", "bullpen_fatigue",
    "bp_high_lev_ip_yesterday", "pgl:leverage data", "OVER", "MEDIUM", "DATA_MISSING",
    "A14, C33. Requires leverage index")

add("top_relievers_unavailable", "bullpen", "bullpen_fatigue",
    "count_unavailable_top >= 3", "pgl:reliever ID + usage", "OVER", "HIGH", "DATA_MISSING",
    "B12, B99, C25. Requires reliever hierarchy")

add("bullpen_handedness_mismatch", "bullpen", "bullpen_fatigue",
    "lineup_hand_pct - bp_matching_hand_pct", "lineup+roster", "OVER", "MEDIUM", "DATA_MISSING",
    "A17, B32, B56, C31. Requires lineup + reliever handedness")

add("bullpen_era_xfip_gap", "bullpen", "bullpen_fatigue",
    "bp_era - bp_xfip", "ft:bp_xfip + fangraphs:bp_era", "UNKNOWN", "LOW", "DATA_MISSING",
    "C27. ERA not in pipeline; xFIP is")

add("bullpen_walk_spike", "bullpen", "bullpen_fatigue",
    "bp_bb_last7 - bp_bb_season", "pgl:reliever walks", "OVER", "MEDIUM", "DERIVABLE",
    "C29. Derivable from reliever game logs")

add("bullpen_k_drop", "bullpen", "bullpen_fatigue",
    "bp_k_season - bp_k_last7", "pgl:reliever strikeouts", "OVER", "MEDIUM", "DERIVABLE",
    "C30. Derivable from reliever game logs")

add("bullpen_early_hook_risk", "bullpen", "bullpen_fatigue",
    "starter_avg_ip_last5 < 5.0", "pgl:starter IP", "OVER", "MEDIUM", "DERIVABLE",
    "C37, B58. Short-start risk = more BP exposure")

add("bullpen_depth_gap", "bullpen", "bullpen_fatigue",
    "home_bp_depth - away_bp_depth", "pgl:reliever usage patterns", "UNDER", "LOW", "DATA_MISSING",
    "C34. Requires depth score derivation")

add("bullpen_fatigue_heat", "bullpen", "multi_factor",
    "bp_pitches_2d * temp_above_85", "pgl+ft:temperature", "OVER", "LOW", "DERIVABLE",
    "C35. Interaction — derivable")

add("bullpen_fatigue_low_total", "bullpen", "multi_factor",
    "bp_pitches_2d * (close_total <= 7.5)", "pgl+ms:close_total", "OVER", "MEDIUM", "DERIVABLE",
    "C36. Low-total BP fatigue matters more")

add("bullpen_meltdown_yesterday", "bullpen", "bullpen_fatigue",
    "bp_runs_allowed_last > 5", "pgl:reliever runs", "OVER", "LOW", "DERIVABLE",
    "C39. Blowout drain")

add("fatigue_bullpen_dependence", "interaction", "multi_factor",
    "compressed_schedule * starter_avg_ip_last5", "pgl:schedule+IP", "OVER", "MEDIUM", "DERIVABLE",
    "C99. Short starters in compressed schedule")

# ═══ SCHEDULE / FATIGUE ═══

add("day_after_night", "schedule", "schedule_fatigue",
    "is_day_game * prev_end_hour", "ft:game_hour_utc + schedule", "UNDER", "MEDIUM", "DERIVABLE",
    "A43, B37, C41. Scanner S20")

add("getaway_day", "schedule", "schedule_fatigue",
    "last_game_series * travel_after", "schedule:series_game_number", "UNDER", "MEDIUM", "DERIVABLE",
    "C42. Derivable from schedule")

add("cross_country_travel", "schedule", "schedule_fatigue",
    "miles_last24h >= 2000", "schedule:venue coords", "OVER", "MEDIUM", "DERIVABLE",
    "A42, B10, C45. Derivable from stadium lat/lon in config")

add("timezone_change", "schedule", "schedule_fatigue",
    "abs(tz_delta) >= 2", "schedule:team TZ", "OVER", "MEDIUM", "DERIVABLE",
    "C46. Derivable from team timezone map")

add("extra_innings_yesterday", "schedule", "schedule_fatigue",
    "prev_innings >= 10", "ft:innings_played (prior game)", "OVER", "MEDIUM", "DERIVABLE",
    "C47. Derivable from feature table")

add("doubleheader_game2", "schedule", "schedule_fatigue",
    "is_dh_game2", "ft:doubleheader_flag,game_number", "OVER", "MEDIUM", "READY",
    "C48. Already in feature table")

add("rest_differential", "schedule", "schedule_fatigue",
    "home_rest - away_rest", "ft:rest_days", "UNDER", "MEDIUM", "READY",
    "Scanner S21. In pipeline")

add("compressed_5in4", "schedule", "schedule_fatigue",
    "games_last4days >= 5", "schedule:game dates", "OVER", "MEDIUM", "DERIVABLE",
    "C51. Derivable from schedule")

add("west_coast_return", "schedule", "schedule_fatigue",
    "from_west_coast * game1_home", "schedule:venue", "OVER", "LOW", "DERIVABLE",
    "C57, B53. Travel recovery")

add("road_trip_length", "schedule", "schedule_fatigue",
    "road_games_streak", "schedule:game dates", "OVER", "LOW", "DERIVABLE",
    "A44, B18, C43-44")

# ═══ WEATHER ═══

add("wind_flyball_out", "weather", "weather_environment",
    "wind_speed * wind_out * avg_fb_rate", "ft:wind+gb_pct", "OVER", "HIGH", "READY",
    "A40, C60, C97. Already in V1 as flyball×wind")

add("wind_flyball_in", "weather", "weather_environment",
    "wind_speed * wind_in * avg_fb_rate", "ft:wind+gb_pct", "UNDER", "MEDIUM", "READY",
    "C61. Inverse — wind suppression")

add("temperature_power", "weather", "weather_environment",
    "temperature * team_ev", "ft:temp + statcast:exit_velo", "OVER", "MEDIUM", "DATA_MISSING",
    "A41, B89. Team exit velo needs Statcast")

add("cold_breaking_ball", "weather", "weather_environment",
    "(60-temp) * breaking_ball_pct when temp < 60", "ft:temp + statcast:pitch_type", "UNDER", "MEDIUM", "DATA_MISSING",
    "C64, B34. Breaking ball % needs Statcast")

add("extreme_heat", "weather", "weather_environment",
    "temp >= 95", "ft:temperature", "OVER", "LOW", "READY",
    "C71. Simple flag")

add("temp_deviation", "weather", "weather_environment",
    "temp - park_seasonal_avg", "ft:temp + derived", "UNKNOWN", "LOW", "DERIVABLE",
    "C65. Seasonal avg derivable")

add("humidity_carry", "weather", "weather_environment",
    "humidity * fb_rate", "weather:humidity + ft:gb_pct", "OVER", "LOW", "DATA_MISSING",
    "C62, C70. Humidity not in pipeline")

add("rain_delay_risk", "weather", "weather_environment",
    "precip_prob >= 50", "weather:precipitation", "UNKNOWN", "LOW", "DATA_MISSING",
    "C67, B69. Precip probability not in pipeline")

add("altitude_weak_bullpen", "weather", "multi_factor",
    "park_altitude * bp_xfip", "config:lat/lon + ft:bp_xfip", "OVER", "LOW", "DERIVABLE",
    "C68, B34. Altitude derivable from park coords")

# ═══ UMPIRE ═══

add("umpire_over_rate", "umpire", "umpire_zone",
    "ump_over_rate - 0.50", "ft:umpire_over_rate", "OVER", "HIGH", "READY",
    "C85. Historical umpire bias. Already in pipeline")

add("umpire_k_rate_delta", "umpire", "umpire_zone",
    "ump_k_rate - league_k_rate", "ft:umpire_k_rate", "UNDER", "MEDIUM", "READY",
    "C79. Umpire strikeout tendency")

add("umpire_pitcher_park", "umpire", "multi_factor",
    "(1/ump_runs) * (1/park_runs)", "ft:umpire_over_rate,park_factor", "UNDER", "MEDIUM", "READY",
    "C81. Double suppression")

add("umpire_hitter_park", "umpire", "multi_factor",
    "ump_runs * park_runs", "ft:umpire_over_rate,park_factor", "OVER", "MEDIUM", "READY",
    "C80. Double inflation")

add("umpire_csw_interaction", "umpire", "multi_factor",
    "ump_k_rate * avg_csw", "ft:umpire + si:csw", "UNDER", "HIGH", "READY",
    "C82, B6. Scanner S11")

add("umpire_walk_pitcher", "umpire", "multi_factor",
    "ump_bb_rate * avg_sp_bb_rate", "ft:umpire + ft:bb_pct", "OVER", "MEDIUM", "DERIVABLE",
    "C83. Ump BB rate derivable from umpire data")

add("umpire_zone_variance", "umpire", "umpire_zone",
    "ump_zone_consistency", "umpire_scorecards:consistency", "UNKNOWN", "LOW", "DATA_MISSING",
    "C86. Requires zone consistency metric")

# ═══ LINEUP ═══

add("wrc_gap", "lineup", "lineup_shape",
    "home_wrc - away_wrc", "ft:wrc_plus", "OVER", "MEDIUM", "READY",
    "Scanner S22. A19-A22 merged")

add("lineup_missing_top_hitter", "lineup", "lineup_shape",
    "top_hitter_out * wrc", "lineup:daily composition", "UNDER", "HIGH", "DATA_MISSING",
    "C87, B82. Requires daily lineup data")

add("lineup_hand_cluster", "lineup", "lineup_shape",
    "pct_vs_platoon_disadvantage", "lineup+pitcher hand", "OVER", "HIGH", "DATA_MISSING",
    "C89, B2, A47-48")

add("lineup_exit_velo_trend", "lineup", "lineup_shape",
    "team_ev_last7 - team_ev_season", "statcast:exit_velo", "OVER", "MEDIUM", "DATA_MISSING",
    "C90. Requires Statcast team batted ball")

add("lineup_depth_score", "lineup", "lineup_shape",
    "top5_wrc - bottom4_wrc", "lineup:individual hitter stats", "UNKNOWN", "MEDIUM", "DATA_MISSING",
    "A23, A24, B97, C93")

add("lineup_protection_loss", "lineup", "lineup_shape",
    "rbi_hitter_behind_wrc", "lineup+injury", "UNDER", "MEDIUM", "DATA_MISSING",
    "C93, B82")

add("power_density", "lineup", "lineup_shape",
    "team_barrel * team_flyball", "statcast:barrel+fb", "OVER", "MEDIUM", "DATA_MISSING",
    "A28, A52")

add("contact_vs_k_pitcher", "lineup", "lineup_shape",
    "team_contact - sp_k_rate", "statcast:contact + ft:k_pct", "OVER", "MEDIUM", "DATA_MISSING",
    "A25")

# ═══ PARK ═══

add("park_run_factor", "park", "park_geometry",
    "park_factor_runs", "ft:park_factor_runs", "OVER", "MEDIUM", "READY",
    "Baseline park factor. Already in V1")

add("park_hr_factor", "park", "park_geometry",
    "park_factor_hr", "ft:park_factor_hr", "OVER", "MEDIUM", "READY",
    "HR-specific park factor")

add("pull_rate_park", "park", "park_geometry",
    "team_pull * park_pull_hr", "statcast:pull + config:park", "OVER", "LOW", "DATA_MISSING",
    "A26, B7, C100")

# ═══ DEFENSE ═══

add("defensive_runs_gap", "interaction", "other",
    "home_drs - away_drs", "fangraphs:DRS or statcast:OAA", "UNDER", "HIGH", "DATA_MISSING",
    "A29-32, B8, B14, B95")

add("infield_defense_gb", "interaction", "other",
    "infield_defense * sp_gb_rate", "statcast:OAA + ft:gb_pct", "UNDER", "MEDIUM", "DATA_MISSING",
    "A30, B14")

# ═══ CATCHER ═══

add("catcher_framing_command", "interaction", "other",
    "catcher_framing * pitcher_zone_rate", "savant:framing + statcast:zone", "UNDER", "HIGH", "DATA_MISSING",
    "A33, B13, B51. Requires framing + zone data")

add("backup_catcher_penalty", "interaction", "other",
    "is_backup * framing_dependence", "roster:catcher + savant:framing", "OVER", "MEDIUM", "DATA_MISSING",
    "B44, B68")

# ═══ BASERUNNING ═══

add("baserunning_pressure", "interaction", "other",
    "sb_success + xbt_pct", "fangraphs:baserunning", "OVER", "MEDIUM", "DATA_MISSING",
    "A34-37, B33, B57")

add("sb_suppression_index", "interaction", "other",
    "catcher_pop_time * pitcher_delivery", "statcast:pop_time+delivery", "UNDER", "LOW", "DATA_MISSING",
    "B33")

# ═══ EXPERIMENTAL ═══

add("debut_overreaction", "interaction", "other",
    "is_debut * scouting_completeness", "roster:debut flag", "UNKNOWN", "LOW", "DATA_MISSING",
    "B54")

add("tanking_signal", "interaction", "other",
    "playoff_prob * remaining_games * young_sp", "standings+roster", "UNKNOWN", "LOW", "DATA_MISSING",
    "B93, C59")

add("blowout_revenge", "interaction", "other",
    "prev_margin * same_opponent", "ft:scores + schedule", "OVER", "LOW", "DERIVABLE",
    "B63, C25. Behavioral — likely noise")

add("series_scouting_fatigue", "interaction", "other",
    "games_vs_opp_last10d", "schedule:opponent history", "OVER", "MEDIUM", "DERIVABLE",
    "B46. Scanner S50. Repeated exposure")

add("interleague_familiarity", "interaction", "other",
    "is_interleague * days_since_faced", "schedule:leagues", "OVER", "LOW", "DERIVABLE",
    "B43, Scanner S24")

add("opener_missequencing", "interaction", "other",
    "is_opener * top3_woba", "roster:opener flag + lineup", "OVER", "MEDIUM", "DATA_MISSING",
    "B9")

add("new_pitch_introduction", "interaction", "other",
    "new_pitch_pct_last3", "statcast:pitch_type tracking", "UNKNOWN", "LOW", "DATA_MISSING",
    "B60")

add("scoring_cluster_variance", "interaction", "other",
    "inning_runs_variance / avg_runs", "game_logs:inning_scoring", "UNKNOWN", "LOW", "DATA_MISSING",
    "B80")

add("release_point_variance", "interaction", "other",
    "release_point_std_last3", "statcast:release_pos", "OVER", "MEDIUM", "DATA_MISSING",
    "B81, B98")

add("age_workload_cliff", "pitching", "starter_quality",
    "age * (recent_ip - career_avg)", "roster:age + pgl:IP", "OVER", "LOW", "DATA_MISSING",
    "B16, B71, B77, B90")

# ── Build DataFrame ──────────────────────────────────────────────────────────

df = pd.DataFrame(signals)

# ── Summary ──────────────────────────────────────────────────────────────────

print("=" * 60)
print("SIGNAL CATALOG — SUMMARY")
print("=" * 60)

print(f"\nTotal signals after dedup: {len(df)}")

print(f"\nBy domain:")
for d, n in df["domain"].value_counts().sort_index().items():
    print(f"  {d:15s}: {n}")

print(f"\nBy data_status:")
for s, n in df["data_status"].value_counts().items():
    print(f"  {s:15s}: {n}")

print(f"\nBy priority:")
for p, n in df["priority"].value_counts().items():
    print(f"  {p:15s}: {n}")

print(f"\nBy correlation_family:")
for c, n in df["correlation_family"].value_counts().items():
    print(f"  {c:20s}: {n}")

# Top 20 HIGH + READY/DERIVABLE
top = df[(df["priority"] == "HIGH") & (df["data_status"].isin(["READY", "DERIVABLE"]))].copy()
print(f"\n{'='*60}")
print(f"TOP PRIORITY SIGNALS (HIGH + READY/DERIVABLE): {len(top)}")
print(f"{'='*60}")
for _, r in top.iterrows():
    print(f"  [{r['signal_id']:3d}] {r['signal_name']:30s} | {r['domain']:12s} | {r['data_status']:10s} | {r['direction']}")

# Save
df.to_parquet(OUT / "signal_catalog.parquet", index=False)

# Write markdown
md = []
md.append("# MLB Signal Catalog\n\n")
md.append(f"Total signals: {len(df)}\n\n")
md.append(f"| Status | Count |\n|--------|-------|\n")
for s, n in df["data_status"].value_counts().items():
    md.append(f"| {s} | {n} |\n")
md.append(f"\n| Priority | Count |\n|----------|-------|\n")
for p, n in df["priority"].value_counts().items():
    md.append(f"| {p} | {n} |\n")

md.append(f"\n## Top Priority (HIGH + READY/DERIVABLE)\n\n")
md.append("| ID | Name | Domain | Status | Direction |\n|-----|------|--------|--------|----------|\n")
for _, r in top.iterrows():
    md.append(f"| {r['signal_id']} | {r['signal_name']} | {r['domain']} | {r['data_status']} | {r['direction']} |\n")

md.append(f"\n## Full Catalog\n\n")
md.append("| ID | Name | Domain | Family | Direction | Priority | Status |\n")
md.append("|-----|------|--------|--------|-----------|----------|--------|\n")
for _, r in df.iterrows():
    md.append(f"| {r['signal_id']} | {r['signal_name']} | {r['domain']} | {r['correlation_family']} | {r['direction']} | {r['priority']} | {r['data_status']} |\n")

with open(OUT / "signal_catalog.md", "w") as f:
    f.writelines(md)

print(f"\nFiles saved:")
print(f"  {OUT / 'signal_catalog.parquet'}")
print(f"  {OUT / 'signal_catalog.md'}")
PYEOF
