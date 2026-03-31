#!/usr/bin/env python3
"""
MLB Phase M5 — Edge Exploitation Layer
Finds where M3 signal is strongest and builds concentration filters.
"""

import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "mlb" / "data"
SIM_DIR = PROJECT_ROOT / "sim" / "data"
M3_DIR = PROJECT_ROOT / "mlb" / "model_m3"
OUT_DIR = Path(__file__).resolve().parent

TRAIN_SEASONS = [2022, 2023]
VAL_SEASON = 2024
REF_SEASON = 2025

LEAGUE_AVG_WOBA = 0.310

def roi_110(hits, n):
    if n == 0: return np.nan
    return (hits * (100/110) - (n - hits)) / n * 100

def bet_stats(df, label=""):
    """Compute N, hit rate, ROI for a set of bets."""
    n = len(df)
    if n == 0:
        return {"label": label, "N": 0, "hit_rate": np.nan, "roi": np.nan}
    wins = df["bet_win"].sum()
    return {"label": label, "N": n, "hit_rate": round(wins/n*100, 1),
            "roi": round(roi_110(wins, n), 2)}


def build_full_dataset():
    """Build unified dataset with M3 + existing predictions for all seasons."""
    print("Building full dataset with predictions for all seasons...")

    ft = pd.read_parquet(SIM_DIR / "feature_table.parquet")
    m3f = pd.read_parquet(M3_DIR / "m3_features.parquet")

    # Merge M3 lineup features
    m3_cols = [c for c in m3f.columns if "lineup" in c or c == "game_pk"]
    ft = ft.merge(m3f[m3_cols].drop_duplicates(subset="game_pk"), on="game_pk", how="left")

    # Fill defaults
    for c in ft.columns:
        if "lineup_woba" in c: ft[c] = ft[c].fillna(LEAGUE_AVG_WOBA)
        elif "lineup_iso" in c: ft[c] = ft[c].fillna(0.150)
        elif "lineup_k_pct" in c: ft[c] = ft[c].fillna(0.224)
        elif "lineup_delta" in c: ft[c] = ft[c].fillna(0.0)

    # Add bullpen features if missing
    bp_file = SIM_DIR / "bullpen_features.parquet"
    if bp_file.exists() and "home_high_leverage_avail" not in ft.columns:
        bp = pd.read_parquet(bp_file)
        for side, tc in [("home", "home_team"), ("away", "away_team")]:
            bp_s = bp.rename(columns={
                "high_leverage_avail": f"{side}_high_leverage_avail",
                "bullpen_delta": f"{side}_bullpen_delta",
                "bp_delta_exposure": f"{side}_bp_delta_exposure",
            })
            avail = [c for c in [f"{side}_high_leverage_avail", f"{side}_bullpen_delta",
                                  f"{side}_bp_delta_exposure"] if c in bp_s.columns]
            if avail:
                ft = ft.merge(bp_s[["game_pk","team"]+avail].drop_duplicates(),
                               left_on=["game_pk",tc], right_on=["game_pk","team"],
                               how="left", suffixes=("","_bp"))
                ft.drop(columns=["team"]+[c for c in ft.columns if c.endswith("_bp")],
                         errors="ignore", inplace=True)

    if "flyball_wind_interaction" not in ft.columns:
        ft["flyball_wind_interaction"] = ft.get("wind_factor_effective", 0).fillna(0)
    for c in ["home_high_leverage_avail","away_high_leverage_avail"]:
        if c not in ft.columns: ft[c] = 1.0
    for c in ["home_bullpen_delta","away_bullpen_delta",
               "home_bp_delta_exposure","away_bp_delta_exposure"]:
        if c not in ft.columns: ft[c] = 0.0

    # ── Generate existing model predictions for ALL seasons ──
    with open(SIM_DIR / "phase9_baseline_model.pkl", "rb") as f:
        p9 = pickle.load(f)

    p9_feats = p9["features"]
    for f_name in p9_feats:
        if f_name not in ft.columns:
            ft[f_name] = 0.0

    X_p9 = ft[p9_feats].fillna(ft[p9_feats].median())
    ft["pred_existing"] = p9["pipeline"].predict(X_p9).clip(4, 22)

    # ── Generate M3 predictions for ALL seasons ──
    # Retrain M3 (variant B_lineup) on 2022-2023, predict all
    m3_feats = [
        "home_sp_xfip", "away_sp_xfip",
        "home_sp_k_pct", "away_sp_k_pct",
        "home_sp_bb_pct", "away_sp_bb_pct",
        "home_sp_avg_ip", "away_sp_avg_ip",
        "park_factor_runs", "park_factor_hr",
        "temperature", "wind_factor_effective",
        "umpire_over_rate",
        "home_rest_days", "away_rest_days",
        "doubleheader_flag",
        "flyball_wind_interaction",
        "home_high_leverage_avail", "away_high_leverage_avail",
        "home_bullpen_delta", "away_bullpen_delta",
        "home_bp_delta_exposure", "away_bp_delta_exposure",
        "home_lineup_woba", "away_lineup_woba",
        "home_lineup_iso", "away_lineup_iso",
        "home_lineup_k_pct", "away_lineup_k_pct",
        "home_lineup_delta", "away_lineup_delta",
    ]
    m3_feats = [f_name for f_name in m3_feats if f_name in ft.columns]

    train = ft[ft["season"].isin(TRAIN_SEASONS)]
    X_train = train[m3_feats].fillna(train[m3_feats].median())
    y_train = train["actual_total"]

    m3_pipe = Pipeline([("scaler", StandardScaler()),
                         ("ridge", RidgeCV(alphas=[1,5,10,25,50,100,200,500], cv=5))])
    m3_pipe.fit(X_train, y_train)

    X_all = ft[m3_feats].fillna(ft[m3_feats].median())
    ft["pred_m3"] = m3_pipe.predict(X_all).clip(4, 22)

    print(f"  Predictions generated: {len(ft)} games")
    print(f"  M3 Ridge alpha: {m3_pipe.named_steps['ridge'].alpha_}")

    # ── Merge closing lines ──
    br = pd.read_parquet(SIM_DIR / "bet_results.parquet")
    br["game_pk"] = pd.to_numeric(br["game_id"], errors="coerce").astype("Int64")
    cl = br[br["game_pk"].notna()][["game_pk","close_total"]].drop_duplicates()
    cl["game_pk"] = cl["game_pk"].astype(int)
    ft = ft.merge(cl, on="game_pk", how="left")

    # Also historical closing lines
    hl = pd.read_parquet(SIM_DIR / "mlb_historical_closing_lines.parquet")
    ft = ft.merge(hl[["game_pk","close_total"]].drop_duplicates().rename(
        columns={"close_total":"close_total_hist"}), on="game_pk", how="left")
    ft["close_total"] = ft["close_total"].fillna(ft["close_total_hist"])
    ft.drop(columns=["close_total_hist"], errors="ignore", inplace=True)

    print(f"  Close total coverage: {ft['close_total'].notna().sum()}/{len(ft)}")

    # ── Compute edges and bet outcomes ──
    ft["m3_edge"] = ft["pred_m3"] - ft["close_total"]
    ft["existing_edge"] = ft["pred_existing"] - ft["close_total"]
    ft["m3_lean"] = np.where(ft["m3_edge"] > 0, "OVER", "UNDER")

    # Bet outcome (betting in M3 direction)
    ft["bet_win"] = np.where(
        ft["m3_lean"] == "OVER",
        (ft["actual_total"] > ft["close_total"]).astype(int),
        (ft["actual_total"] < ft["close_total"]).astype(int)
    )
    # Push = loss
    ft["bet_push"] = (ft["actual_total"] == ft["close_total"]).astype(int)

    return ft


def main():
    lines = []
    def log(s=""):
        lines.append(s)
        print(s)

    log("=" * 70)
    log("MLB PHASE M5 — EDGE EXPLOITATION LAYER")
    log("=" * 70)
    log()

    df = build_full_dataset()
    has_line = df["close_total"].notna()

    # Split
    disc = df[df["season"].isin(TRAIN_SEASONS) & has_line].copy()
    val = df[(df["season"] == VAL_SEASON) & has_line].copy()
    oos = df[(df["season"] == REF_SEASON) & has_line].copy()

    log(f"Discovery: {len(disc)} games with lines")
    log(f"Validation: {len(val)} games with lines")
    log(f"OOS reference: {len(oos)} games with lines")
    log()

    # ══════════════════════════════════════════════════════════
    # SECTION 0 — M3 BASELINE
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 0 — M3 BASELINE CONFIRMATION")
    log("=" * 70)
    log()

    for label, data, min_edges in [("Discovery", disc, [0.5, 1.0, 1.5]),
                                     ("Validation (2024)", val, [0.5, 1.0, 1.5]),
                                     ("OOS (2025)", oos, [0.5, 1.0, 1.5])]:
        log(f"  {label}:")
        mae = np.abs(data["actual_total"] - data["pred_m3"]).mean()
        log(f"    M3 MAE: {mae:.3f}")
        for me in min_edges:
            sub = data[data["m3_edge"].abs() >= me]
            s = bet_stats(sub)
            log(f"    edge >= {me}: N={s['N']}, hit={s['hit_rate']}%, ROI={s['roi']:+.1f}%")
        log()

    # ══════════════════════════════════════════════════════════
    # COMPONENT 1 — DISAGREEMENT ZONE
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 1 — DISAGREEMENT ZONE ANALYSIS")
    log("=" * 70)
    log()

    df["disagree_mag"] = (df["pred_m3"] - df["pred_existing"]).abs()
    df["disagree_dir"] = np.where(
        np.sign(df["m3_edge"]) == np.sign(df["existing_edge"]), "SAME", "OPPOSITE"
    )

    # Refresh splits
    disc = df[df["season"].isin(TRAIN_SEASONS) & has_line].copy()
    val = df[(df["season"] == VAL_SEASON) & has_line].copy()

    log("Disagreement magnitude distribution:")
    for label, data in [("Discovery", disc), ("Validation", val)]:
        dm = data["disagree_mag"]
        log(f"  {label}: mean={dm.mean():.2f}, std={dm.std():.2f}, "
            f"median={dm.median():.2f}, max={dm.max():.2f}")
    log()

    # ROI by disagreement bucket (M3 edge >= 1.0 baseline)
    log("ROI by disagreement magnitude (M3 edge >= 1.0):")
    log(f"{'Bucket':<15s} {'Disc N':>7s} {'Disc ROI':>9s} {'Val N':>7s} {'Val ROI':>9s}")
    log("-" * 50)
    buckets = [(0, 0.5, "0.0-0.5"), (0.5, 1.0, "0.5-1.0"),
               (1.0, 1.5, "1.0-1.5"), (1.5, 2.0, "1.5-2.0"), (2.0, 99, "2.0+")]

    for lo, hi, label_b in buckets:
        for lbl, data in [("disc", disc), ("val", val)]:
            mask = (data["m3_edge"].abs() >= 1.0) & (data["disagree_mag"] >= lo) & (data["disagree_mag"] < hi)
            sub = data[mask]
            s = bet_stats(sub)
            if lbl == "disc":
                d_n, d_roi = s["N"], s["roi"]
            else:
                v_n, v_roi = s["N"], s["roi"]
        log(f"{label_b:<15s} {d_n:>7d} {d_roi:>+8.1f}% {v_n:>7d} {v_roi:>+8.1f}%")
    log()

    # Disagreement direction
    log("ROI by disagreement direction (M3 edge >= 1.0):")
    for direction in ["SAME", "OPPOSITE"]:
        for lbl, data in [("Disc", disc), ("Val", val)]:
            mask = (data["m3_edge"].abs() >= 1.0) & (data["disagree_dir"] == direction)
            s = bet_stats(data[mask])
            log(f"  {direction} ({lbl}): N={s['N']}, hit={s['hit_rate']}%, ROI={s['roi']:+.1f}%")
    log()

    # Combined: large edge + large disagreement
    log("Combined: M3 edge >= 1.0 AND disagree >= 1.0:")
    for lbl, data in [("Discovery", disc), ("Validation", val)]:
        mask = (data["m3_edge"].abs() >= 1.0) & (data["disagree_mag"] >= 1.0)
        s = bet_stats(data[mask])
        log(f"  {lbl}: N={s['N']}, hit={s['hit_rate']}%, ROI={s['roi']:+.1f}%")
    log()

    # Save disagreement analysis
    disagree_cols = ["game_pk", "season", "pred_m3", "pred_existing", "close_total",
                      "actual_total", "m3_edge", "existing_edge", "disagree_mag",
                      "disagree_dir", "bet_win"]
    disagree_cols = [c for c in disagree_cols if c in df.columns]
    df[has_line][disagree_cols].to_parquet(OUT_DIR / "disagreement_analysis.parquet", index=False)

    # ══════════════════════════════════════════════════════════
    # COMPONENT 2 — LINEUP DEVIATION
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 2 — LINEUP DEVIATION ANALYSIS")
    log("=" * 70)
    log()

    # Build lineup deviation from M3 features
    # home_lineup_delta and away_lineup_delta already exist in M3 features
    df["combined_lineup_dev"] = df["home_lineup_delta"].abs() + df["away_lineup_delta"].abs()

    # Also compute directional: negative = weaker lineup than normal
    # For scoring: if home has weak lineup (negative delta), expect fewer home runs
    # If away has weak lineup, expect fewer away runs
    df["net_lineup_dev"] = df["home_lineup_delta"] + df["away_lineup_delta"]

    disc = df[df["season"].isin(TRAIN_SEASONS) & has_line].copy()
    val = df[(df["season"] == VAL_SEASON) & has_line].copy()

    log("Lineup deviation distribution:")
    for label, data in [("Discovery", disc), ("Validation", val)]:
        cd = data["combined_lineup_dev"]
        log(f"  {label}: mean={cd.mean():.4f}, std={cd.std():.4f}, "
            f"max={cd.max():.4f}")
    log()

    # Build full-strength baseline for lineup deviation
    # Use lineups + hitter game logs
    hitters = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    lineup_data = pd.read_parquet(DATA_DIR / "lineups.parquet")
    tgi = pd.read_parquet(DATA_DIR / "team_game_index.parquet")

    h = hitters[hitters["starter_flag"] == 1].copy()
    h["game_date"] = pd.to_datetime(h["game_date"])

    # Compute wOBA per hitter-game
    h["woba_num"] = (0.69*h["walks"] + 0.72*h["hit_by_pitch"] + 0.89*h["singles"] +
                     1.27*h["doubles"] + 1.62*h["triples"] + 2.10*h["home_runs"])
    h["woba_den"] = h["at_bats"] + h["walks"] + h["sac_flies"] + h["hit_by_pitch"]

    # Per-player season rolling wOBA
    h = h.sort_values(["player_id", "game_date"])
    h["cum_woba_num"] = h.groupby(["player_id", "season"])["woba_num"].transform(
        lambda x: x.expanding().sum().shift(1))
    h["cum_woba_den"] = h.groupby(["player_id", "season"])["woba_den"].transform(
        lambda x: x.expanding().sum().shift(1))
    h["player_woba"] = np.where(h["cum_woba_den"] >= 20,
                                 h["cum_woba_num"] / h["cum_woba_den"], LEAGUE_AVG_WOBA)

    # Find most common starters per team-season (top 9 by start count)
    starter_counts = h.groupby(["player_id", "team", "season"]).size().reset_index(name="starts")
    starter_counts = starter_counts.sort_values(["team", "season", "starts"], ascending=[True, True, False])
    top_starters = starter_counts.groupby(["team", "season"]).head(9)
    top_starters["is_regular"] = 1

    # Merge regular flag
    h = h.merge(top_starters[["player_id", "team", "season", "is_regular"]],
                 on=["player_id", "team", "season"], how="left")
    h["is_regular"] = h["is_regular"].fillna(0)

    # Per game: count regulars in lineup, compute lineup wOBA
    game_lineup_stats = h.groupby(["game_pk", "team", "season"]).agg(
        lineup_woba=("player_woba", "mean"),
        n_regulars=("is_regular", "sum"),
    ).reset_index()

    # Full-strength baseline: games where >= 7 of 9 regulars present
    game_lineup_stats = game_lineup_stats.merge(
        tgi[["game_pk", "team", "game_date"]].drop_duplicates(), on=["game_pk", "team"], how="left")
    game_lineup_stats["game_date"] = pd.to_datetime(game_lineup_stats["game_date"])
    game_lineup_stats = game_lineup_stats.sort_values(["team", "game_date"])

    def full_strength_baseline(g):
        g = g.copy()
        full_strength = g[g["n_regulars"] >= 7]["lineup_woba"]
        g["full_strength_woba"] = full_strength.expanding(min_periods=5).mean().shift(1)
        # Fallback: all games
        all_woba = g["lineup_woba"].expanding(min_periods=5).mean().shift(1)
        g["full_strength_woba"] = g["full_strength_woba"].fillna(all_woba)
        g["lineup_dev_vs_full"] = g["lineup_woba"] - g["full_strength_woba"]
        g["n_missing_regulars"] = 9 - g["n_regulars"]
        g["used_fallback"] = g["full_strength_woba"].isna().astype(int)
        return g

    game_lineup_stats = game_lineup_stats.groupby(["team", "season"],
                                                    group_keys=False).apply(full_strength_baseline)

    # Merge into main df (home + away)
    for side, tc in [("home", "home_team"), ("away", "away_team")]:
        gls = game_lineup_stats[["game_pk", "team", "lineup_dev_vs_full",
                                   "n_missing_regulars", "used_fallback"]].rename(columns={
            "lineup_dev_vs_full": f"{side}_dev_vs_full",
            "n_missing_regulars": f"{side}_n_missing",
            "used_fallback": f"{side}_used_fallback",
        })
        df = df.merge(gls, left_on=["game_pk", tc], right_on=["game_pk", "team"],
                       how="left", suffixes=("", f"_{side}_x"))
        df.drop(columns=["team"] + [c for c in df.columns if c.endswith(f"_{side}_x")],
                 errors="ignore", inplace=True)

    for c in ["home_dev_vs_full", "away_dev_vs_full"]:
        df[c] = df[c].fillna(0.0)
    for c in ["home_n_missing", "away_n_missing"]:
        df[c] = df[c].fillna(0)

    df["combined_dev_vs_full"] = df["home_dev_vs_full"].abs() + df["away_dev_vs_full"].abs()
    df["net_dev_vs_full"] = df["home_dev_vs_full"] + df["away_dev_vs_full"]

    disc = df[df["season"].isin(TRAIN_SEASONS) & has_line].copy()
    val = df[(df["season"] == VAL_SEASON) & has_line].copy()

    log("Full-strength lineup deviation (vs games with 7+ regulars):")
    for label, data in [("Discovery", disc), ("Validation", val)]:
        cdv = data["combined_dev_vs_full"]
        log(f"  {label}: mean={cdv.mean():.4f}, std={cdv.std():.4f}")
        fb = data["home_used_fallback"].sum() + data["away_used_fallback"].sum()
        total = len(data) * 2
        log(f"    Fallback used: {fb}/{total} ({fb/total*100:.1f}%)")
    log()

    # ROI by lineup deviation (M3 edge >= 1.0)
    log("ROI by combined lineup deviation (M3 edge >= 1.0):")
    log(f"{'Bucket':<20s} {'Disc N':>7s} {'Disc ROI':>9s} {'Val N':>7s} {'Val ROI':>9s}")
    log("-" * 50)
    dev_buckets = [(0, 0.005, "tiny (<0.005)"), (0.005, 0.015, "small (0.005-0.015)"),
                    (0.015, 0.030, "medium (0.015-0.030)"), (0.030, 99, "large (0.030+)")]
    for lo, hi, label_b in dev_buckets:
        for lbl, data in [("disc", disc), ("val", val)]:
            mask = (data["m3_edge"].abs() >= 1.0) & (data["combined_dev_vs_full"] >= lo) & (data["combined_dev_vs_full"] < hi)
            s = bet_stats(data[mask])
            if lbl == "disc": d_n, d_roi = s["N"], s["roi"]
            else: v_n, v_roi = s["N"], s["roi"]
        log(f"{label_b:<20s} {d_n:>7d} {d_roi:>+8.1f}% {v_n:>7d} {v_roi:>+8.1f}%")
    log()

    # Directional asymmetry
    log("Directional asymmetry (M3 edge >= 1.0):")
    log("  (negative dev = weaker lineup than normal, positive = stronger)")
    for lbl, data in [("Discovery", disc), ("Validation", val)]:
        for direction, mask_fn in [
            ("Weaker lineup", lambda d: d["net_dev_vs_full"] < -0.005),
            ("Normal", lambda d: d["net_dev_vs_full"].abs() <= 0.005),
            ("Stronger lineup", lambda d: d["net_dev_vs_full"] > 0.005),
        ]:
            mask = (data["m3_edge"].abs() >= 1.0) & mask_fn(data)
            s = bet_stats(data[mask])
            log(f"  {direction} ({lbl}): N={s['N']}, ROI={s['roi']:+.1f}%")
    log()

    # Save
    dev_cols = ["game_pk", "season", "home_dev_vs_full", "away_dev_vs_full",
                 "combined_dev_vs_full", "net_dev_vs_full",
                 "home_n_missing", "away_n_missing", "m3_edge", "bet_win"]
    dev_cols = [c for c in dev_cols if c in df.columns]
    df[has_line][dev_cols].to_parquet(OUT_DIR / "lineup_deviation_analysis.parquet", index=False)

    # ══════════════════════════════════════════════════════════
    # COMPONENT 3 — TIMING (SKIP)
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 3 — LINEUP RELEASE TIMING")
    log("=" * 70)
    log()
    log("SKIPPED: Lineup release timestamps are not available in the")
    log("current dataset. The M2 warehouse extracts confirmed lineups")
    log("from boxscores (post-game), not from pre-game lineup announcements.")
    log("No timestamp data exists to classify EARLY vs STANDARD vs LATE.")
    log()
    log("REQUIREMENT: To build this component, would need:")
    log("  - Real-time lineup release timestamps (e.g., from MLB Stats API")
    log("    live feed polling)")
    log("  - Forward collection starting 2026 season")
    log()

    # ══════════════════════════════════════════════════════════
    # COMPONENT 4 — EDGE CONCENTRATION
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 4 — EDGE CONCENTRATION RESULTS")
    log("=" * 70)
    log()

    # Build edge quality scores
    # Normalize each component to 0-1 range
    for data in [disc, val]:
        # A: Edge only
        data["score_A"] = data["m3_edge"].abs()

        # B: Edge + disagreement (equal weight)
        edge_norm = data["m3_edge"].abs() / data["m3_edge"].abs().quantile(0.95).clip(0.01)
        disagree_norm = data["disagree_mag"] / data["disagree_mag"].quantile(0.95).clip(0.01)
        data["score_B"] = (edge_norm + disagree_norm) / 2

        # C: Edge + disagreement + lineup deviation
        dev_norm = data["combined_dev_vs_full"] / data["combined_dev_vs_full"].quantile(0.95).clip(0.001)
        data["score_C"] = (edge_norm + disagree_norm + dev_norm) / 3

    log("Edge concentration comparison:")
    log(f"{'Scheme':<10s} {'Pctile':<8s} {'Disc N':>7s} {'Disc ROI':>9s} {'Val N':>7s} {'Val ROI':>9s}")
    log("-" * 55)

    conc_results = []
    for scheme in ["score_A", "score_B", "score_C"]:
        scheme_label = {"score_A": "A (edge)", "score_B": "B (e+dis)", "score_C": "C (e+d+l)"}[scheme]
        for pctile, pct_label in [(90, "top 10%"), (80, "top 20%"), (70, "top 30%")]:
            for lbl, data in [("disc", disc), ("val", val)]:
                threshold = data[scheme].quantile(pctile / 100)
                mask = data[scheme] >= threshold
                s = bet_stats(data[mask])
                if lbl == "disc": d_n, d_roi, d_hr = s["N"], s["roi"], s["hit_rate"]
                else: v_n, v_roi, v_hr = s["N"], s["roi"], s["hit_rate"]

            log(f"{scheme_label:<10s} {pct_label:<8s} {d_n:>7d} {d_roi:>+8.1f}% {v_n:>7d} {v_roi:>+8.1f}%")
            conc_results.append({
                "scheme": scheme_label, "percentile": pct_label,
                "disc_n": d_n, "disc_roi": d_roi, "disc_hit": d_hr,
                "val_n": v_n, "val_roi": v_roi, "val_hit": v_hr,
            })
    log()

    # Volume trade-off
    log("Volume trade-off (validation, M3 edge >= 1.0 baseline):")
    base = bet_stats(val[val["m3_edge"].abs() >= 1.0])
    log(f"  Baseline: N={base['N']}, ROI={base['roi']:+.1f}%")
    for scheme in ["score_B", "score_C"]:
        scheme_label = {"score_B": "B (e+dis)", "score_C": "C (e+d+l)"}[scheme]
        threshold = val[scheme].quantile(0.80)
        mask = (val["m3_edge"].abs() >= 1.0) & (val[scheme] >= threshold)
        s = bet_stats(val[mask])
        removed = base["N"] - s["N"]
        log(f"  {scheme_label} top 20% filter: N={s['N']}, ROI={s['roi']:+.1f}% "
            f"(removed {removed} bets, {removed/base['N']*100:.0f}% volume)")
    log()

    pd.DataFrame(conc_results).to_csv(OUT_DIR / "edge_concentration_results.csv", index=False)

    # ══════════════════════════════════════════════════════════
    # COMPONENT 5 — DIRECTIONAL ASYMMETRY
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 5 — DIRECTIONAL ASYMMETRY")
    log("=" * 70)
    log()

    log("OVER vs UNDER performance (M3 signal):")
    log(f"{'Direction':<10s} {'Edge':>6s} {'Disc N':>7s} {'Disc ROI':>9s} {'Val N':>7s} {'Val ROI':>9s}")
    log("-" * 50)
    for direction in ["OVER", "UNDER"]:
        for min_e in [0.5, 1.0, 1.5]:
            for lbl, data in [("disc", disc), ("val", val)]:
                mask = (data["m3_lean"] == direction) & (data["m3_edge"].abs() >= min_e)
                s = bet_stats(data[mask])
                if lbl == "disc": d_n, d_roi = s["N"], s["roi"]
                else: v_n, v_roi = s["N"], s["roi"]
            log(f"{direction:<10s} >={min_e:<4.1f} {d_n:>7d} {d_roi:>+8.1f}% {v_n:>7d} {v_roi:>+8.1f}%")
    log()

    # Lineup direction alignment
    log("Lineup direction × signal direction:")
    log("  (OVER when lineup stronger; UNDER when lineup weaker)")
    for lbl, data in [("Discovery", disc), ("Validation", val)]:
        # Aligned: OVER + positive net dev, or UNDER + negative net dev
        aligned = (
            ((data["m3_lean"] == "OVER") & (data["net_dev_vs_full"] > 0.005)) |
            ((data["m3_lean"] == "UNDER") & (data["net_dev_vs_full"] < -0.005))
        ) & (data["m3_edge"].abs() >= 1.0)
        misaligned = (
            ((data["m3_lean"] == "OVER") & (data["net_dev_vs_full"] < -0.005)) |
            ((data["m3_lean"] == "UNDER") & (data["net_dev_vs_full"] > 0.005))
        ) & (data["m3_edge"].abs() >= 1.0)

        s_a = bet_stats(data[aligned])
        s_m = bet_stats(data[misaligned])
        log(f"  {lbl}:")
        log(f"    Aligned:    N={s_a['N']}, ROI={s_a['roi']:+.1f}%")
        log(f"    Misaligned: N={s_m['N']}, ROI={s_m['roi']:+.1f}%")
    log()

    # ══════════════════════════════════════════════════════════
    # COMPONENT 6 — BOOK EFFICIENCY (SKIP)
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 6 — BOOK-SPECIFIC EFFICIENCY")
    log("=" * 70)
    log()
    log("SKIPPED: The existing closing line data uses a single consensus")
    log("line (primarily DraftKings). Book-level line comparison is not")
    log("available in the historical dataset.")
    log("Forward collection (2026+) will capture per-book snapshots.")
    log()

    # ══════════════════════════════════════════════════════════
    # SECTION 7 — RECOMMENDATION
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 7 — PRODUCTION RECOMMENDATION")
    log("=" * 70)
    log()

    # Check gates for best filter
    # Find best filter on validation
    best_filter = None
    best_improvement = 0
    base_val_roi = base["roi"]

    # Test: edge >= 1.0 + disagree >= 1.0
    combo_val = val[(val["m3_edge"].abs() >= 1.0) & (val["disagree_mag"] >= 1.0)]
    combo_stats = bet_stats(combo_val)
    improvement_combo = combo_stats["roi"] - base_val_roi if not np.isnan(combo_stats["roi"]) else -999

    # Test: score_B top 20% (edge + disagreement)
    thresh_b = val["score_B"].quantile(0.80)
    filter_b = val[(val["m3_edge"].abs() >= 1.0) & (val["score_B"] >= thresh_b)]
    stats_b = bet_stats(filter_b)
    improvement_b = stats_b["roi"] - base_val_roi if not np.isnan(stats_b["roi"]) else -999

    # Test: score_C top 20%
    thresh_c = val["score_C"].quantile(0.80)
    filter_c = val[(val["m3_edge"].abs() >= 1.0) & (val["score_C"] >= thresh_c)]
    stats_c = bet_stats(filter_c)
    improvement_c = stats_c["roi"] - base_val_roi if not np.isnan(stats_c["roi"]) else -999

    filters = {
        "edge+disagree>=1.0": (combo_stats, improvement_combo),
        "score_B top 20%": (stats_b, improvement_b),
        "score_C top 20%": (stats_c, improvement_c),
    }

    log("Filter comparison (vs M3 edge >= 1.0 baseline):")
    log(f"  Baseline: N={base['N']}, hit={base['hit_rate']}%, ROI={base_val_roi:+.1f}%")
    log()

    gates_passed = {}
    for fname, (fstats, fimp) in filters.items():
        n_ok = fstats["N"] >= 200
        roi_ok = fimp >= 2.0
        # Check discovery
        if "disagree" in fname:
            d_mask = (disc["m3_edge"].abs() >= 1.0) & (disc["disagree_mag"] >= 1.0)
        elif "score_B" in fname:
            d_thresh = disc["score_B"].quantile(0.80)
            d_mask = (disc["m3_edge"].abs() >= 1.0) & (disc["score_B"] >= d_thresh)
        else:
            d_thresh = disc["score_C"].quantile(0.80)
            d_mask = (disc["m3_edge"].abs() >= 1.0) & (disc["score_C"] >= d_thresh)
        d_stats = bet_stats(disc[d_mask])
        disc_ok = d_stats["roi"] > 0 if not np.isnan(d_stats["roi"]) else False

        # OVER/UNDER balance
        if fstats["N"] > 0:
            if "disagree" in fname:
                v_sub = val[(val["m3_edge"].abs() >= 1.0) & (val["disagree_mag"] >= 1.0)]
            elif "score_B" in fname:
                v_sub = filter_b
            else:
                v_sub = filter_c
            over_pct = (v_sub["m3_lean"] == "OVER").mean()
            balance_ok = 0.35 <= over_pct <= 0.65
        else:
            balance_ok = False

        all_ok = n_ok and roi_ok and disc_ok and balance_ok
        gates_passed[fname] = all_ok

        log(f"  {fname}:")
        log(f"    N={fstats['N']}, hit={fstats['hit_rate']}%, ROI={fstats['roi']:+.1f}%")
        log(f"    Improvement: {fimp:+.1f}pp {'PASS' if roi_ok else 'FAIL'}")
        log(f"    N >= 200: {'PASS' if n_ok else 'FAIL'}")
        log(f"    Discovery ROI > 0: {'PASS' if disc_ok else 'FAIL'} (disc ROI={d_stats['roi']:+.1f}%)")
        log(f"    OVER/UNDER balance: {'PASS' if balance_ok else 'FAIL'} ({over_pct*100:.0f}% OVER)")
        log(f"    ALL GATES: {'PASS' if all_ok else 'FAIL'}")
        log()

    passing = [k for k, v in gates_passed.items() if v]
    if passing:
        best = max(passing, key=lambda k: filters[k][1])
        log(f"RECOMMENDATION: DEPLOY filter '{best}'")
        fstats, fimp = filters[best]
        log(f"  Expected ROI improvement: {fimp:+.1f}pp over M3 baseline")
        log(f"  Expected volume: {fstats['N']} bets on 2024 holdout")
    else:
        # Find closest
        closest = max(filters.keys(), key=lambda k: filters[k][1])
        fstats, fimp = filters[closest]
        log(f"RECOMMENDATION: NOT READY")
        log(f"  Closest filter: '{closest}' ({fimp:+.1f}pp, but failed gates)")
        log()
        log("  M3 edge >= 1.0 remains the recommended strategy.")
        log("  No concentration filter clears all gates simultaneously.")
        log("  The M3 signal is broadly distributed — filtering reduces")
        log("  volume without sufficient ROI concentration to justify it.")
    log()

    # ══════════════════════════════════════════════════════════
    # SECTION 8 — PATTERN OBSERVATIONS
    # ══════════════════════════════════════════════════════════
    log("=" * 70)
    log("SECTION 8 — PATTERN OBSERVATIONS")
    log("=" * 70)
    log()

    log("1. Is M3 edge concentrated in specific game conditions?")
    log("   The disagreement zone analysis shows whether model divergence")
    log("   predicts edge quality. If large disagreement produces higher ROI,")
    log("   it means the lineup signal is strongest when it contradicts the")
    log("   existing team-level model — exactly when lineup composition")
    log("   deviates most from the team average.")
    log()

    log("2. Does disagreement magnitude reliably predict edge quality?")
    # Summarize bucket pattern
    log("   See Section 1 buckets for monotonicity of ROI vs disagreement.")
    log()

    log("3. Does lineup deviation asymmetry explain directional bias?")
    log("   See Section 5 alignment analysis. If aligned signals (OVER+stronger")
    log("   or UNDER+weaker) outperform misaligned, then lineup deviation")
    log("   direction is a genuine signal amplifier.")
    log()

    log("4. What is the clearest next edge source after M5?")
    log("   - Forward collection of lineup release timestamps (Component 3)")
    log("   - Per-book line comparison (Component 6)")
    log("   - Live lineup-adjusted line monitoring (capture when books adjust)")
    log("   - SP scratch detection timing (early vs late scratch edge)")
    log()

    log("5. Is the system ready for live betting deployment?")
    log("   M3 is validated: +7.5% ROI at edge >= 1.0 on 2024 holdout.")
    if passing:
        log(f"   M5 adds a concentration filter ('{passing[0]}') that")
        log(f"   improves ROI by {filters[passing[0]][1]:+.1f}pp.")
        log("   READY for shadow deployment in 2026 season.")
    else:
        log("   M5 filters do not reliably concentrate the edge beyond M3.")
        log("   M3 edge >= 1.0 is the recommended live strategy.")
        log("   Deploy M3 as shadow for 2026 Opening Day.")
    log()

    # Save report
    with open(OUT_DIR / "m5_summary.txt", "w") as f:
        f.write("\n".join(lines))

    log()
    log("=" * 70)
    log("Files saved:")
    log(f"  mlb/model_m5/disagreement_analysis.parquet")
    log(f"  mlb/model_m5/lineup_deviation_analysis.parquet")
    log(f"  mlb/model_m5/edge_concentration_results.csv")
    log(f"  mlb/model_m5/m5_summary.txt")
    log("=" * 70)


if __name__ == "__main__":
    main()
