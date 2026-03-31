"""
Shared CLV (Closing Line Value) utilities.
Used by all shadow systems across MLB, NBA, NHL, Soccer.
"""

import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("ODDS_API_KEY", "")

SPORT_MAP = {
    "MLB": "baseball_mlb",
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "soccer_EPL": "soccer_epl",
    "soccer_BUN": "soccer_germany_bundesliga",
    "soccer_LGA": "soccer_spain_la_liga",
    "soccer_SEA": "soccer_italy_serie_a",
    "soccer_LG1": "soccer_france_ligue_one",
}

PROP_MARKET_MAP = {
    "HITS": "batter_hits",
    "TB": "batter_total_bases",
    "K": "pitcher_strikeouts",
    "POINTS": "player_points",
    "REBOUNDS": "player_rebounds",
    "ASSISTS": "player_assists",
    "THREES": "player_threes",
    "PRA": "player_points_rebounds_assists",
}

PREFERRED_BOOKS = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers"]


def american_to_implied(odds):
    """Convert American odds to implied probability."""
    if pd.isna(odds) or odds == 0:
        return np.nan
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def implied_to_american(prob):
    """Convert implied probability to American odds."""
    if pd.isna(prob) or prob <= 0 or prob >= 1:
        return np.nan
    if prob >= 0.5:
        return round(-(prob / (1 - prob)) * 100)
    else:
        return round(((1 - prob) / prob) * 100)


def compute_clv(decision_odds, closing_odds):
    """
    Compute CLV from decision odds and closing odds.

    Returns dict with:
        clv_raw: closing - decision (American odds points)
        clv_pct: implied_prob(closing) - implied_prob(decision)
        beat_close: True if you got better odds than close
        closing_odds: the closing odds value
    """
    if pd.isna(decision_odds) or pd.isna(closing_odds):
        return {
            "closing_odds": closing_odds if not pd.isna(closing_odds) else np.nan,
            "clv_raw": np.nan,
            "clv_pct": np.nan,
            "beat_close": np.nan,
            "closing_captured": False,
        }

    # For OVER bets: you want lower implied prob at close (line moved toward you)
    # CLV raw = closing_odds - decision_odds
    # If you bet at -150 and close is -170, clv_raw = -170 - (-150) = -20
    # That means the line moved against you (more juice at close)
    # Wait — actually for American odds:
    # If you bet OVER at -150 (implied 60%) and close is -170 (implied 63%),
    # the market agreed with you MORE at close → positive CLV
    # CLV should reflect: did the market move in your direction?

    imp_decision = american_to_implied(decision_odds)
    imp_closing = american_to_implied(closing_odds)

    if pd.isna(imp_decision) or pd.isna(imp_closing):
        return {
            "closing_odds": closing_odds,
            "clv_raw": np.nan,
            "clv_pct": np.nan,
            "beat_close": np.nan,
            "closing_captured": True,
        }

    # CLV pct: positive means closing implied was higher than decision implied
    # = market moved in your direction = you got value
    clv_pct = imp_closing - imp_decision

    # CLV raw in odds points
    clv_raw = float(closing_odds) - float(decision_odds)

    # Beat close: you got better (lower implied) price than the close
    # For OVER: decision_implied < closing_implied = beat the close
    beat_close = imp_decision < imp_closing

    return {
        "closing_odds": float(closing_odds),
        "clv_raw": round(clv_raw, 1),
        "clv_pct": round(clv_pct, 4),
        "beat_close": bool(beat_close),
        "closing_captured": True,
    }


def get_closing_odds(event_id, player_name, prop_type, sport, direction="OVER"):
    """
    Pull closing odds from The Odds API for a specific prop or game total.

    Returns dict with closing_odds, n_books, closing_timestamp.
    Returns None values if unavailable.
    """
    if not API_KEY:
        return {"closing_odds": np.nan, "n_books": 0, "closing_timestamp": None,
                "closing_captured": False, "error": "no_api_key"}

    sport_key = SPORT_MAP.get(sport, sport)
    market = PROP_MARKET_MAP.get(prop_type, prop_type)

    # For game totals (NHL, Soccer, MLB totals)
    if prop_type in ("totals", "TOTAL"):
        market = "totals"

    try:
        time.sleep(0.3)
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
        params = {
            "apiKey": API_KEY,
            "regions": "us",
            "markets": market,
            "oddsFormat": "american",
        }
        r = requests.get(url, params=params, timeout=15)

        if r.status_code != 200:
            return {"closing_odds": np.nan, "n_books": 0, "closing_timestamp": None,
                    "closing_captured": False, "error": f"status_{r.status_code}"}

        data = r.json()
        ts = datetime.now().isoformat()

        # Extract odds
        odds_list = []
        for bk in data.get("bookmakers", []):
            if bk["key"] not in PREFERRED_BOOKS:
                continue
            for mkt in bk.get("markets", []):
                if mkt["key"] != market:
                    continue

                if player_name:
                    # Player prop — match by description
                    for outcome in mkt.get("outcomes", []):
                        desc = outcome.get("description", "").lower()
                        if player_name.lower().split()[-1] in desc:
                            if outcome["name"].lower() == direction.lower():
                                odds_list.append(outcome.get("price"))
                else:
                    # Game total
                    for outcome in mkt.get("outcomes", []):
                        if outcome["name"].lower() == direction.lower():
                            odds_list.append(outcome.get("price"))

        odds_list = [o for o in odds_list if o is not None]

        if not odds_list:
            return {"closing_odds": np.nan, "n_books": 0, "closing_timestamp": ts,
                    "closing_captured": False, "error": "no_matching_outcomes"}

        # Best closing odds (most favorable for bettor)
        if direction.upper() == "OVER":
            best = max(odds_list)  # highest odds = best for over
        else:
            best = max(odds_list)

        return {
            "closing_odds": float(best),
            "consensus_closing_odds": float(np.median(odds_list)),
            "n_books": len(odds_list),
            "closing_timestamp": ts,
            "closing_captured": True,
            "error": None,
        }

    except Exception as e:
        return {"closing_odds": np.nan, "n_books": 0, "closing_timestamp": None,
                "closing_captured": False, "error": str(e)}


def get_historical_closing_odds(event_id, game_date, sport, prop_type=None,
                                 player_name=None, direction="OVER"):
    """
    Pull historical closing odds from The Odds API historical endpoint.
    Used for backfilling CLV on already-played games.
    """
    if not API_KEY:
        return {"closing_odds": np.nan, "closing_captured": False}

    sport_key = SPORT_MAP.get(sport, sport)
    market = PROP_MARKET_MAP.get(prop_type, "totals") if prop_type else "totals"

    # Query at approximately game time (8pm ET = midnight UTC)
    query_date = f"{game_date}T20:00:00Z"

    try:
        time.sleep(0.3)
        url = f"https://api.the-odds-api.com/v4/historical/sports/{sport_key}/events/{event_id}/odds"
        params = {
            "apiKey": API_KEY,
            "date": query_date,
            "regions": "us",
            "markets": market,
            "oddsFormat": "american",
        }
        r = requests.get(url, params=params, timeout=15)

        if r.status_code != 200:
            return {"closing_odds": np.nan, "closing_captured": False}

        data = r.json()
        odds_data = data.get("data", {})

        odds_list = []
        for bk in odds_data.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt["key"] != market:
                    continue
                if player_name:
                    for outcome in mkt.get("outcomes", []):
                        desc = outcome.get("description", "").lower()
                        if player_name.lower().split()[-1] in desc:
                            if outcome["name"].lower() == direction.lower():
                                odds_list.append(outcome.get("price"))
                else:
                    for outcome in mkt.get("outcomes", []):
                        if outcome["name"].lower() == direction.lower():
                            odds_list.append(outcome.get("price"))

        odds_list = [o for o in odds_list if o is not None]

        if not odds_list:
            return {"closing_odds": np.nan, "closing_captured": False}

        best = max(odds_list)
        return {
            "closing_odds": float(best),
            "n_books": len(odds_list),
            "closing_captured": True,
        }

    except Exception:
        return {"closing_odds": np.nan, "closing_captured": False}


def add_clv_columns(df):
    """Add CLV columns to a DataFrame if they don't exist. Backfill with NaN."""
    clv_cols = {
        "closing_odds": np.nan,
        "clv_raw": np.nan,
        "clv_pct": np.nan,
        "beat_close": np.nan,
        "closing_captured": False,
    }
    for col, default in clv_cols.items():
        if col not in df.columns:
            df[col] = default
    return df


def clv_summary(df, label=""):
    """Print CLV summary for a shadow DataFrame."""
    has_clv = df[df["closing_captured"] == True] if "closing_captured" in df.columns else pd.DataFrame()

    print(f"\n  CLV SUMMARY{' — ' + label if label else ''}:")
    if len(has_clv) == 0:
        print("    No plays with closing line captured yet.")
        return

    n = len(has_clv)
    beat = has_clv["beat_close"].sum() if "beat_close" in has_clv.columns else 0
    avg_raw = has_clv["clv_raw"].mean() if "clv_raw" in has_clv.columns else np.nan
    avg_pct = has_clv["clv_pct"].mean() if "clv_pct" in has_clv.columns else np.nan

    print(f"    Plays with CLV: {n}")
    print(f"    Beat the close: {int(beat)} ({beat/n*100:.1f}%)")
    if not pd.isna(avg_raw):
        print(f"    Avg CLV (raw): {avg_raw:+.1f} odds points")
    if not pd.isna(avg_pct):
        print(f"    Avg CLV (pct): {avg_pct:+.2%}")

    # CLV vs outcome
    if "result_outcome" in has_clv.columns or "bet_win" in has_clv.columns:
        win_col = "result_outcome" if "result_outcome" in has_clv.columns else "bet_win"
        if win_col == "result_outcome":
            wins = has_clv[has_clv[win_col] == "WIN"]
            losses = has_clv[has_clv[win_col] == "LOSS"]
        else:
            wins = has_clv[has_clv[win_col] == 1]
            losses = has_clv[has_clv[win_col] == 0]

        if "beat_close" in has_clv.columns:
            clv_pos = has_clv[has_clv["beat_close"] == True]
            clv_neg = has_clv[has_clv["beat_close"] == False]

            print(f"\n    CLV vs Outcome:")
            print(f"      CLV+ & WIN:  {len(clv_pos[clv_pos.index.isin(wins.index)])}")
            print(f"      CLV+ & LOSS: {len(clv_pos[clv_pos.index.isin(losses.index)])}")
            print(f"      CLV- & WIN:  {len(clv_neg[clv_neg.index.isin(wins.index)])}")
            print(f"      CLV- & LOSS: {len(clv_neg[clv_neg.index.isin(losses.index)])}")

    # Coverage
    total = len(df)
    print(f"\n    Closing line coverage: {n}/{total} ({n/total*100:.1f}%)")
