# Shopping-Edge Robustness Audit
**Run:** 2026-08-28 14:11 UTC  
**Trigger:** ChatGPT cross-AI review, Q1 (stale-quote enrichment).  
**Data:** `nfl/data/cache/odds_snapshots/open_*.json`, NFL totals, 2021-2024.  
**Prices:** real captured American odds. **API calls:** 0.

## Snapshot character

- Game-snapshots usable: **1324**
- Snapshot lead time before game date: median **4.5 days** (min 0.5, max 118.5)
- Books per game: median **13**, range 2-20

## A. Headline, rebuilt

| Metric | Mean | t | N |
|---|---|---|---|
| **P&L per unit (best - E[random book])** | **+2.44%** | 9.19 | 2648 |
| Line improvement (points) | +0.365 | 58.98 | 2648 |

If the P&L t-stat and the line t-stat are both large, the review's 'it's just an order statistic' objection is only partly right: the order statistic is real, but it is being converted into money at real prices.

## B. Book-count strata

| Books in pool | Mean P&L diff | t | N |
|---|---|---|---|
| 2-5 | +3.04% | 4.99 | 616 |
| 6-9 | +3.98% | 3.37 | 240 |
| 10-13 | +1.47% | 3.44 | 508 |
| 14+ | +2.25% | 6.08 | 1284 |

A monotone rise with book count is the order-statistic signature and is EXPECTED. What matters is whether the low-count strata are still positive, because that is closer to a realistic account set.

## C. Consensus-distance exclusion (stale-outlier proxy)

| Max |best - median| allowed | Mean P&L diff | t | N |
|---|---|---|---|
| no limit | +2.44% | 9.19 | 2648 |
| 2.0 pts | +2.54% | 9.67 | 2641 |
| 1.5 pts | +2.46% | 9.58 | 2638 |
| 1.0 pts | +2.44% | 9.53 | 2625 |
| 0.5 pts | +2.21% | 9.21 | 2396 |

**Read this as the review's decisive test.** If the effect collapses as far outliers are removed, the edge lives in quotes least likely to be executable.

## D. Quote-age exclusion (stale-BOOK proxy)

Restricting each game's pool to books whose `last_update` is at or fresher than that game's median: **+1.84%**, t=7.57, N=2212

## E. Which books hold the best number

| Book | Times best | Share |
|---|---|---|
| lowvig | 548 | 20.7% |
| draftkings | 485 | 18.3% |
| fanduel | 316 | 11.9% |
| williamhill_us | 285 | 10.8% |
| wynnbet | 154 | 5.8% |
| bovada | 139 | 5.2% |
| pointsbetus | 99 | 3.7% |
| betmgm | 97 | 3.7% |
| betrivers | 77 | 2.9% |
| gtbets | 65 | 2.5% |
| circasports | 60 | 2.3% |
| mybookieag | 52 | 2.0% |

Top-3 concentration: **50.9%**. High concentration in soft/offshore books is a monetisability problem, not a statistical one.

## Limits of this audit

- One snapshot per week: sub-minute quote persistence is NOT measurable here, and the vendor's finest historical grid is 10 minutes. The review's 5/15/30/60-second test cannot be run on any purchasable history.
- Snapshots are early-week, not at-close. Early week is when dispersion is widest AND when limits are lowest. That cuts against monetisability.
- `hardrockbet_fl` is absent from all 22 books here. This result therefore says nothing about the operator's actual executable account set.