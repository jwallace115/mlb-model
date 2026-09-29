# Work order 6D — measured timeouts for the whole game, the kneel decision, one re-fit (2026-09-29)

Written by Cowork after verifying 6C (`phase6c_verification_2026-09-29.md`, D199). Order 2 of the 3-order time box
(proposed finish line: after 3 orders the engine is frozen whatever state it is in). Builds on eng/6c.

Pre-check (Cowork): runtime — items 0-2 are PBP table builds (seconds) + the 200-game sample at N=100 (~5 min each)
+ the late-game test files (~15 min); item 3 is one fit + cal + K1 + K4 + boards + suite (~3 h on the Mac, as 6B/6C).
Credits: zero. Files: nfl/sim/tables.py, nfl/sim/engine.py, nfl/data/sim/tables/timeout_policy.parquet and
kneel_decision.parquet (rebuilt by committed builders), nfl/sim/tests/test_engine_6d.py (new),
nfl/sim/tests/test_dead_tables_5a5.py (selection only), research/nfl_sim/phase6d_*.md + parquets < 2 MB.

```
Work order 6D (research/nfl_sim/workorder_6D_2026-09-29.md). Branch eng/6d from origin/eng/6c (NOT main) in a
worktree. Gates (run `git fetch origin` first): `git rev-parse --short=9 origin/eng/6c` prints db2de2582, and
`git show origin/main:research/nfl_sim/phase6c_verification_2026-09-29.md | grep -c "^### D199"` prints 1; if either
fails, STOP and print both. FIRST COMMIT: append the D199 block from that file VERBATIM at the end of
research/nfl_sim/NFL_SIM_DECISION_v1.md. Then items 0-3, commit AND push each before the next; decisions D200-D203
appended in the same commit as their code. Session log appended to logs/_log_6d.txt (git add -f), timestamps from
`date -u`. Never weaken a test. No file > 2 MB. Re-record the player-OFF hash whenever the fingerprint moves.
Sample = research/nfl_sim/phase5z_sample.txt, N=100.

HARD RULES: a table the order asks for is the deliverable. "ITEM NOT DONE" only for an external blocker (missing data
file, tool/API failure) named exactly; "deferred", "scope" and "time" are not outcomes. NO PROXIES: do not apply rates
measured in one situation (quarter, clock bucket, state) to another; if a cell is thin, pool with a stated fallback
built from real rows, as the clock table does. Every code claim cites file:line. Every pre-registration and null gets
HELD/FAILED with the number. A new test calls the engine and must FAIL on eng/6c — run it there and paste the failure.

Item 0 (D200) — reverse D196; a measured timeout policy for the whole game. TABLE + ENGINE.
  (a) Remove the Q1->Q2 / Q3->Q4 mapping and the whole-game window (engine.py:1404-1412 on eng/6c).
  (b) Rebuild timeout_policy.parquet in tables.py from PBP 2021-24 REG over EVERY quarter (1-4, OT) and seconds
      buckets covering the whole quarter (e.g. 0-30, 31-60, 61-120, 121-180, 181-300, 301-600, 601-900), by side
      (off/def), score state and clock running; per-snap probability = team timeouts called after that snap / snaps
      in the cell, with the builder's usual MIN_CELL pooling. Print the table's row count and every Q1/Q3 row.
  (c) The engine looks up the real quarter and bucket.
  (d) Deliver: team timeouts per game sim vs real by half x side x period (Q2 last 2:00, Q4 last 2:00, Q4 2:00-5:00,
      rest of Q4, rest of game) and timeouts remaining at the 2:00 warning per team, sim vs real.
  Real (Cowork, PBP 2021-24): 7.7 team timeouts a game (H1 off 2.28 / def 1.47, H2 off 1.49 / def 2.35).
  PRE-REGISTER: sim timeouts 6.5-8.5 a game; each period within 25% of real; timeouts left at the Q4 2:00 warning
  within 0.3 of real; tie rate, P(tie|OT), late-half snaps and timeout-policy-live tests PASS. NULL: go_rate and
  fg_att on the sample move < 0.01 / 0.05 a game.

Item 1 (D201) — the kneel decision. DIAGNOSIS THEN FIX.
  D190/D197: the sim's final kneel comes with 6.7 s left vs 22.1 s real. Deliver, sim vs real: clock left, down and
  defence timeouts at the FIRST kneel of each kneel-out sequence (Q2 and Q4 separately); the keys of
  kneel_decision.parquet and how engine.py consults it (file:line), including what happens when the key is missing.
  Fix what the table shows (rebuild or re-key the table from PBP; no hand-set probabilities).
  PRE-REGISTER: first-kneel clock within 5 s of real in Q4; final-kneel clock within 5 s of 22.1; test_engine_6a
  kneel test PASSES; tied-offence-kicks and kneels-and-late-snaps PASS.

Item 2 (D202) — punt fallback and test selection.
  (a) engine.py punt fallback: a landing deeper than the receiving 20 is NOT a touchback; use the landing table's
      nearest bucket instead, and count how often the fallback fired on the sample before and after.
  (b) test_dead_tables_5a5: exclude `ap_all` rows from the clock "largest primary cell" selection and make the punt
      test perturb the table the engine now reads (punt_landing) — state both as test changes with the reason.

Item 3 (D203) — ONE re-fit `fit_6d` on the item-2 engine: cal maps committed BEFORE K1 (clean header), K1 table +
  rows, K4, W2/W3 boards with team_volume, full suite. Points: pts/team fell 21.55 -> 21.28 -> 20.83 across 5Y/6B/6C
  (real 22.39). Deliver Cowork's points-per-drive split on the sample (research/nfl_sim/phase6a_cowork/analyze.py
  method: START MIX / EFFICIENCY / interaction) for fit_6c AND fit_6d, and name what moved.
  PRE-REGISTER: K1 plays 125.8 +- 1.5; safeties 0.028-0.040; pts/team rises vs 6C; go_rate / off_pen / def_pen /
  fg_att PASS; reds allowed to remain: fd_pen, tied expiry. Name every red with its value and the exit code.

Run test_engine_5m, 5w, 5y, 5z, 6a, 6b, 6d after items 0-2. Every item's report separates what the command RETURNED
from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
