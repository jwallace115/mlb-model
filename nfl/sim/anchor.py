#!/usr/bin/env python3
"""
NFL Sim Phase 3 — D7 market anchoring.

Solves additive EPA offsets (delta_home, delta_away) so that the sim's mean
margin and total match the market closing lines. Uses the D6 EPA-shift channel
(same mechanism for research and live).

Market lines:
  Backtest: PBP spread_line and total_line (nflfastR consensus CLOSING lines).
  Live: Hard Rock pre-kickoff line, fallback consensus median.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed

ROOT = Path(__file__).resolve().parent.parent.parent


def _run_sim(home, away, season, week, n_sims, seed,
             epa_h=0.0, epa_a=0.0, with_players=True, **kw):
    """Run engine and return (mean_margin, mean_total, team_df, player_df)."""
    result = simulate_game(
        home, away, season, week, n_sims=n_sims, seed=seed,
        epa_home_offset=epa_h, epa_away_offset=epa_a, **kw)
    if isinstance(result, tuple):
        team_df, player_df = result
    else:
        team_df, player_df = result, None
    margin = (team_df["home_score"] - team_df["away_score"]).mean()
    total = (team_df["home_score"] + team_df["away_score"]).mean()
    return margin, total, team_df, player_df


def estimate_jacobian(n_sims=500, n_games=50, seed=99):
    """Estimate the 2x2 Jacobian ∂(margin,total)/∂(δh,δa) from a sample.

    Returns J_inv (2x2 numpy array).
    """
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)

    pbp = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / "pbp_2024.parquet")
    games = pbp.drop_duplicates("game_id")[
        ["game_id", "season", "week", "home_team", "away_team"]
    ].copy()
    games = games[games["week"] <= 18].head(n_games)

    eps = 0.5  # perturbation in yards/play
    dm_dh, dt_dh, dm_da, dt_da = [], [], [], []

    for _, g in games.iterrows():
        s = stable_seed((g["game_id"], 42))
        m0, t0, _, _ = _run_sim(g["home_team"], g["away_team"],
                                 g["season"], int(g["week"]),
                                 n_sims, s, 0, 0, False, **kw)
        mh, th, _, _ = _run_sim(g["home_team"], g["away_team"],
                                 g["season"], int(g["week"]),
                                 n_sims, s, eps, 0, False, **kw)
        ma, ta, _, _ = _run_sim(g["home_team"], g["away_team"],
                                 g["season"], int(g["week"]),
                                 n_sims, s, 0, eps, False, **kw)
        dm_dh.append((mh - m0) / eps)
        dt_dh.append((th - t0) / eps)
        dm_da.append((ma - m0) / eps)
        dt_da.append((ta - t0) / eps)

    J = np.array([[np.mean(dm_dh), np.mean(dm_da)],
                  [np.mean(dt_dh), np.mean(dt_da)]])
    J_inv = np.linalg.inv(J)
    print(f"Jacobian (50-game estimate):\n{J}")
    print(f"J_inv:\n{J_inv}")
    return J_inv


def anchor_game(home, away, season, week, market_spread, market_total,
                n_sims=1000, seed=42, J_inv=None, max_iter=4,
                with_players=True, **kw):
    """Anchor a single game to market lines.

    market_spread: home-team spread (negative = home favored).
    market_total: closing total line.

    Returns dict with keys:
      team_df, player_df, offsets (δh, δa), iterations, converged,
      raw_margin, raw_total, anchored_margin, anchored_total.
    """
    # nflfastR spread_line: positive = home favored (expected home margin).
    # Verified: corr(spread_line, home_score-away_score) = +0.50 on 2024 data.
    # These are CLOSING consensus lines.
    market_margin = market_spread  # home - away expected

    if J_inv is None:
        # Default from calibration: ~6 pts per yard/play offset
        J_inv = np.array([[0.081, 0.081],
                          [-0.081, 0.081]])

    dh, da = 0.0, 0.0

    for it in range(max_iter):
        m, t, team_df, player_df = _run_sim(
            home, away, season, week, n_sims, seed,
            dh, da, with_players, **kw)

        margin_err = market_margin - m
        total_err = market_total - t

        if it == 0:
            raw_margin, raw_total = m, t

        if abs(margin_err) < 0.5 and abs(total_err) < 1.0:
            return {
                "team_df": team_df, "player_df": player_df,
                "offsets": (dh, da), "iterations": it + 1,
                "converged": True,
                "raw_margin": raw_margin, "raw_total": raw_total,
                "anchored_margin": m, "anchored_total": t,
                "market_margin": market_margin, "market_total": market_total,
            }

        step = J_inv @ np.array([margin_err, total_err])
        dh += step[0]
        da += step[1]

    # Final run with last offsets
    m, t, team_df, player_df = _run_sim(
        home, away, season, week, n_sims, seed,
        dh, da, with_players, **kw)

    return {
        "team_df": team_df, "player_df": player_df,
        "offsets": (dh, da), "iterations": max_iter,
        "converged": abs(market_margin - m) < 0.25 and abs(market_total - t) < 0.5,
        "raw_margin": raw_margin, "raw_total": raw_total,
        "anchored_margin": m, "anchored_total": t,
        "market_margin": market_margin, "market_total": market_total,
    }


def get_market_lines(season, week, game_id=None):
    """Get closing spread and total for a game.

    Backtest (2021-2025): PBP spread_line and total_line (nflfastR CLOSING consensus).
    Live (2026): Hard Rock pre-kickoff from line_history, fallback consensus median.

    Returns (spread, total) or (None, None) if unavailable.
    """
    if season <= 2025:
        pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{season}.parquet"
        if not pbp_path.exists():
            return None, None
        df = pd.read_parquet(pbp_path,
                             columns=["game_id", "spread_line", "total_line"])
        df = df.drop_duplicates("game_id")
        if game_id:
            row = df[df["game_id"] == game_id]
        else:
            return None, None
        if row.empty:
            return None, None
        return float(row.iloc[0]["spread_line"]), float(row.iloc[0]["total_line"])

    # 2026: live lines from odds archive
    hist_dir = ROOT / "data" / "odds_archive" / "nfl" / "line_history" / f"season={season}"
    if not hist_dir.exists():
        return None, None
    # Implementation for live: read latest pre-kickoff snapshot
    # Placeholder — would need game-specific lookup
    return None, None
