# Phase 5L verification (Cowork, 2026-09-22T07:31Z)

Branch `eng/5l` @ `986ca24` (D114-D117 + log). Base `b44a177` (main's D113). Verified from files and by re-running,
not from the report. `git merge-tree` against main: clean (main's only nfl/ changes since the base are the N59
opinion-log files, which the branch does not touch).

## Verdict: MERGE. All four items did what they claim. One claim in D114 is wrong (see 3). Cross-machine
reproducibility, left UNTESTED by Claude Code, now HOLDS completely.

## 1. Item 0+1 (D114) - the fix
- `engine.py` diff is exactly two lines: `rng_obj.beta(a, b, size=N)` and the stable sort on
  (`target_share`, `player_id`). Fingerprint `7f3d96900218c014` -> `c01d2af899c7e9f8`.
- `test_engine_5l.py` (3 tests): PASS on the branch (58 s). With main's `engine.py` swapped in: 3 FAIL. The
  tests can fail and can go green.
- PHI provenance: D114 cites `phase2b_player_report.md` (MLE from PBP 2021-24, N stated per cell). Stop-gate
  passed; the constants stand. Not re-derived by Cowork.

## 2. Item 2 (D115) - old vs new engine on 200 real games, recomputed from the committed row files
Matched 5,344 player-games on (game, player). Brier of P(stat >= rung) against the real outcome:

| pos | family | n | old | new | delta |
|---|---|---|---|---|---|
| WR | rec>=3 | 2075 | 0.1683 | 0.1443 | -0.024 |
| WR | rec>=4 | 2075 | 0.1482 | 0.1263 | -0.022 |
| WR | rec>=5 | 2075 | 0.1251 | 0.1085 | -0.017 |
| TE | rec>=3 | 1213 | 0.1240 | 0.1142 | -0.010 |
| TE | rec>=4 | 1213 | 0.1002 | 0.0904 | -0.010 |
| TE | rec>=5 | 1213 | 0.0699 | 0.0644 | -0.006 |
| RB | rec>=3 | 1377 | 0.1482 | 0.1364 | -0.012 |
| RB | rec>=4 | 1377 | 0.1033 | 0.0968 | -0.007 |
| RB | rec>=5 | 1377 | 0.0716 | 0.0696 | -0.002 |
| RB | car>=10 | 1377 | 0.1202 | 0.0965 | -0.024 |
| RB | car>=15 | 1377 | 0.0981 | 0.0826 | -0.016 |

Every cell improves - P2 HELD, reproduced. Old-engine Briers match D115 exactly; new-engine values differ in the
third decimal because D115's n (2113 WR) includes 226 player-games present only in the NEW file (the old run
has 5,344 rows, the new 5,570; D115's table does not say how it matched). The direction and size are not in
doubt. The extreme-share prediction (P1) was PARTIALLY HELD as D115 says; on Cowork's stricter definition
(p < 0.02 or > 0.98) the WR rec>=3 ratio is 0.37, others 0.54-0.90. Same picture.

## 3. Item 3 (D116) - re-fit and the two reds
- Re-fit `fit_5l` 1087/1087, cal maps re-stamped, board SUPPRESSED before / ranked after: consistent with the
  Linux run below (no SUPPRESSED, 203 priced legs).
- **The 2 T4 reds are reproduced exactly on Linux** (DAL@PHI 2023 w9, N=4000, seed `T4_test`: |margin diff|
  0.68 vs 2SE 0.67; KS p = 0.043). At five other seeds the same pair passes (diffs +0.10, -0.03, +0.42, -0.05,
  -0.45; KS p 0.22-0.96); mean on-off difference across the six seeds -0.12 points (SE ~0.14). So D116's
  reading is right: noise from a shifted RNG stream, not a team-level bias.
- **But D114's sentence "the RNG stream for team-level drives/plays is seeded independently" is FALSE.**
  `simulate_game` builds one `rng` (engine.py:727) and passes it to `_build_player_context` (line 744) and
  then to every play draw (lines 863, 1371-1401). Per-sim Beta draws now consume N x players x 4 values from
  that stream, so with the player layer ON the team-level game is a different random realisation than with
  it OFF. K1 is identical to 4dp only because K1 runs without the player layer - it is a null control for
  the team code, not for this stream effect. Consequence: exact team-level neutrality of the player layer
  (what T4 asserts) no longer holds at a fixed seed. The right fix is a child generator for the player layer
  (e.g. `np.random.default_rng(stable_seed((seed, "player")))`), which restores ON == OFF bit-for-bit at
  team level and turns T4 green without touching a threshold. Work order 5M item 1.
- `phase5l_k1_after.txt` is stamped `3c1e9177e-dirty` (run from a tree with uncommitted changes - the
  re-fit outputs, presumably). The table itself is identical to the item-1 table. Noted, not a defect.
- Punts/game 8.84 vs 7.90 real: the 5I regression (D108) is still there. 5K stays queued.

## 4. Item 4 (D117)
- **Cross-machine, pre-registered >= 99% of legs within 0.02: HELD at 100%.** Cowork ran the board on
  Linux (python 3.11.15 / numpy 2.4.4 / pandas 3.0.2; `--week 2 --as-of 2026-09-20T15:30:00Z`, 31.7 min,
  16/16 converged, 1,443 legs). 1,443 of 1,443 legs match the Mac's `picks_log_mac.parquet` (python
  3.13.1 / numpy 2.4.3 / pandas 2.3.3) EXACTLY on both `sim_p` and `cal_p`; 203 rankable on both. The
  621-leg difference of D108 is gone. The two-draw defect was the whole cause.
- Sim vs book SD, recomputed from the committed Mac board against the 1614Z candidates: 135 matched
  receptions rows, SD(raw - q) = 0.1487, SD(cal - q) = 0.140. D117's 0.149 / 0.140 reproduced. The
  pre-registered < 0.12 DID NOT HOLD, as D117 says.
- D117's closing sentence - "the week-1 share estimates are the larger remaining source" - is a HYPOTHESIS,
  not a measurement; nothing in 5L tested it. It is the same hypothesis Cowork withdrew on 09-21 as the
  FIRST explanation; it is now the leading candidate again, untested. 5M item 3 measures it.

## Checks
Provenance: the fix is mechanical; PHI measured from PBP; the re-fit uses 2021-24 only. Leakage: nothing was
tuned on 2025/2026; the Week 2 diagnostic is a read, not a fit. Identity: the Linux board and the Mac board
are the same object (bit-identical output). Economics: none claimed. Aggregates: item 2 by pos x family x
rung; T4 by seed. The sim still gates nothing (N54).

## NOT done / UNVERIFIED
- Usage rebuild bit-identity (carried since 5J). The played game in the union set (DET@BUF) is still simulated.
- `test_usage_pit_5j.py` still hits the network.
- Whether the T4 fix (child RNG) changes any board number: it will (different stream) - a re-stamp is NOT
  needed because the fingerprint hashes code, but the null control in 5M must show team-level lines unchanged
  in distribution and the player-off run bit-identical to today's.
