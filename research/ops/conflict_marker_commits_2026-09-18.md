# Both auto-committers guard on index state, so conflict markers get committed

Cowork, 2026-09-18.

## What happened, twice

**2026-04-11**: commit `f9cc5b5f9` "auto: NBA pipeline run" committed 25 files under
`soccer/data/cache/daily/` containing literal `<<<<<<< HEAD` / `>>>>>>> 98132240`
markers. All 25 fail to parse as JSON. They sat in the repo for five months.
Removed in `df44e3eee`.

**2026-09-18**: a `git sync` autostash failed to reapply, leaving
`shared/last_updated.json` unmerged AND `data/line_movement.csv` **staged with
markers inside it**. Caught ~20 minutes before the next auto-commit cycle.

## Why the existing guards cannot catch it

Both pushers check the same thing, and it is the wrong thing.

    shared/git_push.sh:26     git status --porcelain | grep -q '^UU\|^AA\|^DD'  -> exit
    shared/push_daemon.sh:15  same pattern                      -> rebase --abort; merge --abort

Those detect an **unmerged index entry**. But once a failed resolution leaves
markers in a file git no longer considers unmerged — because the rebase was
aborted, or the file was staged, or the conflict came from a stash pop rather than
a merge — the file reads as an ordinary `M`. Every guard in the system is blind to
it, and the `git add -A` two lines later commits it.

That is precisely tonight's `data/line_movement.csv` (status `M `, markers inside),
and precisely what April's 25 files must have looked like.

`push_daemon.sh` is worse in one respect: its cleanup runs `git rebase --abort` and
`git merge --abort`, neither of which does anything to a **stash-pop** conflict,
then logs "cleaned up stale conflict state" without verifying anything changed, then
falls through to `git add -A`. It would have logged success while committing markers.

Note also that `git_push.sh:80` already lists the soccer daily cache as a
"high-frequency conflicts" safe-file. This area was known to conflict constantly,
and the resolution path still leaked markers into a commit.

## The fix — check content, not index state

Same lesson as D72: gate on what the thing actually is, not on a proxy that can
drift out from under you. Insert after `git add -A` and before the commit, in BOTH
scripts:

    MARKED=$(git diff --cached --name-only -z \
        | xargs -0 -r grep -lE '^(<<<<<<< |>>>>>>> )' 2>/dev/null)
    if [ -n "$MARKED" ]; then
        echo "$TIMESTAMP — REFUSED: conflict markers in staged files:" >> "$LOG"
        echo "$MARKED" >> "$LOG"
        git reset >> "$LOG" 2>&1
        exit 1
    fi

Match the 7-character marker **plus a trailing space**. A bare `=======` matches
CSV separator rows and minified JSON; `^<<<<<<< ` and `^>>>>>>> ` do not
false-positive — verified against this repo, which contains `=======` rows in
`data/line_movement.csv` legitimately.

## Secondary

`soccer/data/cache/daily/` is still NOT gitignored. It is a regenerable daily API
cache the repo does not need, and it is the largest single source of rebase
conflicts here.
