#!/usr/bin/env python3
"""Ledger E-02: live engine (StartState) vs live Pinnacle, 2023-24. Stage 1 = price every live/intermission row
(this script, multiprocessing); stage 2 = e02_report.py. Engine conditioned on the PRE-GAME Pinnacle close only."""
import sys, json, time, hashlib, numpy as np, pandas as pd
from multiprocessing import Pool
from scipy.optimize import least_squares
sys.path.insert(0, "/home/claude/hunt")
from nhl.sim.engine import simulate, league_average_inputs, TeamMultipliers, StartState
H = "/home/claude/hunt"; E = f"{H}/e"
g = np.load(f"{H}/research/nhl_sim/edge_hunt_2026-09-30/market_grid_v1_cowork.npz")
S, M, J = g["S"], g["M"], g["J"]
Hh = np.arange(16)[:, None]; Aa = np.arange(16)[None, :]; TOT = Hh + Aa
NS = 2000


def interp(s, m):
    fi = np.interp(s, S, np.arange(len(S))); fj = np.interp(m, M, np.arange(len(M)))
    i0, j0 = min(int(fi), len(S) - 2), min(int(fj), len(M) - 2); di, dj = fi - i0, fj - j0
    return ((1 - di) * (1 - dj) * J[i0, j0] + di * (1 - dj) * J[i0 + 1, j0] + (1 - di) * dj * J[i0, j0 + 1] + di * dj * J[i0 + 1, j0 + 1])


def solve(ph, po, pt):
    def f(x):
        Jx = interp(*x); o = Jx[TOT > pt].sum(); push = Jx[TOT == pt].sum()
        return [Jx[Hh > Aa].sum() - ph, o / (1 - push) - po]
    r = least_squares(f, x0=[0.0, 1.0], bounds=([S[0], M[0]], [S[-1], M[-1]]))
    return r.x, np.max(np.abs(r.fun)) <= 0.005


_BASE = None


def init():
    global _BASE; _BASE = league_average_inputs()


def price_row(a):
    gid, ts, s, m, phase, period, sec, hs, as_, ph, pa, pen_h, pen_a = a
    import copy
    inp = copy.deepcopy(_BASE)
    inp.home = TeamMultipliers(finishing=m * np.exp(s / 2), goalie_save=np.exp(-s / 2))
    inp.away = TeamMultipliers(finishing=m * np.exp(-s / 2), goalie_save=np.exp(s / 2))
    if phase == "intermission":
        period, second = int(period) + 1, 0
    else:
        period = int(period); second = int(sec) - (period - 1) * 1200 if period <= 3 else int(sec) - 3600
    if period >= 5:
        return dict(game_id=gid, ts=ts, skipped="shootout")
    st = StartState(period=period, second=max(0, min(second, 1199 if period <= 3 else 299)), home_score=int(hs), away_score=int(as_),
                    home_penalties=[tuple(p) for p in json.loads(pen_h or "[]")], away_penalties=[tuple(p) for p in json.loads(pen_a or "[]")],
                    home_pulled=bool(ph), away_pulled=bool(pa))
    seed = int(hashlib.sha256(f"{gid}|{ts}".encode()).hexdigest()[:8], 16)
    r = simulate(inp, NS, seed=seed, start_state=st)
    h, a = r["home_score"], r["away_score"]; tot = h + a
    out = dict(game_id=gid, ts=ts, e_p_home=float((h > a).mean()), e_mean_total=float(tot.mean()),
               e_p_reg_tie=float((r["decided"] != "REG").mean()))
    for k in range(int(hs + as_), 16):
        out[f"e_tot_{k}"] = float((tot == k).mean() if k < 15 else (tot >= 15).mean())
    return out


def main():
    T = pd.read_parquet(f"{E}/state_at_snapshot_2023.parquet")
    hcols = [c for c in T.columns if c.endswith("_dec_h")]
    T["n_books_h2h"] = T[hcols].notna().sum(axis=1)
    T = T[T.phase.isin(["live", "intermission"]) & (T.n_books_h2h >= 3) & T.pin_p_h_pre.notna() & T.tl_pin_pre.notna() & T.pin_p_over_pre.notna()].copy()
    T = T[(T.phase == "intermission") | T.home_skaters.notna()].copy()
    print("rows to price", len(T), T.phase.value_counts().to_dict(), flush=True)
    # conditioning per game (pre-game Pinnacle close) — solve once per game
    cond = {}
    for gid, x in T.groupby("game_id"):
        r0 = x.iloc[0]; (s, m), ok = solve(r0.pin_p_h_pre, r0.pin_p_over_pre, r0.tl_pin_pre); cond[gid] = (s, m, ok)
    print("games", len(cond), "converged", sum(v[2] for v in cond.values()), flush=True)
    T["s"] = T.game_id.map(lambda k: cond[k][0]); T["m"] = T.game_id.map(lambda k: cond[k][1]); T = T[T.game_id.map(lambda k: cond[k][2])]
    args = []
    for r in T.itertuples():
        args.append((int(r.game_id), str(r.ts), float(r.s), float(r.m), r.phase, r.period, r.sec, r.hs, r.as_,
                     0 if r.phase == "intermission" else int(r.home_goalie == 0), 0 if r.phase == "intermission" else int(r.away_goalie == 0),
                     None if r.phase == "intermission" else r.pen_home, None if r.phase == "intermission" else r.pen_away))
    t0 = time.time(); rows = []
    with Pool(2, initializer=init) as p:
        for i, o in enumerate(p.imap_unordered(price_row, args, chunksize=8)):
            rows.append(o)
            if (i + 1) % 500 == 0: print(f"{i+1}/{len(args)} {time.time()-t0:.0f}s", flush=True)
    R = pd.DataFrame(rows); R["ts"] = pd.to_datetime(R.ts)
    R.to_parquet(f"{E}/e02_engine_live_2023.parquet", index=False)
    print("DONE", len(R), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
