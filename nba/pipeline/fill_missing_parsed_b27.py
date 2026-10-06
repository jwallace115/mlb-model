#!/usr/bin/env python3
"""
B27: Parse all referenced reports missing from history_parsed and manifest.
"""
import hashlib, os, re, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")

ET = ZoneInfo("America/New_York")
MAIN = Path("/Users/jw115/mlb-model")


def _season_tag(fname):
    """Determine season=YYYY from filename date."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", fname)
    if not m:
        return None
    yr, mo = int(m.group(1)), int(m.group(2))
    s = yr if mo >= 7 else yr - 1
    return str(s)


def main():
    from nba.pipeline.injury_report_parser import parse_report

    roles = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/roles.parquet")
    asof = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/game_asof.parquet")
    manifest = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet")

    # All referenced filenames
    roles_files = set(roles[roles.filename != ""].filename.unique())
    asof_files = set(asof[asof.asof_filename != ""].asof_filename.unique())
    all_referenced = roles_files | asof_files
    manifest_files = set(manifest.filename.unique())
    missing = sorted(all_referenced - manifest_files)

    print(f"Missing from manifest: {len(missing)}")

    # Existing parsed parquets
    hp_base = ROOT / "data/injury_archive/nba/history_parsed"

    new_manifest_rows = []
    ok_count = 0
    fail_count = 0

    for fname in missing:
        stag = _season_tag(fname)
        if stag is None:
            print(f"  SKIP: cannot determine season for {fname}")
            continue

        # Find PDF
        pdf_path = MAIN / "data/injury_archive/nba/history" / f"season={stag}" / fname
        if not pdf_path.exists():
            print(f"  NOT FOUND: {pdf_path}")
            fail_count += 1
            continue

        # Parse
        rows, pub, slot_et, status, detail = parse_report(pdf_path)
        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        nys_count = len([r for r in rows if r.get("status") == "NOT_YET_SUBMITTED"])

        # Write parsed parquet
        out_dir = hp_base / f"season={stag}"
        out_dir.mkdir(parents=True, exist_ok=True)
        parquet_name = fname.replace(".pdf", ".parquet")
        parquet_path = out_dir / parquet_name

        if rows:
            df = pd.DataFrame(rows)
            df["published_utc"] = pub.isoformat() if pub else ""
            df["slot_et"] = slot_et or ""
            df["pdf_sha256"] = sha
            df.to_parquet(parquet_path, index=False)
        else:
            df = pd.DataFrame(columns=["game_date", "game_time", "matchup", "team", "player",
                                        "status", "reason", "published_utc", "slot_et", "pdf_sha256"])
            df.to_parquet(parquet_path, index=False)

        new_manifest_rows.append({
            "filename": fname,
            "sha256": sha,
            "published_utc": pub.isoformat() if pub else "",
            "status": status,
            "n_rows": len(rows),
            "n_nys": nys_count,
            "season": stag,
        })

        if status == "ok":
            ok_count += 1
        else:
            fail_count += 1
            print(f"  {status}: {fname}: {detail[:100]}")

    # Append to manifest
    if new_manifest_rows:
        old_mf = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet")
        new_mf = pd.concat([old_mf, pd.DataFrame(new_manifest_rows)], ignore_index=True)
        new_mf.to_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet", index=False)
        print(f"\nManifest: {len(old_mf)} -> {len(new_mf)} rows (+{len(new_manifest_rows)})")
    else:
        print("\nNo new manifest rows")

    print(f"\nParsed: {ok_count} ok, {fail_count} not ok")
    print(f"Expected manifest: 642 + {len(missing)} = {642 + len(missing)}")

    # NULL: verify old 642 manifest rows unchanged
    old_mf = manifest  # the original 642
    new_mf = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet")
    old_subset = new_mf[new_mf.filename.isin(old_mf.filename.values)]
    merged = old_mf.merge(old_subset, on="filename", suffixes=("_old", "_new"))
    mismatches = merged[
        (merged.sha256_old != merged.sha256_new) |
        (merged.published_utc_old != merged.published_utc_new) |
        (merged.status_old != merged.status_new) |
        (merged.n_rows_old != merged.n_rows_new) |
        (merged.n_nys_old != merged.n_nys_new)
    ]
    print(f"\nNULL: old 642 rows - {len(mismatches)} mismatches")


if __name__ == "__main__":
    main()
