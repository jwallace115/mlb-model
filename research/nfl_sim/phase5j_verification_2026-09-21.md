# Phase 5J — Cowork verification (2026-09-21)

Branch `eng/5j` @ `59a686c` (base `0bc2660`); ran 2026-09-20 16:08-16:55Z, i.e. against the ORIGINAL order,
before the 09-21 amendment. Verified in a cloud worktree from the files, not the report.
`engine_fingerprint()` on the branch = `7f3d96900218c014` (RETURNED). No engine/anchor/params/tables/test
file of an earlier phase is touched (diff checked). **NOT MERGED — a 4-item fix order first.**

## What holds
- **Item 1 tests are real:** `test_layer3_rejects_post_kickoff_qb` FAILS on main's `usage.py`, passes on the
  branch (run both ways here).
- **Item 2 tests are real:** all three fail on main (the third only because the old function has no `as_of`).
- **P3 HOLDS — Cowork ran it; Claude Code called it "NOT TESTABLE: line capture stops before kick", which is
  false** (capture runs 14:00-05:30Z; there were simply no post-kick files yet at 16:13Z when it ran). With
  `as_of=18:30Z` on the real tape: the old code reads `snap_180009Z` and returns IN-PLAY lines for 8 kicked
  games (PIT@NE +13.5 / 36.5, CIN@HOU 31.5 total, CLE@TB nothing); the new code returns each game's last
  pre-kick Hard Rock line from `snap_170007Z` (PIT@NE +5.0 / 41.0 — what Jeff's app showed at kick).
  Note: the feed's `commence_time` DRIFTS to the actual kick (17:00:00 -> 17:05:00 -> 17:02:22Z), which is
  why a 17:00:07Z snapshot (book update 16:59:46Z) counts as pre-kick. Correct here, by the feed's grace.
- **Item 3 null control HOLDS on one machine:** main's `run_week.py` vs the branch's, same worktree, same
  lines, same props: 1,239 of 1,239 legs identical `sim_p`, none missing; the branch adds 30 legs.
- **Item 4 sim side reproduces:** every sim number in `phase5j_k1_before.txt` rebuilt from the committed rows file.

## What did not hold, or was not done
1. **P4 MISSED by one: 8/36 -> 33/36 (pre-registered >= 34/36).** Two misses are players outside the sim
   universe (Jonathon Brooks, TreVeyon Henderson). The third, Tyler Allgeier 9.5, IS in the universe: his
   book line equals a rung (9.5), so the new loop skips it (`bline not in rung_lines`) and the rung loop
   drops it for `sim_p` outside 0.05-0.95. "A quoted line is never silently missing" is violated.
2. **Item 3 has NO test.** The order required one that fails on main. Not written, not mentioned in the report.
3. **Item 2: `line_snapshot_utc` / `line_book` exist only in the returned dict** — `grep` finds no writer;
   the order asked for them in `anchoring_log.parquet` / the board header. Present, not reachable.
   Also: the game set is taken from the NEWEST snapshot, so a game that has left the feed is absent without
   a SKIPPED line; and `--as-of` does not cap props pulls (amended order, not yet seen by the branch).
4. **Item 1: nflverse `gametime` is US Eastern; the code parses `gameday + gametime` as UTC**, so a
   schedule-derived kickoff is 4 h early (20:15 ET read as 20:15Z). Conservative (excludes more), not a leak,
   but wrong. `except Exception: pass` around the schedule load means a failed download silently leaves
   every future week with NO layer-3 starter. The new test makes a network call.
   P1 / the 2021-24 bit-identity were NOT re-run by Cowork (needs the full usage build) — UNVERIFIED here.
5. **K1 "actual" punts/game is 7.90, not 8.73.** Cowork recomputed from PBP 2021-24 two ways
   (`play_type=='punt'` and `punt_attempt`): 7.8997 on 1,087 games — the generator is right. D99-D101's 8.73
   came from uncommitted code. So D100/D103's "punts moved TOWARD real (8.19 -> 8.84 vs 8.73)" — repeated in
   Cowork's own 5I verification — is WRONG: the sim over-punts by 0.94/game and 5I moved it AWAY. Consistent
   with drives/game 23.8 vs 21.9. Claude Code's "CHECK vs D102" compared sim columns only and missed it.
   The K1 file is stamped `9b1e09b7c-dirty`.

## New finding, bigger than the order — the BOARD IS NOT REPRODUCIBLE ACROSS MACHINES
Same code (main), same ratings (8 md5s equal), same rosters/depth, same lines, same props, anchoring offsets
equal to 3 decimals in 15 of 15 games: **621 of 1,237 legs differ between Jeff's Mac board (15:50Z) and the
cloud re-run, up to 0.60** (Ashton Jeanty O14.5 rush att 0.756 Mac vs 0.275 cloud; Mike Washington O4.5
0.32 vs 0.92; Blake Corum O9.5 0.945 vs 0.594). Two cloud runs agree with each other exactly. Not RNG
noise at N=5,000: a player-ordering or library-version dependence in the player layer. Cause NOT found.
Related, measured: raw sim vs market at iteration 0 is 8-12 points off in several games (PIT@NE raw NE -6.4
vs market +5.5; totals 48-54 vs 41-45), anchoring answers with EPA offsets up to -2.05, and under those
offsets player volume moves a lot (cloud: Jeanty 21.4 carries unanchored -> 12.3 anchored). Yesterday's
"sim vs book SD 0.147" cannot be interpreted until this is understood. The Week 2 sim-vs-book score is
therefore a score of ONE MACHINE'S board.
