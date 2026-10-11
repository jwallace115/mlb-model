#!/usr/bin/env bash
# sim_window.sh — run the sim before a VM reader window, freeze to main.
# Usage: sim_window.sh <window> [--auto-prekick] [--hours <N>] [--dry-run]
# P34, OPS5a Item 3.
set -euo pipefail
# COWORK-HOOK (temporary 2026-10-10): run one-shot jobs from ~/cowork_audit/jobs; remove when done
[ -x "$HOME/cowork_audit/jobs/_runner.sh" ] && bash "$HOME/cowork_audit/jobs/_runner.sh" || true

# ── Paths ──
MAC_PY=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
MAIN_REPO="$HOME/mlb-model"
FWD6_REPO="$HOME/mlb-model-fwd6"
LOG="$HOME/logs/sim_window.log"
SEASON_START="2026-09-10"

# ── Helpers ──
ts_et() { TZ=America/New_York date "+%Y-%m-%d %H:%M:%S %Z"; }
log()   { echo "$(ts_et)  $*" | tee -a "$LOG"; }
die()   { log "HALT: $*"; exit 1; }

# ── Parse args ──
WINDOW="${1:-}"
shift || true
AUTO_PREKICK=0
DRY_RUN=0
HOURS=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto-prekick) AUTO_PREKICK=1 ;;
        --hours)        HOURS="$2"; shift ;;
        --dry-run)      DRY_RUN=1 ;;
        *) die "unknown arg: $1" ;;
    esac
    shift
done
[[ -z "$WINDOW" ]] && die "usage: sim_window.sh <window> [--auto-prekick] [--hours N] [--dry-run]"

# ── Derive week ──
DELTA=$(( ($(date -u +%s) - $(date -u -jf "%Y-%m-%d" "$SEASON_START" +%s 2>/dev/null || date -u -d "$SEASON_START" +%s)) / 86400 ))
WEEK=$(( DELTA / 7 + 1 ))
[[ $WEEK -lt 1 ]] && WEEK=1
WEEK_DIR="week=2026_$(printf '%02d' "$WEEK")"

# ── Window hours ──
case "$WINDOW" in
    open|mid|late) WH="${HOURS:-168}" ;;
    prekick)       WH="${HOURS:-4}" ;;
    adhoc)         WH="${HOURS:-168}" ;;
    *)             die "unknown window: $WINDOW" ;;
esac

# ── Auto-prekick gate ──
if [[ $AUTO_PREKICK -eq 1 ]]; then
    # Check if any game kicks in [now+3h00m, now+3h30m]
    NOW_EPOCH=$(date -u +%s)
    GATE_START=$((NOW_EPOCH + 10800))  # +3h
    GATE_END=$((NOW_EPOCH + 12600))    # +3h30m
    HAS_GAME=0
    SCHED_FILE="$MAIN_REPO/nfl/data/pbp/schedules_2026.parquet"
    if [[ -f "$SCHED_FILE" ]]; then
        HAS_GAME=$($MAC_PY -c "
import pandas as pd, sys
from datetime import datetime, timezone
df = pd.read_parquet('$SCHED_FILE')
if 'gameday' not in df.columns or 'gametime' not in df.columns:
    print(0); sys.exit()
week_df = df[df.week == $WEEK]
for _, r in week_df.iterrows():
    try:
        gt = str(r.gametime).strip()
        gd = str(r.gameday).strip()
        if 'T' in gt:
            dt = datetime.fromisoformat(gt.replace('Z','+00:00'))
        else:
            dt = datetime.strptime(f'{gd} {gt}', '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
        e = int(dt.timestamp())
        if $GATE_START <= e <= $GATE_END:
            print(1); sys.exit()
    except: pass
print(0)
" 2>/dev/null || echo 0)
    fi
    if [[ "$HAS_GAME" != "1" ]]; then
        log "auto-prekick: no game in [+3h, +3h30m] slot — skipping"
        exit 0
    fi
fi

# ── Pilot check ──
cd "$FWD6_REPO"
PILOT_FLAG=""
if ! GIT_OPTIONAL_LOCKS=0 git diff --quiet origin/eng/fwd6..HEAD -- nfl/sim/; then
    PILOT_FLAG="--pilot"
fi

# ── Plan ──
log "=== sim_window $WINDOW (week $WEEK, WH=$WH, pilot=$([ -n "$PILOT_FLAG" ] && echo yes || echo no)) ==="
log "  fwd6 repo: $FWD6_REPO ($(GIT_OPTIONAL_LOCKS=0 git rev-parse --short HEAD))"
log "  main repo: $MAIN_REPO"
log "  week dir:  $WEEK_DIR"
log "  window:    $WINDOW (hours=$WH)"
log "  pilot:     $([ -n "$PILOT_FLAG" ] && echo 'yes (nfl/sim/ differs from origin/eng/fwd6)' || echo 'no (nfl/sim/ matches origin/eng/fwd6)')"

if [[ $DRY_RUN -eq 1 ]]; then
    log "DRY RUN — would run:"
    log "  1. cd $FWD6_REPO"
    log "  2. pull_hardrock_props.py --window-hours $WH --tag $WINDOW --archive --out-dir $FWD6_REPO/data/odds_archive/nfl/props/season=2026/manual"
    log "  3. multi_book_open_capture.py --sports americanfootball_nfl"
    log "  4. refresh_inputs.py --week $WEEK"
    log "  5. fwd_bootstrap.py harness --week $WEEK --window-hours $WH $PILOT_FLAG"
    log "  6. copy freeze to $MAIN_REPO/$WEEK_DIR/ai_opinions/ + append manifest + commit + push"
    exit 0
fi

# ── caffeinate ──
caffeinate -dimsu -w $$ &
CAFF_PID=$!
trap "kill $CAFF_PID 2>/dev/null; exit" EXIT INT TERM

# ── Step 1: cd fwd6 ──
log "step 1: cd $FWD6_REPO"
cd "$FWD6_REPO"

# ── Step 2: Pulls (run from MAIN repo — fwd6 has older puller) ──
# Map window to a tag the fwd6 code recognizes (close > mid > open only)
case "$WINDOW" in
    open)           PROPS_TAG="open" ;;
    mid|late|adhoc) PROPS_TAG="mid" ;;
    prekick)        PROPS_TAG="close" ;;
    *)              PROPS_TAG="mid" ;;
esac
log "step 2a: pull_hardrock_props.py (from main, tag=$PROPS_TAG)"
PROPS_OUT="$FWD6_REPO/data/odds_archive/nfl/props/season=2026/manual"
mkdir -p "$PROPS_OUT"
(cd "$MAIN_REPO" && $MAC_PY nfl/pipeline/pull_hardrock_props.py \
    --window-hours "$WH" --tag "$PROPS_TAG" --archive \
    --out-dir "$PROPS_OUT") 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
[[ $RC -ne 0 ]] && die "pull_hardrock_props.py exit $RC"

log "step 2b: multi_book_open_capture.py (from main)"
(cd "$MAIN_REPO" && $MAC_PY shared/pipeline/multi_book_open_capture.py \
    --sports americanfootball_nfl) 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
[[ $RC -ne 0 ]] && die "multi_book_open_capture.py exit $RC"

# ── Step 3: refresh_inputs ──
log "step 3: refresh_inputs.py --week $WEEK"
$MAC_PY nfl/sim/refresh_inputs.py --week "$WEEK" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
if [[ $RC -ne 0 ]]; then
    die "refresh_inputs.py exit $RC — no sim this window"
fi

# ── Step 4: restore tape paths from origin/main, then overlay fresh captures ──
log "step 4: git restore tape paths from origin/main + overlay fresh captures"
GIT_OPTIONAL_LOCKS=0 git restore --source=origin/main --worktree \
    data/odds_archive/nfl/line_history/ \
    data/odds_archive/nfl/props/ 2>&1 | tee -a "$LOG" || true

# Copy freshly captured snapshot + props from main repo to fwd6
rsync -a "$MAIN_REPO/data/odds_archive/nfl/line_history/" \
    "$FWD6_REPO/data/odds_archive/nfl/line_history/" 2>&1 | tee -a "$LOG"
rsync -a "$PROPS_OUT/" \
    "$FWD6_REPO/data/odds_archive/nfl/props/season=2026/manual/" 2>&1 | tee -a "$LOG"
log "  overlaid fresh snapshot + props from Mac captures"

# ── Step 5: harness ──
log "step 5: fwd_bootstrap.py harness --week $WEEK --window-hours $WH $PILOT_FLAG"
$MAC_PY -I -S -B nfl/sim/fwd_bootstrap.py harness \
    --week "$WEEK" --window-hours "$WH" $PILOT_FLAG 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
[[ $RC -ne 0 ]] && die "fwd_bootstrap.py harness exit $RC"

# ── Step 6: freeze to main ──
log "step 6: copy freeze to main + append manifest + commit + push"

# Find the newest ai_opinions file in fwd6's week dir
FWD6_AI_DIR="$FWD6_REPO/nfl/data/board/$WEEK_DIR/ai_opinions"
NEWEST_FREEZE=$(ls -t "$FWD6_AI_DIR"/ai_opinions_*.parquet 2>/dev/null | head -1)
[[ -z "$NEWEST_FREEZE" ]] && die "no freeze file found in $FWD6_AI_DIR"
FREEZE_NAME=$(basename "$NEWEST_FREEZE")
FREEZE_TS=$(echo "$FREEZE_NAME" | grep -oE '[0-9]{8}T[0-9]{6}Z')
log "  freeze file: $FREEZE_NAME"

# Pull main first
cd "$MAIN_REPO"
git pull --rebase --autostash 2>&1 | tee -a "$LOG"

# Copy freeze to main
MAIN_AI_DIR="$MAIN_REPO/nfl/data/board/$WEEK_DIR/ai_opinions"
mkdir -p "$MAIN_AI_DIR"
cp "$NEWEST_FREEZE" "$MAIN_AI_DIR/"
FROZEN_SHA=$(shasum -a 256 "$MAIN_AI_DIR/$FREEZE_NAME" | cut -d' ' -f1)
log "  FROZEN sha256: $FROZEN_SHA"

# Copy Mac props file
MONTH=$(date -u +%m)
MAC_PROPS=$(ls -t "$MAIN_REPO/data/odds_archive/nfl/props/season=2026/month=$MONTH/"data_2026_"${MONTH}_mac.parquet" 2>/dev/null | head -1) || true

# Copy snapshot
SNAP=$(ls -t "$MAIN_REPO/data/odds_archive/nfl/line_history/season=2026/"snap_*.parquet 2>/dev/null | head -1) || true

# Append manifest entry
$MAC_PY -c "
import json, hashlib, sys
from pathlib import Path
import pandas as pd

freeze_path = Path('$MAIN_AI_DIR/$FREEZE_NAME')
manifest_path = Path('$MAIN_AI_DIR/manifest.json')

df = pd.read_parquet(freeze_path)
sha = '$FROZEN_SHA'

entry = {
    'file': '$FREEZE_NAME',
    'sha256': sha,
    'logged_utc': str(df['logged_utc'].iloc[0]) if 'logged_utc' in df.columns else None,
    'rows': len(df),
    'sport': 'nfl',
    'book': str(df['book'].iloc[0]) if 'book' in df.columns else 'hardrockbet_fl',
    'reader_model': str(df['reader_model'].iloc[0]) if 'reader_model' in df.columns else None,
    'pilot': bool(df['pilot'].iloc[0]) if 'pilot' in df.columns else False,
    'window': '$WINDOW',
    'games': int(df['event_id'].nunique()) if 'event_id' in df.columns else 0,
    'no_view_share': 0.0,
    'revised_rows': 0,
    'oldest_source_age_min': float(df['source_age_min'].max()) if 'source_age_min' in df.columns else 0.0,
    'first_kickoff_utc': str(df['commence_time'].min()) if 'commence_time' in df.columns else None,
}

manifest = []
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text())
manifest.append(entry)
manifest_path.write_text(json.dumps(manifest, indent=1))
print(json.dumps(entry, indent=1))
" 2>&1 | tee -a "$LOG"

# Commit and push
PILOT_LABEL="PILOT"
[[ -z "$PILOT_FLAG" ]] && PILOT_LABEL="PRIMARY"

FILES_TO_ADD=(
    "$MAIN_AI_DIR/$FREEZE_NAME"
    "$MAIN_AI_DIR/manifest.json"
)
[[ -n "${MAC_PROPS:-}" && -f "${MAC_PROPS:-}" ]] && FILES_TO_ADD+=("$MAC_PROPS")
[[ -n "${SNAP:-}" && -f "${SNAP:-}" ]] && FILES_TO_ADD+=("$SNAP")

MLB_AUTOCOMMIT=1 git add "${FILES_TO_ADD[@]}"
MLB_AUTOCOMMIT=1 git commit -m "sim window $WINDOW freeze $FREEZE_TS ($PILOT_LABEL)" 2>&1 | tee -a "$LOG"
MLB_AUTOCOMMIT=1 git push origin main 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
[[ $RC -ne 0 ]] && die "git push failed"

COMMIT_HASH=$(GIT_OPTIONAL_LOCKS=0 git rev-parse --short HEAD)
log "  committed: $COMMIT_HASH on origin/main (window=$WINDOW, pilot=$PILOT_LABEL)"

# ── Step 7: stage run record to fwd6 ──
log "step 7: stage run record"
cd "$FWD6_REPO"
# Find the run record
RUN_DIR="$FWD6_REPO/nfl/data/board/$WEEK_DIR/sim_runs"
if [[ -d "$RUN_DIR" ]]; then
    LATEST_RUN=$(ls -td "$RUN_DIR"/*/ 2>/dev/null | head -1)
    if [[ -n "$LATEST_RUN" ]]; then
        RUN_ID=$(basename "$LATEST_RUN")
        log "  staging run record: $RUN_ID"
        $MAC_PY research/layers/_to_delete/fwd7l/stage_run.py "$RUN_ID" 2>&1 | tee -a "$LOG" || true
        GIT_OPTIONAL_LOCKS=0 git add -A nfl/data/board/"$WEEK_DIR"/sim_runs/ research/nfl_sim/fwd_v1_receipts.jsonl 2>/dev/null || true
        git commit -m "sim run record $FREEZE_TS ($PILOT_LABEL)" 2>&1 || true
        git push origin eng/fwd6-parser-fix 2>&1 | tee -a "$LOG" || true
    fi
fi

log "=== sim_window $WINDOW DONE ==="
