#!/usr/bin/env python3
"""NHL edge hunt — build one row per regular-season game with point-in-time features (2007-08..2025-26).

Inputs (see README §1): raw/nhl.csv, raw/nhl_goalie_starts.csv (public panel, NHL Stats API + SBRO closing odds),
MoneyPuck all_teams gameByGame (repo nhl/cache), repo nhl/nhl_games_canonical.csv (DK totals with prices).
Every form / goalie / xG feature uses ONLY games strictly before the game's date in the same regular season.
Schedule facts (rest, travel, road-trip position, divisional meetings) are known before the season starts.
Output: games.parquet
"""
import math, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "raw"
MP = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/mnt/user-data/uploads/mlb-model/nhl/cache/moneypuck_all_teams.csv")
CANON = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE.parent / "repo/nhl/nhl_games_canonical.csv"
OUT = HERE / "games.parquet"
FIRST_SEASON = 2007

# arena (lat, lon, standard UTC offset). Well-known locations, not fitted to anything.
ARENA = {
    "ANA": (33.81, -117.88, -8), "ARI": (33.53, -112.26, -7), "BOS": (42.37, -71.06, -5), "BUF": (42.88, -78.88, -5),
    "CGY": (51.04, -114.05, -7), "CAR": (35.80, -78.72, -5), "CHI": (41.88, -87.67, -6), "COL": (39.75, -105.01, -7),
    "CBJ": (39.97, -83.01, -5), "DAL": (32.79, -96.81, -6), "DET": (42.34, -83.05, -5), "EDM": (53.55, -113.50, -7),
    "FLA": (26.16, -80.33, -5), "LAK": (34.04, -118.27, -8), "MIN": (44.94, -93.10, -6), "MTL": (45.50, -73.57, -5),
    "NSH": (36.16, -86.78, -6), "NJD": (40.73, -74.17, -5), "NYI": (40.72, -73.59, -5), "NYR": (40.75, -73.99, -5),
    "OTT": (45.30, -75.93, -5), "PHI": (39.90, -75.17, -5), "PIT": (40.44, -79.99, -5), "SJS": (37.33, -121.90, -8),
    "SEA": (47.62, -122.35, -8), "STL": (38.63, -90.20, -6), "TBL": (27.94, -82.45, -5), "TOR": (43.64, -79.38, -5),
    "VAN": (49.28, -123.11, -8), "VGK": (36.10, -115.18, -8), "WSH": (38.90, -77.02, -5), "WPG": (49.89, -97.14, -6),
    "UTA": (40.77, -111.90, -7),
}
ATLANTA = (33.76, -84.39, -5)  # the WPG franchise played in Atlanta through 2010-11


def venue(team, season):
    return ATLANTA if team == "WPG" and season <= 2010 else ARENA[team]


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def implied(a):
    a = float(a)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def main():
    f = pd.read_csv(RAW / "nhl.csv", low_memory=False)
    f = f[(f.season >= FIRST_SEASON) & (f.game_type == "regular")]
    h = f[f.home_away == "H"].set_index("game_id")
    a = f[f.home_away == "A"].set_index("game_id")
    g = pd.DataFrame({
        "date": pd.to_datetime(h["date"]), "season": h["season"], "home": h["team"], "away": a.loc[h.index, "team"],
        "hg": h["score_for"], "ag": h["score_against"], "decided": h["decided_in"],
        "ml_h": h["moneyline"], "ml_a": a.loc[h.index, "moneyline"], "tl_sbr": h["total_line"], "pl_h": h["line"],
    }).reset_index().rename(columns={"game_id": "game_id"})
    g["home_win"] = (g.hg > g.ag).astype(int)
    g["tot"] = g.hg + g.ag
    ok = g.ml_h.notna() & g.ml_a.notna()
    ih = g.loc[ok, "ml_h"].map(implied); ia = g.loc[ok, "ml_a"].map(implied)
    g.loc[ok, "p_h"] = ih / (ih + ia)
    g.loc[ok, "overround"] = ih + ia
    # ---------------- DK totals with prices (canonical) ----------------
    c = pd.read_csv(CANON)[["game_id", "total_line", "over_price", "under_price"]]
    c = c.rename(columns={"total_line": "tl_dk", "over_price": "op_dk", "under_price": "up_dk"})
    good = c.op_dk.between(-200, 180) & c.up_dk.between(-200, 180)
    io = c.op_dk.map(lambda x: implied(x) if pd.notna(x) else np.nan)
    iu = c.up_dk.map(lambda x: implied(x) if pd.notna(x) else np.nan)
    good &= (io + iu).between(1.0, 1.12)
    c.loc[~good, ["tl_dk", "op_dk", "up_dk"]] = np.nan
    c["pover_dk"] = io / (io + iu)
    g = g.merge(c[["game_id", "tl_dk", "op_dk", "up_dk", "pover_dk"]], on="game_id", how="left")
    # total line used per split (pre-registered): SBRO to 2021-22, DK from 2022-23
    g["tl"] = np.where(g.season <= 2021, g.tl_sbr, g.tl_dk)
    g["over"] = np.where(g.tot > g.tl, 1.0, np.where(g.tot < g.tl, 0.0, np.nan))

    # ---------------- long team-game table ----------------
    rows = []
    for side, opp_side in (("home", "away"), ("away", "home")):
        t = pd.DataFrame({"game_id": g.game_id, "date": g.date, "season": g.season, "team": g[side], "opp": g[opp_side],
                          "is_home": side == "home", "gf": g.hg if side == "home" else g.ag,
                          "ga": g.ag if side == "home" else g.hg, "decided": g.decided, "host": g.home})
        rows.append(t)
    L = pd.concat(rows, ignore_index=True).sort_values(["team", "date", "game_id"]).reset_index(drop=True)
    L["win"] = (L.gf > L.ga).astype(int)
    L["pts"] = np.where(L.win == 1, 2, np.where(L.decided.isin(["OT", "SO"]), 1, 0))
    L["margin"] = L.gf - L.ga

    # MoneyPuck (all situations) -> xGF, xGA, SOG by team-game
    mp = pd.read_csv(MP, usecols=["gameId", "home_or_away", "situation", "xGoalsFor", "xGoalsAgainst",
                                  "shotsOnGoalFor", "shotsOnGoalAgainst", "goalsFor", "goalsAgainst", "playoffGame"])
    mp = mp[(mp.situation == "all") & (mp.playoffGame == 0)]
    mp["is_home"] = mp.home_or_away == "HOME"
    mp = mp.rename(columns={"gameId": "game_id", "xGoalsFor": "xgf", "xGoalsAgainst": "xga",
                            "shotsOnGoalFor": "sogf", "shotsOnGoalAgainst": "soga"})
    mp = mp.drop_duplicates(["game_id", "is_home"])
    L = L.merge(mp[["game_id", "is_home", "xgf", "xga", "sogf", "soga"]], on=["game_id", "is_home"], how="left")
    L = L.sort_values(["team", "date", "game_id"]).reset_index(drop=True)

    grp = L.groupby(["team", "season"], sort=False)
    L["gp_b"] = grp.cumcount()
    for col in ["pts", "win", "gf", "ga", "xgf", "xga", "sogf", "soga"]:
        L[f"{col}_cum"] = grp[col].cumsum() - L[col].fillna(0)
    L["xg_n_b"] = grp["xgf"].transform(lambda s: s.notna().cumsum().shift(1).fillna(0))
    L["ptspct_b"] = L.pts_cum / (2 * L.gp_b).replace(0, np.nan)
    L["gdpg_b"] = (L.gf_cum - L.ga_cum) / L.gp_b.replace(0, np.nan)
    L["xgpct_b"] = np.where(L.xg_n_b >= 5, L.xgf_cum / (L.xgf_cum + L.xga_cum), np.nan)
    L["pdo_b"] = np.where(L.xg_n_b >= 5, L.gf_cum / L.sogf_cum + 1 - L.ga_cum / L.soga_cum, np.nan)
    L["luck_b"] = np.where(L.xg_n_b >= 5, ((L.gf_cum - L.ga_cum) - (L.xgf_cum - L.xga_cum)) / L.gp_b, np.nan)
    L["gfpg_b"] = L.gf_cum / L.gp_b.replace(0, np.nan)
    L["gapg_b"] = L.ga_cum / L.gp_b.replace(0, np.nan)
    L["xgfpg_b"] = np.where(L.xg_n_b >= 5, L.xgf_cum / L.xg_n_b.replace(0, np.nan), np.nan)
    L["xgapg_b"] = np.where(L.xg_n_b >= 5, L.xga_cum / L.xg_n_b.replace(0, np.nan), np.nan)
    L["win10_b"] = grp["win"].transform(lambda s: s.shift(1).rolling(10, min_periods=10).mean())
    L["xg10_b"] = grp["xgf"].transform(lambda s: s.shift(1).rolling(10, min_periods=10).sum()) / (
        grp["xgf"].transform(lambda s: s.shift(1).rolling(10, min_periods=10).sum())
        + grp["xga"].transform(lambda s: s.shift(1).rolling(10, min_periods=10).sum()))
    L["last_margin"] = grp["margin"].shift(1)
    L["last_otloss"] = grp.apply(lambda d: ((d.win == 0) & d.decided.isin(["OT", "SO"])).shift(1)).reset_index(level=[0, 1], drop=True)

    def streak(s):
        out, cur = [], 0
        for w in s:
            out.append(cur)
            cur = (cur + 1 if cur >= 0 else 1) if w == 1 else (cur - 1 if cur <= 0 else -1)
        return pd.Series(out, index=s.index)
    L["streak_b"] = grp["win"].transform(streak)

    # schedule: rest, density, travel, road trips (known in advance)
    L["prev_date"] = grp["date"].shift(1)
    L["rest"] = (L.date - L.prev_date).dt.days
    L["b2b"] = L.rest == 1
    L["prev_host"] = grp["host"].shift(1)
    L["prev_season"] = L.season
    dates = L.groupby(["team", "season"])["date"]
    L["g_last3"] = dates.transform(lambda s: pd.Series([((s.iloc[:i] >= d - pd.Timedelta(days=3))).sum() for i, d in enumerate(s)], index=s.index))
    L["g_last7"] = dates.transform(lambda s: pd.Series([((s.iloc[:i] >= d - pd.Timedelta(days=7))).sum() for i, d in enumerate(s)], index=s.index))
    cur = [venue(h_, s_) for h_, s_ in zip(L.host, L.season)]
    prv = [venue(p_, s_) if isinstance(p_, str) else None for p_, s_ in zip(L.prev_host, L.season)]
    L["travel_mi"] = [miles(p, c_) if p else np.nan for p, c_ in zip(prv, cur)]
    L["tz_shift"] = [c_[2] - p[2] if p else np.nan for p, c_ in zip(prv, cur)]   # + = moved east
    L["home_tz_gap"] = [c_[2] - venue(t_, s_)[2] for c_, t_, s_ in zip(cur, L.team, L.season)]  # venue tz minus own tz
    # consecutive away / home run length including this game
    def runlen(s):
        out, n, last = [], 0, None
        for v in s:
            n = n + 1 if v == last else 1
            last = v; out.append(n)
        return pd.Series(out, index=s.index)
    L["run_len"] = grp["is_home"].transform(runlen)
    L["prev_run_len"] = grp["run_len"].shift(1)
    L["prev_is_home"] = grp["is_home"].shift(1)

    # head-to-head within season (schedule count is known in advance; previous result is prior info)
    pair = L.groupby(["season", "team", "opp"])
    L["meetings_season"] = pair["game_id"].transform("size")
    L["lost_prev_meeting"] = pair["win"].shift(1).map({0: True, 1: False})

    # ---------------- goalies ----------------
    gs = pd.read_csv(RAW / "nhl_goalie_starts.csv")
    gs = gs[(gs.started == 1) & (gs.season >= FIRST_SEASON)]
    gs = gs.drop_duplicates(["game_id", "team"])
    gs["date"] = pd.to_datetime(gs.date)
    gs = gs[gs.game_id.isin(g.game_id)].sort_values(["team", "date", "game_id"])
    # starts-to-date per (team, season, goalie), primary = most starts before this game
    rows = []
    for (tm, se), d in gs.groupby(["team", "season"], sort=False):
        cnt = {}
        for r in d.itertuples(index=False):
            prim = max(cnt, key=cnt.get) if cnt else None
            rows.append((r.game_id, tm, r.goalie_id, cnt.get(r.goalie_id, 0), prim))
            cnt[r.goalie_id] = cnt.get(r.goalie_id, 0) + 1
    gp = pd.DataFrame(rows, columns=["game_id", "team", "goalie_id", "g_starts_b", "primary"])
    # goalie season-to-date save % from ALL his prior appearances this season (starts), and B2B
    gs2 = gs.sort_values(["goalie_id", "date"])
    gg = gs2.groupby(["goalie_id", "season"])
    gs2["sa_cum"] = gg["shots_against"].cumsum() - gs2.shots_against
    gs2["sv_cum"] = gg["saves"].cumsum() - gs2.saves
    gs2["n_b"] = gg.cumcount()
    gs2["gsv_b"] = np.where(gs2.n_b >= 5, gs2.sv_cum / gs2.sa_cum.replace(0, np.nan), np.nan)
    gs2["g_prev"] = gg["date"].shift(1)
    gs2["goalie_b2b"] = (gs2.date - gs2.g_prev).dt.days == 1
    gp = gp.merge(gs2[["game_id", "team", "gsv_b", "goalie_b2b"]], on=["game_id", "team"], how="left")
    L = L.merge(gp, on=["game_id", "team"], how="left")
    L["backup"] = (L.goalie_id != L.primary) & L.primary.notna() & (L.gp_b >= 5)
    # league goalie sv% reference per season (prior-only rank would be ideal; use within-season quantiles of
    # the prior-only values themselves, which contain no future information)
    keep = ["game_id", "is_home", "gp_b", "ptspct_b", "gdpg_b", "xgpct_b", "pdo_b", "luck_b", "win10_b", "xg10_b",
            "gfpg_b", "gapg_b", "xgfpg_b", "xgapg_b", "last_margin", "last_otloss", "streak_b", "rest", "b2b", "g_last3", "g_last7", "travel_mi", "tz_shift",
            "home_tz_gap", "run_len", "prev_run_len", "prev_is_home", "meetings_season", "lost_prev_meeting",
            "g_starts_b", "gsv_b", "goalie_b2b", "backup"]
    hL = L[L.is_home][keep].drop(columns="is_home").add_prefix("h_").rename(columns={"h_game_id": "game_id"})
    aL = L[~L.is_home][keep].drop(columns="is_home").add_prefix("a_").rename(columns={"a_game_id": "game_id"})
    g = g.merge(hL, on="game_id", how="left").merge(aL, on="game_id", how="left")
    g["month"] = g.date.dt.month
    g["dow"] = g.date.dt.dayofweek
    g.to_parquet(OUT, index=False)
    print(f"{len(g)} games -> {OUT}")
    print(g.groupby("season").agg(n=("game_id", "size"), ml=("p_h", "count"), tl=("tl", "count"),
                                  dk=("pover_dk", "count"), xg=("h_xgpct_b", "count"), gsv=("h_gsv_b", "count")).to_string())


if __name__ == "__main__":
    main()
