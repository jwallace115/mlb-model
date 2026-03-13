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

def fetch_boxscore(game_pk: int) -> dict | None:
    """Fetch MLB Stats API boxscore for pitcher Ks and batter stats."""
    try:
        url = f"{MLB_STATS_API}/game/{game_pk}/boxscore"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Could not fetch boxscore for game_pk={game_pk}: {e}")
        return None


def _extract_stats_from_boxscore(boxscore: dict) -> dict:
    """
    Parse boxscore into {player_name.lower(): {"k": int, "tb": float}} lookups.
    TB = 1B + 2*2B + 3*3B + 4*HR.
    """
    stats: dict[str, dict] = {}
    if not boxscore:
        return stats

    for side in ("home", "away"):
        team_data = boxscore.get("teams", {}).get(side, {})

        # Pitchers — strikeouts
        pitchers = team_data.get("pitchers", [])
        players  = team_data.get("players", {})
        for pid in pitchers:
            pid_str = f"ID{pid}"
            p = players.get(pid_str, {})
            name = (
                p.get("person", {}).get("fullName") or
                p.get("person", {}).get("lastName") or ""
            )
            ks = (p.get("stats", {})
                   .get("pitching", {})
                   .get("strikeOuts", 0)) or 0
            if name:
                key = name.lower()
                stats[key] = stats.get(key, {})
                stats[key]["k"] = int(ks)

        # Batters — total bases
        batters = team_data.get("batters", [])
        for pid in batters:
            pid_str = f"ID{pid}"
            p = players.get(pid_str, {})
            name = (
                p.get("person", {}).get("fullName") or
                p.get("person", {}).get("lastName") or ""
            )
            batting = p.get("stats", {}).get("batting", {})
            h   = int(batting.get("hits", 0) or 0)
            d   = int(batting.get("doubles", 0) or 0)
            t   = int(batting.get("triples", 0) or 0)
            hr  = int(batting.get("homeRuns", 0) or 0)
            singles = h - d - t - hr
            tb = singles + 2*d + 3*t + 4*hr
            if name and h >= 0:
                key = name.lower()
                stats[key] = stats.get(key, {})
                stats[key]["tb"] = float(tb)

    return stats


def grade_props_for_date(game_date: str) -> int:
    """
    Grade all ungraded prop bets for game_date using MLB boxscore API.
    Returns count of props graded.
    """
    props = db.get_props_for_date(game_date)
    ungraded = [p for p in props if p.get("result") is None and p.get("is_play")]
    if not ungraded:
        return 0

    # Group by game_pk to minimize API calls
    by_game: dict[int, list] = {}
    for p in ungraded:
        by_game.setdefault(p["game_pk"], []).append(p)

    graded_count = 0
    for game_pk, game_props in by_game.items():
        boxscore = fetch_boxscore(game_pk)
        actuals  = _extract_stats_from_boxscore(boxscore)
        if not actuals:
            continue

        for p in game_props:
            player_key = (p["player_name"] or "").lower()
            market     = p.get("market", "")
            line       = p.get("line")
            lean       = p.get("lean")

            # Try exact match, then last-name fallback
            actual_row = actuals.get(player_key)
            if actual_row is None:
                parts = player_key.split()
                if parts:
                    last = parts[-1]
                    candidates = [(k, v) for k, v in actuals.items()
                                  if k.endswith(last)]
                    if len(candidates) == 1:
                        actual_row = candidates[0][1]

            if actual_row is None:
                continue

            actual_val = actual_row.get(market.lower())
            if actual_val is None:
                continue

            # Compute result
            if line is None:
                result = "NO_LINE"
            elif actual_val > line:
                result = "WIN" if lean == "OVER" else "LOSS"
            elif actual_val < line:
                result = "WIN" if lean == "UNDER" else "LOSS"
            else:
                result = "PUSH"

            db.write_prop({
                "game_date":   game_date,
                "game_pk":     game_pk,
                "player_name": p["player_name"],
                "team":        p.get("team", ""),
                "market":      market,
                "projection":  p.get("projection"),
                "line":        line,
                "edge":        p.get("edge"),
                "edge_pct":    p.get("edge_pct"),
                "lean":        lean,
                "is_play":     p.get("is_play", 0),
                "actual":      actual_val,
                "result":      result,
            })
            graded_count += 1
            logger.info(f"  Prop graded: {p['player_name']} {market} "
                        f"proj={p.get('projection')} line={line} "
                        f"actual={actual_val} → {result}")

    return graded_count


def grade_parlays_for_date(game_date: str) -> int:
    """
    Grade all pending parlays for game_date.
    A parlay hits only if every leg wins. Returns count of parlays graded.
    """
    parlays = db.get_parlays_for_date(game_date)
    pending = [p for p in parlays if p.get("hit") is None and p.get("legs")]
    if not pending:
        return 0

    # Pre-load result lookups for this date
    graded_by_pk = {
        r["game_pk"]: r
        for r in db.get_all_graded_results()
        if r["game_date"] == game_date
    }
    props_by_key = {
        (p["game_pk"], p["player_name"], p["market"]): p
        for p in db.get_props_for_date(game_date)
    }
    with db.get_conn() as conn:
        f5_by_pk = {
            r["game_pk"]: dict(r)
            for r in conn.execute(
                "SELECT * FROM results WHERE game_date = ?", (game_date,)
            ).fetchall()
        }

    graded_count = 0
    for parlay in pending:
        legs       = parlay["legs"]
        legs_won   = 0
        all_done   = True

        for leg in legs:
            market  = leg.get("market", "")
            lean    = leg.get("lean", "OVER")
            game_pk = leg.get("game_pk")

            if market == "full":
                gr = graded_by_pk.get(game_pk)
                if gr and gr.get("result") in ("WIN", "LOSS", "PUSH"):
                    if gr["result"] == "WIN":
                        legs_won += 1
                else:
                    all_done = False

            elif market == "f5":
                f5r = f5_by_pk.get(game_pk)
                if f5r and f5r.get("result_f5") in ("OVER", "UNDER", "PUSH"):
                    if f5r["result_f5"] == lean:
                        legs_won += 1
                else:
                    all_done = False

            elif market in ("K", "TB"):
                pname = leg.get("player_name")
                pr = props_by_key.get((game_pk, pname, market))
                if pr and pr.get("result") in ("WIN", "LOSS", "PUSH"):
                    if pr["result"] == "WIN":
                        legs_won += 1
                else:
                    all_done = False

        if all_done:
            hit = 1 if legs_won == len(legs) else 0
            db.update_parlay_result(game_date, parlay["parlay_type"], hit, legs_won)
            graded_count += 1
            logger.info(
                f"  Parlay {parlay['parlay_type']}: "
                f"{legs_won}/{len(legs)} legs — {'HIT' if hit else 'MISS'}"
            )

    return graded_count


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

    # Grade any prop bets for this date
    props_graded = grade_props_for_date(game_date)
    if props_graded:
        logger.info(f"Graded {props_graded} props for {game_date}")

    # Grade parlays for this date
    parlays_graded = grade_parlays_for_date(game_date)
    if parlays_graded:
        logger.info(f"Graded {parlays_graded} parlays for {game_date}")

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
