#!/usr/bin/env python3
"""S48-ML-R6 CONFIRMATION, one run, 2024-25. Rule frozen from s48_complete.py (Cowork, S-WO4d verification).
Engine = committed swapped-goalie engine priced on the Mac (prices_2024_swapped_engine.parquet)."""
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import norm

H = "/home/claude/hunt"
PR = "/mnt/user-data/uploads/mlb-model/logs/cowork_stage/prices2024/prices_2024_swapped_engine.parquet"
GL = f"{H}/research/nhl_sim/edge_hunt_2026-09-30/games_lines.parquet"
LA = f"{H}/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet"
GR = f"{H}/nhl/data/sim/ratings/goalie_ratings.parquet"
SEASON = 2024
lg = lambda p: np.log(p / (1 - p))


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


def a1(y, pe, pp):
    pe = np.clip(pe, 1e-3, 1 - 1e-3); pp = np.clip(pp, 1e-3, 1 - 1e-3)
    X = sm.add_constant(np.column_stack([lg(pp), lg(pe) - lg(pp)]))
    f = sm.Logit(y, X).fit(disp=0)
    b, se = f.params[2], f.bse[2]
    return b, b - 1.6449 * se, b + 1.6449 * se, 1 - norm.cdf(b / se)


def early_pinnacle(G):
    d = pd.read_parquet(LA)
    d = d[d.event_id.isin(G.event_id) & (d.market == "h2h")].copy()
    d["snap"] = pd.to_datetime(d.snapshot_utc); d["ct"] = pd.to_datetime(d.commence_time)
    d["lead_h"] = (d.ct - d.snap).dt.total_seconds() / 3600
    d = d[d.lead_h >= 12]
    pin = d[d.bookmaker == "pinnacle"]
    first = pin.groupby("event_id").snap.min().rename("snap_e")
    d = d.merge(first, on="event_id"); d = d[d.snap == d.snap_e]; d["dec"] = dec(d.price)
    rows = []
    for e, g in d.groupby("event_id"):
        home, away = g.home_team.iloc[0], g.away_team.iloc[0]
        p = g[g.bookmaker == "pinnacle"]
        hp, ap = p[p.outcome_name == home].price, p[p.outcome_name == away].price
        if len(hp) != 1 or len(ap) != 1:
            continue
        ih, ia = 1 / dec(hp.iloc[0]), 1 / dec(ap.iloc[0])
        rows.append(dict(event_id=e, p_early=float(ih / (ih + ia)), med_dec_h_e=g[g.outcome_name == home].dec.median(),
                         med_dec_a_e=g[g.outcome_name == away].dec.median()))
    return pd.DataFrame(rows)


def main():
    P = pd.read_parquet(PR); P["game_id"] = P.game_id.astype(int)
    G = pd.read_parquet(GL); G = G[G.season == SEASON].copy(); G["game_id"] = G.game_id.astype(int)
    m = P.merge(G[["game_id", "event_id", "date", "home", "away", "home_win", "pin_p_h", "med_dec_h", "med_dec_a"]], on="game_id")
    m = m[m.pin_p_h.notna()].copy()
    gr = pd.read_parquet(GR); gr = gr[gr.season == SEASON].copy(); gr["game_id"] = gr.game_id.astype(int)
    gh = gr[gr.role == "home"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "h_gr"})
    ga = gr[gr.role == "away"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "a_gr"})
    m = m.merge(gh, on="game_id", how="left").merge(ga, on="game_id", how="left")
    print(f"2024-25 games with engine + Pinnacle close: {len(m)}; goalie rating missing {int(m.h_gr.isna().sum() + m.a_gr.isna().sum())}")
    k = ((m.h_gr < 0) & (m.a_gr < 0)).fillna(False).to_numpy()
    d = m[k].copy()
    print(f"R6 regime n = {len(d)}  (2023-24 dev had 133)")
    y = d.home_win.astype(float).to_numpy(); pe = d.p_home_win.to_numpy(); pp = d.pin_p_h.to_numpy()
    b, lo, hi, p = a1(y, pe, pp)
    print(f"A1 disagreement coef {b:.3f}  90% CI [{lo:.3f}, {hi:.3f}]  one-sided p {p:.4f}  -> {'HELD' if lo > 0 else 'NOT HELD'}")
    # A2 picks at close median prices
    da, db = d.med_dec_h.to_numpy(), d.med_dec_a.to_numpy()
    ea = pe - 1 / da; eb = (1 - pe) - 1 / db
    bh, ba = ea >= 0.04, eb >= 0.04
    ret = np.concatenate([np.where(y == 1, da - 1, -1)[bh], np.where(y == 0, db - 1, -1)[ba]])
    clv = np.concatenate([(pp - 1 / da)[bh], ((1 - pp) - 1 / db)[ba]])
    n = len(ret); se = ret.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    cse = clv.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    print(f"A2 picks {n} (home {int(bh.sum())}, away {int(ba.sum())}): ROI {ret.mean():+.4f} (SE {se:.4f});  "
          f"CLV at close (Pinnacle fair - break-even) {clv.mean():+.4f} (SE {cse:.4f}, 90% lo {clv.mean()-1.6449*cse:+.4f}) "
          f"-> {'HELD' if clv.mean()-1.6449*cse > 0 else 'NOT HELD'}")
    d["pick"] = np.where(bh, "home", np.where(ba, "away", ""))
    picks = d[d.pick != ""].copy()
    picks["ret"] = np.where(picks.pick == "home", np.where(picks.home_win == 1, picks.med_dec_h - 1, -1),
                            np.where(picks.home_win == 0, picks.med_dec_a - 1, -1))
    picks["clv"] = np.where(picks.pick == "home", picks.pin_p_h - 1 / picks.med_dec_h, (1 - picks.pin_p_h) - 1 / picks.med_dec_a)
    picks["fav"] = np.where(picks.pick == "home", picks.pin_p_h > 0.5, picks.pin_p_h < 0.5)
    picks["month"] = pd.to_datetime(picks.date).dt.to_period("M")
    print("by month:\n", picks.groupby("month").agg(n=("ret", "size"), roi=("ret", "mean"), clv=("clv", "mean")).round(4).to_string())
    print("by fav/dog:\n", picks.groupby("fav").agg(n=("ret", "size"), roi=("ret", "mean"), clv=("clv", "mean")).round(4).to_string())
    # secondary: hypothetical early-snapshot pick (upper bound; starters unknown then)
    E = early_pinnacle(G)
    de = d.merge(E, on="event_id", how="inner")
    pe2 = de.p_home_win.to_numpy(); pc = de.pin_p_h.to_numpy()
    ea = pe2 - 1 / de.med_dec_h_e.to_numpy(); eb = (1 - pe2) - 1 / de.med_dec_a_e.to_numpy()
    bh, ba = ea >= 0.04, eb >= 0.04
    clv_e = np.concatenate([(pc - 1 / de.med_dec_h_e.to_numpy())[bh], ((1 - pc) - 1 / de.med_dec_a_e.to_numpy())[ba]])
    yy = de.home_win.to_numpy()
    ret_e = np.concatenate([np.where(yy == 1, de.med_dec_h_e.to_numpy() - 1, -1)[bh], np.where(yy == 0, de.med_dec_a_e.to_numpy() - 1, -1)[ba]])
    ne = len(clv_e)
    print(f"secondary (early median price, UPPER BOUND): games with early {len(de)}, picks {ne}: CLV vs close {clv_e.mean():+.4f} "
          f"(SE {clv_e.std(ddof=1)/np.sqrt(ne):.4f}), ROI {ret_e.mean():+.4f}")
    # descriptive: the whole-season A1 for context (not a test)
    b2, lo2, hi2, p2 = a1(m.home_win.astype(float).to_numpy(), m.p_home_win.to_numpy(), m.pin_p_h.to_numpy())
    print(f"context (not a test): ALL 2024-25 games n={len(m)} A1 coef {b2:.3f} [{lo2:.3f}, {hi2:.3f}]")
    picks.to_csv("/home/claude/hunt/work/s48_r6_confirm_picks.csv", index=False)


if __name__ == "__main__":
    main()
