#!/usr/bin/env python3
"""PREREG_ALT.md — engine-conditioned prices for soft-book totals at points Pinnacle does not hang. One run.
EV_SEASONS env selects seasons (default dev 2022,2023)."""
import os, numpy as np, pandas as pd
from scipy.optimize import least_squares

P3 = "/home/claude/nhlhunt/p3"
GRID = "/home/claude/nhl/eng/market_grid_v1.npz"
SEASONS = [int(s) for s in os.environ.get("EV_SEASONS", "2022,2023").split(",")]
TAG = "_".join(map(str, SEASONS))
THR = 0.02
g = np.load(GRID)
S, M, J = g["S"], g["M"], g["J"]
H = np.arange(16)[:, None]; A = np.arange(16)[None, :]
TOT = H + A


def joint(s, m):
    fi = np.interp(s, S, np.arange(len(S))); fj = np.interp(m, M, np.arange(len(M)))
    i0, j0 = min(int(fi), len(S) - 2), min(int(fj), len(M) - 2)
    di, dj = fi - i0, fj - j0
    return ((1 - di) * (1 - dj) * J[i0, j0] + di * (1 - dj) * J[i0 + 1, j0]
            + (1 - di) * dj * J[i0, j0 + 1] + di * dj * J[i0 + 1, j0 + 1])


def p_home(Jx):
    return Jx[H > A].sum()


def p_over_cond(Jx, pt):
    o = Jx[TOT > pt].sum(); push = Jx[TOT == pt].sum()
    return o / (1 - push)


def solve(ph, po, pt):
    f = lambda x: [p_home(joint(*x)) - ph, p_over_cond(joint(*x), pt) - po]
    r = least_squares(f, x0=[0.0, 1.0], bounds=([S[0], M[0]], [S[-1], M[-1]]))
    ok = np.max(np.abs(r.fun)) <= 0.005
    return r.x, ok


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def snapshot_tables(x):
    """x: all rows of one snapshot per event. Returns pinnacle refs per event and soft totals quotes."""
    x = x.copy(); x["dec"] = dec(x.price)
    pin = x[x.bookmaker == "pinnacle"]
    refs = {}
    for e, p in pin.groupby("event_id"):
        home, away = p.home_team.iloc[0], p.away_team.iloc[0]
        h2 = p[p.market == "h2h"]
        hp, ap = h2[h2.outcome_name == home].dec, h2[h2.outcome_name == away].dec
        to = p[p.market == "totals"]
        if len(hp) != 1 or len(ap) != 1 or len(to) != 2 or to.point.nunique() != 1:
            continue
        ph = (1 / hp.iloc[0]) / (1 / hp.iloc[0] + 1 / ap.iloc[0])
        io = 1 / to[to.outcome_name == "Over"].dec.iloc[0]; iu = 1 / to[to.outcome_name == "Under"].dec.iloc[0]
        sp = p[(p.market == "spreads") & (p.point.abs() == 1.5)]
        pl = None
        if len(sp) == 2:
            hr = sp[sp.outcome_name == home]
            if len(hr) == 1:
                ih = 1 / hr.dec.iloc[0]; ia = 1 / sp[sp.outcome_name == away].dec.iloc[0]
                pl = (float(hr.point.iloc[0]), ih / (ih + ia))
        refs[e] = dict(ph=ph, pt=float(to.point.iloc[0]), po=io / (io + iu), pl=pl)
    soft = x[(x.bookmaker != "pinnacle") & (x.market == "totals")][["event_id", "bookmaker", "outcome_name", "point", "dec"]]
    return refs, soft


def ev_of(Jx, side, pt, d):
    o = Jx[TOT > pt].sum(); u = Jx[TOT < pt].sum()
    pw, pl_ = (o, u) if side == "Over" else (u, o)
    return pw * (d - 1) - pl_


def main():
    G = pd.read_parquet(f"{P3}/games_lines.parquet")
    G = G[G.season.isin(SEASONS)][["event_id", "season", "date", "hg", "ag"]]
    d = pd.read_parquet(f"{P3}/lines_all.parquet")
    d = d[d.event_id.isin(G.event_id)].copy()
    d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
    d["lead_h"] = (d.ct - d.snap).dt.total_seconds() / 3600
    d = d[d.snap < d.ct]
    T = {"CLOSE": d.groupby("event_id").snap.max(),
         "EARLY": d[(d.lead_h >= 12) & (d.bookmaker == "pinnacle") & (d.market == "h2h")].groupby("event_id").snap.min()}
    tabs, sol = {}, {}
    for k, t in T.items():
        x = d.merge(t.rename("t"), left_on=["event_id", "snap"], right_on=["event_id", "t"])
        refs, soft = snapshot_tables(x)
        sv, bad = {}, 0
        for e, r in refs.items():
            xy, ok = solve(r["ph"], r["po"], r["pt"])
            if ok:
                sv[e] = (xy, r)
            else:
                bad += 1
        tabs[k], sol[k] = soft, sv
        print(f"{k}: pinnacle refs {len(refs)}, solved {len(sv)}, dropped {bad}")
    # engine-structure check: puck line at CLOSE
    rows = []
    GG = G.set_index("event_id")
    for e, (xy, r) in sol["CLOSE"].items():
        if r["pl"] is None or e not in GG.index:
            continue
        hpt, ppin = r["pl"]
        Jx = joint(*xy)
        peng = Jx[(H - A + hpt) > 0].sum()
        y = int((GG.loc[e, "hg"] - GG.loc[e, "ag"] + hpt) > 0)
        rows.append((ppin, peng, y))
    pl = np.array(rows)
    ll = lambda p, y: -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
    print(f"\nPUCK LINE structure check (CLOSE, n={len(pl)}): mean Pinnacle {pl[:,0].mean():.4f} engine {pl[:,1].mean():.4f} "
          f"actual {pl[:,2].mean():.4f}; mean |diff| {np.abs(pl[:,0]-pl[:,1]).mean():.4f}; "
          f"log-loss Pinnacle {ll(pl[:,0], pl[:,2]):.4f} engine {ll(pl[:,1], pl[:,2]):.4f}")
    out = []
    for k in ["EARLY", "CLOSE"]:
        soft, sv = tabs[k], sol[k]
        cands = []
        for e, q in soft.groupby("event_id"):
            if e not in sv:
                continue
            xy, r = sv[e]
            q = q[q.point != r["pt"]]
            if q.empty:
                continue
            Jx = joint(*xy)
            best = q.sort_values("dec", ascending=False).drop_duplicates(["point", "outcome_name"])
            for b in best.itertuples(index=False):
                cands.append(dict(event_id=e, book=b.bookmaker, side=b.outcome_name, point=b.point, dec=b.dec,
                                  pin_pt=r["pt"], ev=ev_of(Jx, b.outcome_name, b.point, b.dec)))
        C = pd.DataFrame(cands)
        B = C[C.ev >= THR].sort_values("ev", ascending=False).drop_duplicates("event_id").merge(G, on="event_id")
        tot = B.hg + B.ag
        win = np.where(B.side == "Over", tot > B.point, tot < B.point)
        push = tot == B.point
        B["ret"] = np.where(push, 0.0, np.where(win, B.dec - 1, -1.0))
        clv = []
        for b in B.itertuples(index=False):
            if b.event_id in sol["CLOSE"]:
                clv.append(ev_of(joint(*sol["CLOSE"][b.event_id][0]), b.side, b.point, b.dec))
            else:
                clv.append(np.nan)
        B["clv"] = clv
        def cl(b, col):
            b = b[b[col].notna()]
            gs = b.groupby("event_id")[col].agg(["sum", "size"]); mu = gs["sum"].sum() / gs["size"].sum(); n = len(gs)
            se = np.sqrt(n / (n - 1) * ((gs["sum"] - mu * gs["size"]) ** 2).sum()) / gs["size"].sum() if n > 1 else np.nan
            return mu, se
        print(f"\n===== {k}: candidate quotes {len(C)}, share EV>=2% {(C.ev >= THR).mean():.3f}, bets {len(B)} =====")
        for lab, b in [("POOLED", B)] + [(f"season={s}", b) for s, b in B.groupby("season")] + \
                [(f"point={p}/pin={pp}", b) for (p, pp), b in B.groupby(["point", "pin_pt"])] + \
                [(f"side={s}", b) for s, b in B.groupby("side")] + [(f"book={s}", b) for s, b in B.groupby("book")]:
            r_, rse = cl(b, "ret"); c_, cse = cl(b, "clv")
            print(f"  {lab}: bets {len(b)} ROI {r_:+.4f} (SE {rse:.4f})  EV {b.ev.mean():+.4f}  CLV {c_:+.4f} (SE {cse:.4f}, "
                  f"90% lo {c_ - 1.6449 * cse:+.4f})")
            out.append(dict(snap=k, cut=lab, bets=len(b), roi=r_, roi_se=rse, ev=b.ev.mean(), clv=c_, clv_se=cse))
        B["month"] = pd.to_datetime(B.date).dt.to_period("M").astype(str)
        print(B.groupby("month").agg(bets=("ret", "size"), roi=("ret", "mean"), clv=("clv", "mean")).round(4).to_string())
        B.to_parquet(f"/home/claude/nhl/alt/bets_{k.lower()}_{TAG}.parquet", index=False)
        C.to_parquet(f"/home/claude/nhl/alt/cands_{k.lower()}_{TAG}.parquet", index=False)
    pd.DataFrame(out).to_csv(f"/home/claude/nhl/alt/alt_results_{TAG}.csv", index=False)


if __name__ == "__main__":
    main()
