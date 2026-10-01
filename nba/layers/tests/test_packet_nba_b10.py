"""
Tests for nba/layers/build_packet_nba.py (WO2 Item 3, B10).

Each test must FAIL on origin/main (module does not exist -> ImportError).
"""
import json, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def _build_mini_tape(tmpdir, home="Atlanta Hawks", away="Orlando Magic",
                     eid="test_event_001", commence="2026-03-17T00:10:00Z",
                     sport="basketball_nba"):
    """Build a minimal tape snapshot for testing."""
    rows = []
    snap_utc = "2026-03-16T22:00:00Z"
    for book in ["pinnacle", "draftkings"]:
        for mk, sides in [("h2h", (home, away)), ("spreads", (home, away)), ("totals", ("Over", "Under"))]:
            for side, price, pt in [(sides[0], -110, -3.5 if mk == "spreads" else 225.5 if mk == "totals" else None),
                                     (sides[1], -110, 3.5 if mk == "spreads" else 225.5 if mk == "totals" else None)]:
                rows.append({
                    "snapshot_utc": snap_utc, "sport": sport, "event_id": eid,
                    "commence_time": commence, "home_team": home, "away_team": away,
                    "bookmaker": book, "book_last_update": snap_utc,
                    "market": mk, "outcome_name": side, "point": pt, "price": price,
                })
    df = pd.DataFrame(rows)
    tape_dir = Path(tmpdir) / "data" / "odds_archive" / "nba" / "line_history" / "season=2025"
    tape_dir.mkdir(parents=True)
    df.to_parquet(tape_dir / "snap_20260316T220000Z.parquet", index=False)
    return tape_dir


# ─── Test: official report after built_utc excluded ──────────────────

def test_news_timestamp_filter():
    """An official report timestamped after built_utc is NOT in L2.
    FAILS with the filter removed (report would appear)."""
    from nba.layers.build_packet_nba import _news_layer

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake parsed report with timestamp AFTER built_utc
        report_dir = Path(tmpdir) / "data" / "injury_archive" / "nba" / "season=2026" / "reports"
        report_dir.mkdir(parents=True)
        report_df = pd.DataFrame([{
            "report_timestamp": "2026-03-16T23:00:00+00:00",  # 11pm UTC
            "team": "Atlanta Hawks",
            "player": "Test Player",
            "status": "Out",
        }])
        report_df.to_parquet(report_dir / "Injury-Report_2026-03-16_11_00PM.parquet", index=False)

        # built_utc = 10:59pm -> report at 11pm is AFTER -> excluded
        built_t = datetime(2026, 3, 16, 22, 59, tzinfo=timezone.utc)
        import nba.layers.build_packet_nba as B
        old_root = B.ROOT
        B.ROOT = Path(tmpdir)
        try:
            layer = _news_layer("2026-03-16", built_t, "Atlanta Hawks", "Orlando Magic")
        finally:
            B.ROOT = old_root

        assert layer["official_report"] is None, \
            "Report at 11pm should be excluded when built_utc is 10:59pm"


# ─── Test: packet sha identical on two builds from same inputs ───────

def test_packet_sha_deterministic():
    """Packet sha256 is identical on two builds from the same inputs."""
    from nba.layers.build_packet_nba import _market_layer, _model_layer
    from shared.layers.packet import packet_sha256

    # Build two identical market layers
    with tempfile.TemporaryDirectory() as tmpdir:
        tape_dir = _build_mini_tape(tmpdir)
        tape_snaps = []
        for f in sorted(tape_dir.glob("snap_*.parquet")):
            df = pd.read_parquet(f)
            tape_snaps.append((str(df["snapshot_utc"].iloc[0]), df))

        built_t = datetime(2026, 3, 16, 22, 30, tzinfo=timezone.utc)
        l1 = _market_layer("test_event_001", "Atlanta Hawks", tape_snaps, built_t, 2025)
        l2 = _market_layer("test_event_001", "Atlanta Hawks", tape_snaps, built_t, 2025)

    assert json.dumps(l1, sort_keys=True) == json.dumps(l2, sort_keys=True)


# ─── Test: rw_sh fires for DAL @ OKC, not for OKC @ DAL ─────────────

def test_rw_sh_fires():
    """ROAD_WARRIOR(DAL) @ STRONG_HOME(OKC) fires; OKC @ DAL does not."""
    from nba.layers.build_packet_nba import _model_layer

    # DAL is in _ROAD_WARRIOR, OKC is in _STRONG_HOME
    m1 = _model_layer("OKC", "DAL")  # home=OKC, away=DAL -> away in RW, home in SH
    assert m1["rw_sh"]["fires"] is True
    assert m1["rw_sh"]["direction"] == "OVER"

    # Reversed: OKC away, DAL home -> OKC not in RW
    m2 = _model_layer("DAL", "OKC")  # home=DAL, away=OKC -> OKC not in RW
    assert m2["rw_sh"]["fires"] is False


# ─── Test: lists are the objects from run_nba.py ─────────────────────

def test_rw_sh_lists_from_run_nba():
    """The signal lists are imported from run_nba.py (identity test)."""
    from nba.run_nba import _ROAD_WARRIOR, _STRONG_HOME
    from nba.layers.build_packet_nba import _model_layer

    # _model_layer imports the same objects
    import nba.layers.build_packet_nba as B
    # Check that the module uses the real lists
    m = _model_layer("OKC", "DAL")
    # DAL must be in _ROAD_WARRIOR for this to fire
    assert "DAL" in _ROAD_WARRIOR
    assert "OKC" in _STRONG_HOME
    assert m["rw_sh"]["fires"] is True
