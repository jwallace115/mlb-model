# NHL sim — S-WO3e verification (Cowork, 2026-09-29 17:12Z)

The squash of S13-S22 is on main (5d535bc93).

Branch `origin/nhl/sim-s3e`: 27c8e6220 (S23), 48da1fa9f (S24), c38b24d15 (log).
- The diff against main is clean: 6 files — constants_v4.json, manifest.json, ratings.py (+20 lines), the tests, the
  decision doc and the log.
- Checked from the code on origin and the gitignored outputs in ~/mlb-model-nhlsim3e.

## Holds
- **Setup:** the sha256 of the copied parquets matches manifest.json.
- **Tests:**
  - the mutant now patches the REAL ratings.py source;
  - 23 passed, 0 skipped on the Mac.
- **constants_v4:**
  - goals per attempt and xG per attempt are separate fields for every state;
  - uneven states pool both orientations: the power-play side is 69.8 attempts / 60, pooled home + away parts shown;
  - pooled power-play time is 5.11 min per team-game (home-only was 5.30; away 4.92).
- **Calibration pre-registration HELD** (5v5 goals/xG 1.0000; PP 0.98). Caveat: this is close to tautological.
  xg_v2 is a logistic regression fit on these same seasons, and its maximum-likelihood fit makes predicted and
  actual totals match by construction.

## New defect found by Cowork: the xG merge double-counts shots (affects every rating since S-WO3r)
`build_game_stats_vectorised` attaches xG with this merge:

```
shots_all.merge(non_en[[game_id, period, seconds, shooting_team, xg]].drop_duplicates(),
                on=[game_id, period, seconds, shooting_team])
```

- When one team takes two shots in the same second (rebounds, scrambles), each shot matches both xG rows, so the
  shot is counted twice.
- Rows sharing a key per season: 1,036 / 1,072 / 712 / 716 / 628.
- 2023-24, 5v5:

| | event table (truth) | team_game_stats |
|---|---|---|
| attempts | 89,391 | 89,944 (+553, +0.6%) |
| goals | 5,332 | 5,336 |

- **This also explains constants_v4's 5v5 numerator.** v4 has 179,636 against v2/v3's 178,012, and the difference
  is about the number of duplicated-key rows in 2021-22. The log's explanation ("denominator computation") is
  wrong; the denominators are identical (7,576,874).
- The inflation isn't uniform: it lands on teams that generate more rebound and scramble sequences. It's small, but
  it's a real bias in the ratings.
- The goalie path scores `non_en` directly, so goalie ratings are not affected.

## Wrong or not done
1. **No generator for constants_v3 or constants_v4.** Neither `constants_v3` nor `constants_v4` appears in any
   committed .py file in the whole git history. Both JSONs were written by code that was never committed.
   - Cowork missed this for v3 in the S-WO3d verification; it was squashed onto main without a generator.
   - v4 is also built from the double-counted shots.
   - v3 and v4 fail provenance. Mark both superseded; v5 must come from a committed generator.
2. **The null controls failed and were explained away.**
   - (a) did not reproduce v3's home-only numbers; (c) 5v5 42.68 vs 42.29.
   - The log called the gap "ice-state parsing" / "denominator computation" and carried on. The order said to paste
     them; the stop condition applied to the calibration test only. The real cause is the defect above.
3. **S24 is about 20% done.** The PP/PK/penalty "ratings" are:
   - raw running totals with no shrinkage, K or carry-over;
   - hardcoded defaults (7.0, 3.8) when a team has no data — literal constants of exactly the kind S21 removed;
   - penalties per 60 divided by **5v5 seconds** (`ev_seconds`). The log says "total game time"; it isn't.
   - Split-half r/K not reported.
   - The score adjustment was not built, for the third order running, with the same reason ("requires a pipeline
     change"). The pre-registration is NOT TESTED.
4. **Goalie ratings are still not in the truncation test**, for the second order running. The log lists it under
   UNVERIFIED, not NOT DONE.
5. The chat summary said "Point-in-time, per season" and "All 3 items done"-style framing again. The log's NOT DONE
   list was more honest, but still incomplete (item 4).

## Merge decision
**Do not merge nhl/sim-s3e.**
- Its constants_v4 is double-counted and has no generator.
- Its PP/PK ratings are placeholders.
- The test improvements are good and carry forward.

S-WO3f continues on the same branch and worktree, with code-level instructions.

## CHECKS
- **1b:** team ratings are point-in-time (truncation test). The new PP/PK columns are recorded before the update
  (point-in-time), but they are not in the test.
- **2:** fit seasons only.
- **3:** FAILING. There is no generator for v3/v4, and v4 differs from what the committed code would produce.
- **4 / 5:** not applicable yet.
