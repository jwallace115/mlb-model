# Phase 5T verification — Cowork, 2026-09-25T18:10Z

Branch `eng/5t` @ `2e12979` (5 commits; D147 on main = 1). Verified from the files in a Linux
worktree. Every number below was recomputed here unless marked "read".

## Commits and decision records
D148 341f535, D149 a1ab409, D150 45afb04, D151 cd1a290 each carry their decision entry in the same
commit; log e2e. Files: engine (log-only edit), `run_k1_table.py`, `test_engine_5a3.py`,
`run_int_chain_5t.py`, `run_tied_expiry_5t.py`, `test_engine_5t.py`, three reports, two parquets.

## Item 0 (D148) — accepted
go_rate now = go / (go + punts + 4th-down FG); `like_for_like_go` row removed; the 5a3 test uses the
same denominator. Value from the 5S rows: 0.20703, diff +0.0090, PASS by 0.001 — REPRODUCED
(identical to my 5S computation). `test_engine_5i` still carries its own like-for-like assertion;
redundant, harmless.

## Item 1 (D149) — the instrumentation is right; the diagnosis has two arithmetic errors
- Engine edit read: `_dl_end_yl/down/dist` written on the INT play before the spot changes; per-INT
  row appended only under `drive_log`. **Behaviour-neutral, PROVEN:** four games x {drive_log off,
  on} at N=300 give byte-identical team outputs on main's engine and eng/5t's; and the player-OFF
  hash for the new fingerprint `2b9666346a810f9f` records as `31de7e75f17b878b` — the SAME value
  the Mac recorded for 5S's `06caa0cbb12bbe6e` (DAL@PHI 2023 wk9, N=4,000). Two facts in one:
  the edit changes nothing, and Linux reproduces the Mac's hash.
- **Claude Code did not run the suite.** The fingerprint moved and the fixture was not re-recorded,
  so `test_engine_5m::player_off_hash` FAILS on the branch as pushed ("No hash recorded for
  2b9666346a810f9f"). I recorded it here; the fixture goes into the merge commit. The report's
  "Tests: 2/2 pass" counted only `test_engine_5t.py`.
- `test_engine_5t.py` asserts LOS > 0 and in [1, 99] — not "equals the previous play's post-play
  yardline" as ordered. Weak but not tautological on the stale-value defect it targets.
- **The three-cell table is reproduced, the distribution table is not.** From
  `phase5t_int_chain.parquet` (32,750 INTs): six 9.25%, ez 6.60% of all / 7.27% of non-six,
  non-six next start 50.41 — matches. But D149's "air −1.2" averages the pick-six rows, which the
  log writes with air = 0, into the sim mean (14.55); on non-six rows the sim air is 16.04 vs
  real non-six 17.13 (−1.1), and in the "other" cell 15.59 vs 17.19 (−1.6). And the return sign is
  BACKWARDS: sim non-six returns are 12.11 vs real 9.13, "other" cell 12.13 vs 9.54 — the sim
  returns are 2.6 yards LONGER, not 1.7 shorter. Cause: `int_ret_q` (turnover_returns.json) was
  built from ALL 1,675 interceptions including the 152 pick-sixes (mean return 44.5 yards), but the
  engine draws it only AFTER the pick-six branch has been taken. The long returns are counted
  twice. Real-side cells with identical definitions (mine): six 9.07% -> 73.7; ez 12.15% of
  non-six -> 79.9; other: LOS 56.31, air 17.19, catch 39.13, ret 9.54, next 50.91 (formula 51.33).
  Sim other: LOS 56.34 (identical), air 15.59, catch 40.75, ret 12.13, next 48.09 (formula 48.09).
  The other-cell gap of 3.2 (formula to formula) is exactly 1.6 (air) + 2.6 (returns).
- With the right denominators the missing end-zone catches (7.3% vs 12.2% of non-six) are worth
  4.9pp x (80.0 − 48.1) = 1.6 yards — prediction (1)'s second half HELD, not FAILED.
- A small mechanical bias sits under the air deficit: both draws are `int(np.interp(...))`, which
  floors every value (−0.5 yard each on air and return, before anything else).
- Verdict: the residual is placed, better than D149 says: fewer end-zone catches (~1.6 yd), shallower
  air (~1.6 yd in the other cell, partly the floor), and returns 2.6 yd too LONG pulling the other
  way. Fixes are concrete: rebuild the return table from non-TD interceptions, remove the floor, add
  a measured end-zone probability by LOS bucket (or condition on pass depth). -> 5U items 1-2.

## Item 2 (D150) — 33/340 reproduced; a third of the "expired drives" are not drives
Re-ran `run_tied_expiry_5t.py`: reached 340, expired 33, 9.71%. The committed parquet shows what
the report did not look at: 9 of the 33 have `plays == 0`; 3 have a NEGATIVE start clock (−12 s);
and the zero-play rows carry an `end_yardline` that is the mirror (100 − x) of the previous drive's
end — `_dl_end_*` is never reset at `_dl_new_drive`, so a possession flip at 0:00 logs a phantom
drive with the other team's end fields, and `end_yardline <= 35` then marks it "reached". The real
side of the metric requires a scrimmage snap; the sim side does not. On `plays >= 1` the count is
24 (~7%), still red. The order asked for per-drive final state (clock at last snap, timeouts, last
play, which table fired); none was recorded — the report says the drive log lacks it and stops.
Pre-registration reported FAILED honestly. -> 5U item 0 (log hygiene, metric on plays >= 1) and the
per-play trace stays owed.

## Item 3 (D151) — HELD is the wrong verdict; the accounting is off
`penalty_detail.json::auto_first_rate` is `first_down_penalty.mean()` per category (read in
`build_penalty_table.py:111`) — the rate of ANY first down by penalty, yardage-crossed included.
So: (a) the sim's no-play defensive penalties yield, by construction, exactly the real no-play
first-down rate: 1.012x0.992 + 0.803x0.990 + 0.445x0.953 + 1.139x0.218 + 0.052x0.571 = 2.50/game =
1.25/team; (b) the engine then ALSO awards a first down when `pen_yds >= dist` on the non-"auto"
draws (engine.py ~1923) — a double count worth the sim's remaining 0.16/team; (c) the real
total, 1.728/team, therefore exceeds the no-play part by 0.48/team, all of it from live-play
(tacked-on) penalties the engine does not model (`scalars.penalty.p_penalty` = 1.45%/play is
loaded and never used). D151's live-play story is right; its "concentrated in auto-FD fouls, HELD"
is not measured — the real live-play split by type was listed as NOT DONE. Removing the double count
moves fd_pen from 1.41 to ~1.25, AWAY from the target; that is the correct outcome.

## Verdict
5T is accepted for merge with the re-recorded hash fixture; its diagnoses are corrected above
(D152). Nothing in it changes simulation behaviour.
