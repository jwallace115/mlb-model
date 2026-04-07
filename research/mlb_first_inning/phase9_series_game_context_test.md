# Phase 9 — Series Game Number Context Test

**Date:** 2026-04-06
**Scope:** 2024-2025, 4,361 games with first-inning actuals
**Design:** Descriptive splits + chi-square, no modeling

---

## Series Numbering Logic

**Source:** `mlb/data/team_game_index.parquet` (home-side view)

**Method:** For each home team, sort games by date. Consecutive games vs the
same opponent with ≤2-day gap belong to one series. Label sequentially as
G1, G2, G3, G4+.

**Coverage:** 4,361/4,361 = 100%

| Label | N (total) | N (2024) | N (2025) |
|-------|-----------|----------|----------|
| G1    | 1,446     | 722      | 724      |
| G2    | 1,443     | 718      | 725      |
| G3    | 1,283     | 625      | 658      |
| G4+   | 189       | 105      | 84       |

G4+ games are evenly distributed across teams (max 8 per team). These are
4-game series, London/Japan series, and doubleheader makeups.

---

## Raw First-Inning Splits

| Label | N     | Top1%  | Bot1%  | YRFI%  | NRFI%  |
|-------|-------|--------|--------|--------|--------|
| G1    | 1,446 | 0.267  | 0.297  | 0.487  | 0.513  |
| G2    | 1,443 | 0.267  | 0.317  | 0.493  | 0.507  |
| G3    | 1,283 | 0.283  | 0.292  | 0.483  | 0.517  |
| G4+   | 189   | 0.212  | 0.280  | 0.418  | 0.582  |
| ALL   | 4,361 | 0.269  | 0.301  | 0.485  | 0.515  |

Max spread: G2 (49.3%) vs G4+ (41.8%) = 7.5pp

**Chi-square (YRFI across G1/G2/G3/G4+): chi2=3.777, p=0.2865 — NOT significant**

Per-side tests:
- Top-of-1st: chi2=4.492, p=0.2130
- Bot-of-1st: chi2=2.708, p=0.4389

Pairwise (Mann-Whitney):
- G1 vs G2: p=0.75
- G1 vs G3: p=0.85
- G2 vs G3: p=0.62

### By Year

| Label | 2024 YRFI | 2025 YRFI |
|-------|-----------|-----------|
| G1    | 0.449     | 0.525     |
| G2    | 0.492     | 0.494     |
| G3    | 0.475     | 0.491     |
| G4+   | 0.410     | 0.429     |

G1 flips from lowest (2024) to highest (2025). Confirms noise, not signal.
G4+ is consistently low in both years, but N is too small to trust.

---

## Context Splits (G2+ only, N=2,915)

### A) Top-3 Lineup Changes

Coverage: 1,649/2,915 (56.6%)

| Context              | N   | YRFI% | NRFI% |
|----------------------|-----|-------|-------|
| G2 same top3         | 115 | 0.365 | 0.635 |
| G2 changed top3      | 704 | 0.516 | 0.484 |
| G3 same top3         | 90  | 0.389 | 0.611 |
| G3 changed top3      | 634 | 0.498 | 0.502 |
| G4+ same top3        | 12  | 0.083 | 0.917 |
| G4+ changed top3     | 94  | 0.457 | 0.543 |

"Same top3" shows dramatically lower YRFI (36-39% vs 50-52%). However:
- N is small (115, 90, 12)
- Coverage is only 57% — many games lack lineup data for the prior game
- "Same top3" is likely correlated with rest patterns and opponent quality
- The effect does NOT vary by series slot — it's roughly −12pp in both G2 and G3
- This is a lineup-stability signal, not a series-position signal

### B) Catcher Changes

Coverage: 1,384/2,915 (47.5%)

| Context              | N   | YRFI% | NRFI% |
|----------------------|-----|-------|-------|
| G2 same catcher      | 382 | 0.453 | 0.547 |
| G2 changed catcher   | 314 | 0.541 | 0.459 |
| G3 same catcher      | 296 | 0.503 | 0.497 |
| G3 changed catcher   | 306 | 0.467 | 0.533 |
| G4+ same catcher     | 40  | 0.350 | 0.650 |
| G4+ changed catcher  | 46  | 0.435 | 0.565 |

G2 catcher change → +8.8pp YRFI. G3 catcher change → −3.6pp YRFI.
**Direction reverses across slots.** Not a real signal.

### C) Starter Tier Changes

Coverage: 2,602/2,915 (89.3%)

Starter tiers based on entering rolling-5-start ERA:
- Ace: ERA < 3.50
- Mid: ERA 3.50–4.50
- Back: ERA > 4.50

| Context                     | N   | YRFI% | NRFI% |
|-----------------------------|-----|-------|-------|
| G2 same tier both SP        | 335 | 0.481 | 0.519 |
| G2 tier change (either SP)  | 959 | 0.497 | 0.503 |
| G3 same tier both SP        | 316 | 0.487 | 0.513 |
| G3 tier change (either SP)  | 826 | 0.477 | 0.523 |
| G4+ same tier both SP       | 44  | 0.409 | 0.591 |
| G4+ tier change (either SP) | 122 | 0.426 | 0.574 |

Difference is <2pp in all slots. **No signal.**

Combined ERA tercile check (confirms ERA itself matters, but not via series slot):

| Context           | N   | YRFI% |
|-------------------|-----|-------|
| G2 low-ERA pair   | 252 | 0.448 |
| G2 mid-ERA pair   | 219 | 0.493 |
| G2 high-ERA pair  | 236 | 0.559 |

This is just ERA doing its job. No series-slot interaction.

### D) Day Game After Night Game

Coverage: 2,889/2,915 (99.1%)

| Context        | N     | YRFI% | NRFI% |
|----------------|-------|-------|-------|
| G2 DAGN        | 318   | 0.547 | 0.453 |
| G2 not DAGN    | 1,110 | 0.477 | 0.523 |
| G3 DAGN        | 586   | 0.462 | 0.538 |
| G3 not DAGN    | 689   | 0.499 | 0.501 |
| G4+ DAGN       | 102   | 0.431 | 0.569 |
| G4+ not DAGN   | 84    | 0.417 | 0.583 |

G2 DAGN shows +7.0pp YRFI vs non-DAGN. Interesting but:
- G3 DAGN shows −3.7pp (direction reverses)
- G4+ shows no difference
- The G2 DAGN effect could be real (tired hitters + unfamiliar starter = more chaos)
  or it could be noise at N=318

---

## Market Check

| Label | N     | Act YRFI | Imp YRFI | Residual | Act NRFI | Imp NRFI | Residual |
|-------|-------|----------|----------|----------|----------|----------|----------|
| G1    | 1,394 | 0.489    | 0.516    | −0.027   | 0.511    | 0.544    | −0.033   |
| G2    | 1,376 | 0.493    | 0.519    | −0.027   | 0.507    | 0.541    | −0.034   |
| G3    | 1,228 | 0.483    | 0.519    | −0.036   | 0.517    | 0.542    | −0.025   |
| G4+   | 179   | 0.413    | 0.520    | −0.107   | 0.587    | 0.541    | +0.046   |
| ALL   | 4,177 | 0.485    | 0.518    | −0.033   | 0.515    | 0.542    | −0.028   |

**The market does not differentiate by series slot at all** — implied YRFI is
~51.8% in every bucket.

G4+ shows a −10.7pp YRFI residual (actual 41.3% vs implied 52.0%). If this
were real, it would be a massive market blind spot. But N=179 across 2 seasons
and 30 teams. Expected noise range at N=179 with p=0.50 is ±7.3pp (2σ), so
10.7pp is about 1.5σ — notable but not conclusive.

DAGN market check:
| Context  | N     | Act YRFI | Imp YRFI | Residual |
|----------|-------|----------|----------|----------|
| DAGN     | 958   | 0.480    | 0.519    | −0.039   |
| not DAGN | 1,800 | 0.486    | 0.519    | −0.034   |

Difference in residuals: 0.5pp. Market already accounts for DAGN context.

---

## Verdict: NO SIGNAL

Series game number (G1/G2/G3/G4+) does not produce a meaningful first-inning
scoring signal, either by itself or through interaction with same-series changes.

**Evidence:**

1. **Raw splits fail the chi-square test** (p=0.29). G1, G2, G3 are within 1pp
   of each other. Only G4+ differs (−6.7pp YRFI vs average), but N=189 is too
   small and the effect is ~1.5σ.

2. **Year-over-year instability.** G1 flips from lowest YRFI (2024) to highest
   (2025). This is not a stable directional effect.

3. **Context interactions are inconsistent.** Catcher change and DAGN effects
   reverse direction between G2 and G3. Starter tier changes show <2pp across
   all slots.

4. **"Same top3" finding is a lineup-stability artifact**, not a series-slot
   effect. The ~12pp YRFI suppression when top-3 batters don't change is
   constant across G2 and G3 — it doesn't interact with series position.

5. **Market already handles this.** Implied YRFI probabilities are flat across
   series slots. The G4+ residual is the only candidate, but with N=179 it's
   within 2σ noise.

### What's NOT worth carrying forward

- Series game number as a feature in any model
- G4+ as an NRFI flag (N too small, not testable for years)
- Catcher change × series slot (reverses direction)
- Starter tier change × series slot (<2pp)

### Minor footnote (not actionable)

- G2 DAGN (+7pp YRFI, N=318) is the single most interesting cell, but it
  reverses in G3 and the market residual shows the market already prices it.
  Not worth building features for.

- "Same top3 in lineup" (−12pp YRFI, N=115-205 across G2/G3) is a real
  lineup-stability signal but it's already captured by the Phase 1 micro model's
  top-of-order features. It has nothing to do with series position.
