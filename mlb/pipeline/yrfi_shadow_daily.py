#!/usr/bin/env python3
"""
YRFI Shadow Tracker — Full 6-Signal Daily Runner
==================================================
Computes six permutation-confirmed YRFI signals for today's MLB slate,
joins FanDuel first-inning prices, and logs results.

Signals use frozen 2024 discovery tercile thresholds (p33/p67).
Each game is evaluated from both batting contexts (top/bottom of 1st).

Usage:
  python3 mlb/pipeline/yrfi_shadow_daily.py
  python3 mlb/pipeline/yrfi_shadow_daily.py --date 2026-05-06
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yrfi_shadow")

# ── Paths ──
PITCHER_SC = PROJECT_ROOT / "research" / "statcast_enrichment" / "pitcher_statcast_per_start.parquet"
BATTER_SC = PROJECT_ROOT / "research" / "recovery" / "mlb_hitter_statcast_substrate" / "batter_game_statcast.parquet"
PGL_PATH = PROJECT_ROOT / "mlb" / "data" / "pitcher_game_logs.parquet"
ODDS_LOG = PROJECT_ROOT / "mlb" / "logs" / "yrfi_odds_2026.json"
SHADOW_LOG = PROJECT_ROOT / "mlb" / "logs" / "yrfi_shadow_2026.json"

# ── Frozen thresholds from 2024 discovery (p33/p67 on home V6 row) ──
THRESHOLDS = {
    "opp_sp_contact_la_allowed_last_5": {"p33": 15.440890, "p67": 20.375615},
    "opp_sp_workload_ip_last_3": {"p33": 5.000000, "p67": 5.700000},
    "opp_sp_command_bb_rate_last_3": {"p33": 0.056159, "p67": 0.089389},
    "opp_pl_secondary_2strike_drift_last_3": {"p33": -0.016840, "p67": 0.016735},
    "opp_sp_contact_la_allowed_last_10": {"p33": 15.732193, "p67": 20.174236},
    "contact_hh_rate_last_15": {"p33": 0.369679, "p67": 0.401796},
    "contact_xslg_last_7": {"p33": 0.502909, "p67": 0.557415},
    "opp_pl_two_strike_secondary_pct_season_baseline": {"p33": 0.446704, "p67": 0.558762},
    "bullpen_pitches_last_3_games": {"p33": 161.000000, "p67": 203.000000},
    "opp_pl_zone_drift_last_5": {"p33": -0.006996, "p67": 0.001670},
}

# ── Team abbreviation map (Odds API full name → schedule abbr) ──
_ODDS_TO_ABB = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Athletics": "OAK", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SDP", "San Francisco Giants": "SFG",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TBR",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN",
}


def _load_data():
    """Load all data sources needed for feature computation."""
    psc = pd.read_parquet(PITCHER_SC)
    psc["game_date"] = pd.to_datetime(psc["game_date"])
    psc = psc.sort_values(["pitcher_id", "game_date"])

    bsc = pd.read_parquet(BATTER_SC)
    bsc["game_date"] = pd.to_datetime(bsc["game_date"])

    pgl = pd.read_parquet(PGL_PATH)
    pgl["game_date"] = pd.to_datetime(pgl["game_date"])
    pgl = pgl.sort_values(["player_id", "game_date"])

    return psc, bsc, pgl


def _rolling_mean(series, n):
    """PIT-safe rolling mean: shift(1) then rolling."""
    return series.shift(1).rolling(n, min_periods=max(2, n // 2)).mean()


def _compute_batting_context(game_date_ts, offense_team, opp_starter_id,
                              opp_team, psc, bsc, pgl):
    """Compute all features for one batting context (top or bottom of 1st)."""
    today = game_date_ts
    features = {}
    notes = []

    # ── Opposing starter features (from pitcher Statcast aggregate) ──
    if opp_starter_id is not None:
        sp = psc[(psc["pitcher_id"] == opp_starter_id) & (psc["game_date"] < today)].copy()

        if len(sp) >= 2:
            features["opp_sp_contact_la_allowed_last_5"] = float(
                sp["avg_launch_angle"].tail(5).mean()) if len(sp) >= 2 else None
            features["opp_sp_contact_la_allowed_last_10"] = float(
                sp["avg_launch_angle"].tail(10).mean()) if len(sp) >= 2 else None

            # Zone rate drift: last 5 minus season baseline
            season_starts = sp[sp["game_date"].dt.year == today.year]
            if len(season_starts) >= 2:
                season_zone_baseline = season_starts["zone_rate"].mean()
                last5_zone = sp["zone_rate"].tail(5).mean()
                features["opp_pl_zone_drift_last_5"] = float(last5_zone - season_zone_baseline)
            else:
                features["opp_pl_zone_drift_last_5"] = None

            # 2-strike secondary pct drift and baseline
            if "two_strike_secondary_pct" in sp.columns:
                if len(season_starts) >= 2:
                    season_2s_baseline = season_starts["two_strike_secondary_pct"].mean()
                    features["opp_pl_two_strike_secondary_pct_season_baseline"] = float(season_2s_baseline)
                    last3_2s = sp["two_strike_secondary_pct"].tail(3).mean()
                    features["opp_pl_secondary_2strike_drift_last_3"] = float(last3_2s - season_2s_baseline)
                else:
                    features["opp_pl_two_strike_secondary_pct_season_baseline"] = None
                    features["opp_pl_secondary_2strike_drift_last_3"] = None
            else:
                features["opp_pl_two_strike_secondary_pct_season_baseline"] = None
                features["opp_pl_secondary_2strike_drift_last_3"] = None
                notes.append("NO_2STRIKE_SECONDARY_IN_AGGREGATE")
        else:
            for k in ["opp_sp_contact_la_allowed_last_5", "opp_sp_contact_la_allowed_last_10",
                       "opp_pl_zone_drift_last_5", "opp_pl_two_strike_secondary_pct_season_baseline",
                       "opp_pl_secondary_2strike_drift_last_3"]:
                features[k] = None
            notes.append("OPP_STARTER_INSUFFICIENT_HISTORY")

        # Starter features from pitcher game logs
        sp_pgl = pgl[(pgl["player_id"] == opp_starter_id) &
                      (pgl["starter_flag"] == 1) &
                      (pgl["game_date"] < today)]
        if len(sp_pgl) >= 2:
            features["opp_sp_workload_ip_last_3"] = float(
                sp_pgl["innings_pitched"].tail(3).mean())
            sp_pgl = sp_pgl.copy()
            sp_pgl["bb_rate"] = sp_pgl["walks"] / sp_pgl["batters_faced"].clip(lower=1)
            features["opp_sp_command_bb_rate_last_3"] = float(
                sp_pgl["bb_rate"].tail(3).mean())
        else:
            features["opp_sp_workload_ip_last_3"] = None
            features["opp_sp_command_bb_rate_last_3"] = None
            if "OPP_STARTER_INSUFFICIENT_HISTORY" not in notes:
                notes.append("OPP_STARTER_PGL_INSUFFICIENT")
    else:
        for k in ["opp_sp_contact_la_allowed_last_5", "opp_sp_contact_la_allowed_last_10",
                   "opp_sp_workload_ip_last_3", "opp_sp_command_bb_rate_last_3",
                   "opp_pl_zone_drift_last_5", "opp_pl_two_strike_secondary_pct_season_baseline",
                   "opp_pl_secondary_2strike_drift_last_3"]:
            features[k] = None
        notes.append("STARTER_UNAVAILABLE")

    # ── Opposing team bullpen pitches ──
    opp_pgl = pgl[(pgl["team"] == opp_team) &
                   (pgl["starter_flag"] == 0) &
                   (pgl["game_date"] < today)]
    if len(opp_pgl) > 0:
        bp_by_game = opp_pgl.groupby("game_pk")["pitches"].sum().reset_index()
        bp_by_game = bp_by_game.sort_values("game_pk")
        features["bullpen_pitches_last_3_games"] = float(
            bp_by_game["pitches"].tail(3).sum()) if len(bp_by_game) >= 1 else None
    else:
        features["bullpen_pitches_last_3_games"] = None
        notes.append("BULLPEN_DATA_UNAVAILABLE")

    # ── Offense team batting features (team-level from batter aggregate) ──
    team_bsc = bsc[(bsc["team"] == offense_team) & (bsc["game_date"] < today)]
    if len(team_bsc) >= 5:
        # Team-game level: mean across batters per game, then rolling over games
        team_game = team_bsc.groupby(["game_pk", "game_date"]).agg(
            hh_rate=("hard_hit_rate", "mean"),
            xslg=("xslg_contact", "mean"),
        ).reset_index().sort_values("game_date")

        features["contact_hh_rate_last_15"] = float(
            team_game["hh_rate"].tail(15).mean()) if len(team_game) >= 2 else None
        features["contact_xslg_last_7"] = float(
            team_game["xslg"].tail(7).mean()) if len(team_game) >= 2 else None
    else:
        features["contact_hh_rate_last_15"] = None
        features["contact_xslg_last_7"] = None
        notes.append("OFFENSE_BATTING_INSUFFICIENT")

    return features, notes


def _check_signal(features, feat_a, dir_a, feat_b, dir_b):
    """Check if a two-feature signal fires. Returns True/False/None."""
    va = features.get(feat_a)
    vb = features.get(feat_b)
    if va is None or vb is None:
        return None

    ta = THRESHOLDS[feat_a]["p67"] if dir_a == "HIGH" else THRESHOLDS[feat_a]["p33"]
    tb = THRESHOLDS[feat_b]["p67"] if dir_b == "HIGH" else THRESHOLDS[feat_b]["p33"]

    cond_a = va >= ta if dir_a == "HIGH" else va <= ta
    cond_b = vb >= tb if dir_b == "HIGH" else vb <= tb
    return bool(cond_a and cond_b)


SIGNAL_DEFS = [
    ("S1_LA_WORKLOAD", "opp_sp_contact_la_allowed_last_5", "HIGH",
     "opp_sp_workload_ip_last_3", "HIGH"),
    ("S2_COMMAND_DRIFT", "opp_sp_command_bb_rate_last_3", "LOW",
     "opp_pl_secondary_2strike_drift_last_3", "HIGH"),
    ("S3_COMMAND_LA", "opp_sp_command_bb_rate_last_3", "LOW",
     "opp_sp_contact_la_allowed_last_10", "HIGH"),
    ("S4_XSLG_2STRIKE", "contact_xslg_last_7", "LOW",
     "opp_pl_two_strike_secondary_pct_season_baseline", "LOW"),
    ("S5_BULLPEN_ZONE", "bullpen_pitches_last_3_games", "HIGH",
     "opp_pl_zone_drift_last_5", "LOW"),
    ("S6_CONTACT_HH_LA", "contact_hh_rate_last_15", "LOW",
     "opp_sp_contact_la_allowed_last_5", "HIGH"),
]


def _evaluate_signals(features):
    """Evaluate all 6 signals. Returns dict of signal_name -> True/False/None."""
    results = {}
    for name, fa, da, fb, db in SIGNAL_DEFS:
        results[name] = _check_signal(features, fa, da, fb, db)
    return results


def _american_be(price):
    """Break-even from American odds."""
    if price is None or np.isnan(price):
        return None
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)


def _load_odds(game_date_str):
    """Load FanDuel YRFI prices for today from the odds log."""
    if not ODDS_LOG.exists():
        return {}
    try:
        records = json.loads(ODDS_LOG.read_text())
    except Exception:
        return {}
    odds_map = {}
    for r in records:
        if r.get("pull_date") != game_date_str:
            continue
        home_abb = _ODDS_TO_ABB.get(r.get("home_team", ""), r.get("home_team", ""))
        away_abb = _ODDS_TO_ABB.get(r.get("away_team", ""), r.get("away_team", ""))
        key = (home_abb, away_abb)
        odds_map[key] = {
            "fd_yrfi_price": r.get("yrfi_price"),
            "fd_nrfi_price": r.get("nrfi_price"),
            "game_id": r.get("game_id"),
        }
    return odds_map


def _load_shadow_log():
    if SHADOW_LOG.exists():
        try:
            return json.loads(SHADOW_LOG.read_text())
        except Exception:
            return []
    return []


def _save_shadow_log(entries):
    SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
    SHADOW_LOG.write_text(json.dumps(entries, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    game_date_str = args.date or date.today().isoformat()
    game_date_ts = pd.Timestamp(game_date_str)
    run_ts = datetime.now(timezone.utc).isoformat()

    logger.info(f"YRFI Shadow Tracker — {game_date_str}")

    # Load schedule
    from modules.schedule import fetch_schedule
    games = fetch_schedule(game_date_str)
    if not games:
        logger.warning("No games today.")
        return

    logger.info(f"Games on slate: {len(games)}")

    # Load data
    psc, bsc, pgl = _load_data()

    # Load odds
    odds_map = _load_odds(game_date_str)

    # Process each game
    new_entries = []

    for g in games:
        home = g["home_team"]
        away = g["away_team"]
        game_pk = g["game_pk"]
        home_sp = g.get("home_probable_pitcher", {})
        away_sp = g.get("away_probable_pitcher", {})
        home_sp_id = home_sp.get("id") if home_sp else None
        away_sp_id = away_sp.get("id") if away_sp else None
        home_sp_name = home_sp.get("name", "") if home_sp else ""
        away_sp_name = away_sp.get("name", "") if away_sp else ""

        game_notes = []

        # Away batting context (top of 1st: away bats vs home starter)
        away_feats, away_notes = _compute_batting_context(
            game_date_ts, away, home_sp_id, home, psc, bsc, pgl)
        away_signals = _evaluate_signals(away_feats)

        # Home batting context (bottom of 1st: home bats vs away starter)
        home_feats, home_notes = _compute_batting_context(
            game_date_ts, home, away_sp_id, away, psc, bsc, pgl)
        home_signals = _evaluate_signals(home_feats)

        # Game-level consensus
        fired_away = {k for k, v in away_signals.items() if v is True}
        fired_home = {k for k, v in home_signals.items() if v is True}
        all_fired = fired_away | fired_home
        unique_count = len(all_fired)
        total_context_count = len(fired_away) + len(fired_home)

        # Odds
        odds = odds_map.get((home, away), {})
        fd_yrfi = odds.get("fd_yrfi_price")
        fd_nrfi = odds.get("fd_nrfi_price")
        fd_be = _american_be(fd_yrfi) if fd_yrfi is not None else None
        fd_available = fd_yrfi is not None

        if not fd_available:
            game_notes.append("FD_PRICE_UNAVAILABLE")

        entry = {
            "log_date": game_date_str,
            "run_timestamp": run_ts,
            "game_date": game_date_str,
            "game_id": odds.get("game_id", str(game_pk)),
            "game_pk": game_pk,
            "home_team": home,
            "away_team": away,
            "home_starter": home_sp_name,
            "away_starter": away_sp_name,
            "away_batting_context": {
                "opposing_starter": home_sp_name,
                "features": {k: round(v, 6) if isinstance(v, float) else v
                             for k, v in away_feats.items()},
                "signals": away_signals,
                "signal_count": len(fired_away),
                "fired": sorted(fired_away),
                "notes": away_notes,
            },
            "home_batting_context": {
                "opposing_starter": away_sp_name,
                "features": {k: round(v, 6) if isinstance(v, float) else v
                             for k, v in home_feats.items()},
                "signals": home_signals,
                "signal_count": len(fired_home),
                "fired": sorted(fired_home),
                "notes": home_notes,
            },
            "unique_signal_count": unique_count,
            "total_context_signal_count": total_context_count,
            "fired_signals": sorted(all_fired),
            "yrfi_1plus": unique_count >= 1,
            "yrfi_2plus": unique_count >= 2,
            "yrfi_3plus": unique_count >= 3,
            "fd_yrfi_price": fd_yrfi,
            "fd_nrfi_price": fd_nrfi,
            "fd_break_even": round(fd_be, 4) if fd_be is not None else None,
            "fd_price_available": fd_available,
            "result_yrfi": None,
            "result_graded": False,
            "graded_date": None,
            "notes": game_notes,
        }
        new_entries.append(entry)

    # Dedup/update log
    existing = _load_shadow_log()
    new_keys = {(e["game_date"], e["home_team"], e["away_team"], e["log_date"])
                for e in new_entries}
    existing = [e for e in existing
                if (e["game_date"], e["home_team"], e["away_team"], e["log_date"])
                not in new_keys]
    combined = existing + new_entries
    _save_shadow_log(combined)

    # ── Daily card ──
    tier3 = [e for e in new_entries if e["yrfi_3plus"]]
    tier2 = [e for e in new_entries if e["yrfi_2plus"] and not e["yrfi_3plus"]]
    tier1 = [e for e in new_entries if e["yrfi_1plus"] and not e["yrfi_2plus"]]

    print(f"\n=== YRFI SHADOW CARD [{game_date_str}] ===\n")

    def _price_str(e):
        if e["fd_price_available"]:
            return f"FD YRFI={e['fd_yrfi_price']} BE={e['fd_break_even']:.1%}"
        return "no FD price"

    if tier3:
        print("3+ SIGNALS:")
        for e in tier3:
            sigs = ", ".join(e["fired_signals"])
            print(f"  {e['away_team']}@{e['home_team']} | {e['unique_signal_count']} signals | {sigs} | {_price_str(e)}")

    if tier2:
        print("2 SIGNALS:")
        for e in tier2:
            sigs = ", ".join(e["fired_signals"])
            print(f"  {e['away_team']}@{e['home_team']} | {e['unique_signal_count']} signals | {sigs} | {_price_str(e)}")

    if tier1:
        print("1 SIGNAL:")
        for e in tier1:
            sigs = ", ".join(e["fired_signals"])
            print(f"  {e['away_team']}@{e['home_team']} | {e['unique_signal_count']} signals | {sigs} | {_price_str(e)}")

    if not tier3 and not tier2 and not tier1:
        print("NONE TODAY")

    n_with_price = sum(1 for e in new_entries if e["fd_price_available"])
    print(f"\nSummary: {len(new_entries)} games | "
          f"1+: {len(tier1)+len(tier2)+len(tier3)} | "
          f"2+: {len(tier2)+len(tier3)} | "
          f"3+: {len(tier3)} | "
          f"FD priced: {n_with_price} | "
          f"logged: {len(combined)} total")


if __name__ == "__main__":
    main()
