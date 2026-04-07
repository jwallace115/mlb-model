# NHL Original ANEMIC × BNB Layer Test — Phase 6

**Date:** 2026-04-06
**Data:** 1,805 confirmed-starter games with model edge scores, 4 seasons

---

## Verdict: CLOSE

The original ANEMIC × BEND_NOT_BREAK archetype does not help the live NHL model
in any layering framing. At every edge threshold tested, the FAVORABLE archetype
group performs WORSE than the NONE group. The archetype context is at best neutral
and at worst counterproductive as a conditional layer.

---

## Step 0 — Label Audit

Phase 1 archetypes attached cleanly to all 1,805 confirmed-starter games.

| Season | FAVORABLE | STRONG FAV | NONE |
|--------|-----------|------------|------|
| 2021 | 86 | 7 | 371 |
| 2022 | 100 | 8 | 331 |
| 2023 | 51 | 1 | 392 |
| 2024 | 18 | 0 | 456 |

FAVORABLE games are declining across seasons (86 → 18), suggesting the archetype
landscape is shifting — fewer teams fit the ANEMIC × BEND_NOT_BREAK profile in
recent seasons.

---

## Step 2 — Baseline

| Threshold | N | Over% | Implied | Residual | ROI |
|-----------|---|-------|---------|----------|-----|
| edge >= 0.12 | 24 | 54.2% | 50.2% | +4.0pp | +3.4% |
| edge >= 0.10 | 40 | 50.0% | 50.6% | -0.6pp | -4.5% |
| **edge >= 0.08** | **80** | **60.0%** | **50.6%** | **+9.4pp** | **+14.5%** |
| edge >= 0.06 | 140 | 57.1% | 50.6% | +6.5pp | +9.1% |

The edge >= 0.08 threshold actually performs better than edge >= 0.12 in the
confirmed-starter subset (60.0% vs 54.2%). This is notable but outside the
scope of this archetype test.

---

## Step 3 — Conditional Layer Results

### At edge >= 0.08 (most informative threshold)

| Context | N | Over% | Residual | ROI |
|---------|---|-------|----------|-----|
| **NONE** | **69** | **60.9%** | **+10.4pp** | **+16.2%** |
| FAVORABLE | 11 | 54.5% | +3.4pp | +4.1% |

**FAVORABLE performs WORSE than NONE** by -6.4pp. The archetype context does not
help — it actually hurts. Games where the model has edge >= 0.08 AND no archetype
qualification have a 60.9% over rate.

### At edge >= 0.06

| Context | N | Over% | Residual | ROI |
|---------|---|-------|----------|-----|
| **NONE** | **122** | **57.4%** | **+6.8pp** | **+9.5%** |
| FAVORABLE | 18 | 55.6% | +4.4pp | +6.1% |

Same pattern — NONE outperforms FAVORABLE at every threshold.

### At edge >= 0.04 (lowest, for directional check)

| Context | N | Over% |
|---------|---|-------|
| NONE | 187 | 54.0% |
| FAVORABLE | 37 | 56.8% |

At the lowest threshold, FAVORABLE slightly outperforms NONE (+2.8pp). But this
reversal at the lowest threshold with the smallest edge suggests FAVORABLE games
are lower-quality plays that the model barely endorses.

---

## Step 4 — Threshold Modifier

| Test | N | Over% | vs Baseline (54.2%) |
|------|---|-------|---------------------|
| edge >= 0.08 + FAVORABLE | 11 | 54.5% | +0.3pp (negligible) |
| edge >= 0.06 + FAVORABLE | 18 | 55.6% | +1.4pp (not enough) |

No threshold modifier passes. The FAVORABLE context does not justify lowering
the edge threshold.

---

## Step 5 — Pass Filter

| Threshold | FAVORABLE Over% | NONE Over% | Delta |
|-----------|----------------|-----------|-------|
| edge >= 0.08 | 54.5% | **60.9%** | **-6.4pp** |
| edge >= 0.06 | 55.6% | **57.4%** | **-1.8pp** |

**FAVORABLE games are WORSE than NONE at every tested threshold.** The archetype
is not a useful pass filter — if anything, FAVORABLE is the pass signal, not NONE.

---

## Step 6 — CLV Check

CLV data not joinable at this sample size. Omitted.

---

## Why FAVORABLE Underperforms

The most likely explanation: the ANEMIC × BEND_NOT_BREAK cell identifies high-volume,
low-quality shot environments. The live NHL model already captures this information
through its xG and shot-based features. When the model says edge >= 0.08, it has
already accounted for the structural environment. The archetype label adds no
independent information and may actually be correlated with lower-quality
model-edge games (games where the model barely qualifies because shot volume
inflates the projected total but shot quality is low).

---

## Decision

| Framing | Result | Status |
|---------|--------|--------|
| Confidence layer | FAVORABLE underperforms NONE | **CLOSE** |
| Threshold modifier | +0.3pp at best, N=11 | **CLOSE** |
| Pass filter | Wrong direction — should pass FAVORABLE, not NONE | **CLOSE** |
| Context badge | Counterproductive information | **CLOSE** |

**All framings fail. The original Phase 1 archetype does not help the live model
in any capacity.**

---

## Final Disposition of NHL Archetype Program

| Phase | Test | Verdict |
|-------|------|---------|
| 0 | Data audit | GO NOW |
| 1 | Defensive archetypes (standalone) | +0.38 goals — ADVANCE |
| 2 | Practical validation | ARCHIVE — goalie-driven |
| 3 | 8-branch expansion | 4 ADVANCE (fast harness) |
| 4 | Practical validation (top 2) | ARCHIVE — market prices it |
| 5 | Edge layering (Branch 7+8) | CLOSE — N=24 too thin |
| **6** | **Original BNB as layer** | **CLOSE — underperforms baseline** |

**The NHL archetype research program is definitively closed.** The framework
produces real structural descriptions but the NHL totals market efficiently
prices process-stat information. The live model already captures what the
archetypes measure, making them redundant or counterproductive as overlays.

**The existing NHL live model (ridge + calibration + goalie state) remains
the best available approach.** No archetype modification is recommended.
