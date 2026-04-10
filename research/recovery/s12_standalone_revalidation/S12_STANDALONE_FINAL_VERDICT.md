# S12 Standalone Final Verdict

## Signal
S12 = avg(home_csw, away_csw) - 5 * avg(home_xfip, away_xfip)
Rule: S12 >= 8.4468 -> blind UNDER

## PIT Safety
CLEAN. Both CSW (shift(1) rolling-5) and xFIP (PIT v1 rebuild) are
point-in-time safe. Contamination delta = 0.0pp.

## Verdict: DIMINISHED

## Key Numbers
- All-sample ROI: -0.8% (N=2596)
- In-sample ROI (2022-2024): -2.7% at cutoff 8.5
- OOS ROI (2025): +4.7% at cutoff 8.5 (N=706)
- Edge vs blind under: +1.8pp
- Positive seasons: 2/4
- In-sample negative at ALL thresholds tested

## Why Not COLLAPSES
- +1.8pp vs blind under is non-trivial direction
- OOS 2025 is positive (though may be noise)
- The high-total subset (close > 8.5) shows +6.3% ROI

## Why Not SURVIVES
- Overall ROI is negative
- In-sample performance is uniformly negative
- Unstable across seasons (2/4)
- Not additive on low totals where most under bets occur
- OOS result relies on single season

## Deployment Status
SHOULD NOT be deployed as standalone trigger.
May retain value as overlay on high-total games only (monitor, do not bet).
