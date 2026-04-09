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

    # Load game info for starter matching
    # Try to get today's starters from pitcher_game_logs or game schedule
    pgl = pd.read_parquet(PGL_PATH) if PGL_PATH.exists() else pd.DataFrame()
    sp_today = pgl[(pgl["starter_flag"] == 1) & (pgl["game_date"] == game_date)] if not pgl.empty else pd.DataFrame()

    # Also try signals file for starter info
    signals_path = PROJECT_ROOT / "mlb_sim" / "logs" / "signals_2026.json"
    game_starters = {}
    if signals_path.exists():
        try:
            sigs = json.loads(signals_path.read_text())
            for s in sigs:
                if s.get("date") == game_date:
                    gid = s.get("game_id")
                    if gid:
                        game_starters[str(gid)] = {
                            "home_sp": s.get("home_sp_name", ""),
                            "away_sp": s.get("away_sp_name", ""),
                            "home_sp_id": s.get("home_sp_id"),
                            "away_sp_id": s.get("away_sp_id"),
                            "closing_total": s.get("line_at_signal_time"),
                        }
        except Exception:
            pass

    # Also get closing totals from line snapshots
    snap_path = PROJECT_ROOT / "mlb_sim" / "data" / "line_snapshots_2026.json"
    closing_totals = {}
    if snap_path.exists():
        try:
            snaps = json.loads(snap_path.read_text())
            for s in snaps:
                if s.get("game_date") == game_date and s.get("snapshot_label") in ("CLOSING", "5PM", "OPEN"):
                    gid = s.get("game_id")
                    if gid and s.get("total_line"):
                        closing_totals[gid] = float(s["total_line"])
        except Exception:
            pass

    signals = []
    for tt in tt_records:
        home = tt.get("home_team", "")
        away = tt.get("away_team", "")
        posted_home = tt.get("home_total_line")
        posted_away = tt.get("away_total_line")
        event_id = tt.get("event_id", "")

        if posted_home is None and posted_away is None:
            continue

        # Find closing total — try line snapshots or derive from team totals
        closing_total = None
        for gid, ct in closing_totals.items():
            # Match by looking for the same teams in snapshots
            # This is imperfect but workable
            pass

        # Derive from team totals as fallback
        if closing_total is None and posted_home is not None and posted_away is not None:
            closing_total = posted_home + posted_away

        if closing_total is None:
            continue

        # Find starter quality
        home_sp_era = LEAGUE_AVG_ERA
        away_sp_era = LEAGUE_AVG_ERA
        home_sp_name = ""
        away_sp_name = ""

        # Try to match starters
        for gid, info in game_starters.items():
            if info.get("home_sp") and info.get("away_sp"):
                # Simple team name matching (Odds API uses full names, signals use abbreviations)
                pass

        # Use pitcher_game_logs for ERA
        # Match by team abbreviation from today's starters
        if not sp_today.empty:
            for _, row in sp_today.iterrows():
                pid = row["player_id"]
                team = row.get("team", "")
                era = era_map.get(pid)
                if era is not None:
                    # Check if this team is home or away in this TT record
                    if team and (team in home or home in team):
                        home_sp_era = era
                        home_sp_name = row.get("player_name", "")
                    elif team and (team in away or away in team):
                        away_sp_era = era
                        away_sp_name = row.get("player_name", "")

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
    # Build lookup: try matching by team names + date
    actuals = {}
    for _, row in gt.iterrows():
        key = (str(row["date"])[:10] if "date" in gt.columns else "",
               row.get("home_team", ""), row.get("away_team", ""))
        actuals[key] = {
            "home_score": row.get("home_score"),
            "away_score": row.get("away_score"),
        }

    graded = 0
    for entry in data:
        if entry.get("resolved"):
            continue

        # Try to find actual scores
        d = entry.get("date", "")
        # Odds API uses full team names, game_table uses abbreviations
        # This matching is imperfect — will need team name normalization
        actual = None
        for (gd, ht, at), scores in actuals.items():
            if gd == d and scores.get("home_score") is not None:
                # Check if team names overlap
                if (ht in entry.get("home_team", "") or
                    entry.get("home_team", "") in ht):
                    actual = scores
                    break

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
    subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
                     "Team total shadow signal update"], capture_output=True)


if __name__ == "__main__":
    main()
