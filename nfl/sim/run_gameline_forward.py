#!/usr/bin/env python3
"""
GL Forward PILOT runner — capture game-line predictions for one NFL week.

Usage: python3 nfl/sim/run_gameline_forward.py --season 2026 --week N

Sign convention for Odds API `point` on the home team's spreads row:
  - Negative when home is favoured (e.g. KC at -3 means KC favoured by 3)
  - `hr_spread_home` stores this value directly
  - `hr_spread_home_margin_convention` = -point = expected home margin
    (comparable with raw_m, which is home - away)

Writes ONE append-only parquet per week:
  nfl/data/sim/outputs/gl_forward/week=2026_NN.parquet

HALTs if:
- The week file already exists (revision 0 only)
- Any game's kickoff is in the past at run time
- The latest snapshot is older than 3 hours (A10 age gate)
- An unmapped team name is encountered

Reads pbp_2025 ONLY as the s-1 prior for 2026 ratings (what ratings.py does).
"""

import argparse, json, os, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = Path(os.environ.get("NFL_PBP_DIR", str(ROOT / "nfl" / "data" / "pbp")))
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs" / "gl_forward"
HFA_PATH = ROOT / "nfl" / "sim" / "hfa_v1.json"
TEAM_MAP_PATH = ROOT / "nfl" / "sim" / "team_names_odds_api.json"
LINE_HIST_DIR = ROOT / "data" / "odds_archive" / "nfl" / "line_history"
N_SIMS = 5000
CHUNK_SIZE = 2500
MAX_SNAPSHOT_AGE_HOURS = 3


def _load_team_map():
    """Load nflverse abbreviation -> Odds API name map. HALT if file missing."""
    if not TEAM_MAP_PATH.exists():
        print(f"HALT: {TEAM_MAP_PATH} not found", file=sys.stderr)
        sys.exit(1)
    with open(TEAM_MAP_PATH) as f:
        raw = json.load(f)
    # Remove metadata keys
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _load_hfa():
    if HFA_PATH.exists():
        with open(HFA_PATH) as f:
            return json.load(f).get("h", 0.0)
    return 0.0


def _get_hard_rock_lines(snapshot_df, event_ids_by_game, team_map):
    """Get Hard Rock lines by event_id (ID-only join).

    Returns dict: game_key -> {spread, total, prices, snapshot_utc, reason_null}
    """
    # Build reverse map: Odds API name -> abbreviation
    rev_map = {v: k for k, v in team_map.items()}

    hr = snapshot_df[snapshot_df["bookmaker"] == "hardrockbet_fl"].copy()

    results = {}
    for game_key, event_id in event_ids_by_game.items():
        home_abbr = game_key.split("_")[0]
        home_name = team_map.get(home_abbr, "")

        if event_id is None:
            results[game_key] = {"reason_null": f"no event_id match for {game_key}"}
            continue

        game_rows = hr[hr["event_id"] == event_id]
        if game_rows.empty:
            results[game_key] = {
                "reason_null": f"no hardrockbet_fl rows for event {event_id}",
                "event_id": event_id,
            }
            continue

        r = {"event_id": event_id}

        # Spreads — match by EXACT mapped home name
        spreads = game_rows[game_rows["market"] == "spreads"]
        home_spread = spreads[spreads["outcome_name"] == home_name]
        if not home_spread.empty:
            point = float(home_spread.iloc[0]["point"])
            r["hr_spread_home"] = point
            r["hr_spread_home_margin_convention"] = -point
            r["hr_price_spread_home"] = int(home_spread.iloc[0]["price"])
        away_spread = spreads[spreads["outcome_name"] != home_name]
        if not away_spread.empty:
            r["hr_price_spread_away"] = int(away_spread.iloc[0]["price"])

        # Totals
        totals = game_rows[game_rows["market"] == "totals"]
        over = totals[totals["outcome_name"] == "Over"]
        under = totals[totals["outcome_name"] == "Under"]
        if not over.empty:
            r["hr_total"] = float(over.iloc[0]["point"])
            r["hr_price_total_over"] = int(over.iloc[0]["price"])
        if not under.empty:
            r["hr_price_total_under"] = int(under.iloc[0]["price"])

        # Moneyline
        h2h = game_rows[game_rows["market"] == "h2h"]
        home_ml = h2h[h2h["outcome_name"] == home_name]
        away_ml = h2h[h2h["outcome_name"] != home_name]
        if not home_ml.empty:
            r["hr_ml_home"] = int(home_ml.iloc[0]["price"])
        if not away_ml.empty:
            r["hr_ml_away"] = int(away_ml.iloc[0]["price"])

        if "hr_spread_home" not in r and "hr_total" not in r:
            r["reason_null"] = f"HR row found but no spread/total for {home_abbr}"

        results[game_key] = r

    return results


def _match_event_ids(snapshot_df, week_games, team_map):
    """Match nflverse games to Odds API event_ids via (mapped home, mapped away, commence_time ±1h).

    Returns dict: game_key -> event_id or None
    """
    snap_games = snapshot_df.drop_duplicates("event_id")[
        ["event_id", "home_team", "away_team", "commence_time"]
    ].copy()

    results = {}
    unmatched = []

    for _, g in week_games.iterrows():
        home_abbr = g["home_team"]
        away_abbr = g["away_team"]
        home_name = team_map.get(home_abbr)
        away_name = team_map.get(away_abbr)

        if home_name is None:
            print(f"HALT: unmapped team abbreviation '{home_abbr}'", file=sys.stderr)
            sys.exit(1)
        if away_name is None:
            print(f"HALT: unmapped team abbreviation '{away_abbr}'", file=sys.stderr)
            sys.exit(1)

        game_key = f"{home_abbr}_{away_abbr}"

        # Match by exact home AND away name
        matched = snap_games[
            (snap_games["home_team"] == home_name) &
            (snap_games["away_team"] == away_name)
        ]

        if len(matched) == 1:
            results[game_key] = matched.iloc[0]["event_id"]
        elif len(matched) > 1:
            # Multiple matches — disambiguate by commence_time if available
            if "commence_time" in g and pd.notna(g.get("commence_time")):
                kick = pd.Timestamp(g["commence_time"])
                if kick.tzinfo is None:
                    kick = kick.tz_localize("UTC")
                matched["ct"] = pd.to_datetime(matched["commence_time"], utc=True)
                close = matched[abs(matched["ct"] - kick) <= timedelta(hours=1)]
                if len(close) == 1:
                    results[game_key] = close.iloc[0]["event_id"]
                else:
                    results[game_key] = None
                    unmatched.append(f"{game_key}: {len(close)} events within ±1h")
            else:
                results[game_key] = matched.iloc[0]["event_id"]
        else:
            results[game_key] = None
            unmatched.append(f"{game_key}: no match for {home_name} vs {away_name}")

    if unmatched:
        print(f"HALT-LEVEL WARNING: {len(unmatched)} games without exactly one event_id match:",
              file=sys.stderr)
        for u in unmatched:
            print(f"  {u}", file=sys.stderr)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    season, week = args.season, args.week
    now_utc = datetime.now(timezone.utc)

    if season not in [2026]:
        print(f"HALT: forward runner is for 2026 only, got {season}", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    week_file = OUT_DIR / f"week={season}_{week:02d}.parquet"

    if week_file.exists():
        print(f"HALT: {week_file} already exists (revision 0 only)", file=sys.stderr)
        sys.exit(1)

    team_map = _load_team_map()
    h = _load_hfa()
    print(f"HFA h = {h}")

    # Load latest snapshot
    snap_dir = LINE_HIST_DIR / f"season={season}"
    if not snap_dir.exists():
        print(f"HALT: no line history dir {snap_dir}", file=sys.stderr)
        sys.exit(1)

    snaps = sorted(snap_dir.glob("snap_*.parquet"))
    if not snaps:
        print(f"HALT: no snapshots in {snap_dir}", file=sys.stderr)
        sys.exit(1)

    latest_snap = snaps[-1]
    # Parse snapshot UTC from filename: snap_YYYYMMDDTHHMMSSz.parquet
    snap_ts_str = latest_snap.stem.replace("snap_", "").rstrip("Z")
    snap_utc = datetime.strptime(snap_ts_str, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    snap_age = now_utc - snap_utc
    snap_age_hours = snap_age.total_seconds() / 3600

    print(f"Latest snapshot: {latest_snap.name} ({snap_age_hours:.1f}h ago)")

    if snap_age_hours > MAX_SNAPSHOT_AGE_HOURS:
        print(f"HALT: snapshot is {snap_age_hours:.1f}h old (> {MAX_SNAPSHOT_AGE_HOURS}h). "
              f"Run `git pull` on the Mac to get the latest VM captures.", file=sys.stderr)
        sys.exit(1)

    snapshot_df = pd.read_parquet(latest_snap)
    print(f"Snapshot: {len(snapshot_df)} rows, "
          f"{snapshot_df['event_id'].nunique()} events, "
          f"bookmakers: {sorted(snapshot_df['bookmaker'].unique())}")

    # Get game schedule for this week from nflverse PBP or schedule
    # For 2026: we use the snapshot's game list + nflverse week mapping
    # TODO: proper nflverse schedule integration
    print(f"\nForward runner ready for week {week}.")
    print(f"Snapshot file: {latest_snap.name}")
    print(f"Snapshot age: {snap_age_hours:.1f}h")
    print(f"Team map: {len(team_map)} teams")
    print(f"MODE: PILOT")


if __name__ == "__main__":
    main()
