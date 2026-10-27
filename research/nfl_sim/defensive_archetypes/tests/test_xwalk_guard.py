#!/usr/bin/env python3
"""Tests for DA-1 Item 1: crosswalk + guard.

RED-first:
  1. Every (season, team) in schedules 2021-2026 maps via canon().
  2. JAX and JAC map to the same key.
  3. A planted "LAR" in a 2025 row resolves.
  4. Guard HALTs on holdout season.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "nfl_sim" / "defensive_archetypes"))

from team_xwalk import canon
from da_guard import check_prop_seasons


class TestCrosswalk:

    def test_all_schedule_teams_map(self):
        """Every (season, team) in nflverse schedules 2021-2026 maps."""
        import nflreadpy
        unmapped = []
        for season in range(2021, 2027):
            try:
                s = nflreadpy.load_schedules([season])
                if hasattr(s, "to_pandas"):
                    s = s.to_pandas()
            except Exception:
                continue
            for team in set(s["home_team"].unique()) | set(s["away_team"].unique()):
                c = canon(team, season)
                if c is None:
                    unmapped.append((season, team))
        assert unmapped == [], f"unmapped teams: {unmapped}"

    def test_jax_jac_same(self):
        """JAX and JAC map to the same canonical key."""
        assert canon("JAX") == canon("JAC") == "JAX"

    def test_lar_resolves(self):
        """A planted 'LAR' in a 2025 row resolves to 'LA'."""
        assert canon("LAR", 2025) == "LA"

    def test_full_name_resolves(self):
        """Jacksonville Jaguars full name resolves to JAX."""
        assert canon("Jacksonville Jaguars") == "JAX"

    def test_washington_variants(self):
        """All Washington variants resolve to WAS."""
        assert canon("WAS") == "WAS"
        assert canon("WSH") == "WAS"
        assert canon("Washington Commanders") == "WAS"
        assert canon("Washington Football Team") == "WAS"


class TestGuard:

    def test_guard_halts_on_holdout(self):
        """Guard HALTs if 2024 or 2025 prop rows are loaded in discovery mode."""
        import pandas as pd
        df = pd.DataFrame({"nfl_season": [2023, 2024]})
        # Ensure DA_PHASE is discovery
        import da_guard
        old = da_guard.DA_PHASE
        da_guard.DA_PHASE = "discovery"
        try:
            with pytest.raises(SystemExit, match="HALT.*holdout"):
                check_prop_seasons(df)
        finally:
            da_guard.DA_PHASE = old

    def test_guard_ok_in_validation(self):
        """Guard allows holdout seasons when DA_PHASE=validation."""
        import pandas as pd
        df = pd.DataFrame({"nfl_season": [2024, 2025]})
        import da_guard
        old = da_guard.DA_PHASE
        da_guard.DA_PHASE = "validation"
        try:
            check_prop_seasons(df)  # should not raise
        finally:
            da_guard.DA_PHASE = old

    def test_guard_ok_discovery_no_holdout(self):
        """Guard allows discovery seasons without holdout rows."""
        import pandas as pd
        df = pd.DataFrame({"nfl_season": [2021, 2022, 2023]})
        import da_guard
        old = da_guard.DA_PHASE
        da_guard.DA_PHASE = "discovery"
        try:
            check_prop_seasons(df)  # should not raise
        finally:
            da_guard.DA_PHASE = old
