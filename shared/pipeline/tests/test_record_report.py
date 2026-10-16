"""Tests for record_report.py (P55).

(a) Fixture ledger of two freezes → rank buckets and conf bins as pre-registered
(b) Embargo: an ai_nfl row never appears in rendered Record HTML
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import record_report as rr


def _fake_rows():
    """Two freezes: freeze A has 7 rows, freeze B has 3 rows."""
    rows = []
    for i in range(7):
        rows.append({
            "pick_id": f"a{i}", "owner": "ai_nfl", "source_file": "freeze_a.parquet",
            "logged_utc": "2026-10-12T15:00:00Z", "sport": "NFL",
            "market": "spread", "side": "home", "point": -3.5,
            "price_american": -110, "result": "W" if i < 3 else "L",
            "conf": 30 - i * 4,  # 30, 26, 22, 18, 14, 10, 6
        })
    for i in range(3):
        rows.append({
            "pick_id": f"b{i}", "owner": "ai_ncaaf", "source_file": "freeze_b.parquet",
            "logged_utc": "2026-10-12T16:00:00Z", "sport": "NCAAF",
            "market": "total", "side": "over", "point": 45.5,
            "price_american": -110, "result": "W",
            "conf": 20 - i * 8,  # 20, 12, 4
        })
    return rows


class TestRankBuckets:
    """Fixture ledger → rank buckets."""

    def test_rank_assignment(self):
        rows = _fake_rows()
        manifests = {}
        rr.annotate(rows, manifests)
        rr.compute_ranks(rows)

        # Freeze A: 7 rows sorted by conf desc (30,26,22,18,14,10,6)
        freeze_a = [r for r in rows if r["source_file"] == "freeze_a.parquet"]
        freeze_a.sort(key=lambda r: r["_rank"])
        assert freeze_a[0]["_rank"] == 1
        assert freeze_a[0]["_rank_bucket"] == "top5"
        assert freeze_a[4]["_rank"] == 5
        assert freeze_a[4]["_rank_bucket"] == "top5"
        assert freeze_a[5]["_rank"] == 6
        assert freeze_a[5]["_rank_bucket"] == "top10"
        assert freeze_a[6]["_rank"] == 7
        assert freeze_a[6]["_rank_bucket"] == "top10"

        # Freeze B: 3 rows
        freeze_b = [r for r in rows if r["source_file"] == "freeze_b.parquet"]
        freeze_b.sort(key=lambda r: r["_rank"])
        assert freeze_b[0]["_rank_bucket"] == "top5"
        assert freeze_b[2]["_rank_bucket"] == "top5"  # only 3 rows, all top5


class TestConfBins:
    """Fixture ledger → conf bins."""

    def test_conf_bins(self):
        rows = _fake_rows()
        manifests = {}
        rr.annotate(rows, manifests)

        bins = [r["_bin"] for r in rows]
        # Freeze A confs: 30, 26, 22, 18, 14, 10, 6
        # Bins: 30+, 20-29, 20-29, 15-19, 10-14, 10-14, 5-9
        assert bins[0] == "30+"
        assert bins[1] == "20-29"
        assert bins[2] == "20-29"
        assert bins[3] == "15-19"
        assert bins[4] == "10-14"
        assert bins[5] == "10-14"
        assert bins[6] == "5-9"
        # Freeze B confs: 20, 12, 4
        assert bins[7] == "20-29"
        assert bins[8] == "10-14"
        assert bins[9] == "1-4"


class TestBuildTable:
    """build_table produces correct W/L/units."""

    def test_units(self):
        rows = _fake_rows()
        manifests = {}
        rr.annotate(rows, manifests)
        rr.compute_ranks(rows)

        tbl = rr.build_table(rows, lambda r: r.get("owner"))
        ai_nfl = [t for t in tbl if "ai_nfl" in t["key"]][0]
        assert ai_nfl["W"] == 3
        assert ai_nfl["L"] == 4


class TestEmbargoInSite:
    """An ai_nfl row never appears in the rendered Record HTML.

    build_site imports are complex (it imports picks_data, etc.), so this test
    uses subprocess to avoid sys.path conflicts with pytest.
    """

    def test_embargo_hides_ai_nfl(self):
        import subprocess
        root = Path(__file__).resolve().parents[3]  # repo root
        code = '''
import sys, json
sys.path.insert(0, "{site}")
sys.path.insert(0, "{shared}")
import build_site as bs

rows = json.loads('{rows_json}')
for r in rows:
    r["commence_time"] = "2026-10-12T17:00:00Z"
    r["window"] = "open"

embargo_owners = {{"ai_nfl", "sim_nfl"}}
html = bs._record_section(rows, embargo_owners, "NFL", "")
assert "scoring not published" in html, f"embargo not working: {{html[:200]}}"
print("PASS")
'''.format(
            site=str(root / "site"),
            shared=str(root / "shared" / "pipeline"),
            rows_json=json.dumps(_fake_rows()).replace("'", "\\'"),
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"subprocess failed: {result.stderr}"
        assert "PASS" in result.stdout
