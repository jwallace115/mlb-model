# WITHDRAWN — Kalshi Settlement Grading (2026-08-28)

**Status: INVALID. Do not cite. Do not build on.**

This file previously reported that maker fills graded to settlement were
**+0.494c per contract size-weighted**, apparently reversing the negative
markout result. That number is withdrawn. It was wrong.

## Why it failed

The analysis inferred settlement from each market's final observed quote:
mid > 0.95 was read as "settled YES", mid < 0.05 as "settled NO". A direct
check against the capture's own `market_lifecycle_v2` events found:

    markets labelled "settled" by the price rule ........ 140
    of those with an explicit `settled` lifecycle event ... 0

**Zero.** The label had no corroboration at all. What was actually measured was
"the last price seen before the capture stopped", not resolution.

## Why that breaks the result

Selecting markets whose final observed price is extreme selects markets that
experienced a **large price move during the window**. Maker P&L is a direct
function of price movement, so the sample was selected on a quantity mechanically
correlated with the outcome being measured. That is outcome-conditioned selection,
and it invalidates the estimate regardless of sample size.

## The tell that caught it

The result failed an internal coherence check before any of the above was known:

| Fill timing | Reported net |
|---|---|
| final 15 min | −1.286c |
| 15–60 min | −1.080c |
| 1–3 h | **+3.636c** |
| 3 h+ | **−22.697c** |

A +3.6c bucket sitting between two negative buckets, next to a −22.7c bucket, is
not a pattern. Price-bucket results flipped sign incoherently too (+2.5c at
0.2–0.4 against −5.6c at 0.6–0.8). The aggregate was driven almost entirely by
the one anomalous bucket.

## What is unaffected

The adverse-selection result stands. It is a different measurement on a different
basis, it used **all** markets with no outcome-conditioned selection, and its null
control passed (random-time drift +0.0003c to −0.018c, all |t| < 1.9):

    size-weighted maker net, +60s markout ......... −0.347c/contract
    size-weighted maker net, +600s markout ........ −0.663c/contract

## What remains OPEN

The original limitation is still open and is now explicitly unresolved: **markout
is not settlement.** Closing it requires true settlement outcomes, which this
capture does not contain for MLB game markets. The route is actual MLB game
results for 2026-08-15..16 joined to tickers by the embedded date/time/team code
(e.g. `KXMLBGAME-26AUG151610WSHNYM-NYM`). The repo's own MLB results data ends in
2025, so this needs an external source.

Until that is done, no claim may be made that holding to settlement rescues a
negative markout.
