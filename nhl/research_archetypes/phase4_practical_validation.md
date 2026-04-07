# NHL Archetype Phase 4 — Practical Validation

**Date:** 2026-04-06
**Data:** 5,248 games, 4 NHL seasons (confirmed-starter subset: 1,805 games)

---

## Verdict: ARCHIVE BOTH BRANCHES

Neither Branch 7 (Special Teams Net) nor Branch 8 (Process Dominance) produces
a market-beating residual in confirmed-starter games. The over-hit rates are
above base but the market already prices them — fair implied probability is
within 1pp of actual hit rate. These are real structural patterns that the
market efficiently captures.

---

## Branch 8: Process Dominance — ARCHIVE

| Test | Result |
|------|--------|
| Hit rate (starters) | 51.1% over (base 45.6%, lift 1.12x) |
| Market residual | **+1.0pp** (below 3pp threshold) |
| ROI at -110 | +2.6% |
| Season consistency | **4/4** |
| Edge overlap | 2.1% (essentially independent) |
| vs heuristics | Beats all naive methods (1.12x vs 1.00x) |
| Concentration | Top 2 = 10%, effect drops to 49.9% after removal |

**Why it fails:** The market residual is only +1.0pp. The over-hit rate of 51.1%
is real and consistent (4/4 seasons) but the market's fair-implied probability
for these games is already 50.1%. The market knows this structural pattern and
prices it correctly.

**After top-2 team removal:** Over rate drops from 51.1% to 49.9% — the effect
is partially concentrated in MTL and CBJ games, which are weaker teams that
create high-event-count games.

### Branch 7: Special Teams Net — ARCHIVE

| Test | Result |
|------|--------|
| Hit rate (starters) | 49.7% over (base 45.6%, lift 1.09x) |
| Market residual | **-0.5pp** (negative — market overprices OVER) |
| ROI at -110 | -0.8% |
| Season consistency | **4/4** |
| Edge overlap | 2.4% (essentially independent) |
| vs heuristics | Beats naive methods (1.09x vs 1.00x) |
| Concentration | Top 2 = 10%, effect improves to 50.9% after removal |

**Why it fails:** The market residual is actually NEGATIVE (-0.5pp). Despite the
over-hit rate being above base (49.7% vs 45.6%), the market's fair-implied
probability for these games is 50.2% — the market is already pricing these
games as over-likely. No edge exists.

---

## Overlap Check

| Metric | Value |
|--------|-------|
| Branch 8 qualifying games | 1,138 |
| Branch 7 qualifying games | 527 |
| Overlap | 337 (64% of Branch 7) |
| Union | 1,328 |

Branches are **partially redundant** — 64% of Branch 7 games also qualify for
Branch 8. Stacking them would not provide meaningfully additive coverage.

---

## Why the Phase 3 Results Were Misleading

The Phase 3 fast harness found starter residuals of +0.27 to +0.30 goals. These
were real in terms of actual-minus-closing-total arithmetic. But the practical
validation reveals that:

1. **The over-hit rate is 51%, not the 55%+ needed for deployment.** A +0.27 goals
   residual translates to only ~3-5pp lift in over-hit rate, which is below the
   practical threshold when vig is applied.

2. **The market already adjusts for process dominance.** The fair-implied
   probability for qualifying games is 50.1-50.2%, meaning the market sees these
   as essentially coin-flip or slight-over games already. The structural pattern
   is priced.

3. **Concentration matters more than expected.** Removing the top 2 teams (MTL, CBJ
   for Branch 8) drops the over-hit rate from 51.1% to 49.9%, suggesting these
   archetype cells are partially driven by weak-team artifact rather than pure
   structural style.

---

## Implications for NHL Archetype Program

The NHL archetype framework produces real structural descriptions of team style
(4/4 season consistency, interpretable clusters, outperforms naive heuristics).
But it does not produce market-beating residuals because:

1. NHL totals markets are well-calibrated at the game level
2. Process stats (xG, shots, HD) are well-known and widely used by bettors and models
3. The structural patterns these archetypes capture are already reflected in the
   closing line, even if not explicitly via archetype labeling

**The honest conclusion:** NHL totals markets are more efficient than MLB or golf
markets at pricing process-stat information. The archetype framework is valid
descriptively but does not produce actionable mispricing.

---

## Recommended Disposition

1. **Archive the NHL archetype program.** No branch produced a deployable signal.
2. **Do NOT test Branches 5 and 6.** If the two strongest branches (7 and 8) fail
   practical validation, weaker branches will not pass either.
3. **The existing NHL live model** (ridge + calibration + goalie state) remains the
   best available approach for NHL totals.
4. **Future NHL research** should focus on goalie-specific state changes (backup
   goalie in high-event environments) rather than team-level process archetypes,
   since the Phase 2 goalie-state interaction was the only finding that showed
   real market mispricing.
