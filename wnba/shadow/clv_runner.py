#!/usr/bin/env python3
"""WNBA Shadow — CLV Capture (Component 2). Runs 10:30 PM ET."""
import os, sys, time
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

SHADOW_DIR = Path("wnba/shadow")
RUN_MODE = os.environ.get("RUN_MODE", "test")

try:
    from dotenv import load_dotenv; load_dotenv()
except Exception: pass
API_KEY = os.environ.get("ODDS_API_KEY", "")


def run(run_date=None):
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    print("WNBA CLV Runner | %s | mode=%s" % (run_date, RUN_MODE), flush=True)

    pc_file = SHADOW_DIR / "prop_candidates.parquet"
    if not pc_file.exists():
        print("No prop_candidates.parquet. Exiting.", flush=True)
        return

    pc = pd.read_parquet(pc_file)
    today = pc[pc["game_date"] == run_date]
    if len(today) == 0:
        print("No props for %s. Exiting." % run_date, flush=True)
        return

    clv_rows = []

    if RUN_MODE == "test":
        # Stub mode: synthetic closing odds
        print("CLV stub mode — schema validated.", flush=True)
        np.random.seed(42)
        for _, r in today.iterrows():
            move = np.random.uniform(-10, 10)
            closing_over = r["best_over_odds"] + move if pd.notna(r["best_over_odds"]) else np.nan
            closing_under = r["best_under_odds"] - move if pd.notna(r["best_under_odds"]) else np.nan
            sel_side = r["selected_side"]
            if sel_side == "over":
                closing_sel = closing_over
                opening_sel = r["best_over_odds"]
            elif sel_side == "under":
                closing_sel = closing_under
                opening_sel = r["best_under_odds"]
            else:
                closing_sel = np.nan
                opening_sel = np.nan

            clv = opening_sel - closing_sel if pd.notna(opening_sel) and pd.notna(closing_sel) else np.nan
            beat = 1 if pd.notna(clv) and clv >= 0 else 0

            clv_rows.append({
                "player_id": r["player_id"], "player_name": r["player_name"],
                "game_id": r["game_id"], "game_date": run_date,
                "market": r["market"], "line": r["line"],
                "opening_over_odds": r["best_over_odds"],
                "closing_over_odds": round(closing_over, 1) if pd.notna(closing_over) else np.nan,
                "opening_under_odds": r["best_under_odds"],
                "closing_under_odds": round(closing_under, 1) if pd.notna(closing_under) else np.nan,
                "selected_side": sel_side,
                "selected_odds": opening_sel,
                "closing_odds_selected": round(closing_sel, 1) if pd.notna(closing_sel) else np.nan,
                "clv_selected": round(clv, 1) if pd.notna(clv) else np.nan,
                "beat_close": beat,
                "edge_at_open": r.get("selected_edge", np.nan),
                "classification": r.get("classification_over") if sel_side == "over" else r.get("classification_under"),
            })
    else:
        # Live mode — use shared/clv_utils
        from shared.clv_utils import get_closing_odds
        for _, r in today.iterrows():
            sel_side = r["selected_side"]
            if sel_side is None: continue
            result = get_closing_odds(
                event_id=r["game_id"], player_name=r["player_name"],
                prop_type=r["market"], sport="basketball_wnba", direction=sel_side.upper())
            closing = result.get("closing_odds", np.nan)
            opening = r["selected_odds"]
            clv = opening - closing if pd.notna(opening) and pd.notna(closing) else np.nan
            beat = 1 if pd.notna(clv) and clv >= 0 else 0
            clv_rows.append({
                "player_id": r["player_id"], "player_name": r["player_name"],
                "game_id": r["game_id"], "game_date": run_date,
                "market": r["market"], "line": r["line"],
                "opening_over_odds": r["best_over_odds"],
                "closing_over_odds": closing if sel_side == "over" else np.nan,
                "opening_under_odds": r["best_under_odds"],
                "closing_under_odds": closing if sel_side == "under" else np.nan,
                "selected_side": sel_side, "selected_odds": opening,
                "closing_odds_selected": closing,
                "clv_selected": round(clv, 1) if pd.notna(clv) else np.nan,
                "beat_close": beat,
                "edge_at_open": r.get("selected_edge", np.nan),
                "classification": r.get("classification_over") if sel_side == "over" else r.get("classification_under"),
            })
            time.sleep(0.3)

    clv_df = pd.DataFrame(clv_rows)
    clv_file = SHADOW_DIR / "clv_log.parquet"
    if clv_file.exists():
        existing = pd.read_parquet(clv_file)
        clv_df = pd.concat([existing, clv_df], ignore_index=True)
    clv_df.to_parquet(clv_file, index=False)
    print("CLV log: %d rows saved" % len(clv_df), flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(run_date=args.date)
