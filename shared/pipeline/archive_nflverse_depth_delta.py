#!/usr/bin/env python3
"""
WO10c: archive the nflverse depth-chart feed as a DELTA, not a daily full copy.

nfl/data/pbp/depth_charts.parquet is its own history: every 2025+ row carries `dt`, the
snapshot timestamp, and nflverse appends a new snapshot every day (253 distinct snapshot
dates in 2026 as of 09-19). So the file changes daily, a sha256 hash-skip never skips, and a
full copy per day is ~7.2 MB of rows that are already in the previous copy.

This writes only rows whose `dt` is newer than the newest `dt` already archived
(nflverse_depth_delta_<UTC>.parquet), and logs every pull — sha256 of the full file, rows
written, max dt — to _pulls.jsonl, so a pull that adds nothing is still evidence it ran.

Baseline: the newest full copy nflverse_depth_charts_*.parquet already in the archive.
With no baseline and no state, the first run writes every dated row.

Limit, stated: a retroactive edit by nflverse to an already-archived snapshot is NOT
captured as rows. The full-file sha256 in _pulls.jsonl changes whenever anything changes,
which makes such an edit detectable, not reconstructable.
"""
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "nfl" / "data" / "pbp" / "depth_charts.parquet"
ARCHIVE = ROOT / "data" / "depth_archive" / "nfl" / "season=2026"


def _utc(series):
    return pd.to_datetime(series, utc=True, errors="coerce")


def baseline_max_dt(archive_dir):
    """Newest dt already archived: state file first, else newest full copy, else None."""
    state = archive_dir / "_depth_state.json"
    if state.exists():
        v = json.loads(state.read_text()).get("max_dt")
        return pd.Timestamp(v) if v else None
    fulls = sorted(archive_dir.glob("nflverse_depth_charts_*.parquet"))
    if fulls:
        m = _utc(pd.read_parquet(fulls[-1], columns=["dt"])["dt"]).max()
        return None if pd.isna(m) else m
    return None


def archive_delta(src, archive_dir, now=None):
    """Returns dict describing what happened. Raises on a missing/unreadable source."""
    now = now or datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%MZ")
    if not src.exists():
        raise FileNotFoundError(f"HALT: {src} missing")
    archive_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    df = pd.read_parquet(src)
    if "dt" not in df.columns:
        raise ValueError("HALT: depth_charts.parquet has no `dt` column — schema changed")
    dt = _utc(df["dt"])
    if dt.notna().sum() == 0:
        raise ValueError("HALT: no parseable `dt` values")
    base = baseline_max_dt(archive_dir)
    new = df[dt > base] if base is not None else df[dt.notna()]
    new_max = dt.max()
    rec = {"utc": ts, "feed": "nflverse_depth", "file": "depth_charts.parquet", "sha256": sha,
           "max_dt": new_max.isoformat(), "rows": int(len(new))}
    if len(new):
        out = archive_dir / f"nflverse_depth_delta_{ts}.parquet"
        if out.exists():
            raise FileExistsError(f"HALT: {out} exists — append-only, refusing to overwrite")
        new.to_parquet(out, index=False)
        rec["status"] = "delta"
        (archive_dir / "_depth_state.json").write_text(json.dumps({"max_dt": new_max.isoformat()}))
    else:
        rec["status"] = "unchanged"
    with open(archive_dir / "_pulls.jsonl", "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--archive-dir", type=Path, default=ARCHIVE)
    a = ap.parse_args()
    try:
        r = archive_delta(a.src, a.archive_dir)
    except Exception as e:  # halt loudly; never write a partial record
        print(str(e)); sys.exit(1)
    print(f"depth delta: {r['status']} rows={r['rows']} max_dt={r['max_dt']} sha={r['sha256'][:12]}")
