"""Tests for build_events.py — event table schema and null controls.
Each test must FAIL on a stated mutation."""
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.build_events import parse_situation, time_to_seconds


class TestParseSituation:
    def test_5v5_home(self):
        """1551 from home team's view = 5v5."""
        s, own_g, opp_g = parse_situation("1551", event_team_is_home=True)
        assert s == "5v5"
        assert own_g == 1 and opp_g == 1

    def test_5v4_pp_home(self):
        """1451 from home team's view = home has 5 skaters, away has 4 = 5v4 PP."""
        s, own_g, opp_g = parse_situation("1451", event_team_is_home=True)
        assert s == "5v4"

    def test_5v4_pk_away(self):
        """1451 from AWAY team's view = away has 4 skaters, home has 5 = 4v5 PK."""
        s, own_g, opp_g = parse_situation("1451", event_team_is_home=False)
        assert s == "4v5"

    def test_pulled_goalie_6v5(self):
        """0651 = away goalie pulled, 6 away skaters, 5 home."""
        s, own_g, opp_g = parse_situation("0651", event_team_is_home=False)
        assert s == "6v5"
        assert own_g == 0  # away goalie pulled

    def test_empty_net_against(self):
        """1560 = 5 home skaters, 6 away skaters, home goalie pulled."""
        s, own_g, opp_g = parse_situation("1560", event_team_is_home=False)
        assert s == "5v6"
        assert opp_g == 0  # home goalie pulled, from away's view that's the opponent

    def test_mutation_swapped_teams_fails(self):
        """If we swap is_home, 1451 should give different strength."""
        s_home, _, _ = parse_situation("1451", event_team_is_home=True)
        s_away, _, _ = parse_situation("1451", event_team_is_home=False)
        assert s_home != s_away  # 5v4 vs 4v5


class TestTimeToSeconds:
    def test_period_1_start(self):
        assert time_to_seconds("00:00", 1) == 0

    def test_period_1_end(self):
        assert time_to_seconds("20:00", 1) == 1200

    def test_period_2_start(self):
        assert time_to_seconds("00:00", 2) == 1200

    def test_period_3_end(self):
        assert time_to_seconds("20:00", 3) == 3600

    def test_ot_start(self):
        assert time_to_seconds("00:00", 4) == 3600


# ── S7 tests: state timeline (must FAIL on 025494252) ──

import gzip, json

PBP_DIR = ROOT / "nhl" / "cache" / "pbp"


def _process_game(game_id):
    """Load and process a real game from cache."""
    from nhl.sim.build_events import process_game
    path = PBP_DIR / f"{game_id}.json.gz"
    with gzip.open(path, "rt") as f:
        data = json.load(f)
    return process_game(game_id, data), data


class TestS7StateTimeline:
    def test_opening_span_score_zero(self):
        """Game 2024020001: first state span must have score_diff_home == 0.
        Fails on 025494252: the old code set score_diff_home to the FINAL score (-3)."""
        (shots, pens, spans), data = _process_game("2024020001")
        assert len(spans) > 0
        first = spans[0]
        assert first["score_diff_home"] == 0, (
            f"First span score_diff_home={first['score_diff_home']}, expected 0"
        )

    def test_shootout_game_seconds(self):
        """Game 2024020022 (PHI@VAN, SO): total seconds = 3900 (3600 reg + 300 OT).
        Fails on 025494252: old code counted phantom spans into the shootout period."""
        (shots, pens, spans), data = _process_game("2024020022")
        total = sum(s["duration"] for s in spans)
        # Full OT (5 min) + regulation = 3900. Allow 2s tolerance.
        assert abs(total - 3900) <= 2, (
            f"Shootout game total seconds={total}, expected ~3900"
        )

    def test_score_state_before_third_goal(self):
        """Game 2024020001 (NJD 4 @ BUF 1): the third goal (P2 03:29) makes it 3-0.
        Before it, there must be a span with score_diff_home == -2 (down 0-2 from home view).
        Fails on 025494252: old code had final score on every span."""
        (shots, pens, spans), data = _process_game("2024020001")
        # Find spans before the third goal (which is at period 2, ~209 seconds into P2 = 1409 game-sec)
        sd_values = [s["score_diff_home"] for s in spans if s["start_sec"] < 1409]
        assert -2 in sd_values, (
            f"No span with score_diff_home==-2 before third goal; values seen: {sorted(set(sd_values))}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
