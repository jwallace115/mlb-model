# Work order FWD2d — the Sunday runbook (2026-09-30)

Written by Cowork with D238. **Scope: `research/nfl_sim/make_runbook.py` and the runbook it writes, only.** Neither is
in FWD_EXPERIMENT_v1.json, so this does not change the experiment. Do NOT touch any hashed file; `test_freeze_v1` and
the experiment-manifest test must pass unchanged. **Deadline: before Sat 10-03.**

Pre-check (Cowork):
- **Runtime:** seconds (reads the schedule and the tape).
- **Credits:** zero.
- **Paths:** `research/nfl_sim/make_runbook.py` and `research/nfl_sim/fwd1_runbook.md`, both on main after the D238
  merge.
- **The deployed VM props schedule** (capture_status, WO12 deploy), in UTC:

  | Days | Time | Tag |
  |---|---|---|
  | Tue | 14:00 | open |
  | Wed-Sat | 14:00 | mid |
  | Tue-Sat | 02:00 | mid |
  | Thu | 22:00 | TNF |
  | Sun | 15:00 and 16:00 | close |
  | Mon | 23:45 | MNF |

  If the VM's crontab is committed anywhere in the repo, read it from there instead and cite the file.

```
Work order FWD2d (research/nfl_sim/workorder_FWD2d_2026-09-30.md). Branch eng/fwd2d from origin/main (after the D238
merge) in a worktree. Gate: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md | grep -c "^### D238"`
prints 1. One item, one commit, D239 appended in the same commit. Remove the worktree when done.

Item 0 (D239) — make_runbook.py:
  (a) VM props slots by weekday and time, exactly as the table in the order says (or as the committed crontab says —
      cite it). "Latest slot before the run" respects the weekday.
  (b) Windows. Each distinct kick cluster is its own run:
      - TNF: run 23:30Z Thu.
      - Sunday international game(s) before 17:00Z: its own run 45 min before kick, with --window-hours reaching only
        that game, after Jeff's manual pull at kick−75 min (print the exact pull command and its credits).
      - Sunday main slate (17:00Z through SNF): one run at 16:15Z, after the Sun 16:00Z VM slot, with --window-hours
        reaching SNF but not MNF.
      - MNF: run at 23:55Z Mon, after the 23:45Z slot.
      No run may include a game whose newest scheduled pull is more than 3 h old at the run time unless a manual pull
      is printed for it.
  (c) Remove the stale "ratings.py overwrites params_v1.json" note. The weekly refresh block is:
      pull_nflverse_inputs.py, ratings.py (no --write-params), test_freeze_v1.
  (d) Tests (execute make_runbook's functions on the real week-4 schedule):
      - TNF slot = Thu 22:00Z;
      - London IND@WAS is its own run, and not in the main slate;
      - the main-slate run is at or after 16:00Z Sun and covers SNF DET@CAR;
      - MNF ATL@NO is excluded from the Sunday runs;
      - no printed run exceeds the 3 h age rule without a manual pull.
  Regenerate research/nfl_sim/fwd1_runbook.md and paste it in full.
```
