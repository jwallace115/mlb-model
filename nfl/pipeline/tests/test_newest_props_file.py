"""P79 (RED first): the props month file is chosen by newest pull, not by name."""
import pandas as pd
from pathlib import Path
import importlib


def _write(p, ts):
    pd.DataFrame({"event_id": ["e1"], "commence_time": ["2026-10-30T00:15:00Z"], "pull_timestamp": [ts],
                  "bookmaker": ["hardrockbet_fl"], "market_key": ["player_rush_yds"], "player_name": ["A"], "line": [50.5]}).to_parquet(p)


def test_picks_newest_pull_not_last_name(tmp_path, monkeypatch):
    import nfl.pipeline.log_ai_opinions as lao
    d = tmp_path / "season=2026" / "month=10"; d.mkdir(parents=True)
    _write(d / "data_2026_10.parquet", "2026-10-29T18:47:31+00:00")       # VM's own pull — newest
    _write(d / "data_2026_10_mac.parquet", "2026-10-25T15:00:00+00:00")   # sorts LAST by name — stale
    monkeypatch.setattr(lao, "PROPS_DIR", tmp_path)
    assert lao._newest_props_file(2026).name == "data_2026_10.parquet"
    rp, _ = lao.resolve_inputs(2026, pd.Timestamp("2026-10-29T20:00Z"), lines_file="x")
    assert rp.endswith("data_2026_10.parquet")
