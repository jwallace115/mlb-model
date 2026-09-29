#!/usr/bin/env python3
"""Market-level baselines by season/era at real SBRO closing moneylines (context for the null result)."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
G = pd.read_parquet(HERE / "games.parquet"); G = G[G.p_h.notna()].copy()
dec = lambda a: np.where(a > 0, a / 100 + 1, 100 / -a + 1)
G["dh"], G["da"] = dec(G.ml_h), dec(G.ml_a)
G["fav_home"] = G.p_h >= .5
G["fav_win"] = np.where(G.fav_home, G.home_win, 1 - G.home_win)
G["fav_dec"] = np.where(G.fav_home, G.dh, G.da); G["dog_dec"] = np.where(G.fav_home, G.da, G.dh)
G["fav_ret"] = np.where(G.fav_win == 1, G.fav_dec - 1, -1); G["dog_ret"] = np.where(G.fav_win == 0, G.dog_dec - 1, -1)
G["home_ret"] = np.where(G.home_win == 1, G.dh - 1, -1)
G["big_dog"] = G.dog_dec >= 3.0
G["era"] = pd.cut(G.season, [2006, 2014, 2019, 2023], labels=["2007-15 (4v4 OT)", "2015-20 (3v3 OT)", "2020-23"])
def agg(s):
    b = s[s.big_dog]
    return pd.Series({"games": len(s), "home_win": s.home_win.mean(), "home_p": s.p_h.mean(), "ROI_home": s.home_ret.mean(),
                      "ROI_fav": s.fav_ret.mean(), "ROI_dog": s.dog_ret.mean(), "n_dog+200": len(b),
                      "ROI_dog+200": b.dog_ret.mean() if len(b) else np.nan, "hold": s.overround.mean() - 1})
t = pd.concat([G.groupby("era", observed=True).apply(agg), G.groupby("season").apply(agg)])
(HERE / "era_table.md").write_text("# Moneyline baselines at SBRO closing prices (regular season)\n\n" + t.round(3).to_markdown() + "\n")
print(t.round(3).to_string())
