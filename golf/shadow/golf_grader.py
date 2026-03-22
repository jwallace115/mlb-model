#!/usr/bin/env python3
"""Golf Shadow — Grader. Grades completed tournaments in shadow log."""
import os, sys, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

try:
    from dotenv import load_dotenv; load_dotenv()
except Exception: pass

DG_KEY = os.environ.get("DATAGOLF_API_KEY", "")
DG_BASE = "https://feeds.datagolf.com"
RUN_MODE = os.environ.get("RUN_MODE", "test")
SHADOW = Path("golf/shadow")
DATA = Path("golf/data/canonical")

import requests


def dg_get(path, params=None):
    if params is None: params = {}
    params["file_format"] = "json"; params["key"] = DG_KEY
    time.sleep(1.5)
    r = requests.get(DG_BASE + path, params=params, timeout=30)
    if r.status_code == 200:
        try: return r.json()
        except: return None
    return None


def parse_fin(ft):
    if not ft or pd.isna(ft): return 999
    ft = str(ft).strip().upper().replace("T", "")
    if ft in ("CUT", "MC"): return 999
    if ft == "WD": return 998
    try: return int(ft)
    except: return 999


def run():
    print("Golf Grader | mode=%s" % RUN_MODE, flush=True)

    log_file = SHADOW / "golf_shadow_log.parquet"
    if not log_file.exists():
        print("No shadow log. Exiting.", flush=True); return

    log = pd.read_parquet(log_file)
    ungraded = log[log["actual_result"].isna()].copy()
    events = ungraded[["event_id", "calendar_year"]].drop_duplicates()

    if len(events) == 0:
        print("No ungraded events.", flush=True); return

    graded_count = 0
    for _, ev in events.iterrows():
        eid, yr = ev["event_id"], ev["calendar_year"]

        # Fetch results
        if RUN_MODE == "live":
            d = dg_get("/historical-raw-data/rounds", {"tour": "pga", "event_id": int(eid), "year": int(yr)})
            if not d or not isinstance(d, dict):
                continue
            scores = d.get("scores", [])
            if not scores: continue
            completed = d.get("event_completed", False)
            if not completed:
                print("  %s %d: not yet completed, skipping" % (eid, yr), flush=True)
                continue
        else:
            results = pd.read_parquet(DATA / "tournament_results.parquet")
            ev_results = results[(results["event_id"] == eid) & (results["calendar_year"] == yr)]
            if len(ev_results) == 0: continue
            scores = [{"dg_id": r["dg_id"], "fin_text": r["fin_text"]} for _, r in ev_results.iterrows()]

        # Build lookup: dg_id -> finish flags
        finish_lookup = {}
        for s in scores:
            dgid = s.get("dg_id") if isinstance(s, dict) else s.get("dg_id")
            ft = s.get("fin_text", "")
            fn = parse_fin(ft)
            finish_lookup[dgid] = {
                "made_cut": 1 if fn < 900 else 0,
                "top_20": 1 if fn <= 20 else 0,
                "top_10": 1 if fn <= 10 else 0,
                "top_5": 1 if fn <= 5 else 0,
                "winner": 1 if fn == 1 else 0,
            }

        # Grade each row
        mask = (log["event_id"] == eid) & (log["calendar_year"] == yr) & (log["actual_result"].isna())
        for idx in log[mask].index:
            row = log.loc[idx]
            dgid = row["player_id"]
            market = row["market"]
            fl = finish_lookup.get(dgid, {})

            result_key = {
                "make_cut": "made_cut", "top_20": "top_20", "top_10": "top_10",
                "top_5": "top_5", "win": "winner"
            }.get(market)

            if result_key and result_key in fl:
                actual = fl[result_key]
                log.loc[idx, "actual_result"] = actual

                # Shadow P&L for candidates
                if row["classification"] == "candidate" and pd.notna(row["close_odds"]):
                    odds = row["close_odds"]
                    direction = row["direction"]
                    if direction == "over":
                        if actual == 1:
                            payout = (odds / 100) if odds > 0 else (100 / abs(odds))
                            log.loc[idx, "shadow_pnl"] = payout
                        else:
                            log.loc[idx, "shadow_pnl"] = -1.0
                    elif direction == "under":
                        if actual == 0:
                            payout = (odds / 100) if odds > 0 else (100 / abs(odds))
                            log.loc[idx, "shadow_pnl"] = payout
                        else:
                            log.loc[idx, "shadow_pnl"] = -1.0

                # CLV
                mkt_close = row.get("market_prob_close")
                if pd.notna(mkt_close):
                    log.loc[idx, "clv"] = row["model_prob"] - mkt_close

                graded_count += 1

    log.to_parquet(log_file, index=False)

    # Summary
    graded = log[log["actual_result"].notna()]
    cands = graded[graded["classification"] == "candidate"]
    print("\nGraded: %d rows" % graded_count, flush=True)

    if len(cands) > 0:
        for mkt in ["make_cut", "top_20"]:
            sub = cands[cands["market"] == mkt]
            if len(sub) == 0: continue
            hit = sub["actual_result"].mean() * 100
            pnl = sub["shadow_pnl"].dropna()
            roi = pnl.mean() * 100 if len(pnl) > 0 else 0
            clv = sub["clv"].dropna().mean() * 100 if sub["clv"].notna().sum() > 0 else 0
            print("  %s: %d candidates, %.1f%% hit, %+.1f%% ROI, %+.1f%% CLV" % (
                mkt, len(sub), hit, roi, clv), flush=True)


def grade_matchups():
    """Grade matchup/3-ball results."""
    print("\nGrading matchups...", flush=True)
    mlog = SHADOW / "golf_matchup_log.parquet"
    if not mlog.exists():
        print("No matchup log.", flush=True); return

    mdf = pd.read_parquet(mlog)
    # Matchups are graded by comparing final tournament scores
    # For now, just note that matchup grading requires per-round scores
    # which are in player_rounds — grade by total strokes
    results = pd.read_parquet(DATA / "tournament_results.parquet")
    score_lookup = {}
    for _, r in results.iterrows():
        score_lookup[(r["event_id"], r["calendar_year"], r["dg_id"])] = r["total_score"]

    # For DG model pairings, we don't have event_id — skip for now
    ungraded = mdf[mdf["actual_result"].isna()]
    print("Ungraded matchups: %d" % len(ungraded), flush=True)
    print("(Matchup grading requires event_id mapping — will be active in live mode)")
    mdf.to_parquet(mlog, index=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-matchups", action="store_true")
    args = parser.parse_args()
    run()
    if args.include_matchups:
        grade_matchups()
