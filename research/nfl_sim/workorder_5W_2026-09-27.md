# Work order 5W — find where the sim's extra five plays come from (2026-09-27)

Written by Cowork after verifying 5V (`phase5v_verification_2026-09-27.md`, D162). Gate: D162 on main.

## What Cowork measured before writing this (so 5W does not chase the wrong things)
- K1 plays gap is +5.1 (sim 130.90 vs real 125.78, like-for-like, D159).
- **Ruled out:** the typed ~8 s clock after scores/turnovers (`max(16u, 3)`, mean 8.28 s) matches real
  (8.5 s; TD 8.3, INT 9.5, fumble 9.3; 6.77 such plays a game). The pace multiplier the engine applies
  (team pace / league pace) averages 1.005 over the 1,087 K1 games — it slows the sim slightly, not speeds it.
  On 60 early-2021 games the sim's pass/run/incompletion counts are within ~1 of real.
- **The lead:** real plays fall with the final margin; the sim's do not. Real 2022-24: 127.3 plays (margin
  0-7), 124.5 (8-14), 124.2 (15-21), **121.6 (22+)**. Sim, 40 random 2022-24 games x 200 sims, bucketed by the
  sim's own margin: 131.6, 129.6, 130.0, **131.3**. From the K1 rows by the real margin the gap is +3.5 (0-7),
  +5.9, +6.2, **+8.4** (22+); by season +3.9 (2021) rising to **+6.9 (2024)**. The sim does not burn clock the
  way a leading team does, and there is a ~+3.5 base offset even in close games.

Pre-check (Cowork): runtime — item 0 is two PBP passes (seconds) plus one K1-rows recompute; items 1-2 are the
D144 sample (first 200 K1 games, N=100, ~2-4 min on the Mac) plus a PBP pass. No re-fit. Credits: zero. New
files: `nfl/sim/run_clock_state_5w.py`, `nfl/sim/tests/test_engine_5w.py`, `research/nfl_sim/phase5w_*.md`
and SMALL summary parquets only. **No raw per-snap or per-sim file may be committed** (5V committed 29 MB);
anything over 2 MB stays local.

```
Branch eng/5w from origin/main in a worktree; main untouched until Cowork verifies. Commit AND push each
item before the next; every decision (D163-D165) goes into research/nfl_sim/NFL_SIM_DECISION_v1.md in the same
commit as its code. Gate first: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md | grep -c "^### D162"`
must print 1; if 0, STOP. Re-record the player-OFF hash fixture whenever the fingerprint moves and print it.
Never weaken a test the order specifies; if it fails, report it failing. Run the FULL suite after item 2 and
report the exit code and every red by name. Commit no file larger than 2 MB.

Item 0 (D163) — make the drives target reproducible.
  `compute_k1_actuals()` prints drives 21.74 on Linux (Cowork) with PBP inputs whose sha256 prefixes match the
  Mac's; D159 reported 21.92. Run it on the Mac and print the number with pandas/numpy versions. Find the
  cause (first suspect: NaN `fixed_drive` groups and pandas' groupby dropna default) and make the function
  explicit so both machines give one number; add a test that pins the derivation's row counts, not the value.
  Also state the sim-side definition of K1 `drives` (the engine counter) and whether it counts zero-play
  drives; if it does, make the K1 sim value count plays >= 1 drives from the drive log so both sides match.

Item 1 (D164) — a play log that reconciles. LOG-ONLY and drive_log-gated; the player-OFF hash MUST equal
  afdb11999d5b12bf. Replace 5V's per-step log with one row per clock-consuming EVENT, written at each site
  that increments `ev_clock_used` (engine.py ~1344, 1357, 1612, 1644, 1686, 2554, 2561, 2818, 2825 on 5V) with:
  sim_id, quarter, clock before, elapsed CAPPED at the time left in the quarter, event class (the clock-table
  outcome_type drawn: run / complete_inbounds / incomplete / first_down; or drive_ending, kneel, spike, eoh, fgs,
  timeout-stopped), the offence's score_state and clock_period used for the draw, and the pace multiplier
  applied. Fix 5V's `alive` filter so kneel/spike/game-ending snaps are not dropped.
  TEST (as ordered in 5V, not weakened): for every non-OT sim in 3 games x 200 sims, the logged elapsed in
  EACH regulation quarter sums to 900 s within 1 s. It must FAIL on 5V's log (3,450-3,697 s per game).

Item 2 (D165) — decompose by game state. DIAGNOSIS ONLY, no engine change.
  Sim: the D144 sample with the new log. Real: PBP 2021-24 REG, per scrimmage snap the time to the next
  scrimmage snap (the clock table's own definition), same classes, same score_state and clock_period keys,
  capped at the quarter end. Report, sim vs real: snaps per game and mean elapsed per class, by the offence's
  score_state, by the game's final margin bucket (0-7, 8-14, 15-21, 22+), and by season (2024 separately —
  the dynamic kickoff changed return time). Report the run share and mean elapsed for offences leading 9+ and
  trailing 9+.
  PRE-REGISTER before looking: (1) the sim's plays per game do not fall with its own final margin (within 1.5
  plays across buckets) while real plays fall >= 4 from 0-7 to 22+ — the sim-real gap in 22+ games is >= 2x the
  gap in 0-7 games; (2) for offences leading 9+, the sim's mean elapsed per snap is >= 2 s shorter than real OR
  its run share is >= 5 points below real (state which, or both); (3) null: both sides reconcile to 900 s per
  regulation quarter within 1 s. If (3) fails, fix the log or the real derivation before reporting (1)-(2).
  If a prediction fails, say so plainly; no tuning.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and
UNVERIFIED. Append the session log to logs/agent_sessions.md (git add -f).
```
