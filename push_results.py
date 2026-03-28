#!/usr/bin/env python3
"""
push_results.py — Grade yesterday, run today's model, push JSON files to GitHub.

Workflow:
  1. Grade yesterday's MLB games → graded_results table
  2. Build season_stats.json from all historical graded data
  3. Run MLB model → results.json
  4. Run NBA model → grades yesterday's NBA games, saves fresh parquet
  5. Serialize nba_results.json from the fresh parquet
  6. Single git push covering results.json, season_stats.json, nba_results.json

Usage:
    python push_results.py                  # full run (grade + model + push)
    python push_results.py --date 2025-04-15
    python push_results.py --no-push        # save JSON locally, skip git push
    python push_results.py --no-odds        # skip Odds API
    python push_results.py --skip-grading   # skip yesterday's grading step
    python push_results.py --skip-nba       # skip NBA model run
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

import db


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
        }
        (plays if rating != "NO PLAY" else no_plays).append(block)

    plays.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -(b["proj"]["confidence_score"] or 0),
    ))

    from modules.parlays import build_all_parlays
    parlays = build_all_parlays(plays)

    # Persist parlays to DB so results_tracker can grade them later
    for ptype, legs in parlays.items():
        if legs:
            db.write_parlay(game_date, ptype, legs)

    record = db.get_season_record()

    return {
        "generated_at":  datetime.utcnow().isoformat() + "Z",
        "game_date":     game_date,
        "plays":         plays,
        "no_plays":      no_plays,
        "parlay":        parlays["parlay_3"],   # legacy key (3-leg sharp)
        "parlay_3":      parlays["parlay_3"],
        "parlay_5":      parlays["parlay_5"],
        "parlay_7":      parlays["parlay_7"],
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
        if not run(["git", "add", "-f", f]):
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

# ── transaction wire ──────────────────────────────────────────────────────────

def run_transaction_wire(game_date: str, games: list[dict]) -> list[dict]:
    """Fetch today's transactions, store relevant ones, return filtered list."""
    from modules.transactions import fetch_transactions, filter_to_model_relevant
    print("[push_results] Fetching transaction wire ...")
    try:
        raw_txns = fetch_transactions(game_date)
        relevant = filter_to_model_relevant(raw_txns, games)
        db.init_db()
        for txn in relevant:
            db.write_transaction({
                "game_date":      game_date,
                "transaction_id": txn["transaction_id"],
                "player_name":    txn["player_name"],
                "player_id":      txn.get("player_id"),
                "team_name":      txn.get("team_name"),
                "team_id":        txn.get("team_id"),
                "team_abb":       txn.get("team_abb"),
                "type_code":      txn.get("type_code"),
                "type_label":     txn.get("type_label"),
                "description":    txn.get("description"),
                "affects_game_pk": txn.get("affects_game_pk"),
                "affects_team":   txn.get("affects_team"),
                "affects_matchup": txn.get("affects_matchup"),
            })
        print(f"[push_results] Stored {len(relevant)} relevant transactions.")
        return relevant
    except Exception as e:
        print(f"[push_results] Transaction wire failed (non-fatal): {e}", file=sys.stderr)
        return []


def build_mlb_clv_summary() -> dict:
    """
    Compute CLV summary from graded_results table.
    Only includes rows where clv_directional IS NOT NULL (live-season, has closing line).
    Guards: n < 20 → empty summary; coverage < 50% → coverage_warning flag.
    """
    try:
        rows = db.get_all_graded_results()
        plays = [r for r in rows if r.get("was_a_play")]
        n_total = len(plays)
        has_clv = [r for r in plays if r.get("clv_directional") is not None]
        n_clv = len(has_clv)
        coverage = round(n_clv / n_total * 100, 1) if n_total > 0 else 0.0

        if n_clv < 20:
            return {"clv_available": False, "reason": f"insufficient_sample (n={n_clv})",
                    "clv_coverage_pct": coverage}

        vals = [r["clv_directional"] for r in has_clv]
        avg_clv    = round(sum(vals) / len(vals), 3)
        sorted_v   = sorted(vals)
        mid        = len(sorted_v) // 2
        median_clv = round(
            sorted_v[mid] if len(sorted_v) % 2 else (sorted_v[mid-1] + sorted_v[mid]) / 2, 3
        )
        pct_pos = round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1)

        by_tier: dict = {}
        for tier in ("HIGH", "MEDIUM", "LOW"):
            sub = [r["clv_directional"] for r in has_clv if r.get("confidence") == tier]
            by_tier[tier] = round(sum(sub)/len(sub), 3) if sub else None

        by_side: dict = {}
        for side in ("OVER", "UNDER"):
            sub = [r["clv_directional"] for r in has_clv
                   if r.get("recommendation") == side]
            by_side[side] = round(sum(sub)/len(sub), 3) if sub else None

        return {
            "clv_available":    True,
            "total_with_clv":   n_clv,
            "avg_clv":          avg_clv,
            "median_clv":       median_clv,
            "pct_positive_clv": pct_pos,
            "avg_clv_by_tier":  by_tier,
            "avg_clv_by_side":  by_side,
            "clv_coverage_pct": coverage,
            "coverage_warning": coverage < 50.0,
        }
    except Exception as e:
        return {"clv_available": False, "reason": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Grade yesterday + run model + push to GitHub")
    parser.add_argument("--date",          default=None,        help="Game date YYYY-MM-DD (default: today)")
    parser.add_argument("--no-push",       action="store_true", help="Save JSON locally, skip git push")
    parser.add_argument("--no-odds",       action="store_true", help="Skip Odds API")
    parser.add_argument("--skip-grading",  action="store_true", help="Skip grading yesterday's games")
    parser.add_argument("--skip-nba",      action="store_true", help="Skip NBA model run")
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

    # Step 4: transaction wire (needs game list from the model run)
    games_for_txn = [r["game"] for r in raw]
    transactions  = run_transaction_wire(game_date, games_for_txn)

    # Step 5: serialize results
    print(f"[push_results] Serializing {len(raw)} games ...")
    payload = serialize_results(raw, game_date)
    payload["transactions"] = transactions
    payload["mlb_clv_summary"] = build_mlb_clv_summary()

    # Stop rules — evaluated after grading so today's results are reflected
    try:
        from mlb_stop_rules import evaluate_mlb_stop_rules, apply_mlb_stop_rule_filter
        stop_status = evaluate_mlb_stop_rules()
        payload["stop_rule_status"] = stop_status
        if stop_status.get("model_suspended") or stop_status.get("suspended_tiers"):
            print(f"[push_results] MLB STOP RULE ACTIVE: "
                  f"model_suspended={stop_status['model_suspended']}, "
                  f"tiers={stop_status['suspended_tiers']}")
            active_plays, updated_no_plays = apply_mlb_stop_rule_filter(
                payload["plays"], payload["no_plays"], stop_status
            )
            payload["plays"]    = active_plays
            payload["no_plays"] = updated_no_plays
    except Exception as e:
        print(f"[push_results] MLB stop rule evaluation failed (non-fatal): {e}", file=sys.stderr)
        payload["stop_rule_status"] = {"model_suspended": False, "suspended_tiers": []}

    # AI daily (and optional weekly) review
    try:
        from modules.ai_review import (build_graded_games, generate_daily_review,
                                        maybe_weekly, build_week_games,
                                        generate_weekly_review, is_idempotent)
        _review_date = (datetime.fromisoformat(game_date) - timedelta(days=1)).date().isoformat()
        if not is_idempotent(results_path, _review_date):
            _graded = build_graded_games("mlb", _review_date)
            payload["daily_review"] = generate_daily_review(_graded, "mlb", _review_date)
        else:
            print(f"[push_results] MLB daily review already exists for {_review_date} — skipping")
        _wr = maybe_weekly("mlb")
        if _wr:
            _wg = build_week_games("mlb", *_wr)
            payload["weekly_review"] = generate_weekly_review(_wg, "mlb", *_wr)
    except Exception as e:
        print(f"[push_results] MLB AI review failed (non-fatal): {e}", file=sys.stderr)

    with open(results_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[push_results] Wrote {results_path}")

    # Step 6: run NBA model → fresh parquet + NBA grading, then serialize JSON
    dashboard_files = ["results.json", "season_stats.json"]
    skip_nba = args.skip_nba
    if not skip_nba:
        try:
            print(f"[push_results] Running NBA model for {game_date} ...")
            from nba.run_nba import run as nba_run
            nba_run(game_date=game_date, use_odds=not args.no_odds, skip_results=False)
            print(f"[push_results] NBA model complete.")
        except Exception as e:
            print(f"[push_results] NBA model failed (non-fatal): {e}", file=sys.stderr)
        try:
            from push_nba import write_nba_json
            write_nba_json(game_date)
            dashboard_files.append("nba_results.json")
        except Exception as e:
            print(f"[push_results] NBA JSON write failed (non-fatal): {e}", file=sys.stderr)
    else:
        print("[push_results] --skip-nba: skipping NBA model run.")

    # Step 6b: NHL — canonical refresh first, then grade + pipeline + serialize
    try:
        print(f"[push_results] Refreshing NHL canonical table ...")
        subprocess.run(
            [sys.executable, "nhl/nhl_refresh_canonical.py"],
            cwd=repo_dir, check=False,
        )
    except Exception as e:
        print(f"[push_results] NHL canonical refresh failed (non-fatal): {e}", file=sys.stderr)
    try:
        print(f"[push_results] Running NHL pipeline (--grade-yesterday) for {game_date} ...")
        subprocess.run(
            [sys.executable, "nhl/nhl_daily_pipeline.py", "--grade-yesterday", "--date", game_date],
            cwd=repo_dir, check=False,
        )
    except Exception as e:
        print(f"[push_results] NHL pipeline failed (non-fatal): {e}", file=sys.stderr)
    try:
        from push_nhl import write_nhl_json
        write_nhl_json(game_date)
        dashboard_files.append("nhl_results.json")
    except Exception as e:
        print(f"[push_results] NHL JSON write failed (non-fatal): {e}", file=sys.stderr)

    # Step 6c: Soccer — canonical refresh, then grade + pipeline + serialize
    try:
        print(f"[push_results] Refreshing Soccer canonical table ...")
        subprocess.run(
            [sys.executable, "soccer/soccer_refresh_canonical.py"],
            cwd=repo_dir, check=False,
        )
    except Exception as e:
        print(f"[push_results] Soccer canonical refresh failed (non-fatal): {e}", file=sys.stderr)
    try:
        print(f"[push_results] Running Soccer pipeline (--grade-yesterday) for {game_date} ...")
        subprocess.run(
            [sys.executable, "soccer/soccer_daily_pipeline.py", "--grade-yesterday", "--date", game_date],
            cwd=repo_dir, check=False,
        )
    except Exception as e:
        print(f"[push_results] Soccer pipeline failed (non-fatal): {e}", file=sys.stderr)
    try:
        from push_soccer import write_soccer_json
        write_soccer_json(game_date)
        dashboard_files.append("soccer_results.json")
    except Exception as e:
        print(f"[push_results] Soccer JSON write failed (non-fatal): {e}", file=sys.stderr)

    # Step 6d: NFL — pipeline + serialize
    try:
        print(f"[push_results] Running NFL pipeline for {game_date} ...")
        subprocess.run(
            [sys.executable, "nfl/nfl_daily_pipeline.py", "--date", game_date],
            cwd=repo_dir, check=False,
        )
    except Exception as e:
        print(f"[push_results] NFL pipeline failed (non-fatal): {e}", file=sys.stderr)
    try:
        from push_nfl import write_nfl_json
        write_nfl_json(game_date)
        dashboard_files.append("nfl_results.json")
    except Exception as e:
        print(f"[push_nfl] NFL JSON write failed (non-fatal): {e}", file=sys.stderr)

    # Step 6e: Review Engine — daily scan
    try:
        sys.path.insert(0, os.path.join(repo_dir, "review_engine"))
        from engine import daily_scan
        alerts = daily_scan(game_date)
        if alerts:
            for a in alerts:
                print(f"[review_engine] [{a['level']}] {a['message']}")
    except Exception as e:
        print(f"[review_engine] Review engine failed (non-fatal): {e}", file=sys.stderr)

    # Step 6f: Add signal log JSON files for Streamlit Cloud
    for _sig_json in [
        "mlb_sim/logs/signals_2026.json",
        "mlb_sim/logs/f5_signals_2026.json",
        "mlb_sim/logs/f5_runline_2026.json",
        "mlb_sim/logs/parlay_tracker_2026.json",
        "mlb_sim/data/line_snapshots_2026.json",
    ]:
        if os.path.exists(os.path.join(repo_dir, _sig_json)):
            dashboard_files.append(_sig_json)

    # Step 7: single combined push for all dashboard artifacts
    if not args.no_push:
        print(f"[push_results] Pushing {', '.join(dashboard_files)} to GitHub ...")
        ok = git_push(repo_dir, game_date, dashboard_files)
        if not ok:
            print("[push_results] Push failed — check git output above.", file=sys.stderr)
            sys.exit(1)
    else:
        print("[push_results] --no-push: skipping git push.")

    plays_n  = len(payload["plays"])
    noplay_n = len(payload["no_plays"])
    p3_n     = len(payload["parlay_3"])
    p5_n     = len(payload["parlay_5"])
    p7_n     = len(payload["parlay_7"])
    txn_n    = len(transactions)
    print(f"[push_results] parlay_3={p3_n} legs, parlay_5={p5_n} legs, parlay_7={p7_n} legs")
    print(f"[push_results] Done. {plays_n} plays, {noplay_n} no-plays | "
          f"Parlays: 3-leg ({p3_n} legs), 5-leg ({p5_n} legs), 7-leg ({p7_n} legs) | "
          f"{txn_n} transactions.")


if __name__ == "__main__":
    main()
