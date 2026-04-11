# NHL Audit -- Phase 7: Final Damage Map and Recommendations

## Date: 2026-04-10

## Executive Summary

The NHL totals model has one CRITICAL failure and several compounding issues
that render the live system non-functional for betting purposes.

Live record: 27-38 (41.5%), ROI = -20.5%
Historical OOS: 82-72 (53.25%), ROI = +1.65%
Degradation: -11.8 percentage points

## Root Cause Chain

```
MoneyPuck data unavailable for 2025-26
    |
    v
79.4% of model features frozen at 2024-25 league averages
    |
    v
Live model is NOT the model that was validated
    |
    v
Model degenerates to: constant + f(rest, b2b, backup, recent_goals)
    |
    v
Systematic under-projection (mean bias approx -0.79 goals uncorrected)
    |
    v
Static drift correction (+0.4458) calibrated on wrong season
    |
    v
93% UNDER signals, 41.5% hit rate, -20% ROI
```

## Damage Assessment

### What Is Salvageable
1. The canonical data pipeline (phase1) is clean and well-engineered
2. The feature construction logic is PIT-safe (rolling from strictly prior games)
3. The Ridge model architecture is reasonable (not overfit, appropriate regularization)
4. The Poisson simulation framework is correctly implemented
5. The grading and signal infrastructure works correctly

### What Is Broken
1. The live pipeline runs a fundamentally different model than was validated
2. The drift calibration is static and season-specific
3. The variance calibration has known failures at key lines (6.0, 6.5)
4. No tier produces profitable signals in live operation

### What Was Never Built
1. Live computation of PP%, PK%, penalties from NHL API boxscores
2. Live computation of shots_for, shots_against from NHL API boxscores
3. Live computation of goalie SV% from NHL API boxscores
4. Live computation of games_last_7 from schedule data
5. Dynamic drift recalibration within the current season
6. Actual-price ROI tracking

## Immediate Actions

### ACTION 1: SUSPEND LIVE BETTING (immediate)
The model is losing at -20% ROI. No tier, no side, no edge bucket is
profitable. Suspend all live NHL signals until the identity mismatch is
resolved.

### ACTION 2: Recover Live Features from NHL API (1-2 days)
The daily pipeline already fetches NHL API boxscores for goalie identification.
Extend the live data cache to also extract:
- Shots on goal (home, away) -- enables shots_for/against rolling
- PP opportunities, PP goals, PK goals against -- enables PP%, PK%, penalties
- Goalie saves, shots against -- enables goalie SV%
- Game dates for schedule -- enables games_last_7

This would recover approximately 8 of the 14 frozen features, moving from
20.6% to roughly 50-60% of prediction variance being live.

### ACTION 3: MoneyPuck-Free Model Variant (3-5 days)
The remaining frozen features (xGF, xGA, HD shots, Corsi) require MoneyPuck.
Two options:
a) Wait for MoneyPuck 2025-26 data availability
b) Train a new Ridge model that only uses features available from the NHL API,
   dropping xGF/xGA/HD shots entirely. This would be a different model
   requiring full train/validate/OOS cycle.

### ACTION 4: Dynamic Drift Calibration (1 day)
Replace the static VALIDATE_DRIFT = 0.4458 with an expanding-mean drift
computed from the model's own predictions vs actuals in the current season.
This is already implemented in phase45_calibration.py but not wired into
the live pipeline.

### ACTION 5: Actual-Price ROI Tracking (0.5 days)
The live pipeline already captures over_price and under_price. Wire these
into the grading system so ROI reflects actual execution prices rather than
flat -110.

## Comparison to MLB Audit Failure Classes

| Failure Class | MLB | NHL |
|---------------|-----|-----|
| Historical feature lookahead | Found in multiple places | Minor (F1, league avg prior) |
| Research/live identity mismatch | Found | CRITICAL (F3, 79.4% frozen) |
| Synthetic economics | Flat -110 used | Same issue (F4) |
| Hidden regime pathology | Monthly breakdown revealed drift | Compounded by F8 static drift |

The NHL system has a cleaner research pipeline than MLB (PIT-safe rolling
features, proper season splits) but a far worse live deployment failure.
The research work is mostly sound; the deployment is catastrophically
incomplete.

## Priority Order
1. Suspend live betting (immediate)
2. Extend live cache to extract NHL API boxscore fields (ACTION 2)
3. Implement dynamic drift in live pipeline (ACTION 4)
4. Retrain MoneyPuck-free model variant (ACTION 3)
5. Add actual-price ROI tracking (ACTION 5)
6. Fix league avg shrinkage to use prior-season averages (ACTION 6, low priority)
