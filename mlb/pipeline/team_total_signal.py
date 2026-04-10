#!/usr/bin/env python3
"""
Team Total Shadow Signal Engine
=================================
Computes fair-value team totals using the Phase 6 model (L4: empirical share +
truncation + starter quality) and compares to posted team total lines.

SHADOW ONLY — research-grade signal, does not affect live picks.

Frozen formula:
  fair_home = closing_total * 0.5015 - 0.248 + (away_SP_era - 4.50) * 0.621
  fair_away = closing_total * 0.4985         + (home_SP_era - 4.50) * 0.621

Signal fires when gap (posted - fair) exceeds 0.25 runs.

Usage:
  python3 mlb/pipeline/team_total_signal.py
  python3 mlb/pipeline/team_total_signal.py --grade
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("team_total_signal")

TT_DATA_PATH = PROJECT_ROOT / "mlb_sim" / "data" / "team_totals_2026.json"
TT_SHADOW_PATH = PROJECT_ROOT / "mlb_sim" / "logs" / "team_total_shadow_2026.json"
PGL_PATH = PROJECT_ROOT / "mlb" / "data" / "pitcher_game_logs.parquet"
GT_PATH = PROJECT_ROOT / "sim" / "data" / "game_table.parquet"

# ── Frozen model parameters (Phase 6 research) ──────────────────────────────
HOME_SHARE = 0.5015
TRUNCATION_ADJ = 0.248
LEAGUE_AVG_ERA = 4.50  # approximate 2022-2025 league starter ERA
SP_INNINGS_FACTOR = 0.621
GAP_THRESHOLD = 0.25


def _load_starter_era():
    """Build per-pitcher rolling ERA from pitcher_game_logs (pregame-safe)."""
    if not PGL_PATH.exists():
        return {}

    pgl = pd.read_parquet(PGL_PATH)
    sp = pgl[pgl["starter_flag"] == 1].copy()
    sp = sp.sort_values(["player_id", "season", "game_date"])

    current_year = date.today().year
    sp = sp[sp["season"] == current_year].copy()

    # Expanding ERA (shifted by 1 — pregame safe)
    sp["cum_er"] = sp.groupby("player_id")["earned_runs"].transform(lambda x: x.shift(1).expanding().sum())
    sp["cum_ip"] = sp.groupby("player_id")["innings_pitched"].transform(lambda x: x.shift(1).expanding().sum())
    sp["rolling_era"] = np.where(sp["cum_ip"] > 0, sp["cum_er"] / sp["cum_ip"] * 9, np.nan)

    # Latest ERA per pitcher
    latest = sp.dropna(subset=["rolling_era"]).groupby("player_id").last()
    return dict(zip(latest.index, latest["rolling_era"]))


def _load_team_totals():
    """Load today's posted team total lines."""
    if not TT_DATA_PATH.exists():
        return []
    try:
        data = json.loads(TT_DATA_PATH.read_text())
        today = date.today().isoformat()
        return [r for r in data if r.get("game_date") == today]
    except Exception:
        return []


def compute_signals(game_date=None):
    """Compute team total shadow signals for today."""
    game_date = game_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    # Load team totals
    tt_records = _load_team_totals()
    if not tt_records:
        logger.info("No team total lines available for today")
        return []

    # Load starter ERA
    era_map = _load_starter_era()
    logger.info(f"Starter ERA map: {len(era_map)} pitchers")

    # Fetch today's probable starters from MLB Stats API
    _schedule_starters = {}
    try:
        import requests
        r = requests.get("https://statsapi.mlb.com/api/v1/schedule", params={
            "sportId": 1, "date": game_date, "hydrate": "probablePitcher"
        }, timeout=15)
        for g in r.json().get("dates", [{}])[0].get("games", []):
            gpk = str(g["gamePk"])
            hp = g.get("teams", {}).get("home", {}).get("probablePitcher", {})
            ap = g.get("teams", {}).get("away", {}).get("probablePitcher", {})
            _schedule_starters[gpk] = {
                "home_pid": hp.get("id"),
                "away_pid": ap.get("id"),
                "home_name": hp.get("fullName", ""),
                "away_name": ap.get("fullName", ""),
            }
        logger.info(f"MLB API starters: {len(_schedule_starters)} games")
    except Exception as e:
        logger.warning(f"MLB API starter fetch failed: {e}")

    signals = []
    for tt in tt_records:
        home = tt.get("home_team", "")
        away = tt.get("away_team", "")
        posted_home = tt.get("home_total_line")
        posted_away = tt.get("away_total_line")
        event_id = tt.get("event_id", "")

        if posted_home is None and posted_away is None:
            continue

        # Derive closing total from team totals
        closing_total = None
        if posted_home is not None and posted_away is not None:
            closing_total = posted_home + posted_away

        if closing_total is None:
            continue

        # Find starter quality
        home_sp_era = LEAGUE_AVG_ERA
        away_sp_era = LEAGUE_AVG_ERA
        home_sp_name = ""
        away_sp_name = ""
        sp_adj_available_home = False
        sp_adj_available_away = False

        # Match starters via MLB Stats API schedule (probablePitcher)
        gpk = str(tt.get("game_pk", ""))
        home_abbr = tt.get("home_team_abbr", "")
        away_abbr = tt.get("away_team_abbr", "")

        if gpk in _schedule_starters:
            h_pid = _schedule_starters[gpk].get("home_pid")
            a_pid = _schedule_starters[gpk].get("away_pid")
            if h_pid and h_pid in era_map:
                home_sp_era = era_map[h_pid]
                home_sp_name = _schedule_starters[gpk].get("home_name", "")
                sp_adj_available_home = True
            if a_pid and a_pid in era_map:
                away_sp_era = era_map[a_pid]
                away_sp_name = _schedule_starters[gpk].get("away_name", "")
                sp_adj_available_away = True

        degraded = not sp_adj_available_home or not sp_adj_available_away
        if degraded:
            logger.warning(f"TT degraded mode: {away}@{home} — "
                           f"sp_home={sp_adj_available_home}, sp_away={sp_adj_available_away}")

        # ── Compute fair values using frozen formula ──
        truncation_adj = TRUNCATION_ADJ
        sp_adj_home = (away_sp_era - LEAGUE_AVG_ERA) * SP_INNINGS_FACTOR
        sp_adj_away = (home_sp_era - LEAGUE_AVG_ERA) * SP_INNINGS_FACTOR

        fair_home = closing_total * HOME_SHARE - truncation_adj + sp_adj_home
        fair_away = closing_total * (1 - HOME_SHARE) + sp_adj_away

        # ── Compute gaps ──
        gap_home = posted_home - fair_home if posted_home is not None else None
        gap_away = posted_away - fair_away if posted_away is not None else None

        # ── Signal flags ──
        home_tt_under = gap_home is not None and gap_home > GAP_THRESHOLD
        away_tt_under = gap_away is not None and gap_away > GAP_THRESHOLD
        home_tt_over = gap_home is not None and gap_home < -GAP_THRESHOLD
        # Do NOT deploy away_tt_over (52-54% in research, below threshold)

        signals.append({
            "date": game_date,
            "event_id": event_id,
            "game_pk": tt.get("game_pk"),
            "home_team": home,
            "away_team": away,
            "home_sp": home_sp_name or None,
            "away_sp": away_sp_name or None,
            "full_game_line": closing_total,
            "posted_home_total": posted_home,
            "posted_away_total": posted_away,
            "fair_home_total": round(fair_home, 3),
            "fair_away_total": round(fair_away, 3),
            "gap_home": round(gap_home, 3) if gap_home is not None else None,
            "gap_away": round(gap_away, 3) if gap_away is not None else None,
            "truncation_adj": round(truncation_adj, 3),
            "sp_quality_adj_home": round(sp_adj_home, 3),
            "sp_quality_adj_away": round(sp_adj_away, 3),
            "home_tt_under_flag": home_tt_under,
            "away_tt_under_flag": away_tt_under,
            "home_tt_over_flag": home_tt_over,
            "n_books": tt.get("n_books", 0),
            "degraded_mode": degraded,
            "degraded_reason": "missing_sp_era_2026" if degraded else None,
            "sp_adj_available_home": sp_adj_available_home,
            "sp_adj_available_away": sp_adj_available_away,
            "actual_home_runs": None,
            "actual_away_runs": None,
            "home_tt_result": None,
            "away_tt_result": None,
            "resolved": False,
            "logged_at": now,
        })

    n_home_under = sum(1 for s in signals if s["home_tt_under_flag"])
    n_away_under = sum(1 for s in signals if s["away_tt_under_flag"])
    n_home_over = sum(1 for s in signals if s["home_tt_over_flag"])
    logger.info(f"Team total signals: {len(signals)} games, "
                f"{n_home_under} H_UNDER, {n_away_under} A_UNDER, {n_home_over} H_OVER")

    return signals


def save_signals(signals):
    """Append signals to shadow log (dedup by date + event_id)."""
    existing = []
    if TT_SHADOW_PATH.exists():
        try:
            existing = json.loads(TT_SHADOW_PATH.read_text())
        except Exception:
            existing = []

    existing_keys = {(r["date"], r["event_id"]) for r in existing}
    new = [s for s in signals if (s["date"], s["event_id"]) not in existing_keys]

    if new:
        existing.extend(new)
        TT_SHADOW_PATH.parent.mkdir(parents=True, exist_ok=True)
        TT_SHADOW_PATH.write_text(json.dumps(existing, indent=2, default=str))
        logger.info(f"Saved {len(new)} new shadow records ({len(existing)} total)")


def grade_signals():
    """Grade unresolved team total shadow entries."""
    if not TT_SHADOW_PATH.exists() or not GT_PATH.exists():
        return

    try:
        data = json.loads(TT_SHADOW_PATH.read_text())
    except Exception:
        return

    gt = pd.read_parquet(GT_PATH)
    # Build lookup by game_pk (primary) and date+team (fallback)
    actuals_by_pk = {}
    for _, row in gt.iterrows():
        pk = int(row["game_pk"]) if pd.notna(row.get("game_pk")) else None
        if pk and pd.notna(row.get("home_score")):
            actuals_by_pk[pk] = {
                "home_score": row["home_score"],
                "away_score": row["away_score"],
            }

    graded = 0
    for entry in data:
        if entry.get("resolved"):
            continue

        gpk = entry.get("game_pk")
        actual = actuals_by_pk.get(int(gpk)) if gpk else None
        if actual is None:
            continue

        home_runs = actual["home_score"]
        away_runs = actual["away_score"]
        entry["actual_home_runs"] = int(home_runs)
        entry["actual_away_runs"] = int(away_runs)

        # Grade home TT
        if entry.get("posted_home_total") is not None:
            if home_runs < entry["posted_home_total"]:
                entry["home_tt_result"] = "UNDER"
            elif home_runs > entry["posted_home_total"]:
                entry["home_tt_result"] = "OVER"
            else:
                entry["home_tt_result"] = "PUSH"

        # Grade away TT
        if entry.get("posted_away_total") is not None:
            if away_runs < entry["posted_away_total"]:
                entry["away_tt_result"] = "UNDER"
            elif away_runs > entry["posted_away_total"]:
                entry["away_tt_result"] = "OVER"
            else:
                entry["away_tt_result"] = "PUSH"

        entry["resolved"] = True
        graded += 1

    if graded > 0:
        TT_SHADOW_PATH.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"Team total grader: resolved {graded} entries")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grade", action="store_true", help="Grade unresolved entries")
    args = parser.parse_args()

    if args.grade:
        grade_signals()
    else:
        signals = compute_signals()
        if signals:
            save_signals(signals)

    # Auto-push
    # Push handled by push_daemon.sh
    # subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
    #                  "Team total shadow signal update"], capture_output=True)


if __name__ == "__main__":
    main()
