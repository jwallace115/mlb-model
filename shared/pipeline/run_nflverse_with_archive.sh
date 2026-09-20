#!/usr/bin/env bash
# WO10 Item 2d: Run nflverse puller then archive a timestamped copy.
# The sim reads the overwritten parquets; this preserves point-in-time copies.
set -euo pipefail

ROOT=/root/mlb-model
VENV=$ROOT/venv/bin/python3
PBP_DIR=$ROOT/nfl/data/pbp
ARCHIVE_DIR=$ROOT/data/depth_archive/nfl/season=2026
TS=$(date -u +%Y%m%dT%H%MZ)

# Run the puller (overwrites its parquets in place)
cd "$ROOT"
source venv/bin/activate
python3 nfl/sim/pull_nflverse_inputs.py

# Archive timestamped copies
mkdir -p "$ARCHIVE_DIR"
for f in depth_charts.parquet injuries.parquet rosters_weekly.parquet; do
    src="$PBP_DIR/$f"
    if [ -f "$src" ]; then
        name="${f%.parquet}"
        cp "$src" "$ARCHIVE_DIR/nflverse_${name}_${TS}.parquet"
        echo "archived: nflverse_${name}_${TS}.parquet ($(stat -c%s "$src" 2>/dev/null || stat -f%z "$src") bytes)"
    fi
done
