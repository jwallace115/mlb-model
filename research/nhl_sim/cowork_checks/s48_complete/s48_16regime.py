#!/usr/bin/env python3
"""S52: 16-regime family (8 regimes x ML/totals) on fixed engine prices.
Extends S48 with R7 (both teams 5v5 att > 1.02x league) and R8 (both penalties > 1.05x league).
BH 10% across 16 one-sided p-values.

Usage:
  python3 research/nhl_sim/cowork_checks/s48_complete/s48_16regime.py --prices nhl/data/sim/prices/season=2023.parquet
"""
import argparse, sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

GL = ROOT / "research" / "nhl_sim" / "edge_hunt_2026-09-30" / "games_lines.parquet"
GS = ROOT / "research" / "nhl_sim" / "edge_hunt_2026-09-30" / "inputs" / "nhl_goalie_starts.csv"
GR = ROOT / "nhl" / "data" / "sim" / "ratings" / "goalie_ratings.parquet"
TR = ROOT / "nhl" / "data" / "sim" / "ratings" / "team_ratings.parquet"

lg = lambda p: np.log(p / (1 - p))


def a1(y, pe, pp):
    pe = np.clip(pe, 1e-3, 1 - 1e-3)
    pp = np.clip(pp, 1e-3, 1 - 1e-3)
    X = sm.add_constant(np.column_stack([lg(pp), lg(pe) - lg(pp)]))
    f = sm.Logit(y, X).fit(disp=0)
    b, se = f.params[2], f.bse[2]
    return b, b - 1.6449 * se, b + 1.6449 * se, 1 - norm.cdf(b / se)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", required=True)
    ap.add_argument("--season", type=int, default=2023)
    ap.add_argument("--out", default=None)
    ap.add_argument("--fit-season", type=int, default=None, help="If set, also run on this season (descriptive)")
    args = ap.parse_args()

    P = pd.read_parquet(args.prices)
    P["game_id"] = P.game_id.astype(int)
    G = pd.read_parquet(GL)
    G = G[G.season == args.season]
    G["game_id"] = G.game_id.astype(int)

    m = P.drop(columns=["pin_p_home"], errors="ignore").merge(
        G[["game_id", "hg", "ag", "home_win", "pin_p_h", "med_dec_h", "med_dec_a",
           "tl_pin", "pin_p_over", "med_dec_over", "med_dec_under",
           "h_gp_b", "a_gp_b", "h_b2b", "a_b2b"]], on="game_id")
    m = m[m.pin_p_h.notna()].copy()

    # Backup starts
    gs = pd.read_csv(GS)
    gs = gs[(gs.started == 1) & (gs.season == args.season)].sort_values(["date", "game_id"])
    rec = []
    for (tm, se), x in gs.groupby(["team", "season"], sort=False):
        cnt = {}
        for r in x.itertuples(index=False):
            n = sum(cnt.values())
            prim = max(cnt, key=cnt.get) if cnt else None
            share = cnt[prim] / n if prim is not None else np.nan
            # Strict backup: primary has >= 60% share AND >= 10 prior starts
            is_strict_bk = prim is not None and r.goalie_id != prim and share >= 0.6 and n >= 10
            rec.append((r.game_id, tm, is_strict_bk))
            cnt[r.goalie_id] = cnt.get(r.goalie_id, 0) + 1
    B = pd.DataFrame(rec, columns=["game_id", "team", "backup"])
    m = m.merge(B.rename(columns={"team": "home", "backup": "h_bk"}), on=["game_id", "home"], how="left")
    m = m.merge(B.rename(columns={"team": "away", "backup": "a_bk"}), on=["game_id", "away"], how="left")

    # Goalie ratings
    gr = pd.read_parquet(GR)
    gr = gr[gr.season == args.season]
    gr["game_id"] = gr.game_id.astype(int)
    gh = gr[gr.role == "home"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "h_gr"})
    ga = gr[gr.role == "away"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "a_gr"})
    m = m.merge(gh, on="game_id", how="left").merge(ga, on="game_id", how="left")

    # Team ratings for R7 and R8 (pace = ev_att_for / lg, pen = pen_taken / lg)
    tr = pd.read_parquet(TR)
    tr = tr[tr.season == args.season]
    tr["game_id"] = tr.game_id.astype(int)
    tr["pace"] = tr.ev_att_for_per60 / tr.lg_ev_att_for_per60
    tr["pen"] = tr.penalties_taken_per60 / tr.lg_penalties_taken_per60
    for role, pre in [("home", "h_"), ("away", "a_")]:
        m = m.merge(tr[tr.role == role][["game_id", "pace", "pen"]].rename(
            columns={"pace": pre + "pace", "pen": pre + "pen"}), on="game_id", how="left")

    print(f"games {len(m)}; backup flag missing {m.h_bk.isna().sum() + m.a_bk.isna().sum()}; "
          f"goalie rating missing {m.h_gr.isna().sum() + m.a_gr.isna().sum()}")

    # Engine totals: compute pe_over from the PMF (same as Cowork's a_tests.py)
    def p_over_from_pmf(row, line):
        li = int(np.floor(line))
        over = sum(getattr(row, f"p_tot_{k}") for k in range(li + 1, 16))
        push = getattr(row, f"p_tot_{li}") if float(line).is_integer() else 0.0
        return over / (1 - push) if push < 1 else np.nan

    m["pe_over"] = [p_over_from_pmf(r, r.tl_pin) if pd.notna(r.tl_pin) else np.nan for r in m.itertuples()]
    tot = m.hg + m.ag
    same_line = np.isclose(m.pin_total_line, m.tl_pin)
    mt = m[same_line & m.pin_p_over.notna() & m.pe_over.notna() & (tot != m.tl_pin)].copy()
    mt["y"] = (mt.hg + mt.ag > mt.tl_pin).astype(float)
    mt["pe"] = mt.pe_over

    def regimes(d, market):
        pe = d.p_home_win if market == "ML" else d.pe
        pp = d.pin_p_h if market == "ML" else d.pin_p_over
        pick_side_prob = np.where(pe > pp, pp, 1 - pp)
        regs = {
            "R1 early": (d.h_gp_b <= 10) | (d.a_gp_b <= 10),
            "R2 B2B": (d.h_b2b == True) | (d.a_b2b == True),
            "R3 backup(strict)": (d.h_bk == True) | (d.a_bk == True),
            "R4 |diff|>5": (pe - pp).abs() > 0.05,
            "R5 eng=dog": pd.Series(pick_side_prob < 0.5, index=d.index),
            "R6 goalies": ((d.h_gr > 0) & (d.a_gr > 0)) if market == "TOT" else ((d.h_gr < 0) & (d.a_gr < 0)),
            "R7 both high pace": (d.h_pace > 1.02) & (d.a_pace > 1.02),
            "R8 both high pen": (d.h_pen > 1.05) & (d.a_pen > 1.05),
        }
        return regs

    all_rows = []
    for season_label in ([args.season] if args.fit_season is None else [args.fit_season, args.season]):
        if season_label != args.season:
            # Load fit-season prices
            fit_path = args.prices.replace(f"season={args.season}", f"season={season_label}")
            P_fit = pd.read_parquet(fit_path)
            P_fit["game_id"] = P_fit.game_id.astype(int)
            G_fit = pd.read_parquet(GL)
            G_fit = G_fit[G_fit.season == season_label]
            G_fit["game_id"] = G_fit.game_id.astype(int)
            m_fit = P_fit.drop(columns=["pin_p_home"], errors="ignore").merge(
                G_fit[["game_id", "hg", "ag", "home_win", "pin_p_h", "med_dec_h", "med_dec_a",
                       "tl_pin", "pin_p_over", "med_dec_over", "med_dec_under",
                       "h_gp_b", "a_gp_b", "h_b2b", "a_b2b"]], on="game_id")
            m_fit = m_fit[m_fit.pin_p_h.notna()].copy()
            # Add backup, goalies, team ratings for fit season
            gs_f = pd.read_csv(GS)
            gs_f = gs_f[(gs_f.started == 1) & (gs_f.season == season_label)].sort_values(["date", "game_id"])
            rec_f = []
            for (tm2, se2), x2 in gs_f.groupby(["team", "season"], sort=False):
                cnt2 = {}
                for r2 in x2.itertuples(index=False):
                    n2 = sum(cnt2.values())
                    prim2 = max(cnt2, key=cnt2.get) if cnt2 else None
                    share2 = cnt2[prim2] / n2 if prim2 is not None else np.nan
                    is_bk2 = prim2 is not None and r2.goalie_id != prim2 and share2 >= 0.6 and n2 >= 10
                    rec_f.append((r2.game_id, tm2, is_bk2))
                    cnt2[r2.goalie_id] = cnt2.get(r2.goalie_id, 0) + 1
            B_f = pd.DataFrame(rec_f, columns=["game_id", "team", "backup"])
            m_fit = m_fit.merge(B_f.rename(columns={"team": "home", "backup": "h_bk"}), on=["game_id", "home"], how="left")
            m_fit = m_fit.merge(B_f.rename(columns={"team": "away", "backup": "a_bk"}), on=["game_id", "away"], how="left")
            gr_f = pd.read_parquet(GR); gr_f = gr_f[gr_f.season == season_label]; gr_f["game_id"] = gr_f.game_id.astype(int)
            m_fit = m_fit.merge(gr_f[gr_f.role == "home"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "h_gr"}), on="game_id", how="left")
            m_fit = m_fit.merge(gr_f[gr_f.role == "away"][["game_id", "gsax_per_att_rating"]].rename(columns={"gsax_per_att_rating": "a_gr"}), on="game_id", how="left")
            tr_f = pd.read_parquet(TR); tr_f = tr_f[tr_f.season == season_label]; tr_f["game_id"] = tr_f.game_id.astype(int)
            tr_f["pace"] = tr_f.ev_att_for_per60 / tr_f.lg_ev_att_for_per60
            tr_f["pen"] = tr_f.penalties_taken_per60 / tr_f.lg_penalties_taken_per60
            for role, pre in [("home", "h_"), ("away", "a_")]:
                m_fit = m_fit.merge(tr_f[tr_f.role == role][["game_id", "pace", "pen"]].rename(
                    columns={"pace": pre + "pace", "pen": pre + "pen"}), on="game_id", how="left")
            m_fit["pe_over"] = [p_over_from_pmf(r, r.tl_pin) if pd.notna(r.tl_pin) else np.nan for r in m_fit.itertuples()]
            d_ml = m_fit
            tot_f = m_fit.hg + m_fit.ag
            sl_f = np.isclose(m_fit.pin_total_line, m_fit.tl_pin)
            mt_f = m_fit[sl_f & m_fit.pin_p_over.notna() & m_fit.pe_over.notna() & (tot_f != m_fit.tl_pin)].copy()
            mt_f["y"] = (mt_f.hg + mt_f.ag > mt_f.tl_pin).astype(float)
            mt_f["pe"] = mt_f.pe_over
            d_tot = mt_f
        else:
            d_ml = m
            d_tot = mt

        for market, d in [("ML", d_ml), ("TOT", d_tot)]:
            y = (d.home_win.astype(float) if market == "ML" else d.y).to_numpy()
            pe = (d.p_home_win if market == "ML" else d.pe).to_numpy()
            pp = (d.pin_p_h if market == "ML" else d.pin_p_over).to_numpy()
            da, db = (d.med_dec_h, d.med_dec_a) if market == "ML" else (d.med_dec_over, d.med_dec_under)
            for name, k in regimes(d, market).items():
                k = k.fillna(False).to_numpy().astype(bool)
                if k.sum() < 10:
                    continue
                b, lo, hi, p = a1(y[k], pe[k], pp[k])
                ea = pe[k] - 1 / da.to_numpy()[k]
                eb = (1 - pe[k]) - 1 / db.to_numpy()[k]
                win_a = y[k] == 1
                win_b = y[k] == 0
                ret = np.concatenate([np.where(win_a, da.to_numpy()[k] - 1, -1)[ea >= 0.04],
                                      np.where(win_b, db.to_numpy()[k] - 1, -1)[eb >= 0.04]])
                all_rows.append(dict(season=season_label, market=market, regime=name, n=int(k.sum()),
                                     coef=b, lo90=lo, hi90=hi, p=p,
                                     a2_n=len(ret),
                                     a2_roi=ret.mean() if len(ret) else np.nan,
                                     a2_se=ret.std(ddof=1) / np.sqrt(len(ret)) if len(ret) > 1 else np.nan))

    R = pd.DataFrame(all_rows)
    # BH on the validate season only
    Rv = R[R.season == args.season].sort_values("p").reset_index(drop=True)
    Rv["bh_thresh"] = 0.10 * (np.arange(len(Rv)) + 1) / len(Rv)
    passed = Rv.p <= Rv.bh_thresh
    kmax = passed[passed].index.max() if passed.any() else -1
    Rv["BH_survivor"] = Rv.index <= kmax

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)

    if args.fit_season:
        Rf = R[R.season == args.fit_season].sort_values("p").reset_index(drop=True)
        print(f"\n=== {args.fit_season} (descriptive) ===")
        print(Rf.round(4).to_string())

    print(f"\n=== {args.season} (BH 10%) ===")
    print(Rv.round(4).to_string())

    n_surv = Rv["BH_survivor"].sum()
    print(f"\nSurvivors: {n_surv}")
    if n_surv == 0:
        print(f"Min p = {Rv.p.min():.4f}, threshold at rank 1 = {Rv.bh_thresh.iloc[0]:.4f}")

    if args.out:
        full = pd.concat([R[R.season != args.season], Rv], ignore_index=True)
        full.to_csv(args.out, index=False)
        print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
