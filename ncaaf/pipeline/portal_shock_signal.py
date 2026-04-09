#!/usr/bin/env python3
"""
NCAAF Portal Shock Signal — Tiered Early-Season Research Signal (Weeks 1-4)

Mechanism: Market overcorrects for visible portal departures and underweights
retained core production. Teams that lost significant transfer talent but kept
above-median returning production cover early-season spreads at 56.4%.

Frozen thresholds from Phase 2 research (2022-2025, N=259, p=0.047):
  NEGATIVE_SHOCK: net_star_shock <= -29.0 (bottom quartile)
  HIGH_RETURNING: percentPPA >= 0.551 (above median among NEGATIVE_SHOCK)

Tiers:
  Tier 1 (Base):    NEGATIVE_SHOCK + HIGH_RETURNING, Weeks 1-4
  Tier 2 (Strong):  Tier 1 + team is favored
  Tier 3 (Premium): Tier 2 + Power conference + spread 3-14 points

Usage:
  python3 ncaaf/pipeline/portal_shock_signal.py --season 2026
  python3 ncaaf/pipeline/portal_shock_signal.py --season 2026 --week 1
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("portal_shock")

CFBD_KEY = os.getenv("CFBD_API_KEY", "")
CFBD_BASE = "https://api.collegefootballdata.com"
CFBD_HEADERS = {"Authorization": f"Bearer {CFBD_KEY}"}

LOG_PATH = PROJECT_ROOT / "ncaaf" / "logs" / "portal_shock_signal_log.json"
DATA_DIR = PROJECT_ROOT / "ncaaf" / "data"

# ── Frozen thresholds from Phase 2 research ──────────────────────────────────
NET_STAR_SHOCK_THRESHOLD = -29.0   # bottom quartile
RETURNING_PPA_THRESHOLD = 0.551    # above median among NEGATIVE_SHOCK
DEPLOYMENT_WEEKS = {0, 1, 2, 3, 4}  # Week 0 included in early-season window

POWER_CONFERENCES = {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12"}
# Post-2024: Pac-12 effectively dissolved but keep for historical consistency


def _cfbd_get(endpoint, params=None):
    """GET from CFBD API with rate limiting."""
    url = f"{CFBD_BASE}/{endpoint.lstrip('/')}"
    r = requests.get(url, headers=CFBD_HEADERS, params=params or {}, timeout=20)
    r.raise_for_status()
    time.sleep(0.3)
    return r.json()


def build_team_portal_metrics(season):
    """Build per-team portal shock metrics for a season.
    Returns dict: team_name → {net_star_shock, negative_shock, ...}
    """
    # Portal transfers
    transfers = _cfbd_get("/player/portal", {"year": season})
    logger.info(f"  Portal transfers {season}: {len(transfers)}")

    team_in_stars = {}
    team_out_stars = {}
    for t in transfers:
        dest = t.get("destination")
        origin = t.get("origin")
        stars = t.get("stars") or 0
        if dest:
            team_in_stars[dest] = team_in_stars.get(dest, 0) + stars
        if origin:
            team_out_stars[origin] = team_out_stars.get(origin, 0) + stars

    all_teams = set(team_in_stars) | set(team_out_stars)
    metrics = {}
    for team in all_teams:
        net = team_in_stars.get(team, 0) - team_out_stars.get(team, 0)
        metrics[team] = {
            "net_star_shock": net,
            "portal_in_stars": team_in_stars.get(team, 0),
            "portal_out_stars": team_out_stars.get(team, 0),
            "negative_shock": net <= NET_STAR_SHOCK_THRESHOLD,
        }

    # Returning production
    try:
        returning = _cfbd_get("/player/returning", {"year": season})
        for r in returning:
            team = r.get("team")
            ppa = r.get("percentPPA")
            if team in metrics and ppa is not None:
                metrics[team]["returning_ppa"] = ppa
                metrics[team]["high_returning"] = ppa >= RETURNING_PPA_THRESHOLD
    except Exception as e:
        logger.warning(f"  Returning production fetch failed: {e}")

    neg_shock_count = sum(1 for m in metrics.values() if m.get("negative_shock"))
    high_ret_count = sum(1 for m in metrics.values()
                         if m.get("negative_shock") and m.get("high_returning"))
    logger.info(f"  {season}: {len(metrics)} teams, {neg_shock_count} NEGATIVE_SHOCK, "
                f"{high_ret_count} NEG_SHOCK+HIGH_RET")
    return metrics


def build_conference_map(season):
    """Build team → conference mapping for a season."""
    try:
        teams = _cfbd_get("/teams/fbs", {"year": season})
        return {t["school"]: t.get("conference", "") for t in teams}
    except Exception as e:
        logger.warning(f"  Conference fetch failed: {e}")
        return {}


def get_games_with_lines(season, week=None):
    """Fetch games and lines for a season (or specific week)."""
    params = {"year": season, "seasonType": "regular"}
    if week is not None:
        params["week"] = week
    games = _cfbd_get("/games", params)

    # Fetch lines
    line_params = {"year": season}
    if week is not None:
        line_params["week"] = week
    lines_raw = _cfbd_get("/lines", line_params)
    lines_by_game = {}
    for lr in lines_raw:
        gid = lr.get("id")
        book_lines = lr.get("lines", [])
        # Use consensus or first available spread
        for bl in book_lines:
            spread = bl.get("spread")
            if spread is not None:
                try:
                    lines_by_game[gid] = float(spread)
                    break
                except (ValueError, TypeError):
                    continue

    result = []
    for g in games:
        gid = g.get("id")
        week_num = g.get("week", 0)
        if week_num not in DEPLOYMENT_WEEKS:
            continue
        spread = lines_by_game.get(gid)
        if spread is None:
            continue  # no line available

        result.append({
            "game_id": gid,
            "season": season,
            "week": week_num,
            "home_team": g.get("homeTeam") or g.get("home_team"),
            "away_team": g.get("awayTeam") or g.get("away_team"),
            "home_conference": g.get("homeConference") or g.get("home_conference"),
            "away_conference": g.get("awayConference") or g.get("away_conference"),
            "home_points": g.get("homePoints") or g.get("home_points"),
            "away_points": g.get("awayPoints") or g.get("away_points"),
            "spread": spread,  # negative = home favored
            "neutral_site": g.get("neutralSite") or g.get("neutral_site", False),
            "start_date": g.get("startDate") or g.get("start_date"),
        })

    logger.info(f"  {season} Weeks 0-4: {len(result)} games with lines")
    return result


def assign_tiers(games, portal_metrics, conference_map):
    """Assign portal shock tiers to each team-game."""
    signals = []

    for g in games:
        for side in ["home", "away"]:
            team = g[f"{side}_team"]
            opponent = g["away_team"] if side == "home" else g["home_team"]
            pm = portal_metrics.get(team, {})

            neg_shock = pm.get("negative_shock", False)
            high_ret = pm.get("high_returning", False)

            # Spread interpretation: spread is from home perspective
            # home favored = spread < 0, away favored = spread > 0
            if side == "home":
                team_spread = g["spread"]
            else:
                team_spread = -g["spread"]
            favored = team_spread < 0
            abs_spread = abs(team_spread)

            conf = conference_map.get(team, g.get(f"{side}_conference", ""))
            power = conf in POWER_CONFERENCES

            # Tier assignment
            tier_1 = neg_shock and high_ret
            tier_2 = tier_1 and favored
            tier_3 = tier_2 and power and 3.0 <= abs_spread <= 14.0

            if not tier_1:
                continue  # only log qualifying team-games

            # ATS result (for grading later)
            hp = g.get("home_points")
            ap = g.get("away_points")
            ats_result = None
            ats_margin = None
            if hp is not None and ap is not None:
                if side == "home":
                    margin = (hp - ap) + g["spread"]
                else:
                    margin = (ap - hp) - g["spread"]
                ats_margin = round(margin, 1)
                if margin > 0:
                    ats_result = "COVER"
                elif margin < 0:
                    ats_result = "NO_COVER"
                else:
                    ats_result = "PUSH"

            # Determine highest tier
            if tier_3:
                highest_tier = "TIER_3_PREMIUM"
            elif tier_2:
                highest_tier = "TIER_2_STRONG"
            else:
                highest_tier = "TIER_1_BASE"

            signals.append({
                "game_id": g["game_id"],
                "season": g["season"],
                "week": g["week"],
                "date": g.get("start_date", ""),
                "team": team,
                "opponent": opponent,
                "side": side,
                "spread": round(team_spread, 1),
                "closing_spread": round(team_spread, 1),
                "conference": conf,
                "negative_shock_flag": True,
                "high_returning_flag": True,
                "net_star_shock": pm.get("net_star_shock"),
                "returning_ppa": pm.get("returning_ppa"),
                "favored_flag": favored,
                "power_tier_flag": power,
                "spread_band_3_to_14_flag": 3.0 <= abs_spread <= 14.0,
                "portal_tier_1": True,
                "portal_tier_2": tier_2,
                "portal_tier_3": tier_3,
                "highest_tier": highest_tier,
                "ats_result": ats_result,
                "ats_margin": ats_margin,
                "logged_at": datetime.now(timezone.utc).isoformat(),
                "note": f"Portal overcorrection — {team} lost portal talent (net={pm.get('net_star_shock')}) "
                        f"but retained core (retPPA={pm.get('returning_ppa', 'N/A')})",
            })

    return signals


def load_existing_log():
    """Load existing signal log, preserving historical rows."""
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except Exception:
            return []
    return []


def save_log(records):
    """Save signal log (dedup by game_id + team)."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(records, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, default=None,
                        help="Specific week (default: all Weeks 0-4)")
    parser.add_argument("--backfill", action="store_true",
                        help="Backfill all seasons 2022-current")
    args = parser.parse_args()

    if not CFBD_KEY:
        logger.error("CFBD_API_KEY not set in .env")
        sys.exit(1)

    existing = load_existing_log()
    existing_keys = {(r["game_id"], r["team"]) for r in existing}

    seasons = list(range(2022, args.season + 1)) if args.backfill else [args.season]
    all_new = []

    for season in seasons:
        logger.info(f"Processing {season}...")
        portal = build_team_portal_metrics(season)
        conf_map = build_conference_map(season)
        games = get_games_with_lines(season, week=args.week)
        signals = assign_tiers(games, portal, conf_map)

        new = [s for s in signals if (s["game_id"], s["team"]) not in existing_keys]
        all_new.extend(new)
        existing_keys |= {(s["game_id"], s["team"]) for s in new}

        t1 = sum(1 for s in new if s["portal_tier_1"])
        t2 = sum(1 for s in new if s["portal_tier_2"])
        t3 = sum(1 for s in new if s["portal_tier_3"])
        logger.info(f"  {season}: {len(new)} new signals (T1={t1}, T2={t2}, T3={t3})")

    if all_new:
        combined = existing + all_new
        save_log(combined)
        logger.info(f"Saved {len(all_new)} new signals ({len(combined)} total)")
    else:
        logger.info("No new signals to add")

    # Summary
    log = load_existing_log()
    graded = [r for r in log if r.get("ats_result") in ("COVER", "NO_COVER")]
    covers = sum(1 for r in graded if r["ats_result"] == "COVER")
    no_covers = sum(1 for r in graded if r["ats_result"] == "NO_COVER")
    logger.info(f"Signal log: {len(log)} total, {len(graded)} graded, "
                f"ATS: {covers}-{no_covers}")

    # Push handled by push_daemon.sh
    # import subprocess
    # subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
    #                  "NCAAF portal shock signal update"], capture_output=True)


if __name__ == "__main__":
    main()
