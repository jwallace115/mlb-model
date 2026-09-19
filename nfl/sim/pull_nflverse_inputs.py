#!/usr/bin/env python3
"""
NFL Sim — refresh the nflverse inputs the usage builder depends on.

depth_charts.parquet, injuries.parquet and rosters_weekly.parquet had NO
committed puller. They were last refreshed by hand on 2026-09-14 and were
4.5 days stale heading into Week 3 — every usage role predated Week 2 being
played. This script owns them.

Safety, in the style of pull_pbp.py:
  * depth_charts: the season-populated block (2020-2024, old nflverse schema)
    is FINAL and is preserved byte-for-byte. Only the new-schema block
    (season NaN, `dt` populated, 2025+) is re-pulled. Rebuilding history from
    the current API would silently change 2021-24 usage.
  * every file: refuse to install if any season's row count would shrink.
  * write to a temp path, validate, then move. No partial files.

Usage:  python3 nfl/sim/pull_nflverse_inputs.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
NEW_SCHEMA_SEASONS = [2025, 2026]


def _install(df, path):
    """Atomic write: temp file in the same dir, then replace."""
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as t:
        tmp = Path(t.name)
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def refresh_depth_charts():
    import nflreadpy
    path = PBP_DIR / "depth_charts.parquet"
    old = pd.read_parquet(path)
    cols = list(old.columns)
    hist = old[old["season"].notna()].copy()

    frames = [nflreadpy.load_depth_charts([s]).to_pandas() for s in NEW_SCHEMA_SEASONS]
    new = pd.concat(frames, ignore_index=True)
    for c in cols:
        if c not in new.columns:
            new[c] = np.nan
    new = new[cols]
    new["season"] = np.nan          # matches how the new-schema block is stored

    out = pd.concat([hist, new], ignore_index=True)[cols]

    # assertions — fail loudly rather than install something subtly wrong
    h_old = old[old["season"].notna()].reset_index(drop=True)
    h_new = out[out["season"].notna()].reset_index(drop=True)
    assert h_new.equals(h_old), "historical depth-chart block changed — refusing to install"
    n_old = old["season"].isna().sum()
    n_new = out["season"].isna().sum()
    assert n_new >= n_old, f"new-schema block shrank ({n_old} -> {n_new})"

    dt = pd.to_datetime(out["dt"], errors="coerce", utc=True)
    _install(out, path)
    print(f"depth_charts: {len(old):,} -> {len(out):,} rows, "
          f"{dt.nunique()} snapshot days, latest dt {dt.max()}")


def refresh_simple(name, loader):
    """injuries / rosters_weekly — season-keyed, re-pull every season present."""
    path = PBP_DIR / f"{name}.parquet"
    old = pd.read_parquet(path)
    seasons = sorted(int(s) for s in old["season"].dropna().unique())
    new = loader(seasons).to_pandas()
    for c in old.columns:
        if c not in new.columns:
            new[c] = np.nan
    new = new[list(old.columns)]

    per_old = old.groupby("season").size()
    per_new = new.groupby("season").size()
    shrunk = [int(s) for s in per_old.index if per_new.get(s, 0) < per_old[s]]
    assert not shrunk, f"{name}: seasons shrank {shrunk} — refusing to install"

    _install(new, path)
    print(f"{name}: {len(old):,} -> {len(new):,} rows, seasons {seasons[0]}-{seasons[-1]}")


def main():
    import nflreadpy
    refresh_depth_charts()
    refresh_simple("injuries", nflreadpy.load_injuries)
    refresh_simple("rosters_weekly", nflreadpy.load_rosters_weekly)
    print("\nNOTE: the usage table is NOT rebuilt by this script. Fresh inputs do not "
          "reach the board until usage is rebuilt, and rebuilding changes "
          "usage_file_sha256, which fires the D72 calibration gate by design.")


if __name__ == "__main__":
    sys.exit(main())
