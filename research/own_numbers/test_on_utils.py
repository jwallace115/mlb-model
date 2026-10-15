"""
Behavioral tests for ON utilities (ON-D5).
Every test is a fixture that FAILS when the audited defect is reintroduced.
"""
import os, sys, zlib
import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.dirname(__file__))

from on_utils import (
    handicap_to_home_margin,
    compute_gap,
    is_confident,
    match_game_to_event,
    select_close_quote,
    select_decision_quote,
    stable_seed,
    kickoff_utc_from_nflverse,
    compute_prediction_cutoff,
    game_is_admitted,
    guard_2024,
)

ET = ZoneInfo("America/New_York")


# ═══════════════════════════════════════════════════════════════════════════
# 1a. SIGN NORMALISATION — the audit fixture
# ═══════════════════════════════════════════════════════════════════════════

class TestSignNormalisation:
    """Audit fixture: raw home −3, ours_m 2, err_m 2 → gap −1, NOT confident.
    The old code produced gap +5 and confident."""

    def test_home_fav_gap(self):
        """Home favored by 3 (handicap −3) → q = +3 → gap = 2 − 3 = −1."""
        h = -3.0  # home handicap: favored by 3
        ours_m = 2.0
        gap = compute_gap(ours_m, h)
        assert gap == pytest.approx(-1.0), f"gap should be -1.0, got {gap}"

    def test_home_fav_not_confident(self):
        """gap = −1, err_m = 2 → |gap| = 1 < err_m → NOT confident."""
        assert not is_confident(ours_m=2.0, h=-3.0, err_m=2.0)

    def test_old_code_would_give_wrong_gap(self):
        """The OLD bug: gap = ours_m − h = 2 − (−3) = +5.
        Verify that our corrected code does NOT produce +5."""
        gap = compute_gap(2.0, -3.0)
        assert gap != 5.0, "Got the OLD buggy gap of +5"

    def test_home_dog(self):
        """Home dog by 3 (handicap +3) → q = −3 → gap = 2 − (−3) = +5."""
        gap = compute_gap(2.0, 3.0)
        assert gap == pytest.approx(5.0)

    def test_home_dog_confident(self):
        """gap = +5, err_m = 2 → confident."""
        assert is_confident(ours_m=2.0, h=3.0, err_m=2.0)

    def test_pick_em(self):
        """Pick'em (handicap 0) → q = 0 → gap = ours_m."""
        gap = compute_gap(2.0, 0.0)
        assert gap == pytest.approx(2.0)

    def test_pick_em_confident(self):
        """gap = 2, err_m = 1.5 → confident (|gap| ≥ err_m AND ≥ 1)."""
        assert is_confident(ours_m=2.0, h=0.0, err_m=1.5)

    def test_pick_em_not_confident_small_gap(self):
        """gap = 0.5, err_m = 0.3 → |gap| ≥ err_m but < 1 → NOT confident."""
        assert not is_confident(ours_m=0.5, h=0.0, err_m=0.3)

    def test_handicap_to_margin_negates(self):
        assert handicap_to_home_margin(-3.0) == 3.0
        assert handicap_to_home_margin(3.0) == -3.0
        assert handicap_to_home_margin(0.0) == 0.0

    def test_none_handicap(self):
        assert handicap_to_home_margin(None) is None
        assert compute_gap(2.0, None) is None
        assert not is_confident(2.0, None, 1.0)

    def test_nan_handicap(self):
        assert handicap_to_home_margin(float("nan")) is None
        assert compute_gap(2.0, float("nan")) is None


# ═══════════════════════════════════════════════════════════════════════════
# 1b. EVENT IDENTITY
# ═══════════════════════════════════════════════════════════════════════════

def _make_spreads(events):
    """Helper: build a spreads DataFrame from a list of (event_id, team, commence_time) tuples."""
    rows = []
    for eid, team, ct in events:
        rows.append({
            "event_id": eid,
            "team_abbr": team,
            "commence_time": ct,
            "snapshot_utc": ct,
            "point": -3.0,
            "price": -110,
        })
    return pd.DataFrame(rows)


class TestEventMatching:

    def test_single_match(self):
        kick = datetime(2026, 9, 10, 0, 20, tzinfo=timezone.utc)
        spreads = _make_spreads([
            ("e1", "SEA", "2026-09-10T00:20:00Z"),
            ("e1", "NE", "2026-09-10T00:20:00Z"),
        ])
        eid = match_game_to_event("SEA", "NE", kick, 2026, spreads)
        assert eid == "e1"

    def test_rematch_selects_correct_meeting(self):
        """Two meetings of the same teams; each kickoff matches only its event."""
        kick1 = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        kick2 = datetime(2026, 12, 15, 17, 0, tzinfo=timezone.utc)
        spreads = _make_spreads([
            ("e_sep", "SEA", "2026-09-10T17:00:00Z"),
            ("e_sep", "NE", "2026-09-10T17:00:00Z"),
            ("e_dec", "SEA", "2026-12-15T17:00:00Z"),
            ("e_dec", "NE", "2026-12-15T17:00:00Z"),
        ])
        assert match_game_to_event("SEA", "NE", kick1, 2026, spreads) == "e_sep"
        assert match_game_to_event("SEA", "NE", kick2, 2026, spreads) == "e_dec"

    def test_ambiguous_halts(self):
        """Two events within ±1h for the same teams → HALT."""
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        spreads = _make_spreads([
            ("e1", "SEA", "2026-09-10T17:00:00Z"),
            ("e1", "NE", "2026-09-10T17:00:00Z"),
            ("e2", "SEA", "2026-09-10T17:30:00Z"),
            ("e2", "NE", "2026-09-10T17:30:00Z"),
        ])
        with pytest.raises(ValueError, match="ambiguous"):
            match_game_to_event("SEA", "NE", kick, 2026, spreads)

    def test_no_match_returns_none(self):
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        spreads = _make_spreads([
            ("e1", "BUF", "2026-09-10T17:00:00Z"),
            ("e1", "MIA", "2026-09-10T17:00:00Z"),
        ])
        assert match_game_to_event("SEA", "NE", kick, 2026, spreads) is None

    def test_wrong_kickoff_time_no_match(self):
        """Event commence_time > 1h from kickoff → no match."""
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        spreads = _make_spreads([
            ("e1", "SEA", "2026-09-10T20:00:00Z"),  # 3h off
            ("e1", "NE", "2026-09-10T20:00:00Z"),
        ])
        assert match_game_to_event("SEA", "NE", kick, 2026, spreads) is None


# ═══════════════════════════════════════════════════════════════════════════
# 1c. QUOTE SELECTION — close must be strictly pre-kick
# ═══════════════════════════════════════════════════════════════════════════

def _make_quotes(timestamps, point=-3.0):
    """Helper: build quotes DataFrame from a list of UTC timestamp strings."""
    return pd.DataFrame({
        "snapshot_utc": timestamps,
        "point": [point] * len(timestamps),
        "price": [-110] * len(timestamps),
    })


class TestQuoteSelection:

    def test_audit_fixture_in_play_rejected(self):
        """Audit fixture: 16:00Z and 19:00Z quotes for 17:00Z kick → close is 16:00Z.
        The old code returned 19:00Z (in-play)."""
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        quotes = _make_quotes(["2026-09-10T16:00:00Z", "2026-09-10T19:00:00Z"])
        row, flag = select_close_quote(quotes, kick)
        assert row is not None
        ts = pd.to_datetime(row["snapshot_utc"], utc=True)
        assert ts.hour == 16, f"Close should be 16:00Z, got {ts}"
        assert flag == "preferred"

    def test_no_pre_kick_returns_none(self):
        """All quotes after kickoff → no valid close."""
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        quotes = _make_quotes(["2026-09-10T18:00:00Z", "2026-09-10T19:00:00Z"])
        row, flag = select_close_quote(quotes, kick)
        assert row is None
        assert flag is None

    def test_stale_flag_when_old(self):
        """Only quote is > 3h before kick → flagged stale."""
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        quotes = _make_quotes(["2026-09-10T12:00:00Z"])
        row, flag = select_close_quote(quotes, kick)
        assert row is not None
        assert flag == "stale"

    def test_preferred_within_3h(self):
        """Quote 2h before kick → preferred."""
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        quotes = _make_quotes(["2026-09-10T15:00:00Z"])
        row, flag = select_close_quote(quotes, kick)
        assert flag == "preferred"

    def test_selects_latest_pre_kick(self):
        """Multiple pre-kick quotes → selects the latest one."""
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        quotes = _make_quotes([
            "2026-09-10T14:00:00Z",
            "2026-09-10T15:00:00Z",
            "2026-09-10T16:30:00Z",
        ])
        row, flag = select_close_quote(quotes, kick)
        ts = pd.to_datetime(row["snapshot_utc"], utc=True)
        assert ts.hour == 16 and ts.minute == 30

    def test_empty_quotes(self):
        kick = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)
        quotes = _make_quotes([])
        row, flag = select_close_quote(quotes, kick)
        assert row is None

    def test_decision_quote_before_cutoff(self):
        """Decision quote = last quote before prediction cutoff."""
        cutoff = datetime(2026, 9, 8, 16, 0, tzinfo=timezone.utc)  # Monday 12 ET = 16 UTC
        quotes = _make_quotes([
            "2026-09-08T14:00:00Z",
            "2026-09-08T15:30:00Z",
            "2026-09-08T17:00:00Z",  # after cutoff
        ])
        row = select_decision_quote(quotes, cutoff)
        ts = pd.to_datetime(row["snapshot_utc"], utc=True)
        assert ts.hour == 15 and ts.minute == 30


# ═══════════════════════════════════════════════════════════════════════════
# 2c. STABLE SEEDS — must NOT use Python hash()
# ═══════════════════════════════════════════════════════════════════════════

class TestStableSeeds:

    def test_deterministic_across_hashseeds(self):
        """Two calls with the same inputs must produce the same seed,
        regardless of PYTHONHASHSEED (zlib.crc32 is deterministic)."""
        s1 = stable_seed("2021_01_ARI_TEN", 0)
        s2 = stable_seed("2021_01_ARI_TEN", 0)
        assert s1 == s2

    def test_different_chunks_differ(self):
        s0 = stable_seed("2021_01_ARI_TEN", 0)
        s1 = stable_seed("2021_01_ARI_TEN", 1)
        assert s0 != s1

    def test_different_games_differ(self):
        s1 = stable_seed("2021_01_ARI_TEN", 0)
        s2 = stable_seed("2021_01_DAL_TB", 0)
        assert s1 != s2

    def test_not_python_hash(self):
        """The seed must NOT equal Python hash() — which varies by PYTHONHASHSEED."""
        crc_seed = stable_seed("2021_01_ARI_TEN", 0)
        # zlib.crc32 is well-defined; Python hash() is not across processes
        expected = zlib.crc32("2021_01_ARI_TEN:0".encode("utf-8")) & 0x7FFFFFFF
        assert crc_seed == expected

    def test_seed_is_positive_int(self):
        s = stable_seed("2021_01_ARI_TEN", 0)
        assert isinstance(s, int)
        assert 0 <= s < 2**31


# ═══════════════════════════════════════════════════════════════════════════
# 2a. MONDAY CUTOFF — MNF excluded
# ═══════════════════════════════════════════════════════════════════════════

class TestMondayCutoff:

    def test_cutoff_is_noon_et(self):
        cutoff = compute_prediction_cutoff("2026-10-13")
        # Monday Oct 13 2026 is EDT (UTC-4)
        assert cutoff.hour == 16  # 12 ET = 16 UTC in EDT
        assert cutoff.minute == 0

    def test_mnf_excluded(self):
        """Monday Night Football (20:15 ET) + 4h = 00:15 Tue → NOT < Mon noon."""
        cutoff = compute_prediction_cutoff("2026-10-13")
        # MNF kick: Monday 20:15 ET = Tue 00:15 UTC
        mnf_kick = datetime(2026, 10, 14, 0, 15, tzinfo=timezone.utc)
        assert not game_is_admitted(mnf_kick, cutoff)

    def test_sunday_game_admitted(self):
        """Sunday 13:00 ET game + 4h = 17:00 ET < Mon noon → admitted."""
        cutoff = compute_prediction_cutoff("2026-10-13")
        sun_kick = datetime(2026, 10, 12, 17, 0, tzinfo=timezone.utc)  # 13:00 ET
        assert game_is_admitted(sun_kick, cutoff)

    def test_dst_boundary_november(self):
        """DST ends first Sunday in November. Monday Nov 2 2026 = EST (UTC-5).
        Cutoff = 12:00 EST = 17:00 UTC, NOT 16:00 UTC."""
        cutoff = compute_prediction_cutoff("2026-11-02")
        # Nov 2 2026 is a Monday. Clocks fall back Nov 1.
        assert cutoff.hour == 17, f"Expected 17 UTC (EST), got {cutoff.hour}"
        assert cutoff.minute == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3b. 2024 GUARD
# ═══════════════════════════════════════════════════════════════════════════

class TestGuard2024:

    def test_halts_on_2024(self):
        with pytest.raises(RuntimeError, match="2024"):
            guard_2024(2024)

    def test_halts_on_2024_in_list(self):
        with pytest.raises(RuntimeError, match="2024"):
            guard_2024([2021, 2022, 2024])

    def test_allows_2021_2023(self):
        guard_2024(2021)
        guard_2024(2023)
        guard_2024([2021, 2022, 2023])

    def test_allows_2025_2026(self):
        guard_2024(2025)
        guard_2024(2026)


class TestKickoffConstruction:

    def test_nflverse_to_utc(self):
        """2021-09-13 20:15 ET → UTC."""
        kick = kickoff_utc_from_nflverse("2021-09-13", "20:15")
        # Sept 2021 is EDT (UTC-4)
        assert kick == datetime(2021, 9, 14, 0, 15, tzinfo=timezone.utc)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
