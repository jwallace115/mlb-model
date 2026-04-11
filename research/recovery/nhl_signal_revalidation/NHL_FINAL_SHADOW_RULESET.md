# NHL Final Shadow Ruleset

## Effective Date: 2026-04-11
## Model Base: nhl_final_alignment (PK% corrected)

---

## 1. Model

Use the aligned Ridge models:
- Home: research/recovery/nhl_final_alignment/model_A_home.pkl
- Away: research/recovery/nhl_final_alignment/model_A_away.pkl
- Scaler: embedded in pkl packages
- Features: 29 per side (see phase1_locked_base_spec.md)

## 2. Drift

- **VALIDATE_DRIFT = 0.0**
- This replaces the old value of 0.4458
- Rationale: val-optimal drift is -0.10, TV WR-optimal is -0.20, OOS bias at 0.0 is -0.14 (near neutral). Using 0.0 is the conservative choice -- no artificial shift, let the model speak for itself.
- Split equally: +0.0 to each lambda (home and away)
- Dynamic drift computation in the live pipeline currently falls back to VALIDATE_DRIFT anyway
- Monitor live bias after 50+ graded games; recalibrate if bias exceeds +/- 0.2

## 3. Edge Threshold

- **THRESHOLD = 0.12** (unchanged)
- This is the minimum edge to LOG a signal
- All signals with edge >= 0.12 are recorded in nhl_decisions.parquet
- No signals are suppressed at the logging stage

## 4. Confidence Tiers

| Tier | Edge Requirement | Vol Requirement | Status |
|------|-----------------|-----------------|--------|
| HIGH | edge >= 0.15 | vol_bucket != "high" | ACTIVE |
| MEDIUM | edge >= 0.12 | -- | SHADOW |
| LOW | edge < 0.12 | -- | SHADOW |

## 5. Stop Rules

File: nhl/data/nhl_stop_rules.json
```json
{
  "high_tier": "active",
  "medium_tier": "shadow",
  "low_tier": "shadow",
  "evaluation_date": "2026-05-01"
}
```

## 6. Stake Units

| Tier | Units | Economic Exposure |
|------|-------|-------------------|
| HIGH | 1.0 | Real |
| MEDIUM | 0.0 | Tracking only |
| SHADOW_MEDIUM | 0.0 | Tracking only |
| LOW | 0.0 | Tracking only |
| SHADOW_LOW | 0.0 | Tracking only |

## 7. Signal Qualification Flow

```
1. Fetch schedule + goalies + live features
2. Score with aligned Ridge model (home + away lambdas)
3. Add drift: lambda_cal = lambda_raw + 0.0 (no drift)
4. Run Poisson simulation (10k draws)
5. Compute edge = sim_prob - fair_prob (vig-removed)
6. If edge >= 0.12: log signal
7. Assign tier: HIGH if edge >= 0.15 and not high-vol, else MEDIUM/LOW
8. Apply stop rules: only HIGH tier generates nonzero stake
9. Grade next day via NHLe API final scores
```

## 8. What Changes vs Current Pipeline

1. **Drift value**: 0.4458 -> 0.0 in VALIDATE_DRIFT constant
2. **Model files**: Point to aligned pkl files (or copy to nhl/ directory)
3. **No other logic changes**: tiers, thresholds, sim, stop rules all remain as-is

## 9. Monitoring During Shadow

Track daily:
- Signal count per tier
- Win rate by tier (rolling 30-game window)
- ROI by tier (rolling 30-game window)
- Drift stability: compare pred_total vs actual_total bias
- If bias > +0.2 after 50+ games: increase drift toward +0.1
- If bias < -0.2 after 50+ games: drift is fine at 0.0, model naturally under-predicts

## 10. Cutover Criteria

To move any tier from SHADOW to ACTIVE:
- Minimum 50 graded signals in that tier
- Win rate >= 52% (breakeven at -110)
- Positive ROI over the measurement window
- No regime collapse (monthly WR never below 45%)
