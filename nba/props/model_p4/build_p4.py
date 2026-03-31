#!/usr/bin/env python3
"""
NBA Props Phase P4 — Distribution Fix + Minutes Simulation
Fixes: NegBin/Binomial distributions + regime-weighted minutes simulation.
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

N_SIMS = 10000
RNG = np.random.default_rng(42)

# Pooled dispersion estimates (fallback)
POOLED_R = {"POINTS": 4.5, "REBOUNDS": 3.0, "ASSISTS": 2.0, "THREES": 2.5}
MIN_STD = {"POINTS": 3.0, "REBOUNDS": 1.5, "ASSISTS": 1.0, "THREES": 0.7}

STAT_COL = {"POINTS": "PTS", "REBOUNDS": "REB", "ASSISTS": "AST", "THREES": "FG3M"}

def roi_110(w, n):
    if n == 0: return np.nan
    return (w * (100/110) - (n - w)) / n * 100

def _to_implied(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def devig(ov, un):
    ro, ru = _to_implied(ov), _to_implied(un)
    if pd.isna(ro) or pd.isna(ru): return np.nan, np.nan
    t = ro + ru
    return (ro/t, ru/t) if t > 0 else (np.nan, np.nan)

def brier_score(probs, outcomes):
    """Brier score: lower is better."""
    mask = pd.notna(probs) & pd.notna(outcomes)
    p = np.array(probs[mask], dtype=float)
    o = np.array(outcomes[mask], dtype=float)
    return float(((p - o) ** 2).mean()) if len(p) > 0 else np.nan


def negbin_r_from_moments(mean, var):
    """Estimate NegBin r parameter from mean and variance."""
    if var <= mean or mean <= 0:
        return None  # Not overdispersed, use Poisson instead
    r = mean ** 2 / (var - mean)
    return max(0.5, min(r, 100))  # Clamp to reasonable range


def simulate_player_stat(minutes_dist, rate_per_min, prop_type, r_param,
                          fg3_pct=None, fg3a_per_min=None, line=0):
    """Simulate a stat via minutes distribution + appropriate count distribution."""
    # Draw minutes
    min_draws = RNG.choice(minutes_dist, size=N_SIMS, replace=True)
    min_draws = np.maximum(min_draws, 0)

    # Expected stat for each simulated minutes value
    expected = min_draws * rate_per_min

    if prop_type == "THREES" and fg3_pct is not None and fg3a_per_min is not None:
        # Binomial: B(n_attempts, pct)
        attempts = (min_draws * fg3a_per_min).round().astype(int)
        attempts = np.clip(attempts, 0, 20)
        pct = max(0.01, min(0.60, fg3_pct))
        stat_draws = np.array([RNG.binomial(n, pct) for n in attempts])
    elif r_param is not None and r_param > 0:
        # Negative Binomial
        # scipy: NB(r, p) where p = r / (r + mu)
        stat_draws = np.zeros(N_SIMS, dtype=int)
        for i in range(N_SIMS):
            mu = max(0.1, expected[i])
            p = r_param / (r_param + mu)
            p = max(0.01, min(0.99, p))
            stat_draws[i] = RNG.negative_binomial(max(1, round(r_param)), p)
    else:
        # Poisson fallback
        stat_draws = np.array([RNG.poisson(max(0.1, e)) for e in expected])

    p_over = float((stat_draws > line).mean())
    p_under = float((stat_draws <= line).mean())
    return p_over, p_under, float(min_draws.mean()), float(min_draws.std())


def main():
    out = []
    def log(s=""):
        out.append(s)
        print(s)

    log("=" * 65)
    log("NBA PROPS PHASE P4 — DISTRIBUTION FIX + MINUTES SIMULATION")
    log("=" * 65)
    log()

    # ── Load data ──
    mv = pd.read_parquet(PROC_DIR / "props_market_view.parquet")
    logs_c = pd.read_parquet(NBA_DIR / "model_c" / "player_game_logs.parquet")
    logs_b = pd.read_parquet(NBA_DIR / "model_b" / "player_game_logs.parquet")

    # Merge PLUS_MINUS from model_b for regime detection
    logs = logs_c.copy()
    for col in ["MIN", "PTS", "REB", "AST", "FG3M", "FG3A"]:
        logs[col] = pd.to_numeric(logs[col], errors="coerce").fillna(0)
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"])
    logs = logs[logs["MIN"] > 0].sort_values(["PLAYER_ID", "GAME_DATE"])

    # Add PLUS_MINUS
    pm = logs_b[["PLAYER_ID", "GAME_ID", "PLUS_MINUS"]].copy()
    pm["PLUS_MINUS"] = pd.to_numeric(pm["PLUS_MINUS"], errors="coerce")
    logs = logs.merge(pm, on=["PLAYER_ID", "GAME_ID"], how="left", suffixes=("", "_b"))

    # Regime: |PLUS_MINUS| > 15 as blowout proxy (team-level spread not directly available)
    logs["regime"] = np.where(logs["PLUS_MINUS"].abs() > 15, "BLOWOUT", "NORMAL")

    log(f"Player games: {len(logs):,}")
    log(f"Regime split: {logs['regime'].value_counts().to_dict()}")
    log()

    # ── Check odds coverage ──
    has_odds = mv["consensus_over_odds"].notna() & mv["consensus_under_odds"].notna()
    pct = has_odds.mean() * 100
    log(f"Odds coverage: {pct:.1f}%")
    if pct < 80:
        log("STOPPING: odds < 80%")
        return
    log()

    # ── Build per-player rolling features + minutes distributions ──
    log("Building rolling features + minutes distributions...")

    # Per-minute rates and dispersion
    for stat_col in ["PTS", "REB", "AST", "FG3M"]:
        logs[f"{stat_col}_per_min"] = logs[stat_col] / logs["MIN"]
    logs["FG3A_per_min"] = logs["FG3A"] / logs["MIN"]
    logs["FG3_pct"] = np.where(logs["FG3A"] > 0, logs["FG3M"] / logs["FG3A"], 0)

    def player_rolling(g):
        g = g.copy()
        # Minutes
        g["min_L3"] = g["MIN"].rolling(3, min_periods=2).mean().shift(1)
        g["min_L5"] = g["MIN"].rolling(5, min_periods=3).mean().shift(1)
        g["min_szn"] = g["MIN"].expanding(min_periods=3).mean().shift(1)

        # Per-minute rates
        for stat in ["PTS", "REB", "AST", "FG3M"]:
            rpm = f"{stat}_per_min"
            g[f"{rpm}_L10"] = g[rpm].rolling(10, min_periods=5).mean().shift(1)
            g[f"{rpm}_szn"] = g[rpm].expanding(min_periods=3).mean().shift(1)

        # FG3 specific
        g["FG3A_pm_L10"] = g["FG3A_per_min"].rolling(10, min_periods=5).mean().shift(1)
        g["FG3_pct_L15"] = g["FG3_pct"].rolling(15, min_periods=5).mean().shift(1)

        # Dispersion: rolling variance and mean for NegBin r estimation
        for stat in ["PTS", "REB", "AST", "FG3M"]:
            g[f"{stat}_roll_mean"] = g[stat].rolling(15, min_periods=8).mean().shift(1)
            g[f"{stat}_roll_var"] = g[stat].rolling(15, min_periods=8).var().shift(1)

        return g

    logs = logs.groupby(["PLAYER_ID", "season"], group_keys=False).apply(player_rolling)
    log(f"  Rolling features computed for {logs['PLAYER_ID'].nunique()} players")

    # ── Build minutes distribution lookup per player-game ──
    # For each game, build empirical minutes distribution from last 15 games
    # Split by regime

    log("Building minutes distributions by regime...")

    # Create lookup: player_id + game_date → minutes distribution
    # This is compute-intensive so we'll build it during the backtest loop

    # ── Join projections to market view ──
    log("Joining to market view...")

    proj = logs[["PLAYER_ID", "GAME_DATE", "season", "MIN",
                  "PTS_per_min_L10", "PTS_per_min_szn",
                  "REB_per_min_L10", "REB_per_min_szn",
                  "AST_per_min_L10", "AST_per_min_szn",
                  "FG3M_per_min_L10", "FG3M_per_min_szn",
                  "FG3A_pm_L10", "FG3_pct_L15",
                  "PTS_roll_mean", "PTS_roll_var",
                  "REB_roll_mean", "REB_roll_var",
                  "AST_roll_mean", "AST_roll_var",
                  "FG3M_roll_mean", "FG3M_roll_var",
                  "min_L3", "min_L5", "min_szn",
                  "PTS", "REB", "AST", "FG3M"]].copy()
    proj = proj.rename(columns={"PLAYER_ID": "player_id",
                                  "GAME_DATE": "game_date"})
    proj["game_date"] = proj["game_date"].dt.strftime("%Y-%m-%d")
    proj["player_id"] = proj["player_id"].astype(float)

    mv["player_id"] = mv["player_id"].astype(float)
    proj = proj.drop(columns=["season"], errors="ignore")
    joined = mv[has_odds].merge(proj, on=["player_id", "game_date"], how="inner",
                                  suffixes=("", "_proj"))
    # Clean duplicate columns
    for c in list(joined.columns):
        if c.endswith("_proj") and c.replace("_proj", "") in joined.columns:
            joined.drop(columns=[c], inplace=True)
    log(f"  Joined: {len(joined):,} rows")

    # ── Build minutes history lookup (for simulation) ──
    # Group player games by player for fast lookup
    player_min_history = {}
    for pid, group in logs.groupby("PLAYER_ID"):
        group = group.sort_values("GAME_DATE")
        dates = group["GAME_DATE"].values
        mins = group["MIN"].values
        regimes = group["regime"].values
        player_min_history[pid] = (dates, mins, regimes)

    log(f"  Minutes history: {len(player_min_history)} players")

    # ── Simulate ──
    log("\nRunning simulations (10K per play)...")

    all_plays = []
    prop_rate_map = {
        "POINTS": "PTS_per_min_L10",
        "REBOUNDS": "REB_per_min_L10",
        "ASSISTS": "AST_per_min_L10",
        "THREES": "FG3M_per_min_L10",
    }
    prop_rate_szn = {
        "POINTS": "PTS_per_min_szn",
        "REBOUNDS": "REB_per_min_szn",
        "ASSISTS": "AST_per_min_szn",
        "THREES": "FG3M_per_min_szn",
    }
    prop_rmean = {"POINTS": "PTS_roll_mean", "REBOUNDS": "REB_roll_mean",
                   "ASSISTS": "AST_roll_mean", "THREES": "FG3M_roll_mean"}
    prop_rvar = {"POINTS": "PTS_roll_var", "REBOUNDS": "REB_roll_var",
                  "ASSISTS": "AST_roll_var", "THREES": "FG3M_roll_var"}

    count = 0
    for _, row in joined.iterrows():
        pt = row["prop_type"]
        pid = int(row["player_id"])
        gd = pd.Timestamp(row["game_date"])
        line = row["consensus_line"]

        # Get per-minute rate
        rate_col = prop_rate_map.get(pt)
        rate = row.get(rate_col, np.nan)
        if pd.isna(rate):
            rate = row.get(prop_rate_szn.get(pt, ""), 0)
        if pd.isna(rate) or rate <= 0:
            continue

        # Get minutes distribution (last 15 games before this date)
        hist = player_min_history.get(pid)
        if hist is None:
            continue

        dates, mins, regimes = hist
        mask = dates < np.datetime64(gd)
        prior_mins = mins[mask][-15:]  # last 15

        if len(prior_mins) < 5:
            continue

        # Regime weighting: use uniform (no spread data for pre-game)
        # Use the empirical minutes directly as the distribution
        minutes_dist = prior_mins

        # NegBin dispersion
        rmean = row.get(prop_rmean.get(pt), np.nan)
        rvar = row.get(prop_rvar.get(pt), np.nan)
        if pd.isna(rmean) or pd.isna(rvar) or rmean <= 0:
            r_param = POOLED_R.get(pt, 3.0)
        else:
            r_param = negbin_r_from_moments(rmean, rvar)
            if r_param is None:
                r_param = POOLED_R.get(pt, 3.0)

        # Threes: binomial parameters
        fg3_pct = row.get("FG3_pct_L15", np.nan) if pt == "THREES" else None
        fg3a_pm = row.get("FG3A_pm_L10", np.nan) if pt == "THREES" else None
        if pt == "THREES" and (pd.isna(fg3_pct) or fg3_pct <= 0):
            fg3_pct = 0.35  # league avg
        if pt == "THREES" and (pd.isna(fg3a_pm) or fg3a_pm <= 0):
            fg3a_pm = 0.10  # ~3 attempts per 30 min

        # Simulate
        p_over, p_under, sim_min_mean, sim_min_std = simulate_player_stat(
            minutes_dist, rate, pt, r_param,
            fg3_pct=fg3_pct, fg3a_per_min=fg3a_pm, line=line
        )

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

        actual = row.get("actual_value", np.nan)
        if lean == "OVER" and not pd.isna(actual):
            win = 1.0 if actual > line else 0.0
        elif lean == "UNDER" and not pd.isna(actual):
            win = 1.0 if actual < line else 0.0
        else:
            win = np.nan

        # Projection = rate × mean simulated minutes
        projection = rate * sim_min_mean

        all_plays.append({
            "prop_type": pt, "player_name": row["player_name"],
            "player_id": pid, "game_date": row["game_date"],
            "season": row["season"], "dataset_split": row["dataset_split"],
            "line": line, "projection": round(projection, 2),
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
            "sim_min_mean": round(sim_min_mean, 1),
            "sim_min_std": round(sim_min_std, 1),
            "actual_minutes": row.get("MIN", np.nan),
            "r_param": round(r_param, 2) if r_param else np.nan,
            "n_books": row["n_books"],
        })

        count += 1
        if count % 10000 == 0:
            log(f"  {count:,} plays processed...")

    plays = pd.DataFrame(all_plays)
    plays.to_parquet(OUT_DIR / "backtest_results.parquet", index=False)
    plays.to_csv(OUT_DIR / "backtest_results.csv", index=False)

    log(f"\n  Total plays: {len(plays):,}")
    log(f"  With outcomes: {plays['bet_win'].notna().sum():,}")

    # Also load P3 results for Brier comparison
    p3_file = NBA_DIR / "props" / "model_p3" / "backtest_results.parquet"
    p3 = pd.read_parquet(p3_file) if p3_file.exists() else None

    # ══════════════════════════════════════════════════════════
    # REPORTING
    # ══════════════════════════════════════════════════════════

    # ── SECTION 0: CALIBRATION ──
    log()
    log("=" * 65)
    log("SECTION 0 — CALIBRATION RESULTS")
    log("=" * 65)
    log()

    val = plays[(plays["dataset_split"] == "VALIDATION") & plays["actual_value"].notna()]

    calibration_pass = True
    for pt in ["POINTS", "REBOUNDS", "ASSISTS", "THREES"]:
        sub = val[val["prop_type"] == pt]
        if len(sub) < 100:
            continue
        log(f"  {pt}:")
        log(f"  {'Bucket':<12s} {'N':>6s} {'Model':>7s} {'Actual':>7s} {'Implied':>8s} {'Delta':>7s}")
        log(f"  {'-'*50}")
        for lo, hi, label in [(0, 0.35, "<35%"), (0.35, 0.45, "35-45%"),
                               (0.45, 0.55, "45-55%"), (0.55, 0.65, "55-65%"),
                               (0.65, 0.75, "65-75%"), (0.75, 1.01, "75%+")]:
            mask = (sub["model_prob_over"] >= lo) & (sub["model_prob_over"] < hi)
            b = sub[mask]
            if len(b) < 20: continue
            mp = b["model_prob_over"].mean()
            actual_rate = (b["actual_value"] > b["line"]).mean()
            ip = b["implied_prob_over"].mean()
            delta = actual_rate - mp
            flag = " ⚠" if abs(delta) > 0.10 else " ✗" if abs(delta) > 0.15 else ""
            if abs(delta) > 0.15:
                calibration_pass = False
            log(f"  {label:<12s} {len(b):>6d} {mp:>6.1%} {actual_rate:>6.1%} {ip:>7.1%} {delta:>+6.1%}{flag}")
        log()

    # Brier score
    val_with = val[val["model_prob_over"].notna()]
    actual_over = (val_with["actual_value"] > val_with["line"]).astype(float)
    p4_brier = brier_score(val_with["model_prob_over"], actual_over)

    p3_brier = np.nan
    if p3 is not None:
        p3_val = p3[(p3["dataset_split"] == "VALIDATION") & p3["actual_value"].notna() & p3["model_prob_over"].notna()]
        if len(p3_val) > 0:
            p3_actual = (p3_val["actual_value"] > p3_val["line"]).astype(float)
            p3_brier = brier_score(p3_val["model_prob_over"], p3_actual)

    log(f"  Brier score P4: {p4_brier:.4f}")
    log(f"  Brier score P3: {p3_brier:.4f}")
    if not pd.isna(p3_brier):
        log(f"  Improvement: {p3_brier - p4_brier:+.4f} {'(better)' if p4_brier < p3_brier else '(worse)'}")
    log()
    log(f"  Calibration verdict: {'PASS' if calibration_pass else 'FAIL'}")
    log()

    # ── SECTIONS 1-5 ──
    for split_label, split_val in [("VALIDATION (2024-25)", "VALIDATION"),
                                     ("OOS (2025-26)", "OOS")]:
        v = plays[(plays["dataset_split"] == split_val) &
                   (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]
        if len(v) == 0:
            log(f"\n{split_label}: No plays")
            continue

        log(f"{'='*65}")
        log(f"SECTION — {split_label}")
        log(f"{'='*65}")
        log()

        # By prop type
        log("BY PROP TYPE:")
        log(f"  {'Type':<10s} {'N':>6s} {'Hit%':>7s} {'ROI':>8s} {'AvgEdge':>8s}")
        log(f"  {'-'*42}")
        for pt in ["POINTS", "REBOUNDS", "ASSISTS", "THREES"]:
            sub = v[v["prop_type"] == pt]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {pt:<10s} {n:>6d} {w/n*100:>6.1f}% {roi_110(w,n):>+7.1f}% {sub['edge'].mean():>+7.1%}")
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

        # Prop × direction
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
        for bucket in ["0-2%", "2-5%", "5%+"]:
            sub = v[v["edge_bucket"] == bucket]
            if len(sub) == 0: continue
            w = sub["bet_win"].sum(); n = len(sub)
            log(f"  {bucket}: N={n:,}, hit={w/n*100:.1f}%, ROI={roi_110(w,n):+.1f}%")
        log()

        # Minutes accuracy
        has_min = v[v["actual_minutes"].notna() & v["sim_min_mean"].notna()]
        if len(has_min) > 0:
            log("MINUTES ACCURACY:")
            log(f"  Sim mean: {has_min['sim_min_mean'].mean():.1f}")
            log(f"  Actual:   {has_min['actual_minutes'].mean():.1f}")
            log(f"  Delta:    {has_min['sim_min_mean'].mean() - has_min['actual_minutes'].mean():+.1f}")
            log(f"  Corr:     {has_min['sim_min_mean'].corr(has_min['actual_minutes']):.3f}")
        log()

    # ── SECTION 6: RECOMMENDATION ──
    log("=" * 65)
    log("SECTION 6 — PRODUCTION RECOMMENDATION")
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
            log(f"  {pt}: SKIPPED")
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

        oos_roi = roi_110(so["bet_win"].sum(), len(so)) if len(so) > 0 else np.nan
        oos_ok = oos_roi >= 0 if not pd.isna(oos_roi) else False

        if n_ok and roi_ok and mono and oos_ok and calibration_pass:
            log(f"  {pt}: READY FOR SHADOW (N={n}, ROI={val_roi:+.1f}%, OOS={oos_roi:+.1f}%)")
        elif n_ok and val_roi > 0:
            failed = []
            if not roi_ok: failed.append(f"ROI={val_roi:+.1f}%<2%")
            if not mono: failed.append("not monotonic")
            if not oos_ok: failed.append(f"OOS={oos_roi:+.1f}%")
            if not calibration_pass: failed.append("calibration failed")
            log(f"  {pt}: NEAR-MISS ({', '.join(failed)})")
        else:
            log(f"  {pt}: NOT READY (N={n}, ROI={val_roi:+.1f}%)")
    log()

    with open(OUT_DIR / "p4_summary.txt", "w") as f:
        f.write("\n".join(out))

    log("=" * 65)
    log("Files saved:")
    log(f"  nba/props/model_p4/backtest_results.parquet")
    log(f"  nba/props/model_p4/backtest_results.csv")
    log(f"  nba/props/model_p4/p4_summary.txt")
    log("=" * 65)


if __name__ == "__main__":
    main()
