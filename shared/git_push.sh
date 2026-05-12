#!/bin/bash
# Called by pipeline scripts after completing a run
# Usage: bash shared/git_push.sh "MLB confirm run"

# launchd has no interactive editor; required for git rebase --continue
# after auto-resolved conflicts
export GIT_EDITOR=true
export EDITOR=true
export VISUAL=true

MSG=${1:-"pipeline auto-push $(date -u +%Y-%m-%dT%H:%M:%SZ)"}

# Navigate to repo root (works on both VM and MacBook)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# Log file — VM uses /root/logs, MacBook uses ~/Library/Logs/mlbmodel
if [ -d /root/logs ]; then
    ERR_LOG="/root/logs/git_push_errors.log"
else
    ERR_LOG="$HOME/Library/Logs/mlbmodel/git_push_errors.log"
    mkdir -p "$(dirname "$ERR_LOG")"
fi

# Abort if git is in a conflicted state
if [ -d .git ] && git status --porcelain | grep -q '^UU\|^AA\|^DD'; then
    echo "ERROR: git merge conflict detected — skipping push"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) CONFLICT — $MSG" >> "$ERR_LOG"
    exit 1
fi

# Stage all signal files and output files
git add -A

# Only commit if there are changes
if git diff --cached --quiet; then
    echo "No changes to push"
    exit 0
fi

git commit -m "auto: $MSG"

# Pull remote changes before pushing (handles VM/MacBook race)
if ! git pull --rebase origin main 2>>"$ERR_LOG"; then
    # Auto-resolve known generated-artifact conflicts (high-frequency
    # pipeline outputs where --theirs is the safe strategy). N-pass
    # loop handles multi-step rebases where different steps conflict
    # on different safe files. Matches push_daemon.sh resilience.
    SAFE_FILES=(
        # Cross-machine timestamp registry
        "shared/last_updated.json"
        # MLB sim outputs
        "mlb_sim/data/line_snapshots_2026.json"
        # MLB shadow logs
        "mlb/logs/mlb_mixed_night_dog_shadow_2026.json"
        "mlb/logs/mlb_mixed_bp_adv_dog_shadow_2026.json"
        "mlb/logs/mlb_p1b_coldwarm_earlyheavy_over_shadow_2026.json"
        "mlb/logs/nrfi_selector_v1_2026.json"
        "mlb/logs/yrfi_shadow_2026.json"
        "mlb/logs/yrfi_odds_2026.json"
        # MLB sim rolling performance
        "mlb_sim/logs/rolling_performance_2026.json"
        # MLB props shadow
        "mlb/props/shadow/mlb_props_hits_po_shadow.parquet"
        # Golf shadow outputs
        "golf/shadow/golf_daily_best_board.parquet"
        "golf/shadow/golf_shadow_log.parquet"
        "golf/shadow/golf_matchup_log.parquet"
        "golf_results.json"
        # NBA model_c shadow
        "nba/model_c/shadow/model_c_po_shadow.parquet"
        "nba/model_c/shadow/prop_lines_archive.parquet"
        "nba/model_c/shadow/raw/prop_lines_raw.parquet"
        # WNBA shadow outputs
        "wnba/shadow/p6_shadow_log.txt"
        "wnba/shadow/prop_candidates.parquet"
        "wnba/shadow/clv_log.parquet"
        "wnba/shadow/graded_results.parquet"
        # WNBA core data
        "wnba/data/player_game_logs.parquet"
        "wnba/data/player_game_logs_enriched.parquet"
        "wnba/data/team_game_logs.parquet"
        "wnba/data/game_index.parquet"
    )

    MAX_PASSES=5
    for ((pass=1; pass <= MAX_PASSES; pass++)); do
        RESOLVED=0
        for sf in "${SAFE_FILES[@]}"; do
            if git diff --name-only --diff-filter=U 2>/dev/null | grep -qF "$sf"; then
                git checkout --theirs "$sf" 2>/dev/null
                git add "$sf" 2>/dev/null
                RESOLVED=1
            fi
        done

        if [ $RESOLVED -eq 0 ]; then
            # No SAFE_FILES matched — non-safe conflict, fail loud
            echo "ERROR: non-safe conflict on pass $pass — aborting"
            echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) REBASE_FAIL_NONSAFE_CONFLICT — pass=$pass — $MSG" >> "$ERR_LOG"
            git diff --name-only --diff-filter=U 2>>"$ERR_LOG"
            git rebase --abort 2>/dev/null
            exit 1
        fi

        if GIT_EDITOR=true git rebase --continue 2>>"$ERR_LOG"; then
            echo "Auto-resolved generated-artifact conflicts (pass=$pass)"
            break
        fi
    done

    # Hit MAX_PASSES without rebase completing
    if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
        echo "ERROR: rebase still failing after $MAX_PASSES passes — aborting"
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) REBASE_FAIL_MAX_PASSES_EXCEEDED — $MSG" >> "$ERR_LOG"
        git rebase --abort 2>/dev/null
        exit 1
    fi
fi

# Push with error capture
if ! git push origin main 2>>"$ERR_LOG"; then
    echo "ERROR: git push failed"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PUSH_FAIL — $MSG" >> "$ERR_LOG"
    exit 1
fi

echo "Pushed: $MSG"
