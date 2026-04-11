# NHL Layer Compatibility with Rebuilt Base (Phase 4)

## Date: 2026-04-10

---

## Critical Question 1: Is the +0.4458 drift valid on the rebuilt model?

**NO.**

Evidence:
- Rebuild Model A validate-season (2023-24) raw bias: -0.019 goals
- Rebuild Model A OOS (2024-25) raw bias: -0.163 goals
- The correct Model A drift would be +0.02 (validate) to +0.16 (OOS)
- Applying +0.4458 over-corrects by +0.28 to +0.43 goals

But the live pipeline shows even worse:
- Live raw lambda (before drift): ~5.23
- Live actual totals: ~6.57
- Live raw gap: ~1.34 goals

This means the live feature computation (Layer 15) is producing features
that make the model predict ~1.18 goals lower than it would on historical
features. The drift correction only masks ~0.45 of this 1.34-goal gap.

**Conclusion:** The drift constant is wrong, AND there is a deeper
feature-level discrepancy that drift alone cannot fix.

---

## Critical Question 2: Do old tier thresholds make sense with rebuilt edge distribution?

**NO, not currently.**

Current live edge distribution:
- Mean: 0.146
- Median: 0.135
- Range: 0.101 to 0.290

Historical edge distribution:
- Mean: 0.134
- Range varies by split

The live edges are inflated because the model is systematically far from the
market line (lambda_vs_line mean = -0.72). This creates artificially large
UNDER edges. After drift correction, the edge distribution will compress
significantly and the current thresholds may be too high or too low.

**Conclusion:** Tier thresholds must be recalibrated after drift is fixed.

---

## Critical Question 3: Does the rebuilt model already capture goalie quality?

**YES.**

Rebuild Model A was trained with these goalie features:
- `{side}_goalie_sv_pct_rolling_10` — recent save percentage
- `{side}_goalie_vs_team_baseline` — goalie vs team average
- `{side}_goalie_fatigue` — games in last 3 days
- `{side}_goalie_b2b` — back-to-back flag
- `{side}_backup_flag` — backup goalie indicator

These are all native features, not overlay layers. The goalie handling in
the live pipeline correctly computes these features from NHL API data and
feeds them to the model. No duplication or conflict.

---

## Critical Question 4: What is the rebuild model's true capability?

From the rebuild audit (NHL_REBUILD_FINAL_VERDICT.md):
- Model A OOS MAE: 1.8714 (vs Market MAE: 1.8956) = -1.3% better
- Model A OOS bias: -0.1444
- corr(edge, market_error): 0.1552 (genuine edge signal)
- R-squared delta vs market: +0.0232

**The rebuild model has genuine predictive power on historical data.**
The live failure is NOT a model quality issue. It is a feature computation
and drift calibration issue.

---

## Compatibility Matrix

| Layer | Compatible with Rebuild? | Action |
|-------|--------------------------|--------|
| 1. Drift correction (+0.4458) | NO | Must recalibrate to Model A |
| 2. Poisson sim | YES (with minor push correction re-check) | Carry forward |
| 3. Goalie handling | YES (native) | Already integrated |
| 4. Tier system (0.12/0.15) | CONDITIONAL | Recalibrate after drift fix |
| 5. Stop rules | YES (mechanism) | Reset after drift fix |
| 6. Edge calculation | YES | Carry forward |
| 7. Signal threshold (0.12) | CONDITIONAL | Recalibrate after drift fix |
| 8. Grading | YES | Carry forward |
| 9. OT diagnostics | YES | Carry forward |
| 10. Summaries | YES (update benchmarks) | Carry forward |
| 11. CLV snapshots | YES | Carry forward |
| 12. Line movement | YES | Carry forward |
| 13. Data quality audit | YES | Carry forward |
| 14. Season performance | YES | Carry forward |
| 15. Live features | NO — ROOT CAUSE | Must investigate and fix |
