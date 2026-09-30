#!/usr/bin/env python3
"""Ledger A-01 / A-02 / A-03 (+ C-01 checks) on the FIXED-goalie engine prices. One run per prices file.
Usage: python3 a_tests.py <prices.parquet> <tag>"""
import sys, numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import norm

H = "/home/claude/hunt"
GL = f"{H}/research/nhl_sim/edge_hunt_2026-09-30/games_lines.parquet"
LA = f"{H}/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet"
GS = f"{H}/research/nhl_sim/edge_hunt_2026-09-30/inputs/nhl_goalie_starts.csv"
GR = f"{H}/nhl/data/sim/ratings/goalie_ratings.parquet"
OLD = {2022: f"{H}/nhl/data/sim/prices/season=2022.parquet", 2023: f"{H}/nhl/data/sim/prices/season=2023.parquet"}
SEASONS = [2022, 2023]
Q = 0.068513
lg = lambda p: np.log(p / (1 - p))
pd.set_option("display.width", 220)


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def a1(y, pe, pp):
    pe = np.clip(pe, 1e-3, 1 - 1e-3); pp = np.clip(pp, 1e-3, 1 - 1e-3)
    X = sm.add_constant(np.column_stack([lg(pp), lg(pe) - lg(pp)]))
    f = sm.Logit(y, X).fit(disp=0)
    b, se = f.params[2], f.bse[2]
    return b, b - 1.6449 * se, b + 1.6449 * se, 1 - norm.cdf(b / se)


def ll(y, p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def early_snapshots(G):
    """Pinnacle first snapshot >= 12 h before puck: ML prob, total line + de-vigged P(over), median soft decimals."""
    d = pd.read_parquet(LA)
    d = d[d.event_id.isin(G.event_id)].copy()
    d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
    d["lead_h"] = (d.ct - d.snap).dt.total_seconds() / 3600
    d = d[d.lead_h >= 12]
    pin = d[(d.bookmaker == "pinnacle") & (d.market == "h2h")]
    first = pin.groupby("event_id").snap.min().rename("snap_e")
    d = d.merge(first, on="event_id"); d = d[d.snap == d.snap_e]; d["dec"] = dec(d.price)
    rows = []
    for e, g in d.groupby("event_id"):
        home, away = g.home_team.iloc[0], g.away_team.iloc[0]
        p = g[g.bookmaker == "pinnacle"]
        h2 = p[p.market == "h2h"]
        hp, ap = h2[h2.outcome_name == home].price, h2[h2.outcome_name == away].price
        if len(hp) != 1 or len(ap) != 1:
            continue
        ih, ia = 1 / dec(hp.iloc[0]), 1 / dec(ap.iloc[0])
        r = dict(event_id=e, p_early=float(ih / (ih + ia)), lead_e=float(g.lead_h.iloc[0]),
                 med_dec_h_e=g[(g.market == "h2h") & (g.outcome_name == home)].dec.median(),
                 med_dec_a_e=g[(g.market == "h2h") & (g.outcome_name == away)].dec.median())
        to = p[p.market == "totals"]
        if len(to) == 2 and to.point.nunique() == 1:
            io = 1 / to[to.outcome_name == "Over"].dec.iloc[0]; iu = 1 / to[to.outcome_name == "Under"].dec.iloc[0]
            r.update(tl_e=float(to.point.iloc[0]), p_over_e=float(io / (io + iu)))
        rows.append(r)
    return pd.DataFrame(rows)


def starters():
    gs = pd.read_csv(GS)
    gs = gs[(gs.started == 1) & gs.season.isin(SEASONS)].sort_values(["date", "game_id"])
    rec = []
    for (tm, se), x in gs.groupby(["team", "season"], sort=False):
        cnt = {}
        for r in x.itertuples(index=False):
            n = sum(cnt.values())
            prim = max(cnt, key=cnt.get) if cnt else None
            share = cnt[prim] / n if prim is not None else np.nan
            rec.append((r.game_id, tm, prim is not None and r.goalie_id == prim,
                        prim is not None and r.goalie_id != prim,                                   # broad backup
                        prim is not None and r.goalie_id != prim and share >= 0.6 and n >= 10))    # strict backup
            cnt[r.goalie_id] = cnt.get(r.goalie_id, 0) + 1
    return pd.DataFrame(rec, columns=["game_id", "team", "is_primary", "bk_broad", "bk_strict"])


def p_over_from_pmf(row, line):
    li = int(np.floor(line))
    over = sum(getattr(row, f"p_tot_{k}") for k in range(li + 1, 16))
    push = getattr(row, f"p_tot_{li}") if float(line).is_integer() else 0.0
    return over / (1 - push) if push < 1 else np.nan


def main():
    PR, TAG = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(PR); P["game_id"] = P.game_id.astype(int)
    P = P.drop(columns=[c for c in ["home", "away", "date", "season", "et_date", "pin_p_home", "pin_total_line", "p_over", "p_under", "p_push_total"] if c in P.columns])
    G = pd.read_parquet(GL); G = G[G.season.isin(SEASONS)].copy(); G["game_id"] = G.game_id.astype(int)
    keep = ["game_id", "event_id", "season", "date", "home", "away", "hg", "ag", "home_win", "pin_p_h", "med_dec_h", "med_dec_a",
            "tl_pin", "pin_p_over", "med_dec_over", "med_dec_under", "h_gp_b", "a_gp_b", "h_b2b", "a_b2b"]
    m = P.merge(G[keep], on="game_id"); m = m[m.pin_p_h.notna()].copy()
    ST = starters()
    m = m.merge(ST.rename(columns={"team": "home", "is_primary": "h_prim", "bk_broad": "h_bkb", "bk_strict": "h_bks"}), on=["game_id", "home"], how="left")
    m = m.merge(ST.rename(columns={"team": "away", "is_primary": "a_prim", "bk_broad": "a_bkb", "bk_strict": "a_bks"}), on=["game_id", "away"], how="left")
    gr = pd.read_parquet(GR); gr["game_id"] = gr.game_id.astype(int)
    gh = gr[gr.role == "home"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "h_gr"})
    ga = gr[gr.role == "away"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "a_gr"})
    m = m.merge(gh, on="game_id", how="left").merge(ga, on="game_id", how="left")
    m["gdiff"] = (m.h_gr - m.a_gr) / Q
    tr = pd.read_parquet(f"{H}/nhl/data/sim/ratings/team_ratings.parquet"); tr["game_id"] = tr.game_id.astype(int)
    tr["pace"] = tr.ev_att_for_per60 / tr.lg_ev_att_for_per60; tr["pen"] = tr.penalties_taken_per60 / tr.lg_penalties_taken_per60
    for role, pre in [("home", "h_"), ("away", "a_")]:
        m = m.merge(tr[tr.role == role][["game_id", "pace", "pen"]].rename(columns={"pace": pre + "pace", "pen": pre + "pen"}), on="game_id", how="left")
    E = early_snapshots(G)
    m = m.merge(E, on="event_id", how="left")
    print(f"[{TAG}] games with engine + Pinnacle close: {m.season.value_counts().sort_index().to_dict()}; with early: {m[m.p_early.notna()].season.value_counts().sort_index().to_dict()}")

    # ---------- C-01 checks: log-loss vs the committed prices, goalie-diff t, A1
    print("\n===== C-01: fixed engine vs committed (swapped) engine =====")
    for s in SEASONS:
        x = m[m.season == s]; y = x.home_win.astype(float).to_numpy()
        old = pd.read_parquet(OLD[s]); old["game_id"] = old.game_id.astype(int)
        xo = x[["game_id"]].merge(old[["game_id", "p_home_win"]], on="game_id")
        pe, po, pp = x.p_home_win.to_numpy(), xo.p_home_win.to_numpy(), x.pin_p_h.to_numpy()
        f = sm.Logit(y, sm.add_constant(np.column_stack([lg(np.clip(pe, 1e-3, 1 - 1e-3)), x.gdiff]))).fit(disp=0)
        b, lo, hi, p = a1(y, pe, pp)
        print(f"{s}: n={len(x)} LL fixed {ll(y, pe):.4f} | swapped {ll(y, po):.4f} | Pinnacle {ll(y, pp):.4f} ; "
              f"goalie-diff t given fixed engine {f.params[2]/f.bse[2]:+.2f} (coef {f.params[2]:+.2f}) ; "
              f"A1 fixed {b:.3f} [{lo:.3f}, {hi:.3f}] p={p:.4f} ; logit SD fixed {lg(np.clip(pe,1e-3,1-1e-3)).std():.3f} Pin {lg(pp).std():.3f} ; "
              f"corr(fixed logit, gdiff) {np.corrcoef(lg(np.clip(pe,1e-3,1-1e-3)), x.gdiff)[0,1]:+.3f}")

    # ---------- A-01: goalie-news CLV in backup games
    print("\n===== A-01: engine (actual starter) vs Pinnacle early->close move =====")
    me = m[m.p_early.notna()].copy()
    me["clean"] = (me.h_prim == True) & (me.a_prim == True) & (me.h_b2b == False) & (me.a_b2b == False)
    me["bk_strict"] = (me.h_bks == True) | (me.a_bks == True)
    me["bk_broad"] = (me.h_bkb == True) | (me.a_bkb == True)
    for label, col in [("STRICT backup (primary)", "bk_strict"), ("BROAD backup (secondary)", "bk_broad"), ("CLEAN (null control)", "clean")]:
        for s in SEASONS:
            x = me[(me.season == s) & me[col]]
            pe = x.p_home_win.clip(1e-3, 1 - 1e-3); pc = x.pin_p_h.clip(1e-4, 1 - 1e-4); pE = x.p_early.clip(1e-4, 1 - 1e-4)
            y = lg(pc) - lg(pE); z = lg(pe) - lg(pE)
            f = sm.OLS(y.values, sm.add_constant(z.values)).fit(cov_type="HC1")
            lo, hi = f.conf_int(alpha=0.10)[1]; pv = 1 - norm.cdf(f.params[1] / f.bse[1])
            # H2 economics: engine side at early median price when engine - BE >= 0.03
            be_h, be_a = 1 / x.med_dec_h_e, 1 / x.med_dec_a_e
            bh = (pe - be_h) >= 0.03; ba = ((1 - pe) - be_a) >= 0.03
            clv = np.concatenate([(pc[bh] - be_h[bh]).values, ((1 - pc[ba]) - be_a[ba]).values])
            ret = np.concatenate([np.where(x.home_win[bh] == 1, x.med_dec_h_e[bh] - 1, -1.0), np.where(x.home_win[ba] == 0, x.med_dec_a_e[ba] - 1, -1.0)])
            nb = len(clv); cse = clv.std(ddof=1) / np.sqrt(nb) if nb > 1 else np.nan
            print(f"{label:26s} {s}: n={len(x):4d} slope {f.params[1]:+.4f} 90% CI [{lo:+.4f}, {hi:+.4f}] p={pv:.4f} corr {np.corrcoef(y, z)[0,1]:+.3f} | "
                  f"H2 bets {nb:3d} CLV {clv.mean() if nb else np.nan:+.4f} (SE {cse:.4f}) ROI {ret.mean() if nb else np.nan:+.4f}")

    # ---------- A-03: totals move
    print("\n===== A-03: engine total vs Pinnacle early->close TOTAL move (same line only) =====")
    mt = me[me.tl_e.notna() & me.pin_p_over.notna() & np.isclose(me.tl_e, me.tl_pin)].copy()
    print(f"share of early-total games with unchanged line: {len(mt)}/{int(me.tl_e.notna().sum())}")
    mt["pe_over"] = [p_over_from_pmf(r, r.tl_pin) for r in mt.itertuples()]
    for label, col in [("ALL", None), ("STRICT backup", "bk_strict")]:
        for s in SEASONS:
            x = mt[(mt.season == s)] if col is None else mt[(mt.season == s) & mt[col]]
            y = lg(x.pin_p_over.clip(1e-4, 1 - 1e-4)) - lg(x.p_over_e.clip(1e-4, 1 - 1e-4))
            z = lg(x.pe_over.clip(1e-3, 1 - 1e-3)) - lg(x.p_over_e.clip(1e-4, 1 - 1e-4))
            f = sm.OLS(y.values, sm.add_constant(z.values)).fit(cov_type="HC1")
            lo, hi = f.conf_int(alpha=0.10)[1]; pv = 1 - norm.cdf(f.params[1] / f.bse[1])
            print(f"{label:14s} {s}: n={len(x):4d} slope {f.params[1]:+.4f} [{lo:+.4f}, {hi:+.4f}] p={pv:.4f} intercept {f.params[0]:+.3f} corr {np.corrcoef(y, z)[0,1]:+.3f} mean z {z.mean():+.3f}")

    # ---------- A-02: regime family x2 markets, both seasons reported, BH on 2023-24
    print("\n===== A-02: regime family (fixed engine) =====")
    m["pe_over"] = [p_over_from_pmf(r, r.tl_pin) if pd.notna(r.tl_pin) else np.nan for r in m.itertuples()]
    rows = []
    for s in SEASONS:
        d = m[m.season == s].copy()
        tot = d.hg + d.ag
        dt = d[d.pin_p_over.notna() & d.pe_over.notna() & (tot != d.tl_pin)].copy()
        dt["y"] = (dt.hg + dt.ag > dt.tl_pin).astype(float)
        def regimes(x, market):
            pe = x.p_home_win if market == "ML" else x.pe_over
            pp = x.pin_p_h if market == "ML" else x.pin_p_over
            pick = np.where(pe > pp, pp, 1 - pp)
            return {"R1 early": (x.h_gp_b <= 10) | (x.a_gp_b <= 10), "R2 B2B": (x.h_b2b == True) | (x.a_b2b == True),
                    "R3 backup(strict)": (x.h_bks == True) | (x.a_bks == True), "R4 |diff|>5": (pe - pp).abs() > 0.05,
                    "R5 eng=dog": pd.Series(pick < 0.5, index=x.index),
                    "R6 goalies": ((x.h_gr > 0) & (x.a_gr > 0)) if market == "TOT" else ((x.h_gr < 0) & (x.a_gr < 0)),
                    "R7 both high pace": (x.h_pace > 1.02) & (x.a_pace > 1.02),
                    "R8 both high pen": (x.h_pen > 1.05) & (x.a_pen > 1.05)}
        for market, x in [("ML", d), ("TOT", dt)]:
            y = (x.home_win.astype(float) if market == "ML" else x.y).to_numpy()
            pe = (x.p_home_win if market == "ML" else x.pe_over).to_numpy(); pp = (x.pin_p_h if market == "ML" else x.pin_p_over).to_numpy()
            da, db = ((x.med_dec_h, x.med_dec_a) if market == "ML" else (x.med_dec_over, x.med_dec_under))
            da, db = da.to_numpy(), db.to_numpy()
            for name, k in regimes(x, market).items():
                k = k.fillna(False).to_numpy().astype(bool)
                if k.sum() < 30:
                    rows.append(dict(season=s, market=market, regime=name, n=int(k.sum()))); continue
                b, lo, hi, p = a1(y[k], pe[k], pp[k])
                ea = pe[k] - 1 / da[k]; eb = (1 - pe[k]) - 1 / db[k]
                ret = np.concatenate([np.where(y[k] == 1, da[k] - 1, -1)[ea >= 0.04], np.where(y[k] == 0, db[k] - 1, -1)[eb >= 0.04]])
                clv = np.concatenate([(pp[k] - 1 / da[k])[ea >= 0.04], ((1 - pp[k]) - 1 / db[k])[eb >= 0.04]])
                rows.append(dict(season=s, market=market, regime=name, n=int(k.sum()), coef=b, lo90=lo, hi90=hi, p=p, a2_n=len(ret),
                                 a2_roi=ret.mean() if len(ret) else np.nan, a2_se=ret.std(ddof=1) / np.sqrt(len(ret)) if len(ret) > 1 else np.nan,
                                 a2_clv=clv.mean() if len(clv) else np.nan))
    R = pd.DataFrame(rows)
    print(R.round(4).to_string())
    R.to_csv(f"/home/claude/hunt/work/a02_regimes_{TAG}.csv", index=False)
    V = R[(R.season == 2023) & R.p.notna()].sort_values("p").reset_index(drop=True)
    V["bh_thresh"] = 0.10 * (np.arange(len(V)) + 1) / len(V)
    passed = V.p <= V.bh_thresh; kmax = passed[passed].index.max() if passed.any() else -1
    print("\n2023-24 family BH 10% (within-family):", "survivors " + str(V[V.index <= kmax][["market", "regime", "p"]].values.tolist()) if kmax >= 0 else "NO SURVIVORS", f"(min p {V.p.min():.4f}, thresh {V.bh_thresh.iloc[0]:.4f})")


if __name__ == "__main__":
    main()
