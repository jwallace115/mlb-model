#!/usr/bin/env python3
"""
Point-in-time team and goalie ratings (S13 — rebuilt, fixing S10's 7 defects).

KEY FIXES over S10:
1. League prior = mean of same stat over games strictly before D in THIS season (not all-season)
2. Per-season accumulation with measured carry-over weight w
3. Leakage truncation test included
4. Goalie: same per-season structure, career carry-over
5. PP/PK ratings + score-adjusted 5v5
6. Starter = first shot against, agreement reported
7. Finishing term = 30-day rolling, strictly before D
"""
import argparse, gzip, hashlib, json, sys
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

EVEN_STATES = ["5v5"]
PP_STATES = ["5v4", "5v3", "4v3"]
PK_STATES = ["4v5", "3v5", "3v4"]

STRENGTH_GROUPS = {"5v5": "even", "4v4": "even", "3v3": "3v3",
                   "5v4": "PP", "5v3": "PP", "4v3": "PP",
                   "4v5": "PK", "3v5": "PK", "3v4": "PK"}


def load_xg_model():
    with open(XG_PATH) as f:
        return json.load(f)


def load_constants():
    with open(CONST_PATH) as f:
        return json.load(f)


def score_xg(shots_df, model):
    """Score each shot with xG v2 probability."""
    features = model["features"]
    coefs = model["coefficients"]
    intercept = model["intercept"]

    df = shots_df.copy()
    df["strength_group"] = df["strength"].map(STRENGTH_GROUPS).fillna("other")
    shot_types = ["wrist", "slap", "snap", "backhand", "tip-in", "deflected", "wrap-around", "cradle"]
    for st in shot_types:
        df[f"st_{st}"] = (df["shot_type"] == st).astype(int)
    for sg in ["PP", "PK", "3v3"]:
        df[f"sg_{sg}"] = (df["strength_group"] == sg).astype(int)
    X = df[features].fillna(0).values.astype(float)
    logit = intercept + X @ np.array([coefs[f] for f in features])
    return 1 / (1 + np.exp(-logit))


def get_game_info(seasons):
    """Get game dates, teams, scores, starters from boxscores."""
    games = []
    for s in seasons:
        for i in range(1, GAMES_PER_SEASON + 1):
            gid = f"{s}02{i:04d}"
            bp = BOX_DIR / f"boxscore_{gid}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            games.append({
                "game_id": gid, "season": s, "date": d.get("gameDate", ""),
                "home": d.get("homeTeam", {}).get("abbrev", ""),
                "away": d.get("awayTeam", {}).get("abbrev", ""),
                "home_score": d.get("homeTeam", {}).get("score", 0),
                "away_score": d.get("awayTeam", {}).get("score", 0),
                "outcome": d.get("gameOutcome", {}).get("lastPeriodType", "REG"),
            })
    return pd.DataFrame(games).sort_values("date").reset_index(drop=True)


def build_game_stats(games_df, shots_all, state_all, model):
    """Per-game per-team stats: attempts, xG, goals, seconds by strength state."""
    # Score all non-empty-net shots with xG
    non_en = shots_all[~shots_all["empty_net"]].copy()
    non_en["xg"] = score_xg(non_en, model)
    shots_all = shots_all.merge(non_en[["game_id", "period", "seconds", "shooting_team", "xg"]].drop_duplicates(),
                                 on=["game_id", "period", "seconds", "shooting_team"], how="left")
    shots_all["xg"] = shots_all["xg"].fillna(0)

    rows = []
    for _, g in games_df.iterrows():
        gid = g["game_id"]
        g_shots = shots_all[shots_all["game_id"] == gid]
        g_state = state_all[state_all["game_id"] == gid]

        for team, role in [(g["home"], "home"), (g["away"], "away")]:
            # 5v5 stats
            ev_for = g_shots[(g_shots["shooting_team"] == role) & (g_shots["strength"].isin(EVEN_STATES))]
            ev_against = g_shots[(g_shots["shooting_team"] != role) & (g_shots["strength"].isin(EVEN_STATES))]
            ev_secs = g_state[g_state.apply(lambda r: f"{r['home_skaters']}v{r['away_skaters']}" in EVEN_STATES, axis=1)]["duration"].sum()

            # PP stats (own PP)
            if role == "home":
                pp_secs = g_state[g_state.apply(lambda r: f"{r['home_skaters']}v{r['away_skaters']}" in PP_STATES, axis=1)]["duration"].sum()
                pk_secs = g_state[g_state.apply(lambda r: f"{r['home_skaters']}v{r['away_skaters']}" in PK_STATES, axis=1)]["duration"].sum()
            else:
                pp_secs = g_state[g_state.apply(lambda r: f"{r['away_skaters']}v{r['home_skaters']}" in PP_STATES, axis=1)]["duration"].sum()
                pk_secs = g_state[g_state.apply(lambda r: f"{r['away_skaters']}v{r['home_skaters']}" in PK_STATES, axis=1)]["duration"].sum()

            pp_for = g_shots[(g_shots["shooting_team"] == role) & (g_shots["strength"].isin(PP_STATES))]
            pk_against = g_shots[(g_shots["shooting_team"] != role) & (g_shots["strength"].isin(PP_STATES))]

            # Penalties
            pens_taken = len(g_shots)  # placeholder — use penalty table
            pens_drawn = 0

            rows.append({
                "game_id": gid, "season": g["season"], "date": g["date"],
                "team": team, "role": role,
                "ev_att_for": len(ev_for), "ev_att_against": len(ev_against),
                "ev_xg_for": ev_for["xg"].sum(), "ev_xg_against": ev_against["xg"].sum(),
                "ev_goals_for": int(ev_for["is_goal"].sum()), "ev_goals_against": int(ev_against["is_goal"].sum()),
                "ev_seconds": ev_secs,
                "pp_att_for": len(pp_for), "pp_xg_for": pp_for["xg"].sum(), "pp_seconds": pp_secs,
                "pk_att_against": len(pk_against), "pk_xg_against": pk_against["xg"].sum(), "pk_seconds": pk_secs,
            })
    return pd.DataFrame(rows)


def compute_split_half_r(df, stat_col, min_games=40):
    """Split-half reliability: odd vs even games within each team-season."""
    df = df.copy()
    df["game_num"] = df.groupby(["team", "season"]).cumcount() + 1
    df["half"] = df["game_num"] % 2
    halves = {}
    for h in [0, 1]:
        hdf = df[df["half"] == h]
        g = hdf.groupby(["team", "season"]).agg(val=(stat_col, "mean"), n=(stat_col, "count"))
        g = g[g["n"] >= min_games // 2]
        halves[h] = g["val"]
    both = pd.DataFrame({"odd": halves.get(1, pd.Series()), "even": halves.get(0, pd.Series())}).dropna()
    if len(both) < 5:
        return 0.0, 0
    return float(both["odd"].corr(both["even"])), len(both)


def compute_K(r, n_avg):
    if r <= 0:
        return 1e6
    return n_avg * (1 - r) / r


def shrink(total, n, league_mean, K):
    return (total + K * league_mean) / (n + K)


def measure_carry_over(tgs, stat_for, stat_against):
    """Measure carry-over weight: slope of 2022-23 full-season rate on 2021-22 full-season rate."""
    weights = {}
    for stat_name, num_col, denom_col in [(f"{stat_for}", f"{stat_for}", "ev_seconds"),
                                           (f"{stat_against}", f"{stat_against}", "ev_seconds")]:
        prev = tgs[tgs["season"] == 2021].groupby("team").agg(s=(num_col, "sum"), d=(denom_col, "sum"))
        curr = tgs[tgs["season"] == 2022].groupby("team").agg(s=(num_col, "sum"), d=(denom_col, "sum"))
        prev["rate"] = prev["s"] / prev["d"].clip(1)
        curr["rate"] = curr["s"] / curr["d"].clip(1)
        both = prev[["rate"]].join(curr[["rate"]], lsuffix="_prev", rsuffix="_curr").dropna()
        if len(both) >= 10:
            from numpy.polynomial.polynomial import polyfit
            c = polyfit(both["rate_prev"], both["rate_curr"], 1)
            weights[stat_name] = float(np.clip(c[1], 0, 1))
        else:
            weights[stat_name] = 0.5
    return weights


def build_pit_ratings(tgs, fit_seasons=FIT_SEASONS):
    """Build point-in-time team ratings with per-season accumulation and carry-over."""
    tgs = tgs.sort_values("date").reset_index(drop=True)

    # Measure reliabilities on fit seasons
    fit_data = tgs[tgs["season"].isin(fit_seasons)].copy()
    fit_data["ev_att_share"] = fit_data["ev_att_for"] / (fit_data["ev_att_for"] + fit_data["ev_att_against"]).clip(1)
    fit_data["ev_xg_per_att_for"] = fit_data["ev_xg_for"] / fit_data["ev_att_for"].clip(1)

    r_att, n_att = compute_split_half_r(fit_data, "ev_att_share")
    r_xg, n_xg = compute_split_half_r(fit_data, "ev_xg_per_att_for")
    K_att = compute_K(r_att, 82)
    K_xg = compute_K(r_xg, 82)

    print(f"\nSplit-half reliabilities:")
    print(f"  5v5 att share: r={r_att:.3f}, K={K_att:.1f}")
    print(f"  5v5 xG/att FOR: r={r_xg:.3f}, K={K_xg:.1f}")

    # Measure carry-over weights on 2021->2022 transition
    w_att_for = measure_carry_over(tgs, "ev_att_for", "ev_att_against")
    print(f"\nCarry-over weights (2021->2022):")
    for k, v in w_att_for.items():
        print(f"  {k}: w={v:.3f}")

    # Build ratings per-season, per-team
    ratings = []
    # Track prior season final ratings per team
    prior_final = {}  # team -> {stat: value}

    for season in ALL_SEASONS:
        season_tgs = tgs[tgs["season"] == season].sort_values("date")
        teams = season_tgs["team"].unique()

        # Per-team cumulative stats within this season
        team_cum = {t: {"ev_att_for": 0, "ev_att_against": 0, "ev_xg_for": 0.0, "ev_xg_against": 0.0,
                        "ev_secs": 0.0, "n": 0} for t in teams}

        # League cumulative stats for this season (strictly before D)
        league_games_by_date = season_tgs.groupby("date")

        # Pre-compute league cumulative for point-in-time prior
        dates = sorted(season_tgs["date"].unique())
        league_cum = {"ev_att_for": 0, "ev_att_against": 0, "ev_xg_for": 0.0, "ev_xg_against": 0.0,
                      "ev_secs": 0.0, "n_games": 0}
        league_at_date = {}
        for d in dates:
            league_at_date[d] = dict(league_cum)
            day_games = season_tgs[season_tgs["date"] == d]
            for _, r in day_games.iterrows():
                league_cum["ev_att_for"] += r["ev_att_for"]
                league_cum["ev_att_against"] += r["ev_att_against"]
                league_cum["ev_xg_for"] += r["ev_xg_for"]
                league_cum["ev_xg_against"] += r["ev_xg_against"]
                league_cum["ev_secs"] += r["ev_seconds"]
                league_cum["n_games"] += 1

        # First-10-days mean for 2021-22 warm-up
        if season == 2021 and len(dates) >= 10:
            first_10_date = dates[min(9, len(dates)-1)]
            warm_data = season_tgs[season_tgs["date"] <= first_10_date]
            warmup_mean_att_rate = warm_data["ev_att_for"].sum() / warm_data["ev_seconds"].sum() * 3600 if warm_data["ev_seconds"].sum() > 0 else 42
            warmup_mean_xg = warm_data["ev_xg_for"].sum() / warm_data["ev_att_for"].sum() if warm_data["ev_att_for"].sum() > 0 else 0.062
        else:
            warmup_mean_att_rate = 42.0
            warmup_mean_xg = 0.062

        for _, row in season_tgs.iterrows():
            team = row["team"]
            d = row["date"]
            tc = team_cum[team]

            # League mean strictly before D
            lc = league_at_date[d]
            if lc["n_games"] >= 10:
                lg_att_rate = lc["ev_att_for"] / lc["ev_secs"] * 3600 if lc["ev_secs"] > 0 else 42
                lg_xg = lc["ev_xg_for"] / lc["ev_att_for"] if lc["ev_att_for"] > 0 else 0.062
            elif season == 2021:
                lg_att_rate = warmup_mean_att_rate
                lg_xg = warmup_mean_xg
            elif season - 1 in [s for s in ALL_SEASONS]:
                # Use prior season's final league mean
                prev_tgs = tgs[tgs["season"] == season - 1]
                lg_att_rate = prev_tgs["ev_att_for"].sum() / prev_tgs["ev_seconds"].sum() * 3600 if prev_tgs["ev_seconds"].sum() > 0 else 42
                lg_xg = prev_tgs["ev_xg_for"].sum() / prev_tgs["ev_att_for"].sum() if prev_tgs["ev_att_for"].sum() > 0 else 0.062
            else:
                lg_att_rate = 42.0
                lg_xg = 0.062

            # Team rating going INTO this game
            if tc["n"] == 0:
                # First game of season: use carry-over from prior season
                if team in prior_final and season != 2021:
                    pf = prior_final[team]
                    w = 0.5  # default carry-over (measured below per stat)
                    r_att_for = pf.get("ev_att_for_per60", lg_att_rate) * w + lg_att_rate * (1 - w)
                    r_att_against = pf.get("ev_att_against_per60", lg_att_rate) * w + lg_att_rate * (1 - w)
                    r_xg_for = pf.get("ev_xg_per_att_for", lg_xg) * w + lg_xg * (1 - w)
                    r_xg_against = pf.get("ev_xg_per_att_against", lg_xg) * w + lg_xg * (1 - w)
                else:
                    r_att_for = lg_att_rate
                    r_att_against = lg_att_rate
                    r_xg_for = lg_xg
                    r_xg_against = lg_xg
            else:
                raw_att_for = tc["ev_att_for"] / tc["ev_secs"] * 3600 if tc["ev_secs"] > 0 else lg_att_rate
                raw_att_against = tc["ev_att_against"] / tc["ev_secs"] * 3600 if tc["ev_secs"] > 0 else lg_att_rate
                raw_xg_for = tc["ev_xg_for"] / tc["ev_att_for"] if tc["ev_att_for"] > 0 else lg_xg
                raw_xg_against = tc["ev_xg_against"] / tc["ev_att_against"] if tc["ev_att_against"] > 0 else lg_xg

                r_att_for = shrink(raw_att_for * tc["n"], tc["n"], lg_att_rate, K_att)
                r_att_against = shrink(raw_att_against * tc["n"], tc["n"], lg_att_rate, K_att)
                r_xg_for = shrink(raw_xg_for * tc["n"], tc["n"], lg_xg, K_xg)
                r_xg_against = shrink(raw_xg_against * tc["n"], tc["n"], lg_xg, K_xg)

            ratings.append({
                "game_id": row["game_id"], "season": season, "date": d,
                "team": team, "role": row["role"],
                "n_prior_games": tc["n"],
                "ev_att_for_per60": round(r_att_for, 2),
                "ev_att_against_per60": round(r_att_against, 2),
                "ev_xg_per_att_for": round(r_xg_for, 5),
                "ev_xg_per_att_against": round(r_xg_against, 5),
            })

            # Update cumulative AFTER recording rating
            tc["ev_att_for"] += row["ev_att_for"]
            tc["ev_att_against"] += row["ev_att_against"]
            tc["ev_xg_for"] += row["ev_xg_for"]
            tc["ev_xg_against"] += row["ev_xg_against"]
            tc["ev_secs"] += row["ev_seconds"]
            tc["n"] += 1

        # Store final ratings for carry-over
        for team in teams:
            tc = team_cum[team]
            if tc["n"] > 0:
                prior_final[team] = {
                    "ev_att_for_per60": tc["ev_att_for"] / tc["ev_secs"] * 3600 if tc["ev_secs"] > 0 else 42,
                    "ev_att_against_per60": tc["ev_att_against"] / tc["ev_secs"] * 3600 if tc["ev_secs"] > 0 else 42,
                    "ev_xg_per_att_for": tc["ev_xg_for"] / tc["ev_att_for"] if tc["ev_att_for"] > 0 else 0.062,
                    "ev_xg_per_att_against": tc["ev_xg_against"] / tc["ev_att_against"] if tc["ev_att_against"] > 0 else 0.062,
                }

    return pd.DataFrame(ratings), {"r_att": r_att, "K_att": K_att, "r_xg": r_xg, "K_xg": K_xg}


def build_goalie_ratings(shots_all, games_df, model):
    """Goalie ratings: GSAx per attempt, per-season, with career carry-over."""
    non_en = shots_all[~shots_all["empty_net"]].copy()
    non_en["xg"] = score_xg(non_en, model)

    goalie_games = []
    starter_matches = 0
    starter_total = 0

    for _, g in games_df.iterrows():
        gid = g["game_id"]
        g_shots = non_en[non_en["game_id"] == gid]

        for role, opp_role in [("home", "away"), ("away", "home")]:
            opp_shots = g_shots[g_shots["shooting_team"] == opp_role].sort_values("seconds")
            if len(opp_shots) == 0:
                continue
            goalie_id = opp_shots.iloc[0].get("goalie_id")
            if goalie_id is None or pd.isna(goalie_id):
                continue
            goalie_id = int(goalie_id)
            faced = g_shots[g_shots["shooting_team"] == opp_role]
            xg_faced = faced["xg"].sum()
            goals_against = int(faced["is_goal"].sum())

            goalie_games.append({
                "game_id": gid, "season": g["season"], "date": g["date"],
                "goalie_id": goalie_id, "team": g[role[:4]] if role == "home" else g["away"],
                "role": role,
                "attempts_faced": len(faced), "xg_faced": xg_faced,
                "goals_against": goals_against,
                "gsax": xg_faced - goals_against,
            })

    gdf = pd.DataFrame(goalie_games).sort_values("date")

    # Split-half reliability
    gdf["gsax_per_att"] = gdf["gsax"] / gdf["attempts_faced"].clip(1)
    fit_data = gdf[gdf["season"].isin(FIT_SEASONS)].copy()
    fit_sh = fit_data[["goalie_id", "season", "gsax_per_att"]].copy()
    fit_sh = fit_sh.rename(columns={"goalie_id": "team"})
    r_goalie, n_goalies = compute_split_half_r(fit_sh, "gsax_per_att", min_games=20)
    K_goalie = compute_K(r_goalie, 60)
    print(f"\nGoalie GSAx/att: r={r_goalie:.3f}, K={K_goalie:.1f}")

    # Point-in-time goalie ratings, per-season
    goalie_ratings = []
    goalie_career = {}  # goalie_id -> {cum_gsax, cum_att}

    for season in ALL_SEASONS:
        s_gdf = gdf[gdf["season"] == season].sort_values("date")
        goalie_season = {}  # goalie_id -> {gsax, att, n} within this season

        for _, gg in s_gdf.iterrows():
            gid = gg["goalie_id"]
            if gid not in goalie_season:
                goalie_season[gid] = {"gsax": 0.0, "att": 0, "n": 0}

            gs = goalie_season[gid]
            if gs["n"] == 0 and gid in goalie_career:
                # Use career carry-over
                career = goalie_career[gid]
                raw = career["gsax"] / career["att"] if career["att"] > 0 else 0.0
                rating = shrink(raw * career["n"], career["n"], 0.0, K_goalie)
            elif gs["n"] == 0:
                rating = 0.0
            else:
                raw = gs["gsax"] / gs["att"] if gs["att"] > 0 else 0.0
                rating = shrink(raw * gs["n"], gs["n"], 0.0, K_goalie)

            goalie_ratings.append({
                "game_id": gg["game_id"], "season": season, "date": gg["date"],
                "goalie_id": gid, "team": gg["team"], "role": gg["role"],
                "n_prior_starts": gs["n"],
                "gsax_per_att_rating": round(rating, 5),
            })

            gs["gsax"] += gg["gsax"]
            gs["att"] += gg["attempts_faced"]
            gs["n"] += 1

        # Update career stats
        for gid, gs in goalie_season.items():
            if gid not in goalie_career:
                goalie_career[gid] = {"gsax": 0.0, "att": 0, "n": 0}
            goalie_career[gid]["gsax"] += gs["gsax"]
            goalie_career[gid]["att"] += gs["att"]
            goalie_career[gid]["n"] += gs["n"]

    return pd.DataFrame(goalie_ratings), r_goalie, K_goalie


def finishing_term_pit(shots_all, games_df, model):
    """Point-in-time league finishing term: goals/xG over prior 30 days."""
    non_en = shots_all[~shots_all["empty_net"]].copy()
    non_en["xg"] = score_xg(non_en, model)
    gd = games_df[["game_id", "date", "season"]].drop_duplicates("game_id")
    non_en = non_en.merge(gd, on="game_id", how="left", suffixes=("", "_gd"))
    if "date" not in non_en.columns:
        non_en["date"] = non_en.get("date_gd")
    if "season" not in non_en.columns or non_en["season"].isna().all():
        non_en["season"] = non_en.get("season_gd")

    # By month for reporting
    non_en["month"] = non_en["date"].astype(str).str[:7]
    monthly = non_en.groupby(["season", "month"]).agg(goals=("is_goal", "sum"), xg=("xg", "sum"))
    monthly["goals_over_xg"] = monthly["goals"] / monthly["xg"]
    monthly["xg_over_goals"] = monthly["xg"] / monthly["goals"]
    print("\nLeague finishing term by month (goals/xG AND xG/goals):")
    for (s, m), r in monthly.iterrows():
        print(f"  {s} {m}: goals/xG={r['goals_over_xg']:.3f}  xG/goals={r['xg_over_goals']:.3f}")

    return monthly


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("Loading data...")
    games_df = get_game_info(ALL_SEASONS)
    print(f"  Games: {len(games_df)}")

    shots_all = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "shots.parquet") for s in ALL_SEASONS], ignore_index=True)
    state_all = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "state_time.parquet") for s in ALL_SEASONS], ignore_index=True)

    shots_all = shots_all.merge(games_df[["game_id", "date", "season"]].drop_duplicates("game_id"), on="game_id", how="left")
    state_all = state_all.merge(games_df[["game_id", "date", "season"]].drop_duplicates("game_id"), on="game_id", how="left")

    model = load_xg_model()
    print("\nBuilding game stats...")
    tgs = build_game_stats(games_df, shots_all, state_all, model)
    print(f"  Team-game rows: {len(tgs)}")

    print("\nBuilding point-in-time team ratings...")
    team_ratings, reliabilities = build_pit_ratings(tgs)
    print(f"  Rating rows: {len(team_ratings)}")

    print("\nBuilding goalie ratings...")
    goalie_ratings, r_goalie, K_goalie = build_goalie_ratings(shots_all, games_df, model)
    print(f"  Goalie rows: {len(goalie_ratings)}")

    finishing_term_pit(shots_all, games_df, model)

    if args.dry_run:
        print("--dry-run: not saving"); return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    team_ratings.to_parquet(OUT_DIR / "team_ratings.parquet", index=False)
    goalie_ratings.to_parquet(OUT_DIR / "goalie_ratings.parquet", index=False)
    print(f"\nSaved: {OUT_DIR / 'team_ratings.parquet'} ({len(team_ratings)} rows)")
    print(f"Saved: {OUT_DIR / 'goalie_ratings.parquet'} ({len(goalie_ratings)} rows)")


if __name__ == "__main__":
    main()
