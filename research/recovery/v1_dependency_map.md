# V1 Ridge Model — Full Feature & Dependency Map

**Date:** 2026-04-10
**Model:** `sim/data/phase9_baseline_model.pkl` (Ridge, alpha=50, sigma=4.361)

---

## All 25 Features — Classification

The V1 Ridge model uses 25 features total: 18 baseline + flyball_wind + 6 bullpen features (minus 2 dropped = 25 final).

### Phase 6 Baseline (19 features)

| # | Feature | Status | Source | PIT Replacement |
|---|---------|--------|--------|-----------------|
| 1 | `home_sp_xfip` | CONTAMINATED | Season-final FG xFIP | SP FIP from pitcher_game_logs (already built) |
| 2 | `away_sp_xfip` | CONTAMINATED | Season-final FG xFIP | SP FIP from pitcher_game_logs (already built) |
| 3 | `home_sp_k_pct` | CONTAMINATED | Season-final FG K% | K/BF from pitcher_game_logs shift(1).expanding() |
| 4 | `away_sp_k_pct` | CONTAMINATED | Season-final FG K% | K/BF from pitcher_game_logs shift(1).expanding() |
| 5 | `home_sp_bb_pct` | CONTAMINATED | Season-final FG BB% | BB/BF from pitcher_game_logs shift(1).expanding() |
| 6 | `away_sp_bb_pct` | CONTAMINATED | Season-final FG BB% | BB/BF from pitcher_game_logs shift(1).expanding() |
| 7 | `home_sp_avg_ip` | CONTAMINATED | Season-final FG avg IP | IP/start from pitcher_game_logs shift(1).expanding() |
| 8 | `away_sp_avg_ip` | CONTAMINATED | Season-final FG avg IP | IP/start from pitcher_game_logs shift(1).expanding() |
| 9 | `home_wrc_plus` | CONTAMINATED | Season-final FG wRC+ | Offense RPG rolling 20 (already built) |
| 10 | `away_wrc_plus` | CONTAMINATED | Season-final FG wRC+ | Offense RPG rolling 20 (already built) |
| 11 | `park_factor_runs` | CLEAN | Static config.py | No change needed |
| 12 | `park_factor_hr` | CLEAN | Static config.py | No change needed |
| 13 | `temperature` | CLEAN | Per-game Open-Meteo | No change needed |
| 14 | `wind_factor_effective` | CLEAN | Per-game Open-Meteo | No change needed |
| 15 | `umpire_over_rate` | CLEAN | Static ratings | No change needed |
| 16 | `home_rest_days` | CLEAN | Schedule | No change needed |
| 17 | `away_rest_days` | CLEAN | Schedule | No change needed |
| 18 | `doubleheader_flag` | CLEAN | Schedule | No change needed |
| 19 | `flyball_wind_interaction` | CONTAMINATED | Season-final FG fb_pct x wind | Drop or proxy from fly_outs/(fly_outs+ground_outs) |

### Phase 8 Bullpen Features (6 added, 2 later dropped = 4 in final model)

| # | Feature | Status | Source | PIT Replacement |
|---|---------|--------|--------|-----------------|
| 20 | `home_high_leverage_avail` | CLEAN | Per-game boxscores shift(1) | No change needed |
| 21 | `away_high_leverage_avail` | CLEAN | Per-game boxscores shift(1) | No change needed |
| 22 | `home_bullpen_delta` | CONTAMINATED | bp_xfip from feature_table (season-final) | BP FIP from pitcher_game_logs (already built) |
| 23 | `away_bullpen_delta` | CONTAMINATED | bp_xfip from feature_table (season-final) | BP FIP from pitcher_game_logs (already built) |
| 24 | `home_bp_delta_exposure` | CONTAMINATED | Derived from contaminated bullpen_delta | Recompute from PIT BP FIP |
| 25 | `away_bp_delta_exposure` | CONTAMINATED | Derived from contaminated bullpen_delta | Recompute from PIT BP FIP |

**Dropped (not in final model):** `home_relievers_last1`, `away_relievers_last1`, `home_relievers_last3`, `away_relievers_last3`

---

## Contamination Score

- **14 of 25 features contaminated** (56%)
- **11 of 25 features clean** (44%)
- All contamination traces to a single source: `sim/modules/fg_historical.py`

---

## Downstream Consumers of V1 Ridge Output

### Direct consumers (read V1 probabilities or mean prediction):

| Consumer | What it reads | Impact |
|----------|--------------|--------|
| `run_model.py` (simulation mode) | `sim_project_game()` output | Primary daily card when MODEL_MODE=simulation |
| `shadow_run.py` | Ridge mean + sigma for A/B comparison | Shadow log comparison |
| F5 Totals Engine | `p_under_full`, `p_over_full` from V1 signals | F5 under/over signals |
| S12 Overlay | V1 UNDER signal (amplifies stake by 1.25x) | Stake sizing |
| P09 Overlay | V1 UNDER signal (amplifies stake by 1.25x) | Stake sizing |

### Indirect consumers (use V1-trained thresholds):

| Consumer | What it inherited | Impact |
|----------|------------------|--------|
| F5 threshold (0.57) | Tuned on V1 probabilities | Signal firing frequency |
| S12 cutoff (8.4468) | P80 of 2024 S12 values using season-final xFIP | Overlay activation rate |
| Combined Short Exit | Shadow only — no V1 dependency | None |

### NOT consumers of V1 (fully independent):

| Object | Notes |
|--------|-------|
| CS013/CS028/CS004 | Use only pitcher_game_logs |
| KP04 | Uses Statcast per-start |
| ST02 | Schedule data only |
| ADJ signals | Opponent-adjusted per-start |
| Team Totals | Live MLB API + PGL |
| F5 Run Line | Live FG xFIP (clean), gap rule |

---

## S2 Starter Path — Separate Dependency

S2 is trained on `mlb_sim/data/sim_inputs_historical_2022_2024.parquet`, which was built by `mlb_sim/data/build_sim_inputs.py`. That script reads `sp_xfip` from `feature_table.parquet` (contaminated).

**S2 feature breakdown:**
| Feature | Status | Source |
|---------|--------|--------|
| `sp_csw_pct` | CLEAN | Per-start rolling 5 from Phase A Statcast |
| `sp_whiff_pct` | CLEAN | Per-start rolling 5 from Phase A Statcast |
| `sp_fstrike_pct` | CLEAN | Per-start rolling 5 from Phase A Statcast |
| `sp_xfip` | CONTAMINATED | From feature_table via build_sim_inputs |
| `days_rest` | CLEAN | Schedule |
| `sp_recent_pc` | CLEAN | shift(1).rolling(3) from pitcher_game_logs |
| `opp_lineup_woba` | CLEAN | m3_features.parquet (lineup-confirmed) |
| `park_factor` | CLEAN | Static config |
| `weather_run_modifier` | CLEAN | Per-game Open-Meteo |

**S2 contamination: 1 of 9 features (11%)**
