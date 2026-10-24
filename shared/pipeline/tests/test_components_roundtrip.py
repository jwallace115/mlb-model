"""10-24 runaway: the last read's components must round-trip through the manifest, and news triggers only on availability words."""
import json
from shared.pipeline import window_watch as ww


def test_last_components_come_from_manifest_components(tmp_path, monkeypatch):
    board = tmp_path / "ncaaf" / "data" / "board" / "week=2026_08" / "ai_opinions"
    board.mkdir(parents=True)
    import pandas as pd
    pd.DataFrame({"event_id": ["e1"]}).to_parquet(board / "ai_opinions_20261024T120000Z.parquet")
    manifest = [{"file": "ai_opinions_20261024T120000Z.parquet", "reader_model": "ai_reader_v1b/x",
                 "logged_utc": "2026-10-24T12:00:00+00:00",
                 "inputs": {"props_file": "p", "lines_file": "l", "inputs_digest": "{}",
                            "components": {"e1": {"news": ["QB ruled out"], "props_ts": "2026-10-24T11:00"}}}}]
    (board / "manifest.json").write_text(json.dumps(manifest))
    comps = ww._load_last_components("e1", "ncaaf", tmp_path)
    assert comps == {"news": ["QB ruled out"], "props_ts": "2026-10-24T11:00"}
    assert "props_file" not in comps  # the old bug returned the inputs dict itself


def test_news_trigger_only_on_availability_keywords():
    assert ww.NEWS_KEYWORDS.search("Starting QB ruled out for Saturday")
    assert not ww.NEWS_KEYWORDS.search("Week 9 power rankings: who is climbing")
