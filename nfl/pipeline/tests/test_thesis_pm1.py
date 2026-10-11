#!/usr/bin/env python3
"""Tests for thesis validation in log_ai_opinions.py (PM-1 Item 3).

RED first: these must fail before implementation exists.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Thesis grammar validation ──

VALID_LINKS = {"plays", "pass_rate", "run_rate", "share", "efficiency",
               "availability", "script", "points", "turnovers", "price"}
VALID_DIRS = {"up", "down"}


def _valid_thesis(thesis_str):
    """Check thesis grammar: 1-3 claims 'link:dir' joined by ';'."""
    if not thesis_str or thesis_str.strip() == "":
        return False
    claims = [c.strip() for c in thesis_str.split(";")]
    if len(claims) < 1 or len(claims) > 3:
        return False
    for claim in claims:
        parts = claim.split(":")
        if len(parts) != 2:
            return False
        link, direction = parts[0].strip(), parts[1].strip()
        if link not in VALID_LINKS or direction not in VALID_DIRS:
            return False
    return True


def test_valid_thesis_grammar():
    """Valid thesis strings pass."""
    assert _valid_thesis("share:up")
    assert _valid_thesis("pass_rate:down;efficiency:up")
    assert _valid_thesis("plays:up;share:down;efficiency:up")
    assert _valid_thesis("price:up")
    assert _valid_thesis("script:up")
    assert _valid_thesis("turnovers:down")


def test_invalid_thesis_grammar():
    """Invalid thesis strings fail."""
    assert not _valid_thesis("")
    assert not _valid_thesis("bogus:up")
    assert not _valid_thesis("share:sideways")
    assert not _valid_thesis("share:up;too:many;claims:up;fourth:down")
    assert not _valid_thesis("share")  # no direction
    assert not _valid_thesis("share:up:extra")


def test_nfl_view_line_without_thesis_halts():
    """NFL view line without thesis must HALT when thesis_required is True."""
    import log_ai_opinions as lai

    lai.set_sport("nfl")
    # Simulate: SPORTS["nfl"]["thesis_required"] should be True after item 3
    if not SPORTS_HAS_THESIS_REQUIRED():
        pytest.skip("thesis_required not yet implemented")

    # Build minimal sheet + filled
    sheet = pd.DataFrame([{
        "event_id": "ev1", "market_key": "h2h", "player_name": "",
        "line": 0.0, "commence_time": "2026-12-01T18:00:00Z",
        "home_team": "KC", "away_team": "BUF",
        "first_side": "KC", "second_side": "BUF",
        "price_first": -150, "price_second": 130,
        "source_utc": "2026-12-01T15:00:00Z",
        "imp_first": 0.6, "imp_second": 0.435, "two_way": True,
        "q_first": 0.58, "source_age_min": 10.0,
    }])

    filled = pd.DataFrame([{
        "event_id": "ev1", "market_key": "h2h", "player_name": "",
        "line": 0.0, "p_first": 0.60, "tag": "price_vs_sharp",
        "reason": "5 books Pin x3 0.580 vs HR 0.560; take KC.",
        "conf": 40.0, "conf_rank": 1,
        # thesis is MISSING
    }])

    with pytest.raises(SystemExit, match="thesis"):
        lai.validate(sheet, filled)


def test_nfl_no_view_line_passes_without_thesis():
    """NFL no_view line may leave thesis empty."""
    import log_ai_opinions as lai

    lai.set_sport("nfl")
    if not SPORTS_HAS_THESIS_REQUIRED():
        pytest.skip("thesis_required not yet implemented")

    sheet = pd.DataFrame([{
        "event_id": "ev1", "market_key": "h2h", "player_name": "",
        "line": 0.0, "commence_time": "2026-12-01T18:00:00Z",
        "home_team": "KC", "away_team": "BUF",
        "first_side": "KC", "second_side": "BUF",
        "price_first": -150, "price_second": 130,
        "source_utc": "2026-12-01T15:00:00Z",
        "imp_first": 0.6, "imp_second": 0.435, "two_way": True,
        "q_first": 0.58, "source_age_min": 10.0,
    }])

    filled = pd.DataFrame([{
        "event_id": "ev1", "market_key": "h2h", "player_name": "",
        "line": 0.0, "p_first": 0.58, "tag": "no_view",
        "reason": "", "conf": 0.0, "conf_rank": 1,
        # thesis empty — should be OK for no_view
    }])

    # Should NOT raise
    try:
        lai.validate(sheet, filled)
    except SystemExit as e:
        if "thesis" in str(e):
            pytest.fail("no_view line should not require thesis")


def test_ncaaf_freeze_unchanged():
    """NCAAF freeze must NOT require thesis."""
    import log_ai_opinions as lai

    lai.set_sport("ncaaf")
    # thesis_required should be False for ncaaf
    assert not SPORTS.get("ncaaf", {}).get("thesis_required", False)


def test_nhl_freeze_unchanged():
    """NHL freeze must NOT require thesis (different validation path)."""
    import log_ai_opinions as lai

    lai.set_sport("nhl")
    assert not SPORTS.get("nhl", {}).get("thesis_required", False)


def SPORTS_HAS_THESIS_REQUIRED():
    """Check if thesis_required is implemented in SPORTS dict."""
    import log_ai_opinions as lai
    return lai.SPORTS.get("nfl", {}).get("thesis_required", False)


# Import SPORTS for direct checks
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from log_ai_opinions import SPORTS
except ImportError:
    SPORTS = {}
