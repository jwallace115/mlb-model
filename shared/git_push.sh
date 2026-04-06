#!/bin/bash
# Called by pipeline scripts after completing a run
# Usage: bash shared/git_push.sh "MLB confirm run"

MSG=${1:-"pipeline auto-push $(date -u +%Y-%m-%dT%H:%M:%SZ)"}

# Navigate to repo root (works on both VM and MacBook)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# Abort if git is in a conflicted state
if [ -d .git ] && git status --porcelain | grep -q '^UU\|^AA\|^DD'; then
    echo "ERROR: git merge conflict detected — skipping push"
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
git push origin main

echo "Pushed: $MSG"
