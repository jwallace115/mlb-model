# MLB System Registry V2

**Date:** 2026-05-12
**Supersedes:** research/mlb/mlb_system_registry_v1.md
**Source of corrections:** research/mlb/mlb_system_registry_v1_review.md
**Status:** Decision baseline. No MLB system promotion, activation, or code change permitted from this document alone.

---

## Changes from v1

**Critical corrections applied (3):**
- [V1 totals data refresh] — ROI updated from -11.8%/N=57 to -17.5%/N=50 per current `engine_status.json`
- [V1 totals status label] — Changed from VALIDATED_SHADOW (PAUSED) to UNVALIDATED_SHADOW (PAUSED). Historical validation is disputed/void per master doc; live inference continues for comparison only.
- [P09 reclassification] — Changed from UNCLASSIFIED to VALIDATED_SHADOW (PAUSED with V1). Active config with stake rules and positive validation (ADVANCE 5/5) found.

**Non-critical corrections applied (4):**
- [S12 count/summary precision] — Moved S12 from dead/archived count to shadow count in executive summary
- [CS028 precision] — Changed from UNVALIDATED_SHADOW to VALIDATED_SHADOW (INSUFFICIENT_SAMPLE). Validation artifact exists with NEEDS_MORE_DATA verdict.
- [YRFI bug/history note] — Added note about ROI calculation bug discovery and correction (original +50-53% inflated; corrected +16-37%)
- [S12 config evidence] — Noted that `s12_overlay_config.json` does not contain status/active fields; classification based on fresh performance tracker output

**Missing systems added or accounted for (4):**
- [NRFI Helper micro model] — Added as separate system (v1_review Section D)
- [SGP Phase 0] — Added to accounting gaps (v1_review Section D)
- [CLV capture] — Added to accounting gaps as infrastructure (v1_review Section D)
- [F5 Runline] — Explicitly added as ARCHIVED (v1_review Section D)

**Open issues for v2 review:**
- V1 totals status: UNVALIDATED_SHADOW chosen because historical validation is void. If backtests are later re-validated with clean PIT-safe construction, status could be upgraded. This is a v2 judgment call, not a permanent classification.
- P09 live output and grading path not independently verified. VALIDATED_SHADOW label is based on config + research, not on confirmed fresh output inspection.

---

## A. Executive Summary

- **Systems classified:** 19 (15 from v1 + 4 added/split)
- **Currently trustable as live edge:** 0
- **Shadow-only (validated, active data collection):** 10 (YRFI, P1B, CS013, CS004, KP04, Combined Short Exit, Team Total, S12, NRFI Selector INFO, CS028 insufficient sample)
- **Shadow-only (unvalidated):** 2 (Night Dog, BP Adv Dog)
- **Shadow-only (paused):** 3 (V1 Totals, P09, NRFI Helper)
- **Dead/archived:** 4 (F5 Totals, F5 Runline, ADJ Family, none currently active)
- **UNKNOWN critical fields:** VM cron verification deferred for all systems
- **ADJ May 15 activation:** DELAYED — all 5 signals DIMINISHED

---

## B. System Table

| System | Market | Validation | Pricing | Status | Primary Concern |
|---|---|---|---|---|---|
| V1 Totals Engine | FG totals UNDER | void/disputed | real closing | UNVALIDATED_SHADOW (PAUSED) | ROI=-17.5% N=50 hard stop |
| Night Dog | ML dog | NONE FOUND | unknown | UNVALIDATED_SHADOW | No validation artifact |
| BP Adv Dog | ML dog | NONE FOUND | unknown | UNVALIDATED_SHADOW | No validation artifact |
| P1B Cold-Warm | FG totals OVER | positive (inline) | real closing | VALIDATED_SHADOW | Seasonal Jun-Sep |
| CS013 | FG UNDER overlay | positive | proxy | VALIDATED_SHADOW | Overlay on paused V1 |
| CS004 | FG UNDER overlay | positive | proxy | VALIDATED_SHADOW | Overlay on paused V1 |
| CS028 | FG UNDER overlay | insufficient sample | proxy | VALIDATED_SHADOW (INSUFFICIENT_SAMPLE) | NEEDS_MORE_DATA verdict |
| KP04 | Pitcher K OVER | positive | real prices | VALIDATED_SHADOW | Props market |
| Combined Short Exit | FG OVER amplifier | positive | proxy | VALIDATED_SHADOW | OVER amplifier only |
| YRFI Robust V1 | FD YRFI | positive (perm) | real FD | VALIDATED_SHADOW | Two-season finding |
| NRFI Selector | NRFI parlay | negative (-0.6pp) | real F5 | VALIDATED_SHADOW (INFO) | Not edge — filter only |
| NRFI Helper | NRFI micro model | UNKNOWN | UNKNOWN | UNVALIDATED_SHADOW | First-pass; needs review |
| S12 Overlay | FG UNDER overlay | mixed (DIMINISHED) | real closing | VALIDATED_SHADOW | Overall ROI negative |
| P09 Overlay | FG UNDER overlay | positive (ADVANCE) | proxy | VALIDATED_SHADOW (PAUSED with V1) | Active config but V1 paused |
| F5 Totals Engine | F5 totals | UNKNOWN | real closing | ARCHIVED | Engine archived |
| F5 Runline | F5 runline | contaminated | real closing | ARCHIVED | Contaminated; archived |
| ADJ Family | FG UNDER | negative (DIMINISHED) | real closing | VALIDATED_NEGATIVE_DEAD | All 5 DIMINISHED |
| Team Total Signal | Team totals | positive (Ph 6) | real TT lines | VALIDATED_SHADOW | Research-grade |
| SGP Phase 0 | SGP legs | UNKNOWN | UNKNOWN | UNCLASSIFIED | Data collection only |

---

## C. Detailed System Entries

### 1. V1 Totals Engine

1. **SYSTEM NAME:** MLB Sim Engine V1 — Full-Game Totals
2. **MARKET:** Full-game totals UNDER
3. **THESIS:** Phase 9 Ridge model (25 features, alpha=50) predicts game totals; fires UNDER when model edge exceeds threshold
4. **VALIDATION ARTIFACT:** `sim/` Phase 4-9 backtests exist. However, master doc states historical validation is void/contaminated due to feature construction issues. MEMORY.md references Phase 8 STRONG tier 2025 OOS +2.3%, but Phase 7 overall was NOT profitable OOS (-0.5%).
5. **VALIDATION RESULT:** void/disputed — backtests exist but their validity is disputed. 2026 live performance: ROI=-17.5% at N=50.
6. **PRICING BASIS:** real sportsbook prices (DraftKings/FanDuel closing lines)
7. **PIT-SAFETY STATUS:** PARTIAL — same-day pipeline verified; historical feature construction is the source of the validation dispute
8. **LIVE IMPLEMENTATION FILES:** `mlb_sim/pipeline/daily_signal_generator.py`, `mlb_sim/pipeline/performance_tracker.py`, `mlb_sim/pipeline/mlb_two_pass.py`, `mlb_sim/pipeline/engine_status.json` (PAUSED)
9. **LIVE OUTPUT FILES:** `mlb_sim/logs/signals_2026.json`, `mlb_sim/logs/rolling_performance_shadow_2026.json`
10. **CONSUMER PATH:** Dashboard MLB tab; home tab signal count
11. **CRON / LAUNCHD:** Mac `com.mlbmodel.daily.plist`; VM cron suspected
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** MATCH (live pipeline is mechanically clean; validation dispute is about historical construction)
13. **GRADING PATH:** `performance_tracker.py` grades against MLB Stats API actuals
14. **OUTPUT FRESHNESS:** Fresh (engine runs daily but is PAUSED — no new signals generated)
15. **STATUS:** UNVALIDATED_SHADOW (PAUSED) — Historical validation void/disputed. Live inference continues mechanically for 2026 comparison tracking only. Hard stop at ROI=-17.5% N=50. Resume requires manual authorization. Status changed from v1 VALIDATED_SHADOW because "VALIDATED" prefix implied the historical backtests were trustworthy, which is disputed.
16. **OUT-OF-SCOPE:** CS overlays, S12, P09, ADJ, YRFI, NRFI, sides
17. **OPEN QUESTIONS:** Resume conditions; whether historical validation can be re-run with clean PIT-safe construction

### 2. Night Dog

1. **SYSTEM NAME:** MLB Sides — Night Dog
2. **MARKET:** Moneyline dog
3. **THESIS:** Dog ML when night game, MIXED class
4. **VALIDATION ARTIFACT:** NONE FOUND
5. **VALIDATION RESULT:** not validated
6. **PRICING BASIS:** unknown
7. **PIT-SAFETY STATUS:** UNKNOWN
8. **LIVE IMPLEMENTATION FILES:** `mlb/pipeline/mlb_sides_daily_shadow.py`
9. **LIVE OUTPUT FILES:** `mlb/logs/mlb_mixed_night_dog_shadow_2026.json`
10. **CONSUMER PATH:** Dashboard MLB tab
11. **CRON / LAUNCHD:** VM cron suspected
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** NOT APPLICABLE
13. **GRADING PATH:** `mlb_sides_daily_shadow.py --grade`
14. **OUTPUT FRESHNESS:** Fresh
15. **STATUS:** UNVALIDATED_SHADOW
16. **OUT-OF-SCOPE:** BP Adv Dog (same script, different signal)
17. **OPEN QUESTIONS:** Validation origin?

### 3. BP Adv Dog

Same schema as Night Dog. **STATUS: UNVALIDATED_SHADOW.** Same open questions.

### 4. P1B Cold-Warm EARLY_HEAVY Over

**STATUS: VALIDATED_SHADOW — seasonal (Jun-Sep).** Validation: inline in script docstring + session log references. No standalone report. Real closing prices. Fires Jun-Sep only; output stale outside season window.

### 5. CS013

**STATUS: VALIDATED_SHADOW.** Starter deterioration UNDER overlay. Validation: `research/signal_discovery/cs013_diagnostics/`. Proxy pricing. Fresh output. Overlay on paused V1.

### 6. CS004

**STATUS: VALIDATED_SHADOW.** Cold under interaction. Validation: `research/signal_discovery/cs004_under_interactions/`. Proxy pricing. Fresh output.

### 7. CS028

**STATUS: VALIDATED_SHADOW (INSUFFICIENT_SAMPLE).** Bullpen positive state UNDER amplifier. Validation: `research/signal_discovery/test_batch_4/CS028_results.md` — verdict NEEDS_MORE_DATA (N=7 extreme 2025 case). v1 classified as UNVALIDATED; v2 corrected because validation artifact exists with an inconclusive result, which is different from no validation. Proxy pricing. Fresh output.

### 8. KP04

**STATUS: VALIDATED_SHADOW.** Breaking-ball pitcher × high-K lineup (K OVER). Validation: `research/signal_discovery/test_kprops/KP04_results.md` — verdict PASS, ROI +9.57%. Real prices. Fresh output. Independent of V1 totals — operates in props market.

### 9. Combined Short Exit

**STATUS: VALIDATED_SHADOW.** OVER amplifier from durable starters. Validation: `mlb_sim/pipeline/combined_short_exit_shadow_config.json` — walk-forward 2024 +8.4%, 2025 +1.8%. Permutation 88th percentile. Proxy pricing. Fresh output.

### 10. YRFI Robust Family V1

1. **SYSTEM NAME:** YRFI Robust Family V1
2. **MARKET:** FanDuel YRFI (Over 0.5)
3. **THESIS:** 6 permutation-confirmed launch-angle/contact interaction signals; 1+/2+/3+ consensus tiers
4. **VALIDATION ARTIFACT:** `research/first_inning_props/mlb_first_inning_fanduel_v1/` — Two-season (2024 disc, 2025 OOS). Permutation emp_p 0.001-0.021. **Note:** Original ROI figures (+50-53%) were inflated by an operator precedence bug in the profit calculation. Corrected ROI: +16.5% to +37.3% across 8 ROBUST signals.
5. **VALIDATION RESULT:** positive (corrected)
6. **PRICING BASIS:** real FanDuel American odds
7. **PIT-SAFETY STATUS:** PARTIAL — frozen 2024 tercile thresholds; home V6 row construction
8. **LIVE IMPLEMENTATION FILES:** `mlb/pipeline/yrfi_shadow_daily.py`, `mlb/pipeline/pull_yrfi_odds_daily.py`, `mlb/pipeline/yrfi_grading_utils.py`
9. **LIVE OUTPUT FILES:** `mlb/logs/yrfi_shadow_2026.json`, `mlb/logs/yrfi_odds_2026.json`
10. **CONSUMER PATH:** Dashboard MLB tab — YRFI section + tracker
11. **CRON / LAUNCHD:** VM cron: odds 7:05am, tracker 7:30am ET
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** MATCH
13. **GRADING PATH:** MLB Stats API linescore via `yrfi_grading_utils.py`
14. **OUTPUT FRESHNESS:** Fresh
15. **STATUS:** VALIDATED_SHADOW — two-season finding. Promotion gates: 2+ tier N>=100, ROI>+5%, hit>BE+3pp, 3+ months positive.
16. **OUT-OF-SCOPE:** NRFI, V1 totals
17. **OPEN QUESTIONS:** None

### 11. NRFI Selector

**STATUS: VALIDATED_SHADOW (INFO).** Not an edge system — explicitly documented as -0.6pp edge. Parlay helper / entertainment selector. `mlb/pipeline/nrfi_daily_selector.py`. Fresh output. Real F5 closing lines.

### 12. NRFI Helper (micro model)

*Added in v2 per v1_review Section D.*

1. **SYSTEM NAME:** NRFI Parlay Helper — Micro Model
2. **MARKET:** NRFI (first-inning scoring probability)
3. **THESIS:** Micro model using TTO features, Statcast archetype classification, and top-3 lineup stability to score NRFI quality per game
4. **VALIDATION ARTIFACT:** UNKNOWN — `research/recovery/nrfi_phase5_small_engine/NRFI_PHASE5_EXEC_SUMMARY.md` exists but relationship to live micro model not verified
5. **VALIDATION RESULT:** UNKNOWN
6. **PRICING BASIS:** UNKNOWN
7. **PIT-SAFETY STATUS:** UNKNOWN
8. **LIVE IMPLEMENTATION FILES:** `mlb/pipeline/nrfi_helper_daily.py`
9. **LIVE OUTPUT FILES:** `research/mlb_first_inning/nrfi_shadow_log_2026.json`
10. **CONSUMER PATH:** UNKNOWN — not on dashboard
11. **CRON / LAUNCHD:** VM cron suspected; Mac launchd not found
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** UNKNOWN
13. **GRADING PATH:** `nrfi_helper_daily.py --grade`
14. **OUTPUT FRESHNESS:** UNKNOWN
15. **STATUS:** UNVALIDATED_SHADOW
16. **OUT-OF-SCOPE:** NRFI Selector (different system, different approach)
17. **OPEN QUESTIONS:** First-pass classification from v1_review Section D. Requires v2-review pass to validate.

### 13. S12 Overlay

**STATUS: VALIDATED_SHADOW.** CSW/xFIP UNDER overlay. Validation: `research/recovery/s12_standalone_revalidation/S12_STANDALONE_FINAL_VERDICT.md` — DIMINISHED (overall ROI -0.8%, OOS 2025 +4.7%). Performance tracker output fresh (May 12). Note: `s12_overlay_config.json` does not contain explicit status/active fields; classification based on fresh `s12_overlay_performance_2026.json` output. Embedded in V1 pipeline, which is PAUSED — S12 overlay monitoring continues via separate tracker.

### 14. P09 Overlay

1. **SYSTEM NAME:** P09 — Contact Suppression UNDER Overlay
2. **MARKET:** Full-game totals UNDER (overlay)
3. **THESIS:** `((home_hh + away_hh)/2) * park_run_factor` — LOW values predict UNDER
4. **VALIDATION ARTIFACT:** `research/signal_scanner/p09_revalidation.md` — ADVANCE (5/5 score). Permutation PASS. Season-stable. Robust. Independent.
5. **VALIDATION RESULT:** positive
6. **PRICING BASIS:** proxy (research used closing totals, not bet-level prices)
7. **PIT-SAFETY STATUS:** UNKNOWN
8. **LIVE IMPLEMENTATION FILES:** `mlb_sim/pipeline/p09_overlay.py`, `mlb_sim/pipeline/p09_overlay_config.json`
9. **LIVE OUTPUT FILES:** UNKNOWN — not independently verified
10. **CONSUMER PATH:** Embedded in V1 daily_signal_generator
11. **CRON / LAUNCHD:** Runs within V1 pipeline (PAUSED)
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** UNKNOWN — config shows `overlay_status: ACTIVE` with stake rules, but live/research threshold match not verified
13. **GRADING PATH:** Via V1 engine grader (PAUSED)
14. **OUTPUT FRESHNESS:** UNKNOWN
15. **STATUS:** VALIDATED_SHADOW (PAUSED with V1) — Positive validation exists. Active config with stake multipliers (`p09_only: 1.25, both: 1.5`). But runs within V1 which is PAUSED. Changed from v1 UNCLASSIFIED because validation + active config provide sufficient evidence for classification.
16. **OUT-OF-SCOPE:** S12 (separate overlay), ADJ (separate overlay family)
17. **OPEN QUESTIONS:** Live output and grading not independently verified. P09 requires decision review before any live-money interpretation.

### 15. F5 Totals Engine

**STATUS: ARCHIVED.** Signal B closure per master doc. Output stale since Apr 19. Removed from health check.

### 16. F5 Runline

*Added in v2 per v1_review Section D.*

**STATUS: ARCHIVED.** `mlb_sim/pipeline/f5_runline_signal_generator.py`, `mlb_sim/logs/f5_runline_2026.json`. Archived alongside F5 Totals. `f5_runline_status.json` notes: "Clean PIT-safe backtest: 53.9% hit rate, -6.2% ROI at -135. Original +27.9% was contaminated."

### 17. ADJ Family

**STATUS: VALIDATED_NEGATIVE_DEAD.** All 5 signals DIMINISHED per `research/recovery/adj_standalone_rebuild/ADJ_MASTER_KEEP_KILL_MEMO.md`. Identity MISMATCH: live fires on `combined > 0` alone; research required `p_under > 0.57` co-filter. ADJ May 15 activation remains DELAYED.

### 18. Team Total Signal

**STATUS: VALIDATED_SHADOW.** Research-grade shadow. Phase 6 fair-value formula. Real posted team total lines via `pull_team_totals.py`. Fresh output.

### 19. SGP Phase 0

*Added in v2 per v1_review Section D.*

**STATUS: UNCLASSIFIED.** `mlb/sgp_phase0/collect_leg_prices.py` — SGP leg price collector. Runs daily via Mac launchd `com.iamnotuncertain.sgp_phase0`. Data collection only. No signal generation, no validation artifact. First-pass classification from v1_review Section D. Requires v2-review pass to validate.

---

## D. Accounting Gaps

| Artifact | Notes |
|---|---|
| `mlb_sim/pipeline/line_overrides.py` | Infrastructure |
| `mlb_sim/pipeline/line_snapshot_store.py` | Infrastructure |
| `mlb_sim/pipeline/mlb_scratch_checker.py` | Infrastructure |
| `mlb_sim/pipeline/parlay_tracker.py` | Unclassified tracker |
| `mlb/pipeline/lineup_timing_snapshot.py` | Data collection infrastructure |
| `mlb_sim/logs/shadow_signals_2026.json` | V1 derivative output |
| `shared/closing_line_runner.py` | CLV capture infrastructure (v1_review Section D) |

---

## E. Drift / Unsupported Claims

| Claim | Evidence | Verdict |
|---|---|---|
| "V1 engine active" | `engine_status.json`: PAUSED at ROI=-17.5% N=50 | DRIFT |
| "V1 engine PAUSED at -11.8% N=57" (v1 registry) | `engine_status.json` actually shows -17.5% N=50 | DRIFT (stale data in v1) |
| "ADJ family deploy-ready" | All 5 DIMINISHED | DRIFT |
| "Phase 8 STRONG 2025 OOS +2.3%" | Referenced in MEMORY.md only; Phase 7 overall OOS was -0.5% | PARTIAL — STRONG tier claim plausible but overall system OOS was negative |

---

## F. Open Questions for Jeff + ChatGPT

1. V1 Engine PAUSED at -17.5%: resume conditions? Can historical validation be re-run with clean PIT-safe construction?
2. Night Dog / BP Adv Dog: validate formally or reclassify as exploratory?
3. CS overlay value if V1 is paused? CS013/CS004 are overlays on a paused parent system.
4. P09 deployment path? Has positive validation and active config but runs within PAUSED V1.
5. YRFI promotion gate timing (~50-100 game-days for N>=100 at 2+ tier)?
6. VM cron verification needed for all systems.
7. NRFI Helper micro model: relationship to NRFI Selector? Separate system or merged classification?

---

## G. Decision Implications

- No MLB implementation, code change, or activation should occur until this v2 is reviewed and accepted.
- ADJ May 15 activation remains DELAYED — all 5 signals are VALIDATED_NEGATIVE_DEAD.
- P09 requires decision review before any live-money interpretation, even though it has positive validation.
- V1 totals engine should not be resumed without addressing the historical validation dispute.
- YRFI and KP04 are the strongest validated shadow candidates but are in different markets (first-inning props and pitcher strikeouts, respectively).
- Missing-system entries added in v2 (NRFI Helper, SGP Phase 0, F5 Runline) require v2-review verification before being used for decisions.

---

## H. What is NOT Permitted Next

- Any code change before v2 review acceptance.
- Any ADJ activation.
- Any V1 resume without addressing validation dispute.
- Any while-I'm-here patches.
- Any live edge claim from any MLB system.
- Any work on a system without using this registry as the source of truth.
