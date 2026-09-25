# Work order 5U — three measured defects fixed, ONE re-fit (2026-09-25)

Written by Cowork after verifying 5T (`phase5t_verification_2026-09-25.md`, D152). Gate: D152 on main.

Pre-check (Cowork): runtime — items 0-2 are the D144 sample (200 K1 games, N=100, drive_log; 128 s on
the Mac) run once or twice each plus table rebuilds (seconds); item 3 is one fit at N=5000 plus cal,
K1, K4, boards and the suite (~120 min on the Mac, as 5S). Credits: zero. Paths: new files
`nfl/sim/tests/test_engine_5u.py`, `research/nfl_sim/phase5u_*.md/.parquet`, `phase5u_boards/`,
`phase5u_k1_after.txt` + rows, `phase5u_k4.parquet`, fit tag `fit_5u`; tables rebuilt in place by
`tables.py` (`turnover_returns.json`, new `int_ez.parquet`). Contradictions: none — every change here
is a defect D152 measured, none is a tuning.

```
Branch eng/5u from origin/main in a worktree; main untouched until Cowork verifies. Commit AND push
each item before the next; every decision (D153-D156) goes into research/nfl_sim/NFL_SIM_DECISION_v1.md
in the same commit as its code. Gate first: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md
| grep -c "^### D152"` must print 1; if 0, STOP and report. Run the FULL suite at the end of items 0 and
3 and report exit code + every red by name; re-record nfl/sim/tests/fixtures/player_off_hash.json
whenever the fingerprint moves (record_player_off_hash.py) and print the hash it recorded.

Item 0 (D153) — drive-log hygiene and first-down counters. LOG-ONLY; the player-OFF hash recorded for
  the new fingerprint MUST equal 31de7e75f17b878b (that is the neutrality proof; if it differs, STOP).
  (a) Reset `_dl_end_yl/_dl_end_down/_dl_end_dist` in `_dl_new_drive` to the new drive's start values,
  so no drive ever carries the previous drive's end fields (D152: 9 of 33 "expired tied drives" were
  zero-play phantoms with mirrored end yardlines, 3 with a negative start clock). (b) A drive with
  zero plays at game/half end must not be emitted as a drive row (or is emitted with a flag the
  metrics exclude — state which and why). (c) Split `ev_fd_penalty` into `ev_fd_pen_auto` (the
  `u_pen_auto < auto_rate` award) and `ev_fd_pen_yds` (the `pen_yds >= dist` award), keep the total.
  (d) Sim side of the tied-expiry metric (run_tied_expiry_5t.py AND test_engine_5a9::test_t3_tied…)
  requires plays >= 1, matching the real side's scrimmage-snap requirement. Re-run the tied script:
  PRE-REGISTER reached/expired on plays >= 1 = 24 of ~331 (about 7%), still FAIL against 0.05; do not
  relax the tolerance. Report the fd counter split from a 200-game run: PRE-REGISTER auto ~1.25/team,
  yds ~0.16/team (D152's arithmetic from penalty_detail.json).

Item 1 (D154) — two double counts removed. ENGINE + TABLE change.
  (a) `int_ret_q`: rebuild `turnover_returns.json` interception returns from interceptions that were
  NOT returned for a touchdown (PBP 2021-24 REG, `interception == 1 & return_touchdown == 0`; real
  mean 9.13, n = 1,523) — the engine draws the return only after the pick-six branch, so the table
  must exclude pick-six returns (mean 44.5). State the derivation and both means in the report.
  (b) Remove the `int()` floor on the air and return draws (use the interpolated float, or round —
  state which); the floor costs ~0.5 yd on each.
  (c) fd_pen: `auto_first_rate` in penalty_detail.json is `first_down_penalty.mean()` — every first
  down by penalty, yardage-crossed included — so delete the extra `yds_fd` award (engine.py ~1923).
  Keep the counters from item 0. This moves fd_pen AWAY from the target: PRE-REGISTER fd_pen/team
  1.41 -> 1.25 ± 0.03, FAIL widens. That is the correct outcome; do not touch the tolerance and do
  not add a compensating term.
  PRE-REGISTER on the D144 sample (first 200 K1 games, N=100): sim "other"-cell returns 12.1 -> within
  1.0 of 9.5; non-six next start 50.4 -> >= 52.0 (real 54.2). Nulls: INT/game 1.64 ± 0.05; pick-six
  share 9.2% ± 0.5; sim "other"-cell LOS 56.3 ± 0.5 (unchanged by construction).

Item 2 (D155) — end-zone interceptions. ENGINE + TABLE change.
  Measure from PBP 2021-24 REG, non-pick-six interceptions: P(catch in end zone | LOS bucket) where
  ez = (yardline_100 − clip(air_yards, 0)) <= 0, with the five 5S buckets (real overall 12.15% of
  non-six; report each bucket's n and rate). Write `int_ez.parquet` from `tables.py` (committed
  generator). Engine: draw ez first from the bucket rate (new draw `u_int_ez` in the play-loop
  stream, placed next to `u_int_air`); if ez, spot at 80 as today; otherwise draw air from the
  bucket's NON-ez quantiles (rebuild `int_spot.parquet` on the non-ez subset, same 101 points).
  Test (test_engine_5u.py): on the 5S test games the non-six ez share is within 2pp of the
  table's weighted rate, and fails on the 5T engine.
  PRE-REGISTER (D144 sample): non-six ez 7.3% -> 12.2 ± 1.5; "other"-cell air 15.6 -> 17.2 ± 1.0;
  post-INT next start (all INTs incl. six, the D144 definition) 52.7 -> within 1.5 of 56.0.
  Null: INT/game and pick-six share unchanged as in item 1. If a prediction fails, say so and stop
  there — no re-tuning of the table.

Item 3 (D156) — ONE re-fit `fit_5u` on the item-2 engine: cal maps, K1 (table + rows), K4, W2/W3
  boards with team_volume, full suite, hash re-record. PRE-REGISTER before looking: inside-40 starts
  1.56 -> <= 1.45/game; TD 1-3-play share 0.152 -> <= 0.14; plays/game 130.9 ± 0.5 (null — field
  position does not change the play count); pts/team within 0.5 of 22.23 and state the direction
  (actual 22.39); go_rate/off_pen/def_pen/fg_att PASS (nulls); fd_pen ~1.25 FAIL (expected, item 1c);
  tied expiry ~7% FAIL (expected, item 0d). Board: SD(sim_p − q) and pass att gap reported, no
  target. Cross-machine: Cowork will run the W2 board on Linux against phase5u_boards/picks_log_mac
  .parquet — commit it with board_generated_utc intact.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and
UNVERIFIED. Append the session log to logs/agent_sessions.md (git add -f).
```
