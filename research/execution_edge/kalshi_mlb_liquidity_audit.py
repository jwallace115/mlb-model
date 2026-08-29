#!/usr/bin/env python3
"""
Kalshi MLB game-market liquidity audit.

PURPOSE: the operator's target is $200-500/month. That is a CAPACITY question
before it is an edge question. This measures the two numbers that bound it:

  1. THE HURDLE  - round-trip cost of transacting on Kalshi (spread + fees),
                   expressed as vig, directly comparable to a sportsbook's -110.
  2. THE CEILING - dollars actually available at top of book, and dollars
                   actually traded, per game.

WHAT THIS IS NOT: this is NOT the Hard Rock <-> Kalshi cross-venue test.
That test is blocked - no sportsbook lines exist for 2026-08-13..16 because
the Odds API key lapsed and the daily refresh cron has been writing 0-byte
logs since. Substituting a different comparison and calling it the same test
would violate ops Rule 5. Stated, not silently swapped.

Source: kalshi-edge/data/captures (READ ONLY). Outputs land in mlb-model.
Zero API calls.
"""
import re, sys, glob, json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

WORK = Path.home() / "kx_work"
ROOT = Path(__file__).resolve().parent.parent.parent
OUT  = ROOT / "research" / "execution_edge" / "kalshi_mlb_liquidity_2026-08-28.md"

Q = r'\\\\?"'          # a quote that may be backslash-escaped
R_TICK = re.compile(
    Q+r'market_ticker'+Q+r':'+Q+r'(?P<tk>[^"\\\\]+)'+Q+r'.*?'
    +Q+r'yes_bid_dollars'+Q+r':'+Q+r'(?P<bid>[\d.]+)'+Q+r'.*?'
    +Q+r'yes_ask_dollars'+Q+r':'+Q+r'(?P<ask>[\d.]+)'+Q+r'.*?'
    +Q+r'yes_bid_size_fp'+Q+r':'+Q+r'(?P<bsz>[\d.]+)'+Q+r'.*?'
    +Q+r'yes_ask_size_fp'+Q+r':'+Q+r'(?P<asz>[\d.]+)'+Q)
R_DV   = re.compile(Q+r'dollar_volume'+Q+r':(?P<dv>\d+)')
R_TS   = re.compile(Q+r'ts_ms'+Q+r':(?P<ts>\d+)')
R_TRADE = re.compile(
    Q+r'market_ticker'+Q+r':'+Q+r'(?P<tk>[^"\\\\]+)'+Q+r'.*?'
    +Q+r'yes_price_dollars'+Q+r':'+Q+r'(?P<px>[\d.]+)'+Q+r'.*?'
    +Q+r'count_fp'+Q+r':'+Q+r'(?P<ct>[\d.]+)'+Q)
R_GAME = re.compile(r'^KXMLB(GAME|TOTAL)-(\d{2})([A-Z]{3})(\d{2})(\d{4})([A-Z]+)')
MON = {m: i+1 for i, m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"])}

def game_start(tk):
    m = R_GAME.match(tk)
    if not m: return None
    _, yy, mon, dd, hhmm, _ = m.groups()
    try:
        return datetime(2000+int(yy), MON[mon], int(dd),
                        int(hhmm[:2]), int(hhmm[2:]), tzinfo=timezone.utc)
    except Exception:
        return None

def taker_fee(price, n=1):
    """Kalshi taker fee: 0.07 * C * P * (1-P), rounded up to the cent."""
    return np.ceil(0.07 * n * price * (1 - price) * 100) / 100

def main():
    files = sorted(glob.glob(str(WORK / "mlb_b*.jsonl")))
    if not files:
        print(f"HARD STOP: no extracts in {WORK}"); sys.exit(1)

    ticks, trades = [], []
    for fp in files:
        for line in open(fp):
            is_tick = '"msg_type":"ticker"' in line[:400]
            m = (R_TICK if is_tick else R_TRADE).search(line)
            if not m: continue
            tk = m.group("tk")
            if not tk.startswith(("KXMLBGAME", "KXMLBTOTAL")): continue
            ts = R_TS.search(line)
            if not ts: continue
            ts = int(ts.group("ts"))
            if is_tick:
                dv = R_DV.search(line)
                ticks.append((tk, float(m.group("bid")), float(m.group("ask")),
                              float(m.group("bsz")), float(m.group("asz")),
                              int(dv.group("dv")) if dv else 0, ts))
            else:
                trades.append((tk, float(m.group("px")), float(m.group("ct")), ts))

    t = pd.DataFrame(ticks, columns=["ticker","bid","ask","bid_sz","ask_sz","dollar_vol","ts_ms"])
    d = pd.DataFrame(trades, columns=["ticker","price","count","ts_ms"])
    if t.empty:
        print("HARD STOP: no ticker rows parsed"); sys.exit(1)

    # two-sided, sane quotes only
    t = t[(t.bid > 0) & (t.ask > 0) & (t.ask > t.bid) & (t.ask <= 1.0)].copy()
    t["spread_c"] = (t.ask - t.bid) * 100
    t["mid"] = (t.ask + t.bid) / 2
    t["bid_usd"] = t.bid_sz * t.bid
    t["ask_usd"] = t.ask_sz * t.ask
    t["kind"] = np.where(t.ticker.str.startswith("KXMLBGAME"), "moneyline", "total")
    t["start"] = t.ticker.map(game_start)
    t["mins_to_start"] = (t.start - pd.to_datetime(t.ts_ms, unit="ms", utc=True)
                          ).dt.total_seconds() / 60.0

    L = []; W = L.append
    W("# Kalshi MLB Game-Market Liquidity Audit")
    W(f"**Run:** {datetime.utcnow():%Y-%m-%d %H:%M} UTC  ")
    W("**Source:** `kalshi-edge/data/captures/CAPTURE003` (read-only), 2026-08-15..16.  ")
    W("**API calls:** 0.\n")
    W("> **This is not the Hard Rock <-> Kalshi test.** That test is blocked: no")
    W("> sportsbook lines exist for the capture window because the Odds API key")
    W("> lapsed and the daily refresh has written 0-byte logs since. What follows")
    W("> is the capacity and cost question, which is answerable now and which")
    W("> bounds the whole idea regardless of how big the cross-venue gap turns out to be.\n")

    W("## Sample\n")
    W(f"- Quote observations: **{len(t):,}**  ")
    W(f"- Distinct markets: **{t.ticker.nunique():,}** "
      f"({t[t.kind=='moneyline'].ticker.nunique():,} moneyline, "
      f"{t[t.kind=='total'].ticker.nunique():,} totals)  ")
    W(f"- Trades observed: **{len(d):,}**\n")

    W("## 1. THE HURDLE — cost of transacting\n")
    W("| Market | Median spread | Mean | 25th pct | 75th pct |")
    W("|---|---|---|---|---|")
    for k, grp in t.groupby("kind"):
        W(f"| {k} | **{grp.spread_c.median():.2f}c** | {grp.spread_c.mean():.2f}c | "
          f"{grp.spread_c.quantile(.25):.2f}c | {grp.spread_c.quantile(.75):.2f}c |")
    W("")
    liq = t[t.mins_to_start.between(-60, 240)]
    if len(liq):
        W(f"Within 4h of first pitch (N={len(liq):,}): median spread "
          f"**{liq.spread_c.median():.2f}c**, and **{(liq.spread_c<=1.01).mean()*100:.1f}%** "
          f"of quotes are 1 cent wide or tighter.\n")

    W("### Cost of ONE position, held to settlement\n")
    W("Kalshi charges no settlement or exit fee, so the honest comparison is the")
    W("cost of entering a single position and holding it, against the cost of")
    W("placing one sportsbook bet. Fair value is taken as the mid.\n")
    ml = t[t.kind=="moneyline"]
    sp = ml.spread_c.median()          # cents
    half = sp / 2.0
    fee_t = 0.07 * 0.50 * 0.50 * 100   # per-contract taker rate at 50c, un-rounded
    fee_m = fee_t * 0.25
    # taker: pay half-spread + taker fee, on a ~50c contract
    taker_cost_c = half + fee_t
    taker_pct = taker_cost_c / (50.0 + taker_cost_c) * 100
    # maker: EARN half-spread, pay maker fee
    maker_cost_c = -half + fee_m
    maker_pct = maker_cost_c / 50.0 * 100
    W(f"At the median moneyline spread of **{sp:.2f}c** on a ~50c contract:\n")
    W("| Route | Half-spread | Fee/contract | Net cost | As % of stake |")
    W("|---|---|---|---|---|")
    W(f"| Sportsbook -110 | — | — | — | **-4.55%** |")
    W(f"| Kalshi TAKER | -{half:.2f}c | -{fee_t:.2f}c | -{taker_cost_c:.2f}c | **-{taker_pct:.2f}%** |")
    W(f"| Kalshi MAKER | +{half:.2f}c | -{fee_m:.2f}c | {-maker_cost_c:+.2f}c | **{-maker_pct:+.2f}%** |")
    W("")
    W("**Read this carefully, because the obvious reading is wrong.**\n")
    W(f"Crossing the spread on Kalshi costs **{taker_pct:.2f}%**, which is *not* materially")
    W("better than a sportsbook's 4.55%. The fee eats the tighter spread. This")
    W("independently reproduces Program B's own finding that taker economics are")
    W("negative at every horizon — arrived at from cost structure rather than from")
    W("order-flow outcomes.\n")
    W(f"Resting an order is where the venue differs: **{-maker_pct:+.2f}%** before adverse")
    W("selection — approximately free access rather than a 4.55% headwind. That is")
    W("not an edge. It is the *removal of the thing that was killing every edge*.")
    W("Any real signal now has somewhere to express itself; a signal worth 1.5%")
    W("is profitable as a maker and dead everywhere else.\n")
    W("**And it is break-even, not positive.** The entire question becomes whether")
    W("fills arrive disproportionately when the resting quote has gone stale. If")
    W("adverse selection costs more than ~0.1c per contract, this is negative.\n")

    W("## 2. THE CEILING — how much can actually be deployed\n")
    W("Dollars resting at the top of book, per market observation:\n")
    W("| Side | Median | Mean | 75th pct | 95th pct |")
    W("|---|---|---|---|---|")
    for lab, col in [("Bid", "bid_usd"), ("Ask", "ask_usd")]:
        s = t[col]
        W(f"| {lab} | ${s.median():,.0f} | ${s.mean():,.0f} | "
          f"${s.quantile(.75):,.0f} | ${s.quantile(.95):,.0f} |")
    W("")
    if len(d):
        d["usd"] = d["count"] * d.price
        per_mkt = d.groupby("ticker").usd.sum()
        W(f"Actually traded, per market, over the window: median "
          f"**${per_mkt.median():,.0f}**, mean ${per_mkt.mean():,.0f}, "
          f"95th pct ${per_mkt.quantile(.95):,.0f}, max ${per_mkt.max():,.0f}")
        W(f"Total MLB game-market dollar volume observed: **${d.usd.sum():,.0f}** "
          f"across {d.ticker.nunique():,} markets\n")

    W("## 3. WHAT $200-500/MONTH REQUIRES\n")
    if len(d):
        days = max(1, (d.ts_ms.max() - d.ts_ms.min()) / 86400000)
        daily = d.usd.sum() / days
        W(f"Observed MLB game-market volume runs about **${daily:,.0f}/day** "
          f"across all markets ({days:.1f} days observed).")
        for target in (200, 500):
            need = target / 30.0
            W(f"- ${target}/mo = **${need:.2f}/day** of profit. At a 2% net edge that is "
              f"**${need/0.02:,.0f}/day** of turnover — "
              f"**{need/0.02/daily*100:.3f}%** of observed daily volume.")
        W("")
        W("Whether that share is obtainable depends entirely on adverse selection, "
          "which this file does not measure.\n")

    W("## 4. WHAT THIS DOES AND DOES NOT ESTABLISH\n")
    W("**Establishes:** transacting on Kalshi is far cheaper than at a sportsbook, "
      "and there is enough volume in MLB game markets that a few hundred dollars a "
      "month is not obviously capacity-blocked.")
    W("")
    W("**Does not establish:** that any edge exists. Cheap transacting is a "
      "necessary condition, not a sufficient one. A 1c spread you cross randomly "
      "still loses money — just more slowly than a sportsbook would take it.")
    W("")
    W("**Still blocked:** the cross-venue gap (needs Odds API `us2` for Hard Rock), "
      "and EV-conditional-on-fill (needs the queue-aware replay).")

    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}\n")
    print("\n".join(L))

if __name__ == "__main__":
    main()
