#!/usr/bin/env python3
"""
push_results.py — Grade yesterday, run today's model, push JSON files to GitHub.

Workflow:
  1. Grade yesterday's games → graded_results table
  2. Build season_stats.json from all historical graded data
  3. Run today's model → results.json
  4. git push both JSON files

Usage:
    python push_results.py                  # full run (grade + model + push)
    python push_results.py --date 2025-04-15
    python push_results.py --no-push        # save JSON locally, skip git push
    python push_results.py --no-odds        # skip Odds API
    python push_results.py --skip-grading   # skip yesterday's grading step
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta


# ── grade yesterday ────────────────────────────────────────────────────────────

def grade_yesterday(game_date: str) -> None:
    from results_tracker import grade_date
    yesterday = (datetime.fromisoformat(game_date) - timedelta(days=1)).date().isoformat()
    print(f"[push_results] Grading yesterday ({yesterday}) ...")
    try:
        results = grade_date(yesterday)
        wins   = sum(1 for r in results if r["result"] == "WIN")
        losses = sum(1 for r in results if r["result"] == "LOSS")
        plays  = sum(1 for r in results if r["was_a_play"])
        print(f"[push_results] Graded {len(results)} games. "
              f"Plays: {plays}  W/L: {wins}-{losses}")
    except Exception as e:
        print(f"[push_results] Grading failed (non-fatal): {e}", file=sys.stderr)


# ── season stats ──────────────────────────────────────────────────────────────

def build_season_stats_json(out_path: str) -> None:
    from analytics import build_season_stats
    print("[push_results] Building season_stats.json ...")
    stats = build_season_stats()
    with open(out_path, "w") as f:
        json.dump(stats, f, indent=2, default=str)
    print(f"[push_results] Wrote {out_path}")


# ── run the model ──────────────────────────────────────────────────────────────

def run_model(game_date: str, use_odds: bool) -> list[dict]:
    import run_model as rm
    return rm.run(game_date=game_date, quiet=True, use_odds=use_odds)


# ── serialize ──────────────────────────────────────────────────────────────────

def _safe(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def serialize_results(raw: list[dict], game_date: str) -> dict:
    import db
    from modules.odds import edge_summary
    from run_model import classify_game, generate_summary

    plays, no_plays = [], []
    star_order = {"⭐⭐⭐": 0, "⭐⭐": 1, "⭐": 2}

    for r in raw:
        proj       = r["projection"]
        odds       = r.get("odds", {})
        full_lines = odds.get("full") or {}
        f5_lines   = odds.get("f5")   or {}
        fe         = edge_summary(proj["proj_total_full"], full_lines)
        f5e        = edge_summary(proj["proj_total_f5"],  f5_lines)
        rating     = classify_game(proj, fe)
        summary    = generate_summary(r["game"], proj, odds, rating)

        raw_props = r.get("props") or []
        props_out = [
            {
                "player_name": p.get("player_name"),
                "team":        p.get("team"),
                "market":      p.get("market"),
                "projection":  _safe(p.get("projection")),
                "line":        _safe(p.get("line")),
                "lean":        p.get("lean"),
                "edge":        _safe(p.get("edge")),
                "edge_pct":    _safe(p.get("edge_pct")),
                "is_play":     bool(p.get("is_play")),
            }
            for p in raw_props
        ]

        block = {
            "rating":    rating,
            "game":      {k: _safe(v) for k, v in r["game"].items()},
            "proj":      {
                "lean":             proj["lean"],
                "proj_total_full":  _safe(proj["proj_total_full"]),
                "proj_total_f5":    _safe(proj["proj_total_f5"]),
                "confidence":       proj["confidence"],
                "confidence_score": _safe(proj["confidence_score"]),
                "factors":          {k: _safe(v) for k, v in proj["factors"].items()},
            },
            "full_edge": {k: _safe(v) for k, v in fe.items()},
            "f5_edge":   {k: _safe(v) for k, v in f5e.items()},
            "summary":   summary,
            "props":     props_out,
        }
        (plays if rating != "NO PLAY" else no_plays).append(block)

    plays.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -(b["proj"]["confidence_score"] or 0),
    ))

    parlay_legs = [b for b in plays if b["rating"] in ("⭐⭐⭐", "⭐⭐")]
    parlay_legs.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -abs(b["full_edge"].get("edge") or 0),
        -(b["proj"]["confidence_score"] or 0),
    ))
    parlay_legs = parlay_legs[:3]

    record = db.get_season_record()

    return {
        "generated_at":  datetime.utcnow().isoformat() + "Z",
        "game_date":     game_date,
        "plays":         plays,
        "no_plays":      no_plays,
        "parlay":        parlay_legs if len(parlay_legs) >= 2 else [],
        "season_record": {k: _safe(v) for k, v in record.items()} if record else {},
    }


# ── git push ───────────────────────────────────────────────────────────────────

def git_push(repo_dir: str, game_date: str, files: list[str]) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}",
                  file=sys.stderr)
            return False
        return True

    for f in files:
        print(f"  git add {f} ...")
        if not run(["git", "add", f]):
            return False

    status = subprocess.run(
        ["git", "status", "--porcelain"] + files,
        cwd=repo_dir, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("  Nothing to commit — JSON files unchanged.")
        return True

    print("  git commit ...")
    if not run(["git", "commit", "-m", f"results: {game_date}"]):
        return False

    print("  git push ...")
    if not run(["git", "push"]):
        return False

    print("  Pushed successfully.")
    return True


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Grade yesterday + run model + push to GitHub")
    parser.add_argument("--date",          default=None,        help="Game date YYYY-MM-DD (default: today)")
    parser.add_argument("--no-push",       action="store_true", help="Save JSON locally, skip git push")
    parser.add_argument("--no-odds",       action="store_true", help="Skip Odds API")
    parser.add_argument("--skip-grading",  action="store_true", help="Skip grading yesterday's games")
    args = parser.parse_args()

    game_date  = args.date or date.today().isoformat()
    repo_dir   = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(repo_dir, "results.json")
    stats_path   = os.path.join(repo_dir, "season_stats.json")

    # Step 1: grade yesterday
    if not args.skip_grading:
        grade_yesterday(game_date)

    # Step 2: build season_stats.json
    build_season_stats_json(stats_path)

    # Step 3: run today's model
    print(f"[push_results] Running model for {game_date} ...")
    raw = run_model(game_date, use_odds=not args.no_odds)
    if not raw:
        print("[push_results] No games found — results.json not updated.")
        sys.exit(1)

    print(f"[push_results] Serializing {len(raw)} games ...")
    payload = serialize_results(raw, game_date)
    with open(results_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[push_results] Wrote {results_path}")

    # Step 4: push both files
    if not args.no_push:
        print("[push_results] Pushing to GitHub ...")
        ok = git_push(repo_dir, game_date, ["results.json", "season_stats.json"])
        if not ok:
            print("[push_results] Push failed — check git output above.", file=sys.stderr)
            sys.exit(1)
    else:
        print("[push_results] --no-push: skipping git push.")

    plays_n  = len(payload["plays"])
    noplay_n = len(payload["no_plays"])
    parlay_n = len(payload["parlay"])
    print(f"[push_results] Done. {plays_n} plays, {noplay_n} no-plays, "
          f"{parlay_n} parlay legs.")


if __name__ == "__main__":
    main()
