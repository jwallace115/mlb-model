#!/usr/bin/env python3
"""Step 1 of the adverse-selection test: parse extracted Kalshi MLB messages
to two parquet tables. Split from the analysis so neither step exceeds the
shell timeout. Zero API calls. Reads scratch extracts, writes scratch parquet."""
import re, glob, sys
from pathlib import Path
import pandas as pd

WORK = Path.home() / "kx_work"
Q = r'\\?"'
R_TK  = re.compile(Q+r'market_ticker'+Q+r':'+Q+r'([^"\\]+)'+Q)
R_TS  = re.compile(Q+r'ts_ms'+Q+r':(\d+)')
R_BID = re.compile(Q+r'yes_bid_dollars'+Q+r':'+Q+r'([\d.]+)'+Q)
R_ASK = re.compile(Q+r'yes_ask_dollars'+Q+r':'+Q+r'([\d.]+)'+Q)
R_PX  = re.compile(Q+r'yes_price_dollars'+Q+r':'+Q+r'([\d.]+)'+Q)
R_CT  = re.compile(Q+r'count_fp'+Q+r':'+Q+r'([\d.]+)'+Q)
R_SD  = re.compile(Q+r'taker_side'+Q+r':'+Q+r'([a-z]+)'+Q)

def main():
    quotes, trades = [], []
    for f in sorted(glob.glob(str(WORK / "mlb_b*.jsonl"))):
        for l in open(f):
            m = R_TK.search(l)
            if not m: continue
            tk = m.group(1)
            if not tk.startswith(("KXMLBGAME", "KXMLBTOTAL")): continue
            ts = R_TS.search(l)
            if not ts: continue
            ts = int(ts.group(1))
            head = l[:400]
            if '"msg_type":"ticker"' in head:
                b, a = R_BID.search(l), R_ASK.search(l)
                if not (b and a): continue
                b, a = float(b.group(1)), float(a.group(1))
                if not (0 < b < a <= 1.0): continue
                quotes.append((tk, ts, b, a))
            elif '"msg_type":"trade"' in head:
                p, c, s = R_PX.search(l), R_CT.search(l), R_SD.search(l)
                if not (p and c and s): continue
                trades.append((tk, ts, float(p.group(1)), float(c.group(1)), s.group(1)))

    q = pd.DataFrame(quotes, columns=["ticker","ts_ms","bid","ask"])
    d = pd.DataFrame(trades, columns=["ticker","ts_ms","price","count","taker_side"])
    if q.empty or d.empty:
        print("HARD STOP: empty parse"); sys.exit(1)
    q["mid"] = (q.bid + q.ask) / 2
    q = q.sort_values(["ticker","ts_ms"]).reset_index(drop=True)
    d = d.sort_values(["ticker","ts_ms"]).reset_index(drop=True)
    q.to_parquet(WORK / "quotes.parquet", index=False)
    d.to_parquet(WORK / "trades.parquet", index=False)
    print(f"quotes {len(q):,} across {q.ticker.nunique():,} markets")
    print(f"trades {len(d):,} across {d.ticker.nunique():,} markets")
    print(f"taker_side: {d.taker_side.value_counts().to_dict()}")

if __name__ == "__main__":
    main()
