# Hard Rock SGPMax correlation adjustment — MEASURED, 2026-09-19

**Finding: Hard Rock prices each same-game cover+over pair in a blowout at ~0.70 of its
independent value. The joint table says a fair adjustment would be 0.746. You lose ~6.3% of
fair value per pair, compounding.**

This is a real-price measurement from actual Hard Rock bet slips, on the only book Jeff can
bet. It is not a backtest and has no leakage surface — the prices are what they are.

---

## 1. The controlled comparison

Three cards, same book (hardrockbet_fl), same sport, same day, same SGPMax product. The only
variable that moves is whether legs share a game.

| card | legs | same-game pairs | offered | decimal | independent @ -110 | ratio |
|---|---|---|---|---|---|---|
| Cross-game 5-leg | 5 (5 games) | **0** | +2383 | 24.83x | 25.35x (assumed -110) | 0.980 |
| **Cross-game 4-leg** | 4 (4 games) | **0** | **+1201** | **13.010x** | **13.008x (ACTUAL leg prices)** | **1.0001** |
| Morning 5-leg | 5 (3 games) | 2 | +1115 | 12.15x | 25.35x | 0.479 |
| Morning 10-leg | 10 (5 games) | 5 | +15011 (boosted) → ~+10007 base | 101.07x | 642.6x | 0.157 |

The cross-game card is the control. It pays **98%** of the independent product, so Hard Rock
applies essentially NO adjustment when legs come from different games. The 2% shortfall is
single-leg prices not being exactly -110, not a correlation charge.

**CORRECTED 2026-09-19, later slip.** The 4-leg card carried per-leg prices on the slip
(-110, -115, -110, -110). Their product is 13.0083x; Hard Rock offered 13.0100x and paid
$195.12 on $15 — exact to the penny. So the cross-game baseline is **1.000, not 0.98**. The
2% shortfall on the 5-leg card was simply that its legs were not all -110, as suspected.

**Hard Rock applies ZERO adjustment to cross-game parlays: the price is the product of the
single-leg prices.** Therefore everything a same-game card pays BELOW the product of its legs
is pure correlation charge, with nothing else mixed in.

## 2. Per-pair factor

Using the measured 0.98 baseline rather than an assumed one:

    2-pair card:  12.15 / (0.98 x 25.35 = 24.84)  = 0.4892  -> per pair 0.4892^(1/2) = 0.699
    5-pair card: 101.07 / (0.98 x 642.6 = 629.7)  = 0.1605  -> per pair 0.1605^(1/5) = 0.695

**Per-pair factor = 0.70**, from two independent cards with different leg counts, against a
directly measured control. Each pair costs 30% of the payout.

## 3. What it should cost

`joint_outcome_table_v2.parquet`, cell 21+/OU<50 (n=137):

    P(cover & over)  = 0.3796
    independence     = 0.2831
    ratio            = 1.341

If the true joint is 1.341x independence, a fair book pays 1/1.341 = **0.746** of the
independent price for that pair. Hard Rock pays **0.699**.

    0.699 / 0.746 = 0.937  ->  you receive 93.7% of fair value per pair
                           ->  you LOSE 6.3% per pair
    across 5 pairs: 0.937^5 = 0.722  ->  ~28% of fair value surrendered

## 4. The decision this forces

**Never stack cover+over pairs same-game at Hard Rock.** The correlation is real — the table
measures it and it held on 4 of 6 forward pairs tonight — but Hard Rock charges more for it
than it is worth. Taking the same reads as one leg per game in a cross-game parlay incurs no
adjustment at all (measured: 0.98).

This inverts the strategy the joint table originally suggested. The finding survives; the way
to bet it does not.

## 5. Caveats

- ~~The 0.98 baseline assumes...~~ **RESOLVED.** The 4-leg slip carried per-leg prices and the
  cross-game baseline is exactly 1.000. The remaining uncertainty is now on the SAME-GAME side:
  the 5-leg and 10-leg slips did not show per-leg prices, so the 0.70 per-pair factor still
  assumes ~-110 legs there. Capturing per-leg prices on a same-game slip would close it fully.
- The 1.341 true-correlation figure comes from the joint table, whose cell values pool
  discovery (2022-24) and validation (2025) and therefore have no clean OOS estimate. If the
  true correlation is weaker than 1.341, the overpay is LARGER than 6.3%, not smaller.
- Measured on blowout cover+over pairs only. Whether the 0.70 factor is flat across all
  same-game pair types, or specific to this correlation, is unknown and untested.
- The 10-leg carried a 50% Profit Boost; the base price was backed out as
  offered_profit / 1.5. Not independently confirmed against an unboosted slip.

## 6. Provenance

Bet slips, 2026-09-19, hardrockbet_fl:
- 5-leg SGPMax, bet id 2473166698438590742, $15 -> $182.28, +1115, WON
- 4-leg cross-game PARLAY (not SGPMax), $15 -> $195.12, +1201, legs -110/-115/-110/-110
- 10-leg SGPMax, $10, +15011 with 50% Profit Boost, LOST
- Cross-game 5-leg, +2383, quoted pre-bet

All three logged in `ncaaf/logs/ncaaf_board_tickets_2026.json`.


## 7. Side observation — Hard Rock totals vs 9-book consensus

Across two slates, every Hard Rock total quoted has come in BELOW the 9-book consensus, in the
bettor's favour when taking the over:

| game | consensus | Hard Rock |
|---|---|---|
| Akron @ Minnesota | 49.5 | 48.5 |
| Northern Iowa @ Iowa | 49.5 | 48.5 |
| N. Illinois @ Arizona | 50.5 | 49.5 |
| South Dakota @ Boise State | 60.5 | 59.5 |

4 of 4, each exactly 1 point. Too clean and too small a sample to trust — it may be a
systematic offset, a timing artifact (consensus read at a different moment), or coincidence.
It is a testable claim and a direct argument for capturing Hard Rock's board rather than
inferring it. Do NOT act on it before it is measured properly.
