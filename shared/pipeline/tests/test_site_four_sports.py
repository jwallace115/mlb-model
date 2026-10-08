"""Gate tests for the four-sport site — RED first, then GREEN.

OPS2c Item 1.
"""
import json, os, sys, pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


REMOVED_IDS = {"p09", "yrfi2", "night_dog", "bp_adv_dog", "p1b", "nrfi_sel", "adj", "wnba_a"}


# ---- (a) signals_registry has none of the removed ids in signals, all in retired ----
def test_signals_registry_four_sports():
    reg = json.loads((Path(__file__).resolve().parent.parent.parent.parent / "site" / "signals_registry.json").read_text())
    active_ids = {s["id"] for s in reg["signals"]}
    for rid in REMOVED_IDS:
        assert rid not in active_ids, f"{rid} still in active signals"
    retired_ids = {r["id"] for r in reg.get("retired", [])}
    for rid in REMOVED_IDS:
        assert rid in retired_ids, f"{rid} missing from retired list"


# ---- (b) feeds_registry: retired feeds have retired=true, data captures have retired=false ----
def test_feeds_registry_retired():
    reg = json.loads((Path(__file__).resolve().parent.parent / "feeds_registry.json").read_text())
    feeds_by_id = {f["id"]: f for f in reg["feeds"]}
    # MLB signal feeds should be retired
    for fid in ("mlb_lineups", "yrfi_odds", "yrfi_shadow", "p09_shadow", "nrfi_selector",
                "mlb_prelim", "mlb_confirm", "mlb_results", "statcast_mac", "mlb_hits_mac"):
        assert feeds_by_id[fid].get("retired") is True, f"{fid} should be retired"
    # Soccer, golf also retired
    for fid in ("soccer", "golf_daily", "golf_grade"):
        assert feeds_by_id[fid].get("retired") is True, f"{fid} should be retired"
    # MLB data captures should NOT be retired
    for fid in ("tape_mlb", "mlb_event_markets"):
        assert feeds_by_id[fid].get("retired") is not True, f"{fid} should NOT be retired"
    # NFL/NCAAF/NHL/NBA should NOT be retired
    for fid in ("tape_nfl", "tape_ncaaf", "tape_nhl", "tape_nba", "nfl_props", "nhl_daily"):
        assert feeds_by_id[fid].get("retired") is not True, f"{fid} should NOT be retired"


# ---- (c) pipeline_health: retired feed not judged, not unregistered ----
def test_retired_feed_not_judged(tmp_path):
    import pipeline_health as ph

    # Create a minimal registry with one retired feed
    reg = {"feeds": [
        {"id": "test_retired", "label": "Test retired", "sport": "MLB",
         "cron_match": "test_retired_job.py", "retired": True},
        {"id": "test_active", "label": "Test active", "sport": "NFL",
         "cron_match": "test_active_job.py",
         "outputs": ["data/test_active_*"], "ts": "mtime"},
    ]}
    reg_path = tmp_path / "feeds.json"
    reg_path.write_text(json.dumps(reg))

    # Create a crontab file with both jobs
    cron_path = tmp_path / "crontab.txt"
    cron_path.write_text(
        "0 10 * * * cd /root && python3 test_retired_job.py >> /root/logs/retired.log 2>&1\n"
        "0 10 * * * cd /root && python3 test_active_job.py >> /root/logs/active.log 2>&1\n"
    )

    from datetime import datetime, timezone
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    result = ph.build(now, tmp_path, str(cron_path), str(reg_path), with_host=False)

    # The retired feed should NOT be in feeds (not judged)
    judged_ids = {f["id"] for f in result["feeds"]}
    assert "test_retired" not in judged_ids, "retired feed was judged"

    # The retired feed's cron line should NOT appear as "unregistered"
    unreg = [f for f in result["feeds"] if "unregistered" in f.get("label", "")]
    unreg_ids = [f["id"] for f in unreg]
    assert not any("retired" in u for u in unreg_ids), f"retired feed's cron shows as unregistered: {unreg_ids}"

    # The retired feed should be in the retired list
    retired_ids = {r["id"] for r in result.get("retired", [])}
    assert "test_retired" in retired_ids, "retired feed missing from retired list"


# ---- (d) SPORTS list has no MLB ----
def test_sports_no_mlb():
    src = (Path(__file__).resolve().parent.parent.parent.parent / "site" / "build_site.py").read_text()
    # Find the SPORTS = [...] line
    import re
    m = re.search(r"SPORTS\s*=\s*\[([^\]]+)\]", src)
    assert m, "SPORTS list not found"
    sports_text = m.group(1)
    assert "MLB" not in sports_text, "MLB still in SPORTS list"
    for sport in ("NFL", "NCAAF", "NHL", "NBA"):
        assert sport in sports_text, f"{sport} missing from SPORTS list"
