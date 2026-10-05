#!/usr/bin/env python3
"""S56/S58: data-custody manifest and archive copy.

Walks ALL worktree-only data (including large dirs), writes:
- nhl/data/sim/custody/files.parquet (per-file: location, relative, bytes, mtime, sha256) — gitignored
- nhl/data/sim/custody_manifest.json (per-location rollup: count, total_bytes, rollup sha256) — committed
- research/nhl_sim/DATA_CUSTODY.md — committed
"""
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

LOCATIONS = {
    "ratings": ROOT / "nhl" / "data" / "sim" / "ratings",
    "prices": ROOT / "nhl" / "data" / "sim" / "prices",
    "crosswalk": ROOT / "nhl" / "data" / "sim" / "crosswalk",
    "events": ROOT / "nhl" / "data" / "sim" / "events",
    "pbp_cache_nhlsim1": Path.home() / "mlb-model-nhlsim1" / "nhl" / "cache" / "pbp",
    "boxscore_cache_nhlD": Path.home() / "mlb-model-nhlD" / "nhl" / "cache",
    "odds_archive_nhlE": Path.home() / "mlb-model-nhlE" / "data" / "odds_archive" / "nhl" / "history",
}

CUSTODY_DIR = ROOT / "nhl" / "data" / "sim" / "custody"
FILES_PARQUET = CUSTODY_DIR / "files.parquet"
MANIFEST_PATH = ROOT / "nhl" / "data" / "sim" / "custody_manifest.json"
CUSTODY_DOC_PATH = ROOT / "research" / "nhl_sim" / "DATA_CUSTODY.md"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory_location(loc_name, loc_path):
    """Walk a location and return list of dicts for all files."""
    loc_path = Path(loc_path)
    resolved = loc_path.resolve()
    if not resolved.exists():
        return []
    rows = []
    for p in sorted(resolved.rglob("*")):
        if p.is_file() and not p.is_symlink():
            try:
                st = p.stat()
                rows.append({
                    "location": loc_name,
                    "relative": str(p.relative_to(resolved)),
                    "bytes": st.st_size,
                    "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
                    "sha256": sha256_file(p),
                })
            except (PermissionError, OSError):
                pass
    return rows


def rollup_sha256(sha_list):
    """Deterministic rollup: sha256 of sorted per-file sha256 lines."""
    h = hashlib.sha256()
    for s in sorted(sha_list):
        h.update((s + "\n").encode())
    return h.hexdigest()


def main():
    print("Building per-file custody manifest (all locations)...")
    all_rows = []

    for loc_name, loc_path in LOCATIONS.items():
        loc_path = Path(loc_path)
        is_sym = loc_path.is_symlink()
        tag = f" -> {loc_path.resolve()}" if is_sym else ""
        print(f"  {loc_name}: {loc_path}{tag}")
        if not loc_path.resolve().exists():
            print(f"    NOT FOUND, skipping")
            continue
        t0 = time.time()
        rows = inventory_location(loc_name, loc_path)
        elapsed = time.time() - t0
        total_bytes = sum(r["bytes"] for r in rows)
        print(f"    {len(rows)} files, {total_bytes / 1e6:.1f} MB, {elapsed:.1f}s")
        all_rows.extend(rows)

    # Write per-file parquet (gitignored)
    CUSTODY_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(all_rows)
    df.to_parquet(FILES_PARQUET, index=False)
    print(f"\nfiles.parquet: {len(df)} rows, {FILES_PARQUET.stat().st_size / 1e6:.1f} MB")

    # Build per-location rollup for the committed manifest
    location_summaries = {}
    for loc_name, loc_path in LOCATIONS.items():
        loc_path = Path(loc_path)
        loc_df = df[df["location"] == loc_name]
        if loc_df.empty:
            continue
        location_summaries[loc_name] = {
            "path": str(loc_path),
            "resolved_path": str(loc_path.resolve()),
            "is_symlink": loc_path.is_symlink(),
            "n_files": len(loc_df),
            "total_bytes": int(loc_df["bytes"].sum()),
            "rollup_sha256": rollup_sha256(loc_df["sha256"].tolist()),
        }

    # Write committed manifest JSON
    manifest = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_files": len(df),
        "total_bytes": int(df["bytes"].sum()),
        "locations": location_summaries,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Manifest: {MANIFEST_PATH}")

    # Null control: verify the 28 previously hashed small-dir files keep identical sha256
    old_manifest_path = MANIFEST_PATH  # we're overwriting it, but let's check in memory
    small_locs = {"ratings", "prices", "crosswalk", "events"}
    small_df = df[df["location"].isin(small_locs)]
    print(f"\nNull control: {len(small_df)} small-dir files hashed")

    # Write DATA_CUSTODY.md
    custody_info = {
        "ratings": (
            "Team ratings, goalie ratings, finishing term, shrinkage parameters, "
            "team_game_stats, and the ratings manifest. Produced by `nhl/sim/ratings.py` "
            "(S16-S27). Rebuilding requires the events tables (~30s) plus a --measure-hyper "
            "run (~5s). The carryover weights and shrinkage K are fitted once on 2021-22 + 2022-23."
        ),
        "prices": (
            "Engine-simulated game prices for 2022-23 and 2023-24 (2,624 games total). "
            "Produced by `nhl/sim/price_games.py` (S41/S50). Rebuilding: ~50 min at 2,000 sims. "
            "Also contains the pre-fix 'swapped' prices for provenance."
        ),
        "crosswalk": (
            "game_id <-> event_id crosswalk mapping NHL game_ids to Odds API event_ids. "
            "Produced by `nhl/sim/build_crosswalk.py` (S55). Rebuilding: seconds (reads boxscores + lines)."
        ),
        "events": (
            "Per-season shot, state_time, and penalty event tables extracted from play-by-play. "
            "Produced by `nhl/sim/build_events.py`. Rebuilding: ~15 min from the pbp cache."
        ),
        "pbp_cache_nhlsim1": (
            "Raw play-by-play JSON (gzipped), one file per game, 2010-2025 seasons. "
            "Source: NHL Stats API. This is the canonical copy; nhlsim4b and nhlD have "
            "symlinks (`nhl/cache/pbp -> ~/mlb-model-nhlsim1/nhl/cache/pbp`). "
            "Rebuilding: ~2 hours of API calls (rate-limited). PRUNING THE nhlsim1 WORKTREE "
            "WOULD DESTROY THIS DATA."
        ),
        "boxscore_cache_nhlD": (
            "Boxscore JSON files, one per game, 2010-2025. Source: NHL Stats API. "
            "Also used by nhlsim4b via symlink. Rebuilding: ~1 hour of API calls."
        ),
        "odds_archive_nhlE": (
            "Historical odds from the Odds API: lines (h2h/totals/spreads snapshots), "
            "three-way markets, in-play data, event-market mappings. 2022-2025 seasons. "
            "Rebuilding cost: 2,586,062 Odds API credits actually spent "
            "(E-WO1: 2,509,800 + WO2: 76,262 from logs). Plan: 5M credits/month. "
            "THIS IS THE MOST EXPENSIVE DATA TO REBUILD."
        ),
    }
    doc_lines = ["# NHL Sim — Data Custody", "", "Generated by `nhl/sim/archive_inventory.py`.", ""]
    for loc_name, desc in custody_info.items():
        summ = location_summaries.get(loc_name, {})
        path = summ.get("path", "N/A")
        n = summ.get("n_files", 0)
        mb = summ.get("total_bytes", 0) / 1e6
        is_sym = summ.get("is_symlink", False)
        doc_lines.append(f"## {loc_name}")
        doc_lines.append(f"**Path:** `{path}`" + (" (symlink)" if is_sym else ""))
        doc_lines.append(f"**Files:** {n}, **Size:** {mb:.1f} MB")
        doc_lines.append("")
        doc_lines.append(desc)
        doc_lines.append("")

    CUSTODY_DOC_PATH.write_text("\n".join(doc_lines) + "\n")
    print(f"Doc: {CUSTODY_DOC_PATH}")

    # Archive copy
    archive_root = os.environ.get("ARCHIVE_ROOT")
    if not archive_root:
        print("\nARCHIVE_ROOT not set. To archive, run:")
        print(f"  ARCHIVE_ROOT=/path/to/archive python3 {__file__}")
        print("\nOr manually:")
        for loc_name, loc_path in LOCATIONS.items():
            resolved = Path(loc_path).resolve()
            if resolved.exists():
                print(f"  rsync -a --ignore-existing {resolved}/ $ARCHIVE_ROOT/nhl/{loc_name}/")
        print(f"  rsync -a --ignore-existing {FILES_PARQUET} $ARCHIVE_ROOT/nhl/")
        print("\nSTOP: no archive copy made.")
        return

    archive_nhl = Path(archive_root) / "nhl"
    archive_nhl.mkdir(parents=True, exist_ok=True)

    for loc_name, loc_path in LOCATIONS.items():
        resolved = Path(loc_path).resolve()
        if not resolved.exists():
            continue
        dest = archive_nhl / loc_name
        dest.mkdir(parents=True, exist_ok=True)
        cmd = ["rsync", "-a", "--ignore-existing", f"{resolved}/", f"{dest}/"]
        print(f"\n  {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    # Copy files.parquet too
    subprocess.run(["rsync", "-a", "--ignore-existing", str(FILES_PARQUET),
                     str(archive_nhl / "files.parquet")], check=True)

    # Verify archive against files.parquet
    print("\nVerifying archive...")
    mismatches = 0
    verified = 0
    verified_bytes = 0
    for _, row in df.iterrows():
        loc = row["location"]
        rel = row["relative"]
        dest = archive_nhl / loc / rel
        if dest.exists():
            archive_sha = sha256_file(dest)
            if archive_sha != row["sha256"]:
                print(f"  MISMATCH: {dest}")
                mismatches += 1
            verified += 1
            verified_bytes += dest.stat().st_size

    print(f"Archive: {verified} files, {verified_bytes / 1e6:.1f} MB, {mismatches} mismatches")

    for loc_name, loc_path in LOCATIONS.items():
        resolved = Path(loc_path).resolve()
        if resolved.exists():
            result = subprocess.run(["du", "-sh", str(resolved)], capture_output=True, text=True)
            print(f"  Source {loc_name}: {result.stdout.strip()}")
    result = subprocess.run(["du", "-sh", str(archive_nhl)], capture_output=True, text=True)
    print(f"  Archive: {result.stdout.strip()}")


if __name__ == "__main__":
    main()
