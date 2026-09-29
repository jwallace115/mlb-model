#!/usr/bin/env python3
"""constants_v7 = constants_v5 + measured engine inputs that v5 lacks (Cowork S34, 2026-09-29).
Fit seasons 2021-22 + 2022-23, from the committed event tables. Replaces constants_v6.json, which had no generator.

Adds:
  pull_hazard_per_second[k][bin]  pulls / seconds at risk. At risk = 3rd period, last 300 s, team goalie in, team
                                  trailing by k (k = 1, 2, 3+), team NOT on a power play (5v5 or shorthanded).
                                  bin = 30-s bin of time remaining (0 = last 30 s).
  pp_penalty                      penalties that CREATE a power play (the opponent's skater advantage rises within
                                  the -1 s .. +2 s window around the call), per team-game, and the nominal length
                                  shares of those penalties. Offsetting minors, fighting majors and misconducts
                                  mostly do not create a power play; v2's penalty_shares counted every penalty.
Run: python3 nhl/sim/build_constants_v7.py   (prints null controls; writes nhl/data/sim/constants_v7.json)
"""
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "nhl" / "data" / "sim" / "events"
V5 = ROOT / "nhl" / "data" / "sim" / "constants_v5.json"
OUT = ROOT / "nhl" / "data" / "sim" / "constants_v7.json"
FIT = [2021, 2022]
BIN = 30
WINDOW = 300


def load(table):
    return pd.concat([pd.read_parquet(EV / f"season={s}" / f"{table}.parquet") for s in FIT], ignore_index=True)


def team_view(st):
    """One row per (span, team) with the team's own skaters, goalie flag and score diff."""
    h = pd.DataFrame({"game_id": st.game_id, "period": st.period, "start": st.start_sec, "end": st.end_sec,
                      "sk": st.home_skaters, "opp_sk": st.away_skaters, "goalie": st.home_goalie,
                      "sd": st.score_diff_home, "team": "home"})
    a = pd.DataFrame({"game_id": st.game_id, "period": st.period, "start": st.start_sec, "end": st.end_sec,
                      "sk": st.away_skaters, "opp_sk": st.home_skaters, "goalie": st.away_goalie,
                      "sd": -st.score_diff_home, "team": "away"})
    return pd.concat([h, a], ignore_index=True).sort_values(["game_id", "team", "start"]).reset_index(drop=True)


def pull_hazard(st):
    tv = team_view(st)
    p3end = 3 * 1200
    tv = tv[(tv.period == 3)]
    # at-risk seconds, split by 30-s bin of time remaining
    risk = tv[(tv.goalie == 1) & (tv.sd <= -1) & (tv.sk <= tv.opp_sk)].copy()
    risk["k"] = (-risk.sd).clip(upper=3).astype(int)
    at_risk = {}
    for r in risk.itertuples(index=False):
        s, e = max(r.start, p3end - WINDOW), min(r.end, p3end)
        while s < e:
            rem = p3end - s - 1                       # seconds remaining at second s (0-based, last second -> 0)
            b = (rem // BIN) * BIN
            bin_start_sec = p3end - b - BIN           # first game second of this bin
            seg_end = min(e, p3end - b)
            at_risk[(r.k, b)] = at_risk.get((r.k, b), 0) + (seg_end - s)
            s = seg_end
    # pulls: goalie 1 -> 0 transitions within the same game/team, previous span at risk
    tv = tv.copy()
    prev = tv.groupby(["game_id", "team"]).shift(1)
    pull = tv[(tv.goalie == 0) & (prev.goalie == 1) & (prev.sd <= -1) & (prev.sk <= prev.opp_sk)
              & (tv.start >= p3end - WINDOW) & (tv.start < p3end)].copy()
    pull["k"] = (-prev.loc[pull.index, "sd"]).clip(upper=3).astype(int)
    pull["b"] = ((p3end - pull.start - 1) // BIN) * BIN
    pulls = pull.groupby(["k", "b"]).size().to_dict()
    data = {}
    for (k, b), secs in sorted(at_risk.items()):
        n = int(pulls.get((k, b), 0))
        data.setdefault(str(-k), {})[str(int(b))] = {"hazard_per_sec": round(n / secs, 8), "pulls": n, "seconds_at_risk": int(secs)}
    orphan = {kb: n for kb, n in pulls.items() if kb not in at_risk}
    return data, int(sum(pulls.values())), orphan


def pp_penalties(st, pe):
    st = st.sort_values(["game_id", "start_sec"])
    st = st.assign(adv=st.home_skaters - st.away_skaters)
    games = {g: (d.start_sec.to_numpy(), d.end_sec.to_numpy(), d.adv.to_numpy()) for g, d in st.groupby("game_id")}

    def adv_at(g, t):
        s, e, a = games[g]
        i = np.searchsorted(s, t, side="right") - 1
        return int(a[i]) if i >= 0 and t < e[i] else None

    rows = []
    for r in pe.itertuples(index=False):
        if r.game_id not in games:
            continue
        a0, a1 = adv_at(r.game_id, max(r.seconds - 1, 0)), adv_at(r.game_id, r.seconds + 2)
        if a0 is None or a1 is None:
            continue
        delta = (a0 - a1) if r.team == "home" else (a1 - a0)   # opponent's gain in skater advantage
        rows.append((r.minutes, delta > 0))
    R = pd.DataFrame(rows, columns=["minutes", "creates_pp"])
    n_team_games = 2 * st.game_id.nunique()
    total_secs = float(st.end_sec.sub(st.start_sec).sum())
    pp = R[R.creates_pp]
    nominal = pp.minutes.map({0: 2, 2: 2, 10: 2, 4: 4, 5: 5}).fillna(2)   # 0/10-min calls that create a PP travel with a minor
    shares = nominal.value_counts(normalize=True).to_dict()
    by_type = R.groupby("minutes").creates_pp.agg(["mean", "sum", "count"])
    return {
        "per_team_game": round(len(pp) / n_team_games, 4),
        "per_team_per_second": len(pp) / n_team_games / (total_secs / (n_team_games / 2)),
        "nominal_share_2min": round(shares.get(2, 0.0), 4),
        "nominal_share_4min": round(shares.get(4, 0.0), 4),
        "nominal_share_5min": round(shares.get(5, 0.0), 4),
        "n_pp_creating": int(len(pp)), "n_penalties_matched": int(len(R)), "n_team_games": int(n_team_games),
        "creates_pp_rate_by_minutes": {str(int(m)): round(float(x["mean"]), 4) for m, x in by_type.iterrows()},
        "derivation": "penalty creates a PP if the opponent's skater advantage is higher at t+2 s than at t-1 s; "
                      "per_team_per_second = PP-creating penalties / team-games / mean game seconds",
    }


def main():
    v5 = json.loads(V5.read_text())
    st, pe = load("state_time"), load("penalties")
    data, n_pulls, orphan = pull_hazard(st)
    out = {k: v for k, v in v5.items() if k != "constants"}
    out["version"] = 7
    out["based_on"] = "constants_v5.json (all v5 fields copied unchanged)"
    out["constants"] = dict(v5["constants"])
    out["constants"]["pull_hazard_per_second"] = {
        "data": data, "fit_seasons": FIT, "total_pulls": n_pulls,
        "derivation": "pulls / seconds at risk (3rd period last 300 s, goalie in, trailing by k (3 = 3+), not on a PP), 30-s bins of time remaining",
    }
    out["constants"]["pp_penalty"] = pp_penalties(st, pe)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    # NULL CONTROLS
    assert all(out["constants"][k] == v for k, v in v5["constants"].items()), "a v5 field changed"
    print("null (a): every v5 field identical in v7")
    print(f"pulls counted: {n_pulls}; pulls with no at-risk seconds in their bin: {orphan}")
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    assert hashlib.sha256(OUT.read_bytes()).hexdigest() == sha, "not byte-identical"
    print("null (b): byte-identical on rewrite; sha256", sha)
    print("pp_penalty:", {k: v for k, v in out["constants"]["pp_penalty"].items() if k != "derivation"})


if __name__ == "__main__":
    main()
