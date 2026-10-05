"""Gate tests for picks_grader.py — RED first, then GREEN."""
import json, os, sys, pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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
    """Write a crosswalk file: list of (event_id, official_game_id, home_score, away_score, completed)."""
    import pandas as pd
    df = pd.DataFrame(events, columns=["event_id", "official_game_id", "home_score", "away_score",
                                        "completed", "home_team", "away_team"])
    df.to_parquet(ledger / f"crosswalk_{sport.lower()}.parquet", index=False)


# Hand-computed results (BEFORE running the test):
# Team A (home) -3.5 spread: home wins 24-20 → margin = +4 → covers (W)
# Team B (away) +3.5 spread: away loses 20-24 → margin = -4 → does not cover (L)
# Over 44.5 total: 24+20 = 44 < 44.5 → Under wins (L for over)
# Under 44.5 total: → W
# Team A ML: home wins → W
# Team B ML: away loses → L
FIXTURE_HOME_SCORE = 24
FIXTURE_AWAY_SCORE = 20


# (a) symmetry: fixtures with both sides of one spread, one total and one ML
def test_symmetry_spread_total_ml(tmp_path):
    import picks_grader as pg
    eid = "a" * 32
    rows = [
        _ledger_row(pick_id="sp_home", market="spread", side="Team A", point=-3.5),
        _ledger_row(pick_id="sp_away", market="spread", side="Team B", point=3.5),
        _ledger_row(pick_id="tot_over", market="total", side="over", point=44.5),
        _ledger_row(pick_id="tot_under", market="total", side="under", point=44.5),
        _ledger_row(pick_id="ml_home", market="moneyline", side="Team A", point=None),
        _ledger_row(pick_id="ml_away", market="moneyline", side="Team B", point=None),
    ]
    ledger = _setup_ledger(tmp_path, rows)
    _setup_crosswalk(ledger, "NFL", [
        (eid, "2026_04_TB_A", FIXTURE_HOME_SCORE, FIXTURE_AWAY_SCORE, True, "Team A", "Team B"),
    ])
    graded = pg.grade(ledger)

    results = {g["pick_id"]: g["result"] for g in graded}
    # Spread: home -3.5, margin +4 → W; away +3.5, margin -4 → L
    assert results["sp_home"] == "W"
    assert results["sp_away"] == "L"
    # Or both P for push - here margin=4 vs line 3.5, no push
    assert {results["sp_home"], results["sp_away"]} == {"W", "L"}
    # Total: 44 < 44.5 → under wins
    assert results["tot_over"] == "L"
    assert results["tot_under"] == "W"
    assert {results["tot_over"], results["tot_under"]} == {"W", "L"}
    # ML: home wins
    assert results["ml_home"] == "W"
    assert results["ml_away"] == "L"


# (b) event_id not in crosswalk stays UNRESOLVED
def test_no_crosswalk_unresolved(tmp_path):
    import picks_grader as pg
    rows = [_ledger_row(pick_id="orphan", event_id="b" * 32)]
    ledger = _setup_ledger(tmp_path, rows)
    _setup_crosswalk(ledger, "NFL", [
        ("a" * 32, "2026_04_TB_A", 24, 20, True, "Team A", "Team B"),
    ])
    graded = pg.grade(ledger)
    assert len(graded) == 0  # no grade row emitted for unresolved


# (c) game not completed stays UNRESOLVED
def test_incomplete_game_unresolved(tmp_path):
    import picks_grader as pg
    eid = "a" * 32
    rows = [_ledger_row(pick_id="pending", event_id=eid)]
    ledger = _setup_ledger(tmp_path, rows)
    _setup_crosswalk(ledger, "NFL", [
        (eid, "2026_04_TB_A", None, None, False, "Team A", "Team B"),
    ])
    graded = pg.grade(ledger)
    assert len(graded) == 0


# (d) future commence_time is never graded
def test_future_commence_not_graded(tmp_path):
    import picks_grader as pg
    eid = "a" * 32
    rows = [_ledger_row(pick_id="future", event_id=eid,
                        commence_time="2099-12-31T23:00:00Z")]
    ledger = _setup_ledger(tmp_path, rows)
    _setup_crosswalk(ledger, "NFL", [
        (eid, "2026_04_TB_A", 24, 20, True, "Team A", "Team B"),
    ])
    graded = pg.grade(ledger)
    assert len(graded) == 0


# (e) two official games matching one event HALT the crosswalk
def test_ambiguous_crosswalk_halts(tmp_path):
    import event_crosswalk as xw
    import picks_ledger as pl
    # Two different official_game_ids for same event_id → HALT
    import pandas as pd
    events = pd.DataFrame([
        {"event_id": "a" * 32, "home_team": "Team A", "away_team": "Team B",
         "commence_time": "2026-09-28T17:00:00Z"},
    ])
    officials = pd.DataFrame([
        {"official_game_id": "game1", "home": "Team A", "away": "Team B",
         "date": "2026-09-28", "home_score": 24, "away_score": 20, "completed": True},
        {"official_game_id": "game2", "home": "Team A", "away": "Team B",
         "date": "2026-09-28", "home_score": 24, "away_score": 20, "completed": True},
    ])
    with pytest.raises(pl.Halt, match="multiple"):
        xw.build_crosswalk(events, officials, "NFL",
                           team_map=lambda x: x.lower().split()[-1])


# (f) grading twice appends 0 new rows
def test_grade_idempotent(tmp_path):
    import picks_grader as pg
    eid = "a" * 32
    rows = [_ledger_row(pick_id="idem", event_id=eid, market="moneyline",
                        side="Team A", point=None)]
    ledger = _setup_ledger(tmp_path, rows)
    _setup_crosswalk(ledger, "NFL", [
        (eid, "2026_04_TB_A", 24, 20, True, "Team A", "Team B"),
    ])
    g1 = pg.grade(ledger)
    assert len(g1) == 1
    # Write the grade rows to the ledger
    import picks_ledger as pl
    pl.append(g1, ledger)
    # Grade again
    g2 = pg.grade(ledger)
    assert len(g2) == 0  # nothing new to grade


# Null control: 4-leg fixture with known scores grades to hand-computed results
def test_null_control_4leg(tmp_path):
    import picks_grader as pg
    eid = "a" * 32
    # Pre-registered predictions:
    # spread Team A -3.5, home wins 24-20, margin +4: W
    # spread Team B +3.5, home wins 24-20, margin -4: L
    # total over 44.5, total 44: L
    # ML Team A, home wins: W
    rows = [
        _ledger_row(pick_id="nc_sp", market="spread", side="Team A", point=-3.5),
        _ledger_row(pick_id="nc_sp2", market="spread", side="Team B", point=3.5),
        _ledger_row(pick_id="nc_tot", market="total", side="over", point=44.5),
        _ledger_row(pick_id="nc_ml", market="moneyline", side="Team A", point=None),
    ]
    ledger = _setup_ledger(tmp_path, rows)
    _setup_crosswalk(ledger, "NFL", [
        (eid, "2026_04_TB_A", FIXTURE_HOME_SCORE, FIXTURE_AWAY_SCORE, True, "Team A", "Team B"),
    ])
    graded = pg.grade(ledger)
    results = {g["pick_id"]: g["result"] for g in graded}
    assert results["nc_sp"] == "W"
    assert results["nc_sp2"] == "L"
    assert results["nc_tot"] == "L"
    assert results["nc_ml"] == "W"
