# MLB Autonomous Discovery Engine V2 — Report

**Date:** 2026-04-23
**Search depth:** 2-way interactions
**Features:** 501 binary columns (39 archetype + 462 binarized V6)
**Candidates tested:** 125,250
**Runtime:** 8.4s (0.1 min)

## Gate-by-Gate Attrition

| Gate | Description | Passed | Killed |
|---|---|---|---|
| 6 | Sample floor (N>=30) | 120,881 | 4,369 |
| 1 | Effect size (|z|>=2.0) | 5,180 | 115,701 |
| 2 | Anti-monotonicity | 4,240 | 940 |
| 3 | Line bucket consistency | 3,814 | 426 |
| 4 | Month consistency | 3,762 | 52 |
| 5 | Mean control | 3,537 | 225 |
| 7 | Direction plausibility | 3,537 | 0 |
| **Final** | **Discovery survivors** | **3537** | |

## Validation Pass
- Discovery survivors: 3537
- Validation dead (direction reversal): 1762
- Validation weak (attenuation >= 60%): 1201
- Validation low sample: 2
- **Validation survivors:** 1773

## OOS Pass
- Validation survivors: 1773
- **Three-stage survivors (Tier A):** 639
- Tier B (monitoring): 1134
- Tier C (discovery only): 1764

## Three-Stage Survivors

### batting_total_bip_last_10_HIGH × opp_pl_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+4.05, N=127
- Validation: z=+1.59, N=153, attenuation=61%
- OOS: z=+3.38, N=174, attenuation=17%
- ROI: synthetic=+14.4%, real=+14.2%

### batting_total_bip_last_10_HIGH × lineup_quality_xwoba_HIGH
- Direction: OVER
- Discovery: z=+3.96, N=132
- Validation: z=+1.19, N=316, attenuation=70%
- OOS: z=+2.69, N=313, attenuation=32%
- ROI: synthetic=+4.8%, real=+5.0%

### home_bp_CLOSER_DEPENDENT × batting_total_bip_last_10_HIGH
- Direction: OVER
- Discovery: z=+3.92, N=71
- Validation: z=+1.49, N=86, attenuation=62%
- OOS: z=+1.22, N=102, attenuation=69%
- ROI: synthetic=+9.5%, real=+9.1%

### batting_total_bip_last_10_HIGH × opp_pl_ff_pct_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.86, N=125
- Validation: z=+1.75, N=145, attenuation=55%
- OOS: z=+3.63, N=153, attenuation=6%
- ROI: synthetic=+15.1%, real=+14.9%

### damage_hr_rate_last_20_HIGH × opp_pl_pfx_z_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.78, N=124
- Validation: z=+0.87, N=111, attenuation=77%
- OOS: z=+1.65, N=148, attenuation=56%
- ROI: synthetic=+8.3%, real=+8.4%

### contact_xslg_last_7_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+3.77, N=129
- Validation: z=+0.17, N=142, attenuation=96%
- OOS: z=+1.61, N=153, attenuation=57%
- ROI: synthetic=+3.8%, real=+4.2%

### damage_iso_last_15_HIGH × opp_pl_pfx_z_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.72, N=119
- Validation: z=+1.04, N=114, attenuation=72%
- OOS: z=+1.91, N=130, attenuation=49%
- ROI: synthetic=+6.4%, real=+6.2%

### batting_total_bip_last_5_HIGH × lineup_quality_xwoba_HIGH
- Direction: OVER
- Discovery: z=+3.59, N=147
- Validation: z=+0.63, N=365, attenuation=83%
- OOS: z=+2.60, N=322, attenuation=28%
- ROI: synthetic=+4.8%, real=+5.2%

### batting_total_bip_last_10_HIGH × opp_pl_pfx_z_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.58, N=120
- Validation: z=+0.97, N=164, attenuation=73%
- OOS: z=+2.34, N=167, attenuation=35%
- ROI: synthetic=+6.4%, real=+6.2%

### batting_total_bip_last_10_HIGH × exit_prob_by_6_last_10_HIGH
- Direction: OVER
- Discovery: z=+3.56, N=114
- Validation: z=+0.74, N=114, attenuation=79%
- OOS: z=+1.80, N=186, attenuation=50%
- ROI: synthetic=+2.6%, real=+2.6%

### batting_total_bip_last_10_HIGH × opp_pl_pfx_z_mean_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.51, N=117
- Validation: z=+1.46, N=157, attenuation=58%
- OOS: z=+2.97, N=155, attenuation=15%
- ROI: synthetic=+9.7%, real=+9.5%

### damage_iso_last_15_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+3.49, N=159
- Validation: z=+1.28, N=210, attenuation=63%
- OOS: z=+2.26, N=205, attenuation=35%
- ROI: synthetic=+5.2%, real=+5.4%

### opp_pl_edge_rate_last_5_LOW × leverage_gap_k_last_10_HIGH
- Direction: UNDER
- Discovery: z=-3.47, N=54
- Validation: z=-0.16, N=92, attenuation=95%
- OOS: z=-1.53, N=48, attenuation=56%
- ROI: synthetic=+14.1%, real=+15.1%

### batting_barrel_rate_last_5_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-3.46, N=170
- Validation: z=-0.25, N=279, attenuation=93%
- OOS: z=-1.43, N=187, attenuation=59%
- ROI: synthetic=+5.4%, real=+5.1%

### contact_ev_last_20_HIGH × opp_pl_velo_ff_mean_season_baseline_LOW
- Direction: OVER
- Discovery: z=+3.46, N=111
- Validation: z=+0.99, N=149, attenuation=71%
- OOS: z=+1.46, N=191, attenuation=58%
- ROI: synthetic=+4.0%, real=+3.9%

### damage_iso_last_20_HIGH × opp_pl_pfx_z_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.43, N=126
- Validation: z=+1.25, N=122, attenuation=63%
- OOS: z=+1.85, N=140, attenuation=46%
- ROI: synthetic=+9.2%, real=+9.4%

### contact_xslg_last_10_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+3.33, N=128
- Validation: z=+1.53, N=139, attenuation=54%
- OOS: z=+1.02, N=154, attenuation=69%
- ROI: synthetic=+5.6%, real=+6.0%

### damage_iso_last_10_HIGH × opp_sp_command_bb_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+3.32, N=120
- Validation: z=+1.04, N=138, attenuation=69%
- OOS: z=+2.61, N=162, attenuation=21%
- ROI: synthetic=+9.4%, real=+9.5%

### damage_hr_rate_last_10_HIGH × opp_pl_ff_pct_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.31, N=125
- Validation: z=+1.16, N=107, attenuation=65%
- OOS: z=+2.13, N=133, attenuation=35%
- ROI: synthetic=+9.0%, real=+9.0%

### damage_hr_rate_last_10_HIGH × opp_pl_pfx_z_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.31, N=126
- Validation: z=+0.64, N=118, attenuation=81%
- OOS: z=+1.37, N=150, attenuation=58%
- ROI: synthetic=+6.8%, real=+6.7%

### opp_sp_contact_la_allowed_last_10_HIGH × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.28, N=101
- Validation: z=+0.60, N=203, attenuation=82%
- OOS: z=+2.10, N=220, attenuation=36%
- ROI: synthetic=-0.4%, real=-0.3%

### opp_pl_ff_pct_last_5_HIGH × opp_pl_pfx_z_std_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.26, N=145
- Validation: z=+0.29, N=202, attenuation=91%
- OOS: z=+1.05, N=204, attenuation=68%
- ROI: synthetic=+3.3%, real=+3.4%

### contact_ev_last_15_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+3.26, N=124
- Validation: z=+0.03, N=153, attenuation=99%
- OOS: z=+1.13, N=254, attenuation=65%
- ROI: synthetic=-0.4%, real=-0.4%

### contact_xwoba_last_7_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+3.26, N=130
- Validation: z=+0.54, N=163, attenuation=83%
- OOS: z=+1.40, N=168, attenuation=57%
- ROI: synthetic=+2.7%, real=+3.0%

### home_sp_BACK_LOADED × contact_la_last_20_HIGH
- Direction: OVER
- Discovery: z=+3.24, N=182
- Validation: z=+0.73, N=265, attenuation=77%
- OOS: z=+2.15, N=304, attenuation=34%
- ROI: synthetic=+3.7%, real=+3.8%

### batting_total_bip_last_3_HIGH × lineup_quality_xwoba_HIGH
- Direction: OVER
- Discovery: z=+3.23, N=143
- Validation: z=+1.01, N=391, attenuation=69%
- OOS: z=+2.50, N=340, attenuation=23%
- ROI: synthetic=+2.9%, real=+3.4%

### damage_iso_last_10_HIGH × opp_pl_pfx_z_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.21, N=128
- Validation: z=+0.26, N=115, attenuation=92%
- OOS: z=+1.98, N=136, attenuation=39%
- ROI: synthetic=+8.0%, real=+8.1%

### contact_barrel_rate_last_20_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+3.20, N=121
- Validation: z=+2.19, N=142, attenuation=31%
- OOS: z=+1.15, N=283, attenuation=64%
- ROI: synthetic=+3.6%, real=+3.4%

### damage_hr_rate_last_10_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+3.18, N=182
- Validation: z=+1.34, N=242, attenuation=58%
- OOS: z=+1.28, N=261, attenuation=60%
- ROI: synthetic=+2.7%, real=+2.8%

### contact_xslg_last_10_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-3.16, N=136
- Validation: z=-0.32, N=340, attenuation=90%
- OOS: z=-1.00, N=432, attenuation=68%
- ROI: synthetic=+5.4%, real=+5.2%

### plate_k_rate_last_7_LOW × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-3.15, N=61
- Validation: z=-0.93, N=123, attenuation=70%
- OOS: z=-2.43, N=136, attenuation=23%
- ROI: synthetic=+13.4%, real=+13.4%

### damage_hr_rate_last_20_HIGH × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+3.14, N=125
- Validation: z=+1.25, N=118, attenuation=60%
- OOS: z=+3.01, N=177, attenuation=4%
- ROI: synthetic=+8.3%, real=+8.4%

### contact_barrel_rate_last_10_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+3.13, N=128
- Validation: z=+1.56, N=162, attenuation=50%
- OOS: z=+1.00, N=249, attenuation=68%
- ROI: synthetic=+3.2%, real=+3.2%

### damage_hr_rate_last_7_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.12, N=145
- Validation: z=+0.62, N=160, attenuation=80%
- OOS: z=+1.60, N=210, attenuation=49%
- ROI: synthetic=-2.2%, real=-2.3%

### home_lu_HIGH_TURNOVER × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.12, N=68
- Validation: z=+0.05, N=95, attenuation=98%
- OOS: z=+0.96, N=73, attenuation=69%
- ROI: synthetic=+4.2%, real=+4.2%

### contact_ev_last_10_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+3.11, N=129
- Validation: z=+1.07, N=158, attenuation=66%
- OOS: z=+1.88, N=218, attenuation=40%
- ROI: synthetic=+5.6%, real=+5.4%

### damage_iso_last_20_HIGH × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+3.11, N=129
- Validation: z=+1.07, N=129, attenuation=66%
- OOS: z=+2.08, N=161, attenuation=33%
- ROI: synthetic=+5.1%, real=+5.4%

### home_lu_HIGH_TURNOVER × opp_pl_primary_mix_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.10, N=70
- Validation: z=+1.87, N=79, attenuation=40%
- OOS: z=+2.65, N=55, attenuation=15%
- ROI: synthetic=+20.5%, real=+20.7%

### damage_hr_rate_last_20_HIGH × opp_pl_pfx_z_mean_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.10, N=119
- Validation: z=+1.06, N=104, attenuation=66%
- OOS: z=+1.39, N=143, attenuation=55%
- ROI: synthetic=+5.0%, real=+5.1%

### damage_hr_rate_last_10_HIGH × opp_pl_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.09, N=123
- Validation: z=+0.59, N=115, attenuation=81%
- OOS: z=+1.94, N=147, attenuation=37%
- ROI: synthetic=+9.0%, real=+8.9%

### opp_sp_damage_hits_per_bf_last_5_HIGH × opp_pl_sl_pct_last_5_LOW
- Direction: UNDER
- Discovery: z=-3.08, N=136
- Validation: z=-0.99, N=169, attenuation=68%
- OOS: z=-0.94, N=157, attenuation=69%
- ROI: synthetic=+8.6%, real=+8.7%

### damage_iso_last_10_HIGH × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+3.07, N=109
- Validation: z=+2.02, N=149, attenuation=34%
- OOS: z=+1.27, N=184, attenuation=59%
- ROI: synthetic=+8.1%, real=+8.5%

### batting_total_bip_last_10_LOW × low_lev_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-3.07, N=114
- Validation: z=-2.47, N=360, attenuation=20%
- OOS: z=-1.61, N=281, attenuation=47%
- ROI: synthetic=+8.6%, real=+8.5%

### contact_xslg_last_10_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-3.07, N=129
- Validation: z=-0.32, N=340, attenuation=90%
- OOS: z=-1.10, N=431, attenuation=64%
- ROI: synthetic=+4.7%, real=+4.5%

### contact_xslg_last_10_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-3.07, N=129
- Validation: z=-0.32, N=340, attenuation=90%
- OOS: z=-1.10, N=431, attenuation=64%
- ROI: synthetic=+4.7%, real=+4.5%

### plate_bb_rate_last_20_LOW × exit_prob_by_6_last_10_LOW
- Direction: UNDER
- Discovery: z=-3.06, N=142
- Validation: z=-0.01, N=286, attenuation=100%
- OOS: z=-1.42, N=168, attenuation=54%
- ROI: synthetic=+5.2%, real=+5.1%

### batting_total_bip_last_10_LOW × high_lev_k_rate_baseline_LOW
- Direction: UNDER
- Discovery: z=-3.06, N=118
- Validation: z=-1.10, N=372, attenuation=64%
- OOS: z=-1.55, N=441, attenuation=49%
- ROI: synthetic=+6.2%, real=+6.1%

### plate_k_rate_last_7_LOW × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-3.05, N=63
- Validation: z=-0.59, N=153, attenuation=81%
- OOS: z=-3.29, N=166, attenuation=-8%
- ROI: synthetic=+14.9%, real=+14.6%

### damage_hr_rate_last_7_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+3.02, N=125
- Validation: z=+2.11, N=142, attenuation=30%
- OOS: z=+1.52, N=193, attenuation=50%
- ROI: synthetic=+2.2%, real=+2.1%

### opp_sp_command_bb_rate_last_10_LOW × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+3.02, N=128
- Validation: z=+0.01, N=216, attenuation=100%
- OOS: z=+3.29, N=188, attenuation=-9%
- ROI: synthetic=+5.4%, real=+5.1%

### contact_la_last_15_HIGH × opp_sp_contact_hh_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+3.01, N=123
- Validation: z=+0.03, N=200, attenuation=99%
- OOS: z=+1.32, N=290, attenuation=56%
- ROI: synthetic=-0.3%, real=+0.0%

### contact_barrel_rate_last_7_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+3.00, N=131
- Validation: z=+1.78, N=150, attenuation=41%
- OOS: z=+1.11, N=237, attenuation=63%
- ROI: synthetic=+2.7%, real=+2.8%

### damage_hr_rate_last_20_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.97, N=137
- Validation: z=+0.21, N=134, attenuation=93%
- OOS: z=+2.39, N=202, attenuation=20%
- ROI: synthetic=+2.9%, real=+2.8%

### contact_hh_rate_last_7_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.97, N=113
- Validation: z=+2.37, N=156, attenuation=20%
- OOS: z=+1.55, N=288, attenuation=48%
- ROI: synthetic=+5.7%, real=+5.8%

### opp_sp_workload_ppbf_last_10_LOW × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.97, N=123
- Validation: z=-0.16, N=207, attenuation=95%
- OOS: z=-2.19, N=190, attenuation=26%
- ROI: synthetic=+9.0%, real=+9.0%

### batting_total_bip_last_3_LOW × deterioration_score_norm_HIGH
- Direction: UNDER
- Discovery: z=-2.96, N=109
- Validation: z=-2.04, N=190, attenuation=31%
- OOS: z=-1.24, N=179, attenuation=58%
- ROI: synthetic=+8.6%, real=+8.4%

### contact_ev_last_7_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.95, N=123
- Validation: z=+0.47, N=150, attenuation=84%
- OOS: z=+1.50, N=207, attenuation=49%
- ROI: synthetic=+1.7%, real=+1.4%

### contact_la_last_15_HIGH × opp_sp_contact_hh_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.95, N=141
- Validation: z=+0.24, N=230, attenuation=92%
- OOS: z=+1.05, N=299, attenuation=64%
- ROI: synthetic=-1.0%, real=-0.7%

### opp_pl_ff_pct_last_5_HIGH × opp_pl_two_strike_secondary_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.95, N=74
- Validation: z=+0.19, N=119, attenuation=94%
- OOS: z=+1.31, N=152, attenuation=55%
- ROI: synthetic=+5.0%, real=+4.7%

### damage_iso_last_10_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.94, N=129
- Validation: z=+1.01, N=145, attenuation=66%
- OOS: z=+2.36, N=167, attenuation=20%
- ROI: synthetic=+4.5%, real=+4.4%

### opp_sp_contact_ev_allowed_last_10_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.94, N=133
- Validation: z=+0.82, N=196, attenuation=72%
- OOS: z=+1.63, N=293, attenuation=44%
- ROI: synthetic=+0.8%, real=+0.6%

### contact_la_last_20_HIGH × lineup_quality_xwoba_HIGH
- Direction: OVER
- Discovery: z=+2.93, N=187
- Validation: z=+0.89, N=498, attenuation=70%
- OOS: z=+2.30, N=413, attenuation=22%
- ROI: synthetic=+1.2%, real=+1.4%

### middle_order_avg_exit_velo_LOW × lineup_quality_hh_HIGH
- Direction: OVER
- Discovery: z=+2.92, N=109
- Validation: z=+0.13, N=179, attenuation=96%
- OOS: z=+1.95, N=196, attenuation=33%
- ROI: synthetic=+6.1%, real=+6.3%

### opp_pl_edge_rate_last_3_LOW × leverage_gap_k_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.92, N=55
- Validation: z=-1.52, N=102, attenuation=48%
- OOS: z=-0.99, N=64, attenuation=66%
- ROI: synthetic=+14.5%, real=+15.2%

### batting_barrel_rate_last_5_LOW × low_lev_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.92, N=130
- Validation: z=-0.19, N=351, attenuation=93%
- OOS: z=-0.93, N=239, attenuation=68%
- ROI: synthetic=-2.1%, real=-2.1%

### batting_total_bip_last_10_LOW × exit_prob_by_5_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.92, N=178
- Validation: z=-0.95, N=344, attenuation=67%
- OOS: z=-2.70, N=320, attenuation=7%
- ROI: synthetic=+9.9%, real=+10.0%

### home_lu_STABLE_DEEP × opp_sp_workload_pitches_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.90, N=95
- Validation: z=-1.39, N=115, attenuation=52%
- OOS: z=-0.98, N=82, attenuation=66%
- ROI: synthetic=+11.9%, real=+11.6%

### damage_iso_last_20_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.90, N=151
- Validation: z=+0.04, N=219, attenuation=98%
- OOS: z=+2.81, N=212, attenuation=3%
- ROI: synthetic=+2.5%, real=+2.6%

### batting_total_bip_last_5_HIGH × lineup_coverage_overall_LOW
- Direction: OVER
- Discovery: z=+2.89, N=220
- Validation: z=+1.71, N=322, attenuation=41%
- OOS: z=+3.05, N=404, attenuation=-6%
- ROI: synthetic=+4.5%, real=+4.7%

### opp_pl_pfx_z_mean_last_3_HIGH × med_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.89, N=120
- Validation: z=+0.38, N=153, attenuation=87%
- OOS: z=+0.87, N=171, attenuation=70%
- ROI: synthetic=-0.1%, real=-0.4%

### damage_hr_rate_last_20_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.89, N=140
- Validation: z=+0.66, N=138, attenuation=77%
- OOS: z=+2.54, N=196, attenuation=12%
- ROI: synthetic=+2.9%, real=+3.0%

### home_lu_HIGH_TURNOVER × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.89, N=69
- Validation: z=+1.27, N=92, attenuation=56%
- OOS: z=+1.60, N=71, attenuation=45%
- ROI: synthetic=+12.0%, real=+11.6%

### opp_pl_two_strike_ff_pct_last_3_LOW × low_lev_bb_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.88, N=100
- Validation: z=-0.24, N=185, attenuation=92%
- OOS: z=-1.29, N=164, attenuation=55%
- ROI: synthetic=+4.7%, real=+5.0%

### contact_hh_rate_last_20_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.88, N=127
- Validation: z=+1.72, N=135, attenuation=40%
- OOS: z=+1.06, N=335, attenuation=63%
- ROI: synthetic=+0.3%, real=+0.4%

### plate_bb_rate_last_15_HIGH × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.87, N=138
- Validation: z=+1.21, N=149, attenuation=58%
- OOS: z=+1.81, N=170, attenuation=37%
- ROI: synthetic=+8.1%, real=+8.5%

### opp_sp_command_bb_rate_last_5_LOW × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.86, N=132
- Validation: z=+1.52, N=224, attenuation=47%
- OOS: z=+2.60, N=208, attenuation=9%
- ROI: synthetic=+6.9%, real=+6.8%

### contact_xslg_last_10_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.86, N=121
- Validation: z=+0.84, N=141, attenuation=71%
- OOS: z=+1.53, N=145, attenuation=46%
- ROI: synthetic=+6.0%, real=+5.8%

### batting_total_bip_last_10_LOW × exit_prob_by_7_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.86, N=282
- Validation: z=-0.79, N=542, attenuation=72%
- OOS: z=-4.05, N=463, attenuation=-42%
- ROI: synthetic=+8.3%, real=+8.4%

### opp_sp_damage_hits_per_bf_last_5_HIGH × opp_pl_sl_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.85, N=135
- Validation: z=-0.62, N=170, attenuation=78%
- OOS: z=-1.04, N=161, attenuation=63%
- ROI: synthetic=+8.3%, real=+8.4%

### opp_pl_primary_mix_drift_last_3_HIGH × lineup_quality_xwoba_HIGH
- Direction: OVER
- Discovery: z=+2.85, N=116
- Validation: z=+0.79, N=335, attenuation=72%
- OOS: z=+1.26, N=305, attenuation=56%
- ROI: synthetic=-0.9%, real=-0.8%

### contact_ev_last_15_LOW × batting_total_bip_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.84, N=155
- Validation: z=-0.42, N=401, attenuation=85%
- OOS: z=-1.96, N=244, attenuation=31%
- ROI: synthetic=+4.9%, real=+4.8%

### batting_total_bip_last_5_LOW × exit_prob_by_5_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.84, N=197
- Validation: z=-1.58, N=340, attenuation=44%
- OOS: z=-1.91, N=322, attenuation=33%
- ROI: synthetic=+8.7%, real=+8.9%

### opp_sp_command_bb_rate_last_5_LOW × batting_barrel_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.83, N=127
- Validation: z=+1.13, N=157, attenuation=60%
- OOS: z=+1.43, N=255, attenuation=49%
- ROI: synthetic=-0.1%, real=-0.2%

### contact_barrel_rate_last_15_HIGH × opp_sp_contact_barrel_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.82, N=139
- Validation: z=+0.42, N=114, attenuation=85%
- OOS: z=+1.78, N=248, attenuation=37%
- ROI: synthetic=-1.0%, real=-0.9%

### opp_sp_contact_ev_allowed_last_5_HIGH × opp_pl_spin_sl_mean_last_3_LOW
- Direction: OVER
- Discovery: z=+2.82, N=59
- Validation: z=+0.33, N=81, attenuation=88%
- OOS: z=+2.63, N=145, attenuation=7%
- ROI: synthetic=+7.5%, real=+7.7%

### damage_iso_last_20_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.81, N=144
- Validation: z=+0.63, N=158, attenuation=78%
- OOS: z=+2.56, N=176, attenuation=9%
- ROI: synthetic=+3.3%, real=+3.4%

### damage_iso_last_15_HIGH × opp_pl_pfx_z_mean_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.81, N=115
- Validation: z=+1.72, N=103, attenuation=39%
- OOS: z=+1.80, N=120, attenuation=36%
- ROI: synthetic=+4.9%, real=+4.5%

### home_lu_HIGH_TURNOVER × contact_xslg_last_7_HIGH
- Direction: OVER
- Discovery: z=+2.81, N=84
- Validation: z=+0.32, N=71, attenuation=89%
- OOS: z=+1.57, N=56, attenuation=44%
- ROI: synthetic=+1.0%, real=+1.5%

### damage_iso_last_10_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.80, N=171
- Validation: z=+2.03, N=225, attenuation=28%
- OOS: z=+2.44, N=242, attenuation=13%
- ROI: synthetic=+6.1%, real=+6.2%

### contact_barrel_rate_last_20_LOW × opp_sp_command_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.80, N=123
- Validation: z=-0.23, N=279, attenuation=92%
- OOS: z=-1.02, N=228, attenuation=64%
- ROI: synthetic=+3.8%, real=+3.6%

### opp_sp_contact_barrel_allowed_last_3_LOW × batting_barrel_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.80, N=139
- Validation: z=-0.24, N=238, attenuation=91%
- OOS: z=-2.17, N=154, attenuation=23%
- ROI: synthetic=+7.5%, real=+7.4%

### damage_iso_last_15_HIGH × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.79, N=124
- Validation: z=+1.00, N=120, attenuation=64%
- OOS: z=+1.88, N=136, attenuation=32%
- ROI: synthetic=+4.5%, real=+4.6%

### home_lu_HIGH_TURNOVER × top_order_xwoba_contact_HIGH
- Direction: OVER
- Discovery: z=+2.78, N=66
- Validation: z=+0.46, N=140, attenuation=83%
- OOS: z=+1.55, N=131, attenuation=44%
- ROI: synthetic=+2.5%, real=+2.5%

### batting_total_bip_last_5_HIGH × opp_pl_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.78, N=132
- Validation: z=+0.66, N=167, attenuation=76%
- OOS: z=+3.10, N=176, attenuation=-11%
- ROI: synthetic=+9.7%, real=+9.6%

### home_sp_BACK_LOADED × opp_sp_contact_ev_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.78, N=155
- Validation: z=+0.41, N=207, attenuation=85%
- OOS: z=+1.52, N=308, attenuation=45%
- ROI: synthetic=-2.0%, real=-1.9%

### contact_xba_last_10_HIGH × opp_pl_pfx_z_std_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.77, N=125
- Validation: z=+0.34, N=93, attenuation=88%
- OOS: z=+1.33, N=138, attenuation=52%
- ROI: synthetic=+2.4%, real=+2.7%

### low_lev_k_rate_last_5_LOW × leverage_gap_k_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.77, N=106
- Validation: z=-0.53, N=210, attenuation=81%
- OOS: z=-0.97, N=193, attenuation=65%
- ROI: synthetic=+6.1%, real=+6.3%

### opp_pl_ff_pct_last_5_HIGH × high_lev_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.77, N=106
- Validation: z=+0.25, N=126, attenuation=91%
- OOS: z=+1.25, N=169, attenuation=55%
- ROI: synthetic=-0.6%, real=-0.2%

### opp_sp_batmiss_whiff_rate_last_10_LOW × top_order_xwoba_contact_HIGH
- Direction: OVER
- Discovery: z=+2.76, N=117
- Validation: z=+0.03, N=356, attenuation=99%
- OOS: z=+0.86, N=352, attenuation=69%
- ROI: synthetic=-3.0%, real=-2.9%

### contact_xslg_last_15_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.76, N=118
- Validation: z=+0.58, N=140, attenuation=79%
- OOS: z=+1.06, N=145, attenuation=62%
- ROI: synthetic=-0.4%, real=+0.1%

### plate_bb_rate_last_20_LOW × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.75, N=117
- Validation: z=-0.18, N=322, attenuation=94%
- OOS: z=-2.29, N=193, attenuation=17%
- ROI: synthetic=+3.1%, real=+3.3%

### home_sp_BACK_LOADED × opp_pl_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.75, N=149
- Validation: z=+1.00, N=213, attenuation=64%
- OOS: z=+0.90, N=179, attenuation=67%
- ROI: synthetic=+3.1%, real=+3.1%

### batting_total_bip_last_5_LOW × exit_prob_by_7_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.74, N=307
- Validation: z=-0.68, N=541, attenuation=75%
- OOS: z=-2.25, N=479, attenuation=18%
- ROI: synthetic=+5.1%, real=+5.2%

### opp_pl_heart_drift_last_3_LOW × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.74, N=123
- Validation: z=+1.56, N=236, attenuation=43%
- OOS: z=+1.11, N=227, attenuation=59%
- ROI: synthetic=-0.2%, real=-0.3%

### opp_sp_contact_hh_allowed_last_3_HIGH × middle_order_hard_hit_rate_LOW
- Direction: OVER
- Discovery: z=+2.74, N=124
- Validation: z=+0.06, N=218, attenuation=98%
- OOS: z=+1.07, N=306, attenuation=61%
- ROI: synthetic=+0.7%, real=+0.9%

### damage_iso_last_10_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.73, N=131
- Validation: z=+2.07, N=138, attenuation=24%
- OOS: z=+2.98, N=168, attenuation=-9%
- ROI: synthetic=+10.3%, real=+10.2%

### batting_total_bip_last_10_LOW × opp_pl_zone_drift_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.73, N=117
- Validation: z=-0.01, N=237, attenuation=100%
- OOS: z=-1.70, N=163, attenuation=38%
- ROI: synthetic=+6.7%, real=+6.6%

### contact_xwoba_last_10_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.73, N=134
- Validation: z=-0.42, N=290, attenuation=84%
- OOS: z=-1.65, N=404, attenuation=40%
- ROI: synthetic=+8.0%, real=+7.9%

### middle_order_avg_exit_velo_LOW × lineup_quality_ev_HIGH
- Direction: OVER
- Discovery: z=+2.73, N=92
- Validation: z=+0.11, N=189, attenuation=96%
- OOS: z=+1.77, N=211, attenuation=35%
- ROI: synthetic=+5.7%, real=+6.0%

### damage_iso_last_20_HIGH × opp_pl_pfx_z_mean_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.73, N=121
- Validation: z=+1.33, N=112, attenuation=51%
- OOS: z=+1.47, N=132, attenuation=46%
- ROI: synthetic=+5.6%, real=+5.6%

### contact_xwoba_last_20_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.73, N=131
- Validation: z=+1.27, N=161, attenuation=53%
- OOS: z=+1.72, N=155, attenuation=37%
- ROI: synthetic=+6.3%, real=+6.1%

### contact_barrel_rate_last_10_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.72, N=140
- Validation: z=-0.68, N=276, attenuation=75%
- OOS: z=-1.01, N=248, attenuation=63%
- ROI: synthetic=+5.3%, real=+5.0%

### home_lu_HIGH_TURNOVER × contact_la_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.72, N=68
- Validation: z=+1.23, N=144, attenuation=55%
- OOS: z=+2.94, N=101, attenuation=-8%
- ROI: synthetic=+6.2%, real=+6.2%

### batting_barrel_rate_last_5_LOW × leverage_gap_k_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.71, N=49
- Validation: z=-0.69, N=102, attenuation=74%
- OOS: z=-0.89, N=79, attenuation=67%
- ROI: synthetic=+8.6%, real=+8.3%

### batting_total_bip_last_5_HIGH × exit_prob_by_6_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.71, N=117
- Validation: z=+0.94, N=128, attenuation=65%
- OOS: z=+1.34, N=202, attenuation=50%
- ROI: synthetic=+3.9%, real=+4.2%

### home_sp_BACK_LOADED × opp_sp_damage_hr_rate_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.71, N=160
- Validation: z=+0.57, N=198, attenuation=79%
- OOS: z=+1.52, N=215, attenuation=44%
- ROI: synthetic=-2.5%, real=-2.4%

### contact_xwoba_last_7_HIGH × opp_sp_command_bb_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.71, N=123
- Validation: z=+0.12, N=128, attenuation=95%
- OOS: z=+1.34, N=136, attenuation=51%
- ROI: synthetic=+1.5%, real=+1.7%

### damage_iso_last_20_HIGH × bottom_order_hard_hit_rate_HIGH
- Direction: OVER
- Discovery: z=+2.71, N=159
- Validation: z=+0.56, N=216, attenuation=79%
- OOS: z=+3.58, N=231, attenuation=-32%
- ROI: synthetic=+4.2%, real=+4.1%

### batting_total_bip_last_5_HIGH × low_lev_bb_rate_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.70, N=108
- Validation: z=+0.90, N=165, attenuation=67%
- OOS: z=+0.94, N=171, attenuation=65%
- ROI: synthetic=+3.9%, real=+4.0%

### park_factor_runs_HIGH × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.70, N=140
- Validation: z=-1.23, N=315, attenuation=54%
- OOS: z=-2.81, N=290, attenuation=-4%
- ROI: synthetic=+8.1%, real=+8.1%

### park_factor_hr_HIGH × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.70, N=140
- Validation: z=-1.23, N=315, attenuation=54%
- OOS: z=-2.81, N=290, attenuation=-4%
- ROI: synthetic=+8.1%, real=+8.1%

### batting_total_bip_last_5_LOW × top_order_avg_exit_velo_LOW
- Direction: UNDER
- Discovery: z=-2.70, N=168
- Validation: z=-0.17, N=180, attenuation=94%
- OOS: z=-1.46, N=226, attenuation=46%
- ROI: synthetic=+3.5%, real=+3.5%

### home_sp_BACK_LOADED × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.69, N=164
- Validation: z=+0.25, N=250, attenuation=91%
- OOS: z=+3.40, N=247, attenuation=-26%
- ROI: synthetic=+3.5%, real=+3.9%

### lineup_quality_ev_LOW × med_lev_bb_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.69, N=138
- Validation: z=-0.40, N=194, attenuation=85%
- OOS: z=-1.12, N=210, attenuation=58%
- ROI: synthetic=+2.2%, real=+2.2%

### batting_total_bip_last_5_HIGH × opp_pl_ff_pct_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.69, N=129
- Validation: z=+0.94, N=147, attenuation=65%
- OOS: z=+3.42, N=153, attenuation=-27%
- ROI: synthetic=+11.6%, real=+11.5%

### opp_sp_contact_ev_allowed_last_3_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.68, N=113
- Validation: z=-0.80, N=210, attenuation=70%
- OOS: z=-2.44, N=143, attenuation=9%
- ROI: synthetic=+15.4%, real=+15.0%

### opp_sp_command_bb_rate_last_10_LOW × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.68, N=124
- Validation: z=+0.93, N=195, attenuation=65%
- OOS: z=+2.86, N=176, attenuation=-7%
- ROI: synthetic=+7.7%, real=+7.8%

### opp_pl_spin_ff_mean_last_5_LOW × med_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.67, N=102
- Validation: z=+1.20, N=128, attenuation=55%
- OOS: z=+1.42, N=118, attenuation=47%
- ROI: synthetic=+1.2%, real=+1.3%

### batting_total_bip_last_10_LOW × bottom_order_coverage_LOW
- Direction: UNDER
- Discovery: z=-2.66, N=222
- Validation: z=-0.53, N=420, attenuation=80%
- OOS: z=-2.03, N=373, attenuation=24%
- ROI: synthetic=+3.5%, real=+3.2%

### contact_ev_last_20_LOW × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.66, N=149
- Validation: z=-0.30, N=393, attenuation=89%
- OOS: z=-1.47, N=228, attenuation=45%
- ROI: synthetic=+2.7%, real=+2.9%

### wind_speed_HIGH × high_lev_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.66, N=131
- Validation: z=+0.82, N=210, attenuation=69%
- OOS: z=+1.20, N=125, attenuation=55%
- ROI: synthetic=+5.6%, real=+5.8%

### batting_total_bip_last_3_HIGH × exit_prob_by_6_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.66, N=115
- Validation: z=+0.70, N=143, attenuation=74%
- OOS: z=+1.40, N=206, attenuation=47%
- ROI: synthetic=+1.0%, real=+1.4%

### opp_sp_command_bb_rate_last_10_LOW × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.66, N=127
- Validation: z=+0.72, N=194, attenuation=73%
- OOS: z=+2.12, N=174, attenuation=20%
- ROI: synthetic=+5.1%, real=+5.2%

### opp_pl_ff_pct_last_5_HIGH × opp_pl_pfx_z_std_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.65, N=148
- Validation: z=+0.26, N=203, attenuation=90%
- OOS: z=+1.38, N=204, attenuation=48%
- ROI: synthetic=+2.8%, real=+2.9%

### home_sp_BACK_LOADED × opp_sp_batmiss_k_rate_last_3_LOW
- Direction: OVER
- Discovery: z=+2.65, N=131
- Validation: z=+0.75, N=238, attenuation=72%
- OOS: z=+1.64, N=232, attenuation=38%
- ROI: synthetic=+1.9%, real=+1.9%

### home_bp_BALANCED_DEPTH × batting_total_bip_last_1_LOW
- Direction: UNDER
- Discovery: z=-2.65, N=98
- Validation: z=-0.95, N=217, attenuation=64%
- OOS: z=-1.07, N=220, attenuation=59%
- ROI: synthetic=+3.1%, real=+3.1%

### opp_sp_contact_ev_allowed_last_5_HIGH × opp_pl_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.65, N=113
- Validation: z=+0.17, N=132, attenuation=94%
- OOS: z=+1.35, N=226, attenuation=49%
- ROI: synthetic=+5.3%, real=+5.2%

### contact_hh_rate_last_20_HIGH × damage_iso_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.65, N=201
- Validation: z=+1.44, N=186, attenuation=46%
- OOS: z=+0.84, N=357, attenuation=68%
- ROI: synthetic=-2.3%, real=-2.3%

### batting_barrel_rate_last_5_LOW × opp_pl_primary_mix_drift_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.64, N=123
- Validation: z=-0.10, N=200, attenuation=96%
- OOS: z=-1.25, N=133, attenuation=53%
- ROI: synthetic=+5.1%, real=+5.1%

### damage_hr_rate_last_7_HIGH × opp_sp_workload_ppbf_last_3_LOW
- Direction: OVER
- Discovery: z=+2.64, N=131
- Validation: z=+1.06, N=147, attenuation=60%
- OOS: z=+1.41, N=183, attenuation=47%
- ROI: synthetic=+1.8%, real=+1.9%

### opp_sp_command_bb_rate_last_5_LOW × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.64, N=131
- Validation: z=+1.35, N=222, attenuation=49%
- OOS: z=+1.95, N=211, attenuation=26%
- ROI: synthetic=+4.3%, real=+4.2%

### batting_total_bip_last_3_LOW × opp_pl_pfx_x_mean_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.64, N=114
- Validation: z=-0.45, N=239, attenuation=83%
- OOS: z=-1.66, N=182, attenuation=37%
- ROI: synthetic=+7.2%, real=+7.1%

### batting_total_bip_last_5_LOW × deterioration_score_norm_HIGH
- Direction: UNDER
- Discovery: z=-2.63, N=114
- Validation: z=-1.96, N=195, attenuation=25%
- OOS: z=-0.88, N=171, attenuation=67%
- ROI: synthetic=+7.5%, real=+7.4%

### damage_hr_rate_last_15_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.63, N=171
- Validation: z=+0.64, N=228, attenuation=76%
- OOS: z=+2.50, N=248, attenuation=5%
- ROI: synthetic=+0.5%, real=+0.6%

### opp_sp_contact_ev_allowed_last_3_HIGH × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.62, N=138
- Validation: z=+0.43, N=174, attenuation=84%
- OOS: z=+4.12, N=281, attenuation=-57%
- ROI: synthetic=+9.8%, real=+9.9%

### opp_sp_damage_hr_rate_last_3_LOW × batting_avg_exit_velo_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.62, N=128
- Validation: z=-0.70, N=314, attenuation=73%
- OOS: z=-1.95, N=222, attenuation=26%
- ROI: synthetic=+7.1%, real=+7.1%

### damage_hr_rate_last_20_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.61, N=115
- Validation: z=-0.49, N=274, attenuation=81%
- OOS: z=-1.53, N=337, attenuation=41%
- ROI: synthetic=+5.1%, real=+5.1%

### damage_hr_rate_last_20_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.61, N=115
- Validation: z=-0.49, N=274, attenuation=81%
- OOS: z=-1.53, N=337, attenuation=41%
- ROI: synthetic=+5.1%, real=+5.1%

### batting_barrel_rate_last_10_LOW × opp_pl_zone_rate_season_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.60, N=129
- Validation: z=-0.19, N=314, attenuation=93%
- OOS: z=-1.07, N=275, attenuation=59%
- ROI: synthetic=+1.0%, real=+1.0%

### contact_xslg_last_20_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.60, N=134
- Validation: z=+1.99, N=124, attenuation=23%
- OOS: z=+1.09, N=153, attenuation=58%
- ROI: synthetic=+6.1%, real=+5.8%

### damage_hr_rate_last_20_LOW × opp_sp_command_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.60, N=124
- Validation: z=-0.46, N=276, attenuation=82%
- OOS: z=-1.62, N=350, attenuation=38%
- ROI: synthetic=+4.2%, real=+4.1%

### contact_ev_last_20_LOW × opp_sp_command_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.60, N=135
- Validation: z=-0.32, N=345, attenuation=88%
- OOS: z=-1.19, N=278, attenuation=54%
- ROI: synthetic=+4.8%, real=+4.7%

### damage_hr_rate_last_7_HIGH × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.59, N=132
- Validation: z=+1.50, N=137, attenuation=42%
- OOS: z=+1.97, N=168, attenuation=24%
- ROI: synthetic=-0.9%, real=-0.9%

### contact_xwoba_last_10_HIGH × damage_iso_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.59, N=255
- Validation: z=+1.36, N=278, attenuation=47%
- OOS: z=+1.25, N=278, attenuation=52%
- ROI: synthetic=-0.7%, real=-0.5%

### bottom_order_avg_exit_velo_HIGH × low_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.59, N=127
- Validation: z=+0.26, N=279, attenuation=90%
- OOS: z=+1.24, N=245, attenuation=52%
- ROI: synthetic=+1.1%, real=+1.4%

### damage_iso_last_20_HIGH × damage_hr_rate_last_7_HIGH
- Direction: OVER
- Discovery: z=+2.58, N=285
- Validation: z=+0.97, N=263, attenuation=62%
- OOS: z=+1.92, N=341, attenuation=26%
- ROI: synthetic=-1.4%, real=-1.3%

### opp_sp_contact_barrel_allowed_last_5_HIGH × temperature_HIGH
- Direction: OVER
- Discovery: z=+2.58, N=124
- Validation: z=+0.34, N=184, attenuation=87%
- OOS: z=+0.93, N=219, attenuation=64%
- ROI: synthetic=-0.6%, real=-0.7%

### plate_k_rate_last_10_LOW × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.58, N=60
- Validation: z=-0.35, N=143, attenuation=86%
- OOS: z=-1.93, N=158, attenuation=25%
- ROI: synthetic=+7.4%, real=+7.3%

### contact_hh_rate_last_15_LOW × lineup_quality_ev_LOW
- Direction: UNDER
- Discovery: z=-2.57, N=219
- Validation: z=-0.10, N=354, attenuation=96%
- OOS: z=-1.03, N=203, attenuation=60%
- ROI: synthetic=+3.7%, real=+3.8%

### damage_iso_last_20_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.57, N=137
- Validation: z=+0.88, N=156, attenuation=66%
- OOS: z=+1.68, N=175, attenuation=34%
- ROI: synthetic=+1.0%, real=+1.1%

### batting_total_bip_last_3_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.57, N=159
- Validation: z=+2.27, N=327, attenuation=11%
- OOS: z=+1.98, N=294, attenuation=23%
- ROI: synthetic=-0.1%, real=+0.1%

### damage_hr_rate_last_7_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.56, N=135
- Validation: z=+1.04, N=165, attenuation=59%
- OOS: z=+1.94, N=204, attenuation=24%
- ROI: synthetic=-1.8%, real=-1.8%

### damage_hr_rate_last_10_HIGH × opp_sp_workload_ppbf_last_3_LOW
- Direction: OVER
- Discovery: z=+2.56, N=138
- Validation: z=+2.70, N=148, attenuation=-5%
- OOS: z=+1.24, N=187, attenuation=52%
- ROI: synthetic=+8.4%, real=+8.7%

### opp_sp_damage_hits_per_bf_last_5_HIGH × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.56, N=126
- Validation: z=-0.68, N=195, attenuation=73%
- OOS: z=-1.64, N=195, attenuation=36%
- ROI: synthetic=+8.8%, real=+9.2%

### home_sp_BACK_LOADED × opp_sp_damage_hr_rate_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.55, N=149
- Validation: z=+1.63, N=172, attenuation=36%
- OOS: z=+3.20, N=191, attenuation=-25%
- ROI: synthetic=+4.0%, real=+3.9%

### contact_hh_rate_last_20_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.55, N=123
- Validation: z=-0.77, N=307, attenuation=70%
- OOS: z=-1.66, N=182, attenuation=35%
- ROI: synthetic=+7.1%, real=+7.0%

### contact_hh_rate_last_20_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.55, N=123
- Validation: z=-0.77, N=307, attenuation=70%
- OOS: z=-1.66, N=182, attenuation=35%
- ROI: synthetic=+7.1%, real=+7.0%

### home_lu_STABLE_DEEP × opp_pl_arm_angle_mean_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.55, N=98
- Validation: z=-1.12, N=165, attenuation=56%
- OOS: z=-1.37, N=201, attenuation=46%
- ROI: synthetic=+7.6%, real=+7.5%

### batting_total_bip_last_3_HIGH × lineup_coverage_overall_LOW
- Direction: OVER
- Discovery: z=+2.55, N=216
- Validation: z=+0.89, N=356, attenuation=65%
- OOS: z=+2.81, N=433, attenuation=-10%
- ROI: synthetic=+1.7%, real=+1.8%

### home_lu_STABLE_DEEP × opp_sp_workload_pitches_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.54, N=120
- Validation: z=-1.12, N=130, attenuation=56%
- OOS: z=-1.61, N=103, attenuation=37%
- ROI: synthetic=+11.8%, real=+11.5%

### opp_sp_contact_ev_allowed_last_5_HIGH × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.54, N=140
- Validation: z=+0.85, N=162, attenuation=66%
- OOS: z=+2.93, N=282, attenuation=-16%
- ROI: synthetic=+8.0%, real=+8.3%

### opp_sp_workload_ip_last_10_HIGH × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.54, N=126
- Validation: z=+0.46, N=194, attenuation=82%
- OOS: z=+0.87, N=139, attenuation=66%
- ROI: synthetic=+0.4%, real=+0.6%

### damage_iso_last_20_HIGH × opp_pl_two_strike_secondary_pct_season_baseline_LOW
- Direction: OVER
- Discovery: z=+2.53, N=134
- Validation: z=+0.81, N=146, attenuation=68%
- OOS: z=+1.04, N=141, attenuation=59%
- ROI: synthetic=+0.2%, real=+0.7%

### away_sp_BACK_LOADED × damage_hr_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.53, N=143
- Validation: z=-1.10, N=302, attenuation=57%
- OOS: z=-1.43, N=308, attenuation=44%
- ROI: synthetic=+5.4%, real=+5.5%

### batting_total_bip_last_5_HIGH × opp_pl_two_strike_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.53, N=140
- Validation: z=+1.36, N=183, attenuation=46%
- OOS: z=+2.42, N=175, attenuation=4%
- ROI: synthetic=+6.0%, real=+6.0%

### contact_ev_last_20_HIGH × damage_iso_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.53, N=208
- Validation: z=+1.71, N=190, attenuation=32%
- OOS: z=+0.86, N=291, attenuation=66%
- ROI: synthetic=+0.0%, real=+0.1%

### opp_pl_sl_pct_last_5_LOW × top_order_avg_exit_velo_LOW
- Direction: UNDER
- Discovery: z=-2.53, N=111
- Validation: z=-1.33, N=130, attenuation=48%
- OOS: z=-0.79, N=133, attenuation=69%
- ROI: synthetic=+9.6%, real=+9.9%

### damage_hr_rate_last_7_HIGH × opp_pl_secondary_2strike_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.53, N=137
- Validation: z=+0.71, N=147, attenuation=72%
- OOS: z=+0.95, N=142, attenuation=62%
- ROI: synthetic=-1.1%, real=-1.2%

### opp_sp_damage_hr_rate_last_3_LOW × opp_pl_edge_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.53, N=139
- Validation: z=-0.84, N=255, attenuation=67%
- OOS: z=-2.14, N=285, attenuation=15%
- ROI: synthetic=+11.8%, real=+11.9%

### opp_sp_contact_barrel_allowed_last_10_HIGH × lineup_quality_ev_HIGH
- Direction: OVER
- Discovery: z=+2.52, N=119
- Validation: z=+0.22, N=186, attenuation=91%
- OOS: z=+0.81, N=241, attenuation=68%
- ROI: synthetic=-2.9%, real=-3.1%

### home_st_INEFFICIENT_PITCHER × opp_sp_workload_ip_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.52, N=129
- Validation: z=-1.34, N=188, attenuation=47%
- OOS: z=-1.18, N=202, attenuation=53%
- ROI: synthetic=+13.1%, real=+13.3%

### damage_iso_last_15_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.52, N=141
- Validation: z=+2.88, N=130, attenuation=-14%
- OOS: z=+1.29, N=157, attenuation=49%
- ROI: synthetic=+7.5%, real=+7.5%

### contact_ev_last_15_LOW × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.52, N=153
- Validation: z=-0.79, N=390, attenuation=69%
- OOS: z=-1.47, N=248, attenuation=42%
- ROI: synthetic=+3.1%, real=+2.9%

### damage_hr_rate_last_20_HIGH × opp_pl_two_strike_secondary_pct_season_baseline_LOW
- Direction: OVER
- Discovery: z=+2.52, N=139
- Validation: z=+0.08, N=140, attenuation=97%
- OOS: z=+1.01, N=154, attenuation=60%
- ROI: synthetic=-0.4%, real=+0.1%

### damage_iso_last_15_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.52, N=137
- Validation: z=+1.84, N=147, attenuation=27%
- OOS: z=+1.92, N=162, attenuation=24%
- ROI: synthetic=+4.0%, real=+4.0%

### opp_sp_batmiss_whiff_rate_last_10_LOW × batting_barrel_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.52, N=126
- Validation: z=+0.25, N=170, attenuation=90%
- OOS: z=+1.28, N=239, attenuation=49%
- ROI: synthetic=-3.4%, real=-3.1%

### batting_total_bip_last_5_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.52, N=162
- Validation: z=+1.98, N=312, attenuation=21%
- OOS: z=+2.22, N=280, attenuation=12%
- ROI: synthetic=+2.5%, real=+2.6%

### contact_xslg_last_7_LOW × opp_pl_edge_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.51, N=117
- Validation: z=-0.13, N=327, attenuation=95%
- OOS: z=-0.96, N=370, attenuation=62%
- ROI: synthetic=+4.8%, real=+4.8%

### opp_sp_batmiss_whiff_rate_last_10_HIGH × batting_total_bip_last_1_LOW
- Direction: UNDER
- Discovery: z=-2.51, N=117
- Validation: z=-1.17, N=149, attenuation=53%
- OOS: z=-1.80, N=166, attenuation=28%
- ROI: synthetic=+8.0%, real=+7.9%

### contact_ev_last_20_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.51, N=127
- Validation: z=-0.45, N=336, attenuation=82%
- OOS: z=-1.28, N=271, attenuation=49%
- ROI: synthetic=+6.8%, real=+6.6%

### contact_ev_last_20_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.51, N=127
- Validation: z=-0.45, N=336, attenuation=82%
- OOS: z=-1.28, N=271, attenuation=49%
- ROI: synthetic=+6.8%, real=+6.6%

### relievers_used_last_game_LOW × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.51, N=288
- Validation: z=+1.87, N=391, attenuation=26%
- OOS: z=+2.87, N=407, attenuation=-15%
- ROI: synthetic=+7.9%, real=+7.9%

### opp_sp_command_zone_rate_last_3_HIGH × batting_barrel_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.51, N=144
- Validation: z=-1.52, N=286, attenuation=39%
- OOS: z=-1.20, N=237, attenuation=52%
- ROI: synthetic=+5.0%, real=+4.9%

### contact_xslg_last_10_HIGH × damage_iso_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.51, N=268
- Validation: z=+1.58, N=260, attenuation=37%
- OOS: z=+1.41, N=288, attenuation=44%
- ROI: synthetic=-0.1%, real=+0.0%

### damage_iso_last_15_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.51, N=133
- Validation: z=+0.76, N=142, attenuation=70%
- OOS: z=+1.54, N=163, attenuation=39%
- ROI: synthetic=+1.8%, real=+1.8%

### contact_la_last_20_HIGH × relievers_used_last_3_games_HIGH
- Direction: OVER
- Discovery: z=+2.50, N=148
- Validation: z=+2.52, N=303, attenuation=-0%
- OOS: z=+1.59, N=344, attenuation=37%
- ROI: synthetic=+6.2%, real=+6.4%

### contact_barrel_rate_last_20_LOW × batting_avg_exit_velo_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.50, N=75
- Validation: z=-0.07, N=129, attenuation=97%
- OOS: z=-0.91, N=110, attenuation=64%
- ROI: synthetic=+5.5%, real=+5.1%

### plate_bb_rate_last_20_HIGH × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.50, N=140
- Validation: z=+0.93, N=142, attenuation=63%
- OOS: z=+1.94, N=171, attenuation=23%
- ROI: synthetic=+6.4%, real=+6.9%

### opp_sp_contact_la_allowed_last_5_HIGH × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.50, N=116
- Validation: z=+0.49, N=232, attenuation=81%
- OOS: z=+1.72, N=277, attenuation=31%
- ROI: synthetic=-1.9%, real=-1.7%

### away_bp_DEPLETED_BRIDGE × wind_speed_HIGH
- Direction: OVER
- Discovery: z=+2.50, N=109
- Validation: z=+0.57, N=182, attenuation=77%
- OOS: z=+1.14, N=112, attenuation=54%
- ROI: synthetic=+7.4%, real=+7.3%

### home_sp_BACK_LOADED × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.50, N=138
- Validation: z=+1.56, N=223, attenuation=37%
- OOS: z=+0.93, N=207, attenuation=63%
- ROI: synthetic=-1.3%, real=-1.2%

### damage_hr_rate_last_10_HIGH × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.50, N=126
- Validation: z=+1.30, N=111, attenuation=48%
- OOS: z=+0.85, N=142, attenuation=66%
- ROI: synthetic=+7.3%, real=+7.1%

### opp_sp_command_bb_rate_last_3_HIGH × leverage_gap_k_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.50, N=51
- Validation: z=-0.30, N=88, attenuation=88%
- OOS: z=-1.38, N=119, attenuation=45%
- ROI: synthetic=+12.7%, real=+12.8%

### batting_total_bip_last_5_HIGH × low_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.50, N=134
- Validation: z=+1.27, N=173, attenuation=49%
- OOS: z=+2.06, N=192, attenuation=17%
- ROI: synthetic=+7.4%, real=+7.5%

### high_leverage_available_HIGH × leverage_gap_k_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.50, N=65
- Validation: z=-0.55, N=138, attenuation=78%
- OOS: z=-1.87, N=122, attenuation=25%
- ROI: synthetic=+9.4%, real=+9.6%

### batting_hard_hit_rate_last_5_LOW × bottom_order_hard_hit_rate_LOW
- Direction: UNDER
- Discovery: z=-2.50, N=193
- Validation: z=-0.39, N=286, attenuation=84%
- OOS: z=-2.66, N=214, attenuation=-7%
- ROI: synthetic=+5.6%, real=+5.5%

### contact_ev_last_20_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.49, N=130
- Validation: z=+0.75, N=133, attenuation=70%
- OOS: z=+0.98, N=255, attenuation=61%
- ROI: synthetic=-0.3%, real=-0.5%

### damage_hr_rate_last_10_HIGH × opp_pl_secondary_2strike_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.49, N=138
- Validation: z=+0.66, N=148, attenuation=73%
- OOS: z=+1.26, N=145, attenuation=49%
- ROI: synthetic=+3.3%, real=+3.1%

### contact_hh_rate_last_20_LOW × opp_sp_contact_barrel_allowed_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.49, N=139
- Validation: z=-0.32, N=317, attenuation=87%
- OOS: z=-3.36, N=111, attenuation=-35%
- ROI: synthetic=+8.0%, real=+7.9%

### damage_iso_last_10_HIGH × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.49, N=125
- Validation: z=+0.89, N=122, attenuation=64%
- OOS: z=+3.20, N=157, attenuation=-29%
- ROI: synthetic=+6.5%, real=+6.6%

### plate_k_rate_last_15_HIGH × batting_avg_exit_velo_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.49, N=117
- Validation: z=-1.07, N=161, attenuation=57%
- OOS: z=-1.20, N=199, attenuation=52%
- ROI: synthetic=+7.1%, real=+7.2%

### damage_hr_rate_last_10_HIGH × opp_pl_chase_rate_last_3_LOW
- Direction: OVER
- Discovery: z=+2.49, N=123
- Validation: z=+0.78, N=139, attenuation=69%
- OOS: z=+0.79, N=246, attenuation=68%
- ROI: synthetic=+1.8%, real=+2.0%

### damage_hr_rate_last_10_HIGH × opp_pl_zone_rate_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.49, N=123
- Validation: z=+0.78, N=139, attenuation=69%
- OOS: z=+0.79, N=246, attenuation=68%
- ROI: synthetic=+1.8%, real=+2.0%

### batting_total_bip_last_5_HIGH × opp_pl_velo_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.48, N=112
- Validation: z=+1.23, N=159, attenuation=50%
- OOS: z=+1.80, N=170, attenuation=28%
- ROI: synthetic=+1.6%, real=+1.8%

### contact_barrel_rate_last_20_HIGH × opp_sp_contact_barrel_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.48, N=137
- Validation: z=+0.31, N=112, attenuation=88%
- OOS: z=+1.82, N=263, attenuation=27%
- ROI: synthetic=-0.1%, real=+0.1%

### contact_barrel_rate_last_10_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.48, N=178
- Validation: z=-0.33, N=280, attenuation=87%
- OOS: z=-2.87, N=164, attenuation=-16%
- ROI: synthetic=+6.9%, real=+6.8%

### contact_ev_last_15_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.47, N=145
- Validation: z=+1.86, N=160, attenuation=25%
- OOS: z=+1.17, N=283, attenuation=53%
- ROI: synthetic=+2.9%, real=+3.0%

### damage_hr_rate_last_10_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.47, N=137
- Validation: z=+2.22, N=160, attenuation=10%
- OOS: z=+1.78, N=202, attenuation=28%
- ROI: synthetic=+5.3%, real=+5.4%

### batting_barrel_rate_last_1_LOW × high_lev_bb_rate_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.47, N=136
- Validation: z=-1.59, N=166, attenuation=36%
- OOS: z=-1.48, N=180, attenuation=40%
- ROI: synthetic=+10.9%, real=+10.8%

### damage_iso_last_10_HIGH × med_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.47, N=150
- Validation: z=+0.84, N=161, attenuation=66%
- OOS: z=+0.75, N=151, attenuation=69%
- ROI: synthetic=+0.3%, real=+0.3%

### opp_sp_damage_hr_rate_last_3_LOW × park_factor_runs_HIGH
- Direction: UNDER
- Discovery: z=-2.47, N=138
- Validation: z=-0.79, N=270, attenuation=68%
- OOS: z=-2.03, N=251, attenuation=18%
- ROI: synthetic=+7.0%, real=+7.2%

### opp_sp_damage_hr_rate_last_3_LOW × park_factor_hr_HIGH
- Direction: UNDER
- Discovery: z=-2.47, N=138
- Validation: z=-0.79, N=270, attenuation=68%
- OOS: z=-2.03, N=251, attenuation=18%
- ROI: synthetic=+7.0%, real=+7.2%

### batting_total_bip_last_3_HIGH × low_lev_bb_rate_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.47, N=105
- Validation: z=+0.82, N=168, attenuation=67%
- OOS: z=+1.75, N=178, attenuation=29%
- ROI: synthetic=+2.1%, real=+2.5%

### batting_total_bip_last_10_LOW × high_lev_hr_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.47, N=126
- Validation: z=-1.17, N=193, attenuation=53%
- OOS: z=-0.91, N=204, attenuation=63%
- ROI: synthetic=+3.3%, real=+3.3%

### damage_hr_rate_last_15_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.47, N=140
- Validation: z=+1.07, N=142, attenuation=57%
- OOS: z=+1.55, N=187, attenuation=37%
- ROI: synthetic=+0.7%, real=+0.8%

### opp_sp_contact_ev_allowed_last_5_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.46, N=128
- Validation: z=+0.47, N=165, attenuation=81%
- OOS: z=+2.82, N=285, attenuation=-15%
- ROI: synthetic=+5.8%, real=+6.2%

### damage_iso_last_10_HIGH × lineup_depth_dropoff_hh_LOW
- Direction: OVER
- Discovery: z=+2.46, N=114
- Validation: z=+1.33, N=113, attenuation=46%
- OOS: z=+1.59, N=143, attenuation=35%
- ROI: synthetic=+5.5%, real=+5.5%

### opp_sp_contact_la_allowed_last_10_HIGH × home_rest_days_LOW
- Direction: OVER
- Discovery: z=+2.46, N=312
- Validation: z=+0.11, N=492, attenuation=95%
- OOS: z=+0.78, N=491, attenuation=68%
- ROI: synthetic=-2.9%, real=-3.0%

### opp_sp_command_bb_rate_last_5_LOW × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.45, N=129
- Validation: z=+0.30, N=215, attenuation=88%
- OOS: z=+2.09, N=199, attenuation=15%
- ROI: synthetic=+4.6%, real=+4.2%

### contact_ev_last_7_LOW × exit_prob_by_5_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.45, N=171
- Validation: z=-0.23, N=340, attenuation=91%
- OOS: z=-1.37, N=280, attenuation=44%
- ROI: synthetic=+6.1%, real=+6.2%

### contact_xwoba_last_10_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.45, N=128
- Validation: z=-0.43, N=289, attenuation=83%
- OOS: z=-2.05, N=401, attenuation=16%
- ROI: synthetic=+7.5%, real=+7.2%

### contact_xwoba_last_10_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.45, N=128
- Validation: z=-0.43, N=289, attenuation=83%
- OOS: z=-2.05, N=401, attenuation=16%
- ROI: synthetic=+7.5%, real=+7.2%

### home_lu_STABLE_DEEP × batting_total_bip_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.45, N=94
- Validation: z=-3.15, N=201, attenuation=-29%
- OOS: z=-1.05, N=174, attenuation=57%
- ROI: synthetic=+11.8%, real=+12.0%

### contact_xslg_last_20_HIGH × opp_sp_workload_ip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.44, N=138
- Validation: z=+0.14, N=131, attenuation=94%
- OOS: z=+0.94, N=133, attenuation=62%
- ROI: synthetic=+2.1%, real=+2.4%

### contact_hh_rate_last_20_LOW × opp_sp_command_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.44, N=137
- Validation: z=-0.60, N=318, attenuation=76%
- OOS: z=-1.46, N=189, attenuation=40%
- ROI: synthetic=+5.3%, real=+5.2%

### damage_iso_last_10_HIGH × opp_sp_workload_ip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.44, N=149
- Validation: z=+1.21, N=151, attenuation=50%
- OOS: z=+1.47, N=143, attenuation=40%
- ROI: synthetic=+2.4%, real=+2.7%

### contact_xwoba_last_10_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.44, N=116
- Validation: z=+0.68, N=165, attenuation=72%
- OOS: z=+1.52, N=147, attenuation=38%
- ROI: synthetic=+5.1%, real=+5.0%

### contact_xslg_last_20_HIGH × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.44, N=139
- Validation: z=+0.72, N=149, attenuation=71%
- OOS: z=+1.79, N=154, attenuation=26%
- ROI: synthetic=+5.0%, real=+5.4%

### relievers_used_last_game_HIGH × top_order_barrel_rate_LOW
- Direction: UNDER
- Discovery: z=-2.44, N=188
- Validation: z=-0.27, N=191, attenuation=89%
- OOS: z=-0.99, N=215, attenuation=59%
- ROI: synthetic=+4.3%, real=+4.1%

### batting_barrel_rate_last_3_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.43, N=160
- Validation: z=-0.15, N=263, attenuation=94%
- OOS: z=-1.23, N=175, attenuation=50%
- ROI: synthetic=+4.7%, real=+4.8%

### plate_bb_rate_last_10_HIGH × opp_sp_command_bb_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.43, N=136
- Validation: z=-0.75, N=154, attenuation=69%
- OOS: z=-1.00, N=183, attenuation=59%
- ROI: synthetic=+5.4%, real=+5.3%

### opp_pl_chase_rate_last_3_LOW × med_lev_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.43, N=113
- Validation: z=-0.72, N=270, attenuation=71%
- OOS: z=-1.34, N=399, attenuation=45%
- ROI: synthetic=+7.7%, real=+7.6%

### opp_pl_zone_rate_last_3_HIGH × med_lev_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.43, N=113
- Validation: z=-0.72, N=270, attenuation=71%
- OOS: z=-1.34, N=399, attenuation=45%
- ROI: synthetic=+7.7%, real=+7.6%

### contact_xwoba_last_7_LOW × opp_pl_edge_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.43, N=123
- Validation: z=-0.35, N=282, attenuation=85%
- OOS: z=-1.17, N=348, attenuation=52%
- ROI: synthetic=+6.2%, real=+6.2%

### batting_total_bip_last_3_LOW × opp_pl_pfx_x_mean_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.43, N=108
- Validation: z=-0.37, N=223, attenuation=85%
- OOS: z=-1.95, N=171, attenuation=20%
- ROI: synthetic=+7.0%, real=+6.8%

### damage_hr_rate_last_10_HIGH × bottom_order_hard_hit_rate_HIGH
- Direction: OVER
- Discovery: z=+2.43, N=188
- Validation: z=+0.85, N=228, attenuation=65%
- OOS: z=+2.15, N=275, attenuation=12%
- ROI: synthetic=+1.5%, real=+1.5%

### opp_sp_contact_ev_allowed_last_5_HIGH × opp_pl_spin_sl_mean_last_5_LOW
- Direction: OVER
- Discovery: z=+2.43, N=60
- Validation: z=+0.12, N=84, attenuation=95%
- OOS: z=+3.04, N=156, attenuation=-25%
- ROI: synthetic=+6.9%, real=+7.2%

### relievers_used_last_game_HIGH × top_order_xwoba_contact_LOW
- Direction: UNDER
- Discovery: z=-2.43, N=187
- Validation: z=-0.19, N=166, attenuation=92%
- OOS: z=-1.25, N=172, attenuation=48%
- ROI: synthetic=+5.6%, real=+5.5%

### batting_total_bip_last_3_LOW × exit_prob_by_5_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.43, N=195
- Validation: z=-0.59, N=338, attenuation=76%
- OOS: z=-1.11, N=337, attenuation=54%
- ROI: synthetic=+5.5%, real=+5.7%

### damage_hr_rate_last_20_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.42, N=129
- Validation: z=+0.05, N=150, attenuation=98%
- OOS: z=+1.51, N=172, attenuation=38%
- ROI: synthetic=+0.2%, real=+0.2%

### damage_iso_last_10_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.42, N=136
- Validation: z=+0.13, N=145, attenuation=95%
- OOS: z=+2.48, N=188, attenuation=-2%
- ROI: synthetic=+2.1%, real=+2.2%

### away_bp_BALANCED_DEPTH × opp_pl_secondary_2strike_drift_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.41, N=103
- Validation: z=-0.03, N=161, attenuation=99%
- OOS: z=-1.07, N=171, attenuation=56%
- ROI: synthetic=+9.7%, real=+9.7%

### opp_sp_contact_la_allowed_last_10_HIGH × high_lev_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.41, N=118
- Validation: z=+0.48, N=166, attenuation=80%
- OOS: z=+1.16, N=202, attenuation=52%
- ROI: synthetic=-4.5%, real=-4.3%

### damage_hr_rate_last_10_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.41, N=135
- Validation: z=+1.14, N=156, attenuation=53%
- OOS: z=+1.89, N=200, attenuation=22%
- ROI: synthetic=+3.4%, real=+3.3%

### opp_sp_contact_la_allowed_last_5_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.41, N=132
- Validation: z=+1.23, N=215, attenuation=49%
- OOS: z=+4.09, N=245, attenuation=-70%
- ROI: synthetic=+7.5%, real=+7.6%

### opp_sp_command_zone_rate_last_5_HIGH × batting_barrel_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.41, N=129
- Validation: z=-0.81, N=270, attenuation=66%
- OOS: z=-0.98, N=236, attenuation=59%
- ROI: synthetic=+0.3%, real=+0.3%

### home_lu_HIGH_TURNOVER × batting_xwoba_contact_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.41, N=80
- Validation: z=+0.99, N=81, attenuation=59%
- OOS: z=+0.86, N=76, attenuation=64%
- ROI: synthetic=+1.1%, real=+1.2%

### contact_la_last_20_HIGH × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.41, N=143
- Validation: z=+1.61, N=241, attenuation=33%
- OOS: z=+3.63, N=267, attenuation=-51%
- ROI: synthetic=+13.0%, real=+13.2%

### damage_iso_last_20_HIGH × opp_sp_workload_ip_last_5_LOW
- Direction: OVER
- Discovery: z=+2.40, N=129
- Validation: z=+0.23, N=138, attenuation=90%
- OOS: z=+1.11, N=158, attenuation=54%
- ROI: synthetic=+0.2%, real=+0.2%

### contact_xwoba_last_15_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.40, N=119
- Validation: z=+0.30, N=182, attenuation=88%
- OOS: z=+1.14, N=146, attenuation=53%
- ROI: synthetic=-0.1%, real=+0.5%

### contact_la_last_20_HIGH × lineup_quality_ev_HIGH
- Direction: OVER
- Discovery: z=+2.40, N=152
- Validation: z=+0.09, N=417, attenuation=96%
- OOS: z=+2.40, N=354, attenuation=0%
- ROI: synthetic=+1.4%, real=+1.6%

### batting_avg_exit_velo_last_1_LOW × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.40, N=215
- Validation: z=-1.61, N=382, attenuation=33%
- OOS: z=-1.14, N=349, attenuation=52%
- ROI: synthetic=+3.6%, real=+3.7%

### opp_pl_heart_drift_last_3_LOW × opp_pl_secondary_2strike_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.40, N=134
- Validation: z=+0.07, N=215, attenuation=97%
- OOS: z=+2.75, N=196, attenuation=-14%
- ROI: synthetic=+4.4%, real=+4.2%

### batting_barrel_rate_last_10_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.40, N=128
- Validation: z=-1.23, N=288, attenuation=49%
- OOS: z=-0.88, N=238, attenuation=63%
- ROI: synthetic=+2.9%, real=+2.7%

### batting_barrel_rate_last_10_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.40, N=128
- Validation: z=-1.23, N=288, attenuation=49%
- OOS: z=-0.88, N=238, attenuation=63%
- ROI: synthetic=+2.9%, real=+2.7%

### batting_total_bip_last_3_LOW × top_order_avg_exit_velo_LOW
- Direction: UNDER
- Discovery: z=-2.39, N=164
- Validation: z=-0.47, N=185, attenuation=80%
- OOS: z=-1.42, N=229, attenuation=41%
- ROI: synthetic=+3.1%, real=+3.2%

### home_sp_BACK_LOADED × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.39, N=138
- Validation: z=+1.47, N=173, attenuation=38%
- OOS: z=+2.06, N=162, attenuation=14%
- ROI: synthetic=-2.7%, real=-2.6%

### relievers_used_last_game_LOW × opp_pl_velo_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.39, N=201
- Validation: z=+1.80, N=261, attenuation=24%
- OOS: z=+0.72, N=298, attenuation=70%
- ROI: synthetic=-0.4%, real=-0.4%

### damage_iso_last_15_HIGH × bottom_order_barrel_rate_HIGH
- Direction: OVER
- Discovery: z=+2.39, N=188
- Validation: z=+1.05, N=173, attenuation=56%
- OOS: z=+1.50, N=180, attenuation=37%
- ROI: synthetic=+3.9%, real=+4.1%

### opp_sp_workload_ip_last_3_LOW × batting_avg_exit_velo_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.39, N=132
- Validation: z=-1.18, N=277, attenuation=51%
- OOS: z=-1.56, N=251, attenuation=35%
- ROI: synthetic=+7.5%, real=+7.4%

### opp_sp_batmiss_whiff_rate_last_3_LOW × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.38, N=107
- Validation: z=+0.48, N=209, attenuation=80%
- OOS: z=+0.86, N=212, attenuation=64%
- ROI: synthetic=-0.2%, real=-0.3%

### contact_ev_last_20_HIGH × damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.38, N=220
- Validation: z=+1.27, N=185, attenuation=47%
- OOS: z=+1.01, N=305, attenuation=58%
- ROI: synthetic=-0.5%, real=-0.4%

### relievers_used_last_game_LOW × relievers_used_last_3_games_HIGH
- Direction: OVER
- Discovery: z=+2.38, N=168
- Validation: z=+2.43, N=249, attenuation=-2%
- OOS: z=+1.03, N=299, attenuation=57%
- ROI: synthetic=+5.2%, real=+5.3%

### opp_sp_contact_hh_allowed_last_3_LOW × opp_pl_two_strike_ff_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.38, N=121
- Validation: z=-0.80, N=190, attenuation=66%
- OOS: z=-1.36, N=173, attenuation=43%
- ROI: synthetic=+8.0%, real=+8.0%

### contact_xwoba_last_20_LOW × opp_sp_batmiss_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.38, N=113
- Validation: z=-0.36, N=217, attenuation=85%
- OOS: z=-0.95, N=290, attenuation=60%
- ROI: synthetic=+7.2%, real=+7.2%

### damage_iso_last_10_HIGH × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.38, N=132
- Validation: z=+2.20, N=104, attenuation=7%
- OOS: z=+0.97, N=141, attenuation=59%
- ROI: synthetic=+6.7%, real=+6.7%

### home_sp_BACK_LOADED × batting_total_bip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.38, N=170
- Validation: z=+0.93, N=243, attenuation=61%
- OOS: z=+2.52, N=234, attenuation=-6%
- ROI: synthetic=+3.9%, real=+4.0%

### opp_sp_workload_pitches_last_10_LOW × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.38, N=130
- Validation: z=+1.61, N=184, attenuation=32%
- OOS: z=+1.94, N=221, attenuation=18%
- ROI: synthetic=+4.3%, real=+4.4%

### batting_hard_hit_rate_last_5_LOW × batting_barrel_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.38, N=246
- Validation: z=-0.72, N=482, attenuation=70%
- OOS: z=-2.29, N=260, attenuation=4%
- ROI: synthetic=+2.1%, real=+1.9%

### opp_pl_primary_pitch_pct_season_baseline_LOW × low_lev_bb_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.37, N=108
- Validation: z=-0.43, N=188, attenuation=82%
- OOS: z=-0.86, N=181, attenuation=64%
- ROI: synthetic=+7.9%, real=+8.2%

### batting_total_bip_last_5_LOW × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.37, N=240
- Validation: z=-1.59, N=403, attenuation=33%
- OOS: z=-1.44, N=351, attenuation=39%
- ROI: synthetic=+4.4%, real=+4.5%

### opp_pl_zone_rate_season_baseline_HIGH × high_lev_bb_rate_baseline_LOW
- Direction: UNDER
- Discovery: z=-2.37, N=122
- Validation: z=-0.05, N=271, attenuation=98%
- OOS: z=-0.80, N=319, attenuation=66%
- ROI: synthetic=+2.0%, real=+1.9%

### damage_hr_rate_last_15_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.37, N=139
- Validation: z=+1.70, N=142, attenuation=28%
- OOS: z=+2.00, N=174, attenuation=16%
- ROI: synthetic=+4.1%, real=+4.1%

### contact_barrel_rate_last_10_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.37, N=126
- Validation: z=-0.11, N=270, attenuation=95%
- OOS: z=-1.11, N=248, attenuation=53%
- ROI: synthetic=+4.2%, real=+3.8%

### contact_barrel_rate_last_10_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.37, N=126
- Validation: z=-0.11, N=270, attenuation=95%
- OOS: z=-1.11, N=248, attenuation=53%
- ROI: synthetic=+4.2%, real=+3.8%

### plate_bb_rate_last_10_HIGH × opp_sp_command_bb_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.37, N=127
- Validation: z=-0.50, N=132, attenuation=79%
- OOS: z=-0.83, N=172, attenuation=65%
- ROI: synthetic=+6.4%, real=+6.4%

### damage_iso_last_10_HIGH × exit_prob_by_7_last_10_LOW
- Direction: OVER
- Discovery: z=+2.36, N=342
- Validation: z=+0.76, N=330, attenuation=68%
- OOS: z=+1.92, N=415, attenuation=19%
- ROI: synthetic=+0.2%, real=+0.3%

### damage_iso_last_20_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.36, N=127
- Validation: z=+0.11, N=151, attenuation=96%
- OOS: z=+1.44, N=155, attenuation=39%
- ROI: synthetic=-0.3%, real=-0.2%

### bullpen_pitches_last_game_HIGH × low_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.36, N=126
- Validation: z=+0.60, N=162, attenuation=75%
- OOS: z=+1.35, N=181, attenuation=43%
- ROI: synthetic=-2.0%, real=-1.9%

### damage_hr_rate_last_20_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.36, N=165
- Validation: z=+0.16, N=223, attenuation=93%
- OOS: z=+3.05, N=255, attenuation=-29%
- ROI: synthetic=+0.4%, real=+0.4%

### damage_iso_last_10_HIGH × opp_pl_two_strike_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.36, N=124
- Validation: z=+0.04, N=114, attenuation=98%
- OOS: z=+1.90, N=130, attenuation=20%
- ROI: synthetic=+4.8%, real=+4.7%

### contact_ev_last_20_LOW × opp_sp_workload_ppbf_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.36, N=137
- Validation: z=-0.11, N=302, attenuation=95%
- OOS: z=-0.85, N=201, attenuation=64%
- ROI: synthetic=+1.7%, real=+1.4%

### contact_barrel_rate_last_7_HIGH × damage_iso_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.36, N=239
- Validation: z=+0.33, N=224, attenuation=86%
- OOS: z=+1.18, N=304, attenuation=50%
- ROI: synthetic=-1.4%, real=-1.4%

### opp_sp_command_bb_rate_last_10_LOW × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.35, N=107
- Validation: z=+0.73, N=224, attenuation=69%
- OOS: z=+0.98, N=208, attenuation=58%
- ROI: synthetic=+1.2%, real=+1.0%

### contact_barrel_rate_last_20_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.35, N=196
- Validation: z=-0.28, N=293, attenuation=88%
- OOS: z=-1.40, N=152, attenuation=40%
- ROI: synthetic=+4.0%, real=+3.8%

### top_order_barrel_rate_LOW × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.35, N=223
- Validation: z=-0.89, N=199, attenuation=62%
- OOS: z=-1.53, N=260, attenuation=35%
- ROI: synthetic=+7.0%, real=+6.9%

### top_order_hard_hit_rate_HIGH × leverage_gap_k_last_5_LOW
- Direction: OVER
- Discovery: z=+2.35, N=42
- Validation: z=+0.44, N=84, attenuation=81%
- OOS: z=+1.10, N=113, attenuation=53%
- ROI: synthetic=-5.4%, real=-5.3%

### high_leverage_available_LOW × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.35, N=245
- Validation: z=+0.11, N=395, attenuation=95%
- OOS: z=+0.87, N=336, attenuation=63%
- ROI: synthetic=-2.6%, real=-2.8%

### contact_hh_rate_last_20_LOW × top_order_xwoba_contact_LOW
- Direction: UNDER
- Discovery: z=-2.35, N=236
- Validation: z=-0.06, N=201, attenuation=98%
- OOS: z=-1.37, N=131, attenuation=41%
- ROI: synthetic=+5.4%, real=+5.3%

### contact_la_last_15_HIGH × damage_iso_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.34, N=196
- Validation: z=+0.54, N=215, attenuation=77%
- OOS: z=+1.95, N=288, attenuation=17%
- ROI: synthetic=+1.8%, real=+2.0%

### damage_iso_last_20_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.34, N=121
- Validation: z=-1.03, N=327, attenuation=56%
- OOS: z=-2.21, N=404, attenuation=6%
- ROI: synthetic=+6.5%, real=+6.5%

### damage_iso_last_20_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.34, N=121
- Validation: z=-1.03, N=327, attenuation=56%
- OOS: z=-2.21, N=404, attenuation=6%
- ROI: synthetic=+6.5%, real=+6.5%

### home_lu_STABLE_DEEP × contact_xslg_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.34, N=102
- Validation: z=-2.23, N=261, attenuation=5%
- OOS: z=-0.94, N=292, attenuation=60%
- ROI: synthetic=+7.2%, real=+7.2%

### contact_ev_last_15_LOW × batting_barrel_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.34, N=237
- Validation: z=-0.23, N=477, attenuation=90%
- OOS: z=-1.83, N=268, attenuation=22%
- ROI: synthetic=+2.5%, real=+2.4%

### opp_pl_primary_mix_drift_last_3_HIGH × opp_pl_secondary_2strike_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.34, N=65
- Validation: z=+0.92, N=127, attenuation=60%
- OOS: z=+1.41, N=99, attenuation=40%
- ROI: synthetic=+3.2%, real=+3.3%

### opp_pl_primary_mix_drift_last_3_HIGH × opp_pl_two_strike_secondary_pct_season_baseline_LOW
- Direction: OVER
- Discovery: z=+2.34, N=135
- Validation: z=+1.31, N=208, attenuation=44%
- OOS: z=+1.06, N=182, attenuation=54%
- ROI: synthetic=-0.8%, real=-0.5%

### damage_iso_last_10_HIGH × exit_prob_by_5_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.34, N=129
- Validation: z=+0.97, N=125, attenuation=58%
- OOS: z=+1.99, N=165, attenuation=15%
- ROI: synthetic=+6.1%, real=+6.4%

### opp_pl_chase_rate_last_5_LOW × opp_pl_velo_effective_mean_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.34, N=105
- Validation: z=-0.59, N=197, attenuation=75%
- OOS: z=-1.96, N=270, attenuation=16%
- ROI: synthetic=+11.7%, real=+11.8%

### opp_pl_velo_effective_mean_last_3_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.34, N=105
- Validation: z=-0.59, N=197, attenuation=75%
- OOS: z=-1.96, N=270, attenuation=16%
- ROI: synthetic=+11.7%, real=+11.8%

### damage_hr_rate_last_10_HIGH × opp_sp_contact_barrel_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.34, N=140
- Validation: z=+2.17, N=106, attenuation=7%
- OOS: z=+1.08, N=184, attenuation=54%
- ROI: synthetic=+4.2%, real=+4.2%

### opp_sp_command_bb_rate_last_5_HIGH × opp_pl_arm_angle_mean_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.33, N=117
- Validation: z=-1.18, N=155, attenuation=49%
- OOS: z=-1.51, N=252, attenuation=35%
- ROI: synthetic=+7.4%, real=+7.8%

### plate_bb_rate_last_20_LOW × bottom_order_hard_hit_rate_LOW
- Direction: UNDER
- Discovery: z=-2.33, N=149
- Validation: z=-1.24, N=275, attenuation=47%
- OOS: z=-1.40, N=215, attenuation=40%
- ROI: synthetic=+5.1%, real=+5.0%

### opp_sp_damage_hits_per_bf_last_5_HIGH × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.33, N=122
- Validation: z=-0.57, N=200, attenuation=76%
- OOS: z=-2.26, N=185, attenuation=3%
- ROI: synthetic=+8.5%, real=+8.9%

### contact_xslg_last_20_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.33, N=127
- Validation: z=-0.16, N=349, attenuation=93%
- OOS: z=-1.16, N=443, attenuation=50%
- ROI: synthetic=+3.3%, real=+3.1%

### contact_xslg_last_20_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.33, N=127
- Validation: z=-0.16, N=349, attenuation=93%
- OOS: z=-1.16, N=443, attenuation=50%
- ROI: synthetic=+3.3%, real=+3.1%

### wind_direction_HIGH × med_lev_k_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.33, N=140
- Validation: z=-0.29, N=188, attenuation=88%
- OOS: z=-0.78, N=118, attenuation=67%
- ROI: synthetic=+8.1%, real=+8.1%

### contact_xslg_last_7_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.33, N=114
- Validation: z=+0.13, N=129, attenuation=94%
- OOS: z=+1.23, N=131, attenuation=47%
- ROI: synthetic=+3.2%, real=+3.0%

### opp_pl_primary_mix_drift_last_3_HIGH × opp_pl_two_strike_secondary_pct_last_3_LOW
- Direction: OVER
- Discovery: z=+2.32, N=172
- Validation: z=+1.28, N=235, attenuation=45%
- OOS: z=+0.76, N=207, attenuation=67%
- ROI: synthetic=-0.8%, real=-0.7%

### away_st_DEEP_STABLE × contact_barrel_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.32, N=61
- Validation: z=+0.06, N=76, attenuation=97%
- OOS: z=+0.78, N=97, attenuation=66%
- ROI: synthetic=+5.5%, real=+5.9%

### damage_iso_last_7_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.32, N=137
- Validation: z=+0.28, N=154, attenuation=88%
- OOS: z=+1.23, N=202, attenuation=47%
- ROI: synthetic=-4.5%, real=-4.4%

### opp_sp_command_bb_rate_last_3_HIGH × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.32, N=157
- Validation: z=-0.89, N=247, attenuation=62%
- OOS: z=-1.93, N=244, attenuation=17%
- ROI: synthetic=+5.5%, real=+5.4%

### high_leverage_available_HIGH × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.32, N=136
- Validation: z=+0.80, N=322, attenuation=65%
- OOS: z=+0.75, N=357, attenuation=68%
- ROI: synthetic=+1.1%, real=+1.3%

### opp_sp_command_bb_rate_last_10_LOW × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.31, N=111
- Validation: z=+0.90, N=236, attenuation=61%
- OOS: z=+0.84, N=211, attenuation=64%
- ROI: synthetic=+2.0%, real=+1.8%

### opp_pl_chase_rate_last_3_LOW × opp_pl_two_strike_ff_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.31, N=106
- Validation: z=-0.90, N=162, attenuation=61%
- OOS: z=-1.32, N=226, attenuation=43%
- ROI: synthetic=+7.9%, real=+7.9%

### opp_pl_two_strike_ff_pct_last_3_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.31, N=106
- Validation: z=-0.90, N=162, attenuation=61%
- OOS: z=-1.32, N=226, attenuation=43%
- ROI: synthetic=+7.9%, real=+7.9%

### relievers_used_last_game_HIGH × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.31, N=186
- Validation: z=-1.64, N=296, attenuation=29%
- OOS: z=-0.85, N=280, attenuation=63%
- ROI: synthetic=+7.2%, real=+7.0%

### high_lev_hr_rate_last_10_LOW × med_lev_k_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.31, N=136
- Validation: z=-0.34, N=119, attenuation=85%
- OOS: z=-1.84, N=108, attenuation=20%
- ROI: synthetic=+9.8%, real=+9.9%

### contact_hh_rate_last_15_LOW × opp_sp_damage_hits_per_bf_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.31, N=128
- Validation: z=-0.10, N=236, attenuation=96%
- OOS: z=-1.40, N=122, attenuation=40%
- ROI: synthetic=+8.1%, real=+8.0%

### opp_pl_sl_pct_last_3_LOW × top_order_avg_exit_velo_LOW
- Direction: UNDER
- Discovery: z=-2.31, N=112
- Validation: z=-1.05, N=130, attenuation=55%
- OOS: z=-1.18, N=139, attenuation=49%
- ROI: synthetic=+10.0%, real=+10.3%

### opp_pl_spin_ff_mean_last_3_LOW × med_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.31, N=102
- Validation: z=+0.67, N=144, attenuation=71%
- OOS: z=+1.02, N=119, attenuation=56%
- ROI: synthetic=-1.0%, real=-0.8%

### home_lu_HIGH_TURNOVER × contact_la_last_15_HIGH
- Direction: OVER
- Discovery: z=+2.31, N=83
- Validation: z=+2.01, N=138, attenuation=13%
- OOS: z=+2.89, N=101, attenuation=-25%
- ROI: synthetic=+5.9%, real=+5.9%

### exit_prob_by_6_last_5_LOW × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.30, N=191
- Validation: z=-0.02, N=304, attenuation=99%
- OOS: z=-1.61, N=255, attenuation=30%
- ROI: synthetic=+2.6%, real=+2.4%

### batting_avg_exit_velo_last_5_HIGH × low_lev_k_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.30, N=106
- Validation: z=-0.37, N=199, attenuation=84%
- OOS: z=-0.71, N=267, attenuation=69%
- ROI: synthetic=+2.9%, real=+3.4%

### damage_iso_last_20_HIGH × middle_order_xwoba_contact_HIGH
- Direction: OVER
- Discovery: z=+2.30, N=183
- Validation: z=+0.26, N=226, attenuation=89%
- OOS: z=+1.38, N=210, attenuation=40%
- ROI: synthetic=-1.7%, real=-1.6%

### damage_iso_last_20_LOW × opp_sp_command_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.30, N=139
- Validation: z=-0.91, N=330, attenuation=60%
- OOS: z=-2.34, N=433, attenuation=-2%
- ROI: synthetic=+5.8%, real=+5.8%

### opp_pl_primary_pitch_pct_last_5_LOW × top_order_avg_exit_velo_LOW
- Direction: UNDER
- Discovery: z=-2.30, N=128
- Validation: z=-0.91, N=120, attenuation=60%
- OOS: z=-0.80, N=145, attenuation=65%
- ROI: synthetic=+7.5%, real=+7.6%

### home_lu_STABLE_DEEP × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.30, N=87
- Validation: z=-3.49, N=191, attenuation=-52%
- OOS: z=-0.89, N=151, attenuation=61%
- ROI: synthetic=+12.0%, real=+12.1%

### batting_total_bip_last_3_LOW × exit_prob_by_7_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.30, N=304
- Validation: z=-0.71, N=566, attenuation=69%
- OOS: z=-1.61, N=502, attenuation=30%
- ROI: synthetic=+3.7%, real=+3.7%

### relievers_used_last_3_games_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.30, N=141
- Validation: z=+1.75, N=232, attenuation=24%
- OOS: z=+1.81, N=235, attenuation=21%
- ROI: synthetic=+2.5%, real=+2.6%

### contact_barrel_rate_last_15_HIGH × damage_hr_rate_last_15_HIGH
- Direction: OVER
- Discovery: z=+2.30, N=273
- Validation: z=+0.12, N=261, attenuation=95%
- OOS: z=+0.76, N=383, attenuation=67%
- ROI: synthetic=-4.9%, real=-4.8%

### batting_barrel_rate_last_5_LOW × lineup_quality_ev_LOW
- Direction: UNDER
- Discovery: z=-2.30, N=214
- Validation: z=-0.45, N=290, attenuation=80%
- OOS: z=-0.89, N=242, attenuation=61%
- ROI: synthetic=-0.9%, real=-0.8%

### opp_sp_workload_ip_last_3_HIGH × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.29, N=138
- Validation: z=+1.76, N=234, attenuation=23%
- OOS: z=+0.70, N=168, attenuation=69%
- ROI: synthetic=+3.4%, real=+3.5%

### contact_xslg_last_20_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.29, N=125
- Validation: z=-0.01, N=334, attenuation=100%
- OOS: z=-0.84, N=434, attenuation=63%
- ROI: synthetic=+1.9%, real=+1.7%

### contact_xslg_last_20_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.29, N=125
- Validation: z=-0.01, N=334, attenuation=100%
- OOS: z=-0.84, N=434, attenuation=63%
- ROI: synthetic=+1.9%, real=+1.7%

### contact_xslg_last_10_LOW × opp_pl_secondary_pitch_pct_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.29, N=126
- Validation: z=-0.04, N=273, attenuation=98%
- OOS: z=-0.89, N=266, attenuation=61%
- ROI: synthetic=+2.9%, real=+2.7%

### opp_sp_contact_hh_allowed_last_3_LOW × batting_barrel_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.29, N=132
- Validation: z=-0.75, N=273, attenuation=67%
- OOS: z=-1.30, N=134, attenuation=43%
- ROI: synthetic=+4.0%, real=+3.9%

### damage_iso_last_7_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.29, N=130
- Validation: z=-0.67, N=302, attenuation=71%
- OOS: z=-0.73, N=388, attenuation=68%
- ROI: synthetic=+5.5%, real=+5.5%

### opp_sp_command_zone_rate_last_3_HIGH × opp_pl_two_strike_ff_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.29, N=98
- Validation: z=-1.20, N=147, attenuation=48%
- OOS: z=-1.47, N=217, attenuation=36%
- ROI: synthetic=+10.2%, real=+10.2%

### away_bp_BALANCED_DEPTH × contact_la_last_7_LOW
- Direction: UNDER
- Discovery: z=-2.29, N=108
- Validation: z=-0.26, N=183, attenuation=89%
- OOS: z=-1.11, N=254, attenuation=51%
- ROI: synthetic=+5.0%, real=+4.9%

### contact_xslg_last_7_HIGH × opp_sp_workload_ip_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.29, N=123
- Validation: z=+0.63, N=96, attenuation=73%
- OOS: z=+1.16, N=108, attenuation=49%
- ROI: synthetic=+0.3%, real=+0.4%

### contact_hh_rate_last_15_LOW × top_order_barrel_rate_LOW
- Direction: UNDER
- Discovery: z=-2.29, N=231
- Validation: z=-0.22, N=245, attenuation=90%
- OOS: z=-1.27, N=153, attenuation=45%
- ROI: synthetic=+7.6%, real=+7.5%

### damage_hr_rate_last_15_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.28, N=116
- Validation: z=-0.57, N=288, attenuation=75%
- OOS: z=-1.38, N=355, attenuation=39%
- ROI: synthetic=+3.4%, real=+3.5%

### damage_hr_rate_last_15_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.28, N=116
- Validation: z=-0.57, N=288, attenuation=75%
- OOS: z=-1.38, N=355, attenuation=39%
- ROI: synthetic=+3.4%, real=+3.5%

### home_lu_STABLE_DEEP × opp_pl_arm_angle_mean_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.28, N=103
- Validation: z=-0.89, N=173, attenuation=61%
- OOS: z=-1.64, N=212, attenuation=28%
- ROI: synthetic=+7.0%, real=+6.9%

### contact_la_last_20_HIGH × damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.28, N=205
- Validation: z=+0.32, N=226, attenuation=86%
- OOS: z=+1.36, N=302, attenuation=41%
- ROI: synthetic=-0.6%, real=-0.3%

### batting_total_bip_last_10_LOW × low_lev_bb_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.28, N=124
- Validation: z=-0.55, N=349, attenuation=76%
- OOS: z=-1.04, N=264, attenuation=54%
- ROI: synthetic=+0.3%, real=+0.3%

### home_st_DEEP_STABLE × opp_pl_pfx_x_mean_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.28, N=51
- Validation: z=-0.65, N=68, attenuation=72%
- OOS: z=-1.06, N=58, attenuation=53%
- ROI: synthetic=+11.9%, real=+12.1%

### home_lu_HIGH_TURNOVER × contact_xwoba_last_7_HIGH
- Direction: OVER
- Discovery: z=+2.28, N=91
- Validation: z=+0.36, N=77, attenuation=84%
- OOS: z=+1.55, N=63, attenuation=32%
- ROI: synthetic=-1.2%, real=-0.8%

### contact_xwoba_last_10_HIGH × damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.28, N=257
- Validation: z=+1.02, N=248, attenuation=55%
- OOS: z=+1.33, N=283, attenuation=42%
- ROI: synthetic=-0.2%, real=+0.0%

### contact_barrel_rate_last_20_HIGH × contact_la_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.27, N=223
- Validation: z=+0.11, N=254, attenuation=95%
- OOS: z=+1.03, N=404, attenuation=55%
- ROI: synthetic=-2.8%, real=-2.6%

### batting_hard_hit_rate_last_5_LOW × lineup_quality_ev_LOW
- Direction: UNDER
- Discovery: z=-2.27, N=228
- Validation: z=-0.44, N=303, attenuation=81%
- OOS: z=-0.84, N=219, attenuation=63%
- ROI: synthetic=+2.6%, real=+2.6%

### opp_pl_edge_rate_last_3_HIGH × opp_pl_heart_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.27, N=137
- Validation: z=-0.17, N=239, attenuation=92%
- OOS: z=-1.09, N=315, attenuation=52%
- ROI: synthetic=+6.5%, real=+6.6%

### opp_sp_contact_la_allowed_last_3_LOW × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.27, N=136
- Validation: z=-0.19, N=219, attenuation=92%
- OOS: z=-1.26, N=205, attenuation=44%
- ROI: synthetic=+4.5%, real=+4.4%

### contact_hh_rate_last_15_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.27, N=212
- Validation: z=-0.60, N=333, attenuation=73%
- OOS: z=-1.44, N=163, attenuation=37%
- ROI: synthetic=+8.2%, real=+8.1%

### damage_iso_last_10_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.27, N=140
- Validation: z=+0.88, N=151, attenuation=61%
- OOS: z=+2.65, N=189, attenuation=-17%
- ROI: synthetic=+4.4%, real=+4.7%

### damage_hr_rate_last_10_HIGH × opp_sp_contact_barrel_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.27, N=135
- Validation: z=+1.96, N=125, attenuation=14%
- OOS: z=+1.02, N=191, attenuation=55%
- ROI: synthetic=+3.0%, real=+3.0%

### contact_la_last_15_HIGH × opp_sp_command_bb_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.27, N=108
- Validation: z=+0.13, N=227, attenuation=94%
- OOS: z=+0.73, N=224, attenuation=68%
- ROI: synthetic=+1.0%, real=+0.9%

### contact_xslg_last_20_HIGH × opp_sp_contact_hh_allowed_last_10_LOW
- Direction: OVER
- Discovery: z=+2.27, N=115
- Validation: z=+0.18, N=128, attenuation=92%
- OOS: z=+0.79, N=79, attenuation=65%
- ROI: synthetic=-2.4%, real=-2.5%

### contact_xwoba_last_15_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.26, N=121
- Validation: z=+0.70, N=168, attenuation=69%
- OOS: z=+1.11, N=137, attenuation=51%
- ROI: synthetic=+3.9%, real=+3.9%

### opp_sp_damage_hits_per_bf_last_10_LOW × batting_avg_exit_velo_last_10_LOW
- Direction: OVER
- Discovery: z=+2.26, N=121
- Validation: z=+0.81, N=262, attenuation=64%
- OOS: z=+1.27, N=158, attenuation=44%
- ROI: synthetic=+1.6%, real=+1.5%

### damage_iso_last_10_HIGH × opp_sp_workload_ip_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.26, N=137
- Validation: z=+0.54, N=131, attenuation=76%
- OOS: z=+0.81, N=142, attenuation=64%
- ROI: synthetic=+0.3%, real=+0.6%

### damage_iso_last_10_HIGH × opp_sp_batmiss_whiff_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.26, N=120
- Validation: z=+1.99, N=148, attenuation=12%
- OOS: z=+2.23, N=180, attenuation=2%
- ROI: synthetic=+6.4%, real=+6.8%

### lineup_depth_dropoff_ev_LOW × high_lev_hr_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.26, N=162
- Validation: z=-1.18, N=168, attenuation=48%
- OOS: z=-1.19, N=169, attenuation=48%
- ROI: synthetic=+7.4%, real=+7.5%

### home_bp_BALANCED_DEPTH × contact_la_last_15_LOW
- Direction: UNDER
- Discovery: z=-2.26, N=79
- Validation: z=-0.07, N=129, attenuation=97%
- OOS: z=-0.78, N=167, attenuation=65%
- ROI: synthetic=+2.7%, real=+2.5%

### relievers_used_last_3_games_HIGH × opp_sp_contact_ev_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.26, N=148
- Validation: z=+0.64, N=214, attenuation=72%
- OOS: z=+2.17, N=307, attenuation=4%
- ROI: synthetic=+2.1%, real=+2.3%

### damage_hr_rate_last_10_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.26, N=134
- Validation: z=+1.24, N=158, attenuation=45%
- OOS: z=+1.42, N=167, attenuation=37%
- ROI: synthetic=+2.5%, real=+2.4%

### damage_hr_rate_last_20_HIGH × opp_pl_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.26, N=134
- Validation: z=+0.61, N=108, attenuation=73%
- OOS: z=+1.83, N=150, attenuation=19%
- ROI: synthetic=+5.5%, real=+5.7%

### wind_direction_HIGH × opp_pl_heart_drift_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.26, N=108
- Validation: z=-0.09, N=155, attenuation=96%
- OOS: z=-1.22, N=179, attenuation=46%
- ROI: synthetic=+8.0%, real=+7.9%

### damage_iso_last_20_HIGH × middle_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.26, N=169
- Validation: z=+0.05, N=208, attenuation=98%
- OOS: z=+1.31, N=207, attenuation=42%
- ROI: synthetic=-5.4%, real=-5.2%

### batting_avg_exit_velo_last_10_LOW × lineup_quality_ev_HIGH
- Direction: OVER
- Discovery: z=+2.26, N=90
- Validation: z=+0.21, N=279, attenuation=91%
- OOS: z=+1.74, N=153, attenuation=23%
- ROI: synthetic=-0.8%, real=-0.5%

### contact_hh_rate_last_20_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.25, N=138
- Validation: z=-0.62, N=326, attenuation=72%
- OOS: z=-1.07, N=176, attenuation=53%
- ROI: synthetic=+6.3%, real=+6.2%

### batting_hard_hit_rate_last_1_LOW × batting_total_bip_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.25, N=150
- Validation: z=-2.07, N=338, attenuation=8%
- OOS: z=-2.08, N=247, attenuation=8%
- ROI: synthetic=+8.0%, real=+8.0%

### high_lev_hr_rate_last_5_HIGH × exit_prob_by_4_last_5_LOW
- Direction: OVER
- Discovery: z=+2.25, N=188
- Validation: z=+0.82, N=276, attenuation=63%
- OOS: z=+0.93, N=345, attenuation=59%
- ROI: synthetic=-0.5%, real=-0.3%

### wind_direction_HIGH × exit_prob_by_4_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.25, N=187
- Validation: z=-0.63, N=227, attenuation=72%
- OOS: z=-0.82, N=222, attenuation=64%
- ROI: synthetic=+4.5%, real=+4.7%

### home_st_INEFFICIENT_PITCHER × PATH_ASYMMETRY
- Direction: UNDER
- Discovery: z=-2.25, N=80
- Validation: z=-0.34, N=144, attenuation=85%
- OOS: z=-0.78, N=121, attenuation=65%
- ROI: synthetic=+7.7%, real=+7.7%

### opp_pl_heart_drift_last_5_HIGH × exit_prob_by_5_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.24, N=169
- Validation: z=-0.09, N=216, attenuation=96%
- OOS: z=-1.65, N=274, attenuation=27%
- ROI: synthetic=+10.3%, real=+10.5%

### opp_pl_heart_drift_last_5_HIGH × opp_pl_two_strike_ff_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.24, N=116
- Validation: z=-0.63, N=135, attenuation=72%
- OOS: z=-1.92, N=175, attenuation=15%
- ROI: synthetic=+6.9%, real=+7.0%

### opp_pl_heart_drift_last_3_LOW × opp_pl_heart_rate_season_baseline_HIGH
- Direction: OVER
- Discovery: z=+2.24, N=120
- Validation: z=+0.57, N=227, attenuation=74%
- OOS: z=+1.03, N=278, attenuation=54%
- ROI: synthetic=-0.4%, real=-0.7%

### contact_hh_rate_last_7_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.24, N=129
- Validation: z=-0.69, N=296, attenuation=69%
- OOS: z=-0.81, N=182, attenuation=64%
- ROI: synthetic=+7.0%, real=+6.9%

### plate_k_rate_last_15_HIGH × opp_pl_sl_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.24, N=127
- Validation: z=-0.69, N=197, attenuation=69%
- OOS: z=-1.52, N=121, attenuation=32%
- ROI: synthetic=+8.6%, real=+8.5%

### damage_hr_rate_last_10_HIGH × bottom_order_barrel_rate_HIGH
- Direction: OVER
- Discovery: z=+2.24, N=196
- Validation: z=+0.82, N=195, attenuation=63%
- OOS: z=+0.77, N=243, attenuation=66%
- ROI: synthetic=+0.0%, real=+0.1%

### home_lu_HIGH_TURNOVER × exit_prob_by_7_last_10_LOW
- Direction: OVER
- Discovery: z=+2.24, N=175
- Validation: z=+0.60, N=214, attenuation=73%
- OOS: z=+0.97, N=196, attenuation=57%
- ROI: synthetic=-2.0%, real=-1.9%

### contact_barrel_rate_last_10_LOW × bottom_order_barrel_rate_HIGH
- Direction: UNDER
- Discovery: z=-2.24, N=109
- Validation: z=-0.44, N=255, attenuation=80%
- OOS: z=-1.81, N=170, attenuation=19%
- ROI: synthetic=+7.5%, real=+7.3%

### batting_total_bip_last_3_LOW × batting_avg_exit_velo_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.24, N=169
- Validation: z=-0.36, N=375, attenuation=84%
- OOS: z=-1.60, N=278, attenuation=28%
- ROI: synthetic=+1.5%, real=+1.3%

### park_factor_runs_HIGH × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.24, N=151
- Validation: z=-0.96, N=310, attenuation=57%
- OOS: z=-2.37, N=291, attenuation=-6%
- ROI: synthetic=+5.7%, real=+5.9%

### park_factor_hr_HIGH × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.24, N=151
- Validation: z=-0.96, N=310, attenuation=57%
- OOS: z=-2.37, N=291, attenuation=-6%
- ROI: synthetic=+5.7%, real=+5.9%

### home_lu_HIGH_TURNOVER × contact_barrel_rate_last_7_HIGH
- Direction: OVER
- Discovery: z=+2.23, N=80
- Validation: z=+0.78, N=82, attenuation=65%
- OOS: z=+1.65, N=96, attenuation=26%
- ROI: synthetic=-0.7%, real=-0.2%

### batting_total_bip_last_10_LOW × opp_pl_edge_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.23, N=134
- Validation: z=-0.61, N=255, attenuation=73%
- OOS: z=-2.97, N=264, attenuation=-33%
- ROI: synthetic=+10.2%, real=+10.1%

### batting_barrel_rate_last_5_LOW × high_lev_bb_rate_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.23, N=132
- Validation: z=-1.67, N=198, attenuation=25%
- OOS: z=-1.02, N=148, attenuation=54%
- ROI: synthetic=+3.6%, real=+3.3%

### contact_hh_rate_last_20_LOW × exit_prob_by_5_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.23, N=116
- Validation: z=-0.14, N=249, attenuation=94%
- OOS: z=-1.49, N=133, attenuation=33%
- ROI: synthetic=+5.3%, real=+5.5%

### away_sp_BACK_LOADED × exit_prob_by_6_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.23, N=243
- Validation: z=-1.35, N=376, attenuation=40%
- OOS: z=-0.72, N=390, attenuation=68%
- ROI: synthetic=+5.7%, real=+6.1%

### opp_sp_workload_ppbf_last_3_LOW × bottom_order_avg_exit_velo_HIGH
- Direction: OVER
- Discovery: z=+2.23, N=142
- Validation: z=+1.24, N=283, attenuation=44%
- OOS: z=+0.87, N=268, attenuation=61%
- ROI: synthetic=+0.9%, real=+1.0%

### contact_xslg_last_10_HIGH × damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.23, N=276
- Validation: z=+0.83, N=242, attenuation=63%
- OOS: z=+1.11, N=299, attenuation=50%
- ROI: synthetic=-1.2%, real=-1.1%

### contact_hh_rate_last_7_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.23, N=188
- Validation: z=-1.52, N=281, attenuation=32%
- OOS: z=-0.77, N=153, attenuation=65%
- ROI: synthetic=+9.7%, real=+9.6%

### contact_xwoba_last_15_HIGH × opp_sp_batmiss_k_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.23, N=116
- Validation: z=+0.55, N=146, attenuation=75%
- OOS: z=+1.05, N=138, attenuation=53%
- ROI: synthetic=+0.1%, real=+0.7%

### opp_pl_heart_drift_last_3_LOW × opp_pl_two_strike_secondary_pct_last_5_LOW
- Direction: OVER
- Discovery: z=+2.23, N=122
- Validation: z=+0.06, N=213, attenuation=97%
- OOS: z=+1.03, N=157, attenuation=54%
- ROI: synthetic=-3.7%, real=-3.8%

### opp_sp_contact_ev_allowed_last_3_LOW × lineup_depth_dropoff_hh_LOW
- Direction: UNDER
- Discovery: z=-2.22, N=119
- Validation: z=-1.86, N=199, attenuation=16%
- OOS: z=-1.80, N=145, attenuation=19%
- ROI: synthetic=+13.9%, real=+13.7%

### contact_la_last_15_LOW × opp_pl_pfx_z_mean_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.22, N=124
- Validation: z=-0.17, N=157, attenuation=92%
- OOS: z=-0.82, N=196, attenuation=63%
- ROI: synthetic=+2.9%, real=+2.9%

### opp_pl_two_strike_ff_pct_last_5_LOW × low_lev_bb_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.22, N=100
- Validation: z=-0.68, N=170, attenuation=69%
- OOS: z=-0.99, N=161, attenuation=55%
- ROI: synthetic=+5.9%, real=+6.2%

### damage_iso_last_10_HIGH × opp_pl_arm_angle_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.22, N=139
- Validation: z=+0.61, N=122, attenuation=73%
- OOS: z=+1.03, N=116, attenuation=54%
- ROI: synthetic=+6.5%, real=+6.5%

### opp_sp_contact_barrel_allowed_last_10_HIGH × opp_pl_pfx_x_std_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.22, N=112
- Validation: z=+1.81, N=117, attenuation=18%
- OOS: z=+1.79, N=218, attenuation=19%
- ROI: synthetic=+3.9%, real=+3.9%

### damage_hr_rate_last_15_HIGH × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.22, N=124
- Validation: z=+0.60, N=125, attenuation=73%
- OOS: z=+1.59, N=155, attenuation=28%
- ROI: synthetic=+0.4%, real=+0.5%

### contact_la_last_15_HIGH × opp_pl_heart_rate_season_baseline_HIGH
- Direction: OVER
- Discovery: z=+2.22, N=123
- Validation: z=+0.15, N=249, attenuation=93%
- OOS: z=+1.23, N=348, attenuation=45%
- ROI: synthetic=-0.3%, real=-0.2%

### batting_total_bip_last_3_HIGH × opp_pl_pfx_z_std_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.22, N=123
- Validation: z=+1.66, N=159, attenuation=25%
- OOS: z=+0.88, N=189, attenuation=60%
- ROI: synthetic=+2.6%, real=+2.7%

### away_bp_BALANCED_DEPTH × relievers_used_last_3_games_LOW
- Direction: UNDER
- Discovery: z=-2.22, N=151
- Validation: z=-1.18, N=255, attenuation=47%
- OOS: z=-1.89, N=268, attenuation=15%
- ROI: synthetic=+7.5%, real=+7.8%

### contact_xwoba_last_20_HIGH × wind_speed_HIGH
- Direction: OVER
- Discovery: z=+2.22, N=156
- Validation: z=+0.22, N=230, attenuation=90%
- OOS: z=+0.76, N=102, attenuation=66%
- ROI: synthetic=+1.8%, real=+2.1%

### contact_barrel_rate_last_10_LOW × high_lev_bb_rate_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.21, N=98
- Validation: z=-1.22, N=164, attenuation=45%
- OOS: z=-1.72, N=157, attenuation=22%
- ROI: synthetic=+8.9%, real=+8.9%

### contact_barrel_rate_last_7_LOW × batting_hard_hit_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.21, N=222
- Validation: z=-0.22, N=450, attenuation=90%
- OOS: z=-1.26, N=223, attenuation=43%
- ROI: synthetic=+0.1%, real=-0.0%

### opp_sp_command_zone_rate_last_10_LOW × bottom_order_hard_hit_rate_HIGH
- Direction: OVER
- Discovery: z=+2.21, N=91
- Validation: z=+0.46, N=183, attenuation=79%
- OOS: z=+1.72, N=108, attenuation=22%
- ROI: synthetic=+1.3%, real=+1.0%

### contact_hh_rate_last_7_LOW × damage_hr_rate_last_20_LOW
- Direction: UNDER
- Discovery: z=-2.21, N=229
- Validation: z=-0.29, N=387, attenuation=87%
- OOS: z=-2.27, N=223, attenuation=-3%
- ROI: synthetic=+2.9%, real=+3.0%

### opp_pl_sl_pct_last_3_HIGH × middle_order_hard_hit_rate_LOW
- Direction: OVER
- Discovery: z=+2.21, N=124
- Validation: z=+0.40, N=187, attenuation=82%
- OOS: z=+1.55, N=174, attenuation=30%
- ROI: synthetic=+3.0%, real=+3.0%

### away_bp_DEPLETED_BRIDGE × opp_sp_contact_barrel_allowed_last_10_LOW
- Direction: OVER
- Discovery: z=+2.21, N=89
- Validation: z=+0.89, N=108, attenuation=60%
- OOS: z=+1.01, N=113, attenuation=54%
- ROI: synthetic=+3.4%, real=+3.4%

### contact_la_last_15_HIGH × opp_pl_velo_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.21, N=103
- Validation: z=+1.61, N=173, attenuation=27%
- OOS: z=+1.36, N=207, attenuation=38%
- ROI: synthetic=+3.9%, real=+4.2%

### contact_hh_rate_last_20_HIGH × opp_sp_batmiss_whiff_rate_last_3_LOW
- Direction: OVER
- Discovery: z=+2.21, N=123
- Validation: z=+1.15, N=147, attenuation=48%
- OOS: z=+0.95, N=349, attenuation=57%
- ROI: synthetic=-3.4%, real=-3.3%

### damage_hr_rate_last_15_HIGH × opp_sp_workload_ip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=155
- Validation: z=+0.84, N=147, attenuation=62%
- OOS: z=+1.74, N=149, attenuation=21%
- ROI: synthetic=+0.1%, real=+0.3%

### relievers_used_last_game_LOW × batting_total_bip_last_1_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=277
- Validation: z=+1.31, N=375, attenuation=41%
- OOS: z=+1.92, N=391, attenuation=13%
- ROI: synthetic=+1.1%, real=+1.0%

### home_lu_HIGH_TURNOVER × damage_iso_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=72
- Validation: z=+1.19, N=77, attenuation=46%
- OOS: z=+1.22, N=57, attenuation=45%
- ROI: synthetic=-0.1%, real=-0.1%

### damage_iso_last_15_HIGH × batting_barrel_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=269
- Validation: z=+0.58, N=255, attenuation=73%
- OOS: z=+1.29, N=346, attenuation=42%
- ROI: synthetic=-2.0%, real=-1.9%

### contact_xba_last_10_HIGH × damage_iso_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=200
- Validation: z=+1.08, N=167, attenuation=51%
- OOS: z=+2.10, N=218, attenuation=4%
- ROI: synthetic=+1.3%, real=+1.6%

### opp_sp_contact_barrel_allowed_last_3_LOW × opp_pl_pfx_z_mean_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.20, N=149
- Validation: z=-0.81, N=265, attenuation=63%
- OOS: z=-1.19, N=247, attenuation=46%
- ROI: synthetic=+4.0%, real=+4.2%

### home_lu_HIGH_TURNOVER × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=56
- Validation: z=+0.70, N=69, attenuation=68%
- OOS: z=+1.18, N=59, attenuation=46%
- ROI: synthetic=+7.5%, real=+7.5%

### damage_iso_last_15_HIGH × opp_pl_secondary_2strike_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=127
- Validation: z=+0.31, N=110, attenuation=86%
- OOS: z=+2.12, N=115, attenuation=4%
- ROI: synthetic=+3.8%, real=+4.2%

### opp_sp_contact_la_allowed_last_5_HIGH × opp_sp_workload_bf_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.20, N=109
- Validation: z=+1.16, N=163, attenuation=47%
- OOS: z=+1.42, N=130, attenuation=35%
- ROI: synthetic=+2.5%, real=+2.4%

### opp_sp_command_bb_rate_last_5_HIGH × opp_pl_pfx_x_std_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.19, N=107
- Validation: z=-0.23, N=180, attenuation=90%
- OOS: z=-1.19, N=224, attenuation=46%
- ROI: synthetic=+2.4%, real=+2.6%

### contact_xslg_last_10_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.19, N=135
- Validation: z=+0.10, N=144, attenuation=96%
- OOS: z=+0.85, N=155, attenuation=61%
- ROI: synthetic=-2.5%, real=-2.5%

### contact_ev_last_7_LOW × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.19, N=224
- Validation: z=-0.40, N=444, attenuation=82%
- OOS: z=-0.93, N=298, attenuation=58%
- ROI: synthetic=+0.9%, real=+0.7%

### damage_iso_last_15_LOW × opp_pl_heart_rate_season_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.19, N=115
- Validation: z=-0.39, N=361, attenuation=82%
- OOS: z=-0.86, N=408, attenuation=61%
- ROI: synthetic=-0.3%, real=-0.2%

### opp_sp_contact_la_allowed_last_3_HIGH × opp_pl_heart_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.19, N=117
- Validation: z=+0.16, N=211, attenuation=93%
- OOS: z=+1.72, N=215, attenuation=22%
- ROI: synthetic=-0.3%, real=-0.4%

### opp_sp_batmiss_whiff_rate_last_10_HIGH × med_lev_k_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.19, N=105
- Validation: z=-0.25, N=104, attenuation=89%
- OOS: z=-1.04, N=86, attenuation=52%
- ROI: synthetic=+8.3%, real=+7.9%

### damage_hr_rate_last_15_HIGH × opp_sp_command_bb_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.18, N=131
- Validation: z=+1.03, N=142, attenuation=53%
- OOS: z=+1.10, N=169, attenuation=50%
- ROI: synthetic=+2.8%, real=+3.0%

### damage_iso_last_20_HIGH × bottom_order_barrel_rate_HIGH
- Direction: OVER
- Discovery: z=+2.18, N=198
- Validation: z=+0.24, N=177, attenuation=89%
- OOS: z=+2.76, N=194, attenuation=-26%
- ROI: synthetic=+3.2%, real=+3.2%

### damage_hr_rate_last_10_LOW × opp_pl_heart_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.18, N=127
- Validation: z=-0.18, N=252, attenuation=92%
- OOS: z=-1.93, N=320, attenuation=11%
- ROI: synthetic=+3.5%, real=+3.6%

### damage_hr_rate_last_20_HIGH × opp_sp_contact_barrel_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.18, N=130
- Validation: z=+0.15, N=97, attenuation=93%
- OOS: z=+1.62, N=173, attenuation=26%
- ROI: synthetic=+2.5%, real=+2.6%

### plate_k_rate_last_15_HIGH × high_lev_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.18, N=76
- Validation: z=-0.33, N=104, attenuation=85%
- OOS: z=-0.86, N=134, attenuation=61%
- ROI: synthetic=+2.8%, real=+2.6%

### home_lu_STABLE_DEEP × opp_sp_contact_barrel_allowed_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.18, N=96
- Validation: z=-0.22, N=161, attenuation=90%
- OOS: z=-2.09, N=127, attenuation=4%
- ROI: synthetic=+9.5%, real=+9.6%

### contact_xslg_last_7_HIGH × wind_speed_HIGH
- Direction: OVER
- Discovery: z=+2.18, N=158
- Validation: z=+0.17, N=170, attenuation=92%
- OOS: z=+1.80, N=96, attenuation=17%
- ROI: synthetic=+1.6%, real=+1.7%

### batting_total_bip_last_5_LOW × low_lev_bb_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.18, N=132
- Validation: z=-0.60, N=326, attenuation=73%
- OOS: z=-1.04, N=250, attenuation=52%
- ROI: synthetic=+1.3%, real=+1.3%

### batting_hard_hit_rate_last_10_HIGH × high_lev_bb_rate_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.17, N=144
- Validation: z=-0.34, N=160, attenuation=84%
- OOS: z=-1.20, N=291, attenuation=45%
- ROI: synthetic=+5.6%, real=+5.9%

### damage_hr_rate_last_15_HIGH × opp_sp_contact_la_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.17, N=135
- Validation: z=+0.22, N=141, attenuation=90%
- OOS: z=+1.41, N=183, attenuation=35%
- ROI: synthetic=-0.9%, real=-0.9%

### batting_total_bip_last_10_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.17, N=127
- Validation: z=-0.66, N=266, attenuation=70%
- OOS: z=-3.18, N=291, attenuation=-46%
- ROI: synthetic=+10.9%, real=+10.7%

### batting_total_bip_last_10_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.17, N=127
- Validation: z=-0.66, N=266, attenuation=70%
- OOS: z=-3.18, N=291, attenuation=-46%
- ROI: synthetic=+10.9%, real=+10.7%

### damage_hr_rate_last_20_HIGH × bottom_order_hard_hit_rate_HIGH
- Direction: OVER
- Discovery: z=+2.17, N=178
- Validation: z=+0.64, N=208, attenuation=70%
- OOS: z=+3.66, N=257, attenuation=-69%
- ROI: synthetic=+2.7%, real=+2.7%

### opp_sp_workload_pitches_last_5_HIGH × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.17, N=204
- Validation: z=-1.74, N=221, attenuation=20%
- OOS: z=-1.47, N=190, attenuation=33%
- ROI: synthetic=+6.3%, real=+6.0%

### opp_sp_damage_hr_rate_last_3_LOW × opp_pl_pfx_z_mean_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.17, N=141
- Validation: z=-1.84, N=252, attenuation=15%
- OOS: z=-1.53, N=246, attenuation=30%
- ROI: synthetic=+7.3%, real=+7.4%

### contact_xslg_last_15_LOW × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.17, N=138
- Validation: z=+0.76, N=301, attenuation=65%
- OOS: z=+1.15, N=273, attenuation=47%
- ROI: synthetic=-0.2%, real=-0.0%

### contact_xwoba_last_20_HIGH × opp_sp_command_bb_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.17, N=123
- Validation: z=+0.19, N=139, attenuation=91%
- OOS: z=+1.05, N=123, attenuation=52%
- ROI: synthetic=+2.6%, real=+2.8%

### away_lu_STABLE_DEEP × opp_pl_sl_pct_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.17, N=100
- Validation: z=-0.18, N=183, attenuation=92%
- OOS: z=-0.78, N=109, attenuation=64%
- ROI: synthetic=+0.8%, real=+0.8%

### home_lu_STABLE_DEEP × exit_prob_by_5_baseline_LOW
- Direction: UNDER
- Discovery: z=-2.16, N=103
- Validation: z=-0.48, N=162, attenuation=78%
- OOS: z=-1.56, N=165, attenuation=28%
- ROI: synthetic=+3.2%, real=+3.0%

### damage_iso_last_20_HIGH × opp_sp_workload_ip_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.16, N=120
- Validation: z=+0.44, N=118, attenuation=80%
- OOS: z=+0.79, N=133, attenuation=63%
- ROI: synthetic=+0.6%, real=+0.9%

### contact_xslg_last_15_HIGH × wind_speed_HIGH
- Direction: OVER
- Discovery: z=+2.16, N=165
- Validation: z=+0.81, N=196, attenuation=63%
- OOS: z=+1.46, N=95, attenuation=33%
- ROI: synthetic=+3.1%, real=+3.4%

### bullpen_pitches_last_game_LOW × opp_pl_zone_rate_season_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.16, N=118
- Validation: z=-1.40, N=268, attenuation=35%
- OOS: z=-1.19, N=356, attenuation=45%
- ROI: synthetic=+5.5%, real=+5.5%

### opp_sp_contact_la_allowed_last_3_HIGH × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.16, N=137
- Validation: z=+0.62, N=213, attenuation=71%
- OOS: z=+1.90, N=266, attenuation=12%
- ROI: synthetic=-3.4%, real=-3.1%

### contact_ev_last_7_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.16, N=148
- Validation: z=-0.76, N=330, attenuation=65%
- OOS: z=-1.50, N=267, attenuation=31%
- ROI: synthetic=+5.5%, real=+5.3%

### home_lu_STABLE_DEEP × opp_sp_workload_pitches_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.15, N=91
- Validation: z=-1.42, N=104, attenuation=34%
- OOS: z=-2.25, N=85, attenuation=-4%
- ROI: synthetic=+18.3%, real=+18.1%

### damage_hr_rate_last_10_HIGH × opp_sp_contact_la_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.15, N=125
- Validation: z=+1.57, N=139, attenuation=27%
- OOS: z=+1.66, N=171, attenuation=23%
- ROI: synthetic=+4.0%, real=+4.1%

### damage_iso_last_20_LOW × opp_pl_heart_rate_season_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.15, N=122
- Validation: z=-0.17, N=332, attenuation=92%
- OOS: z=-2.08, N=378, attenuation=4%
- ROI: synthetic=+2.9%, real=+3.0%

### home_lu_STABLE_DEEP × opp_sp_damage_hr_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.15, N=109
- Validation: z=-1.73, N=202, attenuation=19%
- OOS: z=-2.81, N=178, attenuation=-31%
- ROI: synthetic=+10.5%, real=+10.6%

### opp_pl_primary_pitch_pct_last_5_HIGH × opp_pl_velo_ff_mean_last_3_LOW
- Direction: OVER
- Discovery: z=+2.15, N=100
- Validation: z=+0.86, N=171, attenuation=60%
- OOS: z=+0.73, N=115, attenuation=66%
- ROI: synthetic=-2.7%, real=-2.3%

### home_lu_HIGH_TURNOVER × low_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.15, N=86
- Validation: z=+0.14, N=85, attenuation=94%
- OOS: z=+1.38, N=87, attenuation=36%
- ROI: synthetic=+2.0%, real=+2.2%

### opp_pl_primary_pitch_pct_last_3_HIGH × opp_pl_velo_mean_last_3_LOW
- Direction: OVER
- Discovery: z=+2.15, N=75
- Validation: z=+0.21, N=102, attenuation=90%
- OOS: z=+1.15, N=82, attenuation=46%
- ROI: synthetic=-2.2%, real=-1.8%

### damage_iso_last_10_HIGH × opp_sp_batmiss_whiff_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.15, N=128
- Validation: z=+2.07, N=151, attenuation=4%
- OOS: z=+2.32, N=182, attenuation=-8%
- ROI: synthetic=+6.1%, real=+6.4%

### opp_pl_primary_mix_drift_last_5_HIGH × high_lev_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.15, N=123
- Validation: z=+1.97, N=161, attenuation=8%
- OOS: z=+0.77, N=201, attenuation=64%
- ROI: synthetic=+0.4%, real=+0.9%

### opp_sp_command_zone_rate_last_10_HIGH × leverage_gap_bb_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.15, N=48
- Validation: z=-0.51, N=72, attenuation=76%
- OOS: z=-0.92, N=134, attenuation=57%
- ROI: synthetic=+8.6%, real=+8.4%

### damage_iso_last_10_HIGH × opp_pl_zone_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.15, N=122
- Validation: z=+1.74, N=112, attenuation=19%
- OOS: z=+0.68, N=149, attenuation=68%
- ROI: synthetic=+0.7%, real=+1.0%

### opp_sp_workload_pitches_last_5_HIGH × park_factor_runs_HIGH
- Direction: UNDER
- Discovery: z=-2.15, N=129
- Validation: z=-1.38, N=150, attenuation=36%
- OOS: z=-0.88, N=131, attenuation=59%
- ROI: synthetic=+4.7%, real=+4.6%

### opp_sp_workload_pitches_last_5_HIGH × park_factor_hr_HIGH
- Direction: UNDER
- Discovery: z=-2.15, N=129
- Validation: z=-1.38, N=150, attenuation=36%
- OOS: z=-0.88, N=131, attenuation=59%
- ROI: synthetic=+4.7%, real=+4.6%

### damage_iso_last_7_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.14, N=123
- Validation: z=-0.07, N=303, attenuation=97%
- OOS: z=-1.28, N=381, attenuation=40%
- ROI: synthetic=+4.7%, real=+4.6%

### damage_iso_last_7_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.14, N=123
- Validation: z=-0.07, N=303, attenuation=97%
- OOS: z=-1.28, N=381, attenuation=40%
- ROI: synthetic=+4.7%, real=+4.6%

### opp_sp_batmiss_k_rate_last_5_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.14, N=148
- Validation: z=+0.93, N=182, attenuation=56%
- OOS: z=+2.87, N=191, attenuation=-34%
- ROI: synthetic=+6.3%, real=+6.6%

### opp_sp_batmiss_k_rate_last_3_LOW × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.14, N=137
- Validation: z=-0.24, N=242, attenuation=89%
- OOS: z=-1.41, N=253, attenuation=34%
- ROI: synthetic=+0.5%, real=+0.5%

### damage_iso_last_15_HIGH × lineup_quality_ev_HIGH
- Direction: OVER
- Discovery: z=+2.14, N=183
- Validation: z=+1.88, N=240, attenuation=12%
- OOS: z=+1.63, N=272, attenuation=24%
- ROI: synthetic=+1.2%, real=+1.3%

### opp_sp_contact_la_allowed_last_5_HIGH × leverage_gap_k_last_10_LOW
- Direction: OVER
- Discovery: z=+2.14, N=62
- Validation: z=+0.44, N=46, attenuation=79%
- OOS: z=+0.85, N=93, attenuation=60%
- ROI: synthetic=+0.8%, real=+0.9%

### home_lu_HIGH_TURNOVER × opp_sp_workload_pitches_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.14, N=74
- Validation: z=+0.22, N=79, attenuation=89%
- OOS: z=+1.77, N=53, attenuation=17%
- ROI: synthetic=+2.8%, real=+2.9%

### opp_pl_primary_pitch_pct_last_3_HIGH × opp_pl_velo_ff_mean_last_3_LOW
- Direction: OVER
- Discovery: z=+2.14, N=105
- Validation: z=+1.07, N=179, attenuation=50%
- OOS: z=+1.00, N=126, attenuation=53%
- ROI: synthetic=+0.2%, real=+0.5%

### damage_iso_last_15_HIGH × opp_pl_arm_angle_mean_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.14, N=126
- Validation: z=+1.00, N=99, attenuation=53%
- OOS: z=+0.70, N=113, attenuation=67%
- ROI: synthetic=+5.5%, real=+5.6%

### opp_sp_batmiss_whiff_rate_last_3_HIGH × low_lev_bb_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.13, N=128
- Validation: z=-0.04, N=221, attenuation=98%
- OOS: z=-1.84, N=207, attenuation=14%
- ROI: synthetic=+6.4%, real=+6.3%

### contact_ev_last_10_LOW × exit_prob_by_5_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.13, N=181
- Validation: z=-0.30, N=378, attenuation=86%
- OOS: z=-0.80, N=304, attenuation=63%
- ROI: synthetic=+6.2%, real=+6.2%

### contact_xslg_last_10_HIGH × opp_sp_workload_bf_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.13, N=130
- Validation: z=+1.56, N=103, attenuation=27%
- OOS: z=+1.07, N=91, attenuation=50%
- ROI: synthetic=+6.5%, real=+6.7%

### contact_la_last_7_LOW × opp_sp_damage_hr_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.13, N=140
- Validation: z=-0.32, N=220, attenuation=85%
- OOS: z=-1.18, N=214, attenuation=45%
- ROI: synthetic=+4.2%, real=+4.0%

### batting_avg_exit_velo_last_5_HIGH × opp_pl_velo_mean_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.13, N=121
- Validation: z=-0.84, N=153, attenuation=61%
- OOS: z=-0.71, N=273, attenuation=67%
- ROI: synthetic=+3.5%, real=+3.5%

### damage_hr_rate_last_10_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.13, N=117
- Validation: z=-0.71, N=280, attenuation=67%
- OOS: z=-1.53, N=359, attenuation=28%
- ROI: synthetic=+4.0%, real=+3.8%

### damage_hr_rate_last_10_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.13, N=117
- Validation: z=-0.71, N=280, attenuation=67%
- OOS: z=-1.53, N=359, attenuation=28%
- ROI: synthetic=+4.0%, real=+3.8%

### opp_pl_chase_rate_last_5_LOW × opp_pl_velo_effective_mean_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.13, N=107
- Validation: z=-0.29, N=199, attenuation=86%
- OOS: z=-1.23, N=278, attenuation=42%
- ROI: synthetic=+8.5%, real=+8.5%

### opp_pl_velo_effective_mean_last_5_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.13, N=107
- Validation: z=-0.29, N=199, attenuation=86%
- OOS: z=-1.23, N=278, attenuation=42%
- ROI: synthetic=+8.5%, real=+8.5%

### opp_pl_ff_pct_last_3_LOW × opp_pl_zone_rate_season_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.13, N=115
- Validation: z=-1.11, N=162, attenuation=48%
- OOS: z=-1.34, N=259, attenuation=37%
- ROI: synthetic=+7.2%, real=+7.2%

### opp_sp_workload_ip_last_10_HIGH × opp_pl_spin_sl_mean_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.13, N=59
- Validation: z=+0.91, N=100, attenuation=57%
- OOS: z=+0.91, N=65, attenuation=57%
- ROI: synthetic=-3.2%, real=-3.3%

### contact_xslg_last_20_HIGH × med_lev_k_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.13, N=123
- Validation: z=+0.06, N=118, attenuation=97%
- OOS: z=+1.59, N=154, attenuation=25%
- ROI: synthetic=+0.5%, real=+0.6%

### opp_sp_workload_bf_last_5_LOW × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.13, N=153
- Validation: z=+1.69, N=203, attenuation=21%
- OOS: z=+2.40, N=249, attenuation=-13%
- ROI: synthetic=+4.3%, real=+4.4%

### plate_k_rate_last_20_LOW × damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.13, N=162
- Validation: z=+2.26, N=170, attenuation=-6%
- OOS: z=+1.19, N=230, attenuation=44%
- ROI: synthetic=+4.2%, real=+4.4%

### damage_hr_rate_last_20_HIGH × opp_pl_pfx_x_std_last_5_LOW
- Direction: OVER
- Discovery: z=+2.12, N=134
- Validation: z=+1.62, N=109, attenuation=24%
- OOS: z=+2.62, N=137, attenuation=-23%
- ROI: synthetic=+8.9%, real=+9.3%

### home_bp_DEPLETED_BRIDGE × batting_barrel_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.12, N=83
- Validation: z=+0.19, N=148, attenuation=91%
- OOS: z=+1.36, N=185, attenuation=36%
- ROI: synthetic=-1.5%, real=-1.7%

### home_st_INEFFICIENT_PITCHER × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.12, N=126
- Validation: z=-2.42, N=216, attenuation=-14%
- OOS: z=-1.67, N=212, attenuation=21%
- ROI: synthetic=+13.1%, real=+13.2%

### opp_sp_contact_barrel_allowed_last_3_LOW × opp_pl_pfx_z_mean_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.12, N=146
- Validation: z=-0.47, N=239, attenuation=78%
- OOS: z=-0.99, N=222, attenuation=53%
- ROI: synthetic=+3.1%, real=+3.2%

### opp_sp_workload_ip_last_3_LOW × opp_pl_velo_mean_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.12, N=103
- Validation: z=-0.44, N=179, attenuation=79%
- OOS: z=-1.18, N=262, attenuation=44%
- ROI: synthetic=+5.2%, real=+5.4%

### plate_k_rate_last_15_HIGH × exit_prob_by_5_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.12, N=119
- Validation: z=-1.04, N=190, attenuation=51%
- OOS: z=-1.41, N=179, attenuation=33%
- ROI: synthetic=+8.0%, real=+8.1%

### opp_sp_contact_barrel_allowed_last_3_HIGH × middle_order_avg_exit_velo_LOW
- Direction: OVER
- Discovery: z=+2.12, N=136
- Validation: z=+1.50, N=216, attenuation=29%
- OOS: z=+1.07, N=289, attenuation=49%
- ROI: synthetic=+2.8%, real=+2.8%

### opp_sp_batmiss_k_rate_last_10_LOW × opp_pl_edge_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.12, N=109
- Validation: z=-0.57, N=203, attenuation=73%
- OOS: z=-1.35, N=308, attenuation=36%
- ROI: synthetic=+6.8%, real=+6.9%

### batting_xwoba_contact_last_3_HIGH × med_lev_k_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.12, N=113
- Validation: z=+0.65, N=185, attenuation=69%
- OOS: z=+0.66, N=205, attenuation=69%
- ROI: synthetic=-6.1%, real=-5.9%

### contact_xslg_last_10_HIGH × batting_total_bip_last_1_HIGH
- Direction: OVER
- Discovery: z=+2.12, N=142
- Validation: z=+2.14, N=167, attenuation=-1%
- OOS: z=+1.01, N=147, attenuation=52%
- ROI: synthetic=+2.6%, real=+2.6%

### home_lu_HIGH_TURNOVER × exit_prob_by_7_last_5_LOW
- Direction: OVER
- Discovery: z=+2.11, N=188
- Validation: z=+0.06, N=248, attenuation=97%
- OOS: z=+0.76, N=229, attenuation=64%
- ROI: synthetic=-3.8%, real=-3.7%

### contact_hh_rate_last_7_HIGH × opp_sp_batmiss_k_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.11, N=109
- Validation: z=+0.65, N=124, attenuation=69%
- OOS: z=+1.39, N=269, attenuation=34%
- ROI: synthetic=+3.2%, real=+3.3%

### damage_iso_last_10_HIGH × bottom_order_xwoba_contact_HIGH
- Direction: OVER
- Discovery: z=+2.11, N=179
- Validation: z=+2.33, N=218, attenuation=-10%
- OOS: z=+1.76, N=271, attenuation=17%
- ROI: synthetic=+5.2%, real=+5.4%

### batting_total_bip_last_5_LOW × opp_pl_secondary_pitch_pct_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.11, N=134
- Validation: z=-0.82, N=245, attenuation=61%
- OOS: z=-1.41, N=218, attenuation=33%
- ROI: synthetic=+8.3%, real=+8.1%

### opp_sp_contact_la_allowed_last_3_HIGH × opp_sp_workload_bf_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.11, N=102
- Validation: z=+1.98, N=163, attenuation=6%
- OOS: z=+1.93, N=127, attenuation=8%
- ROI: synthetic=+5.5%, real=+5.8%

### contact_barrel_rate_last_15_HIGH × opp_sp_contact_barrel_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.11, N=135
- Validation: z=+1.75, N=133, attenuation=17%
- OOS: z=+1.42, N=262, attenuation=33%
- ROI: synthetic=-1.0%, real=-1.0%

### opp_sp_workload_bf_last_3_HIGH × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.11, N=113
- Validation: z=+1.20, N=94, attenuation=43%
- OOS: z=+0.67, N=115, attenuation=68%
- ROI: synthetic=+1.4%, real=+1.4%

### batting_total_bip_last_3_HIGH × bottom_order_coverage_LOW
- Direction: OVER
- Discovery: z=+2.11, N=158
- Validation: z=+1.27, N=311, attenuation=40%
- OOS: z=+3.07, N=360, attenuation=-46%
- ROI: synthetic=+2.8%, real=+2.9%

### med_lev_k_rate_last_5_LOW × low_lev_k_rate_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.11, N=90
- Validation: z=+0.11, N=141, attenuation=95%
- OOS: z=+2.42, N=117, attenuation=-15%
- ROI: synthetic=+0.1%, real=+0.1%

### opp_sp_workload_bf_last_10_HIGH × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.10, N=88
- Validation: z=+1.38, N=72, attenuation=34%
- OOS: z=+0.66, N=90, attenuation=69%
- ROI: synthetic=-0.5%, real=-0.7%

### contact_hh_rate_last_20_LOW × opp_pl_velo_mean_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.10, N=124
- Validation: z=-0.49, N=274, attenuation=77%
- OOS: z=-0.89, N=148, attenuation=58%
- ROI: synthetic=+1.3%, real=+1.2%

### batting_total_bip_last_3_HIGH × low_lev_bb_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.10, N=129
- Validation: z=+0.14, N=177, attenuation=93%
- OOS: z=+4.23, N=198, attenuation=-101%
- ROI: synthetic=+5.7%, real=+5.8%

### damage_hr_rate_last_10_HIGH × med_lev_bb_rate_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.10, N=147
- Validation: z=+1.00, N=120, attenuation=52%
- OOS: z=+2.44, N=154, attenuation=-16%
- ROI: synthetic=+3.6%, real=+3.8%

### contact_barrel_rate_last_10_LOW × bottom_order_xwoba_contact_HIGH
- Direction: UNDER
- Discovery: z=-2.10, N=96
- Validation: z=-0.67, N=322, attenuation=68%
- OOS: z=-0.95, N=184, attenuation=55%
- ROI: synthetic=+3.5%, real=+3.4%

### away_sp_BACK_LOADED × exit_prob_by_7_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.10, N=324
- Validation: z=-1.00, N=521, attenuation=52%
- OOS: z=-1.14, N=483, attenuation=46%
- ROI: synthetic=+5.1%, real=+5.4%

### damage_iso_last_15_HIGH × opp_sp_damage_hits_per_bf_last_10_LOW
- Direction: OVER
- Discovery: z=+2.10, N=132
- Validation: z=+0.34, N=125, attenuation=84%
- OOS: z=+1.00, N=157, attenuation=52%
- ROI: synthetic=-2.8%, real=-2.7%

### batting_hard_hit_rate_last_3_LOW × batting_barrel_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.10, N=229
- Validation: z=-0.77, N=442, attenuation=63%
- OOS: z=-1.36, N=252, attenuation=35%
- ROI: synthetic=+1.0%, real=+0.9%

### opp_pl_heart_drift_last_3_LOW × opp_pl_velo_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.10, N=119
- Validation: z=+2.35, N=189, attenuation=-12%
- OOS: z=+2.39, N=185, attenuation=-14%
- ROI: synthetic=+4.4%, real=+4.2%

### contact_barrel_rate_last_7_LOW × deterioration_score_norm_HIGH
- Direction: UNDER
- Discovery: z=-2.10, N=107
- Validation: z=-0.38, N=198, attenuation=82%
- OOS: z=-0.75, N=136, attenuation=64%
- ROI: synthetic=+1.4%, real=+0.9%

### opp_pl_ff_pct_last_3_HIGH × opp_pl_spin_sl_mean_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.10, N=50
- Validation: z=+0.74, N=134, attenuation=65%
- OOS: z=+0.68, N=118, attenuation=68%
- ROI: synthetic=+5.6%, real=+5.8%

### damage_iso_last_10_HIGH × bottom_order_barrel_rate_HIGH
- Direction: OVER
- Discovery: z=+2.10, N=183
- Validation: z=+1.70, N=194, attenuation=19%
- OOS: z=+1.62, N=225, attenuation=23%
- ROI: synthetic=+4.2%, real=+4.3%

### bullpen_pitches_last_3_games_HIGH × opp_sp_contact_ev_allowed_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.10, N=140
- Validation: z=-0.29, N=216, attenuation=86%
- OOS: z=-2.72, N=157, attenuation=-30%
- ROI: synthetic=+11.8%, real=+11.7%

### relievers_used_last_3_games_HIGH × opp_sp_contact_hh_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.10, N=122
- Validation: z=+1.07, N=171, attenuation=49%
- OOS: z=+0.63, N=274, attenuation=70%
- ROI: synthetic=-0.5%, real=-0.2%

### damage_iso_last_20_HIGH × opp_sp_contact_hh_allowed_last_10_LOW
- Direction: OVER
- Discovery: z=+2.10, N=117
- Validation: z=+0.68, N=133, attenuation=68%
- OOS: z=+1.23, N=92, attenuation=41%
- ROI: synthetic=+0.4%, real=+0.6%

### opp_sp_contact_ev_allowed_last_3_HIGH × opp_pl_two_strike_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.09, N=111
- Validation: z=+0.03, N=157, attenuation=99%
- OOS: z=+1.93, N=221, attenuation=8%
- ROI: synthetic=+3.6%, real=+3.6%

### opp_pl_heart_rate_last_3_HIGH × opp_pl_two_strike_ff_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.09, N=117
- Validation: z=-0.80, N=138, attenuation=62%
- OOS: z=-1.68, N=207, attenuation=19%
- ROI: synthetic=+6.6%, real=+6.7%

### opp_sp_batmiss_whiff_rate_last_3_LOW × opp_pl_edge_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.09, N=96
- Validation: z=+0.43, N=141, attenuation=79%
- OOS: z=+0.82, N=96, attenuation=61%
- ROI: synthetic=+2.3%, real=+2.3%

### opp_sp_contact_la_allowed_last_10_HIGH × away_rest_days_LOW
- Direction: OVER
- Discovery: z=+2.09, N=317
- Validation: z=+0.01, N=503, attenuation=100%
- OOS: z=+0.95, N=509, attenuation=54%
- ROI: synthetic=-4.6%, real=-4.7%

### contact_ev_last_7_LOW × opp_sp_damage_hr_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.09, N=149
- Validation: z=-0.77, N=328, attenuation=63%
- OOS: z=-1.36, N=208, attenuation=35%
- ROI: synthetic=+3.4%, real=+3.2%

### contact_la_last_10_HIGH × opp_pl_pfx_x_mean_last_5_LOW
- Direction: OVER
- Discovery: z=+2.09, N=127
- Validation: z=+0.03, N=228, attenuation=99%
- OOS: z=+0.82, N=266, attenuation=61%
- ROI: synthetic=-0.8%, real=-0.7%

### away_bp_BALANCED_DEPTH × opp_pl_two_strike_secondary_pct_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.09, N=109
- Validation: z=-0.56, N=167, attenuation=73%
- OOS: z=-0.97, N=176, attenuation=54%
- ROI: synthetic=+8.5%, real=+8.5%

### contact_hh_rate_last_20_HIGH × opp_pl_velo_ff_mean_last_3_LOW
- Direction: OVER
- Discovery: z=+2.09, N=108
- Validation: z=+0.34, N=132, attenuation=84%
- OOS: z=+0.80, N=231, attenuation=62%
- ROI: synthetic=-2.4%, real=-2.5%

### opp_sp_workload_ip_last_3_HIGH × opp_pl_velo_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.09, N=130
- Validation: z=+2.19, N=184, attenuation=-5%
- OOS: z=+0.98, N=174, attenuation=53%
- ROI: synthetic=+4.2%, real=+4.1%

### opp_sp_damage_hr_rate_last_3_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.08, N=123
- Validation: z=-1.10, N=230, attenuation=47%
- OOS: z=-1.71, N=322, attenuation=18%
- ROI: synthetic=+10.9%, real=+10.8%

### opp_sp_damage_hr_rate_last_3_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.08, N=123
- Validation: z=-1.10, N=230, attenuation=47%
- OOS: z=-1.71, N=322, attenuation=18%
- ROI: synthetic=+10.9%, real=+10.8%

### contact_xslg_last_15_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.08, N=136
- Validation: z=+1.37, N=128, attenuation=34%
- OOS: z=+1.04, N=141, attenuation=50%
- ROI: synthetic=+3.3%, real=+3.3%

### opp_pl_primary_mix_drift_last_3_HIGH × opp_pl_velo_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.08, N=136
- Validation: z=+2.20, N=192, attenuation=-6%
- OOS: z=+1.14, N=213, attenuation=45%
- ROI: synthetic=-2.0%, real=-1.9%

### contact_xslg_last_7_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.08, N=174
- Validation: z=-0.45, N=367, attenuation=78%
- OOS: z=-1.17, N=297, attenuation=44%
- ROI: synthetic=+0.9%, real=+1.0%

### damage_hr_rate_last_10_HIGH × opp_sp_command_zone_rate_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.08, N=124
- Validation: z=+1.40, N=140, attenuation=33%
- OOS: z=+0.89, N=249, attenuation=57%
- ROI: synthetic=+0.3%, real=+0.5%

### contact_barrel_rate_last_7_HIGH × opp_sp_contact_la_allowed_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.08, N=135
- Validation: z=+0.36, N=161, attenuation=82%
- OOS: z=+1.01, N=259, attenuation=51%
- ROI: synthetic=-2.9%, real=-3.0%

### home_lu_STABLE_DEEP × batting_hard_hit_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.08, N=97
- Validation: z=-1.39, N=209, attenuation=33%
- OOS: z=-1.77, N=152, attenuation=15%
- ROI: synthetic=+7.7%, real=+7.6%

### batting_avg_exit_velo_last_10_HIGH × med_lev_k_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.08, N=115
- Validation: z=-1.72, N=143, attenuation=17%
- OOS: z=-1.57, N=166, attenuation=25%
- ROI: synthetic=+6.8%, real=+6.8%

### contact_barrel_rate_last_10_LOW × bullpen_pitches_last_game_LOW
- Direction: UNDER
- Discovery: z=-2.08, N=154
- Validation: z=-1.30, N=231, attenuation=38%
- OOS: z=-1.16, N=178, attenuation=44%
- ROI: synthetic=+3.9%, real=+4.0%

### contact_xwoba_last_15_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.08, N=141
- Validation: z=+1.10, N=167, attenuation=47%
- OOS: z=+1.21, N=145, attenuation=42%
- ROI: synthetic=+3.1%, real=+3.1%

### contact_xslg_last_20_HIGH × opp_pl_pfx_x_std_last_3_LOW
- Direction: OVER
- Discovery: z=+2.08, N=130
- Validation: z=+1.25, N=108, attenuation=40%
- OOS: z=+1.20, N=116, attenuation=42%
- ROI: synthetic=+8.9%, real=+9.2%

### plate_bb_rate_last_10_LOW × batting_total_bip_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.07, N=136
- Validation: z=-0.22, N=304, attenuation=89%
- OOS: z=-0.70, N=241, attenuation=66%
- ROI: synthetic=-1.6%, real=-1.4%

### contact_barrel_rate_last_10_LOW × opp_sp_contact_barrel_allowed_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.07, N=124
- Validation: z=-0.32, N=179, attenuation=85%
- OOS: z=-1.36, N=165, attenuation=35%
- ROI: synthetic=+1.6%, real=+1.5%

### contact_hh_rate_last_20_LOW × top_order_hard_hit_rate_LOW
- Direction: UNDER
- Discovery: z=-2.07, N=223
- Validation: z=-0.88, N=294, attenuation=58%
- OOS: z=-1.02, N=165, attenuation=51%
- ROI: synthetic=+7.1%, real=+7.1%

### contact_barrel_rate_last_15_HIGH × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.07, N=127
- Validation: z=+0.11, N=113, attenuation=95%
- OOS: z=+0.62, N=173, attenuation=70%
- ROI: synthetic=-5.3%, real=-5.2%

### opp_sp_command_zone_rate_last_5_HIGH × opp_sp_damage_hr_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.07, N=128
- Validation: z=-0.49, N=244, attenuation=76%
- OOS: z=-1.70, N=342, attenuation=18%
- ROI: synthetic=+9.7%, real=+9.6%

### contact_barrel_rate_last_15_HIGH × damage_iso_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.07, N=254
- Validation: z=+1.09, N=253, attenuation=47%
- OOS: z=+1.20, N=347, attenuation=42%
- ROI: synthetic=-3.7%, real=-3.8%

### opp_pl_heart_rate_last_3_HIGH × top_order_avg_exit_velo_LOW
- Direction: UNDER
- Discovery: z=-2.06, N=124
- Validation: z=-0.02, N=140, attenuation=99%
- OOS: z=-1.10, N=223, attenuation=47%
- ROI: synthetic=+4.7%, real=+4.7%

### contact_barrel_rate_last_10_HIGH × damage_hr_rate_last_15_HIGH
- Direction: OVER
- Discovery: z=+2.06, N=279
- Validation: z=+0.14, N=235, attenuation=93%
- OOS: z=+1.09, N=355, attenuation=47%
- ROI: synthetic=-1.8%, real=-1.7%

### opp_sp_damage_hr_rate_last_3_LOW × batting_hard_hit_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.06, N=130
- Validation: z=-0.12, N=202, attenuation=94%
- OOS: z=-0.76, N=296, attenuation=63%
- ROI: synthetic=+4.2%, real=+4.4%

### contact_xslg_last_20_LOW × opp_sp_batmiss_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.06, N=114
- Validation: z=-0.04, N=256, attenuation=98%
- OOS: z=-0.99, N=316, attenuation=52%
- ROI: synthetic=+3.8%, real=+3.6%

### contact_xwoba_last_10_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.06, N=128
- Validation: z=-0.02, N=271, attenuation=99%
- OOS: z=-1.67, N=401, attenuation=19%
- ROI: synthetic=+5.0%, real=+4.8%

### contact_xwoba_last_10_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.06, N=128
- Validation: z=-0.02, N=271, attenuation=99%
- OOS: z=-1.67, N=401, attenuation=19%
- ROI: synthetic=+5.0%, real=+4.8%

### damage_hr_rate_last_10_LOW × bottom_order_barrel_rate_HIGH
- Direction: UNDER
- Discovery: z=-2.06, N=109
- Validation: z=-1.65, N=356, attenuation=20%
- OOS: z=-2.28, N=292, attenuation=-11%
- ROI: synthetic=+5.6%, real=+5.6%

### opp_pl_zone_rate_season_baseline_HIGH × leverage_gap_bb_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.05, N=53
- Validation: z=-1.05, N=116, attenuation=49%
- OOS: z=-0.67, N=149, attenuation=68%
- ROI: synthetic=+7.4%, real=+7.6%

### opp_sp_contact_ev_allowed_last_3_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.05, N=135
- Validation: z=+1.12, N=179, attenuation=45%
- OOS: z=+3.73, N=295, attenuation=-82%
- ROI: synthetic=+7.2%, real=+7.4%

### opp_sp_contact_la_allowed_last_10_LOW × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.05, N=201
- Validation: z=-0.10, N=240, attenuation=95%
- OOS: z=-1.19, N=255, attenuation=42%
- ROI: synthetic=+2.9%, real=+3.0%

### damage_iso_last_20_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.05, N=138
- Validation: z=+2.12, N=131, attenuation=-4%
- OOS: z=+1.96, N=179, attenuation=4%
- ROI: synthetic=+6.8%, real=+6.8%

### opp_sp_damage_hr_rate_last_10_HIGH × middle_order_hard_hit_rate_LOW
- Direction: OVER
- Discovery: z=+2.05, N=131
- Validation: z=+0.41, N=162, attenuation=80%
- OOS: z=+1.25, N=193, attenuation=39%
- ROI: synthetic=+2.8%, real=+2.7%

### plate_bb_rate_last_10_HIGH × exit_prob_by_5_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.05, N=139
- Validation: z=-2.50, N=138, attenuation=-22%
- OOS: z=-0.85, N=200, attenuation=59%
- ROI: synthetic=+10.5%, real=+10.6%

### home_st_SHORT_LEASH_VOLATILE × damage_hr_rate_last_15_HIGH
- Direction: OVER
- Discovery: z=+2.05, N=78
- Validation: z=+0.07, N=106, attenuation=97%
- OOS: z=+1.51, N=107, attenuation=27%
- ROI: synthetic=+0.5%, real=+0.5%

### damage_hr_rate_last_15_HIGH × opp_pl_secondary_pitch_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.05, N=130
- Validation: z=+0.73, N=125, attenuation=64%
- OOS: z=+1.88, N=163, attenuation=8%
- ROI: synthetic=+2.5%, real=+2.4%

### home_lu_HIGH_TURNOVER × contact_xslg_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.05, N=74
- Validation: z=+0.81, N=66, attenuation=60%
- OOS: z=+1.06, N=36, attenuation=48%
- ROI: synthetic=+3.5%, real=+3.8%

### opp_sp_workload_ppbf_last_10_HIGH × opp_pl_velo_ff_mean_last_3_LOW
- Direction: OVER
- Discovery: z=+2.05, N=74
- Validation: z=+0.29, N=76, attenuation=86%
- OOS: z=+0.84, N=74, attenuation=59%
- ROI: synthetic=-2.8%, real=-2.7%

### damage_iso_last_15_HIGH × bottom_order_hard_hit_rate_HIGH
- Direction: OVER
- Discovery: z=+2.05, N=164
- Validation: z=+1.35, N=207, attenuation=34%
- OOS: z=+2.81, N=218, attenuation=-37%
- ROI: synthetic=+5.4%, real=+5.4%

### damage_hr_rate_last_10_LOW × lineup_coverage_overall_LOW
- Direction: UNDER
- Discovery: z=-2.05, N=234
- Validation: z=-0.36, N=473, attenuation=82%
- OOS: z=-0.94, N=515, attenuation=54%
- ROI: synthetic=+1.0%, real=+1.1%

### damage_iso_last_10_HIGH × opp_sp_contact_barrel_allowed_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=136
- Validation: z=+0.76, N=101, attenuation=63%
- OOS: z=+1.50, N=159, attenuation=26%
- ROI: synthetic=+1.3%, real=+1.3%

### contact_la_last_10_HIGH × opp_sp_contact_hh_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=132
- Validation: z=+0.13, N=173, attenuation=93%
- OOS: z=+0.73, N=272, attenuation=64%
- ROI: synthetic=-0.1%, real=+0.2%

### contact_xwoba_last_15_HIGH × opp_sp_command_bb_rate_last_10_LOW
- Direction: OVER
- Discovery: z=+2.04, N=132
- Validation: z=+0.18, N=143, attenuation=91%
- OOS: z=+0.83, N=126, attenuation=60%
- ROI: synthetic=+1.4%, real=+1.6%

### batting_total_bip_last_1_HIGH × opp_pl_velo_drift_last_3_LOW
- Direction: OVER
- Discovery: z=+2.04, N=107
- Validation: z=+0.81, N=184, attenuation=60%
- OOS: z=+2.05, N=170, attenuation=-0%
- ROI: synthetic=+2.8%, real=+2.7%

### damage_hr_rate_last_10_HIGH × opp_sp_contact_ev_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=120
- Validation: z=+0.46, N=118, attenuation=78%
- OOS: z=+1.93, N=240, attenuation=6%
- ROI: synthetic=+1.5%, real=+1.7%

### opp_sp_contact_la_allowed_last_10_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=120
- Validation: z=+1.67, N=189, attenuation=18%
- OOS: z=+4.15, N=191, attenuation=-103%
- ROI: synthetic=+11.4%, real=+11.5%

### opp_sp_batmiss_whiff_rate_last_10_LOW × bottom_order_coverage_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=228
- Validation: z=+0.91, N=334, attenuation=55%
- OOS: z=+0.89, N=348, attenuation=57%
- ROI: synthetic=-4.3%, real=-4.2%

### contact_hh_rate_last_10_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.04, N=191
- Validation: z=-1.45, N=316, attenuation=29%
- OOS: z=-1.12, N=159, attenuation=45%
- ROI: synthetic=+7.9%, real=+7.8%

### plate_bb_rate_last_20_LOW × batting_total_bip_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.04, N=128
- Validation: z=-0.24, N=325, attenuation=88%
- OOS: z=-1.92, N=205, attenuation=6%
- ROI: synthetic=+1.3%, real=+1.4%

### contact_ev_last_15_HIGH × opp_sp_batmiss_k_rate_last_3_LOW
- Direction: OVER
- Discovery: z=+2.04, N=126
- Validation: z=+0.58, N=153, attenuation=71%
- OOS: z=+1.00, N=261, attenuation=51%
- ROI: synthetic=+0.1%, real=+0.1%

### contact_hh_rate_last_7_HIGH × opp_sp_batmiss_whiff_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.04, N=122
- Validation: z=+1.43, N=163, attenuation=30%
- OOS: z=+0.64, N=309, attenuation=69%
- ROI: synthetic=+2.5%, real=+2.6%

### park_factor_runs_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=174
- Validation: z=+0.02, N=223, attenuation=99%
- OOS: z=+2.22, N=280, attenuation=-9%
- ROI: synthetic=-1.0%, real=-0.9%

### park_factor_hr_HIGH × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=174
- Validation: z=+0.02, N=223, attenuation=99%
- OOS: z=+2.22, N=280, attenuation=-9%
- ROI: synthetic=-1.0%, real=-0.9%

### opp_pl_primary_mix_drift_last_3_HIGH × opp_pl_two_strike_ff_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=155
- Validation: z=+1.28, N=231, attenuation=37%
- OOS: z=+0.89, N=225, attenuation=56%
- ROI: synthetic=-3.1%, real=-2.9%

### opp_pl_velo_std_last_5_LOW × opp_pl_zone_rate_season_baseline_HIGH
- Direction: UNDER
- Discovery: z=-2.04, N=93
- Validation: z=-1.06, N=203, attenuation=48%
- OOS: z=-1.52, N=305, attenuation=25%
- ROI: synthetic=+8.9%, real=+8.7%

### contact_xslg_last_15_HIGH × damage_iso_last_15_HIGH
- Direction: OVER
- Discovery: z=+2.04, N=278
- Validation: z=+1.19, N=248, attenuation=42%
- OOS: z=+0.92, N=249, attenuation=55%
- ROI: synthetic=-2.5%, real=-2.4%

### contact_hh_rate_last_20_LOW × lineup_depth_dropoff_ev_LOW
- Direction: UNDER
- Discovery: z=-2.03, N=208
- Validation: z=-1.01, N=312, attenuation=51%
- OOS: z=-1.69, N=162, attenuation=17%
- ROI: synthetic=+8.3%, real=+8.2%

### batting_total_bip_last_3_LOW × exit_prob_by_5_drift_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.03, N=123
- Validation: z=-0.06, N=200, attenuation=97%
- OOS: z=-0.64, N=192, attenuation=68%
- ROI: synthetic=+0.8%, real=+0.6%

### opp_sp_contact_la_allowed_last_10_LOW × opp_pl_pfx_x_std_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.03, N=133
- Validation: z=-0.72, N=197, attenuation=65%
- OOS: z=-1.01, N=179, attenuation=50%
- ROI: synthetic=+6.2%, real=+5.9%

### lineup_depth_dropoff_ev_LOW × med_lev_bb_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.03, N=133
- Validation: z=-0.01, N=231, attenuation=100%
- OOS: z=-1.53, N=209, attenuation=25%
- ROI: synthetic=+2.2%, real=+2.2%

### contact_ev_last_15_LOW × opp_sp_command_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.03, N=146
- Validation: z=-0.47, N=346, attenuation=77%
- OOS: z=-0.64, N=290, attenuation=69%
- ROI: synthetic=+6.3%, real=+6.1%

### damage_hr_rate_last_10_HIGH × lineup_quality_ev_HIGH
- Direction: OVER
- Discovery: z=+2.03, N=187
- Validation: z=+1.63, N=260, attenuation=20%
- OOS: z=+1.29, N=317, attenuation=37%
- ROI: synthetic=-0.4%, real=-0.2%

### contact_xslg_last_20_HIGH × damage_iso_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.03, N=247
- Validation: z=+1.11, N=218, attenuation=45%
- OOS: z=+1.40, N=245, attenuation=31%
- ROI: synthetic=-1.2%, real=-1.1%

### contact_la_last_20_HIGH × batting_xwoba_contact_last_10_LOW
- Direction: OVER
- Discovery: z=+2.03, N=105
- Validation: z=+1.11, N=296, attenuation=45%
- OOS: z=+0.74, N=355, attenuation=63%
- ROI: synthetic=+1.5%, real=+1.6%

### opp_sp_command_zone_rate_last_3_LOW × exit_prob_by_5_drift_last_5_HIGH
- Direction: OVER
- Discovery: z=+2.03, N=130
- Validation: z=+0.12, N=192, attenuation=94%
- OOS: z=+1.20, N=127, attenuation=41%
- ROI: synthetic=+1.9%, real=+1.7%

### contact_ev_last_10_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.03, N=128
- Validation: z=-0.98, N=349, attenuation=52%
- OOS: z=-0.91, N=286, attenuation=55%
- ROI: synthetic=+5.5%, real=+5.5%

### contact_ev_last_10_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.03, N=128
- Validation: z=-0.98, N=349, attenuation=52%
- OOS: z=-0.91, N=286, attenuation=55%
- ROI: synthetic=+5.5%, real=+5.5%

### contact_hh_rate_last_20_LOW × opp_pl_chase_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.03, N=128
- Validation: z=-0.96, N=330, attenuation=53%
- OOS: z=-1.61, N=176, attenuation=21%
- ROI: synthetic=+7.2%, real=+7.1%

### contact_hh_rate_last_20_LOW × opp_pl_zone_rate_last_3_HIGH
- Direction: UNDER
- Discovery: z=-2.03, N=128
- Validation: z=-0.96, N=330, attenuation=53%
- OOS: z=-1.61, N=176, attenuation=21%
- ROI: synthetic=+7.2%, real=+7.1%

### opp_sp_command_bb_rate_last_3_HIGH × opp_sp_contact_hh_allowed_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.03, N=136
- Validation: z=-0.99, N=236, attenuation=51%
- OOS: z=-1.76, N=178, attenuation=13%
- ROI: synthetic=+5.1%, real=+5.0%

### opp_sp_contact_la_allowed_last_3_LOW × opp_sp_workload_pitches_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.03, N=143
- Validation: z=-1.10, N=144, attenuation=46%
- OOS: z=-1.29, N=108, attenuation=36%
- ROI: synthetic=+6.1%, real=+6.0%

### contact_hh_rate_last_15_LOW × opp_pl_chase_rate_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.02, N=125
- Validation: z=-0.21, N=308, attenuation=90%
- OOS: z=-1.73, N=196, attenuation=14%
- ROI: synthetic=+8.7%, real=+8.7%

### contact_hh_rate_last_15_LOW × opp_pl_zone_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.02, N=125
- Validation: z=-0.21, N=308, attenuation=90%
- OOS: z=-1.73, N=196, attenuation=14%
- ROI: synthetic=+8.7%, real=+8.7%

### opp_sp_contact_la_allowed_last_10_HIGH × opp_sp_workload_bf_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.02, N=90
- Validation: z=+2.06, N=153, attenuation=-2%
- OOS: z=+1.13, N=121, attenuation=44%
- ROI: synthetic=+6.2%, real=+6.2%

### opp_sp_damage_hr_rate_last_10_HIGH × top_order_hard_hit_rate_HIGH
- Direction: OVER
- Discovery: z=+2.02, N=121
- Validation: z=+0.13, N=223, attenuation=94%
- OOS: z=+0.62, N=236, attenuation=70%
- ROI: synthetic=-3.7%, real=-3.5%

### plate_k_rate_last_20_HIGH × opp_sp_contact_ev_allowed_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.02, N=116
- Validation: z=+0.49, N=159, attenuation=76%
- OOS: z=+1.09, N=196, attenuation=46%
- ROI: synthetic=-3.3%, real=-3.2%

### opp_sp_workload_pitches_last_3_HIGH × opp_sp_damage_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.02, N=116
- Validation: z=+0.09, N=84, attenuation=96%
- OOS: z=+1.91, N=57, attenuation=5%
- ROI: synthetic=+3.6%, real=+3.4%

### batting_total_bip_last_5_LOW × opp_pl_sl_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.02, N=131
- Validation: z=-0.19, N=229, attenuation=91%
- OOS: z=-1.76, N=183, attenuation=13%
- ROI: synthetic=+4.3%, real=+4.5%

### contact_la_last_20_HIGH × damage_iso_last_20_HIGH
- Direction: OVER
- Discovery: z=+2.02, N=205
- Validation: z=+0.71, N=226, attenuation=65%
- OOS: z=+1.52, N=287, attenuation=25%
- ROI: synthetic=+1.4%, real=+1.6%

### opp_pl_heart_drift_last_3_HIGH × exit_prob_by_5_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.02, N=189
- Validation: z=-0.90, N=241, attenuation=55%
- OOS: z=-0.70, N=280, attenuation=65%
- ROI: synthetic=+6.4%, real=+6.6%

### away_bp_DEPLETED_BRIDGE × opp_pl_primary_pitch_pct_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.02, N=100
- Validation: z=+0.50, N=146, attenuation=75%
- OOS: z=+0.76, N=120, attenuation=62%
- ROI: synthetic=-1.8%, real=-1.8%

### opp_sp_workload_bf_last_5_HIGH × opp_sp_damage_hr_rate_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.02, N=143
- Validation: z=-0.69, N=190, attenuation=66%
- OOS: z=-0.73, N=164, attenuation=64%
- ROI: synthetic=+3.3%, real=+3.1%

### contact_barrel_rate_last_20_HIGH × opp_pl_primary_mix_drift_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.01, N=125
- Validation: z=+0.72, N=144, attenuation=64%
- OOS: z=+0.83, N=254, attenuation=59%
- ROI: synthetic=-4.0%, real=-3.8%

### batting_avg_exit_velo_last_3_LOW × batting_total_bip_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.01, N=153
- Validation: z=-0.61, N=356, attenuation=70%
- OOS: z=-1.35, N=269, attenuation=33%
- ROI: synthetic=+1.2%, real=+1.0%

### opp_sp_command_zone_rate_last_3_HIGH × opp_pl_ff_pct_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.01, N=106
- Validation: z=-1.91, N=166, attenuation=5%
- OOS: z=-1.16, N=244, attenuation=43%
- ROI: synthetic=+8.3%, real=+8.3%

### opp_sp_workload_pitches_last_5_HIGH × exit_prob_by_7_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.01, N=259
- Validation: z=-1.45, N=283, attenuation=28%
- OOS: z=-0.99, N=242, attenuation=51%
- ROI: synthetic=+4.7%, real=+4.6%

### opp_sp_workload_pitches_last_3_LOW × batting_total_bip_last_3_HIGH
- Direction: OVER
- Discovery: z=+2.01, N=150
- Validation: z=+1.79, N=230, attenuation=11%
- OOS: z=+2.01, N=276, attenuation=0%
- ROI: synthetic=+5.7%, real=+5.8%

### opp_sp_contact_barrel_allowed_last_5_LOW × opp_pl_pfx_z_mean_last_3_LOW
- Direction: UNDER
- Discovery: z=-2.01, N=144
- Validation: z=-1.10, N=258, attenuation=45%
- OOS: z=-0.97, N=222, attenuation=52%
- ROI: synthetic=+0.0%, real=+0.2%

### damage_hr_rate_last_20_LOW × opp_sp_batmiss_k_rate_last_10_LOW
- Direction: UNDER
- Discovery: z=-2.01, N=118
- Validation: z=-0.40, N=197, attenuation=80%
- OOS: z=-2.39, N=253, attenuation=-19%
- ROI: synthetic=+6.6%, real=+6.5%

### contact_xslg_last_10_HIGH × damage_hr_rate_last_15_HIGH
- Direction: OVER
- Discovery: z=+2.01, N=261
- Validation: z=+0.82, N=225, attenuation=59%
- OOS: z=+1.14, N=263, attenuation=43%
- ROI: synthetic=-1.3%, real=-1.1%

### contact_barrel_rate_last_10_HIGH × damage_iso_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.01, N=274
- Validation: z=+1.12, N=269, attenuation=44%
- OOS: z=+1.85, N=377, attenuation=8%
- ROI: synthetic=-0.7%, real=-0.6%

### contact_la_last_15_HIGH × high_lev_hr_rate_last_10_HIGH
- Direction: OVER
- Discovery: z=+2.01, N=151
- Validation: z=+0.18, N=242, attenuation=91%
- OOS: z=+0.60, N=339, attenuation=70%
- ROI: synthetic=-2.9%, real=-2.7%

### damage_iso_last_20_LOW × top_order_avg_exit_velo_LOW
- Direction: UNDER
- Discovery: z=-2.01, N=182
- Validation: z=-0.43, N=236, attenuation=79%
- OOS: z=-1.30, N=306, attenuation=35%
- ROI: synthetic=+3.6%, real=+3.8%

### batting_total_bip_last_3_LOW × exit_prob_by_7_last_10_HIGH
- Direction: UNDER
- Discovery: z=-2.00, N=235
- Validation: z=-1.19, N=418, attenuation=41%
- OOS: z=-0.82, N=370, attenuation=59%
- ROI: synthetic=+1.8%, real=+1.9%

### contact_barrel_rate_last_10_HIGH × wind_speed_HIGH
- Direction: OVER
- Discovery: z=+2.00, N=156
- Validation: z=+0.36, N=226, attenuation=82%
- OOS: z=+1.25, N=171, attenuation=38%
- ROI: synthetic=+3.4%, real=+3.4%

### home_sp_VOLATILE × batting_avg_exit_velo_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.00, N=107
- Validation: z=-1.34, N=183, attenuation=33%
- OOS: z=-1.38, N=238, attenuation=31%
- ROI: synthetic=+5.3%, real=+5.6%

### home_lu_STABLE_DEEP × opp_pl_pfx_z_mean_last_5_LOW
- Direction: UNDER
- Discovery: z=-2.00, N=91
- Validation: z=-0.38, N=162, attenuation=81%
- OOS: z=-1.28, N=182, attenuation=36%
- ROI: synthetic=+3.4%, real=+3.7%

### opp_sp_batmiss_whiff_rate_last_5_HIGH × opp_sp_command_bb_rate_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.00, N=139
- Validation: z=-0.62, N=174, attenuation=69%
- OOS: z=-0.98, N=193, attenuation=51%
- ROI: synthetic=+6.6%, real=+6.8%

### contact_xwoba_last_10_LOW × opp_pl_two_strike_secondary_pct_last_5_HIGH
- Direction: UNDER
- Discovery: z=-2.00, N=121
- Validation: z=-0.28, N=207, attenuation=86%
- OOS: z=-0.68, N=288, attenuation=66%
- ROI: synthetic=+4.2%, real=+4.0%

### contact_hh_rate_last_20_HIGH × opp_sp_command_bb_rate_last_5_LOW
- Direction: OVER
- Discovery: z=+2.00, N=127
- Validation: z=+0.57, N=134, attenuation=71%
- OOS: z=+1.09, N=308, attenuation=45%
- ROI: synthetic=-1.9%, real=-2.1%

## Runtime
- Total: 8.4s (0.1 min)
- Credits used: 0 (local compute)
