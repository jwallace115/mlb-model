#!/usr/bin/env python3
"""Ledger B-01: engine-conditioned 3-way (regulation) vs the books, 2024-25. One run. EXPLORATORY (see ledger)."""
import glob, numpy as np, pandas as pd, statsmodels.api as sm
from scipy.optimize import least_squares, brentq
from scipy.stats import norm

H = "/home/claude/hunt"
GRID = f"{H}/work/market_grid_v2.npz"
TW = sorted(glob.glob(f"{H}/data/odds_archive/nhl/history/threeway/season=2024/*.parquet"))
LA = f"{H}/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet"
GL = f"{H}/research/nhl_sim/edge_hunt_2026-09-30/games_lines.parquet"
THR = 0.03
g = np.load(GRID)
S, M, J, JR = g["S"], g["M"], g["J"], g["JR"]
Hh = np.arange(16)[:, None]; Aa = np.arange(16)[None, :]; TOT = Hh + Aa
lg = lambda p: np.log(p / (1 - p))


def interp(T, s, m):
    fi = np.interp(s, S, np.arange(len(S))); fj = np.interp(m, M, np.arange(len(M)))
    i0, j0 = min(int(fi), len(S) - 2), min(int(fj), len(M) - 2)
    di, dj = fi - i0, fj - j0
    return ((1 - di) * (1 - dj) * T[i0, j0] + di * (1 - dj) * T[i0 + 1, j0] + (1 - di) * dj * T[i0, j0 + 1] + di * dj * T[i0 + 1, j0 + 1])


def solve(ph, po, pt):
    def f(x):
        Jx = interp(J, *x)
        o = Jx[TOT > pt].sum(); push = Jx[TOT == pt].sum()
        return [Jx[Hh > Aa].sum() - ph, o / (1 - push) - po]
    r = least_squares(f, x0=[0.0, 1.0], bounds=([S[0], M[0]], [S[-1], M[-1]]))
    return r.x, np.max(np.abs(r.fun)) <= 0.005


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def power_devig(imp):
    """Find k with sum(imp**k) = 1."""
    f = lambda k: np.sum(imp ** k) - 1
    k = brentq(f, 0.5, 5.0)
    return imp ** k


def main():
    t = pd.concat([pd.read_parquet(f) for f in TW])
    t["snap"] = pd.to_datetime(t.snapshot_utc)
    last = t.groupby(["event_id", "bookmaker"]).snap.max().rename("snap_last")   # keep each book's LAST snapshot per event
    t = t.merge(last, on=["event_id", "bookmaker"]); t = t[t.snap == t.snap_last].drop(columns="snap_last")
    t["dec"] = dec(t.price); t["imp"] = 1 / t.dec
    t["side"] = np.where(t.outcome_name == "Draw", "draw", np.where(t.outcome_name == t.home_team, "home", "away"))
    snap3 = t[t.bookmaker == "pinnacle"].groupby("event_id").snap.max().rename("snap3")
    # last 2-way Pinnacle snapshot at or before the 3-way snapshot
    d = pd.read_parquet(LA); d = d[d.event_id.isin(snap3.index) & (d.bookmaker == "pinnacle")].copy()
    d["snap"] = pd.to_datetime(d.snapshot_utc); d = d.merge(snap3, on="event_id"); d = d[d.snap <= d.snap3]
    last = d.groupby("event_id").snap.max().rename("snap2"); d = d.merge(last, on="event_id"); d = d[d.snap == d.snap2]
    d["dec"] = dec(d.price)
    rows = []
    for e, x in d.groupby("event_id"):
        home, away = x.home_team.iloc[0], x.away_team.iloc[0]
        h2 = x[x.market == "h2h"]; to = x[x.market == "totals"]
        hp, ap = h2[h2.outcome_name == home].dec, h2[h2.outcome_name == away].dec
        if len(hp) != 1 or len(ap) != 1 or len(to) != 2 or to.point.nunique() != 1:
            continue
        ph = (1 / hp.iloc[0]) / (1 / hp.iloc[0] + 1 / ap.iloc[0])
        io = 1 / to[to.outcome_name == "Over"].dec.iloc[0]; iu = 1 / to[to.outcome_name == "Under"].dec.iloc[0]
        rows.append(dict(event_id=e, ph=ph, po=io / (io + iu), pt=float(to.point.iloc[0]), gap_h=(x.snap3.iloc[0] - x.snap.iloc[0]).total_seconds() / 3600))
    C = pd.DataFrame(rows)
    print(f"events with 3-way: {snap3.size}; with a prior Pinnacle 2-way snapshot: {len(C)}; gap hours median {C.gap_h.median():.2f}, 90th pct {C.gap_h.quantile(.9):.2f}")
    # engine conditioning
    out = []
    for r in C.itertuples():
        x, ok = solve(r.ph, r.po, r.pt)
        Rx = interp(JR, *x)
        out.append(dict(event_id=r.event_id, ok=ok, s=x[0], m=x[1], e_home=Rx[Hh > Aa].sum(), e_draw=Rx[Hh == Aa].sum(), e_away=Rx[Hh < Aa].sum()))
    E = pd.DataFrame(out); print(f"conditioning converged: {int(E.ok.sum())}/{len(E)}")
    E = E[E.ok]
    # outcomes
    G = pd.read_parquet(GL); G = G[G.season == 2024][["event_id", "date", "hg", "ag", "decided", "home_win", "pin_p_h"]]
    E = E.merge(G, on="event_id")
    E["res"] = np.where(E.decided != "REG", "draw", np.where(E.home_win == 1, "home", "away"))
    print(f"events with outcome: {len(E)}; actual draw rate {(E.res=='draw').mean():.4f}; engine mean draw {E.e_draw.mean():.4f}")
    # Pinnacle 3-way fair (multiplicative + power)
    p3 = t[(t.bookmaker == "pinnacle") & t.event_id.isin(E.event_id)].pivot_table(index="event_id", columns="side", values="imp", aggfunc="first")
    p3 = p3.dropna(); ov = p3.sum(axis=1)
    mult = p3.div(ov, axis=0)
    pw = pd.DataFrame([power_devig(np.array(r, float)) for r in p3.itertuples(index=False)], index=p3.index, columns=p3.columns)
    E = E.merge(mult.add_prefix("pm_"), on="event_id").merge(pw.add_prefix("pp_"), on="event_id")
    print(f"Pinnacle 3-way overround mean {ov.mean():.4f}; fair draw: multiplicative {E.pm_draw.mean():.4f}, power {E.pp_draw.mean():.4f}")
    Y = pd.get_dummies(E.res)[["home", "draw", "away"]].to_numpy().astype(float)
    def ll3(P):
        P = np.clip(P, 1e-4, 1); return float(-np.mean(np.sum(Y * np.log(P), axis=1)))
    print(f"3-class log-loss: engine {ll3(E[['e_home','e_draw','e_away']].to_numpy()):.4f} | Pinnacle mult {ll3(E[['pm_home','pm_draw','pm_away']].to_numpy()):.4f} | Pinnacle power {ll3(E[['pp_home','pp_draw','pp_away']].to_numpy()):.4f}")
    # draw calibration by engine-draw bin
    E["bin"] = pd.qcut(E.e_draw, 5, duplicates="drop")
    print(E.groupby("bin", observed=True).agg(n=("res", "size"), eng=("e_draw", "mean"), pin_mult=("pm_draw", "mean"), pin_pow=("pp_draw", "mean"), actual=("res", lambda s: (s == "draw").mean())).round(4).to_string())
    # H-B01a / b
    for name, y, pe, pp in [("H-B01a DRAW", (E.res == "draw").astype(float), E.e_draw, E.pp_draw), ("H-B01b REG HOME", (E.res == "home").astype(float), E.e_home, E.pp_home)]:
        pe = np.clip(pe, 1e-3, 1 - 1e-3); pp = np.clip(pp, 1e-3, 1 - 1e-3)
        f = sm.Logit(y.to_numpy(), sm.add_constant(np.column_stack([lg(pp), lg(pe) - lg(pp)]))).fit(disp=0)
        b, se = f.params[2], f.bse[2]
        print(f"{name}: n={len(E)} disagreement coef {b:+.3f} 90% CI [{b-1.6449*se:+.3f}, {b+1.6449*se:+.3f}] one-sided p {1-norm.cdf(b/se):.4f} | mean |eng-pin| {np.abs(pe-pp).mean():.4f}")
    # H-B01c economics at every book
    q = t[t.event_id.isin(E.event_id)].merge(E[["event_id", "e_home", "e_draw", "e_away", "res"]], on="event_id")
    q["e"] = np.where(q.side == "draw", q.e_draw, np.where(q.side == "home", q.e_home, q.e_away))
    q["edge"] = q.e - q.imp
    q["ret"] = np.where(q.res == q.side, q.dec - 1, -1.0)
    flags = q[q.edge >= THR]
    print(f"H-B01c: quotes {len(q)}, flags (engine - implied >= {THR}) {len(flags)}; book overrounds: " + ", ".join(f"{b}:{v:.3f}" for b, v in q.groupby(['bookmaker','event_id']).imp.sum().groupby('bookmaker').mean().items()))
    if len(flags):
        n = len(flags); se = flags.ret.std(ddof=1) / np.sqrt(n)
        print(f"  ROI {flags.ret.mean():+.4f} (SE {se:.4f}, 90% lo {flags.ret.mean()-1.6449*se:+.4f}); mean edge {flags.edge.mean():.4f}")
        print(flags.groupby("side").agg(n=("ret", "size"), roi=("ret", "mean"), edge=("edge", "mean")).round(4).to_string())
        print(flags.groupby("bookmaker").agg(n=("ret", "size"), roi=("ret", "mean")).round(4).to_string())
        flags["month"] = pd.to_datetime(flags.commence_time).dt.to_period("M")
        print(flags.groupby("month").agg(n=("ret", "size"), roi=("ret", "mean")).round(4).to_string())
    # descriptive: best-price ROI by side at edge bands
    q["band"] = pd.cut(q.edge, [-1, -0.05, -0.02, 0, 0.02, 0.03, 0.05, 1])
    print("descriptive, all quotes by edge band:\n", q.groupby("band", observed=True).agg(n=("ret", "size"), roi=("ret", "mean")).round(4).to_string())
    E.to_csv(f"{H}/work/b01_events.csv", index=False)


if __name__ == "__main__":
    main()
