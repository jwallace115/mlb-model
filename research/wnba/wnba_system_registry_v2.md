# WNBA System Registry V2

**Date:** 2026-05-09
**Supersedes:** research/wnba/wnba_system_registry_v1.md
**Source of corrections:** research/wnba/wnba_system_registry_v1_review.md
**Status:** Decision baseline. No WNBA system is currently trusted as live edge.

---

## Changes from v1

- **System A STATUS** upgraded from `VALIDATED_DEAD` to `VALIDATED_DEAD — proxy odds only`. Review found validation used flat -110 / proxy ROI, not real sportsbook prices. Qualifier added per review §System A nuance.
- **System B STATUS** upgraded from `UNVALIDATED_LIVE` to `UNVALIDATED_LIVE — exploratory only`. Review confirmed zero validation artifacts exist. Label clarified per review §System B verdict.
- **System C STATUS** changed from `VALIDATED_DEAD` to `VALIDATED_NEGATIVE_DEAD`. Review found anchor v1 validation result was negative (RMSE 15.83 vs market 15.32, "Market wins: True"). v2/v3 performance not independently verified. Per review §System C verdict.
- **System D STATUS** changed from `VALIDATED_DEAD` to `VALIDATED_NEGATIVE_DEAD`. Review confirmed diagnostics explicitly state model loses to market and recommend MARKET_ANCHOR_REBUILD. Per review §System D verdict and §Status Logic Violations.
- **Drift log:** Added "May 16 activation" and "5 cron jobs" entries per review §Drift-Log Gaps. Upgraded "75.5% PRA variance" from SPEC_UNCLEAR to DRIFT — UNSUPPORTED CLAIM per review §Drift-Log Gaps.
- **Accounting:** Added 15 artifacts from review §Accounting Gaps to new "Accounting completeness" section.
- **Shared data layer:** Added note per review §Internal Contradictions that `game_index.parquet`, `team_game_logs.parquet`, and `player_game_logs.parquet` are shared across Systems A, B, and D.

---

## Drift summary — corrected

| Master-doc claim | Reality | v2 verdict | Notes |
|---|---|---|---|
| "All 7 signals deploy-authorized May 16" | Contamination audit exists, all 7 CLEAN/INSUFFICIENT_SAMPLE. But `assign_archetypes.py` does not write 2026 signals. `wnba_archetype_signals_2026.json` is empty `[]`. | PARTIAL | Research is real. Implementation is incomplete. No 2026 output. |
| "Full pipeline built and dry-run validated" | 3 of 5 archetype pipeline scripts are one-line stubs. `pull_live_games.py` is a stub. Only `assign_archetypes.py` and `validate_archetype_pipeline.py` are implemented. | DRIFT | "Full pipeline" is overstated. |
| "+20.6% proxy ROI" | Backfill signals show positive proxy ROI for some signals. Per-signal ROI ranges from -45.5% (ARCH_05) to +34.3% (ARCH_01). The +20.6% figure likely represents a weighted average but its exact derivation has no repo artifact. | PARTIAL | Proxy metric is real but (a) "ROI" implies real money — these are proxy odds, and (b) the specific +20.6% number is not independently verifiable from repo artifacts. |
| "WNBA archetype system: READY" | 3 of 5 pipeline scripts are stubs. No 2026 output. No live odds. Dashboard shows "System reset — rebuilding." | DRIFT | Not READY by any operational definition. |
| "Rate × minutes explains 75.5% of PRA variance" | Zero mentions of "75.5" or "PRA variance" found in any .md, .json, .py, or .txt file across research/ and wnba/. Exhaustive search returned no results. Pertains to System B (player props), not System A (archetypes). | DRIFT — UNSUPPORTED CLAIM | No repo evidence. May be from a prior Claude session that was not saved to a research artifact. |
| "May 16 2026 activation" (implicit) | WNBA season started May 8, 2026. May 16 was the planned deployment date from the contamination audit. As of May 9, System A is not producing 2026 output. | DRIFT | Plan date missed by implementation gaps, not by research invalidity. |
| "5 cron jobs active on VM" (implicit) | VM has 5 WNBA-related cron entries. 1 belongs to System A (`assign_archetypes.py`). 4 belong to System D (`build_features.py`, `run_model.py`, `pull_live_games.py`, `push_signals.py`). "5 cron jobs" conflates two separate systems. | PARTIAL | Technically true count. Misleading as a description of one system. |

---

## Systems

### System A: Archetype Full-Game Totals — ARCH_01–ARCH_07

1. **SYSTEM NAME:** WNBA Archetype Full-Game Totals
2. **MARKET:** Full-game totals (OVER/UNDER). Closing totals range 147–225, median 163.5. Confirmed NOT team totals.
3. **VALIDATION ARTIFACT:** `research/discovery/wnba_contamination_audit_v1/WNBA_CONTAMINATION_AUDIT_REPORT.md` — 7 signals, 3-stage validation, OOS on 2025. ARCH_02 strongest (+22.7% OOS proxy ROI). Contamination verdict: CLEAN.
   - Additional research: `research/wnba/archetypes/` — hypothesis registry, matchup market errors, stability checks, style features, cluster assignments.
   - Additional research: `wnba_archetype_board/reports/` — historical_signal_performance.csv, backfill summary.
   - Additional research: `research/wnba/archetypes/team_game_state_profiles.parquet`, `team_season_profiles.parquet`, `feature_market_proxy_check.csv`.
4. **LIVE IMPLEMENTATION FILES:**
   - `wnba_archetype_board/pipeline/assign_archetypes.py` — IMPLEMENTED, runs daily on VM
   - `wnba_archetype_board/pipeline/build_team_style_features.py` — **STUB** (one print statement)
   - `wnba_archetype_board/pipeline/build_matchup_board.py` — **STUB** (one print statement)
   - `wnba_archetype_board/pipeline/push_archetype_signals.py` — **STUB** (one print statement)
   - `wnba_archetype_board/pipeline/validate_archetype_pipeline.py` — IMPLEMENTED
5. **LIVE OUTPUT FILES:**
   - `wnba_archetype_board/data/signals/wnba_archetype_signals_2026.json` — EMPTY (`[]`), mtime Apr 2
   - `wnba_archetype_board/data/signals/wnba_archetype_signals_backfill_2022_2025.json` — 349 signals, historical only
   - `wnba_archetype_board/data/current/daily_matchup_board.parquet` — 959 rows, max season 2025
   - `wnba_archetype_board/data/current/team_archetypes_season_current.parquet` — 49 rows, 2022–2025
   - `wnba_archetype_board/data/current/team_archetypes_state_current.parquet` — 1750 rows, max 2025-10-10
   - `wnba_archetype_board/data/logs/signal_tracker.parquet` — 349 rows, historical
   - `wnba_archetype_board/dashboard/archetype_tab_payload.json` — pre-built, not consumed
6. **CONSUMER PATH:** Dashboard tab exists (`_render_wnba_archetype_tab`) but shows "System reset — rebuilding." placeholder.
7. **CRON / LAUNCHD:** VM cron: `0 13 * * * ... assign_archetypes.py` (9am ET daily). Runs daily, processes historical data, no 2026 output.
8. **STATUS: VALIDATED_DEAD — proxy odds only**
9. **OUT-OF-SCOPE SYSTEMS:** System B (player props), System C (anchor models), System D (game-total model)

**Notes:**
- Contamination audit validated against full-game totals using proxy ROI (flat -110 equivalent), not real sportsbook prices with actual vig.
- Real sportsbook price validation has not been completed.
- No 2026 live edge output exists.
- Recovery requires completing stub scripts, adding write step, pulling live odds, AND passing a real-price validation gate before any live edge claim.
- ARCH_05 reversed in OOS (28.6% vs 55.6% discovery) — partial instability.
- SEASON-mode signals (ARCH_03, ARCH_05, ARCH_07) could fire using prior-season fallback if write step existed.
- STATE-mode signals (ARCH_01, ARCH_02, ARCH_04, ARCH_06) need ≥8 games + feature builder + GMM assignment.
- `EXPANSION_TEAMS` set incomplete: only GSV. Missing TOR (Toronto Tempo) and PFE (Portland Fire).
- Reads shared data: `wnba/data/game_index.parquet` (also used by System D, written by System B).

---

### System B: Player Props — wnba/shadow/

1. **SYSTEM NAME:** WNBA Player Props Shadow
2. **MARKET:** Player props (points, rebounds, assists, PRA, threes)
3. **VALIDATION ARTIFACT:** **NONE.** No research report, no backtest, no OOS evaluation found anywhere in `research/`. The model uses per-minute career rates × projected minutes — a heuristic, not a validated edge model.
4. **LIVE IMPLEMENTATION FILES:**
   - `wnba/shadow/daily_runner.py` — IMPLEMENTED, pulls Odds API player props, computes projections
   - `wnba/shadow/clv_runner.py` — IMPLEMENTED, captures closing lines via historical endpoint
   - `wnba/shadow/grader.py` — IMPLEMENTED, grades prop outcomes
   - `wnba/shadow/season_updater.py` — IMPLEMENTED (fixed May 9), ingests box scores
   - `wnba/shadow/weekly_report.py` — not inspected
5. **LIVE OUTPUT FILES (all fresh, written today May 9):**
   - `wnba/shadow/prop_candidates.parquet` — 67,245 rows, May 9 data present
   - `wnba/shadow/clv_log.parquet` — 56,524 rows
   - `wnba/shadow/daily_projections.parquet` — 1,205 rows
   - `wnba/shadow/graded_results.parquet` — 2,558 rows (384 May 8 graded)
   - `wnba/shadow/player_name_map.parquet` — 88 rows
   - `wnba/shadow/daily_best_board.parquet` — 0 rows (no edges selected)
   - `wnba/shadow/test_fixtures/` — test data, not live output
6. **CONSUMER PATH:** No dashboard connection. No alert system. Manual review only.
7. **CRON / LAUNCHD:** Mac launchd only:
   - `com.mlbmodel.wnba.daily` — 11am ET, `daily_runner.py` (RUN_MODE=live as of May 9)
   - `com.mlbmodel.wnba.clv` — 10:30pm ET, `clv_runner.py` (RUN_MODE=live as of May 9)
   - `com.mlbmodel.wnba.grader` — 8am ET, `grader.py`
   - `com.mlbmodel.wnba.updater` — 10am ET, `season_updater.py` (RUN_MODE=live, push chain added May 9)
8. **STATUS: UNVALIDATED_LIVE — exploratory only**
9. **OUT-OF-SCOPE SYSTEMS:** System A (archetypes), System C (anchor models), System D (game-total model)

**Notes:**
- Operational plumbing exists and was recently repaired (season_updater stub completed May 9, CLV switched to historical endpoint May 9).
- Zero validation artifact exists in repo. No edge claim is supported.
- Data collection only until formal validation is completed.
- No promotion eligibility.
- System B does NOT use `wnba/models/ridge_wnba.pkl`. It uses inline per-minute rate × projected minutes heuristics.
- `low_history` gate will clear for most players around May 14–16 (after ~3 games played). Once cleared, the system will start classifying edges — but these edges have NO research backing.
- Writes to shared data files (`team_game_logs.parquet`, `game_index.parquet`, `player_game_logs.parquet`) that are also read by Systems A and D.

---

### System C: Anchor Models (v1/v2/v3)

1. **SYSTEM NAME:** WNBA Market-Anchor Totals Adjustment
2. **MARKET:** Full-game totals (predicts `actual_total - closing_total`)
3. **VALIDATION ARTIFACT:**
   - v1: `wnba_anchor/reports/anchor_model_summary.txt` — RMSE 15.83 vs market 15.32. Market wins. LEAN_OVER INVERTED (-18.3% ROI). **Validation result: NEGATIVE.**
   - v2: `wnba_anchor_v2/reports/hypothesis_registry_anchor_v2.json` — expanded closing lines (train 2022-2023, val 2024, holdout 2025). Performance vs market not independently verified in this audit.
   - v3: `wnba_anchor_v3/reports/hypothesis_registry_anchor_v3.json` — UTC/ET date fix, 449 additional games recovered. Performance vs market not independently verified.
4. **LIVE IMPLEMENTATION FILES:**
   - `wnba_anchor/pipeline/build_anchor_features.py`, `run_anchor_model.py`, `validate_anchor_pipeline.py`
   - `wnba_anchor_v2/pipeline/build_anchor_v2_features.py`, `run_anchor_v2_model.py`, `validate_anchor_v2_pipeline.py`
   - `wnba_anchor_v3/pipeline/build_anchor_v3_features.py`, `run_anchor_v3_model.py`, `validate_anchor_v3_pipeline.py`
5. **LIVE OUTPUT FILES:**
   - `wnba_anchor/data/signals/wnba_anchor_signals_2025.json` — mtime Apr 2 (stale)
   - `wnba_anchor_v2/data/signals/wnba_anchor_v2_signals_2025.json` — mtime Apr 2 (stale)
   - `wnba_anchor_v3/data/signals/wnba_anchor_v3_signals_2025.json` — mtime Apr 2 (stale)
6. **CONSUMER PATH:** NONE. No cron, no plist, no dashboard reference.
7. **CRON / LAUNCHD:** NONE.
8. **STATUS: VALIDATED_NEGATIVE_DEAD**
9. **OUT-OF-SCOPE SYSTEMS:** System A (archetypes), System B (player props), System D (game-total model)

**Notes:**
- Validation result for v1 was negative — model is worse than market baseline.
- v2/v3 may have improved on v1 but their performance reports were not independently inspected. Their hypothesis registries exist but contain frozen thresholds, not performance summaries.
- All three use `closing_total_centered` as a feature — they are market-anchor adjustment models, not standalone predictors.
- Not a recovery candidate unless a new thesis identifies a specific salvage reason.
- Nobody reads from these. They appear to be research iterations.

---

### System D: Base Ridge

1. **SYSTEM NAME:** WNBA Game-Total Prediction (Ridge)
2. **MARKET:** Full-game totals (predicts `actual_total` directly, not adjustment)
3. **VALIDATION ARTIFACT:**
   - `research/wnba/model_diagnostics_pass1/diagnostic_summary.txt` — Model RMSE 17.78 vs Market RMSE 15.32. Market wins. Recommendation: MARKET_ANCHOR_REBUILD.
   - `research/wnba/residual_discovery/discovery_summary.txt` — 18 hypotheses tested, 1 CANDIDATE (offense_mismatch), rest NULL/THIN.
4. **LIVE IMPLEMENTATION FILES:**
   - `wnba/pipeline/build_features.py` — IMPLEMENTED
   - `wnba/pipeline/run_model.py` — IMPLEMENTED, loads `wnba/models/ridge_wnba.pkl`
   - `wnba/pipeline/pull_live_games.py` — **STUB**
   - `wnba/pipeline/push_signals.py` — BROKEN (hardcoded 2025, grading placeholder)
   - `wnba/pipeline/validate_pipeline.py` — IMPLEMENTED
5. **LIVE OUTPUT FILES:**
   - `wnba/data/canonical/wnba_feature_table.parquet` — 1,115 rows, max 2025 (rebuilt daily, no 2026 rows)
   - `wnba/data/signals/wnba_signals_2025.json` — mtime Apr 2 (stale)
   - `wnba/models/ridge_wnba.pkl` — frozen model, train 2021-2022, α=100
   - `wnba/models/feature_config_wnba.json` — 17 features
6. **CONSUMER PATH:** NONE.
7. **CRON / LAUNCHD:** VM cron (4 entries, all running daily, all producing no useful output):
   - `0 12 * * * ... build_features.py` (8am ET)
   - `30 12 * * * ... run_model.py` (8:30am ET)
   - `0 2 * * * ... pull_live_games.py` (10pm ET) — STUB
   - `0 3 * * * ... push_signals.py` (11pm ET) — no pending signals
8. **STATUS: VALIDATED_NEGATIVE_DEAD**
9. **OUT-OF-SCOPE SYSTEMS:** System A (archetypes), System B (player props), System C (anchor models)

**Notes:**
- Diagnosed worse than market (RMSE 17.78 vs 15.32). Own diagnostics recommend MARKET_ANCHOR_REBUILD.
- Not a recovery candidate without a new thesis.
- `wnba/models/ridge_wnba.pkl` is NOT used by System B. System B uses inline per-minute rates.
- Reads shared data: `wnba/data/game_index.parquet`, `wnba/data/team_game_logs.parquet`, `wnba/data/player_game_logs.parquet` (written by System B's season_updater).

---

## Shared data layer

The following files are read by multiple systems and written by System B's `season_updater.py`:

| File | Written by | Read by |
|---|---|---|
| `wnba/data/game_index.parquet` | System B (season_updater) | System A (assign_archetypes), System D (build_features) |
| `wnba/data/team_game_logs.parquet` | System B (season_updater) | System D (build_features) |
| `wnba/data/player_game_logs.parquet` | System B (season_updater) | System D (build_features) |
| `wnba/data/player_game_logs_enriched.parquet` | System B (season_updater) | System B (daily_runner, grader) |

---

## Unclassified artifacts

| Path | Notes |
|---|---|
| `wnba/build_data.py` | Data construction script. Used during initial build. Not scheduled. |
| `wnba/data/boxscore_new_raw.parquet` | Raw boxscore data. Source material. |
| `wnba/data/historical_odds_*.parquet` | Historical odds files. System C/D research input. |
| `wnba/data/officials.parquet` | Referee data. research/wnba/m04_referee_foul/ input. |
| `wnba/data/minutes_projections.parquet`, `minutes_redistribution.parquet` | Research artifacts for player minutes modeling. |
| `wnba/data/player_stat_rates_pregame.parquet`, `player_variance_profiles.parquet` | Research artifacts. |
| `wnba/data/rotation_stability.parquet`, `role_*.parquet` | Research artifacts for rotation analysis. |
| `wnba/data/starter_absence_events.parquet` | Research artifact. |
| `wnba/shadow/weekly_report.py` | Not inspected. No cron/plist. |
| `research/wnba/m04_referee_foul/` | Referee-foul signal research. Not promoted. |
| `research/wnba/m07_rotation_fragility/` | Rotation fragility research (2 versions). Not promoted. |

---

## Accounting completeness — v2

Artifacts flagged by review as missing from v1, now placed:

| Artifact | v2 placement |
|---|---|
| `dashboard_components.py` (WNBA mentions) | Infrastructure — off-season suppression logic |
| `dashboard_original_pre_refactor.py` | ARCHIVED |
| `setup_launchd.py` | Infrastructure — launchd setup |
| `shared/health_check.py` | Infrastructure — signal freshness monitoring |
| `research/recovery/site_reset/apply_dashboard_patch.py` | ARCHIVED |
| `wnba_anchor_v2/pipeline/build_anchor_v2_features.py` | System C file list (added above) |
| `wnba_anchor_v3/pipeline/build_anchor_v3_features.py` | System C file list (added above) |
| `research/wnba/archetypes/team_game_state_profiles.parquet` | System A research artifacts (added above) |
| `research/wnba/archetypes/team_season_profiles.parquet` | System A research artifacts (added above) |
| `research/wnba/archetypes/feature_market_proxy_check.csv` | System A research artifacts (added above) |
| `wnba_archetype_board/reports/` directory | System A (added above) |
| `wnba/data/rolling_form.parquet` | System D source data |
| `wnba/data/season_aggregates.parquet` | System D source data |
| `wnba/data/player_identity.parquet` | Shared infrastructure — player identity lookup |

---

## Broken / stub artifacts

| Path | Type | Notes |
|---|---|---|
| `wnba_archetype_board/pipeline/build_team_style_features.py` | STUB | One print statement. Blocks all 2026 state archetype assignments. |
| `wnba_archetype_board/pipeline/build_matchup_board.py` | STUB | One print statement. Blocks daily matchup board generation. |
| `wnba_archetype_board/pipeline/push_archetype_signals.py` | STUB | One print statement. Blocks signal file writing. |
| `wnba/pipeline/pull_live_games.py` | STUB | Prints "would execute here." Blocks System D 2026 data flow. |
| `wnba/pipeline/push_signals.py` | BROKEN | Hardcoded to `wnba_signals_2025.json`. No 2026 path. Grading logic is placeholder. |
| `assign_archetypes.py` write step | MISSING | Script runs, detects signals, but does not write to 2026 JSON. |
| `EXPANSION_TEAMS` set | INCOMPLETE | Only contains `GSV`. Missing `TOR` (Toronto Tempo) and `PFE` (Portland Fire). |

---

## Open questions deferred to v3

1. **Should System B (player props) be allowed to produce signals when `low_history` clears (~May 14)?** There is no validation artifact. The per-minute heuristic has never been backtested. Permitting unvalidated signals to surface — even as shadow — creates a precedent that "running = valid."

2. **Should System A (archetypes) SEASON-mode signals (ARCH_03/05/07) be fast-tracked?** They could fire today using prior-season archetypes if only a write step were added. No feature builder or GMM assignment needed. This is the lowest-complexity path to the only validated WNBA edge.

3. **Are anchor v2/v3 superseded or candidates for revival?** They represent the most methodologically sound approach (market-anchor adjustment) but are completely dead. If System A's archetype signals are the deployment priority, are anchors abandoned?

4. **What is the source of the "+20.6% proxy ROI" and "75.5% PRA variance" claims?** Neither has a repo artifact. If these were computed in a prior Claude session without being saved to a research file, they may be hallucinated or stale.

5. **Should System D's VM cron entries be disabled?** They run daily, consume compute, produce "No games found for 2026," and are confirmed to perform worse than the market.

---

## What is permitted next

Only a Jeff + ChatGPT decision about strategic direction:

- **Option 1:** Recover System A with real-price validation gate. Lowest complexity for SEASON-mode signals. Requires: write step + odds pull + real-price economic test.
- **Option 2:** Pause WNBA and audit MLB next. No further WNBA work until decision is made.
- **Option 3:** Archive WNBA for the 2026 season. Disable all cron/launchd. Accept no WNBA edge this year.
- **Option 4:** Formally validate System B as a long-horizon research project. Requires: backtest, OOS evaluation, contamination audit — the full research governance process.

---

## What is NOT permitted next

- Any code change before a decision is made on the four options above.
- Any quick fix to System A's missing write step without selecting Option 1.
- Any while-I'm-here patches to stubs.
- Any work on a system without using this registry as the source of truth.
- Any live edge claim from WNBA until a system is reclassified through v3 or a later decision document.
- Any assumption that System B edges are valid because the pipeline runs. Running ≠ validated.
- Any treating anchor v1/v2/v3 as interchangeable — each has different training data and feature sets.
