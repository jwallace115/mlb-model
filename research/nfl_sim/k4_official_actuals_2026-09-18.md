# K4 Before/After Official Actuals (D62)

## Pre-registered prediction (written before looking at the numbers)

QB rush_att blind under is currently +18.2% ROI, 63.3% hit vs 50.1% market
no-vig (+13.2pp edge, N=722). If kneels are the cause it should collapse to
roughly break-even-minus-hold: edge near 0pp, ROI near -6.5%.
pass_att under edge (+2.67pp) should shrink toward 0.
NULL CONTROL: rec_yds and pass_yds are continuous markets unaffected by
kneels or spikes. Their cells must be essentially unchanged.

## Result: prediction HELD

QB rush_att under collapsed from +18.2% ROI / +13.2pp edge to -4.5% ROI /
+1.4pp edge. The kneel diagnosis was correct.

## Flat K4 by family (vigged prices)

| Family | N | Old Over | Old Under | New Over | New Under |
|--------|------|----------|-----------|----------|-----------|
| rush_att | 2,364 | -17.6% | **+4.5%** | -11.4% | -2.1% |
| pass_att | 1,429 | -11.3% | -1.3% | -10.5% | -2.1% |
| rush_yds | 13,690 | -9.2% | -2.8% | -10.0% | -2.0% |
| receptions | 11,142 | -9.8% | -2.6% | -9.8% | -2.6% |
| rec_yds | 32,509 | -7.5% | -5.2% | -7.5% | -5.2% |
| pass_yds | 8,215 | -5.4% | -5.0% | -5.4% | -5.0% |
| pass_cmp | 1,708 | -5.1% | -6.4% | -5.1% | -6.4% |
| pass_td | 1,840 | -8.2% | -5.8% | -8.2% | -5.8% |

## rush_att under by position (before / after)

| Position | N | Old ROI | Old Hit | Old Edge | New ROI | New Hit | New Edge |
|----------|-----|---------|---------|----------|---------|---------|----------|
| **QB** | 722 | **+18.2%** | 0.633 | **+13.2pp** | -4.5% | 0.515 | +1.4pp |
| RB | 1,637 | -1.8% | 0.523 | +2.5pp | -1.2% | 0.526 | +2.8pp |

The kneel effect: adding 437 kneels/season as carries pushes QB actual_carries
up by ~1.5/game. On lines 3.5-5.5, this flips many unders from hit to miss.
RB lines are largely above the kneel range and barely affected.

## rush_att under by line bucket (before / after)

| Bucket | N | Old Edge | New Edge | Delta |
|--------|-----|----------|----------|-------|
| <=5.5 | 671 | +12.0pp | +0.8pp | **-11.2pp** |
| 6-10.5 | 536 | +6.6pp | +4.8pp | -1.8pp |
| 11-15.5 | 818 | +2.7pp | +3.0pp | +0.3pp |
| 16-20.5 | 331 | -0.1pp | +0.8pp | +0.9pp |
| >20.5 | 8 | -1.1pp | -1.1pp | 0.0pp |

The kneel effect concentrates in <=5.5 (-11.2pp), decays in 6-10.5 (-1.8pp),
and is negligible above 11.

The two-point-run effect (removing 38 plays): increases some rush_att actuals
by 0-1, moving a few overs from miss to hit. This is small and spread across
all line buckets. Net effect is masked by the larger kneel correction.

## rush_att QB under by season

| Season | N | Old ROI | Old Edge | New ROI | New Edge |
|--------|-----|---------|----------|---------|----------|
| 2023 | 304 | +19.9% | +14.1pp | -0.8% | +3.3pp |
| 2024 | 418 | +16.9% | +12.6pp | -7.1% | +0.1pp |

Both seasons collapse. 2024 goes to essentially zero edge.

## pass_att under

| | N | Edge |
|--|------|------|
| Before | 1,429 | +2.7pp |
| After | 1,429 | +2.3pp |

Shrinks 0.4pp. The spike effect (adding 75 pass attempts) is small because
spikes are uncommon and spread across many games.

## Null control

| Family | Old Over | New Over | Old Under | New Under |
|--------|----------|----------|-----------|-----------|
| rec_yds | -7.5% | -7.5% | -5.2% | -5.2% |
| pass_yds | -5.4% | -5.4% | -5.0% | -5.0% |

**PASS**: both unchanged to 0.00pp. No leakage.

## Summary

The kneel diagnosis was correct. The +18.2% QB rush_att under was entirely a
grading artifact. After official definitions (D62), no family has a positive
blind side above noise.
