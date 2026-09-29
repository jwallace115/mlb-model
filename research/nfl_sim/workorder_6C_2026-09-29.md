# Work order 6C — punts clipped at the 1, a measured timeout policy, kneel timing; one re-fit (2026-09-29)

Written by Cowork after verifying 6B (`phase6b_verification_2026-09-29.md`, D194). 6A and 6B are NOT merged; 6C
builds on eng/6b. Gate: eng/6b @ e432be7d6 and the verification note on main.

Pre-check (Cowork): runtime — items 0-2 are PBP table builds (seconds-minutes) + the 200-game phase5z sample at N=100
(~5 min each) + the late-game test files (~15 min); item 3 is one fit + cal + K1 + K4 + boards + full suite (~3 h on
the Mac, as 6B took). Credits: zero. Files: `nfl/sim/tables.py`, `nfl/sim/engine.py`, `nfl/data/sim/tables/*.parquet`
(rebuilt by committed builders), `nfl/sim/tests/test_engine_6c.py` (new), `nfl/sim/tests/test_engine_6b.py`,
`nfl/sim/tests/test_dead_tables_5a5.py` (item 3, selection only), `research/nfl_sim/phase6c_*.md` + parquets < 2 MB.

```
Work order 6C (research/nfl_sim/workorder_6C_2026-09-29.md). Branch eng/6c from origin/eng/6b (NOT main) in a
worktree. Gates: `git rev-parse --short=9 origin/eng/6b` must print e432be7d6, and `git show
origin/main:research/nfl_sim/phase6b_verification_2026-09-29.md | grep -c "^### D194"` must print 1 (run `git fetch
origin` first); if either fails, STOP and print both outputs. FIRST COMMIT: append the D194 block from that file
VERBATIM at the end of research/nfl_sim/NFL_SIM_DECISION_v1.md. Then items 0-3, commit AND push each before the next;
decisions D195-D198 appended in the same commit as their code. Session log appended to logs/_log_6c.txt (git add -f),
timestamps from `date -u`. Never weaken a test. No file > 2 MB. Re-record the player-OFF hash whenever the fingerprint
moves. Sample = research/nfl_sim/phase5z_sample.txt, N=100.

HARD RULES: a table the order asks for is the deliverable. "ITEM NOT DONE" is allowed ONLY for an external blocker
(missing data file, tool/API failure) named exactly — "scope", "time", "multi-hour" and "depends on another item" are
not blockers (items 0, 1 and 2 are independent). Every claim about the code cites file:line. Every pre-registration
and null gets HELD/FAILED with the number. A test must exercise the engine (simulate_game or the engine function that
owns the logic) — a test that re-implements the formula is not a test — and each new test must FAIL on eng/6b: run
it there and paste the failure.

Item 0 (D195) — punts clipped at the 1, and the penalty rule. TABLE + ENGINE + TESTS.
  Cowork (D194): 74% of the sim's 0.83 own-1/2 drive starts a game follow punts from the opponent's 40-50; the net
  draw from the pooled `midfield` zone carries past the goal line and engine.py:1809 clips it to 99. Real: own-1/2
  starts 0.255 a game; punts from the opponent's 35-50 are touchbacks 14-26% of the time.
  (a) Build a punt landing table from PBP 2021-24 REG: by punt LOS in 5-yard buckets (yardline_100), the receiving
      team's next snap yardline (quantiles), touchbacks included at their spot; blocked punts, return TDs and muffs
      lost excluded (the engine handles those elsewhere — cite where). The engine draws the landing spot from it
      instead of LOS - net clipped at 99. Report sim vs real: drive starts per game at own 1-2, 3-10, 11-20 after
      punts, and touchback rate by LOS bucket.
  (b) Half the distance to the goal applies whenever the offensive penalty's yards exceed half the distance
      (engine.py:1963 currently only when the full yards would pass the 1). D192's half-distance on sack/rush/pass
      LOSSES stays, described in D195 as an approximation ("a loss that did not produce the pre-rolled safety stays
      in the field"), not a rule.
  (c) Replace test_engine_6b::test_offensive_penalty_half_distance with an engine test (own 15, 10-yard offensive
      penalty -> own 7.5; own 4 -> own 2). Keep test_98_100_snaps as is.
  PRE-REGISTER: own-1/2 drive starts 0.83 -> 0.20-0.35 a game; 98-100 snaps (sample) 1.31 -> 0.35-0.55;
  sample safeties 0.069 -> 0.028-0.040; test_98_100_snaps PASSES. NULL: drive starts beyond own 20 move < 5%.

Item 1 (D196) — a measured timeout policy for the whole game. TABLE + ENGINE.
  D191 uses the 121-180 s rates for 181-300 s (never measured). Rebuild timeout_policy from PBP 2021-24 so it covers
  every quarter and seconds bucket (Q1-Q4, incl. > 300 s) by side, score state and clock running; the engine consults
  it at every snap where a timeout can be called; remove the 180/300 s window. Deliver the table the 6B order asked
  for: timeouts per game sim vs real by half x side x period (Q2 last 2:00, Q4 last 2:00, Q4 2:00-5:00, rest of Q4,
  rest of game) x what preceded (running-clock play / stopped-clock play / other). Real (Cowork): 7.7 team timeouts a
  game; 4.0 after running-clock plays.
  PRE-REGISTER: sim team timeouts 6.5-8.5 a game; running-clock timeouts 3.5-4.5; every period within 25% of real;
  test_engine_5a7 off TO within 0.4 of 1.78. Plays: report (most added timeouts are play-clock timeouts at ~40 s and
  barely move the clock). NULL: go_rate and fg_att on the sample move < 0.01 / 0.05 a game.

Item 2 (D197) — kneel timing and the three late reds. DIAGNOSIS THEN FIX.
  D190: the sim's final kneel of a half comes with 6.7 s left vs 22.1 s real (non-final 29.8 vs 32.4). Measure,
  sim vs real: clock left and down at the FIRST kneel of each kneel-out sequence, by quarter and defence timeouts left;
  then how the kneel decision table (kneel_decision.parquet, engine.py kneel_lookup) is keyed and consulted (cite
  file:line). Fix what the table shows. Then, for each remaining late red — test_engine_5a11 OT structure (P(tie|OT)),
  test_engine_5a8 tied-offence FG late, test_engine_5a7 timeouts/kneels, test_engine_6a kneel — give the value on
  main, eng/6a, eng/6b and after this item, and name the cause.
  PRE-REGISTER: first-kneel clock within 5 s of real; test_engine_6a kneel PASSES; at least two of the three 5a
  late reds PASS.

Item 3 (D198) — test selection, points split, ONE re-fit `fit_6c`.
  (a) test_dead_tables_5a5::test_dead_clock_runoff: exclude `ap_all` rows from the "largest primary cell" selection
      (as `p_*` and `all` already are) — state it in D198 as a test change with the reason; nothing else changes.
  (b) fit_6c on the item-2 engine: cal maps committed BEFORE K1 (clean header), K1 table + rows, K4, W2/W3 boards
      with team_volume, full suite. (c) Points-per-drive split on the sample with the new engine, using Cowork's
      method (research/nfl_sim/phase6a_cowork/analyze.py): START MIX / EFFICIENCY / interaction.
  PRE-REGISTER: K1 plays 125.8 +- 1.5; K1 safeties/game 0.028-0.040; go_rate / off_pen / def_pen / fg_att PASS;
  fd_pen still FAILS (known). Reds allowed to remain: fd_pen, tied expiry. Name every red with its value and the
  exit code.

Run test_engine_5m, 5w, 5y, 5z, 6a, 6b, 6c after items 0-2. Every item's report separates what the command RETURNED
from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
