#!/usr/bin/env python3
"""
NBA Totals Model — Phase 7 Daily Runner.

Usage:
  python nba/run_nba.py                    # today's card
  python nba/run_nba.py 2026-03-15        # specific date
  python nba/run_nba.py --no-odds         # skip Odds API
  python nba/run_nba.py --skip-results    # skip prior night grading

Run order within the 7 AM card:
  1. Grade previous night's results (west coast games now final)
  2. Fetch today's NBA schedule
  3. Fetch injury report (ESPN API)
  4. Compute live team rolling features (from completed 2025-26 box stats)
  5. Apply injury adjustments to ORtg
  6. Fetch market lines (basketball_nba full + H1)
  7. Run full-game Ridge model + simulation
  8. Run H1 Ridge model + simulation (conservative — H1 data gaps noted)
  9. Classify HIGH / MEDIUM / LOW confidence plays (thresholds from config)
 10. Print NBA card (clearly labeled)
 11. Send Pushover notification for HIGH confidence plays
 12. Save today's projections for tomorrow's results grading

Framing notes carried from Phase 6:
  • H1 confidence plays treated conservatively: 536/994 2025-26 games had
    available H1 data. H1 flags are noted but not sent as standalone HIGH plays
    until coverage improves.
  • Full-game and H1 models use separate sigma values: 18.62 and 12.21 pts.
    These are NEVER interchanged.
  • All thresholds (EDGE_THRESHOLD_FULL, EDGE_THRESHOLD_HALF, etc.) live in
    nba/config.py — none are hardcoded here.
"""

import argparse
import logging
import os
import pickle
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from nba.config import (
    BOX_STATS_PATH,
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    CURRENT_SEASON,
    EDGE_THRESHOLD_FULL,
    EDGE_THRESHOLD_HALF,
    INJURY_MAX_REDUCTION,
    INJURY_MIN_MPG,
    INJURY_PPP_REDUCTION,
    LEAGUE_AVG_DRTG,
    LEAGUE_AVG_H1_TOTAL,
    LEAGUE_AVG_ORTG,
    LEAGUE_AVG_PACE,
    LEAGUE_AVG_TOTAL,
    MARKET_FLAG_THRESHOLD,
    NBA_PROJECTIONS_PATH,
    NBA_MARKET_SNAPSHOTS_PATH,
    OVER_UNDER_MIN_PROB,
    PLAYOFF_MODE_VERSION,
    PLAYOFF_SERIES_BLEND_CAP,
    PRIOR_SEASON_WEIGHT,
    RESIDUAL_SIGMA,
    RESIDUAL_SIGMA_PLAYOFF,
    ROLLING_WINDOW,
    SEASON_BLEND_END,
    SEASON_BLEND_START,
    SEASON_TYPE_PLAYOFF,
    SEASON_TYPE_REGULAR,
    VALIDATION_SEASON,
    H1_FEATURES_PATH,
)
from nba.modules.simulate import simulate_game

logger = logging.getLogger(__name__)

NBA_DIR     = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(NBA_DIR, "data", "ridge_model.pkl")
H1_MODEL_PATH = os.path.join(NBA_DIR, "data", "h1_ridge_model.pkl")

FEATURE_COLS = [
    "home_ortg", "away_ortg",
    "home_drtg", "away_drtg",
    "home_pace", "away_pace",
    "b2b_flag_away",
    "home_ortg_trend", "away_ortg_trend",
    "home_pace_trend", "away_pace_trend",
    "home_3pa_rate", "away_3pa_rate",
    "home_ft_rate",  "away_ft_rate",
]

SEP  = "═" * 68
SEP2 = "─" * 68


# ── Rolling feature computation for live games ────────────────────────────────

def _build_current_team_states(game_date: str) -> dict:
    """
    Compute rolling efficiency state for each team as of game_date.

    For live use (unlike training), we include the team's most recent completed
    game in the rolling window (no shift). Rolling window = 15 games.

    Returns dict: {team_abbr: {ortg, drtg, pace, fg3a_rate, ft_rate,
                                ortg_trend, pace_trend, games_in_season}}
    """
    from nba.modules.fetch_box_stats import fetch_box_stats

    try:
        hist_box = pd.read_parquet(BOX_STATS_PATH)
    except FileNotFoundError:
        logger.warning("box_stats.parquet not found — using API only")
        hist_box = pd.DataFrame()

    try:
        new_box = fetch_box_stats(CURRENT_SEASON)
    except Exception as e:
        logger.warning(f"Failed to fetch 2025-26 box stats: {e}")
        new_box = pd.DataFrame()

    if new_box.empty and hist_box.empty:
        logger.error("No box stats available — cannot compute rolling features")
        return {}

    all_box = pd.concat([hist_box, new_box], ignore_index=True) if not new_box.empty else hist_box.copy()
    all_box["date"] = pd.to_datetime(all_box["date"])
    cutoff = pd.Timestamp(game_date)

    # Prior-season baselines (2024-25 → 2025-26)
    from nba.modules.features import _build_prior_season_baselines, _blend
    baselines = _build_prior_season_baselines(all_box)

    states = {}
    for team, grp in all_box.groupby("team"):
        # Only 2025-26 games BEFORE today (completed games only)
        cur = grp[
            (grp["season"] == CURRENT_SEASON) &
            (grp["date"] < cutoff)
        ].sort_values("date").reset_index(drop=True)

        if cur.empty:
            # Fall back to prior-season baseline or league average
            bl = baselines.get((team, CURRENT_SEASON), {})
            states[team] = {
                "ortg":          bl.get("ortg", LEAGUE_AVG_ORTG),
                "drtg":          bl.get("drtg", LEAGUE_AVG_DRTG),
                "pace":          bl.get("pace", LEAGUE_AVG_PACE),
                "fg3a_rate":     0.36,
                "ft_rate":       0.28,
                "ortg_trend":    0.0,
                "pace_trend":    0.0,
                "games_in_season": 0,
            }
            continue

        n = len(cur)
        recent15 = cur.tail(ROLLING_WINDOW)
        recent5  = cur.tail(5)

        ortg_roll15 = recent15["ortg"].mean()
        drtg_roll15 = recent15["drtg"].mean()
        pace_roll15 = recent15["pace"].mean()

        ortg_roll5 = recent5["ortg"].mean() if len(recent5) >= 3 else ortg_roll15
        pace_roll5 = recent5["pace"].mean() if len(recent5) >= 3 else pace_roll15

        ortg_trend = round(float(ortg_roll5 - ortg_roll15), 3)
        pace_trend = round(float(pace_roll5 - pace_roll15), 3)

        # Style features
        fg3a_rate = recent15["fg3a_rate"].mean() if "fg3a_rate" in cur.columns else 0.36
        ft_rate   = recent15["ft_rate"].mean()   if "ft_rate"   in cur.columns else 0.28

        # Prior-season blending for early season
        bl = baselines.get((team, CURRENT_SEASON), {})
        ortg = _blend(ortg_roll15, bl.get("ortg", np.nan), n)
        drtg = _blend(drtg_roll15, bl.get("drtg", np.nan), n)
        pace = _blend(pace_roll15, bl.get("pace", np.nan), n)

        states[team] = {
            "ortg":          round(float(ortg), 2),
            "drtg":          round(float(drtg), 2),
            "pace":          round(float(pace), 2),
            "fg3a_rate":     round(float(fg3a_rate), 4),
            "ft_rate":       round(float(ft_rate), 4),
            "ortg_trend":    ortg_trend,
            "pace_trend":    pace_trend,
            "games_in_season": n,
        }

    logger.info(f"Team states computed for {len(states)} teams")
    return states


def _apply_injury_adj(team_state: dict, injuries: list[dict], team: str) -> dict:
    """
    Apply ORtg reduction for Out/Doubtful rotation players.
    Uses INJURY_PPP_REDUCTION per player capped at INJURY_MAX_REDUCTION.
    Returns a modified copy of team_state.
    """
    state = dict(team_state)
    team_injuries = [i for i in injuries if i.get("team") == team]
    if not team_injuries:
        return state

    # Count actionable Out/Doubtful players — apply flat reduction per player
    # (MPG data not available from ESPN; apply if status is out/doubtful)
    n_out = len(team_injuries)
    reduction = min(n_out * INJURY_PPP_REDUCTION, INJURY_MAX_REDUCTION)

    state["ortg"] = round(state["ortg"] - reduction, 2)
    state["injury_players"] = [i["player"] for i in team_injuries]
    state["injury_reduction"] = reduction
    logger.debug(f"{team}: {n_out} Out/Doubtful → ORtg reduced by {reduction:.1f} pts/100")
    return state


def _compute_b2b(game_date: str, team: str, role: str, games: pd.DataFrame) -> int:
    """Return 1 if team played yesterday, 0 otherwise."""
    yesterday = (pd.Timestamp(game_date) - pd.Timedelta(days=1)).date().isoformat()
    if games.empty:
        return 0
    games["date_str"] = pd.to_datetime(games["date"]).dt.date.astype(str)
    yday = games[games["date_str"] == yesterday]
    played = (
        (yday["home_team"] == team) | (yday["away_team"] == team)
    ).any()
    return int(played)


# ── Rolling league avg for today ──────────────────────────────────────────────

def _current_rolling_league_avg(game_date: str) -> float:
    """Return the rolling league average total as of game_date for 2025-26."""
    try:
        from nba.modules.fetch_games import fetch_season
        games = fetch_season(CURRENT_SEASON)
        if games.empty:
            return LEAGUE_AVG_TOTAL
        games["date"] = pd.to_datetime(games["date"])
        cutoff = pd.Timestamp(game_date)
        past = games[
            (games["date"] < cutoff) &
            (games["actual_total"] > 150)  # exclude incomplete games
        ]
        if past.empty:
            return LEAGUE_AVG_TOTAL
        return round(float(past["actual_total"].mean()), 2)
    except Exception as e:
        logger.warning(f"Failed to compute rolling_league_avg: {e}")
        return LEAGUE_AVG_TOTAL


def _current_rolling_h1_avg(game_date: str) -> float:
    """Return the rolling H1 league average total as of game_date for 2025-26."""
    try:
        if not os.path.exists(H1_FEATURES_PATH):
            return LEAGUE_AVG_H1_TOTAL
        h1 = pd.read_parquet(H1_FEATURES_PATH)
        # Use 2024-25 mean as prior (best available H1 prior)
        prior = h1[h1["season"] == VALIDATION_SEASON]["actual_h1_total"].mean()
        return round(float(prior), 2) if not np.isnan(prior) else LEAGUE_AVG_H1_TOTAL
    except Exception:
        return LEAGUE_AVG_H1_TOTAL


# ── Playoff helper functions ──────────────────────────────────────────────────
# All functions here are conditional on is_playoff — regular season code never
# calls into this block. No changes to any existing function above this line.

def _all_team_games(team: str, game_date: str, reg_games: pd.DataFrame,
                    playoff_games: pd.DataFrame) -> pd.DataFrame:
    """Return all completed games for a team across regular season + playoffs before game_date."""
    cutoff = pd.Timestamp(game_date)
    frames = []
    for df in [reg_games, playoff_games]:
        if df.empty:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        mask = (
            ((df["home_team"] == team) | (df["away_team"] == team)) &
            (df["date"] < cutoff)
        )
        frames.append(df[mask])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("date")


def _compute_days_rest_playoff(game_date: str, team: str,
                                reg_games: pd.DataFrame,
                                playoff_games: pd.DataFrame) -> int:
    """Days rest for a team in a playoff game (searches all prior games, capped at 7)."""
    all_games = _all_team_games(team, game_date, reg_games, playoff_games)
    if all_games.empty:
        return 7
    last_game_date = all_games["date"].max()
    days = (pd.Timestamp(game_date) - last_game_date).days - 1
    return min(max(days, 0), 7)


def _infer_playoff_round(home: str, away: str, season: str,
                          all_playoff_games: pd.DataFrame) -> str:
    """
    Infer the playoff round for a given matchup.
    Assigns rounds by the order in which unique matchups first appear.
    NBA standard: 8 first-round series → 4 semis → 2 conf finals → 1 finals.
    """
    if all_playoff_games.empty:
        return "Playoffs"

    # Canonical team-pair key (alphabetical) → first game date
    matchup_first: dict[str, pd.Timestamp] = {}
    for _, g in all_playoff_games.iterrows():
        key = "_vs_".join(sorted([g["home_team"], g["away_team"]]))
        d   = pd.Timestamp(g["date"])
        if key not in matchup_first or d < matchup_first[key]:
            matchup_first[key] = d

    # Sort series by first game date
    ordered = sorted(matchup_first.items(), key=lambda x: x[1])
    current_key = "_vs_".join(sorted([home, away]))

    idx = next((i for i, (k, _) in enumerate(ordered) if k == current_key), None)
    if idx is None:
        return "Playoffs"

    # Round assignment by series position
    if idx < 8:
        return "First Round"
    elif idx < 12:
        return "Conference Semifinals"
    elif idx < 14:
        return "Conference Finals"
    else:
        return "NBA Finals"


def _get_series_metadata(home: str, away: str, game_date: str,
                          season: str) -> dict:
    """
    Derive series metadata from playoff game history.
    Returns all series fields; at Game 1 all win/avg/elim fields are null/0.
    """
    null_meta = {
        "series_game_number":   1,
        "home_series_wins":     None,
        "away_series_wins":     None,
        "series_avg_total":     None,
        "playoff_round":        "First Round",
        "elimination_game_home": 0,
        "elimination_game_away": 0,
        "elimination_game_any":  0,
        "series_sample_size":   0,
        "playoff_blend_weight": 0.0,
    }

    try:
        from nba.modules.fetch_games import fetch_season
        playoff_games = fetch_season(season, SEASON_TYPE_PLAYOFF)
    except Exception as e:
        logger.warning(f"Series metadata fetch failed: {e}")
        return null_meta

    if playoff_games.empty:
        return null_meta

    playoff_games = playoff_games.copy()
    playoff_games["date"] = pd.to_datetime(playoff_games["date"])
    cutoff = pd.Timestamp(game_date)

    # Prior games in this series (either home/away order), strictly before today
    prior = playoff_games[
        (
            ((playoff_games["home_team"] == home) & (playoff_games["away_team"] == away)) |
            ((playoff_games["home_team"] == away) & (playoff_games["away_team"] == home))
        ) &
        (playoff_games["date"] < cutoff)
    ].sort_values("date").reset_index(drop=True)

    n_prior = len(prior)
    series_game_number = n_prior + 1  # 1-indexed

    playoff_round = _infer_playoff_round(home, away, season, playoff_games)

    if n_prior == 0:
        # Game 1 — all series-dependent fields are null
        result = dict(null_meta)
        result["playoff_round"] = playoff_round
        return result

    # Count series wins (from home team's perspective today)
    home_wins = 0
    away_wins = 0
    for _, pg in prior.iterrows():
        if pg["home_score"] > pg["away_score"]:
            winner = pg["home_team"]
        else:
            winner = pg["away_team"]
        if winner == home:
            home_wins += 1
        else:
            away_wins += 1

    home_losses = away_wins   # losses for home = wins by away
    away_losses = home_wins

    series_avg_total = float(prior["actual_total"].mean())

    elim_home = 1 if home_losses == 3 else 0
    elim_away = 1 if away_losses == 3 else 0

    # Calibration fix (2025-03-17): faster blend ramp based on 2025 shadow run.
    # Shadow data showed G1-2 bias = +10 pts (pure baseline) and rapid improvement
    # through G3-4. New schedule reaches full weight by G4 instead of G5.
    # Regular season is unaffected — w_playoff is only used inside is_playoff blocks.
    _W_MAP = {0: 0.00, 1: 0.35, 2: 0.60, 3: 0.80}
    w_playoff = _W_MAP.get(n_prior, 1.00)   # n_prior >= 4 → 1.00

    return {
        "series_game_number":    series_game_number,
        "home_series_wins":      home_wins,
        "away_series_wins":      away_wins,
        "series_avg_total":      round(series_avg_total, 2),
        "playoff_round":         playoff_round,
        "elimination_game_home": elim_home,
        "elimination_game_away": elim_away,
        "elimination_game_any":  max(elim_home, elim_away),
        "series_sample_size":    n_prior,
        "playoff_blend_weight":  round(w_playoff, 3),
    }


def _build_series_rolling(home: str, away: str, game_date: str,
                           season: str) -> dict:
    """
    Compute team efficiency from ONLY prior games in current series.
    Returns per-team rolling: ortg, drtg, pace, pts (mean of prior series games).
    Returns empty dict if no prior series games (Game 1 case).
    Shift rule: only games strictly before game_date are used.
    """
    try:
        from nba.modules.fetch_box_stats import fetch_box_stats
        box = fetch_box_stats(season, SEASON_TYPE_PLAYOFF)
    except Exception as e:
        logger.warning(f"Series rolling fetch failed: {e}")
        return {}

    if box.empty:
        return {}

    box = box.copy()
    box["date"] = pd.to_datetime(box["date"])
    cutoff = pd.Timestamp(game_date)

    result = {}
    for role, team, opp in [("home", home, away), ("away", away, home)]:
        # Box stat rows for this team in this series, before today
        team_rows = box[
            (box["team"] == team) &
            (box["opponent"] == opp) &
            (box["date"] < cutoff)
        ].sort_values("date")

        if team_rows.empty:
            # No prior series data — caller checks series_sample_size
            continue

        result[f"{role}_ortg_rolling_series"] = float(team_rows["ortg"].mean())
        result[f"{role}_drtg_rolling_series"] = float(team_rows["drtg"].mean()) if "drtg" in team_rows else None
        result[f"{role}_pace_rolling_series"] = float(team_rows["pace"].mean())
        result[f"{role}_pts_rolling_series"]  = float(team_rows["pts"].mean())

    return result


def _blend_playoff_features(reg_state: dict, series_roll: dict,
                              role: str, w_playoff: float) -> dict:
    """
    Blend regular-season rolling features with series rolling features.
    Returns a modified copy of reg_state with blended values.
    w_playoff = 0 → pure regular season; w_playoff = 1 → pure series.
    Only blends when series data exists for the feature; otherwise returns reg_state unchanged.
    """
    if w_playoff <= 0 or not series_roll:
        return reg_state

    state = dict(reg_state)
    w_reg = 1.0 - w_playoff

    blends = [
        ("ortg", f"{role}_ortg_rolling_series"),
        ("pace", f"{role}_pace_rolling_series"),
    ]
    for state_key, series_key in blends:
        series_val = series_roll.get(series_key)
        if series_val is not None and not np.isnan(series_val):
            state[state_key] = round(
                w_playoff * series_val + w_reg * state[state_key], 2
            )

    return state


# ── Confidence classification ─────────────────────────────────────────────────

def _classify(
    pred: float,
    line: float,
    p_over: float,
    edge_threshold: float,
    injuries: list,
) -> str:
    """
    Classify a play as HIGH / MEDIUM / LOW based on config thresholds.
    edge_threshold: EDGE_THRESHOLD_FULL or EDGE_THRESHOLD_HALF (from config).
    injuries: list of injury dicts for the teams in this game.

    HIGH  : |pred − line| ≥ edge_threshold AND p(over or under) ≥ OVER_UNDER_MIN_PROB
    MEDIUM: one condition met
    LOW   : neither met
    """
    # Use league avg as line if no market line
    abs_edge  = abs(pred - line)
    p_dir     = p_over if pred > line else (1 - p_over)
    prob_ok   = p_dir >= OVER_UNDER_MIN_PROB
    edge_ok   = (edge_threshold is not None) and (abs_edge >= edge_threshold)
    has_injury = len(injuries) > 0

    if edge_ok and prob_ok:
        return CONF_HIGH if not has_injury else CONF_MEDIUM
    if edge_ok or prob_ok:
        return CONF_MEDIUM
    return CONF_LOW


# ── Archetype matchup detection ───────────────────────────────────────────────

# ELITE_DEF2 @ ELITE_DEF → UNDER signal
# Historical: -3.0 pts (p=0.022, N=203)
# 2024-25: -4.2 pts (p=0.064, N=60)
_ARCHETYPE_GAMES_2026 = {
    # (away_abb, home_abb): date
    ("ORL", "CLE"): "2026-03-24",
    ("MIA", "CLE"): "2026-03-25",
    ("HOU", "MIN"): "2026-03-25",
    ("NYK", "OKC"): "2026-03-29",
    ("LAL", "OKC"): "2026-04-02",
    ("HOU", "GSW"): "2026-04-05",
    ("SAC", "GSW"): "2026-04-07",
    ("LAL", "GSW"): "2026-04-09",
    ("ORL", "BOS"): "2026-04-12",
}

_ELITE_DEF = {"BOS", "CLE", "GSW", "MIL", "MIN", "OKC"}
_ELITE_DEF2 = {"HOU", "LAC", "LAL", "MIA", "NYK", "ORL", "SAC"}


def _flag_archetype_matchups(game_results: list[dict], game_date: str) -> None:
    """Flag games matching ELITE_DEF2 @ ELITE_DEF archetype for UNDER signal."""
    n_flagged = 0
    for g in game_results:
        away = g.get("away_team", "")
        home = g.get("home_team", "")
        g["archetype_signal"] = None
        g["archetype_direction"] = None
        g["archetype_note"] = None

        if away in _ELITE_DEF2 and home in _ELITE_DEF:
            g["archetype_signal"] = "ELITE_DEF2_at_ELITE_DEF"
            g["archetype_direction"] = "UNDER"
            g["archetype_note"] = "UNDER — hist edge -3.0pts (p=0.022)"

            # Find best UNDER number across books if odds available
            best_total = g.get("close_total") or g.get("line")
            best_book = g.get("close_book", "")
            # Check for multi-book data
            for key in ["dk_total", "fd_total", "mgm_total", "pb_total"]:
                val = g.get(key)
                if val and (best_total is None or val > best_total):
                    best_total = val
                    best_book = key.replace("_total", "")

            g["archetype_best_total"] = best_total
            g["archetype_best_book"] = best_book
            n_flagged += 1
            logger.info(f"  ⚡ ARCHETYPE: {away} @ {home} → UNDER"
                        f" (best line: {best_total} at {best_book})")

    if n_flagged > 0:
        logger.info(f"Archetype matchups flagged: {n_flagged}")


# ── Shot profile matchup detection ───────────────────────────────────────────

# Signal 1: BALANCED OFF vs PASSIVE DEF → OVER (+2.2 pts, p=0.013, confirmed 2025-26)
# Signal 2: THREE_HEAVY OFF vs FOUL_PRONE DEF → UNDER (-2.1 pts, p=0.083, confirmed -3.6 2025-26)

_BALANCED_OFF = {"DEN", "HOU", "IND", "NYK", "OKC"}
_PASSIVE_DEF = {"BOS", "CHI", "CLE", "DEN", "LAL", "MIA", "MIL", "NYK", "PHX", "SAS", "UTA", "WAS"}
_THREE_HEAVY_OFF = {"BOS", "CHI", "CLE", "GSW", "MIA", "MIL", "SAC"}
_FOUL_PRONE_DEF = {"HOU", "IND", "ORL"}


def _flag_shot_profile(game_results: list[dict], game_date: str) -> None:
    """Flag games matching shot-profile archetype signals."""
    for g in game_results:
        away = g.get("away_team", "")
        home = g.get("home_team", "")
        g["shot_signal"] = None
        g["shot_direction"] = None
        g["shot_note"] = None

        signals = []

        # Check both interactions: away OFF vs home DEF, home OFF vs away DEF
        # Signal 1: BALANCED @ PASSIVE → OVER
        if away in _BALANCED_OFF and home in _PASSIVE_DEF:
            signals.append(("BALANCED_vs_PASSIVE", "OVER", "clean looks / low disruption"))
        if home in _BALANCED_OFF and away in _PASSIVE_DEF:
            signals.append(("BALANCED_vs_PASSIVE", "OVER", "clean looks / low disruption"))

        # Signal 2: THREE_HEAVY @ FOUL_PRONE → UNDER
        if away in _THREE_HEAVY_OFF and home in _FOUL_PRONE_DEF:
            signals.append(("THREE_HEAVY_vs_FOUL_PRONE", "UNDER", "expected FTA not materializing"))
        if home in _THREE_HEAVY_OFF and away in _FOUL_PRONE_DEF:
            signals.append(("THREE_HEAVY_vs_FOUL_PRONE", "UNDER", "expected FTA not materializing"))

        if not signals:
            continue

        # If multiple signals fire, check agreement
        directions = set(s[1] for s in signals)
        if len(directions) == 1:
            g["shot_signal"] = signals[0][0]
            g["shot_direction"] = signals[0][1]
            g["shot_note"] = signals[0][2]
        else:
            # Conflicting shot signals — rare, flag both
            g["shot_signal"] = "+".join(s[0] for s in signals)
            g["shot_direction"] = "CONFLICT"
            g["shot_note"] = "conflicting shot signals"

        # Compute combined classification with pace archetype
        pace_dir = g.get("archetype_direction")
        shot_dir = g["shot_direction"]

        if pace_dir and shot_dir and shot_dir != "CONFLICT":
            if pace_dir == shot_dir:
                g["signal_class"] = "DOUBLE_SIGNAL"
            else:
                g["signal_class"] = "CONFLICT"
        elif shot_dir and shot_dir != "CONFLICT":
            g["signal_class"] = "SHOT_ONLY"
        elif pace_dir:
            g["signal_class"] = "PACE_ONLY"
        else:
            g["signal_class"] = "NO_SIGNAL"

        logger.info(f"  🎯 SHOT: {away} @ {home} → {g['shot_direction']} "
                    f"({g['shot_signal']}) [{g.get('signal_class', '')}]")


# ── Venue interaction detection (Board 4) ────────────────────────────────────

# ROAD_WARRIOR @ STRONG_HOME → OVER (+4.8 pts, p<0.0001, N=427)
# Confirmed 2024-25: +5.9 pts (p=0.001, N=114)
# Market gap: 3.6 pts unexplained

_ROAD_WARRIOR = {"BKN", "CHI", "DAL", "DET", "GSW", "HOU", "NYK", "PHI", "PHX", "UTA"}
_STRONG_HOME = {"DEN", "IND", "LAL", "MIL", "NOP", "OKC", "POR", "SAS"}


def _flag_venue_signal(game_results: list[dict], game_date: str) -> None:
    """Flag ROAD_WARRIOR @ STRONG_HOME → OVER signal (Board 4)."""
    for g in game_results:
        away = g.get("away_team", "")
        home = g.get("home_team", "")
        g["venue_signal"] = None
        g["venue_direction"] = None
        g["venue_note"] = None

        if away in _ROAD_WARRIOR and home in _STRONG_HOME:
            g["venue_signal"] = "ROAD_WARRIOR_at_STRONG_HOME"
            g["venue_direction"] = "OVER"
            g["venue_note"] = "road warrior maintains output + home boost (+4.8 pts hist)"
            logger.info(f"  🏟️ VENUE: {away} @ {home} → OVER (road warrior @ strong home)")

        # Recompute combined classification with all three boards
        pace_dir = g.get("archetype_direction")
        shot_dir = g.get("shot_direction") if g.get("shot_direction") != "CONFLICT" else None
        venue_dir = g.get("venue_direction")

        directions = [d for d in [pace_dir, shot_dir, venue_dir] if d]
        unique_dirs = set(directions)

        if len(directions) >= 3 and len(unique_dirs) == 1:
            g["signal_class"] = "TRIPLE_SIGNAL"
        elif len(directions) >= 2 and len(unique_dirs) == 1:
            g["signal_class"] = "DOUBLE_SIGNAL"
        elif len(directions) >= 2 and len(unique_dirs) > 1:
            g["signal_class"] = "CONFLICT"
        elif len(directions) == 1:
            if pace_dir: g["signal_class"] = "PACE_ONLY"
            elif shot_dir: g["signal_class"] = "SHOT_ONLY"
            elif venue_dir: g["signal_class"] = "VENUE_ONLY"
        elif not g.get("signal_class"):
            g["signal_class"] = "NO_SIGNAL"


# ── Print NBA card ────────────────────────────────────────────────────────────

def print_nba_card(game_results: list[dict], game_date: str) -> None:
    bar = "═" * 68
    print(f"\n\033[36m{bar}")
    print(f"  NBA TOTALS MODEL  |  {game_date}  |  {datetime.now().strftime('%I:%M %p')}")
    print(f"{bar}\033[0m\n")

    if not game_results:
        print("  No NBA games scheduled today.\n")
        return

    plays    = [g for g in game_results if g["confidence"] != CONF_LOW]
    no_plays = [g for g in game_results if g["confidence"] == CONF_LOW]

    # Sort plays: HIGH first, then by |edge|
    conf_order = {CONF_HIGH: 0, CONF_MEDIUM: 1, CONF_LOW: 2}
    plays.sort(key=lambda g: (conf_order[g["confidence"]], -abs(g.get("edge") or 0)))

    for i, g in enumerate(plays):
        if i > 0:
            print(f"\033[2m{'─' * 68}\033[0m")

        matchup   = f"{g['away_team']} @ {g['home_team']}"
        time_str  = g.get("game_time_et", "")
        lean      = g["lean"]
        pred      = g["pred_total"]
        line      = g.get("line")
        edge      = g.get("edge")
        conf      = g["confidence"]
        p_over    = g.get("p_over", 0.5)

        lean_col  = "\033[91m" if lean == "OVER" else "\033[96m"
        conf_col  = "\033[92m" if conf == CONF_HIGH else "\033[93m"

        line_str  = f"Line {line:.1f}" if line else "No line"
        edge_str  = f"Edge {edge:+.1f}" if edge is not None else ""
        p_str     = f"P(over) {p_over:.1%}"

        print(f"\033[1m{conf_col}{conf}\033[0m  {matchup}  ·  {time_str}")
        print(f"  {lean_col}{lean}\033[0m  Proj {pred:.1f}  ·  {line_str}  ·  {edge_str}  ·  {p_str}")

        # H1 line if available
        pred_h1 = g.get("pred_h1")
        h1_conf = g.get("h1_confidence")
        if pred_h1:
            h1_line  = g.get("h1_line")
            h1_edge  = g.get("h1_edge")
            h1_lean  = g.get("h1_lean", "—")
            h1_p     = g.get("h1_p_over", 0.5)
            h1_line_s = f"H1 Line {h1_line:.1f}" if h1_line else "No H1 line"
            h1_edge_s = f"H1 Edge {h1_edge:+.1f}" if h1_edge is not None else ""
            h1_note = "  [conservative — H1 data coverage gaps]" if h1_conf == CONF_HIGH else ""
            print(f"  H1: {h1_lean}  H1 Proj {pred_h1:.1f}  ·  {h1_line_s}  {h1_edge_s}{h1_note}")

        # Injury note
        if g.get("home_injuries"):
            print(f"  ⚠ {g['home_team']} Out/Doubtful: {', '.join(g['home_injuries'])}")
        if g.get("away_injuries"):
            print(f"  ⚠ {g['away_team']} Out/Doubtful: {', '.join(g['away_injuries'])}")

        # Archetype signal
        if g.get("archetype_signal"):
            best = g.get("archetype_best_total") or g.get("line")
            book = g.get("archetype_best_book", "")
            print(f"  \033[95m⚡ ARCHETYPE: {g['archetype_note']}"
                  f"  (best UNDER: {best} at {book})\033[0m")

        print()

    # Print archetype games that are NO PLAY — still flagged
    arch_no_play = [g for g in no_plays if g.get("archetype_signal")]
    if arch_no_play:
        print(f"\033[95m{'─' * 18}  ARCHETYPE CANDIDATES  {'─' * 18}\033[0m\n")
        for g in arch_no_play:
            matchup = f"{g['away_team']} @ {g['home_team']}"
            best = g.get("archetype_best_total") or g.get("line")
            print(f"  \033[95m⚡ {matchup}  ·  {g['archetype_note']}"
                  f"  (best UNDER: {best})\033[0m")
        print()

    if no_plays:
        print(f"\033[2m{'─' * 24}  NO PLAY  {'─' * 24}\033[0m\n")
        for g in no_plays:
            matchup = f"{g['away_team']} @ {g['home_team']}"
            time_str = g.get("game_time_et", "")
            print(f"  NO PLAY  {matchup}  ·  {time_str}  ·  Proj {g['pred_total']:.1f}")
        print()


# ── Save projections for results tracker ──────────────────────────────────────

def save_projections(game_results: list[dict], game_date: str) -> None:
    """Save today's projections to parquet for tomorrow's results grading."""
    if not game_results:
        return

    _ts_decision = datetime.now(timezone.utc).isoformat()

    rows = []
    for g in game_results:
        rows.append({
            "timestamp_decision":  _ts_decision,
            "game_date":           game_date,
            "game_id":             g.get("game_id"),
            "home_team":           g.get("home_team"),
            "away_team":           g.get("away_team"),
            "game_time_et":        g.get("game_time_et"),
            "pred_total":          g.get("pred_total"),
            "lean":                g.get("lean"),
            "p_over":              g.get("p_over"),
            "confidence":          g.get("confidence"),
            "line":                g.get("line"),
            "edge":                g.get("edge"),
            "rolling_league_avg":  g.get("rolling_league_avg"),
            "market_gap_flag":     g.get("market_gap_flag", False),
            "pred_h1":             g.get("pred_h1"),
            "h1_lean":             g.get("h1_lean"),
            "h1_p_over":           g.get("h1_p_over"),
            "h1_confidence":       g.get("h1_confidence"),
            "h1_line":             g.get("h1_line"),
            "h1_edge":             g.get("h1_edge"),
            "rolling_h1_league_avg": g.get("rolling_h1_league_avg"),
            # Team features
            "home_ortg":           g.get("home_ortg"),
            "away_ortg":           g.get("away_ortg"),
            "home_drtg":           g.get("home_drtg"),
            "away_drtg":           g.get("away_drtg"),
            "home_pace":           g.get("home_pace"),
            "away_pace":           g.get("away_pace"),
            "home_3pa_rate":       g.get("home_3pa_rate"),
            "away_3pa_rate":       g.get("away_3pa_rate"),
            "home_ft_rate":        g.get("home_ft_rate"),
            "away_ft_rate":        g.get("away_ft_rate"),
            "b2b_flag_away":       g.get("b2b_flag_away", 0),
            "home_injuries_str":   ",".join(g.get("home_injuries") or []),
            "away_injuries_str":   ",".join(g.get("away_injuries") or []),
            # Playoff fields (None for regular season games)
            "is_playoff":                g.get("is_playoff", False),
            "playoff_mode_version":      g.get("playoff_mode_version"),
            "season_type":               g.get("season_type", SEASON_TYPE_REGULAR),
            "sigma_used":                g.get("sigma_used"),
            "series_game_number":        g.get("series_game_number"),
            "home_series_wins":          g.get("home_series_wins"),
            "away_series_wins":          g.get("away_series_wins"),
            "series_avg_total":          g.get("series_avg_total"),
            "playoff_round":             g.get("playoff_round"),
            "elimination_game_home":     g.get("elimination_game_home"),
            "elimination_game_away":     g.get("elimination_game_away"),
            "elimination_game_any":      g.get("elimination_game_any"),
            "series_sample_size":        g.get("series_sample_size"),
            "early_series_adjustment":   g.get("early_series_adjustment", 0.0),
            "playoff_blend_weight":      g.get("playoff_blend_weight"),
            "home_ortg_rolling_series":  g.get("home_ortg_rolling_series"),
            "away_ortg_rolling_series":  g.get("away_ortg_rolling_series"),
            "home_pace_rolling_series":  g.get("home_pace_rolling_series"),
            "away_pace_rolling_series":  g.get("away_pace_rolling_series"),
            "home_pts_rolling_series":   g.get("home_pts_rolling_series"),
            "away_pts_rolling_series":   g.get("away_pts_rolling_series"),
            "playoff_days_rest_home":    g.get("playoff_days_rest_home"),
            "playoff_days_rest_away":    g.get("playoff_days_rest_away"),
        })

    new_df = pd.DataFrame(rows)

    # Append to existing projections file (keep historical)
    if os.path.exists(NBA_PROJECTIONS_PATH):
        existing = pd.read_parquet(NBA_PROJECTIONS_PATH)
        # Drop any existing rows for today (allow re-run)
        existing = existing[existing["game_date"] != game_date]
        combined = pd.concat([existing, new_df], ignore_index=True).convert_dtypes()
    else:
        combined = new_df

    combined.to_parquet(NBA_PROJECTIONS_PATH, index=False)
    logger.info(f"Projections saved → {NBA_PROJECTIONS_PATH} ({len(new_df)} games for {game_date})")

    # ── Morning snapshot — write once per game_date (prevent re-run overwrite) ─
    try:
        snap_rows = []
        for g in game_results:
            gid  = g.get("game_id")
            line = g.get("line")
            src  = "odds_api" if line is not None else "no_line"
            snap_rows.append({
                "game_id":          gid,
                "game_date":        game_date,
                "snapshot_type":    "morning",
                "snapshot_time_utc": _ts_decision,
                "line":             line,
                "price":            -110.0,
                "source":           src,
            })
        snap_df = pd.DataFrame(snap_rows)

        if os.path.exists(NBA_MARKET_SNAPSHOTS_PATH):
            existing_snaps = pd.read_parquet(NBA_MARKET_SNAPSHOTS_PATH)
            # Only write if no morning snapshot exists for this game_date yet
            already_have = (
                (existing_snaps["game_date"] == game_date) &
                (existing_snaps["snapshot_type"] == "morning")
            ).any()
            if not already_have:
                combined_snaps = pd.concat([existing_snaps, snap_df], ignore_index=True)
                combined_snaps.to_parquet(NBA_MARKET_SNAPSHOTS_PATH, index=False)
                logger.info(f"Morning snapshot saved ({len(snap_df)} games for {game_date})")
            else:
                logger.info(f"Morning snapshot already exists for {game_date} — skipping overwrite")
        else:
            snap_df.to_parquet(NBA_MARKET_SNAPSHOTS_PATH, index=False)
            logger.info(f"Morning snapshot saved ({len(snap_df)} games for {game_date})")
    except Exception as _e:
        logger.warning(f"Morning snapshot write failed (non-fatal): {_e}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(game_date: str = None, use_odds: bool = True, skip_results: bool = False) -> list[dict]:
    if game_date is None:
        game_date = date.today().isoformat()

    logger.info(f"NBA Phase 7 — {game_date}")

    # ── Step 1: Grade previous night ─────────────────────────────────────────
    if not skip_results:
        from nba.results_tracker import grade_yesterday
        try:
            grade_yesterday(game_date)
        except Exception as e:
            logger.warning(f"Results grading failed (non-fatal): {e}")

    # ── Step 2: Today's schedule ──────────────────────────────────────────────
    from nba.modules.fetch_nba_schedule import fetch_today_schedule
    schedule = fetch_today_schedule(game_date)
    if not schedule:
        logger.warning(f"No NBA games scheduled for {game_date}")
        print(f"\n  [NBA] No games scheduled for {game_date}\n")
        return []
    logger.info(f"Schedule: {len(schedule)} game(s) for {game_date}")

    # ── Step 3: Injury report ─────────────────────────────────────────────────
    from nba.modules.fetch_injuries import fetch_injuries
    try:
        injuries = fetch_injuries()
    except Exception as e:
        logger.warning(f"Injury fetch failed (non-fatal): {e}")
        injuries = []

    # ── Step 4: Load models ───────────────────────────────────────────────────
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"ridge_model.pkl not found at {MODEL_PATH}. Run train_model.py first.")
    with open(MODEL_PATH, "rb") as f:
        fg_bundle = pickle.load(f)
    fg_model  = fg_bundle["model"]
    fg_scaler = fg_bundle["scaler"]

    h1_bundle = None
    h1_sigma  = None
    if os.path.exists(H1_MODEL_PATH):
        with open(H1_MODEL_PATH, "rb") as f:
            h1_bundle = pickle.load(f)
        h1_sigma = h1_bundle.get("h1_sigma", 12.21)
    else:
        logger.warning("h1_ridge_model.pkl not found — H1 projections will be skipped")

    # ── Step 5: Team rolling states ───────────────────────────────────────────
    team_states = _build_current_team_states(game_date)

    # Fetch completed games for B2B calculation (regular season)
    from nba.modules.fetch_games import fetch_season
    try:
        completed_games = fetch_season(CURRENT_SEASON)
    except Exception:
        completed_games = pd.DataFrame()

    # Fetch completed playoff games (for series metadata + rest calculation).
    # Only fetched once per run; cached per-day. Empty if not playoff season.
    try:
        completed_playoff_games = fetch_season(CURRENT_SEASON, SEASON_TYPE_PLAYOFF)
    except Exception:
        completed_playoff_games = pd.DataFrame()

    # ── Step 6: Rolling league averages ──────────────────────────────────────
    rolling_avg    = _current_rolling_league_avg(game_date)
    rolling_h1_avg = _current_rolling_h1_avg(game_date)
    logger.info(f"Rolling league avg: {rolling_avg:.2f} pts (full) | {rolling_h1_avg:.2f} pts (H1)")

    # ── Step 7: Market lines ──────────────────────────────────────────────────
    all_lines = {}
    if use_odds:
        from nba.modules.fetch_nba_odds import fetch_all_nba_lines, get_game_lines
        try:
            all_lines = fetch_all_nba_lines()
        except Exception as e:
            logger.warning(f"NBA odds fetch failed (non-fatal): {e}")
            all_lines = {}

    # ── Step 8: Per-game projections ──────────────────────────────────────────
    game_results = []

    for sched in schedule:
        gid      = sched["game_id"]
        home     = sched["home_team"]
        away     = sched["away_team"]
        time_et  = sched.get("game_time_et", "")

        logger.info(f"  Processing {away} @ {home} ({gid})")

        # Get team states with injury adjustments
        home_state_raw = team_states.get(home, {
            "ortg": LEAGUE_AVG_ORTG, "drtg": LEAGUE_AVG_DRTG, "pace": LEAGUE_AVG_PACE,
            "fg3a_rate": 0.36, "ft_rate": 0.28,
            "ortg_trend": 0.0, "pace_trend": 0.0, "games_in_season": 0,
        })
        away_state_raw = team_states.get(away, {
            "ortg": LEAGUE_AVG_ORTG, "drtg": LEAGUE_AVG_DRTG, "pace": LEAGUE_AVG_PACE,
            "fg3a_rate": 0.36, "ft_rate": 0.28,
            "ortg_trend": 0.0, "pace_trend": 0.0, "games_in_season": 0,
        })

        # ── Playoff detection (Change 1) ──────────────────────────────────────
        is_playoff = (sched.get("season_type", SEASON_TYPE_REGULAR) == SEASON_TYPE_PLAYOFF)

        home_injuries = [i for i in injuries if i.get("team") == home]
        away_injuries = [i for i in injuries if i.get("team") == away]
        home_state = _apply_injury_adj(home_state_raw, injuries, home)
        away_state = _apply_injury_adj(away_state_raw, injuries, away)

        b2b_away = _compute_b2b(game_date, away, "away", completed_games)

        # ── Playoff modifications — all conditional on is_playoff ─────────────
        # Change 2: series metadata
        series_meta = {}
        series_roll  = {}
        playoff_days_rest_home = None
        playoff_days_rest_away = None

        if is_playoff:
            # Change 5: zero B2B flags in playoffs; compute actual rest days instead
            b2b_away = 0

            playoff_days_rest_home = _compute_days_rest_playoff(
                game_date, home, completed_games, completed_playoff_games
            )
            playoff_days_rest_away = _compute_days_rest_playoff(
                game_date, away, completed_games, completed_playoff_games
            )

            # Change 2: series metadata (game number, wins, round, elimination flags)
            series_meta = _get_series_metadata(home, away, game_date, CURRENT_SEASON)
            series_sample = series_meta.get("series_sample_size", 0)

            # Change 4: series rolling features (only if Game 2+)
            if series_sample > 0:
                series_roll = _build_series_rolling(home, away, game_date, CURRENT_SEASON)
                w_p = series_meta.get("playoff_blend_weight", 0.0)
                # Blend regular-season rolling with series rolling
                home_state = _blend_playoff_features(home_state, series_roll, "home", w_p)
                away_state = _blend_playoff_features(away_state, series_roll, "away", w_p)
            else:
                # Game 1: pure regular season rolling (w_playoff = 0)
                pass

        playoff_blend_weight = series_meta.get("playoff_blend_weight", 0.0) if is_playoff else None

        # Build feature vector (unchanged — playoff blending modified the state values above)
        feat_row = {
            "home_ortg":       home_state["ortg"],
            "away_ortg":       away_state["ortg"],
            "home_drtg":       home_state["drtg"],
            "away_drtg":       away_state["drtg"],
            "home_pace":       home_state["pace"],
            "away_pace":       away_state["pace"],
            "b2b_flag_away":   b2b_away,
            "home_ortg_trend": home_state["ortg_trend"],
            "away_ortg_trend": away_state["ortg_trend"],
            "home_pace_trend": home_state["pace_trend"],
            "away_pace_trend": away_state["pace_trend"],
            "home_3pa_rate":   home_state["fg3a_rate"],
            "away_3pa_rate":   away_state["fg3a_rate"],
            "home_ft_rate":    home_state["ft_rate"],
            "away_ft_rate":    away_state["ft_rate"],
        }
        X = np.array([[feat_row[c] for c in FEATURE_COLS]])

        # ── Full-game prediction ──────────────────────────────────────────────
        X_sc       = fg_scaler.transform(X)
        pred_total = float(fg_model.predict(X_sc)[0])

        # Playoff early-series bias correction (Change 11 — calibration fix 2025-03-17).
        # Shadow run showed G1-2 bias = +10.1 pts, overall bias = +4.96 pts.
        # Reg-season baseline (227.7) over-projects playoff totals (actual avg 217.5).
        # Partial correction of 6 pts applied only at G1-2; series blend handles G3+.
        # Regular season: early_series_adjustment is always 0.0 (is_playoff guard).
        if is_playoff:
            sgn = series_meta.get("series_game_number", 1)
            if sgn <= 2:
                pred_total -= 6.0
                early_series_adjustment = -6.0
            else:
                early_series_adjustment = 0.0
        else:
            early_series_adjustment = 0.0

        lean = "OVER" if pred_total > rolling_avg else "UNDER"

        # Change 3: use playoff sigma when is_playoff — regular season sigma unchanged
        sigma_game = RESIDUAL_SIGMA_PLAYOFF if is_playoff else RESIDUAL_SIGMA

        sim = simulate_game(
            pred_total=pred_total,
            line=rolling_avg,
            sigma=sigma_game,
        )
        p_over = sim["p_over"]

        # Market lines
        game_lines = {}
        if all_lines:
            from nba.modules.fetch_nba_odds import get_game_lines
            game_lines = get_game_lines(home, away, all_lines)

        full_line_data = game_lines.get("full")
        line      = full_line_data.get("consensus") if full_line_data else None
        edge      = round(pred_total - line, 2) if line else None

        # If we have a market line, re-run simulation vs actual market line
        if line:
            sim = simulate_game(pred_total=pred_total, line=line, sigma=sigma_game)
            p_over = sim["p_over"]
            lean   = "OVER" if edge > 0 else "UNDER"

        # Market flag
        if line and abs(pred_total - line) > MARKET_FLAG_THRESHOLD:
            logger.warning(
                f"MARKET GAP: {away}@{home} — model {pred_total:.1f} vs line {line:.1f} "
                f"(gap = {abs(pred_total - line):.1f} pts)"
            )

        all_game_injuries = home_injuries + away_injuries
        confidence = _classify(pred_total, line or rolling_avg, p_over,
                                EDGE_THRESHOLD_FULL, all_game_injuries)

        # ── H1 prediction ─────────────────────────────────────────────────────
        pred_h1 = h1_lean = h1_p_over = h1_line = h1_edge = h1_confidence = None

        if h1_bundle is not None:
            h1_model  = h1_bundle["model"]
            h1_scaler = h1_bundle["scaler"]
            X_h1 = h1_scaler.transform(X)
            pred_h1  = float(h1_model.predict(X_h1)[0])
            h1_lean  = "OVER" if pred_h1 > rolling_h1_avg else "UNDER"

            h1_sim = simulate_game(pred_total=pred_h1, line=rolling_h1_avg, sigma=h1_sigma)
            h1_p_over = h1_sim["p_over"]

            h1_line_data = game_lines.get("h1")
            h1_line = h1_line_data.get("consensus") if h1_line_data else None
            h1_edge = round(pred_h1 - h1_line, 2) if h1_line else None

            if h1_line:
                h1_sim = simulate_game(pred_total=pred_h1, line=h1_line, sigma=h1_sigma)
                h1_p_over = h1_sim["p_over"]
                h1_lean   = "OVER" if h1_edge > 0 else "UNDER"

            h1_eff_threshold = EDGE_THRESHOLD_HALF  # may be None (placeholder)
            h1_confidence = _classify(
                pred_h1, h1_line or rolling_h1_avg, h1_p_over,
                h1_eff_threshold, all_game_injuries,
            )
            # H1 confidence conservatively capped at MEDIUM (Phase 6 coverage gap note)
            if h1_confidence == CONF_HIGH:
                h1_confidence = CONF_MEDIUM

        game_results.append({
            "game_id":            gid,
            "game_date":          game_date,
            "home_team":          home,
            "away_team":          away,
            "game_time_et":       time_et,
            # Full game
            "pred_total":         round(pred_total, 2),
            "lean":               lean,
            "p_over":             round(p_over, 4),
            "confidence":         confidence,
            "line":               line,
            "edge":               edge,
            "rolling_league_avg": rolling_avg,
            "market_gap_flag":    bool(line and abs(pred_total - line) > MARKET_FLAG_THRESHOLD),
            # H1
            "pred_h1":            round(pred_h1, 2) if pred_h1 else None,
            "h1_lean":            h1_lean,
            "h1_p_over":          round(h1_p_over, 4) if h1_p_over else None,
            "h1_confidence":      h1_confidence,
            "h1_line":            h1_line,
            "h1_edge":            h1_edge,
            "rolling_h1_league_avg": rolling_h1_avg,
            # Team features (for summary generation)
            "home_ortg":          round(home_state["ortg"], 2),
            "away_ortg":          round(away_state["ortg"], 2),
            "home_drtg":          round(home_state["drtg"], 2),
            "away_drtg":          round(away_state["drtg"], 2),
            "home_pace":          round(home_state["pace"], 2),
            "away_pace":          round(away_state["pace"], 2),
            "home_3pa_rate":      round(home_state["fg3a_rate"], 4),
            "away_3pa_rate":      round(away_state["fg3a_rate"], 4),
            "home_ft_rate":       round(home_state["ft_rate"], 4),
            "away_ft_rate":       round(away_state["ft_rate"], 4),
            "b2b_flag_away":      b2b_away,
            # Injuries
            "home_injuries":      [i["player"] for i in home_injuries],
            "away_injuries":      [i["player"] for i in away_injuries],
            # ── Playoff fields (Changes 1–5) — None for regular season ─────────
            "is_playoff":                    is_playoff,
            "playoff_mode_version":          PLAYOFF_MODE_VERSION if is_playoff else None,
            "season_type":                   sched.get("season_type", SEASON_TYPE_REGULAR),
            "sigma_used":                    sigma_game,
            # Series metadata (Change 2)
            "series_game_number":            series_meta.get("series_game_number"),
            "home_series_wins":              series_meta.get("home_series_wins"),
            "away_series_wins":              series_meta.get("away_series_wins"),
            "series_avg_total":              series_meta.get("series_avg_total"),
            "playoff_round":                 series_meta.get("playoff_round"),
            "elimination_game_home":         series_meta.get("elimination_game_home"),
            "elimination_game_away":         series_meta.get("elimination_game_away"),
            "elimination_game_any":          series_meta.get("elimination_game_any"),
            "series_sample_size":            series_meta.get("series_sample_size"),
            # Calibration fix (2025-03-17): early-series bias correction
            "early_series_adjustment":       early_series_adjustment,
            # Series features (Change 4)
            "playoff_blend_weight":          playoff_blend_weight,
            "home_ortg_rolling_series":      series_roll.get("home_ortg_rolling_series"),
            "away_ortg_rolling_series":      series_roll.get("away_ortg_rolling_series"),
            "home_pace_rolling_series":      series_roll.get("home_pace_rolling_series"),
            "away_pace_rolling_series":      series_roll.get("away_pace_rolling_series"),
            "home_pts_rolling_series":       series_roll.get("home_pts_rolling_series"),
            "away_pts_rolling_series":       series_roll.get("away_pts_rolling_series"),
            # Rest (Change 5)
            "playoff_days_rest_home":        playoff_days_rest_home,
            "playoff_days_rest_away":        playoff_days_rest_away,
        })

        # ── Segment overlay (Phase 3) ────────────────────────────────────────
        try:
            from nba.segment_overlay import classify_segments, apply_overlay
            seg_ctx = {
                "home_pace": home_state["pace"],
                "away_pace": away_state["pace"],
                "b2b_flag_home": b2b_away,  # b2b_away in the code refers to away_b2b flag
                "b2b_home": sched.get("home_b2b", 0),
                "home_ortg": home_state["ortg"],
                "away_ortg": away_state["ortg"],
                "edge": edge,
            }
            # Check if home team is actually on b2b
            # The variable names in this pipeline: b2b_away is the away team's b2b flag
            # Need to check home team b2b
            seg_ctx["b2b_flag_home"] = sched.get("home_b2b", 0)
            seg_result = classify_segments(seg_ctx)
            original_conf = game_results[-1]["confidence"]
            final_conf, overlay_applied = apply_overlay(
                original_conf, lean, seg_result,
                tier_names=(CONF_LOW, CONF_MEDIUM, CONF_HIGH),
            )
            game_results[-1]["confidence"] = final_conf
            game_results[-1]["overlay_applied"] = overlay_applied
            game_results[-1]["overlay_segment"] = seg_result.get("overlay_segment")
            game_results[-1]["original_confidence"] = original_conf
            if overlay_applied:
                logger.info(f"  🎯 Overlay: {original_conf}→{final_conf} ({seg_result['overlay_segment']})")
        except ImportError:
            game_results[-1]["overlay_applied"] = False
            game_results[-1]["overlay_segment"] = None
            game_results[-1]["original_confidence"] = game_results[-1]["confidence"]
        except Exception as e:
            logger.debug(f"  Overlay error (non-fatal): {e}")
            game_results[-1]["overlay_applied"] = False
            game_results[-1]["overlay_segment"] = None
            game_results[-1]["original_confidence"] = game_results[-1]["confidence"]

    # ── Step 8b: Archetype matchup flags ────────────────────────────────────
    _flag_archetype_matchups(game_results, game_date)

    # ── Step 8c: Shot profile matchup flags ──────────────────────────────────
    _flag_shot_profile(game_results, game_date)

    # ── Step 8d: Venue interaction flags (Board 4) ───────────────────────────
    _flag_venue_signal(game_results, game_date)

    # ── Step 9: Print card ────────────────────────────────────────────────────
    print_nba_card(game_results, game_date)

    # ── Step 10: Pushover ─────────────────────────────────────────────────────
    from nba.modules.notify import send_nba_card
    try:
        send_nba_card(game_results, game_date)
    except Exception as e:
        logger.warning(f"Pushover failed (non-fatal): {e}")

    # ── Step 11: Save projections ─────────────────────────────────────────────
    save_projections(game_results, game_date)

    logger.info(f"NBA run complete: {len(game_results)} games projected")
    return game_results


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA Totals Model — Phase 7")
    parser.add_argument("date", nargs="?", default=None,
                        help="Game date YYYY-MM-DD (default: today)")
    parser.add_argument("--no-odds",       action="store_true",
                        help="Skip The Odds API")
    parser.add_argument("--skip-results",  action="store_true",
                        help="Skip previous night's results grading")
    args = parser.parse_args()
    run(
        game_date=args.date,
        use_odds=not args.no_odds,
        skip_results=args.skip_results,
    )
