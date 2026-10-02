#!/usr/bin/env python3
"""
Phase 5J-2 — board-layer tests.

(a) A book-quoted line equal to a rung (e.g. 9.5) with sim_p > 0.95
    is still priced.  FAILS on 9b1e09b (the rung loop skips it for
    sim_p > 0.95, and the book-line loop skips it because
    bline in rung_lines).
(b) Pre-kick snapshot selection: PIT@NE with a post-kick snapshot at
    18:00Z and a pre-kick at 17:00Z — the pre-kick line (+5.0 / 41.0)
    is chosen, not the in-play line (+13.5 / 36.5). Real-tape fixture.
(c) --as-of props cap: props with pull_timestamp after as_of are excluded.
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


@pytest.fixture
def pit_ne_line_dir(tmp_path):
    """Two-snapshot tape: 170007Z (pre-kick) and 180009Z (post-kick)."""
    import shutil
    lh = tmp_path / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    lh.mkdir(parents=True)
    fix = Path(__file__).resolve().parent / "fixtures"
    shutil.copy(fix / "snap_pit_ne_prekick.parquet", lh / "snap_20260920T170007Z.parquet")
    shutil.copy(fix / "snap_pit_ne_postkick.parquet", lh / "snap_20260920T180009Z.parquet")
    return lh


def test_prekick_line_chosen_for_kicked_game(pit_ne_line_dir, monkeypatch):
    """(b) 5N rewrite: PIT@NE kicked at ~17:02Z. With as_of=18:30Z the game
    is ABSENT (commence <= as_of -> excluded by 5M). IND@KC (00:20Z, unkicked)
    still gets the 180009Z snapshot values. Real-tape fixture."""
    from nfl.sim import run_week

    monkeypatch.setattr(run_week, "ROOT",
                        pit_ne_line_dir.parent.parent.parent.parent.parent)
    lines = run_week.get_lines_from_history(
        as_of=pd.Timestamp("2026-09-20T18:30:00Z"))

    # PIT@NE: kicked before as_of -> ABSENT from the game set
    assert "PIT@NE" not in lines, (
        f"PIT@NE should be absent (kicked before as_of). Got: {lines.get('PIT@NE')}")

    # IND@KC: unkicked, so still present with 180009Z values
    assert "IND@KC" in lines, f"IND@KC missing. keys={list(lines)}"
    assert lines["IND@KC"]["total"] == 46.0


def test_as_of_caps_props(monkeypatch, tmp_path):
    """(c) load_props_for_game with as_of excludes rows with
    pull_timestamp > as_of."""
    from nfl.sim import run_week

    ts_early = "2026-09-20T09:00:00+00:00"
    ts_late = "2026-09-20T16:00:00+00:00"
    props = pd.DataFrame([
        {"player_name": "A", "market_key": "player_receptions",
         "line": 3.5, "over_price": -110, "under_price": -110,
         "implied_over": 0.52, "implied_under": 0.52,
         "pull_batch": "b1", "pull_timestamp": ts_early,
         "bookmaker": "hardrockbet_fl", "home_team": "Dallas Cowboys",
         "away_team": "Philadelphia Eagles", "snapshot_tag": "close"},
        {"player_name": "B", "market_key": "player_receptions",
         "line": 4.5, "over_price": -120, "under_price": 100,
         "implied_over": 0.55, "implied_under": 0.50,
         "pull_batch": "b2", "pull_timestamp": ts_late,
         "bookmaker": "hardrockbet_fl", "home_team": "Dallas Cowboys",
         "away_team": "Philadelphia Eagles", "snapshot_tag": "close"},
    ])

    # Write to props archive
    props_dir = (tmp_path / "data" / "odds_archive" / "nfl" / "props"
                 / "season=2026" / "week=02")
    props_dir.mkdir(parents=True)
    props.to_parquet(props_dir / "test_props.parquet", index=False)

    monkeypatch.setattr(run_week, "ROOT", tmp_path)

    # Without as_of: both rows
    df_all, _, _ = run_week.load_props_for_game(
        "Dallas Cowboys", "Philadelphia Eagles", 2026, 2)
    assert len(df_all) == 2, f"Expected 2 rows without as_of, got {len(df_all)}"

    # With as_of at 12:00Z: only the early row
    df_capped, _, _ = run_week.load_props_for_game(
        "Dallas Cowboys", "Philadelphia Eagles", 2026, 2,
        as_of=pd.Timestamp("2026-09-20T12:00:00Z"))
    assert len(df_capped) == 1, f"Expected 1 row with as_of=12:00Z, got {len(df_capped)}"
    assert df_capped.iloc[0]["player_name"] == "A"


def test_layer3_qb_cutoff_is_midnight_of_the_first_game_date(tmp_path, monkeypatch):
    """D272/D273/D274 supersede 5J-2 (d). 5J-2 gave a week WITHOUT play-by-play (the live week)
    the actual Eastern kickoff from a live schedule download, while the same week rebuilt
    later from PBP used midnight UTC of its first game date — live and backtest disagreed
    (audit #14). Now every week uses midnight UTC of the first game date, from the archived
    schedule snapshot for a week without PBP. The test owns its fixture (audit #16): PBP
    weeks 1-3 only, a full-season snapshot whose week-4 opener is 2026-10-01 (8:15pm ET).
    A rank-1 QB dated 2026-10-01T22:00Z (before the opener, after the cutoff) is rejected for
    week 4; the same row at 2026-09-30T23:00Z is used."""
    from nfl.sim.tests.test_fwd7a import _depth_world
    d, usage, rosters, injuries, depth = _depth_world(tmp_path, False)
    monkeypatch.setattr(usage, "PBP_DIR", d)
    assert sorted(pd.read_parquet(d / "pbp_2026.parquet")["week"].unique()) == [1, 2, 3]

    def _starter(dt):
        qb = depth.iloc[[0]].assign(gsis_id="00-FAKEWK4", position="QB", pos_abb="QB",
                                    pos_rank=1, dt=dt)
        return usage.derive_starting_qbs(pd.concat([depth, qb], ignore_index=True),
                                         plays=None).get((2026, 4, "KC"))

    late = _starter("2026-10-01T22:00:00+00:00")
    assert late is None or late["gsis_id"] != "00-FAKEWK4"
    early = _starter("2026-09-30T23:00:00+00:00")
    assert early is not None and early["gsis_id"] == "00-FAKEWK4"
