# Work order 5T — place the INT residual; diagnose the two standing reds (2026-09-25)

Written by Cowork after verifying 5S (`phase5s_verification_2026-09-25.md`). Gate: D147 on main.

Pre-check (Cowork): runtime — item 1 is the D144 sample (200 K1 games, N=100, drive_log; 214 s on the
Mac, 356 s on Linux) run twice at most; item 2 uses the 12-game `test_engine_5a9` sample at N=500
(minutes); item 3 is the K1 rows already on disk plus one PBP pass; no re-fit. Credits: zero. Paths:
`nfl/sim/run_int_chain_5t.py`, `nfl/sim/run_tied_expiry_5t.py`, `nfl/sim/run_fd_pen_5t.py`,
`nfl/sim/tests/test_engine_5t.py`, `research/nfl_sim/phase5t_*.md/.parquet` — all new, in the
existing conventions. Contradictions: none; item 0 is the D143 queue item.

```
Branch eng/5t from origin/main in a worktree; main untouched until Cowork verifies. Commit AND push
each item before the next; every decision goes into research/nfl_sim/NFL_SIM_DECISION_v1.md in the
same commit as the code. Gate first: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md |
grep -c "^### D147"` must print 1; if it prints 0 STOP and report — the 5S merge has not landed.

Item 0 (D148) — go_rate denominator. D143 established that the K1 row `go_rate` divides by go +
punts + ALL field goals while the actual (0.1980) is 4th-down-only. Make the two rows measure the
same thing: give `go_rate` the 4th-down-only denominator (ev_fg_att - ev_fg_non4th), or delete it
and keep `like_for_like_go` — state which and why. Update the test that reads it. Re-run the K1
table from the committed rows (no sim). State the new value and its PASS/FAIL against the existing
0.0100 tolerance. Do not touch the tolerance. If the row now FAILS, that is the correct outcome.

Item 1 (D149) — instrument the INT chain and place the 3.3-yard residual (52.7 sim vs 56.0 real).
  Log-only engine change: when drive_log=True, write `_dl_end_yl` on the INT play BEFORE the spot
  is changed (today it is not written, so a first-play INT carries a stale value — 14.7% of sim
  INTs), and record per INT: LOS, air drawn, catch point, ez flag (catch <= 0), return, six flag,
  next-drive start. Run the D144 sample (first 200 K1 games by game_id, N=100, seed 42) and build
  the REAL side with identical definitions from PBP 2021-24 REG: six = touchdown==1 & td_team==
  defteam; ez = (yardline_100 - clip(air_yards,0)) <= 0 & ~six; next start = yardline_100 of the
  first scrimmage play of the next fixed_drive. Cowork's real-side numbers to reproduce first:
  six 9.1% -> 73.7; ez 11.0% -> 79.9; other 79.9% -> 50.9 (formula 100-catch-ret gives 51.3).
  Report the sim shares and means in the same three cells, plus the LOS distribution (p10/25/50/
  75/90, mean; real mean 52.5) and the air and return distributions (both should match real —
  they are drawn from real quantiles; that is the null control).
  PRE-REGISTER before looking: (1) the sim's ez share is below 8% (a marginal air draw makes
  catch <= 0 rarer than real end-zone throws do) and that cell explains >= 1.5 of the 3.3 yards;
  (2) the sim LOS mean is within 2 of real; (3) returns and air match real within 1 yard at the
  mean (null). If (1) holds, the fix is to condition the air draw on the play's own pass depth (the
  engine already draws depth — use it) or to add an explicit end-zone probability by LOS bucket
  measured from PBP; write the fix as a SEPARATE follow-on, do not implement it in this item.
  If (1) fails, say so and report where the yards actually sit. Fingerprint must not change for
  the log-only part (the instrumentation is drive_log-gated) — prove it by printing it.
  Test: test_engine_5t.py asserts the INT record's LOS is never stale (no 0.0, and equals the
  previous play's post-play yardline) on a 3-game sample.

Item 2 (D150) — tied_drives red, red since 5I. Definition (D94, derive_engine_targets.py::
  derive_tied_drive_expiry_matched): a drive starting in Q4 with <= 300 s, tied at the first snap,
  that reaches the 35 (broad), expiring without a kick — real 0 of 56 (2021-24), sim 0.0959 in
  the 5S K1 table. Take the 12-game test_engine_5a9 sample at N=500 with drive_log, isolate the
  expiring drives, and for each record: clock at the last snap, down, distance, yardline,
  timeouts left (both teams), what the last play was, and whether the FG-setup / kneel / timeout
  policy tables were consulted. Group by mechanism. PRE-REGISTER: >= 60% of expirations are a
  drive whose last snap was inside the final 10 s with the clock running after an in-bounds gain,
  where a real team spikes or uses a timeout and the sim has no spike and did not use one. Report
  what the data say. If the mechanism is unambiguous and the fix is one table lookup or one
  branch, implement it, re-run the 5a9 test, and report the K1 tied row from a re-run of
  run_k1_table.py on the same 200-game sample (no full re-fit). Otherwise diagnosis only. Null:
  kneels/game and late-Q4 snaps (test_t3_kneels_and_late_snaps) must not move.

Item 3 (D151) — fd_pen red, red since 5I. Sim first downs by penalty 1.409/team vs real 1.728
  (derivation in derive_engine_targets.py). From PBP 2021-24 REG, break the real 1.728 down by
  penalty type (DPI, defensive holding, roughing, offside/encroachment on 4th-or-short, illegal
  contact, other) and by whether the yardage alone crossed the sticks vs an automatic first down.
  From the K1 rows and the engine's penalty tables (`build_penalty_table.py`, `penalty_audit.py`),
  state which of those the sim can produce at all and at what rate. PRE-REGISTER: the missing 0.32
  is concentrated in automatic-first-down fouls (DPI/holding/roughing) that the sim either lacks
  or prices at the no-play rate. Diagnosis only; no engine change in this item. Null: off_pen and
  def_pen per game rows stay PASS (they are counts, and must not be touched to make fd_pen move).

Every item's report separates what the command RETURNED from what it MEANS, and ends with NOT
DONE and UNVERIFIED lines. Append the session log to logs/agent_sessions.md (git add -f).
```
