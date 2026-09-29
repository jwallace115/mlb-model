# NHL sim — S-WO3d verification (Cowork, 2026-09-29 16:30Z)

Branch `origin/nhl/sim-s3r`, commits 42b1f7fcf (S20-S22) and 1e7ac1721 (log).

The worktree files are byte-identical to the commit (md5 checked for ratings.py, test_ratings_s18.py,
constants_v3.json, carryover_w.json and manifest.json).

## Holds (checked by Cowork)
**Manifest matches the files on disk.** The sha256 of each of these is identical to manifest.json:
- ratings.py (c319b3b6…);
- carryover_w.json (fe456696…);
- team_ratings.parquet (8dec4b79…);
- goalie_ratings.parquet (2f8d9e51…).

The goalie object can be rebuilt from the branch again (CHECK 3 restored for ratings).

**Tests, re-run by Cowork** (`pytest test_ratings_s18.py`):
- truncation passes;
- the mutant is detected;
- starter agreement is **12,842 / 12,844 = 99.98%**.
- The e17ace021 test skipped in Cowork's sandbox only because git can't run inside the mounted worktree. On Jeff's Mac
  it ran; the report shows 20 passed and 0 skipped.
- Separately, e17ace021's `compute_pit_ratings(tgs)` runs with default arguments. So the old-code test is a real
  comparison, not a vacuous pass through its `except: return` branch.

**Goalie ratings:**
- Code review: the rating is recorded before the game's totals are added (point-in-time).
- The carried-over prior is the season-long shrink target.
- Goalie w is measured at **0.144** (the literal 0.3 is gone).
- No `.get(..., default)` fallbacks remain; a missing weight raises.

**constants_v3:**
- 5v4 power-play side 70.35 attempts / 60; short-handed side 12.30.
- Power-play minutes 5.30 per team-game; 5v5 48.13 minutes per game (fit seasons).
- Null controls pasted: the two sides sum to 2 × v2 to 1.4e-14; 5v5, 4v4 and 3v3 are identical to v2.
- 4 / 4 pre-registrations HELD.
- This fixes the averaging defect Cowork found in S-WO3c.

## Wrong or incomplete
1. **"xg_per_attempt" is actually goals per attempt** (shooting %), in v3 and already in v2. The derivation strings
   say "goals / attempts".
   - The ratings use real xG from the xG model; the constants use realised goals. They share a name and would be
     mixed up in the engine.
   - The 6v5 short-handed "xg_per_attempt" of 0.63 is empty-net goals per attempt.
   - The pre-registration "PP-side xG/att > 0.0945" was really goals/att. It holds either way.
   - Needs: separate `goals_per_attempt_*` and true `xg_per_attempt_*` for every state.
2. **The power-play split uses only home power plays** (the home-5v4 state), which is half the sample and
   home-specific. It should pool home 5v4 with away 5v4 (the 4v5 state).
3. **Goalie ratings were not added to the truncation test.** The order required it. The log's "NOT DONE: (empty)"
   is therefore not accurate.
4. **The mutant is a hand-written re-implementation, not a patch of the real code.** It's disclosed in UNVERIFIED.
   The reason given (a string-replace whitespace problem) doesn't hold: Cowork patched the real file with an exact
   6-line match in S-WO3c. It proves the harness can detect a leak; it doesn't prove a leak in *ratings.py* would be
   caught. Low severity, because Cowork's real-file mutant already failed 20/20.
5. **Branch history.**
   - The log says `git diff origin/main...HEAD` "lists 6 files". Against current main it lists 58, because the
     branch still carries duplicate verification commits and auto commits.
   - The *content* is clean. Limited to the 9 sim paths, the branch vs main is 9 files, +1,917 lines, no deletions,
     and main hasn't touched any of them since the branch point. No file is over 500 KB.
   - So: bring the content in as one clean commit rather than `git merge`.

## Merge decision: YES, squash the 9 paths onto main
What's there is verified:
- point-in-time team and goalie ratings, with tests that can fail;
- a manifest;
- constants with each side of uneven-strength states measured separately.

What's missing (items 1-3 above, PP/PK ratings, score adjustment, the finishing term, the full formula) goes to
S-WO3e / S-WO3f from fresh main. Retire branch nhl/sim-s3r after the squash.

## CHECKS
- **1b:** clean. Team ratings pass the truncation test; goalie ratings are point-in-time by code review, with the test
  pending in S-WO3e.
- **2:** carry-over weights are measured on 2021→22 only; K on 2021-23; constants on 2021-22. No validate or holdout
  data is used in fitting.
- **3:** manifest verified.
- **4 / 5:** not applicable yet (no pricing).
