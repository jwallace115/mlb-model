#!/usr/bin/env python3
"""DA-3 Item 2: ONE-SHOT validation on 2024-25. DA-D13.

Invoked ONCE as: DA_PHASE=validation python3 discovery/run_validation.py
Reads 2024-25 prop rows. Tests H2 only. Not to be re-run.
"""
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "nfl_sim" / "defensive_archetypes"))
sys.path.insert(0, str(ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "discovery"))

from team_xwalk import canon
from da_guard import check_prop_seasons, DA_PHASE

# ── Guard ──
if DA_PHASE != "validation":
    raise SystemExit(f"HALT: DA_PHASE={DA_PHASE!r}, must be 'validation'. "
                     "Run as: DA_PHASE=validation python3 run_validation.py")

# ── Verify frozen cutoffs sha ──
# The cutoffs file sha: verify it has not been modified since the DA-1b rebuild.
# DA-D8 recorded sha 82106ae377c8de87 from in-memory json.dumps; the on-disk file
# re-serializes to 44136fa355b3678a. We verify the file is byte-stable.
CUTOFF_FILE_SHA = "973b6d54484e6773"  # sha256(file bytes)[:16]
cutoff_path = ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "labels" / "tercile_cutoffs_v1.json"
actual_sha = hashlib.sha256(cutoff_path.read_bytes()).hexdigest()[:16]
if actual_sha != CUTOFF_FILE_SHA:
    raise SystemExit(f"HALT: tercile cutoffs file sha {actual_sha} != {CUTOFF_FILE_SHA}")

LABELS_DIR = ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "labels"
OUT = ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "discovery"

import nflreadpy

MARKETS = {
    "player_receptions": "receptions",
    "player_reception_yds": "receiving_yards",
    "player_rush_yds": "rushing_yards",
    "player_rush_attempts": "carries",
    "player_pass_yds": "passing_yards",
    "player_pass_completions": "completions",
    "player_pass_attempts": "attempts",
}
BLEND_K = 4
N_SHUFFLE = 1000


def _implied(p):
    if p is None or pd.isna(p):
        return np.nan
    p = float(p)
    return 100 / (p + 100) if p > 0 else abs(p) / (abs(p) + 100)


def _roi(price, hit_rate, n):
    if n == 0 or pd.isna(price) or pd.isna(hit_rate):
        return np.nan
    p = float(price)
    payout = p / 100 if p > 0 else 100 / abs(p)
    return hit_rate * payout - (1 - hit_rate)


def clustered_z(residuals, game_ids):
    if len(residuals) < 5:
        return np.nan, np.nan, np.nan
    mean_r = np.mean(residuals)
    df_tmp = pd.DataFrame({"r": residuals, "g": game_ids})
    game_means = df_tmp.groupby("g")["r"].mean()
    n_clusters = len(game_means)
    if n_clusters < 3:
        return mean_r, np.nan, np.nan
    se = game_means.std() / np.sqrt(n_clusters)
    z = mean_r / se if se > 0 else np.nan
    return mean_r, se, z


def cross_defense_null(df_cell, label_col, residual_col, game_col, n_draws=N_SHUFFLE):
    zs = []
    for _ in range(n_draws):
        shuffled = df_cell.copy()
        for (s, w), idx in shuffled.groupby(["season", "week"]).groups.items():
            vals = shuffled.loc[idx, label_col].values.copy()
            np.random.shuffle(vals)
            shuffled.loc[idx, label_col] = vals
        top = shuffled[shuffled[label_col] == 3]
        if len(top) >= 5:
            _, _, z = clustered_z(top[residual_col].values, top[game_col].values)
            if pd.notna(z):
                zs.append(z)
    if not zs:
        return np.nan, np.nan
    return np.percentile(zs, 2.5), np.percentile(zs, 97.5)


def center_residuals(df, col):
    return df[col] - df.groupby(["season", "market_key", "position"])[col].transform("mean")


print("=" * 60)
print("DA-3 VALIDATION — ONE SHOT — 2024-25")
print("=" * 60)

# ── Load labels ──
labels = pd.concat([pd.read_parquet(LABELS_DIR / f"da_labels_{s}.parquet") for s in [2024, 2025]], ignore_index=True)
print(f"Labels: {len(labels)} rows (2024-25)")

# ── Load stats ──
stats_frames = []
for s in range(2023, 2026):
    st = nflreadpy.load_player_stats(seasons=[s], summary_level="week")
    if hasattr(st, "to_pandas"):
        st = st.to_pandas()
    stats_frames.append(st)
stats = pd.concat(stats_frames, ignore_index=True)

# ── Load rosters ──
rosters_frames = []
for s in range(2023, 2026):
    r = nflreadpy.load_rosters([s])
    if hasattr(r, "to_pandas"):
        r = r.to_pandas()
    rosters_frames.append(r)
rosters = pd.concat(rosters_frames, ignore_index=True)
pos_map = dict(zip(zip(rosters.gsis_id, rosters.season.astype(int)), rosters.position))

# ── Load schedules ──
sched_frames = []
for s in [2024, 2025]:
    sc = nflreadpy.load_schedules([s])
    if hasattr(sc, "to_pandas"):
        sc = sc.to_pandas()
    sched_frames.append(sc)
sched = pd.concat(sched_frames, ignore_index=True)

# ── Load 2024-25 props ──
prop_frames = []
for f in sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2024/month=*/data_*.parquet"))) + \
         sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2025/month=*/data_*.parquet"))) + \
         sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2026/month=01/data_*.parquet"))) + \
         sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2026/month=02/data_*.parquet"))):
    prop_frames.append(pd.read_parquet(f))
props = pd.concat(prop_frames, ignore_index=True)
ct = pd.to_datetime(props["commence_time"], utc=True, errors="coerce")
props["nfl_season"] = np.where(ct.dt.month >= 9, ct.dt.year, ct.dt.year - 1).astype(int)
props = props[props.nfl_season.isin([2024, 2025])]
check_prop_seasons(props)  # should pass with DA_PHASE=validation
print(f"Props 2024-25: {len(props)}")

# ── Close lines ──
props["_ct"] = pd.to_datetime(props["commence_time"], utc=True, errors="coerce")
props["_lu"] = pd.to_datetime(props["last_update"], utc=True, errors="coerce")
props_pre = props[props["_lu"] < props["_ct"]].copy()
by_book = props_pre.sort_values("_lu").groupby(
    ["event_id", "market_key", "player_name", "bookmaker"]).agg(
    line=("line", "last"), over_price=("over_price", "last"),
    under_price=("under_price", "last")).reset_index()

close_rows = []
for (eid, mk, pn), g in by_book.groupby(["event_id", "market_key", "player_name"]):
    dk = g[g.bookmaker == "draftkings"]
    if len(dk) and pd.notna(dk.iloc[0]["line"]):
        close_rows.append({"event_id": eid, "market_key": mk, "player_name": pn,
                           "close_line": float(dk.iloc[0]["line"]),
                           "close_over_price": dk.iloc[0]["over_price"],
                           "close_under_price": dk.iloc[0]["under_price"],
                           "close_source": "draftkings"})
    elif len(g) >= 3:
        close_rows.append({"event_id": eid, "market_key": mk, "player_name": pn,
                           "close_line": float(g["line"].median()),
                           "close_over_price": np.nan, "close_under_price": np.nan,
                           "close_source": f"median_{len(g)}_books"})
closes = pd.DataFrame(close_rows)
print(f"Close lines 2024-25: {len(closes)}")

# ── Baselines (vectorized) ──
from build_discovery_table import _compute_baselines
baselines = _compute_baselines(stats, {2024, 2025})
print(f"Baselines: {len(baselines)}")

# ── Build rows ──
stats_24_25 = stats[stats.season.isin([2024, 2025])].copy()
stats_24_25["_team"] = stats_24_25["team"].apply(canon)
stats_24_25["_opp"] = stats_24_25["opponent_team"].apply(canon)

mk = "player_receptions"
sc = "receptions"
sub = stats_24_25[stats_24_25[sc].notna()][
    ["player_id", "season", "week", "game_id", sc, "player_display_name", "_team", "_opp"]].copy()
sub.rename(columns={sc: "actual"}, inplace=True)
sub["market_key"] = mk
sub["stat_col"] = sc

bl = baselines[baselines.stat_col == sc][["player_id", "season", "week", "baseline", "t2_residual"]]
sub = sub.merge(bl, on=["player_id", "season", "week"], how="left")
sub = sub[sub.baseline.notna()]

sub["position"] = [pos_map.get((pid, int(s)), "") for pid, s in zip(sub.player_id, sub.season)]

# Opponent label
label_cols = [c for c in labels.columns if c.startswith("f") or c == "n_games_into_label"]
opp_labels = labels[["season", "week", "defense"] + label_cols].copy()
opp_labels.rename(columns={c: f"opp_{c}" for c in label_cols}, inplace=True)
sub = sub.merge(opp_labels, left_on=["season", "week", "_opp"],
                right_on=["season", "week", "defense"], how="left")

# T1: close line
sub = sub.merge(closes.rename(columns={"player_name": "player_display_name"}),
                on=["market_key", "player_display_name"], how="left")
sub["t1_residual"] = sub["actual"] - sub["close_line"]
sub["over_hit"] = np.where(sub.actual > sub.close_line, 1,
                            np.where(sub.actual < sub.close_line, 0, np.nan))

# RB only
df = sub[sub.position.isin(["RB", "FB"])].copy()
print(f"\nH2 validation rows (RB receptions): {len(df)}")

df.to_parquet(OUT / "da3_rows_2024_25.parquet", index=False)

# ── Run H2 ──
label_col = "opp_f1_target_share_rb_tercile"
df_labelled = df[df[label_col].notna()].copy()
top = df_labelled[df_labelled[label_col] == 3]
rest = df_labelled[df_labelled[label_col] != 3]

print(f"Top tercile: {len(top)}, rest: {len(rest)}")

# Centered T1 residual
t1_rows = top[top.t1_residual.notna()]
if len(t1_rows) >= 5:
    t1_rows = t1_rows.copy()
    df_for_center = df_labelled[df_labelled.t1_residual.notna()].copy()
    df_for_center["t1_centered"] = center_residuals(df_for_center, "t1_residual")
    t1_top = df_for_center[df_for_center[label_col] == 3]

    t1c_mean, t1c_se, t1c_z = clustered_z(t1_top["t1_centered"].values, t1_top["game_id"].values)
    t1_mean, t1_se, t1_z = clustered_z(t1_rows["t1_residual"].values, t1_rows["game_id"].values)
    t1_median = t1_rows["t1_residual"].median()
    t1_oh = t1_rows["over_hit"].dropna().mean()

    # Wilson interval for over-hit
    from scipy.stats import norm
    n_oh = int(t1_rows["over_hit"].notna().sum())
    p_oh = t1_oh
    z_ci = 1.96
    denom = 1 + z_ci ** 2 / n_oh
    center = (p_oh + z_ci ** 2 / (2 * n_oh)) / denom
    margin = z_ci * np.sqrt(p_oh * (1 - p_oh) / n_oh + z_ci ** 2 / (4 * n_oh ** 2)) / denom
    oh_lo, oh_hi = center - margin, center + margin
else:
    t1c_mean = t1c_z = t1_mean = t1_z = t1_median = t1_oh = np.nan
    oh_lo = oh_hi = np.nan
    n_oh = 0

# DK ROI
dk_op = t1_rows["close_over_price"].median() if len(t1_rows) else np.nan
dk_up = t1_rows["close_under_price"].median() if len(t1_rows) else np.nan
dk_over_roi = _roi(dk_op, t1_oh, len(t1_rows)) if pd.notna(dk_op) and pd.notna(t1_oh) else np.nan
dk_under_roi = _roi(dk_up, 1 - t1_oh, len(t1_rows)) if pd.notna(dk_up) and pd.notna(t1_oh) else np.nan
triage_over = _roi(-110, t1_oh, len(t1_rows)) if pd.notna(t1_oh) else np.nan
triage_under = _roi(-110, 1 - t1_oh, len(t1_rows)) if pd.notna(t1_oh) else np.nan

# N1: cross-defense null
np.random.seed(42)
n1_lo, n1_hi = cross_defense_null(df_labelled, label_col, "t1_residual",
                                   "game_id") if len(df_labelled) >= 20 else (np.nan, np.nan)

# N2: own-defense
n2_mean, n2_se, n2_z = clustered_z(rest["t1_residual"].dropna().values,
                                     rest.loc[rest.t1_residual.notna(), "game_id"].values) if len(rest) >= 20 else (np.nan, np.nan, np.nan)

# Breakouts
report = ["# DA-3 VALIDATION — ONE-SHOT — not to be re-run\n"]
report.append(f"H2_rb_funnel: RB receptions vs top f1_target_share_rb, direction > 0")
report.append(f"Cutoffs sha: {CUTOFF_FILE_SHA} (verified)")
report.append(f"\n## Main result")
report.append(f"n_top={len(top)}, n_t1={len(t1_rows)}")
report.append(f"T1 raw:      mean={t1_mean:.4f} z={t1_z:.2f}" if pd.notna(t1_z) else "T1: insufficient data")
report.append(f"T1 centered: mean={t1c_mean:.4f} z={t1c_z:.2f}" if pd.notna(t1c_z) else "T1 centered: n/a")
report.append(f"T1 median:   {t1_median:.4f}" if pd.notna(t1_median) else "")
report.append(f"Over-hit:    {t1_oh:.3f} Wilson [{oh_lo:.3f}, {oh_hi:.3f}] n={n_oh}" if pd.notna(t1_oh) else "")
report.append(f"DK ROI:      over={dk_over_roi:.4f} under={dk_under_roi:.4f} sum={dk_over_roi+dk_under_roi:.4f}" if pd.notna(dk_over_roi) and pd.notna(dk_under_roi) else "DK ROI: n/a")
report.append(f"Triage -110: over={triage_over:.4f} under={triage_under:.4f}" if pd.notna(triage_over) else "")
report.append(f"N1 cross-defense band: [{n1_lo:.2f}, {n1_hi:.2f}]" if pd.notna(n1_lo) else "N1: n/a")
report.append(f"N2 own-defense z:      {n2_z:.2f}" if pd.notna(n2_z) else "N2: n/a")

# Breakouts
report.append(f"\n## Breakouts")
for by_col, by_label in [("season", "season"), ("position", "position")]:
    if by_col in t1_rows.columns:
        for val, g in t1_rows.groupby(by_col):
            if len(g) >= 5:
                m, _, z = clustered_z(g.t1_residual.values, g.game_id.values)
                oh = g.over_hit.dropna().mean()
                report.append(f"  {by_label}={val}: n={len(g)} mean={m:.3f} z={z:.2f} oh={oh:.3f}")

# Top 3 defenses share
if len(t1_rows) >= 10:
    by_def = t1_rows.groupby("_opp")["t1_residual"].agg(["mean", "count"]).sort_values("mean", ascending=False)
    top3_share = by_def.head(3)["count"].sum() / len(t1_rows)
    report.append(f"\n  Top 3 defenses share of effect: {top3_share:.1%}")
    report.append(f"  Top 3: {by_def.head(3).to_dict()}")

# Save
cell_result = {
    "cell": "H2_rb_funnel", "n_top": len(top), "n_t1": len(t1_rows),
    "t1_mean": t1_mean, "t1_z": t1_z, "t1_centered_mean": t1c_mean, "t1_centered_z": t1c_z,
    "t1_median": t1_median, "t1_over_hit": t1_oh, "oh_wilson_lo": oh_lo, "oh_wilson_hi": oh_hi,
    "dk_over_roi": dk_over_roi, "dk_under_roi": dk_under_roi,
    "triage_over": triage_over, "triage_under": triage_under,
    "n1_lo": n1_lo, "n1_hi": n1_hi, "n2_z": n2_z,
}
pd.DataFrame([cell_result]).to_parquet(OUT / "da3_cells.parquet", index=False)
(OUT / "DA3_VALIDATION.md").write_text("\n".join(report) + "\n")

print("\n" + "\n".join(report))
print(f"\nSaved: da3_rows_2024_25.parquet, da3_cells.parquet, DA3_VALIDATION.md")
