"""score_week_vs_book: the scorer must be able to favour EITHER side (a scorer that can only
ever say 'book wins' is not a measurement). Uses the real Week 2 pre-kick board + candidates."""
from pathlib import Path
import numpy as np, pandas as pd
from nfl.sim.score_week_vs_book import build_universe, brier, divergent, norm_name

ROOT = Path(__file__).resolve().parents[3]
PICKS = ROOT / "nfl/data/sim/outputs/week=2026_02/picks_log.parquet"
CANDS = sorted((ROOT / "nfl/data/board/week=2026_02").glob("nfl_prop_candidates_*.parquet"))


def _universe(truth_col, seed=7):
    picks = pd.read_parquet(PICKS); cand = pd.read_parquet(CANDS[-1])
    u0, _, _ = build_universe(picks.assign(grade="hit"), cand)      # shape only
    rng = np.random.default_rng(seed)
    key = dict(zip(zip(u0.k, u0.family, u0.line), rng.random(len(u0)) < u0[truth_col]))
    picks["k"] = picks.player_name.map(norm_name)
    picks["grade"] = [("hit" if key.get((k, f, l), False) else "miss")
                      for k, f, l in zip(picks.k, picks.family, picks.line)]
    return build_universe(picks.drop(columns="k"), cand)[0]


def test_universe_matches_measured_coverage():
    u = _universe("q_over")
    assert len(u) == 146 and (u.family == "receptions").sum() == 138


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


def test_placed_rows_do_not_enter_the_universe():
    picks = pd.read_parquet(PICKS); cand = pd.read_parquet(CANDS[-1])
    picks["grade"] = "hit"
    extra = picks[picks.family == "receptions"].head(5).assign(tier="placed", ticket="X_PLACED")
    u, _, _ = build_universe(pd.concat([picks, extra], ignore_index=True), cand)
    assert len(u) == 146 and (u.tier != "placed").all()
