# NHL sim — S-WO4a verification + Cowork engine rewrite (2026-09-29 19:37Z)

S-WO4a's own branch commits: e5bada048 (S32), c3f2b07be (S33), 31779fcdc (log). Main now carries the S23-S31 squash
(0a0783aa3).

## What held in S-WO4a
- The engine skeleton: vectorised, 1-second clock, start_state, determinism.
- The runtime pre-check was done (3.05 s per game at 10k sims).
- The realism bands were reported, with 5 NOT HELD, and nothing was tuned.

## What was wrong
- **Hard rule broken.** Away-team goalie pulls and overtime penalties sat under "NOT DONE", which is a partial item.
- **The away team could never pull.** That alone accounts for most of the home-win and one-goal failures (S34).
- **Every penalty (majors, misconducts) created a power play,** and the home goal-per-attempt effect was applied
  twice.
- **"No literal rates (grep)" was false:** there were ~20 `.get(..., literal)` defaults.
- **constants_v6.json had no generator,** and the realism script was not committed.
- **The log's diagnosis was speculation** ("Poisson clustering needs variance inflation"). The failures were defects.

## What Cowork did
Decisions S34/S35:
- build_constants_v7.py;
- engine.py rewritten;
- realism_report.py committed;
- test_engine.py extended to 11 tests; the new pull test fails on S32.

**Realism: 6 of 9 HELD.** Still NOT HELD:
- PP goals -12.5%, root-caused to a state_time artifact (a PP persists until the next play after its penalty
  expires);
- ties -3.0 pts;
- the total-goals distribution (max diff 0.017).

## Merge decision
**Not yet.** S-WO4a2 fixes the state_time artifact at its root in build_events.py. That changes the constants and
ratings, so the whole chain gets rebuilt and re-verified before anything merges.

## CHECKS
- **1b:** the engine takes only constants from fit seasons.
- **2:** the realism check is in-sample on 2022-23 by design (mechanics); 2023-24 is untouched by S-WO4a/S34.
- **3:** the engine and its inputs come from committed generators (v7). v6 is superseded.
- **4 / 5:** not applicable yet.
