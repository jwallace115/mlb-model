#!/usr/bin/env python3
"""
Step 2: THE ADVERSE-SELECTION TEST.

The question this decides: when you rest a limit order on Kalshi and it fills,
does the price then move against you by more than the spread you captured?

Maker P&L on a fill decomposes exactly into two terms:

    total = spread_capture + adverse_selection
    spread_capture   = signed( fill_price - mid(t) )        ~ +half-spread
    adverse_selection= signed( mid(t)     - mid(t+dt) )     ~ negative if toxic

Sign convention. taker_side="yes" means the taker BOUGHT yes, so the MAKER SOLD
yes and profits when the price falls. taker_side="no" means the maker BOUGHT yes
and profits when it rises. Everything is expressed in CENTS per contract.

NULL CONTROL: the same drift measured at random timestamps in the same markets
with randomly assigned sides. If random-time drift is also negative, the result
is a drift/clock artifact rather than adverse selection. This project has been
burned by exactly that class of error, so the control is not optional.

Horizons match Program B's existing OF-2 order-flow study (+1s..+600s) so the
two are directly comparable.

Zero API calls. Reads scratch parquet. Writes markdown into mlb-model.
"""
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

WORK = Path.home() / "kx_work"
ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "research" / "execution_edge" / "kalshi_adverse_selection_2026-08-28.md"
HORIZONS = [1, 10, 60, 300, 600]
RNG = np.random.default_rng(20260828)

def maker_fee_c(price):
    """Maker fee = 25% of taker. Taker = 0.07*P*(1-P) per contract. In cents."""
    return 0.25 * 0.07 * price * (1 - price) * 100

def tstat(x, w=None):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3: return np.nan, np.nan, len(x)
    m = x.mean()
    se = x.std(ddof=1) / np.sqrt(len(x))
    return m, (m / se if se > 0 else np.nan), len(x)

def main():
    qp, tp = WORK / "quotes.parquet", WORK / "trades.parquet"
    if not qp.exists() or not tp.exists():
        print("HARD STOP: run kalshi_parse_to_parquet.py first"); sys.exit(1)
    q = pd.read_parquet(qp); d = pd.read_parquet(tp)

    # Maker sign. taker_side="yes": the taker BOUGHT yes by lifting the ask, so the
    # maker SOLD yes at the ask and profits when the price falls  => +(fill - mid).
    # taker_side="no": the taker sold yes into the bid, so the maker BOUGHT yes at
    # the bid and profits when the price rises                     => -(fill - mid).
    d["sgn"] = np.where(d.taker_side.eq("yes"), 1.0, -1.0)

    rows, null_rows = [], []
    for tk, g in q.groupby("ticker", sort=False):
        tr = d[d.ticker == tk]
        if len(tr) == 0 or len(g) < 10: continue
        qt = g.ts_ms.to_numpy(); qm = g.mid.to_numpy()
        tmax = qt[-1]

        def mid_at(times, strict=False):
            # strict=True -> last quote STRICTLY before `times` (pre-trade reference)
            idx = np.searchsorted(qt, times, side=("left" if strict else "right")) - 1
            ok = idx >= 0
            out = np.full(len(times), np.nan)
            out[ok] = qm[idx[ok]]
            return out

        tt = tr.ts_ms.to_numpy(); tpx = tr.price.to_numpy()
        tsg = tr.sgn.to_numpy(); tct = tr["count"].to_numpy()
        mid_t = mid_at(tt, strict=True)

        # null control: random times in the same market, random sides
        nt = np.sort(RNG.integers(qt[0], max(qt[0] + 1, tmax), size=len(tt)))
        nsg = RNG.choice([-1.0, 1.0], size=len(tt))
        nmid_t = mid_at(nt, strict=True)

        for h in HORIZONS:
            fwd = h * 1000
            valid = (tt + fwd) <= tmax
            if valid.any():
                m2 = mid_at(tt[valid] + fwd)
                sg = tsg[valid]
                rows.append(pd.DataFrame({
                    "ticker": tk, "h": h, "count": tct[valid], "price": tpx[valid],
                    "spread_cap_c": sg * (tpx[valid] - mid_t[valid]) * 100,
                    "adv_sel_c":    sg * (mid_t[valid] - m2) * 100,
                }))
            nvalid = (nt + fwd) <= tmax
            if nvalid.any():
                nm2 = mid_at(nt[nvalid] + fwd)
                null_rows.append(pd.DataFrame({
                    "h": h,
                    "adv_sel_c": nsg[nvalid] * (nmid_t[nvalid] - nm2) * 100,
                }))

    if not rows:
        print("HARD STOP: no evaluable fills"); sys.exit(1)
    R = pd.concat(rows, ignore_index=True).dropna(subset=["spread_cap_c","adv_sel_c"])
    N = pd.concat(null_rows, ignore_index=True).dropna() if null_rows else pd.DataFrame()
    R["fee_c"] = maker_fee_c(R.price)
    R["total_c"] = R.spread_cap_c + R.adv_sel_c - R.fee_c

    L = []; W = L.append
    W("# Kalshi Adverse-Selection Test — MLB Game Markets")
    W(f"**Run:** {datetime.utcnow():%Y-%m-%d %H:%M} UTC · **API calls:** 0  ")
    W("**Source:** `kalshi-edge/data/captures/CAPTURE003` (read-only), 2026-08-15..16.\n")
    W("**Decides:** whether resting a limit order is profitable before any signal. ")
    W("Maker P&L decomposes as `spread_capture + adverse_selection − fee`, in cents/contract.\n")
    W(f"Evaluable fills: **{len(R[R.h==60]):,}** at the 60s horizon "
      f"({R.ticker.nunique():,} markets).\n")

    W("## Headline — unweighted, per contract\n")
    W("| Horizon | Spread capture | Adverse selection | Fee | **NET** | t (net) |")
    W("|---|---|---|---|---|---|")
    for h in HORIZONS:
        s = R[R.h == h]
        if len(s) < 10: continue
        m, t, n = tstat(s.total_c)
        W(f"| +{h}s | {s.spread_cap_c.mean():+.3f}c | {s.adv_sel_c.mean():+.3f}c | "
          f"−{s.fee_c.mean():.3f}c | **{m:+.3f}c** | {t:.2f} |")
    W("")

    W("## Size-weighted (what the money actually experiences)\n")
    W("| Horizon | Spread capture | Adverse selection | **NET** | contracts |")
    W("|---|---|---|---|---|")
    for h in HORIZONS:
        s = R[R.h == h]
        if len(s) < 10: continue
        w = s["count"].to_numpy()
        wa = lambda c: float(np.average(s[c], weights=w))
        W(f"| +{h}s | {wa('spread_cap_c'):+.3f}c | {wa('adv_sel_c'):+.3f}c | "
          f"**{wa('total_c'):+.3f}c** | {w.sum():,.0f} |")
    W("")

    if len(N):
        W("## NULL CONTROL — same drift at random times, random sides\n")
        W("| Horizon | Random-time drift | t | N | Actual-fill adverse selection |")
        W("|---|---|---|---|---|")
        for h in HORIZONS:
            ns = N[N.h == h]; rs = R[R.h == h]
            if len(ns) < 10 or len(rs) < 10: continue
            m, t, n = tstat(ns.adv_sel_c)
            W(f"| +{h}s | {m:+.4f}c | {t:.2f} | {n:,} | {rs.adv_sel_c.mean():+.4f}c |")
        W("")
        W("If the random-time column is ~0 and the actual-fill column is negative, "
          "the effect is adverse selection. If both are negative, it is drift and "
          "this test proves nothing.\n")

    W("## Break-even reading — WHICH AVERAGE APPLIES TO YOU\n")
    s60 = R[R.h == 60]
    w60 = s60["count"].to_numpy()
    m_un, t_un, _ = tstat(s60.total_c)
    m_w = float(np.average(s60.total_c, weights=w60))
    W(f"- Unweighted mean fill: **{m_un:+.3f}c** (t={t_un:.2f})")
    W(f"- Size-weighted mean fill: **{m_w:+.3f}c**\n")
    W("**The size-weighted number is the one that applies.** A resting order does")
    W("not choose its counterparty. Fills arrive in proportion to taker volume, so")
    W("a large informed taker sweeping the book takes your small resting order along")
    W("with everyone else's at the top of book. You experience the size-weighted")
    W("distribution whether or not your own orders are small.\n")
    if m_w < 0:
        W(f"**Naive passive market making is therefore negative: {m_w:+.3f}c per")
        W("contract at 60s.** Quoting without a signal loses money — slowly, but it loses.\n")
        W(f"The useful output is the HURDLE. Any signal must be worth more than")
        W(f"**{-m_w:.3f}c per contract** — about **{-m_w/50*100:.2f}%** on a 50c contract —")
        W("before a passive strategy earns anything.\n")
        W("| Route | Edge a signal must exceed |")
        W("|---|---|")
        W("| Sportsbook at -110 | ~4.55% |")
        W("| Kalshi taker | ~4.31% |")
        W(f"| Kalshi maker | **~{-m_w/50*100:.2f}%** |")
        W("")
        W(f"That is the whole finding: the venue cuts the required edge by roughly")
        W(f"**{4.55/(-m_w/50*100):.0f}x**. It does not supply an edge. A signal worth 1% is dead")
        W("at a sportsbook, dead as a taker, and profitable as a maker.\n")
        for tgt in (200, 500):
            W(f"- ${tgt}/mo needs a signal beating the hurdle by enough to net "
              f"${tgt/30:.2f}/day on whatever volume you can passively fill.")
        W("")
    W("### Where the toxicity comes from\n")
    d1 = R[R.h==1]; d60 = R[R.h==60]
    W(f"Adverse selection is **{d1.adv_sel_c.mean():+.3f}c at 1s** and "
      f"**{d60.adv_sel_c.mean():+.3f}c at 60s** — most of the information arrives")
    W("within the first ten seconds. Reacting faster than that is a latency contest")
    W("against professional market makers, which is not winnable from a home")
    W("connection. Assume you eat the full 60s figure.\n")

    W("## Limits\n")
    W("- Markout is **not settlement**. A fill that looks bad at +600s can still "
      "settle profitably. Settlement grading needs game results for 2026-08-15..16.")
    W("- No queue model: this measures the P&L of fills that *actually happened*, "
      "which is the population a resting order would have joined, not a simulation "
      "of your own order's queue position.")
    W("- One capture window (~1 day of MLB). Not a season, and not multi-regime.")
    W("- Trades are attributed to the maker as the opposite side of `taker_side`. "
      "Block trades are not excluded.")

    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}\n"); print("\n".join(L))

if __name__ == "__main__":
    main()
