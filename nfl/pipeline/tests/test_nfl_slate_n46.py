#!/usr/bin/env python3
"""N46: the slate dealer and its log, production functions on the real-data fixtures of N43
(CAR@ATL 17:00Z = early, MIA@SF 20:25Z = late, NYG@LAR Monday = outside the 9 h slate)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_nfl_candidates_n43 import _build, FRESH  # noqa: E402

SPECS = [
    {"ticket_id": "ALLDAY_20", "legs": 4, "max_per_game": 2, "window": "all", "pool": "top_q"},
    {"ticket_id": "ALLDAY_10", "legs": 2, "max_per_game": 1, "window": "all", "pool": "top_q"},
    {"ticket_id": "EARLY_5", "legs": 1, "max_per_game": 1, "window": "early", "pool": "role_overs"},
    {"ticket_id": "LATE_5", "legs": 1, "max_per_game": 1, "window": "late", "pool": "role_overs"},
]


def test_deal_is_deterministic_disjoint_and_legal(tmp_path):
    from nfl.pipeline.build_nfl_slate import deal_slate
    cand, _ = _build(tmp_path)
    hands = deal_slate(cand, SPECS)
    ids = lambda h: {t: [(r["event_id"], r["player_name"], r["market_key"]) for r in rows] for t, rows in h.items()}  # noqa: E731
    assert ids(hands) == ids(deal_slate(cand.sample(frac=1.0, random_state=3), SPECS))   # row order cannot matter
    players = [(r["team"], r["player_name"]) for h in hands.values() for r in h]
    assert len(players) == 8 == len(set(players))                     # nobody on two tickets
    big = hands["ALLDAY_20"]
    assert len(big) == 4
    for eid in {r["event_id"] for r in big}:
        teams = [r["team"] for r in big if r["event_id"] == eid]
        assert len(teams) <= 2 and len(set(teams)) == len(teams)       # 2 per game, opposing teams
    assert all(r["home_team"] != "Los Angeles Rams" for h in hands.values() for r in h)   # Monday is not "all day"
    assert hands["EARLY_5"][0]["home_team"] == "Atlanta Falcons" and hands["EARLY_5"][0]["pick_side"] == "Over"
    assert hands["LATE_5"][0]["home_team"] == "San Francisco 49ers"
    assert all(r["eligible"] for h in hands.values() for r in h)


def test_later_ticket_excludes_players_already_on_the_slate(tmp_path):
    from nfl.pipeline.build_nfl_slate import deal_slate
    cand, _ = _build(tmp_path)
    late_spec = [s for s in SPECS if s["ticket_id"] == "LATE_5"]
    first = deal_slate(cand, late_spec)["LATE_5"][0]
    again = deal_slate(cand, late_spec, used_players={(first["team"], first["player_name"])})["LATE_5"][0]
    assert again["player_name"] != first["player_name"]


def test_rule_and_final_tickets_are_logged_and_cross_checked(tmp_path):
    from nfl.pipeline import build_nfl_slate as S
    cand, meta = _build(tmp_path)
    log = tmp_path / "log.json"
    hands = S.log_rule_tickets(log, cand, meta, "2026-09-20", SPECS)
    entries = json.loads(log.read_text())
    assert [e["ticket_id"] for e in entries] == [f"{s['ticket_id']}_RULE" for s in SPECS]
    assert S.slate_players_in_log(log, "2026-09-20") == {(r["team"], r["player_name"]) for h in hands.values() for r in h}

    spec = SPECS[0]
    keys = [(r["event_id"], r["player_name"], r["market_key"]) for r in hands["ALLDAY_20"]]
    reader = {"model": "test", "inputs": ["x"], "raw_output": "y"}
    conf = {k: {"availability_source": "inactives", "checked_at": "2026-09-20T15:40Z"} for k in keys}
    with pytest.raises(RuntimeError, match="removed leg .* needs a reason AND a source"):
        S.log_final_slate_ticket(log, cand, meta, "2026-09-20", spec, keys[:3], {}, conf, reader)
    with pytest.raises(RuntimeError, match="no availability confirmation"):
        S.log_final_slate_ticket(log, cand, meta, "2026-09-20", spec, keys, {}, {}, reader)
    n, entry = S.log_final_slate_ticket(
        log, cand, meta, "2026-09-20", spec, keys[:3],
        {keys[3]: {"reason": "inactive", "source": "team inactive list 15:32Z"}}, conf, reader)
    assert entry["ticket_id"] == "ALLDAY_20_FINAL" and len(entry["legs"]) == 3
    # append-only: a correction is a logged REVISION, never an edit
    with pytest.raises(RuntimeError, match="append-only"):
        S.log_final_slate_ticket(log, cand, meta, "2026-09-20", spec, keys[:3],
                                 {keys[3]: {"reason": "inactive", "source": "x"}}, conf, reader)
    with pytest.raises(RuntimeError, match="revision_reason"):
        S.log_final_slate_ticket(log, cand, meta, "2026-09-20", spec, keys[:2], {}, conf, reader, revision=1)
    n2, rev = S.log_final_slate_ticket(
        log, cand, meta, "2026-09-20", spec, keys[:2],
        {k: {"reason": "inactive", "source": "list"} for k in keys[2:]}, conf, reader,
        revision=1, revision_reason="second inactive")
    assert rev["ticket_id"] == "ALLDAY_20_FINAL_r1" and rev["supersedes"] == "ALLDAY_20_FINAL" and n2 == n + 1
    # a player on one FINAL ticket cannot be added to another
    spec10 = SPECS[1]
    keys10 = [(r["event_id"], r["player_name"], r["market_key"]) for r in hands["ALLDAY_10"]]
    steal = keys[0]
    ok_game = [k for k in keys10 if k[0] != steal[0]]
    with pytest.raises(RuntimeError, match="already on another final ticket"):
        S.log_final_slate_ticket(
            log, cand, meta, "2026-09-20", spec10, ok_game + [steal],
            {steal: {"reason": "r", "source": "s"},
             **{k: {"reason": "r", "source": "s"} for k in keys10 if k not in ok_game}},
            {k: conf[keys[0]] for k in ok_game + [steal]}, reader)


def test_two_legs_on_one_team_in_a_game_is_refused(tmp_path):
    from nfl.pipeline.build_nfl_candidates import check_legs_against_candidates, leg_record
    cand, _ = _build(tmp_path)
    e = cand[cand.eligible & (cand.team == "ATL")].drop_duplicates("player_name").head(2)
    legs = [leg_record(r) for r in e.to_dict("records")]
    with pytest.raises(RuntimeError, match="two legs on one team"):
        check_legs_against_candidates(legs, cand, max_per_game=2)
    with pytest.raises(RuntimeError, match="two legs in one game"):
        check_legs_against_candidates(legs, cand, max_per_game=1)


def test_unchanged_injury_pull_counts_as_a_pulse(tmp_path):
    """The ESPN puller hash-skips: an unchanged feed logs a line, not a file."""
    from nfl.pipeline.build_nfl_candidates import build_candidates
    from test_nfl_candidates_n43 import _tree
    tree = _tree(tmp_path, injury_stamp="20260919T0400Z")           # 12 h before the build: stale alone
    pulls = tmp_path / "inj" / "season=2026" / "_pulls.jsonl"
    pulls.write_text(json.dumps({"utc": "20260919T0400Z", "feed": "espn_injuries", "sha256": "A", "status": "written"}) + "\n")
    cand, meta = build_candidates(build_time=FRESH, **tree)
    assert meta["injury_file_age_hours"] == 12.0 and not cand.eligible.any()
    with open(pulls, "a") as fh:
        fh.write(json.dumps({"utc": "20260919T1230Z", "feed": "espn_injuries", "sha256": "A", "status": "unchanged"}) + "\n")
    cand, meta = build_candidates(build_time=FRESH, **tree)
    assert meta["injury_file_age_hours"] == 3.5 and cand.eligible.any()
    with open(pulls, "a") as fh:                                    # content changed later, file never arrived
        fh.write(json.dumps({"utc": "20260919T1500Z", "feed": "espn_injuries", "sha256": "B", "status": "written"}) + "\n")
    cand, meta = build_candidates(build_time=FRESH, **tree)
    assert meta["injury_file_age_hours"] == 12.0 and not cand.eligible.any()


def test_sequential_deal_gives_the_first_ticket_the_strongest_legs(tmp_path):
    """N47: 'give the 5 leg our most promising, then the 10 and then the 20'."""
    from nfl.pipeline.build_nfl_slate import deal_slate
    cand, _ = _build(tmp_path)
    specs = [{"ticket_id": "BEST_5", "legs": 2, "max_per_game": 1, "window": "all", "pool": "top_q"},
             {"ticket_id": "ALLDAY_10", "legs": 2, "max_per_game": 1, "window": "all", "pool": "top_q"}]
    seq = deal_slate(cand, specs, sequential=True)
    rr = deal_slate(cand, specs)
    q = lambda rows: sorted(r["q_pick"] for r in rows)  # noqa: E731
    assert min(q(seq["BEST_5"])) >= max(min(q(seq["ALLDAY_10"])), 0)       # first ticket is never weaker leg-for-leg
    assert sum(q(seq["BEST_5"])) >= sum(q(rr["BEST_5"]))
    sunday = cand[cand.eligible & (cand.home_team != "Los Angeles Rams")]          # Monday is outside the slate
    best_per_game = sunday.sort_values("q_pick", ascending=False).drop_duplicates("event_id").head(2)
    assert sorted(best_per_game.q_pick) == q(seq["BEST_5"])                # exactly the top leg of the top games
    players = [(r["team"], r["player_name"]) for h in seq.values() for r in h]
    assert len(players) == len(set(players))


def test_balanced_families_stops_the_all_receptions_ticket(tmp_path):
    """N48: on one q scale every dealt leg was a receptions leg (35 of 35 on 2026-09-20)."""
    from nfl.pipeline.build_nfl_slate import deal_slate, FAMILY_GROUP
    cand, _ = _build(tmp_path)
    spec = [{"ticket_id": "T", "legs": 2, "max_per_game": 1, "window": "all", "pool": "top_q"}]
    plain = deal_slate(cand, spec)["T"]
    assert {FAMILY_GROUP[r["market_key"]] for r in plain} == {"REC"}            # the defect, reproduced
    mixed = deal_slate(cand, spec, balance_families=True)["T"]
    assert [FAMILY_GROUP[r["market_key"]] for r in mixed] == ["REC", "RUSH"]    # the cycle, in order
    for r in mixed:                                                            # best q WITHIN its group, legal game
        same = cand[cand.eligible & (cand.market_key.map(FAMILY_GROUP) == FAMILY_GROUP[r["market_key"]])
                    & (cand.home_team != "Los Angeles Rams")]
        assert r["q_pick"] <= same.q_pick.max() + 1e-12
    assert mixed[0]["q_pick"] == cand[cand.eligible & (cand.market_key == "player_receptions")
                                      & (cand.home_team != "Los Angeles Rams")].q_pick.max()
    six = deal_slate(cand, [{**spec[0], "legs": 4, "max_per_game": 2}], balance_families=True)["T"]
    assert [FAMILY_GROUP[r["market_key"]] for r in six][:3] == ["REC", "RUSH", "QB"]


def test_placement_is_appended_and_must_match_the_recommendation(tmp_path):
    """N49: the slip is the record of what was accepted; differences must be explicit."""
    from nfl.pipeline import build_nfl_slate as S
    cand, meta = _build(tmp_path)
    log = tmp_path / "log.json"
    hands = S.log_rule_tickets(log, cand, meta, "s", SPECS)
    rule = json.loads(log.read_text())[0]
    legs = [{"player_name": l["player_name"], "market_key": l["market_key"], "side": l["pick_side"],
             "line": l["line"], "american": l["pick_price"]} for l in rule["legs"]]
    kw = dict(stake=10, quoted_american=900, source="slip screenshot")
    with pytest.raises(RuntimeError, match="not placed and not explained"):
        S.log_placement(log, "s", "P", rule["ticket_id"], legs_placed=legs[1:], **kw)
    with pytest.raises(RuntimeError, match="different contract"):
        S.log_placement(log, "s", "P", rule["ticket_id"], legs_placed=[{**legs[0], "line": legs[0]["line"] + 1}] + legs[1:], **kw)
    with pytest.raises(RuntimeError, match="never recommended"):
        S.log_placement(log, "s", "P", rule["ticket_id"], legs_placed=legs + [{**legs[0], "player_name": "Nobody"}], **kw)
    moved = [{**legs[0], "american": legs[0]["american"] - 15}] + legs[2:]
    n, e = S.log_placement(log, "s", "P", rule["ticket_id"], legs_placed=moved,
                           dropped=[{"player_name": legs[1]["player_name"], "market_key": legs[1]["market_key"],
                                     "reason": "line went up"}], **kw)
    assert e["price_moved"][0]["accepted"] == legs[0]["american"] - 15 and len(e["legs_placed"]) == len(legs) - 1
    assert S.slate_players_in_log(log, "s") == {(r["team"], r["player_name"]) for h in hands.values() for r in h}
    with pytest.raises(RuntimeError, match="append-only"):
        S.log_placement(log, "s", "P", rule["ticket_id"], legs_placed=legs, **kw)
