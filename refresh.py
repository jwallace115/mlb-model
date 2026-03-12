#!/usr/bin/env python3
"""
Pre-game refresh — checks for lineup/weather changes and re-runs projections.

Run this ~90 minutes before first pitch to catch:
  - Updated starting pitcher announcements
  - Significant weather shifts
  - Umpire assignment confirmations

Usage:
  python refresh.py              # refresh all today's games
  python refresh.py --game 12345 # refresh a single game_pk
  python refresh.py --date 2025-04-15
"""

import argparse
import logging
import sys
from datetime import date

from colorama import Fore, Style, init as colorama_init

import db
from config import LOGS_DIR
from modules.schedule    import fetch_schedule
from modules.pitchers    import build_pitcher_db, get_pitcher_metrics
from modules.offense     import build_offense_db, get_team_offense
from modules.weather     import fetch_weather
from modules.bullpen     import calculate_bullpen_fatigue
from modules.umpires     import get_umpire_rating
from modules.projections import project_game

colorama_init(autoreset=True)

LOG_FILE = f"{LOGS_DIR}/refresh_{date.today().isoformat()}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("refresh")


def refresh_games(game_date: str = None, target_game_pk: int = None) -> None:
    if game_date is None:
        game_date = date.today().isoformat()

    db.init_db()
    logger.info(f"Refreshing projections for {game_date}...")

    games = fetch_schedule(game_date)
    if not games:
        logger.warning("No games found.")
        return

    if target_game_pk:
        games = [g for g in games if g["game_pk"] == target_game_pk]
        if not games:
            logger.error(f"Game {target_game_pk} not found in today's slate.")
            return

    pitcher_db = build_pitcher_db()
    offense_db = build_offense_db()

    changes = []

    for game in games:
        gk   = game["game_pk"]
        home = game["home_team"]
        away = game["away_team"]

        # Pull existing projection from DB
        with db.get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM projections WHERE game_pk = ? AND game_date = ?",
                (gk, game_date)
            ).fetchone()

        home_sp  = get_pitcher_metrics(game["home_probable_pitcher"], pitcher_db)
        away_sp  = get_pitcher_metrics(game["away_probable_pitcher"], pitcher_db)
        home_off = get_team_offense(home, offense_db)
        away_off = get_team_offense(away, offense_db)
        weather  = fetch_weather(home, game_time_et=game.get("game_time"))
        umpire   = get_umpire_rating(game.get("home_umpire"))
        home_bp  = calculate_bullpen_fatigue(game["home_team_id"], is_home=True)
        away_bp  = calculate_bullpen_fatigue(game["away_team_id"], is_home=False)

        proj = project_game(
            home_team=home, away_team=away,
            home_sp_metrics=home_sp, away_sp_metrics=away_sp,
            home_offense=home_off, away_offense=away_off,
            weather=weather, umpire=umpire,
            home_bullpen=home_bp, away_bullpen=away_bp,
        )

        # Compare vs prior projection
        if existing:
            old_full = existing["proj_total_full"]
            new_full = proj["proj_total_full"]
            old_sp_h = existing["home_sp"]
            old_sp_a = existing["away_sp"]
            new_sp_h = home_sp["name"]
            new_sp_a = away_sp["name"]
            old_wind = existing["wind_speed"] or 0
            new_wind = proj["factors"]["wind_speed_mph"] or 0

            change_notes = []
            if old_sp_h != new_sp_h:
                change_notes.append(f"HOME SP: {old_sp_h} → {new_sp_h}")
            if old_sp_a != new_sp_a:
                change_notes.append(f"AWAY SP: {old_sp_a} → {new_sp_a}")
            if abs(new_wind - old_wind) >= 5:
                change_notes.append(f"WIND: {old_wind:.0f}mph → {new_wind:.0f}mph")
            if abs(new_full - old_full) >= 0.5:
                change_notes.append(f"TOTAL: {old_full:.1f} → {new_full:.1f}")

            if change_notes:
                changes.append({
                    "game": f"{away} @ {home}",
                    "notes": change_notes,
                    "old_total": old_full,
                    "new_total": new_full,
                    "confidence": proj["confidence"],
                })
                print(f"\n{Fore.YELLOW}CHANGE DETECTED: {away} @ {home}{Style.RESET_ALL}")
                for note in change_notes:
                    print(f"  → {note}")
            else:
                logger.info(f"  {away} @ {home}: No significant changes (total={new_full:.1f})")

        # Re-persist updated projection
        f = proj["factors"]
        db.upsert_projection({
            "game_date":       game_date,
            "game_pk":         gk,
            "home_team":       home,
            "away_team":       away,
            "home_sp":         home_sp.get("name"),
            "away_sp":         away_sp.get("name"),
            "home_sp_xfip":    home_sp.get("xfip"),
            "away_sp_xfip":    away_sp.get("xfip"),
            "home_sp_siera":   home_sp.get("siera"),
            "away_sp_siera":   away_sp.get("siera"),
            "home_wrc_plus":   home_off.get("wrc_plus"),
            "away_wrc_plus":   away_off.get("wrc_plus"),
            "park_factor":     f.get("park_factor"),
            "wind_speed":      f.get("wind_speed_mph"),
            "wind_direction":  f.get("wind_direction"),
            "temperature":     f.get("temperature_f"),
            "umpire_name":     f.get("umpire_name"),
            "umpire_factor":   f.get("umpire_runs_factor"),
            "home_bp_fatigue": f.get("home_bp_fatigue"),
            "away_bp_fatigue": f.get("away_bp_fatigue"),
            "proj_total_full": proj["proj_total_full"],
            "proj_total_f5":   proj["proj_total_f5"],
            "confidence":      proj["confidence"],
            "confidence_score": proj["confidence_score"],
            "factors_json":    proj["factors"],
        })

    # Summary
    if changes:
        print(f"\n{Fore.CYAN}{'='*50}")
        print(f"REFRESH SUMMARY — {len(changes)} game(s) changed")
        print(f"{'='*50}{Style.RESET_ALL}")
        for c in changes:
            direction = "↑" if c["new_total"] > c["old_total"] else "↓"
            print(f"  {c['game']}: {c['old_total']:.1f} {direction} {c['new_total']:.1f} "
                  f"[{c['confidence']}] — {'; '.join(c['notes'])}")
    else:
        print(f"\n{Fore.GREEN}No significant changes detected for {game_date}.{Style.RESET_ALL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-game refresh")
    parser.add_argument("--date", "-d", default=None, help="Game date YYYY-MM-DD")
    parser.add_argument("--game", "-g", type=int, default=None, help="Specific game_pk")
    args = parser.parse_args()
    refresh_games(game_date=args.date, target_game_pk=args.game)
