"""Phase 5A-9 tests — endgame repair: 4th-down table rebuild (D30), EOH / FG-setup
runoff cells (D31, D33), the kneel-then-play defect (D32), FG-setup kneel, play call and
rush cells (D33).

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
from nfl.sim.tables import fourth_down_keys, fd_score_coarse, fg_setup_state, _mom_k  # noqa: E402

TABLES = ROOT / "nfl" / "data" / "sim" / "tables"

# Measured 2021-2024 regular season (phase5a9 report)
ACT_KNEELS = 1.51
ACT_LATE_Q4_SNAPS = 5.61
ACT_FGS_KNEEL_NEXT_SEC_MAX = 4.0     # every in-state kneel with <= 40 s left was followed by the kick at 1-4 s
ACT_TIED_REACHED_EXPIRE = 0.0        # 0 of 56 real tied drives that reached the 35 expired without a kick

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


# ── T1: the rebuilt 4th-down table ───────────────────────────────────────────

def test_t1_shared_keys_match_builder_buckets():
    yd, yl, sc, ck = fourth_down_keys([1, 3, 7, 12], [5, 45, 55, 95], [-10, -2, 0, 4], [1, 2, 4, 5], [500, 60, 100, 300])
    assert list(yd) == ["1-2", "3-5", "6-10", "11+"]
    assert list(yl) == ["opp1-10", "opp41-50", "own41-50", "own1-10"]
    assert list(sc) == ["trail9+", "trail1-3", "tied", "lead4-8"]
    assert list(ck) == ["Q1-3", "Q2<2", "Q4<2", "OT"]
    # coarse score grouping depends on field position (what the decision turns on)
    assert list(fd_score_coarse(["trail1-3", "tied", "trail1-3", "lead9+"], ["opp40", "rz", "own35", "midfield"])) == \
        ["fg_useful", "fg_useful", "trail", "lead"]


def test_t1_shrinkage_k_is_measured_not_chosen():
    meta = json.loads((TABLES / "fourth_down_meta.json").read_text())
    k = meta["k_by_level"]
    assert set(k) == {"0", "1", "2", "3", "4", "5", "6"}
    vals = [v for d in k.values() for v in d.values()]
    assert all(v >= 0 for v in vals) and any(np.isfinite(v) for v in vals)
    # method-of-moments sanity: identical children -> infinite k; wildly different -> small k
    assert np.isinf(_mom_k([100, 100, 100], [50, 50, 50], [0.5, 0.5, 0.5]))
    assert _mom_k([100, 100], [95, 5], [0.5, 0.5]) < 5


def test_t1_late_trailing_offence_goes_and_tied_offence_kicks():
    fd = pd.read_parquet(TABLES / "fourth_down.parquet").set_index(["ydstogo_b", "yl_b", "score_b", "qtr_b"])
    # trailing by 4-8, 4th-and-3-5 at midfield, last 2:00: go, not punt
    r = fd.loc[("3-5", "own41-50", "trail4-8", "Q4<2")]
    assert r.p_go > 0.6 and r.p_punt < 0.2
    # tied, 4th-and-6-10 at the opp 25, last 2:00: kick
    r = fd.loc[("6-10", "opp21-30", "tied", "Q4<2")]
    assert r.p_fg > 0.8
    # leading by 4-8, 4th-and-6-10 from own 30, last 5:00: punt
    r = fd.loc[("6-10", "own21-30", "lead4-8", "Q4_2-5")]
    assert r.p_punt > 0.9
    # OT cells exist and a tied offence at the opp 30 on 4th-and-1 does not punt
    r = fd.loc[("1-2", "opp21-30", "tied", "OT")]
    assert r.p_punt < 0.05


# ── T2: new tables are live (perturbation changes the output) ────────────────

def test_t2_fg_setup_tables_live(ratings):
    home, away, season, week = SAMPLE_GAMES[1]
    seed = stable_seed("5a9_t2")
    r = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
    assert float(r["ev_fgs_snaps"].mean()) > 0.1 and float(r["ev_fgs_runoff"].mean()) > 0.1
    assert float(r["ev_eoh_runoff"].mean()) > 0.5
    saved = E._CACHE["fg_setup"].copy()
    try:
        z = saved.copy(); z["pass_rate"] = 1.0; z["p_kneel"] = 0.0
        E._CACHE["fg_setup"] = z
        r0 = _td(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
        assert float(r0["ev_fgs_runs"].sum()) < float(r["ev_fgs_runs"].sum()) * 0.5
    finally:
        E._CACHE["fg_setup"] = saved


def test_t2_kneel_then_play_defect_is_gone(ratings):
    """D32: a kneel used to be followed by a scrimmage snap in the same iteration, so a
    3rd-down kneel became a 4th-down play without a decision (turnover on downs)."""
    home, away, season, week = SAMPLE_GAMES[0]
    r = _td(simulate_game(home, away, season, week, n_sims=2000, seed=stable_seed("5a9_t2b"),
                          drive_log=True, **ratings))
    dl = r.attrs["drive_log"]
    late_lead = dl[(dl.start_quarter == 4) & (dl.start_clock <= 300) & (dl.sd_start >= 1) & (dl.sd_start <= 8)]
    assert (late_lead.result == "downs").mean() <= 0.05, "leading late drives still end on downs"
    src = (ROOT / "nfl" / "sim" / "engine.py").read_text()
    assert "alive = ~game_over & ~can_kneel & ~spiked & (clock > 0)" in src


# ── T3: acceptance on the 12-game sample, N=500 ──────────────────────────────

@pytest.fixture(scope="module")
def sample(ratings):
    teams, drives = [], []
    for home, away, season, week in SAMPLE_GAMES:
        r = _td(simulate_game(home, away, season, week, n_sims=500,
                              seed=stable_seed(f"5a9_{season}_{week}_{away}_{home}"), drive_log=True, **ratings))
        dl = r.attrs["drive_log"]
        teams.append(r); drives.append(dl[(dl.start_quarter == 4) & (dl.start_clock <= 300)])
    return pd.concat(teams, ignore_index=True), pd.concat(drives, ignore_index=True)


def test_t3_kneels_and_late_snaps(sample):
    t, _ = sample
    assert abs(float(t.ev_kneels.mean()) - ACT_KNEELS) <= 0.3, f"kneels {t.ev_kneels.mean():.2f}"
    assert abs(float(t.ev_late_snaps_q4.mean()) - ACT_LATE_Q4_SNAPS) <= 0.6, f"late Q4 snaps {t.ev_late_snaps_q4.mean():.2f}"


def test_t3_tied_drives_that_reach_range_get_the_kick_off(sample):
    _, d = sample
    x = d[d.sd_start == 0]
    reached = (x.start_yardline - x.yards <= 35) | x.result.isin(["TD"]) | (x.end_yardline <= 35)
    xr = x[reached]
    expired = xr.result.isin(["end_game", "end_half"]).mean()
    assert expired <= ACT_TIED_REACHED_EXPIRE + 0.05, f"tied drives reaching the 35 that expire without a kick: {expired:.3f}"
