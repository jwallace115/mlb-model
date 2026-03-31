"""
Phase 5 — Simulation layer.

Wraps the Ridge point forecast in a Monte Carlo simulation to produce
probability estimates and confidence intervals.

Design principles
-----------------
1. Simulation mean is anchored exactly to the Ridge point forecast — the
   model's central estimate is not adjusted by this layer.
2. Baseline variance comes from training residuals (σ = RESIDUAL_SIGMA ≈ 18.62 pts),
   confirmed approximately normal (Shapiro-Wilk p = 0.16 on 2022-24).
3. Variance is a first-class parameter: any caller can override it per game
   (e.g. high combined 3PA rate, high FT rate, rivalry/playoff context).
   This is the intended extension point for matchup-specific variance in later phases.
4. The simulation architecture, not the analytical formula, is the foundation.
   P(over) = 1 − Φ((line − pred) / σ) is recovered as a special case of the
   simulation with n_iter → ∞, but the simulation can support non-normal
   distributions and joint-game scenarios that the formula cannot.

Framing note
------------
The compressed prediction range (pred σ ≈ 6.5 pts vs actual σ ≈ 20 pts) is
a limitation of the current rolling-average feature structure, not a fundamental
ceiling. The residual σ used here correctly reflects the true uncertainty —
the simulation does NOT use the narrow predicted range as its variance.
Structural improvements to features in later phases may allow matchup-specific
variance estimation that narrows uncertainty selectively.
"""

import logging

import numpy as np
import pandas as pd

from nba.config import (
    RESIDUAL_SIGMA,
    SIMULATION_N_ITER,
)

logger = logging.getLogger(__name__)

# Divergence threshold: flag any game where sim_mean and pred_total differ by
# more than this. Should be near zero for large n_iter; large gaps indicate a
# bug in the simulation setup.
# At n_iter=10,000 and σ=18.62, SE of the sample mean ≈ 0.186 pts.
# A 0.5 pt flag fires ~3.5σ away from zero — expected ~2–3 times per 3,690 games
# by chance. Raising to 1.0 pt (5.4σ) keeps only genuine bugs.
_DIVERGENCE_FLAG = 1.0   # pts


def simulate_game(
    pred_total: float,
    line: float,
    sigma: float = RESIDUAL_SIGMA,
    n_iter: int = SIMULATION_N_ITER,
    rng: np.random.Generator = None,
) -> dict:
    """
    Monte Carlo simulation for a single game total.

    Parameters
    ----------
    pred_total : Ridge point forecast — simulation mean is anchored here.
    line       : Reference line for over/under classification (rolling_league_avg).
    sigma      : Std dev of residual distribution. Defaults to global training σ.
                 Override this per game for matchup-specific variance estimates.
    n_iter     : Number of Monte Carlo draws.
    rng        : Optional numpy random Generator for reproducibility.

    Returns
    -------
    dict with keys:
      pred_total  : echo of input (the Ridge forecast)
      line        : echo of input (the reference line)
      sigma_used  : the sigma actually applied (useful when overridden per game)
      sim_mean    : mean of simulated totals — should be within ~0.1 pts of pred_total
      sim_std     : std of simulated totals — should be ≈ sigma
      p_over      : P(simulated total > line)
      p_under     : P(simulated total < line)
      p_push      : P(simulated total == line) — effectively 0 for continuous draws
      ci_80_low   : 10th percentile of simulated totals
      ci_80_high  : 90th percentile of simulated totals
      ci_80_width : ci_80_high − ci_80_low
      divergence  : |sim_mean − pred_total| (flag if > 0.5 pts)
    """
    if rng is None:
        rng = np.random.default_rng()

    draws = rng.normal(loc=pred_total, scale=sigma, size=n_iter)

    sim_mean = float(draws.mean())
    sim_std  = float(draws.std())
    p_over   = float((draws > line).mean())
    p_under  = float((draws < line).mean())
    p_push   = float((draws == line).mean())   # ≈ 0 for continuous
    ci_low   = float(np.percentile(draws, 10))
    ci_high  = float(np.percentile(draws, 90))
    div      = abs(sim_mean - pred_total)

    return {
        "pred_total":  round(pred_total, 2),
        "line":        round(line, 2),
        "sigma_used":  round(sigma, 4),
        "sim_mean":    round(sim_mean, 4),
        "sim_std":     round(sim_std, 4),
        "p_over":      round(p_over, 6),
        "p_under":     round(p_under, 6),
        "p_push":      round(p_push, 6),
        "ci_80_low":   round(ci_low, 2),
        "ci_80_high":  round(ci_high, 2),
        "ci_80_width": round(ci_high - ci_low, 2),
        "divergence":  round(div, 4),
    }


def simulate_games(
    predictions: pd.DataFrame,
    pred_col: str = "pred_total",
    line_col: str = "rolling_league_avg",
    sigma: float = RESIDUAL_SIGMA,
    per_game_sigma: pd.Series = None,
    n_iter: int = SIMULATION_N_ITER,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Run simulation across all games in a predictions DataFrame.

    Parameters
    ----------
    predictions    : DataFrame containing at minimum pred_col and line_col.
    pred_col       : Column name for Ridge point forecast.
    line_col       : Column name for the reference line (rolling_league_avg).
    sigma          : Default residual sigma — applied to all games unless
                     per_game_sigma is provided.
    per_game_sigma : Optional Series indexed identically to predictions with
                     per-game sigma overrides. Missing values fall back to sigma.
                     This is the intended hook for matchup-specific variance.
    n_iter         : Monte Carlo draws per game.
    seed           : Random seed for full reproducibility.

    Returns
    -------
    Original DataFrame with simulation columns appended:
      sim_mean, sim_std, p_over, p_under, ci_80_low, ci_80_high,
      ci_80_width, sigma_used, divergence
    """
    rng = np.random.default_rng(seed)

    results = []
    n_flagged = 0

    for idx, row in predictions.iterrows():
        pred = float(row[pred_col])
        line = float(row[line_col])

        # Per-game sigma override — falls back to global default if not provided
        if per_game_sigma is not None and idx in per_game_sigma.index:
            game_sigma = float(per_game_sigma.loc[idx])
            if np.isnan(game_sigma):
                game_sigma = sigma
        else:
            game_sigma = sigma

        result = simulate_game(pred, line, sigma=game_sigma, n_iter=n_iter, rng=rng)

        if result["divergence"] > _DIVERGENCE_FLAG:
            logger.warning(
                f"Row {idx}: sim_mean divergence = {result['divergence']:.4f} pts "
                f"(pred={pred:.2f}, sim_mean={result['sim_mean']:.4f}) — "
                f"exceeds flag threshold of {_DIVERGENCE_FLAG} pts"
            )
            n_flagged += 1

        results.append(result)

    if n_flagged > 0:
        logger.warning(f"simulate_games: {n_flagged} game(s) flagged for sim_mean divergence > {_DIVERGENCE_FLAG} pts")
    else:
        logger.info(f"simulate_games: {len(predictions)} games simulated — all sim_means within {_DIVERGENCE_FLAG} pts of pred_total")

    sim_df = pd.DataFrame(results, index=predictions.index)

    # Merge simulation columns back — drop redundant echo columns
    out = predictions.copy()
    for col in ["sim_mean", "sim_std", "p_over", "p_under", "p_push",
                "ci_80_low", "ci_80_high", "ci_80_width", "sigma_used", "divergence"]:
        out[col] = sim_df[col]

    return out
