#!/usr/bin/env python3
"""
Point-in-time team and goalie ratings (S16-S19).

Fixes from S-WO3c:
- Vectorised build_game_stats (was 320s, now < 30s)
- Carry-over w read from carryover_w.json, used as SHRINK TARGET for entire season
- PP/PK, penalties, score-adjusted 5v5
- Point-in-time finishing term (30-day rolling)
- Full implied-goals formula for S15
"""
import argparse, gzip, hashlib, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
BOX_DIR = ROOT / "nhl" / "cache"
XG_PATH = ROOT / "nhl" / "data" / "sim" / "xg_v2.json"
CONST_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v2.json"
OUT_DIR = ROOT / "nhl" / "data" / "sim" / "ratings"
CARRYOVER_PATH = OUT_DIR / "carryover_w.json"

GAMES_PER_SEASON = 1312
GAMES_PER_SEASON_MAP = {
    2010: 1230, 2011: 1230, 2012: 720,  2013: 1230, 2014: 1230,
    2015: 1230, 2016: 1230, 2017: 1271, 2018: 1271, 2019: 1082,
    2020: 868,  2021: 1312, 2022: 1312, 2023: 1312, 2024: 1312,
    2025: 1312,
}
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


def load_carryover():
    """Load carry-over weights. A missing key raises KeyError — no fallback defaults."""
    if not CARRYOVER_PATH.exists():
        raise FileNotFoundError(f"carryover_w.json not found at {CARRYOVER_PATH}")
    with open(CARRYOVER_PATH) as f:
        return json.load(f)


def score_xg(shots_df, model):
    features = model["features"]
    coefs = model["coefficients"]
    intercept = model["intercept"]
    df = shots_df.copy()
    df["strength_group"] = df["strength"].map(STRENGTH_GROUPS).fillna("other")
    for st in ["wrist", "slap", "snap", "backhand", "tip-in", "deflected", "wrap-around", "cradle"]:
        df[f"st_{st}"] = (df["shot_type"] == st).astype(int)
    for sg in ["PP", "PK", "3v3"]:
        df[f"sg_{sg}"] = (df["strength_group"] == sg).astype(int)
    X = df[features].fillna(0).values.astype(float)
    logit = intercept + X @ np.array([coefs[f] for f in features])
    return 1 / (1 + np.exp(-logit))


def get_game_info(seasons):
    games = []
    for s in seasons:
        n_games = GAMES_PER_SEASON_MAP.get(s, GAMES_PER_SEASON)
        for i in range(1, n_games + 1):
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


def build_game_stats_vectorised(games_df, shots_all, state_all, penalties_all, model):
    """Vectorised: group shots/state by game_id + strength, then pivot to per-team rows."""
    t0 = time.time()

    # Score non-empty-net shots (row-wise, no merge — avoids double-counting rebounds)
    en = shots_all["empty_net"].astype(bool)
    shots_all = shots_all.copy()
    shots_all["xg"] = 0.0
    shots_all.loc[~en, "xg"] = score_xg(shots_all.loc[~en], model)

    # Map game_id to home/away teams
    gmap = games_df.set_index("game_id")[["home", "away", "date", "season"]].to_dict("index")

    # Strength classification for state_time
    state_all = state_all.copy()
    state_all["strength_home"] = state_all["home_skaters"].astype(str) + "v" + state_all["away_skaters"].astype(str)

    # --- Shots aggregation ---
    # Tag each shot with its team abbrev and strength group
    def _tag_shot(row):
        g = gmap.get(row["game_id"])
        if not g:
            return None, None
        team = g["home"] if row["shooting_team"] == "home" else g["away"]
        opp = g["away"] if row["shooting_team"] == "home" else g["home"]
        return team, opp

    shots_all["sg"] = shots_all["strength"].map(STRENGTH_GROUPS).fillna("other")

    # Score adjustment for 5v5: weight by 1/score_effect_mult
    constants = load_constants()
    c2 = constants.get("constants", constants)
    ev_all = shots_all[shots_all["strength"].isin(EVEN_STATES)].copy()
    sd = ev_all["score_diff"].clip(-3, 3).astype(int)
    p = ev_all["period"].clip(upper=3).astype(int)

    # Build lookup dicts for score-effect multipliers
    att_mult = {}
    xg_mult = {}
    for s in range(-3, 4):
        for pr in range(1, 4):
            k_att = f"score_effect_attempt_mult_sd{s}_p{pr}"
            k_xg = f"score_effect_xg_mult_sd{s}_p{pr}"
            att_mult[(s, pr)] = c2.get(k_att, {}).get("value", 1.0)
            xg_mult[(s, pr)] = c2.get(k_xg, {}).get("value", 1.0)

    ev_all["w_att"] = [1.0 / att_mult.get((s, p), 1.0) for s, p in zip(sd, p)]
    ev_all["w_xg"] = [1.0 / xg_mult.get((s, p), 1.0) for s, p in zip(sd, p)]
    ev_all["xg_adj"] = ev_all["w_att"] * ev_all["w_xg"] * ev_all["xg"]

    # Split into EV/PP/PK groups
    ev_shots = ev_all  # already filtered to EVEN_STATES
    pp_shots = shots_all[shots_all["strength"].isin(PP_STATES)]

    # Per game, per shooting_team role (including adjusted)
    ev_for = ev_shots.groupby(["game_id", "shooting_team"]).agg(
        ev_att_for=("is_goal", "count"), ev_xg_for=("xg", "sum"), ev_goals_for=("is_goal", "sum"),
        ev_att_for_adj=("w_att", "sum"), ev_xg_for_adj=("xg_adj", "sum"),
    ).reset_index()
    ev_against = ev_shots.groupby(["game_id", "shooting_team"]).agg(
        ev_att_against=("is_goal", "count"), ev_xg_against=("xg", "sum"), ev_goals_against=("is_goal", "sum"),
        ev_att_against_adj=("w_att", "sum"), ev_xg_against_adj=("xg_adj", "sum"),
    ).reset_index()
    # For against: home's against = away's for
    ev_against["opp_role"] = ev_against["shooting_team"].map({"home": "away", "away": "home"})

    pp_for = pp_shots.groupby(["game_id", "shooting_team"]).agg(
        pp_att_for=("is_goal", "count"), pp_xg_for=("xg", "sum")
    ).reset_index()
    pp_against = pp_shots.groupby(["game_id", "shooting_team"]).agg(
        pk_att_against=("is_goal", "count"), pk_xg_against=("xg", "sum")
    ).reset_index()
    pp_against["opp_role"] = pp_against["shooting_team"].map({"home": "away", "away": "home"})

    # Total seconds per game (all states)
    total_secs_per_game = state_all.groupby("game_id")["duration"].sum().rename("total_seconds")

    # State seconds per game per strength from home's perspective
    ev_state = state_all[state_all["strength_home"].isin(EVEN_STATES)]
    ev_secs = ev_state.groupby("game_id")["duration"].sum().rename("ev_seconds")

    pp_state_home = state_all[state_all["strength_home"].isin(PP_STATES)]
    pk_state_home = state_all[state_all["strength_home"].isin(PK_STATES)]
    pp_secs_home = pp_state_home.groupby("game_id")["duration"].sum().rename("pp_seconds_home")
    pk_secs_home = pk_state_home.groupby("game_id")["duration"].sum().rename("pk_seconds_home")

    # Penalties from penalty table
    if penalties_all is not None and len(penalties_all):
        pen_by_game_team = penalties_all.groupby(["game_id", "team"]).size().rename("penalties").reset_index()
    else:
        pen_by_game_team = pd.DataFrame(columns=["game_id", "team", "penalties"])

    # Now build per-team rows
    rows = []
    for _, g in games_df.iterrows():
        gid = g["game_id"]
        for team, role in [(g["home"], "home"), (g["away"], "away")]:
            opp_role = "away" if role == "home" else "home"

            # EV for (including adjusted)
            ef = ev_for[(ev_for["game_id"] == gid) & (ev_for["shooting_team"] == role)]
            eat_for = int(ef["ev_att_for"].iloc[0]) if len(ef) else 0
            exg_for = float(ef["ev_xg_for"].iloc[0]) if len(ef) else 0.0
            egl_for = int(ef["ev_goals_for"].iloc[0]) if len(ef) else 0
            eat_for_adj = float(ef["ev_att_for_adj"].iloc[0]) if len(ef) else 0.0
            exg_for_adj = float(ef["ev_xg_for_adj"].iloc[0]) if len(ef) else 0.0

            # EV against (including adjusted)
            ea = ev_against[(ev_against["game_id"] == gid) & (ev_against["opp_role"] == role)]
            eat_ag = int(ea["ev_att_against"].iloc[0]) if len(ea) else 0
            exg_ag = float(ea["ev_xg_against"].iloc[0]) if len(ea) else 0.0
            egl_ag = int(ea["ev_goals_against"].iloc[0]) if len(ea) else 0
            eat_ag_adj = float(ea["ev_att_against_adj"].iloc[0]) if len(ea) else 0.0
            exg_ag_adj = float(ea["ev_xg_against_adj"].iloc[0]) if len(ea) else 0.0

            ev_s = float(ev_secs.get(gid, 0))
            tot_s = float(total_secs_per_game.get(gid, 0))

            # PP for
            pf = pp_for[(pp_for["game_id"] == gid) & (pp_for["shooting_team"] == role)]
            ppat = int(pf["pp_att_for"].iloc[0]) if len(pf) else 0
            ppxg = float(pf["pp_xg_for"].iloc[0]) if len(pf) else 0.0

            # PK against
            pa = pp_against[(pp_against["game_id"] == gid) & (pp_against["opp_role"] == role)]
            pkat = int(pa["pk_att_against"].iloc[0]) if len(pa) else 0
            pkxg = float(pa["pk_xg_against"].iloc[0]) if len(pa) else 0.0

            # PP/PK seconds
            if role == "home":
                pp_s = float(pp_secs_home.get(gid, 0))
                pk_s = float(pk_secs_home.get(gid, 0))
            else:
                pp_s = float(pk_secs_home.get(gid, 0))  # away PP = home PK
                pk_s = float(pp_secs_home.get(gid, 0))  # away PK = home PP

            # Penalties
            pen = pen_by_game_team[(pen_by_game_team["game_id"] == gid) & (pen_by_game_team["team"] == role)]
            pens_taken = int(pen["penalties"].iloc[0]) if len(pen) else 0
            pen_drawn = pen_by_game_team[(pen_by_game_team["game_id"] == gid) & (pen_by_game_team["team"] == opp_role)]
            pens_drawn = int(pen_drawn["penalties"].iloc[0]) if len(pen_drawn) else 0

            rows.append({
                "game_id": gid, "season": g["season"], "date": g["date"],
                "team": team, "role": role,
                "ev_att_for": eat_for, "ev_att_against": eat_ag,
                "ev_xg_for": exg_for, "ev_xg_against": exg_ag,
                "ev_goals_for": egl_for, "ev_goals_against": egl_ag,
                "ev_att_for_adj": eat_for_adj, "ev_att_against_adj": eat_ag_adj,
                "ev_xg_for_adj": exg_for_adj, "ev_xg_against_adj": exg_ag_adj,
                "ev_seconds": ev_s, "total_seconds": tot_s,
                "pp_att_for": ppat, "pp_xg_for": ppxg, "pp_seconds": pp_s,
                "pk_att_against": pkat, "pk_xg_against": pkxg, "pk_seconds": pk_s,
                "penalties_taken": pens_taken, "penalties_drawn": pens_drawn,
            })

    df = pd.DataFrame(rows)
    print(f"  build_game_stats: {time.time()-t0:.1f}s, {len(df)} rows")
    return df


# ---------------------------------------------------------------------------
# S27 (Cowork, 2026-09-29): generic point-in-time rating engine.
# - Every team stat uses the same structure: league mean strictly before D (in-season),
#   carried-over prior as the season-long shrink target, shrink with measured K.
# - Hyperparameters (K, r, carry-over w) are measured ONCE on fit seasons by
#   --measure-hyper and read from JSON; the rating build never looks at other rows' futures.
# - K = n_half * (1 - r) / r, with n_half the measured mean games per split half
#   (the old compute_K(r, 82) used a full season for a half-season reliability -> 2x K).
# - S26 pre-registration HELD (score-adjusted 5v5 share r 0.925 >= 0.908), so 5v5 uses *_adj columns.
# ---------------------------------------------------------------------------
USE_ADJUSTED_5V5 = True
HYPER_PATH = OUT_DIR / "shrinkage_K.json"
GOALIE_GAMES_PATH = OUT_DIR / "goalie_games.parquet"


def team_stat_specs(adjusted=USE_ADJUSTED_5V5):
    """(rating column, numerator column, denominator column, scale, K group)."""
    if adjusted:
        af, aa, xf, xa = "ev_att_for_adj", "ev_att_against_adj", "ev_xg_for_adj", "ev_xg_against_adj"
    else:
        af, aa, xf, xa = "ev_att_for", "ev_att_against", "ev_xg_for", "ev_xg_against"
    return [
        ("ev_att_for_per60", af, "ev_seconds", 3600.0, "ev_att"),
        ("ev_att_against_per60", aa, "ev_seconds", 3600.0, "ev_att"),
        ("ev_xg_per_att_for", xf, af, 1.0, "ev_xg"),
        ("ev_xg_per_att_against", xa, aa, 1.0, "ev_xg"),
        ("pp_xg_for_per60", "pp_xg_for", "pp_seconds", 3600.0, "pp_xg"),
        ("pk_xg_against_per60", "pk_xg_against", "pk_seconds", 3600.0, "pk_xg"),
        ("penalties_taken_per60", "penalties_taken", "total_seconds", 3600.0, "pen_taken"),
        ("penalties_drawn_per60", "penalties_drawn", "total_seconds", 3600.0, "pen_drawn"),
    ]


def compute_split_half_r(df, stat_col, min_games=40, group_col="team"):
    """Mean-of-per-game split-half r (kept for the 5v5 share, as pre-registered in S26).
    Returns (r, n_pairs, mean games per half)."""
    df = df.copy()
    df["game_num"] = df.groupby([group_col, "season"]).cumcount() + 1
    df["half"] = df["game_num"] % 2
    halves, ns = {}, []
    for h in [0, 1]:
        hdf = df[df["half"] == h]
        g = hdf.groupby([group_col, "season"]).agg(val=(stat_col, "mean"), n=(stat_col, "count"))
        g = g[g["n"] >= min_games // 2]
        halves[h] = g["val"]
        ns.append(g["n"])
    both = pd.DataFrame({"odd": halves[1], "even": halves[0]}).dropna()
    if len(both) < 5:
        raise ValueError(f"split-half on {stat_col}: only {len(both)} pairs")
    n_half = float(pd.concat(ns).mean())
    return float(both["odd"].corr(both["even"])), len(both), n_half


def split_half_ratio(df, num, den, min_games=40, group_col="team"):
    """Ratio-of-sums split-half r for exposure-weighted rates (PP/PK/penalties).
    Returns (r, n_pairs, mean games per half)."""
    df = df.copy()
    df["game_num"] = df.groupby([group_col, "season"]).cumcount() + 1
    df["half"] = df["game_num"] % 2
    out, ns = {}, []
    for h in [0, 1]:
        g = df[df["half"] == h].groupby([group_col, "season"]).agg(s=(num, "sum"), d=(den, "sum"), n=(num, "count"))
        g = g[(g["n"] >= min_games // 2) & (g["d"] > 0)]
        out[h] = g["s"] / g["d"]
        ns.append(g["n"])
    both = pd.DataFrame({"odd": out[1], "even": out[0]}).dropna()
    if len(both) < 5:
        raise ValueError(f"split-half on {num}/{den}: only {len(both)} pairs")
    return float(both["odd"].corr(both["even"])), len(both), float(pd.concat(ns).mean())


def compute_K(r, n_half):
    """Reliability of n games = n / (n + K); split-half r is the reliability of n_half games.
    When r <= 0 (no stable signal), return a very large K (extreme shrinkage toward prior)."""
    if r <= 0:
        return 1e6  # effectively all-prior: rating = target
    return n_half * (1 - r) / r


def shrink(total, n, target, K):
    return (total + K * target) / (n + K)


def measure_hyper(tgs, fit_seasons=FIT_SEASONS, adjusted=USE_ADJUSTED_5V5):
    """Measure r and K per K-group on fit seasons. Written to HYPER_PATH by --measure-hyper."""
    fit = tgs[tgs["season"].isin(fit_seasons)].sort_values("date").copy()
    specs = {s[0]: s for s in team_stat_specs(adjusted)}
    af, aa, xf = specs["ev_att_for_per60"][1], specs["ev_att_against_per60"][1], specs["ev_xg_per_att_for"][1]
    fit["_share"] = fit[af] / (fit[af] + fit[aa]).clip(lower=1e-9)
    fit["_share_unadj"] = fit["ev_att_for"] / (fit["ev_att_for"] + fit["ev_att_against"]).clip(lower=1)
    fit["_xgpa"] = fit[xf] / fit[af].clip(lower=1e-9)
    hyper = {}
    r, n, nh = compute_split_half_r(fit, "_share")
    hyper["ev_att"] = {"r": r, "pairs": n, "n_half": nh, "K": compute_K(r, nh), "method": f"mean-of-games share {af}/({af}+{aa})"}
    r_u, _, _ = compute_split_half_r(fit, "_share_unadj")
    hyper["ev_att"]["r_unadjusted_for_record"] = r_u
    r, n, nh = compute_split_half_r(fit, "_xgpa")
    hyper["ev_xg"] = {"r": r, "pairs": n, "n_half": nh, "K": compute_K(r, nh), "method": f"mean-of-games {xf}/{af}"}
    for grp, num, den in [("pp_xg", "pp_xg_for", "pp_seconds"), ("pk_xg", "pk_xg_against", "pk_seconds"),
                          ("pen_taken", "penalties_taken", "total_seconds"), ("pen_drawn", "penalties_drawn", "total_seconds")]:
        r, n, nh = split_half_ratio(fit, num, den)
        hyper[grp] = {"r": r, "pairs": n, "n_half": nh, "K": compute_K(r, nh), "method": f"ratio-of-sums {num}/{den}"}
    hyper["_fit_seasons"] = list(fit_seasons)
    hyper["_adjusted_5v5"] = bool(adjusted)
    return hyper


def load_hyper():
    with open(HYPER_PATH) as f:
        return json.load(f)


def measure_carryover(tgs, adjusted=USE_ADJUSTED_5V5, fit_seasons=None):
    """Carry-over w per rating: slope of season[1] team rate on season[0] team rate (ratio of sums), clipped to [0, 1]."""
    fit = fit_seasons or FIT_SEASONS
    weights = {}
    for name, num, den, scale, _ in team_stat_specs(adjusted):
        prev = tgs[tgs["season"] == fit[0]].groupby("team").agg(s=(num, "sum"), d=(den, "sum"))
        curr = tgs[tgs["season"] == fit[1]].groupby("team").agg(s=(num, "sum"), d=(den, "sum"))
        prev["rate"] = prev["s"] / prev["d"] * scale
        curr["rate"] = curr["s"] / curr["d"] * scale
        both = prev[["rate"]].join(curr[["rate"]], lsuffix="_prev", rsuffix="_curr").dropna()
        if len(both) < 10:
            raise ValueError(f"carry-over {name}: only {len(both)} teams in both seasons")
        c = np.polyfit(both["rate_prev"], both["rate_curr"], 1)
        weights[name] = float(np.clip(c[0], 0, 1))
    return weights


def build_pit_ratings(tgs, fit_seasons=FIT_SEASONS, adjusted=USE_ADJUSTED_5V5, hyper=None, carryover=None):
    """Point-in-time team ratings. Rating on date D uses only rows with date < D of the same season,
    the previous seasons' finals, and the frozen hyperparameters (K, w)."""
    tgs = tgs.sort_values(["date", "game_id", "role"]).reset_index(drop=True)
    hyper = load_hyper() if hyper is None else hyper
    carryover = load_carryover() if carryover is None else carryover
    specs = team_stat_specs(adjusted)
    K = {grp: hyper[grp]["K"] for grp in {s[4] for s in specs}}
    W = {s[0]: carryover[s[0]] for s in specs}
    acc_cols = sorted({c for s in specs for c in (s[1], s[2])})

    def rate(src, num, den, scale):
        return src[num] / src[den] * scale if src[den] > 0 else np.nan

    prior_final, season_final_league, all_ratings = {}, {}, []
    for season in sorted(tgs["season"].unique()):
        s_tgs = tgs[tgs["season"] == season]
        # league cumulative sums strictly before each date
        day_sums = s_tgs.groupby("date")[acc_cols].sum()
        day_n = s_tgs.groupby("date").size()
        before = day_sums.cumsum().shift(1).fillna(0.0)
        before_n = day_n.cumsum().shift(1).fillna(0).astype(int)
        prev_lg = season_final_league.get(season - 1)
        team_cum = {t: dict({c: 0.0 for c in acc_cols}, n=0) for t in s_tgs["team"].unique()}

        for row in s_tgs.itertuples(index=False):
            r = row._asdict()
            team, d = r["team"], r["date"]
            tc = team_cum[team]
            lg_src, lg_n = before.loc[d], int(before_n.loc[d])
            out = {"game_id": r["game_id"], "season": season, "date": d, "team": team,
                   "role": r["role"], "n_prior_games": tc["n"]}
            # --- rating going INTO this game ---
            for name, num, den, scale, grp in specs:
                if lg_n >= 20 or prev_lg is None:
                    lg = rate(lg_src, num, den, scale)          # in-season, strictly before D (NaN on a season's first date with no prior season)
                else:
                    lg = prev_lg[name]                          # previous season's final league mean
                pf = prior_final.get(season - 1, {}).get(team)
                target = W[name] * pf[name] + (1 - W[name]) * lg if pf is not None else lg
                if tc["n"] == 0 or tc[den] <= 0:
                    val = target
                else:
                    val = shrink(rate(tc, num, den, scale) * tc["n"], tc["n"], target, K[grp])
                out[name] = val
                out[f"lg_{name}"] = lg                          # league mean used (point-in-time), for consumers
            all_ratings.append(out)
            # --- update running totals AFTER the rating is recorded ---
            for c in acc_cols:
                tc[c] += r[c]
            tc["n"] += 1

        prior_final[season] = {t: {name: rate(tc, num, den, scale) for name, num, den, scale, _ in specs}
                               for t, tc in team_cum.items() if tc["n"] > 0}
        tot = s_tgs[acc_cols].sum()
        season_final_league[season] = {name: rate(tot, num, den, scale) for name, num, den, scale, _ in specs}

    return pd.DataFrame(all_ratings), {"K": K, "w": W}


def build_goalie_games(shots_all, games_df, model):
    """One row per goalie start: the first goalie to face a non-empty-net attempt, and everything that team faced."""
    non_en = shots_all[~shots_all["empty_net"].astype(bool)].copy()
    non_en["xg"] = score_xg(non_en, model)
    rows = []
    for gid, g_shots in non_en.groupby("game_id"):
        g = games_df.loc[games_df["game_id"] == gid]
        if g.empty:
            continue
        g = g.iloc[0]
        for role, opp_role in [("home", "away"), ("away", "home")]:
            faced = g_shots[g_shots["shooting_team"] == opp_role].sort_values(["period", "seconds"])
            if len(faced) == 0:
                continue
            goalie_id = faced.iloc[0].get("goalie_id")
            if goalie_id is None or pd.isna(goalie_id):
                continue
            rows.append({
                "game_id": gid, "season": g["season"], "date": g["date"], "goalie_id": int(goalie_id),
                "team": g["home"] if role == "home" else g["away"], "role": role,
                "attempts_faced": len(faced), "xg_faced": float(faced["xg"].sum()),
                "goals_against": int(faced["is_goal"].sum()),
                "gsax": float(faced["xg"].sum()) - int(faced["is_goal"].sum()),
            })
    return pd.DataFrame(rows).sort_values(["date", "game_id", "role"]).reset_index(drop=True)


def measure_goalie_hyper(gdf, fit_seasons=FIT_SEASONS):
    fit = gdf[gdf["season"].isin(fit_seasons)].copy()
    r, n, nh = split_half_ratio(fit, "gsax", "attempts_faced", min_games=20, group_col="goalie_id")
    return {"r": r, "pairs": n, "n_half": nh, "K": compute_K(r, nh), "method": "ratio-of-sums gsax/attempts_faced, goalie-season halves (>=10 starts each)"}


def measure_goalie_carryover(gdf, fit_seasons=None):
    """Slope of season[1] GSAx/att on season[0] GSAx/att across goalies in both seasons."""
    fit = fit_seasons or FIT_SEASONS
    prev = gdf[gdf["season"] == fit[0]].groupby("goalie_id").agg(gsax=("gsax", "sum"), att=("attempts_faced", "sum"))
    curr = gdf[gdf["season"] == fit[1]].groupby("goalie_id").agg(gsax=("gsax", "sum"), att=("attempts_faced", "sum"))
    prev["rate"] = prev["gsax"] / prev["att"]
    curr["rate"] = curr["gsax"] / curr["att"]
    both = prev[["rate"]].join(curr[["rate"]], lsuffix="_p", rsuffix="_c").dropna()
    if len(both) < 10:
        raise ValueError(f"Too few goalies ({len(both)}) for carry-over measurement")
    return float(np.clip(np.polyfit(both["rate_p"], both["rate_c"], 1)[0], 0, 1))


def goalie_ratings_from_games(gdf, hyper=None, carryover=None):
    """Point-in-time goalie GSAx/attempt ratings from the per-start table."""
    hyper = load_hyper() if hyper is None else hyper
    carryover = load_carryover() if carryover is None else carryover
    K_g, w_g = hyper["goalie"]["K"], carryover["goalie_gsax_per_att"]
    gdf = gdf.sort_values(["date", "game_id", "role"]).reset_index(drop=True)
    ratings, last_season_rate = [], {}
    for season in sorted(gdf["season"].unique()):
        season_cum = {}
        for gg in gdf[gdf["season"] == season].itertuples(index=False):
            gs = season_cum.setdefault(gg.goalie_id, {"gsax": 0.0, "att": 0, "n": 0})
            # --- goalie rating going INTO this game ---
            target = w_g * last_season_rate[gg.goalie_id] if gg.goalie_id in last_season_rate else 0.0
            if gs["n"] == 0 or gs["att"] <= 0:
                rating = target
            else:
                rating = shrink(gs["gsax"] / gs["att"] * gs["n"], gs["n"], target, K_g)
            ratings.append({"game_id": gg.game_id, "season": season, "date": gg.date, "goalie_id": gg.goalie_id,
                            "team": gg.team, "role": gg.role, "n_prior_starts": gs["n"], "gsax_per_att_rating": rating})
            gs["gsax"] += gg.gsax
            gs["att"] += gg.attempts_faced
            gs["n"] += 1
        for gid_g, gs in season_cum.items():
            if gs["att"] > 0:
                last_season_rate[gid_g] = gs["gsax"] / gs["att"]
    return pd.DataFrame(ratings)


def build_goalie_ratings(shots_all, games_df, model):
    return goalie_ratings_from_games(build_goalie_games(shots_all, games_df, model))


FINISHING_PATH = OUT_DIR / "finishing_term.parquet"
FINISHING_WINDOW_DAYS = 30
FINISHING_MIN_GAMES = 150   # a full 30-day window holds ~200-240 games (measured); 300 was unreachable


def finishing_term_from_games(gdf, window_days=FINISHING_WINDOW_DAYS, min_games=FINISHING_MIN_GAMES):
    """S31 (Cowork): point-in-time league finishing term per game date.
    F(D) = sum(non-EN goals) / sum(non-EN xG) over games with date in [D - window, D - 1] in the same season.
    If that window holds fewer than min_games games, use the previous season's last `window_days` days of games.
    With neither available, NaN (2021-22 opening weeks only). Inputs: the per-start goalie table, which carries
    every non-empty-net attempt faced by each team (goals_against, xg_faced)."""
    pg = gdf.groupby(["game_id", "season", "date"], as_index=False).agg(goals=("goals_against", "sum"), xg=("xg_faced", "sum"))
    pg["d"] = pd.to_datetime(pg["date"])
    rows = []
    for season in sorted(pg["season"].unique()):
        S = pg[pg["season"] == season]
        P = pg[pg["season"] == season - 1]
        if len(P):
            last = P["d"].max()
            Pw = P[P["d"] > last - pd.Timedelta(days=window_days)]
            prev_F, prev_n = Pw["goals"].sum() / Pw["xg"].sum(), len(Pw)
        for D in sorted(S["d"].unique()):
            w = S[(S["d"] >= D - pd.Timedelta(days=window_days)) & (S["d"] < D)]
            if len(w) >= min_games:
                F, n, src = w["goals"].sum() / w["xg"].sum(), len(w), "in_season"
            elif len(P):
                F, n, src = prev_F, prev_n, "prev_season"
            else:
                F, n, src = np.nan, len(w), "none"
            rows.append({"date": pd.Timestamp(D).strftime("%Y-%m-%d"), "season": season, "F": F, "n_games": n, "source": src})
    return pd.DataFrame(rows)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure-hyper", action="store_true", help="measure K and carry-over w on fit seasons, write JSONs, then build")
    ap.add_argument("--build-stats-only", action="store_true")
    ap.add_argument("--from-cache", action="store_true", help="read team_game_stats.parquet and goalie_games.parquet instead of rebuilding")
    ap.add_argument("--fit-seasons", type=str, default=None, help="comma-separated start years for hyper/carryover (default: 2021,2022)")
    ap.add_argument("--all-seasons", type=str, default=None, help="comma-separated start years for game_stats/ratings (default: 2021..2025)")
    ap.add_argument("--out-dir", type=str, default=None, help="output directory (default: nhl/data/sim/ratings)")
    ap.add_argument("--const-path", type=str, default=None, help="path to constants_v2.json (default: standard)")
    args = ap.parse_args()

    fit = [int(s) for s in args.fit_seasons.split(",")] if args.fit_seasons else FIT_SEASONS
    all_s = [int(s) for s in args.all_seasons.split(",")] if args.all_seasons else ALL_SEASONS
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    hyper_path = out_dir / "shrinkage_K.json"
    carryover_path = out_dir / "carryover_w.json"
    goalie_games_path = out_dir / "goalie_games.parquet"
    finishing_path = out_dir / "finishing_term.parquet"

    if args.const_path:
        global CONST_PATH
        CONST_PATH = Path(args.const_path)

    if args.from_cache:
        tgs = pd.read_parquet(out_dir / "team_game_stats.parquet")
        gdf = pd.read_parquet(goalie_games_path)
    else:
        print(f"Loading data for seasons {all_s}...")
        games_df = get_game_info(all_s)
        shots_all = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "shots.parquet") for s in all_s], ignore_index=True)
        state_all = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "state_time.parquet") for s in all_s], ignore_index=True)
        pens_all = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "penalties.parquet") for s in all_s], ignore_index=True)
        gd = games_df[["game_id", "date", "season"]].drop_duplicates("game_id")
        shots_all = shots_all.merge(gd, on="game_id", how="left")
        state_all = state_all.merge(gd, on="game_id", how="left")
        pens_all = pens_all.merge(gd, on="game_id", how="left")
        model = load_xg_model()
        tgs = build_game_stats_vectorised(games_df, shots_all, state_all, pens_all, model)
        tgs.to_parquet(out_dir / "team_game_stats.parquet", index=False)
        if args.build_stats_only:
            return
        gdf = build_goalie_games(shots_all, games_df, model)
        gdf.to_parquet(goalie_games_path, index=False)

    if args.measure_hyper:
        hyper = measure_hyper(tgs, fit_seasons=fit)
        hyper["goalie"] = measure_goalie_hyper(gdf, fit_seasons=fit)
        w = measure_carryover(tgs, fit_seasons=fit)
        w["goalie_gsax_per_att"] = measure_goalie_carryover(gdf, fit_seasons=fit)
        w["_fit_seasons"] = list(fit)
        w["_derivation"] = f"slope of {fit[1]}-{fit[1]+1:02d} team (goalie) full-season rate on {fit[0]}-{fit[0]+1:02d}, ratio of sums, clipped to [0,1]"
        with open(hyper_path, "w") as f:
            json.dump(hyper, f, indent=2, sort_keys=True)
        with open(carryover_path, "w") as f:
            json.dump(w, f, indent=2, sort_keys=True)
        for k, v in hyper.items():
            print(k, v)
        for k, v in w.items():
            print("w", k, v)

    team_ratings, _ = build_pit_ratings(tgs, fit_seasons=fit,
                                         hyper=load_hyper() if hyper_path == HYPER_PATH else json.loads(hyper_path.read_text()),
                                         carryover=load_carryover() if carryover_path == CARRYOVER_PATH else json.loads(carryover_path.read_text()))
    team_ratings.to_parquet(out_dir / "team_ratings.parquet", index=False)
    goalie_ratings = goalie_ratings_from_games(gdf,
                                               hyper=load_hyper() if hyper_path == HYPER_PATH else json.loads(hyper_path.read_text()),
                                               carryover=load_carryover() if carryover_path == CARRYOVER_PATH else json.loads(carryover_path.read_text()))
    goalie_ratings.to_parquet(out_dir / "goalie_ratings.parquet", index=False)
    finishing = finishing_term_from_games(gdf)
    finishing.to_parquet(finishing_path, index=False)
    manifest = {
        "ratings_py_sha256": _sha(__file__),
        "carryover_w_sha256": _sha(carryover_path),
        "shrinkage_K_sha256": _sha(hyper_path),
        "team_game_stats_sha256": _sha(out_dir / "team_game_stats.parquet"),
        "goalie_games_sha256": _sha(goalie_games_path),
        "team_ratings_sha256": _sha(out_dir / "team_ratings.parquet"),
        "team_ratings_rows": len(team_ratings),
        "goalie_ratings_sha256": _sha(out_dir / "goalie_ratings.parquet"),
        "goalie_ratings_rows": len(goalie_ratings),
        "finishing_term_sha256": _sha(finishing_path),
        "finishing_term_rows": len(finishing),
    }
    with open(out_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
