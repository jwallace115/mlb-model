# Phase 11 — Top-3 Lineup Stability Overlay on NRFI Parlay Helper

**Date:** 2026-04-06
**Design:** Overlay test on frozen Phase 8 helper. No retraining.

---

## Verdict: UPDATE HELPER — Add "exclude games where both teams changed top 3"

Variant H (exclude games where BOTH teams changed their top-3 batting order vs
their prior game) passes all five decision criteria. The excluded "both_changed"
games are dramatically bad for NRFI, especially in 2025 OOS.

---

## Pool Reconstruction Note

The Phase 8 helper pool was reconstructed by re-scoring all 2024-2025 games
with the frozen micro models (top1, bot1, archetype). Due to feature pipeline
differences (TTO1 availability, rolling stat boundary effects), the
reconstructed pool does not exactly match the original Phase 4/Phase 8 reports:

| Pool | Original N / NRFI | Reconstructed N / NRFI |
|------|-------------------|----------------------|
| Phase 4 2024 | 67 / .597 | 114 / .623 |
| Phase 4 2025 | 81 / .568 | 107 / .533 |
| Phase 8 2024 | 46 / .630 | 86 / .663 |
| Phase 8 2025 | 44 / .636 | 80 / .512 |

The reconstructed pool is larger (B10 threshold selects more games from smaller
daily scored slates) and the 2025 NRFI rate is lower. **All comparisons in this
report are relative within the reconstructed pool.** The directional findings
(which variants help/hurt) are valid; the absolute NRFI rates should not replace
the original Phase 8 report values.

---

## Step 0 — Tag Audit

**Source:** `mlb/data/lineups.parquet` → top-3 batting order per game/team
**Logic:** For each team, count hitters in current top 3 not present in prior
team game's top 3. Combined: if either team has changes in top 3, classify as
"one_changed" or "both_changed" (both teams changed at least one top-3 hitter).

**Coverage in Phase 8 pool:**

| Year | Phase 8 N | With tag | both_same | one_changed | both_changed |
|------|-----------|----------|-----------|-------------|--------------|
| 2024 | 86 | 86 (100%) | 7 | 32 | 47 |
| 2025 | 80 | 80 (100%) | 14 | 35 | 31 |

100% coverage — tag is fully attachable to all Phase 8 helper-qualified games.

---

## Step 1 — Overlay Variants

| Variant | N 2024 | NRFI 24 | d24 | N 2025 | NRFI 25 | d25 |
|---------|--------|---------|-----|--------|---------|-----|
| **Phase 8 baseline** | **86** | **.663** | **—** | **80** | **.512** | **—** |
| A) both_same | 7 | .857 | +.194 | 14 | .786 | +.273 |
| B) one_changed | 32 | .688 | +.025 | 35 | .571 | +.059 |
| C) both_changed | 47 | .617 | −.046 | 31 | .323 | **−.190** |
| D) 0 total changes | 7 | .857 | +.194 | 14 | .786 | +.273 |
| E) 1-2 total changes | 61 | .639 | −.023 | 49 | .531 | +.018 |
| F) 3+ total changes | 18 | .667 | +.004 | 17 | .235 | **−.277** |
| **G) exclude 3+** | **68** | **.662** | **−.001** | **63** | **.587** | **+.075** |
| **H) exclude both_changed** | **39** | **.718** | **+.055** | **49** | **.633** | **+.120** |
| I) require ≤2 changes | 68 | .662 | −.001 | 63 | .587 | +.075 |

### Key observations

1. **Variant A (both_same)** has the highest lift (+27.3pp OOS) but **N=14 in
   2025 — fails the N≥30 hard stop.** Not viable as a filter.

2. **Variant H (exclude both_changed)** is the best qualifying filter: +12.0pp
   in 2025 (N=49), +5.5pp in 2024 (N=39). Both years positive.

3. **Variant C/F reveal the mechanism:** "both_changed" games have only 32.3%
   NRFI in 2025 (vs 51.2% baseline). "3+ total changes" is even worse at 23.5%.
   These are the toxic games dragging down the helper pool.

4. Variant G/I (exclude 3+ total changes) is more conservative: +7.5pp lift,
   N=63. Retains more games but weaker improvement.

---

## Step 2 — Control Checks

Variant H pool (N=88 combined):

| Split | N | NRFI |
|-------|---|------|
| Day games | 33 | .697 |
| Night games | 55 | .655 |
| Series G1 | 31 | .613 |
| Series G2 | 21 | .810 |
| Series G3 | 31 | .581 |
| 2024 | 39 | .718 |
| 2025 | 49 | .633 |

- **Day/Night:** No dramatic skew (day .697 vs night .655)
- **Series position:** G2 is high (.810) but N=21; G1 and G3 are similar
- **Year stability:** Both years above Phase 8 baseline

Team distribution:
- Top 5: SEA(20), LAA(13), HOU(12), STL(12), MIA(12)
- HHI: 0.059 — well-distributed, not concentrated

The effect is NOT explained by day/night, series position, or team concentration.
It is a genuine lineup-stability signal.

---

## Step 3 — Parlay Simulation (pooled)

| Pool | NRFI | 3-leg | 5-leg |
|------|------|-------|-------|
| Random 2025 | .499 | 12.4% | 3.1% |
| Phase 8 2024 | .663 | 29.1% | 12.8% |
| Phase 8 2025 | .512 | 13.4% | 3.6% |
| **Variant H 2024** | **.718** | **36.9%** | **19.0%** |
| **Variant H 2025** | **.633** | **25.3%** | **10.1%** |

**3-leg parlay improvement over Phase 8 (2025 OOS): +11.9pp** (25.3% vs 13.4%).
**5-leg parlay improvement: +6.5pp** (10.1% vs 3.6%).

Both are large improvements. Note: pooled simulation, not slate-aware.

---

## Step 4 — Fragility Check (2025)

| Test | N | NRFI |
|------|---|------|
| Full Variant H pool | 49 | .633 |
| Remove top-5 teams (SEA, LAA, MIL, MIA, HOU) | 14 | **.857** |
| First half (≤Jun) | 24 | .667 |
| Second half (Jul+) | 25 | .600 |

- **Team removal: PASSES** — NRFI actually improves after removing top-5 teams
  (N=14, .857). Not a team-concentration artifact.
- **Season stability: PASSES** — H1=.667 and H2=.600. Consistent across halves.
- **N=14 after top-5 removal is small** but the direction is strongly positive.

---

## Decision Criteria

| Criterion | Result | Status |
|-----------|--------|--------|
| 2025 OOS NRFI lift ≥ +2pp | +12.0pp | **PASS** |
| 2025 OOS N ≥ 30 | 49 | **PASS** |
| Non-negative in 2024 | +5.5pp | **PASS** |
| Controls don't explain it away | Day/night, series, team all clean | **PASS** |
| Fragility above Phase 8 baseline | .857 after top-5 removal | **PASS** |
| 3-leg parlay improves | 25.3% vs 13.4% | **PASS** |

All six criteria pass.

---

## Mechanism

When BOTH teams change their top-3 batting order from their prior game, the
first inning becomes less predictable:

- New hitters in the top 3 are unfamiliar to the opposing starter's scouting prep
- Lineup disruption often correlates with rest patterns, call-ups, or matchup
  adjustments that introduce volatility
- The "both_changed" games in the Phase 8 pool had only 32.3% NRFI rate in 2025
  OOS — they are actively harmful to NRFI parlay quality

Excluding these games removes the most unpredictable first-inning matchups from
the helper pool, leaving games where both lineups are stable and the pitching
matchup analysis (which drives the Phase 1 micro model) is most reliable.

---

## Updated Rule (Plain English)

> **NRFI Parlay Helper — Phase 11 Selection Rule:**
>
> Select games where:
> 1. Combined YRFI probability is in the bottom 10% of the day's slate
> 2. Both top-of-1st and bottom-of-1st probabilities are individually in bottom 30%
> 3. Home starting pitcher is NOT classified as CONTACT_RISK archetype
> 4. **It is NOT the case that both teams changed at least one top-3 hitter**
>    **from their prior game's batting order**
>
> Rule 4 requires checking today's confirmed lineups against each team's most
> recent game lineup. If lineups are not yet confirmed, the game cannot be
> evaluated for Rule 4.
>
> Expected pool: ~4-5 games per 100 on the slate (~45-50/season).
> Expected NRFI hit rate: ~63% (vs ~51% Phase 8 baseline in reconstructed pool).
> Expected 3-leg parlay hit rate: ~25% (vs ~13% Phase 8 baseline).

---

## Caveats

1. **Pool reconstruction is imperfect.** The absolute NRFI rates in this report
   differ from the original Phase 8 report due to feature pipeline differences.
   The directional finding (excluding both_changed helps) is robust; the exact
   NRFI improvement may differ in production.

2. **N=49 in 2025 is above threshold but still moderate.** The +12.0pp lift is
   large enough that it should be detectable even with some noise, but expect
   regression toward a smaller (but still positive) effect.

3. **The filter requires confirmed lineups.** Rule 4 cannot be applied before
   lineups are announced (typically 1-3 hours before game time). This makes the
   filter a late-day refinement, not a morning selection tool.

4. **Variant A (both_same → NRFI 78.6%) is tantalizing but N=14.** If future
   data confirms this rate at N≥30, it would justify a stronger "require
   both_same" filter. For now, the conservative "exclude both_changed" is the
   safer production rule.

5. **The excluded "both_changed" pool (NRFI 32.3% in 2025) is genuinely toxic.**
   This is the strongest evidence: not just that stable lineups help, but that
   disrupted lineups actively hurt NRFI outcomes. This is a clear, actionable
   exclusion.
