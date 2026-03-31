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
                    "market_prob": round(float(_mp) * 100, 1) if pd.notna(_mp := r.get("market_prob_close")) else (
                        round(float(_mpo) * 100, 1) if pd.notna(_mpo := r.get("market_prob_open")) else None),
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

    # G13 Wave Weather signals
    if log_file.exists():
        log = pd.read_parquet(log_file)
        latest_ts = log["run_timestamp"].max()
        g13_mask = (log["run_timestamp"] == latest_ts) & (log["market"] == "make_cut")

        g13_plays = []
        g13_avoids = []
        if "g13_signal_flag" in log.columns:
            for _, r in log[g13_mask & (log["g13_signal_flag"] == True)].iterrows():
                g13_plays.append({
                    "player_name": r.get("player_name", ""),
                    "draw_quintile": int(r["draw_quintile"]) if pd.notna(r.get("draw_quintile")) else None,
                    "dg_cut_prob": round(float(r["dg_prob"]) * 100, 1) if pd.notna(r.get("dg_prob")) else 0,
                    "adj_cut_prob": round(float(r["adj_make_cut_prob"]) * 100, 1) if pd.notna(r.get("adj_make_cut_prob")) else 0,
                    "book": r.get("g13_reference_book", ""),
                    "close_odds": float(r.get("close_odds", 0)) if pd.notna(r.get("close_odds")) else None,
                    "fair_prob": round(float(_fp) * 100, 1) if pd.notna(_fp := r.get("market_prob_close", r.get("market_prob_open"))) else 0,
                    "adj_edge": round(float(r.get("adj_make_cut_edge", 0) or 0) * 100, 1),
                })
            for _, r in log[g13_mask & (log.get("g13_avoid_flag", False) == True)].iterrows():
                _mpc = r.get("market_prob_close") if pd.notna(r.get("market_prob_close")) else r.get("market_prob_open")
                dg_edge = (r["dg_prob"] - _mpc) if pd.notna(_mpc) else 0
                g13_avoids.append({
                    "player_name": r.get("player_name", ""),
                    "draw_quintile": 1,
                    "dg_cut_prob": round(float(r["dg_prob"]) * 100, 1) if pd.notna(r.get("dg_prob")) else 0,
                    "close_odds": float(r.get("close_odds", 0)) if pd.notna(r.get("close_odds")) else None,
                    "dg_edge": round(float(dg_edge) * 100, 1),
                })
        results["g13_signals"] = g13_plays
        results["g13_avoids"] = g13_avoids
        results["g13_status"] = "LIVE_SHADOW"

    # G14 Tail Balance signals
    if log_file.exists():
        log = pd.read_parquet(log_file)
        latest_ts = log["run_timestamp"].max()

        g14_plays = []
        g14_win_watch = []
        g14_field_type = ""
        g14_kill = False

        for market, flag_col in [("top_10", "g14_top10_signal"), ("top_5", "g14_top5_signal")]:
            if flag_col not in log.columns:
                continue
            m = (log["run_timestamp"] == latest_ts) & (log["market"] == market) & (log[flag_col] == True)
            for _, r in log[m].iterrows():
                adj_col = f"adj_{market}_prob"
                edge_col = f"{market}_edge"
                g14_plays.append({
                    "player_name": r.get("player_name", ""),
                    "skill_band": r.get("skill_band", ""),
                    "tb_bucket": r.get("tb_bucket", ""),
                    "market": market.replace("_", " ").title(),
                    "dg_prob": round(float(r["dg_prob"]) * 100, 1) if pd.notna(r.get("dg_prob")) else 0,
                    "adj_prob": round(float(r.get(adj_col, 0) or 0) * 100, 1),
                    "book": r.get(f"g14_reference_book_{market}", ""),
                    "close_odds": float(r.get("close_odds", 0)) if pd.notna(r.get("close_odds")) else None,
                    "fair_prob": round(float(_fp14) * 100, 1) if pd.notna(_fp14 := r.get("market_prob_close", r.get("market_prob_open"))) else 0,
                    "adj_edge": round(float(r.get(edge_col, 0) or 0) * 100, 1),
                })

        if "g14_win_watchlist" in log.columns:
            wm = (log["run_timestamp"] == latest_ts) & (log["market"] == "win") & (log["g14_win_watchlist"] == True)
            for _, r in log[wm].iterrows():
                g14_win_watch.append({
                    "player_name": r.get("player_name", ""),
                    "dg_win_prob": round(float(r["dg_prob"]) * 100, 1) if pd.notna(r.get("dg_prob")) else 0,
                    "adj_win_prob": round(float(r.get("adj_win_prob", 0) or 0) * 100, 1),
                    "win_edge": round(float(r.get("win_edge", 0) or 0) * 100, 1),
                })

        if "field_type" in log.columns:
            ft_vals = log[(log["run_timestamp"] == latest_ts) & log["field_type"].notna()]["field_type"]
            g14_field_type = ft_vals.iloc[0] if len(ft_vals) > 0 else ""

        if "g14_rule_fail_reason" in log.columns:
            g14_kill = (log[(log["run_timestamp"] == latest_ts)]["g14_rule_fail_reason"] == "kill_switch_triggered").any()

        results["g14_signals"] = g14_plays
        results["g14_win_watchlist"] = g14_win_watch
        results["g14_field_type"] = g14_field_type
        results["g14_kill_switch"] = bool(g14_kill)
        results["g14_status"] = "LIVE_SHADOW"

    # G15 Elite Density signals
    if log_file.exists():
        log = pd.read_parquet(log_file)
        latest_ts = log["run_timestamp"].max()

        g15_plays = []
        g15_ed_bucket = ""
        g15_kill = False

        if "g15_signal_flag" in log.columns:
            m = (log["run_timestamp"] == latest_ts) & (log["market"] == "top_20") & (log["g15_signal_flag"] == True)
            for _, r in log[m].iterrows():
                g15_plays.append({
                    "player_name": r.get("player_name", ""),
                    "dg_rank": int(r.get("dg_rank", 0)) if pd.notna(r.get("dg_rank")) else None,
                    "dg_top20_prob": round(float(r["dg_prob"]) * 100, 1) if pd.notna(r.get("dg_prob")) else 0,
                    "adj_top20_prob": round(float(r.get("adj_top_20_prob_g15", 0) or 0) * 100, 1),
                    "book": r.get("g15_reference_book", ""),
                    "close_odds": float(r.get("close_odds", 0)) if pd.notna(r.get("close_odds")) else None,
                    "fair_prob": round(float(_fp15) * 100, 1) if pd.notna(_fp15 := r.get("market_prob_close", r.get("market_prob_open"))) else 0,
                    "adj_edge": round(float(r.get("top_20_edge_g15", 0) or 0) * 100, 1),
                })

        if "elite_density_bucket" in log.columns:
            edb = log[(log["run_timestamp"] == latest_ts) & log["elite_density_bucket"].notna()]["elite_density_bucket"]
            g15_ed_bucket = edb.iloc[0] if len(edb) > 0 else ""

        if "g15_rule_fail_reason" in log.columns:
            g15_kill = (log[(log["run_timestamp"] == latest_ts)]["g15_rule_fail_reason"] == "kill_switch_triggered").any()

        results["g15_signals"] = g15_plays
        results["g15_elite_density_bucket"] = g15_ed_bucket
        results["g15_kill_switch"] = bool(g15_kill)
        results["g15_status"] = "LIVE_SHADOW"

    # Model info
    results["model_info"] = {
        "model": "DG logistic + G13 wave + G14 tail + G15 elite density",
        "oos_auc": 0.702, "oos_brier": 0.211,
        "confidence_tier": "LOW",
        "g13_oos_roi": "+9.2%",
        "g13_market": "make_cut",
        "g13_rule": "adj_edge >= 4% AND draw_quintile in {Q4, Q5}",
        "g14_oos_roi_top10": "+11.6%",
        "g14_oos_roi_top5": "+12.5%",
        "g14_markets": "top_10, top_5 (strong fields only)",
        "g15_oos_roi_top20": "+7.3%",
        "g15_market": "top_20 (HIGH elite density)",
        "note": "Shadow tracking. G13 wave + G14 tail + G15 elite density in LIVE_SHADOW.",
    }

    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    print("Saved %s" % OUT, flush=True)


if __name__ == "__main__":
    run()
