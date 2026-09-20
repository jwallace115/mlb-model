"""
Test: Kalshi non-200 and empty markets -> non-zero exit, no file written.

No network.
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


class TestKalshiNon200:
    def test_non200_halts(self, monkeypatch):
        resp = MagicMock()
        resp.status_code = 429
        resp.text = "rate limited"

        monkeypatch.setattr("shared.pipeline.pull_kalshi_football.requests.get",
                            MagicMock(return_value=resp))

        from shared.pipeline.pull_kalshi_football import pull_series
        with pytest.raises(SystemExit) as exc_info:
            pull_series("KXNFLGAME")
        assert exc_info.value.code == 1


class TestKalshiEmptyMarkets:
    def test_empty_markets_no_file(self, tmp_path, monkeypatch):
        """All series return 0 markets -> HALT, no file."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"markets": [], "cursor": ""}

        monkeypatch.setattr("shared.pipeline.pull_kalshi_football.requests.get",
                            MagicMock(return_value=resp))
        monkeypatch.setattr("shared.pipeline.pull_kalshi_football.ROOT", tmp_path)

        import shared.pipeline.pull_kalshi_football as mod
        import sys

        # Simulate main() logic: pull all series, check if empty
        with pytest.raises(SystemExit) as exc_info:
            mod.main.__wrapped__() if hasattr(mod.main, '__wrapped__') else _run_main(mod, tmp_path, monkeypatch)
        assert exc_info.value.code == 1

        out_dir = tmp_path / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026"
        files = list(out_dir.glob("*.parquet")) if out_dir.exists() else []
        assert len(files) == 0


def _run_main(mod, tmp_path, monkeypatch):
    """Run the main function with args."""
    import sys
    monkeypatch.setattr(sys, "argv",
                        ["pull_kalshi_football.py", "--sport", "nfl"])
    mod.main()
