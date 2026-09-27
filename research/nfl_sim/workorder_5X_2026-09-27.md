# Work order 5X — fix the two measured clock defects, re-measure on a stratified sample, one re-fit (2026-09-27)

Written by Cowork after verifying 5W (`phase5w_verification_2026-09-27.md`, D166). Gate: D166 on main.

Pre-check (Cowork): runtime — items 0-1 are a table rebuild (seconds) plus the 3-game log test; item 2 is 200
games x N=100 with the play log (~3 min on the Mac) plus a PBP pass; item 3 is one fit at N=5000 + cal + K1 +
boards + suite (~2 h on the Mac, as 5U). Credits: zero. Files: `nfl/sim/engine.py`, `nfl/sim/tables.py`,
`nfl/data/sim/tables/clock_runoff.parquet` (rebuilt by the committed builder), `nfl/sim/run_clock_class_5x.py`,
`nfl/sim/tests/test_engine_5x.py`, `research/nfl_sim/phase5x_*.md` + summary parquets under 2 MB.

```
Branch eng/5x from origin/main in a worktree; main untouched until Cowork verifies. Commit AND push each item
before the next; each decision (D167-D170) goes into research/nfl_sim/NFL_SIM_DECISION_v1.md, APPENDED AT THE END
of the file, in the same commit as its code. Gate first: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md
| grep -c "^### D166"` must print 1; if 0, STOP. Never weaken a test; if it fails, report it failing. Commit no
file larger than 2 MB. Re-record the player-OFF hash fixture whenever the fingerprint moves and print it.

Item 0 (D167) — quarter ends do not carry clock. ENGINE CHANGE.
  engine.py ~1473 adds 900 to a negative clock at a quarter end ("carry over negative clock"), so each quarter
  after an overshoot starts short: Cowork measured Q2 -19.9 s, Q3 -9.8 s, Q4 -19.8 s per game (D144 sample) —
  ~50 s a game real games do not lose (a real quarter restarts at 15:00; the runoff table's real elapsed for a
  last-seconds snap is already capped by the time left). Start every new quarter at exactly 900. Check OT uses
  its own period length and is unaffected. The 5W test `test_play_log_quarter_sums` (each regulation quarter
  sums to 900 s within 1 s on every non-OT sim) must now PASS without any change to the test or the log.
  PRE-REGISTER: on the D144 sample (first 200 K1 games, N=100) sim plays/game RISE by 1.0-2.5.

Item 1 (D168) — split the first-down runoff by play type. TABLE + ENGINE CHANGE.
  `build_clock_table` pools rush and pass first downs into one `first_down` outcome type. Real rushing first
  downs run to the next snap in 37.0 s vs 32.7 s for passing first downs (first 100 K1 games; 42.9 s when leading
  9+), because pass first downs go out of bounds far more often (27% vs 12%). Add `first_down_rush` and
  `first_down_pass` outcome types (same score_state x clock_period cells, same MIN_CELL fallbacks, fallback to the
  pooled cell only when a split cell is thin — report how many cells fall back). The rush site draws
  `first_down_rush`, the pass site `first_down_pass`. Rebuild with the committed builder.
  PRE-REGISTER: sim rushing-first-down mean elapsed within 1.0 s of real (was -4.4); sim plays/game FALL by
  1.0-2.5 vs item 0; items 0+1 together move plays by less than 1.0 net (they roughly cancel).

Item 2 (D169) — class-by-class re-measurement on a SEASON-STRATIFIED sample. DIAGNOSIS ONLY.
  The D144 sample is 2021 weeks 1-13, where the K1 plays gap is smallest (+3.9 vs +6.9 in 2024). Use 50 games per
  season 2021-24 (fixed seed, list the game_ids in the report), N=100, with the play log. Real side from PBP with
  IDENTICAL classes: run, first_down_rush, complete_inbounds, first_down_pass, incomplete, sack, kneel, spike,
  drive_ending (TD/INT/fumble-lost), and TIMEOUT-FOLLOWED plays as their own class on BOTH sides (real: the next
  PBP row is a timeout; sim: the timeout_stopped / stop_code path) — elapsed = time to the next scrimmage snap,
  capped at the quarter end. Report per class: snaps/game and mean elapsed, sim vs real, overall, by season and by
  the offence's score state; then the per-game clock difference split into mix (count) and rate (seconds) by
  class. PRE-REGISTER: (1) no class is off by more than 1.5 s except where named in the report as the residual;
  (2) the remaining plays gap is largest in 2024 (dynamic-kickoff season) — report the kickoff-to-next-snap time
  sim vs real by season; (3) null: regulation clock reconciles to 900 s per quarter on both sides.

Item 3 (D170) — ONE re-fit `fit_5x` on the item-1 engine: cal maps, K1 (table + rows), K4, W2/W3 boards with
  team_volume, full suite. PRE-REGISTER: K1 plays 130.9 +- 1.0 (the two fixes roughly cancel); pts/team within 0.5
  of 22.04; go_rate/off_pen/def_pen/fg_att PASS (nulls); fd_pen and tied expiry still FAIL (known); the by-margin
  gap table (0-7 / 8-14 / 15-21 / 22+) reported against 5W's +3.9 / +4.0 / +5.0 / +8.4.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
Append the session log to logs/agent_sessions.md (git add -f).
```
