"""Tests for pull_ncaaf_results archive + crosswalk integration (P53).

(a) _load_ncaaf_officials picks the newest archive file
(b) pull_ncaaf_results HALTs on < 500 rows
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import event_crosswalk as xw


class TestLoadNcaafOfficials:
    """_load_ncaaf_officials on a temp archive dir picks the newest file."""

    def test_picks_newest_archive(self, tmp_path):
        archive_dir = tmp_path / "data" / "results_archive" / "ncaaf"
        archive_dir.mkdir(parents=True)

        # Write two archive files with different data
        cols = {"id": [1], "season": [2026], "week": [1], "seasonType": ["regular"],
                "startDate": ["2026-09-05T00:00:00Z"], "completed": [False],
                "homeTeam": ["OldTeam"], "awayTeam": ["OtherTeam"],
                "homePoints": [None], "awayPoints": [None], "neutralSite": [False]}
        old = pd.DataFrame(cols)
        old.to_parquet(archive_dir / "cfbd_games_2026_20261010T093000Z.parquet", index=False)

        cols["homeTeam"] = ["NewTeam"]
        cols["completed"] = [True]
        cols["homePoints"] = [28]
        cols["awayPoints"] = [14]
        new = pd.DataFrame(cols)
        new.to_parquet(archive_dir / "cfbd_games_2026_20261016T093000Z.parquet", index=False)

        # Point RESULTS_ARCHIVE_DIR at tmp
        old_env = os.environ.get("RESULTS_ARCHIVE_DIR")
        os.environ["RESULTS_ARCHIVE_DIR"] = str(tmp_path / "data" / "results_archive")
        try:
            result = xw._load_ncaaf_officials(tmp_path)
        finally:
            if old_env is not None:
                os.environ["RESULTS_ARCHIVE_DIR"] = old_env
            else:
                os.environ.pop("RESULTS_ARCHIVE_DIR", None)

        # Should read the newest file with "NewTeam"
        assert "NewTeam" in result["home"].values, f"expected NewTeam, got {result['home'].values}"

    def test_fallback_to_research_with_warning(self, tmp_path, capsys):
        """If archive dir is empty, falls back to research file with a warning."""
        # No archive dir at all
        research = tmp_path / "research" / "ncaaf"
        research.mkdir(parents=True)
        cols = {"id": [1], "season": [2026], "week": [1], "seasonType": ["regular"],
                "startDate": ["2026-09-05T00:00:00Z"], "completed": [False],
                "homeTeam": ["FallbackTeam"], "awayTeam": ["OtherTeam"],
                "homePoints": [None], "awayPoints": [None], "neutralSite": [False]}
        pd.DataFrame(cols).to_parquet(research / "cfbd_games_2026.parquet", index=False)

        old_env = os.environ.get("RESULTS_ARCHIVE_DIR")
        os.environ["RESULTS_ARCHIVE_DIR"] = str(tmp_path / "data" / "results_archive")
        try:
            result = xw._load_ncaaf_officials(tmp_path)
        finally:
            if old_env is not None:
                os.environ["RESULTS_ARCHIVE_DIR"] = old_env
            else:
                os.environ.pop("RESULTS_ARCHIVE_DIR", None)

        assert "FallbackTeam" in result["home"].values
        captured = capsys.readouterr()
        assert "WARNING" in captured.out


class TestHaltOnLowRows:
    """pull_ncaaf_results HALTs on < 500 rows."""

    def test_halt_under_500(self, monkeypatch):
        import shared.pipeline.pull_ncaaf_results as pnr

        # Mock cfbd_get to return < 500 rows
        small_response = [{"id": i, "season": 2026, "week": 1, "seasonType": "regular",
                           "startDate": "2026-09-05T00:00:00Z", "completed": True,
                           "homeTeam": f"Team{i}", "awayTeam": f"Team{i+100}",
                           "homePoints": 28, "awayPoints": 14, "neutralSite": False}
                          for i in range(100)]

        monkeypatch.setattr(pnr, "cfbd_get", lambda *a, **kw: small_response)
        monkeypatch.setattr(pnr, "CFBD_KEY", "test_key")

        with pytest.raises(SystemExit) as exc:
            pnr.pull()
        assert exc.value.code != 0
