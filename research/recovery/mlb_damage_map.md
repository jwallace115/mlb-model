# MLB Damage Map — Lookahead Contamination Audit

**Date:** 2026-04-10
**Scope:** All MLB objects in the mlb-model codebase
**Root cause:** V1 Ridge model training used end-of-season FanGraphs aggregates via `sim/modules/fg_historical.py` (`season=year, ind=0` = full-season leaderboard, not point-in-time)

---

## Summary Counts

| Status | Count | Description |
|--------|-------|-------------|
| CONTAMINATED | 14 features + 2 trained models | Historical training used future data |
| CAVEATED | 5 live objects | Live inference clean, but weights/thresholds from contaminated training |
| CLEAN | 15+ objects | No contamination in any path |
| VOID | 1 research block | Already voided and rebuilt |

---

## CONTAMINATED Objects

### V1 feature_table.parquet (training data)
- **Path:** `sim/data/feature_table.parquet`
- **Source:** `sim/phase2_build_features.py` calls `sim/modules/fg_historical.py`
- **Problem:** FanGraphs API called with `season=YYYY, ind=0` returns full-season aggregates. Every game in 2022 gets the same end-of-2022 xFIP for each pitcher. This means April games see September performance — textbook lookahead.
- **Affected V1 features (14 of 25):**
  1. `home_sp_xfip` — season-final FG xFIP
  2. `away_sp_xfip` — season-final FG xFIP
  3. `home_sp_k_pct` — season-final FG K%
  4. `away_sp_k_pct` — season-final FG K%
  5. `home_sp_bb_pct` — season-final FG BB%
  6. `away_sp_bb_pct` — season-final FG BB%
  7. `home_sp_avg_ip` — season-final FG avg IP
  8. `away_sp_avg_ip` — season-final FG avg IP
  9. `home_wrc_plus` — season-final FG wRC+
  10. `away_wrc_plus` — season-final FG wRC+
  11. `home_bullpen_delta` — derived from contaminated bp_xfip
  12. `away_bullpen_delta` — derived from contaminated bp_xfip
  13. `home_bp_delta_exposure` — derived from contaminated bp_xfip
  14. `away_bp_delta_exposure` — derived from contaminated bp_xfip

### flyball_wind_interaction (V1 feature)
- **Problem:** `fb_pct` sourced from season-final FG fly ball rate
- **Not reconstructable** from pitcher_game_logs (which has `fly_outs` but not batted-ball type splits)
- **Action:** Drop this feature or attempt proxy from `fly_outs / (fly_outs + ground_outs)`

---

## CAVEATED Objects (Live Inference Clean, Historical Basis Contaminated)

### V1 Ridge Model (phase9_baseline_model.pkl)
- **Live inference:** Pulls current FG API daily — clean
- **Training weights:** Learned from contaminated features — suboptimal but not directionally wrong
- **Impact:** Model may be over-confident in pitcher quality features (xFIP gets 0.35 weight, learned from artificially clean signal)
- **Decision:** KEEP LIVE — turning off V1 is worse than running slightly suboptimal weights

### S2 Starter Path Model (starter_path_model.pkl)
- **Training features:** 9 features, 1 contaminated (`sp_xfip` from feature_table)
- **Other 8 features CLEAN:** CSW/whiff/fstrike from per-start rolling, days_rest, sp_recent_pc, opp_lineup_woba, park_factor, weather_run_modifier
- **Live inference:** Uses live Statcast metrics — clean
- **Decision:** KEEP LIVE; retrain with PIT sp_fip when available

### S12 Overlay
- **Live computation:** Uses live CSW + live xFIP — clean
- **Cutoff (8.4468):** Derived from 2024 research using season-final xFIP values
- **Risk:** Cutoff percentile may shift ~5-10% with PIT-clean data
- **Decision:** KEEP LIVE; re-derive cutoff after V1 retrain

### F5 Totals Engine
- **Consumes:** V1 `p_under` / `p_over` probabilities
- **Thresholds (0.57):** Tuned on contaminated V1 output
- **Decision:** KEEP LIVE; re-validate thresholds post-retrain

### F5 Run Line Signal
- **Live data:** Uses current FG xFIP — clean
- **Threshold (xFIP gap >= 1.0):** Not validated with PIT-clean data
- **Decision:** KEEP LIVE; re-validate threshold

---

## CLEAN Objects

| Object | Data Source | Why Clean |
|--------|------------|-----------|
| V1 Rules Mode | Live FG API daily | No trained model |
| CS013 Shadow | pitcher_game_logs + shift(1) | Per-game boxscores, strictly prior |
| CS028 Shadow | pitcher_game_logs + shift(1) | Per-game boxscores, strictly prior |
| CS004 Shadow | pitcher_game_logs + shift(1) | Per-game boxscores, strictly prior |
| KP04 Shadow | Statcast per-start + shift(1) | Thresholds from clean P75 percentiles |
| ST02 Overlay | Schedule data only | No model, no historical stats |
| ADJ Signals (v2) | Statcast per-start + shift(1).rolling() | Confirmed in build_v2.py |
| P09 per-start metrics | Statcast per-start + shift(1).rolling() | Per-start rolling |
| Combined Short Exit | pitcher_game_logs + shift(1).rolling(15) | IP from game logs |
| high_leverage_avail | Per-game boxscores + shift(1) | Properly PIT |
| park_factor_runs/hr | Static per-park config | No temporal dependency |
| temperature/wind | Per-game Open-Meteo | Actual weather |
| umpire_over_rate | Static ratings table | No temporal dependency |
| rest_days / DH flag | Per-game schedule | No temporal dependency |
| Team Totals Engine | Live MLB API + PIT-fixed PGL ERA | After PIT fix |
| Cross-market triangle | Market data only | Uses closing lines |
| TT-to-side research | Market data only | Uses TT fair values |
| Side Engine (clean rerun) | PIT features | Rebuilt clean |

---

## VOID Objects

| Object | Status | Notes |
|--------|--------|-------|
| MLB Side Engine Phases 2-4 (original) | VOIDED | Used season-final FG features; rebuilt clean; clean rerun showed NEAR MISS |

---

## Contamination Chain

```
FanGraphs API (season=YYYY, ind=0)
  +-- fg_historical.py -> fg_pitch_{year}.json / fg_offense_{year}.json
        +-- phase2_build_features.py -> feature_table.parquet
              |-- V1 Ridge training (14 features contaminated)
              |-- build_sim_inputs.py -> sim_inputs_historical (sp_xfip contaminated)
              |     +-- S2 Starter Path training (1 of 9 features contaminated)
              |-- bullpen_delta computed from bp_xfip (contaminated)
              +-- flyball_wind_interaction computed from fb_pct (contaminated)

Research derived from contaminated V1:
  |-- S12 cutoff (8.4468) from 2024 season-final xFIP research
  |-- F5 thresholds (0.57) tuned on contaminated V1 probabilities
  +-- F5 Run Line threshold (xFIP gap >= 1.0) unvalidated PIT-clean
```
