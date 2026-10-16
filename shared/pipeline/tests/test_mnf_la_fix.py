"""Tests for MNF 10-12 BUF@LA fix (P54).

(a) nfl_team("LA") matches "Los Angeles Rams" → "rams"
(b) _nfl_team_norm("LA") returns "LA" (the nflverse abbreviation)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pick_sources as ps
import event_crosswalk as xw


class TestLARams:
    """nfl_team('LA') must return 'rams' — nflverse uses 'LA' for Rams."""

    def test_la_returns_rams(self):
        # RED on old code: nfl_team("LA") returns None
        assert ps.nfl_team("LA") == "rams", f"expected 'rams', got {ps.nfl_team('LA')!r}"

    def test_lar_still_works(self):
        assert ps.nfl_team("LAR") == "rams"

    def test_lac_still_works(self):
        assert ps.nfl_team("LAC") == "chargers"

    def test_nfl_team_norm_la_matches_full_name(self):
        """Both 'LA' (nflverse) and 'Los Angeles Rams' (tape) must normalize to the same value."""
        norm_la = xw._nfl_team_norm("LA")
        norm_full = xw._nfl_team_norm("Los Angeles Rams")
        assert norm_la == norm_full, f"LA={norm_la!r} != full={norm_full!r}"
        assert norm_la == "LAR", f"expected LAR, got {norm_la!r}"
