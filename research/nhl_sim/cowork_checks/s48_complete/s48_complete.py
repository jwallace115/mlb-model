#!/usr/bin/env python3
"""Cowork completion of S-WO4d S48: the full pre-registered 12-test regime family (6 regimes x ML/totals), 2023-24.
Definitions exactly as workorder_S4d_2026-09-30.md. A1: y ~ logit(p_pin) + (logit(p_eng) - logit(p_pin)), one-sided p
for the disagreement coefficient > 0. A2: edge = engine prob - 1/median decimal >= 0.04, ROI at the median price.
BH 10% across the 12 one-sided p-values. Inputs: S44 prices (seed = game_id), games_lines (Pinnacle close, median
prices), games.parquet (games played before, B2B), goalie starts (backup), goalie_ratings (R6)."""
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import norm

PR = "/mnt/user-data/uploads/mlb-model-nhlsim4b/nhl/data/sim/prices/season=2023.parquet"
GL = "/home/claude/nhlhunt/p3/games_lines.parquet"
GS = "/home/claude/nhlhunt/raw/nhl_goalie_starts.csv"
GR = "/mnt/user-data/uploads/mlb-model-nhlsim4b/nhl/data/sim/ratings/goalie_ratings.parquet"
lg = lambda p: np.log(p / (1 - p))


def a1(y, pe, pp):
    pe = np.clip(pe, 1e-3, 1 - 1e-3); pp = np.clip(pp, 1e-3, 1 - 1e-3)
    X = sm.add_constant(np.column_stack([lg(pp), lg(pe) - lg(pp)]))
    f = sm.Logit(y, X).fit(disp=0)
    b, se = f.params[2], f.bse[2]
    return b, b - 1.6449 * se, b + 1.6449 * se, 1 - norm.cdf(b / se)


def main():
    P = pd.read_parquet(PR); P["game_id"] = P.game_id.astype(int)
    G = pd.read_parquet(GL); G = G[G.season == 2023]; G["game_id"] = G.game_id.astype(int)
    m = P.drop(columns=["pin_p_home"]).merge(G[["game_id", "hg", "ag", "home_win", "pin_p_h", "med_dec_h", "med_dec_a",
                                                "tl_pin", "pin_p_over", "med_dec_over", "med_dec_under",
                                                "h_gp_b", "a_gp_b", "h_b2b", "a_b2b"]], on="game_id")
    m = m[m.pin_p_h.notna()].copy()
    # backup start: starter != team's most-used starter this season before the date (no prior start -> not backup)
    gs = pd.read_csv(GS); gs = gs[(gs.started == 1) & (gs.season == 2023)].sort_values(["date", "game_id"])
    rec = []
    for (tm, se), x in gs.groupby(["team", "season"], sort=False):
        cnt = {}
        for r in x.itertuples(index=False):
            prim = max(cnt, key=cnt.get) if cnt else None
            rec.append((r.game_id, tm, prim is not None and r.goalie_id != prim))
            cnt[r.goalie_id] = cnt.get(r.goalie_id, 0) + 1
    B = pd.DataFrame(rec, columns=["game_id", "team", "backup"])
    m = m.merge(B.rename(columns={"team": "home", "backup": "h_bk"}), on=["game_id", "home"], how="left")
    m = m.merge(B.rename(columns={"team": "away", "backup": "a_bk"}), on=["game_id", "away"], how="left")
    gr = pd.read_parquet(GR); gr = gr[gr.season == 2023]; gr["game_id"] = gr.game_id.astype(int)
    gh = gr[gr.role == "home"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "h_gr"})
    ga = gr[gr.role == "away"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "a_gr"})
    m = m.merge(gh, on="game_id", how="left").merge(ga, on="game_id", how="left")
    print(f"games {len(m)}; backup flag missing {m.h_bk.isna().sum() + m.a_bk.isna().sum()}; goalie rating missing "
          f"{m.h_gr.isna().sum() + m.a_gr.isna().sum()}")
    # engine totals at Pinnacle's line, conditional on no push
    tot = m.hg + m.ag
    pe_o = (m.p_over / (1 - m.p_push_total)).clip(1e-3, 1 - 1e-3)
    same_line = np.isclose(m.pin_total_line, m.tl_pin)
    mt = m[same_line & m.pin_p_over.notna() & (tot != m.tl_pin)].copy()
    mt["y"] = (mt.hg + mt.ag > mt.tl_pin).astype(float); mt["pe"] = pe_o[mt.index]
    # regimes
    def regimes(d, market):
        pe = d.p_home_win if market == "ML" else d.pe
        pp = d.pin_p_h if market == "ML" else d.pin_p_over
        pick_side_prob = np.where(pe > pp, pp, 1 - pp)       # Pinnacle prob of the side the engine prefers
        return {
            "R1 early (<=10 GP either)": (d.h_gp_b <= 10) | (d.a_gp_b <= 10),
            "R2 either B2B": (d.h_b2b == True) | (d.a_b2b == True),
            "R3 either backup": (d.h_bk == True) | (d.a_bk == True),
            "R4 |eng-pin|>5pt": (pe - pp).abs() > 0.05,
            "R5 engine pick = underdog": pd.Series(pick_side_prob < 0.5, index=d.index),
            "R6 goalies": ((d.h_gr > 0) & (d.a_gr > 0)) if market == "TOT" else ((d.h_gr < 0) & (d.a_gr < 0)),
        }
    rows = []
    for market, d in [("ML", m), ("TOT", mt)]:
        y = (d.home_win.astype(float) if market == "ML" else d.y).to_numpy()
        pe = (d.p_home_win if market == "ML" else d.pe).to_numpy()
        pp = (d.pin_p_h if market == "ML" else d.pin_p_over).to_numpy()
        da, db = (d.med_dec_h, d.med_dec_a) if market == "ML" else (d.med_dec_over, d.med_dec_under)
        for name, k in regimes(d, market).items():
            k = k.fillna(False).to_numpy().astype(bool)
            b, lo, hi, p = a1(y[k], pe[k], pp[k])
            ea = pe[k] - 1 / da.to_numpy()[k]; eb = (1 - pe[k]) - 1 / db.to_numpy()[k]
            win_a = y[k] == 1; win_b = y[k] == 0
            ret = np.concatenate([np.where(win_a, da.to_numpy()[k] - 1, -1)[ea >= 0.04],
                                  np.where(win_b, db.to_numpy()[k] - 1, -1)[eb >= 0.04]])
            rows.append(dict(market=market, regime=name, n=int(k.sum()), coef=b, lo90=lo, hi90=hi, p=p,
                             a2_n=len(ret), a2_roi=ret.mean() if len(ret) else np.nan,
                             a2_se=ret.std(ddof=1) / np.sqrt(len(ret)) if len(ret) > 1 else np.nan))
    R = pd.DataFrame(rows).sort_values("p").reset_index(drop=True)
    R["bh_thresh"] = 0.10 * (np.arange(len(R)) + 1) / len(R)
    passed = R.p <= R.bh_thresh
    kmax = passed[passed].index.max() if passed.any() else -1
    R["BH_survivor"] = R.index <= kmax
    pd.set_option("display.width", 200)
    print(R.round(4).to_string())
    R.to_csv("/home/claude/nhl/s48/s48_family_12.csv", index=False)


if __name__ == "__main__":
    main()
