# prop_rush_att_QB was calibrated to 0.99 for every leg, in production

Cowork, 2026-09-18, found while verifying D74's faithfulness check.

## What it was

D74 reported "20/21 families reproduce" and attributed the one mismatch to
"a precedence bug in the original inline script". The bug is real —
`int(val.iloc[0] if len(x) else 0 >= k)` binds `>= k` to the `else` branch only,
so `hit` was the raw carry count rather than 0/1, and isotonic regression against
y values of 0,1,2,… clipped the whole map to the `y_max=0.99` ceiling.

But it was not a faithfulness footnote. It was a live defect in the shipped map.
From the calibration_v1.json in force until `429889abb`:

    prop_rush_att_QB  n=1481   y min 0.9900   y max 0.9900   1 distinct value
                              100% of the domain pinned at the clip ceiling

Every QB rushing-attempts leg, at any raw sim probability from 0.01 to 1.0, was
calibrated to **0.99**. Confirmed in the K4 rows: all 722 QB `rush_att` legs carry
`cal_p` exactly 0.990 (min = max). After the fix: 0.189 to 0.812, 21 distinct
values, 8% at the ceiling.

## Why it matters beyond the map

1. The board's confidence tiering reads `cal_p`. Any QB rush-attempt leg looked
   maximally confident regardless of what the sim said.
2. Every **model-filtered** K4 conclusion for that family is degenerate. The
   "rush_att under +0.4% (N=774)" model-filtered cell reported in
   `phase5d1_usage_provenance.md` was filtered on a constant.
3. This is the second independent defect on the same family. D62 fixed graded
   actuals (kneels excluded, which produced the fake +18.2% QB under edge); this
   one sat in the calibration map alongside it, unnoticed through 5C and all of
   5D. When one family shows an anomaly, check every layer that touches it, not
   just the one that explains the anomaly.

No other family is degenerate: all 21 maps in the fit_5d2 calibration have more
than two distinct y values.

## Unresolved

How long it was live. The map is regenerated per fit, so every calibration
written by the ad-hoc inline script — which is every one before D74 — carries it.
Any conclusion drawn from a model-filtered cell on `prop_rush_att_QB` before
`429889abb` should be treated as void rather than re-derived.
