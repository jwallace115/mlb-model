#!/usr/bin/env bash
# WO10b Item 2c / WO10c: run the nflverse puller, then archive (delta for depth charts,
# hash-skipped full copies for injuries and rosters).
# The sim reads the overwritten parquets; this preserves point-in-time copies.
# Hash-skip: only copy when sha256 differs from the last archived copy.
set -euo pipefail

ROOT=/root/mlb-model
VENV=$ROOT/venv/bin/python3
PBP_DIR=$ROOT/nfl/data/pbp
ARCHIVE_DIR=$ROOT/data/depth_archive/nfl/season=2026
PULLS_LOG=$ARCHIVE_DIR/_pulls.jsonl
TS=$(date -u +%Y%m%dT%H%MZ)

# Run the puller (overwrites its parquets in place)
cd "$ROOT"
source venv/bin/activate
python3 nfl/sim/pull_nflverse_inputs.py

# Archive timestamped copies with hash-skip
mkdir -p "$ARCHIVE_DIR"
# WO10c: depth_charts.parquet is its own history (every row carries `dt`, a new snapshot is
# appended daily), so it changes every day and a full copy never hash-skips: ~7.2 MB/day.
# Archive only the rows newer than what is already archived; every pull is logged.
"$VENV" shared/pipeline/archive_nflverse_depth_delta.py

for f in injuries.parquet rosters_weekly.parquet; do
    src="$PBP_DIR/$f"
    if [ -f "$src" ]; then
        name="${f%.parquet}"
        new_hash=$(sha256sum "$src" | cut -d' ' -f1)
        dest="$ARCHIVE_DIR/nflverse_${name}_${TS}.parquet"

        # Find last archived copy's hash
        last_hash=""
        last_file=$(ls -t "$ARCHIVE_DIR"/nflverse_${name}_*.parquet 2>/dev/null | head -1)
        if [ -n "$last_file" ]; then
            last_hash=$(sha256sum "$last_file" | cut -d' ' -f1)
        fi

        if [ "$new_hash" = "$last_hash" ]; then
            echo "{\"utc\":\"$TS\",\"file\":\"$f\",\"sha256\":\"$new_hash\",\"status\":\"unchanged\"}" >> "$PULLS_LOG"
            echo "skipped: nflverse_${name} unchanged (hash=${new_hash:0:12})"
        else
            cp "$src" "$dest"
            echo "{\"utc\":\"$TS\",\"file\":\"$f\",\"sha256\":\"$new_hash\",\"status\":\"written\"}" >> "$PULLS_LOG"
            echo "archived: nflverse_${name}_${TS}.parquet ($(stat -c%s "$src" 2>/dev/null || stat -f%z "$src") bytes)"
        fi
    fi
done
