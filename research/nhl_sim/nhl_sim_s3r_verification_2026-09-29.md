# NHL sim — S-WO3r verification (Cowork, 2026-09-29 14:43Z)

Branch `origin/nhl/sim-s3r`:
- Commits: 3 cherry-picks (e77e1c5cf, 2178b22a5, a0f06c212), then 3fa82ecce (S13-S14), e78a9e80c (S15) and
  1e7fd8a27 (log).
- The merge-base is current main (66ecbe222).
- The diff is 5 files: ratings.py, sanity_check.py, tests/test_ratings_s13.py, the decision doc and the log. The
  log says 4 files; the test file is the fifth.
- The branch itself is clean.

Verified from the code on origin and from the gitignored outputs in ~/mlb-model-nhlsim3r. Numbers are recomputed,
not taken from the report.

## Reproduced exactly
I re-ran `nhl/sim/sanity_check.py`:

| | 2022-23 | 2023-24 |
|---|---|---|
| games matched to Pinnacle | 1,156 | 1,138 |
| corr(engine goal diff, actual goal diff) | 0.308 | 0.263 |
| corr(engine goal diff, Pinnacle logit) | 0.851 | 0.810 |
| corr(engine total, Pinnacle total) | 0.480 | 0.433 |
| mean total vs actual | -8.2% | -9.3% |
| shuffled null | 0.049 | 0.011 |

The two correlation bars HOLD. The ±3% bar is NOT HELD.

## Measured by Cowork (not in the report)
**Starter agreement: 99.94%.** Checked against the box score's `playerByGameStats.goalies[].starter` flag.
- 12,850 goalie rows; 6 team-games have no single flagged starter.
- The pre-registered > 99% HOLDS.
- The log said this needs a box-score starter field it didn't have. That is false: the field is in every cached
  box score.

**Benchmark on the same games (descriptive).**
- Engine's goal diff vs actual goal diff: 0.292 (fit) / 0.258 (validate).
- Pinnacle logit vs actual goal diff: 0.333 / 0.287.
- On totals: engine 0.105 / 0.064; Pinnacle's line 0.098 / 0.114.
- OLS of actual goal diff on Pinnacle logit plus engine: the engine coefficient has t = 0.63 (fit) and 1.52
  (validate).
- This is not the A1 test (A1 is on probabilities, on the holdout, pre-registered). It only says the ratings are
  not simply a copy of Pinnacle.

## What was fixed
1. **League prior:** now computed per season, strictly before date D. Code-reviewed: `league_at_date[d]` is
   snapshotted before day D is added.
2. **Season boundaries:** team totals reset every season (`n_prior_games = 0` at each season opener).
3. **Holdout-deletion test:** it exists and the log says it passed. Cowork did not re-run it; it needs the
   ~30-minute stats build.
4. **Goalie ratings:** per-season with a career prior.
5. **Finishing-term label:** corrected in the decision doc and log (2025-26 goals ran about 3-9% below xG).
6. **Pinnacle join:** matches build_lines.py's counts. It was re-implemented inside sanity_check.py rather than
   imported.

## Still wrong, or not done
1. **Carry-over is effectively not implemented.**
   - The measured w (0.784 / 0.805) is printed and then never used. The code hardcodes `w = 0.5`.
   - The carried value only sets the game-1 rating. From game 2 onward the rating shrinks toward the league mean
     using in-season games only, so last season is thrown away.
   - Measured in 2023-24: the SD of attempts-for across teams is 2.05 at game 1, 1.42 at game 2 and 1.44 at game 3.
     Last season's information collapses after one game.
   - TOR 2022-23 shows the same thing: 44.64 at game 1, then 42.71 at game 2.
   - Decision-doc S13 says "carry-over measured" as though it were in use. It is not.
2. **The null-control tests are only partly there.**
   - The 1e-12 truncation test was not written.
   - The mutation check (update before record) was not run.
   - "Both tests FAIL on e17ace021" was "verified by checking source code" — nothing was run against the old code.
   - The season-reset test reads a committed parquet file and checks `n_prior_games == 0`. It does not exercise the
     code path.
3. **Not built:**
   - PP/PK team ratings (computed in the per-game table, never rated);
   - penalties taken/drawn (a placeholder line, `pens_taken = len(g_shots)`, is unused);
   - score-adjusted 5v5.
4. **Finishing term** is still reported by month only. There is no per-game, point-in-time column. Decision S14 is
   titled "point-in-time" but it isn't.
5. **S15 formula still simplified:**
   - the same league-average power play for both teams;
   - no finishing term;
   - a flat `+0.35` per team for empty-net and 3v3 goals;
   - goalie factor = 30 × GSAx per attempt, an arbitrary scale.

   The -9.3% miss cannot be put down to the ratings until those are fixed.
6. The chat summary said none of this. The log's NOT DONE list is honest about items 3-5; it does not mention item 1
   (it says carry-over is "measured") or item 2.

## Merge decision
- **Hold `git merge nhl/sim-s3r`.** Nothing is dangerous, but main would carry an S13 that claims working
  carry-over.
- S-WO3c continues on the same branch and worktree. Merge after S-WO3c is verified.

## CHECKS (project discipline)
- **1a / 1b:** point-in-time at the league and team level. The 2021-22 warm-up mean uses its own first 10 days
  (warm-up season only).
- **2:** K and r are measured on 2021-23 only; the holdout is untouched.
- **3:** the ratings are not yet the engine object.
- **4 / 5:** not applicable yet; no bets and no ROI.
