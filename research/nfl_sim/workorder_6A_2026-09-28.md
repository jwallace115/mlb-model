# Work order 6A — fix the timeout and kneel runoff with measured tables, measure the safety roll, finish the points-per-drive split, one re-fit (2026-09-28)

Written by Cowork after verifying 5Z (`phase5z_verification_2026-09-28.md`, D180). Gate: D180 on main.

Pre-check (Cowork): runtime — items 0-2 are PBP passes (seconds) plus the 5Z 200-game sample at N=100 with the play
and drive logs (~3 min each on the Mac); item 3 is one fit at N=5000 + cal + K1 + K4 + boards + full suite (~2.5 h on
the Mac, as 5Y). Credits: zero. Files: `nfl/sim/tables.py`, `nfl/sim/engine.py`, `nfl/data/sim/tables/clock_runoff.parquet`
(rebuilt by the committed builder), `nfl/sim/run_engine_diag_6a.py` (new), `nfl/sim/tests/test_engine_6a.py` (new),
`research/nfl_sim/phase6a_*.md` + summary parquets < 2 MB.

```
Work order 6A (research/nfl_sim/workorder_6A_2026-09-28.md). Branch eng/6a from origin/main in a worktree; main
untouched until Cowork verifies. Commit AND push each item before the next; each decision (D181-D184) is APPENDED AT THE
END of research/nfl_sim/NFL_SIM_DECISION_v1.md in the same commit as its code. Session log to logs/_log_6a.txt
(git add -f), NOT logs/agent_sessions.md. Gate: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md | grep -c
"^### D180"` must print 1; if 0, STOP. Never weaken a test. Commit no file larger than 2 MB. Re-record the player-OFF
hash fixture whenever the fingerprint moves and print it. Sample = the 200 game_ids in research/nfl_sim/phase5z_sample.txt.

HARD RULE: a table the order asks for is the deliverable. If it cannot be produced, the decision reads "ITEM NOT DONE:
<exact blocker>" and you stop. "Not fully scored" or "time constraints" are not outcomes; there is no time limit.

Item 0 (D181) — timeout-followed runoff from a measured table. TABLE + ENGINE CHANGE.
  5Z table (c): plays followed by a timeout run 18.0 s to the stoppage in real games; the sim gives them 8.9 s because
  `_apply_timeouts` sets the play to `stop_code` and the runoff is drawn from the INCOMPLETE cell. Build a
  `timeout_followed` outcome in build_clock_table: real scrimmage plays (pass/run, drive-ending excluded as in D173)
  whose next PBP row before the next snap is a timeout; elapsed = time to the next scrimmage snap (clock stopped by the
  timeout), same score_state x clock_period cells, MIN_CELL fallbacks to parent and legacy like every other outcome.
  Engine: the stop_code path (pass and rush sites) draws from `timeout_followed` (fallback: parent cell, then the
  incomplete cell). Do NOT change the timeout policy (when timeouts are called).
  Report: real timeout-followed snaps/game and mean elapsed by score state and clock period; sim before/after on the
  sample; timeouts called per game sim vs real by team and half (diagnosis only — the sim's 2.2 vs 5.4 is reported,
  not fixed).
  PRE-REGISTER: sim timeout-followed mean elapsed within 1.5 s of real on the sample; sim plays/game FALL 0.4-1.0
  (2.2 snaps x ~+9 s ~ 20 s ~ 0.7 plays). NULL: every other class's sim mean elapsed moves < 0.3 s.

Item 1 (D182) — kneel runoff from a measured table. TABLE + ENGINE CHANGE.
  5Z: sim kneels take 20.3 s to the next snap, real 26.8 s. Measure real kneel elapsed (time to the next snap, or to
  the end of the half/game, capped) by (quarter 2/4, seconds-left bucket, defence timeouts left); make the engine's
  kneel runoff draw from it (replacing whatever constant/rule it uses now — name it in the decision).
  PRE-REGISTER: sim kneel mean within 1.5 s of 26.8 on the sample; sim plays/game fall 0.2-0.5 vs item 0.

Item 2 (D183) — two measurements the 5Z report did not deliver. DIAGNOSIS ONLY.
  (a) Safeties. The engine uses measured per-play rates by own-goal-line zone (constants.json safety_rate_by_zone,
      5A-7; the zeroed sack/run masks are by design — do NOT enable them). Real: 45 safeties on pass/run plays in
      1,087 K1 games (0.041/game); sim 0.072/game. Table: snaps per game in each zone (yl 90-94, 95-97, 98-100) sim vs
      real, sim safeties per zone snap vs the table's p, and whether the roll fires on steps that are not pass/run
      snaps (punt, FG, kneel, spike, no-play penalty) — count them. PRE-REGISTER: per-zone rates match the table within
      25%; the excess is in zone snap counts (sim >= 1.4x real). Name the cause; propose the fix; do not apply it.
  (b) Points per drive (5Z item 2, owed). Real points per drive by start bucket (own 1-20, 21-40, 41-60, opp 40-21,
      opp 20-1) from PBP drives (plays >= 1, the compute_k1_actuals definition); sim from the drive log on the sample.
      Split the per-game points gap into START MIX (sim bucket counts x real points per drive, minus real) and
      EFFICIENCY (real counts x points-per-drive difference). Show the two terms sum to the total gap within 0.1.
      PRE-REGISTER: START MIX >= 50% of the points gap.

Item 3 (D184) — ONE re-fit `fit_6a` on the item-1 engine: cal maps, K1 (table + rows), K4, W2/W3 boards with
  team_volume, full suite. Commit everything first: the K1 header must NOT say "-dirty" (if it does, fix and re-run
  K1 before reporting). PRE-REGISTER: K1 plays 127.2 +- 1.0 (from 128.29); drives fall 0.2-0.6; pts/team moves
  < 0.4; go_rate / off_pen / def_pen / fg_att PASS (nulls); fd_pen and tied expiry still FAIL (known); report the
  safety_share value (no fix yet). Name every red and give the exit code.

Test (test_engine_6a.py): a stop_code play draws from the timeout_followed cell (fails on the 5Z engine); the kneel
runoff uses the measured table (fails on the 5Z engine). Run test_engine_5m, 5w, 5y, 5z, 6a after items 0-1.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
