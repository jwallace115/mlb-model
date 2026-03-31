#!/usr/bin/env python3
"""
Closing Line Runner — Captures closing odds for all pending shadow plays.
Run ~15-20 minutes before first game starts.

Usage:
  python3 shared/closing_line_runner.py              # all sports
  python3 shared/closing_line_runner.py --sport NBA  # one sport
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.clv_utils import get_closing_odds, compute_clv, add_clv_columns

SHADOW_FILES = {
    "NBA": PROJECT_ROOT / "nba" / "model_c" / "shadow" / "model_c_rs_shadow.parquet",
    "MLB_HITS": PROJECT_ROOT / "mlb" / "props" / "shadow" / "mlb_props_hits_rs_shadow.parquet",
    "MLB_TOTALS": PROJECT_ROOT / "sim" / "data" / "shadow_log.parquet",
    "NHL": PROJECT_ROOT / "nhl" / "nhl_decisions.parquet",
    "SOCCER": PROJECT_ROOT / "soccer" / "data" / "soccer_decisions.parquet",
}

SPORT_KEY = {
    "NBA": "NBA",
    "MLB_HITS": "MLB",
    "MLB_TOTALS": "MLB",
    "NHL": "NHL",
    "SOCCER": "SOCCER",
}

LOG_FILE = PROJECT_ROOT / "shared" / "logs" / "clv_capture_log.csv"


def capture_closing_lines(sport_label, shadow_file, target_date=None):
    """Capture closing lines for pending plays in a shadow file."""
    if not shadow_file.exists():
        print(f"  {sport_label}: shadow file not found ({shadow_file})")
        return 0

    df = pd.read_parquet(shadow_file)
    df = add_clv_columns(df)

    today = target_date or datetime.now().strftime("%Y-%m-%d")

    # Find pending plays: today's plays without closing line
    date_col = "date" if "date" in df.columns else "game_date"
    if date_col not in df.columns:
        print(f"  {sport_label}: no date column found")
        return 0

    pending = df[(df[date_col] == today) & (df["closing_captured"] == False)]

    if len(pending) == 0:
        print(f"  {sport_label}: no pending plays for {today}")
        return 0

    print(f"  {sport_label}: {len(pending)} pending plays for {today}")

    captured = 0
    log_rows = []

    for idx in pending.index:
        row = df.loc[idx]

        # Determine what to query
        event_id = row.get("event_id", "")
        player_name = row.get("player_name", "")
        prop_type = row.get("prop_type", "totals")
        direction = row.get("lean_direction", row.get("signal_side", "OVER")).upper()
        decision_odds = row.get("over_odds", row.get("market_line", np.nan))

        sport_key = SPORT_KEY.get(sport_label, sport_label)

        # Get closing odds
        result = get_closing_odds(
            event_id=event_id,
            player_name=player_name if prop_type != "totals" else None,
            prop_type=prop_type,
            sport=sport_key,
            direction=direction,
        )

        closing_odds = result.get("closing_odds", np.nan)

        # Compute CLV
        clv = compute_clv(decision_odds, closing_odds)

        # Update shadow log
        df.loc[idx, "closing_odds"] = clv["closing_odds"]
        df.loc[idx, "clv_raw"] = clv["clv_raw"]
        df.loc[idx, "clv_pct"] = clv["clv_pct"]
        df.loc[idx, "beat_close"] = clv["beat_close"]
        df.loc[idx, "closing_captured"] = clv["closing_captured"]

        if clv["closing_captured"]:
            captured += 1

        log_rows.append({
            "date": today,
            "sport": sport_label,
            "player_name": player_name,
            "prop_type": prop_type,
            "event_id": event_id,
            "decision_odds": decision_odds,
            "closing_odds": closing_odds,
            "clv_raw": clv["clv_raw"],
            "clv_pct": clv["clv_pct"],
            "closing_captured": clv["closing_captured"],
            "error": result.get("error", ""),
        })

    # Save updated shadow log
    df.to_parquet(shadow_file, index=False)

    # Append to capture log
    if log_rows:
        log_df = pd.DataFrame(log_rows)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists():
            existing_log = pd.read_csv(LOG_FILE)
            log_df = pd.concat([existing_log, log_df], ignore_index=True)
        log_df.to_csv(LOG_FILE, index=False)

    print(f"  {sport_label}: captured {captured}/{len(pending)} closing lines")
    return captured


def main():
    parser = argparse.ArgumentParser(description="Closing Line Runner")
    parser.add_argument("--sport", type=str, default=None,
                        help="Specific sport (NBA, MLB_HITS, MLB_TOTALS, NHL, SOCCER)")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    target_date = args.date or datetime.now().strftime("%Y-%m-%d")
    print(f"Closing Line Runner — {target_date}")
    print("=" * 50)

    sports = [args.sport] if args.sport else list(SHADOW_FILES.keys())
    total_captured = 0

    for sport in sports:
        if sport not in SHADOW_FILES:
            print(f"  Unknown sport: {sport}")
            continue
        total_captured += capture_closing_lines(sport, SHADOW_FILES[sport], target_date)

    print(f"\nTotal closing lines captured: {total_captured}")


if __name__ == "__main__":
    main()
