#!/usr/bin/env python3
"""Pre-registered CLV / line-move test (PREREG_CLV.md). One run. Seasons 2022-23 (fit reference) and 2023-24 (validate).
Holdout 2024-25 / 2025-26 is NOT read (filtered out before any computation)."""
import numpy as np, pandas as pd, statsmodels.api as sm

P3 = "/home/claude/nhlhunt/p3"
PR = "/mnt/user-data/uploads/mlb-model-nhlsim4b/nhl/data/sim/prices"
GS = "/home/claude/nhlhunt/raw/nhl_goalie_starts.csv"
SEASONS = [2022, 2023]


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def logit(p):
    return np.log(p / (1 - p))


def main():
    G = pd.read_parquet(f"{P3}/games_lines.parquet")
    G = G[G.season.isin(SEASONS)].copy()
    # ---- early snapshot: earliest Pinnacle h2h snapshot >= 12 h before puck
    d = pd.read_parquet(f"{P3}/lines_all.parquet")
    d = d[d.event_id.isin(G.event_id) & (d.market == "h2h")].copy()
    d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
    d["lead_h"] = (d.ct - d.snap).dt.total_seconds() / 3600
    d = d[d.lead_h >= 12]
    pin = d[d.bookmaker == "pinnacle"]
    first = pin.groupby("event_id").snap.min().rename("snap_e")
    d = d.merge(first, on="event_id")
    d = d[d.snap == d.snap_e]
    d["dec"] = dec(d.price)
    rows = []
    for e, g in d.groupby("event_id"):
        home = g.home_team.iloc[0]; away = g.away_team.iloc[0]
        p = g[g.bookmaker == "pinnacle"]
        hp = p[p.outcome_name == home].price; ap = p[p.outcome_name == away].price
        if len(hp) != 1 or len(ap) != 1:
            continue
        ih, ia = 1 / dec(hp.iloc[0]), 1 / dec(ap.iloc[0])
        rows.append({"event_id": e, "p_early": float(ih / (ih + ia)), "lead_e": g.lead_h.iloc[0],
                     "med_dec_h_e": g[g.outcome_name == home].dec.median(),
                     "med_dec_a_e": g[g.outcome_name == away].dec.median()})
    E = pd.DataFrame(rows)
    G = G.merge(E, on="event_id", how="inner").rename(columns={"pin_p_h": "p_close"})
    # ---- engine prices
    P = pd.concat([pd.read_parquet(f"{PR}/season={s}.parquet") for s in SEASONS])
    P["game_id"] = P.game_id.astype(int)
    G["game_id"] = G.game_id.astype(int)
    G = G.merge(P[["game_id", "p_home_win"]], on="game_id", how="inner")
    # ---- leak control: most-used starter before D (strict: no prior start => excluded), no D-1 game
    gs = pd.read_csv(GS)
    gs = gs[(gs.started == 1) & gs.season.isin(SEASONS)].sort_values(["date", "game_id"])
    rec = []
    for (tm, se), x in gs.groupby(["team", "season"], sort=False):
        cnt = {}
        for r in x.itertuples(index=False):
            prim = max(cnt, key=cnt.get) if cnt else None
            rec.append((r.game_id, tm, prim is not None and r.goalie_id == prim))
            cnt[r.goalie_id] = cnt.get(r.goalie_id, 0) + 1
    ST = pd.DataFrame(rec, columns=["game_id", "team", "is_primary"])
    G = G.merge(ST.rename(columns={"team": "home", "is_primary": "h_prim"}), on=["game_id", "home"], how="left")
    G = G.merge(ST.rename(columns={"team": "away", "is_primary": "a_prim"}), on=["game_id", "away"], how="left")
    n_nan = int(G.p_close.isna().sum() + G.p_early.isna().sum())
    G = G[G.p_close.notna() & G.p_early.notna()].copy()
    print(f"dropped for missing Pinnacle close/early prob: {n_nan}")
    n_all = len(G)
    G["clean"] = (G.h_prim == True) & (G.a_prim == True) & (G.h_b2b == False) & (G.a_b2b == False)
    print(f"games with early+close+engine: {n_all}; by season {G.season.value_counts().sort_index().to_dict()}")
    print(f"clean (both primary starters, neither team on B2B): {int(G.clean.sum())}; "
          f"{G[G.clean].season.value_counts().sort_index().to_dict()}")
    print(f"early lead h median {G.lead_e.median():.1f}; close lead h median {G.lead_h.median():.1f}")
    out = []
    for label, S in [("CLEAN", G[G.clean]), ("ALL (not the pre-registered set, context only)", G)]:
        print(f"\n===== {label} =====")
        for s in SEASONS:
            x = S[S.season == s].copy()
            pe = x.p_early.clip(1e-4, 1 - 1e-4); pc = x.p_close.clip(1e-4, 1 - 1e-4); pg = x.p_home_win.clip(1e-3, 1 - 1e-3)
            y = logit(pc) - logit(pe); z = logit(pg) - logit(pe)
            m = sm.OLS(y.values, sm.add_constant(z.values)).fit(cov_type="HC1")
            lo, hi = m.conf_int(alpha=0.10)[1]
            big = (pg - pe).abs() >= 0.04
            moved = (pc - pe)
            toward = np.sign(moved[big]) == np.sign((pg - pe)[big])
            nz = moved[big] != 0
            print(f"season {s}: n={len(x)}  slope={m.params[1]:.4f}  90% CI [{lo:.4f}, {hi:.4f}]  p={m.pvalues[1]:.4f}  "
                  f"corr={np.corrcoef(y, z)[0,1]:.3f}  sd(move logit)={y.std():.3f}")
            print(f"   |eng-early|>=.04: n={int(big.sum())}; moved toward engine {int((toward & nz).sum())}, away "
                  f"{int((~toward & nz).sum())}, no move {int((~nz).sum())}; share toward (of moved) "
                  f"{(toward & nz).sum() / max(nz.sum(), 1):.3f}")
            # economics: bet the engine side at the EARLY median price when engine - early break-even >= 0.04
            be_h = 1 / x.med_dec_h_e; be_a = 1 / x.med_dec_a_e
            bh = (pg - be_h) >= 0.04; ba = ((1 - pg) - be_a) >= 0.04
            ret = np.where(bh, np.where(x.home_win == 1, x.med_dec_h_e - 1, -1.0), 0.0) + \
                  np.where(ba, np.where(x.home_win == 0, x.med_dec_a_e - 1, -1.0), 0.0)
            nb = int(bh.sum() + ba.sum())
            clv = np.concatenate([(pc[bh] - be_h[bh]).values, ((1 - pc[ba]) - be_a[ba]).values])
            r = ret[(bh | ba).values]
            se = r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
            print(f"   bets {nb} (home {int(bh.sum())}, away {int(ba.sum())}): ROI {r.mean():+.4f} (SE {se:.4f}); "
                  f"mean CLV (close fair prob - early BE) {clv.mean():+.4f}; share CLV>0 {(clv > 0).mean():.3f}")
            x = x.assign(ret=ret, bet=(bh | ba).values)
            x["clvv"] = np.nan
            x.loc[bh.values, "clvv"] = (pc[bh] - be_h[bh]).values
            x.loc[ba.values, "clvv"] = ((1 - pc[ba]) - be_a[ba]).values
            mo = x[x.bet].groupby(pd.to_datetime(x[x.bet].date).dt.to_period("M")).agg(
                bets=("ret", "size"), roi=("ret", "mean"), clv=("clvv", "mean"))
            print(mo.round(4).to_string())
            out.append(dict(set=label, season=s, n=len(x), slope=m.params[1], lo90=lo, hi90=hi, bets=nb,
                            roi=r.mean(), roi_se=se, clv=clv.mean()))
    pd.DataFrame(out).to_csv("/home/claude/nhl/clv/clv_results.csv", index=False)


if __name__ == "__main__":
    main()
