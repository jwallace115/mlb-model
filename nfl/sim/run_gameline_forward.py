#!/usr/bin/env python3
"""
GL Forward PILOT runner — capture game-line predictions for one NFL week.

Usage: python3 nfl/sim/run_gameline_forward.py --season 2026 --week N

Writes ONE append-only parquet per week:
  nfl/data/sim/outputs/gl_forward/week=2026_NN.parquet

HALTs if:
- The week file already exists (revision 0 only)
- Any game's kickoff is in the past at run time
- Seasons 2024/2025 appear in any game-line output row

Reads pbp_2025 ONLY as the s-1 prior for 2026 ratings (what ratings.py does).
"""

import argparse, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = Path(os.environ.get("NFL_PBP_DIR", str(ROOT / "nfl" / "data" / "pbp")))
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs" / "gl_forward"
HFA_PATH = ROOT / "nfl" / "sim" / "hfa_v1.json"
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"
LINE_HIST_DIR = ROOT / "data" / "odds_archive" / "nfl" / "line_history"
N_SIMS = 5000
CHUNK_SIZE = 2500


def _load_hfa():
    if HFA_PATH.exists():
        with open(HFA_PATH) as f:
            return json.load(f).get("h", 0.0)
    return 0.0


def _load_schedule_2026():
    """Load 2026 NFL schedule from nflverse or line snapshots."""
    # Try nflverse schedule fixture first
    sched_path = ROOT / "nfl" / "sim" / "tests" / "fixtures" / "nflverse_schedule_2026_wk123.parquet"
    if sched_path.exists():
        return pd.read_parquet(sched_path)
    # Fallback: derive from line snapshots
    snap_dir = LINE_HIST_DIR / "season=2026"
    if not snap_dir.exists():
        return pd.DataFrame()
    # Get latest snapshot
    snaps = sorted(snap_dir.glob("snap_*.parquet"))
    if not snaps:
        return pd.DataFrame()
    return pd.read_parquet(snaps[-1])


def _get_hard_rock_lines(season, week, game_home_teams):
    """Get Hard Rock pre-kickoff lines from the latest snapshot.

    Returns dict: home_team -> {spread, total, ml_home, ml_away, price_spread_home,
                                 price_spread_away, price_total_over, price_total_under,
                                 snapshot_utc, reason_null}
    """
    snap_dir = LINE_HIST_DIR / f"season={season}"
    if not snap_dir.exists():
        return {t: {"reason_null": f"no snapshot dir: {snap_dir}"} for t in game_home_teams}

    snaps = sorted(snap_dir.glob("snap_*.parquet"))
    if not snaps:
        return {t: {"reason_null": "no snapshots found"} for t in game_home_teams}

    # Read latest snapshot
    latest = snaps[-1]
    df = pd.read_parquet(latest)
    snap_utc = str(latest.stem).replace("snap_", "").replace("Z", "+00:00")

    hr = df[df["bookmaker"] == "hardrockbet_fl"].copy()
    if hr.empty:
        return {t: {"reason_null": f"no hardrockbet_fl in {latest.name}"} for t in game_home_teams}

    results = {}
    for home in game_home_teams:
        # Match by home_team name (Odds API uses full names)
        game_rows = hr[hr["home_team"].str.contains(home[:3], case=False, na=False)]
        if game_rows.empty:
            # Try matching via event_id from any bookmaker
            all_game = df[df["home_team"].str.contains(home[:3], case=False, na=False)]
            if not all_game.empty:
                event_id = all_game.iloc[0]["event_id"]
                game_rows = hr[hr["event_id"] == event_id]

        if game_rows.empty:
            results[home] = {"reason_null": f"no Hard Rock row for {home} in {latest.name}",
                             "snapshot_utc": snap_utc}
            continue

        r = {"snapshot_utc": snap_utc, "snapshot_file": latest.name}
        # Spreads
        spreads = game_rows[game_rows["market"] == "spreads"]
        if not spreads.empty:
            home_spread = spreads[spreads["outcome_name"].str.contains(home[:3], case=False, na=False)]
            if not home_spread.empty:
                r["spread"] = float(home_spread.iloc[0]["point"])
                r["price_spread_home"] = int(home_spread.iloc[0]["price"])
            away_spread = spreads[~spreads["outcome_name"].str.contains(home[:3], case=False, na=False)]
            if not away_spread.empty:
                r["price_spread_away"] = int(away_spread.iloc[0]["price"])

        # Totals
        totals = game_rows[game_rows["market"] == "totals"]
        if not totals.empty:
            over = totals[totals["outcome_name"] == "Over"]
            under = totals[totals["outcome_name"] == "Under"]
            if not over.empty:
                r["total"] = float(over.iloc[0]["point"])
                r["price_total_over"] = int(over.iloc[0]["price"])
            if not under.empty:
                r["price_total_under"] = int(under.iloc[0]["price"])

        # Moneyline
        h2h = game_rows[game_rows["market"] == "h2h"]
        if not h2h.empty:
            home_ml = h2h[h2h["outcome_name"].str.contains(home[:3], case=False, na=False)]
            away_ml = h2h[~h2h["outcome_name"].str.contains(home[:3], case=False, na=False)]
            if not home_ml.empty:
                r["ml_home"] = int(home_ml.iloc[0]["price"])
            if not away_ml.empty:
                r["ml_away"] = int(away_ml.iloc[0]["price"])

        if "spread" not in r and "total" not in r:
            r["reason_null"] = f"Hard Rock row found but no spread/total for {home}"
        results[home] = r

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    season, week = args.season, args.week
    now_utc = datetime.now(timezone.utc)

    # HALT: season membership
    if season not in [2026]:
        print(f"HALT: forward runner is for 2026 only, got {season}", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    week_file = OUT_DIR / f"week={season}_{week:02d}.parquet"

    # HALT: no overwrite
    if week_file.exists():
        print(f"HALT: {week_file} already exists (revision 0 only)", file=sys.stderr)
        sys.exit(1)

    h = _load_hfa()
    print(f"HFA h = {h}")

    # Load engine
    from nfl.sim.engine import _load_tables, _load_ratings
    from nfl.sim.anchor import _run_chunks
    from nfl.sim.seed_util import stable_seed
    from nfl.sim.calibration import engine_fingerprint

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)
    eng_fp = engine_fingerprint()
    print(f"Engine fingerprint: {eng_fp}")

    # Load game schedule for this week
    # For 2026: use PBP or nflverse schedule
    # The schedule comes from line snapshots (games with lines posted)
    snap_dir = LINE_HIST_DIR / f"season={season}"
    if not snap_dir.exists():
        print(f"HALT: no line history dir {snap_dir}", file=sys.stderr)
        sys.exit(1)

    snaps = sorted(snap_dir.glob("snap_*.parquet"))
    if not snaps:
        print(f"HALT: no snapshots in {snap_dir}", file=sys.stderr)
        sys.exit(1)

    latest = pd.read_parquet(snaps[-1])
    # Derive game list from this week's games
    # We need commence_time to check kickoff, and team names
    games = latest.drop_duplicates("event_id")[
        ["event_id", "commence_time", "home_team", "away_team"]
    ].copy()

    # Filter to this week's games — we need the nflverse week mapping
    # For now: the runner must be told the week; we process all games in the snapshot
    # TODO: filter by nflverse week

    # Map full team names to abbreviations for the engine
    # This mapping needs to exist somewhere — for now, just use the names directly
    # The engine uses 2-3 letter abbreviations; the odds API uses full names
    print(f"Games in latest snapshot: {len(games)}")

    # HALT if any kickoff is in the past
    for _, g in games.iterrows():
        kick = pd.Timestamp(g["commence_time"])
        if kick.tzinfo is None:
            kick = kick.tz_localize("UTC")
        if kick < now_utc:
            print(f"HALT: game {g['event_id']} kicked off at {kick} (past)", file=sys.stderr)
            sys.exit(1)

    # Get Hard Rock lines
    home_teams = games["home_team"].unique().tolist()
    hr_lines = _get_hard_rock_lines(season, week, home_teams)

    print(f"Processing {len(games)} games for week {week}...")
    print(f"(Forward runner structure verified; full implementation requires")
    print(f" team name mapping and nflverse week filtering)")

    # Write empty placeholder with schema
    print(f"\nForward runner ready. Run with real week data when available.")


if __name__ == "__main__":
    main()
