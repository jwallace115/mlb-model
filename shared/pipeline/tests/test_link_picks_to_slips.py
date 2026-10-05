"""Item 1: the conservative matching rule. Synthetic data only; no network, no real slips."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _bet_fixtures import frames, mnf_card, mnf_slip, pick, picks, slip, MNF, MNF_KICK_ET  # noqa: E402
import link_picks_to_slips as lk  # noqa: E402


def _match(slips, P):
    S, L = frames(*slips)
    return lk.match_all(S, L, P).set_index("slip_id")


def test_bought_points_still_match():
    # every point differs from the card (Jeff buys points); market, subject and side agree
    M = _match([mnf_slip("s1", points=("12.5", "20.5", "47.5", "9.5"))], picks(*mnf_card()))
    assert M.loc["s1", "matched"] and M.loc["s1", "legs_agreed"] == 4


def test_time_window_alone_is_not_a_match():
    # placed 10 minutes after a card was built, same game, but every leg is something else
    s = slip("s1", "2026-09-28 15:40", [
        (MNF, "Jalen Hurts - Anytime TD", "Over 0.5", MNF_KICK_ET),
        (MNF, "Total Points", "Over 47.5", MNF_KICK_ET),
        (MNF, "D'Andre Swift - Receptions", "Over 2.5", MNF_KICK_ET)])
    M = _match([s], picks(*mnf_card()))
    assert not M.loc["s1", "matched"] and M.loc["s1", "legs_agreed"] == 0


def test_half_the_legs_is_the_bar():
    s = slip("s1", "2026-09-28 15:40", [
        (MNF, "D'Andre Swift - Rushing Attempts", "Over 14.5", MNF_KICK_ET),
        (MNF, "Saquon Barkley - Rushing Attempts", "Under 17.5", MNF_KICK_ET),
        (MNF, "Jalen Hurts - Anytime TD", "Over 0.5", MNF_KICK_ET),
        (MNF, "A.J. Brown - Receptions", "Over 4.5", MNF_KICK_ET),
        (MNF, "DJ Moore - Receptions", "Over 4.5", MNF_KICK_ET)])
    M = _match([s], picks(*mnf_card()))
    assert M.loc["s1", "legs_agreed"] == 2 and M.loc["s1", "need"] == 3 and not M.loc["s1", "matched"]


def test_one_popular_leg_cannot_tag_a_two_leg_slip():
    s = slip("s1", "2026-09-28 15:40", [
        (MNF, "D'Andre Swift - Rushing Attempts", "Over 14.5", MNF_KICK_ET),
        (MNF, "Jalen Hurts - Anytime TD", "Over 0.5", MNF_KICK_ET)])
    M = _match([s], picks(*mnf_card()))
    assert M.loc["s1", "legs_agreed"] == 1 and M.loc["s1", "need"] == 2 and not M.loc["s1", "matched"]


def test_opposite_side_does_not_agree():
    s = mnf_slip("s1")
    s[1][0]["selection"] = "Under 14.5"      # Swift UNDER vs the card's OVER
    s[1][2]["selection"] = "Over 43.5"       # game OVER vs the card's UNDER
    M = _match([s], picks(*mnf_card()))
    assert M.loc["s1", "legs_agreed"] == 2          # only Barkley and Keenum count


def test_outside_window_is_not_a_match():
    M = _match([mnf_slip("s1", placed="2026-10-01 15:40")], picks(*mnf_card()))
    assert not M.loc["s1", "matched"]


def test_copy_of_the_same_ticket_is_contested_and_neither_is_proposed():
    # the 2026-09-27 pattern: the same card placed twice minutes apart (Jeff tagged one `other`)
    M = _match([mnf_slip("s1"), mnf_slip("s2", placed="2026-09-28 15:49")], picks(*mnf_card()))
    assert M.loc["s1", "qualified"] and M.loc["s2", "qualified"]
    assert M.loc["s1", "contested"] and M.loc["s2", "contested"]
    assert not M.loc["s1", "matched"] and not M.loc["s2", "matched"]


def test_same_team_other_week_does_not_agree():
    # a card leg with no kickoff ("Browns +2" written 2026-09-27) vs a Browns leg four days later
    P = picks(pick("nfl_lines", "2026-09-27T12:00:00", "", "spread", "Browns", "Browns", 2.0),
              pick("nfl_lines", "2026-09-27T12:00:00", "", "spread", "Bills", "Bills", -7.0))
    s = slip("s1", "2026-09-28 23:23", [
        ("Browns vs Steelers", "Spread", "Browns +8.5", "2026-10-01 20:15"),
        ("Bills vs Patriots", "Spread", "Bills -3.5", "2026-10-04 13:00")])
    M = _match([s], P)
    assert M.loc["s1", "legs_agreed"] == 0 and not M.loc["s1", "matched"]


def test_ncaaf_school_names():
    P = picks(pick("ncaaf_c", "2026-10-02T19:00:00", "Northwestern Wildcats @ Penn State Nittany Lions", "spread",
                   "Northwestern Wildcats", "Northwestern Wildcats", 2.5, league="NCAAF"),
              pick("ncaaf_c", "2026-10-02T19:00:00", "Iowa Hawkeyes @ Iowa State Cyclones", "spread",
                   "Iowa Hawkeyes", "Iowa Hawkeyes", 3.5, league="NCAAF"))
    s = slip("s1", "2026-10-02 16:30", [
        ("Northwestern vs Penn State", "Spread", "Northwestern +3.5", "2026-10-02 19:00"),
        ("Iowa vs Iowa State", "Spread", "Iowa State -3.5", "2026-10-02 19:00")], league="NCAA, Regular")
    M = _match([s], P)
    # Northwestern agrees; Iowa State is not Iowa
    assert M.loc["s1", "legs_agreed"] == 1 and not M.loc["s1", "matched"]


def test_need_floor():
    assert [lk.need(n) for n in (1, 2, 3, 4, 5, 9, 13)] == [1, 2, 2, 2, 3, 5, 7]
