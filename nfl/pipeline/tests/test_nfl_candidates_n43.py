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


def test_log_is_append_only_and_a_veto_needs_a_source(tmp_path):
    from nfl.pipeline.build_nfl_candidates import baseline_ticket, log_ticket, ticket_price
    cand, meta = _build(tmp_path)
    legs = baseline_ticket(cand)
    entry = {"build_time": FRESH, "ticket_id": "BASELINE_TOPK_Q", "kind": "baseline_rule",
             "manifest": meta, "legs": legs, "price": ticket_price(legs), "vetoes": []}
    log = tmp_path / "log.json"
    assert log_ticket(log, entry) == 1
    with pytest.raises(RuntimeError, match="append-only"):
        log_ticket(log, entry)
    with pytest.raises(RuntimeError, match="reason AND a source"):
        log_ticket(log, {**entry, "ticket_id": "FINAL", "vetoes": [{"leg": "x", "reason": "gut"}]})
    with pytest.raises(RuntimeError, match="missing complement_price"):
        log_ticket(log, {**entry, "ticket_id": "FINAL2",
                         "legs": [{**legs[0], "complement_price": None}]})
    assert len(json.loads(log.read_text())) == 1
