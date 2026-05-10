# WNBA System Registry V1 — Review

**Date:** 2026-05-09
**Reviewer:** Claude Code audit-only session
**Output of review:** Pending Jeff + ChatGPT decision; no edits made.

---

## Executive Verdict

Registry v1 is **usable as a decision baseline**. The four-system classification (A/B/C/D) is fundamentally correct — these are genuinely separate systems with different markets, different models, and different validation histories. No system classification is clearly wrong, though two have minor precision issues documented below. No WNBA system is currently trustable as live edge: System A has validation but no live output; System B has live output but no validation; Systems C and D are dead. The registry accurately captures this state.

---

## Verdict Per System

### System A: WNBA Archetype Team Totals
- **Registry status:** VALIDATED_DEAD
- **Review verdict:** ACCURATE
- **Basis:** Contamination audit exists at claimed path (verified: 2,904 bytes, Apr 23). Contains 7-signal OOS table with per-signal ROI. 2026 signals JSON confirmed empty (len=0). Three pipeline stubs confirmed (one-line print statements). VM cron runs `assign_archetypes.py` daily but produces no 2026 output.
- **Nuance:** "VALIDATED" is slightly generous. The validation uses proxy ROI against historical closing totals at flat -110 equivalent, not real sportsbook prices with actual vig. The audit itself notes "proxy ROI" but the registry doesn't explicitly flag this distinction. ARCH_05 reversed in OOS (28.6% vs 55.6% discovery) — the registry notes this in breakpoints but the STATUS doesn't reflect partial instability.
- **Suggested v2 precision:** Add qualifier "VALIDATED_ON_PROXY_ODDS" or note that ROI is proxy, not real-price.

### System B: WNBA Player Props Shadow
- **Registry status:** UNVALIDATED_LIVE
- **Review verdict:** ACCURATE
- **Basis:** Exhaustive search for player-prop validation artifacts found zero results. No backtest, no OOS report, no contamination audit, no signal registry covering player props exists in `research/`. The "75.5% PRA variance" claim from the master doc has no corresponding artifact. Output files confirmed fresh (May 9 mtime on prop_candidates, clv_log, graded_results).
- **Nuance:** The registry correctly notes System B does NOT use `wnba/models/ridge_wnba.pkl`. Confirmed: `ridge_wnba.pkl` is only loaded by `wnba/pipeline/run_model.py` (System D). System B uses inline per-minute career rate heuristics.

### System C: WNBA Anchor Models
- **Registry status:** VALIDATED_DEAD
- **Review verdict:** QUESTIONABLE
- **Basis:** All three anchor versions have validation artifacts (summary texts, hypothesis registries). However, anchor v1's own validation shows RMSE 15.83 vs market 15.32 — the model is worse than the market. Calling this "VALIDATED" is technically accurate (validation exists) but misleading (the validation result is negative). v2/v3 have hypothesis registries with frozen thresholds but no summary performance reports were inspected to confirm whether they outperform v1.
- **Evidence:** `wnba_anchor/reports/anchor_model_summary.txt` shows "Market wins: True" and LEAN_OVER tier is INVERTED (-18.3% ROI). This is a failed validation, not a successful one.
- **Suggested v2 precision:** Either downgrade to "VALIDATED_NEGATIVE" (validation exists but result is negative) or split v1/v2/v3 into separate sub-entries with independent status. v2/v3 may have better results than v1 but this was not verified.

### System D: WNBA Game-Total Ridge
- **Registry status:** VALIDATED_DEAD
- **Review verdict:** ACCURATE
- **Basis:** Diagnostics artifact exists (verified: 1,700 bytes, Apr 2). Content confirms "Model RMSE: 17.78, Market RMSE: 15.32, Market wins: True, Recommendation: MARKET_ANCHOR_REBUILD." System D's own validation says don't deploy it. VM cron runs daily but feature table has 0 rows for 2026. `ridge_wnba.pkl` confirmed used only by System D.

---

## Accounting Gaps

| Artifact | Why it matters | Suggested v2 handling |
|---|---|---|
| `dashboard_components.py` (mentions WNBA) | Contains off-season suppression logic for WNBA health checks | Add as "infrastructure, not a system" |
| `dashboard_original_pre_refactor.py` | Old dashboard version, mentions WNBA | Add as ARCHIVED |
| `setup_launchd.py` | References WNBA launchd setup | Add as infrastructure |
| `shared/health_check.py` | WNBA signal freshness monitoring | Add as infrastructure |
| `research/recovery/site_reset/apply_dashboard_patch.py` | References WNBA tab | Add as ARCHIVED |
| `wnba_anchor_v2/pipeline/build_anchor_v2_features.py` | Not mentioned in registry System C entry as individual file | Add to System C file list |
| `wnba_anchor_v3/pipeline/build_anchor_v3_features.py` | Not mentioned in registry System C entry as individual file | Add to System C file list |
| `research/wnba/archetypes/team_game_state_profiles.parquet` | Research artifact not listed | Add to System A research artifacts |
| `research/wnba/archetypes/team_season_profiles.parquet` | Research artifact not listed | Add to System A research artifacts |
| `research/wnba/archetypes/feature_market_proxy_check.csv` | Feature-to-market correlation check | Add to System A research artifacts |
| `wnba_archetype_board/reports/` directory | Contains historical_signal_performance.csv, backfill summary | Add to System A |
| `wnba/data/rolling_form.parquet` | 2021-2025 rolling form data | Classify under System D source data |
| `wnba/data/season_aggregates.parquet` | Season-level aggregates | Classify under System D source data |
| `wnba/data/starter_absence_events.parquet` | Research artifact | Add to unclassified |
| `wnba/data/player_identity.parquet` | Player identity lookup | Shared infrastructure, not system-specific |

---

## Status Logic Violations

| System | Registry status | Evidence problem | Suggested v2 correction |
|---|---|---|---|
| System C (anchor v1) | VALIDATED_DEAD | Validation result is NEGATIVE (model worse than market). "Validated" implies the validation succeeded. | Consider "VALIDATED_NEGATIVE_DEAD" or split v1 from v2/v3 |
| System D | VALIDATED_DEAD | Consistent — validation exists and explicitly says model loses to market. Status is correct but could note validation was negative. | Minor: add "validation result: negative" qualifier |

---

## Internal Contradictions

1. **System D's `wnba/models/ridge_wnba.pkl` is in the System D section but could be confused with System B.** Registry correctly notes "System B does NOT use ridge_wnba.pkl" but the proximity of `wnba/models/` to `wnba/shadow/` could cause future confusion. Verified: no cross-reference exists.

2. **System A and System D share `wnba/data/game_index.parquet` as input.** Both `assign_archetypes.py` and `build_features.py` read this file. Registry lists it under System D's implementation but doesn't note System A also reads it. This is a shared data dependency, not a contradiction, but should be documented in v2.

3. **System B's `season_updater.py` writes to files that System D reads** (`team_game_logs.parquet`, `game_index.parquet`, `player_game_logs.parquet`). The registry lists these as System D output files but they're now also written by System B's updater. In v2, these should be classified as "shared data layer" rather than belonging to either system exclusively.

4. **OUT-OF-SCOPE lists are symmetric and consistent.** Each system excludes the other three. No inconsistency found.

5. **No CRON/LAUNCHD overlap.** VM cron entries are System A + System D. Mac launchd entries are System B. System C has no schedule. No double-scheduling detected.

---

## Drift-Log Gaps

| Master doc claim | Registry treatment | Review verdict | Suggested v2 edit |
|---|---|---|---|
| "May 16 2026 activation" | Not in drift log | MISSING — should be noted. Season started May 8. May 16 was the planned deployment date from the contamination audit. The gap between plan and reality (System A not producing 2026 output) should be explicit. | Add to drift log |
| "+20.6% proxy ROI" | Listed as PARTIAL | ACCURATE treatment but the specific +20.6% number should be cross-referenced. It likely refers to the weighted average across all 7 signals, not a single signal. The contamination audit shows per-signal ROI ranging from -45.5% to +34.3%. | Clarify which signals contribute to the +20.6% figure |
| "Rate × minutes explains 75.5% of PRA variance" | Listed as SPEC_UNCLEAR | ACCURATE — no artifact found. Exhaustive search of research/ and wnba/ found zero mentions of "75.5" or "PRA variance" in any .md, .json, .py, or .txt file. This claim appears to exist only in the master doc / memory, with no backing artifact in the repo. | Upgrade from SPEC_UNCLEAR to DRIFT — claim has no repo evidence |
| "5 cron jobs active on VM" | Not in drift log | MISSING — VM has 5 WNBA-related cron entries but they belong to two different systems (System A: 1 entry, System D: 4 entries). "5 cron jobs" is technically true but conflates separate systems. | Add to drift log with system attribution |

---

## Recommended Registry Edits ONLY

- Add "VALIDATED_ON_PROXY_ODDS" qualifier to System A status, noting ROI is proxy not real-price
- Split System C into three sub-entries (v1/v2/v3) with independent validation status; v1 should be VALIDATED_NEGATIVE_DEAD
- Add shared data layer note for `game_index.parquet`, `team_game_logs.parquet`, `player_game_logs.parquet` — used by Systems A, B, and D
- Add missing artifacts from accounting gaps table
- Add "May 16 activation" and "5 cron jobs" to drift log
- Upgrade "75.5% PRA variance" from SPEC_UNCLEAR to DRIFT (no repo evidence)
- Add `wnba_anchor_v2/pipeline/` and `wnba_anchor_v3/pipeline/` individual files to System C entry
- Add research artifacts (`team_game_state_profiles.parquet`, `team_season_profiles.parquet`, `feature_market_proxy_check.csv`) to System A
- Note that `season_updater.py` writes to shared data files that System D reads — creates implicit coupling between System B and System D data layers

---

## Open Questions for Jeff + ChatGPT

1. **Should System B (player props) be allowed to produce signals when `low_history` clears (~May 14)?** There is no validation artifact. The per-minute heuristic has never been backtested. Permitting unvalidated signals to surface — even as shadow — creates a precedent that "running = valid."

2. **Should System A (archetypes) SEASON-mode signals (ARCH_03/05/07) be fast-tracked?** They could fire today using prior-season archetypes if only a write step were added. No feature builder or GMM assignment needed. This is the lowest-complexity path to the only validated WNBA edge.

3. **Are anchor v2/v3 superseded or candidates for revival?** They represent the most methodologically sound approach (market-anchor adjustment) but are completely dead. If System A's archetype signals are the deployment priority, are anchors abandoned?

4. **What is the source of the "+20.6% proxy ROI" and "75.5% PRA variance" claims?** Neither has a repo artifact. If these were computed in a prior Claude session without being saved to a research file, they may be hallucinated or stale.

5. **Should System D's VM cron entries be disabled?** They run daily, consume compute, produce "No games found for 2026," and are confirmed to perform worse than the market. The 4 cron entries could be removed or commented out.
