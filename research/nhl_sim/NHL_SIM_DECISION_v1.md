# NHL simulation engine — decision log (v1)

Entries S1, S2, ... Written only by the NHL chat and the NHL sim work orders it writes. Before numbering:
`grep "^### S" research/nhl_sim/NHL_SIM_DECISION_v1.md | tail -1`. Plan: `research/nhl_sim/NHL_SIM_PLAN_2026-09-29.md`.

---

### S1 — Build a game-state hockey simulation as a Layers-System model layer (L4) (2026-09-29)

Jeff, 2026-09-29: "lets build a hockey simulation engine, similar to the nfl sim engine for that layer." His choices
(asked the same day): **game-state sim** (not a scoring-rate model); **game lines first** (moneyline, puck line,
total, 60-minute 3-way; player props in a later phase on the same engine); judged by **beat-or-match Pinnacle** on a
historical point-in-time test before it counts as a layer.
- Role: an L4 layer. It is logged in the packet as a vote with its own probability and GATES NOTHING (plan §3, N54).
  The reader may use it or not; baseline (b) in H1 becomes this engine's number once it exists.
- Context stated plainly: the phase 1-3 edge hunt found nothing in public pre-game information that the closing
  line misses, and the NFL engine lost to the book on its first scored weeks. The expected outcome is "matches or
  trails Pinnacle". The engine is still useful as an explicit, auditable model of HOW games end (empty nets, OT,
  shootouts) and as the base for props, where markets are thinner.
- Lessons carried over from the NFL engine (CLAUDE.md WORK ORDERS): every constant is measured from the repo's
  own data with the derivation written down; every committed artifact has a committed generator; stamps are content
  hashes, never git HEAD; a claim that something is wired is proven by an execution trace; pre-registered
  predictions with a null control; one holdout, locked.

### S2 — Data, seasons, and the test that decides whether it counts (2026-09-29, before any engine code exists)

- Event data: NHL API play-by-play (api-web.nhle.com, free) for regular seasons 2021-22 .. 2025-26, raw JSON cached
  in the gitignored `nhl/cache/pbp/`. Shot quality: our own expected-goals model fitted on 2021-22 + 2022-23 shots
  ONLY and then frozen (MoneyPuck's published xG comes from a model fit on all seasons — a CHECK 1b problem).
- Seasons: 2021-22 = warm-up for ratings and fit; 2022-23 = fit; 2023-24 = validate (realism checks and any
  calibration map are fitted here and nowhere later); **holdout = 2024-25 + 2025-26**, scored ONCE through a lock
  file `research/nhl_sim/HOLDOUT_SCORED.lock` (the scorer refuses to run if the lock exists, and writes it).
  2025-26 outcomes were seen in aggregate during the edge hunt; the sim-vs-Pinnacle relation on it was not.
- Reference prices: Pinnacle de-vigged, last snapshot within 6 h of puck (NHL WO2 history, 2022-23 .. 2025-26).
- Metrics per market (ML two-way, total at Pinnacle's line, puck line +/-1.5, 3-way where priced): log-loss and
  Brier, sim vs Pinnacle, game-cluster bootstrap 90% CI of the difference.
  BEAT = CI entirely below 0. MATCH = CI inside +/-0.005 log-loss. Otherwise TRAILS.
  BEAT or MATCH on ML AND totals -> the engine's number is carried in the packet as a weighted vote.
  TRAILS -> it is still logged (weight 0, flagged) and its defects are the next work order.
- Pre-registered prediction: Pinnacle's log-loss is lower than the engine's on ML and totals in the holdout
  (TRAILS or MATCH, not BEAT).
- Realism gate BEFORE the holdout may be opened (validate season, bands written in the work order that builds the
  engine): goals/game, SD of total goals, P(OT), P(shootout), P(win by 2+), empty-net goals/game, power-play goals
  and opportunities/game, shots/game, each within its stated band of the actual.

### S3 — Play-by-play pull (2026-09-29)

Pulled: 6,560 games (5 seasons x 1,312) from api-web.nhle.com, gzipped JSON to `nhl/cache/pbp/`.
All 6,560 returned HTTP 200 with gameState OFF/FINAL. Every play carries a situationCode (verified
on sample: 349/349 = 100%). 0 credits (NHL API is free). Runtime: ~110 min on Mac.
Host: Mac (VM also passes the NHL API test, HTTP 200). One-off backfill, no cron.
Generator: `nhl/sim/pull_pbp.py`.

### S4 — Event and strength-state tables (2026-09-29)

Built from PBP for all 5 seasons. Generator: `nhl/sim/build_events.py`.
Per season: shots.parquet (~113k rows), penalties.parquet (~10k), state_time.parquet (~320k).
Null controls (all 6,560 games):
- (a) Goals == boxscore minus SO+1: **100.0%** on all seasons (5,618/5,618 with boxscores). PASS.
- (b) SOG == boxscore: 95.6-98.9%. Mismatches are +0.5/side avg — likely penalty-shot or edge-case
  categorisation. Reported, not 100%.
- (c) State time within 5s of reg+OT: 74.8-79.9%. BELOW the 100% target. The inter-play duration
  accumulator does not handle period boundaries and stoppages cleanly. Does not block the sim
  (engine uses its own clock), but the state_time table should not be trusted for per-game totals.
- (d) Empty-net goals: 438-524/season (5.3-6.6% of goals). Consistent.
Tests: 11 pass (parse_situation, time_to_seconds, mutation checks).
