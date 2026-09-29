#!/usr/bin/env python3
"""Phase 3: one row per NHL game (2022-23..2025-26) with pre-puck prices from the Odds API history pulled by NHL WO2.
Last snapshot strictly before puck; Pinnacle de-vigged references; median-of-books prices in DECIMAL odds.
Joined to phase-1 games.parquet (scores, OT/SO, point-in-time features) by (ET date, home, away)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
P1 = HERE.parent / "out"
NAME = {"Anaheim Ducks": "ANA", "Arizona Coyotes": "ARI", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
        "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR", "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
        "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL", "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
        "Florida Panthers": "FLA", "Los Angeles Kings": "LAK", "Minnesota Wild": "MIN", "Montréal Canadiens": "MTL",
        "Nashville Predators": "NSH", "New Jersey Devils": "NJD", "New York Islanders": "NYI", "New York Rangers": "NYR",
        "Ottawa Senators": "OTT", "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJS",
        "Seattle Kraken": "SEA", "St Louis Blues": "STL", "Tampa Bay Lightning": "TBL", "Toronto Maple Leafs": "TOR",
        "Utah Hockey Club": "UTA", "Utah Mammoth": "UTA", "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK",
        "Washington Capitals": "WSH", "Winnipeg Jets": "WPG"}


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def main():
    d = pd.read_parquet(HERE / "lines_all.parquet")
    d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
    d = d[d.snap < d.ct]
    last = d.groupby("event_id").snap.transform("max")
    d = d[d.snap == last].copy()
    d["lead_h"] = (d.ct - d.snap).dt.total_seconds() / 3600
    d["dec"] = dec(d.price)
    ev = d.drop_duplicates("event_id")[["event_id", "home_team", "away_team", "ct", "lead_h"]].copy()
    n_far = int((ev.lead_h > 6).sum())
    ev = ev[ev.lead_h <= 6]
    ev["home"], ev["away"] = ev.home_team.map(NAME), ev.away_team.map(NAME)
    ev["date"] = (ev.ct.dt.tz_convert("America/New_York")).dt.strftime("%Y-%m-%d")
    rows = []
    D = {e: g for e, g in d[d.event_id.isin(ev.event_id)].groupby("event_id")}
    for e in ev.itertuples(index=False):
        g = D[e.event_id]
        r = {"event_id": e.event_id, "lead_h": e.lead_h}
        # moneyline
        h2 = g[g.market == "h2h"]
        ph = h2[(h2.bookmaker == "pinnacle")]
        hp = ph[ph.outcome_name == e.home_team].price; ap = ph[ph.outcome_name == e.away_team].price
        if len(hp) == 1 and len(ap) == 1:
            ih, ia = 1 / dec(hp.iloc[0]), 1 / dec(ap.iloc[0])
            r["pin_p_h"] = float(ih / (ih + ia))
        r["med_dec_h"] = h2[h2.outcome_name == e.home_team].dec.median()
        r["med_dec_a"] = h2[h2.outcome_name == e.away_team].dec.median()
        r["n_books_ml"] = h2.bookmaker.nunique()
        imp_h = 1 / h2[h2.outcome_name == e.home_team].dec
        r["ml_disp"] = float(imp_h.max() - imp_h.min()) if len(imp_h) else np.nan
        # puck line: main +/-1.5 only
        sp = g[(g.market == "spreads") & (g.point.abs() == 1.5)]
        fav = sp[sp.point == -1.5]
        pin = sp[sp.bookmaker == "pinnacle"]
        pf = pin[pin.point == -1.5]
        if len(pf) == 1 and len(pin) == 2:
            r["pl_fav"] = pf.outcome_name.iloc[0]
            i1 = 1 / dec(pf.price.iloc[0]); i2 = 1 / dec(pin[pin.point == 1.5].price.iloc[0])
            r["pin_p_plfav"] = float(i1 / (i1 + i2))
            r["med_dec_plfav"] = fav[fav.outcome_name == r["pl_fav"]].dec.median()
            dog = sp[(sp.point == 1.5) & (sp.outcome_name != r["pl_fav"])]
            r["med_dec_pldog"] = dog.dec.median()
        # totals at Pinnacle's line
        to = g[g.market == "totals"]
        pt = to[to.bookmaker == "pinnacle"]
        if len(pt) == 2 and pt.point.nunique() == 1:
            line = pt.point.iloc[0]
            io = 1 / dec(pt[pt.outcome_name == "Over"].price.iloc[0]); iu = 1 / dec(pt[pt.outcome_name == "Under"].price.iloc[0])
            r["tl_pin"] = line; r["pin_p_over"] = float(io / (io + iu))
            same = to[to.point == line]
            r["med_dec_over"] = same[same.outcome_name == "Over"].dec.median()
            r["med_dec_under"] = same[same.outcome_name == "Under"].dec.median()
        rows.append(r)
    X = ev.merge(pd.DataFrame(rows), on=["event_id", "lead_h"])
    G = pd.read_parquet(P1 / "games.parquet")
    G["dstr"] = G.date.dt.strftime("%Y-%m-%d")
    M = G.merge(X.rename(columns={"date": "dstr"}), on=["dstr", "home", "away"], how="inner")
    print(f"events with a pre-puck snapshot: {len(ev) + n_far} ; dropped (> 6 h before puck): {n_far}")
    print(f"regular-season games matched to the panel: {len(M)}")
    print(M.groupby("season").agg(games=("game_id", "size"), pin_ml=("pin_p_h", "count"), pin_pl=("pin_p_plfav", "count"),
                                  pin_tot=("pin_p_over", "count"), lead_med=("lead_h", "median")).to_string())
    M.to_parquet(HERE / "games_lines.parquet", index=False)


if __name__ == "__main__":
    main()
