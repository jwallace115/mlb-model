#!/usr/bin/env python3
"""PREREG_EV.md: best soft-book price vs Pinnacle de-vigged fair, same snapshot. 2022-23 + 2023-24 only. One run."""
import numpy as np, pandas as pd

P3 = "/home/claude/nhlhunt/p3"
import os
SEASONS = [int(s) for s in os.environ.get("EV_SEASONS", "2022,2023").split(",")]
THR = 0.02


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def sides(snap):
    """snap: rows of one snapshot for many events. Returns one row per (event, market, side, point) with
    pinnacle fair prob and best non-pinnacle price + book."""
    s = snap.copy()
    s["dec"] = dec(s.price)
    s["side"] = np.select([s.market.eq("h2h") & s.outcome_name.eq(s.home_team),
                           s.market.eq("h2h") & s.outcome_name.eq(s.away_team),
                           s.market.eq("totals") & s.outcome_name.eq("Over"),
                           s.market.eq("totals") & s.outcome_name.eq("Under"),
                           s.market.eq("spreads") & s.outcome_name.eq(s.home_team),
                           s.market.eq("spreads") & s.outcome_name.eq(s.away_team)],
                          ["H", "A", "O", "U", "H", "A"], "")
    s = s[s.side != ""]
    s["pt"] = np.where(s.market == "h2h", 0.0, s.point.astype(float))
    s = s[(s.market != "spreads") | (s.pt.abs() == 1.5)]
    pin = s[s.bookmaker == "pinnacle"]
    # Pinnacle two-way pairs: h2h (H,A); totals (O,U) at the same point; spreads H at pt with A at -pt
    pin = pin.drop_duplicates(["event_id", "market", "side", "pt"])
    pin["key"] = np.where(pin.market == "spreads", np.where(pin.side == "H", pin.pt, -pin.pt), pin.pt)
    g = pin.groupby(["event_id", "market", "key"])
    pin = pin[g.side.transform("size") == 2].copy()
    pin["imp"] = 1 / pin.dec
    pin["fair"] = pin.imp / pin.groupby(["event_id", "market", "key"]).imp.transform("sum")
    # one Pinnacle point per event x market (h2h trivially; totals/spreads: Pinnacle posts one main line)
    npts = pin.groupby(["event_id", "market"]).key.transform("nunique")
    pin = pin[npts == 1]
    oth = s[s.bookmaker != "pinnacle"]
    best = oth.sort_values("dec", ascending=False).drop_duplicates(["event_id", "market", "side", "pt"])
    m = pin[["event_id", "market", "side", "pt", "fair"]].merge(
        best[["event_id", "market", "side", "pt", "dec", "bookmaker"]], on=["event_id", "market", "side", "pt"])
    m["ev"] = m.fair * m.dec - 1
    return m


def grade(r):
    mg = r.hg - r.ag
    if r.market == "h2h":
        return (r.dec - 1) if ((r.side == "H") == (r.home_win == 1)) else -1.0
    if r.market == "totals":
        t = r.hg + r.ag
        if t == r.pt:
            return 0.0
        return (r.dec - 1) if ((r.side == "O") == (t > r.pt)) else -1.0
    # spreads: side H at pt: home covers if mg + pt > 0
    x = mg + r.pt if r.side == "H" else -mg + r.pt
    return (r.dec - 1) if x > 0 else (-1.0 if x < 0 else 0.0)


def clustered(b):
    gsum = b.groupby("event_id").agg(r=("ret", "sum"), n=("ret", "size"))
    roi = gsum.r.sum() / gsum.n.sum()
    G = len(gsum)
    se = np.sqrt(G / (G - 1) * ((gsum.r - roi * gsum.n) ** 2).sum()) / gsum.n.sum() if G > 1 else np.nan
    return roi, se


def main():
    G = pd.read_parquet(f"{P3}/games_lines.parquet")
    G = G[G.season.isin(SEASONS)][["event_id", "season", "date", "hg", "ag", "home_win"]]
    d = pd.read_parquet(f"{P3}/lines_all.parquet")
    d = d[d.event_id.isin(G.event_id)].copy()
    d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
    d["lead_h"] = (d.ct - d.snap).dt.total_seconds() / 3600
    d = d[d.snap < d.ct]
    close_t = d.groupby("event_id").snap.max().rename("t")
    early_t = d[(d.lead_h >= 12) & (d.bookmaker == "pinnacle") & (d.market == "h2h")].groupby("event_id").snap.min().rename("t")
    snaps = {}
    for name, T in [("CLOSE", close_t), ("EARLY", early_t)]:
        x = d.merge(T, left_on=["event_id", "snap"], right_on=["event_id", "t"])
        snaps[name] = sides(x)
    C = snaps["CLOSE"][["event_id", "market", "side", "pt", "fair"]].rename(columns={"fair": "fair_close"})
    print(f"events: {G.event_id.nunique()}  close-snapshot lead median "
          f"{d.merge(close_t, left_on=['event_id','snap'], right_on=['event_id','t']).lead_h.median():.2f} h")
    out = []
    for name, m in snaps.items():
        m = m.merge(G, on="event_id")
        q = m[m.ev >= THR].sort_values("ev", ascending=False).drop_duplicates(["event_id", "market"]).copy()
        q["ret"] = q.apply(grade, axis=1)
        q = q.merge(C, on=["event_id", "market", "side", "pt"], how="left")
        q["clv"] = q.fair_close * q.dec - 1
        q["mkt_label"] = q.market
        print(f"\n===== {name} snapshot: candidate sides {len(m)}, share with EV>=2% {len(q)/len(m):.3f} =====")
        roi, se = clustered(q)
        lo = roi - 1.6449 * se
        print(f"POOLED: bets {len(q)}  games {q.event_id.nunique()}  ROI {roi:+.4f}  SE {se:.4f}  90% lower {lo:+.4f}  "
              f"mean EV {q.ev.mean():+.4f}  mean CLV {q.clv.mean():+.4f} (n with close {q.clv.notna().sum()})")
        out.append(dict(snap=name, cut="pooled", bets=len(q), roi=roi, se=se, lo90=lo, ev=q.ev.mean(), clv=q.clv.mean()))
        for col in ["season", "market", "bookmaker"]:
            for k, b in q.groupby(col):
                r, s_ = clustered(b)
                print(f"  {col}={k}: bets {len(b)} ROI {r:+.4f} (SE {s_:.4f}) EV {b.ev.mean():+.4f} CLV {b.clv.mean():+.4f}")
                out.append(dict(snap=name, cut=f"{col}={k}", bets=len(b), roi=r, se=s_, ev=b.ev.mean(), clv=b.clv.mean()))
        q["evband"] = pd.cut(q.ev, [0.02, 0.03, 0.05, 0.10, 1.0])
        for k, b in q.groupby("evband", observed=True):
            r, s_ = clustered(b)
            print(f"  EV {k}: bets {len(b)} ROI {r:+.4f} (SE {s_:.4f}) CLV {b.clv.mean():+.4f}")
            out.append(dict(snap=name, cut=f"ev={k}", bets=len(b), roi=r, se=s_, ev=b.ev.mean(), clv=b.clv.mean()))
        q["month"] = pd.to_datetime(q.date).dt.to_period("M")
        mo = q.groupby("month").apply(lambda b: pd.Series(dict(bets=len(b), roi=clustered(b)[0], clv=b.clv.mean())))
        print(mo.round(4).to_string())
        q["evband"] = q.evband.astype(str); q["month"] = q.month.astype(str)
        q.to_parquet(f"/home/claude/nhl/ev/bets_{name.lower()}_{'_'.join(map(str, SEASONS))}.parquet", index=False)
    pd.DataFrame(out).to_csv(f"/home/claude/nhl/ev/ev_results_{'_'.join(map(str, SEASONS))}.csv", index=False)


if __name__ == "__main__":
    main()
