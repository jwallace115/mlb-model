#!/usr/bin/env python3
"""Phase 2: one row per player-game-market-line for 2025-26 NHL props (7 books, ~5 min before puck), graded from
NHL boxscores, with point-in-time player/team features. Seasons 2023-24/2024-25 in the player file are HOLDOUT and
are filtered out here (they are read only by the holdout step, after survivors are frozen)."""
import glob, re, unicodedata
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent / "repo"
UP = Path("/mnt/user-data/uploads/mlb-model/_cowork_patches")
SEASON_ID = 20252026


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s.replace("-", " ")).strip()


def implied(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


def main(season_id=SEASON_ID, props_glob=str(REPO / "data/odds_archive/nhl/props/**/*.parquet"), out="props_rows.parquet"):
    P = pd.read_parquet(UP / "nhl_player_games_2023_2025.parquet")
    B = pd.read_parquet(UP / "nhl_box_games_2023_2025.parquet")
    B = B[B.season == season_id]
    P = P[P.game_id.isin(B.game_id)]
    B["full"] = (B.place + " " + B.common).map(norm)
    # ---- props: per book rows -> keep two-way and one-way separately ----
    pr = pd.concat([pd.read_parquet(f) for f in glob.glob(props_glob, recursive=True)])
    pr = pr[pr.market_key.isin(["player_points", "player_assists", "player_shots_on_goal", "player_goals"])]
    pr = pr[pd.to_datetime(pr.last_update) < pd.to_datetime(pr.commence_time)]
    # ---- event -> NHL game ----
    hb = B[B.side == "home"][["game_id", "full", "start", "abbrev"]].rename(columns={"full": "hfull", "abbrev": "habb"})
    ab = B[B.side == "away"][["game_id", "full", "abbrev"]].rename(columns={"full": "afull", "abbrev": "aabb"})
    gm = hb.merge(ab, on="game_id")
    ev = pr.drop_duplicates("event_id")[["event_id", "home_team", "away_team", "commence_time"]].copy()
    ev["hfull"], ev["afull"] = ev.home_team.map(norm), ev.away_team.map(norm)
    alias = {"utah hockey club": "utah mammoth", "montreal canadiens": "montreal canadiens"}
    ev["hfull"] = ev.hfull.replace(alias); ev["afull"] = ev.afull.replace(alias)
    m = ev.merge(gm, on=["hfull", "afull"], how="left")
    m["dt"] = (pd.to_datetime(m.commence_time) - pd.to_datetime(m.start)).abs().dt.total_seconds() / 3600
    m = m[m.dt <= 12].sort_values("dt").drop_duplicates("event_id")
    unmatched = set(ev.event_id) - set(m.event_id)
    print(f"events {len(ev)}, matched to NHL games {len(m)}, unmatched {len(unmatched)}")
    pr = pr.merge(m[["event_id", "game_id", "habb", "aabb"]], on="event_id")
    # ---- player name -> boxscore player within the game ----
    P["last"] = P.name.map(lambda s: norm(str(s).split(". ", 1)[-1]))
    P["init"] = P.name.map(lambda s: norm(s)[:1])
    key = P.groupby(["game_id", "last", "init"]).pid.agg(["first", "size"]).reset_index()
    key = key[key["size"] == 1].rename(columns={"first": "pid"})
    pl = pr[["game_id", "player_name"]].drop_duplicates()
    nn = pl.player_name.map(norm)
    pl["init"] = nn.str[:1]
    pl["last"] = nn.map(lambda s: s.split(" ", 1)[1] if " " in s else s)
    pl = pl.merge(key[["game_id", "last", "init", "pid"]], on=["game_id", "last", "init"], how="left")
    # fallback: last word of the surname (e.g. "van riemsdyk" vs "riemsdyk")
    miss = pl.pid.isna()
    if miss.any():
        P["last1"] = P["last"].str.split().str[-1]
        k2 = P.groupby(["game_id", "last1", "init"]).pid.agg(["first", "size"]).reset_index()
        k2 = k2[k2["size"] == 1].rename(columns={"first": "pid2"})
        pl.loc[miss, "last1"] = pl.loc[miss, "last"].str.split().str[-1]
        pl = pl.merge(k2[["game_id", "last1", "init", "pid2"]], on=["game_id", "last1", "init"], how="left")
        pl["pid"] = pl.pid.fillna(pl.pid2)
    print(f"player-games {len(pl)}, matched {pl.pid.notna().mean():.3%}")
    pr = pr.merge(pl[["game_id", "player_name", "pid"]], on=["game_id", "player_name"]).dropna(subset=["pid"])
    # ---- consensus per player-game-market-line ----
    pr["two_way"] = pr.under_price.notna() & pr.over_price.notna()
    io, iu = implied(pr.over_price), implied(pr.under_price.fillna(0).where(pr.two_way, np.nan))
    pr["pov"] = np.where(pr.two_way, io / (io + iu), np.nan)
    pr["iov"] = io
    # medians of prices are taken in DECIMAL odds (a median of American odds breaks across +/-100)
    pr["dec_o"] = np.where(pr.over_price > 0, pr.over_price / 100 + 1, 100 / -pr.over_price + 1)
    pr["dec_u"] = np.where(pr.under_price > 0, pr.under_price / 100 + 1, 100 / -pr.under_price + 1)
    g = pr.groupby(["game_id", "pid", "market_key", "line"])
    C = g.agg(n_books=("bookmaker", "nunique"), n_two=("two_way", "sum"), p=("pov", "median"),
              p_min=("pov", "min"), p_max=("pov", "max"), ip=("iov", "median"),
              dec_over=("dec_o", "median"), dec_under=("dec_u", "median"),
              commence=("commence_time", "first"), player=("player_name", "first")).reset_index()
    C["two_way"] = C.n_two >= 1
    # ---- outcomes ----
    stat = {"player_points": "points", "player_assists": "assists", "player_shots_on_goal": "sog", "player_goals": "goals"}
    Pk = P.set_index(["game_id", "pid"])
    vals = []
    for r in C.itertuples(index=False):
        try:
            vals.append(Pk.at[(r.game_id, r.pid), stat[r.market_key]])
        except KeyError:
            vals.append(np.nan)
    C["actual"] = vals
    C = C[C.actual.notna()]
    C["y"] = np.where(C.actual > C.line, 1.0, np.where(C.actual < C.line, 0.0, np.nan))
    # ---- point-in-time player features (prior games this season) ----
    Bd = B[["game_id", "date"]].drop_duplicates()
    P2 = P.merge(Bd, on="game_id").sort_values(["pid", "date", "game_id"])
    P2["toi_m"] = P2.toi.map(lambda s: int(s.split(":")[0]) + int(s.split(":")[1]) / 60 if isinstance(s, str) else np.nan)
    gp = P2.groupby("pid")
    P2["gp_b"] = gp.cumcount()
    for col in ["sog", "points", "assists", "goals", "toi_m"]:
        P2[f"{col}_avg_b"] = gp[col].transform(lambda s: s.shift(1).expanding().mean())
        P2[f"{col}_l5_b"] = gp[col].transform(lambda s: s.shift(1).rolling(5, min_periods=5).mean())
    P2["prev_date"] = gp.date.shift(1)
    P2["b2b"] = (pd.to_datetime(P2.date) - pd.to_datetime(P2.prev_date)).dt.days == 1
    feats = ["game_id", "pid", "pos", "is_home", "team", "gp_b", "b2b", "date"] + [c for c in P2.columns if c.endswith("_b") and c != "gp_b"]
    C = C.merge(P2[feats], on=["game_id", "pid"], how="left")
    # prior over-hit rate at this exact line for this stat
    hist = P2[["pid", "date", "sog", "points", "assists", "goals"]]
    hr = []
    H = {pid: d for pid, d in hist.groupby("pid")}
    for r in C.itertuples(index=False):
        d = H.get(r.pid)
        prior = d[d.date < r.date][stat[r.market_key]] if d is not None else pd.Series(dtype=float)
        hr.append((prior > r.line).mean() if len(prior) >= 10 else np.nan)
    C["hit_rate_b"] = hr
    # opponent shots allowed per game (prior) and game total line
    Tg = P[P.pos != "G"].groupby(["game_id", "team"]).sog.sum().reset_index().merge(Bd, on="game_id")
    opp = B[["game_id", "abbrev", "side"]]
    Tg = Tg.merge(opp.rename(columns={"abbrev": "team"}), on=["game_id", "team"])
    other = opp.rename(columns={"abbrev": "opp", "side": "oside"})
    Tg = Tg.merge(other, on="game_id"); Tg = Tg[Tg.side != Tg.oside]
    Tg = Tg.sort_values(["opp", "date"])  # shots AGAINST the opponent = shots for `team`
    Tg["opp_sa_b"] = Tg.groupby("opp").sog.transform(lambda s: s.shift(1).expanding(min_periods=5).mean())
    C = C.merge(Tg[["game_id", "team", "opp_sa_b"]], on=["game_id", "team"], how="left")
    gt = pd.concat([pd.read_parquet(f) for f in glob.glob(str(REPO / "data/odds_archive/nhl/game_markets/**/*.parquet"), recursive=True)])
    gt = gt[gt.market_key == "totals"].groupby("event_id").line.median().rename("game_total").reset_index()
    C = C.merge(m[["event_id", "game_id"]].merge(gt, on="event_id")[["game_id", "game_total"]], on="game_id", how="left")
    C.to_parquet(HERE / out, index=False)
    print(C.shape); print(C.groupby("market_key").agg(rows=("y", "size"), graded=("y", "count"), two=("two_way", "mean")).to_string())


if __name__ == "__main__":
    main()
