#!/usr/bin/env python3
"""
NFL Sim — K4 at real closing prices, reproducible from fit checkpoints.

Usage:
  python3 nfl/sim/run_k4.py --fit-dir fit_5d1 --output k4_rows.parquet
  python3 nfl/sim/run_k4.py --fit-dir fit_5d1 --output k4_new.parquet --legacy-actuals
"""

import argparse, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.names import (load_roster, _build_roster_lookup, resolve_player,
                            FULL_TO_ABBR, is_player_name)

PBP_DIR = ROOT / "nfl" / "data" / "pbp"
PROPS_DIR = ROOT / "data" / "odds_archive" / "nfl" / "props"

MKT_MAP = {
    "player_receptions": ("receptions", "prop_rec"),
    "player_reception_yds": ("rec_yds", "prop_rec_yds"),
    "player_rush_yds": ("rush_yds", "prop_rush_yds"),
    "player_rush_attempts": ("rush_att", "prop_rush_att"),
    "player_pass_yds": ("pass_yds", "prop_pass_yds"),
    "player_pass_attempts": ("pass_att", "prop_pass_att"),
    "player_pass_completions": ("pass_cmp", "prop_pass_cmp"),
    "player_pass_tds": ("pass_td", "prop_pass_td"),
    "player_anytime_td": ("atd", "prop_atd"),
}

COL_MAP = {
    "receptions": "receptions", "rec_yds": "rec_yds",
    "rush_yds": "rush_yds", "rush_att": "carries",
    "pass_yds": "pass_yds", "pass_att": "pass_att",
    "pass_cmp": "pass_cmp", "pass_td": "pass_td",
    "atd": "anytime_td",
}


def _legacy_actual_player_game_stats(game_pbp):
    """Pre-D62 actuals: kneels excluded, two-point runs included, spikes excluded."""
    passes = game_pbp[
        (game_pbp["play_type"] == "pass")
        & game_pbp["down"].notna()
        & (game_pbp.get("sack", pd.Series(0, index=game_pbp.index)) != 1)
    ]
    rec_rows = passes[passes["receiver_player_id"].notna()]
    if len(rec_rows) > 0:
        rec_stats = rec_rows.groupby("receiver_player_id").agg(
            actual_rec=("complete_pass", "sum")).reset_index().rename(
            columns={"receiver_player_id": "player_id"})
        completions = rec_rows[rec_rows["complete_pass"] == 1]
        if len(completions) > 0:
            rec_yds = completions.groupby("receiver_player_id")["yards_gained"].sum(
            ).reset_index().rename(
                columns={"receiver_player_id": "player_id", "yards_gained": "actual_rec_yds"})
            rec_stats = rec_stats.merge(rec_yds, on="player_id", how="left")
            rec_stats["actual_rec_yds"] = rec_stats["actual_rec_yds"].fillna(0).astype(int)
        else:
            rec_stats["actual_rec_yds"] = 0
    else:
        rec_stats = pd.DataFrame(columns=["player_id", "actual_rec", "actual_rec_yds"])

    rushes = game_pbp[
        (game_pbp["play_type"] == "run") & game_pbp["rusher_player_id"].notna()
    ]
    if len(rushes) > 0:
        rush_stats = rushes.groupby("rusher_player_id").agg(
            actual_rush_yds=("yards_gained", "sum"),
            actual_carries=("play_id", "count")).reset_index().rename(
            columns={"rusher_player_id": "player_id"})
    else:
        rush_stats = pd.DataFrame(columns=["player_id", "actual_rush_yds", "actual_carries"])

    if "td_player_id" in game_pbp.columns:
        td_pids = game_pbp[game_pbp["td_player_id"].notna()]["td_player_id"].unique()
    else:
        td_pids = []
    td_stats = pd.DataFrame({"player_id": list(td_pids), "actual_atd": 1}) if len(td_pids) > 0 else pd.DataFrame(columns=["player_id", "actual_atd"])

    if len(passes) > 0 and "passer_player_id" in passes.columns:
        pp = passes[passes["passer_player_id"].notna()]
        if len(pp) > 0:
            pass_stats = pp.groupby("passer_player_id").agg(
                actual_completions=("complete_pass", "sum"),
                actual_pass_att=("play_id", "count"),
                actual_pass_yds=("yards_gained", "sum")).reset_index().rename(
                columns={"passer_player_id": "player_id"})
            ptds = pp[pp.get("pass_touchdown", pd.Series(0, index=pp.index)) == 1]
            if len(ptds) > 0:
                ptd = ptds.groupby("passer_player_id").size().reset_index(
                    name="actual_pass_td").rename(columns={"passer_player_id": "player_id"})
                pass_stats = pass_stats.merge(ptd, on="player_id", how="left")
                pass_stats["actual_pass_td"] = pass_stats["actual_pass_td"].fillna(0).astype(int)
            else:
                pass_stats["actual_pass_td"] = 0
        else:
            pass_stats = pd.DataFrame(columns=["player_id", "actual_completions", "actual_pass_att", "actual_pass_yds", "actual_pass_td"])
    else:
        pass_stats = pd.DataFrame(columns=["player_id", "actual_completions", "actual_pass_att", "actual_pass_yds", "actual_pass_td"])

    return rec_stats, rush_stats, td_stats, pass_stats


def _load_consensus():
    """Load 2023-24 props, compute per-book closing, consensus devig."""
    frames = []
    for s in [2023, 2024]:
        sp = PROPS_DIR / f"season={s}"
        for f in sp.rglob("*.parquet"):
            df = pd.read_parquet(f)
            df["archive_season"] = s
            frames.append(df)
    all_props = pd.concat(frames, ignore_index=True)
    all_props = all_props[all_props["player_name"].apply(is_player_name)]
    all_props["commence_dt"] = pd.to_datetime(all_props["commence_time"], utc=True, errors="coerce")
    all_props["last_update_dt"] = pd.to_datetime(all_props["last_update"], utc=True, errors="coerce")
    pre = all_props[all_props["last_update_dt"] < all_props["commence_dt"]].copy()
    pre = pre.sort_values("last_update_dt", ascending=False)
    closing = pre.drop_duplicates(subset=["event_id", "bookmaker", "market_key", "player_name", "line"], keep="first")
    c2 = closing[closing.implied_over.notna() & closing.implied_under.notna()].copy()
    c2["total_imp"] = c2.implied_over + c2.implied_under
    c2["devig_over"] = c2.implied_over / c2.total_imp
    c2["devig_under"] = c2.implied_under / c2.total_imp
    c2["vig_pct"] = (c2.total_imp - 1.0) / 2.0
    cons = c2.groupby(["event_id", "market_key", "player_name", "line",
                        "home_team", "away_team", "game_date", "archive_season"]).agg(
        n_books=("bookmaker", "nunique"),
        med_devig_over=("devig_over", "median"),
        med_devig_under=("devig_under", "median"),
        med_vig=("vig_pct", "median")).reset_index()
    cons["home_abbr"] = cons.home_team.map(FULL_TO_ABBR)
    cons["away_abbr"] = cons.away_team.map(FULL_TO_ABBR)
    return cons


def run_k4(fit_dir, output_path, legacy_actuals=False):
    FIT_GAMES = ROOT / "nfl" / "data" / "sim" / "outputs" / fit_dir / "games"
    census = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "outputs" / fit_dir / "fit_census.parquet")
    cal = json.load(open(ROOT / "nfl" / "sim" / "calibration_v1.json"))
    cal_maps = cal["maps"]

    def _interp(p, fam):
        if fam in cal_maps:
            return float(np.interp(p, cal_maps[fam]["x"], cal_maps[fam]["y"]))
        return p

    pbp_cache = {}
    for s in [2021, 2022, 2023, 2024]:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if p.exists():
            pbp_cache[s] = pd.read_parquet(p)

    schedule_map = {}
    for s in [2023, 2024]:
        if s not in pbp_cache: continue
        g = pbp_cache[s].drop_duplicates("game_id")
        if "game_date" in g.columns:
            for _, r in g.iterrows():
                schedule_map[(str(r.game_date)[:10], r.home_team, r.away_team)] = r.game_id

    consensus = _load_consensus()
    consensus["game_id"] = consensus.apply(
        lambda r: schedule_map.get((str(r.game_date)[:10], r.home_abbr, r.away_abbr)), axis=1)
    consensus = consensus[consensus.game_id.notna()]

    roster = load_roster()
    rl = {}
    for s in [2023, 2024]:
        rl[s] = _build_roster_lookup(roster, s, 18)

    if legacy_actuals:
        actuals_fn = _legacy_actual_player_game_stats
    else:
        from nfl.sim.actuals import actual_player_game_stats
        actuals_fn = actual_player_game_stats

    census_gids = set(census.game_id)
    k4_rows = []
    t0 = time.time()

    for n, gid in enumerate(sorted(consensus.game_id.unique())):
        if gid not in census_gids:
            continue
        pp = FIT_GAMES / f"{gid}_players.parquet"
        if not pp.exists():
            continue
        pdf = pd.read_parquet(pp)
        N = int(pdf.sim_id.max()) + 1
        season = int(gid.split("_")[0])
        gpbp = pbp_cache.get(season)
        if gpbp is None:
            continue
        game_pbp = gpbp[gpbp.game_id == gid]
        if len(game_pbp) == 0:
            continue
        rec_stats, rush_stats, td_stats, pass_stats = actuals_fn(game_pbp)
        game_props = consensus[consensus.game_id == gid]

        for _, prop in game_props.iterrows():
            bt, bfl, bnl = rl.get(season, ({}, {}, {}))
            pid, _ = resolve_player(prop.player_name, season, 18,
                                     [prop.home_abbr, prop.away_abbr], bt, bfl, bnl)
            if not pid:
                continue
            mkt = prop.market_key
            if mkt not in MKT_MAP:
                continue
            fam_name, cal_prefix = MKT_MAP[mkt]
            psims = pdf[pdf.player_id == pid]
            if psims.empty:
                continue
            pos = psims.position.iloc[0]
            cal_fam = f"{cal_prefix}_{pos}"
            stats = pd.DataFrame({"sim_id": np.arange(N)}).merge(
                psims[["sim_id", "receptions", "rec_yds", "rush_yds", "carries",
                        "pass_att", "pass_cmp", "pass_yds", "pass_td", "anytime_td"]],
                on="sim_id", how="left").fillna(0)
            stat_col = COL_MAP.get(fam_name)
            if not stat_col:
                continue
            threshold = 0.5 if fam_name == "atd" else prop.line
            sim_p = float((stats[stat_col] >= (1 if fam_name == "atd" else threshold)).mean())
            cal_p = _interp(sim_p, cal_fam)

            if fam_name == "receptions":
                ar = rec_stats[rec_stats.player_id == pid]
                actual_val = int(ar.actual_rec.iloc[0]) if len(ar) else 0
            elif fam_name == "rec_yds":
                ar = rec_stats[rec_stats.player_id == pid]
                actual_val = int(ar.actual_rec_yds.iloc[0]) if len(ar) else 0
            elif fam_name == "rush_yds":
                ar = rush_stats[rush_stats.player_id == pid]
                actual_val = int(ar.actual_rush_yds.iloc[0]) if len(ar) else 0
            elif fam_name == "rush_att":
                ar = rush_stats[rush_stats.player_id == pid]
                actual_val = int(ar.actual_carries.iloc[0]) if len(ar) else 0
            elif fam_name == "pass_yds":
                ap = pass_stats[pass_stats.player_id == pid]
                actual_val = int(ap.actual_pass_yds.iloc[0]) if len(ap) else 0
            elif fam_name == "pass_att":
                ap = pass_stats[pass_stats.player_id == pid]
                actual_val = int(ap.actual_pass_att.iloc[0]) if len(ap) else 0
            elif fam_name == "pass_cmp":
                ap = pass_stats[pass_stats.player_id == pid]
                actual_val = int(ap.actual_completions.iloc[0]) if len(ap) else 0
            elif fam_name == "pass_td":
                ap = pass_stats[pass_stats.player_id == pid]
                actual_val = int(ap.actual_pass_td.iloc[0]) if len(ap) else 0
            elif fam_name == "atd":
                at = td_stats[td_stats.player_id == pid]
                actual_val = 1 if len(at) > 0 else 0
            else:
                continue

            hit_over = int(actual_val >= (1 if fam_name == "atd" else prop.line))
            k4_rows.append({
                "game_id": gid, "season": season, "player_id": pid,
                "player_name": prop.player_name, "position": pos,
                "family": fam_name, "line": threshold,
                "n_books": int(prop.n_books),
                "sim_p": sim_p, "cal_p": cal_p,
                "devig_over": prop.med_devig_over, "devig_under": prop.med_devig_under,
                "vig": prop.med_vig,
                "hit_over": hit_over, "hit_under": 1 - hit_over,
            })
        if (n + 1) % 100 == 0:
            print(f"  {n+1} games ({time.time()-t0:.0f}s)")

    k4 = pd.DataFrame(k4_rows)
    k4.to_parquet(output_path, index=False)
    print(f"Saved {len(k4)} rows to {output_path}")
    return k4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-dir", default="fit_5d1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--legacy-actuals", action="store_true",
                        help="Use pre-D62 actuals (kneels excluded, spikes excluded)")
    args = parser.parse_args()
    run_k4(args.fit_dir, Path(args.output), legacy_actuals=args.legacy_actuals)


if __name__ == "__main__":
    main()
