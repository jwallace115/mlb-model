#!/usr/bin/env python3
"""
Point-in-time team and goalie ratings for the NHL sim engine.

Team ratings: per-strength-state rates (attempts, xG) using ONLY games strictly before the game date.
Goalie ratings: GSAx per attempt, shrunk with measured K.
All stabilised with split-half measured K; season carry-over with measured regression weight.

Output: nhl/data/sim/ratings/team_ratings.parquet, goalie_ratings.parquet
"""
import argparse, gzip, hashlib, json, sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
BOX_DIR = ROOT / "nhl" / "cache"
XG_PATH = ROOT / "nhl" / "data" / "sim" / "xg_v2.json"
CONST_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v2.json"
OUT_DIR = ROOT / "nhl" / "data" / "sim" / "ratings"

GAMES_PER_SEASON = 1312
FIT_SEASONS = [2021, 2022]
ALL_SEASONS = [2021, 2022, 2023, 2024, 2025]

# Strength states for per-team rating
EVEN_STATES = ["5v5"]
PP_STATES = ["5v4", "5v3", "4v3"]
PK_STATES = ["4v5", "3v5", "3v4"]


def load_xg_model():
    """Load xG v2 coefficients for scoring shots."""
    with open(XG_PATH) as f:
        model = json.load(f)
    return model


def load_constants():
    with open(CONST_PATH) as f:
        return json.load(f)


def score_xg(shots_df, model):
    """Score each shot with xG v2 probability."""
    features = model["features"]
    coefs = model["coefficients"]
    intercept = model["intercept"]

    # Build feature columns (same as fit_xg.py featurise)
    STRENGTH_GROUPS = {"5v5": "even", "4v4": "even", "3v3": "3v3",
                       "5v4": "PP", "5v3": "PP", "4v3": "PP",
                       "4v5": "PK", "3v5": "PK", "3v4": "PK"}
    df = shots_df.copy()
    df["strength_group"] = df["strength"].map(STRENGTH_GROUPS).fillna("other")

    shot_types = ["wrist", "slap", "snap", "backhand", "tip-in", "deflected", "wrap-around", "cradle"]
    for st in shot_types:
        df[f"st_{st}"] = (df["shot_type"] == st).astype(int)
    for sg in ["PP", "PK", "3v3"]:
        df[f"sg_{sg}"] = (df["strength_group"] == sg).astype(int)

    X = df[features].fillna(0).values.astype(float)
    logit = intercept + X @ np.array([coefs[f] for f in features])
    xg = 1 / (1 + np.exp(-logit))
    return xg


def get_game_dates(seasons):
    """Get game dates and team info from boxscores."""
    games = []
    for s in seasons:
        for i in range(1, GAMES_PER_SEASON + 1):
            gid = f"{s}02{i:04d}"
            bp = BOX_DIR / f"boxscore_{gid}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            date_str = d.get("gameDate", "")
            home = d.get("homeTeam", {}).get("abbrev", "")
            away = d.get("awayTeam", {}).get("abbrev", "")
            home_score = d.get("homeTeam", {}).get("score", 0)
            away_score = d.get("awayTeam", {}).get("score", 0)
            outcome = d.get("gameOutcome", {}).get("lastPeriodType", "REG")
            games.append({
                "game_id": gid, "season": s, "date": date_str,
                "home": home, "away": away,
                "home_score": home_score, "away_score": away_score,
                "outcome": outcome,
            })
    return pd.DataFrame(games)


def compute_split_half_r(team_stats_df, stat_col, min_games=40):
    """Split-half reliability: odd vs even games, return correlation."""
    df = team_stats_df.copy()
    df["game_num"] = df.groupby("team").cumcount() + 1
    df["half"] = df["game_num"] % 2  # 0=even, 1=odd

    halves = {}
    for h in [0, 1]:
        hdf = df[df["half"] == h]
        g = hdf.groupby("team").agg(
            val=(stat_col, "mean"),
            n=(stat_col, "count"),
        )
        g = g[g["n"] >= min_games // 2]
        halves[h] = g["val"]

    both = pd.DataFrame({"odd": halves.get(1, pd.Series()), "even": halves.get(0, pd.Series())}).dropna()
    if len(both) < 5:
        return 0.0, 0
    r = both["odd"].corr(both["even"])
    return r, len(both)


def compute_K(r, n_avg):
    """Regression-to-mean constant K = n(1-r)/r."""
    if r <= 0:
        return 1e6  # full regression
    return n_avg * (1 - r) / r


def shrink(total, n, league_mean, K):
    """Bayesian shrinkage: (total + K * league_mean) / (n + K)."""
    return (total + K * league_mean) / (n + K)


def build_team_ratings(games_df, shots_all, state_all, constants):
    """Build point-in-time team ratings. Each game uses ONLY strictly-before data."""
    model = load_xg_model()

    # Score all shots with xG
    shots_all = shots_all.copy()
    non_en = shots_all[~shots_all["empty_net"]].copy()
    non_en["xg"] = score_xg(non_en, model)
    shots_all = shots_all.merge(non_en[["game_id", "period", "seconds", "shooting_team", "xg"]],
                                 on=["game_id", "period", "seconds", "shooting_team"],
                                 how="left")
    shots_all["xg"] = shots_all["xg"].fillna(0)

    # Get game dates for ordering
    games_df = games_df.sort_values("date").reset_index(drop=True)

    # Build per-game per-team stats
    team_game_stats = []
    for _, g in games_df.iterrows():
        gid = g["game_id"]
        g_shots = shots_all[shots_all["game_id"] == gid]
        g_state = state_all[state_all["game_id"] == gid]

        for team, role in [(g["home"], "home"), (g["away"], "away")]:
            opp = g["away"] if role == "home" else g["home"]

            # 5v5 stats
            ev_for = g_shots[(g_shots["shooting_team"] == role) & (g_shots["strength"].isin(EVEN_STATES))]
            ev_against = g_shots[(g_shots["shooting_team"] != role) & (g_shots["strength"].isin(EVEN_STATES))]
            ev_secs = g_state[g_state.apply(lambda r: f"{r['home_skaters']}v{r['away_skaters']}" in EVEN_STATES, axis=1)]["duration"].sum()

            # PP stats (own PP = when this team has more skaters)
            if role == "home":
                pp_secs = g_state[g_state.apply(lambda r: f"{r['home_skaters']}v{r['away_skaters']}" in PP_STATES, axis=1)]["duration"].sum()
                pk_secs = g_state[g_state.apply(lambda r: f"{r['home_skaters']}v{r['away_skaters']}" in PK_STATES, axis=1)]["duration"].sum()
            else:
                pp_secs = g_state[g_state.apply(lambda r: f"{r['away_skaters']}v{r['home_skaters']}" in PP_STATES, axis=1)]["duration"].sum()
                pk_secs = g_state[g_state.apply(lambda r: f"{r['away_skaters']}v{r['home_skaters']}" in PK_STATES, axis=1)]["duration"].sum()

            pp_for = g_shots[(g_shots["shooting_team"] == role) & (g_shots["strength"].isin(PP_STATES))]
            pk_against = g_shots[(g_shots["shooting_team"] != role) & (g_shots["strength"].isin(PP_STATES))]

            # Penalties
            g_pens = pd.DataFrame()  # simplified; use penalty table later

            team_game_stats.append({
                "game_id": gid, "season": g["season"], "date": g["date"],
                "team": team, "opponent": opp, "role": role,
                "ev_att_for": len(ev_for),
                "ev_att_against": len(ev_against),
                "ev_xg_for": ev_for["xg"].sum() if len(ev_for) else 0,
                "ev_xg_against": ev_against["xg"].sum() if len(ev_against) else 0,
                "ev_goals_for": ev_for["is_goal"].sum() if len(ev_for) else 0,
                "ev_goals_against": ev_against["is_goal"].sum() if len(ev_against) else 0,
                "ev_seconds": ev_secs,
                "pp_att_for": len(pp_for),
                "pp_xg_for": pp_for["xg"].sum() if len(pp_for) else 0,
                "pp_seconds": pp_secs,
                "pk_att_against": len(pk_against),
                "pk_xg_against": pk_against["xg"].sum() if len(pk_against) else 0,
                "pk_seconds": pk_secs,
            })

    tgs = pd.DataFrame(team_game_stats)
    return tgs


def compute_pit_ratings(tgs, fit_seasons=None):
    """Compute point-in-time ratings for each team-game using only prior data.
    Returns one row per team per game with the rating going INTO that game."""
    tgs = tgs.sort_values("date").reset_index(drop=True)

    # Split-half reliability on fit seasons only
    if fit_seasons:
        fit_data = tgs[tgs["season"].isin(fit_seasons)]
    else:
        fit_data = tgs

    # Measure reliability for key stats
    reliabilities = {}
    for stat in ["ev_att_share", "ev_xg_per_att_for"]:
        if stat == "ev_att_share":
            fit_data_copy = fit_data.copy()
            fit_data_copy["ev_att_share"] = fit_data_copy["ev_att_for"] / (fit_data_copy["ev_att_for"] + fit_data_copy["ev_att_against"]).clip(1)
            r, n = compute_split_half_r(fit_data_copy, "ev_att_share")
        elif stat == "ev_xg_per_att_for":
            fit_data_copy = fit_data.copy()
            fit_data_copy["ev_xg_per_att_for"] = fit_data_copy["ev_xg_for"] / fit_data_copy["ev_att_for"].clip(1)
            r, n = compute_split_half_r(fit_data_copy, "ev_xg_per_att_for")
        reliabilities[stat] = {"r": r, "n_teams": n}

    print(f"\nSplit-half reliabilities (fit seasons, min 40 games/half):")
    for stat, vals in reliabilities.items():
        K = compute_K(vals["r"], 82)  # ~82 games per season
        print(f"  {stat}: r={vals['r']:.3f}, K={K:.1f}, n_teams={vals['n_teams']}")

    # Build point-in-time ratings
    # For each game, use all STRICTLY BEFORE games for that team
    league_means = {
        "ev_att_per_60_for": tgs["ev_att_for"].sum() / tgs["ev_seconds"].sum() * 3600 if tgs["ev_seconds"].sum() > 0 else 42,
        "ev_att_per_60_against": tgs["ev_att_against"].sum() / tgs["ev_seconds"].sum() * 3600 if tgs["ev_seconds"].sum() > 0 else 42,
        "ev_xg_per_att_for": tgs["ev_xg_for"].sum() / tgs["ev_att_for"].sum() if tgs["ev_att_for"].sum() > 0 else 0.06,
        "ev_xg_per_att_against": tgs["ev_xg_against"].sum() / tgs["ev_att_against"].sum() if tgs["ev_att_against"].sum() > 0 else 0.06,
    }

    # K values
    K_att_share = compute_K(reliabilities.get("ev_att_share", {}).get("r", 0.5), 82)
    K_xg = compute_K(reliabilities.get("ev_xg_per_att_for", {}).get("r", 0.3), 82)

    ratings = []
    # Group by team, process chronologically
    for team in tgs["team"].unique():
        team_games = tgs[tgs["team"] == team].sort_values("date")
        cum_ev_att_for = 0
        cum_ev_att_against = 0
        cum_ev_xg_for = 0.0
        cum_ev_xg_against = 0.0
        cum_ev_secs = 0.0
        n_games = 0

        for _, g in team_games.iterrows():
            # Rating GOING INTO this game (using strictly-before data)
            if n_games == 0:
                # First game: league mean
                r_att_for = league_means["ev_att_per_60_for"]
                r_att_against = league_means["ev_att_per_60_against"]
                r_xg_for = league_means["ev_xg_per_att_for"]
                r_xg_against = league_means["ev_xg_per_att_against"]
            else:
                team_att_for_per60 = cum_ev_att_for / cum_ev_secs * 3600 if cum_ev_secs > 0 else league_means["ev_att_per_60_for"]
                team_att_against_per60 = cum_ev_att_against / cum_ev_secs * 3600 if cum_ev_secs > 0 else league_means["ev_att_per_60_against"]
                team_xg_for = cum_ev_xg_for / cum_ev_att_for if cum_ev_att_for > 0 else league_means["ev_xg_per_att_for"]
                team_xg_against = cum_ev_xg_against / cum_ev_att_against if cum_ev_att_against > 0 else league_means["ev_xg_per_att_against"]

                r_att_for = shrink(team_att_for_per60 * n_games, n_games, league_means["ev_att_per_60_for"], K_att_share)
                r_att_against = shrink(team_att_against_per60 * n_games, n_games, league_means["ev_att_per_60_against"], K_att_share)
                r_xg_for = shrink(team_xg_for * n_games, n_games, league_means["ev_xg_per_att_for"], K_xg)
                r_xg_against = shrink(team_xg_against * n_games, n_games, league_means["ev_xg_per_att_against"], K_xg)

            ratings.append({
                "game_id": g["game_id"], "season": g["season"], "date": g["date"],
                "team": team, "role": g["role"],
                "n_prior_games": n_games,
                "ev_att_for_per60": round(r_att_for, 2),
                "ev_att_against_per60": round(r_att_against, 2),
                "ev_xg_per_att_for": round(r_xg_for, 5),
                "ev_xg_per_att_against": round(r_xg_against, 5),
            })

            # Update cumulative stats AFTER recording the rating
            cum_ev_att_for += g["ev_att_for"]
            cum_ev_att_against += g["ev_att_against"]
            cum_ev_xg_for += g["ev_xg_for"]
            cum_ev_xg_against += g["ev_xg_against"]
            cum_ev_secs += g["ev_seconds"]
            n_games += 1

    return pd.DataFrame(ratings), reliabilities


def build_goalie_ratings(shots_all, games_df, model):
    """Build point-in-time goalie ratings: GSAx per attempt faced."""
    # Score shots with xG
    non_en = shots_all[~shots_all["empty_net"]].copy()
    non_en["xg"] = score_xg(non_en, model)

    # Per-game goalie stats: goalie = goalie_id on the first shot against
    goalie_games = []
    for _, g in games_df.iterrows():
        gid = g["game_id"]
        g_shots = non_en[non_en["game_id"] == gid]

        # Home goalie: first shot by away team
        away_shots = g_shots[g_shots["shooting_team"] == "away"].sort_values("seconds")
        if len(away_shots):
            home_goalie = away_shots.iloc[0].get("goalie_id")
            if home_goalie and not pd.isna(home_goalie):
                h_faced = g_shots[(g_shots["shooting_team"] == "away")]
                h_xg = h_faced["xg"].sum()
                h_goals = h_faced["is_goal"].sum()
                goalie_games.append({
                    "game_id": gid, "season": g["season"], "date": g["date"],
                    "goalie_id": int(home_goalie), "team": g["home"],
                    "attempts_faced": len(h_faced),
                    "xg_faced": h_xg,
                    "goals_against": int(h_goals),
                    "gsax": h_xg - h_goals,  # positive = saved more than expected
                })

        # Away goalie
        home_shots = g_shots[g_shots["shooting_team"] == "home"].sort_values("seconds")
        if len(home_shots):
            away_goalie = home_shots.iloc[0].get("goalie_id")
            if away_goalie and not pd.isna(away_goalie):
                a_faced = g_shots[(g_shots["shooting_team"] == "home")]
                a_xg = a_faced["xg"].sum()
                a_goals = a_faced["is_goal"].sum()
                goalie_games.append({
                    "game_id": gid, "season": g["season"], "date": g["date"],
                    "goalie_id": int(away_goalie), "team": g["away"],
                    "attempts_faced": len(a_faced),
                    "xg_faced": a_xg,
                    "goals_against": int(a_goals),
                    "gsax": a_xg - a_goals,
                })

    gdf = pd.DataFrame(goalie_games).sort_values("date")

    # Split-half reliability for GSAx/attempt
    gdf["gsax_per_att"] = gdf["gsax"] / gdf["attempts_faced"].clip(1)
    fit_data = gdf[gdf["season"].isin(FIT_SEASONS)]
    fit_sh = fit_data[["goalie_id", "gsax_per_att"]].copy()
    fit_sh = fit_sh.rename(columns={"goalie_id": "team"})
    r_goalie, n_goalies = compute_split_half_r(fit_sh, "gsax_per_att", min_games=20)
    K_goalie = compute_K(r_goalie, 60)  # ~60 starts per season for a starter

    print(f"\nGoalie GSAx/attempt split-half r: {r_goalie:.3f} (n_goalies={n_goalies})")
    print(f"  K_goalie: {K_goalie:.1f}")

    # Point-in-time ratings
    goalie_ratings = []
    for goalie_id in gdf["goalie_id"].unique():
        g_games = gdf[gdf["goalie_id"] == goalie_id].sort_values("date")
        cum_gsax = 0.0
        cum_att = 0
        n = 0

        for _, gg in g_games.iterrows():
            if n == 0:
                rating = 0.0  # league average
            else:
                raw = cum_gsax / cum_att if cum_att > 0 else 0.0
                rating = shrink(raw * n, n, 0.0, K_goalie)

            goalie_ratings.append({
                "game_id": gg["game_id"], "season": gg["season"], "date": gg["date"],
                "goalie_id": goalie_id, "team": gg["team"],
                "n_prior_starts": n,
                "gsax_per_att_rating": round(rating, 5),
            })

            cum_gsax += gg["gsax"]
            cum_att += gg["attempts_faced"]
            n += 1

    return pd.DataFrame(goalie_ratings), r_goalie, K_goalie


def league_finishing_term(shots_all, games_df, model):
    """Goals / xG v2 over the previous 30 days of games, by date."""
    non_en = shots_all[~shots_all["empty_net"]].copy()
    non_en["xg"] = score_xg(non_en, model)
    game_dates = games_df[["game_id", "date", "season"]].drop_duplicates("game_id")
    non_en = non_en.merge(game_dates, on="game_id", how="left", suffixes=("", "_gd"))
    if "date" not in non_en.columns:
        non_en["date"] = non_en["date_gd"]
    if "season" not in non_en.columns or non_en["season"].isna().all():
        non_en["season"] = non_en["season_gd"]

    # By month
    non_en["month"] = non_en["date"].str[:7]
    monthly = non_en.groupby(["season", "month"]).agg(
        goals=("is_goal", "sum"), xg=("xg", "sum"), n=("is_goal", "count")
    )
    monthly["ratio"] = monthly["goals"] / monthly["xg"]
    print("\nLeague finishing term (goals/xG) by month:")
    for (s, m), r in monthly.iterrows():
        print(f"  {s} {m}: {r['ratio']:.3f} (goals={int(r['goals'])}, xg={r['xg']:.0f})")

    return monthly


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("Loading data...")
    games_df = get_game_dates(ALL_SEASONS)
    print(f"  Games: {len(games_df)}")

    shots_all = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "shots.parquet") for s in ALL_SEASONS], ignore_index=True)
    state_all = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "state_time.parquet") for s in ALL_SEASONS], ignore_index=True)
    print(f"  Shots: {len(shots_all)}, State spans: {len(state_all)}")

    # Add game date to shots for merging
    shots_all = shots_all.merge(games_df[["game_id", "date", "season"]].drop_duplicates("game_id"),
                                 on="game_id", how="left")
    state_all = state_all.merge(games_df[["game_id", "date", "season"]].drop_duplicates("game_id"),
                                on="game_id", how="left")

    print("\nBuilding team game stats...")
    tgs = build_team_ratings(games_df, shots_all, state_all, load_constants())
    print(f"  Team-game rows: {len(tgs)}")

    print("\nComputing point-in-time team ratings...")
    team_ratings, reliabilities = compute_pit_ratings(tgs, fit_seasons=FIT_SEASONS)
    print(f"  Rating rows: {len(team_ratings)}")

    print("\nBuilding goalie ratings...")
    model = load_xg_model()
    goalie_ratings, r_goalie, K_goalie = build_goalie_ratings(shots_all, games_df, model)
    print(f"  Goalie rating rows: {len(goalie_ratings)}")

    # League finishing term
    monthly = league_finishing_term(shots_all, games_df, model)

    if args.dry_run:
        print("--dry-run: not saving"); return

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    team_ratings.to_parquet(OUT_DIR / "team_ratings.parquet", index=False)
    goalie_ratings.to_parquet(OUT_DIR / "goalie_ratings.parquet", index=False)
    print(f"\nSaved: {OUT_DIR / 'team_ratings.parquet'} ({len(team_ratings)} rows)")
    print(f"Saved: {OUT_DIR / 'goalie_ratings.parquet'} ({len(goalie_ratings)} rows)")


if __name__ == "__main__":
    main()
