# Phase 5H work order — measure before touching the engine again

Date: 2026-09-19
Repo: jwallace115/mlb-model. Scope: nfl/ only.
Read first: D93 and D94 in `research/nfl_sim/NFL_SIM_DECISION_v1.md`.

## What this phase is

DIAGNOSTICS ONLY. Three phases ordered engine fixes for the same three reds from
hypotheses nobody had measured, and all three failed (D93). D94 then showed two of the
three targets were never measured like-for-like with what the sim test measures. This
phase produces numbers. It fixes nothing.

## HARD RULES

1. **`main`'s engine does not change.** Not `nfl/sim/engine.py`, `anchor.py`,
   `params_v1.json`, `tables.py`, nor anything in `nfl/data/sim/tables/`. The Week 2 board
   runs on `main` against `fit_5d2`; its fingerprint must stay `d929ad258504b275`.
2. **No test, target, tolerance, spec threshold or sample filter is edited.** Anywhere.
   If you think one is wrong, write the case in the decision entry. Do not edit it.
3. Instrumentation that needs an engine edit happens ONLY on branch `diag/5h` in a
   separate worktree (setup below). That branch is never merged.
4. RUNTIME POLICY: never reduce N, subsample, shorten a sweep, skip a test or kill a run to
   finish sooner. Running independent replicates in parallel processes is fine (results
   are identical). Do not budget or narrate how long your own session will take.
5. Prefix EVERY git command with `GIT_OPTIONAL_LOCKS=0`. Push with
   `git pull --rebase --autostash && git push`.
6. 3 items. Commit AND push each before starting the next. Each writes its `### DNN` entry
   in `research/nfl_sim/NFL_SIM_DECISION_v1.md` on `main` in the same commit as its report.
7. A diff is not evidence that code runs. Evidence is pasted execution output.

## Before item 1 — baseline

In `~/mlb-model` on `main`:
- `python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"`
  must print `d929ad258504b275`. If it does not, STOP and report.
- Full `nfl/sim/tests` suite. Expected: 188 collected, 185 passed, 3 failed — go rate
  (0.210), offense penalties (6.20), tied-drive expiry (0.111). `test_first_downs_by_penalty`
  may read differently on this Mac than on Linux; report what you get. Any other red: STOP.

---

## Item 1 — sim-side noise floor of the four metrics (on `main`, no engine edits)

New script `nfl/sim/run_metric_noise_5h.py`. Metrics: 4th-down go rate (5A-3 construction:
50 games of 2023, N=500, drive_log=True), offense and defense penalties/game and first
downs by penalty/team (5A-4: 80 games of 2023, N=500), tied-drive expiry (5A-9: the 12
`SAMPLE_GAMES`, N=500, drives starting Q4 <= 300 s, the test's exact `reached`/`expired`
expressions).

Do, in this order:
1. **Replicate 0 must reproduce pytest.** Rebuild each test's sample with the test's own
   seeds and print the metric. It must equal the value pytest prints on this machine to the
   printed precision. If it does not, the script is measuring something else — STOP and fix
   the script, not the test.
2. **Measure one replicate's wall time per metric and print it BEFORE launching the rest.**
   Cowork's estimate (unverified): ~1 min go rate, ~2 min penalties, <1 min tied-drive on
   this Mac; ~70 replicate-runs total, under 2 h sequential. Report the measured figure.
3. **Seed noise:** same games, 10 seed salts (`stable_seed((game_id, 42, salt))`-style,
   salts 1-10; salt 0 = the test's own seed).
4. **Sample noise:** 10 different game samples (`np.random.default_rng(k)`, k = 0-9; note
   the tests use 42) at the test's sample size, test seeds. For go rate also compute the
   REAL go rate in each sample's same games (definition in
   `nfl/sim/tests/derive_engine_targets.py::derive_fourth_down_go_rate`).
5. For tied-drive expiry print the drive COUNT behind every rate.
6. Write every replicate as a row to
   `research/nfl_sim/phase5h_metric_noise_rows.parquet`; report
   `research/nfl_sim/phase5h_metric_noise.md` with mean / SD / min / max per metric per
   noise source, built FROM the parquet.

**Pre-registered predictions (Cowork, written before any run). State for each whether it
held. If it did not, say so plainly and tune nothing.**
- P1: go-rate seed-salt SD < 0.002; go-rate game-sample SD between 0.003 and 0.008.
- P2: tied-drive expiry seed-salt SD between 0.015 and 0.030.
- P3: offense penalties/game seed-salt SD < 0.05 (so the +0.69 red is > 10 SD — real).
- P4: first downs by penalty/team seed-salt SD between 0.005 and 0.03 (so 0.302 vs a 0.300
  spec is inside the noise).

**Null control:** `engine_fingerprint()` is `d929ad258504b275` before and after, and
`git status --short nfl/sim/engine.py nfl/sim/anchor.py nfl/sim/params_v1.json nfl/sim/tables.py nfl/data/sim/tables`
prints nothing. Paste both.

Decision entry: D95 (measurements only; no recommendation to change a test).

---

## Worktree setup for items 2 and 3

```
cd ~/mlb-model
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-diag -b diag/5h
cd ~/mlb-model-diag
# gitignored inputs are not in a fresh worktree: link them, do not copy
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.engine import simulate_game; print(simulate_game('KC','BUF',2023,6,n_sims=50,seed=1).shape)"
```
If the one-game run fails on a missing input, link that input the same way and say which.
All instrumentation commits go to `diag/5h` (`git push -u origin diag/5h`). Reports and
decision entries go to `main` in `~/mlb-model` and cite the `diag/5h` commit hash that
generated them. Outputs of sims run in the worktree stay in the worktree.

---

## Item 2 — like-for-like: where the go-rate excess and the expiring drives come from

On `diag/5h`, add logging behind a flag (default OFF):
- per 4th-down decision: game_id, sim_id, qtr, clock, ydstogo, yardline_100, offence score
  differential, decision (go / punt / fg), the table cell key used;
- per 3rd-down snap: ydstogo, yards gained, converted or not;
- per snap of drives that start in Q4 with <= 300 s, offence tied or trailing by <= 8:
  clock before and after, yardline before and after, play type, outcome type, timeout
  called (by whom), spike, kneel, fgs_state.

**Byte-identity first:** flag ON vs OFF, 3 games x N=2,000, identical seeds — every
existing output column identical (precedent: `test_drive_log_byte_identity_5a3`). Paste it.
If it is not identical, the instrumentation changed the sim; fix that before measuring.

Run all 1,087 regular-season games 2021-24 at N=500 with the flag ON (measure one game's
wall time first and report the projected total before launching). Then, against real PBP
for the SAME games:

A. **Go rate decomposition.** Sim vs real share of 4th-down decisions by ydstogo bucket x
   field zone x score state (the table's own buckets). Then standardise both ways:
   real cell rates applied to the sim's state mix, and sim cell rates applied to the real
   mix. Report how much of the sim-minus-real gap is STATE MIX and how much is WITHIN-CELL.
B. **Upstream of the mix.** Sim vs real distribution of 3rd-down ydstogo, and of
   (yards gained minus ydstogo) on failed 3rd downs — i.e. where 4th-and-short comes from.
C. **Tied-drive expiry, split.** For sim drives tied at the start, starting Q4 <= 300 s,
   that the 5A-9 test counts as reached-and-expired: how many are (i) zero-play drives,
   (ii) reached the 35 only on their FINAL play, (iii) took a snap at/inside the 35 and
   still expired. Report the sim's STRICT rate (iii only, over drives with a snap inside
   the 35) next to real 0/57, and the BROAD rate next to real 2/64 (D94).
D. **Two-minute drill.** Same drive population plus trailing by 1-8: sim vs real plays per
   drive, seconds per play by outcome type, timeouts used per drive, pass share, spikes,
   and drive result mix.

Pre-registration: write your own prediction for A (what share is state mix) and C (which
of i/ii/iii dominates) in the report BEFORE running, then say whether it held.
Cowork's: A — state mix is more than half the gap; C — (i)+(ii) are more than half of the
sim's expiries. If either fails, say so.

Null control: the go-rate, penalty and expiry values computed from the instrumented run on
the three tests' own samples equal the item 1 replicate-0 values.

Report: `research/nfl_sim/phase5h_like_for_like.md` (+ row-level parquet beside it, tables
built from the parquet). Decision entry: D96 — findings and the measured cause(s). NO fix.

---

## Item 3 — D89 on this Mac, and the penalty breakdown owed from 5G

On `diag/5h` only: re-apply D89 exactly as in commit 27e900bb6 (`tables.py` denominator
`len(scrim) + len(accepted_no_play)`; rebuild `scalars.json`; `p_no_play_penalty` must come
out 0.06716294458229942 — if it does not, STOP).

Using the item 1 script, 10 seed salts on the 5A-4 sample, with and without D89:
offense penalties/game, defense penalties/game, first downs by penalty/team, plus go rate
and tied-drive expiry on their own samples (D89's null controls — Cowork measured them
moving 0.0123 -> 0.011 and 0.111 -> 0.108 on Linux, i.e. not at all).

Then the breakdown the 5G order asked for and did not get: sim vs real penalties per game
by penalty type, and by game context (quarter, score state, down), from real PBP and from
the sim's penalty draws. Where does the sim's mix differ? First downs by penalty: real
no-play vs scrimmage-play split (D89 states 1.251 + 0.477 per team — reproduce those two
numbers from PBP and paste the derivation).

Report: `research/nfl_sim/phase5h_penalties.md`. Decision entry: D97.

---

## Closing

End state that must be TRUE and pasted, in `~/mlb-model` on `main`:
`engine_fingerprint()` = `d929ad258504b275`; `_check_calibration_stamp()` = `(True, [])`;
the `git status --short` line from item 1's null control prints nothing.

Append a session-log entry to `logs/agent_sessions.md` (timestamp from `date -u`) that
separates what each command RETURNED from what it MEANS, and lists what was NOT done and
what remains UNVERIFIED.

## What this work order does NOT do

- It fixes nothing and re-fits nothing. It does not re-land D89 on `main`.
- It does not change any test. Whether the go-rate and tied-drive tests get matched targets
  and noise-based tolerances is Jeff's decision after D95/D96, not an agent's.
- It does not touch the calibration-transfer gate (totals Brier 0.24190 -> 0.24560 under
  calibration). That still decides whether the sim ever prices a ticket.
- The board-level refuse-to-rank trace is still owed; it gets captured the next time the
  engine legitimately changes on `main`, before that change's re-fit.
