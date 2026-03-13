#!/usr/bin/env python3
"""
Pre-game refresh — detects SP scratches, batter scratches, and re-runs projections.

Run at noon, 3pm, and 5:30pm via launchd.  Compares current probable pitchers
and confirmed lineups against what was stored at the 7am model run, flags
changes, adjusts projections, and pushes updated results.json to GitHub.

Usage:
  python refresh.py              # refresh all today's games
  python refresh.py --game 12345 # refresh a single game_pk
  python refresh.py --date 2025-04-15
  python refresh.py --no-push    # run without git push
"""

import argparse
import json
import logging
import os
import sys
from datetime import date

from colorama import Fore, Style, init as colorama_init

import db
from config import LOGS_DIR
from modules.schedule        import fetch_schedule
from modules.pitchers        import build_pitcher_db, get_pitcher_metrics
from modules.offense         import build_offense_db, get_team_offense
from modules.weather         import fetch_weather
from modules.bullpen         import calculate_bullpen_fatigue, build_team_bullpen_db
from modules.umpires         import get_umpire_rating
from modules.projections     import project_game
from modules.odds            import fetch_all_lines, get_game_lines, edge_summary
from modules.lineup_monitor  import (
    detect_sp_changes, detect_batter_scratches, downgrade_confidence,
)
from modules.props_data        import build_pitcher_k_db, build_batter_props_db, get_team_top_batters
from modules.line_tracker      import update_closing_lines
from modules.props_projections import get_game_props
from modules.props_odds        import fetch_props_lines

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

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


# ── git push helper ───────────────────────────────────────────────────────────

def _git_push(game_date: str, files: list[str]) -> bool:
    import subprocess

    def run(cmd):
        r = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        if r.returncode != 0:
            logger.error(f"git {' '.join(cmd[1:])}: {r.stderr.strip()}")
            return False
        return True

    for f in files:
        if not run(["git", "add", f]):
            return False

    status = subprocess.run(
        ["git", "status", "--porcelain"] + files,
        cwd=REPO_DIR, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        logger.info("Nothing to commit — results.json unchanged.")
        return True

    if not run(["git", "commit", "-m", f"refresh: {game_date}"]):
        return False
    if not run(["git", "push"]):
        return False
    logger.info("Pushed refresh to GitHub.")
    return True


# ── results.json rebuilder ────────────────────────────────────────────────────

def _rebuild_results_json(
    game_date: str,
    games: list[dict],
    all_lines: dict,
    lineup_change_alerts: list[dict],
    transaction_alerts: list[dict],
) -> dict:
    """
    Re-read all projections from DB for game_date, re-serialize to the same
    shape as push_results.py, including alert data.
    """
    from datetime import datetime
    from run_model import classify_game, generate_summary

    game_index = {g["game_pk"]: g for g in games}

    with db.get_conn() as conn:
        proj_rows = conn.execute(
            "SELECT * FROM projections WHERE game_date = ? ORDER BY home_team",
            (game_date,),
        ).fetchall()

    props_rows = db.get_props_for_date(game_date)
    props_by_game: dict[int, list] = {}
    for p in props_rows:
        props_by_game.setdefault(p["game_pk"], []).append({
            "player_name": p["player_name"],
            "team":        p.get("team"),
            "market":      p["market"],
            "projection":  p.get("projection"),
            "line":        p.get("line"),
            "lean":        p.get("lean"),
            "edge":        p.get("edge"),
            "edge_pct":    p.get("edge_pct"),
            "is_play":     bool(p.get("is_play")),
        })

    lc_by_game: dict[int, list] = {}
    for a in lineup_change_alerts:
        lc_by_game.setdefault(a["game_pk"], []).append(a)

    def _safe(v):
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        return str(v)

    star_order = {"⭐⭐⭐": 0, "⭐⭐": 1, "⭐": 2}
    plays, no_plays = [], []

    for row in proj_rows:
        gk   = row["game_pk"]
        game = game_index.get(gk)
        if game is None:
            continue

        factors = {}
        if row["factors_json"]:
            try:
                factors = json.loads(row["factors_json"])
            except Exception:
                pass

        proj = {
            "proj_total_full":  row["proj_total_full"],
            "proj_total_f5":    row["proj_total_f5"],
            "confidence":       row["confidence"] or "LOW",
            "confidence_score": row["confidence_score"] or 0.0,
            "lean":             row["lean"] or "NEUTRAL",
            "factors":          factors,
        }

        odds    = get_game_lines(game["home_team"], game["away_team"], all_lines)
        fe      = edge_summary(proj["proj_total_full"], odds.get("full") or {})
        f5e     = edge_summary(proj["proj_total_f5"],   odds.get("f5")   or {})
        rating  = classify_game(proj, fe)
        summary = generate_summary(game, proj, odds, rating)

        game_alerts = [
            {
                "type":             a["change_type"],
                "player_out":       a["player_out"],
                "player_in":        a.get("player_in"),
                "old_projection":   a.get("old_projection"),
                "new_projection":   a.get("new_projection"),
                "projection_delta": a.get("projection_delta"),
                "old_confidence":   a.get("old_confidence"),
                "new_confidence":   a.get("new_confidence"),
            }
            for a in lc_by_game.get(gk, [])
        ]

        block = {
            "rating":    rating,
            "game":      {k: _safe(v) for k, v in game.items()},
            "proj": {
                "lean":             proj["lean"],
                "proj_total_full":  proj["proj_total_full"],
                "proj_total_f5":    proj["proj_total_f5"],
                "confidence":       proj["confidence"],
                "confidence_score": proj["confidence_score"],
                "factors":          {k: _safe(v) for k, v in factors.items()},
            },
            "full_edge": {k: _safe(v) for k, v in fe.items()},
            "f5_edge":   {k: _safe(v) for k, v in f5e.items()},
            "summary":   summary,
            "props":     props_by_game.get(gk, []),
            "alerts":    game_alerts,
        }
        (plays if rating != "NO PLAY" else no_plays).append(block)

    plays.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -(b["proj"]["confidence_score"] or 0),
    ))

    from modules.parlays import build_all_parlays
    parlays = build_all_parlays(plays)

    # Persist updated parlays to DB
    for ptype, legs in parlays.items():
        if legs:
            db.write_parlay(game_date, ptype, legs)

    record = db.get_season_record()

    return {
        "generated_at":  datetime.utcnow().isoformat() + "Z",
        "game_date":     game_date,
        "plays":         plays,
        "no_plays":      no_plays,
        "parlay":        parlays["parlay_3"],   # legacy key
        "parlay_3":      parlays["parlay_3"],
        "parlay_5":      parlays["parlay_5"],
        "parlay_7":      parlays["parlay_7"],
        "season_record": {k: _safe(v) for k, v in record.items()} if record else {},
        "alerts":        lineup_change_alerts,
        "transactions":  transaction_alerts,
    }


# ── main refresh logic ────────────────────────────────────────────────────────

def refresh_games(
    game_date: str = None,
    target_game_pk: int = None,
    push: bool = True,
) -> None:
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
            logger.error(f"Game {target_game_pk} not found.")
            return

    pitcher_db      = build_pitcher_db()
    team_bullpen_db = build_team_bullpen_db(pitcher_db)
    offense_db      = build_offense_db()
    pitcher_k_db    = build_pitcher_k_db()
    batter_props_db = build_batter_props_db()

    all_lines = {}
    try:
        all_lines = fetch_all_lines()
    except Exception as e:
        logger.warning(f"Odds fetch failed (continuing without lines): {e}")

    odds_key    = os.environ.get("ODDS_API_KEY", "")
    any_changes = False

    for game in games:
        gk   = game["game_pk"]
        home = game["home_team"]
        away = game["away_team"]

        # Load stored projection
        with db.get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM projections WHERE game_pk = ? AND game_date = ?",
                (gk, game_date),
            ).fetchone()

        stored_home_sp = existing["home_sp"] if existing else None
        stored_away_sp = existing["away_sp"] if existing else None

        # Detect SP changes vs live probable pitchers
        sp_changes = detect_sp_changes(gk, stored_home_sp, stored_away_sp)

        # Re-run full projection (new schedule already has updated SPs)
        home_sp  = get_pitcher_metrics(game["home_probable_pitcher"], pitcher_db)
        away_sp  = get_pitcher_metrics(game["away_probable_pitcher"], pitcher_db)
        home_off = get_team_offense(home, offense_db,
                                    opp_throws=game["away_probable_pitcher"].get("throws"))
        away_off = get_team_offense(away, offense_db,
                                    opp_throws=game["home_probable_pitcher"].get("throws"))
        weather  = fetch_weather(home, game_time_et=game.get("game_time"))
        umpire   = get_umpire_rating(game.get("home_umpire"))
        home_bp  = calculate_bullpen_fatigue(game["home_team_id"], is_home=True, team_abb=home, team_bullpen_db=team_bullpen_db)
        away_bp  = calculate_bullpen_fatigue(game["away_team_id"], is_home=False, team_abb=away, team_bullpen_db=team_bullpen_db)

        proj = project_game(
            home_team=home, away_team=away,
            home_sp_metrics=home_sp, away_sp_metrics=away_sp,
            home_offense=home_off, away_offense=away_off,
            weather=weather, umpire=umpire,
            home_bullpen=home_bp, away_bullpen=away_bp,
        )

        old_total = existing["proj_total_full"] if existing else None
        old_conf  = existing["confidence"]       if existing else None

        # Apply confidence downgrade if SP changed
        if sp_changes:
            any_changes = True
            downgrade_confidence(proj)
            new_total = proj["proj_total_full"]
            new_conf  = proj["confidence"]
            delta     = round(new_total - old_total, 2) if old_total is not None else None

            for chg in sp_changes:
                side = chg["side"]
                print(
                    f"\n{Fore.RED}🚨 SP SCRATCH — {away} @ {home}{Style.RESET_ALL}\n"
                    f"  {side.upper()} SP: {chg['player_out']} → {chg['player_in']}\n"
                    f"  Projection: {old_total:.1f} → {new_total:.1f}  "
                    f"  Confidence: {old_conf} → {new_conf}"
                )
                change_type = f"SP_SCRATCH_{side.upper()}"
                db.write_lineup_change({
                    "game_pk":          gk,
                    "game_date":        game_date,
                    "home_team":        home,
                    "away_team":        away,
                    "change_type":      change_type,
                    "player_out":       chg["player_out"],
                    "player_in":        chg["player_in"],
                    "old_projection":   old_total,
                    "new_projection":   new_total,
                    "projection_delta": delta,
                    "old_confidence":   old_conf,
                    "new_confidence":   new_conf,
                })
        else:
            # Log non-SP changes for visibility
            if existing:
                new_total = proj["proj_total_full"]
                old_wind  = existing["wind_speed"] or 0
                new_wind  = proj["factors"].get("wind_speed_mph") or 0
                notes = []
                if abs(new_wind - old_wind) >= 5:
                    notes.append(f"wind {old_wind:.0f}→{new_wind:.0f}mph")
                if abs(new_total - old_total) >= 0.5:
                    notes.append(f"total {old_total:.1f}→{new_total:.1f}")
                if notes:
                    logger.info(f"  {away} @ {home}: {'; '.join(notes)}")
                    any_changes = True
            else:
                logger.info(f"  {away} @ {home}: total={proj['proj_total_full']:.1f}")

        # Check batter scratches vs top TB props
        top_batters = {
            home: get_team_top_batters(home, batter_props_db, n=3),
            away: get_team_top_batters(away, batter_props_db, n=3),
        }
        batter_scratches = detect_batter_scratches(gk, home, away, top_batters)

        for scratch in batter_scratches:
            any_changes = True
            team  = scratch["team"]
            pname = scratch["player_out"]
            print(
                f"\n{Fore.YELLOW}⚠️  BATTER SCRATCH — {away} @ {home}{Style.RESET_ALL}\n"
                f"  {pname} ({team}) not in confirmed lineup — TB prop invalidated"
            )
            db.write_lineup_change({
                "game_pk":          gk,
                "game_date":        game_date,
                "home_team":        home,
                "away_team":        away,
                "change_type":      "BATTER_SCRATCH",
                "player_out":       pname,
                "player_in":        None,
                "old_projection":   None,
                "new_projection":   None,
                "projection_delta": None,
                "old_confidence":   None,
                "new_confidence":   None,
            })
            # Invalidate TB prop in DB
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE props SET is_play = 0 "
                    "WHERE game_pk = ? AND game_date = ? "
                    "AND player_name = ? AND market = 'TB'",
                    (gk, game_date, pname),
                )

        # Persist updated projection
        from run_model import classify_game
        _fe = edge_summary(
            proj["proj_total_full"],
            get_game_lines(home, away, all_lines).get("full") or {},
        )
        f = proj["factors"]
        db.upsert_projection({
            "game_date":        game_date,
            "game_pk":          gk,
            "home_team":        home,
            "away_team":        away,
            "home_sp":          home_sp.get("name"),
            "away_sp":          away_sp.get("name"),
            "home_sp_xfip":     home_sp.get("xfip"),
            "away_sp_xfip":     away_sp.get("xfip"),
            "home_sp_siera":    home_sp.get("siera"),
            "away_sp_siera":    away_sp.get("siera"),
            "home_wrc_plus":    home_off.get("wrc_plus"),
            "away_wrc_plus":    away_off.get("wrc_plus"),
            "park_factor":      f.get("park_factor"),
            "wind_speed":       f.get("wind_speed_mph"),
            "wind_direction":   f.get("wind_direction"),
            "temperature":      f.get("temperature_f"),
            "umpire_name":      f.get("umpire_name"),
            "umpire_factor":    f.get("umpire_runs_factor"),
            "home_bp_fatigue":  f.get("home_bp_fatigue"),
            "away_bp_fatigue":  f.get("away_bp_fatigue"),
            "proj_total_full":  proj["proj_total_full"],
            "proj_total_f5":    proj["proj_total_f5"],
            "confidence":       proj["confidence"],
            "confidence_score": proj["confidence_score"],
            "factors_json":     proj["factors"],
            "lean":             proj["lean"],
            "star_rating":      classify_game(proj, _fe),
        })

        # Re-run props if SP changed or batter scratched
        if sp_changes or batter_scratches:
            try:
                props_lines = fetch_props_lines(
                    home, away, game_date, odds_api_key=odds_key or None
                )
                props = get_game_props(
                    game         = game,
                    home_sp_name = home_sp.get("name", ""),
                    away_sp_name = away_sp.get("name", ""),
                    factors      = proj["factors"],
                    umpire       = umpire,
                    pitcher_k_db = pitcher_k_db,
                    batter_db    = batter_props_db,
                    props_lines  = props_lines,
                )
                scratched_names = {s["player_out"].lower() for s in batter_scratches}
                for p in props:
                    is_play = (
                        False if p["player_name"].lower() in scratched_names
                        else p.get("is_play", False)
                    )
                    db.write_prop({
                        "game_date":   game_date,
                        "game_pk":     gk,
                        "player_name": p["player_name"],
                        "team":        p.get("team", ""),
                        "market":      p["market"],
                        "projection":  p["projection"],
                        "line":        p.get("line"),
                        "edge":        p.get("edge"),
                        "edge_pct":    p.get("edge_pct"),
                        "lean":        p.get("lean"),
                        "is_play":     1 if is_play else 0,
                    })
            except Exception as e:
                logger.warning(f"Props re-run failed for {away}@{home}: {e}")

    # Reload all alerts from DB (includes those detected in prior refreshes today)
    all_lc_alerts = db.get_lineup_changes_for_date(game_date)
    game_lkp = {g["game_pk"]: g for g in games}
    for a in all_lc_alerts:
        if "matchup" not in a or not a.get("matchup"):
            g = game_lkp.get(a.get("game_pk"), {})
            a["matchup"] = f"{g.get('away_team','')} @ {g.get('home_team','')}"

    all_tx = db.get_transactions_for_date(game_date)

    # Rebuild results.json and push when changes found
    results_path = os.path.join(REPO_DIR, "results.json")
    payload = _rebuild_results_json(
        game_date, games, all_lines, all_lc_alerts, all_tx,
    )
    with open(results_path, "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
    logger.info(f"Wrote {results_path}")

    try:
        # Build results list in same format as run() for line tracker
        refresh_results = []
        for block in payload.get("plays", []) + payload.get("no_plays", []):
            refresh_results.append({
                "game": block.get("game", {}),
                "projection": block.get("proj", {}),
                "odds": {"full": {"consensus": block.get("full_edge", {}).get("consensus")}},
            })
        update_closing_lines(game_date, refresh_results)
    except Exception as e:
        logger.warning(f"Line tracker closing update failed (non-fatal): {e}")

    if push and any_changes:
        _git_push(game_date, ["results.json"])
    elif not push:
        logger.info("--no-push: skipping git push.")
    else:
        logger.info("No changes — skipping push.")

    # Console summary
    if any_changes:
        sp_cnt  = sum(1 for a in all_lc_alerts if "SP_SCRATCH" in a.get("change_type", ""))
        bat_cnt = sum(1 for a in all_lc_alerts if a.get("change_type") == "BATTER_SCRATCH")
        print(
            f"\n{Fore.CYAN}{'='*55}\n"
            f"REFRESH — {game_date}  |  "
            f"SP scratches: {sp_cnt}  Batter scratches: {bat_cnt}\n"
            f"{'='*55}{Style.RESET_ALL}"
        )
    else:
        print(f"\n{Fore.GREEN}No significant changes for {game_date}.{Style.RESET_ALL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-game refresh")
    parser.add_argument("--date",    "-d", default=None,  help="Game date YYYY-MM-DD")
    parser.add_argument("--game",    "-g", type=int, default=None, help="Specific game_pk")
    parser.add_argument("--no-push", action="store_true", help="Skip git push")
    args = parser.parse_args()
    refresh_games(
        game_date      = args.date,
        target_game_pk = args.game,
        push           = not args.no_push,
    )
