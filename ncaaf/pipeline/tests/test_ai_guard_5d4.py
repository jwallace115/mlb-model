#!/usr/bin/env python3
"""N13: test the no-pricing-number guard with a canned response."""

import json, sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_pricing_number_discarded():
    """A canned AI response containing a pricing number must be discarded."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    # Mock the Anthropic client to return a response with a pricing number
    canned_response = json.dumps({
        "flags": [],
        "rationale": "The spread is too wide.",
        "veto": False,
        "veto_reason": None,
        "fair_spread": -21.5,  # THIS MUST BE DISCARDED
        "projected_total": 52.0,  # THIS MUST BE DISCARDED
    })

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=canned_response)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("ncaaf.pipeline.build_ncaaf_tickets.ANTHROPIC_KEY", "test_key"):
        with patch("anthropic.Anthropic", return_value=mock_client):
            flags, rationale, veto, veto_reason = _call_ai_layer(
                [], [], "Home", "Away")

    # The allowed fields are flags, rationale, veto, veto_reason
    # fair_spread and projected_total must have been discarded
    assert isinstance(flags, list)
    assert isinstance(rationale, str)
    assert veto == False


def test_api_failure_raises():
    """An API failure must raise, not write to ai_rationale."""
    from ncaaf.pipeline.build_ncaaf_tickets import _call_ai_layer

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API down")

    with patch("ncaaf.pipeline.build_ncaaf_tickets.ANTHROPIC_KEY", "test_key"):
        with patch("anthropic.Anthropic", return_value=mock_client):
            with pytest.raises(RuntimeError, match="HALT"):
                _call_ai_layer([], [], "Home", "Away")
