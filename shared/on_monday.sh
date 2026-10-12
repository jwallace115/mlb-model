#!/bin/bash
# ON Monday runner — single sequential cron entry (OPS-ON-1b).
# Cron: 40 15 * * 1  (15:40 UTC every Monday)
# DST handling: in EST the job starts at 10:40 ET and waits until 11:40 ET.
# In EDT it starts at 11:40 ET and proceeds immediately.
set -u

REPO=/root/mlb-model
VENV=$REPO/venv/bin/python
LOG=$REPO/logs/on_monday_$(date -u +%Y%m%d).log
SEASON=2026

exec >> "$LOG" 2>&1
echo "=== ON Monday runner started $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

cd "$REPO" || exit 1
git pull --ff-only || { echo "HALT: git pull failed"; exit 1; }

# ─── Wait until 11:40 ET (DST-safe) ──────────────────────────────
if [ "${ON_SKIP_WAITS:-}" != "1" ]; then
    while true; do
        ET_HHMM=$(TZ=America/New_York date +%H%M)
        if [ "$ET_HHMM" -ge 1140 ]; then
            break
        fi
        echo "Waiting for 11:40 ET (currently $(TZ=America/New_York date +%H:%M) ET)"
        sleep 60
    done
fi

# ─── Pull PBP ────────────────────────────────────────────────────
echo "--- pull_pbp.py $SEASON ---"
$VENV nfl/sim/pull_pbp.py "$SEASON"

# ─── PBP freshness check with retry ──────────────────────────────
MAX_RETRIES=4
for i in $(seq 1 $MAX_RETRIES); do
    if $VENV research/own_numbers/run_monday.py --season "$SEASON" --week auto --check-pbp-only; then
        echo "PBP freshness check passed"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "HALT: PBP freshness check failed after $MAX_RETRIES retries"
        exit 1
    fi
    ET_NOW=$(TZ=America/New_York date +%H%M)
    if [ "$ET_NOW" -ge 1158 ]; then
        echo "HALT: PBP freshness check failed and it is past 11:58 ET"
        exit 1
    fi
    echo "PBP stale, retrying pull in 5 min (attempt $i/$MAX_RETRIES)"
    if [ "${ON_SKIP_WAITS:-}" != "1" ]; then
        sleep 300
    fi
    $VENV nfl/sim/pull_pbp.py "$SEASON"
done

# ─── Wait until 12:00 ET ─────────────────────────────────────────
if [ "${ON_SKIP_WAITS:-}" != "1" ]; then
    while true; do
        ET_HHMM=$(TZ=America/New_York date +%H%M)
        if [ "$ET_HHMM" -ge 1200 ]; then
            break
        fi
        echo "Waiting for 12:00 ET (currently $(TZ=America/New_York date +%H:%M) ET)"
        sleep 60
    done
fi

# ─── Run the Monday runner ───────────────────────────────────────
echo "--- run_monday.py --season $SEASON --week auto ---"
$VENV research/own_numbers/run_monday.py --season "$SEASON" --week auto
RUNNER_RC=$?

# ─── Push results ────────────────────────────────────────────────
echo "--- push_paths.sh ---"
bash shared/push_paths.sh "ON Monday auto" nfl/data/own/forward research/own_numbers/forward_log.md

echo "=== ON Monday runner finished $(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$RUNNER_RC ==="
exit $RUNNER_RC
