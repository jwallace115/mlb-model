# NHL sim — S-WO3g verification (Cowork, 2026-09-29 18:53Z)

Branch origin/nhl/sim-s3e (after Jeff's force-push, clean on top of main): 45cc81125 (S28 review), ee48334b2 (S29
finishing term), 548cd7a4c (S30 check), a26ffd5d2 (log). The diff against main is 14 files, all in the sim paths.

## Holds
**S30 formula (sanity_check_v2.py) follows the order's equations:**
- lg_-relative 5v5;
- power-play minutes from the penalty ratings;
- power-play and penalty-kill terms;
- short-handed, 4v4 and 3v3 xG at league rates;
- goalie factor 1 - rating/q;
- F(D);
- 6v5 / empty-net at half the league per-game rate;
- actual total excludes the shootout goal.

Every constants_v5 key it reads exists, so its silent defaults never fired.

**S30 results (one run, 2023-24):**

| | engine | Pinnacle |
|---|---|---|
| corr with actual goal diff | 0.274 | 0.287 |
| corr with actual total | 0.032 | 0.116 |

- corr(engine goal diff, Pinnacle logit) 0.898: bar HELD.
- corr(engine total, Pinnacle total) 0.295: bar NOT HELD (0.30).
- Mean total -0.7%. This is a consistency check, not blind.
- The month and games-played breakdowns were printed by the script; the log doesn't paste them.

## Wrong
1. **S29's F has no committed generator,** and it used in-season windows of 38+ games. Cowork's 300-game rule was
   unreachable (a 30-day window holds a median of 210 games), so Cowork's spec was wrong. But the deviation was not
   reported, and the order's truncation test and mutant were not written ("NOT DONE"). The hard rule was broken
   again.
2. **S28 "independent review" found no defects but wrote no test.** A "no defects" claim without evidence is an
   opinion, not a review.
3. **Unrequested goalie-factor clip [0.5, 1.5].** It never binds (the factor is about 1 ± 0.05), so it's harmless,
   but it wasn't in the spec.

## Cowork fixed (S31)
F is rebuilt in ratings.py from goalie_games.parquet:
- min 150 games in the window, or the previous season's last 30 days;
- tested: truncation passes; the window-includes-D mutant fails; the rules hold;
- 15 tests pass.

S30 is not re-run.

## What the S30 run says about next steps (fit-season diagnostic, descriptive)
- **Goal difference:** the ratings are already close to Pinnacle on actual outcomes (0.274 vs 0.287).
- **Totals are weak.** Only the 5v5 part carries signal (0.076 on 2022-23). Power-play minutes vary a lot (SD 1.4 min)
  and predict nothing, and the goalie term has the right sign but is small.
- Totals are hard for Pinnacle too (0.10-0.12).
- The engine phase decides, on outcomes (A1), what goes in. Nothing is dropped now.

## Merge decision
**YES: squash the sim paths from nhl/sim-s3e onto main.** Ratings, constants_v5, F, tests and the S30 script are all
verified or reproduced. S-WO4a starts from main.

## CHECKS
- **1b:** all ratings and F are point-in-time and tested, including fit-season truncation.
- **2:** hyperparameters and constants come from 2021-23. 2023-24 was used once for S30. The 2023-24 mean-total bar
  is contaminated (the earlier diagnosis).
- **3:** the manifest covers code, hyperparameters, inputs and outputs, including F.
- **4 / 5:** no pricing yet.
