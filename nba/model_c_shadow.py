#!/usr/bin/env python3
"""
NBA Model C — Player Props Shadow System
Automated daily collection, projection, grading, and archive.

Usage:
  python3 nba/model_c_shadow.py --collect          # morning: pull lines + project + shadow card
  python3 nba/model_c_shadow.py --refresh           # midday/pre-tip: re-pull lines snapshot
  python3 nba/model_c_shadow.py --grade             # next morning: grade yesterday's plays
  python3 nba/model_c_shadow.py --summary           # print summary (RS and PO)
  python3 nba/model_c_shadow.py --collect --date 2026-03-20   # specific date
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Paths ──
_SCRIPT_DIR = Path(__file__).resolve().parent  # .../nba/
PROJECT_ROOT = _SCRIPT_DIR.parent              # .../mlb-model/
MODEL_C_DIR = _SCRIPT_DIR / "model_c"          # .../nba/model_c/
SHADOW_DIR = MODEL_C_DIR / "shadow"
RAW_DIR = SHADOW_DIR / "raw"
CARDS_DIR = SHADOW_DIR / "cards"
REPORTS_DIR = SHADOW_DIR / "reports"
DATA_DIR = _SCRIPT_DIR / "data"

for d in [SHADOW_DIR, RAW_DIR, CARDS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Config ──
API_KEY = os.getenv("ODDS_API_KEY", "")
PROP_MARKETS = ["player_points", "player_rebounds", "player_assists",
                "player_points_rebounds_assists"]
PROP_FAMILY_MAP = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_points_rebounds_assists": "pra",
}
BOOKS_PRIORITY = ["draftkings", "fanduel", "betmgm", "williamhill_us",
                   "betrivers", "pointsbetus", "bovada", "superbook"]

# Confidence tiers by edge size
EDGE_THRESHOLDS = {"HIGH": 3.0, "MEDIUM": 1.5, "LOW": 0.5}

# Playoff detection: NBA playoffs typically start mid-April
# We'll use the schedule to detect, but hardcode a fallback
PLAYOFF_START_FALLBACK = "2026-04-19"

# Shadow archive files
RS_SHADOW_FILE = SHADOW_DIR / "model_c_rs_shadow.parquet"
PO_SHADOW_FILE = SHADOW_DIR / "model_c_po_shadow.parquet"
RAW_ARCHIVE_FILE = RAW_DIR / "prop_lines_raw.parquet"
LINES_ARCHIVE_FILE = SHADOW_DIR / "prop_lines_archive.parquet"


# ══════════════════════════════════════════════════════════════
# SEASON PHASE DETECTION
# ══════════════════════════════════════════════════════════════

def detect_season_phase(date_str):
    """Detect RS or PO based on date and NBA schedule."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    # Check if we have playoff game IDs (start with 004)
    # Fallback: use date threshold
    try:
        from nba_api.stats.endpoints import leaguegamelog
        # Check if any playoff games exist for this season
        lg = leaguegamelog.LeagueGameLog(
            season="2025-26",
            season_type_all_star="Playoffs",
        )
        po_df = lg.get_data_frames()[0]
        if len(po_df) > 0:
            first_po = pd.to_datetime(po_df["GAME_DATE"]).min()
            if dt >= first_po.to_pydatetime():
                return "PO"
    except Exception:
        pass

    # Fallback date check
    if dt >= datetime.strptime(PLAYOFF_START_FALLBACK, "%Y-%m-%d"):
        return "PO"

    return "RS"


# ══════════════════════════════════════════════════════════════
# PHASE A — COLLECTION
# ══════════════════════════════════════════════════════════════

def fetch_events():
    """Fetch today's NBA events."""
    r = requests.get(
        "https://api.the-odds-api.com/v4/sports/basketball_nba/events",
        params={"apiKey": API_KEY}
    )
    if r.status_code != 200:
        print(f"  ERROR fetching events: {r.status_code}")
        return []
    return r.json()


def fetch_player_props(event_id):
    """Fetch player props for a single event."""
    r = requests.get(
        f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{event_id}/odds",
        params={
            "apiKey": API_KEY,
            "regions": "us",
            "markets": ",".join(PROP_MARKETS),
            "oddsFormat": "american",
        }
    )
    remaining = r.headers.get("x-requests-remaining", "?")
    if r.status_code != 200:
        print(f"  Event {event_id}: status {r.status_code}")
        return None, remaining
    return r.json(), remaining


def collect_lines(target_date):
    """Pull all player prop lines for today's games."""
    now = datetime.now()
    ts = now.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"Collecting player prop lines — {ts}")

    events = fetch_events()
    if not events:
        print("  No NBA events found.")
        return pd.DataFrame()

    # Filter to today's events (by target_date in UTC, games can span midnight)
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    today_events = []
    for e in events:
        commence = datetime.strptime(e["commence_time"][:19], "%Y-%m-%dT%H:%M:%S")
        # Include games commencing today (UTC) or yesterday evening (for ET games)
        game_date_et = commence - timedelta(hours=5)  # rough ET conversion
        if game_date_et.date() == target_dt.date():
            today_events.append(e)

    if not today_events:
        # If no exact date match, include all upcoming within 24h
        for e in events:
            commence = datetime.strptime(e["commence_time"][:19], "%Y-%m-%dT%H:%M:%S")
            if abs((commence - target_dt).total_seconds()) < 86400:
                today_events.append(e)

    print(f"  Events for {target_date}: {len(today_events)}")

    all_rows = []
    credits_remaining = "?"

    for i, event in enumerate(today_events):
        eid = event["id"]
        home = event["home_team"]
        away = event["away_team"]
        commence = event["commence_time"]

        time.sleep(0.6)  # rate limit
        data, remaining = fetch_player_props(eid)
        credits_remaining = remaining

        if not data:
            print(f"  SKIP {away} @ {home}: no data")
            continue

        n_props = 0
        for bk in data.get("bookmakers", []):
            book_key = bk["key"]
            for mkt in bk.get("markets", []):
                market_key = mkt["key"]
                prop_family = PROP_FAMILY_MAP.get(market_key, market_key)

                # Group outcomes by player (Over/Under pairs)
                player_lines = {}
                for outcome in mkt.get("outcomes", []):
                    player = outcome.get("description", "Unknown")
                    direction = outcome["name"]  # "Over" or "Under"
                    point = outcome.get("point")
                    price = outcome.get("price")

                    if player not in player_lines:
                        player_lines[player] = {}
                    player_lines[player][direction] = {"point": point, "price": price}

                for player, sides in player_lines.items():
                    over = sides.get("Over", {})
                    under = sides.get("Under", {})
                    line = over.get("point") or under.get("point")
                    if line is None:
                        continue

                    all_rows.append({
                        "date": target_date,
                        "collection_timestamp": ts,
                        "event_id": eid,
                        "home_team": home,
                        "away_team": away,
                        "commence_time": commence,
                        "player_name": player,
                        "prop_type": prop_family,
                        "sportsbook": book_key,
                        "line": float(line),
                        "over_odds": over.get("price"),
                        "under_odds": under.get("price"),
                        "snapshot_type": "collect",
                    })
                    n_props += 1

        print(f"  {away} @ {home}: {n_props} prop lines")

    print(f"  Total lines: {len(all_rows)}, credits remaining: {credits_remaining}")

    df = pd.DataFrame(all_rows)
    if len(df) == 0:
        return df

    # Mark first_seen
    df["first_seen_flag"] = True
    df["latest_seen_flag"] = True

    # Save raw snapshot
    raw_file = RAW_DIR / f"props_{target_date}_{now.strftime('%H%M')}.parquet"
    df.to_parquet(raw_file, index=False)
    print(f"  Raw snapshot: {raw_file.name}")

    # Append to raw archive
    _append_to_archive(df, RAW_ARCHIVE_FILE)

    return df


def refresh_lines(target_date):
    """Re-pull lines for a midday/pre-tip snapshot."""
    now = datetime.now()
    ts = now.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"Refreshing player prop lines — {ts}")

    # Same collection logic but mark as refresh
    events = fetch_events()
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")

    today_events = []
    for e in events:
        commence = datetime.strptime(e["commence_time"][:19], "%Y-%m-%dT%H:%M:%S")
        game_date_et = commence - timedelta(hours=5)
        if game_date_et.date() == target_dt.date():
            today_events.append(e)
    if not today_events:
        for e in events:
            commence = datetime.strptime(e["commence_time"][:19], "%Y-%m-%dT%H:%M:%S")
            if abs((commence - target_dt).total_seconds()) < 86400:
                today_events.append(e)

    print(f"  Events for refresh: {len(today_events)}")

    all_rows = []
    for event in today_events:
        eid = event["id"]
        home = event["home_team"]
        away = event["away_team"]
        commence = event["commence_time"]

        time.sleep(0.6)
        data, _ = fetch_player_props(eid)
        if not data:
            continue

        for bk in data.get("bookmakers", []):
            book_key = bk["key"]
            for mkt in bk.get("markets", []):
                market_key = mkt["key"]
                prop_family = PROP_FAMILY_MAP.get(market_key, market_key)

                player_lines = {}
                for outcome in mkt.get("outcomes", []):
                    player = outcome.get("description", "Unknown")
                    direction = outcome["name"]
                    player_lines.setdefault(player, {})[direction] = {
                        "point": outcome.get("point"),
                        "price": outcome.get("price"),
                    }

                for player, sides in player_lines.items():
                    over = sides.get("Over", {})
                    under = sides.get("Under", {})
                    line = over.get("point") or under.get("point")
                    if line is None:
                        continue

                    all_rows.append({
                        "date": target_date,
                        "collection_timestamp": ts,
                        "event_id": eid,
                        "home_team": home,
                        "away_team": away,
                        "commence_time": commence,
                        "player_name": player,
                        "prop_type": prop_family,
                        "sportsbook": book_key,
                        "line": float(line),
                        "over_odds": over.get("price"),
                        "under_odds": under.get("price"),
                        "snapshot_type": "refresh",
                    })

    df = pd.DataFrame(all_rows)
    if len(df) > 0:
        df["first_seen_flag"] = False
        df["latest_seen_flag"] = True

        # Update previous snapshots: latest_seen_flag = False
        if RAW_ARCHIVE_FILE.exists():
            arch = pd.read_parquet(RAW_ARCHIVE_FILE)
            mask = (arch["date"] == target_date) & (arch["latest_seen_flag"] == True)
            arch.loc[mask, "latest_seen_flag"] = False
            arch.to_parquet(RAW_ARCHIVE_FILE, index=False)

        raw_file = RAW_DIR / f"props_{target_date}_{datetime.now().strftime('%H%M')}_refresh.parquet"
        df.to_parquet(raw_file, index=False)
        _append_to_archive(df, RAW_ARCHIVE_FILE)
        print(f"  Refresh: {len(df)} lines saved")
    else:
        print("  No lines found on refresh")

    return df


# ══════════════════════════════════════════════════════════════
# MODEL C PROJECTION ENGINE
# ══════════════════════════════════════════════════════════════

def load_player_features():
    """Load the latest player feature data, or build live from game logs."""
    feat_file = MODEL_C_DIR / "player_prop_features.parquet"
    if feat_file.exists():
        return pd.read_parquet(feat_file)

    # Build features live from game logs if available
    logs_file = MODEL_C_DIR / "player_game_logs.parquet"
    if not logs_file.exists():
        print("  WARNING: No player_game_logs.parquet — fetching current season...")
        try:
            from nba_api.stats.endpoints import leaguegamelog
            import time as _t
            _t.sleep(1)
            lg = leaguegamelog.LeagueGameLog(
                season="2025-26", player_or_team_abbreviation="P",
                season_type_all_star="Regular Season"
            )
            df = lg.get_data_frames()[0]
            df["season"] = "2025-26"
            df.to_parquet(logs_file, index=False)
            print(f"  Fetched {len(df)} rows for 2025-26")
        except Exception as e:
            print(f"  ERROR: {e}")
            return None

    # Build quick rolling features from logs
    print("  Building live features from game logs...")
    plogs = pd.read_parquet(logs_file)
    plogs["game_date"] = pd.to_datetime(plogs["GAME_DATE"])
    plogs["minutes"] = pd.to_numeric(plogs["MIN"], errors="coerce").fillna(0)
    plogs["pts"] = pd.to_numeric(plogs["PTS"], errors="coerce").fillna(0)
    plogs["reb"] = pd.to_numeric(plogs["REB"], errors="coerce").fillna(0)
    plogs["ast"] = pd.to_numeric(plogs["AST"], errors="coerce").fillna(0)
    plogs["pra"] = plogs["pts"] + plogs["reb"] + plogs["ast"]

    played = plogs[plogs["minutes"] > 0].copy()
    played = played.sort_values(["PLAYER_ID", "game_date"])

    # Per-minute rates
    for stat in ["pts", "reb", "ast", "pra"]:
        played[f"{stat}_per_min"] = played[stat] / played["minutes"]

    # Rolling L10 (shifted for no leakage)
    def _rolling(group):
        g = group.copy()
        for stat in ["minutes", "pts", "reb", "ast", "pra",
                      "pts_per_min", "reb_per_min", "ast_per_min", "pra_per_min"]:
            g[f"{stat}_L10"] = g[stat].rolling(10, min_periods=5).mean().shift(1)
            g[f"{stat}_L5"] = g[stat].rolling(5, min_periods=3).mean().shift(1)
        for stat in ["pts", "reb", "ast", "pra", "minutes"]:
            g[f"{stat}_std10"] = g[stat].rolling(10, min_periods=5).std().shift(1)
        return g

    played = played.groupby("PLAYER_ID", group_keys=False).apply(_rolling)
    played["player_name"] = played["PLAYER_NAME"]
    played["player_id"] = played["PLAYER_ID"]

    return played


def project_player_props(lines_df, feat_df):
    """Generate projections for each player prop line."""
    if feat_df is None or len(feat_df) == 0 or len(lines_df) == 0:
        # No features — add empty projection columns so downstream works
        lines_df["projection"] = np.nan
        lines_df["projected_minutes"] = np.nan
        lines_df["edge"] = np.nan
        lines_df["lean_direction"] = "NEUTRAL"
        lines_df["confidence_tier"] = "NO_PLAY"
        return lines_df

    # Get the latest feature row per player (most recent game before today)
    feat_df = feat_df.sort_values(["player_id", "game_date"])
    latest_feat = feat_df.groupby("player_name").last().reset_index()

    # Build projection lookup
    proj_lookup = {}
    for _, row in latest_feat.iterrows():
        pname = row["player_name"]
        proj_lookup[pname] = {
            "proj_pts": row.get("pts_L10", np.nan),
            "proj_reb": row.get("reb_L10", np.nan),
            "proj_ast": row.get("ast_L10", np.nan),
            "proj_pra": row.get("pra_L10", np.nan),
            "proj_minutes": row.get("minutes_L10", np.nan),
            "pts_per_min": row.get("pts_per_min_L10", np.nan),
            "reb_per_min": row.get("reb_per_min_L10", np.nan),
            "ast_per_min": row.get("ast_per_min_L10", np.nan),
            "pra_per_min": row.get("pra_per_min_L10", np.nan),
            "pts_std": row.get("pts_std10", np.nan),
            "reb_std": row.get("reb_std10", np.nan),
            "ast_std": row.get("ast_std10", np.nan),
            "minutes_L5": row.get("minutes_L5", np.nan),
            "pts_L5": row.get("pts_L5", np.nan),
        }

    PROP_PROJ_MAP = {
        "points": "proj_pts",
        "rebounds": "proj_reb",
        "assists": "proj_ast",
        "pra": "proj_pra",
    }

    projections = []
    for _, row in lines_df.iterrows():
        pname = row["player_name"]
        prop_type = row["prop_type"]

        pdata = proj_lookup.get(pname, {})
        proj_key = PROP_PROJ_MAP.get(prop_type)
        projection = pdata.get(proj_key, np.nan) if proj_key else np.nan
        proj_minutes = pdata.get("proj_minutes", np.nan)

        edge = projection - row["line"] if not pd.isna(projection) else np.nan
        lean = "OVER" if edge > 0 else "UNDER" if edge < 0 else "NEUTRAL"

        abs_edge = abs(edge) if not pd.isna(edge) else 0
        if abs_edge >= EDGE_THRESHOLDS["HIGH"]:
            tier = "HIGH"
        elif abs_edge >= EDGE_THRESHOLDS["MEDIUM"]:
            tier = "MEDIUM"
        elif abs_edge >= EDGE_THRESHOLDS["LOW"]:
            tier = "LOW"
        else:
            tier = "NO_PLAY"

        projections.append({
            "projection": round(projection, 2) if not pd.isna(projection) else np.nan,
            "projected_minutes": round(proj_minutes, 1) if not pd.isna(proj_minutes) else np.nan,
            "edge": round(edge, 2) if not pd.isna(edge) else np.nan,
            "lean_direction": lean,
            "confidence_tier": tier,
        })

    proj_df = pd.DataFrame(projections)
    result = pd.concat([lines_df.reset_index(drop=True), proj_df], axis=1)
    return result


# ══════════════════════════════════════════════════════════════
# SHADOW CARD GENERATION
# ══════════════════════════════════════════════════════════════

def generate_shadow_card(df, target_date):
    """Generate daily shadow card report."""
    if len(df) == 0:
        print("  No data for shadow card.")
        return

    phase = detect_season_phase(target_date)

    # Best line per player-prop (highest priority book)
    df["book_rank"] = df["sportsbook"].map(
        {b: i for i, b in enumerate(BOOKS_PRIORITY)}
    ).fillna(99)

    best = df.sort_values("book_rank").groupby(
        ["player_name", "prop_type"]
    ).first().reset_index()

    # Filter to plays with projections
    has_proj = best["projection"].notna() if "projection" in best.columns else pd.Series(False, index=best.index)
    has_tier = best["confidence_tier"] != "NO_PLAY" if "confidence_tier" in best.columns else pd.Series(False, index=best.index)
    plays = best[has_proj & has_tier].copy()
    if len(plays) > 0:
        plays = plays.sort_values("edge", key=abs, ascending=False)

    lines_out = []
    lines_out.append(f"NBA MODEL C SHADOW CARD — {target_date} ({phase})")
    lines_out.append("=" * 60)
    lines_out.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines_out.append(f"Games: {df['event_id'].nunique()}")
    lines_out.append(f"Total prop lines collected: {len(df)}")
    lines_out.append(f"Unique player-props: {len(best)}")
    lines_out.append(f"Actionable plays: {len(plays)}")
    lines_out.append("")

    for tier in ["HIGH", "MEDIUM", "LOW"]:
        tier_plays = plays[plays["confidence_tier"] == tier]
        if len(tier_plays) == 0:
            continue

        lines_out.append(f"--- {tier} CONFIDENCE ---")
        lines_out.append("")

        for direction in ["OVER", "UNDER"]:
            dir_plays = tier_plays[tier_plays["lean_direction"] == direction]
            if len(dir_plays) == 0:
                continue

            lines_out.append(f"  {direction}:")
            for _, p in dir_plays.head(15).iterrows():
                matchup = f"{p.get('away_team','')} @ {p.get('home_team','')}"
                lines_out.append(
                    f"    {p['player_name']:<22s} {p['prop_type']:<10s} "
                    f"line={p['line']:<6.1f} proj={p['projection']:<6.1f} "
                    f"edge={p['edge']:+.1f}  [{p['sportsbook']}]"
                )
            lines_out.append("")

    # Summary stats
    lines_out.append("-" * 60)
    lines_out.append("SUMMARY:")
    for pt in ["points", "rebounds", "assists", "pra"]:
        pt_plays = plays[plays["prop_type"] == pt]
        n_over = (pt_plays["lean_direction"] == "OVER").sum()
        n_under = (pt_plays["lean_direction"] == "UNDER").sum()
        avg_edge = pt_plays["edge"].abs().mean() if len(pt_plays) > 0 else 0
        lines_out.append(f"  {pt:<12s}: {len(pt_plays):>3d} plays (O:{n_over} U:{n_under}) avg|edge|={avg_edge:.1f}")
    lines_out.append("")

    card_text = "\n".join(lines_out)

    # Save card
    card_file = CARDS_DIR / f"card_{target_date}.txt"
    with open(card_file, "w") as f:
        f.write(card_text)
    print(f"  Shadow card: {card_file.name}")
    print(card_text)

    # Save normalized lines to archive
    archive_cols = ["date", "collection_timestamp", "event_id", "home_team", "away_team",
                    "player_name", "prop_type", "sportsbook", "line", "over_odds", "under_odds",
                    "projection", "projected_minutes", "edge", "lean_direction", "confidence_tier",
                    "first_seen_flag", "latest_seen_flag"]
    archive_cols = [c for c in archive_cols if c in best.columns]
    _append_to_archive(best[archive_cols], LINES_ARCHIVE_FILE)

    # Save to shadow tracker (ungraded)
    shadow_cols = ["date", "collection_timestamp", "player_name",
                   "home_team", "away_team", "prop_type", "sportsbook",
                   "line", "over_odds", "under_odds",
                   "projection", "projected_minutes", "edge",
                   "lean_direction", "confidence_tier"]
    shadow_cols = [c for c in shadow_cols if c in plays.columns]
    shadow_rows = plays[shadow_cols].copy()
    shadow_rows["team"] = ""  # Will be filled on grading
    shadow_rows["opponent"] = ""
    shadow_rows["result_value"] = np.nan
    shadow_rows["result_outcome"] = ""
    shadow_rows["roi_outcome"] = np.nan
    shadow_rows["first_seen_line"] = shadow_rows["line"]
    shadow_rows["latest_seen_line"] = shadow_rows["line"]
    shadow_rows["line_movement"] = 0.0
    shadow_rows["season_phase"] = phase
    shadow_rows["graded"] = False

    shadow_file = PO_SHADOW_FILE if phase == "PO" else RS_SHADOW_FILE
    _append_to_archive(shadow_rows, shadow_file)
    print(f"  Shadow plays appended: {len(shadow_rows)} to {shadow_file.name}")

    return plays


# ══════════════════════════════════════════════════════════════
# PHASE C — GRADING
# ══════════════════════════════════════════════════════════════

def grade_yesterday(target_date):
    """Grade yesterday's shadow plays using actual box scores."""
    yesterday = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Grading shadow plays for {yesterday}...")

    # Load player game logs for actuals
    try:
        from nba_api.stats.endpoints import leaguegamelog
        time.sleep(1)
        lg = leaguegamelog.LeagueGameLog(
            season="2025-26",
            player_or_team_abbreviation="P",
            season_type_all_star="Regular Season",
        )
        actuals = lg.get_data_frames()[0]
        actuals["GAME_DATE"] = pd.to_datetime(actuals["GAME_DATE"])
        actuals = actuals[actuals["GAME_DATE"] == yesterday]

        if len(actuals) == 0:
            # Try playoffs
            time.sleep(1)
            lg2 = leaguegamelog.LeagueGameLog(
                season="2025-26",
                player_or_team_abbreviation="P",
                season_type_all_star="Playoffs",
            )
            actuals = lg2.get_data_frames()[0]
            actuals["GAME_DATE"] = pd.to_datetime(actuals["GAME_DATE"])
            actuals = actuals[actuals["GAME_DATE"] == yesterday]

        print(f"  Actuals for {yesterday}: {len(actuals)} player-games")
    except Exception as e:
        print(f"  ERROR fetching actuals: {e}")
        return

    if len(actuals) == 0:
        print(f"  No games found for {yesterday}")
        return

    # Build actuals lookup
    actuals["PTS"] = pd.to_numeric(actuals["PTS"], errors="coerce")
    actuals["REB"] = pd.to_numeric(actuals["REB"], errors="coerce")
    actuals["AST"] = pd.to_numeric(actuals["AST"], errors="coerce")
    actuals["PRA"] = actuals["PTS"] + actuals["REB"] + actuals["AST"]

    actual_lookup = {}
    for _, row in actuals.iterrows():
        name = row["PLAYER_NAME"]
        actual_lookup[name] = {
            "points": row["PTS"],
            "rebounds": row["REB"],
            "assists": row["AST"],
            "pra": row["PRA"],
            "team": row["TEAM_ABBREVIATION"],
            "minutes": pd.to_numeric(row["MIN"], errors="coerce"),
        }

    # Grade both RS and PO shadows
    for shadow_file, label in [(RS_SHADOW_FILE, "RS"), (PO_SHADOW_FILE, "PO")]:
        if not shadow_file.exists():
            continue

        shadow = pd.read_parquet(shadow_file)
        to_grade = shadow[(shadow["date"] == yesterday) & (shadow["graded"] == False)]

        if len(to_grade) == 0:
            continue

        print(f"  Grading {len(to_grade)} {label} plays...")
        graded = 0

        for idx in to_grade.index:
            pname = shadow.loc[idx, "player_name"]
            prop_type = shadow.loc[idx, "prop_type"]
            line = shadow.loc[idx, "line"]
            lean = shadow.loc[idx, "lean_direction"]

            player_actual = actual_lookup.get(pname, {})
            result_val = player_actual.get(prop_type, np.nan)

            if pd.isna(result_val):
                shadow.loc[idx, "result_outcome"] = "DNP"
                shadow.loc[idx, "graded"] = True
                continue

            shadow.loc[idx, "result_value"] = result_val
            shadow.loc[idx, "team"] = player_actual.get("team", "")

            # Determine outcome
            if lean == "OVER":
                if result_val > line:
                    outcome = "WIN"
                    roi = 100 / 110  # standard -110
                elif result_val < line:
                    outcome = "LOSS"
                    roi = -1.0
                else:
                    outcome = "PUSH"
                    roi = 0.0
            elif lean == "UNDER":
                if result_val < line:
                    outcome = "WIN"
                    roi = 100 / 110
                elif result_val > line:
                    outcome = "LOSS"
                    roi = -1.0
                else:
                    outcome = "PUSH"
                    roi = 0.0
            else:
                outcome = "NO_PLAY"
                roi = 0.0

            shadow.loc[idx, "result_outcome"] = outcome
            shadow.loc[idx, "roi_outcome"] = roi
            shadow.loc[idx, "graded"] = True
            graded += 1

        shadow.to_parquet(shadow_file, index=False)
        print(f"  Graded: {graded} {label} plays")


# ══════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════

def print_summary():
    """Print summary for both RS and PO."""
    for shadow_file, label in [(RS_SHADOW_FILE, "REGULAR SEASON"), (PO_SHADOW_FILE, "PLAYOFFS")]:
        if not shadow_file.exists():
            continue

        shadow = pd.read_parquet(shadow_file)
        graded = shadow[shadow["graded"] == True]
        active = graded[graded["result_outcome"].isin(["WIN", "LOSS", "PUSH"])]

        print(f"\n{'='*60}")
        print(f"NBA MODEL C SHADOW — {label}")
        print(f"{'='*60}")

        if len(active) == 0:
            print("  No graded plays yet.")
            continue

        # Overall
        wins = (active["result_outcome"] == "WIN").sum()
        losses = (active["result_outcome"] == "LOSS").sum()
        pushes = (active["result_outcome"] == "PUSH").sum()
        n = wins + losses
        hit_rate = wins / n * 100 if n > 0 else 0
        roi = active["roi_outcome"].mean() * 100 if n > 0 else 0

        print(f"\n  OVERALL: {wins}W-{losses}L-{pushes}P  ({n} bets)")
        print(f"  Hit rate: {hit_rate:.1f}%")
        print(f"  ROI: {roi:+.2f}%")

        # By prop type
        print(f"\n  BY PROP TYPE:")
        for pt in ["points", "rebounds", "assists", "pra"]:
            sub = active[active["prop_type"] == pt]
            if len(sub) == 0:
                continue
            w = (sub["result_outcome"] == "WIN").sum()
            l = (sub["result_outcome"] == "LOSS").sum()
            n_pt = w + l
            hr = w / n_pt * 100 if n_pt > 0 else 0
            r = sub["roi_outcome"].mean() * 100 if n_pt > 0 else 0
            print(f"    {pt:<12s}: {w}W-{l}L ({hr:.1f}%, ROI {r:+.1f}%)")

        # By confidence tier
        print(f"\n  BY CONFIDENCE:")
        for tier in ["HIGH", "MEDIUM", "LOW"]:
            sub = active[active["confidence_tier"] == tier]
            if len(sub) == 0:
                continue
            w = (sub["result_outcome"] == "WIN").sum()
            l = (sub["result_outcome"] == "LOSS").sum()
            n_t = w + l
            hr = w / n_t * 100 if n_t > 0 else 0
            r = sub["roi_outcome"].mean() * 100 if n_t > 0 else 0
            print(f"    {tier:<8s}: {w}W-{l}L ({hr:.1f}%, ROI {r:+.1f}%)")

        # By direction
        print(f"\n  BY DIRECTION:")
        for d in ["OVER", "UNDER"]:
            sub = active[active["lean_direction"] == d]
            if len(sub) == 0:
                continue
            w = (sub["result_outcome"] == "WIN").sum()
            l = (sub["result_outcome"] == "LOSS").sum()
            n_d = w + l
            hr = w / n_d * 100 if n_d > 0 else 0
            r = sub["roi_outcome"].mean() * 100 if n_d > 0 else 0
            print(f"    {d:<8s}: {w}W-{l}L ({hr:.1f}%, ROI {r:+.1f}%)")

        # By edge band
        print(f"\n  BY EDGE BAND:")
        active_with_edge = active[active["edge"].notna()].copy()
        active_with_edge["abs_edge"] = active_with_edge["edge"].abs()
        for lo, hi, label_band in [(0.5, 1.5, "0.5-1.5"), (1.5, 3.0, "1.5-3.0"), (3.0, 99, "3.0+")]:
            sub = active_with_edge[(active_with_edge["abs_edge"] >= lo) & (active_with_edge["abs_edge"] < hi)]
            if len(sub) == 0:
                continue
            w = (sub["result_outcome"] == "WIN").sum()
            l = (sub["result_outcome"] == "LOSS").sum()
            n_b = w + l
            hr = w / n_b * 100 if n_b > 0 else 0
            r = sub["roi_outcome"].mean() * 100 if n_b > 0 else 0
            print(f"    edge {label_band:<8s}: {w}W-{l}L ({hr:.1f}%, ROI {r:+.1f}%)")

        # By book
        print(f"\n  BY SPORTSBOOK:")
        for book in active["sportsbook"].unique():
            sub = active[active["sportsbook"] == book]
            w = (sub["result_outcome"] == "WIN").sum()
            l = (sub["result_outcome"] == "LOSS").sum()
            n_bk = w + l
            if n_bk == 0:
                continue
            hr = w / n_bk * 100
            print(f"    {book:<16s}: {w}W-{l}L ({hr:.1f}%)")

        # Rolling 7-day
        recent = active[active["date"] >= (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")]
        if len(recent) > 0:
            w7 = (recent["result_outcome"] == "WIN").sum()
            l7 = (recent["result_outcome"] == "LOSS").sum()
            r7 = recent["roi_outcome"].mean() * 100 if (w7 + l7) > 0 else 0
            print(f"\n  LAST 7 DAYS: {w7}W-{l7}L, ROI {r7:+.1f}%")

        # CLV summary
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from shared.clv_utils import clv_summary
            clv_summary(active, label)
        except ImportError:
            pass

        # Dates covered
        dates = sorted(active["date"].unique())
        print(f"\n  Dates: {dates[0]} to {dates[-1]} ({len(dates)} days)")

    # Save summary text
    _save_summary_files()


def _save_summary_files():
    """Save RS and PO summary text files."""
    for shadow_file, label, out_file in [
        (RS_SHADOW_FILE, "RS", SHADOW_DIR / "model_c_rs_summary.txt"),
        (PO_SHADOW_FILE, "PO", SHADOW_DIR / "model_c_po_summary.txt"),
    ]:
        if not shadow_file.exists():
            continue
        shadow = pd.read_parquet(shadow_file)
        graded = shadow[shadow["graded"] == True]
        active = graded[graded["result_outcome"].isin(["WIN", "LOSS", "PUSH"])]

        lines_out = []
        lines_out.append(f"NBA Model C Shadow Summary — {label}")
        lines_out.append(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines_out.append(f"Total graded: {len(active)}")

        if len(active) > 0:
            wins = (active["result_outcome"] == "WIN").sum()
            losses = (active["result_outcome"] == "LOSS").sum()
            n = wins + losses
            lines_out.append(f"Record: {wins}W-{losses}L")
            lines_out.append(f"Hit rate: {wins/n*100:.1f}%" if n > 0 else "Hit rate: N/A")
            lines_out.append(f"ROI: {active['roi_outcome'].mean()*100:+.2f}%" if n > 0 else "ROI: N/A")
        else:
            lines_out.append("No graded plays yet.")

        with open(out_file, "w") as f:
            f.write("\n".join(lines_out))


# ══════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════

def _append_to_archive(df, archive_path):
    """Safely append to a parquet archive."""
    if archive_path.exists():
        existing = pd.read_parquet(archive_path)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined.to_parquet(archive_path, index=False)


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NBA Model C Player Props Shadow System")
    parser.add_argument("--collect", action="store_true", help="Morning: collect lines + project + card")
    parser.add_argument("--refresh", action="store_true", help="Midday: re-pull lines snapshot")
    parser.add_argument("--grade", action="store_true", help="Grade yesterday's plays")
    parser.add_argument("--summary", action="store_true", help="Print summary")
    parser.add_argument("--date", type=str, default=None, help="Target date (YYYY-MM-DD)")

    args = parser.parse_args()
    target_date = args.date or datetime.now().strftime("%Y-%m-%d")

    if not API_KEY:
        print("ERROR: ODDS_API_KEY not set")
        sys.exit(1)

    if not any([args.collect, args.refresh, args.grade, args.summary]):
        print("No action specified. Use --collect, --refresh, --grade, or --summary")
        parser.print_help()
        sys.exit(1)

    if args.collect:
        print(f"\n{'='*60}")
        print(f"MODEL C SHADOW — COLLECT ({target_date})")
        print(f"{'='*60}\n")

        lines_df = collect_lines(target_date)
        if len(lines_df) > 0:
            feat_df = load_player_features()
            projected = project_player_props(lines_df, feat_df)
            generate_shadow_card(projected, target_date)
        else:
            print("No lines collected — no games today?")

    if args.refresh:
        print(f"\n{'='*60}")
        print(f"MODEL C SHADOW — REFRESH ({target_date})")
        print(f"{'='*60}\n")
        refresh_lines(target_date)

    if args.grade:
        print(f"\n{'='*60}")
        print(f"MODEL C SHADOW — GRADE")
        print(f"{'='*60}\n")
        grade_yesterday(target_date)

    if args.summary:
        print_summary()


if __name__ == "__main__":
    main()
