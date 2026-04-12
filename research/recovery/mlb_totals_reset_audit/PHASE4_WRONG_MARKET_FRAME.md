# PHASE 4 — Wrong Market Frame Analysis

**Date:** 2026-04-12

---

## Objects Classified WRONG MARKET FRAME

### 1. Alt-Total Surface Mispricing (F1)

**Signal:** Books use smooth interpolation for alt-total ladders (O/U 7.5, 8.5, 9.5, etc.)
that does not match the actual run-scoring distribution's thinner tails.

**Why it is real:** 82% directional consistency across two independent windows. The curvature
error is statistically measurable at +2 to +5 from the main line.

**Why it cannot be bet:** Hold widens from 5.9% at the main line to 7.0-7.2% at distance
+3-4. This is not accidental — books KNOW their alt-total ladders are approximate and
compensate by widening the vig. Only 1-2 of 7 books showed positive ROI, and the strongest
single result (williamhill_us +5.0%, N=366) is a single-book finding that would not survive
multi-book replication.

**Could it ever be bet?** Only if a book offers alt totals with main-line vig (4.5-5.5%).
This is unlikely in the current market. The finding is structurally correct but economically
unexecutable.

---

### 2. NRFI Selector (H2)

**Signal:** Low-total games (F5<=4.0, FG<=8.0) have 55-56% NRFI rate vs 51.2% baseline.
The selector correctly identifies above-average NRFI probability games.

**Why it is real:** Phase 1-5 research with 9,900 games confirms the directional signal.
F5 total is the strongest single predictor. Day games, cold weather, and pitcher NRFI
history all contribute independently.

**Why it cannot be bet:** NRFI market prices at -135 to -145 (implied 57.4-59.2%). The
best achievable NRFI rate after all filtering is 55.7% — still below the implied
probability. The selector adds +4.4pp over baseline but baseline is 51.2% and the market
demands 57.4%+. The gap is ~2pp. No combination of available features bridges this gap.

**Could it ever be bet?** Only if NRFI vig compresses to -120 range (implied 54.5%).
Some promotional markets occasionally offer this. The selector would be ready to deploy
if market conditions change. Keep the selector frozen but ready.

---

## Key Insight

Both WRONG MARKET FRAME objects demonstrate the same principle: the MLB market has
multiple layers of defense against known edges. The primary defense is the closing line.
The secondary defense is the vig structure, which widens at exactly the points where
models detect mispricing. The tertiary defense is hold compression on derivative markets
where the conversion from main-line pricing to derivative pricing is known to be
approximate.

A successful totals strategy must either:
1. Find signal the market does NOT already price (rare)
2. Find a market where the vig is structurally low enough to permit exploitation (F5 RL at -120 to -140 is the best current candidate)
3. Find promotional or soft-line books that offer -110 on derivatives where the model has +5pp edge
