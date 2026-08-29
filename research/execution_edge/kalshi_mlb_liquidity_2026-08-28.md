# Kalshi MLB Game-Market Liquidity Audit
**Run:** 2026-08-28 14:58 UTC  
**Source:** `kalshi-edge/data/captures/CAPTURE003` (read-only), 2026-08-15..16.  
**API calls:** 0.

> **This is not the Hard Rock <-> Kalshi test.** That test is blocked: no
> sportsbook lines exist for the capture window because the Odds API key
> lapsed and the daily refresh has written 0-byte logs since. What follows
> is the capacity and cost question, which is answerable now and which
> bounds the whole idea regardless of how big the cross-venue gap turns out to be.

## Sample

- Quote observations: **631,914**  
- Distinct markets: **396** (105 moneyline, 291 totals)  
- Trades observed: **189,602**

## 1. THE HURDLE — cost of transacting

| Market | Median spread | Mean | 25th pct | 75th pct |
|---|---|---|---|---|
| moneyline | **1.00c** | 1.84c | 1.00c | 2.00c |
| total | **2.00c** | 4.78c | 1.00c | 5.00c |

Within 4h of first pitch (N=6,059): median spread **1.00c**, and **95.4%** of quotes are 1 cent wide or tighter.

### Cost of ONE position, held to settlement

Kalshi charges no settlement or exit fee, so the honest comparison is the
cost of entering a single position and holding it, against the cost of
placing one sportsbook bet. Fair value is taken as the mid.

At the median moneyline spread of **1.00c** on a ~50c contract:

| Route | Half-spread | Fee/contract | Net cost | As % of stake |
|---|---|---|---|---|
| Sportsbook -110 | — | — | — | **-4.55%** |
| Kalshi TAKER | -0.50c | -1.75c | -2.25c | **-4.31%** |
| Kalshi MAKER | +0.50c | -0.44c | +0.06c | **+0.13%** |

**Read this carefully, because the obvious reading is wrong.**

Crossing the spread on Kalshi costs **4.31%**, which is *not* materially
better than a sportsbook's 4.55%. The fee eats the tighter spread. This
independently reproduces Program B's own finding that taker economics are
negative at every horizon — arrived at from cost structure rather than from
order-flow outcomes.

Resting an order is where the venue differs: **+0.13%** before adverse
selection — approximately free access rather than a 4.55% headwind. That is
not an edge. It is the *removal of the thing that was killing every edge*.
Any real signal now has somewhere to express itself; a signal worth 1.5%
is profitable as a maker and dead everywhere else.

**And it is break-even, not positive.** The entire question becomes whether
fills arrive disproportionately when the resting quote has gone stale. If
adverse selection costs more than ~0.1c per contract, this is negative.

## 2. THE CEILING — how much can actually be deployed

Dollars resting at the top of book, per market observation:

| Side | Median | Mean | 75th pct | 95th pct |
|---|---|---|---|---|
| Bid | $932 | $11,690 | $8,889 | $61,492 |
| Ask | $978 | $23,979 | $10,237 | $163,094 |

Actually traded, per market, over the window: median **$891**, mean $45,017, 95th pct $253,632, max $1,576,316
Total MLB game-market dollar volume observed: **$16,971,314** across 377 markets

## 3. WHAT $200-500/MONTH REQUIRES

Observed MLB game-market volume runs about **$16,971,314/day** across all markets (1.0 days observed).
- $200/mo = **$6.67/day** of profit. At a 2% net edge that is **$333/day** of turnover — **0.002%** of observed daily volume.
- $500/mo = **$16.67/day** of profit. At a 2% net edge that is **$833/day** of turnover — **0.005%** of observed daily volume.

Whether that share is obtainable depends entirely on adverse selection, which this file does not measure.

## 4. WHAT THIS DOES AND DOES NOT ESTABLISH

**Establishes:** transacting on Kalshi is far cheaper than at a sportsbook, and there is enough volume in MLB game markets that a few hundred dollars a month is not obviously capacity-blocked.

**Does not establish:** that any edge exists. Cheap transacting is a necessary condition, not a sufficient one. A 1c spread you cross randomly still loses money — just more slowly than a sportsbook would take it.

**Still blocked:** the cross-venue gap (needs Odds API `us2` for Hard Rock), and EV-conditional-on-fill (needs the queue-aware replay).