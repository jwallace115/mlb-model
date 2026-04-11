#!/usr/bin/env python3
"""
Apply all 5 divergence fixes to nhl/nhl_daily_pipeline.py
Run from repo root: python3 research/recovery/nhl_feature_fix/apply_fixes.py
"""
import re

with open("nhl/nhl_daily_pipeline.py", "r") as f:
    code = f.read()

# ============================================================
# FIX D2: Prior alignment - use raw-stat league averages from 2024 canonical
# ============================================================
old_priors = '''def compute_league_priors(ft: pd.DataFrame) -> dict:
    """Extract league-average feature values for rebuild Model A shrinkage priors.
    Uses rebuild feature table if available, otherwise falls back to old feature table."""
    # Try rebuild feature table first (Model A features)
    if REBUILD_FT.exists():
        rft = pd.read_parquet(REBUILD_FT)
        oos = rft[rft["season_year"] == 2024]
    else:
        oos = ft[ft["season_year"] == 2024]

    priors = {}
    # Model A features \u2014 no MoneyPuck features
    for side in ("home", "away"):
        priors[f"{side}_goals_scored_rolling_10"]      = oos[f"{side}_goals_scored_rolling_10"].mean()
        priors[f"{side}_goals_allowed_rolling_10"]     = oos[f"{side}_goals_allowed_rolling_10"].mean()
        priors[f"{side}_shots_for_rolling_20"]         = oos[f"{side}_shots_for_rolling_20"].mean()
        priors[f"{side}_shots_against_rolling_20"]     = oos[f"{side}_shots_against_rolling_20"].mean()
        priors[f"{side}_pp_pct_rolling_20"]            = oos[f"{side}_pp_pct_rolling_20"].mean()
        priors[f"{side}_pk_pct_rolling_20"]            = oos[f"{side}_pk_pct_rolling_20"].mean()
        priors[f"{side}_pp_opp_per_game_rolling_20"]   = oos[f"{side}_pp_opp_per_game_rolling_20"].mean()
        priors[f"{side}_goalie_sv_pct_rolling_10"]     = oos[f"{side}_goalie_sv_pct_rolling_10"].mean()
        priors[f"{side}_goalie_vs_team_baseline"]      = 0.0
        priors[f"{side}_goalie_fatigue"]               = 0
        priors[f"{side}_goalie_b2b"]                   = 0
        priors[f"{side}_backup_flag"]                  = 0

    # Derived: shot pressure (= 0 when both at league avg)
    priors["home_shot_pressure"] = 0.0
    priors["away_shot_pressure"] = 0.0

    # Schedule defaults
    priors["home_days_rest"]    = 3.0
    priors["away_days_rest"]    = 3.0
    priors["home_b2b"]          = 0
    priors["away_b2b"]          = 0
    priors["home_games_last_7"] = 2.5
    priors["away_games_last_7"] = 2.5

    return priors'''

new_priors = '''def compute_league_priors(ft: pd.DataFrame) -> dict:
    """Compute raw-stat league averages from 2024 canonical season for shrinkage priors.

    FIX D2: Aligns with canonical rebuild \u2014 uses raw per-game stat averages
    (not rolling feature means) from the most recent completed season.
    Falls back to canonical CSV if available, else rebuild feature table.
    """
    priors = {}

    # Try to compute from canonical game CSV (raw stats, matches rebuild exactly)
    _canonical_csv = NHL_DIR / "nhl_games_canonical.csv"
    if _canonical_csv.exists():
        gc = pd.read_csv(_canonical_csv)
        s24 = gc[gc["season_year"] == 2024]
        if len(s24) > 100:
            # Raw per-game stat averages (both home and away perspectives pooled)
            _raw_goals = pd.concat([s24["home_score"], s24["away_score"]]).mean()
            _raw_sog = pd.concat([s24["home_shots_on_goal"], s24["away_shots_on_goal"]]).dropna().mean()

            _pp_pct_arr = []
            _pk_pct_arr = []
            for _, _r in s24.iterrows():
                for _s in ("home", "away"):
                    _opp = "away" if _s == "home" else "home"
                    _ppo = _r.get(f"{_s}_pp_opportunities")
                    _ppg = _r.get(f"{_s}_pp_goals")
                    if pd.notna(_ppo) and pd.notna(_ppg):
                        _pp_pct_arr.append(_ppg / _ppo if _ppo > 0 else 0.0)
                    _opp_ppo = _r.get(f"{_opp}_pp_opportunities")
                    _opp_ppg = _r.get(f"{_opp}_pp_goals")
                    if pd.notna(_opp_ppo) and pd.notna(_opp_ppg):
                        _pk_pct_arr.append(1.0 - _opp_ppg / _opp_ppo if _opp_ppo > 0 else 1.0)
            _raw_pp_pct = float(np.mean(_pp_pct_arr)) if _pp_pct_arr else 0.21
            _raw_pk_pct = float(np.mean(_pk_pct_arr)) if _pk_pct_arr else 0.79
            _raw_pp_opp = pd.concat([s24["home_pp_opportunities"], s24["away_pp_opportunities"]]).dropna().mean()

            _sv_arr = []
            for _, _r in s24.iterrows():
                for _s in ("home", "away"):
                    _sa = _r.get(f"{_s}_goalie_sa")
                    _ga = _r.get(f"{_s}_goalie_ga")
                    if pd.notna(_sa) and _sa > 0 and pd.notna(_ga):
                        _sv_arr.append(1.0 - _ga / _sa)
            _raw_sv = float(np.mean(_sv_arr)) if _sv_arr else 0.91

            for side in ("home", "away"):
                priors[f"{side}_goals_scored_rolling_10"]    = float(_raw_goals)
                priors[f"{side}_goals_allowed_rolling_10"]   = float(_raw_goals)
                priors[f"{side}_shots_for_rolling_20"]       = float(_raw_sog)
                priors[f"{side}_shots_against_rolling_20"]   = float(_raw_sog)
                priors[f"{side}_pp_pct_rolling_20"]          = _raw_pp_pct
                priors[f"{side}_pk_pct_rolling_20"]          = _raw_pk_pct
                priors[f"{side}_pp_opp_per_game_rolling_20"] = float(_raw_pp_opp)
                priors[f"{side}_goalie_sv_pct_rolling_10"]   = _raw_sv
                priors[f"{side}_goalie_vs_team_baseline"]    = 0.0
                priors[f"{side}_goalie_fatigue"]             = 0
                priors[f"{side}_goalie_b2b"]                 = 0
                priors[f"{side}_backup_flag"]                = 0

            priors["home_shot_pressure"] = 0.0
            priors["away_shot_pressure"] = 0.0
            priors["home_days_rest"]    = 3.0
            priors["away_days_rest"]    = 3.0
            priors["home_b2b"]          = 0
            priors["away_b2b"]          = 0
            priors["home_games_last_7"] = 2.5
            priors["away_games_last_7"] = 2.5
            return priors

    # Fallback: use rebuild feature table means (old behavior, less accurate)
    if REBUILD_FT.exists():
        rft = pd.read_parquet(REBUILD_FT)
        oos = rft[rft["season_year"] == 2024]
    else:
        oos = ft[ft["season_year"] == 2024]

    for side in ("home", "away"):
        priors[f"{side}_goals_scored_rolling_10"]      = oos[f"{side}_goals_scored_rolling_10"].mean()
        priors[f"{side}_goals_allowed_rolling_10"]     = oos[f"{side}_goals_allowed_rolling_10"].mean()
        priors[f"{side}_shots_for_rolling_20"]         = oos[f"{side}_shots_for_rolling_20"].mean()
        priors[f"{side}_shots_against_rolling_20"]     = oos[f"{side}_shots_against_rolling_20"].mean()
        priors[f"{side}_pp_pct_rolling_20"]            = oos[f"{side}_pp_pct_rolling_20"].mean()
        priors[f"{side}_pk_pct_rolling_20"]            = oos[f"{side}_pk_pct_rolling_20"].mean()
        priors[f"{side}_pp_opp_per_game_rolling_20"]   = oos[f"{side}_pp_opp_per_game_rolling_20"].mean()
        priors[f"{side}_goalie_sv_pct_rolling_10"]     = oos[f"{side}_goalie_sv_pct_rolling_10"].mean()
        priors[f"{side}_goalie_vs_team_baseline"]      = 0.0
        priors[f"{side}_goalie_fatigue"]               = 0
        priors[f"{side}_goalie_b2b"]                   = 0
        priors[f"{side}_backup_flag"]                  = 0

    priors["home_shot_pressure"] = 0.0
    priors["away_shot_pressure"] = 0.0
    priors["home_days_rest"]    = 3.0
    priors["away_days_rest"]    = 3.0
    priors["home_b2b"]          = 0
    priors["away_b2b"]          = 0
    priors["home_games_last_7"] = 2.5
    priors["away_games_last_7"] = 2.5

    return priors'''

assert old_priors in code, "Could not find old compute_league_priors function"
code = code.replace(old_priors, new_priors)
print("FIX D2: Prior alignment -- APPLIED")

# ============================================================
# FIX D3: Update function signature to accept goalie_id
# ============================================================
old_sig = '''def build_live_team_features(team: str, game_date: date,
                              live: pd.DataFrame, priors: dict,
                              side: str) -> dict:
    """
    Compute rolling features for a team entering game_date.
    Uses live season data with extended boxscore fields.
    All Model A features computed from NHL API data \u2014 no MoneyPuck fallback.
    'side' = 'home' or 'away' \u2014 used for feature naming.
    """'''

new_sig = '''def build_live_team_features(team: str, game_date: date,
                              live: pd.DataFrame, priors: dict,
                              side: str, today_goalie_id: int = None) -> dict:
    """
    Compute rolling features for a team entering game_date.
    Uses live season data with extended boxscore fields.
    All Model A features computed from NHL API data \u2014 no MoneyPuck fallback.
    'side' = 'home' or 'away' \u2014 used for feature naming.

    FIX D3/D4/D5: today_goalie_id enables goalie-specific filtering for
    save%, vs-team-baseline, and fatigue features.
    """'''

assert old_sig in code, "Could not find old function signature"
code = code.replace(old_sig, new_sig)
print("FIX D3: Function signature updated")

# ============================================================
# FIX D3/D4: Goalie SV% + vs-team-baseline — goalie-specific filtering
# ============================================================
old_goalie_sv = '''    # --- Goalie save% rolling 10 (goalie-specific, matching rebuild) ---
    # For live pipeline, we track goalie-specific stats if goalie_id available
    today_goalie_id = None  # will be set in compute_game_features
    gsv_tail = [s for s in goalie_sv_pct[-ROLLING_SHORT:] if not pd.isna(s)]
    feat[f"{side}_goalie_sv_pct_rolling_10"] = shrink(
        float(np.mean(gsv_tail)) if gsv_tail else np.nan,
        len(gsv_tail), priors[f"{side}_goalie_sv_pct_rolling_10"], ROLLING_SHORT)

    # --- Goalie vs team baseline ---
    # Simplified: use overall goalie SV% vs all goalies for the team
    if len(goalie_sv_pct) >= 3:
        all_mean = float(np.mean([s for s in goalie_sv_pct if not pd.isna(s)])) if goalie_sv_pct else 0.91
        feat[f"{side}_goalie_vs_team_baseline"] = feat[f"{side}_goalie_sv_pct_rolling_10"] - all_mean
    else:
        feat[f"{side}_goalie_vs_team_baseline"] = 0.0

    return feat'''

new_goalie_sv = '''    # --- Goalie save% rolling 10 (goalie-specific, matching rebuild) ---
    # FIX D3: Filter to today's starting goalie's games only
    if today_goalie_id is not None:
        goalie_specific_sv = [
            sv for sv, gid in zip(goalie_sv_pct, goalie_ids)
            if gid == today_goalie_id and not pd.isna(sv)
        ]
    else:
        # Fallback: use all team games (pre-fix behavior)
        goalie_specific_sv = [s for s in goalie_sv_pct if not pd.isna(s)]

    gsv_tail = goalie_specific_sv[-ROLLING_SHORT:]
    n_goalie = len(gsv_tail)
    feat[f"{side}_goalie_sv_pct_rolling_10"] = shrink(
        float(np.mean(gsv_tail)) if gsv_tail else np.nan,
        n_goalie, priors[f"{side}_goalie_sv_pct_rolling_10"], ROLLING_SHORT)

    # --- Goalie vs team baseline ---
    # FIX D4: Compare goalie-specific mean to team-wide mean (matches canonical)
    all_sv = [s for s in goalie_sv_pct if not pd.isna(s)]
    team_all_mean = float(np.mean(all_sv)) if all_sv else 0.91
    if today_goalie_id is not None:
        goalie_all_sv = [
            sv for sv, gid in zip(goalie_sv_pct, goalie_ids)
            if gid == today_goalie_id and not pd.isna(sv)
        ]
        goalie_mean = float(np.mean(goalie_all_sv)) if goalie_all_sv else np.nan
    else:
        goalie_mean = np.nan

    if pd.notna(goalie_mean) and n_goalie >= 3:
        feat[f"{side}_goalie_vs_team_baseline"] = goalie_mean - team_all_mean
    else:
        feat[f"{side}_goalie_vs_team_baseline"] = 0.0

    return feat'''

assert old_goalie_sv in code, "Could not find old goalie SV% section"
code = code.replace(old_goalie_sv, new_goalie_sv)
print("FIX D3/D4: Goalie SV% + vs-team-baseline -- APPLIED")

# ============================================================
# FIX D5: Goalie fatigue — filter by goalie-specific starts
# ============================================================
old_fatigue = '''        # Goalie fatigue: games in last 3 days (from live data)
        fatigue = 0
        if len(live) > 0:
            live_copy = live.copy()
            live_copy["game_date"] = pd.to_datetime(live_copy["game_date"]).dt.date
            three_days_ago = game_date - timedelta(days=3)
            recent = live_copy[
                ((live_copy["home_team"] == team) | (live_copy["away_team"] == team)) &
                (live_copy["game_date"] >= three_days_ago) &
                (live_copy["game_date"] < game_date)
            ]
            fatigue = len(recent)
        feat[f"{s}_goalie_fatigue"] = fatigue'''

new_fatigue = '''        # Goalie fatigue: goalie-specific starts in last 3 days (from live data)
        # FIX D5: Count only this goalie's starts, not all team games
        fatigue = 0
        _goalie_id = goalie_info.get("playerId") or goalie_info.get("goalie_id")
        if len(live) > 0 and _goalie_id is not None:
            live_copy = live.copy()
            live_copy["game_date"] = pd.to_datetime(live_copy["game_date"]).dt.date
            three_days_ago = game_date - timedelta(days=3)
            # Filter team games in window
            team_recent = live_copy[
                ((live_copy["home_team"] == team) | (live_copy["away_team"] == team)) &
                (live_copy["game_date"] >= three_days_ago) &
                (live_copy["game_date"] < game_date)
            ]
            # Count only games where THIS goalie started
            for _, _gr in team_recent.iterrows():
                _is_home = (_gr["home_team"] == team)
                _gid_col = "home_goalie_id" if _is_home else "away_goalie_id"
                if _gr.get(_gid_col) == _goalie_id:
                    fatigue += 1
        elif len(live) > 0:
            # Fallback: count team games if goalie_id unknown
            live_copy = live.copy()
            live_copy["game_date"] = pd.to_datetime(live_copy["game_date"]).dt.date
            three_days_ago = game_date - timedelta(days=3)
            recent = live_copy[
                ((live_copy["home_team"] == team) | (live_copy["away_team"] == team)) &
                (live_copy["game_date"] >= three_days_ago) &
                (live_copy["game_date"] < game_date)
            ]
            fatigue = len(recent)
        feat[f"{s}_goalie_fatigue"] = fatigue'''

assert old_fatigue in code, "Could not find old fatigue section"
code = code.replace(old_fatigue, new_fatigue)
print("FIX D5: Goalie fatigue -- APPLIED")

# ============================================================
# Update compute_game_features to pass goalie_id to build_live_team_features
# ============================================================
old_call = '''    h_feat = build_live_team_features(home, game_date, live, priors, "home")
    a_feat = build_live_team_features(away, game_date, live, priors, "away")'''

new_call = '''    # FIX D3: Pass today's starting goalie IDs for goalie-specific feature computation
    home_goalie_id = home_goalie_info.get("playerId") or home_goalie_info.get("goalie_id")
    away_goalie_id = away_goalie_info.get("playerId") or away_goalie_info.get("goalie_id")
    h_feat = build_live_team_features(home, game_date, live, priors, "home", today_goalie_id=home_goalie_id)
    a_feat = build_live_team_features(away, game_date, live, priors, "away", today_goalie_id=away_goalie_id)'''

assert old_call in code, "Could not find old compute_game_features calls"
code = code.replace(old_call, new_call)
print("FIX D3: Goalie ID passed to feature builder -- APPLIED")

# ============================================================
# Add playerId to fetch_goalies result
# ============================================================
old_goalie_result = '''            if starter:
                result[key] = {
                    "name":    starter.get("name", {}).get("default", "Unknown"),
                    "starter": True,
                    "sa":      starter.get("shotsAgainst", 0) or 0,
                    "ga":      (starter.get("shotsAgainst", 0) or 0) -
                               (starter.get("saves", 0) or 0),
                }'''

new_goalie_result = '''            if starter:
                result[key] = {
                    "name":    starter.get("name", {}).get("default", "Unknown"),
                    "starter": True,
                    "playerId": starter.get("playerId"),
                    "sa":      starter.get("shotsAgainst", 0) or 0,
                    "ga":      (starter.get("shotsAgainst", 0) or 0) -
                               (starter.get("saves", 0) or 0),
                }'''

assert old_goalie_result in code, "Could not find old goalie result dict"
code = code.replace(old_goalie_result, new_goalie_result)
print("FIX D3: playerId added to fetch_goalies -- APPLIED")

with open("nhl/nhl_daily_pipeline.py", "w") as f:
    f.write(code)

print("\nAll fixes written to nhl/nhl_daily_pipeline.py")
print(f"New file size: {len(code)} chars")
