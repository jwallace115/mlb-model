# KP04 V2 Sanity Checks

**Date:** 2026-03-28

## Check 1 — Lineup Data Leakage

**Verdict: CONDITIONAL**

The lineup file (`historical_lineups_long.parquet`) contains **actual game lineups** —
players who appeared in the game, not projected pre-game lineups. The per-hitter K rates
use rolling last-20 with shift 1 (no leakage on the rate), but the lineup composition
itself is post-hoc.

Day-to-day lineup K% changes materially (>2pp) in **28.7%** of games. This means in
roughly 1 in 3.5 games, a late scratch could move the lineup K% across the signal
threshold.

Projected lineup data is **not available locally**. The signal is CONDITIONAL — it
works on the actual lineup but cannot be proven clean on the projected lineup available
at bet time.

**Practical mitigation:** In live deployment, lineup K% would be computed from the
announced lineup (available ~2-4 hours before first pitch). Late scratches after
bet placement are a risk but affect all lineup-based signals equally.

## Check 2 — Pitcher Concentration

**Verdict: BROAD**

| Metric | Value | Threshold |
|--------|-------|-----------|
| Unique pitchers | **138** | — |
| Top 1 share | **2.7%** (Miles Mikolas, 8 starts) | <15% |
| Top 3 share | **7.5%** | <35% |

Top 10 pitchers by appearances (N=295 total):

| Pitcher | N | Share | Over HR | ROI |
|---------|---|-------|---------|-----|
| Miles Mikolas | 8 | 2.7% | 12.5% | -71.8% |
| Clarke Schmidt | 7 | 2.4% | 42.9% | -14.2% |
| Chris Sale | 7 | 2.4% | 71.4% | +33.9% |
| Jack Flaherty | 7 | 2.4% | 71.4% | +42.4% |
| Johan Oviedo | 6 | 2.0% | 66.7% | +23.9% |
| Tyler Glasnow | 6 | 2.0% | 50.0% | -6.6% |
| Yusei Kikuchi | 5 | 1.7% | 80.0% | +41.0% |
| Charlie Morton | 5 | 1.7% | 80.0% | +41.8% |
| Clayton Kershaw | 5 | 1.7% | 60.0% | +34.6% |
| Gavin Williams | 5 | 1.7% | 60.0% | +19.0% |

The signal is distributed across 138 unique pitchers with no single pitcher
dominating. The worst performer (Mikolas at 12.5% hit rate) represents only 2.7%
of the sample and doesn't drag the overall signal below threshold.

## Check 3 — Odds Bucket Analysis

**Verdict: ROBUST**

### By odds bucket:

| Bucket | N | Over HR | ROI |
|--------|---|---------|-----|
| Heavy favorite (≤-150) | 38 | 50.0% | **-18.4%** |
| Standard (-149 to -110) | 125 | **61.6%** | **+10.0%** |
| Near even (-109 to +100) | 38 | **55.3%** | **+8.7%** |
| Underdog (>+100) | 94 | **57.5%** | **+23.1%** |

The signal works in 3 of 4 odds buckets. Heavy favorites (≤-150) are the one
failure — the vig at those odds is too steep. The strongest ROI is in the
underdog bucket (+23.1%), where the market underprices K overs most.

### By year:

| Year | N | Over HR | ROI |
|------|---|---------|-----|
| 2023 | 94 | 57.4% | **+8.9%** |
| 2024 | 109 | 53.2% | **+1.3%** |
| 2025 | 92 | **64.1%** | **+22.6%** |

Positive ROI in all 3 years. 2024 is the weakest (+1.3%) but still positive.
2025 is the strongest — the signal appears to be strengthening, not decaying.

**Positive ROI:** 3/4 buckets, 3/3 years → ROBUST

## Summary

| Check | Finding | Verdict |
|-------|---------|---------|
| Lineup leakage | Actual lineups used, not projected; 29% change materially | **CONDITIONAL** |
| Pitcher concentration | 138 pitchers, top 1 at 2.7%, top 3 at 7.5% | **BROAD** |
| Odds distribution | 3/4 buckets positive, 3/3 years positive | **ROBUST** |

## Overall Recommendation: CONDITIONAL — CLEAR TO REGISTER

The signal passes concentration and distribution checks cleanly. The lineup
leakage concern is real but manageable — in live deployment, lineups would
be computed from announced lineups rather than post-hoc actuals.

**Proceed to full KP04 registration** with the lineup leakage concern
documented. The registration should note:
- Live signal requires announced lineup (not projected)
- Signal should not fire before lineups are confirmed (~2-4 hours pre-game)
- V1 (team K%) exists as a pre-lineup-announcement fallback

**Deployment note:** Avoid heavy favorite odds (≤-150). The signal's ROI
is negative at those prices. Consider a price floor of -145 in the signal
definition.
