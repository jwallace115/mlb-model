"""
ON-D6: Score Monday numbers on 2021-23 (ON-1b item 2d).

Fixes from ChatGPT audit c23e62419:
- Report BOTH full selected population and moving subset
- Side fixed at decision time
- Direction accuracy, mean signed movement, ATS at decision and close
- Pushes and missing counted separately
- Null: permutation that REBUILDS the confident subset after each shuffle
- LABEL: DEVELOPMENT RESULT — mechanics fitted on 2021-24; not out-of-sample

Pre-registered predictions (from Cowork's no-leak recompute):
  Direction on moving confident games: 71.8% -> expect 65-75%
  Mean movement: +1.37 -> expect +1.0 to +1.5
  ATS at the open: 50.8% -> expect 47-55%
"""
import os, sys
import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.join(os.path.dirname(__file__), "../..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from on_utils import compute_gap, handicap_to_home_margin
from build_manifest import verify_file_in_manifest


# ─── LOAD (with manifest integrity check) ────────────────────────────
mn_path = os.path.join(ROOT, "nfl/data/own/monday_numbers_2021_23.parquet")
verify_file_in_manifest(mn_path)
mn = pd.read_parquet(mn_path)
print(f"Monday numbers: {mn.shape}")
assert sorted(mn["season"].unique()) == [2021, 2022, 2023]


def wilson_interval(k, n, z=1.96):
    if n == 0:
        return 0.5, 0.0, 1.0
    p_hat = k / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return center, max(0, center - margin), min(1, center + margin)


# ─── CONFIDENT SUBSET (sign-corrected) ──────────────────────────────
# open_spread is already negated to home-margin convention (-bet365_spread_open)
has_open = mn["open_spread"].notna()
print(f"Has open spread: {has_open.sum()}/{len(mn)}")
mn_open = mn[has_open].copy()

mn_open["gap"] = mn_open["ours_m"] - mn_open["open_spread"]
mn_open["confident"] = (mn_open["gap"].abs() >= mn_open["err_m"]) & (mn_open["gap"].abs() >= 1.0)
print(f"\nConfident subset: {mn_open['confident'].sum()}/{len(mn_open)} "
      f"({100*mn_open['confident'].mean():.1f}%)")

# Side fixed at decision time
mn_open["side"] = np.where(mn_open["gap"] > 0, "home", "away")


# ─── DIRECTION + MOVEMENT (full and moving) ──────────────────────────
mn_open["close_minus_open"] = mn_open["spread_line"] - mn_open["open_spread"]
mn_open["ours_minus_open"] = mn_open["ours_m"] - mn_open["open_spread"]

# Moving subset: close != open
mn_open["moved"] = mn_open["close_minus_open"] != 0

# Signed movement: sign(gap) * (close - open)
mn_open["signed_move"] = np.sign(mn_open["gap"]) * mn_open["close_minus_open"]

# Direction agreement (defined on movers)
mn_move = mn_open[mn_open["moved"]].copy()
mn_move["dir_agree"] = (np.sign(mn_move["ours_minus_open"]) == np.sign(mn_move["close_minus_open"]))

# FULL population — includes unchanged lines
conf_all = mn_open[mn_open["confident"]].copy()
conf_move = mn_move[mn_move["confident"]].copy()
non_conf_move = mn_move[~mn_move["confident"]].copy()

print(f"\n{'='*60}")
print("DEVELOPMENT RESULT — mechanics fitted on 2021-24; not out-of-sample")
print(f"{'='*60}")

print(f"\n=== FULL SELECTED POPULATION (unchanged lines included) ===")
print(f"Total selected (confident): {len(conf_all)}")
print(f"  Moved: {conf_all['moved'].sum()}")
print(f"  Unchanged: {(~conf_all['moved']).sum()}")

print(f"\n=== MOVING SUBSET (direction defined only for movers) ===")
print(f"Games with close != open: {len(mn_move)}")
print(f"  Confident moving: {len(conf_move)}")
print(f"  Non-confident moving: {len(non_conf_move)}")

if len(conf_move) > 0:
    dir_pct = conf_move["dir_agree"].mean()
    dir_k = conf_move["dir_agree"].sum()
    p, lo, hi = wilson_interval(int(dir_k), len(conf_move))
    print(f"\nDirection (confident, moving): {dir_pct:.3f} ({int(dir_k)}/{len(conf_move)})")
    print(f"  Wilson 95%: [{lo:.3f}, {hi:.3f}]")

# All moving games
if len(mn_move) > 0:
    all_dir = mn_move["dir_agree"].mean()
    print(f"Direction (all, moving): {all_dir:.3f} ({mn_move['dir_agree'].sum()}/{len(mn_move)})")


# ─── MEAN SIGNED MOVEMENT ───────────────────────────────────────────
print(f"\n=== MEAN SIGNED MOVEMENT ===")
mean_move_all = conf_all["signed_move"].mean()
print(f"All selected (N={len(conf_all)}): +{mean_move_all:.3f} pts")
if len(conf_move) > 0:
    mean_move_moving = conf_move["signed_move"].mean()
    print(f"Moving subset (N={len(conf_move)}): +{mean_move_moving:.3f} pts")


# ─── ATS AT THE DECISION LINE AND AT THE CLOSE ──────────────────────
# For each confident game, the "pick" is the side fixed at decision time.
# ATS at decision line: actual margin vs open_spread, same side
# ATS at close: actual margin vs spread_line, same side

mn_open["actual_margin"] = mn["actual_margin"]

def ats_result(row, line_col):
    """Returns 'W', 'L', or 'P' (push)."""
    margin = row["actual_margin"]
    line = row[line_col]  # home-margin convention
    if row["side"] == "home":
        diff = margin - line
    else:
        diff = -margin + line  # away covers when margin < line
    if abs(diff) < 0.01:
        return "P"
    return "W" if diff > 0 else "L"


conf_all["ats_open"] = conf_all.apply(lambda r: ats_result(r, "open_spread"), axis=1)
conf_all["ats_close"] = conf_all.apply(lambda r: ats_result(r, "spread_line"), axis=1)

print(f"\n=== ATS AT DECISION LINE (same side) ===")
for label, ats_col in [("open", "ats_open"), ("close", "ats_close")]:
    w = (conf_all[ats_col] == "W").sum()
    l = (conf_all[ats_col] == "L").sum()
    p = (conf_all[ats_col] == "P").sum()
    total = w + l + p
    pct = w / (w + l) if (w + l) > 0 else 0
    print(f"  {label}: {w}W-{l}L-{p}P ({pct:.1%} excl pushes, N={total})")


# ─── BY SEASON ────────────────────────────────────────────────────────
print(f"\n=== BY SEASON ===")
for s in [2021, 2022, 2023]:
    sub_conf = conf_move[conf_move["season"] == s]
    sub_all = conf_all[conf_all["season"] == s]
    if len(sub_conf) > 0:
        p, lo, hi = wilson_interval(int(sub_conf["dir_agree"].sum()), len(sub_conf))
        print(f"  {s} dir (conf, moving): {sub_conf['dir_agree'].mean():.3f} "
              f"[{lo:.3f}, {hi:.3f}] N={len(sub_conf)}")
    if len(sub_all) > 0:
        print(f"  {s} selected: {len(sub_all)} (moved: {sub_all['moved'].sum()}, "
              f"unchanged: {(~sub_all['moved']).sum()})")


# ─── NON-CONFIDENT (context) ─────────────────────────────────────────
if len(non_conf_move) > 0:
    nc_dir = non_conf_move["dir_agree"].mean()
    print(f"\nNon-confident direction (moving): {nc_dir:.3f} "
          f"({non_conf_move['dir_agree'].sum()}/{len(non_conf_move)})")


# ─── NULL CONTROL (REBUILDS confident subset per shuffle) ─────────────
print(f"\n=== NULL CONTROL ===")
print("Permutation rebuilds confident subset after each shuffle (audit P6)")
np.random.seed(42)

null_dir_pcts = []
null_n_conf = []
N_PERMS = 1000

for _ in range(N_PERMS):
    shuffled = mn_open.copy()
    # Shuffle ours_m within each (season, week) group
    for (season, week), idx in shuffled.groupby(["season", "week"]).groups.items():
        vals = shuffled.loc[idx, "ours_m"].values.copy()
        np.random.shuffle(vals)
        shuffled.loc[idx, "ours_m"] = vals

    # REBUILD gap and confident subset from shuffled predictions
    shuffled["gap"] = shuffled["ours_m"] - shuffled["open_spread"]
    shuffled["confident"] = (
        (shuffled["gap"].abs() >= shuffled["err_m"]) &
        (shuffled["gap"].abs() >= 1.0)
    )
    shuffled["ours_minus_open"] = shuffled["ours_m"] - shuffled["open_spread"]

    # Direction agreement on confident movers
    sh_conf_move = shuffled[shuffled["confident"] & shuffled["moved"]]
    if len(sh_conf_move) > 0:
        sh_dir = (np.sign(sh_conf_move["ours_minus_open"]) ==
                  np.sign(sh_conf_move["close_minus_open"])).mean()
        null_dir_pcts.append(sh_dir)
        null_n_conf.append(len(sh_conf_move))
    else:
        null_dir_pcts.append(0.5)
        null_n_conf.append(0)

null_mean = np.mean(null_dir_pcts)
null_sd = np.std(null_dir_pcts)
real_dir = conf_move["dir_agree"].mean() if len(conf_move) > 0 else 0
z_score = (real_dir - null_mean) / null_sd if null_sd > 0 else 0

print(f"Real direction (conf, moving): {real_dir:.4f}")
print(f"Null: mean={null_mean:.4f}, SD={null_sd:.4f}")
print(f"Null denominator: mean={np.mean(null_n_conf):.0f}, "
      f"min={np.min(null_n_conf)}, max={np.max(null_n_conf)}")
print(f"Z-score: {z_score:.2f}")


# ─── PRE-REGISTRATION EVALUATION ─────────────────────────────────────
print(f"\n{'='*60}")
print("PRE-REGISTRATION EVALUATION")
print(f"{'='*60}")

if len(conf_move) > 0:
    dir_val = conf_move["dir_agree"].mean()
    print(f"\n1. Direction on moving confident: {dir_val:.1%}")
    print(f"   Pre-registered: 65-75% (from Cowork no-leak: 71.8%)")
    held = 0.65 <= dir_val <= 0.75
    print(f"   {'HELD' if held else 'DID NOT HOLD'}")

mean_move_sel = conf_all["signed_move"].mean()
print(f"\n2. Mean signed movement (all selected): +{mean_move_sel:.3f}")
print(f"   Pre-registered: +1.0 to +1.5 (from Cowork: +1.37)")
held_move = 1.0 <= mean_move_sel <= 1.5
print(f"   {'HELD' if held_move else 'DID NOT HOLD'}")

if len(conf_all) > 0:
    ats_open_w = (conf_all["ats_open"] == "W").sum()
    ats_open_l = (conf_all["ats_open"] == "L").sum()
    ats_open_pct = ats_open_w / (ats_open_w + ats_open_l) if (ats_open_w + ats_open_l) > 0 else 0
    print(f"\n3. ATS at open (same side, excl pushes): {ats_open_pct:.1%}")
    print(f"   Pre-registered: 47-55% (from Cowork: 50.8%)")
    held_ats = 0.47 <= ats_open_pct <= 0.55
    print(f"   {'HELD' if held_ats else 'DID NOT HOLD'}")

print(f"\n{'='*60}")
print("LABEL: DEVELOPMENT RESULT — mechanics fitted on 2021-24; not out-of-sample")
print(f"{'='*60}")
print("\nDONE")
