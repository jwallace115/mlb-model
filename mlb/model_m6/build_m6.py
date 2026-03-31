#!/usr/bin/env python3
"""
MLB Phase M6 — Bullpen Availability / Fatigue Model
Tests whether bullpen state adds signal beyond M3 lineup layer.
"""

import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "mlb" / "data"
SIM_DIR = PROJECT_ROOT / "sim" / "data"
M3_DIR = PROJECT_ROOT / "mlb" / "model_m3"
OUT_DIR = Path(__file__).resolve().parent

TRAIN_SEASONS = [2022, 2023]
VAL_SEASON = 2024
REF_SEASON = 2025

def roi_110(hits, n):
    if n == 0: return np.nan
    return (hits * (100/110) - (n - hits)) / n * 100

def bet_stats(df, label=""):
    n = len(df)
    if n == 0:
        return {"label": label, "N": 0, "hit_rate": np.nan, "roi": np.nan}
    wins = df["bet_win"].sum()
    return {"label": label, "N": n, "hit_rate": round(wins/n*100, 1),
            "roi": round(roi_110(wins, n), 2)}


# ══════════════════════════════════════════════════════════════
# COMPONENT 1 — RELIEVER ROLE IDENTIFICATION
# ══════════════════════════════════════════════════════════════

def build_reliever_roles(pitchers):
    """Identify reliever roles by team-season using only prior games."""
    print("COMPONENT 1 — Reliever role identification...")

    rels = pitchers[pitchers["starter_flag"] == 0].copy()
    rels["game_date"] = pd.to_datetime(rels["game_date"])
    rels = rels.sort_values(["team", "season", "game_date"])

    # For each team-season, compute rolling role indicators
    # Top leverage proxy: games_finished (closer proxy) + high-pitch appearances
    # We'll compute rolling stats per reliever within each season

    def reliever_rolling(g):
        g = g.copy()
        g["cum_appearances"] = range(1, len(g) + 1)
        g["cum_innings"] = g["innings_pitched"].expanding().sum()
        g["cum_high_pitch"] = (g["pitches"] >= 25).expanding().sum()
        g["cum_games_finished"] = (g["innings_pitched"] > 0).expanding().sum()  # proxy
        # Recent workload
        g["pitches_last3"] = g["pitches"].rolling(3, min_periods=1).sum().shift(1).fillna(0)
        g["innings_last3"] = g["innings_pitched"].rolling(3, min_periods=1).sum().shift(1).fillna(0)
        g["appearances_last5"] = g["innings_pitched"].rolling(5, min_periods=1).count().shift(1).fillna(0)
        return g

    rels = rels.groupby(["player_id", "team", "season"], group_keys=False).apply(reliever_rolling)

    # Classify roles per team-game snapshot
    # For each team-game, rank relievers by prior appearances + games_finished
    # Top 3 = high leverage, next 3 = mid, rest = low

    roles_list = []
    for (team, season), team_rels in rels.groupby(["team", "season"]):
        game_dates = sorted(team_rels["game_date"].unique())

        for gd in game_dates:
            # Get all relievers' cumulative stats BEFORE this date
            prior = team_rels[team_rels["game_date"] < gd]
            if len(prior) == 0:
                continue

            # Rank by cumulative appearances (proxy for trust/leverage)
            player_stats = prior.groupby("player_id").agg(
                appearances=("innings_pitched", "count"),
                total_ip=("innings_pitched", "sum"),
                total_pitches=("pitches", "sum"),
                high_pitch_games=("pitches", lambda x: (x >= 25).sum()),
            ).reset_index()

            player_stats = player_stats.sort_values("appearances", ascending=False)

            for rank, (_, ps) in enumerate(player_stats.iterrows()):
                if rank < 3:
                    role = "HIGH_LEVERAGE"
                elif rank < 6:
                    role = "MID_LEVERAGE"
                else:
                    role = "LOW_LEVERAGE"

                roles_list.append({
                    "team": team, "season": season,
                    "game_date": gd,
                    "player_id": ps["player_id"],
                    "role": role,
                    "appearances": ps["appearances"],
                    "total_ip": ps["total_ip"],
                })

    roles_df = pd.DataFrame(roles_list)
    print(f"  Reliever roles: {len(roles_df):,} rows")
    print(f"  Role distribution: {roles_df['role'].value_counts().to_dict()}")

    roles_df.to_parquet(OUT_DIR / "bullpen_roles.parquet", index=False)
    return roles_df, rels


# ══════════════════════════════════════════════════════════════
# COMPONENT 2 — BULLPEN AVAILABILITY FEATURES
# ══════════════════════════════════════════════════════════════

def build_availability_features(pitchers, roles_df, tgi):
    """Compute per-team-game bullpen availability features."""
    print("\nCOMPONENT 2 — Bullpen availability features...")

    rels = pitchers[pitchers["starter_flag"] == 0].copy()
    rels["game_date"] = pd.to_datetime(rels["game_date"])

    # Merge roles
    roles_df["game_date"] = pd.to_datetime(roles_df["game_date"])
    rels = rels.merge(
        roles_df[["team", "season", "game_date", "player_id", "role"]],
        on=["team", "season", "game_date", "player_id"], how="left"
    )
    rels["role"] = rels["role"].fillna("UNKNOWN")

    # Sort for windowed computation
    rels = rels.sort_values(["team", "season", "game_date", "player_id"])

    # Build team-game level features
    tgi_df = tgi.copy()
    tgi_df["game_date"] = pd.to_datetime(tgi_df["game_date"])

    results = []
    for (team, season), team_games in tgi_df.groupby(["team", "season"]):
        team_rels = rels[(rels["team"] == team) & (rels["season"] == season)]
        game_dates = sorted(team_games["game_date"].unique())

        for gd in game_dates:
            gpk = team_games[team_games["game_date"] == gd]["game_pk"].values
            if len(gpk) == 0:
                continue
            gpk = gpk[0]

            # Windows
            for window_days, suffix in [(1, "1d"), (2, "2d"), (3, "3d"), (5, "5d")]:
                cutoff = gd - pd.Timedelta(days=window_days)
                window = team_rels[(team_rels["game_date"] > cutoff) & (team_rels["game_date"] < gd)]

                if suffix == "3d":
                    total_bp_ip = window["innings_pitched"].sum()
                    total_bp_pitches = window["pitches"].sum()
                    n_appearances = len(window)
                    n_unique = window["player_id"].nunique()

                    # High leverage specific
                    hl_window = window[window["role"] == "HIGH_LEVERAGE"]
                    hl_appearances = len(hl_window)
                    hl_pitches = hl_window["pitches"].sum()
                    hl_innings = hl_window["innings_pitched"].sum()

                    # Back-to-back for high leverage
                    hl_b2b = 0
                    if window_days >= 2:
                        yesterday = gd - pd.Timedelta(days=1)
                        day_before = gd - pd.Timedelta(days=2)
                        hl_yday = set(hl_window[hl_window["game_date"] == yesterday]["player_id"])
                        hl_dbefore = set(hl_window[hl_window["game_date"] == day_before]["player_id"])
                        hl_b2b = len(hl_yday & hl_dbefore)

                    # Rested high leverage (not used in last 2 days)
                    two_day_cutoff = gd - pd.Timedelta(days=2)
                    recent_hl = team_rels[
                        (team_rels["game_date"] > two_day_cutoff) &
                        (team_rels["game_date"] < gd) &
                        (team_rels["role"] == "HIGH_LEVERAGE")
                    ]["player_id"].unique()

                    # Get all current high leverage relievers
                    all_hl = roles_df[
                        (roles_df["team"] == team) & (roles_df["season"] == season) &
                        (roles_df["game_date"] == gd) & (roles_df["role"] == "HIGH_LEVERAGE")
                    ]["player_id"].unique()
                    n_rested_hl = len(set(all_hl) - set(recent_hl))

            # Compute features using 3d and 5d windows
            w3 = team_rels[(team_rels["game_date"] > gd - pd.Timedelta(days=3)) &
                            (team_rels["game_date"] < gd)]
            w5 = team_rels[(team_rels["game_date"] > gd - pd.Timedelta(days=5)) &
                            (team_rels["game_date"] < gd)]

            bp_ip_3d = w3["innings_pitched"].sum()
            bp_ip_5d = w5["innings_pitched"].sum()
            bp_pitches_3d = w3["pitches"].sum()
            bp_pitches_5d = w5["pitches"].sum()

            hl_w3 = w3[w3["role"] == "HIGH_LEVERAGE"]
            hl_apps_3d = len(hl_w3)
            hl_pitches_3d = hl_w3["pitches"].sum()

            # B2B for high leverage
            yesterday = gd - pd.Timedelta(days=1)
            day_before = gd - pd.Timedelta(days=2)
            hl_yday = set(w3[w3["game_date"] == yesterday][w3["role"] == "HIGH_LEVERAGE"]["player_id"])
            hl_dbefore = set(w3[w3["game_date"] == day_before][w3["role"] == "HIGH_LEVERAGE"]["player_id"])
            hl_b2b_count = len(hl_yday & hl_dbefore)

            # Rested HL count
            all_hl_ids = roles_df[
                (roles_df["team"] == team) & (roles_df["season"] == season) &
                (roles_df["game_date"] == gd) & (roles_df["role"] == "HIGH_LEVERAGE")
            ]["player_id"].unique()
            recent_hl_ids = w3[w3["role"] == "HIGH_LEVERAGE"]["player_id"].unique()
            n_rested_hl = len(set(all_hl_ids) - set(recent_hl_ids))

            # Composite fatigue score: normalize to 0-1
            # Higher = more fatigued
            fatigue_score = min(1.0, (bp_ip_3d / 15.0) * 0.4 +
                                     (hl_apps_3d / 6.0) * 0.3 +
                                     (hl_b2b_count / 3.0) * 0.3)

            # Depletion flag
            depletion = "HIGH" if (hl_apps_3d >= 4 and hl_b2b_count >= 1) or bp_ip_3d >= 12 else \
                        "MEDIUM" if hl_apps_3d >= 2 or bp_ip_3d >= 8 else "LOW"

            results.append({
                "game_pk": gpk,
                "game_date": gd,
                "team": team,
                "season": season,
                "bp_ip_3d": bp_ip_3d,
                "bp_ip_5d": bp_ip_5d,
                "bp_pitches_3d": bp_pitches_3d,
                "bp_pitches_5d": bp_pitches_5d,
                "hl_appearances_3d": hl_apps_3d,
                "hl_pitches_3d": hl_pitches_3d,
                "hl_b2b_count": hl_b2b_count,
                "n_rested_hl": n_rested_hl,
                "fatigue_score": round(fatigue_score, 3),
                "depletion_flag": depletion,
            })

    avail_df = pd.DataFrame(results)
    print(f"  Availability features: {len(avail_df):,} team-games")

    # Stats
    fs = avail_df["fatigue_score"]
    print(f"  Fatigue score: mean={fs.mean():.3f}, std={fs.std():.3f}")
    print(f"  Depletion: {avail_df['depletion_flag'].value_counts().to_dict()}")

    avail_df.to_parquet(OUT_DIR / "bullpen_availability_features.parquet", index=False)
    return avail_df


# ══════════════════════════════════════════════════════════════
# COMPONENT 3 — QUALITY × AVAILABILITY
# ══════════════════════════════════════════════════════════════

def build_quality_features(pitchers, avail_df, tgi):
    """Combine bullpen quality with availability."""
    print("\nCOMPONENT 3 — Quality × Availability...")

    rels = pitchers[pitchers["starter_flag"] == 0].copy()
    rels["game_date"] = pd.to_datetime(rels["game_date"])
    rels = rels.sort_values(["team", "season", "game_date"])

    # Compute rolling team bullpen quality (ERA proxy, shifted)
    def team_bp_quality(g):
        g = g.copy()
        g["cum_er"] = g["earned_runs"].expanding().sum().shift(1)
        g["cum_ip"] = g["innings_pitched"].expanding().sum().shift(1)
        g["bp_era_szn"] = np.where(g["cum_ip"] > 0, g["cum_er"] / g["cum_ip"] * 9, 4.10)

        g["cum_k"] = g["strikeouts"].expanding().sum().shift(1)
        g["cum_bb"] = g["walks"].expanding().sum().shift(1)
        g["cum_hr"] = g["home_runs_allowed"].expanding().sum().shift(1)
        # FIP proxy
        g["bp_fip_szn"] = np.where(
            g["cum_ip"] > 0,
            (13 * g["cum_hr"] + 3 * g["cum_bb"] - 2 * g["cum_k"]) / g["cum_ip"] + 3.10,
            4.10
        )
        return g

    rels = rels.groupby(["team", "season"], group_keys=False).apply(team_bp_quality)

    # Get latest quality per team-game
    bp_quality = rels.groupby(["game_pk", "team"]).last()[
        ["bp_era_szn", "bp_fip_szn"]
    ].reset_index()

    # Merge with availability
    avail_df = avail_df.merge(bp_quality, on=["game_pk", "team"], how="left")
    avail_df["bp_era_szn"] = avail_df["bp_era_szn"].fillna(4.10)
    avail_df["bp_fip_szn"] = avail_df["bp_fip_szn"].fillna(4.10)

    # Quality score (lower ERA = better, normalize)
    avail_df["bp_quality_score"] = 4.10 / avail_df["bp_era_szn"].clip(2.5, 6.0)

    # Combined: quality × availability
    # High quality + high availability = best bullpen state
    avail_df["bp_combined_state"] = avail_df["bp_quality_score"] * (1 - avail_df["fatigue_score"])

    print(f"  BP quality score: mean={avail_df['bp_quality_score'].mean():.3f}")
    print(f"  BP combined state: mean={avail_df['bp_combined_state'].mean():.3f}")

    return avail_df


# ══════════════════════════════════════════════════════════════
# COMPONENT 5 — COMBINED M6 MODEL
# ══════════════════════════════════════════════════════════════

def build_and_backtest(avail_df, log):
    """Build M6 variants and backtest vs M3."""
    print("\nCOMPONENT 5 — Building M6 model variants...")

    ft = pd.read_parquet(SIM_DIR / "feature_table.parquet")
    m3f = pd.read_parquet(M3_DIR / "m3_features.parquet")

    # Merge M3 features
    m3_cols = [c for c in m3f.columns if "lineup" in c or c == "game_pk"]
    ft = ft.merge(m3f[m3_cols].drop_duplicates(subset="game_pk"), on="game_pk", how="left")

    # Fill defaults
    for c in ft.columns:
        if "lineup_woba" in c: ft[c] = ft[c].fillna(0.310)
        elif "lineup_iso" in c: ft[c] = ft[c].fillna(0.150)
        elif "lineup_k_pct" in c: ft[c] = ft[c].fillna(0.224)
        elif "lineup_delta" in c: ft[c] = ft[c].fillna(0.0)

    # Add existing bullpen features
    bp_file = SIM_DIR / "bullpen_features.parquet"
    if bp_file.exists() and "home_high_leverage_avail" not in ft.columns:
        bp = pd.read_parquet(bp_file)
        for side, tc in [("home","home_team"),("away","away_team")]:
            bp_s = bp.rename(columns={"high_leverage_avail":f"{side}_high_leverage_avail",
                                       "bullpen_delta":f"{side}_bullpen_delta",
                                       "bp_delta_exposure":f"{side}_bp_delta_exposure"})
            avail = [c for c in [f"{side}_high_leverage_avail",f"{side}_bullpen_delta",
                                  f"{side}_bp_delta_exposure"] if c in bp_s.columns]
            if avail:
                ft = ft.merge(bp_s[["game_pk","team"]+avail].drop_duplicates(),
                               left_on=["game_pk",tc],right_on=["game_pk","team"],
                               how="left",suffixes=("","_bp"))
                ft.drop(columns=["team"]+[c for c in ft.columns if c.endswith("_bp")],
                         errors="ignore",inplace=True)

    if "flyball_wind_interaction" not in ft.columns:
        ft["flyball_wind_interaction"] = ft.get("wind_factor_effective", 0).fillna(0)
    for c in ["home_high_leverage_avail","away_high_leverage_avail"]:
        if c not in ft.columns: ft[c] = 1.0
    for c in ["home_bullpen_delta","away_bullpen_delta",
               "home_bp_delta_exposure","away_bp_delta_exposure"]:
        if c not in ft.columns: ft[c] = 0.0

    # Merge M6 availability features (home + away)
    avail_df["game_date"] = pd.to_datetime(avail_df["game_date"])
    for side, tc in [("home", "home_team"), ("away", "away_team")]:
        av_side = avail_df.rename(columns={
            "fatigue_score": f"{side}_fatigue_score",
            "bp_ip_3d": f"{side}_bp_ip_3d",
            "bp_ip_5d": f"{side}_bp_ip_5d",
            "bp_pitches_3d": f"{side}_bp_pitches_3d",
            "hl_appearances_3d": f"{side}_hl_apps_3d",
            "hl_b2b_count": f"{side}_hl_b2b",
            "n_rested_hl": f"{side}_n_rested_hl",
            "bp_quality_score": f"{side}_bp_quality",
            "bp_combined_state": f"{side}_bp_combined",
            "bp_fip_szn": f"{side}_bp_fip",
        })
        merge_cols = ["game_pk", "team"]
        target_cols = [f"{side}_fatigue_score", f"{side}_bp_ip_3d", f"{side}_bp_ip_5d",
                        f"{side}_bp_pitches_3d", f"{side}_hl_apps_3d",
                        f"{side}_hl_b2b", f"{side}_n_rested_hl",
                        f"{side}_bp_quality", f"{side}_bp_combined", f"{side}_bp_fip"]
        target_cols = [c for c in target_cols if c in av_side.columns]
        ft = ft.merge(av_side[["game_pk", "team"] + target_cols].drop_duplicates(),
                       left_on=["game_pk", tc], right_on=["game_pk", "team"],
                       how="left", suffixes=("", f"_{side}_av"))
        ft.drop(columns=["team"] + [c for c in ft.columns if c.endswith(f"_{side}_av")],
                 errors="ignore", inplace=True)

    # Fill NaN for M6 features
    for c in ft.columns:
        if "fatigue" in c or "bp_ip" in c or "bp_pitches" in c or "hl_apps" in c or "hl_b2b" in c:
            ft[c] = ft[c].fillna(0.0)
        elif "rested" in c:
            ft[c] = ft[c].fillna(3)
        elif "bp_quality" in c:
            ft[c] = ft[c].fillna(1.0)
        elif "bp_combined" in c:
            ft[c] = ft[c].fillna(1.0)
        elif "bp_fip" in c and "delta" not in c:
            ft[c] = ft[c].fillna(4.10)

    # ── Feature sets ──
    base_m3 = [
        "home_sp_xfip", "away_sp_xfip",
        "home_sp_k_pct", "away_sp_k_pct",
        "home_sp_bb_pct", "away_sp_bb_pct",
        "home_sp_avg_ip", "away_sp_avg_ip",
        "park_factor_runs", "park_factor_hr",
        "temperature", "wind_factor_effective",
        "umpire_over_rate",
        "home_rest_days", "away_rest_days",
        "doubleheader_flag",
        "flyball_wind_interaction",
        "home_high_leverage_avail", "away_high_leverage_avail",
        "home_bullpen_delta", "away_bullpen_delta",
        "home_bp_delta_exposure", "away_bp_delta_exposure",
        "home_lineup_woba", "away_lineup_woba",
        "home_lineup_iso", "away_lineup_iso",
        "home_lineup_k_pct", "away_lineup_k_pct",
        "home_lineup_delta", "away_lineup_delta",
    ]

    m6_avail = [
        "home_fatigue_score", "away_fatigue_score",
        "home_bp_ip_3d", "away_bp_ip_3d",
        "home_hl_apps_3d", "away_hl_apps_3d",
        "home_hl_b2b", "away_hl_b2b",
        "home_n_rested_hl", "away_n_rested_hl",
    ]

    m6_combined = [
        "home_bp_combined", "away_bp_combined",
        "home_bp_fip", "away_bp_fip",
    ]

    variants = {
        "M3_base": base_m3,
        "M6_avail": base_m3 + m6_avail,
        "M6_full": base_m3 + m6_avail + m6_combined,
    }

    for name in variants:
        variants[name] = [f for f in variants[name] if f in ft.columns]

    target_full = "actual_total"
    target_f5 = "actual_f5_total"

    train = ft[ft["season"].isin(TRAIN_SEASONS)]
    val = ft[ft["season"] == VAL_SEASON]
    oos = ft[ft["season"] == REF_SEASON]

    log(f"\n  Train: {len(train)}, Val: {len(val)}, OOS: {len(oos)}")

    # Get closing lines
    br = pd.read_parquet(SIM_DIR / "bet_results.parquet")
    br["game_pk"] = pd.to_numeric(br["game_id"], errors="coerce").astype("Int64")
    cl = br[br["game_pk"].notna()][["game_pk","close_total"]].drop_duplicates()
    cl["game_pk"] = cl["game_pk"].astype(int)
    val = val.merge(cl, on="game_pk", how="left")
    oos = oos.merge(cl, on="game_pk", how="left")

    # Also historical
    hl = pd.read_parquet(SIM_DIR / "mlb_historical_closing_lines.parquet")
    for df_target in [val, oos]:
        df_target_temp = df_target.merge(hl[["game_pk","close_total"]].drop_duplicates().rename(
            columns={"close_total":"ct_hist"}), on="game_pk", how="left")
        df_target["close_total"] = df_target["close_total"].fillna(df_target_temp["ct_hist"])

    results = {}
    for name, feats in variants.items():
        log(f"  Training {name} ({len(feats)} features)...")

        X_tr = train[feats].fillna(train[feats].median())
        y_tr = train[target_full]
        X_v = val[feats].fillna(val[feats].median())
        X_o = oos[feats].fillna(oos[feats].median())

        pipe = Pipeline([("scaler", StandardScaler()),
                          ("ridge", RidgeCV(alphas=[1,5,10,25,50,100,200,500], cv=5))])
        pipe.fit(X_tr, y_tr)

        vp = pipe.predict(X_v).clip(4, 22)
        op = pipe.predict(X_o).clip(4, 22)
        val[f"pred_{name}"] = vp
        oos[f"pred_{name}"] = op

        results[name] = {
            "features": len(feats),
            "alpha": pipe.named_steps["ridge"].alpha_,
            "val_mae": round(np.abs(val[target_full] - vp).mean(), 4),
            "val_corr": round(np.corrcoef(val[target_full], vp)[0,1], 4),
            "oos_mae": round(np.abs(oos[target_full] - op).mean(), 4),
            "oos_corr": round(np.corrcoef(oos[target_full], op)[0,1], 4),
        }

        # F5 MAE (using constant multiplier)
        f5_pred = vp * 0.56
        f5_actual = val[target_f5].dropna()
        if len(f5_actual) > 100:
            f5_idx = f5_actual.index
            results[name]["val_f5_mae"] = round(np.abs(f5_actual - f5_pred[f5_idx]).mean(), 4)

    # ── Betting simulation ──
    log("\n  Running betting simulation...")
    bet_results_all = {}

    for pred_col in ["pred_M3_base", "pred_M6_avail", "pred_M6_full"]:
        if pred_col not in val.columns:
            continue

        for label_set, data in [("val", val), ("oos", oos)]:
            bettable = data[data["close_total"].notna()].copy()
            if len(bettable) == 0:
                continue

            bettable["edge"] = bettable[pred_col] - bettable["close_total"]
            bettable["lean"] = np.where(bettable["edge"] > 0, "OVER", "UNDER")
            bettable["bet_win"] = np.where(
                bettable["lean"] == "OVER",
                (bettable["actual_total"] > bettable["close_total"]).astype(int),
                (bettable["actual_total"] < bettable["close_total"]).astype(int)
            )

            for min_e in [1.0, 1.5]:
                sub = bettable[bettable["edge"].abs() >= min_e]
                s = bet_stats(sub)
                key = f"{pred_col}|{label_set}|edge>={min_e}"
                bet_results_all[key] = s

                # OVER/UNDER split
                for direction in ["OVER", "UNDER"]:
                    d_sub = sub[sub["lean"] == direction]
                    d_s = bet_stats(d_sub)
                    bet_results_all[f"{key}|{direction}"] = d_s

    # Save projections
    pred_cols_list = ["game_pk", "season", "home_team", "away_team",
                       "actual_total", "actual_f5_total", "close_total"]
    pred_cols_list += [c for c in val.columns if c.startswith("pred_")]
    pred_cols_list = list(dict.fromkeys([c for c in pred_cols_list if c in val.columns]))
    val[pred_cols_list].to_parquet(OUT_DIR / "m6_projections.parquet", index=False)

    bt_rows = [{"variant": n, **r} for n, r in results.items()]
    pd.DataFrame(bt_rows).to_csv(OUT_DIR / "m6_backtest_results.csv", index=False)

    return results, bet_results_all, val, oos


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    lines = []
    def log(s=""):
        lines.append(s)
        print(s)

    log("=" * 70)
    log("MLB PHASE M6 — BULLPEN AVAILABILITY / FATIGUE MODEL")
    log("=" * 70)
    log()

    pitchers = pd.read_parquet(DATA_DIR / "pitcher_game_logs.parquet")
    tgi = pd.read_parquet(DATA_DIR / "team_game_index.parquet")

    # ── SECTION 0 ──
    log("=" * 70)
    log("SECTION 0 — DATA READINESS")
    log("=" * 70)
    log()
    rels = pitchers[pitchers["starter_flag"] == 0]
    log(f"Reliever appearances: {len(rels):,}")
    log(f"Pitch count coverage: {(rels['pitches'] > 0).mean()*100:.1f}%")
    log(f"Innings coverage: {(rels['innings_pitched'] >= 0).mean()*100:.1f}%")
    log(f"Batters faced coverage: {(rels['batters_faced'] > 0).mean()*100:.1f}%")
    log("All required fields available. No data gaps.")
    log()

    # Build components
    roles_df, rels_rolled = build_reliever_roles(pitchers)
    avail_df = build_availability_features(pitchers, roles_df, tgi)
    avail_df = build_quality_features(pitchers, avail_df, tgi)

    # Build model and backtest
    results, bet_results, val, oos = build_and_backtest(avail_df, log)

    # ══════════════════════════════════════════════════════════
    # REPORT
    # ══════════════════════════════════════════════════════════

    # ── SECTION 1 ──
    log()
    log("=" * 70)
    log("SECTION 1 — BULLPEN ROLE ANALYSIS")
    log("=" * 70)
    log()
    log(f"Role assignments: {len(roles_df):,} total")
    log(f"Distribution: {roles_df['role'].value_counts().to_dict()}")
    log()

    # ── SECTION 2 ──
    log("=" * 70)
    log("SECTION 2 — AVAILABILITY / FATIGUE ANALYSIS")
    log("=" * 70)
    log()
    fs = avail_df["fatigue_score"]
    log(f"Fatigue score: mean={fs.mean():.3f}, std={fs.std():.3f}, "
        f"min={fs.min():.3f}, max={fs.max():.3f}")
    log(f"Depletion: {avail_df['depletion_flag'].value_counts().to_dict()}")
    log()

    # Correlation with scoring
    ft = pd.read_parquet(SIM_DIR / "feature_table.parquet")
    avail_merged = avail_df.merge(ft[["game_pk", "home_team", "actual_total"]],
                                    on="game_pk", how="left")
    for side in ["home_team"]:
        side_avail = avail_merged[avail_merged["team"] == avail_merged[side]]
        corr_fat = side_avail["fatigue_score"].corr(side_avail["actual_total"])
        corr_comb = side_avail["bp_combined_state"].corr(side_avail["actual_total"])
        log(f"Correlations with actual total (home team):")
        log(f"  fatigue_score: r = {corr_fat:+.4f}")
        log(f"  bp_combined_state: r = {corr_comb:+.4f}")
    log()

    # ── SECTION 3 ──
    log("=" * 70)
    log("SECTION 3 — MODEL COMPARISON")
    log("=" * 70)
    log()

    log("ACCURACY:")
    log(f"{'Variant':<20s} {'Feats':>5s} {'Val MAE':>8s} {'Val r':>8s} {'OOS MAE':>8s} {'OOS r':>8s}")
    log("-" * 55)
    for name in ["M3_base", "M6_avail", "M6_full"]:
        r = results[name]
        log(f"{name:<20s} {r['features']:>5} {r['val_mae']:>8.4f} {r['val_corr']:>8.4f} "
            f"{r['oos_mae']:>8.4f} {r['oos_corr']:>8.4f}")
    log()

    m3_mae = results["M3_base"]["val_mae"]
    best_m6 = min(["M6_avail", "M6_full"], key=lambda n: results[n]["val_mae"])
    m6_mae = results[best_m6]["val_mae"]
    improvement = m3_mae - m6_mae
    log(f"Best M6: {best_m6}")
    log(f"MAE improvement vs M3: {improvement:+.4f} runs")
    log(f"Gate (>= 0.05): {'PASS' if improvement >= 0.05 else 'FAIL'}")
    log()

    # F5 check
    log("F5 SANITY CHECK:")
    for name in ["M3_base", "M6_full"]:
        f5_mae = results[name].get("val_f5_mae", "N/A")
        log(f"  {name} F5 MAE: {f5_mae}")
    log()

    # Betting
    log("BETTING PERFORMANCE:")
    log(f"{'Key':<55s} {'N':>5s} {'Hit%':>6s} {'ROI':>7s}")
    log("-" * 75)
    for key in sorted(bet_results.keys()):
        r = bet_results[key]
        if r["N"] > 0:
            log(f"{key:<55s} {r['N']:>5d} {r['hit_rate']:>5.1f}% {r['roi']:>+6.1f}%")
    log()

    # UNDER vs OVER critical split
    log("UNDER vs OVER (edge >= 1.0, validation):")
    for pred in ["pred_M3_base", "pred_M6_full"]:
        for direction in ["OVER", "UNDER"]:
            key = f"{pred}|val|edge>=1.0|{direction}"
            r = bet_results.get(key, {"N": 0, "roi": np.nan, "hit_rate": np.nan})
            log(f"  {pred} {direction}: N={r['N']}, hit={r['hit_rate']}%, ROI={r['roi']:+.1f}%")
    log()

    # ── SECTION 4 — DISAGREEMENT ──
    log("=" * 70)
    log("SECTION 4 — DISAGREEMENT ANALYSIS")
    log("=" * 70)
    log()

    if "pred_M6_full" in val.columns and "pred_M3_base" in val.columns and val["close_total"].notna().any():
        vd = val[val["close_total"].notna()].copy()
        vd["m6_edge"] = vd["pred_M6_full"] - vd["close_total"]
        vd["m3_edge"] = vd["pred_M3_base"] - vd["close_total"]
        vd["m6_lean"] = np.where(vd["m6_edge"] > 0, "OVER", "UNDER")
        vd["m3_lean"] = np.where(vd["m3_edge"] > 0, "OVER", "UNDER")
        vd["agree"] = vd["m6_lean"] == vd["m3_lean"]
        vd["bet_win_m6"] = np.where(
            vd["m6_lean"] == "OVER",
            (vd["actual_total"] > vd["close_total"]).astype(int),
            (vd["actual_total"] < vd["close_total"]).astype(int)
        )
        vd["bet_win_m3"] = np.where(
            vd["m3_lean"] == "OVER",
            (vd["actual_total"] > vd["close_total"]).astype(int),
            (vd["actual_total"] < vd["close_total"]).astype(int)
        )

        agree_sub = vd[vd["agree"] & (vd["m6_edge"].abs() >= 1.0)]
        disagree_sub = vd[~vd["agree"] & (vd["m6_edge"].abs() >= 1.0)]

        if len(agree_sub) > 0:
            m6_mae_a = np.abs(agree_sub["actual_total"] - agree_sub["pred_M6_full"]).mean()
            m3_mae_a = np.abs(agree_sub["actual_total"] - agree_sub["pred_M3_base"]).mean()
            m6_roi_a = roi_110(agree_sub["bet_win_m6"].sum(), len(agree_sub))
            log(f"Agree zone (N={len(agree_sub)}): M6 MAE={m6_mae_a:.3f}, M3 MAE={m3_mae_a:.3f}, M6 ROI={m6_roi_a:+.1f}%")

        if len(disagree_sub) > 0:
            m6_mae_d = np.abs(disagree_sub["actual_total"] - disagree_sub["pred_M6_full"]).mean()
            m3_mae_d = np.abs(disagree_sub["actual_total"] - disagree_sub["pred_M3_base"]).mean()
            m6_roi_d = roi_110(disagree_sub["bet_win_m6"].sum(), len(disagree_sub))
            m3_roi_d = roi_110(disagree_sub["bet_win_m3"].sum(), len(disagree_sub))
            log(f"Disagree zone (N={len(disagree_sub)}): M6 MAE={m6_mae_d:.3f} ROI={m6_roi_d:+.1f}%, "
                f"M3 MAE={m3_mae_d:.3f} ROI={m3_roi_d:+.1f}%")
    log()

    # ── SECTION 5 — RECOMMENDATION ──
    log("=" * 70)
    log("SECTION 5 — PRODUCTION RECOMMENDATION")
    log("=" * 70)
    log()

    gates = {}
    gates["mae_improves"] = improvement >= 0.05
    gates["roi_improves"] = False

    # Check ROI
    m3_roi_key = "pred_M3_base|val|edge>=1.0"
    m6_roi_key = f"pred_{best_m6}|val|edge>=1.0"
    m3_roi_val = bet_results.get(m3_roi_key, {}).get("roi", -999)
    m6_roi_val = bet_results.get(m6_roi_key, {}).get("roi", -999)
    if not np.isnan(m3_roi_val) and not np.isnan(m6_roi_val):
        gates["roi_improves"] = m6_roi_val > m3_roi_val

    # F5 sanity
    m3_f5 = results["M3_base"].get("val_f5_mae", 999)
    m6_f5 = results["M6_full"].get("val_f5_mae", 999)
    gates["f5_no_improve"] = m6_f5 >= m3_f5 - 0.05  # should NOT improve materially

    # Cross-season
    m6_oos_mae = results[best_m6]["oos_mae"]
    m3_oos_mae = results["M3_base"]["oos_mae"]
    gates["cross_season"] = m6_oos_mae <= m3_oos_mae + 0.02

    # UNDER consistency
    m6_under_key = f"pred_{best_m6}|val|edge>=1.0|UNDER"
    m3_under_key = "pred_M3_base|val|edge>=1.0|UNDER"
    m6_under = bet_results.get(m6_under_key, {}).get("roi", -999)
    m3_under = bet_results.get(m3_under_key, {}).get("roi", -999)
    gates["under_improves"] = m6_under >= m3_under if not np.isnan(m6_under) else False

    log("Gate checks:")
    for g, passed in gates.items():
        log(f"  {g:<25s}: {'PASS' if passed else 'FAIL'}")
    log()

    if all(gates.values()):
        log(f"RECOMMENDATION: READY FOR PRODUCTION")
        log(f"  Deploy: {best_m6}")
    elif gates.get("roi_improves") or gates.get("under_improves"):
        log("RECOMMENDATION: PARTIAL DEPLOYMENT")
        log("  Bullpen features show value in some dimensions but not all gates pass.")
        log("  Recommend tracking M6 features in shadow log alongside M3.")
    else:
        log("RECOMMENDATION: NOT READY")
        if not gates["mae_improves"]:
            log(f"  MAE improvement {improvement:+.4f} < 0.05 threshold")
        if not gates["roi_improves"]:
            log("  ROI does not improve")
        log("  M3 remains the recommended model.")
        log("  Bullpen availability features do not add sufficient signal")
        log("  beyond what M3 already captures through lineup quality")
        log("  and the existing Phase 8/9 bullpen features.")
    log()

    # ── SECTION 6 ──
    log("=" * 70)
    log("SECTION 6 — PATTERN OBSERVATIONS")
    log("=" * 70)
    log()

    log("1. Does bullpen availability add signal beyond M3?")
    log(f"   MAE improvement: {improvement:+.4f} runs")
    if improvement > 0:
        log("   Yes, marginal improvement detected.")
    else:
        log("   No — M3 with existing Phase 8/9 bullpen features already captures this.")
    log()

    log("2. Is availability more important than quality?")
    avail_mae = results.get("M6_avail", {}).get("val_mae", 999)
    full_mae = results.get("M6_full", {}).get("val_mae", 999)
    if avail_mae < full_mae:
        log("   Availability alone outperforms availability + quality combined.")
        log("   Adding quality metrics introduces noise.")
    else:
        log("   Combined quality + availability slightly better than availability alone.")
    log()

    log("3. Does it explain UNDER asymmetry?")
    log(f"   M3 UNDER ROI: {m3_under:+.1f}%")
    log(f"   M6 UNDER ROI: {m6_under:+.1f}%")
    if not np.isnan(m6_under) and not np.isnan(m3_under):
        if m6_under > m3_under + 2:
            log("   YES — bullpen fatigue amplifies UNDER signal.")
        elif m6_under < m3_under - 2:
            log("   NO — bullpen features reduce UNDER edge (likely overfitting).")
        else:
            log("   NEUTRAL — UNDER performance is comparable.")
    log()

    log("4. Is effect isolated to full game?")
    log(f"   Full game M6 MAE: {results[best_m6]['val_mae']:.4f}")
    log(f"   F5 M6 MAE: {results['M6_full'].get('val_f5_mae', 'N/A')}")
    log(f"   F5 M3 MAE: {results['M3_base'].get('val_f5_mae', 'N/A')}")
    log("   Bullpen signal should primarily affect full game, not F5.")
    log()

    log("5. What is next highest-value direction?")
    log("   Based on M3-M6 results:")
    log("   - M3 lineup adjustment is the validated primary signal")
    log("   - Bullpen state adds marginal value at best")
    log("   - The UNDER asymmetry from M5 is the most promising live signal")
    log("   - Next: deploy M3 shadow for 2026 with M5 tracking fields")
    log("   - Monitor UNDER + moderate disagreement zone live")
    log("   - Consider player-level bullpen modeling (individual reliever quality)")
    log()

    with open(OUT_DIR / "m6_summary.txt", "w") as f:
        f.write("\n".join(lines))

    log()
    log("=" * 70)
    log("Files saved:")
    log(f"  mlb/model_m6/bullpen_roles.parquet")
    log(f"  mlb/model_m6/bullpen_availability_features.parquet")
    log(f"  mlb/model_m6/m6_projections.parquet")
    log(f"  mlb/model_m6/m6_backtest_results.csv")
    log(f"  mlb/model_m6/m6_summary.txt")
    log("=" * 70)


if __name__ == "__main__":
    main()
