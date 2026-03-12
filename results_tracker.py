#!/usr/bin/env python3
"""
Results tracker — log actual game totals and compare vs projections.

Usage:
  python results_tracker.py --date 2025-04-14           # auto-fetch all results for a date
  python results_tracker.py --game 12345 --total 8.5    # log one game manually
  python results_tracker.py --game 12345 --total 8.5 --f5 4.0 --line 8.0 --line-f5 4.5
  python results_tracker.py --summary                    # print season record
  python results_tracker.py --summary --days 30          # last 30 days
"""

import argparse
import logging
import sys
from datetime import date, timedelta

import requests
from colorama import Fore, Style, init as colorama_init
from tabulate import tabulate

import db
from config import MLB_STATS_API, TEAM_ID_TO_ABB

colorama_init(autoreset=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger("results_tracker")


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

        # F5 from innings
        innings = data.get("innings", [])
        f5_total = 0.0
        for inn in innings[:5]:
            f5_total += (inn.get("home", {}).get("runs") or 0)
            f5_total += (inn.get("away", {}).get("runs") or 0)

        return {
            "total":    float(home_runs + away_runs),
            "f5_total": float(f5_total),
            "home_runs": home_runs,
            "away_runs": away_runs,
        }
    except Exception as e:
        logger.warning(f"Could not fetch score for game_pk={game_pk}: {e}")
        return None


def auto_log_date(game_date: str, line_file: str = None) -> None:
    """
    Automatically pull final scores for all projected games on *game_date*
    and log them. Lines must be entered manually afterward (or from a file).
    """
    db.init_db()

    with db.get_conn() as conn:
        projections = conn.execute(
            "SELECT game_pk, home_team, away_team FROM projections WHERE game_date = ?",
            (game_date,)
        ).fetchall()

    if not projections:
        logger.warning(f"No projections found for {game_date}")
        return

    logged = 0
    for proj in projections:
        gk   = proj["game_pk"]
        home = proj["home_team"]
        away = proj["away_team"]

        score = fetch_final_score(gk)
        if not score:
            logger.info(f"  {away} @ {home}: Game not final yet or score unavailable.")
            continue

        db.log_result(
            game_pk=gk,
            game_date=game_date,
            actual_total=score["total"],
            actual_f5_total=score["f5_total"],
        )
        logger.info(f"  {away} @ {home}: {away} {score['away_runs']} — "
                    f"{home} {score['home_runs']} "
                    f"(Total {score['total']}, F5 {score['f5_total']})")
        logged += 1

    print(f"\n{Fore.GREEN}Logged {logged}/{len(projections)} results for {game_date}.{Style.RESET_ALL}")
    print(f"Run with --line to add betting lines for accuracy tracking.\n")


def manual_log(game_pk: int, game_date: str, actual_total: float,
               f5_total: float = None, line_full: float = None,
               line_f5: float = None) -> None:
    db.init_db()
    db.log_result(
        game_pk=game_pk,
        game_date=game_date,
        actual_total=actual_total,
        actual_f5_total=f5_total,
        line_full=line_full,
        line_f5=line_f5,
    )
    print(f"{Fore.GREEN}Logged result for game_pk={game_pk}.{Style.RESET_ALL}")


def update_line(game_pk: int, game_date: str, line_full: float = None,
                line_f5: float = None) -> None:
    """Update just the betting line for an already-logged result."""
    db.init_db()
    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM results WHERE game_pk = ? AND game_date = ?",
            (game_pk, game_date)
        ).fetchone()
        if not existing:
            print(f"{Fore.RED}No result found for game_pk={game_pk} on {game_date}.{Style.RESET_ALL}")
            return

        if line_full is not None:
            conn.execute("UPDATE results SET line_full = ?, result_full = CASE "
                         "WHEN actual_total > ? THEN 'OVER' "
                         "WHEN actual_total < ? THEN 'UNDER' ELSE 'PUSH' END "
                         "WHERE game_pk = ? AND game_date = ?",
                         (line_full, line_full, line_full, game_pk, game_date))
        if line_f5 is not None:
            conn.execute("UPDATE results SET line_f5 = ?, result_f5 = CASE "
                         "WHEN actual_f5_total > ? THEN 'OVER' "
                         "WHEN actual_f5_total < ? THEN 'UNDER' ELSE 'PUSH' END "
                         "WHERE game_pk = ? AND game_date = ?",
                         (line_f5, line_f5, line_f5, game_pk, game_date))
    print(f"{Fore.GREEN}Line updated for game_pk={game_pk}.{Style.RESET_ALL}")


def print_summary(days: int = 30) -> None:
    """Print a detailed performance summary."""
    db.init_db()
    recent = db.get_recent_projections(days=days)

    tracked = [r for r in recent if r.get("actual_total") is not None]
    with_lines = [r for r in tracked if r.get("line_full") is not None]

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  RESULTS SUMMARY — Last {days} days")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    print(f"  Total projections: {len(recent)}")
    print(f"  Games with results: {len(tracked)}")
    print(f"  Games with lines: {len(with_lines)}\n")

    if with_lines:
        correct = sum(1 for r in with_lines
                      if (r["result_full"] == "OVER" and r["proj_total_full"] > r["line_full"])
                      or (r["result_full"] == "UNDER" and r["proj_total_full"] < r["line_full"]))
        pushes  = sum(1 for r in with_lines if r["result_full"] == "PUSH")
        played  = len(with_lines) - pushes
        if played > 0:
            pct = correct / played * 100
            color = Fore.GREEN if pct >= 55 else Fore.YELLOW if pct >= 50 else Fore.RED
            print(f"  {color}Full-game record: {correct}-{played-correct} ({pct:.1f}%){Style.RESET_ALL}")

    # Per-confidence breakdown
    if with_lines:
        print(f"\n  By confidence level:")
        for conf in ("HIGH", "MEDIUM", "LOW"):
            subset = [r for r in with_lines if r.get("confidence") == conf]
            if not subset:
                continue
            c = sum(1 for r in subset
                    if (r["result_full"] == "OVER" and r["proj_total_full"] > r["line_full"])
                    or (r["result_full"] == "UNDER" and r["proj_total_full"] < r["line_full"]))
            p = sum(1 for r in subset if r["result_full"] == "PUSH")
            n = len(subset) - p
            pct = c / n * 100 if n > 0 else 0
            color = Fore.GREEN if pct >= 55 else Fore.YELLOW if pct >= 50 else Fore.RED
            print(f"    {conf:<8}: {c}-{n-c} ({color}{pct:.1f}%{Style.RESET_ALL})")

    # Recent results table
    if tracked:
        print(f"\n  Recent results (last 10 with results):\n")
        last10 = sorted(tracked, key=lambda r: r["game_date"], reverse=True)[:10]
        table_rows = []
        for r in last10:
            proj_str = f"{r['proj_total_full']:.1f}"
            act_str  = f"{r['actual_total']:.1f}"
            line_str = f"{r['line_full']:.1f}" if r.get("line_full") else "—"
            res_str  = r.get("result_full", "—") or "—"
            if res_str == "OVER":
                res_disp = f"{Fore.RED}OVER{Style.RESET_ALL}"
            elif res_str == "UNDER":
                res_disp = f"{Fore.CYAN}UNDER{Style.RESET_ALL}"
            else:
                res_disp = res_str

            table_rows.append([
                r["game_date"],
                f"{r['away_team']} @ {r['home_team']}",
                proj_str,
                line_str,
                act_str,
                res_disp,
                r.get("confidence", "?"),
            ])
        print(tabulate(table_rows,
                       headers=["Date", "Game", "Proj", "Line", "Actual", "Result", "Conf"],
                       tablefmt="rounded_outline"))

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLB Results Tracker")
    parser.add_argument("--date", "-d", default=None,
                        help="Auto-log all results for YYYY-MM-DD")
    parser.add_argument("--game", "-g", type=int, default=None,
                        help="game_pk for manual logging")
    parser.add_argument("--total", type=float, default=None,
                        help="Actual total runs for manual logging")
    parser.add_argument("--f5", type=float, default=None,
                        help="Actual F5 total for manual logging")
    parser.add_argument("--line", type=float, default=None,
                        help="Betting line (full game over/under)")
    parser.add_argument("--line-f5", type=float, default=None,
                        help="Betting line (F5 over/under)")
    parser.add_argument("--update-line", action="store_true",
                        help="Update an existing result's line only")
    parser.add_argument("--summary", "-s", action="store_true",
                        help="Print season summary")
    parser.add_argument("--days", type=int, default=30,
                        help="Days to include in summary (default 30)")
    args = parser.parse_args()

    today = date.today().isoformat()

    if args.summary:
        print_summary(days=args.days)
    elif args.update_line and args.game:
        update_line(args.game, args.date or today, args.line, args.line_f5)
    elif args.game and args.total is not None:
        manual_log(args.game, args.date or today, args.total,
                   f5_total=args.f5, line_full=args.line, line_f5=args.line_f5)
    elif args.date:
        auto_log_date(args.date)
    else:
        # Default: auto-log yesterday
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        print(f"Auto-logging results for {yesterday}...")
        auto_log_date(yesterday)
