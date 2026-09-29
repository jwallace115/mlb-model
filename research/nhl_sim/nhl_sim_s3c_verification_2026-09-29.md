# NHL sim — S-WO3c verification (Cowork, 2026-09-29 15:47Z)

Branch `origin/nhl/sim-s3r`, commits:

| commit | what it touched |
|---|---|
| 65fc3dea0 (S16) | ratings.py, carryover_w.json, decision doc |
| a82a48c0f ("S17-S19") | the decision doc only — no code |
| f005da588 | the log |

- `sanity_check.py` is byte-identical to S-WO3r's version (md5 ce53252d…).
- Every number below was run by Cowork on the Mac worktree, from the committed code and the gitignored caches.

## Cowork ran what S-WO3c deferred
These are the S18 tests the work order required. The log said they needed "~17 min"; one full ratings rebuild
from the cache takes **1.4 s**.

**Vectorisation null control: HOLDS.**
- I rebuilt the old `build_game_stats` (3fa82ecce) season by season, 43 s per season.
- Compared with the new `team_game_stats.parquet`: 12,850 / 12,850 rows. Every shared column matches: max diff
  1.8e-15 on xG, 0 elsewhere.

**Truncation test: HOLDS on the new code, and it can fail.**
- Method: 20 dates in 2023-24 (seed 20260929). For each date D:
  - drop every row after D;
  - replace D's own stats with garbage (×7 + 3);
  - rebuild, and compare the ratings on D with the full run.

| code | failing dates / 20 | max diff |
|---|---|---|
| new code (f005da588) | 0 | 0.0 |
| S-WO3r code (3fa82ecce) | 0 | 0.0 |
| MUTANT: totals updated before the rating is recorded | 20 | 3.30 |
| OLD code (e17ace021, all-season league mean) | 20 | 0.010 |

- The test passes on clean code and fails on both leaks.
- The test script is in Cowork's scratch space; S-WO3d commits it to the repo.

**Carry-over (S16): FIXED.**
- The code reads carryover_w.json. The carried prior is now the shrink target for the whole season.
- SD across teams of attempts-for in 2023-24, by games played so far: 3.05 (0 games), 3.34 (1), 3.25 (2),
  3.41 (10), 3.22 (40). No collapse after game 1. The S16a pre-registration HOLDS (ratio 1.095).

**S19 reproduced exactly (2023-24):**
- actual goal diff 0.256;
- Pinnacle logit 0.842;
- totals 0.474;
- mean total -8.9%;
- null 0.018.

## Wrong or not done
1. **The goalie rating code was deleted.** `build_goalie_ratings` is gone from ratings.py.
   - `goalie_ratings.parquet` (14:05) was built by S-WO3r code that no longer exists at HEAD, and S19 used it.
     The research object can't be rebuilt from the branch (CHECK 3).
   - Goalie carry-over is the literal 0.3 written into the JSON ("not measured", per the log's own UNVERIFIED list),
     even though `measure_goalie_carryover()` exists and is never called.
   - `carryover.get(..., 0.5)` fallbacks are still in the code. The "no literal w (grep confirmed)" claim is false.
2. **S17:** PP/PK/penalty stats are now in the per-game table, and are correct (the null control holds). But no
   PP/PK/penalty RATINGS were built, and there is no score adjustment. The pre-registration was not tested.
3. **S18:** none of the tests are in the repo. Cowork ran them (above).
4. **Finishing term:** still not point-in-time per game.
5. **S19** is the S15 formula with the new team ratings. The decision doc says "Same formula", honestly; the chat
   summary called it "full". PP opportunities per team, the finishing term, the goalie scaling and measured
   EN/3v3 are all still undone.
6. **S16b NOT HELD, and it matters for Jeff's point.**
   - Carry-over raised agreement with Pinnacle (0.810 → 0.842) but not with outcomes: actual goal diff went from
     0.308 to 0.310 on fit, and from 0.263 to 0.256 on validate.
   - The ratings moved toward the market, not toward the results. A1's rule stands: outcomes decide.
7. **Branch history.**
   - The branch carries a duplicate of main's S3r-verification commit (a3809b2ab = c448b8350) and several auto
     commits.
   - `git diff origin/main...branch` shows 27 files, including soccer caches and `shared/last_updated.json`.
   - Rebase onto origin/main before any merge. The diff must then be only nhl/sim, the decision doc, the log and
     tests.

## NEW DEFECT found by Cowork: constants_v2 averages both sides of uneven-strength states
- `attempt_rate_per_60_per_team_5v4 = 41.32`. Its derivation: "both teams' unblocked attempts in 5v4 / seconds / 2".
  The same applies to 4v5, 5v3, 6v5, 5v6 and 4v3.
- In a 5-on-4 only one team is on the power play. Averaging the power-play and short-handed sides gives a number
  that describes neither.
- Measured on 2023-24 events (descriptive):
  - the power-play side generates **71.2 / 60** (73.1 in the per-game table), at 0.103 xG per attempt (constant:
    0.0945);
  - each team gets **5.31 PP min per game** (formula: 3.8);
  - 5v5 is **47.6 min per game** (formula: 50).
- Arithmetic:
  - correct PP xG ≈ 2 × 73.1 × 0.103 × 5.31 / 60 ≈ 1.33 per game, vs the formula's 0.50: **+0.8**;
  - 5v5 minutes: **-0.2**;
  - net ≈ +0.6 goals per game against a 0.56 gap (5.67 vs 6.23).
  - **The -8.9% miss is the constant, not the ratings.**
- **This would have gone straight into the S-WO4 engine:** a game-state sim running power plays at 5v5 volume.
  It must be fixed first (constants_v3, side-specific).
- Caveat: this diagnosis used 2023-24 aggregates, so the ±3% mean-total bar on 2023-24 is **no longer a blind
  test**. Any future pass on it counts as a consistency check only; calibration is judged on the holdout.

## Merge decision
**Still hold.** Before merging:
- rebase;
- commit the tests;
- restore the goalie code;
- constants_v3.
S-WO3d does these and nothing else. The order is smaller on purpose: three orders in a row came back roughly half
done.

## CHECKS
- **1b:** clean. Ratings are point-in-time; the truncation test and the mutant prove it.
- **2:** constants_v2 was fit on 2021-22; validation is contaminated only as noted in the caveat.
- **3:** FAILING. The goalie object can't be rebuilt from HEAD.
- **4 / 5:** not applicable yet.
