#!/usr/bin/env python3
"""Run anchored backtest for one or more seasons. Usage: python3 nfl/sim/run_calibration.py [season]"""
import sys, time, os, numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "nfl", "data", "sim", "outputs")
os.makedirs(OUT, exist_ok=True)

_load_tables()
team_r, tend, sit, kicker, league = _load_ratings()
kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)
J_inv = np.array([[ 0.07450484,  0.10168527], [-0.08895527,  0.1277827 ]])

seasons = [int(s) for s in sys.argv[1:]] if len(sys.argv) > 1 else [2021, 2022, 2023, 2024]

for season in seasons:
    pbp = pd.read_parquet(os.path.join(ROOT, f"nfl/data/pbp/pbp_{season}.parquet"),
        columns=["game_id","season","week","home_team","away_team","home_score","away_score","spread_line","total_line"])
    sg = pbp.drop_duplicates("game_id")
    sg = sg[sg["week"] <= 18]
    print(f"Season {season}: {len(sg)} games", flush=True)

    rows = []
    t0 = time.time()
    for i, (_, g) in enumerate(sg.iterrows()):
        spread = g["spread_line"]; tl = g["total_line"]
        if pd.isna(spread) or pd.isna(tl):
            continue
        seed = hash((g["game_id"], 42)) % (2**31)
        # Run 1: base sim
        td = simulate_game(g["home_team"], g["away_team"], season, int(g["week"]),
                          n_sims=1000, seed=seed, **kw)
        m0 = (td["home_score"] - td["away_score"]).mean()
        t0v = (td["home_score"] + td["away_score"]).mean()
        # Newton step
        step = J_inv @ np.array([spread - m0, tl - t0v])
        # Run 2: anchored
        td2 = simulate_game(g["home_team"], g["away_team"], season, int(g["week"]),
                           n_sims=1000, seed=seed,
                           epa_home_offset=step[0], epa_away_offset=step[1], **kw)
        margin = (td2["home_score"] - td2["away_score"]).values.astype(float)
        total = (td2["home_score"] + td2["away_score"]).values.astype(float)
        am = g["home_score"] - g["away_score"]
        at_ = g["home_score"] + g["away_score"]
        rows.append({
            "game_id": g["game_id"], "season": season, "week": int(g["week"]),
            "raw_m": m0, "raw_t": t0v,
            "anch_m": margin.mean(), "anch_t": total.mean(),
            "mkt_m": float(spread), "mkt_t": float(tl),
            "actual_m": am, "actual_t": at_,
            "dh": step[0], "da": step[1],
            "pts_h": td2["home_score"].mean(), "pts_a": td2["away_score"].mean(),
            "p_hc": (margin - spread > 0).mean(), "ahc": int(am - spread > 0),
            "p_ov": (total > tl).mean(), "aov": int(at_ > tl),
            "p_m3": (np.abs(margin) == 3).mean(),
            "p_m7": (np.abs(margin) == 7).mean(),
            "sd_m": margin.std(),
            "p_hw": (margin > 0).mean(), "ahw": int(am > 0),
        })
        del td, td2
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(sg)} ({time.time()-t0:.0f}s)", flush=True)

    dt = time.time() - t0
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(OUT, f"anchored_{season}.parquet"), index=False)
    pts = (df["pts_h"].mean() + df["pts_a"].mean()) / 2
    print(f"  Done: {dt:.0f}s ({dt/len(sg):.1f}s/game), pts/team={pts:.1f}", flush=True)

# Combine all seasons
if len(seasons) > 1:
    all_dfs = []
    for s in seasons:
        fp = os.path.join(OUT, f"anchored_{s}.parquet")
        if os.path.exists(fp):
            all_dfs.append(pd.read_parquet(fp))
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined.to_parquet(os.path.join(OUT, "anchored_all.parquet"), index=False)
        pts = (combined["pts_h"].mean() + combined["pts_a"].mean()) / 2
        print(f"\nCombined: {len(combined)} games")
        print(f"  pts/team: {pts:.1f}")
        print(f"  P(|m|=3): {combined['p_m3'].mean()*100:.1f}%")
        print(f"  P(|m|=7): {combined['p_m7'].mean()*100:.1f}%")
        print(f"  SD margin: {np.sqrt((combined['sd_m']**2).mean()):.2f}")
        print(f"  Home cover accuracy: {((combined['p_hc']>0.5)==combined['ahc']).mean()*100:.1f}%")
        print(f"  Over/under accuracy: {((combined['p_ov']>0.5)==combined['aov']).mean()*100:.1f}%")
        print(f"  Margin MAE: {(combined['anch_m']-combined['actual_m']).abs().mean():.2f}")
