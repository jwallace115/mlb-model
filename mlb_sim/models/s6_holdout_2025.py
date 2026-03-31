#!/usr/bin/env python3
"""
MLB Simulation Engine — Phase S6: 2025 Frozen Engine Holdout
=============================================================
Runs frozen S1-S3 engine on 2025 data. No parameter changes.
Raw S3 probabilities only (no S4 calibration).
"""

import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path("/Users/jw115/mlb-model")
SIM_DATA = PROJECT_ROOT / "mlb_sim" / "data"
EVAL_DIR = PROJECT_ROOT / "mlb_sim" / "eval"
MODEL_DIR = PROJECT_ROOT / "mlb_sim" / "models"

N_SIMS = 20_000


def wilson_ci(wins, n, z=1.96):
    if n == 0: return 0, 0, 0
    p = wins / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2*n)) / d
    m = z * np.sqrt((p*(1-p) + z**2/(4*n)) / n) / d
    return p, max(0, c-m), min(1, c+m)


def roi_110(w, l):
    n = w + l
    if n == 0: return 0, 0, 0
    net = w * (100/110) - l
    return net / n * 100, n, net


def ip_to_outs(ip):
    if pd.isna(ip): return np.nan
    return int(ip) * 3 + round((ip - int(ip)) * 10)


def assign_path(outs):
    if pd.isna(outs): return np.nan
    if outs < 15: return 0
    elif outs <= 20: return 1
    else: return 2


def assign_regime(p0, p1):
    if p0 == 2 and p1 == 2: return 1
    if p0 == 0 and p1 == 0: return 4
    if p0 == 0 or p1 == 0: return 3
    return 2


def run_s6():
    # ══════════════════════════════════════════════════════════════
    # STEP 1-2: BUILD 2025 FEATURES + PATH PROBS
    # ══════════════════════════════════════════════════════════════
    print("Step 1: Building 2025 feature table...")
    from mlb_sim.data.build_sim_inputs import build_historical_sim_inputs

    # Build with 2025 included
    df_all = build_historical_sim_inputs(seasons=(2022, 2023, 2024, 2025))
    df_25 = df_all[df_all["season"] == 2025].copy()
    df_25.to_parquet(SIM_DATA / "sim_inputs_2025.parquet", index=False)
    print(f"  2025 feature table: {len(df_25)} starter-rows")

    print("\nStep 2: Generating path probabilities (frozen S2 model)...")
    with open(MODEL_DIR / "starter_path_model.pkl", "rb") as f:
        s2 = pickle.load(f)
    feats = s2["features"]
    clean = df_25.dropna(subset=feats).copy()
    Xs = s2["scaler"].transform(clean[feats].values)
    probs = s2["model"].predict_proba(Xs)
    clean["p_path0"] = probs[:, 0]
    clean["p_path1"] = probs[:, 1]
    clean["p_path2"] = probs[:, 2]
    clean["outs_recorded"] = clean["actual_ip"].apply(ip_to_outs)
    clean["actual_path"] = clean["outs_recorded"].apply(assign_path)
    clean.to_parquet(EVAL_DIR / "starter_path_2025.parquet", index=False)
    print(f"  Path probs computed: {len(clean)} starters")

    # ══════════════════════════════════════════════════════════════
    # STEP 3: SIMULATION (frozen S3 engine)
    # ══════════════════════════════════════════════════════════════
    print("\nStep 3: Running frozen simulation on 2025...")
    with open(MODEL_DIR / "run_dist_params.json") as f:
        rp = {int(k): v for k, v in json.load(f).items()}

    # Pivot to game level
    h = clean[clean["is_home"] == 1][["game_pk", "season", "sp_id", "sp_name",
        "p_path0", "p_path1", "p_path2", "sp_csw_pct", "sp_whiff_pct"]].copy()
    a = clean[clean["is_home"] == 0][["game_pk", "sp_id", "sp_name",
        "p_path0", "p_path1", "p_path2", "sp_csw_pct", "sp_whiff_pct"]].copy()
    h.columns = ["game_pk", "season", "hsp_id", "hsp_name", "hp0", "hp1", "hp2", "hcsw", "hwhiff"]
    a.columns = ["game_pk", "asp_id", "asp_name", "ap0", "ap1", "ap2", "acsw", "awhiff"]

    games = h.merge(a, on="game_pk", how="inner")

    # Join scores
    ft = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "feature_table.parquet")
    ft["game_pk"] = ft["game_pk"].astype(str)
    games["game_pk"] = games["game_pk"].astype(str)
    scores = ft[ft["season"] == 2025][["game_pk", "date", "home_team", "away_team",
        "home_score", "away_score", "actual_total"]].copy()
    games = games.merge(scores, on="game_pk", how="left")

    # M3 projections
    m3r = pd.read_csv(PROJECT_ROOT / "research" / "mlb_phase_a" / "m3_residuals_all_seasons.csv")
    m3r["game_id"] = m3r["game_id"].astype(str)
    games = games.merge(m3r[["game_id", "m3_projection"]].rename(columns={"game_id": "game_pk"}), on="game_pk", how="left")

    # Closing lines (eval only)
    hist_cl = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "mlb_historical_closing_lines.parquet")
    mkt = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "market_snapshots.parquet")
    hist_cl["game_pk"] = hist_cl["game_pk"].astype(str)
    id_col = "game_id" if "game_id" in mkt.columns else "game_pk"
    mkt[id_col] = mkt[id_col].astype(str)
    closing = pd.concat([
        hist_cl[["game_pk", "close_total"]].rename(columns={"close_total": "closing_line"}),
        mkt[[id_col, "close_total"]].rename(columns={id_col: "game_pk", "close_total": "closing_line"})
    ]).drop_duplicates("game_pk", keep="first")
    games = games.merge(closing, on="game_pk", how="left")

    # CSW flags (train-defined thresholds from S2)
    with open(MODEL_DIR / "calibration_params.json") as f:
        cp = json.load(f)
    games["dual_high_csw"] = ((games["hcsw"].fillna(0) >= cp["csw_q75"]) &
                               (games["acsw"].fillna(0) >= cp["csw_q75"])).astype(int)

    # Simulate
    valid = games.dropna(subset=["hp0", "ap0", "actual_total", "closing_line"]).copy()
    print(f"  2025 games for simulation: {len(valid)}")

    rng = np.random.default_rng(2025)
    results = []
    for _, g in valid.iterrows():
        hp = np.array([g["hp0"], g["hp1"], g["hp2"]]); hp /= hp.sum()
        ap = np.array([g["ap0"], g["ap1"], g["ap2"]]); ap /= ap.sum()
        mu_h = max((g.get("m3_projection") or 8.5) * 0.505, 1.0)
        mu_a = max((g.get("m3_projection") or 8.5) * 0.495, 1.0)

        hps = rng.choice([0,1,2], N_SIMS, p=hp)
        aps = rng.choice([0,1,2], N_SIMS, p=ap)
        tots = np.zeros(N_SIMS); regs = np.zeros(N_SIMS, dtype=int)
        for i in range(N_SIMS):
            reg = assign_regime(hps[i], aps[i]); regs[i] = reg
            r = rp[reg]["r"]
            tots[i] = rng.negative_binomial(r, r/(r+mu_h)) + rng.negative_binomial(r, r/(r+mu_a))

        cl = g["closing_line"]
        results.append({
            "game_pk": g["game_pk"], "date": g.get("date"), "season": 2025,
            "home_team": g.get("home_team"), "away_team": g.get("away_team"),
            "actual_total": g["actual_total"], "closing_line": cl,
            "m3_projection": g.get("m3_projection"),
            "p_over_line": (tots > cl).mean(),
            "p_under_line": (tots <= cl).mean(),
            "sim_mean_total": tots.mean(), "sim_std_total": tots.std(),
            "dominant_regime": int(pd.Series(regs).mode()[0]),
            "hp0": g["hp0"], "ap0": g["ap0"],
            "dual_high_csw": g["dual_high_csw"],
            "hcsw": g.get("hcsw"), "acsw": g.get("acsw"),
        })

    sim25 = pd.DataFrame(results)
    sim25["actual_over"] = (sim25["actual_total"] > sim25["closing_line"]).astype(int)
    sim25["actual_under"] = 1 - sim25["actual_over"]
    sim25["fragile_normal"] = ((sim25["dominant_regime"] == 3) &
                                (sim25["sim_mean_total"] > cp["low_run_env_threshold"])).astype(int)

    sim25.to_parquet(EVAL_DIR / "sim_results_2025.parquet", index=False)
    print(f"  Saved: {len(sim25)} games\n")

    # ══════════════════════════════════════════════════════════════
    # STEP 4-5: USE RAW PROBS, DEFINE TEMPORAL SPLIT
    # ══════════════════════════════════════════════════════════════
    sim25 = sim25.sort_values("date").reset_index(drop=True)
    mid = (len(sim25) + 1) // 2
    h1 = sim25.iloc[:mid].copy(); h2 = sim25.iloc[mid:].copy()
    print(f"Step 5: Temporal split")
    print(f"  Half 1: {h1['date'].min()} to {h1['date'].max()}, N={len(h1)}")
    print(f"  Half 2: {h2['date'].min()} to {h2['date'].max()}, N={len(h2)}")

    # Also load 2024 OOS for comparison
    sim24 = pd.read_parquet(EVAL_DIR / "sim_results_oos_2024.parquet")
    sim24["actual_over"] = (sim24["actual_total"] > sim24["closing_line"]).astype(int)
    sim24["actual_under"] = 1 - sim24["actual_over"]
    # Need raw p_under for 2024
    if "p_under_line" not in sim24.columns:
        sim24["p_under_line"] = 1 - sim24["p_over_line"]
    # Fragile normal
    sim24["fragile_normal"] = ((sim24["dominant_regime"] == 3) &
                                (sim24["sim_mean_total"] > cp["low_run_env_threshold"])).astype(int)
    # dual_high_csw for 2024
    if "dual_high_csw" not in sim24.columns:
        # Rebuild from S1 inputs
        si = pd.read_parquet(SIM_DATA / "sim_inputs_historical_2022_2024.parquet")
        si24h = si[(si["season"]==2024) & (si["is_home"]==1)][["game_pk","sp_csw_pct"]].rename(columns={"sp_csw_pct":"hcsw24"})
        si24a = si[(si["season"]==2024) & (si["is_home"]==0)][["game_pk","sp_csw_pct"]].rename(columns={"sp_csw_pct":"acsw24"})
        si24h["game_pk"] = si24h["game_pk"].astype(str); si24a["game_pk"] = si24a["game_pk"].astype(str)
        sim24["game_pk"] = sim24["game_pk"].astype(str)
        sim24 = sim24.merge(si24h, on="game_pk", how="left").merge(si24a, on="game_pk", how="left")
        sim24["dual_high_csw"] = ((sim24["hcsw24"].fillna(0) >= cp["csw_q75"]) &
                                   (sim24["acsw24"].fillna(0) >= cp["csw_q75"])).astype(int)

    # ══════════════════════════════════════════════════════════════
    # TESTS
    # ══════════════════════════════════════════════════════════════

    def cohort_stats(df, win_col, label=""):
        w = int(df[win_col].sum()); l = len(df) - w
        r, n, net = roi_110(w, l)
        wr = w / n * 100 if n > 0 else 0
        thin = " (THIN)" if n < 40 else ""
        return {"label": label, "n": n, "win_rate": wr, "roi": r, "net_units": net, "thin": thin}

    # ── TEST A ──
    print(f"\n{'='*60}")
    print("TEST A — Core signal ROI (2025)")
    print("="*60)
    cohorts_def = [
        ("p_over>0.57", sim25[sim25["p_over_line"] > 0.57], "actual_over"),
        ("p_under>0.57", sim25[sim25["p_under_line"] > 0.57], "actual_under"),
        ("p_under>0.60", sim25[sim25["p_under_line"] > 0.60], "actual_under"),
        ("dual_high_csw", sim25[sim25["dual_high_csw"] == 1], "actual_under"),
    ]
    print(f"{'Cohort':<18} | {'N':>5} | {'Net units':>10} | {'Win%':>6} | {'ROI':>8}")
    print("-"*55)
    for name, sub, wc in cohorts_def:
        s = cohort_stats(sub, wc, name)
        print(f"{name:<18} | {s['n']:>5} | {s['net_units']:>+9.2f}u | {s['win_rate']:>5.1f}% | {s['roi']:>+7.1f}%{s['thin']}")

    # ── TEST B ──
    print(f"\n{'='*60}")
    print("TEST B — Threshold sensitivity (2025)")
    print("="*60)
    thresholds = [0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.60]

    print(f"\nOVER side:")
    print(f"{'Thresh':>6} | {'N':>5} | {'Win%':>6} | {'CI low':>7} | {'CI hi':>7} | {'ROI':>8}")
    print("-"*50)
    for t in thresholds:
        sub = sim25[sim25["p_over_line"] > t]
        w = int(sub["actual_over"].sum()); l = len(sub) - w; n = w + l
        wr, ci_lo, ci_hi = wilson_ci(w, n)
        r, _, _ = roi_110(w, l)
        thin = " (THIN)" if n < 40 else ""
        print(f" >{t:.0%} | {n:>5} | {wr*100:>5.1f}% | {ci_lo*100:>6.1f}% | {ci_hi*100:>6.1f}% | {r:>+7.1f}%{thin}")

    print(f"\nUNDER side:")
    print(f"{'Thresh':>6} | {'N':>5} | {'Win%':>6} | {'CI low':>7} | {'CI hi':>7} | {'ROI':>8}")
    print("-"*50)
    for t in thresholds:
        sub = sim25[sim25["p_under_line"] > t]
        w = int(sub["actual_under"].sum()); l = len(sub) - w; n = w + l
        wr, ci_lo, ci_hi = wilson_ci(w, n)
        r, _, _ = roi_110(w, l)
        thin = " (THIN)" if n < 40 else ""
        print(f" >{t:.0%} | {n:>5} | {wr*100:>5.1f}% | {ci_lo*100:>6.1f}% | {ci_hi*100:>6.1f}% | {r:>+7.1f}%{thin}")

    # ── TEST C ──
    print(f"\n{'='*60}")
    print("TEST C — Temporal split (2025)")
    print("="*60)
    print(f"  Half 1: {h1['date'].min()} to {h1['date'].max()}, N={len(h1)}")
    print(f"  Half 2: {h2['date'].min()} to {h2['date'].max()}, N={len(h2)}")

    cohorts_c = [
        ("p_over>0.57", "actual_over", lambda d: d[d["p_over_line"] > 0.57]),
        ("p_under>0.57", "actual_under", lambda d: d[d["p_under_line"] > 0.57]),
        ("p_under>0.60", "actual_under", lambda d: d[d["p_under_line"] > 0.60]),
        ("dual_high_csw", "actual_under", lambda d: d[d["dual_high_csw"] == 1]),
    ]
    print(f"\n{'Cohort':<18} | {'Half':>4} | {'N':>5} | {'Win%':>6} | {'ROI':>8} | {'Net':>8}")
    print("-"*58)
    for name, wc, func in cohorts_c:
        nets = {}
        for hname, hdf in [("H1", h1), ("H2", h2)]:
            sub = func(hdf)
            s = cohort_stats(sub, wc)
            nets[hname] = s["net_units"]
            print(f"{name:<18} | {hname:>4} | {s['n']:>5} | {s['win_rate']:>5.1f}% | {s['roi']:>+7.1f}% | {s['net_units']:>+7.2f}u{s['thin']}")
        total = nets["H1"] + nets["H2"]
        if total != 0:
            h1_share = abs(nets["H1"] / total) * 100
            if h1_share > 70:
                print(f"  *** {name} — H1 contributes {h1_share:.0f}% (HALF CONCENTRATED)")
            elif (100 - h1_share) > 70:
                print(f"  *** {name} — H2 contributes {100-h1_share:.0f}% (HALF CONCENTRATED)")

    # ── TEST D ──
    print(f"\n{'='*60}")
    print("TEST D — Within-band separation (8.0-9.0)")
    print("="*60)
    band = sim25[(sim25["closing_line"] >= 8.0) & (sim25["closing_line"] <= 9.0)]
    for label, sub, wc in [
        ("p_over>0.57", band[band["p_over_line"] > 0.57], "actual_over"),
        ("p_under>0.57", band[band["p_under_line"] > 0.57], "actual_under"),
        ("Not sig (over base)", band[(band["p_over_line"] <= 0.57) & (band["p_under_line"] <= 0.57)], "actual_over"),
        ("Not sig (under base)", band[(band["p_over_line"] <= 0.57) & (band["p_under_line"] <= 0.57)], "actual_under"),
    ]:
        s = cohort_stats(sub, wc, label)
        metric = "over rate" if "over" in wc else "under rate"
        print(f"  {label:<22}: N={s['n']}, {metric}={s['win_rate']:.1f}%, ROI={s['roi']:+.1f}%{s['thin']}")

    # ── TEST E ──
    print(f"\n{'='*60}")
    print("TEST E — dual_high_csw by line band")
    print("="*60)
    for band_name, lo, hi in [("<=7.5", 0, 7.5), (">7.5", 7.5, 20)]:
        dhc = sim25[(sim25["dual_high_csw"] == 1) & (sim25["closing_line"] > lo) & (sim25["closing_line"] <= hi)]
        oth = sim25[(sim25["dual_high_csw"] == 0) & (sim25["closing_line"] > lo) & (sim25["closing_line"] <= hi)]
        dhc_ur = dhc["actual_under"].mean() * 100 if len(dhc) > 0 else 0
        oth_ur = oth["actual_under"].mean() * 100 if len(oth) > 0 else 0
        gap = dhc_ur - oth_ur
        thin_d = " (THIN)" if len(dhc) < 40 else ""
        print(f"  {band_name}: dual_high={dhc_ur:.1f}% (N={len(dhc)}{thin_d}) vs other={oth_ur:.1f}% (N={len(oth)}) gap={gap:+.1f}pp")

    # ── TEST F ──
    print(f"\n{'='*60}")
    print("TEST F — Permutation sanity check (2025)")
    print("="*60)
    prng = np.random.default_rng(777)
    for label, thresh, wc, col in [
        (">57% over", 0.57, "actual_over", "p_over_line"),
        (">57% under", 0.57, "actual_under", "p_under_line"),
    ]:
        actual_sub = sim25[sim25[col] > thresh]
        w = int(actual_sub[wc].sum()); l = len(actual_sub) - w
        actual_roi, _, _ = roi_110(w, l)
        shuf_rois = []
        for _ in range(200):
            sh = sim25.copy()
            sh[col] = prng.permutation(sh[col].values)
            sub = sh[sh[col] > thresh]
            sw = int(sub[wc].sum()); sl = len(sub) - sw
            sr, _, _ = roi_110(sw, sl)
            shuf_rois.append(sr)
        pctile = (np.array(shuf_rois) <= actual_roi).mean() * 100
        print(f"  {label}: actual={actual_roi:+.1f}% | shuf mean={np.mean(shuf_rois):+.1f}% std={np.std(shuf_rois):.1f}% | pctile={pctile:.0f}%")
        if pctile < 90:
            print(f"    *** FLAG: not in top 10% of shuffled distribution ***")

    # ── TEST G ──
    print(f"\n{'='*60}")
    print("TEST G — H1 concentration follow-up")
    print("="*60)
    for name, wc, func in [
        ("p_under>0.57", "actual_under", lambda d: d[d["p_under_line"] > 0.57]),
        ("p_under>0.60", "actual_under", lambda d: d[d["p_under_line"] > 0.60]),
        ("dual_high_csw", "actual_under", lambda d: d[d["dual_high_csw"] == 1]),
    ]:
        s1 = func(h1); s2_h = func(h2)
        w1 = int(s1[wc].sum()); l1 = len(s1) - w1; net1 = w1*(100/110) - l1
        w2 = int(s2_h[wc].sum()); l2 = len(s2_h) - w2; net2 = w2*(100/110) - l2
        total = net1 + net2
        h1_share = abs(net1 / total) * 100 if total != 0 else 50
        if total > 0 and h1_share > 70:
            cls = "REPEATS"
        elif total > 0 and (100 - h1_share) > 70:
            cls = "REVERSES"
        else:
            cls = "DISAPPEARS"
        print(f"  {name:<18}: H1={net1:+.2f}u H2={net2:+.2f}u | H1 share={h1_share:.0f}% | {cls}")

    # ── 2024 vs 2025 COMPARISON ──
    print(f"\n{'='*60}")
    print("2024 vs 2025 SIDE-BY-SIDE COMPARISON")
    print("="*60)
    comparisons = [
        ("p_over>0.57", "actual_over",
         lambda d: d[d["p_over_line"] > 0.57]),
        ("p_under>0.57", "actual_under",
         lambda d: d[d.get("p_under_line", 1 - d.get("p_over_line", 0.5)) > 0.57]),
        ("p_under>0.60", "actual_under",
         lambda d: d[d.get("p_under_line", 1 - d.get("p_over_line", 0.5)) > 0.60]),
        ("dual_high_csw", "actual_under",
         lambda d: d[d["dual_high_csw"] == 1]),
    ]
    print(f"\n{'Cohort':<18} | {'Yr':>4} | {'N':>5} | {'Win%':>6} | {'ROI':>8} | {'Net':>8}")
    print("-"*58)
    for name, wc, func in comparisons:
        for yr, df_yr in [(2024, sim24), (2025, sim25)]:
            # For 2024, p_under_line may need computing
            if "p_under_line" not in df_yr.columns:
                df_yr = df_yr.copy()
                df_yr["p_under_line"] = 1 - df_yr["p_over_line"]
            sub = func(df_yr)
            s = cohort_stats(sub, wc)
            print(f"{name:<18} | {yr:>4} | {s['n']:>5} | {s['win_rate']:>5.1f}% | {s['roi']:>+7.1f}% | {s['net_units']:>+7.2f}u{s['thin']}")

    # ── POOLED ──
    print(f"\n{'='*60}")
    print("POOLED 2024+2025 OOS SUMMARY")
    print("="*60)
    for name, wc, func in comparisons:
        combined = pd.concat([sim24, sim25], ignore_index=True)
        if "p_under_line" not in combined.columns:
            combined["p_under_line"] = 1 - combined["p_over_line"]
        sub = func(combined)
        s = cohort_stats(sub, wc)
        print(f"  {name:<18}: N={s['n']:>5}, Win%={s['win_rate']:.1f}%, ROI={s['roi']:+.1f}%, Net={s['net_units']:+.2f}u{s['thin']}")

    # ── VERDICT ──
    print(f"\n{'='*60}")
    print("OVERALL VERDICT")
    print("="*60)
    print("""
*** Assessment based on combined 2024 and 2025 OOS results. ***
*** Strong performance in one season cannot offset degradation in the other. ***
*** See tables above for detailed results. ***
""")
    print("*** PHASE S6 COMPLETE — awaiting confirmation ***")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    run_s6()
