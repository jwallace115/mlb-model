#!/usr/bin/env python3
"""S30: ONE full-formula sanity check. Uses team_ratings, goalie_ratings, constants_v5, F(D)."""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RATINGS_DIR = ROOT / "nhl" / "data" / "sim" / "ratings"
LINES_DIR = ROOT / "data" / "odds_archive" / "nhl" / "history" / "lines"
BOX_DIR = ROOT / "nhl" / "cache"
C5_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v5.json"
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


def implied_prob(a):
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def load_pinnacle(season):
    sd = LINES_DIR / f"season={season}"
    if not sd.exists(): return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in sorted(sd.glob("snap_*.parquet"))], ignore_index=True)
    df["snap_dt"] = pd.to_datetime(df["snapshot_utc"]); df["ct_dt"] = pd.to_datetime(df["commence_time"])
    df = df[df["snap_dt"] < df["ct_dt"]]
    df["lead_h"] = (df["ct_dt"] - df["snap_dt"]).dt.total_seconds() / 3600
    df = df[df["lead_h"] <= 6]
    last = df.groupby("event_id")["snap_dt"].transform("max"); df = df[df["snap_dt"] == last]
    df["home"] = df["home_team"].map(NAME); df["away"] = df["away_team"].map(NAME)
    try:
        df["et_date"] = df["ct_dt"].dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    except TypeError:
        df["et_date"] = pd.to_datetime(df["ct_dt"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    pin = df[df["bookmaker"] == "pinnacle"]
    results = []
    for eid, g in pin.groupby("event_id"):
        row = {"event_id": eid, "home": g.iloc[0]["home"], "away": g.iloc[0]["away"], "et_date": g.iloc[0]["et_date"]}
        h2h = g[g["market"] == "h2h"]; ht, at = g.iloc[0]["home_team"], g.iloc[0]["away_team"]
        hh, ah = h2h[h2h["outcome_name"] == ht], h2h[h2h["outcome_name"] == at]
        if len(hh) == 1 and len(ah) == 1:
            ph, pa = implied_prob(hh.iloc[0]["price"]), implied_prob(ah.iloc[0]["price"])
            row["pin_p_home"] = ph / (ph + pa)
        tot = g[g["market"] == "totals"]; ov = tot[tot["outcome_name"] == "Over"]
        if len(ov): row["pin_total_line"] = ov.iloc[0]["point"]
        results.append(row)
    return pd.DataFrame(results)


def load_actuals(season):
    rows = []
    for i in range(1, GAMES_PER_SEASON + 1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists(): continue
        with open(bp) as f: d = json.load(f)
        hs, as_ = d["homeTeam"]["score"], d["awayTeam"]["score"]
        outcome = d.get("gameOutcome", {}).get("lastPeriodType", "REG")
        h, a = hs, as_
        if outcome == "SO":
            if h > a: h -= 1
            else: a -= 1
        rows.append({"game_id": gid, "season": season, "home": d["homeTeam"]["abbrev"], "away": d["awayTeam"]["abbrev"],
                      "home_score": hs, "away_score": as_, "reg_goal_diff": h - a, "total_goals": hs + as_,
                      "total_no_so": h + a, "date": d.get("gameDate", "")})
    return pd.DataFrame(rows)


def main():
    with open(C5_PATH) as f: c5 = json.load(f)["constants"]
    tr = pd.read_parquet(RATINGS_DIR / "team_ratings.parquet")
    gr = pd.read_parquet(RATINGS_DIR / "goalie_ratings.parquet")
    ft = pd.read_parquet(RATINGS_DIR / "finishing_term.parquet")

    C5_att = c5["attempt_rate_per_60_per_team_5v5"]["value"]
    C5_xgpa = c5["xg_per_attempt_5v5"]["value"]
    M5 = c5["minutes_per_game_5v5"]["value"]

    # PP/PK constants
    pp_min = sum(c5.get(f"minutes_per_team_game_{s}", {}).get("value", 0) for s in ["5v4", "5v3", "4v3"])
    pp_adv_att = c5.get("attempt_rate_per_60_advantaged_5v4", {}).get("value", 70)
    pp_adv_xg = c5.get("xg_per_attempt_advantaged_5v4", {}).get("value", 0.10)
    sh_dis_att = c5.get("attempt_rate_per_60_disadvantaged_5v4", {}).get("value", 12)
    sh_dis_xg = c5.get("xg_per_attempt_disadvantaged_5v4", {}).get("value", 0.07)

    # 4v4, 3v3
    m44 = c5.get("minutes_per_game_4v4", {}).get("value", 2) / 60
    att44 = c5.get("attempt_rate_per_60_per_team_4v4", {}).get("value", 30)
    xg44 = c5.get("xg_per_attempt_4v4", {}).get("value", 0.08)
    m33 = c5.get("minutes_per_game_3v3", {}).get("value", 2) / 60
    att33 = c5.get("attempt_rate_per_60_per_team_3v3", {}).get("value", 47)
    xg33 = c5.get("xg_per_attempt_3v3", {}).get("value", 0.13)

    # 6v5 (extra attacker / empty net)
    m65 = c5.get("minutes_per_team_game_6v5", {}).get("value", 0.5)
    en_goals_per_game = 2 * m65 / 60 * (
        c5.get("attempt_rate_per_60_advantaged_6v5", {}).get("value", 100) * c5.get("goals_per_attempt_advantaged_6v5", {}).get("value", 0.22) +
        c5.get("attempt_rate_per_60_disadvantaged_6v5", {}).get("value", 40) * c5.get("goals_per_attempt_disadvantaged_6v5", {}).get("value", 0.63)
    )

    # League xG per non-EN attempt (all states)
    total_xg = sum(c5.get(f"xg_per_attempt_{st}", {}).get("value", 0) * c5.get(f"attempt_rate_per_60_per_team_{st}", {}).get("denominator", 0)
                    for st in ["5v5", "4v4", "3v3"])
    total_att = sum(c5.get(f"attempt_rate_per_60_per_team_{st}", {}).get("denominator", 0) for st in ["5v5", "4v4", "3v3"])
    # Add uneven states
    for adv in ["5v4", "5v3", "4v3", "6v5"]:
        for tag in ["advantaged", "disadvantaged"]:
            k = f"xg_per_attempt_{tag}_{adv}"
            ka = f"attempt_rate_per_60_{tag}_{adv}"
            if k in c5 and ka in c5:
                total_xg += c5[k]["value"] * c5[ka].get("denominator", 0)
                total_att += c5[ka].get("denominator", 0)
    q = total_xg / total_att if total_att else 0.065
    print(f"League xG per non-EN attempt (q): {q:.6f}")

    for season in [2022, 2023]:
        print(f"\n{'='*60}\nSANITY CHECK v2: {season}-{season+1}\n{'='*60}")
        actuals = load_actuals(season)
        pinnacle = load_pinnacle(season)
        ft_s = ft[ft["season"] == season].set_index("date")

        implied_rows = []
        for _, g in actuals.iterrows():
            gid, home, away, d = g["game_id"], g["home"], g["away"], g["date"]
            h_tr = tr[(tr["game_id"] == gid) & (tr["team"] == home)]
            a_tr = tr[(tr["game_id"] == gid) & (tr["team"] == away)]
            h_gr = gr[(gr["game_id"] == gid) & (gr["team"] == home)]
            a_gr = gr[(gr["game_id"] == gid) & (gr["team"] == away)]
            if len(h_tr) == 0 or len(a_tr) == 0: continue
            hr, ar = h_tr.iloc[0], a_tr.iloc[0]

            F = ft_s.loc[d, "F"] if d in ft_s.index else 1.0
            if pd.isna(F): F = 1.0

            # 5v5
            A_h = C5_att * (hr["ev_att_for_per60"] / hr["lg_ev_att_for_per60"]) * (ar["ev_att_against_per60"] / ar["lg_ev_att_against_per60"])
            Q_h = C5_xgpa * (hr["ev_xg_per_att_for"] / hr["lg_ev_xg_per_att_for"]) * (ar["ev_xg_per_att_against"] / ar["lg_ev_xg_per_att_against"])
            xG5_h = A_h * Q_h * M5 / 60

            A_a = C5_att * (ar["ev_att_for_per60"] / ar["lg_ev_att_for_per60"]) * (hr["ev_att_against_per60"] / hr["lg_ev_att_against_per60"])
            Q_a = C5_xgpa * (ar["ev_xg_per_att_for"] / ar["lg_ev_xg_per_att_for"]) * (hr["ev_xg_per_att_against"] / hr["lg_ev_xg_per_att_against"])
            xG5_a = A_a * Q_a * M5 / 60

            # PP minutes
            P_h = pp_min * (hr["penalties_drawn_per60"] / hr["lg_penalties_drawn_per60"]) * (ar["penalties_taken_per60"] / ar["lg_penalties_taken_per60"])
            P_a = pp_min * (ar["penalties_drawn_per60"] / ar["lg_penalties_drawn_per60"]) * (hr["penalties_taken_per60"] / hr["lg_penalties_taken_per60"])

            # PP xG
            PPxG_h = P_h / 60 * hr["pp_xg_for_per60"] * (ar["pk_xg_against_per60"] / ar["lg_pk_xg_against_per60"])
            PPxG_a = P_a / 60 * ar["pp_xg_for_per60"] * (hr["pk_xg_against_per60"] / hr["lg_pk_xg_against_per60"])

            # SH xG (short-handed side at league rate)
            SHxG_h = P_a / 60 * sh_dis_att * sh_dis_xg
            SHxG_a = P_h / 60 * sh_dis_att * sh_dis_xg

            # 4v4, 3v3
            xG44 = m44 * att44 * xg44
            xG33 = m33 * att33 * xg33

            # Goalie factor
            g_a_rating = a_gr.iloc[0]["gsax_per_att_rating"] if len(a_gr) else 0.0
            g_h_rating = h_gr.iloc[0]["gsax_per_att_rating"] if len(h_gr) else 0.0
            goalie_a = 1 - g_a_rating / q if q > 0 else 1.0
            goalie_h = 1 - g_h_rating / q if q > 0 else 1.0

            goals_h = F * (xG5_h + PPxG_h + SHxG_h + xG44 + xG33) * np.clip(goalie_a, 0.5, 1.5) + en_goals_per_game / 2
            goals_a = F * (xG5_a + PPxG_a + SHxG_a + xG44 + xG33) * np.clip(goalie_h, 0.5, 1.5) + en_goals_per_game / 2

            implied_rows.append({"game_id": gid, "home": home, "away": away, "date": d,
                                  "n_prior_games_home": int(hr["n_prior_games"]),
                                  "implied_diff": goals_h - goals_a, "implied_total": goals_h + goals_a})

        implied = pd.DataFrame(implied_rows)
        merged = implied.merge(actuals[["game_id", "reg_goal_diff", "total_goals", "total_no_so", "date"]],
                                on=["game_id"], suffixes=("", "_act"))
        if not pinnacle.empty:
            merged = merged.merge(pinnacle[["et_date", "home", "away", "pin_p_home", "pin_total_line"]],
                                   left_on=["date", "home", "away"], right_on=["et_date", "home", "away"], how="left")
        else:
            merged["pin_p_home"] = np.nan; merged["pin_total_line"] = np.nan

        n = len(merged); n_pin = int(merged["pin_p_home"].notna().sum())
        print(f"  Games: {n}, with Pinnacle: {n_pin}")

        # (1) Actual outcome correlations first, next to Pinnacle's own
        corr_gd = float(merged["implied_diff"].corr(merged["reg_goal_diff"]))
        corr_tot = float(merged["implied_total"].corr(merged["total_no_so"]))
        pv = merged["pin_p_home"].notna()
        pin_logit = np.log(merged.loc[pv, "pin_p_home"].clip(0.01, 0.99) / (1 - merged.loc[pv, "pin_p_home"].clip(0.01, 0.99)))
        pin_corr_gd = float(pin_logit.corr(merged.loc[pv, "reg_goal_diff"]))
        pin_corr_tot = float(merged.loc[pv, "pin_total_line"].corr(merged.loc[pv, "total_no_so"]))
        print(f"  corr(engine gd, actual gd): {corr_gd:.3f}  |  Pinnacle: {pin_corr_gd:.3f}")
        print(f"  corr(engine total, actual total): {corr_tot:.3f}  |  Pinnacle: {pin_corr_tot:.3f}")

        # (2) S12 bars
        corr_pin_logit = float(merged.loc[pv, "implied_diff"].corr(pin_logit))
        ptv = merged["pin_total_line"].notna()
        corr_pin_tot = float(merged.loc[ptv, "implied_total"].corr(merged.loc[ptv, "pin_total_line"]))
        mean_i = float(merged["implied_total"].mean())
        mean_a = float(merged["total_no_so"].mean())
        pct = (mean_i - mean_a) / mean_a * 100
        print(f"  corr(engine gd, Pinnacle logit): {corr_pin_logit:.3f}  (bar > 0.60)")
        print(f"  corr(engine total, Pinnacle total): {corr_pin_tot:.3f}  (bar > 0.30)")
        print(f"  mean total: engine {mean_i:.2f}, actual {mean_a:.2f} ({pct:+.1f}%)  (consistency check, not blind)")

        # (3) Shuffled null
        rng = np.random.RandomState(42)
        sh = merged.copy()
        for dt in sh["date"].unique():
            mask = sh["date"] == dt
            idx = sh.loc[mask].index
            v = sh.loc[mask, "implied_diff"].values.copy(); rng.shuffle(v); sh.loc[idx, "implied_diff"] = v
        null_c = float(sh["implied_diff"].corr(sh["reg_goal_diff"]))
        print(f"  null (shuffled): {null_c:.3f}")

        # (4) CHECK 5 breakdowns
        merged["month"] = merged["date"].str[:7]
        print(f"\n  BY MONTH:")
        for m, g in merged.groupby("month"):
            if len(g) < 20: continue
            cg = float(g["implied_diff"].corr(g["reg_goal_diff"]))
            ct = float(g["implied_total"].corr(g["total_no_so"]))
            print(f"    {m}: gd={cg:.3f} total={ct:.3f} n={len(g)}")

        print(f"\n  BY GAMES PLAYED (home team):")
        merged["gp_bucket"] = pd.cut(merged["n_prior_games_home"], bins=[-1, 10, 40, 999], labels=["0-10", "11-40", "41+"])
        for b, g in merged.groupby("gp_bucket", observed=True):
            if len(g) < 20: continue
            cg = float(g["implied_diff"].corr(g["reg_goal_diff"]))
            ct = float(g["implied_total"].corr(g["total_no_so"]))
            print(f"    {b}: gd={cg:.3f} total={ct:.3f} n={len(g)}")


if __name__ == "__main__":
    main()
