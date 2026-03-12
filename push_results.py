#!/usr/bin/env python3
"""
push_results.py — Serialize today's model output to results.json and push to GitHub.

Usage:
    python push_results.py                  # runs today's model, saves + pushes
    python push_results.py --date 2025-04-15
    python push_results.py --no-push        # save JSON locally but don't git push
    python push_results.py --no-odds        # skip Odds API (faster, less data)
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime

# ── run the model ──────────────────────────────────────────────────────────────

def run_model(game_date: str, use_odds: bool) -> list[dict]:
    import run_model as rm
    import db
    from modules.odds import edge_summary
    return rm.run(game_date=game_date, quiet=True, use_odds=use_odds)


# ── serialize ──────────────────────────────────────────────────────────────────

def _safe(v):
    """Make a value JSON-safe (handles None, int, float, str)."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def serialize_results(raw: list[dict], game_date: str) -> dict:
    """Convert raw result dicts from run_model.run() into a JSON-serializable payload."""
    import db
    from modules.odds import edge_summary
    from run_model import classify_game, generate_summary, edge_summary

    plays    = []
    no_plays = []
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

        block = {
            "rating":    rating,
            "game":      {k: _safe(v) for k, v in r["game"].items()},
            "proj":      {
                "lean":              proj["lean"],
                "proj_total_full":   _safe(proj["proj_total_full"]),
                "proj_total_f5":     _safe(proj["proj_total_f5"]),
                "confidence":        proj["confidence"],
                "confidence_score":  _safe(proj["confidence_score"]),
                "factors":           {k: _safe(v) for k, v in proj["factors"].items()},
            },
            "full_edge": {k: _safe(v) for k, v in fe.items()},
            "f5_edge":   {k: _safe(v) for k, v in f5e.items()},
            "summary":   summary,
        }
        (plays if rating != "NO PLAY" else no_plays).append(block)

    plays.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -(b["proj"]["confidence_score"] or 0),
    ))

    # parlay: top 3 two-star+ plays by edge then confidence
    parlay_legs = [b for b in plays if b["rating"] in ("⭐⭐⭐", "⭐⭐")]
    parlay_legs.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -abs(b["full_edge"].get("edge") or 0),
        -(b["proj"]["confidence_score"] or 0),
    ))
    parlay_legs = parlay_legs[:3]

    record = db.get_season_record()

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "game_date":    game_date,
        "plays":        plays,
        "no_plays":     no_plays,
        "parlay":       parlay_legs if len(parlay_legs) >= 2 else [],
        "season_record": {k: _safe(v) for k, v in record.items()} if record else {},
    }


# ── git push ───────────────────────────────────────────────────────────────────

def git_push(repo_dir: str, game_date: str) -> bool:
    """Stage results.json and push to GitHub. Returns True on success."""
    def run(cmd):
        result = subprocess.run(
            cmd, cwd=repo_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}", file=sys.stderr)
            return False
        return True

    print("  git add results.json ...")
    if not run(["git", "add", "results.json"]):
        return False

    # Check if there's anything to commit
    status = subprocess.run(
        ["git", "status", "--porcelain", "results.json"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("  Nothing to commit — results.json unchanged.")
        return True

    print(f"  git commit ...")
    if not run(["git", "commit", "-m", f"results: {game_date}"]):
        return False

    print("  git push ...")
    if not run(["git", "push"]):
        return False

    print("  Pushed successfully.")
    return True


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run model and push results.json to GitHub")
    parser.add_argument("--date",     default=None, help="Game date YYYY-MM-DD (default: today)")
    parser.add_argument("--no-push",  action="store_true", help="Save JSON locally but skip git push")
    parser.add_argument("--no-odds",  action="store_true", help="Skip Odds API")
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()
    repo_dir  = os.path.dirname(os.path.abspath(__file__))
    out_path  = os.path.join(repo_dir, "results.json")

    print(f"[push_results] Running model for {game_date} ...")
    raw = run_model(game_date, use_odds=not args.no_odds)

    if not raw:
        print("[push_results] No games found — results.json not updated.")
        sys.exit(1)

    print(f"[push_results] Serializing {len(raw)} games ...")
    payload = serialize_results(raw, game_date)

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[push_results] Wrote {out_path}")

    if not args.no_push:
        print("[push_results] Pushing to GitHub ...")
        ok = git_push(repo_dir, game_date)
        if not ok:
            print("[push_results] Push failed — check git output above.", file=sys.stderr)
            sys.exit(1)
    else:
        print("[push_results] --no-push: skipping git push.")

    plays_n  = len(payload["plays"])
    noplay_n = len(payload["no_plays"])
    parlay_n = len(payload["parlay"])
    print(f"[push_results] Done. {plays_n} plays, {noplay_n} no-plays, {parlay_n} parlay legs.")


if __name__ == "__main__":
    main()
