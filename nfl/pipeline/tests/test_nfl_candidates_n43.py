#!/usr/bin/env python3
"""N43: production build_candidates / baseline tickets / log on slices of the REAL archives.

fixtures/n43_props_3games.parquet      real Hard Rock rows, CAR@ATL, MIA@SF, NYG@LAR, the
                                       2026-09-18T02:50Z ("mid") and 09-19T15:11Z ("open") pulls
fixtures/n43_usage_2026_wk2.parquet    the real 2026 week-2 usage rows, all 32 teams
fixtures/n43_injuries_20260920T0630Z   the real ESPN injuries pull, fields trimmed to name+status
"""

import gzip
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).resolve().parent / "fixtures"

FRESH = "2026-09-19T16:00:00+00:00"     # 49 min after the 15:11Z pull


def _tree(tmp_path, injury_stamp="20260919T1200Z", edit_injuries=None):
    props = tmp_path / "props" / "season=2026" / "month=09"
    props.mkdir(parents=True)
    shutil.copy(FIX / "n43_props_3games.parquet", props / "data_2026_09.parquet")
    inj = tmp_path / "inj" / "season=2026"
    inj.mkdir(parents=True)
    data = json.load(gzip.open(FIX / "n43_injuries_20260920T0630Z.json.gz", "rt"))
    if edit_injuries:
        edit_injuries(data)
    # The archive began 2026-09-20; the copy is re-stamped so a 09-19 build can read it.
    with gzip.open(inj / f"injuries_{injury_stamp}.json.gz", "wt") as fh:
        json.dump(data, fh)
    return dict(props_dir=tmp_path / "props", injury_dir=tmp_path / "inj",
                usage_path=FIX / "n43_usage_2026_wk2.parquet", season=2026)


def _build(tmp_path, build_time=FRESH, **kw):
    from nfl.pipeline.build_nfl_candidates import build_candidates
    tree = _tree(tmp_path, **{k: kw.pop(k) for k in list(kw) if k in ("injury_stamp", "edit_injuries")})
    return build_candidates(build_time=build_time, **tree, **kw)


def test_devig_is_same_row_and_sums_to_one(tmp_path):
    cand, meta = _build(tmp_path)
    assert meta["week"] == 2 and meta["props_pull_timestamp"].startswith("2026-09-19T15:11")
    two = cand[cand.two_way]
    r = two[(two.player_name == "Bijan Robinson") & (two.market_key == "player_receptions")].iloc[0]
    io = 155 / 255 if r.over_price == -155 else None
    assert io is not None, r.over_price                       # the real row: Over 4.5 -155
    iu = (abs(r.under_price) / (abs(r.under_price) + 100)) if r.under_price < 0 else 100 / (r.under_price + 100)
    assert abs(r.q_over - io / (io + iu)) < 1e-12 and abs(r.hold - (io + iu - 1)) < 1e-12
    assert (two.hold > 0).all() and two.hold.median() > 0.05  # Hard Rock's two-way hold ~6.8%
    assert not cand[~cand.two_way].eligible.any()             # anytime TD: no complement, never eligible
    assert not cand[~cand.volume_family].eligible.any()


def test_nothing_after_build_time_and_nothing_kicked(tmp_path):
    # Before the 09-19 pull existed: only the 09-18 "mid" pull may be read.
    cand, meta = _build(tmp_path, build_time="2026-09-18T04:00:00+00:00", injury_stamp="20260918T0000Z")
    assert meta["props_pull_timestamp"].startswith("2026-09-18T02:50")
    assert set(cand.pull_timestamp) == {"2026-09-18T02:50:33.337271+00:00"}
    # After the early window kicked (CAR@ATL 17:00Z): that game is gone from the board.
    cand2, _ = _build(tmp_path / "b", build_time="2026-09-20T18:00:00+00:00",
                      injury_stamp="20260920T0630Z", max_pull_age_hours=1e9)
    assert "Atlanta Falcons" not in set(cand2.home_team) and len(cand2) > 0


def test_stale_pull_makes_nothing_eligible(tmp_path):
    cand, meta = _build(tmp_path, build_time="2026-09-20T07:00:00+00:00", injury_stamp="20260920T0630Z")
    assert meta["props_pull_age_hours"] > 15
    assert not cand.eligible.any() and cand.ineligible_reasons.str.contains("pull_stale").all()


def test_out_player_is_never_eligible(tmp_path):
    def bijan_out(data):
        for team in data["injuries"]:
            if team["displayName"] == "Atlanta Falcons":
                team["injuries"].append({"status": "Out", "athlete": {"displayName": "Bijan Robinson"}})
    cand, _ = _build(tmp_path, edit_injuries=bijan_out)
    b = cand[cand.player_name == "Bijan Robinson"]
    assert len(b) and not b.eligible.any() and b.ineligible_reasons.str.contains("status_Out").all()
    fresh, _ = _build(tmp_path / "b")
    assert fresh[(fresh.player_name == "Bijan Robinson") & fresh.volume_family].eligible.all()


def test_baselines_are_rules_one_leg_per_game(tmp_path):
    from nfl.pipeline.build_nfl_candidates import baseline_ticket, role_overs_ticket, ticket_price
    cand, _ = _build(tmp_path)
    a, b = baseline_ticket(cand), baseline_ticket(cand.sample(frac=1.0, random_state=7))
    assert a == b and len(a) == 3 == len({leg["event_id"] for leg in a})       # 3 games in the fixture
    top = cand[cand.eligible].q_pick.max()
    assert a[0]["q_pick"] == top
    overs = role_overs_ticket(cand)
    assert overs and all(leg["pick_side"] == "Over" for leg in overs)
    for leg in overs:
        lead = ((leg["market_key"] == "player_receptions" and leg["target_rank"] <= 2)
                or (leg["market_key"] == "player_rush_attempts" and leg["carry_rank"] == 1)
                or leg["market_key"].startswith("player_pass_"))
        assert lead, leg
    price = ticket_price(a)
    assert price["expected_return_per_1_at_book_q"] < 1.0      # a parlay of vig-ed legs is -EV at the book's own q


def test_log_is_append_only_and_refuses_a_leg_that_is_not_a_candidate_row(tmp_path):
    """Audit #5: N43's logger took two copies of one leg at a 999.5 line and +9999."""
    from nfl.pipeline.build_nfl_candidates import baseline_ticket, log_ticket, ticket_price
    cand, meta = _build(tmp_path)
    legs = baseline_ticket(cand)
    entry = {"build_time": FRESH, "ticket_id": "BASELINE_TOPK_Q", "kind": "baseline_rule",
             "manifest": meta, "legs": legs, "price": ticket_price(legs)}
    log = tmp_path / "log.json"
    assert log_ticket(log, entry, cand) == 1
    with pytest.raises(RuntimeError, match="append-only"):
        log_ticket(log, entry, cand)
    invented = {**legs[0], "line": 999.5, "pick_price": 9999, "complement_price": 9999}
    with pytest.raises(RuntimeError, match="candidate row has"):
        log_ticket(log, {**entry, "ticket_id": "X1", "legs": [invented]}, cand)
    with pytest.raises(RuntimeError, match="two legs in one game"):
        other = cand[cand.eligible & (cand.event_id == legs[0]["event_id"])
                     & (cand.player_name != legs[0]["player_name"])].iloc[0].to_dict()
        from nfl.pipeline.build_nfl_candidates import leg_record
        log_ticket(log, {**entry, "ticket_id": "X2", "legs": [legs[0], leg_record(other)]}, cand)
    with pytest.raises(RuntimeError, match="missing complement_price"):
        log_ticket(log, {**entry, "ticket_id": "X3", "legs": [{**legs[0], "complement_price": None}]}, cand)
    ineligible = cand[~cand.eligible & cand.two_way].iloc[0].to_dict()
    with pytest.raises(RuntimeError, match="not eligible"):
        log_ticket(log, {**entry, "ticket_id": "X4", "legs": [leg_record(ineligible)]}, cand)
    assert len(json.loads(log.read_text())) == 1


def test_old_injury_file_makes_nothing_eligible(tmp_path):
    """Audit #5: an August-1 injury file with fresh props still admitted 50 legs."""
    cand, meta = _build(tmp_path, injury_stamp="20260801T0000Z")
    assert meta["injury_file_age_hours"] > 1000
    assert not cand.eligible.any() and cand.ineligible_reasons.str.contains("injury_feed_stale").all()


def test_status_is_read_from_the_players_own_team_only(tmp_path):
    def bijan_on_the_opponent(data):        # CAR @ ATL: an "Out" Bijan Robinson listed under CAROLINA
        for team in data["injuries"]:
            if team["displayName"] == "Carolina Panthers":
                team["injuries"].append({"status": "Out", "athlete": {"displayName": "Bijan Robinson"}})
    cand, _ = _build(tmp_path, edit_injuries=bijan_on_the_opponent)
    b = cand[(cand.player_name == "Bijan Robinson") & cand.volume_family]
    assert len(b) and b.eligible.all() and (b.injury_status != "Out").all()


def _final_inputs(cand):
    from nfl.pipeline.build_nfl_candidates import baseline_ticket, role_overs_ticket, _key
    base = {_key(l) for l in baseline_ticket(cand)} | {_key(l) for l in role_overs_ticket(cand)}
    overs = [_key(l) for l in role_overs_ticket(cand)]
    final = overs[:2]
    reader = {"model": "test", "inputs": ["espn nfl news 20260919T1210Z"], "raw_output": "..."}
    conf = {k: {"availability_source": "official inactives, team site", "checked_at": "2026-09-20T15:40Z"} for k in final}
    reasons = {k: {"reason": "not selected", "source": "candidate table"} for k in base - set(final)}
    return final, reasons, conf, reader, base


def test_final_ticket_departures_are_derived_not_volunteered(tmp_path):
    from nfl.pipeline.build_nfl_candidates import log_final_ticket
    cand, meta = _build(tmp_path)
    final, reasons, conf, reader, base = _final_inputs(cand)
    log = tmp_path / "log.json"
    missing_one = dict(list(reasons.items())[1:])
    with pytest.raises(RuntimeError, match="removed leg .* needs a reason AND a source"):
        log_final_ticket(log, cand, meta, final, missing_one, conf, reader)
    with pytest.raises(RuntimeError, match="no availability confirmation"):
        log_final_ticket(log, cand, meta, final, reasons, {}, reader)
    with pytest.raises(RuntimeError, match="reader record missing"):
        log_final_ticket(log, cand, meta, final, reasons, conf, {"model": "test"})
    outside = cand[cand.eligible & ~cand.apply(lambda r: (r.event_id, r.player_name, r.market_key) in base, axis=1)
                   & ~cand.event_id.isin([k[0] for k in final])].iloc[0]
    k_out = (outside.event_id, outside.player_name, outside.market_key)
    with pytest.raises(RuntimeError, match="added leg .* needs a reason AND a source"):
        log_final_ticket(log, cand, meta, final + [k_out], reasons,
                         {**conf, k_out: conf[final[0]]}, reader)
    assert not log.exists()
    n, entry = log_final_ticket(log, cand, meta, final, reasons, conf, reader)
    assert n == 1 and len(entry["legs"]) == 2
    assert {tuple(k) for k in entry["departures"]["removed_from_baselines"]} == base - set(final)
    row = cand[(cand.event_id == final[0][0]) & (cand.player_name == final[0][1])
               & (cand.market_key == final[0][2])].iloc[0]
    assert entry["legs"][0]["line"] == row.line and entry["legs"][0]["pick_price"] == row.pick_price


def test_no_ticket_is_a_valid_logged_outcome(tmp_path):
    from nfl.pipeline.build_nfl_candidates import log_final_ticket
    cand, meta = _build(tmp_path)
    _, _, _, reader, base = _final_inputs(cand)
    reasons = {k: {"reason": "inactives unresolved at bet time", "source": "team inactive lists 15:30Z"} for k in base}
    n, entry = log_final_ticket(tmp_path / "log.json", cand, meta, [], reasons, {}, reader)
    assert n == 1 and entry["legs"] == [] and entry["price"] is None


def test_main_reaches_the_final_ticket_path(tmp_path, monkeypatch):
    """The production entry point: main() logs both baselines, then `--final file` logs the reader."""
    from nfl.pipeline import build_nfl_candidates as N
    tree = _tree(tmp_path)
    monkeypatch.setattr(N, "ROOT", tmp_path)
    monkeypatch.setattr(N, "BOARD_DIR", tmp_path / "board")
    monkeypatch.setattr(N, "PROPS_DIR", tree["props_dir"])
    monkeypatch.setattr(N, "INJURY_DIR", tree["injury_dir"])
    monkeypatch.setattr(N, "USAGE_PATH", tree["usage_path"])
    monkeypatch.setattr(N.build_candidates, "__defaults__",
                        (tree["props_dir"], tree["usage_path"], tree["injury_dir"], 2026, None,
                         N.MAX_PULL_AGE_HOURS, N.MAX_INJURY_AGE_HOURS))
    monkeypatch.setattr(sys, "argv", ["x", "--build-time", FRESH])
    N.main()
    log = tmp_path / "board" / "nfl_prop_tickets_2026.json"
    entries = json.loads(log.read_text())
    assert [e["ticket_id"] for e in entries] == ["BASELINE_TOPK_Q", "BASELINE_ROLE_OVERS"]
    cand = pd.read_parquet(tmp_path / entries[0]["manifest"]["candidates_file"])
    final, reasons, conf, reader, _ = _final_inputs(cand)
    spec = {"candidates_file": entries[0]["manifest"]["candidates_file"], "final_keys": [list(k) for k in final],
            "reasons": [{"leg": list(k), **v} for k, v in reasons.items()],
            "confirmations": [{"leg": list(k), **v} for k, v in conf.items()], "reader": reader}
    (tmp_path / "reader_ticket.json").write_text(json.dumps(spec))
    monkeypatch.setattr(sys, "argv", ["x", "--final", str(tmp_path / "reader_ticket.json")])
    N.main()
    entries = json.loads(log.read_text())
    assert entries[-1]["ticket_id"] == "FINAL_READER" and len(entries) == 3
    # a candidate table edited after the baselines were logged is refused
    pq = tmp_path / entries[0]["manifest"]["candidates_file"]
    cand.assign(line=cand.line + 1).to_parquet(pq, index=False)
    with pytest.raises(RuntimeError, match="sha256 changed"):
        N.main()
