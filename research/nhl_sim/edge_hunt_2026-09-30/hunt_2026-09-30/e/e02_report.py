#!/usr/bin/env python3
"""Ledger E-02 report (amended: live benchmark = median of books). One run."""
import json, numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import norm
H = "/home/claude/hunt"; E = f"{H}/e"
pd.set_option("display.width", 220)
lg = lambda p: np.log(p / (1 - p))
rng = np.random.default_rng(20260930)


def cluster_boot_a1(y, pe, pp, groups, B=1000):
    pe = np.clip(pe, 1e-3, 1 - 1e-3); pp = np.clip(pp, 1e-3, 1 - 1e-3)
    X = sm.add_constant(np.column_stack([lg(pp), lg(pe) - lg(pp)]))
    try:
        b0 = sm.Logit(y, X).fit(disp=0).params[2]
    except Exception:
        return np.nan, np.nan, np.nan, np.nan
    ug = np.unique(groups); bs = []
    for _ in range(B):
        take = rng.choice(ug, len(ug), replace=True)
        idx = np.concatenate([np.where(groups == g)[0] for g in take])
        try:
            bs.append(sm.Logit(y[idx], X[idx]).fit(disp=0, maxiter=50).params[2])
        except Exception:
            pass
    bs = np.array(bs); se = bs.std()
    return b0, np.percentile(bs, 5), np.percentile(bs, 95), 1 - norm.cdf(b0 / se) if se > 0 else np.nan


def cluster_se(x, groups):
    df = pd.DataFrame({"x": x, "g": groups}); s = df.groupby("g").x.agg(["sum", "size"])
    n = len(x); m = x.mean()
    return np.sqrt(((s["sum"] - m * s["size"]) ** 2).sum()) / n


def main():
    T = pd.read_parquet(f"{E}/state_at_snapshot_2023.parquet")
    R = pd.read_parquet(f"{E}/e02_engine_live_2023.parquet")
    R = R[R.skipped.isna()] if "skipped" in R else R
    T["ts"] = pd.to_datetime(T.ts); D = T.merge(R, on=["game_id", "ts"])
    books = sorted({c[:-6] for c in D.columns if c.endswith("_dec_h")})
    # live median fair ML
    fair = []
    for b in books:
        h, a = D[f"{b}_dec_h"], D[f"{b}_dec_a"]; ih, ia = 1 / h, 1 / a
        fair.append(ih / (ih + ia))
    F = pd.concat(fair, axis=1); F.columns = books
    D["med_p_home"] = F.median(axis=1); D["n_books"] = F.notna().sum(axis=1)
    D["best_dec_h"] = D[[f"{b}_dec_h" for b in books]].max(axis=1); D["best_dec_a"] = D[[f"{b}_dec_a" for b in books]].max(axis=1)
    # live totals: modal point across books, median P(over) at that point, best over/under decimals at that point
    tcols = [b for b in books if f"{b}_tot" in D]
    pts = D[[f"{b}_tot" for b in tcols]]
    D["med_tot"] = pts.mode(axis=1)[0]
    po, bo, bu = [], [], []
    for b in tcols:
        at = np.isclose(D[f"{b}_tot"], D.med_tot)
        io, iu = 1 / D[f"{b}_dec_o"], 1 / D[f"{b}_dec_u"]
        po.append((io / (io + iu)).where(at)); bo.append(D[f"{b}_dec_o"].where(at)); bu.append(D[f"{b}_dec_u"].where(at))
    D["med_p_over"] = pd.concat(po, axis=1).median(axis=1); D["best_dec_o"] = pd.concat(bo, axis=1).max(axis=1); D["best_dec_u"] = pd.concat(bu, axis=1).max(axis=1)
    D["n_books_tot"] = pd.concat(po, axis=1).notna().sum(axis=1)
    # engine P(over) at the modal live point
    def e_over(r):
        pt = r.med_tot
        if pd.isna(pt): return np.nan
        li = int(np.floor(pt)); over = sum(getattr(r, f"e_tot_{k}", 0.0) or 0.0 for k in range(li + 1, 16))
        push = (getattr(r, f"e_tot_{li}", 0.0) or 0.0) if float(pt).is_integer() else 0.0
        return over / (1 - push) if push < 1 else np.nan
    D["e_p_over"] = [e_over(r) for r in D.itertuples()]
    D["res_tot"] = D.hg + D.ag
    D["y_home"] = D.home_win.astype(float)
    D["y_over"] = np.where(D.res_tot > D.med_tot, 1.0, np.where(D.res_tot < D.med_tot, 0.0, np.nan))
    D["rem"] = np.where(D.phase == "intermission", (3 - D.period) * 1200, 3600 - D.sec)   # seconds left in regulation (OT rows negative)
    D["bucket"] = pd.cut(D.rem, [-10000, 0, 300, 600, 1200, 2400, 4000], labels=["OT", "<5:00 P3", "5-10 P3", "10-20 P3", "P2", "P1"])
    print(f"rows {len(D)} games {D.game_id.nunique()} | books per row median {D.n_books.median()} | totals rows {int(D.y_over.notna().sum())}")

    # ---- null (iv): state-blind engine = pre-game Pinnacle close vs live median
    def ll(y, p): p = np.clip(p, 1e-3, 1 - 1e-3); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    print(f"null (iv) ML log-loss: state-blind (pre-game close) {ll(D.y_home, D.pin_p_h_pre):.4f} vs live median {ll(D.y_home, D.med_p_home):.4f} vs live ENGINE {ll(D.y_home, D.e_p_home):.4f}")
    # ---- null (i): pre-match rows at the same snapshots
    P = T[(T.phase == "pre") & T.pin_p_h_pre.notna()].copy()
    fp = []
    for b in books:
        if f"{b}_dec_h" in P:
            ih, ia = 1 / P[f"{b}_dec_h"], 1 / P[f"{b}_dec_a"]; fp.append(ih / (ih + ia))
    P["med_pre"] = pd.concat(fp, axis=1).median(axis=1)
    print(f"null (i) pre-match rows {int(P.med_pre.notna().sum())}: mean |pre-game Pinnacle close − live-snapshot pre-match median| {np.abs(P.pin_p_h_pre - P.med_pre).mean():.4f}")
    # ---- E-02a
    print("\n=== E-02a structure: log-loss by bucket (ML; totals at modal live point) ===")
    for bk, x in D.groupby("bucket", observed=True):
        xt = x[x.y_over.notna() & x.e_p_over.notna() & x.med_p_over.notna()]
        print(f"{str(bk):10s} n={len(x):4d} games={x.game_id.nunique():3d} ML engine {ll(x.y_home, x.e_p_home):.4f} median {ll(x.y_home, x.med_p_home):.4f} | "
              f"TOT n={len(xt):4d} engine {ll(xt.y_over, xt.e_p_over) if len(xt) else np.nan:.4f} median {ll(xt.y_over, xt.med_p_over) if len(xt) else np.nan:.4f}")
    xt = D[D.y_over.notna() & D.e_p_over.notna() & D.med_p_over.notna()]
    print(f"ALL        ML engine {ll(D.y_home, D.e_p_home):.4f} median {ll(D.y_home, D.med_p_home):.4f} | TOT engine {ll(xt.y_over, xt.e_p_over):.4f} median {ll(xt.y_over, xt.med_p_over):.4f}")
    print(f"mean |engine − median| ML {np.abs(D.e_p_home - D.med_p_home).mean():.4f}, totals {np.abs(xt.e_p_over - xt.med_p_over).mean():.4f}")
    # ---- E-02b
    print("\n=== E-02b information (A1, game-clustered bootstrap) ===")
    fam = []
    b, lo, hi, p = cluster_boot_a1(D.y_home.to_numpy(), D.e_p_home.to_numpy(), D.med_p_home.to_numpy(), D.game_id.to_numpy())
    print(f"ML:  n={len(D)} coef {b:+.3f} 90% [{lo:+.3f}, {hi:+.3f}] p={p:.4f}"); fam.append(("E-02b ML", p))
    b, lo, hi, p = cluster_boot_a1(xt.y_over.to_numpy(), xt.e_p_over.to_numpy(), xt.med_p_over.to_numpy(), xt.game_id.to_numpy())
    print(f"TOT: n={len(xt)} coef {b:+.3f} 90% [{lo:+.3f}, {hi:+.3f}] p={p:.4f}"); fam.append(("E-02b TOT", p))
    # ---- E-02c situations
    print("\n=== E-02c situations ===")
    live = D.phase == "live"
    sit = {"S1 goalie pulled": live & ((D.home_goalie == 0) | (D.away_goalie == 0)),
           "S2 power play": live & (D.home_skaters != D.away_skaters) & (D.home_goalie == 1) & (D.away_goalie == 1),
           "S3 one-goal 5v5 <5:00": live & ((D.hs - D.as_).abs() == 1) & (D.home_skaters == 5) & (D.away_skaters == 5) & (D.home_goalie == 1) & (D.away_goalie == 1) & (D.rem <= 300) & (D.rem > 0),
           "S4 tied <5:00": live & (D.hs == D.as_) & (D.rem <= 300) & (D.rem > 0),
           "S5 overtime": D.period == 4}
    rows = []
    for name, k in sit.items():
        x = D[k.fillna(False)]
        for market in ["ML", "TOT"]:
            if market == "TOT":
                x2 = x[x.y_over.notna() & x.e_p_over.notna() & x.med_p_over.notna()]
                y, pe, pp = x2.y_over.to_numpy(), x2.e_p_over.to_numpy(), x2.med_p_over.to_numpy()
                da, db = x2.best_dec_o.to_numpy(), x2.best_dec_u.to_numpy(); ya = y == 1
            else:
                x2 = x; y, pe, pp = x2.y_home.to_numpy(), x2.e_p_home.to_numpy(), x2.med_p_home.to_numpy()
                da, db = x2.best_dec_h.to_numpy(), x2.best_dec_a.to_numpy(); ya = y == 1
            ng = x2.game_id.nunique()
            if len(x2) < 15:
                rows.append(dict(sit=name, market=market, n=len(x2), games=ng)); continue
            b, lo, hi, p = cluster_boot_a1(y, pe, pp, x2.game_id.to_numpy(), B=400)
            ea = pe - 1 / da; eb = (1 - pe) - 1 / db
            pa, pb = ea >= 0.05, eb >= 0.05
            ret = np.concatenate([np.where(ya, da - 1, -1.0)[pa], np.where(~ya, db - 1, -1.0)[pb]])
            grp = np.concatenate([x2.game_id.to_numpy()[pa], x2.game_id.to_numpy()[pb]])
            roi = ret.mean() if len(ret) else np.nan; rse = cluster_se(ret, grp) if len(ret) > 1 else np.nan
            rows.append(dict(sit=name, market=market, n=len(x2), games=ng, coef=b, lo90=lo, hi90=hi, p=p, picks=len(ret), pick_games=len(np.unique(grp)), roi=roi, roi_se=rse,
                             ll_eng=ll(y, pe), ll_med=ll(y, pp)))
            fam.append((f"E-02c {name} {market}", p))
    Rr = pd.DataFrame(rows); print(Rr.round(4).to_string())
    Rr.to_csv(f"{E}/e02_situations.csv", index=False)
    pd.DataFrame(fam, columns=["test", "p"]).to_csv(f"{E}/e02_family.csv", index=False)
    D.to_parquet(f"{E}/e02_rows.parquet", index=False)
    # descriptive: A2 picks over ALL live rows, by bucket and book (economics of the plain live engine)
    print("\n=== descriptive: engine − best-price break-even ≥ 0.05, all rows, ML ===")
    ea = D.e_p_home - 1 / D.best_dec_h; eb = (1 - D.e_p_home) - 1 / D.best_dec_a
    pa, pb = ea >= 0.05, eb >= 0.05
    ret = np.concatenate([np.where(D.y_home == 1, D.best_dec_h - 1, -1.0)[pa], np.where(D.y_home == 0, D.best_dec_a - 1, -1.0)[pb]])
    grp = np.concatenate([D.game_id.to_numpy()[pa], D.game_id.to_numpy()[pb]])
    print(f"picks {len(ret)} games {len(np.unique(grp))} ROI {ret.mean():+.4f} (clustered SE {cluster_se(ret, grp):.4f})")
    bk = pd.DataFrame({"ret": ret, "bucket": np.concatenate([D.bucket.astype(str).to_numpy()[pa], D.bucket.astype(str).to_numpy()[pb]])})
    print(bk.groupby("bucket").ret.agg(["size", "mean"]).round(4).to_string())


if __name__ == "__main__":
    main()
