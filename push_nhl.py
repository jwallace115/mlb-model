#!/usr/bin/env python3
"""
push_nhl.py — Serialize NHL signals + historical performance to nhl_results.json.

Called from push_results.py (daily 7am) or standalone.

Usage:
    python push_nhl.py              # serialize + push
    python push_nhl.py --no-push    # serialize only
    python push_nhl.py --date 2026-03-16
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_DIR     = Path(__file__).parent
NHL_DIR      = REPO_DIR / "nhl"
DECISIONS    = NHL_DIR / "nhl_decisions.parquet"
RESULTS_P    = NHL_DIR / "nhl_results.parquet"
OUT_PATH     = REPO_DIR / "nhl_results.json"

WIN_PER_UNIT = 100.0 / 110.0


def _safe(v):
    if v is None:
        return None
    if hasattr(v, "item"):          # numpy scalar
        return v.item()
    if isinstance(v, float) and v != v:  # NaN
        return None
    return v


def load_today_signals(game_date: str) -> list[dict]:
    """
    Live signals from nhl_decisions.parquet for today (all tiers, all sides).

    FIX 4: caution_flag suppresses display warning only — does NOT filter signals.
    Rows with caution_flag=1 are included in the output exactly like any other row.
    The dashboard renders a ⚠ badge; no signal is suppressed here.
    """
    if not DECISIONS.exists():
        return []
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS)
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date.astype(str)
        today_live = dec[
            (dec["game_date"] == game_date) &
            (dec["split"] == "live")
        ]
        rows = []
        for _, r in today_live.iterrows():
            rows.append({
                "game_id":          _safe(r.get("game_id")),
                "game_date":        r.get("game_date"),
                "home_team":        r.get("home_team"),
                "away_team":        r.get("away_team"),
                "signal_side":      r.get("signal_side"),
                "closing_total":    _safe(r.get("closing_total")),
                "edge":             _safe(r.get("edge")),
                "edge_bucket":      r.get("edge_bucket"),
                "sim_prob":         _safe(r.get("sim_prob")),
                "confidence_tier":  r.get("confidence_tier"),
                # caution_flag: display warning only — does not suppress signal
                "caution_flag":     int(r.get("caution_flag") or 0),
                "volatility_bucket": r.get("volatility_bucket"),
                "lambda_total_calibrated": _safe(r.get("lambda_total_calibrated")),
                "over_price":       _safe(r.get("over_price")),
                "under_price":      _safe(r.get("under_price")),
                "book":             r.get("book"),
                "result":           r.get("result"),
                "graded":           int(r.get("graded") or 0),
            })
        print(f"[push_nhl] Today's signals: {len(rows)}")
        return rows
    except Exception as e:
        print(f"[push_nhl] Failed to load today signals: {e}", file=sys.stderr)
        return []


def load_recent_results(days: int = 14) -> list[dict]:
    """Graded live signals from the past `days` days in nhl_decisions.parquet."""
    if not DECISIONS.exists():
        return []
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS)
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date
        cutoff = (date.today() - timedelta(days=days))
        recent = dec[
            (dec["game_date"] >= cutoff) &
            (dec["split"] == "live") &
            (dec["graded"] == 1)
        ].sort_values("game_date", ascending=False)
        rows = []
        for _, r in recent.iterrows():
            rows.append({
                "game_id":          _safe(r.get("game_id")),
                "game_date":        r["game_date"].isoformat(),
                "home_team":        r.get("home_team"),
                "away_team":        r.get("away_team"),
                "signal_side":      r.get("signal_side"),
                "closing_total":    _safe(r.get("closing_total")),
                "edge":             _safe(r.get("edge")),
                "confidence_tier":  r.get("confidence_tier"),
                "result":           r.get("result"),
                "actual_total_goals_final": _safe(r.get("actual_total_goals_final")),
            })
        print(f"[push_nhl] Recent results ({days}d): {len(rows)}")
        return rows
    except Exception as e:
        print(f"[push_nhl] Failed to load recent results: {e}", file=sys.stderr)
        return []


def build_season_performance() -> dict:
    """Aggregate WIN/LOSS/PUSH from nhl_results.parquet (Phase 5 historical data)."""
    if not RESULTS_P.exists():
        return {}
    try:
        import numpy as np
        import pandas as pd
        res = pd.read_parquet(RESULTS_P)
        graded = res[res["graded"] == 1]

        def agg(df):
            W = int((df["result"] == "WIN").sum())
            L = int((df["result"] == "LOSS").sum())
            P = int((df["result"] == "PUSH").sum())
            n = W + L + P
            hit = round(W / (W + L), 4) if (W + L) > 0 else None
            roi = round((W * WIN_PER_UNIT - L) / n * 100, 2) if n > 0 else None
            return {"W": W, "L": L, "P": P, "n": n, "hit": hit, "roi": roi}

        out = {}
        for split in ("validate", "oos"):
            out[split] = agg(graded[graded["split"] == split])
        out["combined"] = agg(graded)

        # By confidence tier (combined)
        by_tier = {}
        for tier in ("HIGH", "MEDIUM", "LOW"):
            by_tier[tier] = agg(graded[graded["confidence_tier"] == tier])
        out["by_confidence_tier"] = by_tier

        print(f"[push_nhl] Season performance: combined n={out['combined']['n']}")
        return out
    except Exception as e:
        print(f"[push_nhl] Season performance failed: {e}", file=sys.stderr)
        return {}


def _pipeline_freshness(game_date: str) -> tuple[str, str]:
    """
    Return (pipeline_run_date, signals_source).
    pipeline_run_date: most recent game_date in the live split of decisions parquet.
    signals_source: "live" if pipeline ran today, "stale" if yesterday or earlier.
    """
    if not DECISIONS.exists():
        return game_date, "stale"
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS, columns=["game_date", "split"])
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date.astype(str)
        live = dec[dec["split"] == "live"]
        if live.empty:
            return game_date, "stale"
        most_recent = live["game_date"].max()
        source = "live" if most_recent == game_date else "stale"
        return most_recent, source
    except Exception:
        return game_date, "stale"


def write_nhl_json(game_date: str = None) -> str:
    """Write nhl_results.json and return path. Does NOT git push."""
    game_date = game_date or date.today().isoformat()

    today_signals   = load_today_signals(game_date)
    recent_results  = load_recent_results(days=14)
    season_perf     = build_season_performance()

    # Sort today's signals: HIGH first, then by edge desc
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    today_signals.sort(key=lambda s: (
        tier_order.get(s.get("confidence_tier", "LOW"), 2),
        -(s.get("edge") or 0),
    ))

    # FIX 5: data freshness fields
    now_utc = datetime.now(timezone.utc)
    pipeline_run_date, signals_source = _pipeline_freshness(game_date)

    # ── FIX 6: pre-serialization consistency audit ────────────────────────────
    quality_warning = False
    warnings_found  = []

    # Top-level type assertions
    if not isinstance(today_signals, list):
        warnings_found.append(f"today_signals is not a list: {type(today_signals)}")
        today_signals = []
        quality_warning = True

    if not isinstance(recent_results, list):
        warnings_found.append(f"recent_results is not a list: {type(recent_results)}")
        recent_results = []
        quality_warning = True

    if not season_perf:
        warnings_found.append("season_performance is empty or missing")
        quality_warning = True

    # Per-signal field assertions
    valid_sides = {"OVER", "UNDER"}
    valid_tiers = {"HIGH", "MEDIUM", "LOW"}
    for i, s in enumerate(today_signals):
        if s.get("game_id") is None:
            warnings_found.append(f"signal[{i}]: game_id is null")
            quality_warning = True
        if s.get("closing_total") is None:
            warnings_found.append(f"signal[{i}]: closing_total is null")
            quality_warning = True
        edge = s.get("edge")
        if edge is None or not isinstance(edge, (int, float)) or not (0.0 <= edge <= 1.0):
            warnings_found.append(f"signal[{i}]: edge={edge!r} not in [0,1]")
            quality_warning = True
        if s.get("signal_side") not in valid_sides:
            warnings_found.append(f"signal[{i}]: signal_side={s.get('signal_side')!r} invalid")
            quality_warning = True
        if s.get("confidence_tier") not in valid_tiers:
            warnings_found.append(f"signal[{i}]: confidence_tier={s.get('confidence_tier')!r} invalid")
            quality_warning = True

    for w in warnings_found:
        print(f"[push_nhl] DATA QUALITY WARNING: {w}", file=sys.stderr)

    payload = {
        "generated_at":        now_utc.isoformat(),
        "last_updated":        now_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "pipeline_run_date":   pipeline_run_date,
        "signals_source":      signals_source,
        "game_date":           game_date,
        "today_signals":       today_signals,
        "recent_results":      recent_results,
        "season_performance":  season_perf,
        "data_quality_warning": quality_warning,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    perf_rows = len(season_perf) if season_perf else 0
    print(
        f"[push_nhl] complete: {len(today_signals)} signals, "
        f"{len(recent_results)} recent results, "
        f"{perf_rows} performance rows, "
        f"quality_warning={str(quality_warning).lower()}"
    )
    print(f"[push_nhl] Wrote {OUT_PATH}")
    return str(OUT_PATH)


def git_push(game_date: str) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=str(REPO_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}",
                  file=sys.stderr)
            return False
        return True

    run(["git", "add", "nhl_results.json"])
    status = subprocess.run(
        ["git", "status", "--porcelain", "nhl_results.json"],
        cwd=str(REPO_DIR), capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("[push_nhl] Nothing to commit — nhl_results.json unchanged.")
        return True
    if not run(["git", "commit", "-m", f"nhl: {game_date}"]):
        return False
    if not run(["git", "push"]):
        return False
    print("[push_nhl] Pushed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    default=None)
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()
    write_nhl_json(args.date)
    if not args.no_push:
        git_push(args.date or date.today().isoformat())


if __name__ == "__main__":
    main()
