# Work order 6B — fix 6A's clock-table defects, the timeout frequency and the own-1 pile-up; one re-fit (2026-09-28)

Written by Cowork after verifying 6A (`phase6a_verification_2026-09-28.md`, D185). 6A is NOT merged; 6B builds on it.
Gate: eng/6a @ fc3724115 and the verification note on main.

Pre-check (Cowork): runtime — items 0-2 are table rebuilds (seconds) + the 200-game phase5z sample at N=100 with logs
(~3-5 min each on the Mac) + the six late-game test files (~15 min); item 3 is one fit at N=5000 + cal + K1 + K4 +
boards + full suite (~2.5 h on the Mac, as 5Y/6A). Credits: zero. Files: `nfl/sim/tables.py`, `nfl/sim/engine.py`,
`nfl/data/sim/tables/clock_runoff.parquet` (rebuilt by the committed builder), `nfl/sim/run_engine_diag_6b.py` (new),
`nfl/sim/tests/test_engine_6b.py` (new), `nfl/sim/tests/test_engine_5z.py` + `test_engine_6a.py` (see item 0),
`research/nfl_sim/phase6b_*.md` + summary parquets < 2 MB. Real-side numbers below were measured by Cowork; the scripts
are in `research/nfl_sim/phase6a_cowork/` — reuse them, do not re-derive differently.

```
Work order 6B (research/nfl_sim/workorder_6B_2026-09-28.md). Branch eng/6b from origin/eng/6a (NOT from main) in a
worktree; main untouched until Cowork verifies. Gates: `git rev-parse --short=9 origin/eng/6a` must print fc3724115,
and `git show origin/main:research/nfl_sim/phase6a_verification_2026-09-28.md | grep -c "^### D185"` must print 1;
if either fails, STOP. FIRST COMMIT: append the D185 block from that file VERBATIM at the end of
research/nfl_sim/NFL_SIM_DECISION_v1.md (after D184). Then commit AND push each item before the next; each decision
(D186-D189) is appended at the end in the same commit as its code. Session log to logs/_log_6b.txt (git add -f).
Never weaken a test. Commit no file larger than 2 MB. Re-record the player-OFF hash fixture whenever the fingerprint
moves and print it. Sample = the 200 game_ids in research/nfl_sim/phase5z_sample.txt, N=100, seed as 5Z.

HARD RULES: (1) a table the order asks for is the deliverable; if it cannot be produced the decision reads "ITEM NOT
DONE: <exact blocker>" and you stop — there is no time limit. (2) Every claim about what the code does cites
file:line. (3) Every pre-registration and every null gets a line "HELD" or "FAILED" with the number, in the decision.

Item 0 (D186) — the clock-table defects Cowork found in 6A. TABLE + ENGINE + TESTS.
  (a) Late cells. 6A pushed 11 late-game cells under MIN_CELL; they fall back to the ALL-PERIOD parent (~38 s vs
      ~18 s; e.g. run/tied/Q4_late 18.3 -> 38.2). New fallback order everywhere a clock cell is looked up (pass, rush,
      kneel, timeout_followed): (ot, state, period) -> (ot, ALL STATES POOLED, same period) [new builder rows] ->
      (ot, p_state, all) -> legacy. Report the 11 cells: 5Z mean, 6A fallback mean, 6B value.
  (b) timeout_followed = RUNNING-CLOCK plays followed by a team timeout only (the engine routes only those:
      engine.py `_to_changed`). A play whose clock was already stopped (incomplete, out of bounds, spike) keeps its
      own class even if a timeout follows. Real running-clock mean 21.7 s (6A table: 18.1 with stopped plays mixed in).
  (c) Kneels, as 6A item 1 specified: include the kneel that ends the half/game, elapsed = time to the end of the
      half (capped). A kneel followed by a defence timeout draws the timeout_followed cell (fallbacks as in (a)), not
      `incomplete`. Like-for-like real: all kneels 25.9 s (final 22.1, non-final 32.4) — kneel_real.py.
  (d) Log label `timeout_stopped` (the _eoh_runoff path) -> `eoh_runoff`. Log only; it mislabelled 5Z's class table.
  (e) Tests. test_engine_5z::test_player_off_hash_unchanged asserts the fixture's 5Z ENTRY
      (hashes["62320588f80d0593"] == "80848eefb5a45062") — its meaning, which the current form can never pass again.
      test_engine_6a::test_kneel compares the sim's mean over ALL kneels (final ones capped) on its test game with the
      real like-for-like mean computed IN THE TEST from PBP 2021-24 REG, tolerance 3.0 s. Both are stated in D186 as
      test changes with the reason; nothing else in either file changes.
  PRE-REGISTER: sample plays within 127.02 +- 0.8 (6A: 127.02); the 11 cells within 2 s of their 5Z means; NULL:
  normal-period run / complete / first-down cells move < 0.3 s vs 6A. Run test_engine_5a, 5a7, 5a8, 5a9, 5a10, 5a11,
  5z, 6a after the item and report each: at least three of the five 6A late-game reds (tie rate, |m|=3, P(tie|OT),
  off TO, tied FG late) PASS again.

Item 1 (D187) — timeout frequency. DIAGNOSIS THEN FIX.
  Real (Cowork, PBP 2021-24): 7.7 team timeouts a game (H1 off 2.28 / def 1.47, H2 off 1.49 / def 2.35); 4.0 a game
  follow a running-clock play (Q2 last 2:00 def 0.55 / off 0.74; Q4 last 2:00 def 0.43 / off 0.22; Q4 before 2:00 def
  0.91 / off 0.30; rest of the game def 0.25 / off 0.60). Sim (6A, sample): 3.4 a game (off 1.37, def 2.02); 2.8 after
  running-clock plays, almost all in the last 2-3 minutes (normal period 0.06).
  Deliver the same table sim vs real (half x side x period x what preceded: running-clock play / stopped-clock play /
  other), then find why the measured policy (timeout_policy.parquet via to_lookup) produces under half the real rate:
  which keys the engine consults, the clock_running condition, the periods where it is never asked, to_rem. Fix the
  APPLICATION, not the measured values. Do not add timeouts the data does not show.
  PRE-REGISTER: sim timeouts a game >= 5.5; running-clock timeouts by period within 25% of real; off TO/game within
  0.4 of 1.78 (test 5a7); sample plays RISE 0.3-1.0 vs item 0 (defence timeouts before the two-minute mark save
  ~20 s each). NULL: go_rate and fg_att on the sample move < 0.01 / 0.05 a game.

Item 2 (D188) — the own-1 pile-up behind the safety excess. DIAGNOSIS THEN FIX.
  Sim takes 1.31 snaps a game at own 1-2 (yl 98-100) vs 0.385 real; 90-94 and 95-97 are near real (2.04 vs 2.26,
  0.91 vs 0.72). Sim safeties = zone snaps x the measured rates exactly (0.072 = 2.04x0.0020 + 0.91x0.0166 +
  1.31x0.0406). Deliver: for every snap at 98-100, what put the ball there — sack, rush loss, pass loss, offensive
  penalty, drive start (punt / kickoff / turnover / other) — and whether a clip at 99 fired; sim (sample) vs real
  (PBP: the previous play of each real snap at yardline_100 >= 98). Candidate sites (read, not measured): offensive
  penalties add full yards clipped at 99 (engine.py ~1960, ~2014 — the rule is half the distance to the goal); losses
  clipped at 99 (sacks ~2359, completions ~2337, rushes ~2705). Fix what the table shows. For losses: when the
  pre-snap roll did not fire, a loss that would reach the goal line is redrawn from the same distribution
  conditioned on staying in the field of play (at most 20 draws, then clip) — real losses that cross the goal line
  ARE the safeties the per-snap rate already counts. Do NOT enable the zeroed sack/run safety masks (D178/D180).
  PRE-REGISTER: 98-100 snaps 1.31 -> 0.30-0.50 a game; 90-94 and 95-97 move < 15%; safeties 0.069 -> 0.028-0.040
  (the engine models zone snaps only; with real zone snaps it would make 0.032; real total 0.041 includes 10 of 45
  from outside the 10 — report the gap, do not tune to it).
  Test (test_engine_6b.py): 98-100 snaps per game on 3 games x 200 sims <= 0.6 (fails on 6A: 1.31); an offensive
  10-yard penalty from yl 96 leaves the ball at yl 98 (half the distance), not 99. Both must fail on eng/6a — show it.

Item 3 (D189) — ONE re-fit `fit_6b` on the item-2 engine: cal maps, K1 (table + rows), K4, W2/W3 boards with
  team_volume, full suite. Commit the calibration map BEFORE running K1: the K1 header must NOT say "-dirty" (if it
  does, fix and re-run K1 before reporting). Also re-run Cowork's points-per-drive split (phase6a_cowork/analyze.py
  method) on the sample with the new engine and report START MIX / EFFICIENCY / interaction.
  PRE-REGISTER: K1 plays 125.8 +- 1.5; safeties/game 0.028-0.040; the five 6A late-game reds PASS; go_rate / off_pen
  / def_pen / fg_att PASS (nulls); fd_pen still FAILS (known, next order); EFFICIENCY is still the larger term of the
  points split. Report pts/team and drives with the change from 6A (21.17 / 22.945). Name every red and give the
  exit code.

Run test_engine_5m, 5w, 5y, 5z, 6a, 6b after items 0-2. Every item's report separates what the command RETURNED from
what it MEANS and ends with NOT DONE and UNVERIFIED.
```
