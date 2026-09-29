#!/usr/bin/env python3
"""Phase 3 scan (PREREGISTRATION_P3.md). Markets: moneyline, puck line (+/-1.5), total at Pinnacle's line.
Reference = Pinnacle de-vigged; bet price = median-of-books decimal. D = 2022-23+2023-24, V = 2024-25,
H = 2025-26 (opened only for D->V survivors, in holdout_p3.py). Also runs the single pre-registered H_PL test."""
import contextlib, io, itertools, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "out"))
with contextlib.redirect_stdout(io.StringIO()):
    import scan as P1                                     # phase-1 registry (thresholds from 2007-14 discovery)
M = pd.read_parquet(HERE / "games_lines.parquet")
idx = pd.Series(np.arange(len(P1.G)), index=P1.G.game_id).loc[M.game_id].to_numpy()
SEASON = M.season.to_numpy()
SPL = {"D": [2022, 2023], "V": [2024], "H": [2025]}
home = np.ones(len(M), bool)

# ---- outcomes and prices, oriented to HOME for ml, to PL favourite for pl, to OVER for totals ----
y_h = M.home_win.to_numpy().astype(float)
p_h = M.pin_p_h.to_numpy()
fav_is_home = (M.pl_fav == M.home_team).to_numpy()
fav_margin = np.where(fav_is_home, M.hg - M.ag, M.ag - M.hg)
y_plfav = (fav_margin >= 2).astype(float)
p_plfav = M.pin_p_plfav.to_numpy()
tl = M.tl_pin.to_numpy(); tot = M.tot.to_numpy()
y_over = np.where(tot > tl, 1.0, np.where(tot < tl, 0.0, np.nan))
p_over = M.pin_p_over.to_numpy()

# ---- conditions: phase-1 registry subset + new market conditions ----
C = {k: (m[idx], None if s is None else s[idx], fam) for k, (m, s, fam) in P1.C.items()}
Dm = np.isin(SEASON, SPL["D"])
fav_home_ml = p_h >= 0.5
imp_med_h = 1 / M.med_dec_h.to_numpy(); imp_med_a = 1 / M.med_dec_a.to_numpy()
pin_vs_med_h = p_h - imp_med_h / (imp_med_h + imp_med_a)
C["MKT:pin_higher_home3"] = (pin_vs_med_h >= 0.03, home, "pinmed")
C["MKT:pin_lower_home3"] = (pin_vs_med_h <= -0.03, home, "pinmed")
disp_hi = np.nanquantile(M.ml_disp.to_numpy()[Dm], 2 / 3)
C["MKT:ml_dispersion_high"] = (M.ml_disp.to_numpy() >= disp_hi, None, "disp")
fav_ml_p = np.maximum(p_h, 1 - p_h)
ratio = p_plfav / fav_ml_p
r_lo, r_hi = np.nanquantile(ratio[Dm], [1 / 3, 2 / 3])
C["MKT:pl_ratio_low"] = (ratio <= r_lo, fav_home_ml, "plratio")
C["MKT:pl_ratio_high"] = (ratio >= r_hi, fav_home_ml, "plratio")
C["MKT:over_juiced"] = (p_over >= 0.53, None, "tjuice")
C["MKT:under_juiced"] = (p_over <= 0.47, None, "tjuice")
for k in list(C):
    m, s, f = C[k]
    C[k] = (np.nan_to_num(m.astype(float), nan=0).astype(bool), s, f)


def z_ml(mask, side):
    ok = mask & ~np.isnan(p_h)
    sh = side[ok]; y = np.where(sh, y_h[ok], 1 - y_h[ok]); p = np.where(sh, p_h[ok], 1 - p_h[ok])
    return ok.sum(), y, p


def z_pl(mask, side):
    # bet the condition team's puck line: -1.5 if it is the PL favourite, +1.5 if not
    ok = mask & ~np.isnan(p_plfav)
    team_is_home = side[ok]
    team_is_fav = team_is_home == fav_is_home[ok]
    y = np.where(team_is_fav, y_plfav[ok], 1 - y_plfav[ok]); p = np.where(team_is_fav, p_plfav[ok], 1 - p_plfav[ok])
    return ok.sum(), y, p


def z_tot(mask, side):
    ok = mask & ~np.isnan(p_over) & ~np.isnan(y_over)
    return ok.sum(), y_over[ok], p_over[ok]


FN = {"ml": z_ml, "pl": z_pl, "tot": z_tot}


def stats(fn, mask, side):
    n, y, p = fn(mask, side)
    if n == 0:
        return {"n": 0}
    z = (y - p).sum() / np.sqrt((p * (1 - p)).sum())
    return {"n": int(n), "rate": y.mean(), "ref": p.mean(), "z": z}


rows = []
names = list(C)
cells = [(n_, C[n_][0], C[n_][1]) for n_ in names]
for a_, b_ in itertools.combinations(names, 2):
    ma, sa, fa = C[a_]; mb, sb, fb = C[b_]
    if fa == fb:
        continue
    m = ma & mb
    if sa is not None and sb is not None:
        m = m & (sa == sb); s = sa
    else:
        s = sa if sa is not None else sb
    if (m & Dm).sum() < 200:
        continue
    cells.append((f"{a_} & {b_}", m, s))
for nm, m, s in cells:
    side = home if s is None else s
    for mk, fn in FN.items():
        d = stats(fn, m & Dm, side)
        if d["n"] < 200:
            continue
        v = stats(fn, m & np.isin(SEASON, SPL["V"]), side)
        rows.append({"cell": nm, "market": mk, **{f"{k}_D": x for k, x in d.items()}, **{f"{k}_V": x for k, x in v.items()}})
R = pd.DataFrame(rows).drop_duplicates(["cell", "market"])
R["p_D"] = 2 * norm.sf(R.z_D.abs())
mt = len(R); o = np.argsort(R.p_D.to_numpy()); sp = R.p_D.to_numpy()[o]
ok = sp <= np.arange(1, mt + 1) / mt * 0.10
k = ok.nonzero()[0].max() + 1 if ok.any() else 0
rk = np.empty(mt, int); rk[o] = np.arange(1, mt + 1)
R["bh_pass"] = rk <= k
R["same_sign_V"] = np.sign(R.z_D) == np.sign(R.z_V)
R["V_onesided_p"] = norm.sf(np.sign(R.z_D) * R.z_V)
R["DV_survivor"] = R.bh_pass & R.same_sign_V & (R.V_onesided_p < 0.10)
R.to_csv(HERE / "p3_scan_results.csv", index=False)
R[R.DV_survivor].to_csv(HERE / "p3_survivors_DV.csv", index=False)
print(f"conditions {len(C)}; tested cells {mt} (" + ", ".join(f"{mk} {int((R.market==mk).sum())}" for mk in FN) + ")")
for thr in (0.05, 0.01, 0.001):
    print(f"  p_D<{thr}: observed {int((R.p_D<thr).sum())}, expected {mt*thr:.0f}")
print(f"  BH passes {k}; D->V survivors {int(R.DV_survivor.sum())}")
for mk in FN:
    s = R[R.market == mk]
    print(f"  [{mk}] p<.01 {int((s.p_D<.01).sum())} vs {len(s)*.01:.1f}; sign agreement all {s.same_sign_V.mean():.3f}, "
          f"p<.01 {s[s.p_D<.01].same_sign_V.mean() if (s.p_D<.01).any() else float('nan'):.3f}")
print(R.sort_values("p_D").head(20)[["cell", "market", "n_D", "rate_D", "ref_D", "z_D", "n_V", "rate_V", "ref_V", "z_V", "bh_pass"]].round(3).to_string())
