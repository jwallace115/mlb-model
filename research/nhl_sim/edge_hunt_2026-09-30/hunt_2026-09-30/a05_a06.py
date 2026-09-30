#!/usr/bin/env python3
"""Ledger A-05 (ML) and A-06 (totals): early best-of-8 price vs the fixed engine. One run on dev 2022-24.
EV_SEASONS env selects seasons; PRICES env selects the engine prices parquet."""
import os, numpy as np, pandas as pd
H = "/home/claude/hunt"
SEASONS = [int(s) for s in os.environ.get("EV_SEASONS", "2022,2023").split(",")]
PR = os.environ.get("PRICES", f"{H}/work/fixed_2022_2023.parquet")
OLD = [f"{H}/nhl/data/sim/prices/season=2022.parquet", f"{H}/nhl/data/sim/prices/season=2023.parquet"]
THR = 0.03
BOOKS = ["betmgm", "betonlineag", "betrivers", "bovada", "draftkings", "fanduel", "lowvig", "williamhill_us"]
pd.set_option("display.width", 200)


def dec(a):
    a = np.asarray(a, float); return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def p_side_pmf(row, point, side):
    li = int(np.floor(point))
    over = sum(getattr(row, f"p_tot_{k}") for k in range(li + 1, 16))
    push = getattr(row, f"p_tot_{li}") if float(point).is_integer() else 0.0
    if push >= 1: return np.nan
    po = over / (1 - push)
    return po if side == "Over" else 1 - po


def rep(f, label, clvcol="clv"):
    n = len(f)
    if n < 2: print(f"{label}: n={n}"); return
    c = f[clvcol].dropna(); se = c.std(ddof=1) / np.sqrt(len(c)) if len(c) > 1 else np.nan
    rse = f.ret.std(ddof=1) / np.sqrt(n)
    print(f"{label}: flags {n} CLV {c.mean():+.4f} (n {len(c)}, SE {se:.4f}, 90% lo {c.mean()-1.6449*se:+.4f}) ROI {f.ret.mean():+.4f} (SE {rse:.4f}) hit {f.win.mean():.3f}")


def main():
    G = pd.read_parquet(f"{H}/research/nhl_sim/edge_hunt_2026-09-30/games_lines.parquet")
    G = G[G.season.isin(SEASONS)].copy(); G["game_id"] = G.game_id.astype(int)
    P = pd.read_parquet(PR); P["game_id"] = P.game_id.astype(int); P = P.drop(columns=[c for c in ["season", "home", "away", "date"] if c in P.columns])
    O = pd.concat([pd.read_parquet(f) for f in OLD]); O["game_id"] = O.game_id.astype(int)
    d = pd.read_parquet(f"{H}/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet")
    d = d[d.event_id.isin(G.event_id)].copy()
    d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
    d["lead_h"] = (d.ct - d.snap).dt.total_seconds() / 3600
    d = d[d.lead_h >= 12]
    first = d[(d.bookmaker == "pinnacle") & (d.market == "h2h")].groupby("event_id").snap.min().rename("snap_e")
    d = d.merge(first, on="event_id"); d = d[d.snap == d.snap_e]; d["dec"] = dec(d.price); d["imp"] = 1 / d.dec
    # Pinnacle early fair (ML) for the EV baseline
    pin = d[(d.bookmaker == "pinnacle") & (d.market == "h2h")].pivot_table(index="event_id", columns="outcome_name", values="imp", aggfunc="first")
    base = G[["game_id", "event_id", "season", "date", "home", "away", "home_team", "away_team", "hg", "ag", "home_win", "pin_p_h", "tl_pin", "pin_p_over"]].merge(P, on="game_id").merge(O[["game_id", "p_home_win"]].rename(columns={"p_home_win": "p_home_swapped"}), on="game_id")
    # ---------------- A-05 ML
    h = d[(d.market == "h2h") & d.bookmaker.isin(BOOKS)]
    best = h.sort_values("dec").groupby(["event_id", "outcome_name"]).last().reset_index()[["event_id", "outcome_name", "dec", "bookmaker"]]
    x = best.merge(base, on="event_id")
    x["side"] = np.where(x.outcome_name == x.home_team, "home", "away")
    x["pe"] = np.where(x.side == "home", x.p_home_win, 1 - x.p_home_win)
    x["pe_sw"] = np.where(x.side == "home", x.p_home_swapped, 1 - x.p_home_swapped)
    x["fair_close"] = np.where(x.side == "home", x.pin_p_h, 1 - x.pin_p_h)
    pe_ = pin.reset_index().melt(id_vars="event_id", var_name="outcome_name", value_name="imp_pin")
    tot = pin.sum(axis=1).rename("ov").reset_index()
    x = x.merge(pe_, on=["event_id", "outcome_name"], how="left").merge(tot, on="event_id", how="left")
    x["fair_early"] = x.imp_pin / x.ov
    x["win"] = np.where(x.side == "home", x.home_win == 1, x.home_win == 0)
    x["ret"] = np.where(x.win, x.dec - 1, -1.0); x["clv"] = x.fair_close - 1 / x.dec
    x = x[x.fair_close.notna()]
    print(f"===== A-05 ML (early best-of-8 vs fixed engine, thr {THR}) =====  sides {len(x)}")
    for s in SEASONS:
        y = x[x.season == s]
        rep(y[(1 / y.dec) <= y.pe - THR], f"{s} FIXED engine flags")
        rep(y[(1 / y.dec) <= y.pe_sw - THR], f"{s} NULL swapped-engine flags")
        rep(y[(1 / y.dec) <= y.fair_early - 0.02], f"{s} baseline EV early (best >= 2% vs Pinnacle fair)")
        rep(y[((1 / y.dec) <= y.pe - THR) & ((1 / y.dec) <= y.fair_early - 0.02)], f"{s} BOTH engine flag AND EV flag")
        rep(y[((1 / y.dec) <= y.pe - THR) & ((1 / y.dec) > y.fair_early - 0.02)], f"{s} engine flag but NOT EV flag")
    f = x[(1 / x.dec) <= x.pe - THR]
    print(f.groupby("side").agg(n=("clv", "size"), clv=("clv", "mean"), roi=("ret", "mean")).round(4).to_string())
    print(f.groupby("bookmaker").agg(n=("clv", "size"), clv=("clv", "mean"), roi=("ret", "mean")).round(4).to_string())
    # ---------------- A-06 totals
    t = d[(d.market == "totals") & d.bookmaker.isin(BOOKS) & d.point.notna()]
    q = t.merge(base, on="event_id")
    q["pe"] = [p_side_pmf(r, r.point, r.outcome_name) for r in q.itertuples()]
    q = q[q.pe.notna()].copy()
    q["res_tot"] = q.hg + q.ag
    q["push"] = q.res_tot == q.point
    q["win"] = np.where(q.outcome_name == "Over", q.res_tot > q.point, q.res_tot < q.point)
    q = q[~q.push].copy()
    q["ret"] = np.where(q.win, q.dec - 1, -1.0)
    at_close_line = np.isclose(q.point, q.tl_pin) & q.pin_p_over.notna()
    q["clv"] = np.where(at_close_line, np.where(q.outcome_name == "Over", q.pin_p_over, 1 - q.pin_p_over) - 1 / q.dec, np.nan)
    bestq = q.sort_values("dec").groupby(["event_id", "point", "outcome_name"]).last().reset_index()
    print(f"\n===== A-06 totals (early best price per point/side vs fixed engine pmf, thr {THR}) =====  quotes {len(bestq)}")
    for s in SEASONS:
        y = bestq[bestq.season == s]; f = y[(1 / y.dec) <= y.pe - THR]
        rep(f, f"{s} ALL flags")
        for side in ["Over", "Under"]:
            rep(f[f.outcome_name == side], f"{s}   {side}")
        rep(f[np.isclose(f.point, f.tl_pin)], f"{s}   at Pinnacle close line")
        rep(f[~np.isclose(f.point, f.tl_pin)], f"{s}   off Pinnacle close line (ROI only)")
    f = bestq[(1 / bestq.dec) <= bestq.pe - THR]
    print(f.groupby("point").agg(n=("ret", "size"), roi=("ret", "mean"), clv=("clv", "mean")).round(4).to_string())


if __name__ == "__main__":
    main()
