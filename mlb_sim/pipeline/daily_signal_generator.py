#!/usr/bin/env python3
"""
MLB Sim Engine — Daily Signal Generator
========================================
Runs frozen S1→S2→S3 engine, generates UNDER signals for today's games.

DAILY RUN ORDER (enforced strictly):
  Step 1: Resolve prior signals
  Step 2: Recompute rolling performance
  Step 3: Hard stop check
  Step 4: Check engine status — if PAUSED, skip signal generation
  Step 5: Generate new signals (only if ACTIVE)

Over signals: computed and stored internally, NEVER surfaced.
dual_high_csw: logged on every signal, never a standalone trigger.
"""

import json
import logging
import os
import pickle
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger("mlb_sim")

BASE = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE.parent
SIGNALS_PATH = BASE / "logs" / "signals_2026.parquet"
STATUS_PATH = BASE / "pipeline" / "engine_status.json"
MODEL_DIR = BASE / "models"

N_SIMS = 20_000

# Frozen thresholds from S2/S4
with open(MODEL_DIR / "calibration_params.json") as _f:
    _CAL = json.load(_f)
CSW_Q75 = _CAL["csw_q75"]

# Signal thresholds — frozen from S5/S6 validation
UNDER_THRESHOLD_LOW = 0.57   # 0.5u signals
UNDER_THRESHOLD_HIGH = 0.60  # 1.0u signals

# Frozen models
with open(MODEL_DIR / "starter_path_model.pkl", "rb") as _f:
    _S2 = pickle.load(_f)
with open(MODEL_DIR / "run_dist_params.json") as _f:
    _RP = {int(k): v for k, v in json.load(_f).items()}

SIGNAL_COLS = [
    "date", "game_id", "home_team", "away_team", "signal_side",
    "threshold_bucket", "stake_units", "raw_p_under", "raw_p_over",
    "dual_high_csw", "line_at_signal_time", "closing_line", "clv",
    "actual_total", "result", "net_units", "resolved",
    # Overlay fields (S12 + P09 + ST02)
    "s12_overlay_active", "s12_value",
    "p09_overlay_active", "p09_value", "p09_data_available",
    "st02_overlay_active", "st02_value", "st02_favorable_zone", "st02_blocked_by_p09",
    "combined_overlay_tier", "base_stake",
]


def _load_signals():
    if SIGNALS_PATH.exists():
        return pd.read_parquet(SIGNALS_PATH)
    return pd.DataFrame(columns=SIGNAL_COLS)


def _save_signals(df):
    SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SIGNALS_PATH, index=False)
    # Also write JSON for Streamlit Cloud (parquet not committed to git)
    try:
        json_path = SIGNALS_PATH.with_suffix(".json")
        export_cols = ["date", "game_id", "home_team", "away_team", "signal_side",
                       "stake_units", "raw_p_under", "raw_p_over",
                       "line_at_signal_time", "result", "net_units", "resolved"]
        # Include overlay fields if present
        for c in ["s12_overlay_active", "s12_value", "base_stake",
                   "p09_overlay_active", "p09_value", "p09_data_available",
                   "combined_overlay_tier", "final_stake"]:
            if c in df.columns:
                export_cols.append(c)
        avail = [c for c in export_cols if c in df.columns]
        df[avail].to_json(json_path, orient="records", indent=2)
    except Exception:
        pass


def _load_status():
    if STATUS_PATH.exists():
        with open(STATUS_PATH) as f:
            return json.load(f)
    return {"status": "ACTIVE"}


def _assign_regime(p0, p1):
    if p0 == 2 and p1 == 2: return 1
    if p0 == 0 and p1 == 0: return 4
    if p0 == 0 or p1 == 0: return 3
    return 2


# ── STEP 1: Resolve prior signals ───────────────────────────────────────

def resolve_signals(game_date_str):
    """Fill actual_total, result, net_units for completed games."""
    signals = _load_signals()
    if signals.empty:
        return signals

    pending = signals[signals["resolved"] == 0]
    if pending.empty:
        return signals

    # Load results from MLB database
    import sqlite3
    db_path = PROJECT_ROOT / "data" / "mlb_model.db"
    if not db_path.exists():
        logger.warning("MLB database not found — cannot resolve signals")
        return signals

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Get all results for pending dates
    pending_dates = pending["date"].unique().tolist()
    placeholders = ",".join(["?"] * len(pending_dates))
    rows = conn.execute(
        f"SELECT game_pk, actual_total, line_full FROM results "
        f"WHERE game_date IN ({placeholders}) AND actual_total IS NOT NULL",
        pending_dates
    ).fetchall()
    conn.close()

    result_map = {str(r["game_pk"]): dict(r) for r in rows}

    updated = False
    for idx, sig in signals.iterrows():
        if sig["resolved"] != 0:
            continue
        gid = str(sig["game_id"])
        actual = result_map.get(gid)
        if not actual:
            continue

        total = float(actual["actual_total"])
        closing = float(actual["line_full"]) if actual.get("line_full") else None
        line_sig = float(sig["line_at_signal_time"]) if pd.notna(sig["line_at_signal_time"]) else None
        stake = float(sig["stake_units"])

        # Check for Hard Rock line override
        from mlb_sim.pipeline.line_overrides import get_override
        hr_line = get_override(gid, "full_game")

        # Grade using override if present, else closing_line
        grade_line = hr_line if hr_line is not None else (
            closing if closing is not None else (line_sig if line_sig is not None else None)
        )
        if grade_line is None:
            continue

        if total < grade_line:
            result = "WIN"
            net = stake * (100 / 110)
        elif total > grade_line:
            result = "LOSS"
            net = -stake
        else:
            result = "PUSH"
            net = 0.0

        # CLV: for unders, positive = line moved up (good)
        clv = (closing - line_sig) if closing is not None and line_sig is not None else None

        signals.at[idx, "actual_total"] = total
        signals.at[idx, "closing_line"] = closing
        signals.at[idx, "clv"] = clv
        signals.at[idx, "result"] = result
        signals.at[idx, "net_units"] = round(net, 4)
        signals.at[idx, "resolved"] = 1
        updated = True
        logger.info(f"  Resolved: {sig['away_team']}@{sig['home_team']} → {result} ({net:+.2f}u)")

    if updated:
        _save_signals(signals)
    return signals


# ── STEP 5: Generate signals ────────────────────────────────────────────

def generate_signals(game_date_str, schedule, pitcher_db):
    """
    Generate UNDER signals for today's games using frozen S1→S2→S3 engine.

    Args:
        game_date_str: "YYYY-MM-DD"
        schedule: list of game dicts from modules/schedule.py
        pitcher_db: pitcher database from modules/pitchers.py

    Returns: list of signal dicts for display
    """
    signals = _load_signals()
    new_signals = []
    display_signals = []

    rng = np.random.default_rng(int(game_date_str.replace("-", "")))

    for game in schedule:
        gid = str(game.get("game_pk", ""))
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        # Duplicate protection
        if not signals.empty and ((signals["game_id"].astype(str) == gid) & (signals["date"] == game_date_str)).any():
            logger.info(f"  Duplicate: {away}@{home} already logged — skipping")
            continue

        # Get pitcher CSW from pitcher_db
        home_sp_info = game.get("home_probable_pitcher", {})
        away_sp_info = game.get("away_probable_pitcher", {})

        home_sp = _lookup_pitcher(home_sp_info, pitcher_db)
        away_sp = _lookup_pitcher(away_sp_info, pitcher_db)

        if home_sp is None or away_sp is None:
            continue

        # Build S2 feature vector for both starters
        home_probs = _compute_path_probs(home_sp, game)
        away_probs = _compute_path_probs(away_sp, game)

        if home_probs is None or away_probs is None:
            continue

        # Get market line (evaluation only — never a model input)
        from modules.odds import fetch_all_lines, get_game_lines
        all_lines = fetch_all_lines() if not hasattr(generate_signals, "_lines_cache") else generate_signals._lines_cache
        generate_signals._lines_cache = all_lines
        game_lines = get_game_lines(home, away, all_lines)
        line = (game_lines.get("full") or {}).get("consensus")

        # Get M3 projection for mean baseline
        m3_total = _get_m3_total(game, pitcher_db)

        # Run Monte Carlo simulation
        p_over, p_under = _simulate_game(home_probs, away_probs, m3_total, line, rng)

        if p_over is None:
            continue

        # Check CSW flags
        home_csw = home_sp.get("csw_pct")
        away_csw = away_sp.get("csw_pct")
        dual_csw = int(
            home_csw is not None and away_csw is not None
            and home_csw >= CSW_Q75 and away_csw >= CSW_Q75
        )

        # Determine signal
        if p_under > UNDER_THRESHOLD_HIGH:
            bucket = ">0.60"
            stake = 1.0
        elif p_under > UNDER_THRESHOLD_LOW:
            bucket = "0.57-0.60"
            stake = 0.5
        else:
            # No signal — still log over prob internally but don't surface
            continue

        sig = {
            "date": game_date_str,
            "game_id": gid,
            "home_team": home,
            "away_team": away,
            "signal_side": "UNDER",
            "threshold_bucket": bucket,
            "stake_units": stake,
            "raw_p_under": round(p_under, 4),
            "raw_p_over": round(p_over, 4),
            "dual_high_csw": dual_csw,
            "line_at_signal_time": line,
            "closing_line": None,
            "clv": None,
            "actual_total": None,
            "result": None,
            "net_units": None,
            "resolved": 0,
        }

        # S12 overlay: compute score
        s12_active = False
        try:
            from mlb_sim.pipeline.s12_overlay import compute_s12, evaluate_overlay
            s12_val = compute_s12(home_sp, away_sp)
            s12_result = evaluate_overlay(s12_val, sig["stake_units"])
            sig.update(s12_result)
            s12_active = s12_result.get("s12_overlay_active") == 1
        except Exception as e:
            logger.debug(f"S12 overlay failed (non-fatal): {e}")
            sig.setdefault("s12_overlay_active", 0)

        # P09 overlay: contact suppression × pitcher park
        p09_active = False
        try:
            from mlb_sim.pipeline.p09_overlay import compute_p09, evaluate_p09_overlay, apply_combined_overlay
            # Look up hard-hit rates from Statcast rolling data
            if not hasattr(generate_signals, "_hh_cache"):
                _sc_path = BASE.parent / "research" / "statcast_enrichment" / "pitcher_statcast_per_start_starters_only.parquet"
                if _sc_path.exists():
                    import pandas as _pd_sc
                    _sc = _pd_sc.read_parquet(_sc_path).sort_values(["pitcher_id", "game_date"])
                    _sc["hh_r5"] = _sc.groupby("pitcher_id")["hard_hit_rate"].transform(
                        lambda x: x.shift(1).rolling(5, min_periods=3).mean())
                    # Latest per pitcher
                    _latest = _sc.dropna(subset=["hh_r5"]).groupby("pitcher_id").last()[["hh_r5"]]
                    generate_signals._hh_cache = _latest["hh_r5"].to_dict()
                else:
                    generate_signals._hh_cache = {}

            _hh = generate_signals._hh_cache
            h_hh = _hh.get(int(home_sp_info.get("id", 0)))
            a_hh = _hh.get(int(away_sp_info.get("id", 0)))

            from config import STADIUMS
            park_rf = STADIUMS.get(home, {}).get("park_factor", 100)

            p09_val = compute_p09(h_hh, a_hh, park_rf)
            p09_result = evaluate_p09_overlay(p09_val)
            sig.update(p09_result)
            p09_active = p09_result.get("p09_overlay_active") == 1
        except Exception as e:
            logger.debug(f"P09 overlay failed (non-fatal): {e}")
            sig.setdefault("p09_overlay_active", 0)
            sig.setdefault("p09_data_available", 0)

        # ST02 overlay: road-trip fatigue (blocked by P09)
        st02_active = False
        try:
            from mlb_sim.pipeline.st02_overlay import compute_st02, evaluate_st02_overlay
            st02_val = compute_st02(game.get("game_pk"))
            st02_result = evaluate_st02_overlay(st02_val, p09_active)
            sig.update(st02_result)
            st02_active = st02_result.get("st02_overlay_active") == 1
        except Exception as e:
            logger.debug(f"ST02 overlay failed (non-fatal): {e}")
            sig.setdefault("st02_overlay_active", 0)

        # Combined stake: apply S12 + P09 overlays (ST02 is tag-only, no sizing)
        try:
            from mlb_sim.pipeline.p09_overlay import apply_combined_overlay
            base_stake = stake  # original V1 stake before any overlay
            final_stake, tier = apply_combined_overlay(base_stake, s12_active, p09_active)
            sig["base_stake"] = base_stake
            sig["stake_units"] = final_stake
            sig["combined_overlay_tier"] = tier
            sig["final_stake"] = final_stake
        except Exception:
            sig.setdefault("combined_overlay_tier", "NONE")
            sig.setdefault("final_stake", sig["stake_units"])

        new_signals.append(sig)
        display_signals.append({
            **sig,
            "game_time": game.get("game_time_et", ""),
            "home_sp_name": home_sp_info.get("name", "TBD"),
            "away_sp_name": away_sp_info.get("name", "TBD"),
        })

        tags = []
        if s12_active: tags.append("S12")
        if p09_active: tags.append("P09")
        if st02_active: tags.append("ST02")
        tag_str = f" [{'+'.join(tags)}]" if tags else ""
        logger.info(f"  🔵 UNDER {sig['stake_units']}u: {away}@{home} line={line} p_under={p_under:.1%} "
                     f"{'[dual_high_csw]' if dual_csw else ''}{tag_str}")

    # Append new signals
    if new_signals:
        new_df = pd.DataFrame(new_signals, columns=SIGNAL_COLS)
        combined = pd.concat([signals, new_df], ignore_index=True)
        _save_signals(combined)
        logger.info(f"  Logged {len(new_signals)} new signals")

        # Backfill timing lines from daily snapshots at signal creation
        try:
            from mlb_sim.pipeline.timing_line_updater import backfill_from_snapshots
            for sig in new_signals:
                backfill_from_snapshots(game_date_str, sig["game_id"],
                                        sig["home_team"], sig["away_team"])
        except Exception as e:
            logger.debug(f"Timing backfill failed (non-fatal): {e}")

    return display_signals


def _lookup_pitcher(pitcher_info, pitcher_db):
    """Look up pitcher metrics from the database."""
    from modules.pitchers import get_pitcher_metrics
    return get_pitcher_metrics(pitcher_info, pitcher_db)


def _compute_path_probs(sp, game):
    """Compute S2 path probabilities for a starter."""
    features = _S2["features"]
    vals = []
    for f in features:
        if f == "sp_csw_pct":
            v = sp.get("csw_pct")
        elif f == "sp_whiff_pct":
            v = sp.get("whiff_pct")
        elif f == "sp_fstrike_pct":
            v = sp.get("f_strike_pct")
        elif f == "sp_xfip":
            v = sp.get("xfip")
        elif f == "days_rest":
            v = 5  # default if not available
        elif f == "sp_recent_pc":
            v = 85  # default
        elif f == "opp_lineup_woba":
            v = 0.310  # league average default
        elif f == "park_factor":
            v = 100  # neutral
        elif f == "weather_run_modifier":
            v = 0.0  # neutral
        else:
            v = None
        if v is None:
            return None
        vals.append(float(v))

    X = np.array([vals])
    X_s = _S2["scaler"].transform(X)
    probs = _S2["model"].predict_proba(X_s)[0]
    return probs


def _get_m3_total(game, pitcher_db):
    """Get M3-style total projection. Simplified: use xFIP-based estimate."""
    home_sp = _lookup_pitcher(game.get("home_probable_pitcher", {}), pitcher_db)
    away_sp = _lookup_pitcher(game.get("away_probable_pitcher", {}), pitcher_db)
    # Simple xFIP-based total estimate
    h_xfip = home_sp.get("xfip", 4.25)
    a_xfip = away_sp.get("xfip", 4.25)
    return (h_xfip + a_xfip) / 2 * 2.05  # rough runs-per-game estimate


def _simulate_game(home_probs, away_probs, m3_total, line, rng):
    """Run Monte Carlo simulation for one game."""
    if m3_total is None:
        m3_total = 8.5

    mu_h = max(m3_total * 0.505, 1.0)
    mu_a = max(m3_total * 0.495, 1.0)

    hp = np.array(home_probs); hp /= hp.sum()
    ap = np.array(away_probs); ap /= ap.sum()

    hps = rng.choice([0, 1, 2], N_SIMS, p=hp)
    aps = rng.choice([0, 1, 2], N_SIMS, p=ap)
    tots = np.zeros(N_SIMS)

    for i in range(N_SIMS):
        reg = _assign_regime(hps[i], aps[i])
        r = _RP[reg]["r"]
        tots[i] = rng.negative_binomial(r, r / (r + mu_h)) + rng.negative_binomial(r, r / (r + mu_a))

    if line is None:
        return None, None

    p_over = (tots > line).mean()
    p_under = (tots <= line).mean()
    return p_over, p_under


# ── MAIN DAILY RUN ──────────────────────────────────────────────────────

def run_daily(game_date_str=None, schedule=None, pitcher_db=None):
    """
    Full daily pipeline. Call from run_model.py or standalone.
    Returns list of display signals (for dashboard).
    """
    if game_date_str is None:
        game_date_str = date.today().isoformat()

    logger.info(f"MLB Sim Engine — daily run for {game_date_str}")

    # Step 1: Resolve prior signals + compute timing CLV
    logger.info("Step 1: Resolving prior signals...")
    resolve_signals(game_date_str)
    try:
        from mlb_sim.pipeline.timing_line_updater import compute_clv_timing
        compute_clv_timing()
    except Exception as e:
        logger.debug(f"Timing CLV compute failed (non-fatal): {e}")

    # Step 2: Recompute rolling performance + timing analysis
    logger.info("Step 2: Recomputing performance...")
    from mlb_sim.pipeline.performance_tracker import compute_performance, check_hard_stop
    perf = compute_performance()
    try:
        from mlb_sim.pipeline.s12_overlay_tracker import compute_s12_performance
        compute_s12_performance()
    except Exception as e:
        logger.debug(f"S12 overlay tracker failed (non-fatal): {e}")
    try:
        from mlb_sim.pipeline.timing_tracker import compute_timing_analysis
        compute_timing_analysis()
    except Exception as e:
        logger.debug(f"Timing analysis failed (non-fatal): {e}")

    # Step 3: Hard stop check
    logger.info("Step 3: Hard stop check...")
    if check_hard_stop(perf):
        logger.warning("ENGINE PAUSED — hard stop triggered. No signals generated.")
        return []

    # Step 4: Check engine status
    status = _load_status()
    if status.get("status") != "ACTIVE":
        logger.warning(f"Engine status: {status.get('status')} — skipping signal generation")
        return []

    # Step 5: Generate new signals
    logger.info("Step 5: Generating signals...")
    if schedule is None or pitcher_db is None:
        logger.warning("No schedule or pitcher_db provided — cannot generate signals")
        return []

    signals = generate_signals(game_date_str, schedule, pitcher_db)
    logger.info(f"Daily run complete: {len(signals)} signals generated")
    return signals
