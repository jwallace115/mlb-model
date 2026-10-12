"""
ON-1 ITEM 2: Score Monday numbers on 2021-23.
Pre-registrations (ON-1a, ON-1b, ON-2) evaluated with null controls.
"""
import os, sys
import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.join(os.path.dirname(__file__), "../..")
sys.path.insert(0, ROOT)

# ─── LOAD ────────────────────────────────────────────────────────────
mn = pd.read_parquet(os.path.join(ROOT, "nfl/data/own/monday_numbers_2021_23.parquet"))
print(f"Monday numbers: {mn.shape}")
assert sorted(mn["season"].unique()) == [2021, 2022, 2023]

# Drop rows without opens (F10 coverage: ~70%)
has_open = mn["open_spread"].notna()
print(f"Has open spread: {has_open.sum()}/{len(mn)}")
mn_open = mn[has_open].copy()


def wilson_interval(k, n, z=1.96):
    """Wilson score interval for proportion k/n."""
    if n == 0:
        return 0.5, 0.0, 1.0
    p_hat = k / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return center, max(0, center - margin), min(1, center + margin)


# ─── CONFIDENT SUBSET ────────────────────────────────────────────────
# |ours_m - open_spread| >= err_m AND >= 1.0 pt
mn_open["gap"] = mn_open["ours_m"] - mn_open["open_spread"]
mn_open["confident"] = (mn_open["gap"].abs() >= mn_open["err_m"]) & (mn_open["gap"].abs() >= 1.0)
print(f"\nConfident subset: {mn_open['confident'].sum()}/{len(mn_open)} "
      f"({100*mn_open['confident'].mean():.1f}%)")


# ─── DIRECTION AGREEMENT ─────────────────────────────────────────────
# sign(ours - open) matches sign(close - open)
mn_open["close_minus_open"] = mn_open["spread_line"] - mn_open["open_spread"]
mn_open["ours_minus_open"] = mn_open["ours_m"] - mn_open["open_spread"]
# Exclude no-movement games (close == open)
mn_move = mn_open[mn_open["close_minus_open"] != 0].copy()
mn_move["dir_agree"] = (np.sign(mn_move["ours_minus_open"]) == np.sign(mn_move["close_minus_open"]))

print(f"Games with close != open: {len(mn_move)}")
print(f"Direction agreement (all): {mn_move['dir_agree'].mean():.3f} ({mn_move['dir_agree'].sum()}/{len(mn_move)})")

# Confident subset
conf = mn_move[mn_move["confident"]]
print(f"Direction agreement (confident): {conf['dir_agree'].mean():.3f} ({conf['dir_agree'].sum()}/{len(conf)})")

# By season
print("\n=== DIRECTION AGREEMENT BY SEASON ===")
for s in [2021, 2022, 2023]:
    sub_all = mn_move[mn_move["season"] == s]
    sub_conf = conf[conf["season"] == s]
    if len(sub_all) > 0:
        p_all, lo_all, hi_all = wilson_interval(sub_all["dir_agree"].sum(), len(sub_all))
        print(f"  {s} all: {sub_all['dir_agree'].mean():.3f} [{lo_all:.3f}, {hi_all:.3f}] N={len(sub_all)}")
    if len(sub_conf) > 0:
        p_conf, lo_conf, hi_conf = wilson_interval(sub_conf["dir_agree"].sum(), len(sub_conf))
        print(f"  {s} conf: {sub_conf['dir_agree'].mean():.3f} [{lo_conf:.3f}, {hi_conf:.3f}] N={len(sub_conf)}")

# By week-of-season tercile
print("\n=== BY WEEK-OF-SEASON TERCILE ===")
mn_move["week_tercile"] = pd.qcut(mn_move["week"], 3, labels=["early", "mid", "late"])
for t in ["early", "mid", "late"]:
    sub_all = mn_move[mn_move["week_tercile"] == t]
    sub_conf = conf[conf.index.isin(sub_all.index) & conf["confident"]]
    if len(sub_all) > 0:
        p, lo, hi = wilson_interval(sub_all["dir_agree"].sum(), len(sub_all))
        print(f"  {t} all: {sub_all['dir_agree'].mean():.3f} [{lo:.3f}, {hi:.3f}] N={len(sub_all)}")
    if len(sub_conf) > 0:
        p, lo, hi = wilson_interval(sub_conf["dir_agree"].sum(), len(sub_conf))
        print(f"  {t} conf: {sub_conf['dir_agree'].mean():.3f} [{lo:.3f}, {hi:.3f}] N={len(sub_conf)}")

# By err_m tercile
print("\n=== BY ERR_M TERCILE ===")
mn_move["err_tercile"] = pd.qcut(mn_move["err_m"], 3, labels=["low_err", "mid_err", "high_err"])
for t in ["low_err", "mid_err", "high_err"]:
    sub = mn_move[mn_move["err_tercile"] == t]
    if len(sub) > 0:
        p, lo, hi = wilson_interval(sub["dir_agree"].sum(), len(sub))
        print(f"  {t}: {sub['dir_agree'].mean():.3f} [{lo:.3f}, {hi:.3f}] N={len(sub)}")

# By favourite/dog (ours_m < 0 = home fav, > 0 = away fav)
print("\n=== BY FAVOURITE/DOG ===")
mn_move["our_fav"] = np.where(mn_move["ours_m"] < 0, "home_fav", "away_fav")
for cat in ["home_fav", "away_fav"]:
    sub_all = mn_move[mn_move["our_fav"] == cat]
    sub_conf = conf[conf.index.isin(sub_all.index)]
    if len(sub_all) > 0:
        p, lo, hi = wilson_interval(sub_all["dir_agree"].sum(), len(sub_all))
        print(f"  {cat} all: {sub_all['dir_agree'].mean():.3f} [{lo:.3f}, {hi:.3f}] N={len(sub_all)}")
    if len(sub_conf) > 0:
        p, lo, hi = wilson_interval(sub_conf["dir_agree"].sum(), len(sub_conf))
        print(f"  {cat} conf: {sub_conf['dir_agree'].mean():.3f} [{lo:.3f}, {hi:.3f}] N={len(sub_conf)}")

# Same for totals
print("\n=== TOTALS DIRECTION AGREEMENT ===")
mn_open_t = mn_open[mn_open["open_total"].notna()].copy()
mn_open_t["close_minus_open_t"] = mn_open_t["total_line"] - mn_open_t["open_total"]
mn_open_t["ours_minus_open_t"] = mn_open_t["ours_t"] - mn_open_t["open_total"]
mn_move_t = mn_open_t[mn_open_t["close_minus_open_t"] != 0].copy()
mn_move_t["dir_agree_t"] = (np.sign(mn_move_t["ours_minus_open_t"]) == np.sign(mn_move_t["close_minus_open_t"]))
print(f"Totals games with close != open: {len(mn_move_t)}")
print(f"Totals direction agreement: {mn_move_t['dir_agree_t'].mean():.3f} ({mn_move_t['dir_agree_t'].sum()}/{len(mn_move_t)})")


# ─── NULL CONTROL ────────────────────────────────────────────────────
print("\n=== NULL CONTROL ===")
# Shuffle our numbers across games within the same week
np.random.seed(42)
null_agreements = []
for _ in range(1000):
    shuffled = mn_move.copy()
    for (season, week), idx in shuffled.groupby(["season", "week"]).groups.items():
        vals = shuffled.loc[idx, "ours_m"].values.copy()
        np.random.shuffle(vals)
        shuffled.loc[idx, "ours_m"] = vals
    shuffled["ours_minus_open_null"] = shuffled["ours_m"] - shuffled["open_spread"]
    null_agree = (np.sign(shuffled["ours_minus_open_null"]) == np.sign(shuffled["close_minus_open"])).mean()
    null_agreements.append(null_agree)

null_mean = np.mean(null_agreements)
null_sd = np.std(null_agreements)
real_agree = mn_move["dir_agree"].mean()
print(f"Real direction agreement: {real_agree:.4f}")
print(f"Null: mean={null_mean:.4f}, sd={null_sd:.4f}")
print(f"Z-score: {(real_agree - null_mean) / null_sd:.2f}")


# ─── PRE-REGISTRATION OUTCOMES ──────────────────────────────────────
print("\n=== PRE-REGISTRATION OUTCOMES ===")

# ON-1a: confident subset direction agreement > 55%
conf_agree = conf["dir_agree"].mean() if len(conf) > 0 else 0
n_conf = len(conf)
print(f"\nON-1a: Confident subset direction agreement = {conf_agree:.3f} ({conf['dir_agree'].sum()}/{n_conf})")
if conf_agree > 0.55 and n_conf >= 30:
    print(f"  CONFIRMED (> 55%, N={n_conf})")
else:
    print(f"  FALSIFIED (not > 55% or N too small)")

# ON-1b: outside confident subset, direction agreement is 48-52%
non_conf = mn_move[~mn_move["confident"]]
non_conf_agree = non_conf["dir_agree"].mean() if len(non_conf) > 0 else 0
print(f"\nON-1b: Non-confident direction agreement = {non_conf_agree:.3f} ({non_conf['dir_agree'].sum()}/{len(non_conf)})")
if 0.48 <= non_conf_agree <= 0.52:
    print(f"  CONFIRMED (48-52%)")
else:
    print(f"  FALSIFIED (outside 48-52%)")

print("\n\nDONE")
