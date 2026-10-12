"""
ON-D8: Earlier-close comparator and auditable ridge comparison.

Prior-close ratings: team ratings by least squares on home-minus-away
indicators + home intercept, fitted ONLY on closes of games with
kickoff + 4h < the same prediction_cutoff.

Pre-registered: ~55% direction (audit measured 55.0 / 54.4).
"""
import os, sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.dirname(__file__))

from on_utils import (
    compute_prediction_cutoff, game_is_admitted,
    kickoff_utc_from_nflverse, compute_gap,
)

ROOT = os.path.join(os.path.dirname(__file__), "../..")
TARGET_SEASONS = [2021, 2022, 2023]

# ─── LOAD DATA ────────────────────────────────────────────────────────
import nflreadpy as nfl
sched = nfl.load_schedules(TARGET_SEASONS).to_pandas()
games = sched[sched["game_type"] == "REG"].copy()
games["kickoff_utc"] = games.apply(
    lambda r: kickoff_utc_from_nflverse(r["gameday"], r["gametime"]), axis=1
)
print(f"Games: {len(games)}")

# Load Monday numbers (for the engine's selections and err_m)
mn = pd.read_parquet(os.path.join(ROOT, "nfl/data/own/monday_numbers_2021_23.parquet"))
opens = pd.read_parquet(os.path.join(ROOT, "nfl/data/info/spread_opens_2021_23.parquet"))
opens["open_spread"] = -opens["bet365_spread_open"]
mn = mn.merge(opens[["game_id", "open_spread"]], on="game_id", how="left",
              suffixes=("", "_dup"))
if "open_spread_dup" in mn.columns:
    mn.drop(columns=["open_spread_dup"], inplace=True)

# ─── COMPUTE CUTOFFS ─────────────────────────────────────────────────
from datetime import timedelta

def get_week_cutoff_monday(season, week):
    wk_games = games[(games["season"] == season) & (games["week"] == week)]
    min_gd = pd.to_datetime(wk_games["gameday"]).min().date()
    monday = min_gd - timedelta(days=min_gd.weekday())
    return monday.strftime("%Y-%m-%d")

week_cutoffs = {}
for season in TARGET_SEASONS:
    for week in sorted(games[games["season"] == season]["week"].unique()):
        monday_str = get_week_cutoff_monday(season, week)
        week_cutoffs[(season, week)] = compute_prediction_cutoff(monday_str)


# ─── PRIOR-CLOSE RATINGS ──────────────────────────────────────────────

def fit_prior_close_ratings(season, week, sched_df, cutoff_utc, min_games=32):
    """Fit team ratings by least squares on closes of admitted games.

    Model: actual_home_margin = intercept (HFA) + team_home_rating - team_away_rating + eps
    Returns dict: team -> rating, plus intercept.
    Returns None if < min_games training games.
    """
    # Training data: prior-season + current-season admitted games
    # Prior season: all games
    prior_s = sched_df[
        (sched_df["season"] == season - 1) & (sched_df["game_type"] == "REG")
    ]
    # Current season admitted
    curr = sched_df[
        (sched_df["season"] == season) & (sched_df["week"] < week) &
        (sched_df["game_type"] == "REG")
    ]
    if len(curr) > 0:
        mask = curr["kickoff_utc"].apply(lambda k: game_is_admitted(k, cutoff_utc))
        curr = curr[mask]

    train = pd.concat([prior_s, curr], ignore_index=True)
    train = train[train["spread_line"].notna()].copy()

    if len(train) < min_games:
        return None

    # Set up design matrix: one column per team, +1 for home, -1 for away
    teams = sorted(set(train["home_team"].unique()) | set(train["away_team"].unique()))
    team_idx = {t: i for i, t in enumerate(teams)}
    n = len(train)
    p = len(teams) + 1  # teams + intercept

    X = np.zeros((n, p))
    y = train["spread_line"].values  # using close as the "rating" target

    for i, (_, g) in enumerate(train.iterrows()):
        X[i, team_idx[g["home_team"]]] = 1
        X[i, team_idx[g["away_team"]]] = -1
        X[i, -1] = 1  # intercept (HFA)

    # Ridge with tiny regularisation for numerical stability
    lam = 0.01
    XtX = X.T @ X + lam * np.eye(p)
    Xty = X.T @ y
    beta = np.linalg.solve(XtX, Xty)

    ratings = {t: beta[team_idx[t]] for t in teams}
    hfa = beta[-1]
    return {"ratings": ratings, "hfa": hfa, "n_train": len(train)}


# ─── PREDICTIONS ─────────────────────────────────────────────────────
print("\nBuilding prior-close predictions...")
results = []
for _, g in mn.iterrows():
    season, week = g["season"], g["week"]
    cutoff = week_cutoffs[(season, week)]

    model = fit_prior_close_ratings(season, week, games, cutoff)
    if model is None:
        results.append({"game_id": g["game_id"], "pc_pred_m": None, "pc_n_train": 0})
        continue

    home, away = g["home_team"], g["away_team"]
    ratings = model["ratings"]
    hr = ratings.get(home, 0)
    ar = ratings.get(away, 0)
    pred_m = hr - ar + model["hfa"]

    results.append({
        "game_id": g["game_id"],
        "pc_pred_m": pred_m,
        "pc_n_train": model["n_train"],
    })

pc_df = pd.DataFrame(results)
mn = mn.merge(pc_df, on="game_id", how="left")

# Filter to games with both predictions and opens
has_both = mn["pc_pred_m"].notna() & mn["open_spread"].notna()
mn_both = mn[has_both].copy()
print(f"Eligible games (both comparator + open): {len(mn_both)}")


# ─── SCORING ─────────────────────────────────────────────────────────

def score_method(mn_df, pred_col, label, err_m_col="err_m",
                 common_threshold=True, own_threshold=False):
    """Score a prediction method on direction and movement."""
    df = mn_df.copy()
    df["gap"] = df[pred_col] - df["open_spread"]
    df["close_minus_open"] = df["spread_line"] - df["open_spread"]
    df["moved"] = df["close_minus_open"] != 0

    if common_threshold:
        # Use the engine's err_m as the common threshold
        df["confident"] = (df["gap"].abs() >= df[err_m_col]) & (df["gap"].abs() >= 1.0)
        threshold_label = "common (engine err_m)"
    elif own_threshold:
        # Would need own prior-season calibration — simplified for now
        df["confident"] = df["gap"].abs() >= 1.0
        threshold_label = "own (|gap| >= 1)"
    else:
        df["confident"] = True
        threshold_label = "all"

    conf = df[df["confident"]]
    conf_move = conf[conf["moved"]].copy()
    conf_move["dir_agree"] = (np.sign(conf_move["gap"]) == np.sign(conf_move["close_minus_open"]))

    n_selected = len(conf)
    n_moved = len(conf_move)
    n_dir = conf_move["dir_agree"].sum() if n_moved > 0 else 0
    dir_pct = n_dir / n_moved if n_moved > 0 else 0

    signed_move = np.sign(conf["gap"]) * conf["close_minus_open"]
    mean_move = signed_move.mean() if len(conf) > 0 else 0

    print(f"\n{label} (threshold: {threshold_label}):")
    print(f"  Selected: {n_selected} (moved: {n_moved}, unchanged: {n_selected - n_moved})")
    if n_moved > 0:
        print(f"  Direction: {dir_pct:.1%} ({n_dir}/{n_moved})")
    print(f"  Mean signed movement (all selected): +{mean_move:.3f}")

    return {
        "label": label, "threshold": threshold_label,
        "n_selected": n_selected, "n_moved": n_moved,
        "n_dir": n_dir, "dir_pct": dir_pct, "mean_move": mean_move,
    }


print("\n" + "=" * 60)
print("COMPARATOR RESULTS (common threshold = engine err_m)")
print("LABEL: DEVELOPMENT — all methods see 2021-24 through the engine")
print("=" * 60)

# Pre-register: ~55% direction (audit: 55.0 / 54.4)
print("\nPre-registered: prior-close comparator ~55% direction")

# Score the prior-close comparator
pc_common = score_method(mn_both, "pc_pred_m", "Prior-close ratings", common_threshold=True)
pc_own = score_method(mn_both, "pc_pred_m", "Prior-close ratings (own threshold)",
                       common_threshold=False, own_threshold=True)

# Score the engine for comparison (on the same population)
engine = score_method(mn_both, "ours_m", "Engine (ON)", common_threshold=True)


# ─── RIDGE BASELINE ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("RIDGE BASELINE (from origin/eng/gl1)")
print("Training: LOSO 2021-23 — NOT strictly as-of across seasons")
print("=" * 60)

ridge_path = os.path.join(ROOT, "nfl/data/sim/outputs/gl1/baseline_2021_23.parquet")
if os.path.exists(ridge_path):
    ridge = pd.read_parquet(ridge_path)
    # Merge with our data
    ridge_merged = mn_both.merge(
        ridge[["game_id", "pred_m_oof", "mkt_m"]],
        on="game_id", how="inner"
    )
    print(f"Ridge games matched: {len(ridge_merged)}")

    # Score ridge with common threshold (engine's err_m)
    ridge_score = score_method(ridge_merged, "pred_m_oof", "Ridge OOF",
                                common_threshold=True)

    # Paired comparison on engine-selected games
    engine_selected = ridge_merged[
        (ridge_merged["ours_m"] - ridge_merged["open_spread"]).abs() >= ridge_merged["err_m"]
    ]
    engine_selected = engine_selected[
        (engine_selected["ours_m"] - engine_selected["open_spread"]).abs() >= 1.0
    ]
    print(f"\nPaired on engine-selected games (N={len(engine_selected)}):")
    for pred_col, label in [("ours_m", "Engine"), ("pred_m_oof", "Ridge"),
                              ("pc_pred_m", "Prior-close")]:
        sub = engine_selected.copy()
        sub["gap"] = sub[pred_col] - sub["open_spread"]
        sub["close_minus_open"] = sub["spread_line"] - sub["open_spread"]
        moved = sub[sub["close_minus_open"] != 0]
        if len(moved) > 0:
            moved_agree = (np.sign(moved["gap"]) == np.sign(moved["close_minus_open"]))
            signed_m = np.sign(sub["gap"]) * sub["close_minus_open"]
            print(f"  {label}: dir {moved_agree.mean():.1%} ({moved_agree.sum()}/{len(moved)}), "
                  f"mean move +{signed_m.mean():.3f}")
else:
    print(f"MISSING: {ridge_path}")


# ─── SUMMARY ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Prior-close (common threshold): {pc_common['dir_pct']:.1%} direction on {pc_common['n_moved']} movers")
print(f"Pre-registered: ~55%. {'HELD' if 0.50 <= pc_common['dir_pct'] <= 0.60 else 'DID NOT HOLD'}")
print(f"Engine (common threshold): {engine['dir_pct']:.1%} direction on {engine['n_moved']} movers")
print(f"Engine's advantage over trivial comparators is the thing worth testing forward.")
print(f"\nLABEL: DEVELOPMENT — all methods see 2021-24 through the engine")
