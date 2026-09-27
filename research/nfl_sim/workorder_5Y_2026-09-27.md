# Work order 5Y — restore the first-down fallbacks, stop counting drive-ending clock twice, one re-fit (2026-09-27)

Written by Cowork after verifying 5X (`phase5x_verification_2026-09-27.md`, D171). Gate: D171 on main.

Pre-check (Cowork): runtime — items 0-1 are table rebuilds (seconds) plus the two red test files (~4 min on
Linux) and the 200-game sample x N=100 (~2.5 min on the Mac, as 5X item 2); item 2 is the same sample with the
play log plus a PBP pass; item 3 is one fit at N=5000 + cal + K1 + K4 + boards + suite (~2 h on the Mac, as 5X).
Credits: zero. Files: `nfl/sim/tables.py`, `nfl/sim/engine.py`, `nfl/data/sim/tables/clock_runoff.parquet`
(rebuilt by the committed builder), `nfl/sim/run_clock_class_5y.py`, `nfl/sim/tests/test_engine_5y.py`,
`research/nfl_sim/phase5y_*.md` + summary parquets under 2 MB.

```
Branch eng/5y from origin/main in a worktree; main untouched until Cowork verifies. Commit AND push each item
before the next; each decision (D172-D175) goes into research/nfl_sim/NFL_SIM_DECISION_v1.md, APPENDED AT THE END
of the file, in the same commit as its code. Gate first: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md
| grep -c "^### D171"` must print 1; if 0, STOP. Never weaken a test; if it fails, report it failing. Commit no
file larger than 2 MB. Re-record the player-OFF hash fixture whenever the fingerprint moves and print it. Every K1
run is on a CLEAN committed tree (5X's K1 header said "-dirty").

Item 0 (D172) — restore the first-down fallbacks. TABLE + ENGINE CHANGE.
  5X's builder stopped writing pooled `first_down` rows (5W: 32 main + 3 eoh + 3 fgs; 5X: 0), so the engine's
  pooled fallbacks are dead: thin split cells (rush: tied Q2_late/Q4_late/Q4_mid, trail9+ Q4_late/Q4_mid_b,
  trail1-8 Q4_mid_b, lead1-8 Q4_mid_b; pass: tied Q4_late/Q4_mid, lead1-8 Q4_mid_b, lead9+ Q4_mid_a) drop to the
  all-clock parent (a tied late first down draws ~33 s instead of 15.5 s), and `_eoh_runoff` still looks up
  `first_down`, which no longer exists in the eoh/fgs cells.
  Fix: the builder writes the pooled `first_down` rows at every level (main, Q4_mid, parent, legacy, eoh, fgs)
  IN ADDITION to the split rows. The eoh/fgs lookup tries the split name first, then pooled `first_down`, then
  `all`. Report, on the item's sample below, the count of sim first-down draws by the level they resolve to
  (split / pooled / Q4_mid / parent / legacy / eoh / fgs), per clock period.
  TEST (test_engine_5y.py): for every (score_state, clock_period) with a pooled first_down cell, a rush and a pass
  first-down lookup resolves to a cell with that SAME clock_period (split or pooled) — must FAIL on 5X's table.
  PRE-REGISTER: `test_t3_ot_structure` and `test_t4_tied_offence_kicks_not_scores_late` PASS again (Cowork
  measured P(tie|OT) 0.111 and tied late FG 0.189 with the 5W pooled rows appended); plays/game on the sample move
  by less than 0.5 (the dead fallback's aggregate effect was -0.1).

Item 1 (D173) — drive-ending plays out of the runoff cells. TABLE CHANGE.
  The engine charges TD / interception / lost-fumble plays with its typed drive_end clock (`max(16u, 3)`, mean
  8.28 s; real 8.59 s over 6.95 such plays a game) and never draws them from the table — but the table's cells
  include them, so every non-scoring play's draw is pulled short by them: the short clock is counted twice.
  Exclude plays with touchdown == 1 OR interception == 1 OR fumble_lost == 1 from EVERY cell `build_clock_table`,
  `_eoh_runoff_rows` and `_fgs_runoff_rows` write (the engine's drive_end classes are exactly these: td_mask |
  intercepted | pass_fumbled, td_r | fumbled). Leave the typed drive_end clock unchanged. Print, before and after,
  the "normal"-period means of first_down_pass, first_down_rush, complete_inbounds, run, incomplete (lead1-8 and
  all score states pooled) and the sum over cells of (new mean - old mean) x non-drive-ending plays per game.
  Use the 5X item-2 sample (same 200 game_ids, same seed), N=100.
  PRE-REGISTER: the builder reproduces Cowork's PBP numbers ("normal" period, all score states: fd_pass 33.26 ->
  36.71, fd_rush 33.95 -> 37.80, complete 38.93 -> 39.54, run 38.16 -> 38.43, incomplete 8.19 -> 8.11; sum +122.6
  s a game, each within 0.1); sim plays/game on the sample FALL by 3.5-5.5 vs item 0. NULLS: sim run share within
  1 point of item 0; drive_end events per game within 0.2 of item 0. If a prediction fails, say so; no tuning.

Item 2 (D174) — the class-by-class comparison 5X did not do. DIAGNOSIS ONLY.
  Same 200 games, N=100, with the play log, on the item-1 engine. Real side from PBP with IDENTICAL classes: run,
  first_down_rush, complete_inbounds, first_down_pass, incomplete, drive_ending, kneel, spike, eoh/fgs, and
  timeout-followed plays as their own class on BOTH sides (real: the next PBP row is a timeout; sim: the
  stop_code path) — elapsed = time to the next scrimmage snap, capped at the quarter end (drive_ending: the sim's
  typed clock vs the real elapsed). Per class: snaps/game and mean elapsed, sim vs real, overall, by season (2024
  separately) and by the offence's score state; then the per-game clock difference split into mix (count) and
  rate (seconds) by class. Also the real per-class mean elapsed by season: does 2024 differ from 2021-23 by more
  than 1 s in any class?
  PRE-REGISTER: (1) no class off by more than 1.5 s except where the report names the residual; (2) the sample's
  remaining plays gap is +1.5 to +4.0 (5X's sample gap +7.4 minus items 0-1); (3) null: both sides reconcile to
  900 s per regulation quarter (the real side checked, not only the sim).

Item 3 (D175) — ONE re-fit `fit_5y` on the item-1 engine: cal maps, K1 (table + rows, clean tree), K4, W2/W3
  boards with team_volume, full suite. PRE-REGISTER: K1 plays 127.8 +- 1.5; drives fall 0.5-1.2 from 23.98;
  pts/team falls 0.4-1.0 from 22.29 (fewer plays; report it against 22.39 actual, do not tune); go_rate / off_pen /
  def_pen / fg_att PASS (nulls); fd_pen and tied expiry still FAIL (known); the two 5X reds PASS. Full suite:
  exactly 2 reds (fd_pen, tied expiry) — name every red and give the exit code. The by-margin gap table
  (0-7 / 8-14 / 15-21 / 22+) against 5X's K1 gap of +6.6 overall.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
Append the session log to logs/agent_sessions.md (git add -f).
```
