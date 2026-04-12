#!/usr/bin/env python3
"""
Shadow signal tracker for ST02, ADJ_CONTACT, ADJ_HH, adj_k_rate_last3.

SHADOW ONLY — does not affect live picks, bet sizing, or overlay activation.

Computes each signal for each game and logs to shadow JSON file.
Called from run_model.py after V1 projections are available.
Follows the exact same pattern as combined_short_exit_shadow.py.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger("shadow_signals")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

# ── Caches (built once per pipeline run) ──────────────────────────────
_schedule_cache = {}   # game_pk → schedule context
_adj_form_cache = {}   # pitcher_id → {adj_k_rate_last3, adj_contact_rate_last3, adj_hard_hit_last3, adj_bb_rate_last3, adj_run_suppression_last3}


# ======================================================================
# ST02 — road_trip_game_6plus
# ======================================================================

def _build_schedule_lookup():
    """
    Build schedule context from MLB Stats API schedule endpoint.
    Returns dict: game_pk → {road_trip_game_num_away: int or None}.

    Uses the same statsapi as modules/schedule.py.
    Computes road_trip_game_num for the away team by counting consecutive
    away games backwards from the current date.
    """
    global _schedule_cache
    if _schedule_cache:
        return _schedule_cache
    try:
        import pandas as pd
        # Use game_table from sim/data — has home/away team + date for all games
        gt_path = Path(__file__).resolve().parent.parent.parent / "sim" / "data" / "game_table.parquet"
        if not gt_path.exists():
            logger.warning("game_table.parquet not found — ST02 unavailable")
            return {}

        gt = pd.read_parquet(gt_path, columns=["game_pk", "date", "season", "home_team", "away_team"])
        gt["date"] = pd.to_datetime(gt["date"])
        gt = gt.sort_values("date")

        # For each team, compute consecutive away game count up to each game
        # A "road trip" = consecutive games where team is away
        team_games = []
        for _, row in gt.iterrows():
            team_games.append({"game_pk": row["game_pk"], "date": row["date"],
                               "season": row["season"],
                               "team": row["away_team"], "is_away": True})
            team_games.append({"game_pk": row["game_pk"], "date": row["date"],
                               "season": row["season"],
                               "team": row["home_team"], "is_away": False})

        tg = pd.DataFrame(team_games).sort_values(["team", "date", "game_pk"])

        # Count consecutive away games per team
        def count_road_trip(grp):
            grp = grp.sort_values(["date", "game_pk"])
            streak = 0
            out = []
            for _, r in grp.iterrows():
                if r["is_away"]:
                    streak += 1
                else:
                    streak = 0
                out.append(streak)
            grp["road_trip_game_num"] = out
            return grp

        # Compute road trip streak per team, resetting at season boundaries
        tg = tg.sort_values(["team", "date", "game_pk"]).reset_index(drop=True)
        streak = np.zeros(len(tg), dtype=int)
        prev_team = None
        prev_season = None
        s = 0
        for i, row in enumerate(tg.itertuples()):
            if row.team != prev_team or row.season != prev_season:
                s = 0
                prev_team = row.team
                prev_season = row.season
            if row.is_away:
                s += 1
            else:
                s = 0
            streak[i] = s
        tg["road_trip_game_num"] = streak

        # Keep only away entries (road trip count for the away team)
        away_trips = tg[tg["is_away"]][["game_pk", "team", "road_trip_game_num"]]
        _schedule_cache = {}
        for _, row in away_trips.iterrows():
            _schedule_cache[int(row["game_pk"])] = {
                "road_trip_game_num_away": int(row["road_trip_game_num"]),
            }
        logger.info(f"Schedule lookup built: {len(_schedule_cache)} games")
        return _schedule_cache
    except Exception as e:
        logger.warning(f"Failed to build schedule lookup: {e}")
        return {}


def get_road_trip_game_num(game_pk):
    """Get the away team's road trip game number for this game. Returns int or None."""
    if not _schedule_cache:
        _build_schedule_lookup()
    entry = _schedule_cache.get(int(game_pk) if game_pk else -1)
    if entry:
        return entry.get("road_trip_game_num_away")
    return None


def compute_st02(game_pk):
    """
    ST02: road_trip_game_6plus.
    Returns dict with signal_value (int: road trip game #) and favorable_zone_flag (bool).
    """
    rtgn = get_road_trip_game_num(game_pk)
    if rtgn is None:
        return {"signal_value": None, "favorable_zone_flag": False}
    return {
        "signal_value": rtgn,
        "favorable_zone_flag": rtgn >= 6,
    }


# ======================================================================
# ADJ_CONTACT, ADJ_HH, adj_k_rate_last3
# ======================================================================

def _build_adj_form_lookup():
    """
    Build pitcher opponent-adjusted recent form lookup.
    Uses pitcher_recent_adjusted_features.parquet + pitcher_start_adjusted.parquet.
    Returns dict: pitcher_id → {adj_k_rate_last3, adj_contact_rate_last3, adj_hard_hit_last3}.
    """
    global _adj_form_cache
    if _adj_form_cache:
        return _adj_form_cache
    try:
        import pandas as pd
        base = Path(__file__).resolve().parent.parent.parent / "research" / "opponent_adjusted_engine_v2"
        form_path = base / "pitcher_recent_adjusted_features.parquet"
        if not form_path.exists():
            logger.warning("pitcher_recent_adjusted_features.parquet not found — adj signals unavailable")
            return {}

        form = pd.read_parquet(form_path)
        form = form.sort_values(["pitcher_id", "game_date"]).dropna(subset=["adj_k_rate_last3"])

        # Keep latest per pitcher (most recent start with valid rolling features)
        latest = form.groupby("pitcher_id").last().reset_index()
        _adj_form_cache = {}
        for _, row in latest.iterrows():
            pid = int(row["pitcher_id"])
            _adj_form_cache[pid] = {
                "adj_k_rate_last3": _safe_round(row.get("adj_k_rate_last3")),
                "adj_contact_rate_last3": _safe_round(row.get("adj_contact_rate_last3")),
                "adj_hard_hit_last3": _safe_round(row.get("adj_hard_hit_last3")),
                "adj_bb_rate_last3": _safe_round(row.get("adj_bb_rate_last3")),
                "adj_run_suppression_last3": _safe_round(row.get("adj_run_suppression_last3")),
            }
        logger.info(f"Adj form lookup built: {len(_adj_form_cache)} pitchers")
        return _adj_form_cache
    except Exception as e:
        logger.warning(f"Failed to build adj form lookup: {e}")
        return {}


def _safe_round(val, decimals=6):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return round(float(val), decimals)


def get_pitcher_adj_form(pitcher_id):
    """Look up a pitcher's recent adjusted form metrics. Returns dict or None."""
    if not _adj_form_cache:
        _build_adj_form_lookup()
    if pitcher_id is None:
        return None
    return _adj_form_cache.get(int(pitcher_id))


def compute_adj_signals(home_pitcher_id, away_pitcher_id):
    """
    Compute ADJ_CONTACT, ADJ_HH, adj_k_rate_last3 at the game level.
    Uses the average of home and away pitcher adjusted metrics.

    Returns dict with signal values and favorable zone flags.
    Higher adj values = more suppression = UNDER leaning.
    """
    home_form = get_pitcher_adj_form(home_pitcher_id) or {}
    away_form = get_pitcher_adj_form(away_pitcher_id) or {}

    results = {}
    for metric in ["adj_k_rate_last3", "adj_contact_rate_last3", "adj_hard_hit_last3",
                    "adj_bb_rate_last3", "adj_run_suppression_last3"]:
        h_val = home_form.get(metric)
        a_val = away_form.get(metric)
        if h_val is not None and a_val is not None:
            combined = (h_val + a_val) / 2
            results[metric] = {
                "signal_value": round(combined, 6),
                "home_value": h_val,
                "away_value": a_val,
                # Favorable zone: both pitchers suppressing above average
                # adj_k_rate > 0 means better K rate than opponent expected
                # adj_contact_rate > 0 means lower contact rate than opponent expected
                # adj_hard_hit > 0 means lower hard hit rate than league avg
                "favorable_zone_flag": combined > 0,
            }
        else:
            results[metric] = {
                "signal_value": None,
                "home_value": h_val,
                "away_value": a_val,
                "favorable_zone_flag": False,
            }

    return results


# ======================================================================
# V1 direction context (shared logic)
# ======================================================================

def _v1_direction(proj):
    """Derive V1 direction context from projection dict."""
    v1_p_under = None
    if proj.get("model_mode") == "simulation":
        v1_p_under = 1.0 - proj.get("sim_p_over", 0.5)

    if v1_p_under is not None:
        if v1_p_under < 0.45:
            return "OVER"
        elif v1_p_under > 0.57:
            return "UNDER"
    return "NONE"


# ======================================================================
# Price extraction helper
# ======================================================================

def extract_closing_prices(odds_dict):
    """
    Extract closing under/over prices from the odds dict returned by
    modules/odds.get_game_lines().

    Parameters
    ----------
    odds_dict : dict
        The per-game odds dict, e.g. {"full": {"consensus": 8.5,
        "best_under": {"book": "pinnacle", "line": 8.5, "odds": -105},
        "best_over":  {"book": "pinnacle", "line": 8.5, "odds": -115},
        "draftkings": {"line": 8.5, "over": -110, "under": -110}, ...},
        "f5": {...}}

    Returns
    -------
    dict with keys: closing_under_price, closing_over_price, price_source.
    All values may be None if data is unavailable.

    Priority: pinnacle > draftkings > fanduel > best_under/best_over.
    """
    full = (odds_dict or {}).get("full") or {}
    if not full:
        return {"closing_under_price": None, "closing_over_price": None, "price_source": None}

    _BOOK_PRIORITY = ["pinnacle", "draftkings", "fanduel"]
    for bk in _BOOK_PRIORITY:
        book_data = full.get(bk)
        if book_data and book_data.get("under") is not None and book_data.get("over") is not None:
            return {
                "closing_under_price": int(book_data["under"]),
                "closing_over_price": int(book_data["over"]),
                "price_source": bk,
            }

    # Fallback: best_under / best_over (may come from different books)
    bu = full.get("best_under")
    bo = full.get("best_over")
    if bu and bo:
        src = bu.get("book", "unknown")
        if bu.get("book") != bo.get("book"):
            src = f"{bu.get('book', '?')}+{bo.get('book', '?')}"
        return {
            "closing_under_price": int(bu["odds"]),
            "closing_over_price": int(bo["odds"]),
            "price_source": src,
        }

    return {"closing_under_price": None, "closing_over_price": None, "price_source": None}


# ======================================================================
# Logging
# ======================================================================

def log_shadow_signals(game_id, date, season, home_team, away_team,
                       st02_result, adj_results, v1_direction_context,
                       closing_total=None, market_line=None,
                       model_projection=None,
                       closing_under_price=None, closing_over_price=None,
                       price_source=None):
    """
    Log all four shadow signals to a single JSON file per season.
    Each signal gets its own record in the array.
    Deduplicates by (game_id, signal_name).
    """
    log_path = LOG_DIR / f"shadow_signals_{season}.json"

    # Load existing
    records = []
    if log_path.exists():
        try:
            with open(log_path) as f:
                records = json.load(f)
        except (json.JSONDecodeError, Exception):
            records = []

    now = datetime.now().isoformat()

    # Build new records for this game
    new_records = []

    # ST02
    new_records.append({
        "game_id": game_id,
        "date": str(date),
        "signal_name": "ST02_road_trip_6plus",
        "signal_value": st02_result["signal_value"],
        "favorable_zone_flag": st02_result["favorable_zone_flag"],
        "v1_direction_context": v1_direction_context,
        "closing_total": closing_total,
        "home_team": home_team,
        "away_team": away_team,
        "market_line": market_line,
        "model_projection": model_projection,
        "closing_under_price": closing_under_price,
        "closing_over_price": closing_over_price,
        "price_source": price_source,
        "logged_at": now,
    })

    # ADJ signals
    for signal_name, display_name in [
        ("adj_contact_rate_last3", "ADJ_CONTACT"),
        ("adj_hard_hit_last3", "ADJ_HH"),
        ("adj_k_rate_last3", "adj_k_rate_last3"),
        ("adj_bb_rate_last3", "ADJ_BB_RATE"),
        ("adj_run_suppression_last3", "ADJ_RUN_SUPP"),
    ]:
        sig = adj_results.get(signal_name, {})
        new_records.append({
            "game_id": game_id,
            "date": str(date),
            "signal_name": display_name,
            "signal_value": sig.get("signal_value"),
            "favorable_zone_flag": sig.get("favorable_zone_flag", False),
            "v1_direction_context": v1_direction_context,
            "closing_total": closing_total,
            "home_team": home_team,
            "away_team": away_team,
            "market_line": market_line,
            "model_projection": model_projection,
            "home_pitcher_value": sig.get("home_value"),
            "away_pitcher_value": sig.get("away_value"),
            "closing_under_price": closing_under_price,
            "closing_over_price": closing_over_price,
            "price_source": price_source,
            "logged_at": now,
        })

    # Deduplicate: remove old records for this game_id + signal_name
    new_keys = {(r["game_id"], r["signal_name"]) for r in new_records}
    records = [r for r in records if (r.get("game_id"), r.get("signal_name")) not in new_keys]
    records.extend(new_records)

    with open(log_path, "w") as f:
        json.dump(records, f, indent=2)

    # Log favorable zones to console
    for r in new_records:
        if r["favorable_zone_flag"]:
            logger.info(f"  SHADOW {r['signal_name']}: {away_team}@{home_team} — "
                        f"value={r['signal_value']} FAVORABLE (V1={v1_direction_context})")

    return new_records


def fill_actuals(season, game_results):
    """
    Backfill actual_total and result fields for previously logged shadow records.
    game_results: dict mapping game_id -> {"actual_total": int, "closing_total": float}
    """
    log_path = LOG_DIR / f"shadow_signals_{season}.json"
    if not log_path.exists():
        return 0

    with open(log_path) as f:
        records = json.load(f)

    filled = 0
    for r in records:
        gid = r.get("game_id")
        if gid in game_results and r.get("actual_total") is None:
            gr = game_results[gid]
            r["actual_total"] = gr["actual_total"]
            ct = gr.get("closing_total", r.get("closing_total"))
            r["closing_total"] = ct
            if ct is not None:
                r["actual_result_over"] = 1 if gr["actual_total"] > ct else 0
                r["over_hit"] = r["actual_result_over"] == 1
            filled += 1

    with open(log_path, "w") as f:
        json.dump(records, f, indent=2)

    return filled


def grade_shadow_signals(season: int = 2026):
    """Grade unresolved shadow signal entries using game_table actuals."""
    import pandas as pd

    log_path = LOG_DIR / f"shadow_signals_{season}.json"
    gt_path = Path(__file__).resolve().parent.parent.parent / "sim" / "data" / "game_table.parquet"

    if not log_path.exists() or not gt_path.exists():
        return

    try:
        data = json.loads(log_path.read_text())
    except Exception:
        return

    gt = pd.read_parquet(gt_path)
    actuals = dict(zip(gt["game_pk"].astype(int), gt["actual_total"]))

    graded = 0
    for entry in data:
        if entry.get("resolved"):
            continue
        game_id = entry.get("game_id")
        closing = entry.get("closing_total")
        actual = actuals.get(int(game_id)) if game_id else None
        if actual is None or closing is None:
            continue

        entry["actual_total"] = float(actual)

        if actual < closing:
            entry["actual_over_under"] = "UNDER"
        elif actual > closing:
            entry["actual_over_under"] = "OVER"
        else:
            entry["actual_over_under"] = "PUSH"

        # All shadow signals are UNDER-leaning (favorable_zone = suppression)
        if entry.get("favorable_zone_flag"):
            entry["result"] = ("WIN" if entry["actual_over_under"] == "UNDER"
                               else "LOSS" if entry["actual_over_under"] == "OVER"
                               else "PUSH")
        else:
            entry["result"] = None

        entry["resolved"] = True
        graded += 1

    if graded > 0:
        log_path.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"Shadow signals grader: resolved {graded} entries")
