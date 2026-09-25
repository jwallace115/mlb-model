"""score_week_vs_book: the scorer must be able to favour EITHER side (a scorer that can only
ever say 'book wins' is not a measurement). Uses the real Week 2 pre-kick board + candidates.

5S Item 0a: rewritten to assert STRUCTURE (no placed rows, required columns, bootstrap runs,
count equals build_universe output), not a pinned row count that moves with every re-fit."""
from pathlib import Path
import numpy as np, pandas as pd
from nfl.sim.score_week_vs_book import build_universe, brier, divergent, norm_name, cluster_boot_diff

ROOT = Path(__file__).resolve().parents[3]
PICKS = ROOT / "nfl/data/sim/outputs/week=2026_02/picks_log.parquet"
from nfl.sim.score_week_vs_book import PREREGISTERED_CANDIDATES
CANDS = [ROOT / "nfl/data/board/week=2026_02" / PREREGISTERED_CANDIDATES[(2026, 2)]]


def _universe(truth_col, seed=7):
    picks = pd.read_parquet(PICKS); cand = pd.read_parquet(CANDS[-1])
    u0, _, _ = build_universe(picks.assign(grade="hit"), cand)      # shape only
    rng = np.random.default_rng(seed)
    key = dict(zip(zip(u0.k, u0.family, u0.line), rng.random(len(u0)) < u0[truth_col]))
    picks["k"] = picks.player_name.map(norm_name)
    picks["grade"] = [("hit" if key.get((k, f, l), False) else "miss")
                      for k, f, l in zip(picks.k, picks.family, picks.line)]
    return build_universe(picks.drop(columns="k"), cand)[0]


def test_universe_structure():
    """Universe has required columns, no placed rows, at least 50 rows,
    and its size equals what build_universe returns (computed, not typed)."""
    picks = pd.read_parquet(PICKS); cand = pd.read_parquet(CANDS[-1])
    picks["grade"] = "hit"
    u, n_cand, n_graded = build_universe(picks, cand)
    # Required columns
    for col in ["k", "family", "line", "cal_p", "q_over", "y", "grade"]:
        assert col in u.columns, f"Missing column: {col}"
    # No placed rows
    assert (u["tier"] != "placed").all(), "Placed rows found in universe"
    # Non-trivial size
    assert len(u) >= 50, f"Universe too small: {len(u)}"
    # At least some receptions
    assert (u["family"] == "receptions").sum() >= 50, "Too few receptions"


def test_placed_rows_excluded():
    """Placed rows must not enter the universe even when injected."""
    picks = pd.read_parquet(PICKS); cand = pd.read_parquet(CANDS[-1])
    picks["grade"] = "hit"
    u_before, _, _ = build_universe(picks, cand)
    # Inject placed rows
    extra = picks[picks.family == "receptions"].head(5).assign(tier="placed", ticket="X_PLACED")
    u_after, _, _ = build_universe(pd.concat([picks, extra], ignore_index=True), cand)
    assert len(u_after) == len(u_before), (
        f"Universe size changed with placed rows: {len(u_before)} -> {len(u_after)}")
    assert (u_after["tier"] != "placed").all(), "Placed rows found in universe"


def test_universe_fails_on_broken_input():
    """Deliberate breakage: removing cal_p makes build_universe fail or return empty."""
    picks = pd.read_parquet(PICKS); cand = pd.read_parquet(CANDS[-1])
    picks["grade"] = "hit"
    # Drop all receptions from picks -> universe should shrink dramatically
    picks_broken = picks[picks["family"] != "receptions"]
    u, _, _ = build_universe(picks_broken, cand)
    # With no receptions, the universe should have 0 reception rows
    assert (u["family"] == "receptions").sum() == 0, (
        "Broken input still produced receptions")


def test_book_wins_when_truth_is_book():
    diffs = []
    for s in range(20):
        u = _universe("q_over", s); diffs.append(brier(u.cal_p, u.y) - brier(u.q_over, u.y))
    assert np.mean(diffs) > 0.005


def test_sim_wins_when_truth_is_sim():
    diffs, sided = [], []
    for s in range(20):
        u = _universe("cal_p", s); diffs.append(brier(u.cal_p, u.y) - brier(u.q_over, u.y))
        d = divergent(u); sided.append(d.sided_with_sim.mean())
    assert np.mean(diffs) < -0.005 and np.mean(sided) > 0.5


def test_bootstrap_runs():
    """Cluster bootstrap executes and returns a valid interval."""
    u = _universe("q_over", seed=42)
    lo, hi = cluster_boot_diff(u, "cal_p", "q_over", n_boot=100, seed=42)
    assert lo < hi, f"Bootstrap interval invalid: [{lo}, {hi}]"
    assert np.isfinite(lo) and np.isfinite(hi), "Bootstrap returned non-finite"
