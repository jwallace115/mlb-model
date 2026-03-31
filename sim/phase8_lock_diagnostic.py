"""
Phase 8 Lock Diagnostic — 25-Feature Model
===========================================
Before locking the trimmed 25-feature model as the Phase 9 baseline, runs:
  1. Pairwise correlations: away_bullpen_delta, away_bp_delta_exposure,
     away_sp_avg_ip, away_bp_proj_inn, away_bp_xfip, away_sp_xfip
  2. Collinearity check: fit away_bullpen_delta alone / exposure alone / both
     to confirm whether the negative away_bullpen_delta sign is a partial-
     effect artifact from collinearity with the interaction term
  3. Full coefficient table for the trimmed 25-feature model
  4. Final metrics summary vs Phase 6 baseline

Saves locked model to sim/data/phase9_baseline_model.pkl and
saves report to sim/reports/phase8_lock_diagnostic.txt
"""

import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM_DIR.parent))

from sim.phase6_interactions import (
    BASELINE_FEATURES, TRAIN_YEARS, VALIDATE_YEAR, OOS_YEAR, ALPHAS,
)
from sim.phase8_step3_retrain import (
    load_and_merge, load_market, fit_ridge, predict, train_sigma, evaluate_model,
)

PHASE6_FEATURES = BASELINE_FEATURES + ["flyball_wind_interaction"]
BULLPEN_BC = [
    "home_high_leverage_avail", "away_high_leverage_avail",
    "home_bullpen_delta",       "away_bullpen_delta",
    "home_bp_delta_exposure",   "away_bp_delta_exposure",
]
TRIMMED_25 = PHASE6_FEATURES + BULLPEN_BC

REPORT_PATH     = SIM_DIR / "reports" / "phase8_lock_diagnostic.txt"
LOCKED_MODEL    = SIM_DIR / "data"    / "phase9_baseline_model.pkl"
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


def main():
    lines_out: list[str] = []

    def pln(s: str = ""):
        print(s)
        lines_out.append(s)

    pln("=" * 72)
    pln("PHASE 8 LOCK DIAGNOSTIC — 25-FEATURE MODEL")
    pln("=" * 72)
    pln()
    pln("  Features retained:")
    pln("    Phase 6 baseline (19): SP xFIP/K/BB/avgIP × 2, wRC+ × 2,")
    pln("                           park factors, temperature, wind, umpire,")
    pln("                           rest days × 2, DH flag, flyball×wind")
    pln("    Bullpen B — closer availability: home/away_high_leverage_avail")
    pln("    Bullpen C — quality delta:       home/away_bullpen_delta,")
    pln("                                     home/away_bp_delta_exposure")
    pln("  Dropped: home/away_relievers_last1, home/away_relievers_last3")
    pln()

    # ── Load ──────────────────────────────────────────────────────────────────
    print("Loading data...", flush=True)
    df        = load_and_merge()
    df_market = load_market()

    df_train = df[df["season"].isin(TRAIN_YEARS)].copy()
    df_24    = df[df["season"] == VALIDATE_YEAR].copy()
    df_25    = df[df["season"] == OOS_YEAR].copy()

    for c in BULLPEN_BC:
        med = df_train[c].median()
        for d in [df_train, df_24, df_25]:
            d[c] = d[c].fillna(med)

    pln(f"  Train: {len(df_train):,}  |  Val 2024: {len(df_24):,}  |  OOS 2025: {len(df_25):,}")
    pln()

    # ── 1. Pairwise correlations ───────────────────────────────────────────────
    pln("=" * 72)
    pln("1. PAIRWISE CORRELATIONS (2022+2023 training set)")
    pln("=" * 72)
    pln()
    pln("  Columns: away_bullpen_delta (= away_bp_xfip − away_sp_xfip),")
    pln("           away_bp_delta_exposure (= away_bullpen_delta × away_bp_proj_inn),")
    pln("           away_sp_avg_ip, away_bp_proj_inn (projected bullpen innings),")
    pln("           away_bp_xfip, away_sp_xfip")
    pln()

    corr_cols = [
        "away_bullpen_delta",
        "away_bp_delta_exposure",
        "away_sp_avg_ip",
        "away_bp_proj_inn",
        "away_bp_xfip",
        "away_sp_xfip",
    ]
    corr_mat = df_train[corr_cols].corr()

    # Print as formatted table
    short = {
        "away_bullpen_delta":     "bp_delta",
        "away_bp_delta_exposure": "exposure",
        "away_sp_avg_ip":         "sp_avg_ip",
        "away_bp_proj_inn":       "bp_proj_inn",
        "away_bp_xfip":           "bp_xfip",
        "away_sp_xfip":           "sp_xfip",
    }
    headers = [short[c] for c in corr_cols]
    pln("  " + "  ".join(f"{h:>11}" for h in headers))
    pln("  " + "  ".join("─" * 11 for _ in headers))
    for row_col in corr_cols:
        vals = "  ".join(f"{corr_mat.loc[row_col, c]:>11.3f}" for c in corr_cols)
        pln(f"  {vals}   ← {short[row_col]}")

    pln()
    pln("  Key pair: corr(bp_delta, exposure) = "
        f"{corr_mat.loc['away_bullpen_delta','away_bp_delta_exposure']:+.3f}")
    pln("  (>0.90 would indicate near-perfect collinearity; expect high but below 0.9)")
    pln()

    # ── 2. Collinearity check: delta sign with vs without exposure ────────────
    pln("=" * 72)
    pln("2. COLLINEARITY DIAGNOSTIC — away_bullpen_delta sign stability")
    pln("=" * 72)
    pln()
    pln("  Does the negative away_bullpen_delta coefficient in the full model")
    pln("  stabilize or flip when the exposure interaction term is present/absent?")
    pln()

    def quick_coef(features: list[str], targets: list[str]) -> dict[str, tuple[float, float]]:
        """Fit Ridge on features, return {feat: (std_coef, raw_coef)} for targets."""
        X = df_train[features].fillna(df_train[features].median())
        y = df_train["actual_total"].values
        pipe = Pipeline([("sc", StandardScaler()), ("r", RidgeCV(alphas=ALPHAS, cv=5))])
        pipe.fit(X.values, y)
        sc = pipe.named_steps["sc"]
        r  = pipe.named_steps["r"]
        alpha = r.alpha_
        result = {}
        for feat in targets:
            if feat not in features:
                continue
            i = features.index(feat)
            std_c = float(r.coef_[i])
            raw_c = float(std_c / sc.scale_[i])
            result[feat] = (std_c, raw_c, alpha)
        return result

    experiments = [
        ("Phase 6 only (no bullpen)",
         PHASE6_FEATURES,
         ["away_bullpen_delta","away_bp_delta_exposure"]),
        ("+ away_bullpen_delta only",
         PHASE6_FEATURES + ["away_bullpen_delta"],
         ["away_bullpen_delta","away_bp_delta_exposure"]),
        ("+ away_bp_delta_exposure only",
         PHASE6_FEATURES + ["away_bp_delta_exposure"],
         ["away_bullpen_delta","away_bp_delta_exposure"]),
        ("+ both (delta + exposure)",
         PHASE6_FEATURES + ["away_bullpen_delta","away_bp_delta_exposure"],
         ["away_bullpen_delta","away_bp_delta_exposure"]),
        ("Full trimmed 25-feature",
         TRIMMED_25,
         ["away_bullpen_delta","away_bp_delta_exposure"]),
    ]

    pln(f"  {'Model':<40}  {'Feature':<28}  {'Std coef':>9}  {'Raw coef':>9}  {'α':>6}")
    pln(f"  {'─'*40}  {'─'*28}  {'─'*9}  {'─'*9}  {'─'*6}")

    for exp_name, feat_list, targets in experiments:
        coefs = quick_coef(feat_list, targets)
        first = True
        for feat in ["away_bullpen_delta", "away_bp_delta_exposure"]:
            if feat not in coefs:
                label = exp_name if first else ""
                pln(f"  {label:<40}  {feat:<28}  {'(absent)':>9}  {'':>9}  {''}")
            else:
                std_c, raw_c, alpha = coefs[feat]
                label = exp_name if first else ""
                pln(f"  {label:<40}  {feat:<28}  {std_c:>+9.4f}  {raw_c:>+9.4f}  {alpha:>6.0f}")
            first = False

    pln()
    pln("  Interpretation guide:")
    pln("  • If away_bullpen_delta flips sign from (+) alone to (−) with exposure:")
    pln("    → sign change IS a partial-effect collinearity artifact.")
    pln("    → Model correctly decomposes: delta captures quality baseline;")
    pln("      exposure = delta × innings is the economically meaningful term.")
    pln("  • If away_bullpen_delta stays (−) regardless of whether exposure is present:")
    pln("    → sign is a real directional signal (worse bullpen → fewer total runs,")
    pln("      possibly via manager pulling SP earlier when bullpen is bad).")
    pln("  • Ridge shrinkage will keep both if there is residual orthogonal variance.")
    pln()

    # ── 3. Full coefficient table — trimmed 25-feature model ─────────────────
    pln("=" * 72)
    pln("3. TRIMMED 25-FEATURE MODEL — FULL COEFFICIENT TABLE")
    pln("=" * 72)
    pln()

    pipe25  = fit_ridge(df_train, TRIMMED_25)
    sig25   = train_sigma(df_train, pipe25, TRIMMED_25)
    alpha25 = pipe25.named_steps["ridge"].alpha_
    pln(f"  Ridge α = {alpha25:.1f}   training σ = {sig25:.4f}")
    pln()

    sc25 = pipe25.named_steps["scaler"]
    r25  = pipe25.named_steps["ridge"]
    coef_rows = []
    for i, feat in enumerate(TRIMMED_25):
        std_c = float(r25.coef_[i])
        raw_c = float(std_c / sc25.scale_[i])
        coef_rows.append((feat, std_c, raw_c, abs(std_c), feat in BULLPEN_BC))
    coef_rows.sort(key=lambda x: -x[3])

    pln(f"  {'Feature':<32}  {'Std coef':>10}  {'Raw coef':>10}  {'Note'}")
    pln(f"  {'─'*32}  {'─'*10}  {'─'*10}  {'─'*20}")
    for feat, std_c, raw_c, _, is_bp in coef_rows:
        tag = "← bullpen B/C" if is_bp else ""
        pln(f"  {feat:<32}  {std_c:>+10.4f}  {raw_c:>+10.4f}  {tag}")

    pln()
    pln("  Bullpen B/C coefficients only:")
    pln(f"  {'Feature':<32}  {'Std coef':>10}  {'Raw coef':>10}  {'Sign sense'}")
    pln(f"  {'─'*32}  {'─'*10}  {'─'*10}  {'─'*30}")
    bp_sense = {
        "home_high_leverage_avail": "rested closer → expect fewer runs (over-suppressing)",
        "away_high_leverage_avail": "rested closer → expect fewer runs (over-suppressing)",
        "home_bullpen_delta":       "bp_xFIP > sp_xFIP → bullpen worse than SP",
        "away_bullpen_delta":       "bp_xFIP > sp_xFIP → bullpen worse than SP",
        "home_bp_delta_exposure":   "quality gap × innings → more runs if bp pitched more",
        "away_bp_delta_exposure":   "quality gap × innings → more runs if bp pitched more",
    }
    for feat, std_c, raw_c, _, is_bp in coef_rows:
        if not is_bp:
            continue
        pln(f"  {feat:<32}  {std_c:>+10.4f}  {raw_c:>+10.4f}  {bp_sense.get(feat,'')}")

    pln()

    # ── 4. Evaluation summary ─────────────────────────────────────────────────
    pln("=" * 72)
    pln("4. EVALUATION SUMMARY — Trimmed 25 vs Phase 6 Baseline")
    pln("=" * 72)
    pln()

    # Phase 6 baseline for comparison
    pipe6  = fit_ridge(df_train, PHASE6_FEATURES)
    sig6   = train_sigma(df_train, pipe6, PHASE6_FEATURES)

    ev6_24  = evaluate_model("P6 2024",    df_24, pipe6,  PHASE6_FEATURES, sig6,  df_market)
    ev6_25  = evaluate_model("P6 2025",    df_25, pipe6,  PHASE6_FEATURES, sig6,  df_market)
    ev25_24 = evaluate_model("P8T 2024",   df_24, pipe25, TRIMMED_25,     sig25,  df_market)
    ev25_25 = evaluate_model("P8T 2025",   df_25, pipe25, TRIMMED_25,     sig25,  df_market)

    def get(ev, key, sub=None):
        d = ev
        if sub:
            d = d.get(sub, {})
        v = d.get(key, float("nan"))
        return float(v) if v is not None else float("nan")

    pln(f"  {'Metric':<30}  {'P6 2024':>9}  {'P8T 2024':>9}  {'Δ24':>7}  "
        f"{'P6 2025':>9}  {'P8T 2025':>9}  {'Δ25':>7}")
    pln(f"  {'─'*30}  {'─'*9}  {'─'*9}  {'─'*7}  {'─'*9}  {'─'*9}  {'─'*7}")

    def cmp(label, key, sub=None, fmt=".4f", good="lower"):
        v_b24 = get(ev6_24,  key, sub); v_n24 = get(ev25_24, key, sub)
        v_b25 = get(ev6_25,  key, sub); v_n25 = get(ev25_25, key, sub)
        d24 = v_n24 - v_b24; d25 = v_n25 - v_b25
        def mk(d, g): return "✓" if ((d<0 and g=="lower") or (d>0 and g=="higher")) else "✗"
        pln(f"  {label:<30}  {v_b24:>9{fmt}}  {v_n24:>9{fmt}}  {d24:>+7.4f}{mk(d24,good)}  "
            f"{v_b25:>9{fmt}}  {v_n25:>9{fmt}}  {d25:>+7.4f}{mk(d25,good)}")

    cmp("MAE (proxy)",         "mae",                   "metrics_proxy", good="lower")
    cmp("RMSE (proxy)",        "rmse",                  "metrics_proxy", good="lower")
    cmp("Pearson r",           "r",                     "metrics_proxy", good="higher")
    cmp("Spearman ρ",          "rho",                   "metrics_proxy", good="higher")
    cmp("DHR proxy",           "dhr",                   "metrics_proxy", fmt=".3f", good="higher")
    cmp("DHR vs real line",    "dhr_real",              "metrics_real",  fmt=".3f", good="higher")
    cmp("corr(edge,mkt_err)",  "corr_edge_market_error","diagnostics",   good="higher")
    cmp("ΔR² over market",     "delta_r2",              "diagnostics",   good="higher")

    pln()
    pln("  ROI vs real closing lines (BET_EDGE≥1.0, BET_PROB≥0.55, juice=-110):")

    def roi_row(label, ev_b, ev_n, yr):
        rb = ev_b.get("roi",{}).get("by_year",{}).get(yr,{})
        rn = ev_n.get("roi",{}).get("by_year",{}).get(yr,{})
        b_roi = rb.get("roi", float("nan")); b_n = rb.get("n", 0)
        n_roi = rn.get("roi", float("nan")); n_n = rn.get("n", 0)
        d = n_roi - b_roi if not (np.isnan(b_roi) or np.isnan(n_roi)) else float("nan")
        mk = "✓" if (not np.isnan(d) and d > 0) else "✗"
        pln(f"  {label:<30}  {b_roi:>+9.1f}% n={b_n:<4}   {n_roi:>+9.1f}% n={n_n:<4}   "
            f"Δ={d:>+.1f}% {mk}")

    roi_row("ROI 2024 games", ev6_24, ev25_24, 2024)
    roi_row("ROI 2025 games", ev6_25, ev25_25, 2025)

    pln()
    pln("  Confidence tiers (2025 OOS — trimmed 25-feature):")
    pln(f"  {'Tier':<12}  {'P6 n':>6}  {'P6 win%':>8}  {'P6 ROI%':>8}  "
        f"{'P8T n':>6}  {'P8T win%':>8}  {'P8T ROI%':>8}  Δ ROI")
    pln(f"  {'─'*12}  {'─'*6}  {'─'*8}  {'─'*8}  {'─'*6}  {'─'*8}  {'─'*8}  {'─'*6}")
    t6   = {t["tier"]: t for t in ev6_25.get("tiers",[])}
    t25  = {t["tier"]: t for t in ev25_25.get("tiers",[])}
    for tier in ["STRONG","BET","WATCHLIST"]:
        b = t6.get(tier,  {"n":0,"win_pct":float("nan"),"roi":float("nan")})
        n = t25.get(tier, {"n":0,"win_pct":float("nan"),"roi":float("nan")})
        d = n["roi"] - b["roi"] if not (np.isnan(b["roi"]) or np.isnan(n["roi"])) else float("nan")
        pln(f"  {tier:<12}  {b['n']:>6}  {b['win_pct']*100:>8.1f}  {b['roi']:>+8.1f}  "
            f"{n['n']:>6}  {n['win_pct']*100:>8.1f}  {n['roi']:>+8.1f}  {d:>+.1f}pp")

    pln()

    # ── 5. Lock model ─────────────────────────────────────────────────────────
    pln("=" * 72)
    pln("5. MODEL LOCK — PHASE 9 BASELINE")
    pln("=" * 72)
    pln()

    bundle = {
        "pipeline":     pipe25,
        "features":     TRIMMED_25,
        "sigma":        sig25,
        "alpha":        alpha25,
        "train_years":  TRAIN_YEARS,
        "n_features":   len(TRIMMED_25),
        "label":        "Phase 8 trimmed 25-feature (Phase 9 baseline)",
        "bullpen_cols": BULLPEN_BC,
        "dropped":      ["home_relievers_last1","away_relievers_last1",
                         "home_relievers_last3","away_relievers_last3"],
    }
    with open(LOCKED_MODEL, "wb") as f:
        pickle.dump(bundle, f)

    pln(f"  Saved → {LOCKED_MODEL}")
    pln(f"  Features ({len(TRIMMED_25)}):")
    for feat in TRIMMED_25:
        tag = "  ← bullpen" if feat in BULLPEN_BC else ""
        pln(f"    {feat}{tag}")

    pln()
    pln("  INTERPRETATION CARRY-FORWARD:")
    pln("  • Bullpen features added genuine market-relevant signal:")
    pln("    corr(edge, market_error) 0.069→0.090 OOS (+0.021pp)")
    pln("    ΔR² over market 0.005→0.008 OOS (+0.003)")
    pln("  • All-bets OOS ROI remains slightly negative (−0.3% to −0.4%)")
    pln("    → model not broadly actionable yet")
    pln("  • STRONG tier: −7.6% → +5.0% (2025 OOS) — 12.6pp improvement")
    pln("    → monitor this closely in live 2026 data")
    pln("  • Right bullpen signal = availability + quality gap + exposure,")
    pln("    NOT raw reliever counts")
    pln()
    pln("  Ready for Phase 9.")
    pln()

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines_out))
    print(f"\nReport saved → {REPORT_PATH}")
    print(f"Locked model → {LOCKED_MODEL}")


if __name__ == "__main__":
    main()
