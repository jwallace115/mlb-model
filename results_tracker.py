#!/usr/bin/env python3
"""
Results tracker — grade yesterday's games against projections.

Usage:
  python results_tracker.py                  # grade yesterday (default)
  python results_tracker.py --date 2025-04-14
  python results_tracker.py --summary
  python results_tracker.py --summary --days 30
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta

import requests
from colorama import Fore, Style, init as colorama_init

import db
from config import MLB_STATS_API

colorama_init(autoreset=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("results_tracker")

_STAR_COUNT = {"⭐⭐⭐": 3, "⭐⭐": 2, "⭐": 1}


# ── MLB Stats API helpers ──────────────────────────────────────────────────────

def fetch_final_score(game_pk: int) -> dict | None:
    """Pull the final linescore from the MLB Stats API."""
    try:
        url = f"{MLB_STATS_API}/game/{game_pk}/linescore"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        home_runs = data.get("teams", {}).get("home", {}).get("runs")
        away_runs = data.get("teams", {}).get("away", {}).get("runs")
        if home_runs is None or away_runs is None:
            return None

        innings = data.get("innings", [])
        f5_total = sum(
            (inn.get("home", {}).get("runs") or 0) +
            (inn.get("away", {}).get("runs") or 0)
            for inn in innings[:5]
        )

        return {
            "total":     float(home_runs + away_runs),
            "f5_total":  float(f5_total),
            "home_runs": home_runs,
            "away_runs": away_runs,
        }
    except Exception as e:
        logger.warning(f"Could not fetch score for game_pk={game_pk}: {e}")
        return None


# ── classify_game (mirrors run_model.py logic) ─────────────────────────────────

def _classify(lean: str, confidence: str, score: float,
              line: float | None, proj_total: float | None) -> str:
    """Re-derive star rating from stored projection data."""
    if lean == "NEUTRAL":
        return "NO PLAY"

    edge = None
    has_line = line is not None and proj_total is not None
    if has_line:
        edge = abs(proj_total - line)

    if has_line and edge is not None:
        if confidence == "HIGH"   and edge >= 1.0: return "⭐⭐⭐"
        if confidence == "HIGH"   and edge >= 0.5: return "⭐⭐⭐"
        if confidence == "MEDIUM" and edge >= 0.5: return "⭐⭐"
        if confidence == "HIGH"   and edge >= 0.3: return "⭐⭐"
        if edge >= 0.3 and confidence != "LOW":    return "⭐"
        return "NO PLAY"
    else:
        if confidence == "HIGH"   and score >= 0.75: return "⭐⭐⭐"
        if confidence == "HIGH"   and score >= 0.50: return "⭐⭐"
        if confidence == "MEDIUM" and score >= 0.50: return "⭐⭐"
        if confidence == "MEDIUM":                   return "⭐"
        if confidence == "LOW"    and score >= 0.50: return "⭐"
        return "NO PLAY"


# ── result computation ─────────────────────────────────────────────────────────

def _compute_result(lean: str, actual_total: float | None,
                    line: float | None) -> str:
    if actual_total is None:
        return "PENDING"
    if line is None:
        return "NO_LINE"
    if actual_total > line:
        actual_dir = "OVER"
    elif actual_total < line:
        actual_dir = "UNDER"
    else:
        return "PUSH"

    if lean in ("OVER", "UNDER"):
        return "WIN" if lean == actual_dir else "LOSS"
    # NEUTRAL lean — record direction for retrospective analysis only
    return actual_dir


# ── core grader ────────────────────────────────────────────────────────────────

def grade_date(game_date: str) -> list[dict]:
    """
    Grade all projections for game_date against actual scores.
    Fetches scores from MLB Stats API if not yet stored.
    Returns list of graded_result dicts written to DB.
    """
    db.init_db()

    with db.get_conn() as conn:
        projections = conn.execute("""
            SELECT p.*, r.actual_total, r.actual_f5_total, r.line_full
            FROM projections p
            LEFT JOIN results r
              ON p.game_pk = r.game_pk AND p.game_date = r.game_date
            WHERE p.game_date = ?
            ORDER BY p.home_team
        """, (game_date,)).fetchall()

    if not projections:
        logger.warning(f"No projections found for {game_date}")
        return []

    graded = []
    for row in projections:
        gk   = row["game_pk"]
        home = row["home_team"]
        away = row["away_team"]

        # ── actual score ──────────────────────────────────────────────────────
        actual_total = row["actual_total"]
        if actual_total is None:
            score = fetch_final_score(gk)
            if score:
                actual_total = score["total"]
                db.log_result(gk, game_date,
                              actual_total=actual_total,
                              actual_f5_total=score["f5_total"])
                logger.info(f"  {away} @ {home}: {away} {score['away_runs']} — "
                            f"{home} {score['home_runs']} (Total {actual_total})")
            else:
                logger.info(f"  {away} @ {home}: not final yet")

        # ── parse factors JSON ────────────────────────────────────────────────
        factors = {}
        if row["factors_json"]:
            try:
                factors = json.loads(row["factors_json"])
            except Exception:
                pass

        # ── lean + star_rating ────────────────────────────────────────────────
        lean       = row["lean"] or factors.get("lean") or "NEUTRAL"
        line       = row["line_full"]
        proj_total = row["proj_total_full"]
        confidence = row["confidence"] or "LOW"
        conf_score = row["confidence_score"] or 0.0

        star_rating = row["star_rating"] or _classify(
            lean, confidence, conf_score, line, proj_total
        )
        star_count = _STAR_COUNT.get(star_rating, 0)
        was_a_play = 1 if star_rating != "NO PLAY" else 0

        # ── edge + error ──────────────────────────────────────────────────────
        edge             = (proj_total - line) if (proj_total and line) else None
        projection_error = (actual_total - proj_total) if (actual_total and proj_total) else None
        result           = _compute_result(lean, actual_total, line)

        graded_row = {
            "game_date":            game_date,
            "game_pk":              gk,
            "home_team":            home,
            "away_team":            away,
            "projected_total":      proj_total,
            "recommendation":       lean,
            "star_rating":          star_rating,
            "star_count":           star_count,
            "confidence":           confidence,
            "confidence_score":     conf_score,
            "was_a_play":           was_a_play,
            "line":                 line,
            "edge":                 edge,
            "actual_total":         actual_total,
            "projection_error":     projection_error,
            "result":               result,
            "sp_home":              row["home_sp"],
            "sp_away":              row["away_sp"],
            "sp_home_xfip":         row["home_sp_xfip"],
            "sp_away_xfip":         row["away_sp_xfip"],
            "home_wrc_plus":        row["home_wrc_plus"],
            "away_wrc_plus":        row["away_wrc_plus"],
            "park_factor":          row["park_factor"],
            "temperature":          factors.get("temperature_f"),
            "wind_speed":           factors.get("wind_speed_mph"),
            "wind_direction":       factors.get("wind_direction"),
            "wind_desc":            factors.get("wind_desc"),
            "umpire":               row["umpire_name"],
            "umpire_rating":        row["umpire_factor"],
            "home_bullpen_innings": factors.get("home_bp_innings_used"),
            "away_bullpen_innings": factors.get("away_bp_innings_used"),
        }

        db.write_graded_result(graded_row)
        graded.append(graded_row)

    wins   = sum(1 for g in graded if g["result"] == "WIN")
    losses = sum(1 for g in graded if g["result"] == "LOSS")
    plays  = sum(1 for g in graded if g["was_a_play"])
    logger.info(f"Graded {len(graded)} games for {game_date}. "
                f"Plays: {plays}  W/L: {wins}-{losses}")
    return graded


def grade_yesterday() -> list[dict]:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    logger.info(f"Grading results for {yesterday} ...")
    return grade_date(yesterday)


# ── summary ────────────────────────────────────────────────────────────────────

def print_summary(days: int = 30) -> None:
    db.init_db()
    with db.get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM graded_results
            WHERE game_date >= date('now', ? || ' days')
            ORDER BY game_date DESC
        """, (f"-{days}",)).fetchall()
    rows = [dict(r) for r in rows]

    plays  = [r for r in rows if r["was_a_play"]]
    graded = [r for r in plays if r["result"] in ("WIN", "LOSS", "PUSH")]

    wins   = sum(1 for r in graded if r["result"] == "WIN")
    losses = sum(1 for r in graded if r["result"] == "LOSS")
    pushes = sum(1 for r in graded if r["result"] == "PUSH")
    no_line = sum(1 for r in plays if r["result"] == "NO_LINE")
    decided = wins + losses

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  RESULTS SUMMARY — Last {days} days")
    print(f"{'='*60}{Style.RESET_ALL}\n")
    print(f"  Total projected games: {len(rows)}")
    print(f"  Total plays:  {len(plays)}")
    print(f"  Graded (W/L): {decided}  |  No line: {no_line}\n")

    if decided > 0:
        pct = wins / decided * 100
        roi = (wins * 0.9091 - losses) / decided * 100
        color = Fore.GREEN if pct >= 55 else Fore.YELLOW if pct >= 50 else Fore.RED
        print(f"  Record: {color}{wins}-{losses}{Style.RESET_ALL} "
              f"({pct:.1f}%)  |  ROI: {roi:+.1f}%  |  Pushes: {pushes}\n")

    for label, sc in [("⭐⭐⭐", 3), ("⭐⭐", 2), ("⭐", 1)]:
        sub = [r for r in graded if r.get("star_count") == sc]
        if not sub:
            continue
        w = sum(1 for r in sub if r["result"] == "WIN")
        l = sum(1 for r in sub if r["result"] == "LOSS")
        n = w + l
        pct = w / n * 100 if n else 0
        c = Fore.GREEN if pct >= 55 else Fore.YELLOW if pct >= 50 else Fore.RED
        print(f"  {label}: {w}-{l} ({c}{pct:.1f}%{Style.RESET_ALL})")
    print()


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLB Results Tracker")
    parser.add_argument("--date", "-d", default=None,
                        help="Grade YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--summary", "-s", action="store_true",
                        help="Print season summary")
    parser.add_argument("--days", type=int, default=30,
                        help="Days to include in summary")
    args = parser.parse_args()

    if args.summary:
        print_summary(days=args.days)
    else:
        target = args.date or (date.today() - timedelta(days=1)).isoformat()
        grade_date(target)
