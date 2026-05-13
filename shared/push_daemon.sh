#!/bin/bash
# Centralized git push daemon — the ONLY script that pushes to GitHub from the VM.
# Runs every 30 minutes via cron. All pipelines write files locally; this pushes them.
#
# Conflict resolution: auto-resolves known safe files (last_updated.json, golf parquets).
# If other files conflict, aborts and logs — never silently drops data.

LOG=/root/logs/push_daemon.log
REPO=/root/mlb-model
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$REPO" || exit 1

# Abort if already in a conflicted state from a prior failed run
if git status --porcelain | grep -q '^UU\|^AA\|^DD'; then
    git rebase --abort 2>/dev/null
    git merge --abort 2>/dev/null
    echo "$TIMESTAMP — cleaned up stale conflict state" >> "$LOG"
fi

# Stage all changes
git add -A

# Nothing to push — exit cleanly
if git diff --cached --quiet; then
    echo "$TIMESTAMP — no changes" >> "$LOG"
    exit 0
fi

# Commit
git commit -m "auto: dashboard update $TIMESTAMP" >> "$LOG" 2>&1

# Pull with rebase
if ! git pull --rebase origin main >> "$LOG" 2>&1; then
    # Auto-resolve known safe conflict files (always take remote version)
    SAFE_FILES=(
        "shared/last_updated.json"
        "golf/shadow/golf_daily_best_board.parquet"
        "golf/shadow/golf_shadow_log.parquet"
        "mlb/logs/p09_shadow_2026.json"
    )
    RESOLVED=0
    for sf in "${SAFE_FILES[@]}"; do
        if git diff --name-only --diff-filter=U 2>/dev/null | grep -q "$sf"; then
            git checkout --theirs "$sf" 2>/dev/null
            git add "$sf" 2>/dev/null
            RESOLVED=1
        fi
    done

    if [ $RESOLVED -eq 1 ]; then
        # Try to continue rebase after resolving safe files
        if GIT_EDITOR=true git rebase --continue >> "$LOG" 2>&1; then
            echo "$TIMESTAMP — auto-resolved safe file conflicts" >> "$LOG"
        else
            # Still failing — check if more safe files need resolving in next rebase step
            for sf in "${SAFE_FILES[@]}"; do
                if git diff --name-only --diff-filter=U 2>/dev/null | grep -q "$sf"; then
                    git checkout --theirs "$sf" 2>/dev/null
                    git add "$sf" 2>/dev/null
                fi
            done
            if GIT_EDITOR=true git rebase --continue >> "$LOG" 2>&1; then
                echo "$TIMESTAMP — auto-resolved multi-step conflicts" >> "$LOG"
            else
                git rebase --abort 2>/dev/null
                echo "$TIMESTAMP — PUSH FAILED: rebase conflict on non-auto-resolvable file" >> "$LOG"
                exit 1
            fi
        fi
    else
        git rebase --abort 2>/dev/null
        echo "$TIMESTAMP — PUSH FAILED: rebase conflict (no safe files to auto-resolve)" >> "$LOG"
        exit 1
    fi
fi

# Check for incoming code changes (from MacBook deploys)
BEFORE_HASH=$(git rev-parse HEAD)

# Fetch remote to detect incoming changes
git fetch origin >> "$LOG" 2>&1
REMOTE_HASH=$(git rev-parse origin/main)

# Push local changes
if git push origin main >> "$LOG" 2>&1; then
    echo "$TIMESTAMP — PUSH SUCCESS" >> "$LOG"
else
    echo "$TIMESTAMP — PUSH FAILED: push rejected" >> "$LOG"
    exit 1
fi

# Pull any remote changes (from MacBook deploys)
if [ "$BEFORE_HASH" != "$REMOTE_HASH" ]; then
    git pull --rebase origin main >> "$LOG" 2>&1
fi

AFTER_HASH=$(git rev-parse HEAD)

# Restart Streamlit if .py code files changed
if [ "$BEFORE_HASH" != "$AFTER_HASH" ]; then
    CHANGED_PY=$(git diff --name-only "$BEFORE_HASH" "$AFTER_HASH" | grep '\.py$' | wc -l)
    if [ "$CHANGED_PY" -gt 0 ]; then
        systemctl restart streamlit-dashboard 2>/dev/null
        echo "$TIMESTAMP — restarted Streamlit ($CHANGED_PY .py files changed)" >> "$LOG"
    fi
fi
