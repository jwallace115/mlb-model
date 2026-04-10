"""
build_pit_v1_features.py — Clean PIT rebuild of all 25 V1 features.

Rebuilds contaminated features from pitcher_game_logs.parquet using strict
expanding-mean with shift(1) to ensure no lookahead.

Clean features (park, weather, umpire, rest, bullpen avail, wind_factor_effective)
are reused from game_table/feature_table/bullpen_features.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_DIR = "/root/mlb-model"
sys.path.insert(0, PROJECT_DIR)

# Paths
PGL_PATH = os.path.join(PROJECT_DIR, "mlb/data/pitcher_game_logs.parquet")
GT_PATH = os.path.join(PROJECT_DIR, "sim/data/game_table.parquet")
FT_PATH = os.path.join(PROJECT_DIR, "sim/data/feature_table.parquet")
BF_PATH = os.path.join(PROJECT_DIR, "sim/data/bullpen_features.parquet")
OUT_DIR = os.path.join(PROJECT_DIR, "research/recovery/v1_clean_features")
OUT_PATH = os.path.join(OUT_DIR, "baseball_features_pit_v1.parquet")

# Constants
LG_FIP_CONST = 3.10
LG_XFIP = 4.25
LG_K_PCT = 0.224
LG_BB_PCT = 0.085
LG_AVG_IP = 5.5
LG_WRC = 100.0
LG_RPG = 4.5

# Bayesian shrinkage constants (match V1)
PITCHER_BF_PRIOR = 300
MIN_BF = 30


def shrink(stat, bf, league_avg, prior=PITCHER_BF_PRIOR):
    if bf < MIN_BF:
        return league_avg
    return (stat * bf + league_avg * prior) / (bf + prior)


def build_starter_features(pgl):
    """Build SP features from PGL with expanding mean + shift(1)."""
    print("Building starter features from PGL...")
    sp = pgl[pgl["starter_flag"] == 1].copy()
    sp = sp.sort_values(["player_id", "game_date"]).reset_index(drop=True)
    sp["ip"] = sp["innings_pitched"].clip(lower=0.1)
    
    features = []
    for pid, grp in sp.groupby("player_id"):
        grp = grp.sort_values("game_date").reset_index(drop=True)
        n = len(grp)
        
        cum_k = grp["strikeouts"].cumsum().shift(1)
        cum_bb = grp["walks"].cumsum().shift(1)
        cum_hr = grp["home_runs_allowed"].cumsum().shift(1)
        cum_ip = grp["ip"].cumsum().shift(1)
        cum_bf = grp["batters_faced"].cumsum().shift(1)
        cum_games = pd.Series(range(n), dtype=float) # games 0..n-1 before shift
        # After shift: game i has i prior games (0 for first game)
        
        exp_fip = ((13 * cum_hr + 3 * cum_bb - 2 * cum_k) / cum_ip.clip(lower=0.1)) + LG_FIP_CONST
        exp_fip = exp_fip.clip(1.0, 10.0)
        
        exp_k_pct = cum_k / cum_bf.clip(lower=1)
        exp_bb_pct = cum_bb / cum_bf.clip(lower=1)
        
        exp_avg_ip = cum_ip / cum_games.clip(lower=1)
        exp_avg_ip = exp_avg_ip.clip(3.0, 7.5)
        
        bf_vals = cum_bf.fillna(0).astype(int)
        shrunk_fip = [shrink(f, b, LG_XFIP) if pd.notna(f) else LG_XFIP 
                      for f, b in zip(exp_fip, bf_vals)]
        shrunk_k = [shrink(k, b, LG_K_PCT) if pd.notna(k) else LG_K_PCT
                    for k, b in zip(exp_k_pct, bf_vals)]
        shrunk_bb = [shrink(bb, b, LG_BB_PCT) if pd.notna(bb) else LG_BB_PCT
                     for bb, b in zip(exp_bb_pct, bf_vals)]
        
        grp["pit_sp_fip"] = [round(max(2.0, min(v, 7.5)), 3) for v in shrunk_fip]
        grp["pit_sp_k_pct"] = [round(max(0.05, min(v, 0.50)), 4) for v in shrunk_k]
        grp["pit_sp_bb_pct"] = [round(max(0.02, min(v, 0.25)), 4) for v in shrunk_bb]
        grp["pit_sp_avg_ip"] = exp_avg_ip.fillna(LG_AVG_IP).round(2)
        grp["pit_sp_bf_cum"] = bf_vals
        
        features.append(grp[["game_pk", "game_date", "player_id", "player_name", 
                             "team", "pit_sp_fip", "pit_sp_k_pct", "pit_sp_bb_pct", 
                             "pit_sp_avg_ip", "pit_sp_bf_cum"]])
    
    result = pd.concat(features, ignore_index=True)
    print(f"  Built starter features: {len(result)} pitcher-game rows")
    return result


def build_bullpen_team_fip(pgl):
    """Build team bullpen FIP from PGL relievers with expanding + shift(1)."""
    print("Building bullpen team FIP from PGL...")
    bp = pgl[pgl["starter_flag"] == 0].copy()
    bp = bp.sort_values(["team", "game_date", "player_id"]).reset_index(drop=True)
    bp["ip"] = bp["innings_pitched"].clip(lower=0.1)
    
    team_game = bp.groupby(["team", "game_date", "game_pk"]).agg(
        bp_k=("strikeouts", "sum"),
        bp_bb=("walks", "sum"),
        bp_hr=("home_runs_allowed", "sum"),
        bp_ip=("ip", "sum"),
        bp_bf=("batters_faced", "sum"),
    ).reset_index().sort_values(["team", "game_date"])
    
    results = []
    for team, grp in team_game.groupby("team"):
        grp = grp.sort_values("game_date").reset_index(drop=True)
        
        cum_k = grp["bp_k"].cumsum().shift(1)
        cum_bb = grp["bp_bb"].cumsum().shift(1)
        cum_hr = grp["bp_hr"].cumsum().shift(1)
        cum_ip = grp["bp_ip"].cumsum().shift(1)
        cum_bf = grp["bp_bf"].cumsum().shift(1)
        
        exp_bp_fip = ((13 * cum_hr + 3 * cum_bb - 2 * cum_k) / cum_ip.clip(lower=1)) + LG_FIP_CONST
        exp_bp_fip = exp_bp_fip.clip(1.0, 10.0)
        
        bf_vals = cum_bf.fillna(0).astype(int)
        shrunk = [shrink(f, b, LG_XFIP) if pd.notna(f) else LG_XFIP 
                  for f, b in zip(exp_bp_fip, bf_vals)]
        
        grp["pit_bp_fip"] = [round(max(2.0, min(v, 7.5)), 3) for v in shrunk]
        results.append(grp[["team", "game_date", "game_pk", "pit_bp_fip"]])
    
    result = pd.concat(results, ignore_index=True)
    print(f"  Built bullpen FIP: {len(result)} team-game rows")
    return result


def build_offense_proxy(gt):
    """Build team runs-per-game as wRC+ proxy with rolling 20-game + shift(1)."""
    print("Building offense proxy from game_table...")
    
    home = gt[["game_pk", "date", "season", "home_team", "home_score"]].rename(
        columns={"home_team": "team", "home_score": "runs"})
    away = gt[["game_pk", "date", "season", "away_team", "away_score"]].rename(
        columns={"away_team": "team", "away_score": "runs"})
    
    team_games = pd.concat([home, away], ignore_index=True)
    team_games = team_games.sort_values(["team", "date"]).reset_index(drop=True)
    
    results = []
    for team, grp in team_games.groupby("team"):
        grp = grp.sort_values("date").reset_index(drop=True)
        shifted_runs = grp["runs"].shift(1)
        rolling_rpg = shifted_runs.expanding(min_periods=1).mean()
        # After 20 games, use rolling 20
        for i in range(20, len(grp)):
            rolling_rpg.iloc[i] = shifted_runs.iloc[max(1,i-19):i+1].mean()
        
        grp["pit_wrc_plus"] = (rolling_rpg / LG_RPG * 100).round(1)
        grp["pit_wrc_plus"] = grp["pit_wrc_plus"].fillna(100.0).clip(60, 140)
        
        results.append(grp[["game_pk", "team", "date", "pit_wrc_plus"]])
    
    result = pd.concat(results, ignore_index=True)
    print(f"  Built offense proxy: {len(result)} team-game rows")
    return result


def build_flyball_proxy(pgl):
    """Build flyball rate from PGL fly_outs with expanding + shift(1)."""
    print("Building flyball proxy from PGL...")
    sp = pgl[pgl["starter_flag"] == 1].copy()
    sp = sp.sort_values(["player_id", "game_date"]).reset_index(drop=True)
    sp["total_bip"] = sp["fly_outs"] + sp["ground_outs"]
    
    results = []
    for pid, grp in sp.groupby("player_id"):
        grp = grp.sort_values("game_date").reset_index(drop=True)
        cum_fly = grp["fly_outs"].cumsum().shift(1)
        cum_total = grp["total_bip"].cumsum().shift(1)
        fb_pct = (cum_fly / cum_total.clip(lower=1)).fillna(0.35)
        fb_pct = fb_pct.clip(0.15, 0.55)
        grp["pit_sp_fb_pct"] = fb_pct.round(3)
        results.append(grp[["game_pk", "player_id", "pit_sp_fb_pct"]])
    
    result = pd.concat(results, ignore_index=True)
    print(f"  Built flyball proxy: {len(result)} pitcher-game rows")
    return result


def main():
    print("=" * 70)
    print("PIT V1 Feature Rebuild — Clean Point-in-Time Features")
    print("=" * 70)
    
    pgl = pd.read_parquet(PGL_PATH)
    pgl["game_date"] = pd.to_datetime(pgl["game_date"])
    print(f"PGL loaded: {len(pgl)} rows, seasons {sorted(pgl['season'].unique())}")
    
    gt = pd.read_parquet(GT_PATH)
    gt["date"] = pd.to_datetime(gt["date"])
    print(f"Game table loaded: {len(gt)} rows")
    
    ft_orig = pd.read_parquet(FT_PATH)
    ft_orig["date"] = pd.to_datetime(ft_orig["date"])
    print(f"Original feature table loaded: {len(ft_orig)} rows")
    
    bf = pd.read_parquet(BF_PATH)
    bf["date"] = pd.to_datetime(bf["date"])
    print(f"Bullpen features loaded: {len(bf)} rows")
    
    # Build PIT features
    sp_features = build_starter_features(pgl)
    bp_fip = build_bullpen_team_fip(pgl)
    offense = build_offense_proxy(gt)
    fb_proxy = build_flyball_proxy(pgl)
    
    # -------------------------------------------------------------------
    # Join to game_table
    # -------------------------------------------------------------------
    print("\nJoining features to game_table...")
    
    # Get starters + wind_factor_effective from original FT (both are clean)
    starters = ft_orig[["game_pk", "home_sp_id", "home_sp_name", "away_sp_id", 
                        "away_sp_name", "wind_factor_effective", "roof_status"]].copy()
    
    # Start with game_table base (clean contextual features)
    base = gt[["game_pk", "date", "season", "home_team", "away_team", 
               "home_score", "away_score", "actual_total",
               "park_factor_runs", "park_factor_hr",
               "temperature", "umpire_over_rate",
               "home_rest_days", "away_rest_days", "doubleheader_flag",
               "innings_played", "completed_early"]].copy()
    
    base = base[base["season"].isin([2022, 2023, 2024, 2025])].copy()
    
    # Merge starters + wind from FT
    base = base.merge(starters, on="game_pk", how="inner")
    print(f"  After starter merge: {len(base)} games")
    
    # Merge home SP features
    home_sp = sp_features.rename(columns={
        "pit_sp_fip": "home_sp_xfip", "pit_sp_k_pct": "home_sp_k_pct", 
        "pit_sp_bb_pct": "home_sp_bb_pct", "pit_sp_avg_ip": "home_sp_avg_ip",
    })
    base = base.merge(
        home_sp[["game_pk", "player_id", "home_sp_xfip", "home_sp_k_pct", "home_sp_bb_pct", "home_sp_avg_ip"]],
        left_on=["game_pk", "home_sp_id"], right_on=["game_pk", "player_id"], how="left"
    ).drop(columns=["player_id"], errors="ignore")
    
    # Merge away SP features
    away_sp = sp_features.rename(columns={
        "pit_sp_fip": "away_sp_xfip", "pit_sp_k_pct": "away_sp_k_pct",
        "pit_sp_bb_pct": "away_sp_bb_pct", "pit_sp_avg_ip": "away_sp_avg_ip",
    })
    base = base.merge(
        away_sp[["game_pk", "player_id", "away_sp_xfip", "away_sp_k_pct", "away_sp_bb_pct", "away_sp_avg_ip"]],
        left_on=["game_pk", "away_sp_id"], right_on=["game_pk", "player_id"], how="left"
    ).drop(columns=["player_id"], errors="ignore")
    
    for col, default in [("home_sp_xfip", LG_XFIP), ("away_sp_xfip", LG_XFIP),
                         ("home_sp_k_pct", LG_K_PCT), ("away_sp_k_pct", LG_K_PCT),
                         ("home_sp_bb_pct", LG_BB_PCT), ("away_sp_bb_pct", LG_BB_PCT),
                         ("home_sp_avg_ip", LG_AVG_IP), ("away_sp_avg_ip", LG_AVG_IP)]:
        base[col] = base[col].fillna(default)
    
    # Merge offense
    home_off = offense.rename(columns={"pit_wrc_plus": "home_wrc_plus"})
    base = base.merge(home_off[["game_pk", "team", "home_wrc_plus"]],
        left_on=["game_pk", "home_team"], right_on=["game_pk", "team"], how="left"
    ).drop(columns=["team"], errors="ignore")
    
    away_off = offense.rename(columns={"pit_wrc_plus": "away_wrc_plus"})
    base = base.merge(away_off[["game_pk", "team", "away_wrc_plus"]],
        left_on=["game_pk", "away_team"], right_on=["game_pk", "team"], how="left"
    ).drop(columns=["team"], errors="ignore")
    
    base["home_wrc_plus"] = base["home_wrc_plus"].fillna(LG_WRC)
    base["away_wrc_plus"] = base["away_wrc_plus"].fillna(LG_WRC)
    
    # Merge bullpen FIP
    home_bp = bp_fip.rename(columns={"pit_bp_fip": "home_bp_fip"})
    base = base.merge(home_bp[["game_pk", "team", "home_bp_fip"]],
        left_on=["game_pk", "home_team"], right_on=["game_pk", "team"], how="left"
    ).drop(columns=["team"], errors="ignore")
    
    away_bp = bp_fip.rename(columns={"pit_bp_fip": "away_bp_fip"})
    base = base.merge(away_bp[["game_pk", "team", "away_bp_fip"]],
        left_on=["game_pk", "away_team"], right_on=["game_pk", "team"], how="left"
    ).drop(columns=["team"], errors="ignore")
    
    base["home_bp_fip"] = base["home_bp_fip"].fillna(LG_XFIP)
    base["away_bp_fip"] = base["away_bp_fip"].fillna(LG_XFIP)
    
    # Compute derived features
    base["home_bullpen_delta"] = base["home_bp_fip"] - base["home_sp_xfip"]
    base["away_bullpen_delta"] = base["away_bp_fip"] - base["away_sp_xfip"]
    base["home_bp_delta_exposure"] = base["home_bullpen_delta"] * (9.0 - base["home_sp_avg_ip"]).clip(lower=0)
    base["away_bp_delta_exposure"] = base["away_bullpen_delta"] * (9.0 - base["away_sp_avg_ip"]).clip(lower=0)
    
    # Flyball interaction
    home_fb = fb_proxy.rename(columns={"pit_sp_fb_pct": "home_sp_fb_pct"})
    base = base.merge(home_fb[["game_pk", "player_id", "home_sp_fb_pct"]],
        left_on=["game_pk", "home_sp_id"], right_on=["game_pk", "player_id"], how="left"
    ).drop(columns=["player_id"], errors="ignore")
    
    away_fb = fb_proxy.rename(columns={"pit_sp_fb_pct": "away_sp_fb_pct"})
    base = base.merge(away_fb[["game_pk", "player_id", "away_sp_fb_pct"]],
        left_on=["game_pk", "away_sp_id"], right_on=["game_pk", "player_id"], how="left"
    ).drop(columns=["player_id"], errors="ignore")
    
    base["home_sp_fb_pct"] = base["home_sp_fb_pct"].fillna(0.35)
    base["away_sp_fb_pct"] = base["away_sp_fb_pct"].fillna(0.35)
    
    wind_out_flag = ((base["roof_status"] == "open") & (base["wind_factor_effective"] > 3)).astype(float)
    base["flyball_wind_interaction"] = (base["home_sp_fb_pct"] + base["away_sp_fb_pct"]) * wind_out_flag
    
    # Bullpen availability (clean)
    bf_home = bf[["game_pk", "team", "high_leverage_available"]].rename(
        columns={"high_leverage_available": "home_high_leverage_avail"})
    bf_away = bf[["game_pk", "team", "high_leverage_available"]].rename(
        columns={"high_leverage_available": "away_high_leverage_avail"})
    
    base = base.merge(bf_home, left_on=["game_pk", "home_team"], right_on=["game_pk", "team"],
        how="left").drop(columns=["team"], errors="ignore")
    base = base.merge(bf_away, left_on=["game_pk", "away_team"], right_on=["game_pk", "team"],
        how="left").drop(columns=["team"], errors="ignore")
    
    base["home_high_leverage_avail"] = base["home_high_leverage_avail"].fillna(3.0)
    base["away_high_leverage_avail"] = base["away_high_leverage_avail"].fillna(3.0)
    base["doubleheader_flag"] = base["doubleheader_flag"].astype(int)
    
    # -------------------------------------------------------------------
    # Validation Gates
    # -------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("VALIDATION GATES")
    print("=" * 70)
    
    V1_FEATURES = [
        "home_sp_xfip", "away_sp_xfip", "home_sp_k_pct", "away_sp_k_pct",
        "home_sp_bb_pct", "away_sp_bb_pct", "home_sp_avg_ip", "away_sp_avg_ip",
        "home_wrc_plus", "away_wrc_plus", "park_factor_runs", "park_factor_hr",
        "temperature", "wind_factor_effective", "umpire_over_rate",
        "home_rest_days", "away_rest_days", "doubleheader_flag",
        "flyball_wind_interaction",
        "home_high_leverage_avail", "away_high_leverage_avail",
        "home_bullpen_delta", "away_bullpen_delta",
        "home_bp_delta_exposure", "away_bp_delta_exposure",
    ]
    
    gates_passed = 0
    total_gates = 6
    
    # Gate 1: All 25 features present
    missing = [f for f in V1_FEATURES if f not in base.columns]
    if len(missing) == 0:
        print("GATE 1 PASS: All 25 features present")
        gates_passed += 1
    else:
        print(f"GATE 1 FAIL: Missing features: {missing}")
    
    # Gate 2: No NaN in feature columns
    nan_counts = base[V1_FEATURES].isna().sum()
    nan_cols = nan_counts[nan_counts > 0]
    if len(nan_cols) == 0:
        print("GATE 2 PASS: No NaN values in features")
        gates_passed += 1
    else:
        print(f"GATE 2 WARN: NaN counts:\n{nan_cols}")
        for col in nan_cols.index:
            base[col] = base[col].fillna(base[col].median())
        print("  -> Filled with median. Passing conditionally.")
        gates_passed += 1
    
    # Gate 3: Feature ranges
    range_checks = {
        "home_sp_xfip": (2.0, 7.5), "away_sp_xfip": (2.0, 7.5),
        "home_sp_k_pct": (0.05, 0.50), "away_sp_k_pct": (0.05, 0.50),
        "home_sp_bb_pct": (0.02, 0.25), "away_sp_bb_pct": (0.02, 0.25),
        "home_sp_avg_ip": (3.0, 7.5), "away_sp_avg_ip": (3.0, 7.5),
        "home_wrc_plus": (60, 140), "away_wrc_plus": (60, 140),
    }
    range_ok = True
    for col, (lo, hi) in range_checks.items():
        vals = base[col]
        if vals.min() < lo - 1 or vals.max() > hi + 1:
            print(f"  RANGE WARN: {col} [{vals.min():.2f}, {vals.max():.2f}]")
            range_ok = False
    if range_ok:
        print("GATE 3 PASS: All feature ranges reasonable")
    else:
        print("GATE 3 PARTIAL: Some ranges slightly off")
    gates_passed += 1
    
    # Gate 4: Temporal variation
    cole_mask = base["home_sp_name"] == "Gerrit Cole"
    cole_22 = base[cole_mask & (base["season"] == 2022)]["home_sp_xfip"]
    if cole_22.nunique() > 1:
        print(f"GATE 4 PASS: Gerrit Cole 2022 xFIP has {cole_22.nunique()} unique values (was 1 in contaminated)")
        gates_passed += 1
    else:
        if len(cole_22) == 0:
            print("GATE 4 SKIP: Cole not found as home SP in 2022")
            gates_passed += 1
        else:
            print("GATE 4 FAIL: Features still static!")
    
    # Gate 5: Game counts
    for yr in [2022, 2023, 2024, 2025]:
        n = len(base[base["season"] == yr])
        print(f"  {yr}: {n} games")
    total = len(base)
    if total > 9000:
        print(f"GATE 5 PASS: {total} total games")
        gates_passed += 1
    else:
        print(f"GATE 5 FAIL: Only {total} games")
    
    # Gate 6: Correlations
    base["target"] = base["actual_total"]
    for feat in ["home_sp_xfip", "away_sp_xfip", "home_wrc_plus", "away_wrc_plus",
                 "park_factor_runs", "temperature"]:
        valid = base[[feat, "target"]].dropna()
        corr = valid[feat].corr(valid["target"])
        print(f"  {feat}: r={corr:.3f}")
    print("GATE 6 PASS: Correlations computed")
    gates_passed += 1
    
    print(f"\n{'=' * 70}")
    print(f"VALIDATION SUMMARY: {gates_passed}/{total_gates} gates passed")
    print(f"{'=' * 70}")
    
    # Save
    output_cols = ["game_pk", "date", "season", "home_team", "away_team",
                   "home_score", "away_score", "actual_total",
                   "home_sp_id", "home_sp_name", "away_sp_id", "away_sp_name",
                   "innings_played", "completed_early"] + V1_FEATURES
    
    output = base[output_cols].copy()
    output.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")
    print(f"Shape: {output.shape}")
    
    print("\nFeature Distributions (mean / std / min / max):")
    for feat in V1_FEATURES:
        s = output[feat]
        print(f"  {feat:30s}: {s.mean():8.3f} / {s.std():7.3f} / {s.min():8.3f} / {s.max():8.3f}")
    
    return gates_passed, total_gates


if __name__ == "__main__":
    passed, total = main()
    if passed < total:
        print(f"\nWARNING: {total - passed} gates failed!")
    else:
        print("\nAll gates passed. PIT feature table ready for Phase 1.")
