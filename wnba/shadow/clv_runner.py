#!/usr/bin/env python3
"""WNBA Shadow — CLV Capture (Component 2). Runs 10:30 PM ET.
Uses historical event-level Odds API endpoint for closing-line capture,
so afternoon games that disappear from the live endpoint are still captured.
"""
import os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

SHADOW_DIR = Path("wnba/shadow")
RUN_MODE = os.environ.get("RUN_MODE", "test")

try:
    from dotenv import load_dotenv; load_dotenv()
except Exception: pass
API_KEY = os.environ.get("ODDS_API_KEY", "")

WNBA_SPORT = "basketball_wnba"
PROP_MARKETS = "player_points,player_rebounds,player_assists,player_points_rebounds_assists,player_threes"
HIST_BASE = "https://api.the-odds-api.com/v4/historical/sports"


def _fetch_historical_closing(game_id, commence_time):
    """Fetch pre-tip player prop snapshot via historical event-level endpoint.
    Returns dict: (player_name_lower, market, point) -> {over: price, under: price, book: key}
    """
    # Query 60 seconds before commence_time to get near-closing snapshot
    try:
        ct = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    except Exception:
        return {}, None

    query_ts = (ct - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")

    url = f"{HIST_BASE}/{WNBA_SPORT}/events/{game_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": PROP_MARKETS,
        "oddsFormat": "american",
        "date": query_ts,
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            print(f"  Historical API {r.status_code} for {game_id}", flush=True)
            return {}, None
    except Exception as e:
        print(f"  Historical API error for {game_id}: {e}", flush=True)
        return {}, None

    data = r.json()
    snapshot_ts = data.get("timestamp")
    event_data = data.get("data", {})
    bookmakers = event_data.get("bookmakers", []) if isinstance(event_data, dict) else []

    if not bookmakers:
        print(f"  No bookmakers in historical response for {game_id}", flush=True)
        return {}, snapshot_ts

    # Build closing price lookup: best price across books per (player, market, line)
    closes = {}  # (player_lower, market, point) -> {over: price, under: price}
    for bk in bookmakers:
        for mkt in bk.get("markets", []):
            mkt_key = mkt.get("key", "")
            for oc in mkt.get("outcomes", []):
                player = (oc.get("description") or "").lower().strip()
                point = oc.get("point")
                side = oc.get("name", "").lower()
                price = oc.get("price")
                if not player or point is None or price is None:
                    continue
                key = (player, mkt_key, float(point))
                if key not in closes:
                    closes[key] = {"over": np.nan, "under": np.nan}
                if side == "over":
                    if np.isnan(closes[key]["over"]) or price > closes[key]["over"]:
                        closes[key]["over"] = price
                elif side == "under":
                    if np.isnan(closes[key]["under"]) or price > closes[key]["under"]:
                        closes[key]["under"] = price

    time.sleep(0.5)
    return closes, snapshot_ts


def run(run_date=None):
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    print(f"WNBA CLV Runner | {run_date} | mode={RUN_MODE}", flush=True)

    pc_file = SHADOW_DIR / "prop_candidates.parquet"
    if not pc_file.exists():
        print("No prop_candidates.parquet. Exiting.", flush=True)
        return

    pc = pd.read_parquet(pc_file)
    today = pc[pc["game_date"] == run_date]
    if len(today) == 0:
        print(f"No props for {run_date}. Exiting.", flush=True)
        return

    print(f"  Candidates: {len(today)} props across {today['game_id'].nunique()} games", flush=True)

    clv_rows = []

    if RUN_MODE == "test":
        print("CLV stub mode — schema validated.", flush=True)
        np.random.seed(42)
        for _, r in today.iterrows():
            move = np.random.uniform(-10, 10)
            closing_over = r["best_over_odds"] + move if pd.notna(r["best_over_odds"]) else np.nan
            closing_under = r["best_under_odds"] - move if pd.notna(r["best_under_odds"]) else np.nan
            sel_side = r["selected_side"]
            if sel_side == "over":
                closing_sel = closing_over
                opening_sel = r["best_over_odds"]
            elif sel_side == "under":
                closing_sel = closing_under
                opening_sel = r["best_under_odds"]
            else:
                closing_sel = np.nan
                opening_sel = np.nan

            clv = opening_sel - closing_sel if pd.notna(opening_sel) and pd.notna(closing_sel) else np.nan
            beat = 1 if pd.notna(clv) and clv >= 0 else 0

            clv_rows.append({
                "player_id": r["player_id"], "player_name": r["player_name"],
                "game_id": r["game_id"], "game_date": run_date,
                "market": r["market"], "line": r["line"],
                "opening_over_odds": r["best_over_odds"],
                "closing_over_odds": round(closing_over, 1) if pd.notna(closing_over) else np.nan,
                "opening_under_odds": r["best_under_odds"],
                "closing_under_odds": round(closing_under, 1) if pd.notna(closing_under) else np.nan,
                "selected_side": sel_side,
                "selected_odds": opening_sel,
                "closing_odds_selected": round(closing_sel, 1) if pd.notna(closing_sel) else np.nan,
                "clv_selected": round(clv, 1) if pd.notna(clv) else np.nan,
                "beat_close": beat,
                "edge_at_open": r.get("selected_edge", np.nan),
                "classification": r.get("classification_over") if sel_side == "over" else r.get("classification_under"),
            })
    else:
        # Live mode — historical event-level endpoint per game
        has_commence = "commence_time" in today.columns and today["commence_time"].notna().any()
        if not has_commence:
            print("  WARNING: candidates missing commence_time — cannot query historical endpoint.", flush=True)
            print("  Skipping CLV capture. Re-run daily_runner in live mode first.", flush=True)
            return

        api_calls = 0
        matched = 0
        unmatched = 0

        for game_id, game_group in today.groupby("game_id"):
            ct = game_group["commence_time"].dropna().iloc[0] if game_group["commence_time"].notna().any() else None
            if not ct:
                print(f"  Game {game_id}: no commence_time, skipping", flush=True)
                continue

            closes, snapshot_ts = _fetch_historical_closing(game_id, ct)
            api_calls += 1

            if not closes:
                print(f"  Game {game_id}: no closing prices found", flush=True)
                continue

            home = game_group["home_team"].iloc[0]
            away = game_group["away_team"].iloc[0]
            print(f"  Game {game_id} ({away}@{home}): {len(closes)} closing lines, snapshot={snapshot_ts}", flush=True)

            for _, r in game_group.iterrows():
                player_lower = str(r["player_name"]).lower().strip()
                market = r["market"]
                line = float(r["line"])
                key = (player_lower, market, line)

                close_data = closes.get(key)
                if close_data is None:
                    unmatched += 1
                    continue

                closing_over = close_data.get("over", np.nan)
                closing_under = close_data.get("under", np.nan)

                sel_side = r["selected_side"]
                opening_sel = r.get("selected_odds", np.nan)
                if sel_side == "over":
                    closing_sel = closing_over
                elif sel_side == "under":
                    closing_sel = closing_under
                else:
                    closing_sel = np.nan

                clv = opening_sel - closing_sel if pd.notna(opening_sel) and pd.notna(closing_sel) else np.nan
                beat = 1 if pd.notna(clv) and clv >= 0 else 0

                clv_rows.append({
                    "player_id": r["player_id"], "player_name": r["player_name"],
                    "game_id": r["game_id"], "game_date": run_date,
                    "market": market, "line": line,
                    "opening_over_odds": r["best_over_odds"],
                    "closing_over_odds": closing_over if pd.notna(closing_over) else np.nan,
                    "opening_under_odds": r["best_under_odds"],
                    "closing_under_odds": closing_under if pd.notna(closing_under) else np.nan,
                    "selected_side": sel_side,
                    "selected_odds": opening_sel,
                    "closing_odds_selected": closing_sel if pd.notna(closing_sel) else np.nan,
                    "clv_selected": round(clv, 1) if pd.notna(clv) else np.nan,
                    "beat_close": beat,
                    "edge_at_open": r.get("selected_edge", np.nan),
                    "classification": r.get("classification_over") if sel_side == "over" else r.get("classification_under"),
                    "clv_source": "historical_event",
                    "historical_snapshot": snapshot_ts,
                })
                matched += 1

        print(f"  Historical API calls: {api_calls}", flush=True)
        print(f"  Matched: {matched}, Unmatched: {unmatched}", flush=True)

    if not clv_rows:
        print("No CLV rows to write.", flush=True)
        return

    clv_df = pd.DataFrame(clv_rows)
    clv_file = SHADOW_DIR / "clv_log.parquet"
    if clv_file.exists():
        existing = pd.read_parquet(clv_file)
        # Add new columns to existing if missing
        for col in clv_df.columns:
            if col not in existing.columns:
                existing[col] = np.nan
        for col in existing.columns:
            if col not in clv_df.columns:
                clv_df[col] = np.nan
        clv_df = pd.concat([existing, clv_df], ignore_index=True)
    clv_df.to_parquet(clv_file, index=False)
    print(f"CLV log: {len(clv_df)} total rows saved", flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(run_date=args.date)
