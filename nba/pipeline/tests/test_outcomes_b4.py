"""
Tests for nba/pipeline/nba_outcomes.py (WO1 Item 3, B4).

Each test uses real data and must FAIL on a stated mutation.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nba.pipeline.nba_outcomes import _ODDS_TO_ABBR, _ESPN_TO_ABBR, fetch_scoreboard


def test_all_30_odds_api_names_map():
    """All 30 Odds API team names have a mapping.
    Source: data/odds_archive/nba/game_markets/season=2026/month=03/data_2026_03.parquet."""
    import pandas as pd
    pq = ROOT / "data" / "odds_archive" / "nba" / "game_markets" / "season=2026" / "month=03" / "data_2026_03.parquet"
    df = pd.read_parquet(pq)
    odds_teams = sorted(set(df["home_team"].unique()) | set(df["away_team"].unique()))
    assert len(odds_teams) == 30, f"Expected 30 teams, got {len(odds_teams)}"
    unmapped = [t for t in odds_teams if t not in _ODDS_TO_ABBR]
    assert unmapped == [], f"Unmapped Odds API teams: {unmapped}"


def test_ot_game_total_includes_ot():
    """An OT game's total includes overtime (not just periods 1-4).
    MUTATION: sum only periods 1-4 -> FAIL (total would be 250, not 269).

    Fixture: DEN vs POR 2026-04-06, ESPN periods=5, total=269.
    Regulation linescores: DEN [31,27,29,38] + POR [35,37,29,24] = 250.
    OT: DEN 12 + POR 7 = 19. Full total = 269."""
    games = fetch_scoreboard("20260406")
    ot_game = None
    for g in games:
        if g["home"] == "DEN" and g["away"] == "POR":
            ot_game = g
            break
    assert ot_game is not None, "DEN vs POR not found on 2026-04-06"
    assert ot_game["went_to_ot"] is True, "Expected OT game"
    assert ot_game["periods"] > 4, f"Expected periods > 4, got {ot_game['periods']}"
    total = ot_game["home_score"] + ot_game["away_score"]
    assert total == 269, f"Full-game total should be 269 (incl OT), got {total}"
    # If we only summed periods 1-4, we'd get 250 — the test would fail
    assert total != 250, "Total must NOT be regulation-only (250)"
