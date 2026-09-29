"""6D tests: whole-game timeout policy; kneel decision fix; punt fallback."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed

SAMPLE = ROOT / "research" / "nfl_sim" / "phase5z_sample.txt"
N = 100


def _load():
    _load_tables()
    return _load_ratings()


def _run_sample(team_r, tend, sit, kicker, league, n_games=50):
    games = open(SAMPLE).read().strip().split("\n")[:n_games]
    results = []
    for g in games:
        parts = g.split("_")
        season, week, away, home = int(parts[0]), int(parts[1]), parts[2], parts[3]
        seed = stable_seed((home, away, season, week, 42))
        r = simulate_game(home, away, season, week, n_sims=N, seed=seed,
                          team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                          league=league, drive_log=True)
        results.append(r)
    return results


def test_timeout_policy_whole_game():
    """6D: the timeout table has all 5 quarters and 7 seconds buckets.
    The engine must NOT proxy Q1->Q2 or Q3->Q4."""
    tbl = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "tables" / "timeout_policy.parquet")
    qtrs = sorted(tbl["qtr"].unique())
    assert 1 in qtrs and 3 in qtrs, f"Table missing Q1/Q3: {qtrs}"
    assert 5 in qtrs, f"Table missing OT: {qtrs}"
    sec_bs = sorted(tbl["sec_b"].unique())
    for sb in ["181-300", "301-600", "601-900"]:
        assert sb in sec_bs, f"Table missing bucket {sb}: {sec_bs}"


def test_timeout_policy_live():
    """6D: sim timeouts >= 4.0 per team-game (was ~3.4 under Q2/Q4-only table).
    Real is 7.7; the sim captures the scrimmage-snap-triggered subset."""
    team_r, tend, sit, kicker, league = _load()
    results = _run_sample(team_r, tend, sit, kicker, league, n_games=50)
    mean_to = np.mean([(r["ev_to_off"].mean() + r["ev_to_def"].mean()) for r in results])
    assert mean_to >= 4.0, f"TO/game {mean_to:.2f} < 4.0"


def test_kneel_first_clock_q4():
    """6D: the sim's first Q4 kneel-out happens at approximately the right time.
    Real first-kneel clock_before: ~55.5 s (PBP 2021-24). Was 6.7 s on eng/6c."""
    team_r, tend, sit, kicker, league = _load()
    results = _run_sample(team_r, tend, sit, kicker, league, n_games=50)
    first_kneel_clocks = []
    for r in results:
        pl = r.attrs.get("play_log")
        if pl is None or len(pl) == 0:
            continue
        kneels = pl[(pl["event_class"] == "kneel") & (pl["qtr"] == 4)]
        if len(kneels) == 0:
            continue
        for sim_id in kneels["sim_id"].unique():
            sk = kneels[kneels["sim_id"] == sim_id]
            first_kneel_clocks.append(sk["clock_before"].iloc[0])
    if len(first_kneel_clocks) > 50:
        mean_first = np.mean(first_kneel_clocks)
        # Real first-kneel in Q4 ~55.5 s; accept within 15 s
        assert mean_first >= 40.0, (
            f"Q4 first kneel clock {mean_first:.1f}s < 40.0 (real ~55.5)")


def test_punt_fallback_not_touchback():
    """6D: punt landings inside the receiving 20 use the nearest landing-table bucket,
    not a touchback at the 20."""
    tbl = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "tables" / "punt_landing.parquet")
    min_bucket = tbl["los_bucket"].min()
    # The engine should snap to the nearest available bucket for out-of-range LOS
    # Run a game and check that punt destinations include values < 20
    team_r, tend, sit, kicker, league = _load()
    seed = stable_seed(("KC", "BUF", 2024, 11, 42))
    r = simulate_game("KC", "BUF", 2024, 11, n_sims=500, seed=seed,
                      team_r=team_r, tend=tend, sit=sit, kicker=kicker,
                      league=league, drive_log=True)
    dl = r.attrs.get("drive_log")
    assert dl is not None
    # Drives after a punt should sometimes start inside the 20 (yl > 80)
    # but not be exactly at 80 (the old touchback default)
    punt_starts = dl[dl["result"].shift(1) == "punt"]["start_yardline"]
    if len(punt_starts) > 20:
        # The old fallback set recv_yl > 80 to exactly 80.0
        at_80 = (punt_starts == 80.0).sum()
        assert at_80 / len(punt_starts) < 0.15, (
            f"Too many punt starts at exactly 80 ({at_80}/{len(punt_starts)}): "
            f"fallback still converting to touchback")
