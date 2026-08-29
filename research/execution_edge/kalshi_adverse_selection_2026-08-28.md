# Kalshi Adverse-Selection Test — MLB Game Markets
**Run:** 2026-08-28 15:34 UTC · **API calls:** 0  
**Source:** `kalshi-edge/data/captures/CAPTURE003` (read-only), 2026-08-15..16.

**Decides:** whether resting a limit order is profitable before any signal. 
Maker P&L decomposes as `spread_capture + adverse_selection − fee`, in cents/contract.

Evaluable fills: **186,205** at the 60s horizon (373 markets).

## Headline — unweighted, per contract

| Horizon | Spread capture | Adverse selection | Fee | **NET** | t (net) |
|---|---|---|---|---|---|
| +1s | +1.359c | -0.592c | −0.316c | **+0.451c** | 72.59 |
| +10s | +1.351c | -0.851c | −0.317c | **+0.183c** | 21.25 |
| +60s | +1.349c | -0.955c | −0.318c | **+0.076c** | 5.22 |
| +300s | +1.358c | -0.896c | −0.325c | **+0.137c** | 4.54 |
| +600s | +1.311c | -0.966c | −0.336c | **+0.009c** | 0.23 |

## Size-weighted (what the money actually experiences)

| Horizon | Spread capture | Adverse selection | **NET** | contracts |
|---|---|---|---|---|
| +1s | +0.947c | -0.490c | **+0.142c** | 35,997,345 |
| +10s | +0.945c | -0.809c | **-0.179c** | 35,945,513 |
| +60s | +0.942c | -0.973c | **-0.347c** | 35,717,294 |
| +300s | +0.951c | -0.992c | **-0.366c** | 34,445,421 |
| +600s | +0.939c | -1.264c | **-0.663c** | 31,991,523 |

## NULL CONTROL — same drift at random times, random sides

| Horizon | Random-time drift | t | N | Actual-fill adverse selection |
|---|---|---|---|---|
| +1s | +0.0003c | 0.16 | 189,569 | -0.5918c |
| +10s | -0.0060c | -1.32 | 189,378 | -0.8506c |
| +60s | -0.0184c | -1.82 | 188,312 | -0.9548c |
| +300s | -0.0008c | -0.03 | 183,629 | -0.8962c |
| +600s | -0.0160c | -0.48 | 177,754 | -0.9661c |

If the random-time column is ~0 and the actual-fill column is negative, the effect is adverse selection. If both are negative, it is drift and this test proves nothing.

## Break-even reading — WHICH AVERAGE APPLIES TO YOU

- Unweighted mean fill: **+0.076c** (t=5.22)
- Size-weighted mean fill: **-0.347c**

**The size-weighted number is the one that applies.** A resting order does
not choose its counterparty. Fills arrive in proportion to taker volume, so
a large informed taker sweeping the book takes your small resting order along
with everyone else's at the top of book. You experience the size-weighted
distribution whether or not your own orders are small.

**Naive passive market making is therefore negative: -0.347c per
contract at 60s.** Quoting without a signal loses money — slowly, but it loses.

The useful output is the HURDLE. Any signal must be worth more than
**0.347c per contract** — about **0.69%** on a 50c contract —
before a passive strategy earns anything.

| Route | Edge a signal must exceed |
|---|---|
| Sportsbook at -110 | ~4.55% |
| Kalshi taker | ~4.31% |
| Kalshi maker | **~0.69%** |

That is the whole finding: the venue cuts the required edge by roughly
**7x**. It does not supply an edge. A signal worth 1% is dead
at a sportsbook, dead as a taker, and profitable as a maker.

- $200/mo needs a signal beating the hurdle by enough to net $6.67/day on whatever volume you can passively fill.
- $500/mo needs a signal beating the hurdle by enough to net $16.67/day on whatever volume you can passively fill.

### Where the toxicity comes from

Adverse selection is **-0.592c at 1s** and **-0.955c at 60s** — most of the information arrives
within the first ten seconds. Reacting faster than that is a latency contest
against professional market makers, which is not winnable from a home
connection. Assume you eat the full 60s figure.

## Limits

- Markout is **not settlement**. A fill that looks bad at +600s can still settle profitably. Settlement grading needs game results for 2026-08-15..16.
- No queue model: this measures the P&L of fills that *actually happened*, which is the population a resting order would have joined, not a simulation of your own order's queue position.
- One capture window (~1 day of MLB). Not a season, and not multi-regime.
- Trades are attributed to the maker as the opposite side of `taker_side`. Block trades are not excluded.