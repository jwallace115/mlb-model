# Phase 11 - Temporal Split Lock
## MLB Totals Context Engine V1

### Split Definitions (LOCKED)

The following split definitions are permanently locked for this engine version. They cannot be changed to improve validation metrics without invalidating the engine entirely.

---

### DISCOVERY Split

- **Definition:** season IN (2022, 2023)
- **Date range:** 2022-04-07 to 2023-10-01
- **Games:** 4,860
- **Purpose:** All formula development, weight assignment, normalization bounds, bucket thresholds
- **Rules:** No formula element may be derived from, tuned on, or informed by validation or OOS data

### VALIDATION Split

- **Definition:** season == 2024
- **Date range:** 2024-03-20 to 2024-09-29
- **Games:** 2,427
- **Purpose:** Verify component directional consistency. Identify outputs that collapse.
- **Rules:** Formulas already frozen. Validation is observe-only. No tuning.

### OOS Split (Out-of-Sample)

- **Definition:** season == 2025
- **Date range:** 2025-03-27 to 2025-09-28
- **Games:** 2,428
- **Purpose:** True out-of-sample performance check. Ground truth for context utility.
- **Rules:** Treated as live data. No review until after formulas locked. Case studies in Phase 9.

---

### 2026 Exclusion

Season 2026 is excluded from all modeling, formula development, validation, and output table. Data collection for 2026 is ongoing. 2026 will be a future OOS hold-out if the engine is refreshed.

---

### Why Not Use Rolling Splits?

Rolling window splits (e.g., train on prior 2 seasons, test on next) are appropriate for adaptive models. This engine uses frozen formulas derived from structural baseball rules, not optimized model weights. The discovery period was chosen as 2022-2023 because:

1. 2022 includes the season with sticky-ball enforcement changes (mid-season) - tests robustness
2. 2023 is the shift-ban introduction - different offensive environment - tests generalizability
3. 2024-2025 provide clean validation period with different offensive and defensive regimes

The engine is designed to capture durable structural relationships, not regime-specific patterns. If the formulas cannot survive the 2022 -> 2023 regime change in discovery, they should not be used.

---

### Monotonicity Locks

Certain directional relationships are asserted as structural (locked) for each output:

| Output | Expected Direction | Locked? |
|--------|--------------------|---------|
| BRE HIGH -> higher actual_total | Positive | YES |
| ESP HIGH -> higher actual_f5_total | Positive | YES |
| LSP HIGH -> higher late_runs | Positive | YES |
| SS STABLE -> lower actual_total | Negative | YES |
| BS UNSTABLE -> higher late_runs | Positive | YES |
| WPL LIFTED -> higher actual_total | Positive | YES |
| TCV VOLATILE -> higher total_std | Positive | YES |
| MPS | DATA-BLOCKED | N/A |

If any output fails the monotonicity check in validation or OOS, it is flagged for review. The formula is not adjusted - the output is reclassified to USEFUL BUT SECONDARY or REDUNDANT in the Final Scorecard.

---

Built: 2026-04-12
