#!/usr/bin/env python3
"""
MLB Totals P1B Shadow — Cold-Warm EARLY_HEAVY FG Over
=====================================================
Shadow signal: Full-game OVER at cold-climate outdoor parks
on warm days (>=75F) when the market implies early-heavy
scoring path (F5 ratio > 0.5625).

Frozen rules (do not modify without full revalidation):
  1. June-September only
  2. Cold-climate outdoor park (frozen 18-park set)
  3. Forecast first-pitch temperature >= 75 F
  4. EARLY_HEAVY: F5_total / FG_total > 0.5625
  5. Closing FG over price <= -105
  6. Side: Full-game OVER

object_id: mlb_p1b_coldwarm_earlyheavy_over_v1

Usage:
  python3 mlb/pipeline/mlb_totals_p1b_shadow.py            # generate today's signals
  python3 mlb/pipeline/mlb_totals_p1b_shadow.py --grade     # grade completed games
  python3 mlb/pipeline/mlb_totals_p1b_shadow.py --summary   # print season summary
  python3 mlb/pipeline/mlb_totals_p1b_shadow.py --date 2026-06-15  # specific date
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ── Project root ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# ── Constants (FROZEN — do not change) ────────────────────────────────────────
OBJECT_ID = "mlb_p1b_coldwarm_earlyheavy_over_v1"
RULESET_VERSION = "frozen_v1"

COLD_CLIMATE_OUTDOOR = {
    "BAL", "BOS", "CHC", "CHW", "CIN", "CLE", "COL", "DET",
    "KCR", "MIN", "NYM", "NYY", "PHI", "PIT", "SEA", "SFG",
    "STL", "WSN",
}

F5_RATIO_THRESHOLD = 0.5625
TEMP_THRESHOLD = 75.0
OVER_PRICE_MAX = -105
MONTH_MIN = 6
MONTH_MAX = 9

# ── Paths ─────────────────────────────────────────────────────────────────────
TRACKER_PATH = ROOT / "mlb" / "logs" / "mlb_p1b_coldwarm_earlyheavy_over_shadow_2026.json"
F5_LINES_PATH = ROOT / "mlb_sim_f5" / "data" / "f5_lines_2026.parquet"
LINE_SNAPSHOTS_PATH = ROOT / "mlb_sim" / "data" / "line_snapshots_2026.json"
ODDS_CACHE_DIR = ROOT / "data" / "cache"

# MLB Stats API abbreviation -> our standard abbreviation
_STATSAPI_ABB_MAP = {
    "AZ": "ARI", "CWS": "CHW", "KC": "KCR", "SD": "SDP",
    "SF": "SFG", "TB": "TBR", "WSH": "WSN", "ATH": "OAK",
}

# Odds API full name -> our abbreviation (from config.py)
_ODDS_FULL_TO_ABB = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Athletics": "OAK",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SDP", "San Francisco Giants": "SFG",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR", "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN",
}


def _normalize_abb(abb: str) -> str:
    """Map MLB Stats API abbreviation to our canonical form."""
    return _STATSAPI_ABB_MAP.get(abb, abb)


def _load_tracker() -> dict:
    """Load or initialize the shadow tracker."""
    if TRACKER_PATH.exists():
        with open(TRACKER_PATH) as f:
            return json.load(f)
    return {
        "object_id": OBJECT_ID,
        "ruleset_version": RULESET_VERSION,
        "start_date": date.today().isoformat(),
        "signals": [],
    }


def _save_tracker(tracker: dict):
    """Save tracker to disk."""
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_PATH, "w") as f:
        json.dump(tracker, f, indent=2, default=str)


# ── Data loaders ──────────────────────────────────────────────────────────────

def fetch_schedule(target_date: str) -> list[dict]:
    """Fetch MLB schedule from Stats API with team abbreviations."""
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}&hydrate=team,linescore"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            status = g["status"]["detailedState"]
            ht = g["teams"]["home"]["team"]
            at = g["teams"]["away"]["team"]
            home_abb = _normalize_abb(ht.get("abbreviation", ""))
            away_abb = _normalize_abb(at.get("abbreviation", ""))
            # Extract actual total from linescore if game is Final
            actual_total = None
            if status == "Final":
                ls = g.get("linescore", {})
                hr = ls.get("teams", {}).get("home", {}).get("runs")
                ar = ls.get("teams", {}).get("away", {}).get("runs")
                if hr is not None and ar is not None:
                    actual_total = hr + ar
            # Extract game time
            game_dt = g.get("gameDate", "")  # ISO format UTC
            games.append({
                "game_pk": g["gamePk"],
                "home_team": home_abb,
                "away_team": away_abb,
                "status": status,
                "actual_total": actual_total,
                "game_datetime_utc": game_dt,
            })
    return games


def load_fg_lines(target_date: str) -> dict:
    """
    Load full-game total lines for target_date.
    Returns {home_team: {"total_line": float, "over_price": int}} from:
    1. Line snapshots (preferred — latest available snapshot)
    2. Odds API cache
    """
    lines = {}

    # Try line_snapshots first (latest snapshot per game)
    if LINE_SNAPSHOTS_PATH.exists():
        with open(LINE_SNAPSHOTS_PATH) as f:
            snaps = json.load(f)
        for s in snaps:
            if s["game_date"] == target_date:
                ht = s["home_team"]
                # Keep latest snapshot for each game
                if ht not in lines or s.get("snapshot_time", "") > lines[ht].get("_snap_time", ""):
                    lines[ht] = {
                        "total_line": s["total_line"],
                        "over_price": s["over_price"],
                        "_snap_time": s.get("snapshot_time", ""),
                    }

    # Fallback: odds cache
    if not lines:
        cache_file = ODDS_CACHE_DIR / f"odds_full_{target_date}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                odds_data = json.load(f)
            for game in odds_data:
                home_full = game.get("home_team", "")
                home_abb = _ODDS_FULL_TO_ABB.get(home_full)
                if not home_abb:
                    continue
                # Use first bookmaker with totals
                for bm in game.get("bookmakers", []):
                    for mk in bm.get("markets", []):
                        if mk["key"] == "totals":
                            for oc in mk.get("outcomes", []):
                                if oc["name"] == "Over":
                                    lines[home_abb] = {
                                        "total_line": oc["point"],
                                        "over_price": oc["price"],
                                    }
                            break
                    if home_abb in lines:
                        break

    # Strip internal keys
    for ht in lines:
        lines[ht].pop("_snap_time", None)
    return lines


def load_f5_lines(target_date: str) -> dict:
    """
    Load F5 total lines for target_date.
    Returns {home_team: f5_total}.
    """
    f5 = {}
    if not F5_LINES_PATH.exists():
        return f5
    df = pd.read_parquet(F5_LINES_PATH)
    df_day = df[df["date"] == target_date]
    # Use canonical rows preferentially
    canonical = df_day[df_day["is_canonical"] == True]
    if len(canonical) > 0:
        df_day = canonical
    for _, row in df_day.iterrows():
        ht = row["home_team"]
        f5[ht] = row["f5_total"]
    return f5


def fetch_temperature(home_team: str, game_datetime_utc: str) -> dict:
    """
    Fetch forecast temperature from Open-Meteo for the game.
    Returns {"forecast_temp_f": float, "weather_source": str, "weather_timestamp": str}
    or None if dome/unavailable.
    """
    try:
        from modules.weather import fetch_weather
        # Convert UTC to ET game time string
        if game_datetime_utc:
            from datetime import datetime as dt
            from zoneinfo import ZoneInfo
            utc_dt = dt.fromisoformat(game_datetime_utc.replace("Z", "+00:00"))
            et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
            game_time_et = et_dt.strftime("%I:%M %p ET")
        else:
            game_time_et = "07:05 PM ET"

        wx = fetch_weather(home_team, game_time_et)
        if wx.get("is_dome"):
            return None  # Cold-climate outdoor only; domes excluded
        return {
            "forecast_temp_f": wx.get("temperature_f"),
            "weather_source": "open_meteo_forecast",
            "weather_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        print(f"  [WARN] Weather fetch failed for {home_team}: {e}")
        return None


# ── Core logic ────────────────────────────────────────────────────────────────

def generate_signals(target_date: str) -> list[dict]:
    """
    Apply frozen P1B rules to today's MLB slate.
    Returns list of qualifying signal dicts.
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    month = dt.month

    print(f"P1B Shadow — {target_date}")
    print(f"  Month: {month} (window: {MONTH_MIN}-{MONTH_MAX})")

    # Gate 1: Month
    if month < MONTH_MIN or month > MONTH_MAX:
        print(f"  MONTH GATE: {month} outside Jun-Sep window. 0 signals.")
        return []

    # Fetch data
    schedule = fetch_schedule(target_date)
    fg_lines = load_fg_lines(target_date)
    f5_lines = load_f5_lines(target_date)

    print(f"  Games: {len(schedule)}, FG lines: {len(fg_lines)}, F5 lines: {len(f5_lines)}")

    signals = []
    for game in schedule:
        ht = game["home_team"]
        at = game["away_team"]
        label = f"{at}@{ht}"

        # Gate 2: Cold-climate outdoor park
        if ht not in COLD_CLIMATE_OUTDOOR:
            continue

        # Gate 3: Need both FG and F5 lines
        fg = fg_lines.get(ht)
        f5_total = f5_lines.get(ht)
        if not fg or f5_total is None:
            print(f"  {label}: SKIP — missing lines (FG={fg is not None}, F5={f5_total is not None})")
            continue

        fg_total = fg["total_line"]
        over_price = fg["over_price"]

        # Gate 4: F5 ratio
        if fg_total == 0:
            continue
        f5_ratio = f5_total / fg_total
        if f5_ratio <= F5_RATIO_THRESHOLD:
            print(f"  {label}: SKIP — F5 ratio {f5_ratio:.4f} <= {F5_RATIO_THRESHOLD}")
            continue

        # Gate 5: Over price
        if over_price > OVER_PRICE_MAX:
            print(f"  {label}: SKIP — over price {over_price} > {OVER_PRICE_MAX}")
            continue

        # Gate 6: Temperature
        wx = fetch_temperature(ht, game.get("game_datetime_utc", ""))
        if wx is None:
            print(f"  {label}: SKIP — dome or weather unavailable")
            continue

        temp_f = wx["forecast_temp_f"]
        if temp_f is None or temp_f < TEMP_THRESHOLD:
            print(f"  {label}: SKIP — temp {temp_f}F < {TEMP_THRESHOLD}F")
            continue

        # All gates passed
        signal = {
            "date": target_date,
            "game_pk": game["game_pk"],
            "home_team": ht,
            "away_team": at,
            "side": "OVER",
            "fg_total": fg_total,
            "over_price": over_price,
            "f5_total": f5_total,
            "f5_ratio": round(f5_ratio, 4),
            "forecast_temp_f": temp_f,
            "weather_source": wx["weather_source"],
            "weather_timestamp": wx["weather_timestamp"],
            "actual_total": None,
            "result": None,  # W / L / P (push)
            "graded": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"  {label}: QUALIFIES — F5r={f5_ratio:.4f}, temp={temp_f}F, price={over_price}, line={fg_total}")
        signals.append(signal)

    print(f"  Total qualifying: {len(signals)}")
    return signals


def grade_signals(tracker: dict, target_date: str = None) -> int:
    """
    Grade ungraded signals using actual game totals.
    If target_date is specified, only grade that date; otherwise grade all ungraded.
    Returns count of newly graded signals.
    """
    ungraded = [s for s in tracker["signals"]
                if not s["graded"] and (target_date is None or s["date"] == target_date)]

    if not ungraded:
        print("  No ungraded signals to process.")
        return 0

    # Group by date
    dates = sorted(set(s["date"] for s in ungraded))
    graded_count = 0

    for d in dates:
        schedule = fetch_schedule(d)
        scores = {g["game_pk"]: g["actual_total"] for g in schedule
                  if g["actual_total"] is not None}

        for sig in ungraded:
            if sig["date"] != d:
                continue
            pk = sig["game_pk"]
            actual = scores.get(pk)
            if actual is None:
                continue

            sig["actual_total"] = actual
            fg_line = sig["fg_total"]
            if actual > fg_line:
                sig["result"] = "W"
            elif actual < fg_line:
                sig["result"] = "L"
            else:
                sig["result"] = "P"
            sig["graded"] = True
            graded_count += 1
            print(f"  Graded {sig['away_team']}@{sig['home_team']} {d}: "
                  f"actual={actual} vs line={fg_line} -> {sig['result']}")

    return graded_count


def print_summary(tracker: dict):
    """Print season summary statistics."""
    signals = tracker["signals"]
    if not signals:
        print("\n  No signals recorded yet.")
        return

    graded = [s for s in signals if s["graded"]]
    wins = sum(1 for s in graded if s["result"] == "W")
    losses = sum(1 for s in graded if s["result"] == "L")
    pushes = sum(1 for s in graded if s["result"] == "P")

    print(f"\n{'='*60}")
    print(f"P1B Shadow Summary — {OBJECT_ID}")
    print(f"{'='*60}")
    print(f"  Total signals:  {len(signals)}")
    print(f"  Graded:         {len(graded)}")
    print(f"  Ungraded:       {len(signals) - len(graded)}")

    if wins + losses > 0:
        wp = wins / (wins + losses)
        # Compute approximate ROI assuming -110 vig as baseline
        # Actual ROI uses recorded over_price
        total_risked = 0
        total_returned = 0
        for s in graded:
            if s["result"] == "P":
                continue
            price = s.get("over_price", -110)
            if price < 0:
                risk = abs(price)
                win_return = risk + 100
            else:
                risk = 100
                win_return = 100 + price
            total_risked += risk
            if s["result"] == "W":
                total_returned += win_return

        roi = (total_returned - total_risked) / total_risked * 100 if total_risked > 0 else 0

        print(f"  Record:         {wins}-{losses} (pushes: {pushes})")
        print(f"  Win%:           {wp:.1%}")
        print(f"  ROI:            {roi:+.2f}%")

    # By month
    from collections import Counter
    monthly = Counter()
    monthly_w = Counter()
    for s in graded:
        m = s["date"][:7]  # YYYY-MM
        monthly[m] += 1
        if s["result"] == "W":
            monthly_w[m] += 1
    if monthly:
        print(f"\n  By month:")
        for m in sorted(monthly):
            n = monthly[m]
            w = monthly_w[m]
            print(f"    {m}: {w}-{n-w} ({w/n:.0%})")

    print(f"{'='*60}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MLB Totals P1B Shadow")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="Target date (YYYY-MM-DD)")
    parser.add_argument("--grade", action="store_true",
                        help="Grade completed signals")
    parser.add_argument("--summary", action="store_true",
                        help="Print season summary")
    args = parser.parse_args()

    tracker = _load_tracker()

    if args.summary:
        print_summary(tracker)
        return

    if args.grade:
        print(f"P1B Shadow — grading ungraded signals")
        n = grade_signals(tracker, target_date=None)
        print(f"  Graded {n} signals")
        _save_tracker(tracker)
        print_summary(tracker)
        return

    # Generate signals for target date
    target = args.date
    # Check if we already have signals for this date
    existing = [s for s in tracker["signals"] if s["date"] == target]
    if existing:
        print(f"  Already have {len(existing)} signal(s) for {target}. Skipping generation.")
        print(f"  Use --grade to grade, or delete entries to re-run.")
        return

    new_signals = generate_signals(target)
    tracker["signals"].extend(new_signals)
    _save_tracker(tracker)

    print(f"\n  Tracker saved: {TRACKER_PATH}")
    print(f"  Total signals in tracker: {len(tracker['signals'])}")


if __name__ == "__main__":
    main()
