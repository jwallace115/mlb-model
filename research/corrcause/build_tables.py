#!/usr/bin/env python3
"""
CC-1 Item 1: Build point-in-time condition tables for the corrcause screen.

Usage:
    python3 build_tables.py --sport nhl --seasons 2022 2023
    python3 build_tables.py --sport nba --seasons 2022 2023

Outputs (in research/corrcause/data/):
    games_<sport>.parquet   — one row per DEV game with prices + outcomes
    features_<sport>.parquet — every condition input, built point-in-time
    second_pred_<sport>.parquet — post-game Q quantities (separate file)
"""

import argparse
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ============ Odds conversion ============

def american_to_decimal(price):
    if pd.isna(price): return np.nan
    if price >= 100: return 1.0 + price / 100.0
    elif price <= -100: return 1.0 + 100.0 / abs(price)
    return np.nan

def american_to_implied(price):
    if pd.isna(price): return np.nan
    if price >= 100: return 100.0 / (price + 100.0)
    elif price <= -100: return abs(price) / (abs(price) + 100.0)
    return np.nan

def devig_mult(p1, p2):
    if pd.isna(p1) or pd.isna(p2) or (p1 + p2) == 0: return np.nan, np.nan
    total = p1 + p2
    return p1 / total, p2 / total

v_american_to_implied = np.vectorize(american_to_implied)
v_american_to_decimal = np.vectorize(american_to_decimal)

SOFT_BOOKS = [
    "draftkings", "fanduel", "betmgm", "williamhill_us",
    "betrivers", "bovada", "pointsbetus", "unibet_us", "betonlineag"
]

# ============ NHL team mapping ============

_NHL_ABBREV_TO_FULL = {
    "ANA": "Anaheim Ducks", "ARI": "Arizona Coyotes", "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres", "CGY": "Calgary Flames", "CAR": "Carolina Hurricanes",
    "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche", "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars", "DET": "Detroit Red Wings", "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers", "LAK": "Los Angeles Kings", "MIN": "Minnesota Wild",
    "MTL": "Montréal Canadiens", "NSH": "Nashville Predators", "NJD": "New Jersey Devils",
    "NYI": "New York Islanders", "NYR": "New York Rangers", "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers", "PIT": "Pittsburgh Penguins", "SJS": "San Jose Sharks",
    "SEA": "Seattle Kraken", "STL": "St Louis Blues", "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs", "UTA": "Utah Hockey Club",
    "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights",
    "WSH": "Washington Capitals", "WPG": "Winnipeg Jets",
}
_NHL_FULL_TO_ABBREV = {}
for _a, _f in _NHL_ABBREV_TO_FULL.items():
    _NHL_FULL_TO_ABBREV[_f] = _a
    _ascii = unicodedata.normalize("NFD", _f).encode("ascii", "ignore").decode("ascii")
    _NHL_FULL_TO_ABBREV[_ascii] = _a

def nhl_full_to_abbrev(name):
    return _NHL_FULL_TO_ABBREV.get(name, name)

# ============ NBA team mapping ============

_NBA_ABBREV = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}
def nba_full_to_abbrev(name):
    return _NBA_ABBREV.get(name, name)


def _nba_season_str(season_int):
    return f"{season_int}-{str(season_int + 1)[-2:]}"


# ============ Vectorized close/opener extraction ============

def extract_closes(tape, events_df, bookmakers, home_col="home_team"):
    """
    From a pre-tip tape, extract the last snapshot per event/book/market/outcome.
    Returns a wide DataFrame: one row per event, columns for each book's prices.
    """
    # Filter to events of interest
    tape = tape[tape["event_id"].isin(events_df["event_id"])].copy()

    # Sort and take last snapshot per group
    tape = tape.sort_values("snap")
    idx = tape.groupby(["event_id", "bookmaker", "market", "outcome_name"])["snap"].idxmax()
    last = tape.loc[idx].copy()

    # Identify home/away for h2h and spreads using the tape's own home_team
    last["is_home"] = last["outcome_name"] == last[home_col]
    last["is_over"] = last["outcome_name"] == "Over"

    rows = {}
    for eid, grp in last.groupby("event_id"):
        r = {"event_id": eid, "close_snap": grp["snap"].max()}
        ct = events_df.loc[events_df["event_id"] == eid, "ct"]
        if len(ct) > 0:
            r["close_age_min"] = (ct.iloc[0] - r["close_snap"]).total_seconds() / 60.0

        for book in bookmakers:
            bk = grp[grp["bookmaker"] == book]
            prefix = "pin" if book == "pinnacle" else f"soft_{book}"

            # h2h
            h2h = bk[bk["market"] == "h2h"]
            h_h2h = h2h[h2h["is_home"]]
            a_h2h = h2h[~h2h["is_home"]]
            if len(h_h2h) > 0: r[f"{prefix}_close_ml_h"] = h_h2h["price"].iloc[0]
            if len(a_h2h) > 0: r[f"{prefix}_close_ml_a"] = a_h2h["price"].iloc[0]

            # totals
            tot = bk[bk["market"] == "totals"]
            over = tot[tot["is_over"]]
            under = tot[~tot["is_over"]]
            if len(over) > 0:
                r[f"{prefix}_close_total"] = over["point"].iloc[0]
                r[f"{prefix}_close_over_price"] = over["price"].iloc[0]
            if len(under) > 0:
                r[f"{prefix}_close_under_price"] = under["price"].iloc[0]

            # spreads
            spr = bk[bk["market"] == "spreads"]
            h_spr = spr[spr["is_home"]]
            a_spr = spr[~spr["is_home"]]
            if len(h_spr) > 0:
                r[f"{prefix}_close_spread_h"] = h_spr["point"].iloc[0]
                r[f"{prefix}_close_spread_h_price"] = h_spr["price"].iloc[0]
            if len(a_spr) > 0:
                r[f"{prefix}_close_spread_a_price"] = a_spr["price"].iloc[0]

        rows[eid] = r

    return pd.DataFrame(rows.values())


def extract_openers(tape, events_df, home_col="home_team"):
    """Extract Pinnacle opener: first snapshot ≥ 12h before commence_time."""
    pin = tape[(tape["bookmaker"] == "pinnacle") & (tape["event_id"].isin(events_df["event_id"]))].copy()
    # Add ct from events_df if not already present
    if "ct" not in pin.columns:
        pin = pin.merge(events_df[["event_id", "ct"]].drop_duplicates("event_id"), on="event_id", how="left")
    pin["hours_before"] = (pin["ct"] - pin["snap"]).dt.total_seconds() / 3600
    pin = pin[pin["hours_before"] >= 12.0].copy()

    if len(pin) == 0:
        return pd.DataFrame(columns=["event_id"])

    # Earliest per event/market/outcome
    pin = pin.sort_values("snap")
    idx = pin.groupby(["event_id", "market", "outcome_name"])["snap"].idxmin()
    first = pin.loc[idx].copy()
    # home_col should exist in the tape data
    if home_col not in first.columns:
        first = first.merge(
            events_df[["event_id", home_col]].drop_duplicates("event_id"),
            on="event_id", how="left"
        )
    first["is_home"] = first["outcome_name"] == first[home_col]
    first["is_over"] = first["outcome_name"] == "Over"

    rows = {}
    for eid, grp in first.groupby("event_id"):
        r = {"event_id": eid}
        h2h = grp[grp["market"] == "h2h"]
        h = h2h[h2h["is_home"]]
        a = h2h[~h2h["is_home"]]
        if len(h) > 0: r["pin_open_ml_h"] = h["price"].iloc[0]
        if len(a) > 0: r["pin_open_ml_a"] = a["price"].iloc[0]

        tot = grp[grp["market"] == "totals"]
        over = tot[tot["is_over"]]
        under = tot[~tot["is_over"]]
        if len(over) > 0:
            r["pin_open_total"] = over["point"].iloc[0]
            r["pin_open_over_price"] = over["price"].iloc[0]
        if len(under) > 0:
            r["pin_open_under_price"] = under["price"].iloc[0]

        spr = grp[grp["market"] == "spreads"]
        h_spr = spr[spr["is_home"]]
        a_spr = spr[~spr["is_home"]]
        if len(h_spr) > 0:
            r["pin_open_spread_h"] = h_spr["point"].iloc[0]
            r["pin_open_spread_h_price"] = h_spr["price"].iloc[0]
        if len(a_spr) > 0:
            r["pin_open_spread_a_price"] = a_spr["price"].iloc[0]
        rows[eid] = r

    return pd.DataFrame(rows.values())


def add_devig(games, prefix):
    """Add de-vigged fair probabilities for a given prefix (pin_close, pin_open)."""
    ml_h = f"{prefix}_ml_h"
    ml_a = f"{prefix}_ml_a"
    if ml_h in games.columns:
        imp_h = v_american_to_implied(games[ml_h].values)
        imp_a = v_american_to_implied(games[ml_a].values)
        total = imp_h + imp_a
        mask = total > 0
        games[f"{prefix}_fair_h"] = np.where(mask, imp_h / total, np.nan)
        games[f"{prefix}_fair_a"] = np.where(mask, imp_a / total, np.nan)

    op = f"{prefix}_over_price"
    up = f"{prefix}_under_price"
    if op in games.columns:
        imp_o = v_american_to_implied(games[op].values)
        imp_u = v_american_to_implied(games[up].values)
        total = imp_o + imp_u
        mask = total > 0
        games[f"{prefix}_fair_over"] = np.where(mask, imp_o / total, np.nan)
        games[f"{prefix}_fair_under"] = np.where(mask, imp_u / total, np.nan)
    return games


# =====================================================================
#  NHL
# =====================================================================

def build_nhl_games(seasons):
    print("=== Building NHL games table ===")
    t0 = time.time()

    # 1. In-play tape (close source)
    print("  Loading in-play tape...")
    frames = []
    for s in seasons:
        path = Path.home() / f"mlb-model-nhlE/data/odds_archive/nhl/history/inplay/season={s}"
        files = sorted(path.glob("*.parquet"))
        print(f"    season={s}: {len(files)} files")
        frames.extend(pd.read_parquet(f) for f in files)
    inplay = pd.concat(frames, ignore_index=True)
    inplay["snap"] = pd.to_datetime(inplay["snapshot_utc"])
    inplay["ct"] = pd.to_datetime(inplay["commence_time"])
    inplay = inplay[inplay["snap"] < inplay["ct"]].copy()
    print(f"  Pre-tip rows: {len(inplay):,} ({time.time()-t0:.0f}s)")

    # 2. Lines_all (for openers — has earlier snapshots)
    lines = pd.read_parquet(
        Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet"
    )
    lines["snap"] = pd.to_datetime(lines["snapshot_utc"])
    lines["ct"] = pd.to_datetime(lines["commence_time"])
    lines = lines[lines["snap"] < lines["ct"]].copy()

    # 3. SBRO outcomes
    sbro = pd.read_parquet(
        Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet"
    )
    sbro["date_dt"] = pd.to_datetime(sbro["date"])

    # 4. Event list from in-play tape
    events = inplay[["event_id", "ct", "home_team", "away_team"]].drop_duplicates("event_id")
    events["season"] = events["ct"].apply(lambda x: x.year if x.month >= 10 else x.year - 1)
    events = events[events["season"].isin(seasons)].copy()
    print(f"  Events: {len(events)}")

    # 5. Extract closes (Pinnacle + all soft books)
    print("  Extracting closes...")
    all_books = ["pinnacle"] + SOFT_BOOKS
    close_df = extract_closes(inplay, events, all_books)
    close_df = close_df.rename(columns={"close_snap": "close_snap", "close_age_min": "close_age_min"})
    # Rename pin columns to match convention
    close_df["close_source"] = "inplay_tape"
    print(f"  Closes extracted: {len(close_df)} ({time.time()-t0:.0f}s)")

    # 6. Extract openers from combined lines_all + in-play tape
    print("  Extracting openers...")
    combined_for_opener = pd.concat([
        lines[["event_id", "snap", "ct", "bookmaker", "market", "outcome_name", "point", "price",
               "home_team", "away_team"]],
        inplay[["event_id", "snap", "ct", "bookmaker", "market", "outcome_name", "point", "price",
                "home_team", "away_team"]],
    ], ignore_index=True)
    opener_df = extract_openers(combined_for_opener, events)
    print(f"  Openers extracted: {len(opener_df)} ({time.time()-t0:.0f}s)")

    # 7. Match outcomes from SBRO
    print("  Matching outcomes...")
    events["h_abbrev"] = events["home_team"].map(nhl_full_to_abbrev)
    events["a_abbrev"] = events["away_team"].map(nhl_full_to_abbrev)
    # Convert commence_time to Eastern date for matching
    events["game_date_et"] = events["ct"].dt.tz_convert("US/Eastern").dt.date

    sbro_dev = sbro[sbro["season"].isin(seasons)].copy()
    sbro_dev["game_date"] = sbro_dev["date_dt"].dt.date

    # Merge on date + home + away abbreviation
    outcomes = events[["event_id", "game_date_et", "h_abbrev", "a_abbrev"]].merge(
        sbro_dev[["game_id", "game_date", "home", "away", "hg", "ag", "home_win", "decided"]],
        left_on=["game_date_et", "h_abbrev", "a_abbrev"],
        right_on=["game_date", "home", "away"],
        how="left"
    )[["event_id", "game_id", "hg", "ag", "home_win", "decided"]]
    outcomes = outcomes.rename(columns={"hg": "home_goals", "ag": "away_goals"})
    outcomes["total_goals"] = outcomes["home_goals"] + outcomes["away_goals"]
    matched = outcomes["game_id"].notna().sum()
    print(f"  Matched: {matched}/{len(events)}")

    # 8. Merge all
    games = events[["event_id", "ct", "home_team", "away_team", "season",
                     "h_abbrev", "a_abbrev"]].copy()
    games = games.rename(columns={"ct": "commence_time"})
    games = games.merge(close_df, on="event_id", how="left")
    games = games.merge(opener_df, on="event_id", how="left")
    games = games.merge(outcomes, on="event_id", how="left")

    # De-vig
    games = add_devig(games, "pin_close")
    games = add_devig(games, "pin_open")

    # Totals grading (exclude SO goal per registry)
    games["total_for_totals"] = games["total_goals"].copy()
    so_mask = games["decided"] == "SO"
    games.loc[so_mask, "total_for_totals"] = games.loc[so_mask, "total_goals"] - 1
    games["over"] = np.where(
        games["total_for_totals"] > games["pin_close_total"], 1.0,
        np.where(games["total_for_totals"] < games["pin_close_total"], 0.0, np.nan)
    )

    out = DATA_DIR / "games_nhl.parquet"
    games.to_parquet(out, index=False)
    print(f"  Wrote {out} ({len(games)} rows, {time.time()-t0:.0f}s)")
    return games


def build_nhl_features(seasons, games):
    print("\n=== Building NHL features ===")
    t0 = time.time()

    sbro = pd.read_parquet(
        Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet"
    )
    sbro["date_dt"] = pd.to_datetime(sbro["date"])
    sbro = sbro.sort_values("date_dt")

    gs = pd.read_csv(
        Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/nhl_goalie_starts.csv"
    )
    gs["date_dt"] = pd.to_datetime(gs["date"])

    gr = pd.read_parquet(Path.home() / "mlb-model-nhlD/nhl/data/sim/ratings/goalie_ratings.parquet")
    gr["date_dt"] = pd.to_datetime(gr["date"])

    features = []
    for _, g in games.iterrows():
        eid = g["event_id"]
        gid = g.get("game_id")
        row = {"event_id": eid}

        if pd.isna(gid):
            features.append(row)
            continue

        gid = int(gid)
        game_date = pd.to_datetime(g["commence_time"]).tz_convert("US/Eastern").date()
        season = g["season"]
        h_abbrev = g["h_abbrev"]
        a_abbrev = g["a_abbrev"]

        # Prior games in same season, strictly before game_date
        season_prior = sbro[(sbro["season"] == season) & (sbro["date_dt"].dt.date < game_date)]

        for side, abbrev in [("home", h_abbrev), ("away", a_abbrev)]:
            team_prior = season_prior[
                (season_prior["home"] == abbrev) | (season_prior["away"] == abbrev)
            ].sort_values("date_dt")

            if len(team_prior) > 0:
                last = team_prior.iloc[-1]
                last_date = last["date_dt"].date()
                rest = (game_date - last_date).days
                row[f"{side}_rest_days"] = rest
                row[f"{side}_b2b"] = 1 if rest == 1 else 0
                row[f"{side}_last_decided"] = last["decided"]
                row[f"{side}_last_game_ot"] = 1 if last["decided"] in ("OT", "SO") else 0

                # Games in last 4 days
                recent4 = team_prior[
                    team_prior["date_dt"].dt.date >= (pd.Timestamp(game_date) - pd.Timedelta(days=3)).date()
                ]
                row[f"{side}_games_in_4"] = len(recent4)

                # Points %
                pts = 0
                for _, pg in team_prior.iterrows():
                    is_h = pg["home"] == abbrev
                    won = (is_h and pg["home_win"]) or (not is_h and not pg["home_win"])
                    if won: pts += 2
                    elif pg["decided"] in ("OT", "SO"): pts += 1
                row[f"{side}_pts_pct"] = pts / (2 * len(team_prior))
                row[f"{side}_gp"] = len(team_prior)

                # Goal diff per game (last 10)
                last10 = team_prior.tail(10)
                gd = sum(
                    (pg["hg"] - pg["ag"]) if pg["home"] == abbrev else (pg["ag"] - pg["hg"])
                    for _, pg in last10.iterrows()
                )
                row[f"{side}_gd_per_game_10"] = gd / len(last10)

                # Streak
                streak = 0
                for _, pg in team_prior.iloc[::-1].iterrows():
                    won = (pg["home"] == abbrev and pg["home_win"]) or \
                          (pg["away"] == abbrev and not pg["home_win"])
                    if streak == 0:
                        streak = 1 if won else -1
                    elif (streak > 0 and won) or (streak < 0 and not won):
                        streak += 1 if streak > 0 else -1
                    else:
                        break
                row[f"{side}_streak"] = streak

            # Goalie: backup detection (A-01)
            team_starts = gs[
                (gs["team"] == abbrev) & (gs["season"] == season) &
                (gs["date_dt"].dt.date < game_date) & (gs["started"] == 1)
            ]
            n_starts = len(team_starts)
            row[f"{side}_team_starts"] = n_starts
            if n_starts >= 10:
                primary_id = team_starts.groupby("goalie_id").size().idxmax()
                primary_share = team_starts.groupby("goalie_id").size().max() / n_starts
                row[f"{side}_primary_goalie"] = primary_id
                row[f"{side}_primary_share"] = primary_share

                game_starters = gs[
                    (gs["game_id"] == gid) & (gs["team"] == abbrev) & (gs["started"] == 1)
                ]
                if len(game_starters) > 0:
                    starter_id = game_starters.iloc[0]["goalie_id"]
                    row[f"{side}_starter"] = starter_id
                    row[f"{side}_is_backup"] = 1 if (starter_id != primary_id and primary_share >= 0.6) else 0

                    # GSAx
                    for gid_check, label in [(starter_id, "starter"), (primary_id, "primary")]:
                        rating = gr[
                            (gr["goalie_id"] == gid_check) & (gr["season"] == season) &
                            (gr["date_dt"].dt.date < game_date)
                        ]
                        if len(rating) > 0:
                            row[f"{side}_{label}_gsax"] = rating.iloc[-1]["gsax_per_att_rating"]

        # Market behaviour features (from games table directly)
        if not pd.isna(g.get("pin_close_ml_h")) and not pd.isna(g.get("pin_open_ml_h")):
            c = american_to_implied(g["pin_close_ml_h"])
            o = american_to_implied(g["pin_open_ml_h"])
            if not pd.isna(c) and not pd.isna(o):
                row["pin_ml_move_h"] = (c - o) * 100

        if not pd.isna(g.get("pin_close_total")) and not pd.isna(g.get("pin_open_total")):
            row["pin_total_move"] = g["pin_close_total"] - g["pin_open_total"]

        row["pin_close_total"] = g.get("pin_close_total")
        row["pin_open_total"] = g.get("pin_open_total")
        row["pin_close_fair_h"] = g.get("pin_close_fair_h")
        row["pin_close_fair_a"] = g.get("pin_close_fair_a")

        features.append(row)

    df = pd.DataFrame(features)
    out = DATA_DIR / "features_nhl.parquet"
    df.to_parquet(out, index=False)
    print(f"  Wrote {out} ({len(df)} rows, {time.time()-t0:.0f}s)")
    return df


def build_nhl_second_pred(seasons, games):
    print("\n=== Building NHL second predictions ===")
    t0 = time.time()

    shots_all = []
    state_all = []
    for s in seasons:
        base = Path.home() / f"mlb-model-nhlsim1/nhl/data/sim/events/season={s}"
        shots_all.append(pd.read_parquet(base / "shots.parquet"))
        state_all.append(pd.read_parquet(base / "state_time.parquet"))
    shots = pd.concat(shots_all, ignore_index=True)
    state = pd.concat(state_all, ignore_index=True)

    sbro = pd.read_parquet(
        Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet"
    )

    rows = []
    for _, g in games.iterrows():
        eid = g["event_id"]
        gid = g.get("game_id")
        row = {"event_id": eid}

        if pd.isna(gid):
            rows.append(row)
            continue
        gid_str = str(int(gid))
        h_abbrev = g["h_abbrev"]

        gs = shots[shots["game_id"] == gid_str]
        gst = state[state["game_id"] == gid_str]

        if len(gs) == 0 or len(gst) == 0:
            rows.append(row)
            continue

        # 5v5 state time
        fv5 = gst[
            (gst["home_skaters"] == 5) & (gst["away_skaters"] == 5) &
            (gst["home_goalie"] == 1) & (gst["away_goalie"] == 1)
        ]
        fv5_sec = fv5["duration"].sum()

        if fv5_sec > 0:
            # 5v5 shots
            fv5_shots = gs[gs["strength"].str.contains("5v5|Ev", case=False, na=False)]
            n_5v5 = len(fv5_shots)
            row["fivev5_attempts_per60"] = n_5v5 * 3600 / fv5_sec

            # P1 5v5 attempt share
            p1_state = fv5[fv5["period"] == 1]
            p1_sec = p1_state["duration"].sum()
            if p1_sec > 0:
                p1_shots = fv5_shots[fv5_shots["period"] == 1]
                home_p1 = len(p1_shots[p1_shots["shooting_team"] == "home"])
                total_p1 = len(p1_shots)
                row["p1_5v5_home_share"] = home_p1 / total_p1 if total_p1 > 0 else np.nan

            # Home 5v5 attempt share (full game)
            home_5v5 = len(fv5_shots[fv5_shots["shooting_team"] == "home"])
            row["fivev5_home_attempt_share"] = home_5v5 / n_5v5 if n_5v5 > 0 else np.nan

        # All-situation shooting %
        total_shots = len(gs)
        if total_shots > 0:
            goals = gs[gs["is_goal"] == True]
            row["all_sit_sh_pct"] = len(goals) / total_shots

        rows.append(row)

    df = pd.DataFrame(rows)
    out = DATA_DIR / "second_pred_nhl.parquet"
    df.to_parquet(out, index=False)
    print(f"  Wrote {out} ({len(df)} rows, {time.time()-t0:.0f}s)")
    return df


# =====================================================================
#  NBA
# =====================================================================

def build_nba_games(seasons):
    print("\n=== Building NBA games table ===")
    t0 = time.time()

    # Lines hourly
    print("  Loading lines_hourly...")
    frames = []
    for s in seasons:
        path = Path.home() / f"mlb-model/data/odds_archive/nba/history/lines_hourly/season={s}"
        files = sorted(path.glob("*.parquet"))
        print(f"    season={s}: {len(files)} files")
        frames.extend(pd.read_parquet(f) for f in files)
    lh = pd.concat(frames, ignore_index=True)
    lh["snap"] = pd.to_datetime(lh["snapshot_utc"])
    lh["ct"] = pd.to_datetime(lh["commence_time"])
    lh = lh[lh["snap"] < lh["ct"]].copy()
    print(f"  Pre-tip rows: {len(lh):,} ({time.time()-t0:.0f}s)")

    # In-play tape for season=2023 only
    ip = pd.DataFrame()
    ip_path = Path.home() / "mlb-model/data/odds_archive/nba/history/inplay/season=2023"
    if ip_path.exists():
        print("  Loading in-play tape (season=2023)...")
        ip_files = sorted(ip_path.glob("*.parquet"))
        if ip_files:
            ip = pd.concat([pd.read_parquet(f) for f in ip_files], ignore_index=True)
            ip["snap"] = pd.to_datetime(ip["snapshot_utc"])
            ip["ct"] = pd.to_datetime(ip["commence_time"])
            ip = ip[ip["snap"] < ip["ct"]].copy()
            print(f"    Pre-tip rows: {len(ip):,}")

    # Event list
    events = lh[["event_id", "ct", "home_team", "away_team"]].drop_duplicates("event_id")
    events["season_int"] = events["ct"].apply(lambda x: x.year if x.month >= 10 else x.year - 1)
    events = events[events["season_int"].isin(seasons)].copy()
    print(f"  Events: {len(events)}")

    # Use lines_hourly for all NBA closes (the in-play tape for NBA has sparse
    # pre-tip snapshots and worse close timing than lines_hourly's hourly snapshots)
    print("  Extracting closes from lines_hourly...")
    all_books = ["pinnacle"] + SOFT_BOOKS
    close_df = extract_closes(lh, events, all_books)
    close_df["close_source"] = "lines_hourly"
    print(f"  Closes: {len(close_df)} ({time.time()-t0:.0f}s)")

    # Openers from lines_hourly
    print("  Extracting openers...")
    opener_df = extract_openers(lh, events)
    print(f"  Openers: {len(opener_df)}")

    # Outcomes
    print("  Matching outcomes...")
    nba_games = pd.read_parquet(Path.home() / "mlb-model/nba/data/games.parquet")

    events["game_date"] = events["ct"].dt.tz_convert("US/Eastern").dt.date.astype(str)
    events["season_str"] = events["season_int"].apply(_nba_season_str)
    events["h_abbrev"] = events["home_team"].map(nba_full_to_abbrev)
    events["a_abbrev"] = events["away_team"].map(nba_full_to_abbrev)

    nba_games_m = nba_games.copy()
    nba_games_m["date"] = nba_games_m["date"].astype(str)

    outcomes = events[["event_id", "game_date", "h_abbrev", "a_abbrev", "season_str"]].merge(
        nba_games_m[["game_id", "date", "home_team", "away_team", "home_score", "away_score",
                      "actual_total", "season"]].rename(columns={"game_id": "nba_game_id"}),
        left_on=["game_date", "h_abbrev", "a_abbrev", "season_str"],
        right_on=["date", "home_team", "away_team", "season"],
        how="left"
    )[["event_id", "nba_game_id", "home_score", "away_score", "actual_total"]]

    outcomes["home_win"] = outcomes["home_score"] > outcomes["away_score"]
    outcomes["margin"] = outcomes["home_score"] - outcomes["away_score"]
    matched = outcomes["nba_game_id"].notna().sum()
    print(f"  Matched: {matched}/{len(events)}")

    # Merge
    games = events[["event_id", "ct", "home_team", "away_team", "season_int"]].copy()
    games = games.rename(columns={"ct": "commence_time", "season_int": "season"})
    games = games.merge(close_df, on="event_id", how="left")
    games = games.merge(opener_df, on="event_id", how="left")
    games = games.merge(outcomes, on="event_id", how="left")

    games = add_devig(games, "pin_close")
    games = add_devig(games, "pin_open")

    # Totals grade
    if "actual_total" in games.columns and "pin_close_total" in games.columns:
        games["over"] = np.where(
            games["actual_total"] > games["pin_close_total"], 1.0,
            np.where(games["actual_total"] < games["pin_close_total"], 0.0, np.nan)
        )

    # ATS grade
    if "margin" in games.columns and "pin_close_spread_h" in games.columns:
        adjusted = games["margin"] + games["pin_close_spread_h"]
        games["home_covers"] = np.where(adjusted > 0, 1.0, np.where(adjusted < 0, 0.0, np.nan))

    out = DATA_DIR / "games_nba.parquet"
    games.to_parquet(out, index=False)
    print(f"  Wrote {out} ({len(games)} rows, {time.time()-t0:.0f}s)")
    return games


def build_nba_features(seasons, games):
    print("\n=== Building NBA features ===")
    t0 = time.time()

    box = pd.read_parquet(Path.home() / "mlb-model/nba/data/box_stats.parquet")
    box["date_dt"] = pd.to_datetime(box["date"])
    sched = pd.read_parquet(Path.home() / "mlb-model/nba/data/nba_schedule_features.parquet")
    sched["game_date_dt"] = pd.to_datetime(sched["game_date"])

    features = []
    for _, g in games.iterrows():
        eid = g["event_id"]
        row = {"event_id": eid}
        ct = pd.to_datetime(g["commence_time"])
        game_date = ct.tz_convert("US/Eastern").date()
        ht_full = g["home_team"]
        at_full = g["away_team"]
        ht = nba_full_to_abbrev(ht_full)
        at = nba_full_to_abbrev(at_full)
        season_str = _nba_season_str(g["season"])

        # Schedule features
        sf_match = sched[
            (sched["game_date_dt"].dt.date == game_date) & (sched["home_team"] == ht)
        ]
        if len(sf_match) > 0:
            sf = sf_match.iloc[0]
            for col in ["home_rest_days", "away_rest_days", "home_games_last_4",
                        "away_games_last_4", "home_travel_miles_est", "away_travel_miles_est"]:
                if col in sf.index:
                    row[col] = sf[col]

        row["home_b2b"] = 1 if row.get("home_rest_days") == 0 else 0
        row["away_b2b"] = 1 if row.get("away_rest_days") == 0 else 0
        row["home_3in4"] = 1 if row.get("home_games_last_4", 0) >= 3 else 0
        row["away_3in4"] = 1 if row.get("away_games_last_4", 0) >= 3 else 0

        # Box stat priors
        for side, team in [("home", ht), ("away", at)]:
            tb = box[
                (box["team"] == team) & (box["season"] == season_str) &
                (box["date_dt"].dt.date < game_date)
            ].sort_values("date_dt")
            if len(tb) > 0:
                last10 = tb.tail(10)
                row[f"{side}_poss_avg10"] = last10["poss"].mean()
                row[f"{side}_pace_avg10"] = last10["pace"].mean()
                row[f"{side}_pts_avg10"] = last10["pts"].mean()

                # Last game
                last = tb.iloc[-1]
                row[f"{side}_last_margin"] = last["pts"] - last["opp_pts"]
                row[f"{side}_last_ot"] = 1 if last["went_ot"] else 0

                # Streak
                streak = 0
                for _, b in tb.iloc[::-1].iterrows():
                    won = b["pts"] > b["opp_pts"]
                    if streak == 0:
                        streak = 1 if won else -1
                    elif (streak > 0 and won) or (streak < 0 and not won):
                        streak += 1 if streak > 0 else -1
                    else:
                        break
                row[f"{side}_streak"] = streak

        # Market moves
        if not pd.isna(g.get("pin_close_total")) and not pd.isna(g.get("pin_open_total")):
            row["pin_total_move"] = g["pin_close_total"] - g["pin_open_total"]
        if not pd.isna(g.get("pin_close_spread_h")) and not pd.isna(g.get("pin_open_spread_h")):
            row["pin_spread_move_h"] = g["pin_close_spread_h"] - g["pin_open_spread_h"]
        if not pd.isna(g.get("pin_close_ml_h")) and not pd.isna(g.get("pin_open_ml_h")):
            c = american_to_implied(g["pin_close_ml_h"])
            o = american_to_implied(g["pin_open_ml_h"])
            if not pd.isna(c) and not pd.isna(o):
                row["pin_ml_move_h"] = (c - o) * 100

        row["pin_close_total"] = g.get("pin_close_total")
        row["pin_open_total"] = g.get("pin_open_total")
        row["pin_close_fair_h"] = g.get("pin_close_fair_h")
        row["pin_close_fair_a"] = g.get("pin_close_fair_a")
        row["month"] = ct.month
        row["weekday"] = ct.weekday()

        features.append(row)

    df = pd.DataFrame(features)
    out = DATA_DIR / "features_nba.parquet"
    df.to_parquet(out, index=False)
    print(f"  Wrote {out} ({len(df)} rows, {time.time()-t0:.0f}s)")
    return df


def build_nba_second_pred(seasons, games):
    print("\n=== Building NBA second predictions ===")
    t0 = time.time()

    box = pd.read_parquet(Path.home() / "mlb-model/nba/data/box_stats.parquet")
    box["date_dt"] = pd.to_datetime(box["date"])
    plogs = pd.read_parquet(Path.home() / "mlb-model/nba/model_c/player_game_logs.parquet")
    plogs["GAME_DATE_DT"] = pd.to_datetime(plogs["GAME_DATE"])

    rows = []
    for _, g in games.iterrows():
        eid = g["event_id"]
        row = {"event_id": eid}
        if pd.isna(g.get("nba_game_id")):
            rows.append(row)
            continue

        game_date = pd.to_datetime(g["commence_time"]).tz_convert("US/Eastern").date()
        ht = nba_full_to_abbrev(g["home_team"])
        at = nba_full_to_abbrev(g["away_team"])
        season_str = _nba_season_str(g["season"])

        # Box stats
        gb = box[
            (box["date_dt"].dt.date == game_date) &
            ((box["team"] == ht) | (box["team"] == at)) &
            (box["season"] == season_str)
        ]
        h_box = gb[gb["team"] == ht]
        a_box = gb[gb["team"] == at]
        if len(h_box) > 0: row["home_poss"] = h_box.iloc[0]["poss"]
        if len(a_box) > 0: row["away_poss"] = a_box.iloc[0]["poss"]
        if "home_poss" in row and "away_poss" in row:
            row["total_poss"] = row["home_poss"] + row["away_poss"]

        # Top-5 minutes
        for side, team in [("home", ht), ("away", at)]:
            tp = plogs[
                (plogs["GAME_DATE_DT"].dt.date == game_date) &
                (plogs["TEAM_ABBREVIATION"] == team)
            ]
            if len(tp) > 0:
                top5 = tp.nlargest(5, "MIN")
                row[f"{side}_top5_min_avg"] = top5["MIN"].mean()

        rows.append(row)

    df = pd.DataFrame(rows)
    out = DATA_DIR / "second_pred_nba.parquet"
    df.to_parquet(out, index=False)
    print(f"  Wrote {out} ({len(df)} rows, {time.time()-t0:.0f}s)")
    return df


# =====================================================================
#  MAIN
# =====================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", required=True, choices=["nhl", "nba"])
    parser.add_argument("--seasons", nargs="+", type=int, required=True)
    args = parser.parse_args()

    print(f"Sport: {args.sport}, Seasons: {args.seasons}")
    print(f"Python: {sys.executable}")

    if args.sport == "nhl":
        games = build_nhl_games(args.seasons)
        build_nhl_features(args.seasons, games)
        build_nhl_second_pred(args.seasons, games)
    else:
        games = build_nba_games(args.seasons)
        build_nba_features(args.seasons, games)
        build_nba_second_pred(args.seasons, games)

    print("\nDone.")

if __name__ == "__main__":
    main()
