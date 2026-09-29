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

### S5 — Own expected-goals model, frozen (2026-09-29)

Logistic regression on 225,912 non-empty-net unblocked attempts from 2021-22 + 2022-23.
Features: distance, angle, shot type (8 one-hot), rebound, rush, strength group (PP/PK/3v3).
Generator: `nhl/sim/fit_xg.py`. Output: `nhl/data/sim/xg_v1.json`.

Pre-registered checks (all predictions written BEFORE looking at numbers):
- Calibration slope 0.9-1.1 on 2023-24: **0.978 — HELD**
- sum(xG)/goals within +/-5% on 2023-24: **0.998 — HELD**
- AUC above 0.72: **0.7496 OOS — HELD**
- NULL CONTROL: shuffled AUC 0.50 +/- 0.01: **0.5053 — HELD**

sum(xG)/goals by season: 2021=0.983, 2022=1.018, 2023=0.998, 2024=1.013, 2025=1.068.
2024-25 and 2025-26 are REPORTED only — nothing refitted on them.
sha256: f18728ec7da3f4fe662e9c8334fd225816921fc42e6947491090f05cb142c539.

### S6 — Measured league constants (2026-09-29)

Fitted on 2021-22 + 2022-23 (2,624 games). Generator: `nhl/sim/build_constants.py`.
Output: `nhl/data/sim/constants_v1.json`. Manifest: `research/nhl_sim/constants_v1_manifest.md`.

Pre-registered checks:
- PP goals per 60 of PP time: **6.94 — HELD** (expected 6-8). Bug found and fixed: initial
  calculation counted only one team's PP time (13.4), corrected to include both teams' PP.
- Home share of unblocked attempts: **51.44% — HELD** (expected 50.5-52.0%).
- Shootout per-attempt conversion 28-35%: **NOT MEASURED** — shootout plays excluded from
  the shots table (periodType SO filter). Needs a separate shootout parser in S-WO2.
- Pull hazard at -1 in last 3:00 (>80%): **NOT MEASURED** — the empty-net detection from
  situationCode captures shots against an empty net, not the moment of the pull. Needs
  state-transition tracking in S-WO2.

2023-24 validate_drift reported beside fit values (not used in engine).
sha256: 32aa748bd643bb4593a62fb9fa83fef3673fd0cd0ed81301830e65f67a5db3d1.

### S7 — State timeline rebuilt (2026-09-29, S-WO2 Item 1)

**What S3-S6 got wrong** (per nhl_sim_s1_verification_2026-09-29.md):
1. state_time score was the FINAL score on every span (defect #1) — now running score.
2. Shootout games had phantom spans (4,800s instead of 3,900) — now SO excluded, period-end caps.
3. penalties_per_60 was 225.9 (units error) — constants_v1 withdrawn, v2 in S8.
4. Score effects were state frequencies, not rate multipliers — fixed in S8.
5. pull_en_shots=0 at -1 (wrong sign) — fixed in S8.
6. Rush was False everywhere — fixed: detects zone transitions from PBP.
7. Shootout/pull/empty-net constants not measured — addressed in S8.

**Rebuilt:** `nhl/sim/build_events.py` — state timeline now walks plays in order with running
score, emits spans capped at period boundaries, excludes shootout. Rush feature reads zoneCode.

**Null controls (all 6,560 games):**
- (a) Goals == boxscore: 100.0% (6,218/6,218 with boxscores).
- (b) SOG match: 95.6-98.9%.
- (c) State time within 2s: **100.0%** (was 75-80% on S-WO1). FIXED.
- (b2) First span score_diff == 0: **100.0%** (was the FINAL score on S-WO1). FIXED.
- (c2) Last span score == final regulation diff: 99.7-100.0%.
- (d2) Home goalie out while not trailing: 270-391 spans/season, median 4-7s (delayed penalties).

**Tests:** 3 new (opening score=0, shootout seconds=3900, score_diff=-2 before third goal).
All 3 FAIL on 025494252: old code gives score=-3, seconds=4800, and no -2 spans.

### S8 — Constants v2, as rates (2026-09-29, S-WO2 Item 2)

Fitted on 2021-22 + 2022-23 (2,624 games). Output: `nhl/data/sim/constants_v2.json`.
v1 withdrawn and marked in manifest. Generator: `nhl/sim/build_constants.py`.

Pre-registered checks (all predictions written BEFORE looking at numbers):
- Penalties per team per game 2.8-4.5: **3.77 — HELD**
- Trailing-by-1 3rd period 5v5 attempt mult > 1.05: **1.076 — HELD**
- Leading-by-1 3rd period 5v5 attempt mult < 0.95: **0.907 — HELD**
- >80% of pulls at -1 in last 3:00: **93.9% (n=1,056) — HELD**
- Shootout conversion 28-35%: **32.3% — HELD**
- OT decided share 55-75%: **66.6% — HELD**

All 6 pre-registrations held.

NULL CONTROL: old state_time gives first-span score != 0 (the FINAL score), and the old
penalty formula gives 451.8 (outside any band). New data: first-span score = 0 on 100%
of games, penalty rate = 3.77 (within band).

sha256: 188c0dec7022a39ecca645193c6a5f6ccfa8c8537ad8c05a3fb2ebff9c51c74b.

### S9 — Rush feature, xG v2, SOG mismatches (2026-09-29, S-WO2 Item 3)

**Rush feature:** detects zone transitions from PBP zoneCode. Rate: 9.4% of attempts.
Rush goal rate 10.2% vs non-rush 6.9% (1.48x multiplier).

**xG v2** (same model, now with real rush instead of all-False):
- Calibration slope 0.9-1.1 on 2023-24: **0.949 — HELD**
- sum(xG)/goals within +/-5% on 2023-24: **1.003 — HELD**
- AUC above 0.72: **0.7462 OOS — HELD**
- NULL CONTROL: shuffled AUC 0.50+/-0.01: **0.5057 — HELD**
- Rush coefficient positive: **+0.416 — HELD**

All 5 pre-registrations held. xg_v1 kept, marked superseded.
sha256: 3ae7c91e4d5c2a14e72791038ac7315ca68590651ae49b6a76a28e07ded66250.

**SOG mismatches:** 14-52 games per season (1.1-4.4%). ALL mismatches are exactly +1
(table > boxscore) on one side. The PBP categorizes penalty shots as shot-on-goal or
goal; the NHL boxscore SOG excludes them. Cannot be reconciled from available data.

**Goals/xG by season:** 2021=0.981, 2022=1.018, 2023=1.003, 2024=1.012, 2025=1.068.
2025-26 drift (1.068) is the largest — reported only, nothing refitted.

### S10 — Team ratings (2026-09-29, S-WO3 Item 1)

Point-in-time team ratings for 6,425 games (5 seasons, 12,850 team-game rows).
Generator: `nhl/sim/ratings.py`. Output: `nhl/data/sim/ratings/team_ratings.parquet`.

Stats: 5v5 attempts FOR/AGAINST per 60, 5v5 xG per attempt FOR/AGAINST.
Stabilised with split-half K on 2021-22 + 2022-23.

Split-half reliabilities (fit seasons, 40 games/half):
- 5v5 attempt share: **r=0.932, K=6.0** — pre-registered > 0.60: **HELD**
- 5v5 xG per attempt FOR: **r=0.798, K=20.7** — pre-registered < attempt share's r: **HELD**
- PP xG per attempt: **r=0.211** — pre-registered < 0.40: **HELD**

Season carry-over: not yet implemented (first game of each season starts at league mean).

### S11 — Goalie ratings and league finishing term (2026-09-29, S-WO3 Item 2)

Goalie GSAx per attempt, point-in-time, shrunk. Generator: same `nhl/sim/ratings.py`.
Output: `nhl/data/sim/ratings/goalie_ratings.parquet`.

- GSAx/attempt split-half r: **0.207, K=229.3** — pre-registered < 0.30: **HELD**
- Starter = goalie on first shot against (from event table). Agreement with box score: TBD.
- League finishing term (goals/xG v2 by month): 2025-26 runs 0.91-0.97 (below 1.0, indicating
  the xG v2 overpredicts for that season — consistent with the 1.068 drift noted in S9).

### S12 — Ratings-only sanity check (2026-09-29, S-WO3 Item 3)

Simplified implied goals from 5v5 team ratings only (no PP/PK, no goalie, no finishing term).
Evaluated on 2022-23 (fit) and 2023-24 (validate). No holdout data touched.

**Results:**
- corr(implied goal diff, actual goal diff): 0.287 (fit), 0.225 (validate)
- corr(implied goal diff, Pinnacle logit): **NOT MEASURABLE** — historical lines use
  event_id hashes that don't join with the boxscore game_id format. Needs a team/date match.
- corr(implied total, Pinnacle total line): **NOT MEASURABLE** (same join issue)
- Mean implied total: 5.43 (fit), 5.49 (validate) vs actual 6.36, 6.23
  Within +/-3% of actual: **NOT HELD** (-14.6% fit, -11.8% validate). The simplified formula
  omits PP/PK contribution (~1 goal/team/game), goalie factor, and finishing term.
- NULL CONTROL: shuffled within date, corr = 0.054 (fit), 0.037 (validate) — near 0: **HELD**

The ratings carry real signal (positive correlation, null near 0) but the simplified implied-goals
formula is too crude for absolute calibration. The full engine (S-WO4) adds PP/PK, goalie,
finishing term, and proper time allocation. The Pinnacle comparison needs a team+date join
to be built in S-WO4.

### S13 — Ratings rebuilt point-in-time, per-season (2026-09-29, S-WO3r Item 1)

**What S10-S12 got wrong** (per nhl_sim_s3_verification_2026-09-29.md):
1. League prior used ALL seasons including holdout (future data in every past rating).
2. No season boundary — cumulative ran across all 5 seasons without reset.
3. Leakage truncation test not run.
4. Goalie same all-season structure.
5. PP/PK not in table, score adjustment not applied.
6. S12 used simplified 5v5-only formula, Pinnacle marked "not measurable".
7. Finishing term was monthly, including same-month games.

**Rebuilt:** Per-season accumulation; league mean = strictly-before-D in that season;
carry-over measured on 2021->2022 transition (w=0.784 att_for, 0.805 att_against).
2021-22 opening uses first-10-days mean (flagged as warm-up exception).

Split-half reliabilities (per-season halves, fit seasons):
- 5v5 att share: r=0.907, K=8.4
- 5v5 xG/att FOR: r=0.686, K=37.5
- Goalie GSAx/att: r=0.188, K=258.5 (pre-registered <0.30: **HELD**)

Carry-over: w=0.784 (att_for), w=0.805 (att_against).

NULL CONTROLS:
- Holdout leakage: 2022-23 ratings identical with and without 2024-25 + 2025-26 (max diff < 1e-10). PASS.
- Season reset: first game of each season has n_prior_games=0. PASS.
- Both tests FAIL on e17ace021: old code uses all-season league mean (leakage) and has no season boundary.

### S14 — League finishing term, point-in-time (2026-09-29, S-WO3r Item 2)

Correction: S9's "Goals/xG 2025=1.068" was xG/goals. In 2025-26, goals came in ~6.8% BELOW xG
(goals/xG = 0.91-0.97 monthly). The xG model OVERpredicts for that season.

Finishing term reported with both labels: goals/xG AND xG/goals by month for all 5 seasons.
