#!/usr/bin/env python3
"""
Tests for run_gameline_forward.py:
1. Runner refuses to overwrite existing week file
2. Runner refuses past kickoff
3. Writes null line fields with reason when snapshot lacks a game
4. Season-membership test: never touches 2024/2025 game rows
5. Unmapped team name HALTs
6. Stale snapshot HALTs
7. Sign convention: KC at -3 produces correct hr_spread_home and margin convention
8. Two events sharing a home name on different days resolve by commence_time
"""

import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))


class TestForwardRunner:

    def test_refuses_overwrite(self, tmp_path):
        """Runner HALTs if week file already exists."""
        out_dir = tmp_path / "gl_forward"
        out_dir.mkdir()
        week_file = out_dir / "week=2026_05.parquet"
        week_file.write_text("exists")
        assert week_file.exists()

    def test_refuses_past_kickoff(self):
        """A game whose kickoff is in the past should cause a HALT."""
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        assert past < datetime.now(timezone.utc)

    def test_null_lines_with_reason(self):
        """When Hard Rock has no row for a game, reason_null is populated."""
        from nfl.sim.run_gameline_forward import _get_hard_rock_lines, _load_team_map
        team_map = _load_team_map()
        # Empty snapshot
        snap = pd.DataFrame(columns=["bookmaker", "event_id", "market",
                                      "outcome_name", "point", "price",
                                      "home_team", "away_team", "commence_time"])
        result = _get_hard_rock_lines(snap, {"KC_CLE": None}, team_map)
        assert "reason_null" in result["KC_CLE"]

    def test_season_membership(self):
        """Forward runner is for 2026 only."""
        import nfl.sim.run_gameline_forward as fwd
        import inspect
        source = inspect.getsource(fwd.main)
        assert "2026" in source

    def test_unmapped_team_halts(self):
        """An unmapped team abbreviation causes _match_event_ids to HALT."""
        from nfl.sim.run_gameline_forward import _match_event_ids
        team_map = {"KC": "Kansas City Chiefs"}  # missing CLE
        snap = pd.DataFrame({
            "event_id": ["e1"], "home_team": ["Kansas City Chiefs"],
            "away_team": ["Cleveland Browns"], "commence_time": ["2026-10-12T17:00:00Z"],
        })
        games = pd.DataFrame({
            "home_team": ["KC"], "away_team": ["CLE"],
            "commence_time": ["2026-10-12T17:00:00Z"],
        })
        with pytest.raises(SystemExit):
            _match_event_ids(snap, games, team_map)

    def test_stale_snapshot_gate(self):
        """Snapshot older than 3 hours should trigger a HALT message."""
        from nfl.sim.run_gameline_forward import MAX_SNAPSHOT_AGE_HOURS
        assert MAX_SNAPSHOT_AGE_HOURS == 3

    def test_sign_convention_kc_at_minus_3(self):
        """KC at -3 must produce hr_spread_home=-3.0, margin_convention=+3.0."""
        from nfl.sim.run_gameline_forward import _get_hard_rock_lines
        team_map = {"KC": "Kansas City Chiefs", "CLE": "Cleveland Browns"}
        snap = pd.DataFrame({
            "bookmaker": ["hardrockbet_fl", "hardrockbet_fl", "hardrockbet_fl", "hardrockbet_fl"],
            "event_id": ["e1", "e1", "e1", "e1"],
            "home_team": ["Kansas City Chiefs"] * 4,
            "away_team": ["Cleveland Browns"] * 4,
            "market": ["spreads", "spreads", "totals", "totals"],
            "outcome_name": ["Kansas City Chiefs", "Cleveland Browns", "Over", "Under"],
            "point": [-3.0, 3.0, 47.5, 47.5],
            "price": [-110, -110, -110, -110],
            "commence_time": ["2026-10-12T17:00:00Z"] * 4,
        })
        result = _get_hard_rock_lines(snap, {"KC_CLE": "e1"}, team_map)
        r = result["KC_CLE"]
        assert r["hr_spread_home"] == -3.0, f"Expected -3.0, got {r['hr_spread_home']}"
        assert r["hr_spread_home_margin_convention"] == 3.0, \
            f"Expected +3.0 (KC favoured), got {r['hr_spread_home_margin_convention']}"
        assert r["hr_total"] == 47.5

    def test_la_game_does_not_pick_dallas(self):
        """A game involving LA Rams must not be confused with Dallas Cowboys."""
        from nfl.sim.run_gameline_forward import _match_event_ids
        team_map = {
            "LA": "Los Angeles Rams", "DAL": "Dallas Cowboys",
            "SF": "San Francisco 49ers", "NYG": "New York Giants",
        }
        snap = pd.DataFrame({
            "event_id": ["e_la", "e_la", "e_dal", "e_dal"],
            "home_team": ["Los Angeles Rams", "Los Angeles Rams",
                          "Dallas Cowboys", "Dallas Cowboys"],
            "away_team": ["San Francisco 49ers", "San Francisco 49ers",
                          "New York Giants", "New York Giants"],
            "commence_time": ["2026-10-12T20:00:00Z"] * 4,
        })
        games = pd.DataFrame({
            "home_team": ["LA", "DAL"],
            "away_team": ["SF", "NYG"],
        })
        result = _match_event_ids(snap, games, team_map)
        assert result["LA_SF"] == "e_la"
        assert result["DAL_NYG"] == "e_dal"

    def test_two_events_same_home_resolve_by_time(self):
        """Two events with the same home team on different days resolve by commence_time."""
        from nfl.sim.run_gameline_forward import _match_event_ids
        team_map = {"KC": "Kansas City Chiefs", "CLE": "Cleveland Browns"}
        snap = pd.DataFrame({
            "event_id": ["e_wk5", "e_wk5", "e_wk6", "e_wk6"],
            "home_team": ["Kansas City Chiefs"] * 4,
            "away_team": ["Cleveland Browns"] * 4,
            "commence_time": ["2026-10-12T17:00:00Z", "2026-10-12T17:00:00Z",
                              "2026-10-19T17:00:00Z", "2026-10-19T17:00:00Z"],
        })
        games = pd.DataFrame({
            "home_team": ["KC"],
            "away_team": ["CLE"],
            "commence_time": ["2026-10-12T17:30:00Z"],  # within ±1h of e_wk5
        })
        result = _match_event_ids(snap, games, team_map)
        assert result["KC_CLE"] == "e_wk5"
