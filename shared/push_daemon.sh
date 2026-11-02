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
if GIT_OPTIONAL_LOCKS=0 git status --porcelain | grep -q '^UU\|^AA\|^DD'; then
    git rebase --abort 2>/dev/null
    git merge --abort 2>/dev/null
    if GIT_OPTIONAL_LOCKS=0 git status --porcelain | grep -q '^UU\|^AA\|^DD'; then
        echo "$TIMESTAMP — STILL CONFLICTED after abort (stash-pop conflicts are not
 cleared by rebase/merge --abort) — refusing to commit" >> "$LOG"
        exit 1
    fi
    echo "$TIMESTAMP — cleaned up stale conflict state" >> "$LOG"
fi

# P81(a): a stale rebase dir with only an autostash in it (aborted --autostash rebase) blocks every later pull --rebase
for d in .git/rebase-merge .git/rebase-apply; do
    if [ -d "$d" ] && [ ! -f "$d/head-name" ] && [ ! -f "$d/onto" ]; then
        rm -rf "$d"
        echo "$TIMESTAMP — removed stale $d (no rebase in progress)" >> "$LOG"
    fi
done

# P81(b): conflict resolution by path ownership. During `git pull --rebase`, --ours = origin (what the Mac pushed), --theirs = the
# commit being replayed (the VM's own output). Mac-owned paths take origin; everything else the VM writes takes the VM's version.
is_mac_owned() {
    case "$1" in
        *_mac.parquet|soccer/data/cache/daily/*|nfl/data/board/*/sim_runs/*|data/odds_archive/nfl/props/season=*/month=*/data_*_mac.parquet) return 0;;
        *) return 1;;
    esac
}
resolve_conflicts() {   # returns 0 when the rebase finished, 1 when it could not
    local step
    for step in 1 2 3 4 5 6 7 8 9 10; do
        local U; U=$(git diff --name-only --diff-filter=U 2>/dev/null)
        [ -z "$U" ] && [ ! -d .git/rebase-merge ] && [ ! -d .git/rebase-apply ] && return 0
        local f
        for f in $U; do
            if is_mac_owned "$f"; then git checkout --ours -- "$f" 2>/dev/null; else git checkout --theirs -- "$f" 2>/dev/null; fi
            git add -- "$f" 2>/dev/null || git rm -q --cached -- "$f" 2>/dev/null
            echo "$TIMESTAMP — resolved $f ($(is_mac_owned "$f" && echo origin || echo vm))" >> "$LOG"
        done
        GIT_EDITOR=true git rebase --continue >> "$LOG" 2>&1 || true
        [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || return 0
    done
    return 1
}

# Stage all changes
git add -A

# Refuse to commit conflict markers. The UU/AA/DD check above is an INDEX-STATE
# check: once a failed resolution leaves markers in a file git no longer considers
# unmerged (rebase aborted, file staged, or a stash-pop conflict), the file reads
# as an ordinary M and that check is blind to it. This is a CONTENT check.
# 2026-04-11 f9cc5b5f9 committed 25 unparseable soccer cache files this way.
# Matches the 7-char marker plus a trailing space: a bare "=======" occurs
# legitimately in data/line_movement.csv. -I skips binaries (parquet).
MARKED=$(git diff --cached --name-only -z | while IFS= read -r -d '' f; do
    if [ -f "$f" ] && grep -qIE '^(<<<<<<< |>>>>>>> )' "$f" 2>/dev/null; then
        printf '%s\n' "$f"
    fi
done)
if [ -n "$MARKED" ]; then
    echo "$TIMESTAMP — REFUSED: conflict markers in staged files" >> "$LOG"
    echo "$MARKED" >> "$LOG"
    git reset >/dev/null 2>&1
    exit 1
fi

# Nothing to push — exit cleanly
if git diff --cached --quiet; then
    echo "$TIMESTAMP — no changes" >> "$LOG"
    exit 0
fi

# Commit
git commit -m "auto: dashboard update $TIMESTAMP" >> "$LOG" 2>&1

# Pull with rebase (P81: ownership-based conflict resolution)
if ! git pull --rebase --autostash origin main >> "$LOG" 2>&1; then
    if resolve_conflicts; then
        echo "$TIMESTAMP — auto-resolved rebase conflicts by path ownership" >> "$LOG"
    else
        git rebase --abort 2>/dev/null
        rm -rf .git/rebase-merge .git/rebase-apply
        echo "$TIMESTAMP — PUSH FAILED: rebase conflict not resolvable by ownership rules" >> "$LOG"
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
