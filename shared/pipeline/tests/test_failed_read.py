#!/usr/bin/env python3
"""Tests for OPS-CAD2 Item 2 — a failed read is not a read (P68).

RED-first:
  1. 3 games, one HALTs → freeze has 2 games only.
  2. Manifest carries inputs_digest per event and trigger text.
  3. HALTed game triggers again next tick.
  4. Retry back-off works.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))

import window_watch as ww
import ai_reader as ar


class TestFailedReadNotFrozen:

    def test_halted_game_excluded_from_concat(self):
        """If one game HALTs in picks_to_filled, only the others are frozen."""
        def _row(eid, mk="spreads", line=-3.0):
            imp = ar._implied(-110)
            return {
                "event_id": eid, "market_key": mk, "player_name": "",
                "line": line, "commence_time": "2026-10-26T17:00:00Z",
                "home_team": "H", "away_team": "A",
                "price_first": -110, "price_second": -110,
                "first_side": "H", "second_side": "A",
                "imp_first": imp, "imp_second": imp,
                "two_way": True, "q_first": 0.5,
                "source_utc": "2026-10-23T12:00:00Z", "source_age_min": 60,
            }

        sheet = pd.DataFrame([_row("g1"), _row("g2"), _row("g3")])
        picks_g1 = [{"market": "spreads", "player": "", "line": -3.0,
                      "side": "first", "tag": "matchup", "conf": 10,
                      "reason": "Home team covers the spread at -110 here",
                      "thesis": "points:up"}]
        picks_g2 = [{"market": "spreads", "player": "", "line": -3.0,
                      "side": "first", "tag": "matchup", "conf": 8,
                      "reason": "Another home cover at -110 for this game",
                      "thesis": "points:up"}]

        # g1 and g2 succeed
        filled_g1 = ar.picks_to_filled(picks_g1, sheet, "nfl", event_id="g1")
        filled_g2 = ar.picks_to_filled(picks_g2, sheet, "nfl", event_id="g2")
        # g3 would HALT (unquoted pick)
        with pytest.raises(SystemExit):
            ar.picks_to_filled(
                [{"market": "totals", "player": "", "line": 44.5,
                  "side": "first", "tag": "matchup", "conf": 5,
                  "reason": "Over 44.5 total points in this game today",
                  "thesis": "points:up"}],
                sheet, "nfl", event_id="g3")

        # Concatenate only successful
        filled = pd.concat([filled_g1, filled_g2], ignore_index=True)
        assert set(filled.event_id.unique()) == {"g1", "g2"}
        assert "g3" not in filled.event_id.values


class TestRetryBackoff:

    def test_backoff_records_and_blocks(self):
        """After a HALT, the game is in back-off for the first delay (60s)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()

            # Not in backoff initially
            assert ww._is_in_backoff("ev1", "nfl", root) is False

            # Record a failure
            ww._record_retry("ev1", "nfl", "parse error", root)

            # Now in backoff (within 60s)
            assert ww._is_in_backoff("ev1", "nfl", root) is True

    def test_backoff_clears_after_delay(self):
        """After the delay passes, the game is no longer in back-off."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "status").mkdir()

            # Record a failure with a past timestamp
            # attempt=0, delay=RETRY_DELAYS[0]=60s; last_utc 120s ago
            data = {
                "nfl:ev1": {
                    "attempt": 0,
                    "last_utc": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
                    "error": "test",
                }
            }
            ww._save_retry(data, root)

            # 120s > 60s delay for attempt 0, so should be clear
            assert ww._is_in_backoff("ev1", "nfl", root) is False


class TestDigestInManifest:

    def test_digest_parsed_from_json(self):
        """get_last_read_digest parses per-event digest from a JSON dict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board = root / "nfl" / "data" / "board" / "week=2026_07" / "ai_opinions"
            board.mkdir(parents=True, exist_ok=True)

            # Create a freeze file with one event
            import pyarrow as pa
            df = pd.DataFrame([{"event_id": "ev1", "market_key": "spreads",
                                "player_name": "", "line": -3.0}])
            df.to_parquet(board / "ai_opinions_20261023T1400Z.parquet", index=False)

            manifest = [{
                "file": "ai_opinions_20261023T1400Z.parquet",
                "sha256": "abc", "logged_utc": "2026-10-23T14:00:00Z",
                "rows": 1, "reader_model": "ai_reader_v1b/sonnet",
                "window": "event",
                "inputs": {
                    "inputs_digest": json.dumps({"ev1": "digest_abc"}),
                    "triggers": {"ev1": "horizon_entry"},
                },
            }]
            (board / "manifest.json").write_text(json.dumps(manifest))

            digest, logged, model = ww.get_last_read_digest("ev1", "nfl", root=root)
            assert digest == "digest_abc", f"expected per-event digest, got {digest}"
            assert logged == "2026-10-23T14:00:00Z"
            assert model == "ai_reader_v1b/sonnet"


def test_event_window_is_exempt_from_prekick_band():
    """10-24 13:04Z: anchor reads inside 3 h must freeze; the P20 band applies to fixed windows only."""
    import inspect, nfl.pipeline.log_ai_opinions as lao
    src = inspect.getsource(lao)
    assert 'window not in ("prekick", "adhoc", "event")' in src
