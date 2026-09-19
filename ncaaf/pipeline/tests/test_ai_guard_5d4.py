#!/usr/bin/env python3
"""N13/N17/N20: test the no-pricing-number guard and API failure handling."""

import json, sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

_MOCK_MATCHUP = {
    "favourite": "Team A", "underdog": "Team B", "spread_magnitude": 7.0,
    "total_line": 50.0,
    "fav_row": {"outcome_name": "Team A", "consensus_point": -7.0, "dispersion": 1.0},
    "dog_row": {"outcome_name": "Team B", "consensus_point": 7.0, "dispersion": 1.0},
    "over_row": {"outcome_name": "Over", "consensus_point": 50.0, "dispersion": 0.5},
    "totals": [
        {"outcome_name": "Over", "consensus_point": 50.0},
        {"outcome_name": "Under", "consensus_point": 50.0},
    ],
}


def test_pricing_number_discarded_and_logged():
    """A canned AI response containing pricing numbers must be discarded."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    canned = json.dumps({
        "legs": [{"market": "spreads", "side": "Team A", "point": -7.0, "reason": "test"}],
        "abstain": False, "abstain_reason": None,
        "flags": [], "rationale": "test",
        "fair_spread": -21.5,
        "projected_total": 52.0,
        "win_probability": 0.78,
    })

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=canned)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("ncaaf.pipeline.build_ncaaf_tickets.ANTHROPIC_KEY", "test_key"):
        with patch("anthropic.Anthropic", return_value=mock_client):
            result, discarded = _call_ai_layer(_MOCK_MATCHUP, [], "Home", "Away")

    assert "fair_spread" in discarded, f"fair_spread not discarded: {discarded}"
    assert discarded["fair_spread"] == -21.5
    assert "projected_total" in discarded
    assert "win_probability" in discarded
    # Allowed fields survived
    assert "legs" in result
    assert "rationale" in result


def test_guard_with_no_pricing_fields():
    """A clean response produces an empty discarded dict."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    canned = json.dumps({
        "legs": [], "abstain": True, "abstain_reason": "no edge",
        "flags": [], "rationale": "Normal game.",
    })

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=canned)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("ncaaf.pipeline.build_ncaaf_tickets.ANTHROPIC_KEY", "test_key"):
        with patch("anthropic.Anthropic", return_value=mock_client):
            result, discarded = _call_ai_layer(_MOCK_MATCHUP, [], "Home", "Away")

    assert discarded == {}


def test_api_failure_raises():
    """An API failure must raise."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API down")

    with patch("ncaaf.pipeline.build_ncaaf_tickets.ANTHROPIC_KEY", "test_key"):
        with patch("anthropic.Anthropic", return_value=mock_client):
            with pytest.raises(RuntimeError, match="HALT"):
                _call_ai_layer(_MOCK_MATCHUP, [], "Home", "Away")
