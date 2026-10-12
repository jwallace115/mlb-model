"""
IE-1 ITEM 3: Discovery fit on 2021-23.
Per family: residual ~ family score, LOSO by season, pooled t and per-season sign.
All-family ridge. Null control (shuffled labels within week).
NO 2024 data.
"""
import os
os.environ["SSL_CERT_FILE"] = __import__("certifi").where()

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.metrics import log_loss
import hashlib

np.random.seed(42)

# Load feature table
ft = pd.read_parquet(os.path.join(os.path.dirname(__file__),
    "../../nfl/data/info/feature_table_2021_23.parquet"))
assert sorted(ft["season"].unique()) == [2021, 2022, 2023], "HALT: wrong seasons"
print(f"Feature table: {ft.shape}")

# ─── FAMILY DEFINITIONS ─────────────────────────────────────────────
FAMILIES = {
    "F1": {
        "cols": ["f1_inj_trajectory_diff"],
        "name": "Injury trajectory",
    },
    "F2": {
        "cols": ["f2_pressure_diff"],
        "name": "Pass protection",
    },
    "F3": {
        "cols": ["f3_home_motion_rate", "f3_away_motion_rate",
                 "f3_home_pa_rate", "f3_away_pa_rate"],
        "name": "Scheme tendency",
    },
    "F4": {
        "cols": ["f4_ryoe_diff"],
        "name": "Rushing RYOE",
    },
    "F5": {
        "cols": ["f5_home_separation", "f5_away_separation"],
        "name": "Receiving separation",
    },
    "F6": {
        "cols": ["f6_home_snap_shift", "f6_away_snap_shift"],
        "name": "Snap-count shift",
    },
    "F7": {
        "cols": ["f7_ref_avg_total", "f7_ref_game_count"],
        "name": "Referee crew",
    },
    "F8": {
        "cols": ["f8_home_dc_changes", "f8_away_dc_changes"],
        "name": "Depth chart instability",
    },
    "F9": {
        "cols": ["f9_wind_x_outdoor", "f9_rest_diff", "f9_temp",
                 "f9_outdoor", "f9_grass"],
        "name": "Rest/surface/weather",
    },
    "F10": {
        "cols": ["f10_line_move"],
        "name": "Line movement",
    },
}

TARGETS = {
    "margin_resid": "Margin residual (margin - (-spread_line))",
    "total_resid": "Total residual (total - total_line)",
}

SEASONS = [2021, 2022, 2023]


def loso_t_stat(ft_df, family_cols, target_col):
    """Leave-one-season-out pooled t-statistic.
    For each held-out season, fit on the other two and predict.
    Pool all OOS predictions, compute t on the correlation."""
    oos_preds = []
    oos_actuals = []

    for held_out in SEASONS:
        train = ft_df[ft_df["season"] != held_out].dropna(subset=family_cols + [target_col])
        test = ft_df[ft_df["season"] == held_out].dropna(subset=family_cols + [target_col])

        if len(train) < 10 or len(test) < 5:
            continue

        X_train = train[family_cols].values
        y_train = train[target_col].values
        X_test = test[family_cols].values
        y_test = test[target_col].values

        # Simple OLS via ridge with very small alpha
        model = Ridge(alpha=0.01)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        oos_preds.extend(preds)
        oos_actuals.extend(y_test)

    if len(oos_preds) < 20:
        return np.nan, 0, {}

    oos_preds = np.array(oos_preds)
    oos_actuals = np.array(oos_actuals)

    # Correlation test
    r, p = stats.pearsonr(oos_preds, oos_actuals)
    n = len(oos_preds)
    t = r * np.sqrt((n - 2) / (1 - r**2)) if abs(r) < 1 else 0

    # Per-season sign
    per_season = {}
    for s in SEASONS:
        s_mask = ft_df["season"] == s
        s_data = ft_df[s_mask].dropna(subset=family_cols + [target_col])
        if len(s_data) < 10:
            per_season[s] = "N/A"
            continue
        X = s_data[family_cols].values
        y = s_data[target_col].values
        model = Ridge(alpha=0.01)
        model.fit(X, y)
        coefs = model.coef_
        per_season[s] = "+" if np.mean(coefs) > 0 else "-"

    return t, n, per_season


def null_control(ft_df, family_cols, target_col, n_draws=1000):
    """Shuffle team labels within week, compute null t distribution."""
    null_ts = []
    for i in range(n_draws):
        ft_shuffled = ft_df.copy()
        # Shuffle target within week
        for (season, week), idx in ft_shuffled.groupby(["season", "week"]).groups.items():
            rng = np.random.RandomState(42 * 1000 + i + season * 100 + week)
            vals = ft_shuffled.loc[idx, target_col].values.copy()
            rng.shuffle(vals)
            ft_shuffled.loc[idx, target_col] = vals

        t, n, _ = loso_t_stat(ft_shuffled, family_cols, target_col)
        if not np.isnan(t):
            null_ts.append(t)

    if null_ts:
        return np.mean(null_ts), np.std(null_ts)
    return 0.0, 1.0


# ─── PER-FAMILY FITS ────────────────────────────────────────────────
results = []
print("\n" + "="*80)
print("PER-FAMILY RESULTS")
print("="*80)

for fam_id, fam_info in FAMILIES.items():
    cols = fam_info["cols"]
    name = fam_info["name"]
    print(f"\n--- {fam_id}: {name} ---")
    print(f"    Features: {cols}")

    for target_name, target_desc in TARGETS.items():
        t, n, per_season = loso_t_stat(ft, cols, target_name)
        null_mean, null_sd = null_control(ft, cols, target_name, n_draws=200)

        print(f"  {target_name}: t={t:.3f} (n={n}), per-season: {per_season}")
        print(f"    Null: mean={null_mean:.3f}, sd={null_sd:.3f}")

        results.append({
            "family": fam_id,
            "family_name": name,
            "target": target_name,
            "t_stat": t,
            "n_obs": n,
            "per_season_signs": str(per_season),
            "null_mean": null_mean,
            "null_sd": null_sd,
        })

results_df = pd.DataFrame(results)
results_df.to_parquet(os.path.join(os.path.dirname(__file__),
    "../../nfl/data/info/family_results_2021_23.parquet"), index=False)
print("\nSaved family results to nfl/data/info/family_results_2021_23.parquet")


# ─── ALL-FAMILY RIDGE ───────────────────────────────────────────────
print("\n" + "="*80)
print("ALL-FAMILY RIDGE")
print("="*80)

all_cols = []
for fam_info in FAMILIES.values():
    all_cols.extend(fam_info["cols"])

# LOSO alpha selection on 2021-23
alphas = [1, 10, 50, 100, 500, 1000]
best_alpha = None
best_loss = float("inf")

for alpha in alphas:
    losses = []
    for held_out in SEASONS:
        train = ft[ft["season"] != held_out].dropna(subset=all_cols + ["margin_resid"])
        test = ft[ft["season"] == held_out].dropna(subset=all_cols + ["margin_resid"])
        if len(train) < 20 or len(test) < 10:
            continue
        X_train = train[all_cols].fillna(0).values
        y_train = (train["margin"] > train["spread_line"]).astype(int).values  # IE-D8: corrected
        X_test = test[all_cols].fillna(0).values
        y_test = (test["margin"] > test["spread_line"]).astype(int).values  # IE-D8: corrected

        # LogReg with all family features
        lr = LogisticRegression(C=1/alpha, max_iter=1000, solver="lbfgs")
        lr.fit(X_train, y_train)
        probs = lr.predict_proba(X_test)
        if probs.shape[1] == 2:
            losses.append(log_loss(y_test, probs[:, 1]))
        else:
            losses.append(log_loss(y_test, probs))

    if losses:
        avg_loss = np.mean(losses)
        if avg_loss < best_loss:
            best_loss = avg_loss
            best_alpha = alpha
        print(f"  alpha={alpha}: LOSO log-loss={avg_loss:.6f}")

print(f"\nBest alpha: {best_alpha} (log-loss={best_loss:.6f})")

# Close-only baseline
close_losses = []
for held_out in SEASONS:
    test = ft[ft["season"] == held_out].dropna(subset=["margin_resid"])
    if len(test) < 10:
        continue
    y_test = (test["margin"] > test["spread_line"]).astype(int).values  # IE-D8: corrected
    # Close-only model: predict 0.5 for everyone (no information beyond close)
    close_losses.append(log_loss(y_test, np.full(len(y_test), 0.5)))

close_loss = np.mean(close_losses)
improvement = close_loss - best_loss
print(f"\nClose-only log-loss: {close_loss:.6f}")
print(f"All-family ridge log-loss: {best_loss:.6f}")
print(f"Improvement: {improvement:.6f}")

# Ridge on totals
print("\n--- Totals residual ridge ---")
best_alpha_t = None
best_loss_t = float("inf")
for alpha in alphas:
    losses = []
    for held_out in SEASONS:
        train = ft[ft["season"] != held_out].dropna(subset=all_cols + ["total_resid"])
        test = ft[ft["season"] == held_out].dropna(subset=all_cols + ["total_resid"])
        if len(train) < 20 or len(test) < 10:
            continue
        X_train = train[all_cols].fillna(0).values
        y_train = train["total_resid"].values
        X_test = test[all_cols].fillna(0).values
        y_test = test["total_resid"].values

        model = Ridge(alpha=alpha)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mse = np.mean((preds - y_test)**2)
        losses.append(mse)

    if losses:
        avg_mse = np.mean(losses)
        if avg_mse < best_loss_t:
            best_loss_t = avg_mse
            best_alpha_t = alpha

print(f"Best alpha (totals): {best_alpha_t} (LOSO MSE={best_loss_t:.4f})")

# Baseline: predict 0 (the close is the prediction)
baseline_mse = np.mean(ft["total_resid"].dropna()**2)
print(f"Baseline MSE (predict close): {baseline_mse:.4f}")
print(f"Ridge MSE improvement: {baseline_mse - best_loss_t:.4f}")


# ─── MARGIN RIDGE BY SEASON AND TERCILE ─────────────────────────────
print("\n--- Margin ridge by season ---")
for held_out in SEASONS:
    train = ft[ft["season"] != held_out].copy()
    test = ft[ft["season"] == held_out].copy()
    X_train = train[all_cols].fillna(0).values
    y_train = train["margin_resid"].fillna(0).values
    X_test = test[all_cols].fillna(0).values
    y_test = test["margin_resid"].fillna(0).values

    if len(X_test) == 0:
        print(f"  {held_out}: SKIP (no test data)")
        continue

    model = Ridge(alpha=best_alpha_t or 100)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    r, p = stats.pearsonr(preds, y_test)
    print(f"  {held_out}: r={r:.4f}, p={p:.4f}, n={len(test)}")


# ─── FROZEN SPEC ─────────────────────────────────────────────────────
print("\n" + "="*80)
print("FROZEN SPEC")
print("="*80)

# SHA256 of build_feature_table.py
build_path = os.path.join(os.path.dirname(__file__), "build_feature_table.py")
with open(build_path, "rb") as f:
    build_sha = hashlib.sha256(f.read()).hexdigest()
print(f"  build_feature_table.py SHA256: {build_sha}")

# SHA256 of this script
with open(__file__, "rb") as f:
    fit_sha = hashlib.sha256(f.read()).hexdigest()
print(f"  discovery_fit.py SHA256: {fit_sha}")

print(f"  Feature list: {all_cols}")
print(f"  Alpha (margin/cover): {best_alpha}")
print(f"  Alpha (totals): {best_alpha_t}")
print(f"  As-of rule: all features use week N-1 or earlier; F8 uses N-1 only")
print(f"  Aggregation: snap-weighted mean, >=20 snaps, by position group")

# ─── PRE-REGISTRATION OUTCOMES ──────────────────────────────────────
print("\n" + "="*80)
print("PRE-REGISTRATION OUTCOMES")
print("="*80)

# P-IE1-1: No single family |t| >= 2.5 on margin
margin_ts = results_df[results_df["target"] == "margin_resid"]["t_stat"].values
max_margin_t = max(abs(t) for t in margin_ts if not np.isnan(t))
print(f"\nP-IE1-1: max |t| on margin = {max_margin_t:.3f}")
if max_margin_t < 2.5:
    print("  CONFIRMED: no single family reaches |t| >= 2.5 on margin")
else:
    fam = results_df[(results_df["target"] == "margin_resid") &
                      (abs(results_df["t_stat"]) == max_margin_t)]["family"].values[0]
    print(f"  FALSIFIED: {fam} reaches |t| = {max_margin_t:.3f}")

# P-IE1-2: F7 or F9 reaches t >= 2 on totals
f7_t = results_df[(results_df["family"] == "F7") &
                   (results_df["target"] == "total_resid")]["t_stat"].values[0]
f9_t = results_df[(results_df["family"] == "F9") &
                   (results_df["target"] == "total_resid")]["t_stat"].values[0]
print(f"\nP-IE1-2: F7 t={f7_t:.3f}, F9 t={f9_t:.3f}")
if f7_t >= 2 or f9_t >= 2:
    which = "F7" if f7_t >= 2 else "F9"
    print(f"  CONFIRMED: {which} reaches t >= 2 on totals")
else:
    print(f"  FALSIFIED: neither F7 nor F9 reaches t >= 2")

# P-IE1-3: F8 |t| < 1 on both
f8_margin_t = results_df[(results_df["family"] == "F8") &
                          (results_df["target"] == "margin_resid")]["t_stat"].values[0]
f8_total_t = results_df[(results_df["family"] == "F8") &
                         (results_df["target"] == "total_resid")]["t_stat"].values[0]
print(f"\nP-IE1-3: F8 margin t={f8_margin_t:.3f}, total t={f8_total_t:.3f}")
if abs(f8_margin_t) < 1 and abs(f8_total_t) < 1:
    print("  CONFIRMED: F8 reads |t| < 1 on both")
else:
    print(f"  FALSIFIED: F8 exceeds |t| = 1 on at least one target")

# P-IE1-4: All-family ridge improves LOSO log-loss by < 0.003
print(f"\nP-IE1-4: log-loss improvement = {improvement:.6f}")
if improvement < 0.003:
    print("  CONFIRMED: improvement < 0.003")
else:
    print(f"  FALSIFIED: improvement = {improvement:.6f} >= 0.003")

print("\n\nDONE")
