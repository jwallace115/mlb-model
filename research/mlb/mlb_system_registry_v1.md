# MLB System Registry V1

**Date:** 2026-05-11
**Status:** Classification snapshot. No system promotion, activation, or code change permitted from this document alone.

---

## A. Executive Summary

- **Systems classified:** 15
- **Currently trustable as live edge:** 0 (V1 Totals engine is PAUSED at ROI=-11.8%)
- **Shadow-only (active data collection):** 10 (YRFI, Night Dog, BP Adv Dog, P1B, CS013, CS004, CS028, KP04, Combined Short Exit, Team Total)
- **Unvalidated live/shadow:** 2 (Night Dog, BP Adv Dog — no standalone research validation artifact found)
- **Dead/archived/broken:** 3 (F5, ADJ family, S12 performance tracker stale but overlay runs)
- **UNKNOWN critical fields:** VM cron verification deferred for all systems

---

## B. System Table

| System | Market | Validation | Pricing | Live Output | Identity Match | Status | Primary Concern |
|---|---|---|---|---|---|---|---|
| V1 Totals Engine | FG totals UNDER | positive (Ph 7-9) | real closing | Fresh | MATCH | VALIDATED_SHADOW (PAUSED) | ROI=-11.8% hard stop |
| Night Dog | ML dog | NONE FOUND | unknown | Fresh | N/A | UNVALIDATED_SHADOW | No validation artifact |
| BP Adv Dog | ML dog | NONE FOUND | unknown | Fresh | N/A | UNVALIDATED_SHADOW | No validation artifact |
| P1B Cold-Warm | FG totals OVER | positive (inline) | real closing | Stale (Jun-Sep) | PARTIAL | VALIDATED_SHADOW | Seasonal; not firing yet |
| CS013 | FG UNDER overlay | positive | proxy | Fresh | PARTIAL | VALIDATED_SHADOW | Overlay on paused V1 |
| CS004 | FG UNDER overlay | positive | proxy | Fresh | PARTIAL | VALIDATED_SHADOW | Overlay on paused V1 |
| CS028 | FG UNDER overlay | mixed | proxy | Fresh | UNKNOWN | UNVALIDATED_SHADOW | NEEDS_MORE_DATA verdict |
| KP04 | Pitcher K OVER | positive | real prices | Fresh | PARTIAL | VALIDATED_SHADOW | Props market |
| Combined Short Exit | FG OVER amplifier | positive | proxy | Fresh | PARTIAL | VALIDATED_SHADOW | OVER amplifier only |
| YRFI Robust V1 | FD YRFI | positive (perm) | real FD | Fresh | MATCH | VALIDATED_SHADOW | Two-season finding |
| NRFI Selector | NRFI parlay | negative (-0.6pp) | real F5 | Fresh | MATCH | VALIDATED_SHADOW (INFO) | Not edge — filter only |
| S12 Overlay | FG UNDER overlay | mixed (DIMINISHED) | real closing | Fresh | PARTIAL | VALIDATED_SHADOW | Overall ROI negative |
| P09 Overlay | FG UNDER overlay | positive (ADVANCE) | proxy | Not verified | UNKNOWN | UNCLASSIFIED | Advanced but undeployed |
| F5 Totals Engine | F5 totals | UNKNOWN | real closing | Stale (Apr 19) | UNKNOWN | ARCHIVED | Engine archived |
| ADJ Family | FG UNDER | negative (DIMINISHED) | real closing | Not producing | MISMATCH | VALIDATED_NEGATIVE_DEAD | All 5 DIMINISHED |
| Team Total Signal | Team totals | positive (Ph 6) | real TT lines | Fresh | PARTIAL | VALIDATED_SHADOW | Research-grade |

---

## C. Detailed System Entries

### 1. V1 Totals Engine

1. **SYSTEM NAME:** MLB Sim Engine V1 — Full-Game Totals
2. **MARKET:** Full-game totals UNDER
3. **THESIS:** Phase 9 Ridge model (25 features, alpha=50) predicts game totals; fires UNDER when model edge exceeds threshold
4. **VALIDATION ARTIFACT:** `sim/` Phase 4-9 backtests; memory/MEMORY.md references Phase 8 STRONG tier 2025 OOS +2.3%
5. **VALIDATION RESULT:** positive (in-sample and OOS, but 2026 live ROI is -11.8% at N=57)
6. **PRICING BASIS:** real sportsbook prices (DraftKings/FanDuel closing lines)
7. **PIT-SAFETY STATUS:** PARTIAL — same-day pipeline verified; historical feature construction not fully audited this session
8. **LIVE IMPLEMENTATION FILES:** `mlb_sim/pipeline/daily_signal_generator.py`, `mlb_sim/pipeline/performance_tracker.py`, `mlb_sim/pipeline/mlb_two_pass.py`, `mlb_sim/pipeline/engine_status.json` (PAUSED)
9. **LIVE OUTPUT FILES:** `mlb_sim/logs/signals_2026.json`, `mlb_sim/logs/rolling_performance_shadow_2026.json`
10. **CONSUMER PATH:** Dashboard MLB tab; home tab signal count
11. **CRON / LAUNCHD:** Mac `com.mlbmodel.daily.plist`; VM cron suspected
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** MATCH
13. **GRADING PATH:** `performance_tracker.py` grades against MLB Stats API actuals
14. **OUTPUT FRESHNESS:** Fresh
15. **STATUS:** VALIDATED_SHADOW (PAUSED) — hard stop at ROI=-11.8% N=57
16. **OUT-OF-SCOPE:** CS overlays, S12, P09, ADJ, YRFI, NRFI, sides
17. **OPEN QUESTIONS:** VM cron exact entries; resume conditions

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
14. **OUTPUT FRESHNESS:** Fresh (within 3 days)
15. **STATUS:** UNVALIDATED_SHADOW
16. **OUT-OF-SCOPE:** BP Adv Dog (same script, different signal)
17. **OPEN QUESTIONS:** Validation origin?

### 3. BP Adv Dog

Same schema as Night Dog. **STATUS: UNVALIDATED_SHADOW.** `mlb/logs/mlb_mixed_bp_adv_dog_shadow_2026.json`. Same open questions.

### 4. P1B Cold-Warm EARLY_HEAVY Over

1. **SYSTEM NAME:** P1B Cold-Warm EARLY_HEAVY Full-Game Over
2. **MARKET:** Full-game totals OVER
3. **THESIS:** FG OVER at cold-climate outdoor parks, temp >=75F, EARLY_HEAVY scoring path, Jun-Sep only
4. **VALIDATION ARTIFACT:** Inline in script docstring; session log references. No standalone report.
5. **VALIDATION RESULT:** positive (per session references)
6. **PRICING BASIS:** real closing prices
7. **PIT-SAFETY STATUS:** PARTIAL
8. **LIVE IMPLEMENTATION FILES:** `mlb/pipeline/mlb_totals_p1b_shadow.py`
9. **LIVE OUTPUT FILES:** `mlb/logs/mlb_p1b_coldwarm_earlyheavy_over_shadow_2026.json`
10. **CONSUMER PATH:** Dashboard MLB tab
11. **CRON / LAUNCHD:** VM cron suspected
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** PARTIAL MATCH
13. **GRADING PATH:** `mlb_totals_p1b_shadow.py --grade`
14. **OUTPUT FRESHNESS:** Stale (fires Jun-Sep only)
15. **STATUS:** VALIDATED_SHADOW — seasonal
16. **OUT-OF-SCOPE:** V1 totals
17. **OPEN QUESTIONS:** Standalone backtest report?

### 5-8. CS013, CS004, CS028, KP04

**CS013** — Starter deterioration UNDER overlay. Validation: `research/signal_discovery/cs013_diagnostics/`. **STATUS: VALIDATED_SHADOW.** Proxy pricing. Fresh output.

**CS004** — Cold under interaction. Validation: `research/signal_discovery/cs004_under_interactions/`. **STATUS: VALIDATED_SHADOW.** Proxy pricing. Fresh output.

**CS028** — Bullpen positive state UNDER amplifier. Validation: `research/signal_discovery/test_batch_4/CS028_results.md` — verdict NEEDS_MORE_DATA. **STATUS: UNVALIDATED_SHADOW.** Fresh output.

**KP04** — Breaking-ball pitcher × high-K lineup (K OVER). Validation: `research/signal_discovery/test_kprops/KP04_results.md` — verdict PASS, ROI +9.57%. Real prices. **STATUS: VALIDATED_SHADOW.** Fresh output.

### 9. Combined Short Exit

OVER amplifier from durable starters. Validation: `mlb_sim/pipeline/combined_short_exit_shadow_config.json` — walk-forward 2024 +8.4%, 2025 +1.8%. Permutation 88th percentile. **STATUS: VALIDATED_SHADOW.** Proxy pricing. Fresh output.

### 10. YRFI Robust Family V1

1. **SYSTEM NAME:** YRFI Robust Family V1
2. **MARKET:** FanDuel YRFI (Over 0.5)
3. **THESIS:** 6 permutation-confirmed launch-angle/contact interaction signals; 1+/2+/3+ consensus
4. **VALIDATION ARTIFACT:** `research/first_inning_props/mlb_first_inning_fanduel_v1/` — corrected ROI +16.5% to +37.3%. Permutation emp_p 0.001-0.021. Two-season (2024 disc, 2025 OOS).
5. **VALIDATION RESULT:** positive
6. **PRICING BASIS:** real FanDuel American odds
7. **PIT-SAFETY STATUS:** PARTIAL — frozen 2024 tercile thresholds; home V6 row construction
8. **LIVE IMPLEMENTATION FILES:** `mlb/pipeline/yrfi_shadow_daily.py`, `mlb/pipeline/pull_yrfi_odds_daily.py`, `mlb/pipeline/yrfi_grading_utils.py`
9. **LIVE OUTPUT FILES:** `mlb/logs/yrfi_shadow_2026.json`, `mlb/logs/yrfi_odds_2026.json`
10. **CONSUMER PATH:** Dashboard MLB tab — YRFI section + tracker
11. **CRON / LAUNCHD:** VM cron: odds 7:05am, tracker 7:30am ET
12. **RESEARCH OBJECT VS LIVE OBJECT MATCH:** MATCH
13. **GRADING PATH:** MLB Stats API linescore via `yrfi_grading_utils.py`
14. **OUTPUT FRESHNESS:** Fresh
15. **STATUS:** VALIDATED_SHADOW — two-season finding. Promotion gates: 2+ N>=100, ROI>+5%.
16. **OUT-OF-SCOPE:** NRFI, V1 totals
17. **OPEN QUESTIONS:** None

### 11. NRFI Selector

**STATUS: VALIDATED_SHADOW (INFO).** Not an edge system — explicitly documented as -0.6pp edge. Parlay helper / entertainment selector. `mlb/pipeline/nrfi_daily_selector.py`. Fresh output.

### 12. S12 Overlay

Validation: `research/recovery/s12_standalone_revalidation/S12_STANDALONE_FINAL_VERDICT.md` — DIMINISHED (overall ROI -0.8%, OOS 2025 +4.7%). **STATUS: VALIDATED_SHADOW** (mixed result). Performance tracker active.

### 13. P09 Overlay

Validation: `research/signal_scanner/p09_revalidation.md` — ADVANCE (5/5). Live implementation exists but deployment path unclear. **STATUS: UNCLASSIFIED.**

### 14. F5 Totals Engine

**STATUS: ARCHIVED.** Signal B closure per master doc. Output stale since Apr 19. Removed from health check.

### 15. ADJ Family

Validation: `research/recovery/adj_standalone_rebuild/ADJ_MASTER_KEEP_KILL_MEMO.md` — all 5 signals DIMINISHED. Live implementation uses different gate than research (combined>0 vs p_under>0.57 co-filter). **STATUS: VALIDATED_NEGATIVE_DEAD.** Identity MISMATCH.

### 16. Team Total Signal

Research-grade shadow. Validation: `research/mlb_distribution/phase6_team_total_engine.md`. Uses Phase 6 fair-value formula. Real posted team total lines via `pull_team_totals.py`. **STATUS: VALIDATED_SHADOW.** Fresh output.

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
| `mlb_sim/logs/f5_runline_2026.json` | Archived F5 system |

---

## E. Drift / Unsupported Claims

| Claim | Evidence | Verdict |
|---|---|---|
| "V1 engine active" | `engine_status.json`: PAUSED at -11.8% N=57 | DRIFT |
| "ADJ family deploy-ready" | All 5 DIMINISHED | DRIFT |
| "Phase 8 STRONG 2025 OOS +2.3%" | Referenced in MEMORY.md only | PARTIAL — plausible but no standalone artifact |

---

## F. Open Questions for Jeff + ChatGPT

1. V1 Engine PAUSED at -11.8%: resume conditions?
2. Night Dog / BP Adv Dog: validate formally or reclassify as exploratory?
3. CS overlay value if V1 is paused?
4. P09 deployment path?
5. YRFI promotion gate timing (~50-100 game-days for N>=100)?
6. VM cron verification needed for all systems.
