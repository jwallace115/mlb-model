"""
NCAAF Base Spread Engine — Steps 1-5
Pulls data from CFBD API, builds canonical table, engineers features,
trains ridge regression, evaluates, and writes report.
"""

import os
import sys
import time
import json
import requests
import numpy as np
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CFBD_KEY = os.environ.get("CFBD_API_KEY")
if not CFBD_KEY:
    sys.exit("ERROR: CFBD_API_KEY not found in environment")

HEADERS = {
    "Authorization": f"Bearer {CFBD_KEY}",
    "Accept": "application/json",
}
BASE = "https://api.collegefootballdata.com"
DELAY = 0.35  # rate limit

SEASONS = [2022, 2023, 2024, 2025]
TRAIN_YEARS = [2022, 2023]
VAL_YEARS = [2024]
OOS_YEARS = [2025]

# P5 conferences (post-realignment 2024+)
P5_CONFERENCES = {
    "SEC", "Big Ten", "Big 12", "ACC", "Pac-12",
    # pre-2024 names
    "PAC-12", "Pac-10",
}


def api_get(endpoint, params=None):
    """GET from CFBD API with rate limiting."""
    url = f"{BASE}{endpoint}"
    time.sleep(DELAY)
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# =========================================================================
# STEP 1 — PULL DATA & BUILD CANONICAL TABLE
# =========================================================================

def pull_games(seasons):
    rows = []
    for yr in seasons:
        data = api_get("/games", {"year": yr, "seasonType": "regular"})
        for g in data:
            rows.append({
                "game_id": g["id"],
                "season": g["season"],
                "week": g["week"],
                "home_team": g["homeTeam"],
                "away_team": g["awayTeam"],
                "home_points": g.get("homePoints"),
                "away_points": g.get("awayPoints"),
                "neutral_site": g.get("neutralSite", False),
                "conference_game": g.get("conferenceGame", False),
                "home_classification": g.get("homeClassification"),
                "away_classification": g.get("awayClassification"),
                "home_conference": g.get("homeConference"),
                "away_conference": g.get("awayConference"),
                "completed": g.get("completed", False),
            })
        print(f"  Games {yr}: {len([r for r in rows if r['season']==yr])} total")
    return pd.DataFrame(rows)


def pull_lines(seasons):
    rows = []
    for yr in seasons:
        data = api_get("/lines", {"year": yr})
        for g in data:
            game_id = g["id"]
            lines = g.get("lines", [])
            if not lines:
                continue
            # Priority: ESPN Bet > consensus > DraftKings > first available
            chosen = None
            for pref in ["ESPN Bet", "consensus", "DraftKings", "Bovada"]:
                for ln in lines:
                    if ln.get("provider") == pref and ln.get("spread") is not None:
                        chosen = ln
                        break
                if chosen:
                    break
            if not chosen:
                for ln in lines:
                    if ln.get("spread") is not None:
                        chosen = ln
                        break
            if chosen:
                rows.append({
                    "game_id": game_id,
                    "closing_spread": chosen["spread"],
                    "spread_provider": chosen.get("provider"),
                    "over_under": chosen.get("overUnder"),
                })
        print(f"  Lines {yr}: {len([r for r in rows if True])} cumulative")
    return pd.DataFrame(rows)


def pull_sp_ratings(seasons):
    """SP+ ratings per team per season."""
    rows = []
    for yr in seasons:
        data = api_get("/ratings/sp", {"year": yr})
        for t in data:
            rows.append({
                "team": t["team"],
                "season": yr,
                "sp_overall": t.get("rating"),
                "sp_offense": t.get("offense", {}).get("rating") if isinstance(t.get("offense"), dict) else None,
                "sp_defense": t.get("defense", {}).get("rating") if isinstance(t.get("defense"), dict) else None,
            })
        print(f"  SP+ {yr}: {len([r for r in rows if r['season']==yr])} teams")
    return pd.DataFrame(rows)


def pull_advanced_stats(seasons):
    """Season-level advanced stats (PPA, success rate)."""
    rows = []
    for yr in seasons:
        data = api_get("/stats/season/advanced", {"year": yr})
        for t in data:
            off = t.get("offense", {}) or {}
            dfn = t.get("defense", {}) or {}
            rows.append({
                "team": t["team"],
                "season": yr,
                "ppa_offense": off.get("totalPPA"),
                "ppa_defense": dfn.get("totalPPA"),
                "success_rate_off": off.get("successRate"),
                "success_rate_def": dfn.get("successRate"),
                "explosiveness_off": off.get("explosiveness"),
                "explosiveness_def": dfn.get("explosiveness"),
            })
        print(f"  Advanced {yr}: {len([r for r in rows if r['season']==yr])} teams")
    return pd.DataFrame(rows)


def pull_returning(seasons):
    rows = []
    for yr in seasons:
        data = api_get("/player/returning", {"year": yr})
        for t in data:
            rows.append({
                "team": t["team"],
                "season": yr,
                "percent_ppa": t.get("percentPPA"),
                "percent_passing_ppa": t.get("percentPassingPPA"),
                "percent_rushing_ppa": t.get("percentRushingPPA"),
                "total_ppa": t.get("totalPPA"),
            })
        print(f"  Returning {yr}: {len([r for r in rows if r['season']==yr])} teams")
    return pd.DataFrame(rows)


def pull_talent(seasons):
    rows = []
    for yr in seasons:
        data = api_get("/talent", {"year": yr})
        for t in data:
            rows.append({
                "team": t.get("team") or t.get("school"),
                "season": yr,
                "talent": t.get("talent"),
            })
        print(f"  Talent {yr}: {len([r for r in rows if r['season']==yr])} teams")
    return pd.DataFrame(rows)


def pull_coaches(seasons):
    rows = []
    for yr in seasons:
        data = api_get("/coaches", {"year": yr})
        for c in data:
            for s in c.get("seasons", []):
                if s.get("year") == yr:
                    rows.append({
                        "coach_name": f"{c.get('firstName','')} {c.get('lastName','')}".strip(),
                        "team": s.get("school"),
                        "season": yr,
                        "wins": s.get("wins"),
                        "losses": s.get("losses"),
                    })
        print(f"  Coaches {yr}: {len([r for r in rows if r['season']==yr])} entries")
    return pd.DataFrame(rows)


def pull_game_advanced(seasons):
    """Per-game advanced stats for rolling features."""
    rows = []
    for yr in seasons:
        for wk in range(1, 16):
            try:
                data = api_get("/stats/game/advanced", {"year": yr, "week": wk})
            except Exception as e:
                print(f"    Week {wk} {yr}: {e}")
                continue
            for g in data:
                game_id = g.get("gameId")
                team_name = g.get("team")
                off = g.get("offense", {}) or {}
                dfn = g.get("defense", {}) or {}
                rows.append({
                    "game_id": game_id,
                    "team": team_name,
                    "season": yr,
                    "week": wk,
                    "game_ppa_off": off.get("totalPPA"),
                    "game_ppa_def": dfn.get("totalPPA"),
                    "game_success_off": off.get("successRate"),
                    "game_success_def": dfn.get("successRate"),
                })
        print(f"  Game-level advanced {yr}: {len([r for r in rows if r['season']==yr])} team-game rows")
    return pd.DataFrame(rows)


def pull_portal(seasons):
    rows = []
    for yr in seasons:
        try:
            data = api_get("/player/portal", {"year": yr})
            for p in data:
                rows.append({
                    "season": yr,
                    "origin": p.get("origin"),
                    "destination": p.get("destination"),
                    "stars": p.get("stars"),
                    "rating": p.get("rating"),
                    "position": p.get("position"),
                })
            print(f"  Portal {yr}: {len([r for r in rows if r['season']==yr])} entries")
        except Exception as e:
            print(f"  Portal {yr}: FAILED ({e})")
    return pd.DataFrame(rows)


def build_canonical(games_df, lines_df):
    """Filter to FBS-vs-FBS completed regular season, join lines."""
    df = games_df.copy()
    # FBS vs FBS only
    df = df[(df["home_classification"] == "fbs") & (df["away_classification"] == "fbs")]
    # completed only
    df = df[df["completed"] == True]
    # drop nulls on points
    df = df.dropna(subset=["home_points", "away_points"])
    df["actual_margin"] = df["home_points"] - df["away_points"]

    # Join closing spread
    df = df.merge(lines_df[["game_id", "closing_spread", "spread_provider", "over_under"]],
                  on="game_id", how="left")

    print(f"\nCanonical table: {len(df)} games")
    for yr in SEASONS:
        n = len(df[df["season"] == yr])
        n_lines = df[df["season"] == yr]["closing_spread"].notna().sum()
        print(f"  {yr}: {n} games, {n_lines} with closing spread")

    return df


# =========================================================================
# STEP 2 — FEATURE ENGINEERING
# =========================================================================

def build_coach_continuity(coaches_df):
    """Derive new_coach flag: 1 if coach is different from prior year."""
    coaches_df = coaches_df.sort_values(["team", "season"])
    records = []
    for team, grp in coaches_df.groupby("team"):
        grp = grp.sort_values("season")
        prev_coach = None
        for _, row in grp.iterrows():
            new_coach = 0
            if prev_coach is not None and row["coach_name"] != prev_coach:
                new_coach = 1
            records.append({
                "team": team,
                "season": row["season"],
                "new_coach": new_coach,
                "coach_name": row["coach_name"],
            })
            prev_coach = row["coach_name"]
    return pd.DataFrame(records)


def build_portal_net_stars(portal_df):
    """Net star shock from portal: incoming - outgoing stars per team."""
    if portal_df.empty:
        return pd.DataFrame(columns=["team", "season", "portal_net_stars"])

    records = []
    for yr in portal_df["season"].unique():
        yr_df = portal_df[portal_df["season"] == yr].copy()
        yr_df["stars"] = yr_df["stars"].fillna(0)

        # Outgoing stars
        out = yr_df.groupby("origin")["stars"].sum().reset_index()
        out.columns = ["team", "stars_out"]

        # Incoming stars (only where destination is known)
        inc_df = yr_df[yr_df["destination"].notna()]
        inc = inc_df.groupby("destination")["stars"].sum().reset_index()
        inc.columns = ["team", "stars_in"]

        merged = out.merge(inc, on="team", how="outer").fillna(0)
        merged["portal_net_stars"] = merged["stars_in"] - merged["stars_out"]
        merged["season"] = yr
        records.append(merged[["team", "season", "portal_net_stars"]])

    return pd.concat(records, ignore_index=True)


def build_rolling_features(canonical_df, game_adv_df):
    """Build rolling PPA features (shifted, pregame-safe)."""
    # For each team, build game-by-game timeline and compute rolling stats
    records = []

    for side in ["home", "away"]:
        team_col = f"{side}_team"
        for _, game in canonical_df.iterrows():
            records.append({
                "game_id": game["game_id"],
                "team": game[team_col],
                "season": game["season"],
                "week": game["week"],
                "side": side,
                "margin": game["actual_margin"] if side == "home" else -game["actual_margin"],
            })

    timeline = pd.DataFrame(records)
    # Merge game-level advanced stats
    if not game_adv_df.empty:
        timeline = timeline.merge(
            game_adv_df[["game_id", "team", "game_ppa_off", "game_ppa_def"]],
            on=["game_id", "team"], how="left"
        )
    else:
        timeline["game_ppa_off"] = np.nan
        timeline["game_ppa_def"] = np.nan

    timeline = timeline.sort_values(["team", "season", "week"])

    # Compute rolling features per team-season (shifted by 1 = pregame safe)
    rolling_records = []
    for (team, season), grp in timeline.groupby(["team", "season"]):
        grp = grp.sort_values("week")
        for i, (idx, row) in enumerate(grp.iterrows()):
            prev = grp.iloc[:i]  # all games before this one in the season
            n_prev = len(prev)

            rolling_margin_3g = prev["margin"].tail(3).mean() if n_prev >= 1 else np.nan
            rolling_ppa_off_season = prev["game_ppa_off"].mean() if n_prev >= 1 else np.nan
            rolling_ppa_def_season = prev["game_ppa_def"].mean() if n_prev >= 1 else np.nan

            rolling_records.append({
                "game_id": row["game_id"],
                "team": team,
                "side": row["side"],
                "games_played": n_prev,
                "rolling_margin_3g": rolling_margin_3g,
                "rolling_ppa_off_season": rolling_ppa_off_season,
                "rolling_ppa_def_season": rolling_ppa_def_season,
            })

    return pd.DataFrame(rolling_records)


def engineer_features(canonical_df, sp_df, adv_df, returning_df, talent_df,
                      coach_cont_df, portal_stars_df, rolling_df):
    """Build difference features for each game."""
    df = canonical_df.copy()

    # --- Prior year lookups ---
    # SP+ from prior year
    sp_prior = sp_df.copy()
    sp_prior["season"] = sp_prior["season"] + 1  # shift to be "prior" for next year

    # Advanced stats from prior year
    adv_prior = adv_df.copy()
    adv_prior["season"] = adv_prior["season"] + 1

    for side, prefix in [("home", "h"), ("away", "a")]:
        team_col = f"{side}_team"

        # SP+ prior
        merged = df[[team_col, "season"]].merge(
            sp_prior.rename(columns={"team": team_col}),
            on=[team_col, "season"], how="left"
        )
        df[f"{prefix}_prior_sp"] = merged["sp_overall"]
        df[f"{prefix}_prior_sp_off"] = merged["sp_offense"]
        df[f"{prefix}_prior_sp_def"] = merged["sp_defense"]

        # Advanced prior
        merged = df[[team_col, "season"]].merge(
            adv_prior.rename(columns={"team": team_col}),
            on=[team_col, "season"], how="left"
        )
        df[f"{prefix}_prior_ppa_off"] = merged["ppa_offense"]
        df[f"{prefix}_prior_ppa_def"] = merged["ppa_defense"]

        # Returning production (current year)
        merged = df[[team_col, "season"]].merge(
            returning_df.rename(columns={"team": team_col}),
            on=[team_col, "season"], how="left"
        )
        df[f"{prefix}_returning_ppa"] = merged["percent_ppa"]

        # Talent (current year)
        merged = df[[team_col, "season"]].merge(
            talent_df.rename(columns={"team": team_col}),
            on=[team_col, "season"], how="left"
        )
        df[f"{prefix}_talent"] = merged["talent"]

        # Coach continuity (current year)
        merged = df[[team_col, "season"]].merge(
            coach_cont_df.rename(columns={"team": team_col}),
            on=[team_col, "season"], how="left"
        )
        df[f"{prefix}_new_coach"] = merged["new_coach"]

        # Portal net stars (current year)
        merged = df[[team_col, "season"]].merge(
            portal_stars_df.rename(columns={"team": team_col}),
            on=[team_col, "season"], how="left"
        )
        df[f"{prefix}_portal_net_stars"] = merged["portal_net_stars"]

        # Rolling features
        side_rolling = rolling_df[rolling_df["side"] == side].copy()
        merged = df[["game_id"]].merge(
            side_rolling.rename(columns={
                "rolling_margin_3g": f"{prefix}_rolling_margin_3g",
                "rolling_ppa_off_season": f"{prefix}_rolling_ppa_off",
                "rolling_ppa_def_season": f"{prefix}_rolling_ppa_def",
                "games_played": f"{prefix}_games_played",
            })[["game_id", f"{prefix}_rolling_margin_3g", f"{prefix}_rolling_ppa_off",
                f"{prefix}_rolling_ppa_def", f"{prefix}_games_played"]],
            on="game_id", how="left"
        )
        df[f"{prefix}_rolling_margin_3g"] = merged[f"{prefix}_rolling_margin_3g"]
        df[f"{prefix}_rolling_ppa_off"] = merged[f"{prefix}_rolling_ppa_off"]
        df[f"{prefix}_rolling_ppa_def"] = merged[f"{prefix}_rolling_ppa_def"]
        df[f"{prefix}_games_played"] = merged[f"{prefix}_games_played"]

    # --- Difference features ---
    diff_features = []

    def add_diff(name, h_col, a_col):
        df[name] = df[h_col] - df[a_col]
        diff_features.append(name)

    add_diff("diff_prior_sp", "h_prior_sp", "a_prior_sp")
    add_diff("diff_prior_sp_off", "h_prior_sp_off", "a_prior_sp_off")
    add_diff("diff_prior_sp_def", "h_prior_sp_def", "a_prior_sp_def")
    add_diff("diff_prior_ppa_off", "h_prior_ppa_off", "a_prior_ppa_off")
    add_diff("diff_prior_ppa_def", "h_prior_ppa_def", "a_prior_ppa_def")
    add_diff("diff_returning_ppa", "h_returning_ppa", "a_returning_ppa")
    add_diff("diff_talent", "h_talent", "a_talent")
    add_diff("diff_new_coach", "h_new_coach", "a_new_coach")
    add_diff("diff_portal_net_stars", "h_portal_net_stars", "a_portal_net_stars")
    add_diff("diff_rolling_margin_3g", "h_rolling_margin_3g", "a_rolling_margin_3g")
    add_diff("diff_rolling_ppa_off", "h_rolling_ppa_off", "a_rolling_ppa_off")
    add_diff("diff_rolling_ppa_def", "h_rolling_ppa_def", "a_rolling_ppa_def")

    # Context features
    df["home_flag"] = (~df["neutral_site"]).astype(int)
    df["conf_game"] = df["conference_game"].astype(int)

    context_features = ["home_flag", "conf_game", "week"]
    all_features = diff_features + context_features

    # Impute missing rolling features with 0
    for f in diff_features:
        if "rolling" in f:
            df[f] = df[f].fillna(0)

    # Impute other missing with median
    for f in diff_features:
        if "rolling" not in f:
            med = df[f].median()
            if pd.isna(med):
                med = 0
            df[f] = df[f].fillna(med)

    print(f"\nFeature list ({len(all_features)} features):")
    for f in all_features:
        miss = df[f].isna().sum()
        print(f"  {f}: {miss} missing ({miss/len(df)*100:.1f}%)")

    print(f"\nFinal training sample: {len(df)} games")

    return df, all_features


# =========================================================================
# STEP 3 — MODEL BUILD
# =========================================================================

def train_model(df, features):
    from sklearn.linear_model import RidgeCV
    from sklearn.preprocessing import StandardScaler
    import joblib

    train = df[df["season"].isin(TRAIN_YEARS)].copy()
    val = df[df["season"].isin(VAL_YEARS)].copy()
    oos = df[df["season"].isin(OOS_YEARS)].copy()

    print(f"\nSplit sizes: Train={len(train)}, Validate={len(val)}, OOS={len(oos)}")

    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[features])
    X_val = scaler.transform(val[features])
    X_oos = scaler.transform(oos[features])

    y_train = train["actual_margin"].values
    y_val = val["actual_margin"].values
    y_oos = oos["actual_margin"].values

    model = RidgeCV(alphas=[1, 5, 10, 50, 100, 500], cv=5)
    model.fit(X_train, y_train)

    print(f"\nChosen alpha: {model.alpha_}")
    print(f"\nFeature coefficients:")
    for name, coef in sorted(zip(features, model.coef_), key=lambda x: -abs(x[1])):
        print(f"  {name:30s}: {coef:+.4f}")
    print(f"  {'intercept':30s}: {model.intercept_:+.4f}")

    # Predictions
    train["pred_margin"] = model.predict(X_train)
    val["pred_margin"] = model.predict(X_val)
    oos["pred_margin"] = model.predict(X_oos)

    # Save model
    model_dir = Path("ncaaf/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "base_ridge_v1.pkl"
    joblib.dump({"model": model, "scaler": scaler, "features": features}, model_path)
    print(f"\nModel saved to {model_path}")

    return model, scaler, train, val, oos


# =========================================================================
# STEP 4 — EVALUATION
# =========================================================================

def evaluate(train, val, oos, features):
    from scipy.stats import pearsonr

    results = {}

    for name, split in [("Train", train), ("Validate", val), ("OOS", oos)]:
        mae = np.abs(split["pred_margin"] - split["actual_margin"]).mean()
        rmse = np.sqrt(((split["pred_margin"] - split["actual_margin"])**2).mean())
        corr_actual = pearsonr(split["pred_margin"], split["actual_margin"])[0]

        has_spread = split["closing_spread"].notna()
        # CFBD spread: negative = home favored. Model margin: positive = home wins.
        # So market implied margin = -closing_spread. Correlate pred with market implied margin.
        corr_spread = pearsonr(split.loc[has_spread, "pred_margin"],
                               -split.loc[has_spread, "closing_spread"])[0] if has_spread.sum() > 10 else np.nan

        # Market MAE: market implied margin = -closing_spread
        # Market error = |actual_margin - (-closing_spread)| = |actual_margin + closing_spread|
        mkt_mae = np.abs(split.loc[has_spread, "actual_margin"] + split.loc[has_spread, "closing_spread"]).mean() if has_spread.sum() > 10 else np.nan

        results[name] = {
            "N": len(split),
            "MAE": mae,
            "RMSE": rmse,
            "Corr_Actual": corr_actual,
            "Corr_Spread": corr_spread,
            "Market_MAE": mkt_mae,
            "MAE_vs_Market": mae - mkt_mae if mkt_mae is not None and not np.isnan(mkt_mae) else np.nan,
        }

        print(f"\n--- {name} ({len(split)} games) ---")
        print(f"  MAE:           {mae:.2f}")
        print(f"  RMSE:          {rmse:.2f}")
        print(f"  Corr(pred,act): {corr_actual:.4f}")
        print(f"  Corr(pred,mkt): {corr_spread:.4f}" if not np.isnan(corr_spread) else "  Corr(pred,mkt): N/A")
        if not np.isnan(mkt_mae):
            print(f"  Market MAE:    {mkt_mae:.2f}")
            print(f"  MAE vs Market: {mae - mkt_mae:+.2f}")

    return results


def ats_analysis(df, label=""):
    """ATS analysis: when model disagrees with market by N+ points."""
    has = df[df["closing_spread"].notna()].copy()
    if len(has) < 10:
        return {}

    # Model spread = -pred_margin (negative of predicted margin in home perspective)
    # Closing spread: negative = home favored
    # ATS cover: actual_margin + closing_spread > 0 means home covered
    has["model_spread"] = -has["pred_margin"]
    has["ats_result"] = has["actual_margin"] + has["closing_spread"]  # >0 = home covers
    has["edge"] = has["closing_spread"] - has["model_spread"]  # positive = model thinks home is better than market

    # When model disagrees with market, bet the model's side
    results = {}
    for threshold in [0, 1, 2, 3]:
        # Model says home is better: edge > threshold → bet home to cover
        home_bets = has[has["edge"] > threshold]
        # Model says away is better: edge < -threshold → bet away to cover (home doesn't cover)
        away_bets = has[has["edge"] < -threshold]

        home_wins = (home_bets["ats_result"] > 0).sum()
        home_pushes = (home_bets["ats_result"] == 0).sum()
        away_wins = (away_bets["ats_result"] < 0).sum()
        away_pushes = (away_bets["ats_result"] == 0).sum()

        total_bets = len(home_bets) + len(away_bets)
        total_wins = home_wins + away_wins + 0.5 * (home_pushes + away_pushes)

        if total_bets > 0:
            hit_rate = total_wins / total_bets
            roi = hit_rate * 2 * (100/110) - 1  # at -110
            results[threshold] = {
                "n": total_bets,
                "wins": total_wins,
                "hit_rate": hit_rate,
                "roi": roi,
            }
            print(f"  {label} Edge>={threshold}: {total_bets} bets, {total_wins:.0f} wins, "
                  f"{hit_rate:.3f} ATS, ROI {roi:+.1%}")

    return results


def calibration_analysis(df):
    """Calibration by spread bucket."""
    has = df[df["closing_spread"].notna()].copy()
    if len(has) < 10:
        return pd.DataFrame()

    has["market_implied_margin"] = -has["closing_spread"]
    bins = [-999, -21, -14, -7, -3, 3, 7, 14, 21, 999]
    labels = ["<-21", "-21:-14", "-14:-7", "-7:-3", "-3:3", "3:7", "7:14", "14:21", ">21"]
    has["spread_bucket"] = pd.cut(has["closing_spread"], bins=bins, labels=labels)

    cal = has.groupby("spread_bucket", observed=False).agg(
        n=("actual_margin", "size"),
        mean_pred=("pred_margin", "mean"),
        mean_actual=("actual_margin", "mean"),
        mean_market=("market_implied_margin", "mean"),
    ).reset_index()
    cal["pred_vs_actual"] = cal["mean_pred"] - cal["mean_actual"]

    print("\nCalibration by spread bucket:")
    print(cal.to_string(index=False))
    return cal


def season_stability(df):
    """MAE per season."""
    from scipy.stats import pearsonr
    print("\nSeason stability:")
    records = []
    for yr in sorted(df["season"].unique()):
        sub = df[df["season"] == yr]
        mae = np.abs(sub["pred_margin"] - sub["actual_margin"]).mean()
        corr = pearsonr(sub["pred_margin"], sub["actual_margin"])[0]
        records.append({"season": yr, "n": len(sub), "MAE": mae, "Corr": corr})
        print(f"  {yr}: n={len(sub)}, MAE={mae:.2f}, Corr={corr:.4f}")
    return pd.DataFrame(records)


def split_analysis(df):
    """Splits: home/away/neutral, P5/G5, fav/dog, early/late, conf/non-conf."""
    from scipy.stats import pearsonr

    splits = {}

    # Home vs Away vs Neutral
    print("\n--- Home vs Away vs Neutral ---")
    for label, mask in [
        ("Home (non-neutral)", df["home_flag"] == 1),
        ("Neutral", df["home_flag"] == 0),
    ]:
        sub = df[mask]
        if len(sub) < 10:
            continue
        mae = np.abs(sub["pred_margin"] - sub["actual_margin"]).mean()
        corr = pearsonr(sub["pred_margin"], sub["actual_margin"])[0]
        print(f"  {label}: n={len(sub)}, MAE={mae:.2f}, Corr={corr:.4f}")
        splits[label] = {"n": len(sub), "MAE": mae, "Corr": corr}

    # P5 vs G5
    print("\n--- P5 vs G5 (both teams) ---")
    for label, mask in [
        ("Both P5", (df["home_conference"].isin(P5_CONFERENCES)) & (df["away_conference"].isin(P5_CONFERENCES))),
        ("Both G5", (~df["home_conference"].isin(P5_CONFERENCES)) & (~df["away_conference"].isin(P5_CONFERENCES))),
        ("P5 vs G5", (df["home_conference"].isin(P5_CONFERENCES)) != (df["away_conference"].isin(P5_CONFERENCES))),
    ]:
        sub = df[mask]
        if len(sub) < 10:
            continue
        mae = np.abs(sub["pred_margin"] - sub["actual_margin"]).mean()
        corr = pearsonr(sub["pred_margin"], sub["actual_margin"])[0]
        print(f"  {label}: n={len(sub)}, MAE={mae:.2f}, Corr={corr:.4f}")
        splits[label] = {"n": len(sub), "MAE": mae, "Corr": corr}

    # Favorites vs Underdogs
    print("\n--- Favorites vs Underdogs ---")
    has = df[df["closing_spread"].notna()].copy()
    for label, mask in [
        ("Favorites (spread < -3)", has["closing_spread"] < -3),
        ("Pick'em (-3 to 3)", (has["closing_spread"] >= -3) & (has["closing_spread"] <= 3)),
        ("Underdogs (spread > 3)", has["closing_spread"] > 3),
    ]:
        sub = has[mask]
        if len(sub) < 10:
            continue
        mae = np.abs(sub["pred_margin"] - sub["actual_margin"]).mean()
        corr = pearsonr(sub["pred_margin"], sub["actual_margin"])[0] if len(sub) > 10 else np.nan
        print(f"  {label}: n={len(sub)}, MAE={mae:.2f}, Corr={corr:.4f}")
        splits[label] = {"n": len(sub), "MAE": mae, "Corr": corr}

    # Weeks 1-4 vs 5+
    print("\n--- Early vs Late Season ---")
    for label, mask in [
        ("Weeks 1-4", df["week"] <= 4),
        ("Weeks 5+", df["week"] > 4),
    ]:
        sub = df[mask]
        if len(sub) < 10:
            continue
        mae = np.abs(sub["pred_margin"] - sub["actual_margin"]).mean()
        corr = pearsonr(sub["pred_margin"], sub["actual_margin"])[0]
        print(f"  {label}: n={len(sub)}, MAE={mae:.2f}, Corr={corr:.4f}")
        splits[label] = {"n": len(sub), "MAE": mae, "Corr": corr}

    # Conference vs Non-conference
    print("\n--- Conference vs Non-Conference ---")
    for label, mask in [
        ("Conference", df["conf_game"] == 1),
        ("Non-Conference", df["conf_game"] == 0),
    ]:
        sub = df[mask]
        if len(sub) < 10:
            continue
        mae = np.abs(sub["pred_margin"] - sub["actual_margin"]).mean()
        corr = pearsonr(sub["pred_margin"], sub["actual_margin"])[0]
        print(f"  {label}: n={len(sub)}, MAE={mae:.2f}, Corr={corr:.4f}")
        splits[label] = {"n": len(sub), "MAE": mae, "Corr": corr}

    return splits


# =========================================================================
# STEP 5 — WRITE REPORT
# =========================================================================

def write_report(results, ats_results, calibration, stability, splits, features, model, train, val, oos):
    report_path = Path("research/ncaaf_base/phase2_base_engine_results.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# NCAAF Base Spread Engine — Phase 2 Results\n")
    lines.append(f"**Date:** 2026-04-08\n")
    lines.append(f"**Model:** Ridge regression (alpha={model.alpha_})\n")
    lines.append(f"**Features:** {len(features)}\n")
    lines.append(f"**Train:** {len(train)} games (2022-2023)")
    lines.append(f"**Validate:** {len(val)} games (2024)")
    lines.append(f"**OOS:** {len(oos)} games (2025)\n")

    lines.append("---\n")
    lines.append("## Feature Coefficients\n")
    lines.append("| Feature | Coefficient |")
    lines.append("|---------|------------|")
    for name, coef in sorted(zip(features, model.coef_), key=lambda x: -abs(x[1])):
        lines.append(f"| {name} | {coef:+.4f} |")
    lines.append(f"| intercept | {model.intercept_:+.4f} |")

    lines.append("\n---\n")
    lines.append("## Primary Metrics\n")
    lines.append("| Split | N | MAE | RMSE | Corr(pred,actual) | Corr(pred,spread) | Market MAE | MAE vs Market |")
    lines.append("|-------|---|-----|------|-------------------|-------------------|------------|--------------|")
    for name in ["Train", "Validate", "OOS"]:
        r = results[name]
        lines.append(f"| {name} | {r['N']} | {r['MAE']:.2f} | {r['RMSE']:.2f} | "
                     f"{r['Corr_Actual']:.4f} | {r['Corr_Spread']:.4f} | "
                     f"{r['Market_MAE']:.2f} | {r['MAE_vs_Market']:+.2f} |")

    lines.append("\n---\n")
    lines.append("## ATS Analysis (OOS 2025)\n")
    lines.append("| Edge Threshold | N Bets | Wins | Hit Rate | ROI (-110) |")
    lines.append("|----------------|--------|------|----------|------------|")
    for thr, r in sorted(ats_results.get("OOS", {}).items()):
        lines.append(f"| >= {thr} | {r['n']} | {r['wins']:.0f} | {r['hit_rate']:.3f} | {r['roi']:+.1%} |")

    lines.append("\n### ATS by Split\n")
    lines.append("| Split | Edge Threshold | N Bets | Wins | Hit Rate | ROI (-110) |")
    lines.append("|-------|----------------|--------|------|----------|------------|")
    for split_name in ["Train", "Validate", "OOS"]:
        for thr, r in sorted(ats_results.get(split_name, {}).items()):
            lines.append(f"| {split_name} | >= {thr} | {r['n']} | {r['wins']:.0f} | {r['hit_rate']:.3f} | {r['roi']:+.1%} |")

    lines.append("\n---\n")
    lines.append("## Calibration by Spread Bucket\n")
    if not calibration.empty:
        lines.append("| Bucket | N | Mean Pred | Mean Actual | Mean Market | Pred-Actual |")
        lines.append("|--------|---|-----------|-------------|-------------|-------------|")
        for _, row in calibration.iterrows():
            lines.append(f"| {row['spread_bucket']} | {row['n']} | {row['mean_pred']:.1f} | "
                         f"{row['mean_actual']:.1f} | {row['mean_market']:.1f} | {row['pred_vs_actual']:+.1f} |")

    lines.append("\n---\n")
    lines.append("## Season Stability\n")
    lines.append("| Season | N | MAE | Correlation |")
    lines.append("|--------|---|-----|------------|")
    for _, row in stability.iterrows():
        lines.append(f"| {int(row['season'])} | {int(row['n'])} | {row['MAE']:.2f} | {row['Corr']:.4f} |")

    lines.append("\n---\n")
    lines.append("## Splits\n")
    lines.append("| Split | N | MAE | Correlation |")
    lines.append("|-------|---|-----|------------|")
    for name, s in splits.items():
        corr_str = f"{s['Corr']:.4f}" if not np.isnan(s.get('Corr', np.nan)) else "N/A"
        lines.append(f"| {name} | {s['n']} | {s['MAE']:.2f} | {corr_str} |")

    lines.append("\n---\n")
    lines.append("## Verdict\n")

    # Determine verdict
    oos_r = results["OOS"]
    mae_ok = oos_r["MAE"] < 14
    corr_ok = oos_r["Corr_Actual"] > 0.40
    # Check season stability
    max_mae = stability["MAE"].max()
    min_mae = stability["MAE"].min()
    stable = (max_mae - min_mae) < 3.0

    if mae_ok and corr_ok and stable:
        verdict = "ADVANCE"
        reason = (f"OOS MAE={oos_r['MAE']:.2f} (< 14), Corr={oos_r['Corr_Actual']:.4f} (> 0.40), "
                  f"season MAE range {min_mae:.2f}-{max_mae:.2f} (stable). "
                  f"Engine meets all thresholds for overlay development.")
    elif (mae_ok or corr_ok) and not (mae_ok and corr_ok and stable):
        verdict = "NEAR MISS"
        reason = (f"OOS MAE={oos_r['MAE']:.2f} ({'OK' if mae_ok else 'HIGH'}), "
                  f"Corr={oos_r['Corr_Actual']:.4f} ({'OK' if corr_ok else 'LOW'}), "
                  f"season stability {'OK' if stable else 'UNSTABLE'}. "
                  f"One or more criteria borderline; targeted improvements may resolve.")
    else:
        verdict = "CLOSE"
        reason = f"OOS MAE={oos_r['MAE']:.2f}, Corr={oos_r['Corr_Actual']:.4f}. Fundamental issues."

    lines.append(f"**{verdict}**\n")
    lines.append(f"{reason}\n")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport written to {report_path}")

    return verdict, reason


# =========================================================================
# MAIN
# =========================================================================

def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root

    print("=" * 60)
    print("STEP 1 — PULLING DATA FROM CFBD API")
    print("=" * 60)

    # Need prior year data too (2021) for prior-year features in 2022
    all_seasons = [2021] + SEASONS

    print("\nPulling games...")
    games_df = pull_games(SEASONS)

    print("\nPulling lines...")
    lines_df = pull_lines(SEASONS)

    print("\nPulling SP+ ratings...")
    sp_df = pull_sp_ratings(all_seasons)

    print("\nPulling advanced stats...")
    adv_df = pull_advanced_stats(all_seasons)

    print("\nPulling returning production...")
    returning_df = pull_returning(SEASONS)

    print("\nPulling talent composites...")
    talent_df = pull_talent(SEASONS)

    print("\nPulling coaching data...")
    coaches_df = pull_coaches(all_seasons)

    print("\nPulling game-level advanced stats (for rolling features)...")
    game_adv_df = pull_game_advanced(SEASONS)

    print("\nPulling portal data...")
    portal_df = pull_portal(SEASONS)

    # Build canonical table
    print("\n" + "=" * 60)
    print("Building canonical table...")
    canonical = build_canonical(games_df, lines_df)

    print("\n" + "=" * 60)
    print("STEP 2 — FEATURE ENGINEERING")
    print("=" * 60)

    coach_cont = build_coach_continuity(coaches_df)
    portal_stars = build_portal_net_stars(portal_df)

    print("\nBuilding rolling features...")
    rolling = build_rolling_features(canonical, game_adv_df)

    print("\nEngineering difference features...")
    featured_df, features = engineer_features(
        canonical, sp_df, adv_df, returning_df, talent_df,
        coach_cont, portal_stars, rolling
    )

    # Save canonical table
    data_dir = Path("ncaaf/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = data_dir / "ncaaf_canonical_2022_2025.parquet"
    featured_df.to_parquet(canonical_path, index=False)
    print(f"\nCanonical table saved to {canonical_path}")

    print("\n" + "=" * 60)
    print("STEP 3 — MODEL BUILD")
    print("=" * 60)

    model, scaler, train, val, oos = train_model(featured_df, features)

    print("\n" + "=" * 60)
    print("STEP 4 — EVALUATION")
    print("=" * 60)

    results = evaluate(train, val, oos, features)

    # Combine all splits for overall analysis
    all_data = pd.concat([train, val, oos])

    # ATS analysis
    ats_results = {}
    for name, split in [("Train", train), ("Validate", val), ("OOS", oos)]:
        print(f"\nATS — {name}:")
        ats_results[name] = ats_analysis(split, label=name)

    # Calibration (on all data with spreads)
    calibration = calibration_analysis(all_data)

    # Season stability
    stability = season_stability(all_data)

    # Splits (on OOS)
    print("\n--- Splits (OOS 2025) ---")
    splits = split_analysis(oos)

    print("\n" + "=" * 60)
    print("STEP 5 — WRITE REPORT")
    print("=" * 60)

    verdict, reason = write_report(results, ats_results, calibration, stability, splits,
                                   features, model, train, val, oos)

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"\nFiles created:")
    print(f"  ncaaf/data/ncaaf_canonical_2022_2025.parquet")
    print(f"  ncaaf/models/base_ridge_v1.pkl")
    print(f"  research/ncaaf_base/phase2_base_engine_results.md")

    print(f"\nFeature list ({len(features)}):")
    for f in features:
        print(f"  {f}")

    print(f"\nSample sizes: Train={len(train)}, Validate={len(val)}, OOS={len(oos)}")

    print(f"\nVerdict: {verdict}")
    print(f"{reason}")


if __name__ == "__main__":
    main()
