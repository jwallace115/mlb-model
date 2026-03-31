#!/usr/bin/env python3
"""
Team Totals Suppressed Offense Research
========================================
Tests whether betting the suppressed team's team total under
outperforms betting the full-game under among V1 signal games.

Dataset: 2024-2025 only (2023 excluded — thin coverage)
Team total lines: REAL MARKET PRICES (SNAPSHOT, T-1h)
S3 per-team projections: APPROXIMATE (mu = m3_proj × 0.505/0.495)
All results reported three ways: all / books>=2 / thin-only
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings("ignore")

PROJECT = Path("/Users/jw115/mlb-model")
sys.path.insert(0, str(PROJECT))

OUT_DIR = PROJECT / "research" / "team_totals"
DATA_DIR = OUT_DIR / "data"


def roi_110(w, l):
    n = w + l
    if n == 0: return 0, 0, 0
    net = w * (100/110) - l
    return net / n * 100, n, net


def build_dataset():
    """Build the research dataset joining TT lines, S3 sims, actual scores."""
    print("Building research dataset...")

    # Team total lines (2024-2025, ok status)
    tt = pd.read_parquet(DATA_DIR / "team_totals_historical.parquet")
    tt = tt[(tt["pull_status"] == "ok") & (tt["date"] >= "2024-01-01") & (tt["date"] <= "2025-12-31")]
    tt["game_id"] = tt["game_id"].astype(str)
    tt["thin_market_flag"] = (tt["books_count"] == 1).astype(int)
    print(f"  TT lines: {len(tt)} games")

    # Feature table (actual scores)
    ft = pd.read_parquet(PROJECT / "sim" / "data" / "feature_table.parquet")
    ft["game_pk"] = ft["game_pk"].astype(str)
    scores = ft[ft["season"].isin([2024, 2025])][
        ["game_pk", "season", "home_score", "away_score", "actual_total",
         "home_sp_id", "away_sp_id", "home_sp_name", "away_sp_name",
         "home_sp_xfip", "away_sp_xfip"]].copy()

    # S3 sim results (for p_under and projections)
    sim24 = pd.read_parquet(PROJECT / "mlb_sim" / "eval" / "sim_results_oos_2024.parquet")
    sim25 = pd.read_parquet(PROJECT / "mlb_sim" / "eval" / "sim_results_2025.parquet")
    sim = pd.concat([sim24, sim25], ignore_index=True)
    sim["game_pk"] = sim["game_pk"].astype(str)

    # Reconstruct per-team projections (APPROXIMATE)
    sim["mu_home"] = sim["m3_projection"].fillna(sim["sim_mean_total"]) * 0.505
    sim["mu_away"] = sim["m3_projection"].fillna(sim["sim_mean_total"]) * 0.495

    # Raw p_under for V1 signal identification
    if "p_under_line" not in sim.columns:
        sim["p_under_line"] = 1 - sim["p_over_line"]

    # CSW data from S1 inputs
    si = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_historical_2022_2024.parquet")
    # Also load 2025
    try:
        si25 = pd.read_parquet(PROJECT / "mlb_sim" / "data" / "sim_inputs_2025.parquet")
        si = pd.concat([si[si["season"].isin([2024])], si25], ignore_index=True)
    except:
        si = si[si["season"] == 2024]
    si["game_pk"] = si["game_pk"].astype(str)

    # Get CSW per starter
    home_csw = si[si["is_home"] == 1][["game_pk", "sp_id", "sp_csw_pct"]].rename(
        columns={"sp_id": "home_sp_id_si", "sp_csw_pct": "home_csw"})
    away_csw = si[si["is_home"] == 0][["game_pk", "sp_id", "sp_csw_pct"]].rename(
        columns={"sp_id": "away_sp_id_si", "sp_csw_pct": "away_csw"})

    # Join everything
    df = tt.merge(scores, left_on="game_id", right_on="game_pk", how="inner")
    df = df.merge(sim[["game_pk", "p_over_line", "p_under_line", "mu_home", "mu_away",
                        "sim_mean_total", "closing_line", "dominant_regime"]],
                  left_on="game_id", right_on="game_pk", how="inner", suffixes=("", "_sim"))
    df = df.merge(home_csw, left_on="game_id", right_on="game_pk", how="left")
    df = df.merge(away_csw, left_on="game_id", right_on="game_pk", how="left")

    print(f"  Joined dataset: {len(df)} games")
    print(f"  2024: {len(df[df['season']==2024])}, 2025: {len(df[df['season']==2025])}")

    # ── STEP 1: Identify suppressed team ──
    df["run_gap"] = (df["mu_home"] - df["mu_away"]).abs()

    # Suppressed = team with LOWER expected runs
    df["suppressed_is_home"] = (df["mu_home"] < df["mu_away"]).astype(int)
    df["suppressed_team"] = np.where(df["suppressed_is_home"] == 1, df["home_team"], df["away_team"])
    df["favored_team"] = np.where(df["suppressed_is_home"] == 1, df["away_team"], df["home_team"])

    # Suppressing pitcher = pitcher FACING the suppressed team
    # (the dominant starter whose suppression creates the run gap)
    df["suppressing_pitcher_xfip"] = np.where(
        df["suppressed_is_home"] == 1, df["away_sp_xfip"], df["home_sp_xfip"])
    df["suppressing_pitcher_csw"] = np.where(
        df["suppressed_is_home"] == 1, df["away_csw"], df["home_csw"])

    # Suppressed team's actual runs and team total line
    df["suppressed_actual"] = np.where(
        df["suppressed_is_home"] == 1, df["home_score"], df["away_score"])
    df["suppressed_tt_line"] = np.where(
        df["suppressed_is_home"] == 1, df["home_tt_line"], df["away_tt_line"])
    df["suppressed_over_price"] = np.where(
        df["suppressed_is_home"] == 1, df["home_over_price"], df["away_over_price"])
    df["suppressed_under_price"] = np.where(
        df["suppressed_is_home"] == 1, df["home_under_price"], df["away_under_price"])

    df["expected_runs_suppressed"] = np.where(
        df["suppressed_is_home"] == 1, df["mu_home"], df["mu_away"])
    df["pricing_error"] = df["suppressed_tt_line"] - df["expected_runs_suppressed"]

    # V1 signal flag
    df["v1_057"] = (df["p_under_line"] > 0.57).astype(int)
    df["v1_060"] = (df["p_under_line"] > 0.60).astype(int)

    df.to_parquet(DATA_DIR / "team_totals_results.parquet", index=False)
    print(f"  Saved: team_totals_results.parquet")
    return df


def run_backtest(df):
    """Run full backtest with all signals, controls, and diagnostics."""

    # V1 signal games only
    v1_games = df[df["v1_057"] == 1]
    v1_060 = df[df["v1_060"] == 1]
    print(f"\nV1 signal games (p_under > 0.57): {len(v1_games)}")
    print(f"V1 signal games (p_under > 0.60): {len(v1_060)}")

    # ═══════════════════════════════════════════════════════
    # STEP 2 — ROUNDING ARTIFACT CONTROLS
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("STEP 2 — ROUNDING ARTIFACT CONTROLS")
    print("="*60)

    # Control A: Pricing error distribution
    print(f"\n  Control A — Pricing error (APPROXIMATE S3 projections):")
    pe = v1_games["pricing_error"].dropna()
    print(f"    Mean: {pe.mean():+.3f}")
    print(f"    Median: {pe.median():+.3f}")
    print(f"    Std: {pe.std():.3f}")
    print(f"    % positive: {(pe > 0).mean()*100:.1f}%")
    print(f"    Systematically positive: {'YES' if pe.mean() > 0.1 else 'NO'}")

    # Control C: Half-run sensitivity
    print(f"\n  Control C — Half-run sensitivity:")
    for ending, label in [(lambda x: x % 1 == 0, "lines ending .0"),
                           (lambda x: x % 1 == 0.5, "lines ending .5")]:
        sub = v1_games[v1_games["suppressed_tt_line"].apply(ending)]
        if len(sub) > 0:
            w = (sub["suppressed_actual"] < sub["suppressed_tt_line"]).sum()
            l = (sub["suppressed_actual"] > sub["suppressed_tt_line"]).sum()
            p = (sub["suppressed_actual"] == sub["suppressed_tt_line"]).sum()
            r, n, net = roi_110(w, l)
            wr = w / (w + l) * 100 if (w + l) > 0 else 0
            print(f"    {label}: N={n}+{p}push, win%={wr:.1f}%, ROI={r:+.1f}%")

    # ═══════════════════════════════════════════════════════
    # STEP 3 — BACKTEST
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("STEP 3 — BACKTEST")
    print("="*60)

    gap_thresholds = [0.5, 0.75, 1.0]

    def grade_signal(sub, line_col, actual_col, stake=1.0, label=""):
        """Grade under bets."""
        w = (sub[actual_col] < sub[line_col]).sum()
        l = (sub[actual_col] > sub[line_col]).sum()
        p = (sub[actual_col] == sub[line_col]).sum()
        r, n, net = roi_110(int(w), int(l))
        wr = w / (w + l) * 100 if (w + l) > 0 else 0
        thin = " (THIN)" if n < 40 else ""
        return {"label": label, "n": n, "pushes": int(p), "wr": wr, "roi": r,
                "net": net, "thin": thin, "w": int(w), "l": int(l)}

    def run_group(gdf, group_label):
        """Run all signals for one market group."""
        print(f"\n  --- {group_label} (N={len(gdf)}) ---")

        # Signal A: full-game under
        for sig_label, sig_filter, threshold_needed in [
            ("A: Game Under (p>0.57)", gdf[gdf["v1_057"] == 1], False),
            ("B: TT Under (p>0.57)", gdf[gdf["v1_057"] == 1], True),
            ("C: TT Under (p>0.60)", gdf[gdf["v1_060"] == 1], True),
        ]:
            if not threshold_needed:
                # Full game under at closing line
                s = grade_signal(sig_filter, "closing_line", "actual_total", label=sig_label)
                print(f"    {sig_label}: N={s['n']}, win%={s['wr']:.1f}%, ROI={s['roi']:+.1f}%, net={s['net']:+.1f}u{s['thin']}")
            else:
                for gap in gap_thresholds:
                    sub = sig_filter[sig_filter["run_gap"] >= gap]
                    s = grade_signal(sub, "suppressed_tt_line", "suppressed_actual",
                                     label=f"{sig_label} gap>={gap}")
                    pe = sub["pricing_error"].mean() if len(sub) > 0 else 0
                    print(f"    {sig_label} gap>={gap}: N={s['n']}, win%={s['wr']:.1f}%, "
                          f"ROI={s['roi']:+.1f}%, net={s['net']:+.1f}u, "
                          f"avg_pe={pe:+.2f}{s['thin']}")

        # Signal D: Combined (both game under + TT under)
        for gap in gap_thresholds:
            sub = gdf[(gdf["v1_057"] == 1) & (gdf["run_gap"] >= gap)]
            if len(sub) == 0: continue
            # Game under leg
            gw = (sub["actual_total"] < sub["closing_line"]).sum()
            gl = (sub["actual_total"] > sub["closing_line"]).sum()
            # TT under leg
            tw = (sub["suppressed_actual"] < sub["suppressed_tt_line"]).sum()
            tl = (sub["suppressed_actual"] > sub["suppressed_tt_line"]).sum()
            # Combined: 2u risked per signal
            total_net = gw*(100/110) - gl + tw*(100/110) - tl
            total_risked = len(sub) * 2
            combined_roi = total_net / total_risked * 100 if total_risked > 0 else 0
            both_win = ((sub["actual_total"] < sub["closing_line"]) &
                        (sub["suppressed_actual"] < sub["suppressed_tt_line"])).sum()
            both_lose = ((sub["actual_total"] > sub["closing_line"]) &
                         (sub["suppressed_actual"] > sub["suppressed_tt_line"])).sum()
            split = len(sub) - both_win - both_lose
            thin = " (THIN)" if len(sub) < 40 else ""
            print(f"    D: Combined gap>={gap}: N={len(sub)}, ROI={combined_roi:+.1f}% (on 2u/sig), "
                  f"net={total_net:+.1f}u, both_win={both_win}, both_lose={both_lose}, split={split}{thin}")

    # Run for all three groups
    for group_label, group_filter in [
        ("ALL ROWS", df),
        ("BOOKS >= 2", df[df["thin_market_flag"] == 0]),
        ("THIN ONLY (1 book)", df[df["thin_market_flag"] == 1]),
    ]:
        run_group(group_filter, group_label)

    # ═══════════════════════════════════════════════════════
    # STEP 4 — DIAGNOSTICS
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("STEP 4 — DIAGNOSTICS")
    print("="*60)

    # Use best gap threshold (will determine from results)
    best_gap = 0.75  # default, adjust if needed
    sig_b = v1_games[v1_games["run_gap"] >= best_gap]

    # 4A: Run gap stratification
    print(f"\n  4A — Run gap stratification (Signal B, gap>={best_gap}):")
    for lo, hi, label in [(0.5, 0.75, "0.5-0.75"), (0.75, 1.0, "0.75-1.0"), (1.0, 99, ">1.0")]:
        sub = v1_games[(v1_games["run_gap"] >= lo) & (v1_games["run_gap"] < hi)]
        s = grade_signal(sub, "suppressed_tt_line", "suppressed_actual", label=label)
        print(f"    {label}: N={s['n']}, win%={s['wr']:.1f}%, ROI={s['roi']:+.1f}%{s['thin']}")

    # 4B: Suppressing pitcher dominance
    print(f"\n  4B — Suppressing pitcher metrics (V1 signal games):")
    for metric, label in [("suppressing_pitcher_csw", "CSW"), ("suppressing_pitcher_xfip", "xFIP")]:
        vals = v1_games[metric].dropna()
        if len(vals) < 40: continue
        q_cuts = vals.quantile([0.25, 0.50, 0.75]).values
        for qi, (lo, hi, ql) in enumerate([
            (vals.min(), q_cuts[0], "Q1"), (q_cuts[0], q_cuts[1], "Q2"),
            (q_cuts[1], q_cuts[2], "Q3"), (q_cuts[2], vals.max()+1, "Q4")]):
            sub = v1_games[(v1_games[metric] >= lo) & (v1_games[metric] < hi) & (v1_games["run_gap"] >= best_gap)]
            if len(sub) < 10: continue
            s = grade_signal(sub, "suppressed_tt_line", "suppressed_actual", label=f"{label} {ql}")
            print(f"    {label} {ql}: N={s['n']}, win%={s['wr']:.1f}%, ROI={s['roi']:+.1f}%{s['thin']}")

    # 4C: Pricing error by run_gap
    print(f"\n  4C — Pricing error by run_gap:")
    for lo, hi, label in [(0.5, 0.75, "0.5-0.75"), (0.75, 1.0, "0.75-1.0"), (1.0, 99, ">1.0")]:
        sub = v1_games[(v1_games["run_gap"] >= lo) & (v1_games["run_gap"] < hi)]
        pe = sub["pricing_error"].dropna()
        if len(pe) > 0:
            print(f"    {label}: mean_pe={pe.mean():+.3f}, median={pe.median():+.3f}, N={len(pe)}")

    # 4D: Season stability
    print(f"\n  4D — Season stability (Signal B, gap>={best_gap}):")
    for s in [2024, 2025]:
        sub = v1_games[(v1_games["season"] == s) & (v1_games["run_gap"] >= best_gap)]
        r = grade_signal(sub, "suppressed_tt_line", "suppressed_actual", label=str(s))
        print(f"    {s}: N={r['n']}, win%={r['wr']:.1f}%, ROI={r['roi']:+.1f}%, net={r['net']:+.1f}u{r['thin']}")

    # Check season concentration
    nets = {}
    for s in [2024, 2025]:
        sub = v1_games[(v1_games["season"] == s) & (v1_games["run_gap"] >= best_gap)]
        r = grade_signal(sub, "suppressed_tt_line", "suppressed_actual")
        nets[s] = r["net"]
    total_net = sum(nets.values())
    if total_net != 0:
        for s, n in nets.items():
            share = abs(n / total_net) * 100
            if share > 60:
                print(f"    *** {s} contributes {share:.0f}% of net units (SEASON CONCENTRATED)")

    # 2025 STANDALONE
    print(f"\n  2025 STANDALONE (Signal B, gap>={best_gap}):")
    sub_25 = v1_games[(v1_games["season"] == 2025) & (v1_games["run_gap"] >= best_gap)]
    r25 = grade_signal(sub_25, "suppressed_tt_line", "suppressed_actual", label="2025")
    print(f"    N={r25['n']}, win%={r25['wr']:.1f}%, ROI={r25['roi']:+.1f}%, net={r25['net']:+.1f}u{r25['thin']}")
    print(f"    2025 ROI positive: {'YES ✓' if r25['roi'] > 0 else 'NO ✗'}")

    # 4E: Permutation sanity
    print(f"\n  4E — Permutation sanity (Signal B, gap>={best_gap}):")
    sig_perm = v1_games[v1_games["run_gap"] >= best_gap].copy()
    actual_w = (sig_perm["suppressed_actual"] < sig_perm["suppressed_tt_line"]).sum()
    actual_l = (sig_perm["suppressed_actual"] > sig_perm["suppressed_tt_line"]).sum()
    actual_roi, _, _ = roi_110(int(actual_w), int(actual_l))

    rng = np.random.default_rng(42)
    shuf_rois = []
    actuals = sig_perm["suppressed_actual"].values.copy()
    for _ in range(200):
        rng.shuffle(actuals)
        sw = (actuals < sig_perm["suppressed_tt_line"].values).sum()
        sl = (actuals > sig_perm["suppressed_tt_line"].values).sum()
        sr, _, _ = roi_110(int(sw), int(sl))
        shuf_rois.append(sr)
    pctile = (np.array(shuf_rois) <= actual_roi).mean() * 100
    print(f"    Actual ROI: {actual_roi:+.1f}%")
    print(f"    Shuffled: mean={np.mean(shuf_rois):+.1f}%, std={np.std(shuf_rois):.1f}%")
    print(f"    Percentile: {pctile:.0f}%")
    if pctile < 90:
        print(f"    *** FLAG: not in top 10% of shuffled distribution")

    # ═══════════════════════════════════════════════════════
    # STEP 5 — SIDE-BY-SIDE
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("STEP 5 — SIDE-BY-SIDE COMPARISON (gap>={best_gap})")
    print("="*60)

    sig_all = v1_games[v1_games["run_gap"] >= best_gap]

    # Signal A: game under
    sa = grade_signal(sig_all, "closing_line", "actual_total", label="A: Game Under")
    # Signal B: TT under
    sb = grade_signal(sig_all, "suppressed_tt_line", "suppressed_actual", label="B: TT Under")

    print(f"\n  {'':>25} | {'Signal A':>12} | {'Signal B':>12}")
    print(f"  {'':>25} | {'Game Under':>12} | {'TT Under':>12}")
    print("  " + "-" * 55)
    print(f"  {'N':>25} | {sa['n']:>12} | {sb['n']:>12}")
    print(f"  {'Win rate':>25} | {sa['wr']:>11.1f}% | {sb['wr']:>11.1f}%")
    print(f"  {'ROI':>25} | {sa['roi']:>+11.1f}% | {sb['roi']:>+11.1f}%")
    print(f"  {'Net units':>25} | {sa['net']:>+11.1f}u | {sb['net']:>+11.1f}u")

    # ═══════════════════════════════════════════════════════
    # DECISION CRITERIA
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("DECISION CRITERIA (pre-registered)")
    print("="*60)

    pe_mean = v1_games[v1_games["run_gap"] >= best_gap]["pricing_error"].mean()
    criteria = {
        "ROI >= 3% pooled": sb["roi"] >= 3,
        "N >= 200": sb["n"] >= 200,
        "2025 standalone ROI positive": r25["roi"] > 0,
        "Pricing error positive": pe_mean > 0,
        "Permutation top 10%": pctile >= 90,
        "TT lines are REAL (not inferred)": True,
    }
    all_pass = all(criteria.values())

    for crit, passed in criteria.items():
        print(f"  {crit}: {'PASS ✓' if passed else 'FAIL ✗'}")
    print(f"\n  Overall: {'ALL CRITERIA MET' if all_pass else 'CRITERIA NOT MET'}")

    print(f"\n*** TEAM TOTALS RESEARCH COMPLETE — awaiting confirmation ***")


if __name__ == "__main__":
    df = build_dataset()
    run_backtest(df)
