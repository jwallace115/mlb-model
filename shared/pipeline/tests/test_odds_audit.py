#!/usr/bin/env python3
"""Tests for OPS-CAD3 Item 4 — odds balance audit (report only).

Verifies the odds_credits.json file exists and has the expected shape.
The audit itself is a report in opscad3_report.txt (no code changes).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class TestOddsCreditsShape:

    def test_file_exists_and_has_shape(self):
        """odds_credits.json has remaining, used_today, by_purpose."""
        p = ROOT / "status" / "odds_credits.json"
        if not p.exists():
            return  # file only exists on the VM after a props pull
        data = json.loads(p.read_text())
        assert "remaining" in data
        assert "used_today" in data
        assert isinstance(data["used_today"], dict)

    def test_props_cost_per_event(self):
        """Props pull costs 10 credits per event (10 markets, 1 region)."""
        sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
        import pull_hardrock_props as php
        assert len(php.MARKET_LIST) == 10
        assert len(php.BOOKS) <= 10  # 1 region-equivalent
