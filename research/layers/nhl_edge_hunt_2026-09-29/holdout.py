#!/usr/bin/env python3
"""Open the holdout ONCE for discovery->validation survivors (survivors_DV.csv). Real prices only:
moneyline = the side's SBRO closing price; totals = DraftKings closing price (de-vigged for the expectation).
Also prints the survivor's record by season and by OT era. Output: holdout_results.csv"""
import contextlib, io
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
with contextlib.redirect_stdout(io.StringIO()):
    import scan  # rebuilds the identical registry (deterministic); its own outputs are unchanged
G, C = scan.G, scan.C
S = pd.read_csv(HERE / "survivors_DV.csv")


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


rows = []
for r in S.itertuples(index=False):
    parts = r.cell.split(" & ")
    m = np.ones(len(G), bool); side = None
    for p in parts:
        mm, ss, _ = C[p]
        m &= mm
        if ss is not None:
            if side is not None:
                m &= (side == ss)
            side = ss
    side = scan.home if side is None else side
    direction = int(np.sign(r.z_D))            # +1 = bet the condition side / over; -1 = opponent / under
    for sp in ("D", "V", "H"):
        mk = m & np.isin(G.season, list(scan.SPLITS[r.market][sp]))
        if r.market == "tot":
            if sp == "H":
                sub = G[mk & G.tl_dk.notna() & G.op_dk.notna()]
                y = np.where(sub.tot > sub.tl_dk, 1.0, np.where(sub.tot < sub.tl_dk, 0.0, np.nan))
                ok = ~np.isnan(y); y = y[ok]; sub = sub[ok]
                bet_over = direction > 0
                win = y if bet_over else 1 - y
                price = dec(sub.op_dk if bet_over else sub.up_dk)
                pexp = sub.pover_dk if bet_over else 1 - sub.pover_dk
                roi = np.mean(win * (price - 1) - (1 - win))
                be = np.mean(1 / price)
                rows.append({"cell": r.cell, "market": "tot", "split": sp, "bet": "over" if bet_over else "under",
                             "n": len(sub), "win_rate": win.mean(), "devig_expect": float(pexp.mean()),
                             "breakeven_at_price": be, "roi_real_price": roi, "price_source": "DraftKings close"})
                for se, s2 in sub.assign(win=win).groupby("season"):
                    rows.append({"cell": r.cell, "market": "tot", "split": f"H:{se}", "n": len(s2),
                                 "win_rate": s2.win.mean()})
            else:
                sub = G[mk & G.over.notna()]
                win = sub.over if direction > 0 else 1 - sub.over
                rows.append({"cell": r.cell, "market": "tot", "split": sp, "bet": "over" if direction > 0 else "under",
                             "n": len(sub), "win_rate": win.mean(), "breakeven_at_price": 110 / 210,
                             "price_source": "none (line only; -110 triage)"})
                for se, s2 in sub.assign(win=win).groupby("season"):
                    rows.append({"cell": r.cell, "market": "tot", "split": f"{sp}:{se}", "n": len(s2),
                                 "win_rate": s2.win.mean()})
        else:
            sub = G[mk & G.p_h.notna()]
            sh = side[mk & G.p_h.notna().to_numpy()]
            if direction < 0:
                sh = ~sh
            y = np.where(sh, sub.home_win, 1 - sub.home_win)
            p = np.where(sh, sub.p_h, 1 - sub.p_h)
            price = dec(np.where(sh, sub.ml_h, sub.ml_a))
            rows.append({"cell": r.cell, "market": "ml", "split": sp, "bet": "side" if direction > 0 else "opponent",
                         "n": len(sub), "win_rate": y.mean(), "devig_expect": p.mean(),
                         "breakeven_at_price": np.mean(1 / price), "roi_real_price": np.mean(y * (price - 1) - (1 - y)),
                         "price_source": "SBRO closing moneyline"})
out = pd.DataFrame(rows)
out.to_csv(HERE / "holdout_results.csv", index=False)
print(out.to_string())
