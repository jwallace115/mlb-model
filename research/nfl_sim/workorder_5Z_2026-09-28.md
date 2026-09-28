# Work order 5Z — measure the three open engine questions; change nothing (2026-09-28)

Written by Cowork after verifying 5Y (`phase5y_verification_2026-09-28.md`, D176). Gate: D176 on main.

Pre-check (Cowork): runtime — all three items run on ONE sim pass of the 5X/5Y season-stratified sample (the same 200
game_ids, seed 42, N=100, play log + drive log on: ~3 min on the Mac) plus PBP passes over 2021-24 (seconds). No
re-fit, no K1, no boards, no full suite. Credits: zero. Files: `nfl/sim/run_engine_diag_5z.py` (new), `nfl/sim/engine.py`
(log-only counters, item 1), `nfl/sim/tests/test_engine_5z.py` (new), `research/nfl_sim/phase5z_*.md` + summary
parquets < 2 MB.

```
Branch eng/5z from origin/main in a worktree; main untouched until Cowork verifies. Commit AND push each item before
the next; each decision (D177-D179) is APPENDED AT THE END of research/nfl_sim/NFL_SIM_DECISION_v1.md in the same commit
as its code. Session log goes to logs/_log_5z.txt (git add -f), NOT logs/agent_sessions.md. Gate: `git show
origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md | grep -c "^### D176"` must print 1; if 0, STOP. Never weaken a
test. Commit no file larger than 2 MB. This order is DIAGNOSIS ONLY: the engine's outputs must not change — the
player-OFF hash for the current fingerprint must be unchanged after item 1 (print it before and after).

HARD RULE FOR THIS ORDER: a table the order asks for is the deliverable. If a table cannot be produced, do NOT write
the decision as if the item were done — write "ITEM NOT DONE: <exact blocker>" as the decision, commit it, and stop.
"Not completed due to time constraints" is not an acceptable outcome; there is no time limit on this session.

Sample for all items: the 200 game_ids of the 5X/5Y item-2 sample (list them in phase5z_sample.txt), N=100, one pass
with the play log and drive log on. Real side: PBP 2021-24 REG, the same 200 games AND all 1,087 K1 games (report both).

Item 0 (D177) — the per-class clock comparison (asked in 5W, 5X and 5Y; never delivered).
  Classes, IDENTICAL on both sides: run, first_down_rush, complete_inbounds, first_down_pass, incomplete, sack,
  timeout_followed (real: the next PBP row is a timeout; sim: the stop_code path), drive_ending (TD / INT / lost
  fumble; sim = its typed clock), kneel, spike, eoh/fgs. Elapsed = time to the next scrimmage snap, capped at the
  quarter end. Deliver THREE tables (markdown in phase5z_clock_class.md + one parquet):
   (a) per class: snaps/game and mean elapsed, sim vs real, and the difference;
   (b) the same by the offence's score state (trail9+, trail1-8, tied, lead1-8, lead9+);
   (c) the per-game clock difference split into MIX (snaps x real rate) and RATE (real snaps x rate difference) per
       class, summing to the total sim-minus-real clock per game (show the sum closes to within 5 s).
  Null (must hold before (a)-(c) are reported): both sides reconcile to 900 s per regulation quarter on the sample.
  PRE-REGISTER: (1) the remaining plays gap (+2.5 in K1) is mostly RATE (>= 60% of the clock shortfall), not MIX;
  (2) the largest single rate shortfall is in run / complete_inbounds while the offence leads (5W measured sim
  29.8 vs real 33.1 s per snap at lead 9+ before the 5X-5Y fixes). Say plainly if either fails.

Item 1 (D178) — safeties: the engine makes ~0.078 a game vs 0.049 real (53 in 1,087 K1 games).
  Real side: every safety in PBP 2021-24 REG classified by the play that produced it (sack in the end zone, run
  tackled in the end zone, offensive penalty in the end zone (holding/grounding), punt/kick play, other) with
  counts per game and the offence's yardline at the snap. Sim side: add LOG-ONLY counters for the same types at the
  engine's safety sites (the hash must not change — print it), run the sample. Deliver the table sim vs real per type
  per game, and the rate per snap from inside the offence's own 5 / own 10.
  PRE-REGISTER: the excess is concentrated in ONE type (the sim's sack/run-in-end-zone rate from inside its own 5),
  not spread evenly. Name the branch and table the excess comes from; propose the fix in the decision; do NOT apply it.

Item 2 (D179) — points per drive: sim 1.85 vs real 2.06, with ~1.55 extra drives a game.
  From the drive log (sim) and PBP drives (real; plays >= 1, same definition as compute_k1_actuals): drives per
  game by start bucket (own 1-20, own 21-40, midfield 41-60, opp 40-21, opp 20-1) and by the preceding event
  (kickoff, punt, turnover, downs, missed FG, other); outcome mix per bucket (TD, FG, punt, turnover, downs,
  end of half, safety); points per drive per bucket. Then split the per-game points gap into START MIX (bucket
  counts x real points per drive) and EFFICIENCY (real counts x points-per-drive difference).
  PRE-REGISTER: (1) the sim has more drives starting in its own 1-20 than real (the extra punts: 9.1 vs 7.9 in K1);
  (2) >= 70% of the points-per-drive gap is START MIX, < 30% EFFICIENCY. Say plainly if either fails.

Test (test_engine_5z.py): the new safety counters sum to ev_safeties on every sim of 3 games x 200 sims; the
player-OFF hash equals the pre-item-1 value. No other test changes. Run test_engine_5m, 5w, 5y, 5z and report.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
