# Cross-AI Review Brief — Football Edge + Kalshi Integration
**Prepared for adversarial review · 2026-08-28**
**Operator:** Jeff (FL). **Reviewer role requested:** attack this, don't validate it.

---

## 0. HOW TO USE THIS

Two independent research programs converged this week on the same conclusion from
opposite directions. That convergence is either the most useful finding in either
project, or it is two AIs pattern-matching on a coincidence. **Your job is to determine
which.**

Please do not summarise this back. Answer the questions in §6, lead with the strongest
objection you have, and say explicitly where you think the reasoning is motivated rather
than evidenced.

---

## 1. THE TWO PROGRAMS

**Program A — "iamnotuncertain"** (18 months). Multi-sport betting models: MLB, NBA,
NHL, golf, soccer, WNBA, NCAAF, NFL. History of contamination failures (end-of-season
lookahead, discovery-validation leakage) that produced a strict audit framework: PIT
provenance, leakage checks, research/live object identity, real-price economics, regime
breakdowns. Five autonomous discovery engines have collectively tested ~2.8M conditions
across MLB/NBA/NHL.

**Program B — "Kalshi Edge Lab"** (~6 months). Prediction-market microstructure research.
Order-book capture (26.4M frames), replay, provenance, forward-only methodology,
pre-frozen hypotheses, strict governance with explicit authority boundaries.

The operator built both. **Until this week they had never been connected.**

---

## 2. WHAT WAS MEASURED THIS WEEK (Program A, football)

All computed directly against repo archives. Numbers are exact, not recalled.

### 2.1 The physics
- SD(actual margin − closing line), NCAAF 2022–25, N=2,998: **15.24 points**. NFL totals: 13.10.
- Picking the market favourite straight up: **73.0%** correct. Favourites laying 21+: **95.2%**.
- Same games against the spread: home covers 49.4%, away 49.8%.
- Edge required: **0.91 pts** to break even at −110; **1.92 pts** for 55%; 3.86 for 60%.
- Market's own average error: 12.02 pts.
- NCAAF ridge engine: corr(pred, actual)=0.5765 but corr(pred, spread)=**0.8558** — ~86% of the
  model re-derived the line. OOS ATS 49.5–50.0%, −9.1% to −11.1% ROI, MAE 13.23 vs market 11.87.

### 2.2 The execution finding (replicated 3×)
Value of taking the best available number vs one randomly chosen book:

| Test | Books | Value | t | Prices |
|---|---|---|---|---|
| NFL totals | 10 | +4.31% | 4.63 | real captured |
| NCAAF spreads | 2 | +3.63% | 7.71 | flat −110 |
| NCAAF totals | 2 | +2.32% | 3.56 | flat −110 |

- Dispersion at open **1.213 pts** vs close **0.711** (same 10 books, NFL totals).
- In line units, 10-book shopping ≈ **0.89 pts** against the **0.91 pts** needed to break even.
- Books do not price the dispersion: mean under-price at the *best* number −108.3 vs −109.9
  at the median number. The better line comes at a marginally better price.

### 2.3 The wind finding (survived a pre-registered kill test)
Kill condition fixed before running: survives only if slope ≤ −0.10 AND t ≤ −2.00.

| Wind source | Slope (pts/mph on residual) | t |
|---|---|---|
| nflreadpy reported | −0.1669 | −2.24 |
| Open-Meteo archive | **−0.2182** | **−2.83** |
| IV (archive instruments nflreadpy) | −0.3088 | — |

- Book prices **−0.0924** pts/mph into the line. Residual −0.2182. Sum −0.3106 vs independent
  IV of −0.3088 — two routes agreeing to 0.002. Books capture ~**30%** of a −0.31 effect.
- Survives controls for temperature, month, total size (β=−0.165, t=−2.21).
- Forecast attenuation measured on 2024 (N=187): λ ≈ **0.77 at 24h**, 0.69 at 48h.
  Bettable slope ≈ −0.168 → **~2.5 pts of edge on a 15mph game** vs 0.78 needed.
- **Known flaws:** wind is sampled at 17:00 UTC for every game regardless of kickoff (biases
  against the finding). Two weather sources correlate only 0.683 with each other. Forecast
  variance exceeds analysis variance at 48/72h, which makes the λ correction unreliable there.

### 2.4 Key numbers
NFL margin lands exactly on 3 in **14.27%** of games, on 7 in 8.24%. NCAAF 10.91% / 8.81%.
Cross-book straddles of a key number are ~1.5–1.8× more common at open than close.
Where books straddle, the choice of book flips the result **12.33%** (at 3) and **20.29%** (at 7).

### 2.5 The variance reality
272 NFL games, 1 unit each, −110: season SD **15.7 units**. A genuine 53% bettor expects +3.2u
and **loses money in 41.9% of seasons**. Seasons of 272 bets until a 95% CI on ROI excludes zero:
53% → **91.8**; 54% → 13.4; 55% → 5.1.

---

## 3. WHAT DIED (calibrate on these)

- **11 football research branches**: all closed, near-miss, or failed audit. Every one was
  prediction-edge work (feature → residual vs the line).
- **Conditional-subset sweep**: 19 real situational conditions, all 2- and 3-way combos.
  Real data produced 104 systems ≥55%. **Identical search on randomly shuffled outcomes
  produced 94** — and the best system in pure noise (70.2% avg, 76.5% max) beat the best in
  real data (67.5%). The search manufactures false positives faster than 1,656 games refute them.
- **Moneyline vs run-line consistency** (MLB, 10,728 games): markets agree. Best cell t=0.78.
- **Middles across key numbers**: +EV only across 3 and 7, ~17 games/season. Under 2 units.
- **Line shopping alone**: +0.4pp — necessary, not sufficient.
- **Autonomous engines** (MLB/NBA/NHL, ~2.8M tests): survivors at or below the noise floor.
  V2 produced 639 three-stage survivors against ~884 expected by chance.

---

## 4. WHAT PROGRAM B ALREADY FOUND (Kalshi, independent)

From `docs/capture003_of2_sports_audit.md`, written before any of the above:

- Sports = **73%** of OF-2 order-flow signals (12,581 of 17,230) — the dominant category.
- **Fixed-horizon taker economics are negative at every horizon**: −7.56c at +1s through
  −4.80c at +600s. Cumulative −16,120c over 3,356 observations.
- 47.3% "ever net positive" — but requires oracle exit timing.
- By market type: **totals 57.5%, spreads 54.4%, winners 44.4%** ever-net-positive.
- By sport: MLB 56.5%, Tennis 53.9%, **NFL 44.6%** (weak), UFC 19.0%.
- Down/NO direction 58.9% vs Up/YES 42.5%.
- 1c-spread signals perform **worst** (42.1%).
- Stated conclusion: *"the spread is the dominant cost"*; recommended next direction is
  **sports-specific maker entry**, blocked on live fill data.

Kalshi fee structure (verified): taker max 1.75c/contract at 50c; **maker = 25% of taker**,
max 0.44c; **no fee on unfilled or cancelled limit orders**; no settlement or inactivity fees.
Exchanges do not limit winning accounts.

---

## 5. THE CONVERGENCE CLAIM (most likely thing to be wrong)

Program A concluded: *the edge is in the number you obtain, not the side you pick; obtaining
a better number is worth almost exactly the vig (0.89 vs 0.91 pts).*

Program B concluded: *the spread is the dominant cost; avoiding crossing it is the only
untested path.*

**The claim is that these are the same finding in two vocabularies** — and that Program B's
venue (no account limits, near-zero maker fees, free resting orders) is the natural execution
layer for Program A's edge, while Program A supplies the fair value Program B lacks.

---

## 6. QUESTIONS — please answer these directly

**Q1 (attack the execution finding).** The shopping result is a paired comparison: best
available number vs one randomly chosen book, same game, same side. It replicated across two
sports, two markets, two datasets, all p<0.001. What is the strongest reason this could be
spurious or non-monetisable? Specifically: is there a selection or survivorship mechanism in
"which book happens to hold the outlier number" that we have not accounted for?

**Q2 (attack the wind finding).** It passed a pre-registered kill test and the residual +
book-adjustment sums to an independently derived IV estimate. But wind is sampled at the wrong
hour, the two weather sources correlate only 0.683, and forecast variance exceeds analysis
variance at the lead times that matter. Is the IV estimate valid here, or is the exclusion
restriction violated — i.e. can Open-Meteo archive error be correlated with nflreadpy error
(both derive partly from the same station networks)? If so, what does that do to −0.3088?

**Q3 (attack the convergence).** Is §5 a real structural identity or two AIs pattern-matching?
What would distinguish those empirically? Note NFL is one of Kalshi's *weakest* sports (44.6%)
while the football research is NFL/NCAAF-focused — does that undercut the integration thesis?

**Q4 (the blind spot).** The April 2026 four-AI consultation found one category all four models
missed: promotional/bonus economics as a first-class edge source. What is this week's equivalent?
What has been systematically ignored?

**Q5 (sequencing under real constraints).** Operator constraints: only legal in-state book is
Hard Rock (never captured; sits in Odds API region `us2`, which every pull has missed for 3
years); Odds API key lapsed; no offshore accounts yet; the Kalshi repo has an explicit
governance boundary ("Phase A5c3 not authorized... no research execution authority").
Given ~$120/mo of API budget and no capital deployed, what is the correct order of operations?

**Q6 (the honest ceiling).** Given σ=15.24, 272 NFL games/season, and 91.8 seasons to prove a
53% win rate — is a retail single-operator football program rational at all, or is the correct
answer to redirect entirely to MLB (2,430 games/season) and Kalshi microstructure? Argue the
case for abandoning football specifically.

---

## 7. GROUND RULES FOR THE REVIEW

- Nothing here is deployed. No capital anywhere. Nothing is promoted.
- Every number is measured, not remembered. Ask for the query if one looks wrong.
- The operator's stated frustration is that prior work "found surface-level things, investigated,
  found we could beat the vig, and gave up." A review that simply endorses the findings is
  worth nothing. **Assume something above is wrong and find it.**
