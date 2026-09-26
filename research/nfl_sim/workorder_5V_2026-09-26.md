# Work order 5V — measure the plays target, then find where the clock goes (2026-09-26)

Written by Cowork after verifying 5U (`phase5u_verification_2026-09-26.md`, D157). Gate: D157 on main.

Why: after five phases of field-position work the sim still runs +6.4 plays and +1.8 drives a game (K1
130.9 / 23.7 vs 124.5 / 21.9), and the board's QB pass attempts are still +3.5 per team over the book. But
the 124.5 is a HARDCODED constant (run_k1_table.py, diagnostics.py, k1_compare_5a4.py, engine.py:3076),
and it is exactly PBP pass + run per game (72.01 + 52.49), while the sim's `n_plays` also counts kneels and
spikes (engine.py ~1591, ~1675) — 1.52 + 0.24 a game in real PBP. The like-for-like gap is probably ~+4.6,
not +6.4. Measure the target first, then decompose the clock.

Pre-check (Cowork): runtime — item 0 is a table rebuild (seconds) plus one hash record; item 1 is a PBP pass
(seconds); items 2-3 are the D144 sample (first 200 K1 games by game_id, N=100; ~2-6 min) with a play log,
plus a PBP pass. No re-fit. Credits: zero. New paths: `nfl/sim/actuals_k1.py` (or a function in the existing
`nfl/sim/actuals.py` — state which), `nfl/sim/run_clock_decomp_5v.py`, `nfl/sim/tests/test_engine_5v.py`,
`research/nfl_sim/phase5v_*.md/.parquet`.

```
Branch eng/5v from origin/main in a worktree; main untouched until Cowork verifies. Commit AND push each
item before the next; every decision (D158-D161) goes into research/nfl_sim/NFL_SIM_DECISION_v1.md in the
same commit as its code. Gate first: `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md | grep -c
"^### D157"` must print 1; if 0, STOP and report. Re-record nfl/sim/tests/fixtures/player_off_hash.json
whenever the fingerprint moves and print the value recorded. Run the FULL suite at the end of item 3 and
report the exit code and every red by name.

Item 0 (D158) — table hygiene. BEHAVIOUR-NEUTRAL: the player-OFF hash recorded for the new fingerprint MUST
  equal afdb11999d5b12bf (5U's value); if it differs, STOP.
  (a) `tables.py::build_all` must call `build_int_ez_table` and write `int_ez.parquet` (today it never does:
  a rebuild leaves the table missing). Rebuild and show the file is byte-for-byte or value-identical to the
  committed one.
  (b) The engine must RAISE if `int_spot.parquet`, `int_ez.parquet` or the interception entries of
  `turnover_returns.json` are missing. Today it falls back silently to LOS spotting / zero end-zone INTs under
  an unchanged fingerprint. Test (test_engine_5v.py): point the loader at a directory without int_ez.parquet
  and assert it raises; the test must fail on the current engine.

Item 1 (D159) — measure the plays and drives targets instead of typing them.
  Read every `n_plays[...] += 1` site in engine.py and list the event each one counts (the report must
  contain that list). Write a committed function that derives real plays/game from PBP 2021-24 REG with
  exactly that event set (Cowork's read: pass incl. sacks + run + qb_kneel + qb_spike; decide and state what
  happens to two-point tries and aborted snaps on BOTH sides). Do the same for drives/game against the sim's
  drive definition (plays >= 1 since D153). Replace every hardcoded 124.5 and 21.9 with the derived values.
  PRE-REGISTER: like-for-like real plays = 126.3 ± 0.3 (Cowork: 72.01 + 52.49 + 1.52 + 0.24), so the K1 gap
  is +4.6 ± 0.3, not +6.4. If it does not hold, report the number the data give and why.
  Null: the K1 sim values do not change (this item edits targets, not the engine).

Item 2 (D160) — play-level clock log. LOG-ONLY and drive_log-gated; the hash must again equal
  afdb11999d5b12bf. For every snap the engine processes, record: sim_id, quarter, game clock before the
  snap, clock consumed until the next snap, the play class the engine used to draw the runoff (the key it
  looked up in clock_runoff.parquet or equivalent — name the key fields), whether the clock stopped
  (incomplete, out of bounds, first-down stop if modelled, score, change of possession, timeout, penalty,
  two-minute warning), score differential for the offence, and the offence's timeouts left. Expose it as
  `team_df.attrs["play_log"]`. Test: on 3 games the per-sim sum of clock consumed equals the regulation
  clock (3600 s) within 1 s for games that do not reach overtime.

Item 3 (D161) — decompose the seconds-per-snap gap. DIAGNOSIS ONLY, no engine change.
  Sim: the D144 sample with the play log. Real: PBP 2021-24 REG, same games, elapsed = difference in
  game_seconds_remaining between consecutive snaps in the same half, classified with the SAME classes and
  cells (derive the real class from PBP fields: incomplete_pass, out_of_bounds, sack, penalty, timeout,
  two-minute warning, change of possession, score; state each mapping). Report per class: snaps per game,
  mean elapsed, sim vs real, and a mix-vs-rate decomposition of the total per-game clock difference (how
  much comes from HOW MANY of each class vs HOW LONG each class takes). Break out by quarter and by
  two-minute vs not, and by score state (lead 9+, within 8, trail 9+).
  PRE-REGISTER before looking: (1) sim mean elapsed per snap is >= 0.8 s shorter than real; (2) more than
  half of the per-game clock shortfall comes from MIX, led by more incomplete passes per game (the sim
  passes more than the book's QB lines imply); (3) null: total regulation clock consumed per game is equal on
  both sides within 5 s (if not, the play log or the real derivation is wrong — fix that first). If a
  prediction fails, say so plainly and report where the seconds actually go. No tuning in this item.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and
UNVERIFIED. Append the session log to logs/agent_sessions.md (git add -f).
```
