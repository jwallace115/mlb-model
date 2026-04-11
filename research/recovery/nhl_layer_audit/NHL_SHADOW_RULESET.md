# NHL Shadow Deployment Ruleset (Phase 7)

## Date: 2026-04-10

---

## Current State: ALL TIERS SHOULD BE IN SHADOW

The live pipeline has a fundamental calibration failure. Until the feature
mismatch (Layer 15) and drift (Layer 1) are fixed, NO tier should carry
real stake.

### Immediate Action
Set `nhl_stop_rules.json` to:
```json
{
  "high_tier": "shadow",
  "high_shadow_date": "2026-04-10",
  "high_shadow_reason": "Layer audit: drift miscalibration, 41.7% hit rate (5-7)",
  "medium_tier": "shadow",
  "medium_shadow_date": "2026-04-09",
  "medium_shadow_reason": "33.3% win rate 2026 (7-14)",
  "low_tier": "shadow",
  "low_shadow_date": "2026-04-09",
  "low_shadow_reason": "26.7% win rate 2026 (4-11)",
  "evaluation_date": "2026-05-15"
}
```

---

## Shadow-to-Active Promotion Gate

A tier may be promoted from shadow to active ONLY when ALL of the following
conditions are met:

### Gate 1: Feature Fix Verified
- [ ] Live feature values compared against historical feature values for
      the same team/date — mean absolute difference < 0.5 std of training distribution
- [ ] Live lambda_raw (before drift) is within 0.3 goals of market line on average

### Gate 2: Drift Recalibrated
- [ ] New drift constant derived from >= 50 live games with corrected features
- [ ] Post-drift bias on held-out live games < 0.15 goals

### Gate 3: Threshold Validated
- [ ] Edge distribution is mixed OVER/UNDER (neither side > 70% of signals)
- [ ] New empirical threshold identifies at least one band with hit >= 52.5%, n >= 30
- [ ] Tier boundaries produce meaningful subsetting of edges

### Gate 4: Shadow Performance
- [ ] Minimum 14 shadow days after feature fix
- [ ] Minimum 30 graded shadow signals after feature fix
- [ ] Shadow hit rate >= 52.0% for the tier being promoted
- [ ] No data quality warnings in the shadow period

### Gate 5: Stability
- [ ] No model or feature changes in the 7 days preceding promotion
- [ ] Rolling 14-day CLV is non-negative (if CLV data available)

---

## Portable Layers: No Shadow Restriction

The following layers operate correctly regardless of model state and do not
need shadow gates:

1. **Grading** — Grade all signals (including shadow) to build performance history
2. **CLV Snapshots** — Continue capturing morning/pregame lines
3. **Line Movement** — Continue tracking open vs current lines
4. **OT Diagnostics** — Continue logging OT/SO impact
5. **Data Quality Audit** — Continue pre-serialization checks
6. **Season Performance** — Continue aggregating results
7. **Summaries** — Continue generating (with updated benchmarks)

---

## Recalibration Sequence (when feature fix is ready)

### Step 1: Feature Validation (1-2 days)
Run corrected live features alongside historical features for overlapping dates.
Compare distributions. Verify mean/std alignment.

### Step 2: Dynamic Drift Implementation (1 day)
Complete the stub in `predict_and_calibrate()` (lines 640-643):
- After MIN_SEASON_GAMES (10+) live games with corrected features:
  - Compute mean(actual_total - lambda_raw) over those games
  - Use as seasonal_drift
  - Update daily as new games are graded

### Step 3: Threshold Sweep (1 day)
With corrected drift applied:
- Compute edge distribution over shadow period
- Sweep edge bands [0.04, 0.06, 0.08, 0.10, 0.12, 0.14]
- Set THRESHOLD to lowest band with hit >= 52.5% AND n >= 30
- Set HIGH threshold to edge value where hit rate is maximized and n >= 15

### Step 4: Shadow Deploy (14+ days)
- Set all tiers to shadow
- Log all signals with corrected features/drift/thresholds
- Grade daily
- Monitor hit rate, bias, edge distribution, CLV

### Step 5: Promotion Decision
- Run Gate 1-5 checks
- If all pass: promote highest-performing tier first
- Promote one tier at a time with 7-day gap between promotions

---

## Monitoring During Shadow

Daily checks (automated via `shadow_run.py --checklist` pattern):
1. Signal count: expect 2-6 per day on average
2. Side balance: OVER/UNDER split should be 30-70% / 70-30% (not 8/92)
3. Lambda vs line: mean should be within +-0.3 of zero
4. Edge range: mean should be 0.05-0.15 (not 0.15+ from bias)
5. Bias: rolling 7-day (lambda_cal - actual) should be within +-0.3

---

## Emergency Stop

If at any point during shadow or after promotion:
- 7-day rolling hit rate drops below 35% on 10+ signals: shadow ALL tiers
- Model bias exceeds +-0.5 goals on 20+ games: shadow ALL tiers
- Feature computation error (NaN, out-of-range): halt pipeline, investigate
