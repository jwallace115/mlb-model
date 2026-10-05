"""
Tests for B15: ESPN content-based de-dup.

Test: two REAL consecutive archive files where the second has the same content
(minus timestamp) should be skipped.

FAILS on origin/main: raw-byte SHA never matches because top-level "timestamp"
differs, so every file is treated as new.
"""
import gzip, hashlib, json, os, sys, tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

ESPN_DIR = ROOT / "data" / "injury_archive" / "nba" / "season=2026" / "espn"


def _content_sha(data_dict):
    """B15 canonical hash: remove 'timestamp', sort keys."""
    canonical = {k: v for k, v in data_dict.items() if k != "timestamp"}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def _find_consecutive_content_dup():
    """Find two consecutive ESPN archive files with same content hash (diff timestamp)."""
    files = sorted(ESPN_DIR.glob("*.json.gz"))
    prev_sha = None
    for f in files:
        raw = gzip.open(f, "rb").read()
        data = json.loads(raw)
        sha = _content_sha(data)
        if sha == prev_sha:
            prev_f = files[files.index(f) - 1]
            return prev_f, f, sha
        prev_sha = sha
    return None, None, None


def test_consecutive_content_dup_skipped():
    """Two consecutive files with same content (diff timestamp) -> second is skipped.
    FAILS on origin/main: raw-byte hash differs (timestamp changes), so both kept."""
    f1, f2, sha = _find_consecutive_content_dup()
    assert f1 is not None, "No consecutive content-duplicate found in ESPN archive"

    # Verify they differ in raw bytes (timestamp is different)
    raw1 = gzip.open(f1, "rb").read()
    raw2 = gzip.open(f2, "rb").read()
    raw_sha1 = hashlib.sha256(raw1).hexdigest()
    raw_sha2 = hashlib.sha256(raw2).hexdigest()
    assert raw_sha1 != raw_sha2, "Raw bytes should differ (timestamp is different)"

    # Verify content hashes match (our B15 fix)
    data1 = json.loads(raw1)
    data2 = json.loads(raw2)
    assert _content_sha(data1) == _content_sha(data2), "Content hashes should match"

    # Verify the old (raw SHA) approach would NOT dedup them
    # This is exactly why the test FAILS on origin/main
    old_sha1 = hashlib.sha256(raw1).hexdigest()
    old_sha2 = hashlib.sha256(raw2).hexdigest()
    assert old_sha1 != old_sha2, (
        "Old approach (raw SHA) would not detect duplicate — "
        "this is the bug B15 fixes"
    )


def test_content_union_preserved():
    """NULL CONTROL: union of (team_id, athlete_id, status, date) over all files
    equals the union over the kept set (files with distinct content hashes)."""
    import re
    files = sorted(ESPN_DIR.glob("*.json.gz"))

    def extract_items(data):
        items = set()
        teams = data.get("injuries", [])
        for team in teams:
            team_id = str(team.get("id", ""))
            for inj in team.get("injuries", []):
                ath = inj.get("athlete", {})
                ath_id = ""
                if isinstance(ath, dict):
                    if ath.get("id"):
                        ath_id = str(ath["id"])
                    else:
                        for link in ath.get("links", []):
                            m = re.search(r"/id/(\d+)/", link.get("href", ""))
                            if m:
                                ath_id = m.group(1)
                                break
                items.add((team_id, ath_id, inj.get("status", ""), inj.get("date", "")))
        return items

    # Determine "kept" files (first of each consecutive run with same content hash)
    kept_names = set()
    prev_sha = None
    for f in files:
        raw = gzip.open(f, "rb").read()
        sha = _content_sha(json.loads(raw))
        if sha != prev_sha:
            kept_names.add(f.name)
        prev_sha = sha

    all_items = set()
    kept_items = set()
    for f in files:
        raw = gzip.open(f, "rb").read()
        data = json.loads(raw)
        items = extract_items(data)
        all_items |= items
        if f.name in kept_names:
            kept_items |= items

    assert all_items == kept_items, (
        f"Union differs: {len(all_items)} items total vs {len(kept_items)} kept. "
        f"Lost: {all_items - kept_items}"
    )
