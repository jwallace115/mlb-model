# BetOnline Pricing Diagnostic — Under 1.5 Total Bases

**Date:** 2026-03-27
**Status:** Market structure research — no model changes

---

## Executive Summary

The BetOnline Under 1.5 TB signal identified in v1 and v1.1 is caused by **two stacked effects**, not one:

| Effect | Contribution | Magnitude |
|:-------|:-------------|:----------|
| **Selection bias** (different player population) | PRIMARY | ~19pp of the 22pp "edge" |
| **Genuine mispricing** (flat odds for heterogeneous players) | SECONDARY | ~3pp residual |

**The v1.1 SHADOW CANDIDATE verdict was contaminated by selection bias.** The 83% win rate and +22% ROI at BetOnline Under 1.5 are predominantly explained by BetOnline posting 1.5-line props for *much weaker hitters* than other books, not by sportsbook mispricing.

---

## Finding 1: Zero Cross-Book Overlap

**Not a single batter-game-date appears at line 1.5 on both BetOnline and any other book.**

| Book Pair | Overlapping Batter-Dates at Line 1.5 |
|:----------|---:|
| BetOnline ∩ FanDuel | **0** |
| BetOnline ∩ DraftKings | **0** |
| BetOnline ∩ BetMGM | **0** |
| BetOnline ∩ William Hill | **0** |
| BetOnline ∩ Bovada | **0** |
| BetOnline ∩ Fanatics | **0** |

Cross-book price comparison is impossible because the books serve entirely different player pools at this line. The BetOnline players who appear at line 1.5 show up on FanDuel at lines 2.5-4.5 (higher lines for the same players, 12 matches found).

---

## Finding 2: Dramatically Different Player Populations

| Book | N | Avg Batting Order | Mean Actual TB | P(TB = 0) | P(Under 1.5) | Implied P(Over) |
|:-----|---:|---:|---:|---:|---:|---:|
| **BetOnline** | **241** | **5.4** | **0.776** | **0.680** | **0.830** | 0.391 |
| FanDuel | 5,844 | 5.0 | 1.481 | 0.381 | 0.640 | 0.408 |
| DraftKings | 88 | 2.6 | 2.057 | 0.182 | 0.443 | 0.486 |
| BetMGM | 28 | 2.4 | 2.286 | 0.179 | 0.429 | 0.462 |

BetOnline at line 1.5 serves players with mean actual TB of **0.776** — roughly half of FanDuel's 1.481. These are predominantly bottom-of-order and bench-type hitters where getting zero total bases is the *modal outcome* (68% of the time).

DraftKings and BetMGM do the opposite: they post line 1.5 for top-of-order power hitters (avg slot 2.5) where the actual Under rate is only ~44%.

---

## Finding 3: BetOnline's Pricing Is Also Genuinely Flat

Within BetOnline's own population, their implied Over probability barely varies by player quality:

| Batting Order Slot | N | BetOnline Implied P(Over) | Actual P(Under 1.5) | Pricing Gap |
|---:|---:|---:|---:|---:|
| 1 | 25 | 0.425 | 0.640 | 21.5pp |
| 2 | 19 | 0.412 | 0.737 | 14.9pp |
| 5 | 23 | 0.380 | 0.913 | 29.3pp |
| 8 | 35 | 0.397 | 0.943 | 34.6pp |
| 9 | 35 | 0.374 | 0.943 | 31.7pp |

BetOnline uses an implied Over range of only 0.374–0.425 across all batting order slots, while the actual Under rate ranges from 0.640 to 0.943. **BetOnline appears to use near-flat pricing for line 1.5 regardless of the player's actual quality.** This is genuine mispricing — but it's mispricing of the *easy* kind (not differentiating within a weak-hitter pool), and the base rate of the pool does most of the work.

---

## Finding 4: Internal Pricing Gaps by Book

| Book | N | Actual Under Rate | Implied Under Rate | Gap |
|:-----|---:|---:|---:|---:|
| **BetOnline** | **241** | **0.830** | **0.609** | **+22.1pp** |
| FanDuel | 5,844 | 0.640 | 0.592 | +4.8pp |
| DraftKings | 88 | 0.443 | 0.514 | -7.1pp |
| BetMGM | 28 | 0.429 | 0.538 | -10.9pp |

BetOnline's internal gap (22.1pp) is 4.6x larger than FanDuel's (4.8pp). This confirms BetOnline is genuinely less accurate at pricing its 1.5-line props, but the 22pp gap is primarily because they're posting these props for players whose true Under rate is ~83%, not because their odds engine is uniquely broken.

For comparison, FanDuel's 4.8pp gap on a *normal* player population represents the true market-wide Over bias the model can potentially exploit.

---

## Decomposition of the BetOnline "Edge"

| Component | Estimated Contribution |
|:----------|---:|
| Base rate of BetOnline player pool (83% Under vs 64% general) | ~19pp |
| BetOnline flat pricing within pool (doesn't differentiate by player) | ~3pp |
| **Total apparent edge** | **~22pp** |

The model correctly identifies these as high-Under-probability situations (because the players are genuinely weak hitters). But the "edge vs market" comparison is misleading because the market benchmark (implied_over) at BetOnline is set without proper player-level differentiation.

---

## Implications for v1.1 Verdict

### The v1.1 SHADOW CANDIDATE verdict is **DOWNGRADED to INVESTIGATE FURTHER**.

The 91% win rate and +28% ROI at BetOnline were real but misleading:
- The win rate is real because the players genuinely go Under 1.5 at 83%
- The ROI is real because BetOnline's Under odds were beatable on these weak hitters
- But the signal is **not a model edge** — it's a data pipeline artifact

### What's left after removing the selection bias?

The FanDuel signal (N=5,844) is the clean test of the model:
- FanDuel serves a broad player population (avg slot 5.0)
- Actual Under rate: 64.0%
- Implied Under rate: 59.2%
- **Genuine edge: +4.8pp**
- No Under odds available to compute ROI

This 4.8pp edge at FanDuel is consistent across the full population and stable across half-seasons. It represents the real market-wide Over bias that the model captures. However, it is unclear whether 4.8pp of edge survives standard vig on Under TB props.

### Remaining questions

1. If FanDuel begins posting Under TB odds, is 4.8pp enough to generate positive ROI?
2. Can the model's top-confidence cohort (67.5% win rate at top 20%) beat standard vig?
3. Is the BetOnline flat-pricing anomaly exploitable on its own terms (weak hitters where BetOnline sets identical odds for slot 1 vs slot 9)?

---

## Revised Verdict

**INVESTIGATE FURTHER**

The model has genuine discrimination ability (+4.8pp edge on FanDuel's broad population, 0.61 AUC). But the primary evidence for positive ROI (BetOnline) was contaminated by selection bias. The correct next step is:

1. Monitor FanDuel for Under TB odds publication
2. If BetOnline continues flat-pricing, a narrow slot 7-9 strategy may survive — but verify with fresh 2026 data first
3. Do not shadow-deploy until clean ROI evidence exists on a non-biased population

---

## Output Files

| File | Description |
|:-----|:------------|
| `betonline_pricing_diagnostic.md` | This report |
| `betonline_crossbook_matched.parquet` | Cross-book matching attempt (0 matches — documents the zero-overlap finding) |
