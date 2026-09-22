# Phase 5M verification (Cowork, 2026-09-22T17:02Z)

Branch `eng/5m` @ `63c80c5` (D119-D122 + log), base `58d5645` (main after D118). Verified from files and by
re-running on Linux. `git merge-tree` vs main: clean.

## Verdict: MERGE the engine (items 1-3) and the measurement (item 4). Two NEW tests are red at HEAD and one
reported red is not red; 5N item 1 fixes the tests before anything else.

## Item 1 (D119) - child RNG, played-game exclusion, offline test
- Diff is as ordered: `player_rng = np.random.default_rng(stable_seed((seed, "player")))` at engine.py:742;
  the play-loop `rng` untouched. `get_lines_from_history` skips a game with `commence_time <= as_of`.
- (i) player-ON scores == player-OFF at the same seed: test passes here. (ii) T4: all 5
  `TestT4PlayerLayerNeutral` tests PASS on Linux at HEAD. (iii) the player-OFF hash null control: HELD at
  D119's commit (`c98664e98b00c7ff` reproduced here with the item-1 engine and tables) - **but the test
  hardcodes that hash and item 2 legitimately moved the play stream, so `test_player_off_hash_stable` is
  RED at HEAD** (`10425a6562817ec2`). D121's suite listing does not mention it and instead lists the T4
  margin/KS reds copied from 5L, which do not reproduce (T4 is green, as D119 itself says). The null
  control did its job at item 1; the test as written cannot survive any later engine change.
- `test_prekick_line_chosen_for_kicked_game` (5J) is red because 5M made kicked games absent, which is what
  the order asked for. D119 labels it "KNOWN EXPECTED FAILURE". A red that stays red is the pattern
  CLAUDE.md forbids; the test must be rewritten to assert the new behaviour. 5N item 1.
- `test_usage_pit_5j.py`: no `nflreadpy` import; fixture present; passes.

## Item 2 (D120) - Q4_mid split
- Cell sizes stated before the edit (Q4_mid_a all 10 >= 100; Q4_mid_b 3 thin -> unsplit fallback); the
  4-level fallback is in both the scalar and vectorised paths (read). `clock_runoff.parquet` rebuilt 160
  rows. Fingerprint `02fbcab6e6ed042e`.

## Item 3 (D121) - re-fit, K1, board
- Punts/game 8.842 vs pre-registered >= 0.3 drop: **DID NOT HOLD**, stated plainly, nothing tuned. Tied-drive
  expiry 0.119 -> 0.105: HELD. All five K1 null controls within tolerance (read from
  `phase5m_k1_after.txt`). The punt excess is NOT a Q4 pace problem: the same table shows drives/game 23.8
  vs 21.9 real and plays/game 130.3 vs 124.5 - the sim runs ~2 extra drives per game, and ~0.9 extra
  punts is what 2 extra drives produce. That is the cause to measure next (5N item 3).
- **Cross-machine, pre-registered >= 99% within 0.02: HELD at 100%.** Linux board (`--week 2 --as-of
  2026-09-20T15:30:00Z`, 25.9 min, 15 games - DET@BUF gone - 15/15 converged, 1,353 legs) matches
  `phase5m_boards/picks_log_mac.parquet` on every leg, sim_p and cal_p exactly.
- Full suite on Linux at HEAD (209 tests, 39.9 min): 203 pass, 6 fail. Two are an artefact of running the
  board into the same outputs dir the `test_score_vs_book` fixtures read (they pass in a clean clone);
  four are real: the two 5M test defects above, plus `fd_pen` and `tied_drives` (known since 5I, still
  uninvestigated). Claude Code's "77 passed, 3 failed" counted a subset.

## Item 4 (D122) - share shrinkage, REPRODUCED EXACTLY by re-running the committed script
WR target holdout reduction 47.3% (n=68), TE 30.6% (38), RB target 21.8% (36), RB carry 15.0% (40);
discovery w = 0.7/0.6/0.7/0.4. Pre-registered (WR, RB target > 15%): HELD.
Provenance, both classes: week-1 share and the prior season's share are both known before Week 2; the
outcome is weeks 2-8 (1b clean); the live layer would use the same two inputs (identity: not yet built).
Leakage: w picked on 2021-24 from an 11-point grid, applied once to 2025 - clean, small grid.
**Two caveats before applying it, both Cowork's own fault in the order:**
1. **Survivorship.** "Player-season with >= 8 games" is a FUTURE condition at week 1: it keeps players whose
   role held up and drops the ones who got hurt or benched. Shrinkage toward a prior season looks best
   on exactly that population. The direction is not in doubt; the 22-47% is an upper bound.
2. **Scope.** The gain is vs week-1-ONLY shares. The usage layer uses weeks 1..k-1 by week k, so the gain
   decays through the season; it is a Week-2/3 effect until measured at k = 2, 3, 4. And it exists only
   for players with a qualifying prior season (about half of the discovery sample; "81% have 2025 data"
   on the 2026 board uses a looser definition).
Re-measure (5N item 2) without the games filter and at k = 1..4; then decide.

## Checks
Provenance: item 4 above; items 1-3 are engine mechanics on 2021-24. Leakage: nothing tuned on 2025/2026.
Identity: Linux board == Mac board bit-for-bit; the item-4 estimator is not in the live layer yet.
Economics: none claimed. Aggregates: K1 by metric, item 4 by position and share type. The sim gates
nothing (N54).

## NOT done / UNVERIFIED
- Usage rebuild bit-identity (carried since 5J).
- Whether Q4_mid_b's three thin cells (pass/lead9+, pass/tied, run/tied) are where the tied-expiry residual
  lives - the split moved expiry 0.014 of the 0.038 needed.
