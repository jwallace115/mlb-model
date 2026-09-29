#!/usr/bin/env python3
"""S33/S35 realism report: league-average engine vs the ACTUAL 2022-23 regular season (fit season: a mechanics
check, not predictive evidence). All games are identical league-average matchups, so one matchup is simulated
n times (batches of 10,000 with seeds 0..).
Usage: python3 nhl/sim/realism_report.py [--n-sims 100000] [--season 2022]"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from nhl.sim.engine import simulate, league_average_inputs

EV = ROOT / "nhl" / "data" / "sim" / "events"
BOX = ROOT / "nhl" / "cache"
PP_STATES = ["5v4", "5v3", "4v3"]
# pre-registered in research/nhl_sim/workorder_S4a_2026-09-29.md (S33); unchanged
BANDS = {"goals_per_game": ("rel", 0.03), "tied_after_reg": ("abs", 0.020), "so_share": ("abs", 0.015),
         "pp_opps_per_team": ("rel", 0.05), "pp_goals_per_team": ("rel", 0.08), "en_goals_per_game": ("rel", 0.15),
         "reg_one_goal_share": ("abs", 0.020), "home_win": ("abs", 0.020), "total_dist_maxdiff": ("max", 0.015)}


def actuals(season):
    rows = []
    for i in range(1, 1313):
        p = BOX / f"boxscore_{season}02{i:04d}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        rows.append({"game_id": f"{season}02{i:04d}", "h": d["homeTeam"]["score"], "a": d["awayTeam"]["score"],
                     "type": d.get("gameOutcome", {}).get("lastPeriodType", "REG")})
    g = pd.DataFrame(rows)
    shots = pd.read_parquet(EV / f"season={season}" / "shots.parquet")
    shots = shots[shots.game_id.isin(g.game_id)]
    st = pd.read_parquet(EV / f"season={season}" / "state_time.parquet")
    pe = pd.read_parquet(EV / f"season={season}" / "penalties.parquet")
    n = len(g)
    # PP opportunities: penalties that raise the opponent's skater advantage (same rule as constants_v7)
    st = st.sort_values(["game_id", "start_sec"]).assign(adv=lambda x: x.home_skaters - x.away_skaters)
    idx = {k: (v.start_sec.to_numpy(), v.end_sec.to_numpy(), v.adv.to_numpy()) for k, v in st.groupby("game_id")}
    def adv_at(gid, t):
        s, e, a = idx[gid]; i = np.searchsorted(s, t, side="right") - 1
        return int(a[i]) if i >= 0 and t < e[i] else None
    n_pp = 0
    for r in pe[pe.game_id.isin(g.game_id)].itertuples(index=False):
        if r.game_id not in idx: continue
        a0, a1 = adv_at(r.game_id, max(r.seconds - 1, 0)), adv_at(r.game_id, r.seconds + 2)
        if a0 is None or a1 is None: continue
        n_pp += ((a0 - a1) if r.team == "home" else (a1 - a0)) > 0
    pp_secs = st[(st.home_skaters > st.away_skaters) | (st.away_skaters > st.home_skaters)]
    pp_secs = pp_secs[(pp_secs.home_goalie == 1) & (pp_secs.away_goalie == 1)].duration.sum()
    reg = g[g.type == "REG"]
    tot = g.h + g.a
    return {
        "n_games": n,
        "goals_per_game": tot.mean(),
        "tied_after_reg": (g.type != "REG").mean(),
        "so_share": (g.type == "SO").mean(),
        "pp_opps_per_team": n_pp / (2 * n),
        "pp_goals_per_team": shots[shots.strength.isin(PP_STATES) & (shots.is_goal == 1)].shape[0] / (2 * n),
        "pp_minutes_per_team": pp_secs / 60 / (2 * n),
        "en_goals_per_game": shots[shots.empty_net.astype(bool) & (shots.is_goal == 1)].shape[0] / n,
        "reg_one_goal_share": ((reg.h - reg.a).abs() == 1).mean(),
        "home_win": (g.h > g.a).mean(),
        "total_dist": np.bincount(np.clip(tot, 0, 13), minlength=14)[:13] / n,
        "penalties_per_team_all_types": len(pe[pe.game_id.isin(g.game_id)]) / (2 * n),
    }


def simulated(n_sims):
    inp = league_average_inputs()
    parts = [simulate(inp, 10000, seed=s) for s in range(int(np.ceil(n_sims / 10000)))]
    r = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    tot = r["home_score"] + r["away_score"]
    regm = r["decided"] == "REG"
    return {
        "n_games": len(tot),
        "goals_per_game": tot.mean(),
        "tied_after_reg": (~regm).mean(),
        "so_share": (r["decided"] == "SO").mean(),
        "pp_opps_per_team": (r["home_pp_opps"] + r["away_pp_opps"]).mean() / 2,
        "pp_goals_per_team": (r["home_pp_goals"] + r["away_pp_goals"]).mean() / 2,
        "pp_minutes_per_team": (r["home_pp_seconds"] + r["away_pp_seconds"]).mean() / 2 / 60,
        "en_goals_per_game": (r["home_en_goals"] + r["away_en_goals"]).mean(),
        "reg_one_goal_share": (np.abs(r["home_score"] - r["away_score"])[regm] == 1).mean(),
        "home_win": (r["home_score"] > r["away_score"]).mean(),
        "total_dist": np.bincount(np.clip(tot, 0, 13), minlength=14)[:13] / len(tot),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-sims", type=int, default=100000)
    ap.add_argument("--season", type=int, default=2022)
    a = ap.parse_args()
    t0 = time.time()
    act = actuals(a.season)
    sim = simulated(a.n_sims)
    print(f"season {a.season}: actual games {act['n_games']}, sims {sim['n_games']}, {time.time()-t0:.0f}s")
    print(f"{'metric':24s} {'sim':>8s} {'actual':>8s} {'diff':>9s}  band      held")
    for k, (kind, tol) in BANDS.items():
        if k == "total_dist_maxdiff":
            d = np.abs(sim["total_dist"] - act["total_dist"])
            print(f"{k:24s} {d.max():8.4f} {'':>8s} {'':>9s}  <={tol:<6} {'HELD' if d.max() <= tol else 'NOT HELD'}  (worst k={d.argmax()})")
            continue
        s, x = sim[k], act[k]
        diff = (s - x) / x if kind == "rel" else s - x
        ok = abs(diff) <= tol
        print(f"{k:24s} {s:8.4f} {x:8.4f} {diff:+9.4f}  +-{tol:<6} {'HELD' if ok else 'NOT HELD'}")
    print(f"{'pp_minutes_per_team':24s} {sim['pp_minutes_per_team']:8.3f} {act['pp_minutes_per_team']:8.3f}   (diagnostic)")
    print(f"penalties per team, all types (actual, diagnostic): {act['penalties_per_team_all_types']:.3f}")
    print("total goals k: " + " ".join(f"{k}:{s:.3f}/{x:.3f}" for k, (s, x) in enumerate(zip(sim['total_dist'], act['total_dist']))))


if __name__ == "__main__":
    main()
