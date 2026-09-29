#!/usr/bin/env python3
"""
S12: Ratings-only sanity check against Pinnacle and actual outcomes.
Fit (2022-23) and validate (2023-24) seasons ONLY. No holdout.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RATINGS_DIR = ROOT / "nhl" / "data" / "sim" / "ratings"
LINES_DIR = ROOT / "data" / "odds_archive" / "nhl" / "history" / "lines"
BOX_DIR = ROOT / "nhl" / "cache"
GAMES_PER_SEASON = 1312


def implied_prob(american):
    """American odds to implied probability."""
    if american > 0:
        return 100 / (american + 100)
    return -american / (-american + 100)


def load_pinnacle_lines(season):
    """Load Pinnacle lines for a season, latest snapshot per game."""
    season_dir = LINES_DIR / f"season={season}"
    if not season_dir.exists():
        return pd.DataFrame()
    files = sorted(season_dir.glob("snap_*.parquet"))
    if not files:
        return pd.DataFrame()
    all_dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(all_dfs, ignore_index=True)
    # Keep only Pinnacle
    df = df[df["bookmaker"] == "pinnacle"]
    # Keep latest snapshot per game (by snapshot_utc)
    df = df.sort_values("snapshot_utc")
    df = df.drop_duplicates(["event_id", "market", "outcome_name"], keep="last")
    return df


def get_pinnacle_probs(season):
    """Get Pinnacle de-vigged home probability and total line per game."""
    lines = load_pinnacle_lines(season)
    if lines.empty:
        return pd.DataFrame()

    games = {}
    for eid, g in lines.groupby("event_id"):
        home = g.iloc[0].get("home_team", "")
        away = g.iloc[0].get("away_team", "")

        # h2h
        h2h = g[g["market"] == "h2h"]
        home_h2h = h2h[h2h["outcome_name"] == home]
        away_h2h = h2h[h2h["outcome_name"] == away]
        if len(home_h2h) and len(away_h2h):
            p_home = implied_prob(home_h2h.iloc[0]["price"])
            p_away = implied_prob(away_h2h.iloc[0]["price"])
            total_imp = p_home + p_away
            devig_home = p_home / total_imp
        else:
            devig_home = np.nan

        # totals
        totals = g[g["market"] == "totals"]
        over = totals[totals["outcome_name"] == "Over"]
        total_line = over.iloc[0]["point"] if len(over) else np.nan

        games[eid] = {
            "event_id": eid, "home_team": home, "away_team": away,
            "pinnacle_home_prob": devig_home,
            "pinnacle_total_line": total_line,
        }

    return pd.DataFrame(games.values())


def load_actuals(season):
    """Load actual game results from boxscores."""
    results = []
    for i in range(1, GAMES_PER_SEASON + 1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists():
            continue
        with open(bp) as f:
            d = json.load(f)
        home_score = d.get("homeTeam", {}).get("score", 0)
        away_score = d.get("awayTeam", {}).get("score", 0)
        outcome = d.get("gameOutcome", {}).get("lastPeriodType", "REG")
        # Remove shootout +1 for regulation goal diff
        h = home_score
        a = away_score
        if outcome == "SO":
            if h > a: h -= 1
            else: a -= 1
        results.append({
            "season": season, "game_id": gid,
            "home": d.get("homeTeam", {}).get("abbrev", ""),
            "away": d.get("awayTeam", {}).get("abbrev", ""),
            "home_score": home_score, "away_score": away_score,
            "reg_goal_diff": h - a,
            "total_goals": home_score + away_score,
            "date": d.get("gameDate", ""),
        })
    return pd.DataFrame(results)


def compute_implied_goals(team_ratings, goalie_ratings, games_df, season):
    """For each game, compute implied goals per team from ratings."""
    tr = team_ratings[team_ratings["season"] == season].copy()
    gr = goalie_ratings[goalie_ratings["season"] == season].copy()

    implied = []
    for _, g in games_df[games_df["season"] == season].iterrows():
        gid = g["game_id"]
        home = g["home"]
        away = g["away"]

        # Get team ratings for this game
        home_r = tr[(tr["game_id"] == gid) & (tr["team"] == home)]
        away_r = tr[(tr["game_id"] == gid) & (tr["team"] == away)]

        if len(home_r) == 0 or len(away_r) == 0:
            continue

        hr = home_r.iloc[0]
        ar = away_r.iloc[0]

        # League averages
        league_att = 42.0  # approximate
        league_xg = 0.062

        # Implied 5v5 goals per team (simplified)
        # Home attempts = home_for * away_against / league * minutes
        avg_5v5_min = 50  # approximate 5v5 minutes per game
        home_att_rate = hr["ev_att_for_per60"] * ar["ev_att_against_per60"] / league_att
        away_att_rate = ar["ev_att_for_per60"] * hr["ev_att_against_per60"] / league_att

        home_xg_rate = hr["ev_xg_per_att_for"] * ar["ev_xg_per_att_against"] / league_xg
        away_xg_rate = ar["ev_xg_per_att_for"] * hr["ev_xg_per_att_against"] / league_xg

        home_ev_goals = home_att_rate * home_xg_rate * avg_5v5_min / 60
        away_ev_goals = away_att_rate * away_xg_rate * avg_5v5_min / 60

        # Add ~0.5 goals per team from special teams (rough)
        home_goals = home_ev_goals + 0.5
        away_goals = away_ev_goals + 0.5

        implied.append({
            "game_id": gid, "season": season, "date": g["date"],
            "home": home, "away": away,
            "implied_home_goals": home_goals,
            "implied_away_goals": away_goals,
            "implied_goal_diff": home_goals - away_goals,
            "implied_total": home_goals + away_goals,
        })

    return pd.DataFrame(implied)


def main():
    ap = argparse.ArgumentParser()
    args = ap.parse_args()

    tr = pd.read_parquet(RATINGS_DIR / "team_ratings.parquet")
    gr = pd.read_parquet(RATINGS_DIR / "goalie_ratings.parquet")

    for season in [2022, 2023]:
        season_name = f"{season}-{season+1}"
        print(f"\n{'='*60}")
        print(f"SANITY CHECK: {season_name}")
        print(f"{'='*60}")

        actuals = load_actuals(season)
        pinnacle = get_pinnacle_probs(season)
        implied = compute_implied_goals(tr, gr, actuals, season)

        if implied.empty:
            print("  No implied goals computed"); continue

        # Merge with actuals
        merged = implied.merge(actuals[["game_id", "reg_goal_diff", "total_goals"]], on="game_id")
        merged = merged.merge(pinnacle[["event_id", "pinnacle_home_prob", "pinnacle_total_line"]],
                               left_on="game_id", right_on="event_id", how="left")

        n = len(merged)
        n_pin = merged["pinnacle_home_prob"].notna().sum()
        print(f"  Games: {n}, with Pinnacle: {n_pin}")

        # Correlations
        corr_gd = merged["implied_goal_diff"].corr(merged["reg_goal_diff"])
        print(f"  corr(implied goal diff, actual goal diff): {corr_gd:.3f}")

        if n_pin > 0:
            pin_logit = np.log(merged["pinnacle_home_prob"].clip(0.01, 0.99) /
                               (1 - merged["pinnacle_home_prob"].clip(0.01, 0.99)))
            corr_pin = merged["implied_goal_diff"].dropna().corr(pin_logit.dropna())
            print(f"  corr(implied goal diff, Pinnacle logit): {corr_pin:.3f}")

            pin_total = merged["pinnacle_total_line"].dropna()
            imp_total = merged.loc[pin_total.index, "implied_total"]
            corr_total = imp_total.corr(pin_total)
            print(f"  corr(implied total, Pinnacle total line): {corr_total:.3f}")

        mean_implied = merged["implied_total"].mean()
        mean_actual = merged["total_goals"].mean()
        pct_diff = (mean_implied - mean_actual) / mean_actual * 100
        print(f"  mean implied total: {mean_implied:.2f}, actual: {mean_actual:.2f} ({pct_diff:+.1f}%)")

        # NULL CONTROL: shuffle team labels within each date
        rng = np.random.RandomState(42)
        shuffled = merged.copy()
        for date in shuffled["date"].unique():
            mask = shuffled["date"] == date
            idx = shuffled.loc[mask].index
            shuffled_gd = shuffled.loc[mask, "implied_goal_diff"].values.copy()
            rng.shuffle(shuffled_gd)
            shuffled.loc[idx, "implied_goal_diff"] = shuffled_gd
        null_corr_gd = shuffled["implied_goal_diff"].corr(shuffled["reg_goal_diff"])
        print(f"  NULL (shuffled within date): corr(gd) = {null_corr_gd:.3f} (expected ~0)")


if __name__ == "__main__":
    main()
