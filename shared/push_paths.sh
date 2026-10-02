#!/bin/bash
# Narrow push for Mac-side pipelines: commit ONLY the given paths, then rebase onto origin and push.
# Replaces the dependence on broad `git add -A` sweeps (WNBA updater / Statcast) — pipeline audit
# 2026-10-01, master doc v39 §9. Never touches anything outside the listed paths.
#
# Usage: bash shared/push_paths.sh "<message>" <path> [<path> ...]
set -u
export GIT_EDITOR=true EDITOR=true VISUAL=true

MSG=${1:?message required}
shift
[ "$#" -ge 1 ] || { echo "no paths given"; exit 2; }

cd "$(dirname "$0")/.." || exit 1
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if [ -e .git/index.lock ] || [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
    echo "$TS SKIP: git busy (lock or rebase in progress)"
    exit 0
fi

git add -- "$@" || exit 1
if git diff --cached --quiet -- "$@"; then
    echo "$TS no changes in: $*"
    exit 0
fi
# commit only these paths, even if something else happens to be staged
git commit -q -m "auto: $MSG $TS" -- "$@" || exit 1

for attempt in 1 2 3; do
    if git pull -q --rebase --autostash origin main && git push -q origin main; then
        echo "$TS PUSHED: $MSG"
        exit 0
    fi
    git rebase --abort 2>/dev/null
    sleep $((attempt * 20))
done
echo "$TS PUSH FAILED after 3 attempts: $MSG (commit kept locally; next run retries)"
exit 1
