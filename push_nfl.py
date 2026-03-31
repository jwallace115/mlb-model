#!/usr/bin/env python3
"""
push_nfl.py — Serialize NFL projections + season accuracy to nfl_results.json.

Usage:
    python3 push_nfl.py              # serialize + push
    python3 push_nfl.py --no-push    # serialize only
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

import pandas as pd

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
NFL_DIR = os.path.join(REPO_DIR, "nfl")
DATA_DIR = os.path.join(NFL_DIR, "data")
OUT_PATH = os.path.join(REPO_DIR, "nfl_results.json")

DECISIONS_PATH = os.path.join(DATA_DIR, "nfl_decisions.parquet")
MODEL_OUT_PATH = os.path.join(DATA_DIR, "nfl_model_outputs.parquet")

WIN_PER_UNIT = 100.0 / 110.0


def _safe(v):
    if v is None:
        return None
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, float) and (v != v):
        return None
    return v


def load_recent_results(days: int = 14) -> list[dict]:
    if not os.path.exists(DECISIONS_PATH):
        return []
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS_PATH)
        if dec.empty:
            return []
        # Only live graded
        live = dec[dec["market_snapshot_status"] == "live"] if "market_snapshot_status" in dec.columns else pd.DataFrame()
        if live.empty:
            return []
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        recent = live[live["date"] >= cutoff].sort_values("date", ascending=False)
        rows = []
        for _, r in recent.iterrows():
            rows.append({
                "date": r.get("date"),
                "away_team": r.get("away_team"),
                "home_team": r.get("home_team"),
                "signal_side": r.get("signal_side"),
                "line": _safe(r.get("closing_total_line")),
                "edge": _safe(r.get("edge")),
                "result": r.get("result"),
                "tier": r.get("confidence_tier"),
                "model_total": _safe(r.get("model_total")),
                "total_points": _safe(r.get("total_points")),
            })
        return rows
    except Exception as e:
        print(f"[push_nfl] Failed to load results: {e}", file=sys.stderr)
        return []


def build_season_performance() -> dict:
    if not os.path.exists(DECISIONS_PATH):
        return {}
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS_PATH)
        live = dec[dec.get("market_snapshot_status", pd.Series()) == "live"] if "market_snapshot_status" in dec.columns else pd.DataFrame()
        graded = live[live["result"].isin(["WIN", "LOSS", "PUSH"])] if not live.empty else pd.DataFrame()
        if graded.empty:
            return {"total_games": 0}

        def agg(df):
            w = int((df["result"] == "WIN").sum())
            l = int((df["result"] == "LOSS").sum())
            p = int((df["result"] == "PUSH").sum())
            n = w + l
            hit = round(w / n, 4) if n > 0 else None
            roi = round((w * WIN_PER_UNIT - l) / n * 100, 2) if n > 0 else None
            return {"n": w + l + p, "w": w, "l": l, "p": p, "hit": hit, "roi": roi}

        out = {"overall": agg(graded)}
        by_tier = {}
        for tier in ["HIGH", "MEDIUM", "LOW"]:
            sub = graded[graded["confidence_tier"] == tier]
            if len(sub) > 0:
                by_tier[tier] = agg(sub)
        out["by_tier"] = by_tier
        return out
    except Exception:
        return {}


def build_stop_rule_status() -> dict:
    try:
        sys.path.insert(0, NFL_DIR)
        from nfl_stop_rules import evaluate
        return evaluate()
    except Exception:
        return {"model_suspended": False, "suspended_tiers": []}


def _build_conditional_section(game_date: str) -> dict:
    """Build conditional signals section for nfl_results.json."""
    signals_path = os.path.join(DATA_DIR, "nfl_conditional_signals.parquet")
    results_path = os.path.join(DATA_DIR, "nfl_conditional_results.parquet")
    stop_path = os.path.join(DATA_DIR, "nfl_conditional_stop_rules.json")

    # Today's signals
    today_sigs = []
    if os.path.exists(signals_path):
        try:
            sigs = pd.read_parquet(signals_path)
            today = sigs[sigs["date"] == game_date]
            for _, s in today.iterrows():
                today_sigs.append({
                    "game_id": s.get("game_id"),
                    "home_team": s.get("home_team"),
                    "away_team": s.get("away_team"),
                    "segment_name": s.get("segment_name"),
                    "display_name": s.get("display_name"),
                    "bet_side": s.get("bet_side"),
                    "closing_total_line": _safe(s.get("closing_total_line")),
                    "week": _safe(s.get("week")),
                    "risk_note": s.get("risk_note", "standard"),
                })
        except Exception:
            pass

    # Recent results (14 days)
    recent = []
    if os.path.exists(results_path):
        try:
            res = pd.read_parquet(results_path)
            cutoff = (date.fromisoformat(game_date) - timedelta(days=14)).isoformat()
            rec = res[res["date"] >= cutoff].sort_values("date", ascending=False)
            for _, r in rec.iterrows():
                recent.append({
                    "date": r.get("date"),
                    "game_id": r.get("game_id"),
                    "segment_name": r.get("segment_name"),
                    "bet_side": r.get("bet_side"),
                    "decision_line": _safe(r.get("decision_line")),
                    "actual_total": _safe(r.get("actual_total")),
                    "result": r.get("result"),
                })
        except Exception:
            pass

    # Segment performance (live only)
    seg_perf = {}
    if os.path.exists(results_path):
        try:
            res = pd.read_parquet(results_path)
            live = res[res.get("market_snapshot_status", pd.Series()) == "live"] if "market_snapshot_status" in res.columns else res
            graded = live[live["graded"] == True] if "graded" in live.columns else pd.DataFrame()
            for seg in ["dome_low_total", "late_season", "no_move_low_total"]:
                sub = graded[graded["segment_name"] == seg] if not graded.empty else pd.DataFrame()
                w = int((sub["result"] == "WIN").sum()) if not sub.empty else 0
                l = int((sub["result"] == "LOSS").sum()) if not sub.empty else 0
                n = w + l
                seg_perf[seg] = {
                    "live_n": n,
                    "live_hit_rate": round(w / n, 3) if n > 0 else None,
                    "live_roi": round((w * WIN_PER_UNIT - l) / n * 100, 1) if n > 0 else None,
                    "status": "active",
                }
                if seg == "no_move_low_total" and n > 0:
                    seg_perf[seg]["monitoring_note"] = f"hit rate {w/n:.1%} vs 82.6% baseline"
        except Exception:
            pass

    # Stop rules
    stop = {"model_suspended": False, "suspended_segments": [], "live_signals_total": 0}
    if os.path.exists(stop_path):
        try:
            with open(stop_path) as f:
                stop = json.load(f)
        except Exception:
            pass

    return {
        "today": today_sigs,
        "recent_results": recent,
        "segment_performance": seg_perf,
        "stop_rule_status": stop,
    }


def write_nfl_json(game_date: str = None) -> str:
    game_date = game_date or date.today().isoformat()
    now_utc = datetime.now(timezone.utc)

    recent_results = load_recent_results(days=14)
    season_perf = build_season_performance()
    stop_status = build_stop_rule_status()

    # OOS backtest reference
    oos_ref = {
        "note": "Phase 1 baseline — OOS gate FAILED (51.1% hit rate, need 52.5%)",
        "overall_hit": 0.511,
        "overall_roi": -2.5,
        "n_signals": 185,
        "model_status": "not_deployed",
    }

    # Conditional signals (Phase 8)
    conditional = _build_conditional_section(game_date)

    payload = {
        "generated_at": now_utc.isoformat(),
        "game_date": game_date,
        "model_description": "NFL Phase 8 — Conditional segment signals (dome+low, late season, no-move+low). Phase 1 totals model excluded.",
        "model_status": "conditional_active",
        "today_signals": [],
        "recent_results": recent_results,
        "season_performance": season_perf,
        "stop_rule_status": stop_status,
        "oos_reference": oos_ref,
        "conditional_signals": conditional,
    }

    # AI review
    try:
        sys.path.insert(0, REPO_DIR)
        from modules.ai_review import (build_graded_games, generate_daily_review,
                                        is_idempotent)
        review_date = (date.fromisoformat(game_date) - timedelta(days=1)).isoformat()
        if not is_idempotent(OUT_PATH, review_date):
            graded = build_graded_games("nfl", review_date)
            payload["daily_review"] = generate_daily_review(graded, "nfl", review_date)
    except Exception as e:
        print(f"[push_nfl] AI review failed (non-fatal): {e}", file=sys.stderr)

    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[push_nfl] Wrote {OUT_PATH}")
    return OUT_PATH


def git_push(game_date: str) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        return result.returncode == 0

    run(["git", "add", "nfl_results.json"])
    status = subprocess.run(
        ["git", "status", "--porcelain", "nfl_results.json"],
        cwd=REPO_DIR, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("[push_nfl] Nothing to commit.")
        return True
    if not run(["git", "commit", "-m", f"nfl: {game_date}"]):
        return False
    if not run(["git", "push"]):
        return False
    print("[push_nfl] Pushed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()
    write_nfl_json(game_date=args.date)
    if not args.no_push:
        git_push(args.date or date.today().isoformat())


if __name__ == "__main__":
    main()
