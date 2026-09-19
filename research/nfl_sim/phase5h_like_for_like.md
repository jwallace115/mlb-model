# Phase 5H Item 2 — Like-for-like decomposition

Generated from 1,087 regular-season games 2021-24, N=500, on branch `diag/5h`
(commit `9b46510db`). Byte-identity verified (flag ON vs OFF, 3 games x N=2000).
1.08 s/game, 19.5 min total. engine_fingerprint: `d929ad258504b275`.

## Pre-registered predictions

**A (go-rate decomposition):** I predict state mix accounts for MORE THAN HALF the gap.
**C (tied-drive expiry):** I predict (i) zero-play + (ii) reached-on-final-play > 50%.
Both match Cowork's predictions.

## A: Go rate decomposition

| | Rate | |
|---|---:|---|
| Real go rate | 0.19802 | 3,085 / 15,579 decisions |
| Sim go rate | 0.21854 | 8,133,076 / ~37.3M decisions |
| **Gap** | **+0.02051** | |
| Real rates @ sim mix | 0.21234 | state-mix effect: +0.01431 |
| Sim rates @ real mix | 0.20077 | within-cell effect: +0.00274 |

**State mix: 69.8% of the gap.** Within-cell: 13.4%. Interaction: 16.8%.

Prediction held: state mix > 50% (measured 69.8%). Cowork's prediction also held.

**By ydstogo:**
| Bucket | Real % | Sim % | Diff |
|--------|--------|-------|------|
| 1-2 | 19.5% | 22.4% | +2.9pp |
| 3-5 | 22.9% | 26.5% | +3.5pp |
| 6-10 | 32.3% | 30.7% | -1.6pp |
| 11+ | 25.2% | 20.4% | -4.8pp |

The sim produces too many short-yardage 4th downs (+6.4pp in 1-5 bucket)
and too few long-yardage (-6.4pp in 6+).

## B: Upstream — 3rd-down distribution

**3rd-down ydstogo:**
| Bucket | Real % | Sim % | Diff |
|--------|--------|-------|------|
| 1-2 | 20.7% | 18.6% | -2.2pp |
| 3-5 | 25.0% | 26.3% | +1.3pp |
| 6-10 | 36.1% | 37.5% | +1.4pp |
| 11+ | 18.2% | 12.7% | -5.5pp |

The sim has FEWER 3rd-and-1-2 situations (-2.2pp) but MORE 3rd-and-3-10 (+2.7pp).
Since shorter 3rd downs convert more → 4th-and-short, the shift toward medium
distances with lower conversion rates produces more 4th-and-short residuals.

**Failed 3rd-down residual (yards_gained - ydstogo):**
- Real: mean -7.52, P(remaining <= 2) = 0.205
- Sim:  mean -7.00, P(remaining <= 2) = 0.205

Essentially identical P(4th-and-short | 3rd-down failure) — the upstream cause is
the 3rd-down ydstogo distribution, not the yardage tables.

## C: Tied-drive expiry split

N=315 reached drives (test definition), 35 expired (11.1%).

| Category | Count | % of expired |
|----------|-------|-------------|
| (i) zero-play drives | 11 | 31.4% |
| (ii) reached 35 only on final play | 22 | 62.9% |
| (iii) took snap at/inside 35 | 2 | 5.7% |
| **(i)+(ii)** | **33** | **94.3%** |

Prediction held: (i)+(ii) > 50% (measured 94.3%). Cowork's prediction also held.

**Strict rate** (iii only, drives with a snap inside the 35): **6/57 = 0.105** vs real 0/57.
**Broad rate** (test definition): **35/315 = 0.111** vs real D94 2/64 = 0.031.

Category (ii) dominates: drives that started outside the 35 and ran out of clock
getting there, then the final play happened to end inside the 35.

## D: Two-minute drill

**Seconds per play:**
| Play type | Real | Sim | Diff |
|-----------|------|-----|------|
| Pass | 13.9s | 16.3s | +2.4s |
| Rush | 24.3s | 24.4s | +0.1s |
| Spike | — | 1.0s | — |

The sim's pass plays are 2.4s slower than reality. Over a 6-play drive, this is
+14.4s — enough to turn a drive that reaches FG range into one that expires.
Rush play timing matches well.

**Pass share:** real 63.5%, sim 66.2% (+2.7pp).

**Real drive result mix (Q4, <=300s, tied/trail<=8, N=1079):**
Touchdown 21.8%, FG 17.1%, Turnover 16.7%, Downs 15.2%, Punt 12.9%,
End of half 10.2%, Missed FG 4.3%, Opp TD 1.1%.
