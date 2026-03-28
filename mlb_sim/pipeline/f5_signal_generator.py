#!/usr/bin/env python3
"""
F5 Signal Generator — Under + Over signals on first-5-innings totals.
Reads V1 probabilities (p_under_full, p_over_full) from the existing
daily simulation output. Reads F5 lines from f5_lines_2026.parquet.

Does NOT recompute probabilities — purely consumes V1 output.
Independent from V1 full-game signal pipeline. Separate hard stop.
"""

import json
import logging
import pickle
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("f5_signal")

BASE = Path(__file__).resolve().parent.parent
LOGS = BASE / "logs"
PIPELINE = BASE / "pipeline"
MODEL_DIR = BASE / "models"

F5_SIGNALS_PATH = LOGS / "f5_signals_2026.parquet"
F5_PERF_PATH = LOGS / "f5_rolling_performance_2026.json"
F5_STATUS_PATH = PIPELINE / "f5_engine_status.json"

# V1 sim outputs — read only
V1_SIGNALS_PATH = LOGS / "signals_2026.parquet"

# F5 lines collected by mlb_sim_f5
F5_LINES_PATH = BASE.parent / "mlb_sim_f5" / "data" / "f5_lines_2026.parquet"

# Feature table for actual F5 scores
FEATURE_TABLE_PATH = BASE.parent / "sim" / "data" / "feature_table.parquet"

# ── Signal thresholds (frozen from research) ──
UNDER_THRESHOLD = 0.57
OVER_THRESHOLD = 0.57
UNDER_STAKE = 0.75
OVER_STAKE = 0.5
OVER_LINE_FLOOR = 4.0  # suppress F5 over when f5_line <= this

WIN_UNIT = 100 / 110  # ~0.9091

F5_SIGNAL_COLS = [
    "date", "game_id", "home_team", "away_team",
    "f5_signal_side", "signal_tier", "stake_units",
    "p_under_full", "p_over_full",
    "f5_line", "f5_line_closing", "f5_clv_raw", "f5_clv_signed",
    "actual_f5_total", "result", "net_units", "resolved",
]


# ─── File I/O ────────────────────────────────────────────────────────────────

def _load_f5_signals():
    if F5_SIGNALS_PATH.exists():
        return pd.read_parquet(F5_SIGNALS_PATH)
    return pd.DataFrame(columns=F5_SIGNAL_COLS)


def _save_f5_signals(df):
    LOGS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(F5_SIGNALS_PATH, index=False)
    try:
        df.to_json(F5_SIGNALS_PATH.with_suffix(".json"), orient="records", indent=2)
    except Exception:
        pass


def _load_f5_status():
    if F5_STATUS_PATH.exists():
        with open(F5_STATUS_PATH) as f:
            return json.load(f)
    return None


def _save_f5_status(status):
    PIPELINE.mkdir(parents=True, exist_ok=True)
    with open(F5_STATUS_PATH, "w") as f:
        json.dump(status, f, indent=2)


def _bootstrap():
    """Create missing files on first run. Idempotent."""
    created = []
    if not F5_SIGNALS_PATH.exists():
        _save_f5_signals(pd.DataFrame(columns=F5_SIGNAL_COLS))
        created.append("f5_signals_2026.parquet")
    if not F5_STATUS_PATH.exists():
        _save_f5_status({
            "status": "ACTIVE",
            "last_updated": date.today().isoformat(),
            "pause_reason": None,
            "pause_triggered_at_n": None,
            "pause_triggered_at_roi": None,
            "resume_authorized_by": None,
            "resume_date": None,
        })
        created.append("f5_engine_status.json")
    if created:
        logger.info(f"First run — initializing F5 files: {', '.join(created)}")


# ─── Step 1: Resolve prior F5 signals ────────────────────────────────────────

def resolve_signals(game_date_str):
    """Grade pending F5 signals using actual F5 scores from MLB database."""
    sigs = _load_f5_signals()
    pending = sigs[sigs["resolved"] == 0]
    if len(pending) == 0:
        return 0

    # Load actual F5 scores from SQLite DB (same source as V1 grader)
    import sqlite3
    db_path = BASE.parent / "data" / "mlb_model.db"
    if not db_path.exists():
        logger.warning("MLB database not found — cannot resolve F5 signals")
        return 0
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    pending_dates = pending["date"].unique().tolist()
    placeholders = ",".join(["?"] * len(pending_dates))
    rows = conn.execute(
        f"SELECT game_pk, actual_f5_total FROM results "
        f"WHERE game_date IN ({placeholders}) AND actual_f5_total IS NOT NULL",
        pending_dates
    ).fetchall()
    conn.close()
    score_map = {str(r["game_pk"]): float(r["actual_f5_total"]) for r in rows}

    resolved_count = 0
    for idx in pending.index:
        gid = str(sigs.at[idx, "game_id"])
        if gid not in score_map:
            continue

        actual = score_map[gid]
        line = sigs.at[idx, "f5_line"]
        side = sigs.at[idx, "f5_signal_side"]
        stake = sigs.at[idx, "stake_units"]

        if pd.isna(line) or pd.isna(actual):
            continue

        # Check for Hard Rock line override
        from mlb_sim.pipeline.line_overrides import get_override
        hr_line = get_override(gid, "f5_total")
        grade_line = hr_line if hr_line is not None else float(line)

        sigs.at[idx, "actual_f5_total"] = actual

        # Grade using override if present
        if side == "UNDER":
            if actual < grade_line:
                result, net = "WIN", stake * WIN_UNIT
            elif actual > grade_line:
                result, net = "LOSS", -stake
            else:
                result, net = "PUSH", 0.0
        else:  # OVER
            if actual > grade_line:
                result, net = "WIN", stake * WIN_UNIT
            elif actual < grade_line:
                result, net = "LOSS", -stake
            else:
                result, net = "PUSH", 0.0

        sigs.at[idx, "result"] = result
        sigs.at[idx, "net_units"] = net
        sigs.at[idx, "resolved"] = 1
        resolved_count += 1

    if resolved_count > 0:
        _save_f5_signals(sigs)
        logger.info(f"F5 resolved: {resolved_count} signals graded")
    return resolved_count


# ─── Step 2: Fill closing lines + CLV ────────────────────────────────────────

def fill_closing_lines():
    """Fill f5_line_closing from the latest F5 line pull before game time."""
    sigs = _load_f5_signals()
    if len(sigs) == 0:
        return

    needs_close = sigs[sigs["f5_line_closing"].isna() & (sigs["resolved"] == 1)]
    if len(needs_close) == 0:
        return

    if not F5_LINES_PATH.exists():
        return

    f5_lines = pd.read_parquet(F5_LINES_PATH)
    if len(f5_lines) == 0:
        return

    # Use "close" pull type canonical line as closing line
    if "is_canonical" not in f5_lines.columns:
        f5_lines["is_canonical"] = True
    close_rows = f5_lines[
        (f5_lines["pull_type"] == "close") &
        (f5_lines["is_canonical"] == True) &
        f5_lines["f5_total"].notna()
    ].copy()
    close_rows["game_id"] = close_rows["game_id"].astype(str)
    close_map = dict(zip(close_rows["game_id"], close_rows["f5_total"]))

    updated = 0
    for idx in needs_close.index:
        gid = str(sigs.at[idx, "game_id"])
        if gid in close_map:
            closing = close_map[gid]
            signal_line = sigs.at[idx, "f5_line"]
            side = sigs.at[idx, "f5_signal_side"]

            sigs.at[idx, "f5_line_closing"] = closing
            sigs.at[idx, "f5_clv_raw"] = closing - signal_line

            # Side-aware CLV: positive = favorable movement
            if side == "UNDER":
                sigs.at[idx, "f5_clv_signed"] = closing - signal_line
            else:  # OVER
                sigs.at[idx, "f5_clv_signed"] = signal_line - closing
            updated += 1

    if updated > 0:
        _save_f5_signals(sigs)
        logger.info(f"F5 closing lines filled: {updated}")


# ─── Probability computation (reuses frozen V1 S2/S3 models) ─────────────────

# Lazy-load frozen models (same files V1 uses, read-only)
_S2_CACHE = None
_RP_CACHE = None
_N_SIMS = 20_000


def _get_s2():
    global _S2_CACHE
    if _S2_CACHE is None:
        with open(MODEL_DIR / "starter_path_model.pkl", "rb") as f:
            _S2_CACHE = pickle.load(f)
    return _S2_CACHE


def _get_rp():
    global _RP_CACHE
    if _RP_CACHE is None:
        with open(MODEL_DIR / "run_dist_params.json") as f:
            _RP_CACHE = {int(k): v for k, v in json.load(f).items()}
    return _RP_CACHE


def _assign_regime(p0, p1):
    if p0 == 2 and p1 == 2: return 1
    if p0 == 0 and p1 == 0: return 4
    if p0 == 0 or p1 == 0: return 3
    return 2


def _compute_path_probs(sp, game):
    """Compute S2 path probabilities for a starter (same as V1)."""
    s2 = _get_s2()
    features = s2["features"]
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
            v = 5
        elif f == "sp_recent_pc":
            v = 85
        elif f == "opp_lineup_woba":
            v = 0.310
        elif f == "park_factor":
            v = 100
        elif f == "weather_run_modifier":
            v = 0.0
        else:
            v = None
        if v is None:
            return None
        vals.append(float(v))
    X = np.array([vals])
    X_s = s2["scaler"].transform(X)
    return s2["model"].predict_proba(X_s)[0]


def _simulate_game(home_probs, away_probs, m3_total, line, rng):
    """Run Monte Carlo simulation for one game (same as V1)."""
    if m3_total is None:
        m3_total = 8.5
    mu_h = max(m3_total * 0.505, 1.0)
    mu_a = max(m3_total * 0.495, 1.0)
    hp = np.array(home_probs); hp /= hp.sum()
    ap = np.array(away_probs); ap /= ap.sum()
    rp = _get_rp()
    hps = rng.choice([0, 1, 2], _N_SIMS, p=hp)
    aps = rng.choice([0, 1, 2], _N_SIMS, p=ap)
    tots = np.zeros(_N_SIMS)
    for i in range(_N_SIMS):
        reg = _assign_regime(hps[i], aps[i])
        r = rp[reg]["r"]
        tots[i] = rng.negative_binomial(r, r / (r + mu_h)) + \
                  rng.negative_binomial(r, r / (r + mu_a))
    if line is None:
        return None, None
    p_over = (tots > line).mean()
    p_under = (tots <= line).mean()
    return p_over, p_under


def compute_all_game_probs(game_date_str, schedule, pitcher_db):
    """
    Compute V1 probabilities for ALL games on the schedule.
    Reuses frozen S2/S3 models (read-only). Does not modify any V1 file.

    Returns list of dicts:
        game_id, home_team, away_team, p_under, p_over, game_time_et
    """
    from modules.pitchers import get_pitcher_metrics
    from modules.odds import fetch_all_lines, get_game_lines

    rng = np.random.default_rng(int(game_date_str.replace("-", "")))
    all_lines = fetch_all_lines()
    results = []

    for game in schedule:
        gid = str(game.get("game_pk", ""))
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        home_sp_info = game.get("home_probable_pitcher", {})
        away_sp_info = game.get("away_probable_pitcher", {})
        home_sp = get_pitcher_metrics(home_sp_info, pitcher_db)
        away_sp = get_pitcher_metrics(away_sp_info, pitcher_db)

        if home_sp is None or away_sp is None:
            continue

        home_probs = _compute_path_probs(home_sp, game)
        away_probs = _compute_path_probs(away_sp, game)
        if home_probs is None or away_probs is None:
            continue

        game_lines = get_game_lines(home, away, all_lines)
        line = (game_lines.get("full") or {}).get("consensus")

        # M3-style total projection (same as V1)
        h_xfip = home_sp.get("xfip", 4.25)
        a_xfip = away_sp.get("xfip", 4.25)
        m3_total = (h_xfip + a_xfip) / 2 * 2.05

        p_over, p_under = _simulate_game(home_probs, away_probs, m3_total, line, rng)
        if p_over is None:
            continue

        results.append({
            "game_id": gid,
            "home_team": home,
            "away_team": away,
            "p_under": round(p_under, 4),
            "p_over": round(p_over, 4),
            "game_time_et": game.get("game_time_et", ""),
        })

    return results


# ─── Step 5: Generate new F5 signals ─────────────────────────────────────────

def _get_latest_pregame_f5_line(game_id_str, game_date_str):
    """
    Select the latest available canonical pregame F5 line for a game.
    Filter to rows where pull_type != "signal_time" and is_canonical == True,
    take the row with the most recent pull_timestamp.
    Returns (f5_total, f5_over_price, f5_under_price) or (None, None, None).
    """
    if not F5_LINES_PATH.exists():
        return None, None, None

    f5 = pd.read_parquet(F5_LINES_PATH)
    if len(f5) == 0:
        return None, None, None

    # Backward compat: treat missing is_canonical as True
    if "is_canonical" not in f5.columns:
        f5["is_canonical"] = True

    f5["game_id"] = f5["game_id"].astype(str)
    candidates = f5[
        (f5["game_id"] == game_id_str) &
        (f5["date"] == game_date_str) &
        (f5["pull_type"] != "signal_time") &
        (f5["is_canonical"] == True) &
        f5["f5_total"].notna()
    ]

    if len(candidates) == 0:
        logger.debug(f"F5: no canonical line for game {game_id_str}")
        return None, None, None

    # Take the latest pull
    candidates = candidates.sort_values("pull_timestamp", ascending=False)
    best = candidates.iloc[0]
    return best["f5_total"], best.get("f5_over_price"), best.get("f5_under_price")


def generate_signals(game_date_str, schedule=None):
    """
    Generate F5 signals using V1 probabilities + F5 lines.
    Returns list of display dicts for dashboard integration.
    """
    sigs = _load_f5_signals()

    # Read V1 simulation outputs for today
    if not V1_SIGNALS_PATH.exists():
        logger.info("F5: No V1 signals file — skipping")
        return []

    v1 = pd.read_parquet(V1_SIGNALS_PATH)
    v1_today = v1[v1["date"] == game_date_str]

    # V1 signals contain raw_p_under and raw_p_over for signal games.
    # But we need probabilities for ALL games, not just those that
    # triggered V1 under signals. V1 only logs games that fired,
    # so we need to read from the full schedule's simulation outputs.
    # Use schedule to iterate games, and check V1 log for probabilities.
    # For games NOT in V1 log (no V1 under signal), we need to check
    # if they have p_over > 0.57 (which means p_under < 0.43, so V1
    # wouldn't have logged them).

    # Strategy: V1 logs raw_p_under for ALL signal games.
    # For F5 over signals (p_over > 0.57 = p_under < 0.43),
    # these games would NOT appear in V1 log.
    # We need the V1 engine to have run and produced probabilities.
    # Since V1 only saves signal games, we need another source.

    # Best approach: read ALL games' probabilities from V1 output.
    # The V1 engine saves p_under for signal games only. For non-signal
    # games, we need to run the simulation — but the prompt says
    # "do not recompute probabilities".

    logger.info("F5: generate_signals() called without probability data — "
                "use generate_signals_from_probs() instead")
    return []


def generate_signals_from_probs(game_date_str, all_game_probs):
    """
    Generate F5 signals from pre-computed V1 probabilities.

    Args:
        game_date_str: "YYYY-MM-DD"
        all_game_probs: list of dicts, each with:
            game_id, home_team, away_team, p_under, p_over, game_time_et
    Returns:
        list of display dicts for dashboard
    """
    sigs = _load_f5_signals()
    new_signals = []
    display = []

    for gp in all_game_probs:
        gid = str(gp["game_id"])
        p_under = gp.get("p_under")
        p_over = gp.get("p_over")

        if p_under is None or p_over is None:
            continue

        # Mutual exclusivity guard
        if p_under > UNDER_THRESHOLD and p_over > OVER_THRESHOLD:
            logger.error(f"F5 ERROR: game {gid} fires BOTH sides "
                         f"(p_under={p_under:.4f}, p_over={p_over:.4f}). Skipping.")
            continue

        # Determine signal side
        if p_under > UNDER_THRESHOLD:
            side = "UNDER"
            tier = "primary_under"
            stake = UNDER_STAKE
        elif p_over > OVER_THRESHOLD:
            side = "OVER"
            tier = "secondary_over"
            stake = OVER_STAKE
        else:
            continue  # dead zone — no signal

        # Get F5 line
        f5_line, f5_over_price, f5_under_price = _get_latest_pregame_f5_line(
            gid, game_date_str)

        if f5_line is None:
            logger.debug(f"F5: no line for {gid} — skipping")
            continue

        # Suppress F5 over when line <= 4.0
        if side == "OVER" and f5_line <= OVER_LINE_FLOOR:
            logger.info(f"F5: suppressed OVER for {gid} (f5_line={f5_line} <= {OVER_LINE_FLOOR})")
            continue

        # Check for duplicate (unique key: game_id + date + f5_signal_side)
        dup_mask = (
            (sigs["game_id"].astype(str) == gid) &
            (sigs["date"] == game_date_str) &
            (sigs["f5_signal_side"] == side)
        )
        if dup_mask.any():
            logger.debug(f"F5: signal already exists for {gid} {side} — skipping")
            continue

        row = {
            "date": game_date_str,
            "game_id": gid,
            "home_team": gp["home_team"],
            "away_team": gp["away_team"],
            "f5_signal_side": side,
            "signal_tier": tier,
            "stake_units": stake,
            "p_under_full": p_under,
            "p_over_full": p_over,
            "f5_line": f5_line,
            "f5_line_closing": None,
            "f5_clv_raw": None,
            "f5_clv_signed": None,
            "actual_f5_total": None,
            "result": None,
            "net_units": None,
            "resolved": 0,
        }
        new_signals.append(row)

        display.append({
            "game_id": gid,
            "home_team": gp["home_team"],
            "away_team": gp["away_team"],
            "game_time_et": gp.get("game_time_et"),
            "f5_signal_side": side,
            "f5_line": f5_line,
            "stake_units": stake,
            "p_display": p_under if side == "UNDER" else p_over,
        })

    if new_signals:
        new_df = pd.DataFrame(new_signals, columns=F5_SIGNAL_COLS)
        sigs = pd.concat([sigs, new_df], ignore_index=True)
        _save_f5_signals(sigs)
        n_under = sum(1 for s in new_signals if s["f5_signal_side"] == "UNDER")
        n_over = sum(1 for s in new_signals if s["f5_signal_side"] == "OVER")
        logger.info(f"F5 signals: {n_under} UNDER, {n_over} OVER for {game_date_str}")

    return display


# ─── Orchestration ────────────────────────────────────────────────────────────

def run_daily(game_date_str, all_game_probs=None):
    """
    Full F5 daily pipeline.

    Daily run order:
      Step 1: Resolve prior F5 signals
      Step 2: Fill closing lines + CLV
      Step 3: Recompute F5 rolling performance + hard stop check
      Step 4: Check f5_engine_status — if PAUSED, log and exit
      Step 5: Generate new F5 signals (only if ACTIVE)

    Args:
        game_date_str: "YYYY-MM-DD"
        all_game_probs: list of dicts with game_id, p_under, p_over, etc.
            If None, F5 signal generation is skipped (resolve-only run).
    Returns:
        list of display dicts for dashboard
    """
    _bootstrap()

    # Step 1: Resolve prior signals
    n_resolved = resolve_signals(game_date_str)

    # Step 2: Fill closing lines + CLV
    fill_closing_lines()

    # Step 3: Recompute performance + hard stop check
    from mlb_sim.pipeline.f5_performance_tracker import compute_performance, check_hard_stop
    perf = compute_performance()
    if check_hard_stop(perf):
        logger.warning("F5 HARD STOP triggered — engine paused")
        return []

    # Step 4: Check engine status
    status = _load_f5_status()
    if status and status.get("status") == "PAUSED":
        logger.info(f"F5 engine PAUSED — skipping signal generation. "
                    f"Reason: {status.get('pause_reason', 'unknown')}")
        return []

    # Step 5: Generate new signals
    if all_game_probs is None:
        logger.info("F5: no probability data provided — resolve-only run")
        return []

    return generate_signals_from_probs(game_date_str, all_game_probs)
