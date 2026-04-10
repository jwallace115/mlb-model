"""
V2 Clean-Room MLB Totals Engine
All PIT-safe features. No API calls. No modifications to existing files.
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import warnings, os
warnings.filterwarnings("ignore")

OUT_DIR = "research/recovery/v2_engine"

# ─────────────────────────────────────────────────────────
# PHASE 0: Feature Inventory
# ─────────────────────────────────────────────────────────
print("=" * 70)
print("PHASE 0: Feature Inventory")
print("=" * 70)

pit = pd.read_parquet("research/recovery/v1_clean_features/baseball_features_pit_v1.parquet")
gt = pd.read_parquet("sim/data/game_table.parquet")
canon = pd.read_parquet("mlb_sim/data/mlb_odds_closing_canonical.parquet")

print(f"PIT features: {pit.shape[0]} games, {pit.shape[1]} columns")
print(f"game_table:   {gt.shape[0]} games")
print(f"canonical:    {canon.shape[0]} rows")

pit_baseball = [
    "home_sp_xfip", "away_sp_xfip",
    "home_sp_k_pct", "away_sp_k_pct",
    "home_sp_bb_pct", "away_sp_bb_pct",
    "home_sp_avg_ip", "away_sp_avg_ip",
    "home_wrc_plus", "away_wrc_plus",
    "home_high_leverage_avail", "away_high_leverage_avail",
    "home_bullpen_delta", "away_bullpen_delta",
    "home_bp_delta_exposure", "away_bp_delta_exposure",
]
pit_context = [
    "park_factor_runs", "park_factor_hr",
    "temperature", "wind_factor_effective",
    "umpire_over_rate",
    "home_rest_days", "away_rest_days",
    "doubleheader_flag",
    "flyball_wind_interaction",
]

inventory_lines = []
inventory_lines.append("# V2 Feature Inventory\n")
inventory_lines.append("## PIT Baseball Features (16)")
for f in pit_baseball:
    inventory_lines.append(f"  - {f} [PIT-safe]")
inventory_lines.append("\n## PIT Context Features (9)")
for f in pit_context:
    inventory_lines.append(f"  - {f} [PIT-safe]")
inventory_lines.append("\n## Market-Derived (from canonical odds)")
inventory_lines.append("  - total_line [MARKET - closing total]")
inventory_lines.append("  - total_over_price [MARKET - closing over juice]")
inventory_lines.append("  - total_under_price [MARKET - closing under juice]")

with open(f"{OUT_DIR}/phase0_feature_inventory.txt", "w") as fh:
    fh.write("\n".join(inventory_lines))
print("Feature inventory written.\n")

# ─────────────────────────────────────────────────────────
# PHASE 1: Build V2 Modeling Table
# ─────────────────────────────────────────────────────────
print("=" * 70)
print("PHASE 1: Build V2 Modeling Table")
print("=" * 70)

canon_sorted = canon.sort_values("book_key", ascending=True)
canon_dedup = canon_sorted.drop_duplicates(subset=["game_pk"], keep="first").copy()
canon_dedup = canon_dedup[canon_dedup["game_pk"].str.match(r"^\d+$", na=False)].copy()
canon_dedup["game_pk"] = canon_dedup["game_pk"].astype(int)
print(f"Canonical odds after dedup: {canon_dedup.shape[0]} games")

df = pit.merge(
    canon_dedup[["game_pk", "total_line", "total_over_price", "total_under_price"]],
    on="game_pk", how="inner"
)
print(f"After merge PIT+canon: {df.shape[0]} games")

df["market_total"] = df["total_line"]
df["market_error"] = df["actual_total"] - df["market_total"]
df["over_result"] = (df["actual_total"] > df["market_total"]).astype(int)
push_mask = df["actual_total"] == df["market_total"]
df.loc[push_mask, "over_result"] = np.nan

# Composite features
df["sp_fip_diff"] = df["away_sp_xfip"] - df["home_sp_xfip"]
df["sp_k_diff"] = df["home_sp_k_pct"] - df["away_sp_k_pct"]
df["sp_bb_diff"] = df["away_sp_bb_pct"] - df["home_sp_bb_pct"]
df["sp_ip_diff"] = df["home_sp_avg_ip"] - df["away_sp_avg_ip"]
df["offense_diff"] = df["home_wrc_plus"] - df["away_wrc_plus"]
df["bp_fip_diff"] = df["away_bullpen_delta"] - df["home_bullpen_delta"]
df["bp_avail_diff"] = df["home_high_leverage_avail"] - df["away_high_leverage_avail"]
df["rest_diff"] = df["home_rest_days"] - df["away_rest_days"]
df["home_flag"] = 1

df["sp_fip_sum"] = df["home_sp_xfip"] + df["away_sp_xfip"]
df["offense_sum"] = df["home_wrc_plus"] + df["away_wrc_plus"]
df["bp_fip_sum"] = df["home_bullpen_delta"] + df["away_bullpen_delta"]
df["bp_exposure_sum"] = df["home_bp_delta_exposure"] + df["away_bp_delta_exposure"]

df = df[df["innings_played"] >= 9].copy()
print(f"After filtering 9+ innings: {df.shape[0]} games")

model_features_all = [
    "sp_fip_diff", "sp_fip_sum", "sp_k_diff", "sp_bb_diff", "sp_ip_diff",
    "offense_diff", "offense_sum",
    "bp_fip_diff", "bp_fip_sum", "bp_avail_diff", "bp_exposure_sum",
    "park_factor_runs", "temperature", "wind_factor_effective",
    "umpire_over_rate", "rest_diff", "doubleheader_flag",
    "flyball_wind_interaction",
]
df_clean = df.dropna(subset=model_features_all + ["market_total", "actual_total"])
print(f"After dropping nulls: {df_clean.shape[0]} games")

print("\nCoverage by season:")
for s in sorted(df_clean.season.unique()):
    n = (df_clean.season == s).sum()
    print(f"  {s}: {n} games")

df_clean.to_parquet(f"{OUT_DIR}/v2_modeling_table.parquet", index=False)
print(f"\nModeling table saved: {df_clean.shape}")

# ─────────────────────────────────────────────────────────
# PHASE 2: Build Three Models
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 2: Build Three Models")
print("=" * 70)

train = df_clean[df_clean.season.isin([2022, 2023])].copy()
val = df_clean[df_clean.season == 2024].copy()
oos = df_clean[df_clean.season == 2025].copy()
print(f"Train: {len(train)}, Val: {len(val)}, OOS: {len(oos)}")

for label, subset in [("Train", train), ("Val", val), ("OOS", oos)]:
    rmse = np.sqrt(mean_squared_error(subset["actual_total"], subset["market_total"]))
    mae = mean_absolute_error(subset["actual_total"], subset["market_total"])
    print(f"Market baseline {label}: RMSE={rmse:.4f}, MAE={mae:.4f}")

features_A = [
    "sp_fip_diff", "sp_fip_sum", "offense_diff", "offense_sum",
    "bp_fip_diff", "bp_fip_sum", "bp_avail_diff",
    "park_factor_runs", "temperature", "wind_factor_effective",
    "umpire_over_rate", "rest_diff", "doubleheader_flag",
    "flyball_wind_interaction",
]
features_B = features_A.copy()
features_C = features_A + ["market_total"]

results = {}
report_lines = []
report_lines.append("# V2 Engine - Model Results\n")

def american_to_decimal(price):
    if pd.isna(price):
        return np.nan
    if price > 0:
        return 1 + price / 100
    else:
        return 1 + 100 / abs(price)

def compute_roi(actuals, markets, prices, direction="under"):
    wins = losses = pushes = 0
    profit = 0.0
    for act, mkt, price in zip(actuals, markets, prices):
        if act == mkt:
            pushes += 1
            continue
        dec = american_to_decimal(price)
        if pd.isna(dec):
            dec = american_to_decimal(-110)
        if direction == "under":
            if act < mkt:
                wins += 1
                profit += (dec - 1)
            else:
                losses += 1
                profit -= 1
        else:
            if act > mkt:
                wins += 1
                profit += (dec - 1)
            else:
                losses += 1
                profit -= 1
    n_bets = wins + losses
    roi = profit / n_bets * 100 if n_bets > 0 else 0
    hit = wins / n_bets * 100 if n_bets > 0 else 0
    return wins, losses, pushes, hit, roi

for model_name, features, target in [
    ("Model_A", features_A, "actual_total"),
    ("Model_B", features_B, "market_error"),
    ("Model_C", features_C, "actual_total"),
]:
    print(f"\n--- {model_name} (target={target}) ---")
    report_lines.append(f"\n## {model_name} (target={target})")
    report_lines.append(f"Features: {features}")

    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[features])
    X_val = scaler.transform(val[features])
    X_oos = scaler.transform(oos[features])

    y_train = train[target].values
    y_val = val[target].values
    y_oos = oos[target].values

    model = Ridge(alpha=50)
    model.fit(X_train, y_train)

    coef_df = pd.DataFrame({
        "feature": features,
        "coef": model.coef_,
    }).assign(abs_coef=lambda x: x.coef.abs()).sort_values("abs_coef", ascending=False)

    report_lines.append(f"Intercept: {model.intercept_:.4f}")
    report_lines.append("Coefficients:")
    for _, row in coef_df.iterrows():
        report_lines.append(f"  {row['feature']:30s} {row['coef']:+.4f}")

    print(f"  Intercept: {model.intercept_:.4f}")
    for _, row in coef_df.head(5).iterrows():
        print(f"    {row['feature']:30s} {row['coef']:+.4f}")

    for label, X, y in [("Train", X_train, y_train), ("Val", X_val, y_val), ("OOS", X_oos, y_oos)]:
        pred = model.predict(X)
        rmse = np.sqrt(mean_squared_error(y, pred))
        mae = mean_absolute_error(y, pred)
        msg = f"  {label}: RMSE={rmse:.4f}, MAE={mae:.4f}"
        print(msg)
        report_lines.append(msg)

    oos_pred = model.predict(X_oos)
    val_pred = model.predict(X_val)
    results[model_name] = {
        "model": model, "scaler": scaler, "features": features, "target": target,
        "oos_pred": oos_pred, "val_pred": val_pred,
    }

# ─────────────────────────────────────────────────────────
# PHASE 3: Market Comparison
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 3: Market Comparison")
print("=" * 70)
report_lines.append("\n\n# Phase 3: Market Comparison\n")

for model_name in ["Model_A", "Model_B", "Model_C"]:
    res = results[model_name]
    oos_pred = res["oos_pred"]
    if res["target"] == "actual_total":
        predicted_total = oos_pred
    else:
        predicted_total = oos.market_total.values + oos_pred

    model_rmse = np.sqrt(mean_squared_error(oos.actual_total.values, predicted_total))
    market_rmse = np.sqrt(mean_squared_error(oos.actual_total.values, oos.market_total.values))
    delta_rmse = model_rmse - market_rmse

    print(f"\n--- {model_name} ---")
    print(f"  Model RMSE: {model_rmse:.4f} vs Market: {market_rmse:.4f} (delta: {delta_rmse:+.4f})")
    report_lines.append(f"\n## {model_name}")
    report_lines.append(f"  Model RMSE: {model_rmse:.4f} vs Market: {market_rmse:.4f} (delta: {delta_rmse:+.4f})")

    edge = predicted_total - oos.market_total.values

    hdr = f"  {'Thresh':>6s} {'Dir':>6s} {'N':>5s} {'W':>5s} {'L':>5s} {'Hit%':>6s} {'ROI@-110':>9s} {'ROI@real':>9s}"
    print(hdr)
    report_lines.append(hdr)

    for thresh in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]:
        for direction in ["under", "over"]:
            if direction == "under":
                mask = edge <= -thresh
                prices_real = oos.total_under_price.values[mask]
            else:
                mask = edge >= thresh
                prices_real = oos.total_over_price.values[mask]

            if mask.sum() < 10:
                continue

            actuals_m = oos.actual_total.values[mask]
            markets_m = oos.market_total.values[mask]
            prices_110 = np.full(mask.sum(), -110.0)

            w1, l1, p1, hit1, roi1 = compute_roi(actuals_m, markets_m, prices_110, direction)
            w2, l2, p2, hit2, roi2 = compute_roi(actuals_m, markets_m, prices_real, direction)
            n = w1 + l1 + p1
            line = f"  {thresh:6.2f} {direction:>6s} {n:5d} {w1:5d} {l1:5d} {hit1:5.1f}% {roi1:+8.1f}% {roi2:+8.1f}%"
            print(line)
            report_lines.append(line)

# ─────────────────────────────────────────────────────────
# PHASE 4: Signal Map
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 4: Signal Map - Context Splits")
print("=" * 70)
report_lines.append("\n\n# Phase 4: Signal Map\n")

for model_name in ["Model_B", "Model_C"]:
    res = results[model_name]
    oos_pred = res["oos_pred"]
    if res["target"] == "actual_total":
        predicted_total = oos_pred
    else:
        predicted_total = oos.market_total.values + oos_pred

    edge = predicted_total - oos.market_total.values
    model_error = oos.actual_total.values - predicted_total
    market_error_oos = oos.actual_total.values - oos.market_total.values

    print(f"\n--- {model_name} Context Splits (OOS 2025) ---")
    report_lines.append(f"\n## {model_name} - Context Splits (OOS 2025)")

    splits = {
        "SP mismatch large (|FIP diff|>1.0)": oos["sp_fip_diff"].abs() > 1.0,
        "SP mismatch small (|FIP diff|<0.3)": oos["sp_fip_diff"].abs() < 0.3,
        "Total band low (<7.5)":   oos["market_total"] < 7.5,
        "Total band mid (7.5-9.5)": (oos["market_total"] >= 7.5) & (oos["market_total"] <= 9.5),
        "Total band high (>9.5)":  oos["market_total"] > 9.5,
        "BP mismatch (|bp_fip_diff|>0.5)": oos["bp_fip_diff"].abs() > 0.5,
        "Cold weather (temp<50)":  oos["temperature"] < 50,
        "Hot weather (temp>85)":   oos["temperature"] > 85,
        "High wind (wind_eff>0.3)": oos["wind_factor_effective"] > 0.3,
        "Ump high over (top Q)":   oos["umpire_over_rate"] > oos["umpire_over_rate"].quantile(0.75),
        "Ump low over (bottom Q)": oos["umpire_over_rate"] < oos["umpire_over_rate"].quantile(0.25),
    }

    hdr = f"  {'Context':<40s} {'N':>5s} {'MdlRMSE':>8s} {'MktRMSE':>8s} {'Delta':>7s} {'U_Hit':>6s} {'O_Hit':>6s} {'U_ROI':>7s} {'O_ROI':>7s}"
    print(hdr)
    report_lines.append(hdr)

    for label, mask in splits.items():
        n = mask.sum()
        if n < 20:
            continue
        idx = mask.values
        me = model_error[idx]
        mke = market_error_oos[idx]
        model_rmse_s = np.sqrt(np.mean(me ** 2))
        mkt_rmse_s = np.sqrt(np.mean(mke ** 2))
        delta = model_rmse_s - mkt_rmse_s

        edge_s = edge[idx]
        act_s = oos.actual_total.values[idx]
        mkt_s = oos.market_total.values[idx]
        under_prices = oos.total_under_price.values[idx]
        over_prices = oos.total_over_price.values[idx]

        # Under signals (edge < -0.5)
        u_mask = edge_s < -0.5
        if u_mask.sum() > 5:
            w, l, p, hit_u, roi_u = compute_roi(act_s[u_mask], mkt_s[u_mask], under_prices[u_mask], "under")
        else:
            hit_u, roi_u = 0, 0

        # Over signals (edge > 0.5)
        o_mask = edge_s > 0.5
        if o_mask.sum() > 5:
            w, l, p, hit_o, roi_o = compute_roi(act_s[o_mask], mkt_s[o_mask], over_prices[o_mask], "over")
        else:
            hit_o, roi_o = 0, 0

        line = f"  {label:<40s} {n:5d} {model_rmse_s:8.3f} {mkt_rmse_s:8.3f} {delta:+7.3f} {hit_u:5.1f}% {hit_o:5.1f}% {roi_u:+6.1f}% {roi_o:+6.1f}%"
        print(line)
        report_lines.append(line)

# ─────────────────────────────────────────────────────────
# PHASE 5: Threshold Derivation
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 5: Threshold Derivation")
print("=" * 70)
report_lines.append("\n\n# Phase 5: Threshold Derivation\n")

for model_name in ["Model_C", "Model_B"]:
    res = results[model_name]
    oos_pred = res["oos_pred"]
    val_pred = res["val_pred"]

    if res["target"] == "actual_total":
        edge_oos = oos_pred - oos.market_total.values
        edge_val = val_pred - val.market_total.values
    else:
        edge_oos = oos_pred  # predicted market_error: positive = over signal
        edge_val = val_pred

    print(f"\n{model_name} - Threshold scan (Val 2024 / OOS 2025)")
    report_lines.append(f"\n## {model_name} - Threshold scan")
    hdr = f"  {'Thresh':>6s} {'Dir':>6s} | {'N_v':>4s} {'Hit_v':>6s} {'ROI_v':>7s} | {'N_o':>4s} {'Hit_o':>6s} {'ROI_o':>7s} | {'Stable':>6s}"
    print(hdr)
    report_lines.append(hdr)

    for thresh in [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        for direction in ["under", "over"]:
            if direction == "under":
                mv = edge_val <= -thresh
                mo = edge_oos <= -thresh
                pv = val.total_under_price.values[mv]
                po = oos.total_under_price.values[mo]
            else:
                mv = edge_val >= thresh
                mo = edge_oos >= thresh
                pv = val.total_over_price.values[mv]
                po = oos.total_over_price.values[mo]

            nv = mv.sum()
            no = mo.sum()
            if nv < 10 and no < 10:
                continue

            if nv >= 5:
                wv, lv, ppv, hitv, roiv = compute_roi(val.actual_total.values[mv], val.market_total.values[mv], pv, direction)
            else:
                hitv, roiv = 0, 0
            if no >= 5:
                wo, lo, ppo, hito, roio = compute_roi(oos.actual_total.values[mo], oos.market_total.values[mo], po, direction)
            else:
                hito, roio = 0, 0

            # Stability: both positive ROI
            stable = "YES" if roiv > 0 and roio > 0 else "no"
            line = f"  {thresh:6.2f} {direction:>6s} | {nv:4d} {hitv:5.1f}% {roiv:+6.1f}% | {no:4d} {hito:5.1f}% {roio:+6.1f}% | {stable:>6s}"
            print(line)
            report_lines.append(line)

# ─────────────────────────────────────────────────────────
# PHASE 6: Verdict
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 6: Verdict")
print("=" * 70)
report_lines.append("\n\n# Phase 6: Verdict\n")

market_rmse_oos = np.sqrt(mean_squared_error(oos.actual_total.values, oos.market_total.values))

# Model C metrics
res_C = results["Model_C"]
pred_C = res_C["oos_pred"]
modelC_rmse = np.sqrt(mean_squared_error(oos.actual_total.values, pred_C))
edge_C = pred_C - oos.market_total.values

# Model B metrics
res_B = results["Model_B"]
pred_B_total = oos.market_total.values + res_B["oos_pred"]
modelB_rmse = np.sqrt(mean_squared_error(oos.actual_total.values, pred_B_total))

# Best signal scan
best_roi = -999
best_desc = ""
for thresh in [0.5, 0.75, 1.0, 1.5]:
    for direction in ["under", "over"]:
        if direction == "under":
            mask = edge_C <= -thresh
            prices = oos.total_under_price.values[mask]
        else:
            mask = edge_C >= thresh
            prices = oos.total_over_price.values[mask]
        if mask.sum() < 20:
            continue
        w, l, p, hit, roi = compute_roi(oos.actual_total.values[mask], oos.market_total.values[mask], prices, direction)
        if roi > best_roi:
            best_roi = roi
            best_desc = f"Model_C {direction} edge>={thresh}: N={w+l+p}, Hit={hit:.1f}%, ROI={roi:+.1f}%"

verdict_lines = []
verdict_lines.append(f"Market RMSE (OOS 2025):  {market_rmse_oos:.4f}")
verdict_lines.append(f"Model A RMSE (OOS 2025): {results['Model_A']['rmse_oos'] if 'rmse_oos' in results['Model_A'] else np.sqrt(mean_squared_error(oos.actual_total.values, results['Model_A']['oos_pred'])):.4f}")
verdict_lines.append(f"Model B RMSE (OOS 2025): {modelB_rmse:.4f}")
verdict_lines.append(f"Model C RMSE (OOS 2025): {modelC_rmse:.4f}")
verdict_lines.append(f"Best signal: {best_desc}")

# Store RMSE for comparison
for mn in ["Model_A", "Model_B", "Model_C"]:
    r = results[mn]
    p = r["oos_pred"] if r["target"] == "actual_total" else oos.market_total.values + r["oos_pred"]
    results[mn]["rmse_oos"] = np.sqrt(mean_squared_error(oos.actual_total.values, p))
    results[mn]["mae_oos"] = mean_absolute_error(oos.actual_total.values, p)

# Decision
if modelC_rmse < market_rmse_oos and best_roi > 3.0:
    verdict = "DEPLOYABLE BROAD"
elif best_roi > 1.0:
    verdict = "NARROW POCKET"
elif modelC_rmse < market_rmse_oos + 0.05:
    verdict = "SHADOW-ONLY"
else:
    verdict = "COLLAPSE"

verdict_lines.append(f"\n>>> VERDICT: {verdict} <<<")

for line in verdict_lines:
    print(line)
    report_lines.append(line)

# ─────────────────────────────────────────────────────────
# PHASE 7: V1 vs V2 Comparison
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 7: V1 vs V2 Comparison")
print("=" * 70)
report_lines.append("\n\n# Phase 7: V1 vs V2 Comparison\n")

comparison = []
comparison.append(f"{'Metric':<35s} {'Market':>10s} {'V2_A':>10s} {'V2_B':>10s} {'V2_C':>10s}")
comparison.append("-" * 80)
comparison.append(f"{'RMSE (OOS 2025)':<35s} {market_rmse_oos:10.4f} {results['Model_A']['rmse_oos']:10.4f} {results['Model_B']['rmse_oos']:10.4f} {results['Model_C']['rmse_oos']:10.4f}")

market_mae_oos = mean_absolute_error(oos.actual_total.values, oos.market_total.values)
comparison.append(f"{'MAE (OOS 2025)':<35s} {market_mae_oos:10.4f} {results['Model_A']['mae_oos']:10.4f} {results['Model_B']['mae_oos']:10.4f} {results['Model_C']['mae_oos']:10.4f}")

for mn in ["Model_A", "Model_B", "Model_C"]:
    r = results[mn]
    p = r["oos_pred"] if r["target"] == "actual_total" else oos.market_total.values + r["oos_pred"]
    results[mn]["corr_oos"] = np.corrcoef(oos.actual_total.values, p)[0, 1]

mkt_corr = np.corrcoef(oos.actual_total.values, oos.market_total.values)[0, 1]
comparison.append(f"{'Corr(pred, actual) OOS':<35s} {mkt_corr:10.4f} {results['Model_A']['corr_oos']:10.4f} {results['Model_B']['corr_oos']:10.4f} {results['Model_C']['corr_oos']:10.4f}")

mkt_var = np.var(oos.actual_total.values)
for mn in ["Model_A", "Model_B", "Model_C"]:
    mkt_r2 = 1 - (market_rmse_oos ** 2) / mkt_var
    mod_r2 = 1 - (results[mn]["rmse_oos"] ** 2) / mkt_var
    results[mn]["delta_r2"] = mod_r2 - mkt_r2

comparison.append(f"{'Delta-R2 vs market':<35s} {'--':>10s} {results['Model_A']['delta_r2']:+10.4f} {results['Model_B']['delta_r2']:+10.4f} {results['Model_C']['delta_r2']:+10.4f}")

comparison.append("")
comparison.append("Phase 9 baseline (from project memory):")
comparison.append("  25 features, Ridge(alpha=50), sigma=4.361")
comparison.append("  Phase 8 OOS STRONG tier: +2.3% ROI")
comparison.append("  Phase 7 OOS ROI @ edge>=1.0: -0.5%")

for line in comparison:
    print(line)
    report_lines.append(line)

# ─────────────────────────────────────────────────────────
# Save
# ─────────────────────────────────────────────────────────
with open(f"{OUT_DIR}/v2_engine_report.txt", "w") as fh:
    fh.write("\n".join(report_lines))

print(f"\nAll output saved to {OUT_DIR}/")
print("Files: v2_engine_report.txt, v2_modeling_table.parquet, phase0_feature_inventory.txt")
