#!/usr/bin/env python3
"""E-WO1 Item 3 completion (Cowork): state_at_snapshot_2023 — one row per (in-play snapshot, game) with the game
state at the snapshot's wall time (ESPN wallclock -> game seconds), strength/goalie flags from the repo's
state_time table, active penalties, and every book's live h2h / totals."""
import gzip, json, glob, numpy as np, pandas as pd
H = "/home/claude/hunt"; E = f"{H}/e"
ALIAS = {"NJ": "NJD", "TB": "TBL", "LA": "LAK", "SJ": "SJS"}


def dec(a):
    a = np.asarray(a, float); return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def clock_sec(s):
    m, ss = s.split(":"); return int(m) * 60 + int(ss)


def load_espn():
    G = pd.read_parquet(f"{H}/research/nhl_sim/edge_hunt_2026-09-30/games_lines.parquet")
    G = G[G.season == 2023].copy(); G["game_id"] = G.game_id.astype(int)
    games = {}
    unmatched = []
    for f in sorted(glob.glob(f"{E}/nhl/cache/espn_pbp/*.json.gz")):
        j = json.load(gzip.open(f))
        comp = j["header"]["competitions"][0]
        teams = {c["homeAway"]: ALIAS.get(c["team"]["abbreviation"], c["team"]["abbreviation"]) for c in comp["competitors"]}
        d = pd.Timestamp(comp["date"])
        cand = G[(G.home == teams["home"]) & (G.away == teams["away"]) & ((G.ct - d).abs() < pd.Timedelta("12h"))]
        if len(cand) != 1:
            unmatched.append((f, teams, comp["date"], len(cand))); continue
        gid = int(cand.game_id.iloc[0])
        rows = []
        for p in j.get("plays", []):
            per = p["period"]["number"]; el = clock_sec(p["clock"]["displayValue"])
            sec = (per - 1) * 1200 + el if per <= 3 else (3600 + el if per == 4 else 3900)
            rows.append((pd.Timestamp(p["wallclock"]), per, sec, p["homeScore"], p["awayScore"], p["type"]["text"]))
        P = pd.DataFrame(rows, columns=["wall", "period", "sec", "hs", "as_", "type"]).sort_values("wall", kind="stable").reset_index(drop=True)
        games[gid] = P
    print(f"ESPN games matched {len(games)}; unmatched {len(unmatched)}: {unmatched[:5]}")
    return G, games


def state_at(P, ts):
    """Game state at wall time ts from ESPN plays. Returns dict or None if not started / finished."""
    idx = P.index[P.wall <= ts]
    if len(idx) == 0:
        return dict(phase="pre")
    i = idx[-1]; r = P.loc[i]
    if r.type in ("End of Game", "Shootout End") or (P.type.iloc[-1] == "End of Game" and i == len(P) - 1):
        return dict(phase="final")
    if r.type == "Period End":
        return dict(phase="intermission", period=int(r.period), sec=int(r.sec), hs=int(r.hs), as_=int(r.as_))
    nxt = P.loc[i + 1] if i + 1 < len(P) else None
    gap = (ts - r.wall).total_seconds()
    adv = gap if nxt is None else min(gap, max(nxt.sec - r.sec, 0))
    sec = int(r.sec + adv)
    per = int(r.period)
    if per <= 3:
        sec = min(sec, per * 1200 - 1)
    else:
        sec = min(sec, 3899)
    return dict(phase="live", period=per, sec=sec, hs=int(r.hs), as_=int(r.as_), wall_gap=gap)


def main():
    G, games = load_espn()
    st = pd.read_parquet(f"{H}/nhl/data/sim/events/season=2023/state_time.parquet"); st["game_id"] = st.game_id.astype(int)
    pen = pd.read_parquet(f"{H}/nhl/data/sim/events/season=2023/penalties.parquet"); pen["game_id"] = pen.game_id.astype(int)
    pen["start"] = pen.seconds.astype(int); pen["end"] = pen.start + (pen.minutes * 60).astype(int)
    files = sorted(glob.glob(f"{E}/data/odds_archive/nhl/history/inplay/season=2023/*.parquet"))
    q = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    q["ts"] = pd.to_datetime(q.snapshot_utc); q["ct"] = pd.to_datetime(q.commence_time); q["dec"] = dec(q.price)
    ev = G.set_index("event_id")
    st_by = {k: v.sort_values("start_sec") for k, v in st.groupby("game_id")}
    pen_by = {k: v for k, v in pen.groupby("game_id")}
    rows = []
    import time as _t; _t0 = _t.time(); _k = 0
    for (ts, e), x in q.groupby(["ts", "event_id"]):
        _k += 1
        if _k % 2000 == 0: print(f"{_k} groups {_t.time()-_t0:.0f}s", flush=True)
        if e not in ev.index:
            continue
        g = ev.loc[e]; gid = int(g.game_id)
        started = x.ct.iloc[0] < ts
        s = state_at(games[gid], ts) if (gid in games and started) else (dict(phase="pre") if not started else dict(phase="no_espn"))
        row = dict(ts=ts, event_id=e, game_id=gid, home=g.home, away=g.away, commence=x.ct.iloc[0], hg=g.hg, ag=g.ag, decided=g.decided,
                   home_win=g.home_win, pin_p_h_pre=g.pin_p_h, tl_pin_pre=g.tl_pin, pin_p_over_pre=g.pin_p_over, **s)
        if s["phase"] == "live":
            sg = st_by.get(gid, st.iloc[0:0]); sp = sg[(sg.start_sec <= s["sec"]) & (sg.end_sec > s["sec"])]
            if len(sp):
                sp = sp.iloc[0]
                row.update(home_skaters=int(sp.home_skaters), away_skaters=int(sp.away_skaters), home_goalie=int(sp.home_goalie),
                           away_goalie=int(sp.away_goalie), st_score_diff_home=int(sp.score_diff_home))
            pg = pen_by.get(gid, pen.iloc[0:0]); ap = pg[(pg.start <= s["sec"]) & (pg.end > s["sec"]) & pg.minutes.isin([2, 4, 5])]
            row["pen_home"] = json.dumps([[int(r.end - s["sec"]), int(r.minutes * 60)] for r in ap[ap.team == "home"].itertuples()])
            row["pen_away"] = json.dumps([[int(r.end - s["sec"]), int(r.minutes * 60)] for r in ap[ap.team == "away"].itertuples()])
        # prices
        for b, y in x.groupby("bookmaker"):
            h2 = y[y.market == "h2h"]; to = y[y.market == "totals"]
            hp = h2[h2.outcome_name == x.home_team.iloc[0]]; ap_ = h2[h2.outcome_name == x.away_team.iloc[0]]
            if len(hp) == 1 and len(ap_) == 1:
                row[f"{b}_dec_h"] = float(hp.dec.iloc[0]); row[f"{b}_dec_a"] = float(ap_.dec.iloc[0])
            if len(to) == 2 and to.point.nunique() == 1:
                row[f"{b}_tot"] = float(to.point.iloc[0])
                row[f"{b}_dec_o"] = float(to[to.outcome_name == "Over"].dec.iloc[0]); row[f"{b}_dec_u"] = float(to[to.outcome_name == "Under"].dec.iloc[0])
        rows.append(row)
    T = pd.DataFrame(rows)
    T.to_parquet(f"{E}/state_at_snapshot_2023.parquet", index=False)
    print("rows", len(T), T.phase.value_counts().to_dict())
    L = T[T.phase == "live"]
    print("live rows with strength:", int(L.home_skaters.notna().sum()), "| pinnacle h2h present:", int(L.pinnacle_dec_h.notna().sum()), "| pinnacle totals:", int(L.pinnacle_tot.notna().sum()))
    # ---- pre-registered sanity checks (E-WO1 item 3)
    tot_now = L.hs + L.as_
    a = (L.pinnacle_tot >= tot_now + 0.5)[L.pinnacle_tot.notna()]
    print(f"(a) Pinnacle live total >= score+0.5: {a.mean():.4f} (n {len(a)})  -> {'HELD' if a.mean() >= 0.99 else 'NOT HELD'}")
    pre = T[T.phase == "pre"]; print(f"(b) pre-match rows: {len(pre)} (period undefined by construction: HELD)")
    pulled = ((L.home_goalie == 0) | (L.away_goalie == 0)).mean()
    print(f"(c) share of live rows with a goalie pulled: {pulled:.4f} -> {'HELD' if 0.02 <= pulled <= 0.15 else 'NOT HELD'}")
    d = L[L.st_score_diff_home.notna()]
    agree = ((d.hs - d.as_) == d.st_score_diff_home).mean()
    print(f"(d) ESPN score diff == state_time score diff at mapped second: {agree:.4f} (n {len(d)})")
    print("period dist of live rows:", L.period.value_counts().sort_index().to_dict())
    print("wall gap since last play (s): median", L.wall_gap.median(), "90th", L.wall_gap.quantile(.9))
    print("live rows per game:", L.groupby("game_id").size().describe().round(2).to_dict())


if __name__ == "__main__":
    main()
