#!/bin/bash
# Called by pipeline scripts after completing a run
# Usage: bash shared/git_push.sh "MLB confirm run"

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
    echo "ERROR: git pull --rebase failed — aborting push"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) REBASE_FAIL — $MSG" >> "$ERR_LOG"
    git rebase --abort 2>/dev/null
    exit 1
fi

# Push with error capture
if ! git push origin main 2>>"$ERR_LOG"; then
    echo "ERROR: git push failed"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PUSH_FAIL — $MSG" >> "$ERR_LOG"
    exit 1
fi

echo "Pushed: $MSG"
