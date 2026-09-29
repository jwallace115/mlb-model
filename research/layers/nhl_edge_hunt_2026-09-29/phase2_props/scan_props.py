#!/usr/bin/env python3
"""Phase 2 props scan (PREREGISTRATION_P2.md). Discovery 2025-10-07..2025-12-31, validation 2026-01-01..03-27.
Two-way lines: y vs consensus de-vigged Over probability. One-way (goal Over only): y vs the median
vig-inclusive implied price (so + means profitable at the median book). Game-clustered z. BH 10% over all
discovery cells. Output: props_scan_results.csv, props_survivors_DV.csv (frozen before any holdout pull)."""
import itertools
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
C = pd.read_parquet(HERE / "props_rows.parquet")
C = C[C.y.notna()].copy()
C["date"] = pd.to_datetime(C.date)
C["split"] = np.where(C.date <= "2025-12-31", "D", "V")
stat = {"player_points": "points", "player_assists": "assists", "player_shots_on_goal": "sog", "player_goals": "goals"}
C["avg_b"] = [getattr(r, f"{stat[r.market_key]}_avg_b") for r in C.itertuples()]
C["l5_b"] = [getattr(r, f"{stat[r.market_key]}_l5_b") for r in C.itertuples()]
C["group"] = np.where(C.two_way, C.market_key.str.replace("player_", ""), "goals_oneway")
C["ref"] = np.where(C.two_way, C.p, C.ip)
C = C[C.ref.notna() & (C.ref > 0) & (C.ref < 1)]


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


D = C[C.split == "D"]
TH = {"opp_sa": D.opp_sa_b.quantile([.25, .75]).tolist()}


def conds(df):
    gp5 = df.gp_b >= 5
    out = {}
    for v in sorted(df.line.unique()):
        out[f"line={v}"] = df.line == v
    for lo, hi in [(0, .2), (.2, .35), (.35, .5), (.5, .65), (.65, .8), (.8, 1)]:
        out[f"ref_{lo:.2f}-{hi:.2f}"] = (df.ref >= lo) & (df.ref < hi)
    dl = df.avg_b - df.line
    out["avg_below_line_0.5+"] = gp5 & (dl <= -0.5)
    out["avg_below_line_0-0.5"] = gp5 & (dl > -0.5) & (dl < 0)
    out["avg_above_line_0-0.5"] = gp5 & (dl >= 0) & (dl < 0.5)
    out["avg_above_line_0.5+"] = gp5 & (dl >= 0.5)
    out["hot_l5"] = (df.l5_b > df.avg_b * 1.3) & gp5
    out["cold_l5"] = (df.l5_b < df.avg_b * 0.7) & gp5
    out["toi_up"] = (df.toi_m_l5_b - df.toi_m_avg_b) >= 1.5
    out["toi_down"] = (df.toi_m_l5_b - df.toi_m_avg_b) <= -1.5
    out["hitrate_hi"] = df.hit_rate_b >= 0.6
    out["hitrate_lo"] = df.hit_rate_b <= 0.4
    out["hitrate_above_mkt"] = (df.hit_rate_b - df.ref) >= 0.10
    out["hitrate_below_mkt"] = (df.hit_rate_b - df.ref) <= -0.10
    out["defense"] = df.pos == "D"
    out["forward"] = df.pos.isin(["C", "L", "R"])
    out["home"] = df.is_home == True
    out["away"] = df.is_home == False
    out["b2b"] = df.b2b == True
    out["opp_allows_many"] = df.opp_sa_b >= TH["opp_sa"][1]
    out["opp_allows_few"] = df.opp_sa_b <= TH["opp_sa"][0]
    out["game_total_high"] = df.game_total >= 6.5
    out["game_total_low"] = df.game_total <= 5.5
    out["early_gp<5"] = df.gp_b < 5
    out["books<=3"] = df.n_books <= 3
    out["books>=6"] = df.n_books >= 6
    out["books_disagree"] = (df.p_max - df.p_min) >= 0.06
    return {k: v.fillna(False).to_numpy() for k, v in out.items()}


def cell_stats(df, mask):
    s = df[mask]
    if len(s) == 0:
        return None
    r = s.y - s.ref
    cs = r.groupby(s.game_id).sum()
    z = r.sum() / np.sqrt((cs ** 2).sum()) if (cs ** 2).sum() > 0 else 0.0
    roi_o = np.mean(np.where(s.y == 1, s.dec_over - 1, -1))
    roi_u = np.mean(np.where(s.y == 0, s.dec_under - 1, -1)) if s.two_way.all() else np.nan
    return {"n": len(s), "games": s.game_id.nunique(), "rate": s.y.mean(), "ref": s.ref.mean(), "z": z,
            "roi_over_med": roi_o, "roi_under_med": roi_u}


rows = []
for grp, df in C.groupby("group"):
    df = df.reset_index(drop=True)
    cd = conds(df)
    isD = (df.split == "D").to_numpy()
    names = list(cd)
    fam = {k: k.split("_")[0].split("=")[0] for k in names}
    cells = [(k, cd[k]) for k in names] + [(f"{a} & {b}", cd[a] & cd[b]) for a, b in itertools.combinations(names, 2)
                                          if fam[a] != fam[b]]
    for nm, m in cells:
        mD = m & isD
        if mD.sum() < 300 or df[mD].game_id.nunique() < 100:
            continue
        d = cell_stats(df, mD); v = cell_stats(df, m & ~isD) or {}
        rows.append({"group": grp, "cell": nm, **{f"{k}_D": x for k, x in d.items()}, **{f"{k}_V": x for k, x in v.items()}})
R = pd.DataFrame(rows)
R["p_D"] = 2 * norm.sf(R.z_D.abs())
m = len(R); order = np.argsort(R.p_D.to_numpy()); sp = R.p_D.to_numpy()[order]
ok = sp <= np.arange(1, m + 1) / m * 0.10
k = ok.nonzero()[0].max() + 1 if ok.any() else 0
rk = np.empty(m, int); rk[order] = np.arange(1, m + 1)
R["bh_pass"] = rk <= k
R["same_sign_V"] = np.sign(R.z_D) == np.sign(R.z_V)
R["V_onesided_p"] = norm.sf(np.sign(R.z_D) * R.z_V)
R["DV_survivor"] = R.bh_pass & R.same_sign_V & (R.V_onesided_p < 0.10)
R.to_csv(HERE / "props_scan_results.csv", index=False)
S = R[R.DV_survivor]
S.to_csv(HERE / "props_survivors_DV.csv", index=False)
print(f"rows D {int((C.split=='D').sum())}, V {int((C.split=='V').sum())}; tested cells {m}")
for thr in (0.05, 0.01, 0.001):
    print(f"  p_D<{thr}: observed {int((R.p_D<thr).sum())}, expected {m*thr:.0f}")
print(f"  BH passes {k}; D->V survivors {len(S)}; sign agreement all {R.same_sign_V.mean():.3f}, "
      f"p<.01 {R[R.p_D<.01].same_sign_V.mean():.3f} (n={int((R.p_D<.01).sum())})")
print("by group (tested / p<.01 / BH):")
print(R.groupby("group").agg(cells=("cell", "size"), p01=("p_D", lambda s: (s < .01).sum()), bh=("bh_pass", "sum"), dv=("DV_survivor", "sum")).to_string())
cols = ["group", "cell", "n_D", "games_D", "rate_D", "ref_D", "z_D", "roi_over_med_D", "roi_under_med_D", "n_V", "rate_V", "ref_V", "z_V", "roi_over_med_V", "roi_under_med_V"]
print(R.sort_values("p_D").head(30)[cols].round(3).to_string())
