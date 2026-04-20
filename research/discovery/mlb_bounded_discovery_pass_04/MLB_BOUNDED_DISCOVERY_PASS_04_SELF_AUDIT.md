# MLB BOUNDED DISCOVERY PASS 04 — SELF AUDIT

**Pass Date:** 2026-04-20
**Auditor:** Claude (same operator as pass execution)

---

## Audit Questions

### 1. Were any thresholds adjusted after seeing validation data?

**NO.**

All four thresholds were calibrated on discovery data (2022–2023) and locked before validation was examined:
- S1: `opp_sp_workload_ip_last_3 <= 4.67` — set from discovery percentile analysis
- S2: `opp_sp_command_bb_rate_last_3 >= 0.10` — set from discovery distribution
- S5: `opp_sp_contact_barrel_allowed_last_3 >= 0.07` — set from discovery distribution
- S6: `opp_sp_workload_ppbf_last_3 >= 4.10` — set from discovery distribution

Validation and OOS splits were not examined until thresholds were fully frozen. No threshold was modified after seeing any holdout data.

### 2. Were all tested fields confirmed PIT-safe?

**YES.**

All four tested fields are `opp_sp_*` features from the starter_profile substrate. They are rolling averages computed over prior starts (last 3), not same-game data. CAVEAT_02 applies (SC available-only averaging) but does not affect PIT-safety — it affects precision, not temporal contamination.

No exceptions.

### 3. Were any fields substituted for unavailable candidates?

**NO.**

Two priority candidates (S3: ERA/FIP, S4: pitcher rest days) were identified as DATA_GAP. Neither field exists in the runtime object. No substitute field was used. Both candidates were explicitly skipped with DATA_GAP notation.

### 4. Were any fields used that were not in the field dictionary?

**NO.**

All four tested fields appear in `MLB_RUNTIME_OBJECT_V1_FIELD_DICTIONARY.csv`:
- `opp_sp_workload_ip_last_3` — OPP_SP_FEATURE, CAVEAT_02
- `opp_sp_command_bb_rate_last_3` — OPP_SP_FEATURE, CAVEAT_02
- `opp_sp_contact_barrel_allowed_last_3` — OPP_SP_FEATURE, CAVEAT_02
- `opp_sp_workload_ppbf_last_3` — OPP_SP_FEATURE, CAVEAT_02

The outcome variable `actual_total` is also in the field dictionary (OUTCOME field from game_table_spine).

### 5. Is the run differential metric computed against closing total line or pre-game line?

**NEITHER.** The metric used in this pass is the raw `actual_total` mean — the average of actual game total runs for flagged vs unflagged games. The "gap" is the difference in mean actual_total between flagged and unflagged groups.

This is NOT a residual against any line. It is a raw mean comparison. This is why all results are labeled **DISCOVERY_TRIAGE_ONLY** — they reflect raw scoring patterns, not market-adjusted residuals. Any surviving candidate would require an economic reality check using the market bridge (mlb_w01_market_bridge_v1) before advancing.

No candidates survived to warrant that check.

---

## Audit Verdict

**CLEAN.** No threshold contamination, no field substitution, no PIT-safety violations, no outside-package files used. Pass completed honestly with all candidates dead.

---

*Self-audit completed: 2026-04-20*
