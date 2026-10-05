#!/usr/bin/env python3
"""D7: price every walk-forward game (2012-13..2020-21) using per-season constants/ratings.

For each target season T, loads constants and ratings from
nhl/data/sim/walkforward/season=T/ and prices all games in that season.

Usage:
  python3 nhl/sim/price_walkforward.py                # all 9 seasons
  python3 nhl/sim/price_walkforward.py --targets 2015  # single season
  python3 nhl/sim/price_walkforward.py --n-sims 2000   # (default)
"""
import json, sys, time, hashlib, copy
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nhl.sim.engine import simulate, league_average_inputs, GameInputs
from nhl.sim.game_inputs import build_team_mult, game_inputs_for
from nhl.sim.build_events import GAMES_PER_SEASON_MAP

BOX_DIR = ROOT / "nhl" / "cache"
WF_DIR = ROOT / "nhl" / "data" / "sim" / "walkforward"
PRICES_DIR = ROOT / "nhl" / "data" / "sim" / "prices"


def load_wf_inputs(T):
    """Load per-season inputs from walkforward directory."""
    wf = WF_DIR / f"season={T}"
    tr = pd.read_parquet(wf / "team_ratings.parquet")
    gr = pd.read_parquet(wf / "goalie_ratings.parquet")
    ft = pd.read_parquet(wf / "finishing_term.parquet")
    c8 = json.loads((wf / "constants_v8.json").read_text())
    q = c8["constants"]["q_league_xg_per_non_en_attempt"]["value"]
    meta = json.loads((wf / "meta.json").read_text())
    ot_base = meta.get("ot_base_skaters", 3)
    # Build league-average inputs from these constants
    base_inp = league_average_inputs(
        c7_path=str(wf / "constants_v8.json"),
    )
    base_inp.ot_base_skaters = ot_base
    return tr, gr, ft, q, base_inp


def price_season(season, n_sims, tr, gr, ft, q, base_inp):
    """Simulate every game in a season and compute prices."""
    rows = []
    t0 = time.time()
    n_games = GAMES_PER_SEASON_MAP.get(season, 1312)

    for i in range(1, n_games + 1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists():
            continue
        with open(bp) as f:
            d = json.load(f)
        home = d["homeTeam"]["abbrev"]
        away = d["awayTeam"]["abbrev"]
        date = d.get("gameDate", "")

        try:
            inp = game_inputs_for(gid, tr, gr, ft, q, base_inp)
        except ValueError as e:
            # For walk-forward pricing, missing goalie data in pre-2019 PBP is
            # a known data gap (1 game in 2019-20). Log and skip rather than HALT.
            print(f"  SKIP {gid}: {e}", file=sys.stderr, flush=True)
            continue

        seed = int(gid)
        r = simulate(inp, n_sims, seed=seed)

        p_home_win = (r["home_score"] > r["away_score"]).mean()
        p_reg_home = ((r["decided"] == "REG") & (r["home_score"] > r["away_score"])).mean()
        p_reg_tie = (r["decided"] != "REG").mean()
        p_reg_away = ((r["decided"] == "REG") & (r["away_score"] > r["home_score"])).mean()
        p_home_m15 = ((r["home_score"] - r["away_score"]) >= 2).mean()
        p_away_p15 = 1.0 - p_home_m15
        mean_total = (r["home_score"] + r["away_score"]).mean()

        totals = r["home_score"] + r["away_score"]
        tot_dist = {}
        for k in range(16):
            if k < 15:
                tot_dist[f"p_tot_{k}"] = round(float((totals == k).mean()), 6)
            else:
                tot_dist[f"p_tot_{k}"] = round(float((totals >= k).mean()), 6)

        row = {
            "game_id": gid, "season": season, "date": date, "home": home, "away": away,
            "p_home_win": round(p_home_win, 4),
            "p_reg_home": round(p_reg_home, 4),
            "p_reg_tie": round(p_reg_tie, 4),
            "p_reg_away": round(p_reg_away, 4),
            "p_home_m15": round(p_home_m15, 4),
            "p_away_p15": round(p_away_p15, 4),
            "mean_total": round(mean_total, 2),
            "mean_home_goals": round(float(r["home_score"].mean()), 4),
            "mean_away_goals": round(float(r["away_score"].mean()), 4),
            "n_sims": n_sims,
            **tot_dist,
        }
        rows.append(row)

        if i % 200 == 0:
            print(f"  [{i}/{n_games}] {time.time()-t0:.0f}s", flush=True)

    elapsed = time.time() - t0
    print(f"  Season {season}: {len(rows)} games priced, {elapsed:.0f}s ({elapsed/len(rows):.2f}s/game)")
    return pd.DataFrame(rows)


def _price_one_season(args_tuple):
    """Worker function for multiprocessing. Returns (T, df, elapsed)."""
    T, n_sims = args_tuple
    tr, gr, ft, q, base_inp = load_wf_inputs(T)
    tr_t = tr[tr["season"] == T]
    gr_t = gr[gr["season"] == T]
    ft_t = ft[ft["season"] == T]
    t0 = time.time()
    df = price_season(T, n_sims, tr_t, gr_t, ft_t, q, base_inp)
    out_path = PRICES_DIR / f"season={T}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    sha = hashlib.sha256(out_path.read_bytes()).hexdigest()[:16]
    elapsed = time.time() - t0
    print(f"  Season {T}: saved {len(df)} rows, sha={sha}, {elapsed:.0f}s", flush=True)
    return T, len(df), elapsed


def main():
    import argparse
    from multiprocessing import Pool
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", type=str, default="2012,2013,2014,2015,2016,2017,2018,2019,2020")
    ap.add_argument("--n-sims", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    targets = [int(s) for s in args.targets.split(",")]

    PRICES_DIR.mkdir(parents=True, exist_ok=True)

    total_games = sum(GAMES_PER_SEASON_MAP.get(T, 1312) for T in targets)
    est_min = total_games * 1.2 / args.workers / 60
    print(f"Runtime pre-check: {total_games} games x ~1.2 s/game / {args.workers} workers = {est_min:.0f} min")
    print(f"Starting pricing with {args.n_sims} sims per game, {args.workers} workers...\n")

    t_total = time.time()
    work = [(T, args.n_sims) for T in targets]

    with Pool(args.workers) as pool:
        results = pool.map(_price_one_season, work)

    total_elapsed = time.time() - t_total
    total_rows = sum(r[1] for r in results)
    print(f"\nTotal: {total_rows} games, {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
