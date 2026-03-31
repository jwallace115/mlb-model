#!/usr/bin/env python3
"""Build merged, deduplicated MLB signal inventory from List A + List B."""

import json
from pathlib import Path
import pandas as pd

OUT = Path("/Users/jw115/mlb-model/research/signal_scanner")

# ── Define all signals after dedup ──────────────────────────────────────────

signals = [
    # ═══ STARTER BUCKET ═══
    {"signal_id": 1, "name": "K-BB% gap between starters", "formula": "home_sp_kbb - away_sp_kbb",
     "mechanism": "Better K-BB pitchers suppress runs more reliably than ERA-based pricing captures",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "feature_table (sp_k_pct, sp_bb_pct), pitcher_game_logs (K, BB, BF)",
     "variants": "A1. Derivable from existing K% and BB%"},

    {"signal_id": 2, "name": "CSW% gap between starters", "formula": "home_sp_csw - away_sp_csw",
     "mechanism": "CSW captures dominance and command better than surface stats, especially early in games",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "per_start_csv (csw_r5), sim_inputs (sp_csw_pct)",
     "variants": "A2. Already used in V1 simulation engine"},

    {"signal_id": 3, "name": "xFIP gap between starters", "formula": "away_sp_xfip - home_sp_xfip",
     "mechanism": "xFIP mismatch captures starter quality differential — validated as Signal B in F5 RL research",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "feature_table, sim_inputs (sp_xfip)",
     "variants": "Subset of A1/B58. Already deployed as F5 RL Signal B"},

    {"signal_id": 4, "name": "Stuff+ gap between starters", "formula": "home_stuff_plus - away_stuff_plus",
     "mechanism": "Raw pitch quality mismatches may matter more than public-facing ERA/xFIP",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires Stuff+ from Statcast pitch-level or FanGraphs Pitch Models",
     "variants": "A3"},

    {"signal_id": 5, "name": "Velocity recency delta", "formula": "velo_last3 - velo_season",
     "mechanism": "Velocity drops precede ERA spikes by 2-3 starts; a leading indicator books miss",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "per_start_csv (fb_velo_r3, fb_velo_season, velo_trend)",
     "variants": "A4, B5. Merged — same mechanism, velo change over recent starts"},

    {"signal_id": 6, "name": "First-time-through-order suppression", "formula": "pitcher_1st_tto_woba - pitcher_overall_woba",
     "mechanism": "Elite sequencers suppress 1st TTO hitters dramatically; F5-specific value",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires TTO splits from Statcast pitch-level or FanGraphs",
     "variants": "A6, B4. Merged — same 1st TTO mechanism"},

    {"signal_id": 7, "name": "Third-time-through-order collapse", "formula": "pitcher_3rd_tto_woba - pitcher_1st_tto_woba",
     "mechanism": "Large 3rd TTO penalties are overvalued in full-game markets, undervalued in F5",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires TTO splits from Statcast/FanGraphs",
     "variants": "A7, B52. Merged — same TTO decay mechanism"},

    {"signal_id": 8, "name": "Pitch efficiency (pitches per PA)", "formula": "pitches_per_pa",
     "mechanism": "Inefficient pitchers create early exits and extra bullpen exposure",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "pitcher_game_logs (pitches, batters_faced), per_start_csv (total_pitches)",
     "variants": "A8"},

    {"signal_id": 9, "name": "Command collapse risk", "formula": "bb_pct / zone_pct",
     "mechanism": "Pitchers who both miss the zone and walk hitters are blow-up candidates",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires zone% from Statcast pitch-level data",
     "variants": "A9. BB% available; zone% needs new pull"},

    {"signal_id": 10, "name": "Instability score (BB × hard hit)", "formula": "bb_pct * hard_hit_pct_allowed",
     "mechanism": "Walks plus hard contact create explosive innings more than either stat alone",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "BB% available; hard_hit_pct_allowed needs Statcast pitch-level",
     "variants": "A10, A50 (mismatch severity). Merged interaction signals"},

    {"signal_id": 11, "name": "Whiff% gap between starters", "formula": "home_sp_whiff - away_sp_whiff",
     "mechanism": "Whiff rate captures swing-and-miss ability; validated in F5 RL Signal C",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "per_start_csv (whiff_r5), sim_inputs (sp_whiff_pct)",
     "variants": "Implicit in A2/A51. Already tested in F5 RL research"},

    {"signal_id": 12, "name": "Starter stamina cliff", "formula": "(pitch_count_last5 - season_avg) × manager_hook_tendency",
     "mechanism": "Pitchers beyond recent conditioning level exit earlier than market expects",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Pitch counts available; manager hook tendency needs derivation",
     "variants": "B1"},

    {"signal_id": 13, "name": "Platoon punishment index", "formula": "pct_lineup_same_hand × pitcher_platoon_split",
     "mechanism": "Lineups stacked against pitcher's platoon weakness create underpriced scoring",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires lineup composition per game + platoon splits",
     "variants": "B2, A47, A48. Merged handedness signals"},

    {"signal_id": 14, "name": "Pitch repertoire concentration", "formula": "1 - pitcher_repertoire_entropy",
     "mechanism": "One-pitch-dependent pitchers are more predictable when that pitch isn't working",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires pitch-type usage from Statcast",
     "variants": "B39, A46 (pitch type vs lineup)"},

    {"signal_id": 15, "name": "Starter-reliever quality gap", "formula": "starter_fip - bullpen_fip",
     "mechanism": "Elite starters with poor bullpens are mispriced between F5 and full-game",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "feature_table (sp_xfip, bp_xfip)",
     "variants": "B58"},

    {"signal_id": 16, "name": "Contact suppression index", "formula": "csw_pct / hard_hit_pct_allowed",
     "mechanism": "Missing bats while avoiding hard contact identifies hidden aces",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "CSW available; hard_hit_pct_allowed needs Statcast",
     "variants": "A51"},

    {"signal_id": 17, "name": "Groundball rate", "formula": "pitcher_gb_pct",
     "mechanism": "Groundball tendency interacts with defense, park, and lineup composition",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "feature_table (sp_gb_pct), pitcher_game_logs (ground_outs, fly_outs)",
     "variants": "Base stat for A38, A39, B14, B21, B42, B57"},

    {"signal_id": 18, "name": "Strikeout drought regression", "formula": "(k_rate_last5 - season_k_rate) × csw_last5",
     "mechanism": "If K rate lags while CSW holds, strikeout regression is imminent",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "per_start_csv (k_count, csw_r5), pitcher_game_logs (K, BF)",
     "variants": "B96"},

    {"signal_id": 19, "name": "Spin rate recovery", "formula": "spin_rate_last3 - season_avg_spin",
     "mechanism": "Rebounding spin forecasts improving pitch quality before ERA changes",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires pitch-level spin rate from Statcast",
     "variants": "B94"},

    {"signal_id": 20, "name": "Two-start pitcher fatigue", "formula": "is_2nd_start_in_7d × ip_first_start × age",
     "mechanism": "Short rest with heavy prior workload causes velocity and command decline",
     "bucket": "starter", "tag": "READY_NOW",
     "data_sources": "pitcher_game_logs (game_date, IP), per_start_csv (total_pitches)",
     "variants": "B22, B74 (rest days). Merged rest/fatigue signals"},

    # ═══ BULLPEN BUCKET ═══
    {"signal_id": 21, "name": "Bullpen xFIP gap", "formula": "home_bp_xfip - away_bp_xfip",
     "mechanism": "Underlying bullpen skill may differ from recent results",
     "bucket": "bullpen", "tag": "READY_NOW",
     "data_sources": "feature_table (home_bp_xfip, away_bp_xfip), sim_inputs (bullpen_xfip)",
     "variants": "A12. A11 (ERA gap) merged — xFIP preferred over ERA"},

    {"signal_id": 22, "name": "Bullpen recent workload", "formula": "bullpen_ip_last3days",
     "mechanism": "Overused bullpens underperform season averages",
     "bucket": "bullpen", "tag": "READY_NOW",
     "data_sources": "pitcher_game_logs (IP by reliever, game_date). Derivable from existing data",
     "variants": "A13, A14, B3, B28. Merged bullpen fatigue signals"},

    {"signal_id": 23, "name": "Closer unavailability", "formula": "closer_pitches_last2days > threshold",
     "mechanism": "Missing primary closer matters more than aggregate bullpen stats suggest",
     "bucket": "bullpen", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires closer identification + recent pitch counts per reliever",
     "variants": "A15, B25. Merged closer signals"},

    {"signal_id": 24, "name": "Bullpen fatigue × quality interaction", "formula": "bp_ip_last2d × bp_era",
     "mechanism": "Bad and tired is exponentially worse than either alone",
     "bucket": "bullpen", "tag": "READY_NOW",
     "data_sources": "pitcher_game_logs + feature_table (bp_xfip)",
     "variants": "A18"},

    {"signal_id": 25, "name": "High-leverage bullpen concentration risk", "formula": "top2_reliever_pct / bp_depth",
     "mechanism": "Teams relying on two elite arms are fragile when those arms are unavailable",
     "bucket": "bullpen", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires reliever-level leverage data",
     "variants": "B12, B99. Merged concentration signals"},

    {"signal_id": 26, "name": "Bullpen handedness mismatch", "formula": "lineup_hand_mix vs bp_hand_mix",
     "mechanism": "Some bullpens are structurally weak against one lineup handedness type",
     "bucket": "bullpen", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires lineup composition + reliever handedness breakdown",
     "variants": "A17, B32, B56. Merged handedness signals"},

    # ═══ OFFENSE BUCKET ═══
    {"signal_id": 27, "name": "Team wRC+ gap", "formula": "home_wrc_plus - away_wrc_plus",
     "mechanism": "Offensive quality differential as priced by the model",
     "bucket": "offense", "tag": "READY_NOW",
     "data_sources": "feature_table (home_wrc_plus, away_wrc_plus)",
     "variants": "Implicit in A19, A20, A21, A22. wRC+ captures OBP+SLG combined"},

    {"signal_id": 28, "name": "Team hard-hit% gap", "formula": "home_hard_hit - away_hard_hit",
     "mechanism": "Contact quality leads scoring better than runs/game",
     "bucket": "offense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires team-level Statcast batted ball data",
     "variants": "A21, A22 (barrel%). Merged contact quality signals"},

    {"signal_id": 29, "name": "Lineup depth score", "formula": "top5_wrc - bottom4_wrc",
     "mechanism": "Top-heavy vs balanced lineups score differently than average offense suggests",
     "bucket": "offense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires per-game lineup construction with individual hitter stats",
     "variants": "A23, A24, B97. Merged lineup depth signals"},

    {"signal_id": 30, "name": "Team contact rate vs pitcher K rate", "formula": "team_contact_pct - pitcher_k_pct",
     "mechanism": "Contact-heavy teams can neutralize strikeout pitchers",
     "bucket": "offense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires team contact% from Statcast; pitcher K% available",
     "variants": "A25"},

    {"signal_id": 31, "name": "Power density (barrel × flyball)", "formula": "barrel_pct * flyball_pct",
     "mechanism": "Teams that both barrel and elevate create disproportionate run upside",
     "bucket": "offense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires team barrel% and flyball% from Statcast",
     "variants": "A28, A52 (run explosion). Merged power signals"},

    {"signal_id": 32, "name": "RISP clutch residual", "formula": "team_woba_risp - team_overall_woba",
     "mechanism": "Teams that outperform with RISP may have conditional advantages",
     "bucket": "offense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires team RISP splits",
     "variants": "B70"},

    {"signal_id": 33, "name": "Leadoff OBP amplifier", "formula": "team_leadoff_obp × park_scoring_rate",
     "mechanism": "High-OBP leadoff hitters create more late-inning scoring opportunities",
     "bucket": "offense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires per-game lineup position stats",
     "variants": "B23"},

    # ═══ DEFENSE BUCKET ═══
    {"signal_id": 34, "name": "Defensive runs saved gap", "formula": "home_drs - away_drs",
     "mechanism": "Defense suppresses scoring and preserves pitcher edges",
     "bucket": "defense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires DRS/OAA from FanGraphs or Statcast",
     "variants": "A29, A30, A31, A32, B8, B14, B95. Merged defense signals"},

    {"signal_id": 35, "name": "Infield defense × groundball pitcher", "formula": "infield_defense × pitcher_gb_pct",
     "mechanism": "Groundball pitchers need strong infield support",
     "bucket": "defense", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires infield defense metrics; gb_pct available",
     "variants": "A30, B14"},

    # ═══ CATCHER BUCKET ═══
    {"signal_id": 36, "name": "Catcher framing × pitcher command", "formula": "catcher_framing × pitcher_zone_rate",
     "mechanism": "Elite framers add meaningful value to pitchers who throw in the zone",
     "bucket": "catcher", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires catcher framing metrics from Statcast",
     "variants": "A33, B13, B51, B68. Merged catcher signals"},

    {"signal_id": 37, "name": "Backup catcher penalty", "formula": "is_backup_catcher × pitcher_framing_dependence",
     "mechanism": "Pitchers relying on framing show measurable drops with backup catchers",
     "bucket": "catcher", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires catcher ID per game + framing data",
     "variants": "B44, B68"},

    # ═══ BASERUNNING BUCKET ═══
    {"signal_id": 38, "name": "Team baserunning pressure", "formula": "sb_success_pct + xbt_pct",
     "mechanism": "Baserunning pressure creates non-hit run creation",
     "bucket": "baserunning", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires SB%, XBT% from Statcast/FanGraphs",
     "variants": "A34, A35, A36, A37, B33, B57. Merged speed/baserunning signals"},

    {"signal_id": 39, "name": "Stolen base suppression index", "formula": "catcher_pop_time × pitcher_delivery_time",
     "mechanism": "Fast-delivery pitchers with elite catchers neutralize speed offenses",
     "bucket": "baserunning", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires catcher pop time + pitcher delivery time",
     "variants": "B33"},

    # ═══ PARK / WEATHER BUCKET ═══
    {"signal_id": 40, "name": "Flyball pitcher × HR park factor", "formula": "pitcher_fb_pct × park_hr_factor",
     "mechanism": "Park and batted-ball shape interact strongly for run scoring",
     "bucket": "park_weather", "tag": "READY_NOW",
     "data_sources": "feature_table (park_factor_hr), pitcher_game_logs (fly_outs for fb_pct proxy)",
     "variants": "A38, B36, B61. Merged park×batted-ball signals"},

    {"signal_id": 41, "name": "Wind × flyball rate", "formula": "wind_out × combined_fb_pct",
     "mechanism": "Wind matters more for elevated-contact games",
     "bucket": "park_weather", "tag": "READY_NOW",
     "data_sources": "feature_table (wind_factor_effective, wind_speed, wind_direction)",
     "variants": "A40, B15, B55. Already in V1 as flyball×wind interaction"},

    {"signal_id": 42, "name": "Temperature × exit velocity", "formula": "temp × team_avg_ev",
     "mechanism": "Warm weather amplifies hard contact into extra bases",
     "bucket": "park_weather", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Temperature available; team exit velocity needs Statcast",
     "variants": "A41, B89 (cold suppressor). Merged temp signals"},

    {"signal_id": 43, "name": "Park altitude × breaking ball pitcher", "formula": "altitude × pitcher_breaking_pct",
     "mechanism": "High altitude reduces breaking-ball movement significantly",
     "bucket": "park_weather", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Altitude derivable from park lat/lon; breaking ball% needs Statcast",
     "variants": "B34"},

    {"signal_id": 44, "name": "Team pull rate × park dimensions", "formula": "team_pull_rate × park_pull_hr_factor",
     "mechanism": "Pull-heavy teams benefit in parks rewarding pulled fly balls",
     "bucket": "park_weather", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires team pull rate from Statcast; park factors partially available",
     "variants": "A26, A27, B7. Merged park×spray signals"},

    # ═══ SCHEDULE / TRAVEL BUCKET ═══
    {"signal_id": 45, "name": "Travel fatigue composite", "formula": "travel_miles_48h × is_day_game × road_games_streak",
     "mechanism": "Compounded travel creates fatigue books rarely price explicitly",
     "bucket": "schedule_travel", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires travel distance computation from schedule + venue coordinates",
     "variants": "A42, A43, A44, A45, B10, B18, B37, B53. Merged travel/fatigue signals"},

    {"signal_id": 46, "name": "Day game after night game", "formula": "is_day_after_night",
     "mechanism": "Short recovery windows hurt offense and defense",
     "bucket": "schedule_travel", "tag": "READY_NOW",
     "data_sources": "feature_table (game_hour_utc, date). Derivable from schedule",
     "variants": "A43, B37"},

    {"signal_id": 47, "name": "Rest days differential", "formula": "home_rest - away_rest",
     "mechanism": "Unequal rest creates performance asymmetries",
     "bucket": "schedule_travel", "tag": "READY_NOW",
     "data_sources": "feature_table (home_rest_days, away_rest_days)",
     "variants": "Implicit in many schedule signals"},

    # ═══ MATCHUP BUCKET ═══
    {"signal_id": 48, "name": "Umpire strike zone × pitcher command", "formula": "ump_called_strike_rate × pitcher_zone_rate",
     "mechanism": "Expansive umpires benefit command pitchers disproportionately",
     "bucket": "matchup", "tag": "READY_NOW",
     "data_sources": "feature_table (umpire_k_rate, umpire_over_rate). Umpire data in pipeline",
     "variants": "B6, B19, B62. Merged umpire signals"},

    {"signal_id": 49, "name": "Chase rate mismatch", "formula": "pitcher_o_swing_induced - opponent_o_swing_rate",
     "mechanism": "Pitchers generating chase above what opponents typically chase get extra whiffs",
     "bucket": "matchup", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires O-Swing% from Statcast",
     "variants": "B20"},

    {"signal_id": 50, "name": "Consecutive series scouting fatigue", "formula": "games_vs_opponent_last10d",
     "mechanism": "Repeated recent exposure gives hitters recognition advantages",
     "bucket": "matchup", "tag": "READY_NOW",
     "data_sources": "Derivable from schedule/feature_table game dates and opponents",
     "variants": "B46"},

    {"signal_id": 51, "name": "Interleague familiarity deficit", "formula": "is_interleague × days_since_last_faced",
     "mechanism": "Unfamiliar opponents in interleague create pricing uncertainty",
     "bucket": "matchup", "tag": "READY_NOW",
     "data_sources": "Derivable from schedule (home/away league, opponent history)",
     "variants": "B43"},

    {"signal_id": 52, "name": "Soft-toss vs power lineup", "formula": "pitcher_avg_velo - opponent_avg_ev",
     "mechanism": "Soft-tossers are vulnerable to power lineups that generate hard contact without velocity",
     "bucket": "matchup", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Velocity available in per_start_csv; team exit velocity needs Statcast",
     "variants": "B26, B75"},

    {"signal_id": 53, "name": "Combined pitcher score", "formula": "(csw_gap×100) + (whiff_gap×100) + (xfip_gap×2)",
     "mechanism": "Multi-factor pitcher quality composite captures mismatch better than any single stat",
     "bucket": "matchup", "tag": "READY_NOW",
     "data_sources": "All components in sim_inputs/feature_table",
     "variants": "Signal D from F5 RL research — already validated"},

    # ═══ EXPERIMENTAL BUCKET ═══
    {"signal_id": 54, "name": "Pitching debut overreaction", "formula": "is_mlb_debut × scouting_database_completeness",
     "mechanism": "Debutants have no MLB scouting history; books may misprice the unknown",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Debut flag derivable; scouting completeness is conceptual",
     "variants": "B54"},

    {"signal_id": 55, "name": "Late-season tanking signal", "formula": "playoff_prob × remaining_games × young_pitcher_starts",
     "mechanism": "Eliminated teams deploy talent differently than season averages imply",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires playoff probability data + roster usage patterns",
     "variants": "B93"},

    {"signal_id": 56, "name": "Position player pitching signal", "formula": "P(position_player_pitching) × expected_run_diff",
     "mechanism": "Blowouts ending with position-player pitchers inflate late scoring",
     "bucket": "experimental", "tag": "TOO_VAGUE",
     "data_sources": "Requires real-time blowout detection — not predictive",
     "variants": "B76"},

    {"signal_id": 57, "name": "Blowout revenge game", "formula": "margin_loss_yesterday × is_same_opponent",
     "mechanism": "Teams that lost badly come out more aggressive next game",
     "bucket": "experimental", "tag": "READY_NOW",
     "data_sources": "Derivable from feature_table (scores, dates, opponents)",
     "variants": "B63. Behavioral signal — may be noise"},

    {"signal_id": 58, "name": "Series clincher pressure", "formula": "is_series_deciding × team_clinch_win_pct",
     "mechanism": "Teams underperform in clinching/elimination dynamics",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires series context tracking",
     "variants": "B91"},

    {"signal_id": 59, "name": "Lineup protection removal", "formula": "key_hitter_injured × on_base_pct_3_4_5",
     "mechanism": "When the hitter behind a star is out, run production falls",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires injury data + lineup position tracking",
     "variants": "B82"},

    {"signal_id": 60, "name": "Release point variance", "formula": "pitcher_release_point_variance",
     "mechanism": "Release-point inconsistency signals mechanical problems before ERA changes",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires pitch-level release point data from Statcast",
     "variants": "B81, B98 (tunneling)"},

    {"signal_id": 61, "name": "Scoring cluster variance", "formula": "team_inning_runs_variance / team_avg_runs",
     "mechanism": "High-variance offenses create different O/U dynamics than smooth offenses",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires inning-level scoring data",
     "variants": "B80"},

    {"signal_id": 62, "name": "Opener mis-sequencing", "formula": "is_opener × top3_woba × home_flag",
     "mechanism": "Openers expose top of order twice in first 3 innings",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires opener identification + lineup composition",
     "variants": "B9"},

    {"signal_id": 63, "name": "New pitch introduction effect", "formula": "new_pitch_pct_last3 × opponent_familiarity",
     "mechanism": "Pitchers adding a new pitch gain short-term deception",
     "bucket": "experimental", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires pitch-type tracking over time from Statcast",
     "variants": "B60"},

    {"signal_id": 64, "name": "Walk-heavy inning compressor", "formula": "bb_rate × ump_ball_tendency × park_hr_factor",
     "mechanism": "High-walk pitchers + permissive umpires + HR parks = compounding risk",
     "bucket": "matchup", "tag": "READY_NOW",
     "data_sources": "feature_table (sp_bb_pct, umpire_over_rate, park_factor_hr)",
     "variants": "B41"},

    {"signal_id": 65, "name": "Pitcher age × workload cliff", "formula": "age × (recent_ip - career_avg_ip)",
     "mechanism": "Older pitchers on high workload show steeper performance cliffs",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Age requires roster data; workload from pitcher_game_logs",
     "variants": "B16, B71, B77, B90. Merged age-fatigue signals"},

    {"signal_id": 66, "name": "Knuckleball-weather amplifier", "formula": "is_knuckleball × wind × temp",
     "mechanism": "Knuckleball movement is highly weather-dependent",
     "bucket": "experimental", "tag": "TOO_VAGUE",
     "data_sources": "Only ~2 knuckleball pitchers in MLB; too thin to model",
     "variants": "B72"},

    {"signal_id": 67, "name": "Shift removal BABIP inflation", "formula": "gb_babip_post_rule - gb_babip_career",
     "mechanism": "Shift-dependent groundball pitchers may still be mispriced after rule change",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires BABIP splits pre/post shift rule from Statcast",
     "variants": "B40, B79"},

    {"signal_id": 68, "name": "Hitter count preference exploit", "formula": "pitcher_strike_first × opponent_first_pitch_swing",
     "mechanism": "First-pitch aggression vs strike-first pitchers changes count quality",
     "bucket": "matchup", "tag": "READY_NOW",
     "data_sources": "per_start_csv (f_strike_pct, f_strike_r5). Opponent swing needs derivation",
     "variants": "B92. F-strike% available; opponent first-pitch swing needs team-level data"},

    {"signal_id": 69, "name": "Rain delay disruption", "formula": "P(rain_delay) × pitcher_warmup_sensitivity",
     "mechanism": "Some pitchers perform far worse after interruption",
     "bucket": "experimental", "tag": "TOO_VAGUE",
     "data_sources": "Requires rain delay prediction + pitcher-specific delay response",
     "variants": "B69"},

    {"signal_id": 70, "name": "RISP stranding skill", "formula": "strand_rate - FIP_implied_strand",
     "mechanism": "Pitchers consistently stranding above FIP may have sequencing skill",
     "bucket": "starter", "tag": "NEEDS_NEW_DATA",
     "data_sources": "Requires strand rate + FIP from FanGraphs",
     "variants": "B35"},
]

# ── Build DataFrame ──────────────────────────────────────────────────────────

df = pd.DataFrame(signals)

# ── Summary ──────────────────────────────────────────────────────────────────

print("=" * 60)
print("SIGNAL INVENTORY — SUMMARY")
print("=" * 60)

print(f"\nTotal signals after dedup: {len(df)}")

print(f"\nBy bucket:")
for b, n in df["bucket"].value_counts().sort_index().items():
    print(f"  {b:20s}: {n}")

print(f"\nBy tag:")
for t, n in df["tag"].value_counts().items():
    print(f"  {t:20s}: {n}")

# ── Save ─────────────────────────────────────────────────────────────────────

df.to_parquet(OUT / "signal_inventory.parquet", index=False)

# ── Write markdown report ────────────────────────────────────────────────────

md = []
md.append("# MLB Signal Inventory\n")
md.append(f"Total signals: {len(df)} (deduplicated from 152 raw inputs)\n")

md.append("\n## Section 1: Summary\n")
md.append(f"| Bucket | Count |\n|--------|-------|\n")
for b, n in df["bucket"].value_counts().sort_index().items():
    md.append(f"| {b} | {n} |\n")

md.append(f"\n| Tag | Count |\n|-----|-------|\n")
for t, n in df["tag"].value_counts().items():
    md.append(f"| {t} | {n} |\n")

md.append("\n## Section 2: Full Inventory\n")
md.append("| ID | Name | Bucket | Tag | Mechanism |\n")
md.append("|-----|------|--------|-----|------------|\n")
for _, r in df.iterrows():
    md.append(f"| {r['signal_id']} | {r['name']} | {r['bucket']} | {r['tag']} | {r['mechanism'][:80]} |\n")

md.append("\n## Section 3: READY_NOW Signals\n")
ready = df[df["tag"] == "READY_NOW"].sort_values("bucket")
md.append("| ID | Name | Bucket | Data Source |\n")
md.append("|-----|------|--------|-------------|\n")
for _, r in ready.iterrows():
    md.append(f"| {r['signal_id']} | {r['name']} | {r['bucket']} | {r['data_sources'][:60]} |\n")

md.append("\n## Section 4: NEEDS_NEW_DATA Signals\n")
needs = df[df["tag"] == "NEEDS_NEW_DATA"].sort_values("bucket")
md.append("| ID | Name | Bucket | Data Needed |\n")
md.append("|-----|------|--------|-------------|\n")
for _, r in needs.iterrows():
    md.append(f"| {r['signal_id']} | {r['name']} | {r['bucket']} | {r['data_sources'][:60]} |\n")

with open(OUT / "signal_inventory.md", "w") as f:
    f.writelines(md)

print(f"\nFiles saved:")
print(f"  {OUT / 'signal_inventory.md'}")
print(f"  {OUT / 'signal_inventory.parquet'}")

# Print READY_NOW list
print(f"\n{'='*60}")
print("READY_NOW SIGNALS ({} total)".format(len(ready)))
print("="*60)
for _, r in ready.iterrows():
    print(f"  [{r['signal_id']:2d}] {r['name']:40s} ({r['bucket']})")
