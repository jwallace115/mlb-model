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
    """(b) PIT@NE kicked at ~17:02Z.  With as_of=18:30Z the 180009Z snapshot
    has in-play lines (+13.5 / 36.5); get_lines_from_history must return the
    170007Z pre-kick line (+5.0 / 41.0).  IND@KC (00:20Z kick) is unkicked
    and gets 180009Z values.  Real-tape fixture."""
    from nfl.sim import run_week

    monkeypatch.setattr(run_week, "ROOT",
                        pit_ne_line_dir.parent.parent.parent.parent.parent)
    lines = run_week.get_lines_from_history(
        as_of=pd.Timestamp("2026-09-20T18:30:00Z"))

    # PIT@NE: pre-kick line from 170007Z
    assert "PIT@NE" in lines, f"PIT@NE missing. keys={list(lines)}"
    assert lines["PIT@NE"]["spread"] == 5.0, (
        f"PIT@NE spread {lines['PIT@NE']['spread']} != 5.0 (pre-kick)")
    assert lines["PIT@NE"]["total"] == 41.0, (
        f"PIT@NE total {lines['PIT@NE']['total']} != 41.0 (pre-kick)")
    assert "17:00:07" in lines["PIT@NE"]["line_snapshot_utc"], (
        f"PIT@NE snapshot {lines['PIT@NE']['line_snapshot_utc']} not from 170007Z")

    # IND@KC: unkicked, so 180009Z (newest pre-kick for that game)
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


def test_schedule_kickoff_timezone_accepts_pre_kick_qb(monkeypatch):
    """(d) A rank-1 QB dated 2026-09-24T22:00Z (6pm ET) is before the
    8:15pm ET Week 3 opener (= 00:15Z Sep 25).  The current code rejects it
    because it parses 20:15 ET as 20:15Z (4 h early).  FAILS on 15ec21c."""
    from nfl.sim import usage

    # Load the real depth chart and remove all QB rows for a test team (ARI)
    real_depth = pd.read_parquet(usage.PBP_DIR / "depth_charts.parquet")
    mask = (real_depth["team"] == "ARI") & (real_depth.get("pos_abb", pd.Series(dtype=str)) == "QB")
    depth_no_ari_qb = real_depth[~mask].copy()

    # Inject a fake rank-1 QB for ARI with dt = 2026-09-24T22:00Z
    fake_row = {
        "team": "ARI", "gsis_id": "00-FAKEWK3", "pos_abb": "QB",
        "pos_rank": 1, "dt": "2026-09-24T22:00:00+00:00",
        "position": "QB", "season": 2026, "week": 0,
        "club_code": "ARI", "depth_team": 1, "full_name": "Fake QB WK3",
    }
    depth = pd.concat([depth_no_ari_qb, pd.DataFrame([fake_row])], ignore_index=True)

    # Monkeypatch nflreadpy to use the offline fixture
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "nflverse_schedule_2026_wk123.parquet"
    fixture_df = pd.read_parquet(fixture_path)

    class FakeNflreadpy:
        @staticmethod
        def load_schedules(seasons):
            class _Wrapper:
                def __init__(self, df):
                    self._df = df
                def to_pandas(self):
                    return self._df
            return _Wrapper(fixture_df[fixture_df["season"].isin(seasons)])

    monkeypatch.setitem(sys.modules, "nflreadpy", FakeNflreadpy())

    starting = usage.derive_starting_qbs(depth, plays=None)
    wk3_ari = starting.get((2026, 3, "ARI"))

    assert wk3_ari is not None, (
        "No starter for (2026, 3, ARI) — fake QB at 22:00Z was rejected. "
        "Schedule kickoff timezone is still wrong (20:15 ET read as 20:15Z)."
    )
    assert wk3_ari["gsis_id"] == "00-FAKEWK3", (
        f"Wrong starter: {wk3_ari['gsis_id']}, expected 00-FAKEWK3"
    )
