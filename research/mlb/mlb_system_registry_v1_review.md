# MLB System Registry V1 — Review

**Date:** 2026-05-12
**Reviewer:** Claude Code audit-only session
**Registry reviewed:** research/mlb/mlb_system_registry_v1.md

---

## A. Verdict

**ACCEPT WITH CORRECTIONS**

The four-system-tier classification structure is sound. System inventory is substantially complete (15 systems). Status labels are defensible for most systems. Three critical corrections are required before using this as a decision baseline.

---

## B. Critical Corrections Required

### 1. V1 Totals Engine — ROI figure is stale/wrong

**Registry claims:** ROI=-11.8% at N=57
**Repo evidence:** `engine_status.json` shows `"pause_reason": "Hard stop: ROI=-17.5% at N=50"`

The registry was written when engine_status.json had an older snapshot. The current file shows worse performance (-17.5% vs -11.8%) at a different N (50 vs 57). This is a factual error that affects the severity assessment.

**Required v2 edit:** Update all references to ROI=-17.5% at N=50, matching current `engine_status.json`.

### 2. V1 Totals Engine — STATUS label should reflect validation void

**Registry claims:** VALIDATED_SHADOW (PAUSED)
**Issue:** The master doc v38 states the historical validation is void/contaminated due to feature construction issues discovered in prior sessions. The registry labels it VALIDATED based on Phase 7-9 backtests, but if those backtests are contaminated, the "VALIDATED" prefix is misleading.

**Evidence from MEMORY.md:**
- Phase 7: "ROI @ edge≥1.0, P≥0.55, -110: 2024 **+6.5%** / 2025 **-0.5%** (NOT profitable OOS)"
- Phase 8 STRONG tier: "2025: −7.6% → +2.3% (+10pp)" — but Phase 7 overall was not profitable OOS
- 2026 live: -17.5% at N=50

**Recommended status:** UNVALIDATED_SHADOW (PAUSED) — if historical validation is void, the system cannot carry a VALIDATED prefix regardless of Phase 7-9 backtest existence. The backtests exist but their validity is disputed. Alternatively: VALIDATED_SHADOW (PAUSED, VALIDATION_DISPUTED) to preserve the nuance.

### 3. P09 Overlay — missing critical context

**Registry claims:** STATUS: UNCLASSIFIED. "Advanced but undeployed."
**Repo evidence:** `p09_overlay_config.json` shows `"overlay_status": "ACTIVE"` and `"stake_rules"` with bet sizing. This is not undeployed — it has an active config with stake multipliers.

**Required v2 edit:** Reclassify P09. It has a positive validation (ADVANCE 5/5), an active config, and is embedded in the V1 pipeline (which is PAUSED). Status should be VALIDATED_SHADOW (PAUSED with V1) or similar, not UNCLASSIFIED.

---

## C. Non-Critical Corrections / Wording Improvements

1. **S12 config status:** Registry says "Performance tracker active" but `s12_overlay_config.json` returns `status: None, active: None` — the config file doesn't have these fields. The performance tracker JSON is fresh (May 12), so the system IS running, but the config evidence is weaker than stated.

2. **Executive summary count:** Claims "3 dead/archived/broken" listing "F5, ADJ family, S12 performance tracker stale but overlay runs" — but S12 is listed as VALIDATED_SHADOW in the system table, not dead. The summary contradicts the table. S12 should be counted under shadow, not dead.

3. **CS028 status:** Registry says UNVALIDATED_SHADOW, but validation artifact exists (`CS028_results.md`) with verdict NEEDS_MORE_DATA. This is a validation that produced an inconclusive result, not absence of validation. Consider VALIDATED_SHADOW (INSUFFICIENT_SAMPLE) to match the WNBA registry pattern.

4. **YRFI validation note:** Registry correctly states "two-season finding" but should note the ROI bug discovery and correction more prominently — the original reported ROI (+50-53%) was inflated by an operator precedence bug; corrected ROI (+16-37%) is substantially lower.

---

## D. Missing Systems or Accounting Gaps

1. **NRFI Helper (micro model):** `mlb/pipeline/nrfi_helper_daily.py` — a separate system from the NRFI Selector. The helper uses a micro model with TTO features, Statcast archetype classification, and lineup stability checks. It writes to `research/mlb_first_inning/nrfi_shadow_log_2026.json`. Not listed in registry.

2. **MLb SGP Phase 0:** `mlb/sgp_phase0/collect_leg_prices.py` — SGP leg price collector. Runs daily via Mac launchd. Not classified.

3. **MLB CLV capture:** `shared/closing_line_runner.py` — captures closing lines. Runs via Mac launchd (`com.mlbmodel.clv.capture.plist`). Infrastructure, not a signal system, but should be noted.

4. **F5 Runline:** `mlb_sim/pipeline/f5_runline_signal_generator.py` and `mlb_sim/logs/f5_runline_2026.json` — listed in accounting gaps but should be explicitly noted as ARCHIVED alongside F5 totals.

---

## E. High-Drift Candidate Review

### S12 / P09

**Registry:** S12 = VALIDATED_SHADOW (mixed). P09 = UNCLASSIFIED.

**Repo evidence:**
- S12 standalone verdict is DIMINISHED (overall ROI -0.8%). Performance tracker is fresh (May 12). S12 overlay runs embedded in V1 pipeline.
- P09 overlay config shows `overlay_status: ACTIVE` with stake rules. P09 revalidation says ADVANCE (5/5). P09 is embedded in V1 pipeline.

**Master doc v38 position (from prior sessions):** S12/P09 overlays were described as archived in some versions, active in others. The repo evidence shows they are embedded in the V1 daily_signal_generator and have active configs.

**Review verdict:** Both should be VALIDATED_SHADOW (PAUSED with V1) — they run when V1 runs, which is currently PAUSED. Registry correctly captures S12 as mixed-result shadow; P09 UNCLASSIFIED is too weak given active config and positive validation.

### V1 Totals

**Registry:** VALIDATED_SHADOW (PAUSED)

**Issue:** See Critical Correction #2. The VALIDATED prefix may be misleading if historical validation is disputed. The 2026 live result (-17.5% at N=50) is substantially worse than OOS projections.

**Review verdict:** Status should include a validation-dispute qualifier or be downgraded to UNVALIDATED.

### NRFI Selector

**Registry:** VALIDATED_SHADOW (INFO) — not edge, parlay filter only.

**Review verdict:** ACCURATE. Registry correctly captures this as non-edge entertainment/parlay system. No drift.

### YRFI Shadow Tracker

**Registry:** VALIDATED_SHADOW — two-season finding.

**Review verdict:** ACCURATE. Registry correctly identifies this as shadow-only, not live-money deployment. Two-season finding qualifier is appropriate. No v36 drift reintroduced.

### CS028

**Registry:** UNVALIDATED_SHADOW

**Review verdict:** QUESTIONABLE — see Non-Critical Correction #3. A validation artifact exists (NEEDS_MORE_DATA verdict), so "unvalidated" is imprecise. Better: VALIDATED_SHADOW (INSUFFICIENT_SAMPLE).

---

## F. Recommended V2 Changes

1. Fix V1 ROI: -11.8%/N=57 → -17.5%/N=50 (from engine_status.json)
2. Reassess V1 status: add validation-dispute qualifier or downgrade to UNVALIDATED
3. Reclassify P09 from UNCLASSIFIED to VALIDATED_SHADOW (PAUSED with V1)
4. Fix executive summary count: S12 is shadow not dead
5. Upgrade CS028 from UNVALIDATED to VALIDATED_SHADOW (INSUFFICIENT_SAMPLE)
6. Add NRFI Helper (micro model) as separate system
7. Add SGP Phase 0 to accounting gaps
8. Add CLV capture to infrastructure
9. Note YRFI ROI bug correction more prominently
10. Add F5 Runline as explicit ARCHIVED entry

---

## G. Decision Implications

1. **No MLB system is currently trustable for live edge deployment.** V1 is PAUSED at -17.5%. All other systems are shadow-only.

2. **YRFI is the strongest shadow candidate** — validated by permutation, real FanDuel prices, corrected positive ROI. Promotion depends on accumulating N>=100 at 2+ tier.

3. **KP04 (K OVER) is a validated shadow in a different market** (pitcher strikeouts, not game totals). Its +9.57% ROI is real-price. It operates independently of V1.

4. **ADJ May 15 activation should remain blocked** — all 5 ADJ signals are DIMINISHED. The ADJ family is VALIDATED_NEGATIVE_DEAD.

5. **MLB registry v2 is required before any implementation work** to correct the V1 ROI figure and P09 classification. These are decision-relevant errors.

6. **Systems safe for continued monitoring without code changes:** YRFI, KP04, CS013, CS004, Combined Short Exit, Team Total, NRFI (info), S12 (monitoring only).

7. **Systems that should NOT produce signals without further review:** Night Dog, BP Adv Dog (unvalidated), CS028 (insufficient sample), P09 (unclear deployment path).
