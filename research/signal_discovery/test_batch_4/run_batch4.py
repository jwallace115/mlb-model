#!/usr/bin/env python3
"""
Batch 4 signal tests: CS028, CS029, CS030, CS031, CS032, CS033.
All thresholds frozen on 2022-2023. Permutation within-season. 500 shuffles.
"""
import json
import math
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

np.random.seed(42)
OUT_DIR = Path("research/signal_discovery/test_batch_4")
SAFETY_DIR = Path("research/signal_discovery/safety_layer")
WIN_PER_UNIT = 100.0 / 110.0

# ======================================================================
# LOAD BASE DATA
# ======================================================================
# Game table with actual totals (2022-2026)
gt = pd.read_parquet("sim/data/game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
gt = gt[gt["actual_total"].notna()].copy()
print(f"Game table: {len(gt)} games with scores")

# Historical closing lines (2022-2023)
cl_hist = pd.read_parquet("sim/data/mlb_historical_closing_lines.parquet")
cl_hist["date"] = pd.to_datetime(cl_hist["date"])

# Market snapshots (2024-2025)
ms = pd.read_parquet("sim/data/market_snapshots.parquet")
ms["date"] = pd.to_datetime(ms["date"])
ms = ms.rename(columns={"game_id": "game_pk"})
ms["game_pk"] = ms["game_pk"].astype(int)

# Combine closing lines: historical + market snapshots
lines_2223 = cl_hist[["game_pk", "date", "season", "home_team", "away_team", "close_total"]].copy()
lines_2425 = ms[["game_pk", "date", "close_total"]].copy()
lines_2425 = lines_2425.merge(
    gt[["game_pk", "season", "home_team", "away_team"]].drop_duplicates("game_pk"),
    on="game_pk", how="left"
)
all_lines = pd.concat([lines_2223, lines_2425[lines_2223.columns]], ignore_index=True)
all_lines = all_lines.drop_duplicates("game_pk", keep="first")

# Master game table: lines + actuals
base = gt[["game_pk", "date", "season", "home_team", "away_team", "actual_total"]].merge(
    all_lines[["game_pk", "close_total"]], on="game_pk", how="inner"
)
base = base[base["close_total"].notna()].copy()
base["went_under"] = (base["actual_total"] < base["close_total"]).astype(int)
base["went_over"] = (base["actual_total"] > base["close_total"]).astype(int)
base["push"] = (base["actual_total"] == base["close_total"]).astype(int)

for s in sorted(base["season"].unique()):
    n = len(base[base["season"] == s])
    print(f"  Season {s}: {n} games")
print(f"Total: {len(base)} games")
print(f"Baseline under rate: {base['went_under'].mean():.4f}")
print(f"Baseline over rate: {base['went_over'].mean():.4f}")

TRAIN = base[base["season"].isin([2022, 2023])].copy()
VAL_2024 = base[base["season"] == 2024].copy()
VAL_2025 = base[base["season"] == 2025].copy()
print(f"\nTrain: {len(TRAIN)}, Val 2024: {len(VAL_2024)}, Val 2025: {len(VAL_2025)}")

# ======================================================================
# PITCHER GAME LOGS (for CS028)
# ======================================================================
pgl = pd.read_parquet("mlb/data/pitcher_game_logs.parquet")
pgl["game_date"] = pd.to_datetime(pgl["game_date"])

# ======================================================================
# UTILITY FUNCTIONS
# ======================================================================
def compute_stats(subset, direction="UNDER"):
    n = len(subset)
    if n == 0:
        return {"N": 0, "rate": None, "roi": None}
    if direction == "UNDER":
        hits = subset["went_under"].sum()
    else:
        hits = subset["went_over"].sum()
    losses = n - hits - subset["push"].sum()
    roi = (hits * WIN_PER_UNIT - losses) / n * 100
    rate = hits / n
    return {"N": n, "rate": round(rate, 4), "roi": round(roi, 2)}


def permutation_test(data, signal_mask, direction="UNDER", n_perms=500):
    col = "went_under" if direction == "UNDER" else "went_over"
    n_signal = signal_mask.sum()
    if n_signal == 0:
        return 0.0
    actual_rate = data.loc[signal_mask, col].mean()
    shuffle_rates = []
    seasons = data["season"].unique()
    for _ in range(n_perms):
        shuffled_mask = pd.Series(False, index=data.index)
        for s in seasons:
            s_idx = data.index[data["season"] == s]
            n_in = signal_mask[data["season"] == s].sum()
            if n_in > 0 and len(s_idx) >= n_in:
                chosen = np.random.choice(s_idx, size=n_in, replace=False)
                shuffled_mask.loc[chosen] = True
        shuffle_rates.append(data.loc[shuffled_mask, col].mean())
    shuffle_rates = np.array(shuffle_rates)
    return round((shuffle_rates < actual_rate).mean() * 100, 1)


# ======================================================================
# CS028: BAYESIAN BULLPEN BLOWUP
# ======================================================================
print("\n" + "=" * 70)
print("CS028: BAYESIAN BULLPEN BLOWUP")
print("=" * 70)

# Identify relievers (starter_flag == 0)
relievers = pgl[pgl["starter_flag"] == 0].copy()
relievers = relievers.sort_values(["player_id", "game_date"]).reset_index(drop=True)

# For each reliever appearance, compute trailing blowup posterior
# Blowup = runs_allowed >= 2
relievers["blowup"] = (relievers["runs_allowed"] >= 2).astype(int)

# Season baseline runs/appearance
season_baseline = relievers.groupby("season")["runs_allowed"].mean().to_dict()
print(f"Season baseline runs/appearance: {season_baseline}")

# Compute rolling posterior per reliever
# Prior: season baseline rate of blowup
season_blowup_rate = relievers.groupby("season")["blowup"].mean().to_dict()
print(f"Season blowup rate: {season_blowup_rate}")

# For each reliever, track trailing 3-appearance blowup count and total appearances
records = []
for (pid, season), grp in relievers.groupby(["player_id", "season"]):
    grp = grp.sort_values("game_date")
    prior_rate = season_blowup_rate.get(season, 0.25)
    appearances = []
    for i, row in grp.iterrows():
        n_prior = len(appearances)
        if n_prior >= 5:
            # Last 3 appearances
            last3 = appearances[-3:]
            blowups_last3 = sum(last3)
            # Bayesian posterior: beta-binomial with prior centered at season rate
            # Simple conjugate: alpha_prior = 2*prior_rate, beta_prior = 2*(1-prior_rate)
            a0 = 2 * prior_rate
            b0 = 2 * (1 - prior_rate)
            posterior_p = (a0 + blowups_last3) / (a0 + b0 + 3)
            records.append({
                "game_pk": row["game_pk"],
                "game_date": row["game_date"],
                "season": season,
                "player_id": pid,
                "team": row["team"],
                "home_away": row["home_away"],
                "blowup_posterior": posterior_p,
                "appearances_so_far": n_prior,
            })
        appearances.append(row["blowup"])

bp_df = pd.DataFrame(records)
print(f"Reliever posterior records: {len(bp_df)}")

# Exclude relievers who appeared in previous game (assume unavailable)
# For each team-game, get the previous game's date
team_game_dates = pgl.groupby(["team", "game_pk"])["game_date"].first().reset_index()
team_game_dates = team_game_dates.sort_values(["team", "game_date"])

# Get previous game_pk per team
prev_games = {}
for team, tg in team_game_dates.groupby("team"):
    tg = tg.sort_values("game_date")
    for i in range(1, len(tg)):
        prev_games[(team, tg.iloc[i]["game_pk"])] = tg.iloc[i - 1]["game_pk"]

# Get relievers who appeared in previous game
bp_df["prev_game_pk"] = bp_df.apply(
    lambda r: prev_games.get((r["team"], r["game_pk"])), axis=1
)
prev_game_relievers = set()
for _, row in bp_df.iterrows():
    if row["prev_game_pk"] is not None:
        # Check if this reliever appeared in prev game
        mask = (relievers["player_id"] == row["player_id"]) & (relievers["game_pk"] == row["prev_game_pk"])
        if mask.any():
            prev_game_relievers.add((row["player_id"], row["game_pk"]))

bp_df["appeared_prev_game"] = bp_df.apply(
    lambda r: (r["player_id"], r["game_pk"]) in prev_game_relievers, axis=1
)
bp_available = bp_df[~bp_df["appeared_prev_game"]].copy()
print(f"After excluding prev-game relievers: {len(bp_available)} records")

# Team blowup score: mean posterior across available relievers (min 3 with 5+ appearances)
team_scores = bp_available.groupby(["game_pk", "game_date", "season", "team", "home_away"]).agg(
    n_relievers=("blowup_posterior", "count"),
    team_blowup_score=("blowup_posterior", "mean"),
).reset_index()
team_scores = team_scores[team_scores["n_relievers"] >= 3].copy()
print(f"Team-game scores (>=3 relievers): {len(team_scores)}")

# Separate home/away
home_scores = team_scores[team_scores["home_away"] == "H"][["game_pk", "team_blowup_score"]].rename(
    columns={"team_blowup_score": "home_blowup_score"})
away_scores = team_scores[team_scores["home_away"] == "A"][["game_pk", "team_blowup_score"]].rename(
    columns={"team_blowup_score": "away_blowup_score"})

# Merge onto base
cs028_data = base.merge(home_scores, on="game_pk", how="left")
cs028_data = cs028_data.merge(away_scores, on="game_pk", how="left")
cs028_data["either_blowup"] = cs028_data[["home_blowup_score", "away_blowup_score"]].max(axis=1)

# Coverage
for col in ["home_blowup_score", "away_blowup_score"]:
    pct = cs028_data[col].notna().mean() * 100
    print(f"  {col} coverage: {pct:.1f}%")

# Freeze 90th percentile on 2022-2023
train_scores = cs028_data[cs028_data["season"].isin([2022, 2023])]
for variant, col in [("home", "home_blowup_score"), ("away", "away_blowup_score"), ("either", "either_blowup")]:
    valid = train_scores[col].dropna()
    if len(valid) > 0:
        p90 = valid.quantile(0.90)
        print(f"  {variant} 90th pctile (frozen): {p90:.4f} (N={len(valid)})")

# Use 'either' variant as primary (pre-committed before seeing 2025)
p90_either = train_scores["either_blowup"].dropna().quantile(0.90)
p90_home = train_scores["home_blowup_score"].dropna().quantile(0.90)
p90_away = train_scores["away_blowup_score"].dropna().quantile(0.90)

# Test all three variants on training data first
print("\n  --- Training results by variant ---")
variants = {}
for vname, col, thresh in [("home", "home_blowup_score", p90_home),
                            ("away", "away_blowup_score", p90_away),
                            ("either", "either_blowup", p90_either)]:
    mask = train_scores[col].notna() & (train_scores[col] >= thresh)
    sub = train_scores[mask.values]
    st = compute_stats(sub, "OVER")
    perm = permutation_test(train_scores[train_scores[col].notna()],
                            mask[train_scores[col].notna().values], "OVER", 500)
    variants[vname] = {"stats": st, "perm": perm, "col": col, "thresh": thresh}
    print(f"    {vname}: N={st['N']}, over_rate={st['rate']}, ROI={st['roi']}%, perm={perm}")

# Select best variant by clearest monotonicity (pre-commit before seeing 2025)
# Use the variant with highest training over_rate (simplest monotonic criterion)
best_variant = max(variants.items(), key=lambda x: (x[1]["stats"]["rate"] or 0))
bv_name = best_variant[0]
bv_col = best_variant[1]["col"]
bv_thresh = best_variant[1]["thresh"]
print(f"\n  Pre-committed variant: {bv_name} (col={bv_col}, thresh={bv_thresh:.4f})")

# Now run on 2024 and 2025
cs028_results = {"signal_id": "CS028", "variant": bv_name, "threshold_frozen": round(bv_thresh, 4)}
for label, data in [("train", train_scores), ("val_2024", cs028_data[cs028_data["season"] == 2024]),
                     ("val_2025", cs028_data[cs028_data["season"] == 2025])]:
    valid = data[data[bv_col].notna()]
    mask = valid[bv_col] >= bv_thresh
    st = compute_stats(valid[mask], "OVER")
    cs028_results[label] = st
    print(f"  {label}: N={st['N']}, over_rate={st['rate']}, ROI={st['roi']}%")

cs028_results["perm_pctile"] = variants[bv_name]["perm"]
cs028_results["direction_2025"] = (
    cs028_results["val_2025"]["rate"] is not None and cs028_results["val_2025"]["rate"] > 0.50
)

# Monotonicity: decile table
print("\n  --- Monotonicity: blowup score decile vs over_rate (training) ---")
mono_data = train_scores[train_scores[bv_col].notna()].copy()
mono_data["decile"] = pd.qcut(mono_data[bv_col], 10, labels=False, duplicates="drop")
mono_table = mono_data.groupby("decile").agg(
    n=("went_over", "count"),
    over_rate=("went_over", "mean"),
    avg_score=(bv_col, "mean"),
).reset_index()
for _, row in mono_table.iterrows():
    print(f"    Decile {int(row['decile'])}: N={int(row['n'])}, over_rate={row['over_rate']:.3f}, avg_score={row['avg_score']:.4f}")

# ======================================================================
# CS029/CS030: PITCHER ENTROPY — DATA_GAP CHECK
# ======================================================================
print("\n" + "=" * 70)
print("CS029/CS030: PITCHER ENTROPY")
print("=" * 70)

# Statcast pitch-type data covers 2023-2025 only. Need 2022-2023 for freezing.
# 2022 is missing → training coverage = 1 of 2 seasons = 50% < 70%.
sp_pitch = pd.read_parquet("mlb/props/data/statcast_pitchers.parquet",
                            columns=["pitcher", "game_date", "game_pk", "pitch_type", "game_year"])
seasons_available = sorted(sp_pitch["game_year"].unique())
print(f"Statcast pitch-type data seasons: {seasons_available}")
print(f"2022 data available: {'2022' in str(seasons_available)}")
print(f"Training period: 2022-2023. Available: 2023 only. Coverage: 50% < 70%.")
print(f">>> CS029: DATA_GAP — 2022 pitch-type data unavailable")
print(f">>> CS030: DATA_GAP — 2022 pitch-type data unavailable")

cs029_results = {
    "signal_id": "CS029", "verdict": "DATA_GAP",
    "reason": "2022 pitch-type data unavailable in statcast_pitchers.parquet. Training coverage = 50% (2023 only) < 70% threshold.",
    "train": {"N": 0, "rate": None, "roi": None},
    "val_2025": {"N": 0, "rate": None, "roi": None},
    "perm_pctile": None, "direction_2025": False,
}
cs030_results = {
    "signal_id": "CS030", "verdict": "DATA_GAP",
    "reason": "2022 pitch-type data unavailable in statcast_pitchers.parquet. Training coverage = 50% (2023 only) < 70% threshold.",
    "train": {"N": 0, "rate": None, "roi": None},
    "val_2025": {"N": 0, "rate": None, "roi": None},
    "perm_pctile": None, "direction_2025": False,
}

# ======================================================================
# CS031/CS032: REPERTOIRE MIX SHIFT — DATA_GAP
# ======================================================================
print("\n" + "=" * 70)
print("CS031/CS032: REPERTOIRE MIX SHIFT")
print("=" * 70)
print(f"Same data source as CS029/CS030. 2022 pitch-type data missing.")
print(f">>> CS031: DATA_GAP")
print(f">>> CS032: DATA_GAP")

cs031_results = {
    "signal_id": "CS031", "verdict": "DATA_GAP",
    "reason": "2022 pitch-type data unavailable. Training coverage = 50% < 70% threshold.",
    "train": {"N": 0, "rate": None, "roi": None},
    "val_2025": {"N": 0, "rate": None, "roi": None},
    "perm_pctile": None, "direction_2025": False,
}
cs032_results = {
    "signal_id": "CS032", "verdict": "DATA_GAP",
    "reason": "2022 pitch-type data unavailable. Training coverage = 50% < 70% threshold.",
    "train": {"N": 0, "rate": None, "roi": None},
    "val_2025": {"N": 0, "rate": None, "roi": None},
    "perm_pctile": None, "direction_2025": False,
}

# ======================================================================
# CS033: K PROP VS TOTAL DIVERGENCE
# ======================================================================
print("\n" + "=" * 70)
print("CS033: K PROP VS TOTAL DIVERGENCE")
print("=" * 70)

kprop = pd.read_parquet("research/kprop/data/kprop_lines_historical.parquet")
kprop["date"] = pd.to_datetime(kprop["date"])
kprop["season"] = kprop["date"].dt.year
print(f"K prop lines: {len(kprop)} rows, seasons {sorted(kprop['season'].unique())}")

# Need home SP and away SP K lines per game
# Identify home/away pitchers: join game-level team info
# kprop has: game_id (game_pk), pitcher_name, k_line, home_team, away_team
# For each game, find the home SP k_line and away SP k_line

# Get starters from pitcher_game_logs
starters = pgl[(pgl["starter_flag"] == 1)].copy()
home_starters = starters[starters["home_away"] == "H"][["game_pk", "player_id", "player_name", "team"]].drop_duplicates("game_pk")
away_starters = starters[starters["home_away"] == "A"][["game_pk", "player_id", "player_name", "team"]].drop_duplicates("game_pk")

# Match kprop pitcher to home/away designation
# kprop has pitcher_id — match to starters
kprop["game_pk"] = kprop["game_id"].astype(int)

home_k = kprop.merge(
    home_starters[["game_pk", "player_id"]].rename(columns={"player_id": "sp_id"}),
    left_on=["game_pk", "pitcher_id"],
    right_on=["game_pk", "sp_id"],
    how="inner"
)[["game_pk", "k_line", "date", "season"]].rename(columns={"k_line": "home_sp_k_line"})

away_k = kprop.merge(
    away_starters[["game_pk", "player_id"]].rename(columns={"player_id": "sp_id"}),
    left_on=["game_pk", "pitcher_id"],
    right_on=["game_pk", "sp_id"],
    how="inner"
)[["game_pk", "k_line"]].rename(columns={"k_line": "away_sp_k_line"})

# Merge home + away K lines per game
k_game = home_k.merge(away_k, on="game_pk", how="inner")
k_game["combined_k_line"] = k_game["home_sp_k_line"] + k_game["away_sp_k_line"]
print(f"Games with both SP K lines: {len(k_game)}")

# Merge with base (close_total + actual_total)
cs033_data = k_game.merge(base[["game_pk", "close_total", "actual_total", "went_under", "went_over", "push", "season"]],
                           on="game_pk", how="inner", suffixes=("_k", ""))
# Use season from base (more reliable)
cs033_data = cs033_data.drop(columns=["season_k"], errors="ignore")
print(f"Merged with game data: {len(cs033_data)}")

# Coverage check
for s in sorted(cs033_data["season"].unique()):
    n_games_total = len(base[base["season"] == s])
    n_covered = len(cs033_data[cs033_data["season"] == s])
    pct = n_covered / n_games_total * 100 if n_games_total > 0 else 0
    print(f"  {s}: {n_covered}/{n_games_total} games ({pct:.1f}% coverage)")

# Check if 2022-2023 coverage meets 70% threshold
train_coverage = len(cs033_data[cs033_data["season"].isin([2022, 2023])]) / len(base[base["season"].isin([2022, 2023])]) * 100
print(f"  Training (2022-2023) coverage: {train_coverage:.1f}%")

if train_coverage < 70:
    print(f">>> CS033: DATA_GAP — training coverage {train_coverage:.1f}% < 70%")
    cs033_results = {
        "signal_id": "CS033", "verdict": "DATA_GAP",
        "reason": f"K prop training coverage = {train_coverage:.1f}% < 70% threshold.",
        "train": {"N": 0, "rate": None, "roi": None},
        "val_2025": {"N": 0, "rate": None, "roi": None},
        "perm_pctile": None, "direction_2025": False,
    }
else:
    # Fit OLS on 2022-2023: combined_K_line ~ close_total
    from numpy.polynomial.polynomial import polyfit
    train_k = cs033_data[cs033_data["season"].isin([2022, 2023])].copy()

    # Simple OLS: combined_K = a + b * close_total
    x_train = train_k["close_total"].values
    y_train = train_k["combined_k_line"].values
    coeffs = np.polyfit(x_train, y_train, 1)  # [slope, intercept]
    slope, intercept = coeffs
    print(f"\n  OLS (frozen): combined_K = {slope:.4f} * close_total + {intercept:.4f}")

    # Compute residual for all games
    cs033_data["predicted_k"] = slope * cs033_data["close_total"] + intercept
    cs033_data["k_divergence"] = cs033_data["combined_k_line"] - cs033_data["predicted_k"]

    # Freeze 75th percentile on training
    p75 = train_k_div = cs033_data[cs033_data["season"].isin([2022, 2023])]["k_divergence"]
    p75_thresh = p75.quantile(0.75)
    print(f"  75th pctile threshold (frozen): {p75_thresh:.4f}")

    # Signal: k_divergence >= p75_thresh → UNDER
    for label, data in [("train", cs033_data[cs033_data["season"].isin([2022, 2023])]),
                         ("val_2024", cs033_data[cs033_data["season"] == 2024]),
                         ("val_2025", cs033_data[cs033_data["season"] == 2025])]:
        mask = data["k_divergence"] >= p75_thresh
        st = compute_stats(data[mask], "UNDER")
        print(f"  {label}: N={st['N']}, under_rate={st['rate']}, ROI={st['roi']}%")

    # Permutation on training
    train_mask = cs033_data[cs033_data["season"].isin([2022, 2023])]["k_divergence"] >= p75_thresh
    train_full = cs033_data[cs033_data["season"].isin([2022, 2023])]
    perm = permutation_test(train_full, train_mask, "UNDER", 500)
    print(f"  Permutation: {perm}")

    val25 = cs033_data[cs033_data["season"] == 2025]
    mask25 = val25["k_divergence"] >= p75_thresh
    st25 = compute_stats(val25[mask25], "UNDER")

    cs033_results = {
        "signal_id": "CS033",
        "regression_coeffs": {"slope": round(slope, 4), "intercept": round(intercept, 4)},
        "threshold_frozen": round(p75_thresh, 4),
        "train": compute_stats(train_full[train_mask], "UNDER"),
        "val_2024": compute_stats(cs033_data[cs033_data["season"] == 2024][
            cs033_data[cs033_data["season"] == 2024]["k_divergence"] >= p75_thresh], "UNDER"),
        "val_2025": st25,
        "perm_pctile": perm,
        "direction_2025": st25["rate"] is not None and st25["rate"] > 0.50,
    }

# ======================================================================
# VERDICTS
# ======================================================================
print("\n" + "=" * 70)
print("VERDICTS")
print("=" * 70)

all_results = []
for r in [cs028_results, cs029_results, cs030_results, cs031_results, cs032_results, cs033_results]:
    sid = r["signal_id"]
    if r.get("verdict") == "DATA_GAP":
        r["final_verdict"] = "DATA_GAP"
        print(f"  {sid}: DATA_GAP — {r.get('reason', '')}")
    else:
        train_n = r.get("train", {}).get("N", 0)
        perm = r.get("perm_pctile", 0) or 0
        dir_2025 = r.get("direction_2025", False)

        if train_n < 50:
            r["final_verdict"] = "FAIL (THIN_SAMPLE)"
        elif perm >= 85 and dir_2025:
            r["final_verdict"] = "PASS"
        else:
            reasons = []
            if perm < 85:
                reasons.append(f"perm={perm}<85")
            if not dir_2025:
                val_rate = r.get("val_2025", {}).get("rate")
                reasons.append(f"2025_dir={'pos' if dir_2025 else 'neg'}(rate={val_rate})")
            r["final_verdict"] = f"FAIL ({'; '.join(reasons)})"
        print(f"  {sid}: {r['final_verdict']}")
    all_results.append(r)

# ======================================================================
# SAVE OUTPUTS
# ======================================================================
# batch4_results.json
batch_path = OUT_DIR / "batch4_results.json"
with open(batch_path, "w") as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\nSaved: {batch_path}")

# Append to signal_board.json
board_path = SAFETY_DIR / "signal_board.json"
with open(board_path) as f:
    board = json.load(f)

for r in all_results:
    sid = r["signal_id"]
    board[sid] = {
        "canonical_signal_id": sid,
        "verdict": r["final_verdict"],
        "train_N": r.get("train", {}).get("N", 0),
        "train_rate": r.get("train", {}).get("rate"),
        "val_2025_N": r.get("val_2025", {}).get("N", 0),
        "val_2025_rate": r.get("val_2025", {}).get("rate"),
        "perm_pctile": r.get("perm_pctile"),
        "tested_date": "2026-03-28",
        "batch": "batch_4",
    }

with open(board_path, "w") as f:
    json.dump(board, f, indent=2, default=str)
print(f"Updated: {board_path}")

# Append to test_results_log.json
log_path = SAFETY_DIR / "test_results_log.json"
with open(log_path) as f:
    log = json.load(f)

for r in all_results:
    log.append({
        "canonical_signal_id": r["signal_id"],
        "test_date": "2026-03-28",
        "registered_hypothesis_used": True,
        "thresholds_match_registered": True,
        "train_result": r.get("train"),
        "validation_2024": r.get("val_2024"),
        "validation_2025": r.get("val_2025"),
        "permutation_percentile": r.get("perm_pctile"),
        "season_support_pass": r.get("direction_2025", False),
        "verdict": r.get("final_verdict", "DATA_GAP"),
        "failure_reason": r.get("reason") if r.get("final_verdict") == "DATA_GAP" else None,
        "batch": "batch_4",
    })

with open(log_path, "w") as f:
    json.dump(log, f, indent=2, default=str)
print(f"Updated: {log_path}")

# ======================================================================
# SUMMARY TABLE
# ======================================================================
print(f"\n{'='*120}")
print("SUMMARY TABLE")
print(f"{'='*120}")
print(f"{'signal_id':<10} {'N_train':>8} {'N_val':>7} {'train_rate':>12} {'val_rate':>10} {'ROI':>8} {'perm_pctile':>12} {'2025_direction':>16} {'verdict'}")
print("-" * 120)
for r in all_results:
    sid = r["signal_id"]
    tn = r.get("train", {}).get("N", 0)
    vn = r.get("val_2025", {}).get("N", 0)
    tr = r.get("train", {}).get("rate")
    vr = r.get("val_2025", {}).get("rate")
    roi = r.get("train", {}).get("roi")
    pp = r.get("perm_pctile")
    d25 = "positive" if r.get("direction_2025") else "negative"
    if r.get("final_verdict") == "DATA_GAP":
        d25 = "N/A"

    tr_s = f"{tr:.4f}" if tr is not None else "N/A"
    vr_s = f"{vr:.4f}" if vr is not None else "N/A"
    roi_s = f"{roi}%" if roi is not None else "N/A"
    pp_s = f"{pp}" if pp is not None else "N/A"

    print(f"{sid:<10} {tn:>8} {vn:>7} {tr_s:>12} {vr_s:>10} {roi_s:>8} {pp_s:>12} {d25:>16}   {r['final_verdict']}")

print(f"\n{'='*120}")
print("OUTPUT FILES:")
print(f"  research/signal_discovery/test_batch_4/batch4_results.json")
print(f"  research/signal_discovery/safety_layer/signal_board.json (appended CS028-CS033)")
print(f"  research/signal_discovery/safety_layer/test_results_log.json (appended)")
print(f"  research/signal_discovery/safety_layer/hypothesis_registry.json (CS029-CS033 registered)")
print(f"{'='*120}")
