#!/usr/bin/env python3
"""WNBA Shadow — Results Grader (Component 3). Runs 8:00 AM ET next morning."""
import os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

SHADOW_DIR = Path("wnba/shadow")
DATA_DIR = Path("wnba/data")
RUN_MODE = os.environ.get("RUN_MODE", "test")

STAT_COL = {
    "player_points": "points",
    "player_rebounds": "rebounds_total",
    "player_assists": "assists",
    "player_points_rebounds_assists": "pra",
}


def american_to_decimal(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return (odds / 100) + 1 if odds > 0 else (100 / abs(odds)) + 1


def run(grade_date=None):
    if grade_date is None:
        grade_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print("WNBA Grader | grading %s | mode=%s" % (grade_date, RUN_MODE), flush=True)

    pc_file = SHADOW_DIR / "prop_candidates.parquet"
    if not pc_file.exists():
        print("No prop_candidates. Exiting.", flush=True); return

    pc = pd.read_parquet(pc_file)
    today_props = pc[pc["game_date"] == grade_date]
    if len(today_props) == 0:
        print("No props for %s. Exiting." % grade_date, flush=True); return

    # Fetch actuals
    if RUN_MODE == "test":
        # Use enriched game logs
        enr = pd.read_parquet(DATA_DIR / "player_game_logs_enriched.parquet")
        enr["game_date"] = pd.to_datetime(enr["game_date"])
        actuals = enr[enr["game_date"] == grade_date][
            ["player_id", "game_id", "points", "rebounds_total", "assists", "pra", "minutes"]
        ].copy()
        # OT detection: minutes > 40 for regulation = 40 min
        game_max_min = actuals.groupby("game_id")["minutes"].max()
        ot_games = set(game_max_min[game_max_min > 40].index)
    else:
        # Live: use nba_api
        from nba_api.stats.endpoints import BoxScoreTraditionalV3
        enr = pd.read_parquet(DATA_DIR / "player_game_logs_enriched.parquet")
        actuals = enr[enr["game_date"] == grade_date][
            ["player_id", "game_id", "points", "rebounds_total", "assists", "pra", "minutes"]
        ].copy()
        game_max_min = actuals.groupby("game_id")["minutes"].max()
        ot_games = set(game_max_min[game_max_min > 40].index)

    if len(actuals) == 0:
        print("No actuals found for %s." % grade_date, flush=True); return

    # Build lookup
    actual_lookup = {}
    for _, row in actuals.iterrows():
        actual_lookup[(row["player_id"], row.get("game_id"))] = row

    graded = []
    for _, prop in today_props.iterrows():
        pid = prop["player_id"]
        gid = prop["game_id"]
        market = prop["market"]
        stat_col = STAT_COL.get(market, "pra")
        line = prop["line"]

        # Try to match by player_id (game_id from API won't match enriched game_id)
        player_actuals = actuals[actuals["player_id"] == pid]
        if len(player_actuals) == 0:
            continue
        act_row = player_actuals.iloc[0]
        actual_stat = act_row[stat_col]
        actual_gid = act_row.get("game_id", gid)

        over_result = 1 if actual_stat > line else 0
        under_result = 1 - over_result

        sel_side = prop["selected_side"]
        if sel_side == "over": result = over_result
        elif sel_side == "under": result = under_result
        else: result = None

        # Shadow P&L
        shadow_profit = None
        cls = prop.get("classification_over") if sel_side == "over" else prop.get("classification_under")
        if cls == "candidate" and sel_side is not None and result is not None:
            d = american_to_decimal(prop["selected_odds"])
            if pd.notna(d):
                shadow_profit = 100 * (d - 1) if result == 1 else -100

        ot = 1 if actual_gid in ot_games else 0

        graded.append({
            "player_id": pid, "player_name": prop["player_name"],
            "game_id": gid, "game_date": grade_date,
            "market": market, "line": line,
            "selected_side": sel_side, "selected_odds": prop["selected_odds"],
            "selected_edge": prop["selected_edge"], "selected_prob": prop["selected_prob"],
            "projection": prop["projection"], "actual_stat": actual_stat,
            "projection_error": actual_stat - prop["projection"],
            "over_result": over_result, "under_result": under_result,
            "result_for_selected_side": result,
            "shadow_profit": shadow_profit,
            "classification": cls,
            "recent_role_change_flag": prop.get("recent_role_change_flag", 0),
            "low_history": prop.get("low_history", False),
            "overtime_flag": ot,
        })

    graded_df = pd.DataFrame(graded)
    gr_file = SHADOW_DIR / "graded_results.parquet"
    if gr_file.exists():
        existing = pd.read_parquet(gr_file)
        graded_df = pd.concat([existing, graded_df], ignore_index=True)
    graded_df.to_parquet(gr_file, index=False)

    # Summary
    today_graded = graded_df[graded_df["game_date"] == grade_date]
    cands = today_graded[today_graded["classification"] == "candidate"]
    if len(cands) > 0:
        wins = cands["result_for_selected_side"].sum()
        n = cands["result_for_selected_side"].notna().sum()
        profit = cands["shadow_profit"].sum()
        print("Candidates: %d/%d won (%.1f%%), P&L: %+.0f units" % (wins, n, wins/n*100 if n else 0, profit/100), flush=True)
    print("Graded: %d props for %s" % (len(today_graded), grade_date), flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(grade_date=args.date)
