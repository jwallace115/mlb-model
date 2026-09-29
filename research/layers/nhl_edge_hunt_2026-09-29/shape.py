#!/usr/bin/env python3
"""Shape of NHL outcomes vs what prices imply. Descriptive; nothing here is a bet without a real price."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
f = pd.read_csv(HERE.parent / "raw/nhl.csv", low_memory=False)
h = f[(f.home_away == "H") & (f.game_type == "regular") & (f.season >= 2005)].copy()
h["tie60"] = h.decided_in.isin(["OT", "SO"])
h["margin_abs"] = h.margin.abs()
h["era"] = pd.cut(h.season, [2004, 2014, 2019, 2022, 2026], labels=["2005-15 (4v4 OT)", "2015-20 (3v3)", "2020-23", "2023-26"])
G = pd.read_parquet(HERE / "games.parquet")
out = []
out.append("## A. Games tied after 60 minutes (OT or shootout), regular season\n")
out.append(h.groupby("season").agg(n=("tie60", "size"), tie60=("tie60", "mean"), so=("decided_in", lambda s: (s == "SO").mean())).round(3).T.to_string())
g = G[G.p_h.notna()].copy()
g["tie60"] = g.decided.isin(["OT", "SO"])
g["close"] = pd.cut((g.p_h - .5).abs(), [-.01, .05, .10, .15, .5], labels=["|p-.5|<=.05", ".05-.10", ".10-.15", ">.15"])
g["tl_b"] = pd.cut(g.tl, [0, 5.75, 6.25, 6.75, 99], labels=["<=5.5", "6", "6.5", ">=7"])
g["era"] = np.where(g.season < 2015, "2007-15", "2015-23")
out.append("\n\n## B. 60-minute tie rate by closeness of the moneyline x total line (2007-08..2022-23p)\n")
out.append(g.pivot_table(index=["era", "close"], columns="tl_b", values="tie60", aggfunc=["mean", "size"], observed=True).round(3).to_string())
# margins
h2 = h[h.decided_in == "REG"]
out.append("\n\n## C. Regulation wins: share decided by exactly 1 goal / 2 / 3+ (all regular-season games incl. OT as 1-goal)\n")
h["m_bucket"] = np.where(h.decided_in != "REG", "OT/SO (1)", np.where(h.margin_abs == 1, "REG 1", np.where(h.margin_abs == 2, "REG 2", "REG 3+")))
out.append(pd.crosstab(h.season, h.m_bucket, normalize="index").round(3).to_string())
# favourite -1.5 cover by fav prob, by era
g["fav_home"] = g.p_h >= .5
g["fav_p"] = np.maximum(g.p_h, 1 - g.p_h)
g["fav_margin"] = np.where(g.fav_home, g.hg - g.ag, g.ag - g.hg)
g["fav_cover15"] = g.fav_margin >= 2
g["fav_win"] = g.fav_margin > 0
g["fp_b"] = pd.cut(g.fav_p, [.5, .55, .6, .65, .7, 1.0])
g["era3"] = pd.cut(g.season, [2006, 2014, 2019, 2023], labels=["2007-15", "2015-20", "2020-23"])
t = g.groupby(["fp_b", "era3"], observed=True).agg(n=("fav_cover15", "size"), fav_p=("fav_p", "mean"), win=("fav_win", "mean"), cover_m15=("fav_cover15", "mean"))
t["fair_price_m15"] = t.cover_m15.map(lambda p: f"{(100*(1-p)/p):+.0f}" if p < .5 else f"{(-100*p/(1-p)):.0f}")
out.append("\n\n## D. Favourite -1.5 (puck line) cover rate by closing favourite probability and era; fair American price\n")
out.append(t.round(3).to_string())
# P(win by 2+ | win) trend (all games since 2005, both sides)
h["winner_by2"] = h.margin_abs >= 2
out.append("\n\n## E. Share of games won by 2+ goals, by season (empty-net / pulled-goalie trend)\n")
out.append(h.groupby("season").winner_by2.mean().round(3).to_string())
# totals: DK real prices calibration by line and juice side
d = G[G.pover_dk.notna() & G.tl_dk.notna()].copy()
d["y"] = np.where(d.tot > d.tl_dk, 1.0, np.where(d.tot < d.tl_dk, 0.0, np.nan))
d = d[d.y.notna()]
d["juice"] = pd.cut(d.pover_dk, [0, .46, .5, .54, 1], labels=["under fav (>.54 under)", "under .50-.54", "over .50-.54", "over fav (>.54)"])
d["per"] = np.where(d.season <= 2022, "2021-23", "2023-26")
out.append("\n\n## F. Totals with real DraftKings prices: actual over rate vs de-vigged over probability, by line x juice\n")
tf = d.groupby(["tl_dk", "juice", "per"], observed=True).agg(n=("y", "size"), actual_over=("y", "mean"), devig_over=("pover_dk", "mean"))
tf["diff"] = tf.actual_over - tf.devig_over
tf["se"] = np.sqrt(tf.devig_over * (1 - tf.devig_over) / tf.n)
out.append(tf[tf.n >= 30].round(3).to_string())
# goal-count distribution vs Poisson at the same mean
out.append("\n\n## G. Total-goals distribution vs Poisson with the same mean (2015-26 regular season)\n")
hh = h[h.season >= 2015]
mu = hh.total.mean()
from scipy.stats import poisson
emp = hh.total.value_counts(normalize=True).sort_index()
comp = pd.DataFrame({"actual": emp, "poisson": [poisson.pmf(k, mu) for k in emp.index]}).head(13)
out.append(f"mean goals {mu:.3f}, variance {hh.total.var():.3f} (Poisson variance = mean)\n" + comp.round(4).to_string())
Path(HERE / "shape_report.md").write_text("# NHL outcome shape (descriptive)\n\n" + "\n".join(out) + "\n")
print("\n".join(out))
