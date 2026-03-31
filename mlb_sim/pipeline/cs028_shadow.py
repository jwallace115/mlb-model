#!/usr/bin/env python3
"""
CS028 Shadow — Bayesian bullpen blowup probability tracker.

SHADOW ONLY — does not affect live picks, bet sizing, or overlay activation.

Computes per-reliever Bayesian blowup posterior (P(next appearance >= 2 runs))
aggregated at team level. Fires when home team blowup score >= frozen threshold.

Variant: home team only (pre-committed in Batch 4 before 2025 validation).
Frozen threshold: 0.2563 (90th percentile from 2022-2023 training).

Called from run_model.py after CS013 shadow block.
"""

import json
import logging
from datetime import date as _date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("cs028_shadow")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
DATA_PATH = Path(__file__).resolve().parent.parent.parent / "mlb" / "data" / "pitcher_game_logs.parquet"

# Frozen from Batch 4 backtest (2022-2023 training, 90th percentile)
BLOWUP_THRESHOLD = 0.2563
MIN_PRIOR_APPEARANCES = 5
MIN_RELIEVERS_PER_TEAM = 3

# ── Cache (built once per pipeline run) ───────────────────
_cache = {}  # team → {"blowup_score": float, "n_relievers": int}


def _build_cache():
    """
    Build per-team Bayesian blowup score from pitcher_game_logs.

    Per reliever (current season only, starter_flag == 0):
      1. Compute season blowup rate as prior: P(runs >= 2) across all relievers
      2. For each reliever with >= 5 prior appearances this season:
         - Take last 3 appearances
         - Bayesian posterior: (a0 + blowups_last3) / (a0 + b0 + 3)
           where a0 = 2 * prior_rate, b0 = 2 * (1 - prior_rate)
      3. Exclude relievers who appeared in their team's most recent game
      4. Team score = mean posterior across eligible relievers (>= 3 required)
    """
    global _cache
    if _cache:
        return _cache

    try:
        if not DATA_PATH.exists():
            logger.warning("pitcher_game_logs.parquet not found — CS028 shadow disabled")
            return {}

        pl = pd.read_parquet(DATA_PATH)
        rlv = pl[pl["starter_flag"] == 0].sort_values(
            ["player_id", "game_date", "game_pk"]
        ).copy()

        current_year = _date.today().year
        if not (rlv["season"] == current_year).any():
            logger.info(f"  No {current_year} reliever data — CS028 INSUFFICIENT_HISTORY")
            _cache = {"_status": "INSUFFICIENT_HISTORY"}
            return _cache

        # Current season only
        rlv = rlv[rlv["season"] == current_year].copy()

        # Season blowup rate (prior)
        blowup_flags = (rlv["runs_allowed"] >= 2).astype(int)
        season_blowup_rate = blowup_flags.mean()
        if season_blowup_rate == 0:
            season_blowup_rate = 0.14  # fallback if season just started

        # Find each team's most recent game_pk
        team_game_dates = rlv.groupby(["team", "game_pk"])["game_date"].first().reset_index()
        team_game_dates = team_game_dates.sort_values(["team", "game_date"])
        team_latest_gp = team_game_dates.groupby("team")["game_pk"].last().to_dict()

        # Build per-reliever posterior
        records = []
        for (pid, team), grp in rlv.groupby(["player_id", "team"]):
            grp = grp.sort_values("game_date")
            blowup_history = []
            for _, row in grp.iterrows():
                blowup_history.append(1 if row["runs_allowed"] >= 2 else 0)

            n_apps = len(blowup_history)
            if n_apps < MIN_PRIOR_APPEARANCES:
                continue

            # Posterior from last 3 appearances
            last3 = blowup_history[-3:]
            blowups_l3 = sum(last3)
            a0 = 2 * season_blowup_rate
            b0 = 2 * (1 - season_blowup_rate)
            posterior = (a0 + blowups_l3) / (a0 + b0 + 3)

            # Check if appeared in team's most recent game
            latest_gp = team_latest_gp.get(team)
            appeared_in_latest = (grp["game_pk"] == latest_gp).any() if latest_gp else False

            records.append({
                "player_id": pid,
                "team": team,
                "posterior": posterior,
                "n_appearances": n_apps,
                "appeared_in_latest": appeared_in_latest,
            })

        if not records:
            logger.info("  No relievers with 5+ appearances — CS028 INSUFFICIENT_HISTORY")
            _cache = {"_status": "INSUFFICIENT_HISTORY"}
            return _cache

        rdf = pd.DataFrame(records)
        # Exclude those who appeared in most recent game (assume unavailable)
        available = rdf[~rdf["appeared_in_latest"]]

        # Team-level aggregation
        team_agg = available.groupby("team").agg(
            n_relievers=("posterior", "count"),
            blowup_score=("posterior", "mean"),
        ).reset_index()

        _cache = {}
        for _, row in team_agg.iterrows():
            _cache[row["team"]] = {
                "blowup_score": round(float(row["blowup_score"]), 6),
                "n_relievers": int(row["n_relievers"]),
            }

        n_flagged = sum(1 for v in _cache.values()
                        if v["n_relievers"] >= MIN_RELIEVERS_PER_TEAM
                        and v["blowup_score"] >= BLOWUP_THRESHOLD)
        logger.info(
            f"CS028 cache built: {len(_cache)} teams, "
            f"{n_flagged} with blowup score >= {BLOWUP_THRESHOLD}"
        )
        return _cache

    except Exception as e:
        logger.warning(f"Failed to build CS028 cache: {e}")
        return {}


def compute_cs028(home_team, away_team):
    """
    Compute CS028 for a game. Returns dict with home blowup score and signal flag.
    """
    if not _cache:
        _build_cache()

    if _cache.get("_status") == "INSUFFICIENT_HISTORY":
        return {
            "home_blowup_score": None,
            "signal_fires": False,
            "relievers_scored": 0,
            "status": "INSUFFICIENT_HISTORY",
        }

    h = _cache.get(home_team, {})
    score = h.get("blowup_score")
    n_rlv = h.get("n_relievers", 0)

    if n_rlv < MIN_RELIEVERS_PER_TEAM:
        return {
            "home_blowup_score": score,
            "signal_fires": False,
            "relievers_scored": n_rlv,
            "status": f"INSUFFICIENT_RELIEVERS ({n_rlv} < {MIN_RELIEVERS_PER_TEAM})",
        }

    fires = score is not None and score >= BLOWUP_THRESHOLD
    return {
        "home_blowup_score": score,
        "signal_fires": bool(fires),
        "relievers_scored": n_rlv,
        "status": "OK",
    }


def _read_cs013_flag(game_id, season):
    """Read CS013 flag for same game_id from cs013_shadow log."""
    try:
        cs013_log = LOG_DIR / f"cs013_shadow_{season}.json"
        if not cs013_log.exists():
            return False
        data = json.loads(cs013_log.read_text())
        for rec in data:
            if rec.get("game_id") == game_id:
                return bool(rec.get("cs013_flag"))
        return False
    except Exception:
        return False


def log_cs028_record(game_id, date, home_team, away_team,
                     cs028_result, closing_total=None):
    """
    Append a CS028 shadow record to JSON log.
    Deduplicates by game_id.
    """
    season = int(str(date)[:4])
    log_path = LOG_DIR / f"cs028_shadow_{season}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cs013_also = _read_cs013_flag(game_id, season)

    record = {
        "game_id": game_id,
        "game_date": str(date),
        "home_team": home_team,
        "away_team": away_team,
        "home_blowup_score": cs028_result.get("home_blowup_score"),
        "signal_fires": cs028_result.get("signal_fires", False),
        "threshold_used": BLOWUP_THRESHOLD,
        "relievers_scored": cs028_result.get("relievers_scored", 0),
        "cs013_also_active": cs013_also,
        "actual_over_under": None,
        "closing_total": closing_total,
        "clv": None,
        "logged_at": datetime.utcnow().isoformat(),
    }

    existing = []
    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text())
        except Exception:
            existing = []

    # Deduplicate
    existing = [r for r in existing if r.get("game_id") != game_id]
    existing.append(record)

    log_path.write_text(json.dumps(existing, indent=2, default=str))

    if cs028_result.get("signal_fires"):
        logger.info(
            f"  CS028 FIRES: {home_team} home blowup={cs028_result['home_blowup_score']:.4f} "
            f">= {BLOWUP_THRESHOLD} (CS013 also={'yes' if cs013_also else 'no'})"
        )
    else:
        logger.debug(f"  CS028 logged: {home_team} score={cs028_result.get('home_blowup_score')}")
