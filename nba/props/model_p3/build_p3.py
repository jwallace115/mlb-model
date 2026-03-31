#!/usr/bin/env python3
"""
NBA Props Phase P3 — Baseline Model Build
Simple distribution-driven projections for Points, Rebounds, Assists, Threes.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NBA_DIR = PROJECT_ROOT / "nba"
PROPS_DIR = NBA_DIR / "props"
PROC_DIR = PROPS_DIR / "processed"
OUT_DIR = Path(__file__).resolve().parent

LEAGUE_AVG = {"POINTS": 14.0, "REBOUNDS": 5.0, "ASSISTS": 3.5, "THREES": 1.5}
MIN_STD = {"POINTS": 4.0, "REBOUNDS": 2.0, "ASSISTS": 1.5, "THREES": 0.8}

STAT_COL = {"POINTS": "PTS", "REBOUNDS": "REB", "ASSISTS": "AST", "THREES": "FG3M"}

def roi_110(w, n):
    if n == 0: return np.nan
    return (w * (100/110) - (n - w)) / n * 100


# ══════════════════════════════════════════════════════════════
# FIX: REBUILD MARKET VIEW WITH ODDS
# ══════════════════════════════════════════════════════════════

def rebuild_market_view():
    """Rebuild market view with best odds from props_lines."""
    print("Rebuilding market view with odds...")
    pl = pd.read_parquet(PROC_DIR / "props_lines.parquet")
    pr = pd.read_parquet(PROC_DIR / "props_results.parquet")

    # Get actuals
    actuals = pr.groupby(["event_id", "player_id", "prop_type"]).first()[
        ["actual_value", "over_hit", "under_hit", "game_id"]
    ].reset_index()

    grouped = pl.groupby(["event_id", "player_id", "player_name", "prop_type",
                           "game_date", "season", "dataset_split"])

    rows = []
    for key, group in grouped:
        event_id, player_id, player_name, prop_type, game_date, season, split = key
        lines = group["line"].dropna()
        if len(lines) == 0:
            continue

        over_rows = group[group["over_odds"].notna()]
        under_rows = group[group["under_odds"].notna()]

        # Best over: lowest line
        if len(over_rows) > 0:
            idx = over_rows["line"].idxmin()
            best_over_line = over_rows.loc[idx, "line"]
            best_over_odds = over_rows.loc[idx, "over_odds"]
            best_over_book = over_rows.loc[idx, "bookmaker"]
        else:
            best_over_line = lines.min()
            best_over_odds = np.nan
            best_over_book = ""

        # Best under: highest line
        if len(under_rows) > 0:
            idx = under_rows["line"].idxmax()
            best_under_line = under_rows.loc[idx, "line"]
            best_under_odds = under_rows.loc[idx, "under_odds"]
            best_under_book = under_rows.loc[idx, "bookmaker"]
        else:
            best_under_line = lines.max()
            best_under_odds = np.nan
            best_under_book = ""

        # Consensus
        consensus_line = round(lines.median(), 1)
        cons_over = group[(group["line"] == consensus_line) & group["over_odds"].notna()]
        cons_under = group[(group["line"] == consensus_line) & group["under_odds"].notna()]
        consensus_over_odds = cons_over["over_odds"].median() if len(cons_over) > 0 else np.nan
        consensus_under_odds = cons_under["under_odds"].median() if len(cons_under) > 0 else np.nan

        rows.append({
            "event_id": event_id, "player_id": player_id,
            "player_name": player_name, "prop_type": prop_type,
            "game_date": game_date, "season": season, "dataset_split": split,
            "consensus_line": consensus_line,
            "consensus_over_odds": consensus_over_odds,
            "consensus_under_odds": consensus_under_odds,
            "best_over_line": best_over_line, "best_over_odds": best_over_odds,
            "best_over_book": best_over_book,
            "best_under_line": best_under_line, "best_under_odds": best_under_odds,
            "best_under_book": best_under_book,
            "n_books": group["bookmaker"].nunique(),
            "line_std": round(lines.std(), 2) if len(lines) > 1 else 0.0,
        })

    mv = pd.DataFrame(rows)
    mv = mv.merge(actuals, on=["event_id", "player_id", "prop_type"], how="left")
    mv.to_parquet(PROC_DIR / "props_market_view.parquet", index=False)

    has_odds = mv["consensus_over_odds"].notna() & mv["consensus_under_odds"].notna()
    print(f"  Market view: {len(mv):,} rows")
    print(f"  With odds: {has_odds.sum():,} ({has_odds.mean()*100:.1f}%)")
    return mv


# ══════════════════════════════════════════════════════════════
# DEVIG
# ══════════════════════════════════════════════════════════════

def _to_implied(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def devig(over_odds, under_odds):
    ro, ru = _to_implied(over_odds), _to_implied(under_odds)
    if pd.isna(ro) or pd.isna(ru): return np.nan, np.nan
    t = ro + ru
    return (ro/t, ru/t) if t > 0 else (np.nan, np.nan)


# ══════════════════════════════════════════════════════════════
# PROJECTION ENGINE
# ══════════════════════════════════════════════════════════════

def build_projections():
    """Build rolling projections for all players."""
    print("Building projections...")
    logs = pd.read_parquet(NBA_DIR / "model_c" / "player_game_logs.parquet")
    logs["MIN"] = pd.to_numeric(logs["MIN"], errors="coerce").fillna(0)
    logs["PTS"] = pd.to_numeric(logs["PTS"], errors="coerce").fillna(0)
    logs["REB"] = pd.to_numeric(logs["REB"], errors="coerce").fillna(0)
    logs["AST"] = pd.to_numeric(logs["AST"], errors="coerce").fillna(0)
    logs["FG3M"] = pd.to_numeric(logs["FG3M"], errors="coerce").fillna(0)
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"])
    logs = logs[logs["MIN"] > 0].sort_values(["PLAYER_ID", "GAME_DATE"])

    # Per-minute rates
    for stat in ["PTS", "REB", "AST", "FG3M"]:
        logs[f"{stat}_per_min"] = logs[stat] / logs["MIN"]

    def _rolling(g):
        g = g.copy()
        # Minutes
        g["min_L3"] = g["MIN"].rolling(3, min_periods=2).mean().shift(1)
        g["min_L5"] = g["MIN"].rolling(5, min_periods=3).mean().shift(1)
        g["min_szn"] = g["MIN"].expanding(min_periods=3).mean().shift(1)
        g["proj_min"] = np.where(
            g["min_L3"].notna(),
            0.5 * g["min_L3"] + 0.3 * g["min_L5"].fillna(g["min_szn"]) + 0.2 * g["min_szn"],
            g["min_szn"]
        )
        g["proj_min"] = pd.Series(g["proj_min"], index=g.index).fillna(20)

        for stat in ["PTS", "REB", "AST", "FG3M"]:
            rpm = f"{stat}_per_min"
            g[f"{rpm}_L5"] = g[rpm].rolling(5, min_periods=3).mean().shift(1)
            g[f"{rpm}_L10"] = g[rpm].rolling(10, min_periods=5).mean().shift(1)
            g[f"{rpm}_szn"] = g[rpm].expanding(min_periods=3).mean().shift(1)

            l10_fill = g[f"{rpm}_L10"].fillna(g[f"{rpm}_szn"])
            g[f"proj_{rpm}"] = np.where(
                g[f"{rpm}_L5"].notna(),
                0.5 * g[f"{rpm}_L5"] + 0.3 * l10_fill + 0.2 * g[f"{rpm}_szn"],
                g[f"{rpm}_szn"]
            )
            g[f"proj_{rpm}"] = pd.Series(g[f"proj_{rpm}"], index=g.index).fillna(0)

            # Rolling std for distribution
            g[f"{stat}_std"] = g[stat].rolling(10, min_periods=5).std().shift(1)
            g[f"{stat}_std"] = g[f"{stat}_std"].fillna(g[stat].expanding(min_periods=3).std().shift(1))

        return g

    logs = logs.groupby(["PLAYER_ID", "season"], group_keys=False).apply(_rolling)

    # Final projections: proj_POINTS, proj_REBOUNDS, etc.
    for prop_label, stat_col in STAT_COL.items():
        logs[f"proj_{prop_label}"] = logs["proj_min"] * logs[f"proj_{stat_col}_per_min"]
        logs[f"proj_{prop_label}"] = logs[f"proj_{prop_label}"].clip(0, 60 if prop_label == "POINTS" else 20)
        # Also rename std columns
        logs[f"{prop_label}_std"] = logs[f"{stat_col}_std"]

    print(f"  Projections: {len(logs):,} player-games")
    return logs


# ══════════════════════════════════════════════════════════════
# DISTRIBUTIONS
# ══════════════════════════════════════════════════════════════

def prob_over_normal(mean, std, line):
    if pd.isna(mean) or pd.isna(std) or std <= 0:
        return np.nan
    return 1 - scipy_stats.norm.cdf(line + 0.5, loc=mean, scale=std)  # continuity correction

def prob_under_normal(mean, std, line):
    if pd.isna(mean) or pd.isna(std) or std <= 0:
        return np.nan
    return scipy_stats.norm.cdf(line - 0.5, loc=mean, scale=std)

def prob_over_poisson(lam, line):
    if pd.isna(lam) or lam <= 0:
        return np.nan
    threshold = int(np.floor(line)) + 1
    return 1 - scipy_stats.poisson.cdf(threshold - 1, lam)

def prob_under_poisson(lam, line):
    if pd.isna(lam) or lam <= 0:
        return np.nan
    threshold = int(np.floor(line))
    return scipy_stats.poisson.cdf(threshold, lam)


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    out = []
    def log(s=""):
        out.append(s)
        print(s)

    log("=" * 65)
    log("NBA PROPS PHASE P3 — BASELINE MODEL BUILD")
    log("=" * 65)
    log()

    mv = rebuild_market_view()
    log()

    # Check odds coverage
    has_odds = mv["consensus_over_odds"].notna() & mv["consensus_under_odds"].notna()
    pct = has_odds.mean() * 100
    log(f"Odds coverage: {pct:.1f}%")
    if pct < 80:
        log(f"STOPPING: {pct:.1f}% < 80%")
        with open(OUT_DIR / "p3_summary.txt", "w") as f:
            f.write("\n".join(out))
        return
    log()

    projections = build_projections()
    log()

    # ── Join projections to market view ──
    log("Joining projections to market...")

    # Build lookup: latest projection per player before each game
    # Use GAME_ID from logs to join with event_id from market view
    # But IDs don't match directly — join via player_id + game_date
    proj_lookup = projections[["PLAYER_ID", "GAME_DATE", "season",
                                "proj_min",
                                "proj_POINTS", "proj_REBOUNDS", "proj_ASSISTS", "proj_THREES",
                                "POINTS_std", "REBOUNDS_std", "ASSISTS_std", "THREES_std",
                                "PTS", "REB", "AST", "FG3M", "MIN"]].copy()
    proj_lookup = proj_lookup.rename(columns={"PLAYER_ID": "player_id", "GAME_DATE": "game_date"})
    proj_lookup["game_date"] = proj_lookup["game_date"].dt.strftime("%Y-%m-%d")
    proj_lookup["player_id"] = proj_lookup["player_id"].astype(float)

    mv["player_id"] = mv["player_id"].astype(float)

    joined = mv[has_odds].merge(proj_lookup, on=["player_id", "game_date"], how="inner",
                                  suffixes=("", "_proj"))

    log(f"  Joined: {len(joined):,} rows (from {has_odds.sum():,} with odds)")
    log()

    # ── Compute distributions and edges ──
    log("Computing distributions and edges...")

    all_plays = []
    prop_proj_map = {"POINTS": "proj_POINTS", "REBOUNDS": "proj_REBOUNDS",
                      "ASSISTS": "proj_ASSISTS", "THREES": "proj_THREES"}
    prop_std_map = {"POINTS": "POINTS_std", "REBOUNDS": "REBOUNDS_std",
                     "ASSISTS": "ASSISTS_std", "THREES": "THREES_std"}
    prop_actual_map = {"POINTS": "PTS", "REBOUNDS": "REB",
                        "ASSISTS": "AST", "THREES": "FG3M"}

    for _, row in joined.iterrows():
        pt = row["prop_type"]
        proj = row.get(prop_proj_map.get(pt, ""), np.nan)
        std = row.get(prop_std_map.get(pt, ""), np.nan)
        line = row["consensus_line"]

        if pd.isna(proj):
            continue

        # Enforce minimum std
        if pd.isna(std) or std < MIN_STD.get(pt, 1.0):
            std = MIN_STD.get(pt, 1.0)

        # Distribution
        if pt == "THREES":
            p_over = prob_over_poisson(proj, line)
            p_under = prob_under_poisson(proj, line)
        else:
            p_over = prob_over_normal(proj, std, line)
            p_under = prob_under_normal(proj, std, line)

        if pd.isna(p_over) or pd.isna(p_under):
            continue

        # Devig
        imp_over, imp_under = devig(row["consensus_over_odds"], row["consensus_under_odds"])
        if pd.isna(imp_over):
            continue

        edge_over = p_over - imp_over
        edge_under = p_under - imp_under

        lean = "OVER" if edge_over > edge_under and edge_over > 0 else \
               "UNDER" if edge_under > 0 else "NO_PLAY"
        edge = edge_over if lean == "OVER" else edge_under if lean == "UNDER" else 0

        abs_e = abs(edge)
        bucket = "5%+" if abs_e >= 0.05 else "2-5%" if abs_e >= 0.02 else "0-2%"

        # Actual from market view (already joined)
        actual = row.get("actual_value", np.nan)

        # Bet outcome
        if lean == "OVER" and not pd.isna(actual):
            win = 1.0 if actual > line else 0.0
        elif lean == "UNDER" and not pd.isna(actual):
            win = 1.0 if actual < line else 0.0
        else:
            win = np.nan

        all_plays.append({
            "prop_type": pt, "player_name": row["player_name"],
            "player_id": row["player_id"],
            "game_date": row["game_date"], "season": row["season"],
            "dataset_split": row["dataset_split"],
            "line": line, "projection": round(proj, 2),
            "model_prob_over": round(p_over, 4),
            "model_prob_under": round(p_under, 4),
            "implied_prob_over": round(imp_over, 4),
            "implied_prob_under": round(imp_under, 4),
            "edge_over": round(edge_over, 4),
            "edge_under": round(edge_under, 4),
            "lean": lean, "edge": round(edge, 4),
            "edge_bucket": bucket,
            "actual_value": actual,
            "bet_win": win,
            "n_books": row["n_books"],
            "book": row.get("best_over_book", "") if lean == "OVER" else row.get("best_under_book", ""),
        })

    plays = pd.DataFrame(all_plays)
    plays.to_parquet(OUT_DIR / "backtest_results.parquet", index=False)
    plays.to_csv(OUT_DIR / "backtest_results.csv", index=False)

    log(f"  Total plays: {len(plays):,}")
    log(f"  With outcomes: {plays['bet_win'].notna().sum():,}")
    log()

    # ══════════════════════════════════════════════════════════
    # REPORTING
    # ══════════════════════════════════════════════════════════

    for split_label, split_val in [("VALIDATION (2024-25)", "VALIDATION"),
                                     ("OOS (2025-26)", "OOS")]:
        v = plays[(plays["dataset_split"] == split_val) &
                   (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]

        log("=" * 65)
        log(f"SECTION — {split_label}")
        log("=" * 65)
        log()

        if len(v) == 0:
            log("  No plays.")
            continue

        # By prop type
        log("BY PROP TYPE:")
        log(f"  {'Type':<10s} {'N':>6s} {'Hit%':>7s} {'ROI':>8s} {'AvgEdge':>8s}")
        log(f"  {'-'*42}")
        for pt in ["POINTS", "REBOUNDS", "ASSISTS", "THREES"]:
            sub = v[v["prop_type"] == pt]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {pt:<10s} {n:>6d} {w/n*100:>6.1f}% {roi_110(w,n):>+7.1f}% {sub['edge'].mean():>+7.1%}")
        # Total
        w = v["bet_win"].sum(); n = len(v)
        log(f"  {'TOTAL':<10s} {n:>6d} {w/n*100:>6.1f}% {roi_110(w,n):>+7.1f}% {v['edge'].mean():>+7.1%}")
        log()

        # OVER vs UNDER
        log("BY DIRECTION:")
        for d in ["OVER", "UNDER"]:
            sub = v[v["lean"] == d]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {d}: N={n:,}, hit={w/n*100:.1f}%, ROI={roi_110(w,n):+.1f}%")
        log()

        # By prop × direction
        log("BY PROP × DIRECTION:")
        for pt in ["POINTS", "REBOUNDS", "ASSISTS", "THREES"]:
            for d in ["OVER", "UNDER"]:
                sub = v[(v["prop_type"] == pt) & (v["lean"] == d)]
                if len(sub) < 10: continue
                w = sub["bet_win"].sum(); n = len(sub)
                log(f"  {pt} {d}: N={n:,}, hit={w/n*100:.1f}%, ROI={roi_110(w,n):+.1f}%")
        log()

        # Edge buckets
        log("BY EDGE BUCKET:")
        log(f"  {'Bucket':<8s} {'N':>6s} {'Hit%':>7s} {'ROI':>8s}")
        log(f"  {'-'*30}")
        for bucket in ["0-2%", "2-5%", "5%+"]:
            sub = v[v["edge_bucket"] == bucket]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {bucket:<8s} {n:>6d} {w/n*100:>6.1f}% {roi_110(w,n):>+7.1f}%")
        log()

        # Calibration
        log("CALIBRATION (model P(over) vs actual over rate):")
        log(f"  {'Bucket':<10s} {'N':>6s} {'Model':>7s} {'Actual':>7s} {'Implied':>8s} {'Delta':>7s}")
        log(f"  {'-'*48}")
        for lo, hi, label in [(0, 0.45, "<45%"), (0.45, 0.50, "45-50%"),
                               (0.50, 0.55, "50-55%"), (0.55, 0.60, "55-60%"),
                               (0.60, 0.65, "60-65%"), (0.65, 1.01, "65%+")]:
            mask = (v["model_prob_over"] >= lo) & (v["model_prob_over"] < hi)
            sub = v[mask]
            if len(sub) < 20: continue
            mp = sub["model_prob_over"].mean()
            actual_over = (sub["actual_value"] > sub["line"]).mean()
            ip = sub["implied_prob_over"].mean()
            delta = actual_over - mp
            flag = " ⚠" if abs(delta) > 0.10 else ""
            log(f"  {label:<10s} {len(sub):>6d} {mp:>6.1%} {actual_over:>6.1%} {ip:>7.1%} {delta:>+6.1%}{flag}")
        log()

        # Summary metrics
        log("SUMMARY METRICS:")
        log(f"  Avg model_prob (lean dir): {np.where(v['lean']=='OVER', v['model_prob_over'], v['model_prob_under']).mean():.1%}")
        log(f"  Avg implied_prob:          {np.where(v['lean']=='OVER', v['implied_prob_over'], v['implied_prob_under']).mean():.1%}")
        log(f"  Avg edge:                  {v['edge'].mean():+.1%}")
        log()

    # ── RECOMMENDATION ──
    log("=" * 65)
    log("PRODUCTION RECOMMENDATION")
    log("=" * 65)
    log()

    val = plays[(plays["dataset_split"] == "VALIDATION") &
                 (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]
    oos = plays[(plays["dataset_split"] == "OOS") &
                 (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]

    for pt in ["POINTS", "REBOUNDS", "ASSISTS", "THREES"]:
        sv = val[val["prop_type"] == pt]
        so = oos[oos["prop_type"] == pt]
        if len(sv) < 50:
            log(f"  {pt}: SKIPPED (N={len(sv)})")
            continue

        w = sv["bet_win"].sum(); n = len(sv)
        val_roi = roi_110(w, n)
        n_ok = n >= 200
        roi_ok = val_roi >= 2.0

        # Monotonicity
        prev = -999; mono = True
        for bucket in ["0-2%", "2-5%", "5%+"]:
            b = sv[sv["edge_bucket"] == bucket]
            if len(b) > 10:
                r = roi_110(b["bet_win"].sum(), len(b))
                if not pd.isna(r) and r < prev - 5: mono = False
                if not pd.isna(r): prev = r

        # OOS check
        oos_roi = np.nan
        if len(so) > 0:
            oos_roi = roi_110(so["bet_win"].sum(), len(so))
        oos_ok = oos_roi >= 0 if not pd.isna(oos_roi) else False

        if n_ok and roi_ok and mono and oos_ok:
            log(f"  {pt}: READY FOR SHADOW (val N={n}, ROI={val_roi:+.1f}%, OOS={oos_roi:+.1f}%)")
        elif n_ok and val_roi > 0:
            failed = []
            if not roi_ok: failed.append(f"ROI={val_roi:+.1f}%<2%")
            if not mono: failed.append("not monotonic")
            if not oos_ok: failed.append(f"OOS={oos_roi:+.1f}%<0%")
            log(f"  {pt}: NEAR-MISS ({', '.join(failed)})")
        else:
            log(f"  {pt}: NOT READY (N={n}, ROI={val_roi:+.1f}%)")
    log()

    # Save
    with open(OUT_DIR / "p3_summary.txt", "w") as f:
        f.write("\n".join(out))

    log("=" * 65)
    log("Files saved:")
    log(f"  nba/props/model_p3/backtest_results.parquet")
    log(f"  nba/props/model_p3/backtest_results.csv")
    log(f"  nba/props/model_p3/p3_summary.txt")
    log("=" * 65)


if __name__ == "__main__":
    main()
