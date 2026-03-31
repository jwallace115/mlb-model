#!/usr/bin/env python3
"""
MLB Props Shadow — HITS OVER Only
Automated daily collection, projection, grading for batter hits props.

Usage:
  python3 mlb/props_shadow.py --collect           # 9am: pull lines + project + card
  python3 mlb/props_shadow.py --refresh           # 5pm: re-pull lines
  python3 mlb/props_shadow.py --grade             # 7am next day: grade yesterday
  python3 mlb/props_shadow.py --hits-summary      # print summary
  python3 mlb/props_shadow.py --collect --date 2026-03-28
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
from scipy import stats as scipy_stats

load_dotenv(override=True)

_SCRIPT_DIR = Path(__file__).resolve().parent  # mlb/
PROJECT_ROOT = _SCRIPT_DIR.parent
SHADOW_DIR = _SCRIPT_DIR / "props" / "shadow"
RAW_DIR = SHADOW_DIR / "raw"
CARDS_DIR = SHADOW_DIR / "cards"
DATA_DIR = _SCRIPT_DIR / "data"

for d in [SHADOW_DIR, RAW_DIR, CARDS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("ODDS_API_KEY", "")

RS_SHADOW = SHADOW_DIR / "mlb_props_hits_rs_shadow.parquet"
PO_SHADOW = SHADOW_DIR / "mlb_props_hits_po_shadow.parquet"

PO_START = "2026-04-19"

# Empirical PA by lineup slot (from M2 warehouse audit)
EMPIRICAL_PA = {1: 4.40, 2: 4.29, 3: 4.16, 4: 4.06, 5: 3.94,
                6: 3.83, 7: 3.67, 8: 3.51, 9: 3.32}

LEAGUE_AVG_HIT_RATE = 0.245

# Market-implied PA by slot (from PA opportunity engine)
MARKET_PA_BY_SLOT = {1: 4.23, 2: 4.13, 3: 4.04, 4: 3.93, 5: 3.82,
                     6: 3.69, 7: 3.55, 8: 3.38, 9: 3.16}
PA_SUPPRESSION_THRESHOLD = -0.75  # pa_gap below this → flag

# ── Contact profile lookup ──
CONTACT_PROFILES_FILE = _SCRIPT_DIR / "distribution_shape" / "contact_engine" / "contact_combined_profiles.parquet"
_contact_cache = None

def _load_contact_profiles():
    """Load contact profile lookup (batter + game_date → profile)."""
    global _contact_cache
    if _contact_cache is not None:
        return _contact_cache
    if not CONTACT_PROFILES_FILE.exists():
        return None
    try:
        cp = pd.read_parquet(CONTACT_PROFILES_FILE)
        cp["batter"] = cp["batter"].astype(float)
        cp["gd_str"] = pd.to_datetime(cp["game_date"]).dt.strftime("%Y-%m-%d")
        # Keep latest profile per player for live use
        latest = cp.sort_values("game_date").groupby("batter").last().reset_index()
        _contact_cache = latest
        return _contact_cache
    except Exception:
        return None


def get_contact_profile(player_name):
    """Get contact profile for a player. Returns (combined, layer1, layer2)."""
    profiles = _load_contact_profiles()
    if profiles is None:
        return "UNKNOWN", "UNKNOWN", "UNKNOWN"

    # Load hitter rolling to map player_name → player_id
    latest = _load_hitter_rolling()
    match = latest[latest["player_name"].str.lower() == player_name.lower()]
    if len(match) == 0:
        last = player_name.split()[-1].lower()
        match = latest[latest["player_name"].str.lower().str.endswith(last)]
    if len(match) == 0:
        return "UNKNOWN", "UNKNOWN", "UNKNOWN"

    pid = float(match.iloc[0]["player_id"])
    prof = profiles[profiles["batter"] == pid]
    if len(prof) == 0:
        return "UNKNOWN", "UNKNOWN", "UNKNOWN"

    row = prof.iloc[0]
    combined = row.get("combined", "UNKNOWN")
    layer1 = row.get("contact_class", "UNKNOWN")
    layer2 = row.get("quality_class", "UNKNOWN")
    return combined, layer1, layer2


_pa_model = None

def _load_pa_model():
    """Load the PA prediction model (GBR from opportunity engine)."""
    global _pa_model
    if _pa_model is not None:
        return _pa_model
    pa_model_dir = _SCRIPT_DIR / "opportunity_engine"
    # Try loading cached model; if not available, build a simple one from hitter logs
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.preprocessing import StandardScaler
        import pickle

        pkl_path = pa_model_dir / "pa_gbr_model.pkl"
        if pkl_path.exists():
            with open(pkl_path, "rb") as f:
                _pa_model = pickle.load(f)
            return _pa_model

        # Build from hitter logs if model not cached
        h = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
        h = h[h["starter_flag"] == 1].copy()
        h["game_date"] = pd.to_datetime(h["game_date"])
        h = h.sort_values(["player_id", "game_date"])
        h["pa_L10"] = h.groupby(["player_id", "season"])["plate_appearances"].transform(
            lambda x: x.rolling(10, min_periods=5).mean().shift(1))
        h["pa_std10"] = h.groupby(["player_id", "season"])["plate_appearances"].transform(
            lambda x: x.rolling(10, min_periods=5).std().shift(1))

        h = h.dropna(subset=["pa_L10"])
        train = h[h["season"].isin([2022, 2023])]
        X = train[["batting_order_position", "pa_L10", "pa_std10"]].fillna(0)
        y = train["plate_appearances"]

        gbr = GradientBoostingRegressor(n_estimators=100, max_depth=3,
                                         min_samples_leaf=50, random_state=42)
        gbr.fit(X, y)

        _pa_model = {"model": gbr, "features": ["batting_order_position", "pa_L10", "pa_std10"]}
        pa_model_dir.mkdir(parents=True, exist_ok=True)
        with open(pkl_path, "wb") as f:
            pickle.dump(_pa_model, f)
        return _pa_model
    except Exception as e:
        print(f"  PA model not available: {e}")
        return None


def compute_pa_gap(player_name, lineup_slot):
    """Compute PA gap = model_predicted_PA - market_implied_PA."""
    mdl = _load_pa_model()
    market_pa = MARKET_PA_BY_SLOT.get(lineup_slot, 3.8)

    if mdl is None:
        return 0.0, market_pa, market_pa, False

    # Get player's recent PA stats
    latest = _load_hitter_rolling()
    match = latest[latest["player_name"].str.lower() == player_name.lower()]
    if len(match) == 0:
        last = player_name.split()[-1].lower()
        match = latest[latest["player_name"].str.lower().str.endswith(last)]
    if len(match) == 0:
        return 0.0, market_pa, market_pa, False

    row = match.iloc[0]
    pa_l10 = row.get("plate_appearances", market_pa)  # latest game PA as proxy for L10
    # Better: compute from rolling if available
    # For live use, pa_L10 may not be in the latest cache — use empirical as fallback
    pa_l10_val = pa_l10 if not pd.isna(pa_l10) else market_pa

    try:
        X = pd.DataFrame([{
            "batting_order_position": lineup_slot,
            "pa_L10": pa_l10_val,
            "pa_std10": 1.0,  # default
        }])
        model_pa = float(mdl["model"].predict(X)[0])
    except Exception:
        model_pa = market_pa

    pa_gap = model_pa - market_pa
    suppressed = pa_gap <= PA_SUPPRESSION_THRESHOLD
    return pa_gap, model_pa, market_pa, suppressed


def _season_phase(date_str):
    return "PO" if date_str >= PO_START else "RS"


def _shadow_file(date_str):
    return PO_SHADOW if _season_phase(date_str) == "PO" else RS_SHADOW


def _append(df, path):
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df
    combined.to_parquet(path, index=False)


def _american_to_implied(odds):
    if pd.isna(odds) or odds == 0:
        return np.nan
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def _devig(over_odds, under_odds):
    ro = _american_to_implied(over_odds)
    ru = _american_to_implied(under_odds)
    if pd.isna(ro) or pd.isna(ru):
        return np.nan, np.nan
    total = ro + ru
    return (ro / total, ru / total) if total > 0 else (np.nan, np.nan)


def roi_110(w, n):
    if n == 0: return np.nan
    return (w * (100 / 110) - (n - w)) / n * 100


# ══════════════════════════════════════════════════════════════
# HITTER PROJECTION ENGINE
# ══════════════════════════════════════════════════════════════

_hitter_cache = None

def _load_hitter_rolling():
    """Load hitter game logs and compute rolling stats."""
    global _hitter_cache
    if _hitter_cache is not None:
        return _hitter_cache

    h = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    h["game_date"] = pd.to_datetime(h["game_date"])
    h = h[h["starter_flag"] == 1].sort_values(["player_id", "game_date"])

    h["hit_rate"] = np.where(h["at_bats"] > 0, h["hits"] / h["at_bats"], 0)

    def _roll(g):
        g = g.copy()
        g["hit_rate_L15"] = g["hit_rate"].rolling(15, min_periods=5).mean().shift(1)
        g["hit_rate_L30"] = g["hit_rate"].rolling(30, min_periods=10).mean().shift(1)
        g["hit_rate_szn"] = g["hit_rate"].expanding(min_periods=5).mean().shift(1)

        for hand in ["L", "R"]:
            mask = g["opp_pitcher_hand"] == hand
            gh = g[mask]
            g[f"hit_rate_vs{hand}"] = np.nan
            if len(gh) > 0:
                cum_h = gh["hits"].expanding().sum().shift(1)
                cum_ab = gh["at_bats"].expanding().sum().shift(1)
                g.loc[gh.index, f"hit_rate_vs{hand}"] = np.where(cum_ab >= 20, cum_h / cum_ab, np.nan)
                g[f"hit_rate_vs{hand}"] = g[f"hit_rate_vs{hand}"].ffill()
        return g

    h = h.groupby(["player_id", "season"], group_keys=False).apply(_roll)
    # Keep latest row per player for live projection
    latest = h.sort_values("game_date").groupby("player_id").last().reset_index()
    _hitter_cache = latest
    return latest


def project_hits(player_name, lineup_slot, opp_pitcher_hand=None):
    """Project hits for a player. Returns (projection, model_prob_over_0_5, expected_pa)."""
    latest = _load_hitter_rolling()

    # Find player
    match = latest[latest["player_name"].str.lower() == player_name.lower()]
    if len(match) == 0:
        # Try last name
        last = player_name.split()[-1].lower()
        match = latest[latest["player_name"].str.lower().str.endswith(last)]

    if len(match) == 0:
        return None, None, None

    row = match.iloc[0]
    expected_pa = EMPIRICAL_PA.get(lineup_slot, 3.8)

    # Platoon-adjusted hit rate
    opp = opp_pitcher_hand
    hr_l30 = row.get("hit_rate_L30", np.nan)
    hr_l30 = hr_l30 if not pd.isna(hr_l30) else row.get("hit_rate_szn", LEAGUE_AVG_HIT_RATE)

    if opp == "L" and not pd.isna(row.get("hit_rate_vsL")):
        hit_rate = row["hit_rate_vsL"]
    elif opp == "R" and not pd.isna(row.get("hit_rate_vsR")):
        hit_rate = row["hit_rate_vsR"]
    elif not pd.isna(row.get("hit_rate_L15")):
        szn = row.get("hit_rate_szn", LEAGUE_AVG_HIT_RATE)
        hit_rate = 0.5 * row["hit_rate_L15"] + 0.3 * hr_l30 + 0.2 * szn
    else:
        hit_rate = row.get("hit_rate_szn", LEAGUE_AVG_HIT_RATE)

    if pd.isna(hit_rate):
        hit_rate = LEAGUE_AVG_HIT_RATE

    proj_hits = hit_rate * expected_pa
    return proj_hits, hit_rate, expected_pa


def compute_hits_prob_over(expected_pa, hit_rate, line):
    """P(hits > line) using binomial distribution."""
    n = max(1, round(expected_pa))
    p = max(0.01, min(0.5, hit_rate))
    threshold = int(np.floor(line)) + 1
    probs = np.array([scipy_stats.binom.pmf(k, n, p) for k in range(n + 1)])
    return float(probs[threshold:].sum()) if threshold < len(probs) else 0.0


# ══════════════════════════════════════════════════════════════
# COLLECTION
# ══════════════════════════════════════════════════════════════

def collect_hits(target_date):
    """Pull HITS prop lines for today's games."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    print(f"Collecting HITS props — {target_date} ({ts})")

    # Get events
    r = requests.get("https://api.the-odds-api.com/v4/sports/baseball_mlb/events",
                      params={"apiKey": API_KEY}, timeout=30)
    if r.status_code != 200:
        print(f"  Events: {r.status_code}")
        return pd.DataFrame()

    events = r.json()
    # Filter to today
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

    print(f"  Events: {len(today_events)}")

    all_rows = []
    for event in today_events:
        eid = event["id"]
        home = event["home_team"]
        away = event["away_team"]

        time.sleep(0.5)
        r2 = requests.get(
            f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{eid}/odds",
            params={"apiKey": API_KEY, "regions": "us",
                    "markets": "batter_hits", "oddsFormat": "american"},
            timeout=30)

        if r2.status_code != 200:
            continue

        data = r2.json()
        n_props = 0
        for bk in data.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt["key"] != "batter_hits":
                    continue
                player_lines = {}
                for o in mkt.get("outcomes", []):
                    player = o.get("description", "")
                    player_lines.setdefault(player, {})[o["name"]] = {
                        "point": o.get("point"), "price": o.get("price")}

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
                        "player_name": player,
                        "sportsbook": bk["key"],
                        "line": float(line),
                        "over_odds": over.get("price"),
                        "under_odds": under.get("price"),
                        "snapshot_type": "collect",
                    })
                    n_props += 1

        print(f"  {away} @ {home}: {n_props} HITS lines")

    credits = r2.headers.get("x-requests-remaining", "?") if today_events else "?"
    print(f"  Total: {len(all_rows)} lines, credits={credits}")

    df = pd.DataFrame(all_rows)
    if len(df) == 0:
        return df

    # Save raw
    raw_file = RAW_DIR / f"hits_{target_date}_{datetime.now().strftime('%H%M')}.parquet"
    df.to_parquet(raw_file, index=False)

    # Project + compute edges
    return _project_and_filter(df, target_date)


def _project_and_filter(df, target_date):
    """Project hits, compute corrected edge, generate shadow card."""
    # Best line per player (lowest over line = best for over bet)
    best = df.sort_values("line").groupby("player_name").first().reset_index()

    plays = []
    for _, row in best.iterrows():
        proj, hit_rate, exp_pa = project_hits(row["player_name"], 5)  # default slot 5
        if proj is None:
            continue

        model_p = compute_hits_prob_over(exp_pa, hit_rate, row["line"])
        imp_over, imp_under = _devig(row["over_odds"], row["under_odds"])
        if pd.isna(imp_over):
            continue

        edge = model_p - imp_over
        if edge < 0.02:  # Only OVER with edge >= 2%
            continue

        edge_bucket = "5%+" if edge >= 0.05 else "2-5%"

        # PA suppression flag
        pa_gap, model_pa, mkt_pa, pa_suppressed = compute_pa_gap(
            row["player_name"], 5)  # default slot 5

        # Contact profile
        contact_combined, contact_l1, contact_l2 = get_contact_profile(row["player_name"])

        plays.append({
            "date": target_date,
            "collection_timestamp": row["collection_timestamp"],
            "player_name": row["player_name"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "sportsbook": row["sportsbook"],
            "market_line": row["line"],
            "over_odds": row["over_odds"],
            "model_probability": round(model_p, 4),
            "implied_probability": round(imp_over, 4),
            "corrected_edge": round(edge, 4),
            "edge_bucket": edge_bucket,
            "projected_PA": round(exp_pa, 2),
            "projection": round(proj, 2),
            "lean_direction": "OVER",
            "first_seen_line": row["line"],
            "latest_seen_line": row["line"],
            "actual_PA": np.nan,
            "actual_hits": np.nan,
            "result_outcome": "",
            "roi_outcome": np.nan,
            "season_phase": _season_phase(target_date),
            "graded": False,
            "pa_gap": round(pa_gap, 3),
            "pa_suppression_flag": pa_suppressed,
            "contact_profile": contact_combined,
            "contact_layer1": contact_l1,
            "contact_layer2": contact_l2,
        })

    plays_df = pd.DataFrame(plays)
    if len(plays_df) == 0:
        print("  No qualifying HITS OVER plays.")
        return plays_df

    # Shadow card
    _generate_card(plays_df, target_date)

    # Append to shadow tracker
    _append(plays_df, _shadow_file(target_date))
    print(f"  Shadow plays: {len(plays_df)} HITS OVER → {_shadow_file(target_date).name}")

    return plays_df


def _generate_card(plays_df, target_date):
    """Generate daily shadow card."""
    phase = _season_phase(target_date)
    plays_df = plays_df.sort_values("corrected_edge", ascending=False)

    lines = []
    lines.append(f"MLB HITS OVER SHADOW CARD — {target_date} ({phase})")
    lines.append("=" * 55)
    lines.append(f"Generated: {datetime.now().strftime('%H:%M')}")
    lines.append(f"Plays: {len(plays_df)}")
    lines.append("")

    for bucket in ["5%+", "2-5%"]:
        sub = plays_df[plays_df["edge_bucket"] == bucket]
        if len(sub) == 0:
            continue
        lines.append(f"--- {bucket} EDGE ---")
        for _, p in sub.iterrows():
            lines.append(
                f"  {p['player_name']:<22s} line={p['market_line']:<5.1f} "
                f"proj={p['projection']:<5.2f} edge={p['corrected_edge']:+.1%} "
                f"[{p['sportsbook']}]"
            )
        lines.append("")

    card_text = "\n".join(lines)
    card_file = CARDS_DIR / f"hits_{target_date}.txt"
    with open(card_file, "w") as f:
        f.write(card_text)
    print(card_text)


# ══════════════════════════════════════════════════════════════
# REFRESH
# ══════════════════════════════════════════════════════════════

def refresh_hits(target_date):
    """Re-pull lines for pre-tip snapshot."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    print(f"Refreshing HITS props — {target_date} ({ts})")

    r = requests.get("https://api.the-odds-api.com/v4/sports/baseball_mlb/events",
                      params={"apiKey": API_KEY}, timeout=30)
    if r.status_code != 200:
        return

    events = r.json()
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    today_events = [e for e in events
                     if abs((datetime.strptime(e["commence_time"][:19], "%Y-%m-%dT%H:%M:%S") -
                             target_dt).total_seconds()) < 86400]

    all_rows = []
    for event in today_events:
        time.sleep(0.5)
        r2 = requests.get(
            f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event['id']}/odds",
            params={"apiKey": API_KEY, "regions": "us",
                    "markets": "batter_hits", "oddsFormat": "american"}, timeout=30)
        if r2.status_code != 200:
            continue
        for bk in r2.json().get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt["key"] != "batter_hits": continue
                player_lines = {}
                for o in mkt.get("outcomes", []):
                    player_lines.setdefault(o.get("description", ""), {})[o["name"]] = {
                        "point": o.get("point"), "price": o.get("price")}
                for player, sides in player_lines.items():
                    over = sides.get("Over", {})
                    under = sides.get("Under", {})
                    line = over.get("point") or under.get("point")
                    if line is None: continue
                    all_rows.append({
                        "date": target_date, "collection_timestamp": ts,
                        "player_name": player, "sportsbook": bk["key"],
                        "line": float(line), "over_odds": over.get("price"),
                        "under_odds": under.get("price"), "snapshot_type": "refresh",
                    })

    if all_rows:
        df = pd.DataFrame(all_rows)
        raw_file = RAW_DIR / f"hits_{target_date}_{datetime.now().strftime('%H%M')}_refresh.parquet"
        df.to_parquet(raw_file, index=False)

        # Update latest_seen_line in shadow tracker
        sf = _shadow_file(target_date)
        if sf.exists():
            shadow = pd.read_parquet(sf)
            today_mask = shadow["date"] == target_date
            for idx in shadow[today_mask].index:
                pname = shadow.loc[idx, "player_name"]
                refresh_lines = df[df["player_name"] == pname]
                if len(refresh_lines) > 0:
                    shadow.loc[idx, "latest_seen_line"] = refresh_lines["line"].min()
            shadow.to_parquet(sf, index=False)

        print(f"  Refresh: {len(all_rows)} lines saved, tracker updated")
    else:
        print("  No lines on refresh")


# ══════════════════════════════════════════════════════════════
# GRADING
# ══════════════════════════════════════════════════════════════

def grade_yesterday(target_date):
    """Grade yesterday's plays."""
    yesterday = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Grading HITS plays for {yesterday}...")

    # Fetch actuals from MLB Stats API
    try:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={yesterday}&hydrate=boxscore"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  MLB API: {r.status_code}")
            return

        data = r.json()
        actuals = {}  # player_name -> {hits, pa}

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                boxscore = game.get("boxscore", game.get("liveData", {}).get("boxscore", {}))
                if not boxscore:
                    gpk = game.get("gamePk")
                    time.sleep(0.3)
                    r2 = requests.get(f"https://statsapi.mlb.com/api/v1/game/{gpk}/boxscore", timeout=30)
                    if r2.status_code == 200:
                        boxscore = r2.json()

                for side in ["home", "away"]:
                    team_data = boxscore.get("teams", {}).get(side, {})
                    for pid_key, player in team_data.get("players", {}).items():
                        batting = player.get("stats", {}).get("batting", {})
                        if not batting:
                            continue
                        name = player.get("person", {}).get("fullName", "")
                        hits = int(batting.get("hits", 0) or 0)
                        pa = int(batting.get("plateAppearances", 0) or 0)
                        actuals[name.lower()] = {"hits": hits, "pa": pa}

        print(f"  Actuals: {len(actuals)} players")
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    # Grade shadow files
    for sf in [RS_SHADOW, PO_SHADOW]:
        if not sf.exists():
            continue
        shadow = pd.read_parquet(sf)
        to_grade = shadow[(shadow["date"] == yesterday) & (~shadow["graded"])]
        if len(to_grade) == 0:
            continue

        graded = 0
        for idx in to_grade.index:
            pname = shadow.loc[idx, "player_name"]
            player_data = actuals.get(pname.lower())
            if not player_data:
                shadow.loc[idx, "result_outcome"] = "DNP"
                shadow.loc[idx, "graded"] = True
                continue

            actual_hits = player_data["hits"]
            actual_pa = player_data["pa"]
            line = shadow.loc[idx, "market_line"]

            shadow.loc[idx, "actual_hits"] = actual_hits
            shadow.loc[idx, "actual_PA"] = actual_pa

            if actual_hits > line:
                shadow.loc[idx, "result_outcome"] = "WIN"
                shadow.loc[idx, "roi_outcome"] = 100 / 110
            elif actual_hits < line:
                shadow.loc[idx, "result_outcome"] = "LOSS"
                shadow.loc[idx, "roi_outcome"] = -1.0
            else:
                shadow.loc[idx, "result_outcome"] = "PUSH"
                shadow.loc[idx, "roi_outcome"] = 0.0

            shadow.loc[idx, "graded"] = True
            graded += 1

        shadow.to_parquet(sf, index=False)
        print(f"  Graded {graded} plays in {sf.name}")


# ══════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════

def hits_summary():
    """Print HITS OVER shadow summary."""
    for sf, label in [(RS_SHADOW, "REGULAR SEASON"), (PO_SHADOW, "PLAYOFFS")]:
        if not sf.exists():
            continue
        shadow = pd.read_parquet(sf)
        active = shadow[shadow["result_outcome"].isin(["WIN", "LOSS", "PUSH"])]

        print(f"\n{'='*55}")
        print(f"  MLB HITS OVER SHADOW — {label}")
        print(f"{'='*55}")

        if len(active) == 0:
            print("  No graded plays yet.")
            continue

        w = (active["result_outcome"] == "WIN").sum()
        l = (active["result_outcome"] == "LOSS").sum()
        p = (active["result_outcome"] == "PUSH").sum()
        n = w + l

        print(f"\n  OVERALL: {w}W-{l}L-{p}P ({n} bets)")
        print(f"  Hit rate: {w/n*100:.1f}%" if n > 0 else "")
        print(f"  ROI: {roi_110(w,n):+.1f}%" if n > 0 else "")

        # By edge bucket
        print(f"\n  BY EDGE BUCKET:")
        for bucket in ["2-5%", "5%+"]:
            sub = active[active["edge_bucket"] == bucket]
            sw = (sub["result_outcome"] == "WIN").sum()
            sn = sw + (sub["result_outcome"] == "LOSS").sum()
            if sn > 0:
                print(f"    {bucket}: {sw}W-{sn-sw}L ({sw/sn*100:.1f}%, ROI {roi_110(sw,sn):+.1f}%)")

        # By book
        print(f"\n  BY BOOK:")
        for book in sorted(active["sportsbook"].unique()):
            sub = active[active["sportsbook"] == book]
            sw = (sub["result_outcome"] == "WIN").sum()
            sn = sw + (sub["result_outcome"] == "LOSS").sum()
            if sn > 0:
                print(f"    {book:<16s}: {sw}W-{sn-sw}L ({sw/sn*100:.1f}%)")

        # PA accuracy
        has_pa = active[active["actual_PA"].notna() & active["projected_PA"].notna()]
        if len(has_pa) > 0:
            avg_proj = has_pa["projected_PA"].mean()
            avg_actual = has_pa["actual_PA"].mean()
            print(f"\n  PA ACCURACY:")
            print(f"    Projected: {avg_proj:.2f}")
            print(f"    Actual:    {avg_actual:.2f}")
            print(f"    Delta:     {avg_proj - avg_actual:+.2f}")

        # Prob tracking
        print(f"\n  PROBABILITY:")
        print(f"    Avg model_prob:   {active['model_probability'].mean():.1%}")
        print(f"    Avg implied_prob: {active['implied_probability'].mean():.1%}")
        print(f"    Avg edge:         {active['corrected_edge'].mean():+.1%}")

        # PA suppression tracking
        if "pa_suppression_flag" in active.columns:
            print(f"\n  PA SUPPRESSION ANALYSIS:")
            for flag_val, flag_label in [(True, "SUPPRESSED (pa_gap <= -0.75)"),
                                          (False, "NORMAL (pa_gap > -0.75)")]:
                sub = active[active["pa_suppression_flag"] == flag_val]
                if len(sub) == 0:
                    print(f"    {flag_label}: N=0")
                    continue
                sw = (sub["result_outcome"] == "WIN").sum()
                sn = sw + (sub["result_outcome"] == "LOSS").sum()
                if sn > 0:
                    print(f"    {flag_label}:")
                    print(f"      N={sn}, hit={sw/sn*100:.1f}%, ROI={roi_110(sw,sn):+.1f}%")
                else:
                    print(f"    {flag_label}: N=0 graded")

            # PA gap distribution
            has_gap = active[active["pa_gap"].notna()]
            if len(has_gap) > 0:
                print(f"\n    PA gap distribution:")
                print(f"      mean={has_gap['pa_gap'].mean():+.3f}, "
                      f"std={has_gap['pa_gap'].std():.3f}")
                print(f"      suppressed: {(has_gap['pa_suppression_flag']==True).sum()} plays "
                      f"({(has_gap['pa_suppression_flag']==True).mean()*100:.1f}%)")

        # CLV summary
        try:
            import sys as _sys
            _sys.path.insert(0, str(PROJECT_ROOT))
            from shared.clv_utils import clv_summary
            clv_summary(active, label)
        except ImportError:
            pass

        # Contact profile tracking
        if "contact_profile" in active.columns:
            print(f"\n  CONTACT PROFILE ANALYSIS:")
            known = active[active["contact_profile"] != "UNKNOWN"]
            if len(known) > 0:
                # By contact profile
                print(f"    By profile (N={len(known)}):")
                for profile in sorted(known["contact_profile"].unique()):
                    sub = known[known["contact_profile"] == profile]
                    sw = (sub["result_outcome"] == "WIN").sum()
                    sn = sw + (sub["result_outcome"] == "LOSS").sum()
                    if sn >= 3:
                        print(f"      {profile:<35s}: {sw}W-{sn-sw}L ({sw/sn*100:.1f}%, ROI {roi_110(sw,sn):+.1f}%)")

                # By contact layer 2 (quality)
                if "contact_layer2" in known.columns:
                    print(f"\n    By contact quality:")
                    for qual in ["ELITE_CONTACT", "SOLID_CONTACT", "AVERAGE_CONTACT", "WEAK_CONTACT"]:
                        sub = known[known["contact_layer2"] == qual]
                        sw = (sub["result_outcome"] == "WIN").sum()
                        sn = sw + (sub["result_outcome"] == "LOSS").sum()
                        if sn >= 3:
                            print(f"      {qual:<20s}: {sw}W-{sn-sw}L ({sw/sn*100:.1f}%)")

                # Contact × odds band (for 0.5 line plays)
                line_05 = known[known.get("market_line", known.get("line", pd.Series(dtype=float))) == 0.5] if "market_line" in known.columns else known
                if len(line_05) > 0 and "over_odds" in line_05.columns:
                    print(f"\n    Contact × Odds Band (0.5 line):")
                    for qual in ["ELITE_CONTACT", "WEAK_CONTACT"]:
                        qual_sub = line_05[line_05["contact_layer2"] == qual] if "contact_layer2" in line_05.columns else pd.DataFrame()
                        if len(qual_sub) < 3:
                            continue
                        for lo, hi, band_label in [(-125, -110, "-110 to -125"),
                                                     (-160, -125, "-125 to -160"),
                                                     (-9999, -160, "-160+")]:
                            odds_col = qual_sub["over_odds"]
                            band = qual_sub[(odds_col >= lo) & (odds_col < hi)]
                            if len(band) < 2:
                                continue
                            sw = (band["result_outcome"] == "WIN").sum()
                            sn = sw + (band["result_outcome"] == "LOSS").sum()
                            if sn > 0:
                                print(f"      {qual} {band_label}: {sw}W-{sn-sw}L ({sw/sn*100:.1f}%)")
            else:
                print(f"    No contact profiles matched yet")

        dates = sorted(active["date"].unique())
        print(f"\n  Dates: {dates[0]} to {dates[-1]} ({len(dates)} days)")
    print()


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="MLB HITS OVER Shadow System")
    p.add_argument("--collect", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--grade", action="store_true")
    p.add_argument("--hits-summary", action="store_true")
    p.add_argument("--date", type=str, default=None)
    args = p.parse_args()

    target = args.date or datetime.now().strftime("%Y-%m-%d")

    if not any([args.collect, args.refresh, args.grade, args.hits_summary]):
        p.print_help()
        return

    if args.collect:
        collect_hits(target)
    if args.refresh:
        refresh_hits(target)
    if args.grade:
        grade_yesterday(target)
    if args.hits_summary:
        hits_summary()


if __name__ == "__main__":
    main()
