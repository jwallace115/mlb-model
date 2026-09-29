# NHL sim S-WO1 — verification from the files (Cowork, 2026-09-29)

Branch `nhl/sim-s1` (5 commits, 94ac40ad1 .. 025494252), worktree data in `~/mlb-model-nhlsim1`. Checked by reading
the tables, the constants JSON and the code — not the report.

## Holds
- 6,560 play-by-play files (5 x 1,312), all seasons complete. The report's "2025-26 has only ~1,177 completed games"
  is wrong: every 2025-26 regular-season game has been played.
- Goals from the shot table vs the canonical results (all 6,560 games, not the 5,618 the report checked):
  **6,558 / 6,560** match exactly after removing the shootout +1. The 2 misses (2025021229, 2025021230) have
  canonical scores that do not match the NHL's — most likely stale canonical rows; not an event-table defect.
- Shot-row score state is correct (score BEFORE the event, shooter's view).
- xG pre-registrations as reported (not independently recomputed here).

## Wrong — each changes a number the engine would use
1. **state_time score state is the FINAL score on every span.** `build_events.py` writes
   `"score_diff_home": home_score - away_score,  # approximate at this point` after the play loop, so game
   2024020001 (final 1-4) shows -3 from the opening faceoff. Every score-state rate is wrong.
2. **Shootout games carry up to 15 minutes of phantom time.** The span from the last OT play to the first
   shootout play (period 5, 00:00 -> 4,800 s) is counted. Per-game seconds: REG games 3,600 exactly; OT/SO games
   3,604-4,800. The report put null control (c) down to "period boundaries". The real cause is this span. It
   inflates 3-on-3 seconds, so the OT attempt rate is understated.
3. **penalties_per_60_per_team = 225.9.** A units error (per-minute rate x 3,600). The real value is about 3.5-4
   penalties per team per game.
4. **"Score effects" are state frequencies, not rate multipliers.** "attempts at score_diff=-1 period 3 /
   attempts at tied" = 0.774 measures how often teams are down one, not how hard they shoot. The derivation needs
   attempts per 60 in the state (from a correct state_time) divided by attempts per 60 when tied.
5. **pull_en_shots = 0 (n = 0) at -1, -2, -3.** Empty-net attempts are taken by the LEADING team: 313 at +1 and
   324 at +2 in 2022-23, shooter's view. The query used the trailing team's sign.
6. **Rush is False on every row**, yet S5 lists it as a model feature.
7. **Dropped from the order, only partly disclosed:** shootout conversion, pulled-goalie hazard, empty-net rates,
   share of minors ended early, score effects on xG per attempt, SOG-mismatch categories.

The S-WO1 decision entries S3-S6 overstate what landed. Corrections go in S7-S9 (S-WO2), not in edits to S3-S6.
Constants v1 must not be used. Do not merge nhl/sim-s1 into main before S-WO2 (it would publish the bad JSON), or
merge it with the S7 note that v1 is withdrawn — S-WO2 builds on the branch either way.
