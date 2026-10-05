"""Item 2: a pick logged with a ticket_id, then a slip recorded against it, joins on ticket_id
with no fuzzy matching. Written before shared/pipeline/ticket_id.py existed (red first)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _bet_fixtures import pick, picks  # noqa: E402


def test_pick_then_slip_joins_on_ticket_id_without_fuzzy_matching(tmp_path):
    from ticket_id import stamp, record_placement, read_placements, attach_slips

    logged = {"legs": [{"game": "Northwestern @ Penn State", "market": "spreads", "side": "Northwestern"}]}
    tid = stamp(logged, "ncaaf", "2026-10-04", "card5", "2026-10-04T15:02:12+00:00")
    assert tid == "ncaaf_2026-10-04_card5_20261004T150212Z"

    P = picks(pick(tid, "2026-10-04T15:02:12", "Northwestern Wildcats @ Penn State Nittany Lions", "spread",
                   "Northwestern Wildcats", "Northwestern Wildcats", 2.5, league="NCAAF", kind="card"))
    before = attach_slips(P, [])
    assert before.slip_id.isna().all()

    store = tmp_path / "placements.csv"
    assert record_placement("hr-1", tid, "ncaaf", path=store) is True
    J = attach_slips(P, read_placements(store))
    assert (J.slip_id == "hr-1").all() and (J.join_method == "ticket_id").all()
    # another pick with no placement row stays unjoined: nothing is inferred
    P2 = picks(pick("ncaaf_2026-10-04_card10_20261004T150300Z", "2026-10-04T15:03:00", "A @ B", "total", "", "under",
                    league="NCAAF"))
    assert attach_slips(P2, read_placements(store)).slip_id.isna().all()


def test_stamp_keeps_an_existing_id_and_old_picks_still_log():
    from ticket_id import stamp
    p = {"ticket_id": "nfl_2026-09-20_lead5_20260920T142403Z"}
    assert stamp(p, "nfl", "x", "y") == "nfl_2026-09-20_lead5_20260920T142403Z"
    legacy = {"market": "totals", "side": "Under"}          # a pick logged without any id
    assert "ticket_id" not in legacy                         # nothing requires it


def test_a_slip_comes_from_one_ticket(tmp_path):
    from ticket_id import record_placement
    store = tmp_path / "placements.csv"
    record_placement("hr-1", "nfl_a_b_20260101T000000Z", "nfl", path=store)
    assert record_placement("hr-1", "nfl_a_b_20260101T000000Z", "nfl", path=store) is False
    with pytest.raises(ValueError):
        record_placement("hr-1", "nfl_other_b_20260101T000000Z", "nfl", path=store)


def test_ids_need_a_known_lane_and_utc():
    from ticket_id import make_ticket_id
    from datetime import datetime
    with pytest.raises(ValueError):
        make_ticket_id("hockey", "2026-10-04", "card")
    with pytest.raises(ValueError):
        make_ticket_id("nhl", "2026-10-04", "card", datetime(2026, 10, 4, 15, 0))   # naive time
