#!/usr/bin/env python3
"""NHL edge hunt — exhaustive condition scan, discovery + validation only (holdout is holdout.py, run once).

Pre-registration: PREREGISTRATION.md (splits, statistic, n >= 200, BH 10% FDR, survivor rule).
Markets: moneyline (side = the team the condition describes; H0 = no-vig closing probability) and
totals (over among non-push; H0 = 50%, TRIAGE only — the line has no price before 2021-22).
Quantile thresholds are computed on DISCOVERY seasons only.
Output: scan_results.csv (every tested cell), survivors_DV.csv
"""
import itertools
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
G = pd.read_parquet(HERE / "games.parquet")
MIN_N = 200
SPLITS = {
    "ml": {"D": range(2007, 2014), "V": range(2014, 2019), "H": range(2019, 2023)},
    "tot": {"D": range(2007, 2014), "V": range(2014, 2023), "H": range(2023, 2026)},
}
disc = G[G.season.isin(SPLITS["ml"]["D"])]


def q(col, p):
    """Quantile threshold from DISCOVERY seasons only (both teams' columns pooled)."""
    v = pd.concat([disc["h_" + col], disc["a_" + col]]).dropna()
    return float(v.quantile(p))


TH = {c: (q(c, .25), q(c, .75)) for c in ["gsv_b", "ptspct_b", "xgpct_b", "xg10_b", "gfpg_b", "gapg_b",
                                         "xgfpg_b", "xgapg_b"]}
home = np.ones(len(G), bool)
fav_home = (G.p_h >= 0.5).to_numpy()

# ---------------- condition registry: name -> (mask, side_is_home or None, family) ----------------
C = {}


def add(name, mask, side, fam):
    m = pd.Series(mask, index=G.index).fillna(False).astype(bool).to_numpy()
    C[name] = (m, None if side is None else np.asarray(side, bool), fam)


def team_conds(t, o):
    T = lambda c: G[f"{t}_{c}"]
    O = lambda c: G[f"{o}_{c}"]
    gp10 = (T("gp_b") >= 10) & (O("gp_b") >= 10)
    d = {
        "b2b_opp_not": (T("b2b") == True) & (O("b2b") != True),
        "b2b": T("b2b") == True,
        "rest3plus": T("rest") >= 3,
        "rest_adv2": (T("rest") - O("rest")) >= 2,
        "third_in_4": T("g_last3") >= 2,
        "dense7_4plus": T("g_last7") >= 4,
        "travel_1500": T("travel_mi") > 1500,
        "moved_east2": T("tz_shift") >= 2,
        "moved_west2": T("tz_shift") <= -2,
        "far_tz2": T("home_tz_gap").abs() >= 2,
        "backup": T("backup") == True,
        "backup_vs_primary": (T("backup") == True) & (O("backup") != True),
        "goalie_b2b": T("goalie_b2b") == True,
        "gsv_top": T("gsv_b") >= TH["gsv_b"][1],
        "gsv_bottom": T("gsv_b") <= TH["gsv_b"][0],
        "goalie_new": (T("g_starts_b") <= 2) & (T("gp_b") >= 10),
        "pts_top": gp10 & (T("ptspct_b") >= TH["ptspct_b"][1]),
        "pts_bottom": gp10 & (T("ptspct_b") <= TH["ptspct_b"][0]),
        "pts_gap15": gp10 & ((T("ptspct_b") - O("ptspct_b")) >= 0.15),
        "win10_hot": T("win10_b") >= 0.7,
        "win10_cold": T("win10_b") <= 0.3,
        "streak_w4": T("streak_b") >= 4,
        "streak_l4": T("streak_b") <= -4,
        "last_lost_by3": T("last_margin") <= -3,
        "last_won_by3": T("last_margin") >= 3,
        "last_ot_loss": T("last_otloss") == True,
        "xg_top": T("xgpct_b") >= TH["xgpct_b"][1],
        "xg_bottom": T("xgpct_b") <= TH["xgpct_b"][0],
        "xg10_top": T("xg10_b") >= TH["xg10_b"][1],
        "xg10_bottom": T("xg10_b") <= TH["xg10_b"][0],
        "pdo_high": T("pdo_b") >= 1.02,
        "pdo_low": T("pdo_b") <= 0.98,
        "lucky": T("luck_b") >= 0.3,
        "unlucky": T("luck_b") <= -0.3,
        "xg_better_pts_worse": gp10 & (T("xgpct_b") > O("xgpct_b") + 0.03) & (T("ptspct_b") < O("ptspct_b")),
        "revenge": T("lost_prev_meeting") == True,
        "tank": (T("gp_b") >= 60) & (T("ptspct_b") < 0.45),
        "early_gp10": T("gp_b") < 10,
    }
    return d


for t, o, side in (("h", "a", home), ("a", "h", ~home)):
    tag = "HOME" if t == "h" else "AWAY"
    for k, m in team_conds(t, o).items():
        add(f"{tag}:{k}", m, side, "team:" + k)
# away-only / home-only schedule shapes
add("AWAY:road_trip_4plus", (G.a_run_len >= 4), ~home, "trip")
add("HOME:first_home_after_trip3", (G.h_run_len == 1) & (G.h_prev_run_len >= 3) & (G.h_prev_is_home == False), home, "trip")
add("HOME:homestand_5plus", G.h_run_len >= 5, home, "trip")
# price (moneyline)
for lo, hi in [(0, .35), (.35, .42), (.42, .48), (.48, .52), (.52, .58), (.58, .65), (.65, .72), (.72, 1.01)]:
    add(f"PRICE:home_p_{lo:.2f}-{hi:.2f}", (G.p_h >= lo) & (G.p_h < hi), home, "price_home")
for lo, hi in [(.5, .55), (.55, .6), (.6, .65), (.65, .7), (.7, 1.01)]:
    fp = np.maximum(G.p_h, 1 - G.p_h)
    add(f"PRICE:fav_p_{lo:.2f}-{hi:.2f}", (fp >= lo) & (fp < hi), fav_home, "price_fav")
ov_t = disc.overround.quantile([1 / 3, 2 / 3]).to_list()
add("PRICE:hold_low", G.overround <= ov_t[0], None, "hold")
add("PRICE:hold_high", G.overround >= ov_t[1], None, "hold")
add("PRICE:pl_disagrees_ml", ((G.p_h > .5) & (G.pl_h > 0)) | ((G.p_h < .5) & (G.pl_h < 0)), None, "pl")
# totals line
for lo, hi, nm in [(0, 5.75, "tl<=5.5"), (5.75, 6.25, "tl=6"), (6.25, 6.75, "tl=6.5"), (6.75, 99, "tl>=7")]:
    add(f"TOTAL:{nm}", (G.tl >= lo) & (G.tl < hi), None, "tline")
# game-level context (neutral side = home for ML)
add("GAME:both_b2b", (G.h_b2b == True) & (G.a_b2b == True), None, "both")
add("GAME:both_backups", (G.h_backup == True) & (G.a_backup == True), None, "both")
add("GAME:both_primary", (G.h_backup == False) & (G.a_backup == False), None, "both")
add("GAME:divisional", G.h_meetings_season >= 4, None, "div")
pace = G.h_gfpg_b + G.h_gapg_b + G.a_gfpg_b + G.a_gapg_b
xpace = G.h_xgfpg_b + G.h_xgapg_b + G.a_xgfpg_b + G.a_xgapg_b
pq = disc.eval("h_gfpg_b + h_gapg_b + a_gfpg_b + a_gapg_b").quantile([.25, .75]).to_list()
xq = disc.eval("h_xgfpg_b + h_xgapg_b + a_xgfpg_b + a_xgapg_b").quantile([.25, .75]).to_list()
add("GAME:pace_high", (G.h_gp_b >= 10) & (pace >= pq[1]), None, "pace")
add("GAME:pace_low", (G.h_gp_b >= 10) & (pace <= pq[0]), None, "pace")
add("GAME:xpace_high", xpace >= xq[1], None, "xpace")
add("GAME:xpace_low", xpace <= xq[0], None, "xpace")
# pace vs line: goals environment above/below the total line
add("GAME:pace_above_line", (G.h_gp_b >= 10) & (pace / 2 - G.tl >= 0.5), None, "pace_line")
add("GAME:pace_below_line", (G.h_gp_b >= 10) & (pace / 2 - G.tl <= -0.5), None, "pace_line")
for m in [10, 11, 12, 1, 2, 3, 4]:
    add(f"CAL:month_{m}", G.month == m, None, "month")
for d, nm in enumerate(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]):
    add(f"CAL:dow_{nm}", G.dow == d, None, "dow")

print(f"{len(C)} single conditions")


# ---------------- evaluation ----------------
def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, a / 100 + 1, 100 / -a + 1)


Y_H = G.home_win.to_numpy().astype(float)
P_H = G.p_h.to_numpy()
ML_H, ML_A = G.ml_h.to_numpy(), G.ml_a.to_numpy()
OVER = G.over.to_numpy()
SEASON = G.season.to_numpy()


def ml_stats(mask, side_home):
    ok = mask & ~np.isnan(P_H)
    n = int(ok.sum())
    if n == 0:
        return n, np.nan, np.nan, np.nan, np.nan, np.nan
    sh = side_home[ok]
    y = np.where(sh, Y_H[ok], 1 - Y_H[ok])
    p = np.where(sh, P_H[ok], 1 - P_H[ok])
    z = (y - p).sum() / np.sqrt((p * (1 - p)).sum())
    d_side = dec(np.where(sh, ML_H[ok], ML_A[ok]))
    d_opp = dec(np.where(sh, ML_A[ok], ML_H[ok]))
    roi_side = np.mean(y * (d_side - 1) - (1 - y))
    roi_opp = np.mean((1 - y) * (d_opp - 1) - y)
    return n, y.mean(), p.mean(), z, roi_side, roi_opp


def tot_stats(mask):
    ok = mask & ~np.isnan(OVER)
    n = int(ok.sum())
    if n == 0:
        return n, np.nan, np.nan, np.nan, np.nan, np.nan
    y = OVER[ok]
    z = (y.sum() - 0.5 * n) / np.sqrt(0.25 * n)
    r110 = 100 / 110
    return n, y.mean(), 0.5, z, np.mean(y * r110 - (1 - y)), np.mean((1 - y) * r110 - y)


def seasons_mask(market, split):
    return np.isin(SEASON, list(SPLITS[market][split]))


def evaluate(name, mask, side, market):
    out = {"cell": name, "market": market}
    for sp in ("D", "V"):
        m = mask & seasons_mask(market, sp)
        n, y, p, z, r1, r2 = ml_stats(m, side) if market == "ml" else tot_stats(m)
        out.update({f"n_{sp}": n, f"rate_{sp}": y, f"exp_{sp}": p, f"z_{sp}": z,
                    f"roi_side_{sp}": r1, f"roi_opp_{sp}": r2})
    return out


rows = []
names = list(C)
# singles
for nm in names:
    m, s, fam = C[nm]
    rows.append(evaluate(nm, m, home if s is None else s, "ml"))
    rows.append(evaluate(nm, m, home, "tot"))
# pairs
for a_, b_ in itertools.combinations(names, 2):
    ma, sa, fa = C[a_]
    mb, sb, fb = C[b_]
    if fa == fb:
        continue
    m = ma & mb
    if sa is not None and sb is not None:
        m = m & (sa == sb)
        side = sa
    else:
        side = sa if sa is not None else (sb if sb is not None else home)
    if (m & seasons_mask("ml", "D")).sum() < MIN_N:
        continue
    nm = f"{a_} & {b_}"
    rows.append(evaluate(nm, m, side, "ml"))
    # totals: side-free, only if the pair did not require a same-team match to exist
    rows.append(evaluate(nm, ma & mb, home, "tot"))

R = pd.DataFrame(rows)
R = R[R.n_D >= MIN_N].drop_duplicates(["cell", "market"]).reset_index(drop=True)
R["p_D"] = 2 * norm.sf(R.z_D.abs())
R["p_V"] = 2 * norm.sf(R.z_V.abs())
# BH over ALL discovery tests (both markets pooled)
m_tests = len(R)
order = np.argsort(R.p_D.to_numpy())
ranks = np.empty(m_tests, int); ranks[order] = np.arange(1, m_tests + 1)
R["bh_crit"] = ranks / m_tests * 0.10
sorted_p = R.p_D.to_numpy()[order]
passed = sorted_p <= (np.arange(1, m_tests + 1) / m_tests * 0.10)
k = passed.nonzero()[0].max() + 1 if passed.any() else 0
R["bh_pass"] = ranks <= k
R["same_sign_V"] = np.sign(R.z_D) == np.sign(R.z_V)
R["V_onesided_p"] = norm.sf(np.sign(R.z_D) * R.z_V)
R["DV_survivor"] = R.bh_pass & R.same_sign_V & (R.V_onesided_p < 0.10)
R.to_csv(HERE / "scan_results.csv", index=False)
R[R.DV_survivor].to_csv(HERE / "survivors_DV.csv", index=False)

print(f"tested cells: {m_tests} (ml {int((R.market=='ml').sum())}, totals {int((R.market=='tot').sum())})")
for thr in (0.05, 0.01, 0.001):
    print(f"  p_D < {thr}: observed {int((R.p_D < thr).sum())}  expected by chance {m_tests*thr:.0f}")
print(f"  BH 10% FDR passes: {k}")
print(f"  of those, same sign in validation: {int((R.bh_pass & R.same_sign_V).sum())}; "
      f"validation one-sided p<0.10: {int(R.DV_survivor.sum())}")
# null-agreement check: among ALL cells, how often does validation sign agree with discovery sign?
for mk in ("ml", "tot"):
    s = R[R.market == mk]
    top = s[s.p_D < 0.01]
    print(f"  [{mk}] sign agreement D->V: all cells {s.same_sign_V.mean():.3f} (n={len(s)}); "
          f"p_D<0.01 cells {top.same_sign_V.mean() if len(top) else float('nan'):.3f} (n={len(top)})")
print(R.sort_values("p_D").head(25)[["cell", "market", "n_D", "rate_D", "exp_D", "z_D", "p_D", "bh_pass",
                                     "n_V", "rate_V", "exp_V", "z_V"]].to_string())
