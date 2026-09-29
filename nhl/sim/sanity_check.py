#!/usr/bin/env python3
"""
S15: Ratings sanity check with full implied-goals formula and Pinnacle join.
Join by (ET date, home abbrev, away abbrev), as build_lines.py does.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RATINGS_DIR = ROOT / "nhl" / "data" / "sim" / "ratings"
LINES_DIR = ROOT / "data" / "odds_archive" / "nhl" / "history" / "lines"
BOX_DIR = ROOT / "nhl" / "cache"
CONST_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v2.json"
GAMES_PER_SEASON = 1312

NAME = {"Anaheim Ducks": "ANA", "Arizona Coyotes": "ARI", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
        "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR", "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
        "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL", "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
        "Florida Panthers": "FLA", "Los Angeles Kings": "LAK", "Minnesota Wild": "MIN", "Montréal Canadiens": "MTL",
        "Nashville Predators": "NSH", "New Jersey Devils": "NJD", "New York Islanders": "NYI", "New York Rangers": "NYR",
        "Ottawa Senators": "OTT", "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJS",
        "Seattle Kraken": "SEA", "St Louis Blues": "STL", "Tampa Bay Lightning": "TBL", "Toronto Maple Leafs": "TOR",
        "Utah Hockey Club": "UTA", "Utah Mammoth": "UTA", "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK",
        "Washington Capitals": "WSH", "Winnipeg Jets": "WPG"}


def implied_prob(american):
    if american > 0:
        return 100 / (american + 100)
    return -american / (-american + 100)


def load_pinnacle_for_season(season):
    """Pinnacle de-vigged h2h and totals. Last snapshot strictly before puck, <= 6h."""
    season_dir = LINES_DIR / f"season={season}"
    if not season_dir.exists():
        return pd.DataFrame()
    files = sorted(season_dir.glob("snap_*.parquet"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["snap_dt"] = pd.to_datetime(df["snapshot_utc"])
    df["ct_dt"] = pd.to_datetime(df["commence_time"])
    df = df[df["snap_dt"] < df["ct_dt"]]
    df["lead_h"] = (df["ct_dt"] - df["snap_dt"]).dt.total_seconds() / 3600
    df = df[df["lead_h"] <= 6]
    last = df.groupby("event_id")["snap_dt"].transform("max")
    df = df[df["snap_dt"] == last]
    df["home"] = df["home_team"].map(NAME)
    df["away"] = df["away_team"].map(NAME)
    try:
        df["et_date"] = df["ct_dt"].dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    except TypeError:
        df["et_date"] = pd.to_datetime(df["ct_dt"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")

    pin = df[df["bookmaker"] == "pinnacle"]
    results = []
    for eid, g in pin.groupby("event_id"):
        row = {"event_id": eid, "home": g.iloc[0]["home"], "away": g.iloc[0]["away"],
               "et_date": g.iloc[0]["et_date"]}
        h2h = g[g["market"] == "h2h"]
        ht, at = g.iloc[0]["home_team"], g.iloc[0]["away_team"]
        hh, ah = h2h[h2h["outcome_name"] == ht], h2h[h2h["outcome_name"] == at]
        if len(hh) == 1 and len(ah) == 1:
            ph, pa = implied_prob(hh.iloc[0]["price"]), implied_prob(ah.iloc[0]["price"])
            row["pin_p_home"] = ph / (ph + pa)
        tot = g[g["market"] == "totals"]
        ov = tot[tot["outcome_name"] == "Over"]
        if len(ov):
            row["pin_total_line"] = ov.iloc[0]["point"]
        results.append(row)
    return pd.DataFrame(results)


def load_actuals(season):
    results = []
    for i in range(1, GAMES_PER_SEASON + 1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists(): continue
        with open(bp) as f:
            d = json.load(f)
        hs, as_ = d["homeTeam"]["score"], d["awayTeam"]["score"]
        outcome = d.get("gameOutcome", {}).get("lastPeriodType", "REG")
        h, a = hs, as_
        if outcome == "SO":
            if h > a: h -= 1
            else: a -= 1
        results.append({"game_id": gid, "season": season,
                        "home": d["homeTeam"]["abbrev"], "away": d["awayTeam"]["abbrev"],
                        "home_score": hs, "away_score": as_,
                        "reg_goal_diff": h - a, "total_goals": hs + as_,
                        "date": d.get("gameDate", "")})
    return pd.DataFrame(results)


def compute_implied(tr, gr, actuals, constants):
    c = constants.get("constants", constants)
    lg_att = c.get("attempt_rate_per_60_per_team_5v5", {}).get("value", 42)
    lg_xg = c.get("xg_per_attempt_5v5", {}).get("value", 0.062)
    pp_att = c.get("attempt_rate_per_60_per_team_5v4", {}).get("value", 41)
    pp_xg = c.get("xg_per_attempt_5v4", {}).get("value", 0.095)
    avg_ev_min, avg_pp_min = 50, 3.8

    rows = []
    for _, g in actuals.iterrows():
        gid, home, away = g["game_id"], g["home"], g["away"]
        h_tr = tr[(tr["game_id"] == gid) & (tr["team"] == home)]
        a_tr = tr[(tr["game_id"] == gid) & (tr["team"] == away)]
        a_gr = gr[(gr["game_id"] == gid) & (gr["team"] == away)]
        h_gr = gr[(gr["game_id"] == gid) & (gr["team"] == home)]
        if len(h_tr) == 0 or len(a_tr) == 0: continue
        hr, ar = h_tr.iloc[0], a_tr.iloc[0]

        h_att = hr["ev_att_for_per60"] * ar["ev_att_against_per60"] / lg_att
        a_att = ar["ev_att_for_per60"] * hr["ev_att_against_per60"] / lg_att
        h_xg = hr["ev_xg_per_att_for"] * ar["ev_xg_per_att_against"] / lg_xg
        a_xg = ar["ev_xg_per_att_for"] * hr["ev_xg_per_att_against"] / lg_xg

        h_ev = h_att * h_xg * avg_ev_min / 60
        a_ev = a_att * a_xg * avg_ev_min / 60
        h_pp = pp_att * pp_xg * avg_pp_min / 60
        a_pp = pp_att * pp_xg * avg_pp_min / 60

        # Goalie factor
        ag_f = 1.0 - (a_gr.iloc[0]["gsax_per_att_rating"] * 30 if len(a_gr) else 0)
        hg_f = 1.0 - (h_gr.iloc[0]["gsax_per_att_rating"] * 30 if len(h_gr) else 0)
        ag_f, hg_f = np.clip(ag_f, 0.8, 1.2), np.clip(hg_f, 0.8, 1.2)

        h_goals = (h_ev + h_pp) * ag_f + 0.35
        a_goals = (a_ev + a_pp) * hg_f + 0.35

        rows.append({"game_id": gid, "home": home, "away": away, "date": g["date"],
                      "implied_diff": h_goals - a_goals, "implied_total": h_goals + a_goals})
    return pd.DataFrame(rows)


def main():
    with open(CONST_PATH) as f:
        constants = json.load(f)
    tr = pd.read_parquet(RATINGS_DIR / "team_ratings.parquet")
    gr = pd.read_parquet(RATINGS_DIR / "goalie_ratings.parquet")

    for season in [2022, 2023]:
        print(f"\n{'='*60}\nSANITY CHECK: {season}-{season+1}\n{'='*60}")
        actuals = load_actuals(season)
        implied = compute_implied(tr, gr, actuals, constants)
        pinnacle = load_pinnacle_for_season(season)

        merged = implied.merge(actuals[["game_id", "reg_goal_diff", "total_goals", "date"]],
                                on=["game_id"], suffixes=("", "_act"))
        if not pinnacle.empty:
            merged = merged.merge(pinnacle[["et_date", "home", "away", "pin_p_home", "pin_total_line"]],
                                   left_on=["date", "home", "away"],
                                   right_on=["et_date", "home", "away"], how="left")
            n_pin = int(merged["pin_p_home"].notna().sum())
        else:
            n_pin = 0
            merged["pin_p_home"] = np.nan
            merged["pin_total_line"] = np.nan

        n = len(merged)
        print(f"  Games: {n}, with Pinnacle: {n_pin}")

        # Actual outcomes FIRST (per A1.1)
        corr_gd = float(merged["implied_diff"].corr(merged["reg_goal_diff"]))
        print(f"  corr(implied goal diff, actual goal diff): {corr_gd:.3f}")

        if n_pin > 10:
            pv = merged["pin_p_home"].notna()
            pin_logit = np.log(merged.loc[pv, "pin_p_home"].clip(0.01, 0.99) /
                               (1 - merged.loc[pv, "pin_p_home"].clip(0.01, 0.99)))
            corr_pin = float(merged.loc[pv, "implied_diff"].corr(pin_logit))
            print(f"  corr(implied goal diff, Pinnacle logit): {corr_pin:.3f}")

            ptv = merged["pin_total_line"].notna()
            corr_tot = float(merged.loc[ptv, "implied_total"].corr(merged.loc[ptv, "pin_total_line"]))
            print(f"  corr(implied total, Pinnacle total): {corr_tot:.3f}")

        mean_i = float(merged["implied_total"].mean())
        mean_a = float(merged["total_goals"].mean())
        pct = (mean_i - mean_a) / mean_a * 100
        print(f"  mean implied total: {mean_i:.2f}, actual: {mean_a:.2f} ({pct:+.1f}%)")

        # NULL CONTROL: shuffle within date
        rng = np.random.RandomState(42)
        sh = merged.copy()
        for dt in sh["date"].unique():
            mask = sh["date"] == dt
            idx = sh.loc[mask].index
            v = sh.loc[mask, "implied_diff"].values.copy()
            rng.shuffle(v)
            sh.loc[idx, "implied_diff"] = v
        null_c = float(sh["implied_diff"].corr(sh["reg_goal_diff"]))
        print(f"  NULL (shuffled): corr = {null_c:.3f}")


if __name__ == "__main__":
    main()
