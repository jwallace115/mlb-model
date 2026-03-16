#!/usr/bin/env python3
"""
NBA Results Tracker — Phase 7.

Runs at the START of the 7 AM morning card (not as a separate job).
West coast games finish late — we grade them the following morning.

Pipeline:
  1. Load yesterday's NBA projections (saved by the prior run)
  2. Pull completed game scores from the NBA games cache (refreshed by phase4b)
  3. Match projections to actual scores — full-game and H1 where available
  4. Log results (actual vs projected, hit/miss by confidence tier)
  5. Update and print running season accuracy stats
  6. Flag any game where model/market gap > MARKET_FLAG_THRESHOLD

H1 coverage note:
  2025-26 H1 data gaps persist (ScoreboardV2 limitation). H1 results are
  tracked only for games where H1 actual is available. Coverage will improve
  as the season progresses or a better H1 source is added.
"""

import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd
from datetime import date, timedelta

from nba.config import (
    CACHE_DIR,
    CURRENT_SEASON,
    MARKET_FLAG_THRESHOLD,
    NBA_API_TIMEOUT,
    NBA_PROJECTIONS_PATH,
    NBA_RESULTS_LOG_PATH,
)

logger = logging.getLogger(__name__)

SEP  = "═" * 68
SEP2 = "─" * 68


# ── OT diagnostic data (ScoreboardV2 line scores) ────────────────────────────

def _ot_cache_path(game_date: str) -> str:
    return os.path.join(CACHE_DIR, f"ot_data_{game_date}.json")


def fetch_ot_data(game_date: str) -> dict:
    """
    Fetch quarter-by-quarter scores for game_date from ScoreboardV2.
    Returns {game_id: {"went_to_ot": 0/1, "regulation_total": float or None}}.
    Caches to disk. Gracefully returns {} on any API failure.
    Shadow diagnostic only — does not affect official grading.
    """
    cache_path = _ot_cache_path(game_date)
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(f"OT data loaded from cache for {game_date}: {len(data)} games")
            return data
        except Exception:
            pass

    try:
        from nba_api.stats.endpoints import scoreboardv2
        from nba.modules.fetch_games import _call_with_retry
        date_str = pd.Timestamp(game_date).strftime("%m/%d/%Y")
        board = _call_with_retry(
            scoreboardv2.ScoreboardV2,
            game_date=date_str,
            day_offset=0,
            league_id="00",
            timeout=NBA_API_TIMEOUT,
        )
        time.sleep(0.6)
        ls = board.get_data_frames()[1]   # LineScore (index 1)
    except Exception as e:
        logger.warning(f"OT data fetch failed for {game_date}: {e}")
        return {}

    if ls.empty:
        return {}

    qt_cols = ["PTS_QTR1", "PTS_QTR2", "PTS_QTR3", "PTS_QTR4"]
    ot_cols = [f"PTS_OT{i}" for i in range(1, 11)]

    result = {}
    for gid, grp in ls.groupby("GAME_ID"):
        gid_str = str(gid)
        # OT detection: any OT column with score > 0
        ot_pts = sum(
            int(grp[c].fillna(0).sum())
            for c in ot_cols if c in grp.columns
        )
        went_to_ot = 1 if ot_pts > 0 else 0

        # Regulation total: sum of all 4 quarters for both teams
        reg_total = None
        if all(c in grp.columns for c in qt_cols):
            vals = grp[qt_cols].fillna(0).values
            if not (vals == 0).all():     # data present (not all zeroes)
                reg_total = float(vals.sum())

        result[gid_str] = {"went_to_ot": went_to_ot, "regulation_total": reg_total}

    try:
        with open(cache_path, "w") as f:
            json.dump(result, f)
    except Exception:
        pass

    logger.info(f"OT data fetched for {game_date}: {len(result)} games")
    return result


# ── Load previous projections ─────────────────────────────────────────────────

def load_yesterday_projections(game_date: str) -> pd.DataFrame:
    """Load projections saved from yesterday's morning run."""
    if not os.path.exists(NBA_PROJECTIONS_PATH):
        logger.info("No NBA projections file found — skipping results logging")
        return pd.DataFrame()

    projs = pd.read_parquet(NBA_PROJECTIONS_PATH)
    yesterday = (pd.Timestamp(game_date) - timedelta(days=1)).date().isoformat()
    projs_yday = projs[projs["game_date"] == yesterday].copy()
    logger.info(f"Found {len(projs_yday)} projections for {yesterday}")
    return projs_yday


# ── Fetch actual scores ───────────────────────────────────────────────────────

def fetch_actual_scores(game_date: str) -> pd.DataFrame:
    """
    Pull actual scores for yesterday's games from the NBA games cache.
    Uses fetch_season to get the most recent completed games.
    """
    yesterday = (pd.Timestamp(game_date) - timedelta(days=1)).date().isoformat()
    try:
        from nba.modules.fetch_games import fetch_season
        games = fetch_season(CURRENT_SEASON)
        if games.empty:
            return pd.DataFrame()
        games["date"] = pd.to_datetime(games["date"])
        yday_games = games[games["date"].dt.date.astype(str) == yesterday].copy()
        logger.info(f"Found {len(yday_games)} completed games for {yesterday}")
        return yday_games
    except Exception as e:
        logger.warning(f"Failed to fetch actual scores: {e}")
        return pd.DataFrame()


# ── Grade and log ─────────────────────────────────────────────────────────────

def grade_and_log(projs: pd.DataFrame, actuals: pd.DataFrame, game_date: str) -> pd.DataFrame:
    """
    Match projections to actuals and produce a results DataFrame.
    Returns graded results with columns:
      game_date, game_id, home_team, away_team,
      pred_total, actual_total, full_err, full_correct,
      pred_h1, actual_h1_total, h1_err, h1_correct,
      confidence, line, edge, market_gap_flag
    """
    if projs.empty or actuals.empty:
        return pd.DataFrame()

    rows = []
    yesterday = (pd.Timestamp(game_date) - timedelta(days=1)).date().isoformat()

    # Shadow OT diagnostic layer — fetch quarter scores for yesterday
    ot_data = fetch_ot_data(yesterday)

    for _, proj in projs.iterrows():
        gid  = proj.get("game_id")
        home = proj.get("home_team")
        away = proj.get("away_team")

        # Match by game_id first, then by team pair
        match = actuals[actuals["game_id"] == gid]
        if match.empty:
            match = actuals[
                (actuals["home_team"] == home) & (actuals["away_team"] == away)
            ]
        if match.empty:
            logger.debug(f"No actual score found for {away}@{home} ({gid})")
            continue

        actual = match.iloc[0]
        actual_total = actual.get("actual_total")
        if pd.isna(actual_total) or actual_total < 150:
            # Game incomplete or postponed
            continue
        actual_total = float(actual_total)

        pred_total  = float(proj.get("pred_total", 0) or 0)
        line        = proj.get("line")
        edge        = proj.get("edge")
        confidence  = proj.get("confidence", "LOW")
        lean        = proj.get("lean", "NEUTRAL")
        rolling_avg = proj.get("rolling_league_avg", 228.5)

        full_err    = pred_total - actual_total
        # Directional: did model lean in the right direction vs rolling avg?
        pred_over   = pred_total > rolling_avg
        actual_over = actual_total > rolling_avg
        full_correct = int(pred_over == actual_over)

        # Market gap flag
        if line is not None and abs(pred_total - float(line)) > MARKET_FLAG_THRESHOLD:
            market_gap_flag = 1
        else:
            market_gap_flag = 0

        # H1 — may not be available
        pred_h1       = proj.get("pred_h1")
        h1_line       = proj.get("h1_line")
        h1_rolling    = proj.get("rolling_h1_league_avg")

        # H1 actual — will be None until we fetch it (Phase 7 limitation: same source gap)
        actual_h1     = None
        h1_err        = None
        h1_correct    = None

        # ── Official W/L/P vs posted line (for OT diagnostic reference) ────────
        official_result = None
        if line is not None:
            lin = float(line)
            if actual_total == lin:
                official_result = "PUSH"
            elif lean == "OVER":
                official_result = "WIN" if actual_total > lin else "LOSS"
            else:
                official_result = "WIN" if actual_total < lin else "LOSS"

        # ── Shadow OT diagnostic fields (do not affect official grading) ───────
        ot_info          = ot_data.get(str(gid), {})
        went_to_ot       = ot_info.get("went_to_ot")          # 0/1 or None
        regulation_total = ot_info.get("regulation_total")     # float or None
        regulation_result = None
        ot_flip           = None

        if went_to_ot is not None:
            if went_to_ot == 0:
                # Regulation game: reg total == actual total, no flip possible
                regulation_total  = actual_total
                regulation_result = official_result
                ot_flip           = 0
            elif regulation_total is not None and official_result is not None and line is not None:
                reg_t = float(regulation_total)
                lin   = float(line)
                if reg_t == lin:
                    regulation_result = "PUSH"
                elif lean == "OVER":
                    regulation_result = "WIN" if reg_t > lin else "LOSS"
                else:
                    regulation_result = "WIN" if reg_t < lin else "LOSS"
                ot_flip = 1 if official_result != regulation_result else 0

        rows.append({
            "game_date":          yesterday,
            "game_id":            gid,
            "home_team":          home,
            "away_team":          away,
            "pred_total":         round(pred_total, 2),
            "actual_total":       round(actual_total, 2),
            "full_err":           round(full_err, 2),
            "full_correct":       full_correct,
            "confidence":         confidence,
            "lean":               lean,
            "line":               line,
            "edge":               edge,
            "pred_h1":            pred_h1,
            "actual_h1":          actual_h1,
            "h1_err":             h1_err,
            "h1_correct":         h1_correct,
            "h1_line":            h1_line,
            "market_gap_flag":    market_gap_flag,
            # Shadow OT diagnostics (reference only — official grading unchanged)
            "went_to_ot":         went_to_ot,
            "regulation_total":   regulation_total,
            "regulation_result":  regulation_result,
            "ot_flip":            ot_flip,
        })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ── Persist results ───────────────────────────────────────────────────────────

def append_results_log(new_results: pd.DataFrame) -> pd.DataFrame:
    """Append new_results to the running results log, deduplicating by game_id."""
    if new_results.empty:
        return new_results

    if os.path.exists(NBA_RESULTS_LOG_PATH):
        existing = pd.read_parquet(NBA_RESULTS_LOG_PATH)
        combined = pd.concat([existing, new_results], ignore_index=True)
        combined = combined.drop_duplicates(subset=["game_id"], keep="last")
    else:
        combined = new_results.drop_duplicates(subset=["game_id"], keep="last").copy()

    combined.to_parquet(NBA_RESULTS_LOG_PATH, index=False)
    logger.info(f"Results log updated: {len(combined)} total games")
    return combined


# ── Print results ─────────────────────────────────────────────────────────────

def print_results(results: pd.DataFrame, all_log: pd.DataFrame) -> None:
    if results.empty:
        print("\n  NBA: No results to grade today (west coast games or no projections saved)\n")
        return

    yesterday = results["game_date"].iloc[0]
    print(f"\n{SEP}")
    print(f"  NBA RESULTS — {yesterday}")
    print(SEP)

    err  = results["full_err"]
    n    = len(results)
    mae  = err.abs().mean()
    bias = err.mean()
    hr   = results["full_correct"].mean() * 100

    print(f"""
   Games graded   : {n}
   MAE            : {mae:.2f} pts
   Bias           : {bias:+.2f} pts
   Directional HR : {hr:.1f}%
""")

    # Per-game table
    print(f"   {'Matchup':<22} {'Pred':>6} {'Actual':>7} {'Err':>6} {'Line':>6} {'OK':>4} {'Conf':<8}")
    print(f"   {SEP2[:60]}")
    for _, r in results.iterrows():
        matchup = f"{r['away_team']} @ {r['home_team']}"
        line_s  = f"{r['line']:.1f}" if r.get("line") else "  —  "
        ok_s    = "✓" if r["full_correct"] else "✗"
        flag    = " ⚠ MKTGAP" if r.get("market_gap_flag") else ""
        print(f"   {matchup:<22} {r['pred_total']:>6.1f} {r['actual_total']:>7.1f} "
              f"{r['full_err']:>+6.1f} {line_s:>6} {ok_s:>4} {r['confidence']:<8}{flag}")

    # Season summary
    if not all_log.empty:
        print(f"\n{SEP2}")
        print(f"  Season accuracy (all games logged):")
        for conf in ["HIGH", "MEDIUM", "LOW"]:
            sub = all_log[all_log["confidence"] == conf]
            if len(sub) == 0:
                continue
            s_mae = sub["full_err"].abs().mean()
            s_hr  = sub["full_correct"].mean() * 100
            print(f"  {conf:<8}: n={len(sub):>4}  MAE={s_mae:.2f}  HR={s_hr:.1f}%")

        # Market gap flags
        flagged = all_log[all_log["market_gap_flag"] == 1]
        if len(flagged):
            print(f"\n  ⚠  {len(flagged)} game(s) flagged: model/market gap > {MARKET_FLAG_THRESHOLD} pts")

    print()


# ── Main entry point ──────────────────────────────────────────────────────────

def grade_yesterday(game_date: str = None) -> pd.DataFrame:
    """
    Full grading pipeline. Called at the start of the 7 AM NBA run.
    Returns graded results DataFrame (may be empty if nothing to grade).
    """
    if game_date is None:
        game_date = date.today().isoformat()

    projs   = load_yesterday_projections(game_date)
    actuals = fetch_actual_scores(game_date)
    results = grade_and_log(projs, actuals, game_date)
    log     = append_results_log(results)
    print_results(results, log)
    return results


if __name__ == "__main__":
    grade_yesterday()
