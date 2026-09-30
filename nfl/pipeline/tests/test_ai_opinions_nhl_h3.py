"""H3 tests: NHL entry in freeze tool — date-keyed slates, drivers, tag scoping."""
import sys, json, hashlib, tempfile, shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import nfl.pipeline.log_ai_opinions as L

FIXTURE = Path(__file__).parent / "fixtures" / "nhl_tape_20260929T2000Z.parquet"
# freeze time before any game in the fixture (snap is 20:00Z 2026-09-29, games start 21:00Z+)
NOW = datetime(2026, 9, 29, 20, 5, tzinfo=timezone.utc)


def _nhl_sheet(slate_date="2026-09-29"):
    """Build an NHL sheet from the fixture for a specific slate date."""
    L.set_sport("nhl")
    lines = pd.read_parquet(FIXTURE)
    props = pd.DataFrame(columns=["bookmaker", "commence_time", "home_team", "away_team",
                                   "market_key", "player_name", "line", "over_price",
                                   "under_price", "pull_timestamp", "event_id"])
    return L.build_sheet(props, lines, NOW, slate_date=slate_date)


def _filled(sheet, tag="matchup", drivers="market,history"):
    """Build a filled sheet with valid NHL columns."""
    f = sheet[L.KEY].copy()
    f["p_first"] = sheet["q_first"] + 0.02  # small gap so side != "none"
    f["p_first"] = f["p_first"].clip(L.P_MIN, L.P_MAX)
    f["tag"] = tag
    f["reason"] = "test reason for NHL" + " " * 5
    f["conf"] = list(range(100, 100 - len(f), -1))
    f["conf_rank"] = list(range(1, len(f) + 1))
    f["drivers"] = drivers
    return f


class TestDateSlate:
    def setup_method(self):
        L.set_sport("nhl")

    def teardown_method(self):
        L.set_sport("nfl")

    def test_date_filter_keeps_only_that_date(self):
        """Only games on 2026-09-29 ET are in the sheet."""
        s = _nhl_sheet("2026-09-29")
        assert len(s) > 0
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        for _, r in s.iterrows():
            ct = L.parse_utc(r["commence_time"]).astimezone(et)
            assert ct.date().isoformat() == "2026-09-29", f"{r['event_id']} on {ct.date()}"
        # The fixture has games on 2026-09-30 ET — they must NOT appear
        all_games = _nhl_sheet(None)
        assert len(all_games) > len(s), "Fixture must have games on other dates"

    def test_mutation_no_date_filter_includes_other_days(self):
        """MUTATION: without the date filter, other days' games appear."""
        s_all = _nhl_sheet(None)
        s_29 = _nhl_sheet("2026-09-29")
        assert len(s_all) > len(s_29)

    def test_next_day_games_excluded(self):
        """Games that fall on 2026-09-30 ET are NOT in the 2026-09-29 sheet."""
        s = _nhl_sheet("2026-09-29")
        s30 = _nhl_sheet("2026-09-30")
        common = set(s["event_id"]) & set(s30["event_id"])
        assert len(common) == 0, f"Events overlap: {common}"


class TestDrivers:
    def setup_method(self):
        L.set_sport("nhl")

    def teardown_method(self):
        L.set_sport("nfl")

    def test_missing_drivers_halts(self):
        s = _nhl_sheet("2026-09-29")
        f = _filled(s)
        f = f.drop(columns=["drivers"])
        with pytest.raises(SystemExit, match="missing 'drivers'"):
            L.validate(s, f)

    def test_empty_drivers_halts(self):
        s = _nhl_sheet("2026-09-29")
        f = _filled(s, drivers="")
        with pytest.raises(SystemExit, match="empty drivers"):
            L.validate(s, f)

    def test_unknown_driver_halts(self):
        s = _nhl_sheet("2026-09-29")
        f = _filled(s, drivers="market,weather")
        with pytest.raises(SystemExit, match="unknown driver"):
            L.validate(s, f)

    def test_valid_drivers_pass(self):
        s = _nhl_sheet("2026-09-29")
        f = _filled(s, drivers="history,market,news")
        m = L.validate(s, f)
        # drivers are sorted, unique, comma-separated
        assert all(m["drivers"] == "history,market,news")


class TestNHLTags:
    def setup_method(self):
        L.set_sport("nhl")

    def teardown_method(self):
        L.set_sport("nfl")

    def test_no_view_halts_for_nhl(self):
        """no_view is not in the NHL tag set."""
        s = _nhl_sheet("2026-09-29")
        f = _filled(s, tag="no_view")
        f["reason"] = ""
        f["p_first"] = s["q_first"]
        with pytest.raises(SystemExit, match="unknown tag"):
            L.validate(s, f)

    def test_weather_tag_halts_for_nhl(self):
        """'weather' is a football-only tag and must be rejected for NHL."""
        s = _nhl_sheet("2026-09-29")
        f = _filled(s, tag="weather")
        with pytest.raises(SystemExit, match="unknown tag"):
            L.validate(s, f)

    def test_valid_nhl_tag_passes(self):
        s = _nhl_sheet("2026-09-29")
        f = _filled(s, tag="goalie")
        m = L.validate(s, f)
        assert (m["tag"] == "goalie").all()


class TestNHLWithoutDate:
    def test_nhl_sheet_without_date_cli(self):
        """NHL without --date must HALT (checked in main)."""
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "nfl.pipeline.log_ai_opinions",
             "sheet", "--sport", "nhl", "--out", "/dev/null"],
            capture_output=True, text=True, cwd=str(ROOT))
        assert r.returncode != 0
        assert "HALT" in r.stderr or "HALT" in r.stdout


class TestNHLSeasonRule:
    def test_season_2026_from_october(self):
        assert L.nhl_season("2026-10-01") == 2026

    def test_season_2026_from_march(self):
        """2027-03-15 is mid-season 2026-27, so season = 2026."""
        assert L.nhl_season("2027-03-15") == 2026

    def test_season_2026_from_july(self):
        assert L.nhl_season("2026-07-01") == 2026

    def test_season_2025_from_june(self):
        assert L.nhl_season("2026-06-30") == 2025


class TestNHLFreeze:
    def setup_method(self):
        L.set_sport("nhl")
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        L.set_sport("nfl")
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_freeze_writes_slate_date_not_week(self):
        s = _nhl_sheet("2026-09-29")
        f = _filled(s)
        d = self.tmpdir / "date=2026-09-29" / "ai_opinions"
        dest, sha, m = L.freeze(s, f, 2026, None, True, NOW, d=d,
                                reader_model="test-model", slate_date="2026-09-29")
        assert "slate_date" in m.columns
        assert (m["slate_date"] == "2026-09-29").all()
        assert "week" not in m.columns

    def test_freeze_season_from_date(self):
        s = _nhl_sheet("2026-09-29")
        f = _filled(s)
        d = self.tmpdir / "date=2026-09-29" / "ai_opinions"
        dest, sha, m = L.freeze(s, f, 2026, None, True, NOW, d=d,
                                reader_model="test-model", slate_date="2026-09-29")
        assert (m["season"] == 2026).all()


class TestFootballUnchanged:
    """NULL CONTROL: football freeze and verify produce identical results."""

    def test_nfl_verify_unchanged(self):
        L.set_sport("nfl")
        for wk, expected_shas in [
            (2, ["5608e10f452689b6"]),
            (3, ["4e597ba013c62511", "cc0eb46725eae9a6", "c7f59a147a436b8b"]),
        ]:
            entries, bad, unlisted = L.verify(2026, wk)
            assert bad == [], f"NFL wk{wk} bad={bad}"
            assert unlisted == [], f"NFL wk{wk} unlisted={unlisted}"
            for e, expected_prefix in zip(entries, expected_shas):
                assert e["sha256"].startswith(expected_prefix), (
                    f"NFL wk{wk} {e['file']}: expected sha prefix {expected_prefix}, "
                    f"got {e['sha256'][:16]}")

    def test_ncaaf_verify_unchanged(self):
        L.set_sport("ncaaf")
        entries, bad, unlisted = L.verify(2026, 4)
        assert bad == [], f"NCAAF wk4 bad={bad}"
        assert unlisted == [], f"NCAAF wk4 unlisted={unlisted}"
        expected_shas = ["504e1fb61af566f6", "d329749b92c823bc"]
        for e, expected_prefix in zip(entries, expected_shas):
            assert e["sha256"].startswith(expected_prefix), (
                f"NCAAF wk4 {e['file']}: expected sha prefix {expected_prefix}, "
                f"got {e['sha256'][:16]}")
        L.set_sport("nfl")

    def test_football_tags_unchanged(self):
        """Football tags are the same as the original TAGS constant."""
        expected = ("injury_news", "role_change", "game_script", "matchup", "weather",
                    "price_vs_sharp", "usage_trend", "line_move", "no_view", "sim_v1")
        assert L.SPORTS["nfl"]["tags"] == expected
        assert L.SPORTS["ncaaf"]["tags"] == expected
        assert L.TAGS == expected

    def test_football_no_drivers_required(self):
        """Football does not require drivers."""
        assert not L.SPORTS["nfl"].get("drivers_required", False)
        assert not L.SPORTS["ncaaf"].get("drivers_required", False)
