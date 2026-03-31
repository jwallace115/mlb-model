#!/usr/bin/env python3
"""
NBA Phase 6 — Forward Shadow (Small Edge System).

Split into two independent logs:
  Phase 6 RS: regular season (through April 18, 2026)
  Phase 6 PO: playoffs (April 19, 2026 onward)

Same 0-1 edge logic + fast pace overlay in both.
Zero data mixing between RS and PO. Ever.

The 150-bet decision threshold applies ONLY to Phase 6 RS.
Phase 6 PO has no decision threshold — it is exploratory context only.

Usage:
    python3 nba/phase6_shadow.py                    # process today
    python3 nba/phase6_shadow.py --date 2026-03-18  # specific date
    python3 nba/phase6_shadow.py --summary          # print dashboard
    python3 nba/phase6_shadow.py --grade             # grade yesterday
"""

import argparse
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NBA_DIR = Path(__file__).resolve().parent
DATA_DIR = NBA_DIR / "data"

# Split logs — RS vs PO
SHADOW_RS = DATA_DIR / "nba_phase6_rs_shadow.parquet"
SHADOW_PO = DATA_DIR / "nba_phase6_po_shadow.parquet"

# Legacy log (pre-split data stays here, not backfilled)
SHADOW_LEGACY = DATA_DIR / "nba_small_edge_shadow.parquet"

FEATURES_PATH = DATA_DIR / "features.parquet"

# Playoff cutoff date (2025-26 season)
PLAYOFF_START = "2026-04-19"

_PACE_MEDIAN = None
WIN = 100.0 / 110.0


def _get_log_path(game_date: str) -> Path:
    """Route to RS or PO log based on game date."""
    return SHADOW_PO if game_date >= PLAYOFF_START else SHADOW_RS


def _get_pace_median() -> float:
    global _PACE_MEDIAN
    if _PACE_MEDIAN is not None:
        return _PACE_MEDIAN
    if FEATURES_PATH.exists():
        ft = pd.read_parquet(FEATURES_PATH)
        disc = ft[ft["season"].isin(["2022-23", "2023-24"])]
        _PACE_MEDIAN = float(disc["home_pace"].median())
    else:
        _PACE_MEDIAN = 100.0
    return _PACE_MEDIAN


def _build_rows(game_date: str) -> list[dict]:
    """Build qualifying 0-1 edge rows from today's projections."""
    proj_path = DATA_DIR / "nba_daily_projections.parquet"
    if not proj_path.exists():
        return []

    dp = pd.read_parquet(proj_path)
    today = dp[dp["game_date"] == game_date]
    if today.empty:
        return []

    pace_med = _get_pace_median()
    rows = []

    for _, g in today.iterrows():
        pred = g.get("pred_total")
        line = g.get("line")
        if pred is None or line is None or pd.isna(pred) or pd.isna(line):
            continue

        edge = pred - line
        abs_edge = abs(edge)
        if abs_edge > 1.0:
            continue

        lean = "OVER" if edge > 0 else "UNDER"
        home_pace = g.get("home_pace", 0) or 0
        away_pace = g.get("away_pace", 0) or 0
        both_fast = home_pace > pace_med and away_pace > pace_med
        overlay_applied = both_fast and lean == "OVER"

        original_tier = g.get("confidence", "LOW")
        if overlay_applied:
            final_tier = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "HIGH"}.get(original_tier, original_tier)
        else:
            final_tier = original_tier

        row_dict = {
            "date": game_date,
            "game_id": g.get("game_id"),
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "closing_total": float(line),
            "model_projection": round(float(pred), 2),
            "model_edge": round(float(edge), 2),
            "bet_direction": lean,
            "both_fast_pace": both_fast,
            "overlay_applied": overlay_applied,
            "overlay_segment": "both_fast_pace" if overlay_applied else None,
            "original_tier": original_tier,
            "final_tier": final_tier,
            "result": None,
            "roi_outcome": None,
        }

        # Playoff tagging — PO log only, observational fields
        # Source: playoff_round and series_game_number from nba_daily_projections.parquet
        if game_date >= PLAYOFF_START:
            row_dict["playoff_round"] = g.get("playoff_round")
            row_dict["playoff_game_number"] = g.get("series_game_number")

        rows.append(row_dict)

    return rows


def process_games(game_date: str):
    """Process today's projections and log qualifying 0-1 edge games."""
    rows = _build_rows(game_date)
    if not rows:
        logger.info(f"No 0-1 edge games for {game_date}")
        return

    new_df = pd.DataFrame(rows)
    log_path = _get_log_path(game_date)
    phase = "PO" if game_date >= PLAYOFF_START else "RS"

    if log_path.exists():
        existing = pd.read_parquet(log_path)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["game_id"], keep="last")
    else:
        combined = new_df

    combined.to_parquet(log_path, index=False)
    logger.info(f"[{phase}] Logged {len(new_df)} small-edge games for {game_date} ({len(combined)} total in {log_path.name})")
    for _, r in new_df.iterrows():
        ovl = " 🎯" if r["overlay_applied"] else ""
        print(f"  [{phase}] {r['away_team']}@{r['home_team']} {r['bet_direction']} {r['closing_total']:.1f} "
              f"edge={r['model_edge']:+.2f} {r['final_tier']}{ovl}")


def grade_games(grade_date: str):
    """Grade shadow games using results log. Routes to correct log file."""
    log_path = _get_log_path(grade_date)
    if not log_path.exists():
        # Also try legacy log
        if SHADOW_LEGACY.exists():
            log_path = SHADOW_LEGACY
        else:
            return

    log = pd.read_parquet(log_path)
    to_grade = log[(log["date"] == grade_date) & log["result"].isna()]
    if to_grade.empty:
        return

    rl_path = DATA_DIR / "nba_results_log.parquet"
    if not rl_path.exists():
        return

    rl = pd.read_parquet(rl_path)
    graded = 0

    for idx, row in to_grade.iterrows():
        gid = row["game_id"]
        result_row = rl[rl["game_id"] == gid]
        if result_row.empty:
            continue

        actual = result_row.iloc[0].get("actual_total")
        if actual is None or pd.isna(actual):
            continue

        line = row["closing_total"]
        lean = row["bet_direction"]

        if actual > line:
            result = "WIN" if lean == "OVER" else "LOSS"
        elif actual < line:
            result = "WIN" if lean == "UNDER" else "LOSS"
        else:
            result = "PUSH"

        roi = WIN if result == "WIN" else (-1.0 if result == "LOSS" else 0.0)
        log.loc[log["game_id"] == gid, "result"] = result
        log.loc[log["game_id"] == gid, "roi_outcome"] = roi
        graded += 1

    log.to_parquet(log_path, index=False)
    if graded:
        phase = "PO" if grade_date >= PLAYOFF_START else "RS"
        logger.info(f"[{phase}] Graded {graded} games for {grade_date}")


def _print_section(log_path: Path, label: str, target: int | None = None):
    """Print metrics for one shadow log section."""
    if not log_path.exists():
        print(f"\n  {label}: No data yet.")
        if label == "PLAYOFF (Phase 6 PO)":
            print(f"  Playoff tracking begins April 19")
        return

    log = pd.read_parquet(log_path)
    graded = log[log["result"].isin(["WIN", "LOSS"])].copy()

    print(f"\n  {'─'*55}")
    print(f"  {label}")
    print(f"  Source: {log_path.name}")
    print(f"  {'─'*55}")
    print(f"  Logged: {len(log)}, Graded: {len(graded)}, Pending: {log['result'].isna().sum()}")
    if len(log) > 0:
        print(f"  Date range: {log['date'].min()} to {log['date'].max()}")

    if len(graded) == 0:
        print(f"  No graded results yet.")
        return

    def metrics(df, lbl):
        if len(df) == 0:
            return
        w = (df["result"] == "WIN").sum()
        l = (df["result"] == "LOSS").sum()
        n = w + l
        hit = w / n if n > 0 else 0
        roi = (w * WIN - l) / n * 100 if n > 0 else 0
        print(f"  {lbl:<30} N={n:>4}, hit={hit:.1%}, ROI={roi:+.1f}%")

    metrics(graded, "All 0-1 edge")

    ovl = graded[graded["overlay_applied"] == True]
    non = graded[graded["overlay_applied"] != True]
    metrics(ovl, "Fast pace overlay")
    metrics(non, "Non-overlay")

    # Sub-buckets
    print(f"\n  Edge sub-buckets:")
    graded["abs_edge"] = graded["model_edge"].abs()
    for lo, hi in [(0, 0.25), (0.25, 0.50), (0.50, 0.75), (0.75, 1.0)]:
        sub = graded[(graded["abs_edge"] >= lo) & (graded["abs_edge"] < hi)]
        metrics(sub, f"    {lo:.2f}-{hi:.2f}")

    # Monthly
    graded["month"] = pd.to_datetime(graded["date"]).dt.to_period("M")
    print(f"\n  Monthly:")
    for m in sorted(graded["month"].unique()):
        sub = graded[graded["month"] == m]
        metrics(sub, f"    {m}")

    # Alerts
    print(f"\n  Alerts:")
    if len(graded) >= 30:
        last30 = graded.tail(30)
        w30 = (last30["result"] == "WIN").sum()
        l30 = len(last30) - w30
        roi30 = (w30 * WIN - l30) / (w30 + l30) * 100
        if roi30 < -10:
            print(f"    ⚠️ Last 30 bets ROI: {roi30:+.1f}%")
        else:
            print(f"    ✅ Last 30 bets ROI: {roi30:+.1f}%")

    # Progress (RS only)
    if target is not None:
        remaining = max(0, target - len(graded))
        print(f"\n  Progress: {len(graded)}/{target} minimum bets ({remaining} remaining)")
    else:
        print(f"\n  Note: exploratory only — not part of 150-bet validation threshold")


def print_summary():
    """Print split RS/PO dashboard."""
    print(f"\n{'='*60}")
    print(f"  NBA SMALL EDGE SHADOW — DASHBOARD")
    print(f"{'='*60}")

    # Regular Season — 150-bet decision threshold applies here ONLY
    _print_section(SHADOW_RS, "REGULAR SEASON (Phase 6 RS)", target=150)

    # Legacy data (pre-split)
    if SHADOW_LEGACY.exists():
        leg = pd.read_parquet(SHADOW_LEGACY)
        leg_graded = leg[leg["result"].isin(["WIN", "LOSS"])]
        if len(leg_graded) > 0:
            print(f"\n  Note: {len(leg_graded)} graded bets in legacy log (pre-split)")

    # Playoffs — no decision threshold, exploratory only
    today = date.today().isoformat()
    if today >= PLAYOFF_START or SHADOW_PO.exists():
        _print_section(SHADOW_PO, "PLAYOFF (Phase 6 PO)", target=None)
    else:
        print(f"\n  {'─'*55}")
        print(f"  PLAYOFF (Phase 6 PO)")
        print(f"  Playoff tracking begins April 19")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--grade", action="store_true")
    args = parser.parse_args()

    game_date = args.date or date.today().isoformat()

    if args.summary:
        print_summary()
        return

    if args.grade:
        yesterday = (date.fromisoformat(game_date) - timedelta(days=1)).isoformat()
        grade_games(yesterday)

    process_games(game_date)


if __name__ == "__main__":
    main()
