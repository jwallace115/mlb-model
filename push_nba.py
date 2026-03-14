#!/usr/bin/env python3
"""
push_nba.py — Serialize NBA projections + season accuracy to nba_results.json and push to GitHub.

Called automatically from push_results.py (daily 7am run) or standalone.

Usage:
    python push_nba.py              # serialize + push
    python push_nba.py --no-push    # serialize only, skip git
    python push_nba.py --date 2026-03-14
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime

REPO_DIR     = os.path.dirname(os.path.abspath(__file__))
OUT_PATH     = os.path.join(REPO_DIR, "nba_results.json")

NBA_PROJ_PATH    = os.path.join(REPO_DIR, "nba", "data", "nba_daily_projections.parquet")
NBA_RESULTS_PATH = os.path.join(REPO_DIR, "nba", "data", "nba_results_log.parquet")


def _safe(v):
    if v is None:
        return None
    if hasattr(v, "item"):        # numpy scalar
        return v.item()
    if isinstance(v, float) and (v != v):  # NaN
        return None
    return v


def load_today_projections(game_date: str) -> list[dict]:
    if not os.path.exists(NBA_PROJ_PATH):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(NBA_PROJ_PATH)
        today = df[df["game_date"] == game_date]
        if today.empty:
            print(f"[push_nba] No NBA projections found for {game_date}")
            return []
        rows = []
        for _, r in today.iterrows():
            rows.append({
                "game_date":    r.get("game_date"),
                "game_id":      r.get("game_id"),
                "home_team":    r.get("home_team"),
                "away_team":    r.get("away_team"),
                "game_time_et": r.get("game_time_et"),
                "pred_total":   _safe(r.get("pred_total")),
                "lean":         r.get("lean"),
                "p_over":       _safe(r.get("p_over")),
                "confidence":   r.get("confidence"),
                "line":         _safe(r.get("line")),
                "edge":         _safe(r.get("edge")),
                "pred_h1":      _safe(r.get("pred_h1")),
                "h1_lean":      r.get("h1_lean"),
                "h1_p_over":    _safe(r.get("h1_p_over")),
                "h1_confidence":r.get("h1_confidence"),
                "h1_line":      _safe(r.get("h1_line")),
                "h1_edge":      _safe(r.get("h1_edge")),
                "rolling_league_avg":    _safe(r.get("rolling_league_avg")),
                "rolling_h1_league_avg": _safe(r.get("rolling_h1_league_avg")),
            })
        print(f"[push_nba] Loaded {len(rows)} projections for {game_date}")
        return rows
    except Exception as e:
        print(f"[push_nba] Failed to load projections: {e}", file=sys.stderr)
        return []


def build_season_accuracy() -> dict:
    """Compute running MAE + directional HR from nba_results_log.parquet."""
    if not os.path.exists(NBA_RESULTS_PATH):
        return {}
    try:
        import pandas as pd
        log = pd.read_parquet(NBA_RESULTS_PATH)
        if log.empty:
            return {}

        out = {"total_games": int(len(log))}

        by_conf = {}
        for conf in ["HIGH", "MEDIUM", "LOW"]:
            sub = log[log["confidence"] == conf]
            if len(sub) == 0:
                continue
            mae  = float(sub["full_err"].abs().mean())
            hr   = float(sub["full_correct"].mean() * 100)
            bias = float(sub["full_err"].mean())
            by_conf[conf] = {
                "n":    int(len(sub)),
                "mae":  round(mae, 2),
                "hr":   round(hr, 1),
                "bias": round(bias, 2),
            }

        # Overall
        mae_all  = float(log["full_err"].abs().mean())
        hr_all   = float(log["full_correct"].mean() * 100)
        bias_all = float(log["full_err"].mean())
        out["overall"] = {
            "n":    int(len(log)),
            "mae":  round(mae_all, 2),
            "hr":   round(hr_all, 1),
            "bias": round(bias_all, 2),
        }
        out["by_confidence"] = by_conf

        # Market gap count
        if "market_gap_flag" in log.columns:
            out["market_gap_count"] = int(log["market_gap_flag"].sum())

        print(f"[push_nba] Season accuracy: {len(log)} games graded. "
              f"Overall MAE={mae_all:.2f} HR={hr_all:.1f}%")
        return out
    except Exception as e:
        print(f"[push_nba] Season accuracy failed: {e}", file=sys.stderr)
        return {}


def serialize(game_date: str, games: list[dict], accuracy: dict) -> dict:
    plays    = [g for g in games if g.get("confidence") in ("HIGH", "MEDIUM")]
    no_plays = [g for g in games if g not in plays]

    # Sort plays: HIGH first, then MEDIUM; within tier by |edge| desc
    def _sort_key(g):
        tier = {"HIGH": 0, "MEDIUM": 1}.get(g.get("confidence", "LOW"), 2)
        edge = abs(g.get("edge") or 0)
        return (tier, -edge)

    plays.sort(key=_sort_key)

    return {
        "generated_at":    datetime.utcnow().isoformat() + "Z",
        "game_date":       game_date,
        "plays":           plays,
        "no_plays":        no_plays,
        "season_accuracy": accuracy,
    }


def git_push(game_date: str) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}",
                  file=sys.stderr)
            return False
        return True

    run(["git", "add", "nba_results.json"])

    status = subprocess.run(
        ["git", "status", "--porcelain", "nba_results.json"],
        cwd=REPO_DIR, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("[push_nba] Nothing to commit — nba_results.json unchanged.")
        return True

    if not run(["git", "commit", "-m", f"nba: {game_date}"]):
        return False

    if not run(["git", "push"]):
        return False

    print("[push_nba] Pushed successfully.")
    return True


def push_nba(game_date: str = None, push: bool = True) -> None:
    game_date = game_date or date.today().isoformat()

    games    = load_today_projections(game_date)
    accuracy = build_season_accuracy()
    payload  = serialize(game_date, games, accuracy)

    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[push_nba] Wrote {OUT_PATH} ({len(games)} games)")

    if push:
        git_push(game_date)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",     default=None)
    parser.add_argument("--no-push",  action="store_true")
    args = parser.parse_args()
    push_nba(game_date=args.date, push=not args.no_push)


if __name__ == "__main__":
    main()
