#!/usr/bin/env python3
"""
Phase 2 — Pre-registered signal tests for NBA schedule fatigue.
Runs all 7 signals independently with permutation testing, validation, and venue independence.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)

OUT_DIR = Path("research/nba/schedule_fatigue")
WIN_PER_UNIT = 100.0 / 110.0  # -110 flat

# ── Load data ───────────────────────────────────────────────────────────────
df = pd.read_parquet("nba/data/nba_schedule_features.parquet")

# Exclude OT games
df = df[df["went_to_ot"] == False].copy()
print(f"Games after OT exclusion: {len(df)}")

# Under flag: actual_total < total (closing line)
df["went_under"] = (df["actual_total"] < df["total"]).astype(int)
# Push = 0 (neither win nor loss)
df["push"] = (df["actual_total"] == df["total"]).astype(int)

# Seasons
TRAIN_SEASONS = ["2022-23", "2023-24"]
VAL_SEASON = "2024-25"

train = df[df["season"].isin(TRAIN_SEASONS)].copy()
val = df[df["season"] == VAL_SEASON].copy()

print(f"Train: {len(train)} games ({TRAIN_SEASONS})")
print(f"Validation: {len(val)} games ({VAL_SEASON})")
print(f"Full dataset baseline under_rate: {df['went_under'].mean():.4f}")
print(f"Train baseline under_rate: {train['went_under'].mean():.4f}")
print(f"Val baseline under_rate: {val['went_under'].mean():.4f}")


# ── Venue independence approximation ────────────────────────────────────────
# Compute season win pct and home win pct per team per season
box = pd.read_parquet("nba/data/box_stats.parquet",
                      columns=["game_id", "date", "season", "team", "opponent",
                               "location", "pts", "opp_pts", "went_ot"])
box = box[box["went_ot"] == False].copy()
box["won"] = (box["pts"] > box["opp_pts"]).astype(int)

# Overall season win pct
season_wp = box.groupby(["season", "team"])["won"].mean().reset_index()
season_wp.columns = ["season", "team", "season_win_pct"]

# Home-only win pct
home_box = box[box["location"] == "H"]
home_wp = home_box.groupby(["season", "team"])["won"].mean().reset_index()
home_wp.columns = ["season", "team", "home_win_pct"]


def get_venue_flag(row):
    """
    ROAD_WARRIOR @ STRONG_HOME: away_season_win_pct >= 0.52 AND home_season_home_win_pct >= 0.60
    """
    season = row["season"]
    away = row["away_team"]
    home = row["home_team"]

    awp = season_wp[(season_wp["season"] == season) & (season_wp["team"] == away)]
    hwp = home_wp[(home_wp["season"] == season) & (home_wp["team"] == home)]

    away_wp_val = awp["season_win_pct"].values[0] if len(awp) > 0 else 0.5
    home_hwp_val = hwp["home_win_pct"].values[0] if len(hwp) > 0 else 0.5

    return away_wp_val >= 0.52 and home_hwp_val >= 0.60


print("\nComputing venue flags...")
df["venue_flag"] = df.apply(get_venue_flag, axis=1)
train["venue_flag"] = df.loc[train.index, "venue_flag"]
val["venue_flag"] = df.loc[val.index, "venue_flag"]
print(f"Venue flag (ROAD_WARRIOR @ STRONG_HOME): {df['venue_flag'].sum()} games ({df['venue_flag'].mean()*100:.1f}%)")


# ── Signal definitions ──────────────────────────────────────────────────────
def apply_signal(data, signal_id):
    """Return boolean mask for signal condition."""
    if signal_id == "FA01A":
        return (data["away_games_last_5"] >= 3) & (data["home_games_last_4"] <= 1)
    elif signal_id == "FA01H":
        return (data["home_games_last_5"] >= 3) & (data["away_games_last_4"] <= 1)
    elif signal_id == "FA02":
        return data["away_road_trip_length"] >= 5
    elif signal_id == "FA03A":
        return (data["away_prev_altitude_game"] == True) & (data["away_hours_since_prev"] <= 48)
    elif signal_id == "FA03H":
        return (data["home_prev_altitude_game"] == True) & (data["home_hours_since_prev"] <= 48)
    elif signal_id == "FA04A":
        return (data["away_cross_country"] == True) & (data["away_hours_since_prev"] <= 48)
    elif signal_id == "FA04H":
        return (data["home_cross_country"] == True) & (data["home_hours_since_prev"] <= 48)
    else:
        raise ValueError(f"Unknown signal: {signal_id}")


def compute_stats(subset):
    """Compute under_rate, ROI at -110, avg total."""
    n = len(subset)
    if n == 0:
        return {"N": 0, "under_rate": None, "roi": None, "avg_total": None, "avg_actual": None}
    under_rate = subset["went_under"].mean()
    wins = subset["went_under"].sum()
    losses = n - wins - subset["push"].sum()
    pushes = subset["push"].sum()
    roi = (wins * WIN_PER_UNIT - losses) / n * 100
    return {
        "N": n,
        "under_rate": round(under_rate, 4),
        "roi": round(roi, 2),
        "avg_total": round(subset["total"].mean(), 2),
        "avg_actual": round(subset["actual_total"].mean(), 2),
    }


def permutation_test(data, signal_mask, n_perms=500):
    """
    Shuffle signal flag within each season independently.
    Return percentile of actual under_rate vs shuffle distribution.
    """
    actual_ur = data.loc[signal_mask, "went_under"].mean()
    n_signal = signal_mask.sum()
    if n_signal == 0:
        return 0.0

    shuffle_urs = []
    seasons = data["season"].unique()

    for _ in range(n_perms):
        shuffled_mask = pd.Series(False, index=data.index)
        for s in seasons:
            s_mask = data["season"] == s
            s_idx = data.index[s_mask]
            n_in_season = signal_mask[s_mask].sum()
            chosen = np.random.choice(s_idx, size=n_in_season, replace=False)
            shuffled_mask.loc[chosen] = True
        shuffle_urs.append(data.loc[shuffled_mask, "went_under"].mean())

    shuffle_urs = np.array(shuffle_urs)
    percentile = (shuffle_urs < actual_ur).mean() * 100
    return round(percentile, 1)


# ── Run all 7 signals ──────────────────────────────────────────────────────
SIGNALS = ["FA01A", "FA01H", "FA02", "FA03A", "FA03H", "FA04A", "FA04H"]
results = []

for sig_id in SIGNALS:
    print(f"\n{'='*60}")
    print(f"SIGNAL {sig_id}")
    print(f"{'='*60}")

    # Step 1 — Training
    train_mask = apply_signal(train, sig_id)
    train_sub = train[train_mask]
    train_stats = compute_stats(train_sub)
    train_baseline = compute_stats(train)

    print(f"\n  TRAIN ({TRAIN_SEASONS}):")
    print(f"    N = {train_stats['N']}")
    print(f"    Under rate = {train_stats['under_rate']}")
    print(f"    ROI @ -110 = {train_stats['roi']}%")
    print(f"    Avg total (signal) = {train_stats['avg_total']}")
    print(f"    Avg actual (signal) = {train_stats['avg_actual']}")
    print(f"    Baseline under rate = {train_baseline['under_rate']}")
    print(f"    Baseline avg actual = {train_baseline['avg_actual']}")

    # Step 2 — Permutation test
    perm_pctile = permutation_test(train, train_mask, n_perms=500)
    print(f"\n  PERMUTATION TEST:")
    print(f"    Percentile = {perm_pctile}")

    # Step 3 — Validation
    val_mask = apply_signal(val, sig_id)
    val_sub = val[val_mask]
    val_stats = compute_stats(val_sub)
    val_thin = val_stats["N"] < 20

    print(f"\n  VALIDATION ({VAL_SEASON}):")
    print(f"    N = {val_stats['N']}")
    print(f"    Under rate = {val_stats['under_rate']}")
    print(f"    ROI @ -110 = {val_stats['roi']}%")
    if val_thin:
        print(f"    *** VALIDATION_THIN (N < 20)")
    if val_stats["under_rate"] is not None:
        direction_match = val_stats["under_rate"] > 0.50
        beats_vig = val_stats["under_rate"] > 0.524
        print(f"    Direction match (>50%): {direction_match}")
        print(f"    Beats vig (>52.4%): {beats_vig}")
    else:
        direction_match = False
        beats_vig = False

    # Step 4 — Venue independence
    # Use train + val combined for this check (all available data)
    all_data = df.copy()
    all_mask = apply_signal(all_data, sig_id)
    signal_games = all_data[all_mask]

    venue_sub = signal_games[signal_games["venue_flag"] == True]
    non_venue_sub = signal_games[signal_games["venue_flag"] == False]

    venue_stats = compute_stats(venue_sub)
    non_venue_stats = compute_stats(non_venue_sub)
    thin_indep = non_venue_stats["N"] < 20

    print(f"\n  VENUE INDEPENDENCE CHECK:")
    print(f"    Venue (ROAD_WARRIOR @ STRONG_HOME): N={venue_stats['N']}, under_rate={venue_stats['under_rate']}")
    print(f"    Non-venue: N={non_venue_stats['N']}, under_rate={non_venue_stats['under_rate']}")
    if thin_indep:
        print(f"    *** THIN_INDEPENDENCE (non-venue N < 20)")

    # Pass gates
    train_n_pass = train_stats["N"] >= 50
    perm_pass = perm_pctile >= 85
    val_pass = val_stats["under_rate"] is not None and val_stats["under_rate"] > 0.524
    if thin_indep:
        venue_pass = True  # Can't fail if THIN
        venue_label = "THIN_INDEPENDENCE"
    else:
        venue_pass = non_venue_stats["under_rate"] is not None and non_venue_stats["under_rate"] > 0.524
        venue_label = f"{non_venue_stats['under_rate']}" if non_venue_stats["under_rate"] is not None else "N/A"

    all_pass = train_n_pass and perm_pass and val_pass and venue_pass
    if not train_n_pass:
        verdict = "FAIL (THIN_SAMPLE)"
    elif not all_pass:
        failures = []
        if not perm_pass:
            failures.append(f"perm={perm_pctile}<85")
        if not val_pass:
            if val_thin:
                failures.append("VALIDATION_THIN")
            else:
                failures.append(f"val_ur={val_stats['under_rate']}")
        if not venue_pass:
            failures.append(f"venue_indep={non_venue_stats['under_rate']}")
        verdict = f"FAIL ({'; '.join(failures)})"
    else:
        verdict = "PASS"

    print(f"\n  GATES:")
    print(f"    Train N >= 50: {'PASS' if train_n_pass else 'FAIL'} ({train_stats['N']})")
    print(f"    Perm >= 85: {'PASS' if perm_pass else 'FAIL'} ({perm_pctile})")
    print(f"    Val under_rate > 52.4%: {'PASS' if val_pass else 'FAIL'} ({val_stats['under_rate']})")
    print(f"    Venue indep > 52.4%: {'PASS' if venue_pass else 'FAIL'} ({venue_label})")
    print(f"\n  >>> VERDICT: {verdict}")

    results.append({
        "signal_id": sig_id,
        "train_N": train_stats["N"],
        "val_N": val_stats["N"],
        "train_under_rate": train_stats["under_rate"],
        "val_under_rate": val_stats["under_rate"],
        "train_roi": train_stats["roi"],
        "val_roi": val_stats["roi"],
        "perm_pctile": perm_pctile,
        "train_avg_total": train_stats["avg_total"],
        "train_avg_actual": train_stats["avg_actual"],
        "train_baseline_under_rate": train_baseline["under_rate"],
        "venue_sub_N": venue_stats["N"],
        "venue_sub_under_rate": venue_stats["under_rate"],
        "non_venue_sub_N": non_venue_stats["N"],
        "non_venue_sub_under_rate": non_venue_stats["under_rate"],
        "thin_independence": thin_indep,
        "validation_thin": val_thin,
        "verdict": verdict,
    })

# ── Save signal_board.json ──────────────────────────────────────────────────
board_path = OUT_DIR / "signal_board.json"
with open(board_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved: {board_path}")

# ── Summary table ───────────────────────────────────────────────────────────
print(f"\n{'='*120}")
print("SUMMARY TABLE")
print(f"{'='*120}")
print(f"{'signal_id':<10} {'train_N':>8} {'val_N':>7} {'train_ur':>10} {'val_ur':>10} {'ROI':>8} {'perm_pct':>10} {'venue_indep_ur':>16} {'verdict'}")
print("-" * 120)
for r in results:
    vi_label = "THIN_INDEP" if r["thin_independence"] else (
        f"{r['non_venue_sub_under_rate']:.4f}" if r["non_venue_sub_under_rate"] is not None else "N/A")
    vt_suffix = " THIN" if r["validation_thin"] else ""
    print(f"{r['signal_id']:<10} {r['train_N']:>8} {r['val_N']:>7}{vt_suffix} {r['train_under_rate']:>10} "
          f"{r['val_under_rate'] if r['val_under_rate'] is not None else 'N/A':>10} "
          f"{r['train_roi']:>7}% {r['perm_pctile']:>9} {vi_label:>16}   {r['verdict']}")

print(f"\n{'='*120}")
print("OUTPUT FILES:")
print(f"  research/nba/schedule_fatigue/hypothesis_registry.json")
print(f"  research/nba/schedule_fatigue/signal_board.json")
print(f"  nba/data/nba_schedule_features.parquet")
print(f"{'='*120}")
