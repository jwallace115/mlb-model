# NCAAF Joint-Outcome Correlation — OOS Test on 2025

## Pre-registered predictions (written before computing anything on 2025)

**Prediction 1**: In |spread| >= 21, phi(home cover, over) is POSITIVE and of
the same order as 2022-2024 (roughly 0.10 to 0.25).

**Prediction 2**: In |spread| 14-21, phi is positive but smaller.

**Prediction 3**: In |spread| 0-3, 3-7 and 7-14, phi is flat — |t| < 2 in
all three buckets.

Buckets: 0-3, 3-7, 7-14, 14-21, 21+. SAME as the probe. Not re-cut.

**NULL CONTROL**: P(home cover) and P(over) on 2025 must each come back near
0.50 (the 2022-2024 values were 0.4992 and 0.5111). If either is materially
off 0.50, the data/join/sign convention is wrong — HALT.

## Results

### Null control

| Marginal | 2022-24 | 2025 |
|----------|---------|------|
| P(home cover) | 0.4992 | 0.5243 |
| P(over) | 0.5111 | 0.4956 |

Both within 3pp of 0.50. NULL CONTROL PASS.

### Bucketed results — BOTH conventions (2025, Bovada, N=904)

N09: The original report used left-closed bins while the probe used right-closed
(pd.cut). The bin LABELS matched; the EDGES did not. In football 3/7/14/21 are
modal spreads, so the convention reallocates a large mass of games across exactly
the tested boundaries. Both are now shown.

| Bucket | LEFT-CLOSED [lo,hi) | | | RIGHT-CLOSED (lo,hi] (probe) | | |
|--------|-----|-------|------|-----|-------|------|
| | N | phi | t | N | phi | t |
| 0-3 | 115 | -0.155 | -1.66 | 179 | -0.075 | -1.00 |
| 3-7 | 245 | 0.059 | 0.92 | 225 | 0.104 | 1.56 |
| 7-14 | 215 | 0.155 | 2.27 | 198 | 0.089 | 1.25 |
| 14-21 | 131 | 0.148 | 1.69 | 118 | 0.211 | 2.29 |
| 21+ | 198 | 0.280 | 3.94 | 184 | 0.278 | 3.77 |

Pooled: N=904, phi=0.116, t=3.48.

### Verdict

**Prediction 1: HELD.** 21+ bucket: phi=0.278-0.280, t=3.77-3.94 under both
conventions. Robust. (2022-24: phi=0.196, t=3.79.)

**Prediction 2: HELD.** 14-21 bucket: phi=0.148-0.211, t=1.69-2.29 depending
on convention. Positive under both, but significance depends on the convention.
Not robust.

**Prediction 3: HELD.** Under the probe's own bins (right-closed), 7-14 gives
t=1.25, 3-7 t=1.56, 0-3 t=-1.00. All three |t| < 2.

> **WITHDRAWN (N09).** The original report stated "Prediction 3: DID NOT HOLD"
> based on left-closed bins giving 7-14 t=2.27. This was 1 of 8 configurations
> that cleared |t|>2 for that bucket (the only one the script happened to use).
> Under the probe's own right-closed bins it is t=1.25. The original
> interpretation — "the correlation appears to reach into games that are not
> blowouts but are still large favourites" — described a bin boundary, not
> college football. **Deleted, not reworded.**

### Robustness matrix (from audit, §3)

#### |spread| >= 21 — robust under all eight

| window | line key | bins | N | phi | t |
|--------|----------|------|-----|-------|------|
| 2022-24 | spread | left | 398 | 0.196 | 3.98 |
| 2022-24 | spread | right | 363 | 0.196 | 3.79 |
| 2022-24 | spreadOpen | left | 375 | 0.195 | 3.85 |
| 2022-24 | spreadOpen | right | 343 | 0.213 | 4.03 |
| 2025 | spread | left | 198 | 0.280 | 4.09 |
| 2025 | spread | right | 184 | 0.278 | 3.90 |
| 2025 | spreadOpen | left | 190 | 0.264 | 3.75 |
| 2025 | spreadOpen | right | 176 | 0.304 | 4.20 |

phi 0.195-0.304, t 3.75-4.20. **Significant in every configuration.**

#### |spread| 14-21 — not robust

t swings 0.78-2.32 on convention alone. Crosses significance in 2 of 8.

**Branch decision: take Branch A** — the 21+ correlation survived out of sample.
14-21 did not survive robustness testing and should not enter the joint table.
