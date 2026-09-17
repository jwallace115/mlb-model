"""Phase 5A-6 tests — end-of-half field-goal decision, Q2<2 clock bucket, and
Kaplan-Meier goal-line censoring in the yardage tables.

Tolerances below are the acceptance spec. A failing test is reported red; it is
never widened. Runtime ~2 min.
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
from nfl.sim.tables import _km_quantiles, QUANTILE_POINTS  # noqa: E402
from nfl.sim.seed_util import stable_seed  # noqa: E402

TABLES = ROOT / "nfl" / "data" / "sim" / "tables"

# Measured 2021-2024 regular season (see phase5a6 report), per game unless noted.
ACT_NON4TH_FG_PER_GAME = 0.33
ACT_OFF_TDS_PER_GAME = 4.73
ACT_COMP_TD_RATE = {"0-5": 0.843, "5-10": 0.527, "10-20": 0.214}
ACT_RUSH_TD_RATE = {"0-5": 0.431, "5-10": 0.126, "10-20": 0.048}
ACT_Q2LATE_PASS_RATE = 0.80   # last 2:00 of Q2, all score states 0.77-0.85

SAMPLE_GAMES = [("KC", "BUF", 2023, 6), ("PHI", "DAL", 2022, 10), ("SF", "SEA", 2024, 12),
                ("DET", "GB", 2023, 4), ("BAL", "CIN", 2022, 14), ("MIA", "NYJ", 2024, 8),
                ("LA", "ARI", 2023, 12), ("MIN", "CHI", 2022, 6), ("TB", "ATL", 2024, 15),
                ("DEN", "LV", 2023, 17), ("CLE", "PIT", 2022, 2), ("HOU", "IND", 2024, 5)]


@pytest.fixture(scope="module")
def ratings():
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    return dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)


def _team_df(r):
    return r[0] if isinstance(r, tuple) else r


# ── T1: the table exists and is empirical ─────────────────────────────────────

def test_t1_eoh_table_populated():
    t = pd.read_parquet(TABLES / "eoh_fg_decision.parquet")
    assert {"state", "sec_b", "yl_b", "n", "p_fg"} <= set(t.columns)
    assert (t["n"] >= 30).all(), "min-cell rule violated"
    assert t["p_fg"].between(0, 1).all()
    useful = t[(t.state == "fg_useful") & (t.yl_b == "all")]
    assert set(useful.sec_b) == {"0-3", "4-6", "7-10", "11-20", "21-40"}
    # Football sanity from the data itself: kick rate falls as seconds rise; leaders never kick
    p = useful.set_index("sec_b")["p_fg"]
    assert p["0-3"] > p["4-6"] > p["7-10"] > p["11-20"] >= p["21-40"]
    lead = t[t.state == "Q4_lead"]
    assert (lead["p_fg"] == 0).all()


# ── T2: the table is live (perturbation changes the output) ──────────────────

def test_t2_eoh_table_is_live(ratings):
    home, away, season, week = SAMPLE_GAMES[0]
    seed = stable_seed("5a6_t2")
    r = _team_df(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
    n_with = int(r["ev_fg_non4th"].sum())
    assert n_with > 0, "no end-of-half FG attempts on downs 1-3 at all"
    saved = E._CACHE["eoh_fg"].copy()
    saved_fgs = E._CACHE["fg_setup"].copy() if E._CACHE.get("fg_setup") is not None else None
    try:
        z = saved.copy(); z["p_fg"] = 0.0
        E._CACHE["eoh_fg"] = z
        if saved_fgs is not None:  # 5A-11 (D40): OT sudden-death kicks on downs 1-3 share the counter
            zf = saved_fgs.copy(); zf["p_fg"] = 0.0
            E._CACHE["fg_setup"] = zf
        r0 = _team_df(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
        assert int(r0["ev_fg_non4th"].sum()) == 0
        assert abs(float(r0["ev_fg_att"].mean()) - float(r["ev_fg_att"].mean())) > 0.02
    finally:
        E._CACHE["eoh_fg"] = saved
        if saved_fgs is not None:
            E._CACHE["fg_setup"] = saved_fgs


# ── T3: Q2<2 bucket is present in both tables and wired in the engine ────────

def test_t3_q2late_bucket_present_and_live(ratings):
    pc = pd.read_parquet(TABLES / "playcall_xpass.parquet")
    fd = pd.read_parquet(TABLES / "fourth_down.parquet")
    assert pc["bucket"].str.contains("Q2<2").sum() >= 40
    assert (fd["qtr_b"] == "Q2<2").sum() >= 50
    # Late-Q2 pass rate in the table is the measured two-minute-drill rate
    late = pc[pc["bucket"].str.contains("Q2<2") & ~pc["bucket"].str.contains("_c_")]
    w = np.average(late["pass_rate"], weights=late["n"])
    assert abs(w - ACT_Q2LATE_PASS_RATE) < 0.05, f"table Q2<2 pass rate {w:.3f}"
    # Perturb: zero every Q2<2 pass rate -> fewer pass plays in the game
    home, away, season, week = SAMPLE_GAMES[1]
    seed = stable_seed("5a6_t3")
    r = _team_df(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
    saved = E._CACHE["playcall"].copy()
    try:
        z = saved.copy()
        z.loc[z["bucket"].str.contains("Q2<2"), "pass_rate"] = 0.0
        E._CACHE["playcall"] = z
        r0 = _team_df(simulate_game(home, away, season, week, n_sims=2000, seed=seed, **ratings))
        assert float(r["ev_pass_plays"].mean()) - float(r0["ev_pass_plays"].mean()) > 2.0
    finally:
        E._CACHE["playcall"] = saved


# ── T4: Kaplan-Meier censoring — estimator and tables ────────────────────────

def test_t4_km_recovers_uncensored_distribution():
    rng = np.random.default_rng(0)
    n = 20000
    true = rng.integers(0, 10, n)            # true gains uniform on 0..9
    yl = rng.choice([5, 10], n)              # half the plays are snapped from the 5
    rec = np.minimum(true, yl)               # recorded gain is censored at the goal line
    cens = (rec >= yl) & (rec > 0)
    q = _km_quantiles(rec, yl, cens)
    assert q[50] == 5.0 and q[90] == 9.0, f"KM q50={q[50]} q90={q[90]}"
    assert np.quantile(rec, 0.9) < 9.0       # the naive estimator is biased low


def test_t4_tables_carry_censoring_and_unbias_red_zone():
    for name in ("pass_outcomes", "rush_outcomes"):
        t = pd.read_parquet(TABLES / f"{name}.parquet")
        assert "n_censored" in t.columns
        rz = t[t["zone"] == "rz10"]
        assert (rz["n_censored"] > 0).all()
        # 90th percentile of a successful red-zone play now reaches the goal line
        # from anywhere in the zone (was capped at ~the zone's own recorded gains)
        q90 = np.array([np.array(x)[90] for x in rz["yds_success_q"]])
        assert (q90 >= 10).mean() >= 0.8, f"{name} rz10 q90: {q90}"


# ── T5: acceptance — per-play TD rates by yardline and TDs per game ──────────

@pytest.fixture(scope="module")
def sample_runs(ratings):
    E._DEBUG_YDS = []
    tds = []
    for home, away, season, week in SAMPLE_GAMES:
        r = _team_df(simulate_game(home, away, season, week, n_sims=500,
                                   seed=stable_seed(f"5a6_{season}_{week}_{away}_{home}"), **ratings))
        tds.append(float(r["ev_td_long"].mean() + r["ev_td_short"].mean()))
    rec = E._DEBUG_YDS
    E._DEBUG_YDS = None
    return rec, float(np.mean(tds))


def _td_rate_by_bin(rec, kind):
    y = np.concatenate([a[1] for a in rec if a[0] == kind])
    yl = np.concatenate([a[2] for a in rec if a[0] == kind])
    td = (y >= yl) & (y > 0)
    out = {}
    for label, lo, hi in (("0-5", 0, 5), ("5-10", 5, 10), ("10-20", 10, 20)):
        m = (yl > lo) & (yl <= hi)
        out[label] = float(td[m].mean())
    return out


def test_t5_completion_td_rate_by_yardline(sample_runs):
    rec, _ = sample_runs
    got = _td_rate_by_bin(rec, "pass")
    for k, v in ACT_COMP_TD_RATE.items():
        assert abs(got[k] - v) <= 0.08, f"completions {k}: sim {got[k]:.3f} vs actual {v:.3f}"


def test_t5_rush_td_rate_by_yardline(sample_runs):
    rec, _ = sample_runs
    got = _td_rate_by_bin(rec, "rush")
    for k, v in ACT_RUSH_TD_RATE.items():
        assert abs(got[k] - v) <= 0.08, f"rushes {k}: sim {got[k]:.3f} vs actual {v:.3f}"


def test_t5_offensive_tds_per_game(sample_runs):
    _, tds = sample_runs
    assert abs(tds - ACT_OFF_TDS_PER_GAME) <= 0.5, f"offensive TDs/game {tds:.2f} vs {ACT_OFF_TDS_PER_GAME}"
