#!/usr/bin/env python3
"""
NBA Playoff Shadow Run — Change 10.

Retrospective analysis of 2024-25 NBA playoff games using the playoff mode
projection engine. Compares playoff mode projected totals to:
  1. Actual game totals
  2. Odds API historical closing lines (where available)

Reports:
  - MAE / bias by playoff round
  - Directional accuracy G1-2 / G3-4 / G5+  (blend weight ramp validation)
  - Blend weight ramp analysis (does more series data help?)
  - 5 sample games (series context + prediction vs actual)
  - RESIDUAL_SIGMA_PLAYOFF calibration check

Usage:
    python3 nba/playoff_shadow.py
    python3 nba/playoff_shadow.py --sigma 15.5     # override sigma
    python3 nba/playoff_shadow.py --season 2024    # different season (default: 2024)
    python3 nba/playoff_shadow.py --verbose        # show all games
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

import numpy as np
import pandas as pd
from datetime import date, timedelta

from nba.config import (
    CACHE_DIR,
    CURRENT_SEASON,
    RESIDUAL_SIGMA_PLAYOFF,
    PLAYOFF_MODE_VERSION,
    PLAYOFF_SERIES_BLEND_CAP,
    NBA_API_TIMEOUT,
)
from nba.modules.fetch_games import fetch_season, SEASON_TYPE_PLAYOFF, SEASON_TYPE_REGULAR

SEP  = "═" * 70
SEP2 = "─" * 70

ROUND_ORDER = ["First Round", "Conf Semis", "Conf Finals", "Finals"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _infer_round(matchup_rank: int) -> str:
    """Given 0-based series index (sorted by first game date), infer round label."""
    if matchup_rank < 8:
        return "First Round"
    if matchup_rank < 12:
        return "Conf Semis"
    if matchup_rank < 14:
        return "Conf Finals"
    return "Finals"


def _series_key(home: str, away: str) -> str:
    teams = sorted([home, away])
    return f"{teams[0]}_{teams[1]}"


def _build_series_index(playoff_games: pd.DataFrame) -> dict:
    """
    Returns {series_key: rank} sorted by first game date.
    Rank 0-7 = First Round, 8-11 = Conf Semis, 12-13 = Conf Finals, 14 = Finals.
    """
    if playoff_games.empty:
        return {}
    playoff_games = playoff_games.copy()
    playoff_games["date"] = pd.to_datetime(playoff_games["date"])
    first_dates = {}
    for _, row in playoff_games.iterrows():
        k = _series_key(row["home_team"], row["away_team"])
        d = row["date"]
        if k not in first_dates or d < first_dates[k]:
            first_dates[k] = d
    ranked = sorted(first_dates.items(), key=lambda x: x[1])
    return {k: i for i, (k, _) in enumerate(ranked)}


def _series_games_prior(home: str, away: str, game_date: pd.Timestamp,
                         playoff_games: pd.DataFrame) -> pd.DataFrame:
    """All completed playoff games between these two teams before game_date."""
    if playoff_games.empty:
        return pd.DataFrame()
    pg = playoff_games.copy()
    pg["date"] = pd.to_datetime(pg["date"])
    mask = (
        (
            ((pg["home_team"] == home) & (pg["away_team"] == away)) |
            ((pg["home_team"] == away) & (pg["away_team"] == home))
        ) &
        (pg["date"].dt.date < game_date.date())
    )
    return pg[mask].copy()


# ── Load historical lines ─────────────────────────────────────────────────────

def _load_historical_lines(season: int) -> dict:
    """
    Attempt to load historical closing lines from the Odds API snapshot cache.
    Returns {game_id: line} or empty dict if unavailable.
    """
    # Try parquet snapshot saved by sim/phase7_market.py or similar
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "sim", "data", f"lines_{season}.parquet"),
        os.path.join(os.path.dirname(__file__), "..", "sim", "data", "lines_2024.parquet"),
    ]
    for p in possible_paths:
        p = os.path.normpath(p)
        if os.path.exists(p):
            try:
                df = pd.read_parquet(p)
                if "game_id" in df.columns and "total" in df.columns:
                    return dict(zip(df["game_id"].astype(str), df["total"].astype(float)))
            except Exception:
                pass
    return {}


# ── Simulate projection for a single playoff game ─────────────────────────────

def _project_game(row: pd.Series, sigma: float,
                   playoff_games: pd.DataFrame,
                   series_index: dict,
                   reg_games: pd.DataFrame) -> dict | None:
    """
    Lightweight projection for a single completed playoff game.

    Uses the same logic as run_nba.py's playoff blending path but
    reads from the cached regular-season rolling averages rather than
    rebuilding full per-game state — appropriate for a shadow run.

    Returns dict with projection fields, or None if data insufficient.
    """
    try:
        from nba.run_nba import (
            _get_series_metadata,
            _build_series_rolling,
            _blend_playoff_features,
        )
        from nba.modules.model import simulate_total
    except ImportError as e:
        logging.getLogger(__name__).error(f"Import failed: {e}")
        return None

    game_date = pd.Timestamp(row["date"])
    home = row["home_team"]
    away = row["away_team"]
    actual_total = row.get("actual_total")

    if pd.isna(actual_total) or actual_total < 150:
        return None  # incomplete

    # Series metadata
    prior = _series_games_prior(home, away, game_date, playoff_games)
    n_prior = len(prior)
    w_playoff = min(n_prior, PLAYOFF_SERIES_BLEND_CAP) / PLAYOFF_SERIES_BLEND_CAP

    sk = _series_key(home, away)
    rank = series_index.get(sk, 99)
    rnd = _infer_round(rank)

    # Win counts
    home_wins = 0
    away_wins = 0
    for _, pg in prior.iterrows():
        winner = pg.get("home_team") if (pg.get("home_score", 0) or 0) > (pg.get("away_score", 0) or 0) else pg.get("away_team")
        if winner == home:
            home_wins += 1
        else:
            away_wins += 1

    # For the shadow run we use the league average as baseline projection
    # (we don't have per-team rolling state for 2024 without a full replay)
    # This gives us blend weight ramp validation with minimal infrastructure.
    # A full production run would call sim_project_game() with real state.
    baseline = row.get("rolling_league_avg", 228.5)
    if pd.isna(baseline):
        baseline = 228.5

    # Series rolling avg (if prior games exist)
    if n_prior > 0 and not prior.empty and "actual_total" in prior.columns:
        series_avg = prior["actual_total"].mean()
        if not pd.isna(series_avg):
            pred_total = (1 - w_playoff) * baseline + w_playoff * series_avg
        else:
            pred_total = baseline
    else:
        pred_total = baseline

    return {
        "game_date":         game_date.date().isoformat(),
        "home_team":         home,
        "away_team":         away,
        "actual_total":      float(actual_total),
        "pred_total":        round(pred_total, 2),
        "playoff_round":     rnd,
        "series_game_number": n_prior + 1,
        "home_series_wins":  home_wins,
        "away_series_wins":  away_wins,
        "n_prior":           n_prior,
        "w_playoff":         w_playoff,
        "baseline":          baseline,
    }


# ── Main analysis ─────────────────────────────────────────────────────────────

def run_shadow(season: int = 2024, sigma: float = RESIDUAL_SIGMA_PLAYOFF,
               verbose: bool = False) -> None:
    print(f"\n{SEP}")
    print(f"  NBA PLAYOFF SHADOW RUN — Season {season}-{str(season+1)[-2:]}")
    print(f"  Playoff Mode {PLAYOFF_MODE_VERSION}  ·  σ={sigma}")
    print(SEP)

    # Load completed playoff games for this season
    print(f"\n  Loading {season} playoff games...", end=" ", flush=True)
    playoff_games = fetch_season(season, SEASON_TYPE_PLAYOFF)
    if playoff_games.empty:
        print("NO DATA — cannot continue.")
        print(f"  Run fetch_season({season}, '{SEASON_TYPE_PLAYOFF}') first.")
        return

    # Filter to completed games (actual_total present)
    playoff_games["date"] = pd.to_datetime(playoff_games["date"])
    completed = playoff_games[
        playoff_games["actual_total"].notna() & (playoff_games["actual_total"] > 150)
    ].copy()
    print(f"{len(completed)} completed games found.")

    if completed.empty:
        print("  No completed playoff games available for this season.")
        return

    # Load regular season games for context
    reg_games = fetch_season(season, SEASON_TYPE_REGULAR)

    # Build series index (for round inference)
    series_index = _build_series_index(completed)

    # Load historical lines
    hist_lines = _load_historical_lines(season)
    print(f"  Historical lines loaded: {len(hist_lines)} games")

    # Project each game
    results = []
    for _, row in completed.sort_values("date").iterrows():
        proj = _project_game(row, sigma, completed, series_index, reg_games)
        if proj is None:
            continue
        # Attach historical line if available
        gid = str(row.get("game_id", ""))
        proj["hist_line"] = hist_lines.get(gid)
        results.append(proj)

    if not results:
        print("  No projections produced.")
        return

    df = pd.DataFrame(results)
    df["err"] = df["pred_total"] - df["actual_total"]
    df["abs_err"] = df["err"].abs()

    # ── Overall stats ──────────────────────────────────────────────────────────
    n       = len(df)
    mae     = df["abs_err"].mean()
    bias    = df["err"].mean()
    print(f"\n  Overall — {n} games  MAE={mae:.2f}  Bias={bias:+.2f}")

    # ── By round ──────────────────────────────────────────────────────────────
    print(f"\n  {'Round':<16} {'N':>4} {'MAE':>7} {'Bias':>7}")
    print(f"  {SEP2[:40]}")
    for rnd in ROUND_ORDER:
        sub = df[df["playoff_round"] == rnd]
        if len(sub) == 0:
            continue
        r_mae  = sub["abs_err"].mean()
        r_bias = sub["err"].mean()
        print(f"  {rnd:<16} {len(sub):>4} {r_mae:>7.2f} {r_bias:>+7.2f}")

    # ── By series game number (blend ramp) ────────────────────────────────────
    print(f"\n  Blend Ramp — accuracy by series game number")
    print(f"  {'G#':<6} {'N':>4} {'w_playoff':>10} {'MAE':>7} {'Bias':>7}")
    print(f"  {SEP2[:42]}")

    bucket_map = {1: "G1-2", 2: "G1-2", 3: "G3-4", 4: "G3-4", 5: "G5+", 6: "G5+", 7: "G5+"}
    df["bucket"] = df["series_game_number"].map(bucket_map).fillna("G5+")

    for gnum in sorted(df["series_game_number"].unique()):
        sub = df[df["series_game_number"] == gnum]
        avg_w = sub["w_playoff"].mean()
        r_mae = sub["abs_err"].mean()
        r_bias = sub["err"].mean()
        print(f"  G{gnum:<5} {len(sub):>4} {avg_w:>10.2f} {r_mae:>7.2f} {r_bias:>+7.2f}")

    # Bucket summary
    print(f"\n  Bucket summary:")
    for bucket in ["G1-2", "G3-4", "G5+"]:
        sub = df[df["bucket"] == bucket]
        if len(sub) == 0:
            continue
        avg_w  = sub["w_playoff"].mean()
        r_mae  = sub["abs_err"].mean()
        r_bias = sub["err"].mean()
        print(f"    {bucket}: n={len(sub):>3}  avg_w={avg_w:.2f}  MAE={r_mae:.2f}  Bias={r_bias:+.2f}")

    # ── Lines comparison (if available) ───────────────────────────────────────
    with_lines = df[df["hist_line"].notna()].copy()
    if len(with_lines) >= 5:
        with_lines["line_err"] = with_lines["hist_line"] - with_lines["actual_total"]
        print(f"\n  vs Market (closing lines available for {len(with_lines)} games):")
        print(f"    Model  MAE: {with_lines['abs_err'].mean():.2f}")
        print(f"    Market MAE: {with_lines['line_err'].abs().mean():.2f}")
        corr = np.corrcoef(with_lines["err"], with_lines["line_err"])[0, 1]
        print(f"    Error correlation (model vs market): {corr:.3f}")
    else:
        print(f"\n  Market lines: insufficient data ({len(with_lines)} games with closing lines)")

    # ── Sigma calibration ─────────────────────────────────────────────────────
    print(f"\n  Sigma calibration check (σ={sigma}):")
    # If sigma is well-calibrated, ~68% of actual totals should fall within pred ± sigma
    in_band = ((df["actual_total"] >= df["pred_total"] - sigma) &
               (df["actual_total"] <= df["pred_total"] + sigma)).mean()
    print(f"    % actuals within pred ± σ: {in_band*100:.1f}%  (target ~68%)")
    # Suggest sigma based on empirical std of errors
    emp_std = df["err"].std()
    print(f"    Empirical error std: {emp_std:.2f}  →  suggested σ ≈ {emp_std:.1f}")
    if abs(emp_std - sigma) > 2.0:
        print(f"    ⚠  Consider updating RESIDUAL_SIGMA_PLAYOFF from {sigma} → {emp_std:.1f}")
    else:
        print(f"    ✓  Current σ={sigma} is within 2 pts of empirical std")

    # ── 5 sample games ────────────────────────────────────────────────────────
    print(f"\n  Sample games (5 spread across series):")
    sample = df.sample(min(5, len(df)), random_state=42).sort_values("game_date")
    print(f"  {'Date':<12} {'Matchup':<24} {'G#':>3} {'Pred':>6} {'Actual':>7} {'Err':>6} {'Round'}")
    print(f"  {SEP2[:72]}")
    for _, r in sample.iterrows():
        matchup = f"{r['away_team']} @ {r['home_team']}"
        print(
            f"  {r['game_date']:<12} {matchup:<24} {int(r['series_game_number']):>3} "
            f"{r['pred_total']:>6.1f} {r['actual_total']:>7.1f} {r['err']:>+6.1f}  {r['playoff_round']}"
        )

    if verbose:
        print(f"\n{SEP2}")
        print("  All games:")
        print(f"  {'Date':<12} {'Matchup':<24} {'G#':>3} {'w':>5} {'Pred':>6} {'Actual':>7} {'Err':>6}")
        print(f"  {SEP2[:66]}")
        for _, r in df.sort_values(["playoff_round", "game_date"]).iterrows():
            matchup = f"{r['away_team']} @ {r['home_team']}"
            print(
                f"  {r['game_date']:<12} {matchup:<24} {int(r['series_game_number']):>3} "
                f"{r['w_playoff']:>5.2f} {r['pred_total']:>6.1f} {r['actual_total']:>7.1f} {r['err']:>+6.1f}"
            )

    print(f"\n{SEP}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NBA Playoff Shadow Run")
    parser.add_argument("--season", type=int, default=2024,
                        help="NBA season year (e.g. 2024 for 2024-25). Default: 2024")
    parser.add_argument("--sigma", type=float, default=RESIDUAL_SIGMA_PLAYOFF,
                        help=f"Residual sigma override. Default: {RESIDUAL_SIGMA_PLAYOFF}")
    parser.add_argument("--verbose", action="store_true",
                        help="Print all games, not just sample")
    args = parser.parse_args()
    run_shadow(season=args.season, sigma=args.sigma, verbose=args.verbose)


if __name__ == "__main__":
    main()
