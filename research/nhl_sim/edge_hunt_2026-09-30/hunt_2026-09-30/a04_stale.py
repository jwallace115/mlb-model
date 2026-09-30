#!/usr/bin/env python3
"""Ledger A-04: soft books lag a Pinnacle move. EV_SEASONS env (default dev 2022,2023)."""
import os, numpy as np, pandas as pd
H = "/home/claude/hunt"
SEASONS = [int(s) for s in os.environ.get("EV_SEASONS", "2022,2023").split(",")]
MOVE, STALE = 0.03, 0.02
def dec(a):
    a = np.asarray(a, float); return np.where(a > 0, a / 100 + 1, 100 / -a + 1)
d = pd.read_parquet(f"{H}/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet")
d = d[d.market == "h2h"].copy()
d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
d["season"] = np.where(d.ct.dt.month >= 9, d.ct.dt.year, d.ct.dt.year - 1)
d = d[d.season.isin(SEASONS)]
d["lead"] = (d.ct - d.snap).dt.total_seconds() / 3600
d["dec"] = dec(d.price); d["side"] = np.where(d.outcome_name == d.home_team, "home", "away")
G = pd.read_parquet(f"{H}/research/nhl_sim/edge_hunt_2026-09-30/games_lines.parquet")[["event_id", "home_win", "date"]]
# Pinnacle fair per event-snapshot
p = d[d.bookmaker == "pinnacle"].pivot_table(index=["event_id", "snap"], columns="side", values="dec", aggfunc="first").dropna().reset_index()
p["ph"] = (1 / p.home) / (1 / p.home + 1 / p.away)
p = p.sort_values(["event_id", "snap"])
p["ph_prev"] = p.groupby("event_id").ph.shift(1); p["k"] = p.groupby("event_id").cumcount()
close = p.groupby("event_id").last()[["ph"]].rename(columns={"ph": "ph_close"})
p = p.merge(close, on="event_id").merge(d[["event_id", "snap", "lead"]].drop_duplicates(), on=["event_id", "snap"])
p = p[p.k >= 1]
p["move"] = p.ph - p.ph_prev
mv = p[(p.move.abs() >= MOVE) & (p.lead >= 1)].copy()
mv["toward"] = np.where(mv.move > 0, "home", "away")
print(f"seasons {SEASONS}: Pinnacle event-snapshots with a previous snapshot {len(p)}; moves >= {MOVE} and lead >= 1h: {len(mv)} ({mv.event_id.nunique()} events)")
soft = d[d.bookmaker != "pinnacle"][["event_id", "snap", "bookmaker", "side", "dec"]]
x = mv.merge(soft, on=["event_id", "snap"])
x["fair_k"] = np.where(x.side == "home", x.ph, 1 - x.ph)
x["fair_close"] = np.where(x.side == "home", x.ph_close, 1 - x.ph_close)
x["stale"] = x.fair_k - 1 / x.dec
x = x.merge(G, on="event_id")
x["win"] = np.where(x.side == "home", x.home_win == 1, x.home_win == 0)
x["ret"] = np.where(x.win, x.dec - 1, -1.0); x["clv"] = x.fair_close - 1 / x.dec
x["season"] = np.where(pd.to_datetime(x.date).dt.month >= 9, pd.to_datetime(x.date).dt.year, pd.to_datetime(x.date).dt.year - 1)
def report(f, label):
    n = len(f)
    if n < 2: print(f"{label}: n={n}"); return
    se = f.clv.std(ddof=1) / np.sqrt(n); rse = f.ret.std(ddof=1) / np.sqrt(n)
    print(f"{label}: flags {n} (events {f.event_id.nunique()}) CLV {f.clv.mean():+.4f} (SE {se:.4f}, 90% lo {f.clv.mean()-1.6449*se:+.4f}) ROI {f.ret.mean():+.4f} (SE {rse:.4f}) hit {f.win.mean():.3f}")
for s in SEASONS:
    y = x[x.season == s]
    report(y[(y.side == y.toward) & (y.stale >= STALE)], f"{s} TOWARD-side stale>={STALE}")
    report(y[(y.side != y.toward) & (y.stale >= STALE)], f"{s} NULL away-from-move side stale>={STALE}")
f = x[(x.side == x.toward) & (x.stale >= STALE)]
print("\nby book:\n", f.groupby("bookmaker").agg(n=("clv", "size"), clv=("clv", "mean"), roi=("ret", "mean")).round(4).to_string())
f = f.assign(mv_band=pd.cut(f.move.abs(), [0.03, 0.04, 0.06, 1]), lead_band=pd.cut(f.lead, [1, 6, 20, 30, 1000]), fav=f.fair_k > 0.5)
for c in ["mv_band", "lead_band", "fav"]:
    print(f.groupby(c, observed=True).agg(n=("clv", "size"), clv=("clv", "mean"), roi=("ret", "mean")).round(4).to_string())
f["month"] = pd.to_datetime(f.date).dt.to_period("M")
print(f.groupby("month").agg(n=("clv", "size"), clv=("clv", "mean"), roi=("ret", "mean")).round(4).to_string())
