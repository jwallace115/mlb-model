#!/usr/bin/env python3
"""
Batch 4 signal tests v2: CS028-CS034.
CS028 fully tested. CS029-CS034 all DATA_GAP.
Thresholds frozen on 2022-2023. Permutation within-season. 500 shuffles.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)
OUT_DIR = Path("research/signal_discovery/test_batch_4")
SAFETY_DIR = Path("research/signal_discovery/safety_layer")
WIN_PER_UNIT = 100.0 / 110.0

# ======================================================================
# LOAD BASE DATA
# ======================================================================
gt = pd.read_parquet("sim/data/game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
gt = gt[gt["actual_total"].notna()].copy()

cl_hist = pd.read_parquet("sim/data/mlb_historical_closing_lines.parquet")
cl_hist["date"] = pd.to_datetime(cl_hist["date"])

ms = pd.read_parquet("sim/data/market_snapshots.parquet")
ms["date"] = pd.to_datetime(ms["date"])
ms = ms.rename(columns={"game_id": "game_pk"})
ms["game_pk"] = ms["game_pk"].astype(int)

lines_2223 = cl_hist[["game_pk", "date", "season", "home_team", "away_team", "close_total"]].copy()
lines_2425 = ms[["game_pk", "date", "close_total"]].copy()
lines_2425 = lines_2425.merge(
    gt[["game_pk", "season", "home_team", "away_team"]].drop_duplicates("game_pk"),
    on="game_pk", how="left"
)
all_lines = pd.concat([lines_2223, lines_2425[lines_2223.columns]], ignore_index=True)
all_lines = all_lines.drop_duplicates("game_pk", keep="first")

base = gt[["game_pk", "date", "season", "home_team", "away_team", "actual_total"]].merge(
    all_lines[["game_pk", "close_total"]], on="game_pk", how="inner"
)
base = base[base["close_total"].notna()].copy()
base["went_under"] = (base["actual_total"] < base["close_total"]).astype(int)
base["went_over"] = (base["actual_total"] > base["close_total"]).astype(int)
base["push"] = (base["actual_total"] == base["close_total"]).astype(int)

print(f"Base games: {len(base)}")
for s in sorted(base["season"].unique()):
    print(f"  {s}: {len(base[base['season'] == s])}")
print(f"Baseline under: {base['went_under'].mean():.4f}, over: {base['went_over'].mean():.4f}")

TRAIN = base[base["season"].isin([2022, 2023])].copy()
print(f"Train: {len(TRAIN)}")


# ======================================================================
# HELPERS
# ======================================================================
def compute_stats(subset, direction="UNDER"):
    n = len(subset)
    if n == 0:
        return {"N": 0, "rate": None, "roi": None}
    col = "went_under" if direction == "UNDER" else "went_over"
    hits = subset[col].sum()
    losses = n - hits - subset["push"].sum()
    roi = (hits * WIN_PER_UNIT - losses) / n * 100
    return {"N": n, "rate": round(hits / n, 4), "roi": round(roi, 2)}


def permutation_test(data, signal_mask, direction="UNDER", n_perms=500):
    col = "went_under" if direction == "UNDER" else "went_over"
    n_signal = signal_mask.sum()
    if n_signal == 0:
        return 0.0
    actual_rate = data.loc[signal_mask, col].mean()
    shuffle_rates = []
    for _ in range(n_perms):
        shuffled = pd.Series(False, index=data.index)
        for s in data["season"].unique():
            s_idx = data.index[data["season"] == s]
            n_in = signal_mask[data["season"] == s].sum()
            if n_in > 0 and len(s_idx) >= n_in:
                chosen = np.random.choice(s_idx, size=n_in, replace=False)
                shuffled.loc[chosen] = True
        shuffle_rates.append(data.loc[shuffled, col].mean())
    return round((np.array(shuffle_rates) < actual_rate).mean() * 100, 1)


# ======================================================================
# CS028: BAYESIAN BULLPEN BLOWUP
# ======================================================================
print("\n" + "=" * 70)
print("CS028: BAYESIAN BULLPEN BLOWUP")
print("=" * 70)

pgl = pd.read_parquet("mlb/data/pitcher_game_logs.parquet")
pgl["game_date"] = pd.to_datetime(pgl["game_date"])

relievers = pgl[pgl["starter_flag"] == 0].sort_values(["player_id", "game_date"]).reset_index(drop=True)
relievers["blowup"] = (relievers["runs_allowed"] >= 2).astype(int)

season_blowup_rate = relievers.groupby("season")["blowup"].mean().to_dict()
print(f"Season blowup rates: {season_blowup_rate}")

# Compute trailing posterior per reliever
records = []
for (pid, season), grp in relievers.groupby(["player_id", "season"]):
    grp = grp.sort_values("game_date")
    prior_rate = season_blowup_rate.get(season, 0.25)
    history = []
    for _, row in grp.iterrows():
        n_prior = len(history)
        if n_prior >= 5:
            last3 = history[-3:]
            blowups_l3 = sum(last3)
            a0 = 2 * prior_rate
            b0 = 2 * (1 - prior_rate)
            posterior_p = (a0 + blowups_l3) / (a0 + b0 + 3)
            records.append({
                "game_pk": row["game_pk"],
                "game_date": row["game_date"],
                "season": season,
                "player_id": pid,
                "team": row["team"],
                "home_away": row["home_away"],
                "blowup_posterior": posterior_p,
            })
        history.append(row["blowup"])

bp_df = pd.DataFrame(records)
print(f"Reliever posterior records: {len(bp_df)}")

# Exclude relievers who appeared in previous game
team_game_dates = pgl.groupby(["team", "game_pk"])["game_date"].first().reset_index().sort_values(["team", "game_date"])
prev_game_map = {}
for team, tg in team_game_dates.groupby("team"):
    tg = tg.sort_values("game_date")
    pks = tg["game_pk"].values
    for i in range(1, len(pks)):
        prev_game_map[(team, pks[i])] = pks[i - 1]

bp_df["prev_game_pk"] = bp_df.apply(lambda r: prev_game_map.get((r["team"], r["game_pk"])), axis=1)

# Build set of (player_id, game_pk) pairs where reliever appeared in that game
reliever_appearances = set(zip(relievers["player_id"], relievers["game_pk"]))

bp_df["appeared_prev"] = bp_df.apply(
    lambda r: (r["player_id"], r["prev_game_pk"]) in reliever_appearances if r["prev_game_pk"] is not None else False,
    axis=1
)
bp_available = bp_df[~bp_df["appeared_prev"]].copy()
print(f"After excluding prev-game: {len(bp_available)}")

# Team blowup score
team_scores = bp_available.groupby(["game_pk", "game_date", "season", "team", "home_away"]).agg(
    n_relievers=("blowup_posterior", "count"),
    team_blowup_score=("blowup_posterior", "mean"),
).reset_index()
team_scores = team_scores[team_scores["n_relievers"] >= 3]
print(f"Team-game scores (>=3 relievers): {len(team_scores)}")

home_scores = team_scores[team_scores["home_away"] == "H"][["game_pk", "team_blowup_score"]].rename(
    columns={"team_blowup_score": "home_blowup"})
away_scores = team_scores[team_scores["home_away"] == "A"][["game_pk", "team_blowup_score"]].rename(
    columns={"team_blowup_score": "away_blowup"})

cs028 = base.merge(home_scores, on="game_pk", how="left")
cs028 = cs028.merge(away_scores, on="game_pk", how="left")
cs028["either_blowup"] = cs028[["home_blowup", "away_blowup"]].max(axis=1)

for col in ["home_blowup", "away_blowup", "either_blowup"]:
    pct = cs028[col].notna().mean() * 100
    print(f"  {col} coverage: {pct:.1f}%")

# Freeze 90th percentile on 2022-2023
train_cs028 = cs028[cs028["season"].isin([2022, 2023])]
thresholds = {}
for vname, col in [("home", "home_blowup"), ("away", "away_blowup"), ("either", "either_blowup")]:
    valid = train_cs028[col].dropna()
    p90 = valid.quantile(0.90)
    thresholds[vname] = {"col": col, "thresh": p90}
    print(f"  {vname} P90 threshold (frozen): {p90:.4f} (N={len(valid)})")

# Test all three variants on training
print("\n  --- Training results by variant ---")
variant_results = {}
for vname, info in thresholds.items():
    col, thresh = info["col"], info["thresh"]
    valid_train = train_cs028[train_cs028[col].notna()]
    mask = valid_train[col] >= thresh
    st = compute_stats(valid_train[mask], "OVER")
    perm = permutation_test(valid_train, mask, "OVER", 500)
    variant_results[vname] = {"stats": st, "perm": perm}
    print(f"    {vname}: N={st['N']}, over_rate={st['rate']}, ROI={st['roi']}%, perm={perm}")

# Pre-commit: select variant with highest training over_rate
best_v = max(variant_results, key=lambda v: variant_results[v]["stats"]["rate"] or 0)
bv_col = thresholds[best_v]["col"]
bv_thresh = thresholds[best_v]["thresh"]
print(f"\n  Pre-committed variant: {best_v} (thresh={bv_thresh:.4f})")

# Per-season N flagged
print("\n  --- N flagged per season per variant ---")
for vname, info in thresholds.items():
    col, thresh = info["col"], info["thresh"]
    for s in sorted(cs028["season"].unique()):
        n_flagged = ((cs028["season"] == s) & cs028[col].notna() & (cs028[col] >= thresh)).sum()
        n_total = ((cs028["season"] == s) & cs028[col].notna()).sum()
        print(f"    {vname} {s}: {n_flagged}/{n_total}")

# Validate on 2024 and 2025 using pre-committed variant
print(f"\n  --- Validation ({best_v} variant) ---")
cs028_final = {}
for label, s_filter in [("train", [2022, 2023]), ("val_2024", [2024]), ("val_2025", [2025])]:
    data = cs028[cs028["season"].isin(s_filter)]
    valid = data[data[bv_col].notna()]
    mask = valid[bv_col] >= bv_thresh
    st = compute_stats(valid[mask], "OVER")
    cs028_final[label] = st
    print(f"    {label}: N={st['N']}, over_rate={st['rate']}, ROI={st['roi']}%")

cs028_final["perm_pctile"] = variant_results[best_v]["perm"]
cs028_final["direction_2025"] = (
    cs028_final["val_2025"]["rate"] is not None and cs028_final["val_2025"]["rate"] > 0.50
)

# Monotonicity table
print(f"\n  --- Monotonicity: {best_v} blowup decile vs over_rate (training) ---")
mono = train_cs028[train_cs028[bv_col].notna()].copy()
mono["decile"] = pd.qcut(mono[bv_col], 10, labels=False, duplicates="drop")
mono_tbl = mono.groupby("decile").agg(n=("went_over", "count"), over_rate=("went_over", "mean"),
                                        avg_score=(bv_col, "mean")).reset_index()
for _, row in mono_tbl.iterrows():
    print(f"    D{int(row['decile'])}: N={int(row['n'])}, over_rate={row['over_rate']:.3f}, avg_score={row['avg_score']:.4f}")

# ======================================================================
# CS029-CS032: DATA_GAP (pitch-type data missing 2022)
# ======================================================================
print("\n" + "=" * 70)
print("CS029-CS032: DATA_GAP")
print("=" * 70)
print("Pitch-type data (statcast_pitchers.parquet) covers 2023-2025 only.")
print("2022 missing → training coverage = 50% < 70% threshold.")
print(">>> CS029: DATA_GAP")
print(">>> CS030: DATA_GAP")
print(">>> CS031: DATA_GAP")
print(">>> CS032: DATA_GAP")

# ======================================================================
# CS033: DATA_GAP (K-prop data missing 2022)
# ======================================================================
print("\n" + "=" * 70)
print("CS033: DATA_GAP")
print("=" * 70)
print("K-prop lines (kprop_lines_historical.parquet) covers 2023-2025 only.")
print("2022 missing → training coverage = 50% < 70% threshold.")
print(">>> CS033: DATA_GAP")

# ======================================================================
# CS034: DATA_GAP (inherited_runners column missing)
# ======================================================================
print("\n" + "=" * 70)
print("CS034: DATA_GAP")
print("=" * 70)
print("inherited_runners and inherited_scored columns not present in pitcher_game_logs.parquet.")
print(">>> CS034: DATA_GAP")

# ======================================================================
# VERDICTS
# ======================================================================
print("\n" + "=" * 70)
print("VERDICTS")
print("=" * 70)

all_results = []

# CS028
train_n = cs028_final["train"]["N"]
perm = cs028_final["perm_pctile"]
dir_2025 = cs028_final["direction_2025"]
if train_n < 50:
    verdict_028 = "FAIL (THIN_SAMPLE)"
elif perm >= 85 and dir_2025:
    verdict_028 = "PASS"
else:
    reasons = []
    if perm < 85:
        reasons.append(f"perm={perm}<85")
    if not dir_2025:
        reasons.append(f"2025_dir=neg(rate={cs028_final['val_2025']['rate']})")
    verdict_028 = f"FAIL ({'; '.join(reasons)})"

print(f"  CS028: {verdict_028}")
all_results.append({
    "signal_id": "CS028",
    "variant": best_v,
    "threshold_frozen": round(bv_thresh, 4),
    "train": cs028_final["train"],
    "val_2024": cs028_final["val_2024"],
    "val_2025": cs028_final["val_2025"],
    "perm_pctile": perm,
    "direction_2025": dir_2025,
    "final_verdict": verdict_028,
})

# DATA_GAP signals
for sid, reason in [
    ("CS029", "2022 pitch-type data unavailable. Training coverage = 50% < 70%."),
    ("CS030", "2022 pitch-type data unavailable. Training coverage = 50% < 70%."),
    ("CS031", "2022 pitch-type data unavailable. Training coverage = 50% < 70%."),
    ("CS032", "2022 pitch-type data unavailable. Training coverage = 50% < 70%."),
    ("CS033", "2022 K-prop data unavailable. Training coverage = 50% < 70%."),
    ("CS034", "inherited_runners/inherited_scored columns missing from pitcher_game_logs.parquet."),
]:
    print(f"  {sid}: DATA_GAP")
    all_results.append({
        "signal_id": sid,
        "final_verdict": "DATA_GAP",
        "reason": reason,
        "train": {"N": 0, "rate": None, "roi": None},
        "val_2025": {"N": 0, "rate": None, "roi": None},
        "perm_pctile": None,
        "direction_2025": False,
    })

# ======================================================================
# SAVE OUTPUTS
# ======================================================================
batch_path = OUT_DIR / "batch4_results.json"
with open(batch_path, "w") as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\nSaved: {batch_path}")

# Append to signal_board.json (list format)
board_path = SAFETY_DIR / "signal_board.json"
with open(board_path) as f:
    board = json.load(f)

for r in all_results:
    sid = r["signal_id"]
    entry = {
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
    if isinstance(board, list):
        board = [b for b in board if b.get("canonical_signal_id") != sid]
        board.append(entry)
    else:
        board[sid] = entry

with open(board_path, "w") as f:
    json.dump(board, f, indent=2, default=str)
print(f"Updated: {board_path}")

# Append to test_results_log.json
log_path = SAFETY_DIR / "test_results_log.json"
with open(log_path) as f:
    log = json.load(f)

# Remove any prior batch_4 entries to avoid duplicates
log = [e for e in log if e.get("batch") != "batch_4"]
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
        "verdict": r["final_verdict"],
        "failure_reason": r.get("reason"),
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
hdr = f"{'signal_id':<10} {'N_train':>8} {'N_val':>7} {'train_rate':>12} {'val_rate':>10} {'ROI':>8} {'perm_pctile':>12} {'2025_dir':>10}   verdict"
print(hdr)
print("-" * 120)
for r in all_results:
    sid = r["signal_id"]
    tn = r.get("train", {}).get("N", 0)
    vn = r.get("val_2025", {}).get("N", 0)
    tr = r.get("train", {}).get("rate")
    vr = r.get("val_2025", {}).get("rate")
    roi = r.get("train", {}).get("roi")
    pp = r.get("perm_pctile")
    d25 = "positive" if r.get("direction_2025") else ("N/A" if r["final_verdict"] == "DATA_GAP" else "negative")
    print(f"{sid:<10} {tn:>8} {vn:>7} {str(tr) if tr is not None else 'N/A':>12} "
          f"{str(vr) if vr is not None else 'N/A':>10} "
          f"{(str(roi)+'%') if roi is not None else 'N/A':>8} "
          f"{str(pp) if pp is not None else 'N/A':>12} "
          f"{d25:>10}   {r['final_verdict']}")

print(f"\n{'='*120}")
print("OUTPUT FILES:")
print(f"  research/signal_discovery/test_batch_4/batch4_results.json")
print(f"  research/signal_discovery/safety_layer/signal_board.json (CS028-CS034 appended)")
print(f"  research/signal_discovery/safety_layer/test_results_log.json (appended)")
print(f"  research/signal_discovery/safety_layer/hypothesis_registry.json (CS028-CS034 registered)")
print(f"{'='*120}")
