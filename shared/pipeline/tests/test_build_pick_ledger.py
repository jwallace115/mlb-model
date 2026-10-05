"""Item 3: the pick ledger halts on a source it cannot parse instead of dropping it."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pick_sources as ps  # noqa: E402
from _bet_fixtures import frames, pick, picks, slip  # noqa: E402


def test_unparseable_source_halts(tmp_path):
    (tmp_path / "nfl/data/board/week=2026_05").mkdir(parents=True)
    (tmp_path / "nfl/data/board/week=2026_05/sun_cards_20261004.json").write_text("{not json")
    with pytest.raises(ps.Halt):
        ps.load_picks(tmp_path, sources=[("nfl/data/board/week=*/sun_cards*.json", ps.p_sun_cards, "extra")])


def test_unknown_layout_halts(tmp_path):
    (tmp_path / "nfl/data/board/week=2026_05").mkdir(parents=True)
    (tmp_path / "nfl/data/board/week=2026_05/x_placements_20261004.json").write_text(json.dumps({"surprise": 1}))
    with pytest.raises(ps.Halt):
        ps.load_picks(tmp_path, sources=[("nfl/data/board/week=*/*placements*.json", ps.p_nfl_placements, "workorder")])


def test_empty_glob_halts(tmp_path):
    with pytest.raises(ps.Halt):
        ps.load_picks(tmp_path, sources=[("nfl/data/board/week=*/mnf_sgp*.json", ps.p_mnf_sgp, "extra")])


def test_parses_a_sun_card(tmp_path):
    d = tmp_path / "nfl/data/board/week=2026_03"
    d.mkdir(parents=True)
    (d / "sun_cards_20260927.json").write_text(json.dumps({
        "slate": "2026-09-27", "written_utc": "2026-09-27T15:00:00Z",
        "cards": {"LINES_2": {"legs": [{"game": "SEA@WAS", "pick": "Seahawks -8.5", "price": -110},
                                       {"game": "TEN@NYG", "pick": "TEN@NYG over 35.5", "price": -110}]}}}))
    P, F = ps.load_picks(tmp_path, sources=[("nfl/data/board/week=*/sun_cards*.json", ps.p_sun_cards, "extra")])
    assert list(P.market) == ["spread", "total"] and P.market.notna().all()


def test_ledger_joins_on_ticket_id_even_where_the_leg_rule_cannot(tmp_path):
    import build_pick_ledger as bl
    import ticket_id as tk
    tid = "ncaaf_2026-10-04_card5_20261004T150212Z"
    P = picks(pick(tid, "2026-10-04T15:02:12", "Northwestern Wildcats @ Penn State Nittany Lions", "spread",
                   "Northwestern Wildcats", "Northwestern Wildcats", 2.5, league="NCAAF"))
    # placed 3 days later on another game: outside the rule's window and no leg agrees
    S, L = frames(slip("hr-1", "2026-10-07 12:00", [("Ohio vs Akron", "Spread", "Ohio -3.5", "2026-10-07 19:00")],
                       league="NCAA, Regular"))
    assert bl.join_slips(P, S, L, []).slip_id.isna().all()
    store = tmp_path / "placements.csv"
    tk.record_placement("hr-1", tid, "ncaaf", path=store)
    J = bl.join_slips(P, S, L, tk.read_placements(store))
    assert (J.slip_id == "hr-1").all() and (J.join_method == "ticket_id").all()
    assert J.leg_outcome.isna().all()        # the swapped leg carries no outcome
