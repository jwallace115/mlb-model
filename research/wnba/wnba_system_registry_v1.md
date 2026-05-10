# WNBA System Registry V1

**Date:** 2026-05-09 (in-season; opening day was May 8)
**Status:** Hard-brake snapshot. No system trusted as live edge until re-classified here.
**Author:** Automated audit session

---

## Drift Summary

| Claim (from master doc / memory) | Reality | Verdict |
|---|---|---|
| "All 7 signals deploy-authorized May 16" | Contamination audit exists, all 7 CLEAN/INSUFFICIENT_SAMPLE. But `assign_archetypes.py` does not write 2026 signals. `wnba_archetype_signals_2026.json` is empty `[]`. | PARTIAL — research is real, implementation is incomplete |
| "Full pipeline built and dry-run validated" | `build_team_style_features.py`, `build_matchup_board.py`, `push_archetype_signals.py` are all one-line stubs. `pull_live_games.py` prints "would execute here." Only `assign_archetypes.py` is implemented. | DRIFT — "full pipeline" is overstated |
| "+20.6% proxy ROI" | Backfill signals show positive ROI for ARCH_02/ARCH_07, but this is proxy ROI against historical closing totals, not actual bet-level ROI. No real prices tracked. | PARTIAL — proxy metric is real, but "ROI" implies real money |
| "WNBA archetype system: READY" | 3 of 5 pipeline scripts are stubs. No 2026 output. No live odds. Dashboard shows "System reset — rebuilding." | DRIFT — not READY |
| "Rate × minutes explains 75.5% of PRA variance" | This claim pertains to System B (player props), not System A (archetypes). No validation artifact found for the player-prop system in research/. | SPEC_UNCLEAR — may exist as inline analysis, not as research artifact |

---

## Systems

### System A: WNBA Archetype Team Totals (ARCH_01–ARCH_07)

1. **SYSTEM NAME:** WNBA Archetype Team Totals
2. **MARKET:** Full-game totals (OVER/UNDER). Closing totals range 147–225, median 163.5. Confirmed NOT team totals.
3. **VALIDATION ARTIFACT:** `research/discovery/wnba_contamination_audit_v1/WNBA_CONTAMINATION_AUDIT_REPORT.md` — 7 signals, 3-stage validation, OOS on 2025. ARCH_02 strongest (+22.7% OOS ROI). Contamination verdict: CLEAN.
4. **LIVE IMPLEMENTATION FILES:**
   - `wnba_archetype_board/pipeline/assign_archetypes.py` — IMPLEMENTED, runs daily on VM
   - `wnba_archetype_board/pipeline/build_team_style_features.py` — **STUB** (one print statement)
   - `wnba_archetype_board/pipeline/build_matchup_board.py` — **STUB** (one print statement)
   - `wnba_archetype_board/pipeline/push_archetype_signals.py` — **STUB** (one print statement)
   - `wnba_archetype_board/pipeline/validate_archetype_pipeline.py` — IMPLEMENTED (validation checks)
5. **LIVE OUTPUT FILES:**
   - `wnba_archetype_board/data/signals/wnba_archetype_signals_2026.json` — EMPTY (`[]`), mtime Apr 2
   - `wnba_archetype_board/data/signals/wnba_archetype_signals_backfill_2022_2025.json` — 349 signals, historical only
   - `wnba_archetype_board/data/current/daily_matchup_board.parquet` — 959 rows, max season 2025
   - `wnba_archetype_board/data/current/team_archetypes_season_current.parquet` — 49 rows, 2022–2025
   - `wnba_archetype_board/data/current/team_archetypes_state_current.parquet` — 1750 rows, max 2025-10-10
   - `wnba_archetype_board/data/logs/signal_tracker.parquet` — 349 rows, historical
6. **CONSUMER PATH:** Dashboard tab exists (`_render_wnba_archetype_tab`) but shows "System reset — rebuilding." placeholder.
7. **CRON / LAUNCHD:** VM cron: `0 13 * * * ... assign_archetypes.py` (9am ET daily). Runs daily, processes historical data, no 2026 output.
8. **STATUS: VALIDATED_DEAD** — Validation artifact is real and thorough. But implementation has 3 stub scripts, no 2026 signal output, no live odds, no dashboard.
9. **OUT-OF-SCOPE SYSTEMS:** System B (player props), System C (anchor models), System D (game-total model)

**Breakpoints:**
- `build_team_style_features.py` is a stub → no 2026 rolling features → no 2026 state archetypes
- `assign_archetypes.py` runs but does not write to `wnba_archetype_signals_2026.json`
- No live team-total odds pull (Odds API `basketball_wnba` `totals` market confirmed available)
- SEASON-mode signals (ARCH_03, ARCH_05, ARCH_07) could fire using prior-season fallback if write step existed
- STATE-mode signals (ARCH_01, ARCH_02, ARCH_04, ARCH_06) need ≥8 games + feature builder + GMM assignment
- Toronto Tempo (TOR) is 2026 expansion but not in `EXPANSION_TEAMS` set (only GSV)

---

### System B: WNBA Player Props Shadow

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
6. **CONSUMER PATH:** No dashboard connection. No alert system. Manual review only.
7. **CRON / LAUNCHD:** Mac launchd only:
   - `com.mlbmodel.wnba.daily` — 11am ET, `daily_runner.py` (RUN_MODE=live as of May 9)
   - `com.mlbmodel.wnba.clv` — 10:30pm ET, `clv_runner.py` (RUN_MODE=live as of May 9)
   - `com.mlbmodel.wnba.grader` — 8am ET, `grader.py`
   - `com.mlbmodel.wnba.updater` — 10am ET, `season_updater.py` (RUN_MODE=live, push chain added May 9)
8. **STATUS: UNVALIDATED_LIVE** — Actively writing data, ingesting box scores, capturing CLV. But no research validation exists. The `low_history` gate correctly blocks signal generation until players have ≥3 games. All 2,174 May 9 candidates classified as `no_bet`.
9. **OUT-OF-SCOPE SYSTEMS:** System A (archetypes), System C (anchor models), System D (game-total model)

**Notes:**
- System B does NOT use `wnba/models/ridge_wnba.pkl`. It uses inline per-minute rate × projected minutes heuristics.
- `low_history` gate will clear for most players around May 14–16 (after ~3 games played).
- Once low_history clears, the system will start classifying edges. But these edges have NO research backing.

---

### System C: WNBA Anchor Models (v1/v2/v3)

1. **SYSTEM NAME:** WNBA Market-Anchor Totals Adjustment
2. **MARKET:** Full-game totals (predicts `actual_total - closing_total`)
3. **VALIDATION ARTIFACT:**
   - `wnba_anchor/reports/anchor_model_summary.txt` — Anchor v1: RMSE 15.83 vs market 15.32, STRONG_OVER +9.1% ROI, LEAN_OVER INVERTED
   - `wnba_anchor_v2/reports/hypothesis_registry_anchor_v2.json` — v2 with expanded closing lines (train 2022-2023, val 2024, holdout 2025)
   - `wnba_anchor_v3/reports/hypothesis_registry_anchor_v3.json` — v3 with UTC/ET date fix, 449 additional games recovered
4. **LIVE IMPLEMENTATION FILES:**
   - `wnba_anchor/pipeline/build_anchor_features.py`, `run_anchor_model.py`, `validate_anchor_pipeline.py`
   - `wnba_anchor_v2/pipeline/` (same 3 scripts)
   - `wnba_anchor_v3/pipeline/` (same 3 scripts)
5. **LIVE OUTPUT FILES:**
   - `wnba_anchor/data/signals/wnba_anchor_signals_2025.json` — mtime Apr 2 (stale)
   - `wnba_anchor_v2/data/signals/wnba_anchor_v2_signals_2025.json` — mtime Apr 2 (stale)
   - `wnba_anchor_v3/data/signals/wnba_anchor_v3_signals_2025.json` — mtime Apr 2 (stale)
6. **CONSUMER PATH:** NONE. No cron, no plist, no dashboard reference.
7. **CRON / LAUNCHD:** NONE. Not scheduled anywhere. Only referenced in `wnba_anchor/pipeline/` scripts (self-contained).
8. **STATUS: VALIDATED_DEAD** — Three versions exist with validation artifacts and frozen models. None are scheduled or producing 2026 output. All signal files frozen at Apr 2.
9. **OUT-OF-SCOPE SYSTEMS:** System A (archetypes), System B (player props), System D (game-total model)

**Notes:**
- v1 trained on 2021-2022 (sparse — only 56 games with closing lines)
- v2 expanded to 2022-2023 training
- v3 fixed UTC/ET date alignment, recovered 449 additional games
- All three use `closing_total_centered` as a feature — they are market-anchor models that adjust the closing line, not standalone predictors
- Nobody reads from these. They appear to be research iterations that were superseded.

---

### System D: WNBA Game-Total Ridge Model

1. **SYSTEM NAME:** WNBA Game-Total Prediction (Ridge)
2. **MARKET:** Full-game totals (predicts `actual_total` directly, not adjustment)
3. **VALIDATION ARTIFACT:**
   - `research/wnba/model_diagnostics_pass1/diagnostic_summary.txt` — Model RMSE 17.78 vs Market RMSE 15.32. Market wins. Recommendation: MARKET_ANCHOR_REBUILD.
   - `research/wnba/residual_discovery/discovery_summary.txt` — 18 hypotheses tested, 1 CANDIDATE (offense_mismatch), rest NULL/THIN.
4. **LIVE IMPLEMENTATION FILES:**
   - `wnba/pipeline/build_features.py` — IMPLEMENTED, builds 17-feature table from team_game_logs
   - `wnba/pipeline/run_model.py` — IMPLEMENTED, loads `wnba/models/ridge_wnba.pkl`, predicts game totals
   - `wnba/pipeline/pull_live_games.py` — **STUB** (prints "would execute here")
   - `wnba/pipeline/push_signals.py` — IMPLEMENTED but hardcoded to `wnba_signals_2025.json` (no 2026 path)
   - `wnba/pipeline/validate_pipeline.py` — IMPLEMENTED
5. **LIVE OUTPUT FILES:**
   - `wnba/data/canonical/wnba_feature_table.parquet` — 1,115 rows, max 2025 (rebuilt daily but no 2026 rows)
   - `wnba/data/signals/wnba_signals_2025.json` — mtime Apr 2 (stale, hardcoded 2025)
   - `wnba/models/ridge_wnba.pkl` — frozen model, train 2021-2022, α=100
6. **CONSUMER PATH:** NONE. Dashboard doesn't read System D signals.
7. **CRON / LAUNCHD:** VM cron:
   - `0 12 * * * ... build_features.py` (8am ET)
   - `30 12 * * * ... run_model.py` (8:30am ET)
   - `0 2 * * * ... pull_live_games.py` (10pm ET) — **STUB, does nothing**
   - `0 3 * * * ... push_signals.py` (11pm ET) — writes nothing (no pending signals)
8. **STATUS: VALIDATED_DEAD** — Validation shows model LOSES to market baseline (RMSE 17.78 vs 15.32). Diagnostic recommends MARKET_ANCHOR_REBUILD. Model runs daily but produces "No games found for 2026" because feature table has no 2026 rows. The `pull_live_games.py` stub prevents 2026 data from flowing into the feature table.
9. **OUT-OF-SCOPE SYSTEMS:** System A (archetypes), System B (player props), System C (anchor models)

**Notes:**
- System D is the "base" Ridge model that System C (anchor) was designed to replace.
- System D's own diagnostics say it's worse than the market. It should not be deployed standalone.
- `wnba/models/ridge_wnba.pkl` is NOT used by System B (player props). System B uses inline per-minute rates.
- `wnba/models/feature_config_wnba.json` (17 features, α=100, train 2021-2022) is System D's config.

---

## Unclassified Artifacts

| Path | Notes |
|---|---|
| `wnba/build_data.py` | Data construction script. Used during initial build. Not scheduled. |
| `wnba/data/boxscore_new_raw.parquet` | Raw boxscore data. Source material, not output. |
| `wnba/data/historical_odds_*.parquet` | Historical odds files. Used by System C/D research. Not live. |
| `wnba/data/officials.parquet` | Referee data. Used by research/wnba/m04_referee_foul/. Not live. |
| `wnba/data/minutes_projections.parquet`, `minutes_redistribution.parquet` | Research artifacts for player minutes modeling. Not actively consumed. |
| `wnba/data/player_stat_rates_pregame.parquet`, `player_variance_profiles.parquet` | Research artifacts. Not actively consumed by any live system. |
| `wnba/data/rotation_stability.parquet`, `role_*.parquet` | Research artifacts for rotation analysis. |
| `wnba/shadow/weekly_report.py` | Not inspected. No cron/plist. |
| `wnba/shadow/test_fixtures/` | Test data for System B. Not live output. |
| `wnba_archetype_board/dashboard/archetype_tab_payload.json` | Pre-built dashboard payload. Not consumed by current dashboard. |
| `research/wnba/m04_referee_foul/` | Referee-foul signal research. Not promoted to any live system. |
| `research/wnba/m07_rotation_fragility/` | Rotation fragility research (2 versions). Not promoted. |

---

## Broken / Stub Artifacts

| Path | Type | Notes |
|---|---|---|
| `wnba_archetype_board/pipeline/build_team_style_features.py` | STUB | One print statement. Blocks all 2026 state archetype assignments. |
| `wnba_archetype_board/pipeline/build_matchup_board.py` | STUB | One print statement. Blocks daily matchup board generation. |
| `wnba_archetype_board/pipeline/push_archetype_signals.py` | STUB | One print statement. Blocks signal file writing. |
| `wnba/pipeline/pull_live_games.py` | STUB | Prints "would execute here." Blocks System D 2026 data flow. |
| `wnba/pipeline/push_signals.py` | BROKEN | Hardcoded to `wnba_signals_2025.json`. No 2026 path. Grading logic is placeholder (`graded = 0`). |
| `assign_archetypes.py` write step | MISSING | Script runs, detects signals, but does not write to 2026 JSON. |
| `EXPANSION_TEAMS` set | INCOMPLETE | Only contains `GSV`. Missing `TOR` (Toronto Tempo, 2026 expansion). Missing `PFE` (Portland Fire, 2026 expansion). |

---

## What This Registry Says About WNBA Edge Status

**No WNBA system is currently producing actionable edge signals for 2026.**

System A (Archetypes) has the only validated research backing (contamination audit, 7 signals, 3-stage OOS) but its implementation is incomplete — 3 of 5 pipeline scripts are stubs, no 2026 signals are being written, and no live odds are being pulled. SEASON-mode signals (ARCH_03/05/07) could theoretically fire today using prior-season archetype fallback, but the missing write step means they silently pass through.

System B (Player Props) is the only system actively writing 2026 data, but it has zero research validation. Its per-minute heuristic projections have never been backtested. The `low_history` gate correctly prevents signal generation for the first ~3 games per player, but when that gate lifts (~May 14), the system will start producing edges with no empirical basis.

System C (Anchor Models) represents the most sophisticated modeling approach (market-anchor adjustment) but all three versions are dead — no cron, no plist, no 2026 output.

System D (Base Ridge) was explicitly diagnosed as worse than the market (RMSE 17.78 vs 15.32) and recommended for market-anchor rebuild. It should not be deployed.

---

## What Is NOT Permitted Next

- No code changes to any system marked UNCLASSIFIED, BROKEN, or STUB until that system has been formally classified in v2 of this registry.
- No "quick fixes" to stubs without a clear specification of what the stub should do.
- No assuming System A and System D are the same because they both predict totals.
- No assuming System B edges are valid because the pipeline runs. Running ≠ validated.
- No work on System B signal classification without a validation artifact establishing that per-minute rate × projected minutes produces real edge over market prices.
- No deployment claims for any system without both (a) a validation artifact and (b) verified 2026 live output.
- No treating anchor v1/v2/v3 as interchangeable — each has different training data and feature sets.
