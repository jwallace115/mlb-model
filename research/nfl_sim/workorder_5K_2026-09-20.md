# Phase 5K work order — split Q4_mid at 180 s, one re-fit (QUEUED: run only after 5J is verified and merged)

Date: 2026-09-20 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: D59, D77, D81, D100, D102, D103 in `research/nfl_sim/NFL_SIM_DECISION_v1.md`, and
`research/nfl_sim/phase5i_verification_2026-09-20.md` (section "What did not hold").

## Why this order exists

One `Q4_mid` clock cell covers 121-300 s. Measured by Cowork (2023, 272 games, N=200, offence
tied or trailing 1-8): sim is +5.0 s/play slow on passes and +4.6 on runs in 121-180 s, and
-2.0 / -4.9 in 181-300 s. Right on average, wrong where a tied drive is racing the clock. Broad
tied-drive expiry: 11-salt mean 0.099 (SD 0.012) vs matched 0.081. This order CHANGES THE ENGINE
FINGERPRINT and needs a re-fit, which is why it is separate from 5J. Prerequisites on main:
5J merged, `nfl/sim/run_k1_table.py` and `research/nfl_sim/phase5j_k1_before.txt` present.

## HARD RULES

1. ALL work on branch `eng/5k` in worktree `~/mlb-model-5k`. `main` is not touched. Cowork
   verifies and merges.
2. No existing test, target, tolerance, threshold, `MIN_CELL` or sample filter is edited. New
   tests go in NEW files: `nfl/sim/tests/test_engine_5k.py`.
3. No constant is tuned to hit a test. Table numbers are measured from PBP 2021-24 by committed
   builder code. `N=5,000` for the fit is D51 and does not change.
4. RUNTIME POLICY: never reduce N, subsample, shorten a sweep, skip a test or kill a run to
   finish sooner. Do not budget or narrate how long your own session will take.
5. Prefix EVERY git command with `GIT_OPTIONAL_LOCKS=0`. Push with `git push -u origin eng/5k`.
6. One item, committed and pushed in stages (cell sizes; engine+tables+tests; re-fit+stamp). It writes its `### DNN` entry (after 5J's D104-D107 —
   run `grep -n "^### D1" research/nfl_sim/NFL_SIM_DECISION_v1.md | tail -3` first and take the
   next free number) ON THE BRANCH in the same commit.
7. A diff is not evidence that code runs. Evidence is pasted execution output from the
   production entry point, and for every guard, a run where it changes an outcome.
8. Every number in a report comes from COMMITTED code. API credits: zero — nothing here pulls.
9. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model
GIT_OPTIONAL_LOCKS=0 git pull --rebase --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5k -b eng/5k
cd ~/mlb-model-5k
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"   # must print 7f3d96900218c014
```
If it prints anything else, STOP and report. If a run fails on another missing gitignored
input, link it the same way and say which.

---

## Item 1 (only item) — split `Q4_mid` at 180 s, ONE re-fit, re-stamp

Step 0 — CELL SIZES FIRST, before any engine edit. From `build_clock_table`'s own `scrim`
frame, print n for every (outcome_type x score_state) cell in `Q4_mid_a` = 181-300 s and
`Q4_mid_b` = 121-180 s. `MIN_CELL` is 100 and stays 100. 5I found the tied cells already thin
(n = 117 / 138). Today a missing cell falls back to the ALL-GAME parent `p_<score_state>`
(~normal pace) — for a tied offence at 2:30 that is WORSE than the current unsplit cell.
So the fallback order becomes: split cell -> the existing unsplit `Q4_mid` cell (keep building
it) -> `p_<score_state>` -> legacy. Report which cells used which level. No pooling of score
states, no other new cells.

Change, in all THREE places that set the period — `tables.py::build_clock_table` (~531-538),
`engine.py` scalar path (~1576-1577), and both vectorised blocks (~2429-2444, ~2696-2705) — and
prove by a test that the scalar and vectorised paths label the same (qtr, clock) grid identically.

PRE-REGISTERED (write before running anything after Step 0):
- P1. Sim sec/play, offence tied or trailing 1-8, 2023, 272 games, N=200, measured with the
  late-snap instrumentation from `diag/5h` (commit 07fbed6) cherry-picked onto a scratch
  branch `diag/5k` that is pushed but NEVER merged: pass 121-180 within 2.0 s of real 12.63;
  run 121-180 within 2.0 s of 20.05; pass 181-300 within 2.0 s of 20.17; run 181-300 within
  2.0 s of 32.48. Extend `run_verify_5h.py::late_clock`'s buckets to [0,40,120,180,300] in a
  NEW committed script `nfl/sim/run_verify_5k.py`; do not edit the 5H one.
- P2. Broad tied-drive expiry, 11 salts (same harness as `run_metric_noise_5h.py`): mean falls
  from 0.099 to between 0.085 and 0.095. Cowork's LAST prediction on this metric
  (< 0.081) FAILED, so this one is deliberately modest. The 5A-9 test compares to 0.050 and
  will very likely STAY RED. That is the correct outcome. Do not relax it, do not tune toward it.
- NULL CONTROLS, from `run_k1_table.py` after vs `phase5j_k1_before.txt` (produced by 5J item 4; if it is not on main, STOP), against the 5H seed
  SDs: go rate moves < 0.002 (SD 0.00052); off penalties/game < 0.06 (SD 0.018); def
  penalties < 0.03 (SD 0.007); pts/team < 0.15; Q1-Q3 plays per game < 0.2. Also report
  drives/game (23.8 vs real 21.9) and the 0-40 s bucket (+3.6 s): this item is NOT expected to
  fix either; say what they did.
If a prediction does not hold, say so in the first line of the next free D number. Nothing is tuned to rescue it.

Then, in this order, pasting each trace:
1. Full suite. Summary + every failing assertion with its value. For each red, state whether it
   is red at the parent commit WITH THE SAME VALUE (run it there; do not recall it).
2. `python3 nfl/sim/run_week.py --week 2 --as-of 2026-09-20T15:30:00Z` BEFORE the re-fit: must
   show SIM PRICES SUPPRESSED and NO ranked leg (fingerprint mismatch vs `fit_5i`). If it ranks,
   STOP — bigger finding. Do NOT commit anything under `nfl/data/sim/outputs/week=2026_02/` from
   the worktree: main holds the pre-kick Week 2 board of record (`git checkout -- ` that dir after).
3. `python3 nfl/sim/run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5k` (check the
   script's usage line first; 5C-2b measured ~90 min on 10 workers — measure and report).
   Paste `fit_meta.json`.
4. `run_cal_maps.py --fit-dir fit_5k`; show `save_calibration` read fingerprints from `fit_meta.json`.
5. Board again (same command): ranks, `sim_pricing_enabled` true. Paste the trace.
6. `run_k1_table.py` -> `phase5k_k1_after.txt` (+ rows). `run_k4.py` on `fit_5k`, rows committed
   this time. Report K4 as a measurement. **Do not interpret it as validation.**

Decision entry: the next free D number — cell sizes and fallback levels, P1/P2 held or not, null controls, the new
fingerprint, K1 before/after with every line that crossed a tolerance in EITHER direction.

---

## What this work order does NOT do

- It does not merge to `main`; Cowork verifies first. From the merge on, the board runs on `fit_5k`;
  every logged sim leg carries its fingerprint and `fit_5i` weeks are never pooled silently with
  `fit_5k` weeks in the prospective comparison. The fit uses 2021-24 only; nothing is tuned on 2026.
- It does not touch drives/game, the 0-40 s clock, first-down-by-penalty or half-the-distance.
- It does not close the calibration-transfer gate. The sim prices no ticket.

## Closing

Append to `logs/agent_sessions.md` (`git add -f`), timestamp from `date -u`. Separate what each
command RETURNED from what it MEANS. List what was NOT DONE and what is UNVERIFIED.
