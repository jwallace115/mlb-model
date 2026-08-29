#!/usr/bin/env python3
"""
=============================================================================
WITHDRAWN 2026-08-28 -- THIS SCRIPT PRODUCES AN INVALID RESULT. DO NOT RUN.
=============================================================================
Its settlement label was inferred from each market's final observed quote.
A check against the capture's own market_lifecycle_v2 events found that ZERO
of the 140 markets it labelled "settled" had an actual settled event. The
label meant "capture stopped while the price was extreme", not "resolved".

Selecting on that label selects markets with large price moves, and maker P&L
is a direct function of price movement -- outcome-conditioned selection.

Kept only as a record of the error. See kalshi_settlement_grade_2026-08-28.md.
Superseding work must obtain real settlement outcomes, not infer them.
=============================================================================
"""
import sys; sys.exit("WITHDRAWN: invalid settlement inference. See the .md.")

_ORIGINAL = r"""

import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

WORK = Path.home() / "kx_work"
ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "research" / "execution_edge" / "kalshi_settlement_grade_2026-08-28.md"

def maker_fee_c(p): return 0.25 * 0.07 * p * (1 - p) * 100
def tstat(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 3: return np.nan, np.nan, len(x)
    se = x.std(ddof=1) / np.sqrt(len(x))
    return x.mean(), (x.mean() / se if se > 0 else np.nan), len(x)

def main():
    q = pd.read_parquet(WORK / "quotes.parquet")
    d = pd.read_parquet(WORK / "trades.parquet")

    last = q.sort_values("ts_ms").groupby("ticker").tail(1)[["ticker","mid","ts_ms"]]
    last = last.rename(columns={"mid":"final_mid","ts_ms":"final_ts"})
    last["settle"] = np.where(last.final_mid > .95, 1.0,
                       np.where(last.final_mid < .05, 0.0, np.nan))
    resolved = last.dropna(subset=["settle"])

    d = d.merge(resolved, on="ticker", how="inner")
    if d.empty:
        print("HARD STOP: no fills in resolved markets"); sys.exit(1)
    d["sgn"] = np.where(d.taker_side.eq("yes"), 1.0, -1.0)
    d["fee_c"] = maker_fee_c(d.price)
    d["gross_c"] = d.sgn * (d.price - d.settle) * 100
    d["net_c"] = d.gross_c - d.fee_c
    d["mins_before_end"] = (d.final_ts - d.ts_ms) / 60000.0

    L = []; W = L.append
    W("# Kalshi Maker Fills Graded to SETTLEMENT")
    W(f"**Run:** {datetime.utcnow():%Y-%m-%d %H:%M} UTC · **API calls:** 0  ")
    W("**Source:** `kalshi-edge/data/captures/CAPTURE003` (read-only).\n")
    W("Closes the top limitation of the adverse-selection test: markout is not "
      "settlement. Grades passive fills against the actual outcome.\n")
    W(f"- Resolved markets: **{len(resolved)}** of {len(last)} "
      f"({len(resolved)/len(last)*100:.0f}%)")
    W(f"- Fills in resolved markets: **{len(d):,}** "
      f"({d['count'].sum():,.0f} contracts)\n")
    W("> **Selection bias.** Markets resolving inside a ~1-day window are the EARLY "
      "games; later games are censored. Not a random sample.\n")

    W("## Headline\n")
    mu, tu, nu = tstat(d.net_c)
    w = d["count"].to_numpy()
    mw = float(np.average(d.net_c, weights=w))
    W("| Measure | Gross | Fee | **Net** | t | N |")
    W("|---|---|---|---|---|---|")
    W(f"| Unweighted | {d.gross_c.mean():+.3f}c | −{d.fee_c.mean():.3f}c | "
      f"**{mu:+.3f}c** | {tu:.2f} | {nu:,} |")
    W(f"| Size-weighted | {float(np.average(d.gross_c,weights=w)):+.3f}c | "
      f"−{float(np.average(d.fee_c,weights=w)):.3f}c | **{mw:+.3f}c** | — | "
      f"{w.sum():,.0f} ctr |")
    W("")
    W("Size-weighted is the number that applies to a resting order, for the reason "
      "given in the adverse-selection file: fills arrive in proportion to taker volume.\n")

    W("## Versus the markout estimate\n")
    W("| Method | Size-weighted net |")
    W("|---|---|")
    W("| Markout @ +60s (all markets) | −0.347c |")
    W("| Markout @ +600s (all markets) | −0.663c |")
    W(f"| **Settlement (resolved markets only)** | **{mw:+.3f}c** |")
    W("")
    if mw < -0.347:
        W("Settlement is **worse** than the 60s markout implied. Holding to resolution "
          "does not rescue a toxic fill — it compounds it.\n")
    elif mw < 0:
        W("Settlement is negative but **less bad** than the long-horizon markout. Some "
          "of the post-fill drift reverts before resolution.\n")
    else:
        W("Settlement is **positive** despite negative markout. Post-fill drift partly "
          "reverts by resolution, and markout overstates the damage.\n")

    W("## By time before resolution\n")
    W("| Fill timing | Net (size-wtd) | Mean fill price | N |")
    W("|---|---|---|---|")
    for lo, hi, lab in [(0,15,"final 15 min"), (15,60,"15-60 min"),
                        (60,180,"1-3 h"), (180,1e9,"3 h+")]:
        s = d[(d.mins_before_end >= lo) & (d.mins_before_end < hi)]
        if len(s) < 30: continue
        ww = s["count"].to_numpy()
        W(f"| {lab} | {float(np.average(s.net_c,weights=ww)):+.3f}c | "
          f"{s.price.mean():.3f} | {len(s):,} |")
    W("")

    W("## By contract price at fill\n")
    W("| Price bucket | Net (size-wtd) | N |")
    W("|---|---|---|")
    for lo, hi in [(0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.01)]:
        s = d[(d.price >= lo) & (d.price < hi)]
        if len(s) < 30: continue
        ww = s["count"].to_numpy()
        W(f"| {lo:.1f}–{hi:.1f} | {float(np.average(s.net_c,weights=ww)):+.3f}c | {len(s):,} |")
    W("")
    W("Longshot/favourite asymmetry matters: a maker who only quotes near 50c faces "
      "a different distribution than one quoting the tails.\n")

    W("## What this does not settle\n")
    W("- Only early-resolving markets. Late games are censored entirely.")
    W("- Settlement inferred from final quote, not from a settlement-price field.")
    W("- Still no queue model and no fill-probability model.")
    W("- Still measured on general flow, not conditional on any signal firing.")

    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}\n"); print("\n".join(L))

if __name__ == "__main__":
    main()

"""
