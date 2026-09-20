"""WO10c: nflverse depth-chart delta archive. No network. Imports the real module."""
import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from shared.pipeline.archive_nflverse_depth_delta import archive_delta


def _src(path, dts):
    pd.DataFrame({"dt": dts, "gsis_id": [f"p{i}" for i in range(len(dts))],
                  "pos_rank": range(len(dts))}).to_parquet(path, index=False)


def test_baseline_from_full_copy_then_delta_then_unchanged(tmp_path):
    arch = tmp_path / "arch"; arch.mkdir()
    src = tmp_path / "depth_charts.parquet"
    _src(arch / "nflverse_depth_charts_20260920T0221Z.parquet",
         [None, "2026-09-18T12:00:00Z", "2026-09-19T12:00:00Z"])
    _src(src, [None, "2026-09-18T12:00:00Z", "2026-09-19T12:00:00Z",
               "2026-09-20T12:00:00Z", "2026-09-20T12:00:00Z"])
    r = archive_delta(src, arch, now=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc))
    assert r["status"] == "delta" and r["rows"] == 2
    d = pd.read_parquet(arch / "nflverse_depth_delta_20260920T0900Z.parquet")
    assert len(d) == 2 and set(d["gsis_id"]) == {"p3", "p4"}
    r2 = archive_delta(src, arch, now=datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc))
    assert r2["status"] == "unchanged" and r2["rows"] == 0
    assert not (arch / "nflverse_depth_delta_20260920T1500Z.parquet").exists()
    lines = [json.loads(x) for x in (arch / "_pulls.jsonl").read_text().splitlines()]
    assert [x["status"] for x in lines] == ["delta", "unchanged"]      # a skipped write is still logged


def test_no_baseline_writes_every_dated_row(tmp_path):
    src = tmp_path / "depth_charts.parquet"
    _src(src, [None, "2026-09-19T12:00:00Z", "2026-09-20T12:00:00Z"])
    r = archive_delta(src, tmp_path / "arch", now=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc))
    assert r["rows"] == 2


def test_halts_and_writes_nothing(tmp_path):
    arch = tmp_path / "arch"
    with pytest.raises(FileNotFoundError):
        archive_delta(tmp_path / "missing.parquet", arch)
    bad = tmp_path / "bad.parquet"
    pd.DataFrame({"gsis_id": ["a"]}).to_parquet(bad, index=False)
    with pytest.raises(ValueError):
        archive_delta(bad, arch)
    assert not (arch / "_pulls.jsonl").exists()


def test_refuses_to_overwrite(tmp_path):
    arch = tmp_path / "arch"; arch.mkdir()
    src = tmp_path / "depth_charts.parquet"
    _src(src, ["2026-09-20T12:00:00Z"])
    (arch / "nflverse_depth_delta_20260920T0900Z.parquet").write_bytes(b"x")
    with pytest.raises(FileExistsError):
        archive_delta(src, arch, now=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc))
