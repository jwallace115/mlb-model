# Phase 5J-2 — Cowork verification (2026-09-21 ~16:00Z)

Branch `eng/5j` @ `57760d8`. Verified from the files in a cloud worktree (Linux, python 3.11.15, numpy 2.4.4,
pandas 3.0.2). `engine_fingerprint()` = `7f3d96900218c014` (RETURNED). `git diff origin/main...origin/eng/5j`
touches no engine/anchor/params/tables file and no earlier-phase test. `git merge-tree` vs main: clean.
**VERDICT: items 1-3 MERGE. Item 4's diagnosis is right about the symptom and missed the cause (below).**

## Verified by running it
- 9 new tests pass on the branch. Against the pre-fix code: item 1's test FAILS on `9b1e09b` ("Book-quoted
  rung 9.5 missing"), item 3's FAILS on `15ec21c` (fake QB at 22:00Z rejected), item 2's props-cap test fails
  on `b6e3ed6` by signature (TypeError — a weak failure, but the cap is proven below by execution).
- Full board by Cowork, `--week 2 --as-of 2026-09-20T15:30:00Z`, archives holding pulls to 23:50Z:
  newest props pull used = **15:00:10Z** (cap works); `anchoring_log.parquet` has `line_snapshot_utc`
  (15:00:09Z) and the board header prints it (written, not just computed);
  **P4 = 34 of 36** RB rush-attempt rows priced at the book's line (pre-registered 34 exactly — HELD);
  receptions 128/142 unchanged; **null control 1,269 / 1,269 legs identical** to the 5J board, same machine.
- P3 was re-run by Claude Code and matches Cowork's table (PIT@NE +5.0/41.0 vs in-play +13.5/36.5).

## Not right / not done
1. The union game set now pulls in a game ALREADY PLAYED: the run simulated 16 games, incl. Thursday's
   DET@BUF from its 09-18 00:00Z line, adding 76 legs for a finished game. Harmless for a rebuild, wrong
   for a live Sunday board. Needs `commence_time > as_of` (board layer; folded into 5L item 1).
2. `test_usage_pit_5j.py` still makes a network call (the order said tests run offline; only the new test does).
3. Line-history walk-back over 740 files took ~4 min on 2 cores before the first sim. Not a defect; will grow.
4. P1 / 2021-24 bit-identity for `usage.py`: hashes are in D111; Cowork did not rebuild usage. UNVERIFIED here.

## Item 4 — the diagnosis stopped one question short. THE ENGINE DRAWS PLAYER SHARES ONCE PER CHUNK.
D112: unstable `sort_values` on tied `target_share` re-orders players, "the per-player Beta draws shift", and
three orderings give Jeanty 16.6 / 23.7 / 21.4 mean carries. True. But at N=5,000 a different set of random
draws cannot move a MEAN by 7 carries — unless there are almost no draws. Cowork checked:
`_disperse` (engine ~504-519), documented "Draw (N, n_pl) dispersed shares", does
`out[:, j] = rng_obj.beta(a, b)` with no `size=N` — one scalar per player, broadcast to all sims.
- `_build_player_context('LAC','LV',2026,2,n_sims=2500)`: Jeanty's carry share across 2,500 sims has
  **1 unique value** (0.7721, std 0).
- `simulate_game(n_sims=1000)` seeds 1-6: Jeanty mean carries 21.19, 21.64, 19.28, **10.47**, 17.30, 20.77
  (SD 4.2); Washington 5.55, 2.01, 7.61, **14.55**, 8.86, 1.38; LV team carries 28.7-29.4.
The board = 2 chunks of 2,500, so each player's share on a board is set by TWO random numbers. This — not
week-1 share shrinkage, Cowork's guess on 09-20 — is the first explanation for the sim disagreeing with Hard
Rock by SD 0.147 and for pairs like Kaelon Black O9.5 = 0.905 / McCaffrey O14.5 = 0.151. It is team-level
neutral (anchoring equal to 3 dp across machines and orders), which is why K1 never saw it.
Every player-level artefact fitted on this engine — the calibration maps in `calibration_v1.json`, K4, the
TRUSTED / WATCH tiers, Week 1's 9-of-30 grade — was produced with it. Fix = work order **5L** (engine edit,
fingerprint change, one re-fit); 5K queues behind it. Until 5L lands, no player number from the sim is an
input worth reading; the standing rule (N54) already keeps it out of picks.
