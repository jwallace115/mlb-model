"""Phase 5A-8 tests — close-game diagnostic instrumentation and the late-game
4th-down decision spec.

Tolerances are the acceptance spec; a failing test is reported red, never widened.
T3 and T4 were RED on the 5A-8 engine by design: they encode the defect 5A-8 found
(4th-down fallback keys never matched the table's level-2/3 rows, so late-Q4 decisions
pooled leaders with trailers) and are the acceptance spec for the 5A-9 fix (D30-D33).
"""
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
from nfl.sim.close_game_diagnostic import sd_bucket, RESULT_MAP_SIM  # noqa: E402

TABLES = ROOT / "nfl" / "data" / "sim" / "tables"

# Measured 2021-2024 regular season (phase5a8 report), drives starting in Q4 with <= 5:00
ACT_PUNT_TRAIL4_8 = 0.037     # P(drive ends in a punt | offence trailing by 4-8 at drive start)
ACT_PUNT_TRAIL1_3 = 0.046
ACT_DOWNS_LEAD1_8 = 0.021     # P(turnover on downs | offence leading by 1-8)
ACT_FG_TIED = 0.251           # P(FG made | tied at drive start)
ACT_TD_TIED = 0.048

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


# ── T1: snapshot instrumentation is populated and observation-only ───────────

def test_t1_q4_snapshots_populated(ratings):
    home, away, season, week = SAMPLE_GAMES[0]
    seed = stable_seed("5a8_t1")
    r = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
    for c in ("m_q4_300", "m_q4_120", "poss_q4_300", "poss_q4_120", "yl_q4_120"):
        assert c in r.columns
    assert (r["m_q4_300"] != -999).all()
    # a single play's runoff can carry the clock from >120 s to <= 0 (clock-table q100 = 118 s
    # before pace); measured 5 of 543,500 sims in K1 — anything beyond 0.1% is a regression
    assert (r["m_q4_120"] == -999).mean() <= 0.001
    assert set(np.unique(r["poss_q4_300"])) <= {0, 1}
    assert (r["yl_q4_120"].between(1, 99)).all()
    # the 2:00 margin can only differ from the 5:00 margin by scoring in between
    d = (r["m_q4_120"] - r["m_q4_300"]).abs()
    assert d.max() <= 30
    # seed-identity with the same call: the snapshot code draws no random numbers
    r2 = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
    assert np.array_equal(r["home_score"], r2["home_score"]) and np.array_equal(r["m_q4_120"], r2["m_q4_120"])


def test_t1_drive_log_has_exact_score_state(ratings):
    home, away, season, week = SAMPLE_GAMES[1]
    r = _td(simulate_game(home, away, season, week, n_sims=300, seed=stable_seed("5a8_t1b"),
                          drive_log=True, **ratings))
    dl = r.attrs["drive_log"]
    assert {"sd_start", "opp_points"} <= set(dl.columns)
    # sd_start is the exact differential behind the coarse score_state label
    lab = np.where(dl.sd_start <= -9, "trail9+", np.where(dl.sd_start <= -1, "trail1-8",
          np.where(dl.sd_start == 0, "tied", np.where(dl.sd_start <= 8, "lead1-8", "lead9+"))))
    assert (lab == dl.score_state.to_numpy()).all()
    assert (dl.opp_points >= 0).all() and (dl.opp_points <= 8).all()
    # defensive points only occur on turnover / safety drives, or a punt returned for a TD
    assert dl[dl.opp_points > 0].result.isin(["turnover_int", "turnover_fumble", "safety", "punt"]).all()


# ── T3: the 4th-down table is a complete grid and the engine's keys are the builder's ──

def test_t3_fourth_down_table_is_complete_and_keyed_by_the_shared_function():
    """5A-8 found the old fallback levels 2/3 unreachable (builder prefixed the grouped
    columns, the engine looked up unprefixed keys) so 52% of Q4 and 99% of OT decisions
    used the coarsest cell. 5A-9 (D30) replaced the chain with a complete fine grid and one
    shared key function; this test is the spec for that."""
    from nfl.sim.tables import (fourth_down_keys, FD_YD_LABELS, FD_YL_LABELS, FD_SC_LABELS,
                                FD_CK_LABELS)
    fd = pd.read_parquet(TABLES / "fourth_down.parquet")
    assert len(fd) == len(FD_YD_LABELS) * len(FD_YL_LABELS) * len(FD_SC_LABELS) * len(FD_CK_LABELS)
    keys = set(zip(fd.ydstogo_b, fd.yl_b, fd.score_b, fd.qtr_b))
    assert len(keys) == len(fd), "duplicate cells"
    assert not fd.yl_b.str.contains("_").any() and not fd.score_b.str.startswith(("c_", "z_", "zc_")).any()
    assert np.allclose(fd[["p_go", "p_punt", "p_fg"]].sum(axis=1), 1.0)
    # every key the engine can construct exists: sweep the state space
    rng = np.random.default_rng(0)
    n = 20000
    yd = rng.integers(1, 30, n); y = rng.integers(1, 100, n); sd = rng.integers(-30, 31, n)
    q = rng.integers(1, 7, n); cl = rng.uniform(0, 900, n)
    k = fourth_down_keys(yd, y, sd, q, cl)
    missing = [t for t in zip(*k) if t not in keys]
    assert not missing, f"{len(missing)} engine keys without a cell, e.g. {missing[:3]}"
    assert (ROOT / "nfl" / "data" / "sim" / "tables" / "fourth_down_meta.json").exists()
    src = (ROOT / "nfl" / "sim" / "engine.py").read_text()
    assert "fourth_down_keys(" in src and "zc_" not in src.split("def simulate_game")[1].split("# 5A-3: Team 4th-down GOE")[0]


# ── T4: late-game 4th-down behaviour on the 12-game sample (spec for 5A-9) ───

@pytest.fixture(scope="module")
def late_drives(ratings):
    frames = []
    for home, away, season, week in SAMPLE_GAMES:
        r = _td(simulate_game(home, away, season, week, n_sims=500,
                              seed=stable_seed(f"5a8_{season}_{week}_{away}_{home}"),
                              drive_log=True, **ratings))
        dl = r.attrs["drive_log"]
        frames.append(dl[(dl.start_quarter == 4) & (dl.start_clock <= 300)])
    d = pd.concat(frames, ignore_index=True)
    d["res"] = d["result"].map(RESULT_MAP_SIM)
    d["state"] = sd_bucket(d.sd_start)
    return d


def test_t4_trailing_offence_does_not_punt_late(late_drives):
    d = late_drives
    p48 = (d[d.state == "trail4-8"].res == "punt").mean()
    p13 = (d[d.state == "trail1-3"].res == "punt").mean()
    assert p48 <= ACT_PUNT_TRAIL4_8 + 0.08, f"trail4-8 punt rate {p48:.3f} vs actual {ACT_PUNT_TRAIL4_8}"
    assert p13 <= ACT_PUNT_TRAIL1_3 + 0.08, f"trail1-3 punt rate {p13:.3f} vs actual {ACT_PUNT_TRAIL1_3}"


def test_t4_leading_offence_does_not_go_late(late_drives):
    d = late_drives
    k = d.state.isin(["lead1-3", "lead4-8"])
    downs = (d[k].res == "downs").mean()
    assert downs <= ACT_DOWNS_LEAD1_8 + 0.05, f"leading offence turnover-on-downs rate {downs:.3f} vs actual {ACT_DOWNS_LEAD1_8}"


def test_t4_tied_offence_kicks_not_scores_late(late_drives):
    d = late_drives[late_drives.state == "tied"]
    fg = (d.res == "FG_made").mean(); td = (d.res == "TD").mean()
    assert abs(fg - ACT_FG_TIED) <= 0.08, f"tied-drive FG rate {fg:.3f} vs actual {ACT_FG_TIED}"
    assert td <= ACT_TD_TIED + 0.05, f"tied-drive TD rate {td:.3f} vs actual {ACT_TD_TIED}"
