#!/usr/bin/env python3
"""
MLB Sides Daily Shadow — night_dog + bp_adv_dog overlays
Phase 7 operational shadow deployment.

Usage:
    python3 mlb/pipeline/mlb_sides_daily_shadow.py --date 2026-04-12
    python3 mlb/pipeline/mlb_sides_daily_shadow.py --grade
    python3 mlb/pipeline/mlb_sides_daily_shadow.py --summary
"""

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# ─── PATHS ───────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

GT_PATH = os.path.join(ROOT, "sim", "data", "game_table.parquet")
PGL_PATH = os.path.join(ROOT, "mlb", "data", "pitcher_game_logs.parquet")
CANON_ODDS_PATH = os.path.join(ROOT, "mlb_sim", "data", "mlb_odds_closing_canonical.parquet")
LOG_DIR = os.path.join(ROOT, "mlb", "logs")

TRACKER_NIGHT = os.path.join(LOG_DIR, "mlb_mixed_night_dog_shadow_2026.json")
TRACKER_BP = os.path.join(LOG_DIR, "mlb_mixed_bp_adv_dog_shadow_2026.json")

os.makedirs(LOG_DIR, exist_ok=True)

# ─── FROZEN DISCOVERY THRESHOLDS (2022-2023 p50) ────────────
MIXED_THRESHOLDS = {
    "sp_fip_diff_median": 0.814,   # p50 of |SP FIP diff| in discovery
    "off_diff_median": 0.800,      # p50 of |offense R20 diff| in discovery
    "bp_era_diff_median": 0.583,   # p50 of |BP ERA diff| in discovery
}

# ─── TEAM ABBREVIATION MAPS ─────────────────────────────────
PGL_TO_GT = {
    "AZ": "ARI", "CWS": "CHW", "KC": "KCR", "SD": "SDP",
    "SF": "SFG", "TB": "TBR", "WSH": "WSN", "ATH": "OAK",
}

ODDS_API_TEAM_MAP = {
    "Los Angeles Angels": "LAA", "Arizona Diamondbacks": "ARI",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU",
    "Kansas City Royals": "KCR", "Los Angeles Dodgers": "LAD",
    "Washington Nationals": "WSN", "New York Mets": "NYM",
    "Oakland Athletics": "OAK", "Athletics": "OAK",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SDP",
    "Seattle Mariners": "SEA", "San Francisco Giants": "SFG",
    "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TBR",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR",
    "Minnesota Twins": "MIN", "Philadelphia Phillies": "PHI",
    "Atlanta Braves": "ATL", "Chicago White Sox": "CHW",
    "Miami Marlins": "MIA", "New York Yankees": "NYY",
    "Milwaukee Brewers": "MIL",
}

# MLB Stats API team ID -> abbreviation (PGL-style)
MLB_ID_TO_ABB = {
    133: "ATH", 134: "PIT", 135: "SD", 136: "SEA", 137: "SF",
    138: "STL", 139: "TB", 140: "TEX", 141: "TOR", 142: "MIN",
    143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA", 147: "NYY",
    158: "MIL", 108: "LAA", 109: "AZ", 110: "BAL", 111: "BOS",
    112: "CHC", 113: "CIN", 114: "CLE", 115: "COL", 116: "DET",
    117: "HOU", 118: "KC", 119: "LAD", 120: "WSH", 121: "NYM",
}

# Timezone for local hour computation
TEAM_TZ = {
    "LAA": "America/Los_Angeles", "LAD": "America/Los_Angeles",
    "SDP": "America/Los_Angeles", "SFG": "America/Los_Angeles",
    "OAK": "America/Los_Angeles", "SEA": "America/Los_Angeles",
    "ARI": "America/Phoenix",
    "COL": "America/Denver",
    "TEX": "America/Chicago", "HOU": "America/Chicago",
    "KCR": "America/Chicago", "MIN": "America/Chicago",
    "MIL": "America/Chicago", "CHC": "America/Chicago",
    "CHW": "America/Chicago", "STL": "America/Chicago",
    "CIN": "America/New_York", "CLE": "America/New_York",
    "DET": "America/New_York", "PIT": "America/New_York",
    "ATL": "America/New_York", "MIA": "America/New_York",
    "TBR": "America/New_York", "BAL": "America/New_York",
    "BOS": "America/New_York", "NYM": "America/New_York",
    "NYY": "America/New_York", "PHI": "America/New_York",
    "TOR": "America/New_York", "WSN": "America/New_York",
}


def pgl_to_gt(team: str) -> str:
    return PGL_TO_GT.get(team, team)


# ─── MLB STATS API ───────────────────────────────────────────
MLB_API = "https://statsapi.mlb.com/api/v1"


def fetch_schedule(target_date: str) -> list:
    """Fetch MLB schedule for a date. Returns list of game dicts."""
    url = f"{MLB_API}/schedule?sportId=1&date={target_date}&hydrate=probablePitcher,linescore"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ERROR] Schedule fetch failed: {e}")
        return []
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if g.get("status", {}).get("detailedState") in ("Postponed", "Cancelled", "Suspended"):
                continue
            home_id = g["teams"]["home"]["team"]["id"]
            away_id = g["teams"]["away"]["team"]["id"]
            home_raw = MLB_ID_TO_ABB.get(home_id, str(home_id))
            away_raw = MLB_ID_TO_ABB.get(away_id, str(away_id))
            # Normalize to GT standard
            home = PGL_TO_GT.get(home_raw, home_raw)
            away = PGL_TO_GT.get(away_raw, away_raw)
            game_pk = g["gamePk"]
            game_dt = g.get("gameDate", "")  # UTC ISO
            # Probable pitchers
            pp_home = g["teams"]["home"].get("probablePitcher", {})
            pp_away = g["teams"]["away"].get("probablePitcher", {})
            # Compute local start hour
            local_hour = None
            if game_dt:
                try:
                    from zoneinfo import ZoneInfo
                    utc_dt = datetime.fromisoformat(game_dt.replace("Z", "+00:00"))
                    tz_name = TEAM_TZ.get(home, "America/New_York")
                    local_dt = utc_dt.astimezone(ZoneInfo(tz_name))
                    local_hour = local_dt.hour + local_dt.minute / 60.0
                except Exception:
                    pass
            # Day/night classification
            day_night = "night" if (local_hour is not None and local_hour >= 17) else "day"
            games.append({
                "game_pk": game_pk,
                "date": target_date,
                "home_team": home,
                "away_team": away,
                "local_start_hour": local_hour,
                "day_night": day_night,
                "home_sp_id": pp_home.get("id"),
                "home_sp_name": pp_home.get("fullName", "TBD"),
                "away_sp_id": pp_away.get("id"),
                "away_sp_name": pp_away.get("fullName", "TBD"),
            })
    return games


def fetch_game_results(game_pk: int) -> Optional[dict]:
    """Fetch final score for a completed game."""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    gd = data.get("gameData", {})
    status = gd.get("status", {}).get("detailedState", "")
    if status != "Final":
        return None
    ls = data.get("liveData", {}).get("linescore", {})
    home_runs = ls.get("teams", {}).get("home", {}).get("runs")
    away_runs = ls.get("teams", {}).get("away", {}).get("runs")
    if home_runs is None or away_runs is None:
        return None
    return {"home_score": home_runs, "away_score": away_runs}


# ─── ODDS API — ML LINES ────────────────────────────────────
def fetch_ml_lines(target_date: str) -> dict:
    """
    Fetch moneyline odds from The Odds API for a given date.
    Returns dict keyed by (home_team_gt, away_team_gt) with ml prices + implied probs.
    Falls back to canon if available for historical dates.
    """
    result = {}
    
    # Try canonical odds first for historical dates
    target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
    if os.path.exists(CANON_ODDS_PATH) and target_dt <= date(2025, 9, 30):
        canon = pd.read_parquet(CANON_ODDS_PATH)
        canon_day = canon[canon["date"] == target_date]
        if len(canon_day) > 0:
            # Use DK first, then FD
            dk = canon_day[canon_day["book_key"] == "draftkings"].sort_values("pull_timestamp").drop_duplicates(
                "game_pk", keep="last")
            fd = canon_day[canon_day["book_key"] == "fanduel"].sort_values("pull_timestamp").drop_duplicates(
                "game_pk", keep="last")
            merged = pd.concat([dk, fd[~fd["game_pk"].isin(dk["game_pk"])]], ignore_index=True)
            for _, row in merged.iterrows():
                key = (row["home_team"], row["away_team"])
                result[key] = {
                    "ml_home_price": row["ml_home_price"],
                    "ml_away_price": row["ml_away_price"],
                    "ml_home_implied": row["ml_home_implied"],
                    "ml_away_implied": row["ml_away_implied"],
                    "game_pk": row.get("game_pk"),
                }
            if result:
                return result

    # Live fetch from Odds API for current/recent dates
    api_key = os.environ.get("ODDS_API_KEY", "")
    if not api_key:
        try:
            from config import ODDS_API_KEY
            api_key = ODDS_API_KEY
        except ImportError:
            pass
    if not api_key:
        print("[WARN] No ODDS_API_KEY — cannot fetch live ML lines")
        return result
    
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h",
        "bookmakers": "pinnacle,draftkings,fanduel",
        "oddsFormat": "american",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        events = r.json()
    except Exception as e:
        print(f"[WARN] Odds API ML fetch failed: {e}")
        return result
    
    for ev in events:
        commence = ev.get("commence_time", "")[:10]
        if commence != target_date:
            continue
        ht_full = ev.get("home_team", "")
        at_full = ev.get("away_team", "")
        ht = ODDS_API_TEAM_MAP.get(ht_full, ht_full)
        at = ODDS_API_TEAM_MAP.get(at_full, at_full)
        
        # Find best book (pinnacle > DK > FD)
        for bm in ev.get("bookmakers", []):
            bk = bm.get("key", "")
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in mkt.get("outcomes", [])}
                home_price = outcomes.get(ht_full)
                away_price = outcomes.get(at_full)
                if home_price is not None and away_price is not None:
                    home_imp = _american_to_implied(home_price)
                    away_imp = _american_to_implied(away_price)
                    # Normalize to remove vig
                    total_imp = home_imp + away_imp
                    if total_imp > 0:
                        home_imp /= total_imp
                        away_imp /= total_imp
                    key = (ht, at)
                    if key not in result or bk == "pinnacle":
                        result[key] = {
                            "ml_home_price": home_price,
                            "ml_away_price": away_price,
                            "ml_home_implied": home_imp,
                            "ml_away_implied": away_imp,
                            "book": bk,
                        }
                        if bk == "pinnacle":
                            break
    return result


def _american_to_implied(price: float) -> float:
    if price >= 100:
        return 100.0 / (price + 100.0)
    else:
        return abs(price) / (abs(price) + 100.0)


# ─── FEATURE COMPUTATION ────────────────────────────────────

def compute_sp_fip_rolling(pgl: pd.DataFrame, target_date: str) -> pd.DataFrame:
    """
    Compute rolling PIT-safe SP FIP for each pitcher as of target_date.
    Returns DataFrame with columns: [player_id, team_gt, sp_fip]
    """
    sp = pgl[pgl["starter_flag"] == 1].copy()
    sp["team_gt"] = sp["team"].map(pgl_to_gt)
    sp = sp[sp["game_date"] < target_date].sort_values(["player_id", "game_date"])
    
    # Expanding cumulative stats per pitcher (all seasons, no season boundary)
    agg = sp.groupby("player_id").agg(
        cum_er=("earned_runs", "sum"),
        cum_ip=("innings_pitched", "sum"),
        cum_k=("strikeouts", "sum"),
        cum_bb=("walks", "sum"),
        cum_hr=("home_runs_allowed", "sum"),
        team_gt=("team_gt", "last"),
        player_name=("player_name", "last"),
    ).reset_index()
    
    agg["sp_fip"] = np.where(
        agg["cum_ip"] >= 10,
        (13 * agg["cum_hr"] + 3 * agg["cum_bb"] - 2 * agg["cum_k"]) / agg["cum_ip"] + 3.10,
        np.nan
    )
    return agg[["player_id", "team_gt", "player_name", "sp_fip"]].dropna(subset=["sp_fip"])


def compute_bp_era_rolling(pgl: pd.DataFrame, target_date: str) -> pd.DataFrame:
    """
    Compute rolling PIT-safe BP ERA per team as of target_date.
    PIT-safe: shift(1).expanding() per team within each season, then use latest.
    Returns DataFrame with columns: [team_gt, bp_era]
    """
    bp = pgl[pgl["starter_flag"] == 0].copy()
    bp["team_gt"] = bp["team"].map(pgl_to_gt)
    bp = bp[bp["game_date"] < target_date].copy()
    
    # Aggregate per team per game
    bp_game = bp.groupby(["team_gt", "game_date"]).agg(
        bp_er=("earned_runs", "sum"),
        bp_ip=("innings_pitched", "sum"),
    ).reset_index().sort_values(["team_gt", "game_date"])
    
    # Expanding cumulative
    bp_game["cum_er"] = bp_game.groupby("team_gt")["bp_er"].transform(
        lambda x: x.shift(1).expanding().sum())
    bp_game["cum_ip"] = bp_game.groupby("team_gt")["bp_ip"].transform(
        lambda x: x.shift(1).expanding().sum())
    bp_game["bp_era"] = np.where(
        bp_game["cum_ip"] >= 10,
        bp_game["cum_er"] / bp_game["cum_ip"] * 9,
        np.nan)
    
    # Get latest value per team
    latest = bp_game.dropna(subset=["bp_era"]).sort_values("game_date").drop_duplicates(
        "team_gt", keep="last")
    return latest[["team_gt", "bp_era"]]


def compute_offense_r20(gt: pd.DataFrame, target_date: str) -> pd.DataFrame:
    """
    Compute rolling 20-game offense (runs/game) per team as of target_date.
    PIT-safe: shift(1).rolling(20, min_periods=10).
    Returns DataFrame with columns: [team, off_r20]
    """
    home_g = gt[["game_pk", "date", "home_team", "home_score"]].rename(
        columns={"home_team": "team", "home_score": "runs"})
    away_g = gt[["game_pk", "date", "away_team", "away_score"]].rename(
        columns={"away_team": "team", "away_score": "runs"})
    tg = pd.concat([home_g, away_g]).sort_values(["team", "date"])
    tg = tg[tg["date"] < target_date].copy()
    
    tg["off_r20"] = tg.groupby("team")["runs"].transform(
        lambda x: x.shift(1).rolling(20, min_periods=10).mean())
    
    latest = tg.dropna(subset=["off_r20"]).sort_values("date").drop_duplicates(
        "team", keep="last")
    return latest[["team", "off_r20"]]


def classify_mixed(sp_fip_diff: float, off_diff: float, bp_era_diff: float) -> bool:
    """Check if all three gaps are below frozen discovery medians."""
    return (
        abs(sp_fip_diff) < MIXED_THRESHOLDS["sp_fip_diff_median"]
        and abs(off_diff) < MIXED_THRESHOLDS["off_diff_median"]
        and abs(bp_era_diff) < MIXED_THRESHOLDS["bp_era_diff_median"]
    )


# ─── MAIN DAILY PIPELINE ────────────────────────────────────

def run_daily(target_date: str):
    """Run the daily shadow pipeline for a given date."""
    print(f"\n{'='*60}")
    print(f"  MLB SIDES SHADOW — {target_date}")
    print(f"{'='*60}\n")
    
    # 1. Load schedule
    games = fetch_schedule(target_date)
    if not games:
        print("[INFO] No games found for", target_date)
        return
    print(f"[1] Schedule: {len(games)} games")
    for g in games:
        print(f"    {g['away_team']} @ {g['home_team']} — {g['day_night']} "
              f"(local={g['local_start_hour']:.1f}h)" if g['local_start_hour'] else
              f"    {g['away_team']} @ {g['home_team']} — {g['day_night']}")
    
    # 2. Load ML odds
    ml_lines = fetch_ml_lines(target_date)
    print(f"\n[2] ML lines: {len(ml_lines)} games matched")
    
    # 3. Load feature data
    pgl = pd.read_parquet(PGL_PATH)
    gt = pd.read_parquet(GT_PATH)
    
    sp_fip_df = compute_sp_fip_rolling(pgl, target_date)
    bp_era_df = compute_bp_era_rolling(pgl, target_date)
    off_r20_df = compute_offense_r20(gt, target_date)
    
    print(f"\n[3] Features loaded:")
    print(f"    SP FIP: {len(sp_fip_df)} pitchers")
    print(f"    BP ERA: {len(bp_era_df)} teams")
    print(f"    Off R20: {len(off_r20_df)} teams")
    
    # 4. Process each game
    night_dog_signals = []
    bp_adv_dog_signals = []
    all_games_detail = []
    
    print(f"\n[4] Game-by-game analysis:")
    print(f"{'─'*80}")
    
    for g in games:
        home = g["home_team"]
        away = g["away_team"]
        game_pk = g["game_pk"]
        day_night = g["day_night"]
        
        # ML odds
        key = (home, away)
        odds = ml_lines.get(key, {})
        if not odds:
            print(f"  {away} @ {home}: NO ML LINES — skipped")
            all_games_detail.append({**g, "status": "no_lines"})
            continue
        
        ml_home_imp = odds.get("ml_home_implied", 0)
        ml_away_imp = odds.get("ml_away_implied", 0)
        ml_home_price = odds.get("ml_home_price")
        ml_away_price = odds.get("ml_away_price")
        
        # Close-game filter: fav implied 0.512-0.556
        fav_imp = max(ml_home_imp, ml_away_imp)
        if fav_imp < 0.512 or fav_imp > 0.556:
            tag = f"fav_imp={fav_imp:.3f}" if fav_imp > 0 else "no_imp"
            print(f"  {away} @ {home}: NOT CLOSE ({tag}) — skipped")
            all_games_detail.append({**g, "status": "not_close", "fav_implied": fav_imp})
            continue
        
        fav_side = "home" if ml_home_imp > ml_away_imp else "away"
        fav_team = home if fav_side == "home" else away
        dog_team = away if fav_side == "home" else home
        fav_ml = ml_home_price if fav_side == "home" else ml_away_price
        dog_ml = ml_away_price if fav_side == "home" else ml_home_price
        
        # SP FIP
        home_sp_fip = sp_fip_df[sp_fip_df["player_id"] == g.get("home_sp_id")]
        away_sp_fip = sp_fip_df[sp_fip_df["player_id"] == g.get("away_sp_id")]
        h_fip = home_sp_fip["sp_fip"].values[0] if len(home_sp_fip) > 0 else None
        a_fip = away_sp_fip["sp_fip"].values[0] if len(away_sp_fip) > 0 else None
        
        if h_fip is None or a_fip is None:
            print(f"  {away} @ {home}: MISSING SP FIP "
                  f"(H={'%.2f'%h_fip if h_fip else 'N/A'}, A={'%.2f'%a_fip if a_fip else 'N/A'}) — skipped")
            all_games_detail.append({**g, "status": "missing_sp_fip", "fav_implied": fav_imp})
            continue
        
        fav_sp = h_fip if fav_side == "home" else a_fip
        dog_sp = a_fip if fav_side == "home" else h_fip
        sp_diff = fav_sp - dog_sp
        
        # BP ERA
        home_bp = bp_era_df[bp_era_df["team_gt"] == home]
        away_bp = bp_era_df[bp_era_df["team_gt"] == away]
        h_bp = home_bp["bp_era"].values[0] if len(home_bp) > 0 else None
        a_bp = away_bp["bp_era"].values[0] if len(away_bp) > 0 else None
        
        if h_bp is None or a_bp is None:
            print(f"  {away} @ {home}: MISSING BP ERA — skipped")
            all_games_detail.append({**g, "status": "missing_bp_era", "fav_implied": fav_imp})
            continue
        
        fav_bp = h_bp if fav_side == "home" else a_bp
        dog_bp = a_bp if fav_side == "home" else h_bp
        bp_diff = fav_bp - dog_bp
        
        # Offense R20
        home_off = off_r20_df[off_r20_df["team"] == home]
        away_off = off_r20_df[off_r20_df["team"] == away]
        h_off = home_off["off_r20"].values[0] if len(home_off) > 0 else None
        a_off = away_off["off_r20"].values[0] if len(away_off) > 0 else None
        
        if h_off is None or a_off is None:
            print(f"  {away} @ {home}: MISSING OFFENSE — skipped")
            all_games_detail.append({**g, "status": "missing_offense", "fav_implied": fav_imp})
            continue
        
        fav_off = h_off if fav_side == "home" else a_off
        dog_off = a_off if fav_side == "home" else h_off
        off_diff = fav_off - dog_off
        
        # MIXED classification
        is_mixed = classify_mixed(sp_diff, off_diff, bp_diff)
        
        detail = {
            **g,
            "status": "processed",
            "fav_side": fav_side, "fav_team": fav_team, "dog_team": dog_team,
            "fav_implied": fav_imp,
            "fav_ml_price": fav_ml, "dog_ml_price": dog_ml,
            "fav_sp_fip": round(fav_sp, 3), "dog_sp_fip": round(dog_sp, 3),
            "sp_fip_diff": round(sp_diff, 3),
            "fav_off_r20": round(fav_off, 3), "dog_off_r20": round(dog_off, 3),
            "off_diff": round(off_diff, 3),
            "fav_bp_era": round(fav_bp, 3), "dog_bp_era": round(dog_bp, 3),
            "bp_era_diff": round(bp_diff, 3),
            "is_mixed": is_mixed,
        }
        all_games_detail.append(detail)
        
        mixed_tag = "MIXED" if is_mixed else "NOT-MIXED"
        print(f"\n  {away} @ {home} | fav={fav_team} ({fav_imp:.3f}) | {mixed_tag} | {day_night}")
        print(f"    SP FIP:  fav={fav_sp:.2f}  dog={dog_sp:.2f}  diff={sp_diff:+.3f}  "
              f"(thresh={MIXED_THRESHOLDS['sp_fip_diff_median']:.3f})")
        print(f"    OFF R20: fav={fav_off:.2f}  dog={dog_off:.2f}  diff={off_diff:+.3f}  "
              f"(thresh={MIXED_THRESHOLDS['off_diff_median']:.3f})")
        print(f"    BP ERA:  fav={fav_bp:.2f}  dog={dog_bp:.2f}  diff={bp_diff:+.3f}  "
              f"(thresh={MIXED_THRESHOLDS['bp_era_diff_median']:.3f})")
        
        if not is_mixed:
            reasons = []
            if abs(sp_diff) >= MIXED_THRESHOLDS["sp_fip_diff_median"]:
                reasons.append(f"|SP|={abs(sp_diff):.3f}>=thresh")
            if abs(off_diff) >= MIXED_THRESHOLDS["off_diff_median"]:
                reasons.append(f"|OFF|={abs(off_diff):.3f}>=thresh")
            if abs(bp_diff) >= MIXED_THRESHOLDS["bp_era_diff_median"]:
                reasons.append(f"|BP|={abs(bp_diff):.3f}>=thresh")
            print(f"    → NOT MIXED because: {', '.join(reasons)}")
            continue
        
        # ── NIGHT_DOG overlay ──
        if day_night == "night":
            sig = {
                "game_pk": game_pk,
                "game_date": target_date,
                "matchup": f"{away} @ {home}",
                "fav_team": fav_team,
                "dog_team": dog_team,
                "fav_side": fav_side,
                "fav_implied": round(fav_imp, 4),
                "dog_ml_price": dog_ml,
                "sp_fip_diff": round(sp_diff, 3),
                "off_diff": round(off_diff, 3),
                "bp_era_diff": round(bp_diff, 3),
                "day_night": day_night,
                "local_start_hour": g["local_start_hour"],
                "win_loss": None,
            }
            night_dog_signals.append(sig)
            print(f"    ★ NIGHT_DOG FIRES → back {dog_team} at {dog_ml}")
        else:
            print(f"    → night_dog: NO (day game)")
        
        # ── BP_ADV_DOG overlay ──
        if bp_diff > 0:  # fav BP ERA > dog BP ERA → dog has better bullpen
            sig = {
                "game_pk": game_pk,
                "game_date": target_date,
                "matchup": f"{away} @ {home}",
                "fav_team": fav_team,
                "dog_team": dog_team,
                "fav_side": fav_side,
                "fav_implied": round(fav_imp, 4),
                "dog_ml_price": dog_ml,
                "sp_fip_diff": round(sp_diff, 3),
                "off_diff": round(off_diff, 3),
                "bp_era_diff": round(bp_diff, 3),
                "fav_bp_era": round(fav_bp, 3),
                "dog_bp_era": round(dog_bp, 3),
                "win_loss": None,
            }
            bp_adv_dog_signals.append(sig)
            print(f"    ★ BP_ADV_DOG FIRES → back {dog_team} at {dog_ml} "
                  f"(fav_bp={fav_bp:.3f} > dog_bp={dog_bp:.3f})")
        else:
            print(f"    → bp_adv_dog: NO (dog BP ERA {dog_bp:.3f} >= fav BP ERA {fav_bp:.3f})")
    
    # 5. Summary
    print(f"\n{'='*60}")
    print(f"  SIGNAL SUMMARY — {target_date}")
    print(f"{'='*60}")
    n_processed = sum(1 for d in all_games_detail if d.get("status") == "processed")
    n_mixed = sum(1 for d in all_games_detail if d.get("is_mixed"))
    print(f"  Games on slate:     {len(games)}")
    print(f"  Fully processed:    {n_processed}")
    print(f"  MIXED class:        {n_mixed}")
    print(f"  night_dog signals:  {len(night_dog_signals)}")
    print(f"  bp_adv_dog signals: {len(bp_adv_dog_signals)}")
    
    # Check overlap
    night_pks = {s["game_pk"] for s in night_dog_signals}
    bp_pks = {s["game_pk"] for s in bp_adv_dog_signals}
    overlap = night_pks & bp_pks
    if overlap:
        print(f"  OVERLAP (both fire): {len(overlap)} games")
        for pk in overlap:
            ns = [s for s in night_dog_signals if s["game_pk"] == pk][0]
            print(f"    {ns['matchup']}")
    
    # 6. Save to trackers
    _save_signals(TRACKER_NIGHT, "mlb_mixed_night_dog_v1", night_dog_signals)
    _save_signals(TRACKER_BP, "mlb_mixed_bp_adv_dog_v1", bp_adv_dog_signals)
    
    return all_games_detail


def _save_signals(tracker_path: str, object_id: str, new_signals: list):
    """Append new signals to tracker, avoiding duplicates by game_pk."""
    if os.path.exists(tracker_path):
        with open(tracker_path) as f:
            tracker = json.load(f)
    else:
        tracker = {
            "object_id": object_id,
            "ruleset_version": "frozen_v1",
            "start_date": "2026-04-12",
            "signals": [],
        }
    
    existing_pks = {s["game_pk"] for s in tracker["signals"]}
    added = 0
    for sig in new_signals:
        if sig["game_pk"] not in existing_pks:
            tracker["signals"].append(sig)
            added += 1
    
    with open(tracker_path, "w") as f:
        json.dump(tracker, f, indent=2)
    print(f"  [{object_id}] Saved: +{added} new signals (total={len(tracker['signals'])})")


# ─── GRADE MODE ──────────────────────────────────────────────

def run_grade():
    """Grade ungraded signals from both trackers."""
    print(f"\n{'='*60}")
    print(f"  GRADING UNGRADED SIGNALS")
    print(f"{'='*60}\n")
    
    today = date.today().isoformat()
    
    for tracker_path, label in [(TRACKER_NIGHT, "night_dog"), (TRACKER_BP, "bp_adv_dog")]:
        if not os.path.exists(tracker_path):
            print(f"  [{label}] No tracker file found")
            continue
        
        with open(tracker_path) as f:
            tracker = json.load(f)
        
        ungraded = [s for s in tracker["signals"]
                     if s.get("win_loss") is None and s["game_date"] < today]
        print(f"  [{label}] {len(ungraded)} ungraded signals")
        
        graded = 0
        for sig in ungraded:
            result = fetch_game_results(sig["game_pk"])
            if result is None:
                print(f"    {sig['matchup']} ({sig['game_date']}): game not final")
                continue
            
            home_score = result["home_score"]
            away_score = result["away_score"]
            
            # Dog wins?
            if sig["fav_side"] == "home":
                dog_won = away_score > home_score
            else:
                dog_won = home_score > away_score
            
            sig["win_loss"] = "W" if dog_won else "L"
            sig["final_score"] = f"{result['away_score']}-{result['home_score']}"
            graded += 1
            wl = sig["win_loss"]
            print(f"    {sig['matchup']} ({sig['game_date']}): {wl} "
                  f"(score: {sig['final_score']}, dog={sig['dog_team']})")
        
        with open(tracker_path, "w") as f:
            json.dump(tracker, f, indent=2)
        print(f"  [{label}] Graded {graded} signals\n")


# ─── SUMMARY MODE ────────────────────────────────────────────

def run_summary():
    """Print cumulative shadow performance for both objects."""
    print(f"\n{'='*60}")
    print(f"  MLB SIDES SHADOW — CUMULATIVE SUMMARY")
    print(f"{'='*60}\n")
    
    for tracker_path, label in [(TRACKER_NIGHT, "night_dog"), (TRACKER_BP, "bp_adv_dog")]:
        if not os.path.exists(tracker_path):
            print(f"  [{label}] No tracker file")
            continue
        
        with open(tracker_path) as f:
            tracker = json.load(f)
        
        signals = tracker["signals"]
        n_total = len(signals)
        graded = [s for s in signals if s.get("win_loss") is not None]
        n_graded = len(graded)
        n_ungraded = n_total - n_graded
        
        wins = sum(1 for s in graded if s["win_loss"] == "W")
        losses = n_graded - wins
        
        # ROI computation (flat $100 on dog ML)
        total_profit = 0
        for s in graded:
            dog_price = s.get("dog_ml_price", 100)
            if s["win_loss"] == "W":
                if dog_price >= 100:
                    total_profit += dog_price
                else:
                    total_profit += 10000 / abs(dog_price)
            else:
                total_profit -= 100
        
        roi = total_profit / (n_graded * 100) * 100 if n_graded > 0 else 0
        win_pct = wins / n_graded * 100 if n_graded > 0 else 0
        
        print(f"  ┌─ {label.upper()} ({tracker['object_id']}) ─────────────")
        print(f"  │ Total signals:  {n_total}")
        print(f"  │ Graded:         {n_graded}")
        print(f"  │ Ungraded:       {n_ungraded}")
        print(f"  │ Record:         {wins}-{losses} ({win_pct:.1f}%)")
        print(f"  │ ROI:            {roi:+.1f}%")
        print(f"  │ Profit (units): {total_profit/100:+.2f}")
        
        # Kill switch check
        if n_graded >= 50 and roi < -15:
            print(f"  │ ⚠ KILL SWITCH: ROI < -15% after 50+ bets")
        # Promotion gate
        if n_graded >= 100 and roi > 0:
            print(f"  │ ✓ PROMOTION GATE: ROI > 0% after 100+ bets")
        
        print(f"  └{'─'*45}")
        
        # Recent signals
        if signals:
            print(f"\n  Recent signals:")
            for s in signals[-5:]:
                wl = s.get("win_loss", "?")
                score = s.get("final_score", "pending")
                print(f"    {s['game_date']} {s['matchup']} → {s['dog_team']} "
                      f"at {s['dog_ml_price']} | {wl} ({score})")
        print()


# ─── BP TRACE MODE ───────────────────────────────────────────

def trace_bp(signals: list, pgl: pd.DataFrame, n: int = 3):
    """Print detailed BP ERA trace for N bp_adv_dog signals."""
    print(f"\n{'='*60}")
    print(f"  BP ERA TRACE — {n} signals")
    print(f"{'='*60}\n")
    
    bp = pgl[pgl["starter_flag"] == 0].copy()
    bp["team_gt"] = bp["team"].map(pgl_to_gt)
    
    for sig in signals[:n]:
        gdate = sig["game_date"]
        fav = sig["fav_team"]
        dog = sig["dog_team"]
        print(f"  {sig['matchup']} ({gdate})")
        print(f"  Fav={fav}, Dog={dog}")
        
        for team, role in [(fav, "FAV"), (dog, "DOG")]:
            team_bp = bp[(bp["team_gt"] == team) & (bp["game_date"] < gdate)]
            bp_game = team_bp.groupby("game_date").agg(
                bp_er=("earned_runs", "sum"), bp_ip=("innings_pitched", "sum")
            ).reset_index().sort_values("game_date")
            
            cum_er = bp_game["bp_er"].shift(1).expanding().sum().iloc[-1] if len(bp_game) > 1 else 0
            cum_ip = bp_game["bp_ip"].shift(1).expanding().sum().iloc[-1] if len(bp_game) > 1 else 0
            era = cum_er / cum_ip * 9 if cum_ip >= 10 else float("nan")
            n_games = len(bp_game)
            
            print(f"    {role} ({team}): cum_ER={cum_er:.0f}, cum_IP={cum_ip:.1f}, "
                  f"BP_ERA={era:.3f}, games={n_games}")
            # Show last 3 game dates
            if len(bp_game) >= 3:
                last3 = bp_game.tail(3)
                for _, row in last3.iterrows():
                    print(f"      {row['game_date']}: ER={row['bp_er']:.0f} IP={row['bp_ip']:.1f}")
        
        print(f"    Reported: fav_bp={sig['fav_bp_era']:.3f}, dog_bp={sig['dog_bp_era']:.3f}, "
              f"diff={sig['bp_era_diff']:+.3f}")
        print()


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MLB Sides Daily Shadow")
    parser.add_argument("--date", type=str, default=date.today().isoformat(),
                        help="Target date (YYYY-MM-DD)")
    parser.add_argument("--grade", action="store_true", help="Grade ungraded signals")
    parser.add_argument("--summary", action="store_true", help="Print cumulative summary")
    parser.add_argument("--trace-bp", type=int, default=0,
                        help="Trace BP ERA for N bp_adv_dog signals from today's run")
    args = parser.parse_args()
    
    if args.grade:
        run_grade()
        return
    
    if args.summary:
        run_summary()
        return
    
    detail = run_daily(args.date)
    
    if args.trace_bp > 0 and os.path.exists(TRACKER_BP):
        with open(TRACKER_BP) as f:
            tracker = json.load(f)
        today_sigs = [s for s in tracker["signals"] if s["game_date"] == args.date]
        if today_sigs:
            pgl = pd.read_parquet(PGL_PATH)
            trace_bp(today_sigs, pgl, n=args.trace_bp)
        else:
            print(f"\n[trace-bp] No bp_adv_dog signals for {args.date}")


if __name__ == "__main__":
    main()
