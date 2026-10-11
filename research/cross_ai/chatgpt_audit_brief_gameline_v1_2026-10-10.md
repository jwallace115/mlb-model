# ChatGPT Audit Brief — Game-Line Baseline + Unanchored Engine v1

**Date:** 2026-10-10
**Pinned to commit:** `aad7f9699` (GL1 Item 3: shape test)
**Requested by:** Jeff (GL1 work order, Item 4b)
**Lane:** eng/gl1

---

## Scope

Return ALL findings in each of the following classes. Do not summarize; list every
instance.

### Class 1a: Feature provenance (live signal pre-first-pitch)

For every feature in `nfl/sim/gameline_baseline.py`'s `build_feature_row()`:

1. Name the feature.
2. Trace its data source to the PBP column(s) it ultimately reads.
3. State whether that PBP column is available before the first pitch of the game
   being predicted (yes/no/conditional).
4. If conditional, state the condition (e.g., "available after the prior week's
   games are final").

The 10 margin features are:
- `pass_epa_home_adv` = home pass_off_epa − away pass_def_epa
- `pass_epa_away_adv` = away pass_off_epa − home pass_def_epa
- `rush_epa_home_adv` = home rush_off_epa − away rush_def_epa
- `rush_epa_away_adv` = away rush_off_epa − home rush_def_epa
- `pass_success_home_adv` = home pass_off_success − away pass_def_success
- `pass_success_away_adv` = away pass_off_success − home pass_def_success
- `rush_success_home_adv` = home rush_off_success − away rush_def_success
- `rush_success_away_adv` = away rush_off_success − home rush_def_success
- `qb_diff` = home primary QB EPA − away primary QB EPA
- `home_field` = 1.0 (constant)

The 5 total features are sums of the same EPA/success terms plus QB sum.

Each EPA/success rating is computed by `_build_team_rating_as_of()` which calls
`_build_game_aggs()` on PBP plays filtered to `week < w` for the current season
and all plays for the prior season.

### Class 1b: Feature provenance (point-in-time training)

For the same features:

1. Were training features built point-in-time, or from end-of-season aggregates?
2. Is the `week < w` filter applied consistently for both the current season and
   the prior season?
3. Does the prior-season component use full-season data (which is available before
   the current season starts, so this is legitimate)?
4. Is there any path where a feature for game (s, w) could incorporate data from
   week w or later in season s?

The truncation test (`test_gameline_gl1.py::TestTruncationEquivalence`) asserts
byte-identical features from full vs. truncated data at 6 (s,w) pairs plus a
negative control. Verify whether this test is sufficient or has gaps.

### Class 2: Week-level as-of sufficiency

The as-of rule is: for (season s, week w), use only plays from (season < s) or
(season == s AND week < w).

1. Is this sufficient for NFL scheduling? (Games within the same week can be
   played on different days — Thursday, Sunday, Monday.)
2. Could a Sunday game's features incorporate Thursday's results from the same week?
   (Answer: yes, because `week < w` excludes the current week entirely, including
   Thursday. But verify this is correct — Thursday games ARE excluded.)
3. Is there a scenario where this is too conservative (excludes data that is actually
   available before kickoff)?

### Class 3: Ledger honesty

Review `research/nfl_sim/FIT_WINDOW_LEDGER.md`:

1. Is the CONSUMED status for 2021-23 game-line honest? What exactly was seen?
2. Is the UNTOUCHED status for 2024 game-line defensible? Could any file in the
   codebase have been produced using 2024 game-line data in a way that leaks into
   the baseline or engine?
3. Is the NOT BLIND status for 2025 correct? What specifically touched it?
4. Are there any missing entries (seasons or purposes that were looked at but not
   recorded)?

### Class 4: Research object == live object

1. Is the engine object run in `run_gameline_gl1.py` (Item 2) the same engine that
   `run_week.py` uses for live forward predictions? Same `simulate_game()`, same
   `_run_chunks()`, same tables, same ratings?
2. Is the baseline model in `gameline_baseline.py` structured so that the research
   fit and the live predict use the same code path? (Currently: `fit_baseline()`
   returns models that `predict_baseline()` consumes. Are there any formula
   differences between the training and prediction paths?)
3. Does the engine fingerprint in the forward protocol match the engine fingerprint
   in the live run?

### Class 5: Forward protocol gamability

Review `research/nfl_sim/GL_FORWARD_PROTOCOL_v1.md`:

1. Can freeze timing be gamed? (E.g., run the engine on 2026 data, see results,
   then "freeze" with a favorable snapshot.)
2. Is the append-only constraint enforceable?
3. Is 125 games (≈8 weeks) sufficient for the mixed-regression c to be meaningful?
   (Power analysis: at what effect size does c become detectable with N=125?)
4. Is there a path where forward results could leak back into the baseline or
   engine tuning?
5. Does the PILOT → PRIMARY gate have clear, falsifiable criteria?

---

## Files to Read

1. `nfl/sim/gameline_baseline.py` — the baseline model (all feature construction)
2. `nfl/sim/tests/test_gameline_gl1.py` — truncation and season-membership tests
3. `nfl/sim/run_gameline_gl1.py` — the unanchored engine runner
4. `nfl/sim/ratings.py` — the rating system (prior_regression, prior_weight, shrinkage)
5. `nfl/sim/anchor.py` — `_run_chunks()` (the unanchored sim path)
6. `nfl/sim/engine.py` — `simulate_game()` (the engine itself)
7. `nfl/sim/calibration.py` — `engine_fingerprint()`
8. `research/nfl_sim/FIT_WINDOW_LEDGER.md` — the ledger under audit
9. `research/nfl_sim/NFL_GAMELINE_DECISION_v1.md` — G1, G2, G3 decisions
10. `research/nfl_sim/GL_FORWARD_PROTOCOL_v1.md` — the forward protocol
11. `research/nfl_sim/GL1_report_2026-10-10.md` — the report

## Output Format

For each class, list every finding with:
- **FINDING-{class}-{n}**: one-line summary
- **Detail**: what you found, where, and why it matters
- **Severity**: CRITICAL (blocks deployment) / HIGH (must fix before PRIMARY) /
  MEDIUM (should fix) / LOW (cosmetic or theoretical)
