#!/usr/bin/env python3
"""N13/N17: test the no-pricing-number guard — must discard numeric pricing fields."""

import json, sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_pricing_number_discarded_and_logged():
    """A canned AI response containing pricing numbers must be discarded,
    and the discarded fields must be returned."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    canned = json.dumps({
        "flags": [{"flag": "rivalry_game", "headline": "test", "published": "2026-09-19T00:00:00Z"}],
        "rationale": "The spread is too wide.",
        "veto": False,
        "veto_reason": None,
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
            flags, rationale, veto, veto_reason, discarded = _call_ai_layer(
                [], [], "Home", "Away")

    # The discarded dict must contain the pricing fields
    assert "fair_spread" in discarded, f"fair_spread not discarded: {discarded}"
    assert discarded["fair_spread"] == -21.5
    assert "projected_total" in discarded
    assert discarded["projected_total"] == 52.0
    assert "win_probability" in discarded
    assert discarded["win_probability"] == 0.78

    # The returned structure must NOT contain them
    assert isinstance(flags, list)
    assert len(flags) == 1  # the rivalry_game flag survived
    assert rationale == "The spread is too wide."
    assert veto == False


def test_guard_with_no_pricing_fields():
    """A clean response produces an empty discarded dict."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    canned = json.dumps({
        "flags": [],
        "rationale": "Normal game.",
        "veto": False,
        "veto_reason": None,
    })

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=canned)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("ncaaf.pipeline.build_ncaaf_tickets.ANTHROPIC_KEY", "test_key"):
        with patch("anthropic.Anthropic", return_value=mock_client):
            flags, rationale, veto, veto_reason, discarded = _call_ai_layer(
                [], [], "Home", "Away")

    assert discarded == {}, f"Expected empty discarded, got {discarded}"


def test_api_failure_raises():
    """An API failure must raise, not write to ai_rationale."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API down")

    with patch("ncaaf.pipeline.build_ncaaf_tickets.ANTHROPIC_KEY", "test_key"):
        with patch("anthropic.Anthropic", return_value=mock_client):
            with pytest.raises(RuntimeError, match="HALT"):
                _call_ai_layer([], [], "Home", "Away")
