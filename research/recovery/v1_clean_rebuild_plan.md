# V1 Clean Feature Rebuild Plan

**Date:** 2026-04-10
**Goal:** Replace all 14 contaminated V1 features with PIT-clean equivalents

---

## What Already Exists

The side engine PIT rebuild (`research/mlb_side_engine/clean_features/`) already built:
- **SP FIP (PIT):** `home_sp_fip_pit`, `away_sp_fip_pit` — FIP from pitcher_game_logs, shift(1).expanding()
- **SP ERA (PIT):** `home_sp_era_pit`, `away_sp_era_pit` — ERA from pitcher_game_logs
- **BP FIP (PIT):** `home_bp_fip_pit`, `away_bp_fip_pit` — team bullpen FIP from game logs
- **Offense RPG (PIT):** `home_offense_rpg_pit`, `away_offense_rpg_pit` — rolling 20-game RPG

All saved to: `research/mlb_side_engine/clean_features/baseball_features_pit.parquet`

---

## What Still Needs to Be Built

### 1. SP K% (PIT)
- **Source:** `pitcher_game_logs.parquet` — `strikeouts` and `batters_faced` columns
- **Formula:** `K_pct = cumulative_K / cumulative_BF` (season-to-date, shift(1))
- **Implementation:** `groupby(player_id, season).shift(1).expanding().sum()` for numerator and denominator, then divide
- **Minimum:** 3 prior starts (matches existing thin-flag convention)
- **Difficulty:** Straightforward

### 2. SP BB% (PIT)
- **Source:** `pitcher_game_logs.parquet` — `walks` and `batters_faced` columns
- **Formula:** `BB_pct = cumulative_BB / cumulative_BF` (season-to-date, shift(1))
- **Implementation:** Same pattern as K%
- **Difficulty:** Straightforward

### 3. SP avg_ip (PIT)
- **Source:** `pitcher_game_logs.parquet` — `innings_pitched` column
- **Formula:** `avg_ip = mean(prior_starts_IP)` (season-to-date, shift(1))
- **Implementation:** `groupby(player_id, season)['innings_pitched'].shift(1).expanding().mean()`
- **Minimum:** 3 prior starts
- **Difficulty:** Straightforward

### 4. wRC+ proxy (PIT)
- **Source:** Already built as `offense_rpg_pit` — rolling 20-game RPG
- **Note:** This is NOT wRC+ and should not pretend to be. It is a PIT-clean proxy for team offensive quality. The Ridge model will learn the appropriate coefficient.
- **Column name:** Rename to `home_offense_pit` / `away_offense_pit` to avoid false precision
- **Difficulty:** Already done

### 5. Bullpen delta (PIT)
- **Source:** BP FIP already built. Need to recompute `bullpen_delta = sp_fip_pit - bp_fip_pit` and `bp_delta_exposure = bullpen_delta * (9 - sp_avg_ip_pit)`
- **Difficulty:** Trivial once SP and BP FIP are merged

### 6. flyball_wind_interaction (PIT) — OPTIONAL
- **Source:** `pitcher_game_logs.parquet` has `fly_outs` and `ground_outs`
- **Proxy:** `fb_proxy = fly_outs / (fly_outs + ground_outs)` per start, then shift(1).expanding()
- **Caveat:** `fly_outs` is not identical to `fb_pct` (fly_outs includes some line drives caught as fly outs). This is a reasonable but imperfect proxy.
- **Alternative:** Drop this feature entirely. In Phase 6, flyball_wind was a marginal survivor. If the proxy is too noisy, it may not survive ablation anyway.
- **Recommendation:** Build the proxy; let ablation decide

---

## Data Availability Check

From `mlb/data/pitcher_game_logs.parquet` (84,669 rows, 2022-2026):

| Column | Available | Notes |
|--------|-----------|-------|
| `strikeouts` | Yes | For K% |
| `walks` | Yes | For BB% |
| `batters_faced` | Yes | Denominator for K%, BB% |
| `innings_pitched` | Yes | For avg_ip |
| `home_runs_allowed` | Yes | For FIP (already built) |
| `fly_outs` | Yes | For fb proxy |
| `ground_outs` | Yes | For fb proxy |
| `air_outs` | Yes | Alternative to fly_outs |
| `earned_runs` | Yes | For ERA (already built) |

From `mlb/data/hitter_game_logs.parquet` (204,548 rows, 2022-2026):

| Column | Available | Notes |
|--------|-----------|-------|
| `plate_appearances` | Yes | Not needed (using RPG from game_table) |
| `hits`, `walks`, etc. | Yes | Could build wOBA proxy if needed |

**Verdict:** All required raw data is available. No additional API calls needed.

---

## Implementation Steps

### Step 1: Extend existing build_pit_features.py
Location: `research/mlb_side_engine/clean_features/build_pit_features.py`

Add these features to the existing PIT build:
- `home_sp_k_pct_pit`, `away_sp_k_pct_pit`
- `home_sp_bb_pct_pit`, `away_sp_bb_pct_pit`
- `home_sp_avg_ip_pit`, `away_sp_avg_ip_pit`
- `home_fb_proxy_pit`, `away_fb_proxy_pit` (optional)

### Step 2: Build V1-format feature table
Create: `research/recovery/v1_clean_features/v1_feature_table_pit.parquet`

Schema must match V1 exactly (same column names as feature_table.parquet) but with PIT-clean values:
- `home_sp_xfip` -> `home_sp_fip_pit` (renamed to match V1 slot)
- `home_sp_k_pct` -> `home_sp_k_pct_pit`
- `home_sp_bb_pct` -> `home_sp_bb_pct_pit`
- `home_sp_avg_ip` -> `home_sp_avg_ip_pit`
- `home_wrc_plus` -> `home_offense_rpg_pit`
- `home_bullpen_delta` -> recomputed from PIT values
- `home_bp_delta_exposure` -> recomputed from PIT values
- `flyball_wind_interaction` -> fb_proxy * wind_factor_effective (or dropped)

### Step 3: Validate coverage
- Compare PIT fill rates to contaminated feature_table
- Expect: ~80% SP coverage (May-Oct), ~95% BP, ~96% offense
- April will have ~35-40% SP coverage (thin-sample flags)
- Early-season thin samples should be NaN, not imputed

### Step 4: Spot-check divergence
- Pick 10 random mid-season games
- Compare PIT values to contaminated values
- They MUST differ (if they match, something is wrong)
- Typical divergence: SP FIP will differ by 0.1-0.5 from season-final xFIP

---

## Feature Mapping (V1 contaminated -> V1 PIT-clean)

| V1 Contaminated Feature | PIT Replacement | Source |
|-------------------------|-----------------|--------|
| `home_sp_xfip` | `home_sp_fip_pit` | pitcher_game_logs FIP shift(1).expanding() |
| `away_sp_xfip` | `away_sp_fip_pit` | pitcher_game_logs FIP shift(1).expanding() |
| `home_sp_k_pct` | `home_sp_k_pct_pit` | K/BF shift(1).expanding() |
| `away_sp_k_pct` | `away_sp_k_pct_pit` | K/BF shift(1).expanding() |
| `home_sp_bb_pct` | `home_sp_bb_pct_pit` | BB/BF shift(1).expanding() |
| `away_sp_bb_pct` | `away_sp_bb_pct_pit` | BB/BF shift(1).expanding() |
| `home_sp_avg_ip` | `home_sp_avg_ip_pit` | IP/start shift(1).expanding() |
| `away_sp_avg_ip` | `away_sp_avg_ip_pit` | IP/start shift(1).expanding() |
| `home_wrc_plus` | `home_offense_rpg_pit` | Team RPG rolling 20, shift(1) |
| `away_wrc_plus` | `away_offense_rpg_pit` | Team RPG rolling 20, shift(1) |
| `home_bullpen_delta` | `home_bullpen_delta_pit` | sp_fip_pit - bp_fip_pit |
| `away_bullpen_delta` | `away_bullpen_delta_pit` | sp_fip_pit - bp_fip_pit |
| `home_bp_delta_exposure` | `home_bp_delta_exposure_pit` | delta_pit * (9 - avg_ip_pit) |
| `away_bp_delta_exposure` | `away_bp_delta_exposure_pit` | delta_pit * (9 - avg_ip_pit) |
| `flyball_wind_interaction` | `fb_proxy_wind_pit` or DROP | fly_outs/(fly_outs+ground_outs) * wind |

---

## Expected Differences from Contaminated Model

| Aspect | Contaminated V1 | PIT-Clean V1 |
|--------|-----------------|--------------|
| SP metric | xFIP (park/league adjusted) | FIP (raw, no league adjustment) |
| SP noise | Low (season-final = 162 games signal) | Higher (expanding mean from 3+ starts) |
| Offense metric | wRC+ (park/league adjusted, 0-1 scale centered on 100) | RPG (raw runs, 0-9 scale centered on ~4.5) |
| Coverage | ~100% (every pitcher has season-final) | ~80% mid-season, ~40% April (thin flags) |
| R-squared (in-sample) | Will be LOWER | This is expected and correct |
| Alpha (regularization) | 50 | Likely needs re-tuning (probably higher) |
| Sigma | 4.361 | Likely 4.4-4.6 (more honest noise) |

**The PIT model WILL look worse in-sample.** This is the whole point. The contaminated model's in-sample metrics were inflated by lookahead. The PIT model's metrics are honest.
