#!/usr/bin/env python3
"""Push golf shadow data to golf_results.json for Streamlit dashboard."""
import json, os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

SHADOW = Path("golf/shadow")
OUT = Path("golf_results.json")


def run():
    results = {
        "generated_at": datetime.now().isoformat(),
        "sport": "golf",
    }

    # Current board
    board_file = SHADOW / "golf_daily_best_board.parquet"
    if board_file.exists():
        board = pd.read_parquet(board_file)
        if len(board) > 0:
            results["event_name"] = board.iloc[0].get("event_name", "")
            results["event_id"] = int(board.iloc[0].get("event_id", 0))
            results["is_major"] = bool(board.iloc[0].get("is_major", False))
            results["last_updated"] = board.iloc[0].get("run_timestamp", "")
            results["n_candidates"] = int((board["classification"] == "candidate").sum())
            results["n_leans"] = int((board["classification"] == "lean").sum())

            plays = []
            for _, r in board.iterrows():
                plays.append({
                    "player_name": r.get("player_name", ""),
                    "dg_id": int(r["player_id"]) if pd.notna(r.get("player_id")) else 0,
                    "market": r.get("market", ""),
                    "model_prob": round(float(r["model_prob"]) * 100, 1) if pd.notna(r.get("model_prob")) else 0,
                    "market_prob": round(float(r.get("market_prob_close", r.get("market_prob_open", 0)) or 0) * 100, 1),
                    "edge": round(float(r.get("edge", 0) or 0) * 100, 1),
                    "direction": r.get("direction", ""),
                    "classification": r.get("classification", ""),
                    "close_odds": float(r.get("close_odds", 0)) if pd.notna(r.get("close_odds")) else None,
                })
            results["plays"] = plays

    # Season results
    log_file = SHADOW / "golf_shadow_log.parquet"
    if log_file.exists():
        log = pd.read_parquet(log_file)
        graded = log[log["actual_result"].notna()]
        cands = graded[graded["classification"] == "candidate"]

        season_stats = {}
        for mkt in ["make_cut", "top_20"]:
            sub = cands[cands["market"] == mkt]
            if len(sub) == 0: continue
            pnl = sub["shadow_pnl"].dropna()
            season_stats[mkt] = {
                "n": int(len(sub)),
                "hit_rate": round(float(sub["actual_result"].mean()) * 100, 1),
                "roi": round(float(pnl.mean()) * 100, 1) if len(pnl) > 0 else 0,
                "clv": round(float(sub["clv"].dropna().mean()) * 100, 1) if sub["clv"].notna().sum() > 0 else 0,
            }
        results["season_stats"] = season_stats

        # Recent events
        recent = []
        for (eid, yr), grp in graded.groupby(["event_id", "calendar_year"]):
            cands_ev = grp[grp["classification"] == "candidate"]
            if len(cands_ev) == 0: continue
            pnl = cands_ev["shadow_pnl"].dropna()
            recent.append({
                "event_name": grp.iloc[0].get("event_name", ""),
                "event_id": int(eid), "year": int(yr),
                "n_candidates": int(len(cands_ev)),
                "hit_rate": round(float(cands_ev["actual_result"].mean()) * 100, 1),
                "roi": round(float(pnl.mean()) * 100, 1) if len(pnl) > 0 else 0,
            })
        results["recent_results"] = recent[-5:]

    # Matchup candidates
    mlog = SHADOW / "golf_matchup_log.parquet"
    if mlog.exists():
        mdf = pd.read_parquet(mlog)
        # Latest capture only
        if "capture_timestamp" in mdf.columns and len(mdf) > 0:
            latest_ts = mdf["capture_timestamp"].max()
            latest_m = mdf[mdf["capture_timestamp"] == latest_ts]
            matchup_plays = []
            for _, r in latest_m[latest_m["classification"].isin(["candidate", "lean"])].head(20).iterrows():
                matchup_plays.append({
                    "player_1": r.get("player_1_name", ""),
                    "player_2": r.get("player_2_name", ""),
                    "player_3": r.get("player_3_name", ""),
                    "match_type": r.get("match_type", ""),
                    "book": r.get("book_name", ""),
                    "bet_edge": round(float(r.get("bet_edge", 0)) * 100, 1),
                    "classification": r.get("classification", ""),
                })
            results["matchup_candidates"] = matchup_plays
            results["matchup_n_candidates"] = int((latest_m["classification"] == "candidate").sum())
            results["matchup_n_leans"] = int((latest_m["classification"] == "lean").sum())

    # Model info
    results["model_info"] = {
        "model": "DG-only logistic regression",
        "oos_auc": 0.702, "oos_brier": 0.211,
        "confidence_tier": "LOW",
        "note": "Shadow tracking only. Reference book: DraftKings.",
    }

    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    print("Saved %s" % OUT, flush=True)


if __name__ == "__main__":
    run()
