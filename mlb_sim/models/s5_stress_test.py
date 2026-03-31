#!/usr/bin/env python3
"""
MLB Simulation Engine — Phase S5: Stress Test and Stability Validation
======================================================================
Pressure-tests S4 edge results. Tries to break them, not confirm them.
Only 2024 OOS results count as validation evidence.
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
MODEL_DIR = Path(__file__).resolve().parent
SIM_DATA = Path(__file__).resolve().parent.parent / "data"

# Load calibration params
with open(MODEL_DIR / "calibration_params.json") as f:
    cal_params = json.load(f)

CSW_Q75 = cal_params["csw_q75"]
CSW_Q50 = cal_params["csw_q50"]
LOW_RUN_THRESH = cal_params["low_run_env_threshold"]


def wilson_ci(wins, n, z=1.96):
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return 0, 0, 0
    p_hat = wins / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return p_hat, max(0, center - margin), min(1, center + margin)


def roi_110(wins, losses):
    n = wins + losses
    if n == 0:
        return 0, 0
    return (wins * (100 / 110) - losses) / n * 100, n


def run_s5():
    # ── Load S4 calibration report ───────────────────────────────────────────
    print("Loading data...")
    report = pd.read_parquet(EVAL_DIR / "s4_calibration_report.parquet")

    # We need train sims too — rebuild from S3 + S4 logic
    # Load raw S3 OOS results for uncalibrated comparison
    sim_oos_raw = pd.read_parquet(EVAL_DIR / "sim_results_oos_2024.parquet")
    sim_oos_raw["game_pk"] = sim_oos_raw["game_pk"].astype(str)

    # Need all-seasons data for Task 1
    # Rebuild train by running sim on 2022-2023
    # Actually: load sim_inputs + run path model + simulate inline
    import pickle
    from sklearn.isotonic import IsotonicRegression

    sim_inputs = pd.read_parquet(SIM_DATA / "sim_inputs_historical_2022_2024.parquet")
    sim_inputs["game_pk"] = sim_inputs["game_pk"].astype(str)

    with open(MODEL_DIR / "starter_path_model.pkl", "rb") as f:
        s2 = pickle.load(f)
    with open(MODEL_DIR / "run_dist_params.json") as f:
        rp = {int(k): v for k, v in json.load(f).items()}

    SIM_FT = PROJECT_ROOT / "sim" / "data" / "feature_table.parquet"
    ft = pd.read_parquet(SIM_FT)
    ft["game_pk"] = ft["game_pk"].astype(str)
    m3r = pd.read_csv(PROJECT_ROOT / "research" / "mlb_phase_a" / "m3_residuals_all_seasons.csv")
    m3r["game_id"] = m3r["game_id"].astype(str)

    hist_cl = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "mlb_historical_closing_lines.parquet")
    mkt = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "market_snapshots.parquet")
    hist_cl["game_pk"] = hist_cl["game_pk"].astype(str)
    id_col = "game_id" if "game_id" in mkt.columns else "game_pk"
    mkt[id_col] = mkt[id_col].astype(str)
    cl = pd.concat([
        hist_cl[["game_pk", "close_total"]].rename(columns={"close_total": "closing_line"}),
        mkt[[id_col, "close_total"]].rename(columns={id_col: "game_pk", "close_total": "closing_line"})
    ]).drop_duplicates("game_pk", keep="first")

    # Compute path probs
    fc = sim_inputs.dropna(subset=s2["features"]).copy()
    Xs = s2["scaler"].transform(fc[s2["features"]].values)
    probs = s2["model"].predict_proba(Xs)
    fc["p_path0"] = probs[:, 0]
    fc["p_path1"] = probs[:, 1]
    fc["p_path2"] = probs[:, 2]

    # Pivot to game level
    h = fc[fc["is_home"] == 1][["game_pk", "season", "p_path0", "p_path1", "p_path2", "sp_csw_pct", "sp_whiff_pct"]].rename(
        columns={"p_path0": "hp0", "p_path1": "hp1", "p_path2": "hp2", "sp_csw_pct": "hcsw", "sp_whiff_pct": "hwhiff"})
    a = fc[fc["is_home"] == 0][["game_pk", "p_path0", "p_path1", "p_path2", "sp_csw_pct", "sp_whiff_pct"]].rename(
        columns={"p_path0": "ap0", "p_path1": "ap1", "p_path2": "ap2", "sp_csw_pct": "acsw", "sp_whiff_pct": "awhiff"})

    gall = h.merge(a, on="game_pk").merge(ft[["game_pk", "home_team", "away_team", "home_score", "away_score", "actual_total"]], on="game_pk", how="left")
    gall = gall.merge(m3r[["game_id", "m3_projection"]].rename(columns={"game_id": "game_pk"}), on="game_pk", how="left")
    gall = gall.merge(cl, on="game_pk", how="left")

    def assign_regime(p0, p1):
        if p0 == 2 and p1 == 2: return 1
        if p0 == 0 and p1 == 0: return 4
        if p0 == 0 or p1 == 0: return 3
        return 2

    # Simulate ALL seasons
    print("Simulating all seasons for stability testing...")
    rng = np.random.default_rng(999)
    N = 5000
    all_res = []
    for _, g in gall.dropna(subset=["hp0", "ap0", "actual_total"]).iterrows():
        hp = np.array([g["hp0"], g["hp1"], g["hp2"]]); hp /= hp.sum()
        ap = np.array([g["ap0"], g["ap1"], g["ap2"]]); ap /= ap.sum()
        mu_h = max((g.get("m3_projection") or 8.5) * 0.505, 1.0)
        mu_a = max((g.get("m3_projection") or 8.5) * 0.495, 1.0)
        hps = rng.choice([0,1,2], N, p=hp)
        aps = rng.choice([0,1,2], N, p=ap)
        tots = np.zeros(N); regs = np.zeros(N, dtype=int)
        for i in range(N):
            reg = assign_regime(hps[i], aps[i]); regs[i] = reg
            r = rp[reg]["r"]
            tots[i] = rng.negative_binomial(r, r/(r+mu_h)) + rng.negative_binomial(r, r/(r+mu_a))
        cline = g.get("closing_line")
        all_res.append({
            "game_pk": g["game_pk"], "season": g["season"],
            "actual_total": g["actual_total"], "closing_line": cline,
            "sim_mean_total": tots.mean(), "sim_std_total": tots.std(),
            "p_over_line": (tots > cline).mean() if pd.notna(cline) else np.nan,
            "dominant_regime": int(pd.Series(regs).mode()[0]),
            "hp0": g["hp0"], "ap0": g["ap0"],
            "hcsw": g.get("hcsw"), "acsw": g.get("acsw"),
        })
    alldf = pd.DataFrame(all_res)
    alldf["low_run_env"] = (alldf["sim_mean_total"] <= LOW_RUN_THRESH).astype(int)
    alldf["dual_high_csw"] = ((alldf["hcsw"].fillna(0) >= CSW_Q75) & (alldf["acsw"].fillna(0) >= CSW_Q75)).astype(int)

    # Apply isotonic calibration (fit on train, apply to all)
    train_cal = alldf[alldf["season"].isin([2022, 2023])].dropna(subset=["closing_line", "p_over_line"]).copy()
    train_cal["ao"] = (train_cal["actual_total"] > train_cal["closing_line"]).astype(int)
    iso_low = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    iso_norm = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    tl = train_cal[train_cal["low_run_env"] == 1]; tn = train_cal[train_cal["low_run_env"] == 0]
    if len(tl) > 20: iso_low.fit(tl["p_over_line"].values, tl["ao"].values)
    if len(tn) > 20: iso_norm.fit(tn["p_over_line"].values, tn["ao"].values)

    valid = alldf.dropna(subset=["closing_line", "p_over_line"]).copy()
    valid["actual_over"] = (valid["actual_total"] > valid["closing_line"]).astype(int)
    valid["cal_p_over"] = np.where(valid["low_run_env"] == 1,
        iso_low.predict(valid["p_over_line"].values), iso_norm.predict(valid["p_over_line"].values))
    valid["cal_p_under"] = 1 - valid["cal_p_over"]
    valid["fragile_normal"] = ((valid["dominant_regime"] == 3) & (valid["low_run_env"] == 0)).astype(int)

    print(f"Total games with lines: {len(valid)}")
    for s in sorted(valid["season"].unique()):
        print(f"  {s}: {len(valid[valid['season']==s])}")

    # ══════════════════════════════════════════════════════════════
    # TASK 1 — SEASON-BY-SEASON STABILITY
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("TASK 1 — SEASON-BY-SEASON STABILITY")
    print("="*60)

    cohorts = {
        "A: p_over>57%":  lambda d: d[d["cal_p_over"] > 0.57],
        "B: p_under>57%": lambda d: d[d["cal_p_under"] > 0.57],
        "C: p_under>60%": lambda d: d[d["cal_p_under"] > 0.60],
        "D: Fragile×norm": lambda d: d[d["fragile_normal"] == 1],
        "E: dual_high_csw": lambda d: d[d["dual_high_csw"] == 1],
    }
    # For A/D: win = actual_over; For B/C/E: win = actual_under
    win_col = {"A": "actual_over", "B": "actual_under", "C": "actual_under",
               "D": "actual_over", "E": "actual_under"}
    valid["actual_under"] = 1 - valid["actual_over"]

    print(f"\n{'Cohort':<20} | {'Season':>6} | {'N':>5} | {'Win%':>6} | {'ROI':>8} | {'Net units':>10} | {'Label':>6}")
    print("-"*75)
    for cname, cfunc in cohorts.items():
        wc = win_col[cname[0]]
        season_units = {}
        for s in [2022, 2023, 2024]:
            sub = cfunc(valid[valid["season"] == s])
            if len(sub) == 0:
                season_units[s] = 0
                continue
            w = sub[wc].sum(); l = len(sub) - w
            r, n = roi_110(int(w), int(l))
            net = w * (100/110) - l
            season_units[s] = net
            label = "TRAIN" if s < 2024 else "OOS"
            thin = " (THIN)" if n < 40 else ""
            print(f"{cname:<20} | {s:>6} | {n:>5} | {w/(w+l)*100 if (w+l)>0 else 0:>5.1f}% | {r:>+7.1f}% | {net:>+9.2f}u | {label}{thin}")
        total_net = sum(season_units.values())
        if total_net != 0:
            for s, nu in season_units.items():
                if abs(nu / total_net) > 0.60 and total_net > 0:
                    print(f"  *** {cname} — {s} contributes {abs(nu/total_net)*100:.0f}% of net units (SEASON CONCENTRATED)")

    # ══════════════════════════════════════════════════════════════
    # TASK 2 — THRESHOLD SENSITIVITY
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("TASK 2 — THRESHOLD SENSITIVITY (2024 OOS only)")
    print("="*60)

    oos = valid[valid["season"] == 2024]
    thresholds = [0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.60]

    print(f"\nOVER side:")
    print(f"{'Thresh':>6} | {'N':>5} | {'Win%':>6} | {'CI low':>7} | {'CI high':>8} | {'ROI':>8}")
    print("-"*52)
    prev_wr_o = 0
    mono_o = True
    for t in thresholds:
        sub = oos[oos["cal_p_over"] > t]
        w = sub["actual_over"].sum(); l = len(sub) - w; n = int(w + l)
        wr, ci_lo, ci_hi = wilson_ci(int(w), n)
        r, _ = roi_110(int(w), int(l))
        thin = " (THIN)" if n < 40 else ""
        print(f" >{t:.0%} | {n:>5} | {wr*100:>5.1f}% | {ci_lo*100:>6.1f}% | {ci_hi*100:>7.1f}% | {r:>+7.1f}%{thin}")
        if wr < prev_wr_o and n >= 40: mono_o = False
        prev_wr_o = wr

    print(f"\nUNDER side:")
    print(f"{'Thresh':>6} | {'N':>5} | {'Win%':>6} | {'CI low':>7} | {'CI high':>8} | {'ROI':>8}")
    print("-"*52)
    prev_wr_u = 0
    mono_u = True
    for t in thresholds:
        sub = oos[oos["cal_p_under"] > t]
        w = sub["actual_under"].sum(); l = len(sub) - w; n = int(w + l)
        wr, ci_lo, ci_hi = wilson_ci(int(w), n)
        r, _ = roi_110(int(w), int(l))
        thin = " (THIN)" if n < 40 else ""
        print(f" >{t:.0%} | {n:>5} | {wr*100:>5.1f}% | {ci_lo*100:>6.1f}% | {ci_hi*100:>7.1f}% | {r:>+7.1f}%{thin}")
        if wr < prev_wr_u and n >= 40: mono_u = False
        prev_wr_u = wr

    print(f"\n  Over monotonic: {'YES' if mono_o else 'NO — non-monotonic win rate'}")
    print(f"  Under monotonic: {'YES' if mono_u else 'NO — non-monotonic win rate'}")

    # ══════════════════════════════════════════════════════════════
    # TASK 3 — WITHIN-2024 TEMPORAL SPLIT
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("TASK 3 — WITHIN-2024 TEMPORAL SPLIT")
    print("="*60)

    oos_sorted = oos.sort_values("date" if "date" in oos.columns else "game_pk")
    mid = len(oos_sorted) // 2
    h1 = oos_sorted.iloc[:mid].copy()
    h2 = oos_sorted.iloc[mid:].copy()

    # Get date ranges
    d1_min = h1["date"].min() if "date" in h1.columns else "?"
    d1_max = h1["date"].max() if "date" in h1.columns else "?"
    d2_min = h2["date"].min() if "date" in h2.columns else "?"
    d2_max = h2["date"].max() if "date" in h2.columns else "?"
    print(f"\n  Half 1: {d1_min} to {d1_max}, N={len(h1)}")
    print(f"  Half 2: {d2_min} to {d2_max}, N={len(h2)}")

    print(f"\n{'Cohort':<20} | {'Half':>5} | {'N':>5} | {'Win%':>6} | {'ROI':>8} | {'Net units':>10}")
    print("-"*65)
    for cname, cfunc in cohorts.items():
        wc = win_col[cname[0]]
        half_units = {}
        for hname, hdf in [("H1", h1), ("H2", h2)]:
            sub = cfunc(hdf)
            if len(sub) == 0:
                half_units[hname] = 0
                continue
            w = sub[wc].sum(); l = len(sub) - w; n = int(w + l)
            r, _ = roi_110(int(w), int(l))
            net = w * (100/110) - l
            half_units[hname] = net
            thin = " (THIN)" if n < 40 else ""
            print(f"{cname:<20} | {hname:>5} | {n:>5} | {w/(w+l)*100 if (w+l)>0 else 0:>5.1f}% | {r:>+7.1f}% | {net:>+9.2f}u{thin}")
        total = sum(half_units.values())
        if total != 0:
            for hname, nu in half_units.items():
                if abs(nu / total) > 0.70:
                    print(f"  *** {cname} — {hname} contributes {abs(nu/total)*100:.0f}% (HALF CONCENTRATED)")

    # ══════════════════════════════════════════════════════════════
    # TASK 4 — MARKET REALISM CHECK
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("TASK 4 — MARKET REALISM CHECK")
    print("="*60)

    # 4A: Line-band concentration
    print(f"\n  Step 4A: Line-band concentration")
    line_bands = [0, 7.0, 7.5, 8.0, 8.5, 9.0, 20]
    line_labels = ["<=7.0", "7.5", "8.0", "8.5", "9.0", ">=9.5"]

    for cohort_name, cohort_df in [("p_under>60%", oos[oos["cal_p_under"] > 0.60]),
                                     ("Fragile×norm", oos[oos["fragile_normal"] == 1])]:
        print(f"\n    {cohort_name} (N={len(cohort_df)}) vs baseline (N={len(oos)}):")
        print(f"    {'Band':<8} | {'Cohort%':>8} | {'Baseline%':>10}")
        print("    " + "-"*35)
        coh_bins = pd.cut(cohort_df["closing_line"], bins=line_bands, labels=line_labels, include_lowest=True)
        base_bins = pd.cut(oos["closing_line"], bins=line_bands, labels=line_labels, include_lowest=True)
        for lb in line_labels:
            cp = (coh_bins == lb).mean() * 100 if len(cohort_df) > 0 else 0
            bp = (base_bins == lb).mean() * 100
            flag = " ***" if cp > bp * 1.5 and cp > 5 else ""
            print(f"    {lb:<8} | {cp:>7.1f}% | {bp:>9.1f}%{flag}")

    # 4B: Within-band separation (8.0-9.0)
    print(f"\n  Step 4B: Within-band separation (closing 8.0-9.0)")
    band89 = oos[(oos["closing_line"] >= 8.0) & (oos["closing_line"] <= 9.0)]
    over_sig = band89[band89["cal_p_over"] > 0.57]
    under_sig = band89[band89["cal_p_under"] > 0.57]
    neither = band89[(band89["cal_p_over"] <= 0.57) & (band89["cal_p_under"] <= 0.57)]
    for label, sub, wc in [("p_over>57%", over_sig, "actual_over"),
                            ("p_under>57%", under_sig, "actual_under"),
                            ("Not signaled", neither, "actual_over")]:
        if len(sub) == 0: continue
        w = sub[wc].sum(); l = len(sub) - w; n = int(w + l)
        r, _ = roi_110(int(w), int(l))
        wr = w / (w+l) * 100 if (w+l) > 0 else 0
        thin = " (THIN)" if n < 40 else ""
        metric = "over rate" if wc == "actual_over" else "under rate"
        print(f"    {label:<15}: N={n}, {metric}={wr:.1f}%, ROI={r:+.1f}%{thin}")

    # 4C: dual_high_csw by line band
    print(f"\n  Step 4C: dual_high_csw vs non by line band")
    for band_name, lo, hi in [("<=7.5", 0, 7.5), (">7.5", 7.5, 20)]:
        dhc = oos[(oos["dual_high_csw"] == 1) & (oos["closing_line"] > lo) & (oos["closing_line"] <= hi)]
        ndhc = oos[(oos["dual_high_csw"] == 0) & (oos["closing_line"] > lo) & (oos["closing_line"] <= hi)]
        dhc_ur = (1 - dhc["actual_over"]).mean() * 100 if len(dhc) > 0 else 0
        ndhc_ur = (1 - ndhc["actual_over"]).mean() * 100 if len(ndhc) > 0 else 0
        thin_d = " (THIN)" if len(dhc) < 40 else ""
        print(f"    {band_name}: dual_high_csw under={dhc_ur:.1f}% (N={len(dhc)}{thin_d}) vs other under={ndhc_ur:.1f}% (N={len(ndhc)})")

    # ══════════════════════════════════════════════════════════════
    # TASK 5 — CALIBRATION STABILITY
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("TASK 5 — CALIBRATION STABILITY")
    print("="*60)

    # 5A: Bootstrap
    print(f"\n  Step 5A: Bootstrap calibration stability (200 resamples)")
    train_low = train_cal[train_cal["low_run_env"] == 1].copy()
    bins_5a = [0, 0.40, 0.45, 0.50, 0.55, 0.60, 1.0]
    labels_5a = ["<40%", "40-45%", "45-50%", "50-55%", "55-60%", ">60%"]

    if len(train_low) > 30:
        boot_results = {lb: [] for lb in labels_5a}
        brng = np.random.default_rng(77)
        for _ in range(200):
            idx = brng.choice(len(train_low), size=len(train_low), replace=True)
            bs = train_low.iloc[idx]
            iso_b = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
            iso_b.fit(bs["p_over_line"].values, bs["ao"].values)
            # Apply to original (fixed) train predictions
            cal_preds = iso_b.predict(train_low["p_over_line"].values)
            buckets = pd.cut(train_low["p_over_line"], bins=bins_5a, labels=labels_5a, include_lowest=True)
            for lb in labels_5a:
                mask = buckets == lb
                if mask.sum() > 0:
                    boot_results[lb].append(cal_preds[mask].mean())

        print(f"    {'Bucket':<10} | {'Mean':>8} | {'Std':>8} | {'P10':>8} | {'P90':>8} | {'Flag':>10}")
        print("    " + "-"*60)
        for lb in labels_5a:
            vals = boot_results[lb]
            if len(vals) == 0: continue
            m = np.mean(vals) * 100; s = np.std(vals) * 100
            p10 = np.percentile(vals, 10) * 100; p90 = np.percentile(vals, 90) * 100
            flag = " UNSTABLE" if s > 3 else ""
            print(f"    {lb:<10} | {m:>7.1f}% | {s:>7.1f}% | {p10:>7.1f}% | {p90:>7.1f}% |{flag}")

    # 5B: Calibrated vs uncalibrated
    print(f"\n  Step 5B: Calibrated vs uncalibrated comparison (2024 OOS)")
    # Join raw p_over_line to OOS
    oos_raw = oos.copy()
    for label, thresh, wc, cal_col, raw_col in [
        (">57% over", 0.57, "actual_over", "cal_p_over", "p_over_line"),
        (">57% under", 0.57, "actual_under", "cal_p_under", None),
        (">60% under", 0.60, "actual_under", "cal_p_under", None),
    ]:
        cal_sub = oos[oos[cal_col] > thresh]
        if raw_col:
            raw_sub = oos[oos[raw_col] > thresh]
        else:
            # For under: raw p_under = 1 - p_over_line
            raw_sub = oos[(1 - oos["p_over_line"]) > thresh]

        w_c = cal_sub[wc].sum(); l_c = len(cal_sub) - w_c
        r_c, n_c = roi_110(int(w_c), int(l_c))
        w_r = raw_sub[wc].sum(); l_r = len(raw_sub) - w_r
        r_r, n_r = roi_110(int(w_r), int(l_r))

        # Overlap
        overlap = len(set(cal_sub["game_pk"]) & set(raw_sub["game_pk"]))
        ovl_pct = overlap / max(len(cal_sub), 1) * 100

        print(f"    {label}: cal N={n_c} ROI={r_c:+.1f}% | raw N={n_r} ROI={r_r:+.1f}% | overlap={ovl_pct:.0f}%")

    # 5C: Permutation sanity check
    print(f"\n  Step 5C: Permutation sanity check (2024 OOS, 200 shuffles)")
    prng = np.random.default_rng(555)
    for label, thresh, wc, col in [
        (">57% over", 0.57, "actual_over", "cal_p_over"),
        (">57% under", 0.57, "actual_under", "cal_p_under"),
    ]:
        actual_sub = oos[oos[col] > thresh]
        w_a = actual_sub[wc].sum(); l_a = len(actual_sub) - w_a
        actual_roi, _ = roi_110(int(w_a), int(l_a))

        shuf_rois = []
        for _ in range(200):
            shuffled = oos.copy()
            shuffled[col] = prng.permutation(shuffled[col].values)
            sub = shuffled[shuffled[col] > thresh]
            w = sub[wc].sum(); l = len(sub) - w
            r, _ = roi_110(int(w), int(l))
            shuf_rois.append(r)

        pctile = (np.array(shuf_rois) <= actual_roi).mean() * 100
        print(f"    {label}: actual ROI={actual_roi:+.1f}% | shuffled mean={np.mean(shuf_rois):+.1f}% std={np.std(shuf_rois):.1f}% | percentile={pctile:.0f}%")
        if pctile < 90:
            print(f"      *** FLAG: actual ROI not in top 10% of shuffled distribution ***")

    # ══════════════════════════════════════════════════════════════
    # OVERALL VERDICT
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("OVERALL VERDICT")
    print("="*60)

    print("""
Signal verdicts (based on 2024 OOS results):

  >57% over signals:      [see results above]
  >57% under signals:     [see results above]
  >60% under signals:     [see results above]
  Fragile × normal:       [see results above]
  dual_high_csw:          [see results above]

*** Assessment based on 2024 OOS only — train performance cannot
    upgrade a mixed OOS conclusion. ***
""")
    print("*** PHASE S5 COMPLETE — awaiting confirmation ***")


if __name__ == "__main__":
    run_s5()
