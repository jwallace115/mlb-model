# NFL H1 Script Regime Matchup Test — Phase 2

**Date:** 2026-04-06
**Season:** 2025 NFL regular season (183 games with H1 market close + regime labels)

---

## Verdict: CLOSE THIS BRANCH

No matchup cell produces a residual exceeding 1.0 points vs the H1 market close.
The maximum absolute residual across all cells is 0.7 points. All residuals
collapse to < 0.5 after controlling for the full-game closing total. The
offensive script shape regime framework does not identify structural H1 total
mispricing.

---

## Step 1 — Clustering Choice

**K=3** produced a thin TEMPO cluster (N=15, dominated by no-huddle offenses like
BUF/MIA). **K=2 chosen** for stability.

### Cluster Definitions (K=2)

| Cluster | N | H1 EPA/play | Pass Rate | Explosive% | No-Huddle% | Sack% |
|---------|---|-------------|-----------|-----------|-----------|-------|
| EFFICIENT | 312 | +0.101 | .566 | .065 | .104 | .029 |
| STRUGGLING | 194 | -0.119 | .581 | .042 | .066 | .054 |

EFFICIENT: positive EPA, more explosive plays, fewer sacks.
STRUGGLING: negative EPA, lower explosiveness, higher sack rate.

---

## Step 2 — Matchup Cell Results

| Home Offense | Away Offense | N | H1 Actual | H1 Close | Residual | Flag |
|-------------|-------------|---|-----------|----------|----------|------|
| EFFICIENT | EFFICIENT | 64 | 24.1 | 24.1 | **-0.0** | — |
| EFFICIENT | STRUGGLING | 43 | 22.7 | 23.4 | -0.7 | — |
| STRUGGLING | EFFICIENT | 47 | 22.0 | 22.5 | -0.5 | — |
| STRUGGLING | STRUGGLING | 29 | 20.9 | 21.4 | -0.5 | — |

**No cell exceeds 1.0 point residual.** The maximum is -0.7 (EFFICIENT vs STRUGGLING).

The H1 market line already captures the efficiency difference:
- EFFICIENT×EFFICIENT: close=24.1, actual=24.1 (perfect)
- STRUGGLING×STRUGGLING: close=21.4, actual=20.9 (-0.5)

The market correctly prices ~3 points lower for double-STRUGGLING games.

---

## Step 3 — Control Check

| Cell | Raw Residual | After Full-Game Total Control | Survives? |
|------|-------------|------------------------------|-----------|
| EFFICIENT × STRUGGLING | -0.7 | -0.4 | **NO** |
| STRUGGLING × EFFICIENT | -0.5 | -0.1 | **NO** |
| STRUGGLING × STRUGGLING | -0.5 | +0.1 | **NO** |
| EFFICIENT × EFFICIENT | -0.0 | +0.3 | **NO** |

All residuals collapse to < 0.5 after controlling for the full-game closing total.
The script regime effect is fully captured by the full-game total line.

---

## Step 4 — Stability Check

| Cell | First Half (W1-9) | Second Half (W10-18) | Consistent? |
|------|-------------------|---------------------|-------------|
| EFFICIENT × STRUGGLING | -0.8 (N=18) | -0.7 (N=25) | YES |
| STRUGGLING × EFFICIENT | -1.5 (N=21) | +0.3 (N=26) | **NO** |
| STRUGGLING × STRUGGLING | -0.1 (N=11) | -0.7 (N=18) | YES |
| EFFICIENT × EFFICIENT | -0.2 (N=35) | +0.2 (N=29) | **NO** |

Two cells are directionally consistent but with tiny residuals (-0.7 to -0.8).
Two cells flip direction across halves of the season.

---

## Step 5 — Concentration Check

| Cell | Top 5 Teams | Share |
|------|-------------|-------|
| EFFICIENT × STRUGGLING | CIN(5), NO(5), DAL(5), LV(5), IND(4) | 28% |
| STRUGGLING × EFFICIENT | CLE(6), BAL(6), LAC(6), SF(5), NYJ(5) | 30% |
| STRUGGLING × STRUGGLING | TEN(6), ARI(5), LV(5), NYJ(5), KC(4) | 43% |

STRUGGLING×STRUGGLING is moderately concentrated (43% in 5 teams), but this is
moot since the cell doesn't produce a meaningful residual anyway.

---

## Why This Branch Failed

1. **The H1 market already prices offensive efficiency.** The closing H1 total
   moves ~3 points between double-EFFICIENT and double-STRUGGLING games. The
   script shape regime is a valid structural descriptor but the market knows it.

2. **Full-game total subsumes the regime signal.** After controlling for the
   full-game closing total, all regime residuals collapse to noise. The full-game
   line already incorporates how well each offense is playing.

3. **K=2 is too coarse for non-obvious effects.** EFFICIENT vs STRUGGLING is
   essentially "good offense vs bad offense" — exactly what Vegas prices. K=3
   adds a TEMPO dimension but the sample is too thin (N=15) to be useful.

4. **NFL H1 totals are noisy.** The market close correlates only r=0.173 with
   actual H1 totals (from Phase 1 audit). Even a perfect structural model would
   explain little additional variance in this inherently high-noise outcome.

---

## Implications for the NFL Derivatives Project

The offensive script shape regime does not produce a usable H1 total mispricing
signal. This does not kill the entire derivatives project, but it closes the most
natural first branch.

**Remaining options from the project brief:**
- **Defensive vulnerability regimes** — test whether defensive structure adds
  value beyond what offense-only regimes captured (may face same problem)
- **Player props** — fundamentally different market structure, may be less
  efficiently priced than game totals derivatives
- **Role redistribution (injury lags)** — state-change approach rather than
  regime approach, may avoid the "Vegas already knows" problem

**Recommended next step:** Move to player props (Branch B from the project brief)
rather than continuing to test more H1 total regime variants. The props archive
has 2.3M rows and may offer better opportunities where market efficiency is lower.
