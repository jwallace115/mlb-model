#!/usr/bin/env python3
"""WNBA Shadow — Weekly Performance Report (Component 4). Monday 8 AM ET."""
import os, sys
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

SHADOW_DIR = Path("wnba/shadow")


def run(end_date=None, days=7):
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    start = (pd.Timestamp(end_date) - timedelta(days=days)).strftime("%Y-%m-%d")
    print("WNBA Weekly Report | %s to %s" % (start, end_date), flush=True)

    gr_file = SHADOW_DIR / "graded_results.parquet"
    clv_file = SHADOW_DIR / "clv_log.parquet"
    if not gr_file.exists():
        print("No graded results. Exiting.", flush=True); return

    gr = pd.read_parquet(gr_file)
    gr["game_date"] = pd.to_datetime(gr["game_date"])
    week = gr[(gr["game_date"] >= start) & (gr["game_date"] <= end_date)]
    season = gr.copy()

    clv = pd.read_parquet(clv_file) if clv_file.exists() else pd.DataFrame()

    lines = []
    lines.append("WNBA SHADOW — WEEKLY REPORT (%s to %s)" % (start, end_date))
    lines.append("=" * 60)

    def section(df, label):
        out = []
        cands = df[df["classification"] == "candidate"]
        out.append("\n--- %s ---" % label)
        out.append("Props evaluated: %d" % len(df))
        out.append("Candidates: %d" % len(cands))

        if len(cands) > 0 and cands["result_for_selected_side"].notna().sum() > 0:
            wins = cands["result_for_selected_side"].sum()
            n = cands["result_for_selected_side"].notna().sum()
            profit = cands["shadow_profit"].dropna().sum()
            roi = profit / (100 * n) * 100 if n > 0 else 0
            out.append("Win rate: %d/%d (%.1f%%)" % (wins, n, wins/n*100))
            out.append("Shadow ROI: %+.1f%%" % roi)

            # By market
            out.append("\nBy market:")
            for mkt in ["player_points_rebounds_assists", "player_rebounds", "player_assists", "player_points"]:
                sub = cands[cands["market"] == mkt]
                if len(sub) == 0: continue
                w = sub["result_for_selected_side"].sum()
                nn = sub["result_for_selected_side"].notna().sum()
                p = sub["shadow_profit"].dropna().sum()
                out.append("  %s: %d/%d (%.1f%%), ROI=%+.1f%%" % (
                    mkt.replace("player_", ""), w, nn, w/nn*100 if nn else 0, p/(100*nn)*100 if nn else 0))

            # Edge buckets
            out.append("\nEdge buckets:")
            for lo, hi, label_e in [(0.03, 0.05, "3-5%"), (0.05, 0.07, "5-7%"), (0.07, 1.0, "7%+")]:
                sub = cands[(cands["selected_edge"] >= lo) & (cands["selected_edge"] < hi)]
                if len(sub) == 0: continue
                w = sub["result_for_selected_side"].sum()
                nn = sub["result_for_selected_side"].notna().sum()
                p = sub["shadow_profit"].dropna().sum()
                out.append("  %s: %d/%d (%.1f%%), ROI=%+.1f%%" % (
                    label_e, w, nn, w/nn*100 if nn else 0, p/(100*nn)*100 if nn else 0))

            # Role change / low history hypothesis
            out.append("\nHypothesis splits:")
            for flag, fname in [("recent_role_change_flag", "role_change"),
                                ("low_history", "low_history")]:
                if flag in cands.columns:
                    sub = cands[cands[flag] == 1]
                    if len(sub) > 0:
                        w = sub["result_for_selected_side"].sum()
                        nn = sub["result_for_selected_side"].notna().sum()
                        out.append("  %s: %d/%d (%.1f%%)" % (fname, w, nn, w/nn*100 if nn else 0))

            # OT
            if "overtime_flag" in cands.columns:
                ot = cands[cands["overtime_flag"] == 1]
                non_ot = cands[cands["overtime_flag"] == 0]
                out.append("\nOvertime: %d games" % len(ot))
                if len(ot) > 0:
                    out.append("  OT MAE: %.2f" % (ot["projection_error"].abs().mean()))
                if len(non_ot) > 0:
                    out.append("  Non-OT MAE: %.2f" % (non_ot["projection_error"].abs().mean()))

        return "\n".join(out)

    lines.append(section(week, "WEEK"))
    lines.append(section(season, "SEASON CUMULATIVE"))

    # CLV
    if len(clv) > 0:
        clv["game_date"] = pd.to_datetime(clv["game_date"])
        week_clv = clv[(clv["game_date"] >= start) & (clv["game_date"] <= end_date)]
        cand_clv = week_clv[week_clv["classification"] == "candidate"]
        if len(cand_clv) > 0:
            beat = cand_clv["beat_close"].mean() * 100
            avg_clv = cand_clv["clv_selected"].mean()
            lines.append("\nCLV (week): beat close %.1f%%, avg CLV %.1f" % (beat, avg_clv))

    report = "\n".join(lines)
    print(report, flush=True)

    with open(SHADOW_DIR / "p6_shadow_log.txt", "a") as f:
        f.write("\n" + report + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    run(end_date=args.end_date, days=args.days)
