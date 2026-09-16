"""Phase 5A-10 tests — scoring-event composition: the exact-differential two-point table
(D35) and the PAT uniform reuse (D36).

Tolerances are the acceptance spec; a failing test is reported red, never widened.
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import nfl.sim.engine as E  # noqa: E402
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings  # noqa: E402
from nfl.sim.seed_util import stable_seed  # noqa: E402

TABLES = ROOT / "nfl" / "data" / "sim" / "tables"

# Measured 2021-2024 regular season (phase5a10 report)
ACT_P_M3 = 0.1454                 # P(|final margin| = 3)
ACT_P_M3_GIVEN_3COMP = 0.713      # P(|m| = 3 | equal TD counts and a one-FG difference)
ACT_XP_MAKE = 0.9491

SAMPLE_GAMES = [("KC", "BUF", 2023, 6), ("PHI", "DAL", 2022, 10), ("SF", "SEA", 2024, 12),
                ("DET", "GB", 2023, 4), ("BAL", "CIN", 2022, 14), ("MIA", "NYJ", 2024, 8),
                ("LA", "ARI", 2023, 12), ("MIN", "CHI", 2022, 6), ("TB", "ATL", 2024, 15),
                ("DEN", "LV", 2023, 17), ("CLE", "PIT", 2022, 2), ("HOU", "IND", 2024, 5)]


@pytest.fixture(scope="module")
def ratings():
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    return dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)


def _td(r):
    return r[0] if isinstance(r, tuple) else r


# ── T1: the two-point table is an exact-differential grid with the real decisions ──

def test_t1_twopt_table_exact_grid():
    t = pd.read_parquet(TABLES / "twopt_decision.parquet")
    assert set(t.period) == {"Q1-3", "Q4+"} and len(t) == 2 * 33
    assert set(t.sd_post) == set(range(-16, 17))
    q4 = t[t.period == "Q4+"].set_index("sd_post").p_2pt
    # the decisions the old 7-bucket table smeared (measured: -2, -5, +1, -10 ~100%; -3, -7 ~0%)
    assert q4[-2] > 0.9 and q4[-5] > 0.9 and q4[1] > 0.9 and q4[-10] > 0.9
    assert q4[-3] < 0.1 and q4[-7] < 0.1 and q4[-4] < 0.1 and q4[0] < 0.1
    q13 = t[t.period == "Q1-3"].set_index("sd_post").p_2pt
    assert q13[6] < 0.05 and q13[-1] < 0.05


# ── T2: PAT uniforms are their own draws (D36) ────────────────────────────────

def test_t2_xp_make_rate_is_the_measured_rate(ratings):
    """With the 2-pt decision switched off, every TD is followed by an XP; the make
    rate must be the measured league rate, not the u_pat-conditioned one (~0.938)."""
    home, away, season, week = SAMPLE_GAMES[0]
    saved = E._CACHE["twopt"].copy()
    try:
        z = saved.copy(); z["p_2pt"] = 0.0
        E._CACHE["twopt"] = z
        r = _td(simulate_game(home, away, season, week, n_sims=3000, seed=stable_seed("5a10_t2"),
                              drive_log=True, **ratings))
    finally:
        E._CACHE["twopt"] = saved
    dl = r.attrs["drive_log"]
    td = dl[dl.points.isin([6, 7])]
    make = (td.points == 7).mean()
    scal = json.loads((TABLES / "scalars.json").read_text())
    assert abs(make - scal["xp_rate"]) <= 0.01, f"XP make rate {make:.4f} vs measured {scal['xp_rate']:.4f}"
    src = (ROOT / "nfl" / "sim" / "engine.py").read_text()
    assert "made = m_xp & (u_xp < xp_prob)" in src and "u_2pt < twopt_conv_rate" in src


# ── T3: acceptance on the 12-game sample, N=500 ──────────────────────────────

@pytest.fixture(scope="module")
def sample(ratings):
    teams, comps = [], []
    for home, away, season, week in SAMPLE_GAMES:
        r = _td(simulate_game(home, away, season, week, n_sims=500,
                              seed=stable_seed(f"5a10_{season}_{week}_{away}_{home}"), drive_log=True, **ratings))
        dl = r.attrs["drive_log"]
        c = dl.assign(td=(dl.points >= 6).astype(int), fg=(dl.result == "FG_made").astype(int)) \
              .groupby(["sim_id", "team"])[["td", "fg"]].sum().unstack("team")
        c.columns = [f"{a}_{b}" for a, b in c.columns]
        c["m"] = r.home_score.to_numpy()[c.index] - r.away_score.to_numpy()[c.index]
        teams.append(r); comps.append(c)
    return pd.concat(teams, ignore_index=True), pd.concat(comps, ignore_index=True)


def test_t3_key_number_three(sample):
    t, _ = sample
    m = (t.home_score - t.away_score).abs()
    p3 = float((m == 3).mean())
    assert abs(p3 - ACT_P_M3) <= 0.035, f"P(|m|=3) {p3:.3f} vs actual {ACT_P_M3}"


def test_t3_three_composition_lands_on_three(sample):
    _, c = sample
    k = (c.td_0 == c.td_1) & ((c.fg_0 - c.fg_1).abs() == 1)
    p = float((c[k].m.abs() == 3).mean())
    assert abs(p - ACT_P_M3_GIVEN_3COMP) <= 0.10, f"P(|m|=3 | equal TDs, one FG apart) {p:.3f} vs actual {ACT_P_M3_GIVEN_3COMP}"
