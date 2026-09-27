# Phase 5V verification — Cowork, 2026-09-27

Branch `eng/5v` @ `063470b` (branched from the repair commit b6ae537; main's decision doc and log have not
moved since, so the merge is clean). Verified in a Linux worktree; numbers recomputed here unless marked "read".

## Item 0 (D158) — accepted
`build_all` now writes `int_ez.parquet`; the loader raises `FileNotFoundError` if `int_spot` or `int_ez`
is missing (read in the diff; `test_missing_int_ez_raises` passes and would fail on the 5U loader, which never
raised). Player-OFF hash `afdb11999d5b12bf` for every new fingerprint; `test_engine_5m` + `test_engine_5v`
pass at head (4/4). The suite's third red ("transient" hash) is resolved at head: the fixture carries the head
fingerprint `559875bb4f8172ff`. Note the fingerprint also moved between items 2 and 3 with no engine change
(only a new script in `nfl/sim/`): the fingerprint hashes more than the engine.

## Item 1 (D159) — the plays target is right; the drives target does not reproduce
- The event list is right (pass incl. sacks, run, kneel, spike; two-point tries excluded because the engine
  counts them in the PAT branch). Plays/game **125.78** reproduces exactly (pass 71.67, run 52.35, kneel 1.52,
  spike 0.24). My pre-registered 126.3 FAILED because I counted two-point tries: accepted. K1 gap +5.1.
- **Drives/game does not reproduce.** The committed `compute_k1_actuals()` prints **21.74** on Linux with
  PBP files whose sha256 prefixes match the Mac's (a9741a72, 6809039b, 81984d68, 35d5a2e2). D159 reports 21.92.
  Either the report typed a number the code does not produce, or the code gives different answers on the two
  machines (pandas NaN-group handling is the first suspect). Also unverified: whether the sim's `drives`
  counter excludes zero-play drives the way the target now does. -> 5W item 0.

## Item 2 (D160) — the log exists but does not do what the order asked
- One row per ENGINE STEP in which `ev_clock_used` rose, with sim, quarter, clock before, elapsed and score
  difference. **No play class, no clock-stopped flag, no timeouts** — the fields the decomposition needed.
- The step filter uses `alive` as reassigned mid-step, which excludes sims that kneeled or spiked (and games
  that ended) in that step, so those snaps' clock is dropped.
- It does not reconcile. On 3 games x 200 sims (Linux), the per-sim sum of logged regulation clock ranges
  **3,450.7 to 3,697.3 s** (means 3,569-3,574) — it should be 3,600 for every non-OT sim. Runoff past the end
  of a quarter is counted (sums above 3,600) and some snaps are missed (sums below).
- **The order's test was relaxed.** `test_play_log_clock_sum`'s docstring still says "equals 3600 s within
  1 s"; the body asserts only >= 95% of `ev_clock_used` and `return`s after the first game. That is the gate
  the order said to let fail.

## Item 3 (D161) — not an answer to the question asked
- Real side: elapsed between consecutive pass/run/kneel/spike snaps in a half, so it silently includes the
  time of every kickoff, punt and field goal in between and drops the first snap of each half (123.7 of the
  125.8 snaps). Sim side: clock per engine step (above). The two populations are defined differently.
- With total clock fixed at ~3,600 s, "more snaps" and "fewer seconds per snap" are the same fact stated
  twice; the rate-vs-mix split at the total level is arithmetic, not a finding. The order's decomposition was
  BY PLAY CLASS; the log has no class, so prediction (2) was "partially scored" and prediction (3) — the null
  that both sides reconcile — FAILED and was not fixed first, as the order required.
- D161's conclusion ("+1.8 extra drives from short fields") is contradicted by 5S and 5U: both cut
  short-field starts and neither moved plays (130.9 before and after).
- `phase5v_clock_decomp.parquet` is **29 MB** of raw sim rows committed to a public repo. It stays off
  main (untracked and ignored at merge); summaries only from now on.

## What stands
Items 0 and 1 are good work and go to main. The clock question is still open, now with a correct plays
target (+5.1) and a log that needs one more pass. 5W: reconcile the drives target across machines, rebuild the
log per event with classes and exact quarter reconciliation, then decompose by class against a real side that
counts every play type.

## Cowork measurements for the next order (5W)
Two hypotheses tested here and disconfirmed: the engine's typed clock after scores/turnovers (mean 8.28 s)
matches real (8.5 s over 6.77 such plays a game); the pace multiplier averages 1.005 across the K1 games.
The lead: real plays fall with the final margin (2022-24: 127.3 / 124.5 / 124.2 / 121.6 for margins 0-7 /
8-14 / 15-21 / 22+), the sim's do not (131.6 / 129.6 / 130.0 / 131.3 by its own margin, 40 games x 200 sims).
By real margin the K1 gap is +3.5 / +5.9 / +6.2 / +8.4; by season +3.9 (2021) to +6.9 (2024). The sim does
not burn clock the way a leading team does, on top of a ~+3.5 base offset in close games.
