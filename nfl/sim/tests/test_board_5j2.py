#!/usr/bin/env python3
"""
Phase 5J-2 — board-layer tests.

(a) A book-quoted line equal to a rung (e.g. 9.5) with sim_p > 0.95
    is still priced.  FAILS on 9b1e09b (the rung loop skips it for
    sim_p > 0.95, and the book-line loop skips it because
    bline in rung_lines).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_book_quoted_rung_not_dropped(monkeypatch, tmp_path):
    """Synthetic RB with book lines at 13.5 (non-rung) and 9.5 (rung,
    sim_p > 0.95).  Both must appear in the board with
    sim_p == mean(carries >= k).  FAILS on 9b1e09b."""
    from nfl.sim import run_week

    N = 1000
    # 980 sims with 14 carries, 20 with 8 carries
    # P(carries >= 10) = 980/1000 = 0.98  (> 0.95, rung 9.5)
    # P(carries >= 14) = 980/1000 = 0.98  (non-rung 13.5)
    carries = np.array([14] * 980 + [8] * 20, dtype=float)

    player_df = pd.DataFrame({
        "sim_id": np.arange(N),
        "player_id": "RB01",
        "player_name": "Test Runner",
        "position": "RB",
        "team": "DAL",
        "targets": 0.0,
        "carries": carries,
        "receptions": 0.0,
        "rec_yds": 0.0,
        "rush_yds": 50.0,
        "anytime_td": 0.0,
    })

    rng = np.random.default_rng(42)
    team_df = pd.DataFrame({
        "home_score": rng.integers(10, 30, N),
        "away_score": rng.integers(10, 30, N),
    })

    game_results = [{
        "home": "DAL", "away": "PHI",
        "team_df": team_df, "player_df": player_df,
        "spread": -3.0, "total": 45.0,
        "converged": True, "source": "test",
    }]

    # Synthetic props: two rush_attempts lines for our RB
    props_df = pd.DataFrame([
        {"player_name": "Test Runner", "market_key": "player_rush_attempts",
         "line": 9.5, "over_price": -110, "under_price": -110,
         "implied_over": 0.524, "implied_under": 0.524,
         "pull_batch": "test", "pull_timestamp": "2026-09-20T15:00:00Z",
         "bookmaker": "hardrockbet_fl", "home_team": "Dallas Cowboys",
         "away_team": "Philadelphia Eagles", "snapshot_tag": "close"},
        {"player_name": "Test Runner", "market_key": "player_rush_attempts",
         "line": 13.5, "over_price": -120, "under_price": 100,
         "implied_over": 0.545, "implied_under": 0.500,
         "pull_batch": "test", "pull_timestamp": "2026-09-20T15:00:00Z",
         "bookmaker": "hardrockbet_fl", "home_team": "Dallas Cowboys",
         "away_team": "Philadelphia Eagles", "snapshot_tag": "close"},
    ])

    # Point ROOT at tmp_path so open-snapshot scan finds nothing
    monkeypatch.setattr(run_week, "ROOT", tmp_path)
    out_base = tmp_path / "nfl" / "data" / "sim" / "outputs"
    out_base.mkdir(parents=True)
    monkeypatch.setattr(run_week, "OUT_BASE", out_base)

    monkeypatch.setattr(run_week, "load_calibration", lambda: {})
    monkeypatch.setattr(run_week, "_check_calibration_stamp",
                        lambda cal_path=None: (True, []))
    monkeypatch.setattr(run_week, "load_props_for_game",
                        lambda *a, **kw: (props_df, "close", "2026-09-20T15:00:00Z"))
    monkeypatch.setattr(run_week, "is_player_name", lambda n: True)
    monkeypatch.setattr(run_week, "resolve_player",
                        lambda name, s, w, teams, *a: ("RB01", "exact"))

    _board_text, all_legs = run_week.build_board(
        week=2, game_results=game_results, lines_used={},
        team_game_counts={"DAL": 5, "PHI": 5},
        roster=pd.DataFrame(), roster_lookups=({}, {}, {}),
        pull_ts_str="test",
    )

    rush_legs = [l for l in all_legs if l["family"] == "rush_attempts"]
    rush_lines = {l["line"] for l in rush_legs}

    assert 9.5 in rush_lines, (
        f"Book-quoted rung 9.5 missing from rush legs. Present: {rush_lines}")
    assert 13.5 in rush_lines, (
        f"Book-quoted non-rung 13.5 missing from rush legs. Present: {rush_lines}")

    # Verify sim_p == mean(carries >= k) for both
    for leg in rush_legs:
        if leg["line"] in (9.5, 13.5):
            k = int(leg["line"]) + 1
            expected = round(float((carries >= k).mean()), 4)
            assert leg["sim_p"] == expected, (
                f"Line {leg['line']}: sim_p={leg['sim_p']} != expected {expected}")
