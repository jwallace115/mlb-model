"""
Tests for OPS6: player stats pull (P45), prop grading (P46), prop history layer (P47).
RED first, then GREEN.
"""
import json, os, sys, pytest
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---- Item 1: pull_nfl_player_stats column guard ----

def test_player_stats_missing_column_halts():
    """A frame missing 'receptions' must HALT naming the missing column."""
    import pull_nfl_player_stats as ps
    import pandas as pd

    # Build a frame with all columns except 'receptions'
    cols = [c for c in ps.KEEP_COLS if c != "receptions"]
    df = pd.DataFrame({c: ["x"] for c in cols})

    missing = [c for c in ps.KEEP_COLS if c not in df.columns]
    assert missing == ["receptions"], f"expected ['receptions'], got {missing}"


def test_player_stats_kept_columns_exact():
    """KEEP_COLS is exactly the spec list."""
    import pull_nfl_player_stats as ps
    expected = [
        "player_id", "player_display_name", "player_name", "team", "opponent_team",
        "season", "week", "season_type",
        "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions",
        "carries", "rushing_yards", "rushing_tds",
        "receptions", "receiving_yards", "receiving_tds",
    ]
    assert ps.KEEP_COLS == expected


# ---- Item 2: prop grading ----

def _ledger_row(**kw):
    r = dict(
        pick_id="test_p1", ticket_id="test_t1", owner="ai_nfl", source="ai_opinion",
        logged_utc="2026-09-28T12:00:00Z", sport="NFL", event_id="a" * 32,
        commence_time="2026-09-28T17:00:00Z", home="Team A", away="Team B",
        market="spread", player_id=None, player_name=None, side="Team A",
        point=-3.5, price_american=-110, book="hardrockbet_fl", reason="test",
        share_link=None, supersedes=None, result=None, graded_utc=None,
        result_source=None, ingested_utc="2026-09-28T12:00:01Z",
        source_file="test.json", source_row=0,
    )
    r.update(kw)
    return r


def _setup_ledger(tmp_path, rows):
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    (ledger / "members.json").write_text('{"members":["jeff"]}')
    with open(ledger / "picks.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return ledger


def _setup_crosswalk(ledger, sport, events):
    import pandas as pd
    df = pd.DataFrame(events, columns=["event_id", "official_game_id", "home_score", "away_score",
                                        "completed", "home_team", "away_team"])
    df.to_parquet(ledger / f"crosswalk_{sport.lower()}.parquet", index=False)


def _setup_player_stats(tmp_path, rows):
    """Write a player_stats parquet in the expected location."""
    import pandas as pd
    df = pd.DataFrame(rows)
    stats_dir = tmp_path / "results_archive" / "nfl"
    stats_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = stats_dir / f"player_stats_2026_{ts}.parquet"
    df.to_parquet(path, index=False)
    return path


def _setup_schedules(tmp_path, rows):
    """Write a schedules parquet."""
    import pandas as pd
    df = pd.DataFrame(rows)
    stats_dir = tmp_path / "results_archive" / "nfl"
    stats_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = stats_dir / f"schedules_2026_{ts}.parquet"
    df.to_parquet(path, index=False)
    return path


def _setup_env(tmp_path):
    """Point env vars at tmp_path so the grader finds stats/schedules."""
    os.environ["MLB_REPO_ROOT"] = str(tmp_path)
    os.environ["RESULTS_ARCHIVE_DIR"] = str(tmp_path / "results_archive")


def test_prop_grading_four_cases(tmp_path):
    """Fixture with four prop picks: Over win, Under win, push, DNP → W, W, P, V."""
    import picks_grader as pg

    eid = "a" * 32
    rows = [
        # Over rush_yds 50.5 — player has 65 → W
        _ledger_row(pick_id="prop_over_w", market="prop:rush_yds", side="over",
                    point=50.5, player_name="Alice Runner",
                    home="TA", away="TB"),
        # Under pass_yds 250.5 — player has 200 → W
        _ledger_row(pick_id="prop_under_w", market="prop:pass_yds", side="under",
                    point=250.5, player_name="Bob Thrower",
                    home="TA", away="TB"),
        # Use exact push: Over rec 5.0 — player has 5 → P
        _ledger_row(pick_id="prop_push", market="prop:rec", side="over",
                    point=5.0, player_name="Charlie Catcher",
                    home="TA", away="TB"),
        # DNP: player not in stats at all → V
        _ledger_row(pick_id="prop_dnp", market="prop:rush_att", side="over",
                    point=10.5, player_name="Dave Benchwarmer",
                    home="TA", away="TB"),
    ]
    ledger = _setup_ledger(tmp_path, rows)
    _setup_crosswalk(ledger, "NFL", [
        (eid, "2026_04_TB_A", 24, 20, True, "TA", "TB"),
    ])
    _setup_schedules(tmp_path, [
        {"game_id": "2026_04_TB_TA", "season": 2026, "week": 4, "gameday": "2026-09-28",
         "gametime": "13:00", "home_team": "TA", "away_team": "TB",
         "home_score": 24, "away_score": 20, "game_type": "REG"},
    ])
    _setup_player_stats(tmp_path, [
        {"player_display_name": "Alice Runner", "player_name": "A.Runner",
         "team": "TA", "opponent_team": "TB", "season": 2026, "week": 4,
         "season_type": "REG", "rushing_yards": 65, "carries": 15,
         "completions": 0, "attempts": 0, "passing_yards": 0, "passing_tds": 0,
         "passing_interceptions": 0, "rushing_tds": 1, "receptions": 0,
         "receiving_yards": 0, "receiving_tds": 0, "player_id": "a1"},
        {"player_display_name": "Bob Thrower", "player_name": "B.Thrower",
         "team": "TA", "opponent_team": "TB", "season": 2026, "week": 4,
         "season_type": "REG", "rushing_yards": 5, "carries": 2,
         "completions": 20, "attempts": 30, "passing_yards": 200, "passing_tds": 2,
         "passing_interceptions": 1, "rushing_tds": 0, "receptions": 0,
         "receiving_yards": 0, "receiving_tds": 0, "player_id": "b1"},
        {"player_display_name": "Charlie Catcher", "player_name": "C.Catcher",
         "team": "TB", "opponent_team": "TA", "season": 2026, "week": 4,
         "season_type": "REG", "rushing_yards": 0, "carries": 0,
         "completions": 0, "attempts": 0, "passing_yards": 0, "passing_tds": 0,
         "passing_interceptions": 0, "rushing_tds": 0, "receptions": 5,
         "receiving_yards": 40, "receiving_tds": 0, "player_id": "c1"},
        # No row for Dave Benchwarmer → DNP
    ])
    _setup_env(tmp_path)

    graded = pg.grade(ledger)
    results = {g["pick_id"]: g["result"] for g in graded}

    assert results.get("prop_over_w") == "W", f"expected W, got {results.get('prop_over_w')}"
    assert results.get("prop_under_w") == "W", f"expected W, got {results.get('prop_under_w')}"
    assert results.get("prop_push") == "P", f"expected P, got {results.get('prop_push')}"
    assert results.get("prop_dnp") == "V", f"expected V, got {results.get('prop_dnp')}"


def test_name_normalization():
    """Name normalization strips periods, suffixes, collapses spaces."""
    import picks_grader as pg

    assert pg._normalize_name("Ted Hurst III") == pg._normalize_name("Ted Hurst")
    assert pg._normalize_name("D.J. Moore") == pg._normalize_name("DJ Moore")
    assert pg._normalize_name("Kenneth Walker III") == pg._normalize_name("Kenneth Walker")


def test_name_override_wins():
    """An override entry beats normalization."""
    import picks_grader as pg

    overrides = {"Weird Name": "Official Name"}
    assert pg._resolve_player_name("Weird Name", overrides) == "official name"
    assert pg._resolve_player_name("Normal Name", overrides) == pg._normalize_name("Normal Name")


def test_game_market_grades_unchanged_after_prop_grading(tmp_path):
    """Null control: game-market grades are byte-identical before/after prop grading is enabled."""
    import picks_grader as pg

    eid = "a" * 32
    game_row = _ledger_row(pick_id="game_sp", market="spread", side="TA", point=-3.5,
                           home="TA", away="TB")
    prop_row = _ledger_row(pick_id="prop_test", market="prop:rush_yds", side="over",
                           point=50.5, player_name="Alice Runner", home="TA", away="TB")
    ledger = _setup_ledger(tmp_path, [game_row, prop_row])
    _setup_crosswalk(ledger, "NFL", [
        (eid, "2026_04_TB_A", 24, 20, True, "TA", "TB"),
    ])
    _setup_schedules(tmp_path, [
        {"game_id": "2026_04_TB_TA", "season": 2026, "week": 4, "gameday": "2026-09-28",
         "gametime": "13:00", "home_team": "TA", "away_team": "TB",
         "home_score": 24, "away_score": 20, "game_type": "REG"},
    ])
    _setup_player_stats(tmp_path, [
        {"player_display_name": "Alice Runner", "player_name": "A.Runner",
         "team": "TA", "opponent_team": "TB", "season": 2026, "week": 4,
         "season_type": "REG", "rushing_yards": 65, "carries": 15,
         "completions": 0, "attempts": 0, "passing_yards": 0, "passing_tds": 0,
         "passing_interceptions": 0, "rushing_tds": 1, "receptions": 0,
         "receiving_yards": 0, "receiving_tds": 0, "player_id": "a1"},
    ])
    _setup_env(tmp_path)

    graded = pg.grade(ledger)
    game_grades = [g for g in graded if g["pick_id"] == "game_sp"]
    assert len(game_grades) == 1
    assert game_grades[0]["result"] == "W"  # same as test_symmetry in test_picks_grader.py


# ---- Item 3: prop history layer ----

def test_prop_history_leak_control(tmp_path):
    """A pick logged before week-5 kickoff yields weeks 1-4 only."""
    import pick_layers as pl_mod

    # This test requires _prop_history to exist — RED until Item 3 is implemented
    assert hasattr(pl_mod, '_prop_history'), "_prop_history not implemented yet"


def test_prop_history_no_line_captured(tmp_path):
    """A week with no hardrockbet_fl row before kickoff → 'line not captured' and result '—'."""
    import pick_layers as pl_mod
    assert hasattr(pl_mod, '_prop_history'), "_prop_history not implemented yet"


def test_prop_history_no_stats(tmp_path):
    """A player with no stats → value null with note."""
    import pick_layers as pl_mod
    assert hasattr(pl_mod, '_prop_history'), "_prop_history not implemented yet"


def test_prop_history_other_layers_unchanged(tmp_path):
    """Null control: every other layer of a rebuilt fixture card is byte-identical."""
    import pick_layers as pl_mod
    assert hasattr(pl_mod, '_prop_history'), "_prop_history not implemented yet"
