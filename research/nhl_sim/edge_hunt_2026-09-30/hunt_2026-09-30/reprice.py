#!/usr/bin/env python3
"""Cowork re-pricer (C-01). Same as S41 price_games.price_season (seed = int(game_id), n_sims) but
(a) game list comes from the existing prices parquet (no boxscores needed), (b) --fix swaps the goalie
assignment back to the intended side, (c) multiprocessing.
Usage: python3 reprice.py --seasons 2022,2023 --out X.parquet [--fix] [--limit 20]
"""
import argparse, copy, sys, time
from pathlib import Path
import numpy as np, pandas as pd
from multiprocessing import Pool

ROOT = Path("/home/claude/hunt")
sys.path.insert(0, str(ROOT))
from nhl.sim.engine import simulate, league_average_inputs
from nhl.sim import game_inputs as GI

_DATA = {}


def init(fix):
    tr, gr, ft, q = GI.load_all()
    _DATA.update(tr=tr, gr=gr, ft=ft, q=q, base=league_average_inputs(), fix=fix)


def inputs_for(gid):
    tr, gr, ft, q, base = _DATA["tr"], _DATA["gr"], _DATA["ft"], _DATA["q"], _DATA["base"]
    inp = GI.game_inputs_for(gid, tr, gr, ft, q, base)
    if _DATA["fix"]:
        # committed code: h.goalie_save = 1 - a_gsax/q ; a.goalie_save = 1 - h_gsax/q  (swapped)
        # intended: home.goalie_save is the HOME goalie's factor (engine applies opp.goalie_save when the other team attacks)
        h_gs, a_gs = inp.home.goalie_save, inp.away.goalie_save
        inp.home.goalie_save, inp.away.goalie_save = a_gs, h_gs
    return inp


def price_one(args):
    gid, n_sims = args
    inp = inputs_for(gid)
    r = simulate(inp, n_sims, seed=int(gid))
    h, a = r["home_score"], r["away_score"]
    tot = h + a
    row = dict(game_id=gid,
               p_home_win=round(float((h > a).mean()), 4),
               p_reg_home=round(float(((r["decided"] == "REG") & (h > a)).mean()), 4),
               p_reg_tie=round(float((r["decided"] != "REG").mean()), 4),
               p_reg_away=round(float(((r["decided"] == "REG") & (a > h)).mean()), 4),
               p_home_m15=round(float(((h - a) >= 2).mean()), 4),
               mean_total=round(float(tot.mean()), 2),
               mean_home_goals=round(float(h.mean()), 4), mean_away_goals=round(float(a.mean()), 4),
               var_total=round(float(tot.var()), 4),
               n_sims=n_sims)
    for k in range(16):
        row[f"p_tot_{k}"] = round(float((tot == k).mean() if k < 15 else (tot >= 15).mean()), 6)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--n-sims", type=int, default=2000)
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    seasons = [int(s) for s in a.seasons.split(",")]
    gids = []
    for s in seasons:
        P = pd.read_parquet(ROOT / f"nhl/data/sim/prices/season={s}.parquet")
        gids += [str(g) for g in P.game_id]
    if a.limit:
        gids = gids[: a.limit]
    t0 = time.time()
    rows = []
    with Pool(a.procs, initializer=init, initargs=(a.fix,)) as p:
        for i, row in enumerate(p.imap_unordered(price_one, [(g, a.n_sims) for g in gids], chunksize=4)):
            rows.append(row)
            if (i + 1) % 100 == 0:
                print(f"{i+1}/{len(gids)} {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows).sort_values("game_id")
    df["season"] = df.game_id.str[:4].astype(int)
    df.to_parquet(a.out, index=False)
    print(f"DONE {len(df)} games {time.time()-t0:.0f}s fix={a.fix}", flush=True)


if __name__ == "__main__":
    main()
