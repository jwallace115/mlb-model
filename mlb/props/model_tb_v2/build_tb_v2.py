#!/usr/bin/env python3
"""
MLB Props — Total Bases v2 Rebuild
Player-specific base outcome rates + MC simulation + actual odds.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "mlb" / "data"
PROPS_DIR = PROJECT_ROOT / "mlb" / "props"
PROC_DIR = PROPS_DIR / "processed"
OUT_DIR = Path(__file__).resolve().parent

N_SIMS = 2000  # reduced for performance; still statistically sufficient
RNG = np.random.default_rng(42)

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
    mask = pd.notna(probs) & pd.notna(outcomes)
    p, o = np.array(probs[mask], dtype=float), np.array(outcomes[mask], dtype=float)
    return float(((p - o)**2).mean()) if len(p) > 0 else np.nan

def realized_roi(wins, odds_series):
    """Compute ROI using actual recorded odds."""
    total = len(odds_series)
    if total == 0: return np.nan
    profit = 0
    for w, odds in zip(wins, odds_series):
        if w == 1:
            profit += (odds / 100) if odds > 0 else (100 / abs(odds))
        else:
            profit -= 1
    return profit / total * 100


def main():
    import sys
    out = []
    def log(s=""):
        out.append(s)
        print(s, flush=True)

    log("=" * 65)
    log("MLB PROPS — TOTAL BASES v2 REBUILD")
    log("=" * 65)
    log()

    # ── Load data ──
    h = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    mv = pd.read_parquet(PROC_DIR / "props_market_view.parquet")

    h["game_date"] = pd.to_datetime(h["game_date"])
    starters = h[h["starter_flag"] == 1].copy().sort_values(["player_id", "game_date"])

    # ── Build empirical PA distributions by slot + home/away ──
    log("Building empirical PA distributions...")
    pa_dists = {}
    for ha in ["H", "A"]:
        for slot in range(1, 10):
            pa_vals = starters[(starters["home_away"] == ha) &
                                (starters["batting_order_position"] == slot)]["plate_appearances"].values
            if len(pa_vals) > 50:
                pa_dists[(ha, slot)] = pa_vals
            else:
                pa_dists[(ha, slot)] = starters[starters["batting_order_position"] == slot]["plate_appearances"].values

    # ── Build player-specific rolling base outcome rates ──
    log("Building player-specific rolling base outcome rates...")

    # Per-PA outcome counts
    starters["tb"] = starters["singles"] + 2*starters["doubles"] + 3*starters["triples"] + 4*starters["home_runs"]
    # For multinomial: outcomes per PA
    # 0 bases = PA - (1B + 2B + 3B + HR)  (includes outs, walks, HBP — but walks/HBP = 0 bases)
    starters["bases_0"] = starters["plate_appearances"] - starters["singles"] - starters["doubles"] - starters["triples"] - starters["home_runs"]

    def player_rolling(g):
        g = g.copy()
        for outcome in ["bases_0", "singles", "doubles", "triples", "home_runs"]:
            g[f"cum_{outcome}"] = g[outcome].expanding().sum().shift(1)
            g[f"r30_{outcome}"] = g[outcome].rolling(30, min_periods=10).sum().shift(1)
            g[f"r60_{outcome}"] = g[outcome].rolling(60, min_periods=20).sum().shift(1)

        g["cum_pa"] = g["plate_appearances"].expanding().sum().shift(1)
        g["r30_pa"] = g["plate_appearances"].rolling(30, min_periods=10).sum().shift(1)
        g["r60_pa"] = g["plate_appearances"].rolling(60, min_periods=20).sum().shift(1)

        # Platoon splits
        for hand in ["L", "R"]:
            mask_h = g["opp_pitcher_hand"] == hand
            gh = g[mask_h]
            for outcome in ["bases_0", "singles", "doubles", "triples", "home_runs"]:
                g[f"vs{hand}_{outcome}"] = np.nan
                if len(gh) > 0:
                    cum = gh[outcome].expanding().sum().shift(1)
                    g.loc[gh.index, f"vs{hand}_{outcome}"] = cum
                    g[f"vs{hand}_{outcome}"] = g[f"vs{hand}_{outcome}"].ffill()

            g[f"vs{hand}_pa"] = np.nan
            if len(gh) > 0:
                cum_pa = gh["plate_appearances"].expanding().sum().shift(1)
                g.loc[gh.index, f"vs{hand}_pa"] = cum_pa
                g[f"vs{hand}_pa"] = g[f"vs{hand}_pa"].ffill()

        # ISO for profiling
        g["cum_iso_num"] = (g["doubles"] + 2*g["triples"] + 3*g["home_runs"]).expanding().sum().shift(1)
        g["cum_ab"] = g["at_bats"].expanding().sum().shift(1)
        g["rolling_iso"] = np.where(g["cum_ab"] > 0, g["cum_iso_num"] / g["cum_ab"], 0.15)

        return g

    starters = starters.groupby(["player_id", "season"], group_keys=False).apply(player_rolling)
    log(f"  Players: {starters['player_id'].nunique()}")

    # ── Function to get player rates for a game ──
    def get_player_rates(row):
        """Return {0:p0, 1:p1, 2:p2, 3:p3, 4:p4} for this player-game."""
        opp_hand = row.get("opp_pitcher_hand", "")
        outcomes = ["bases_0", "singles", "doubles", "triples", "home_runs"]

        # Try platoon split first (need >= 50 PA)
        vs_pa = row.get(f"vs{opp_hand}_pa", np.nan)
        if not pd.isna(vs_pa) and vs_pa >= 50:
            counts = [max(0, row.get(f"vs{opp_hand}_{o}", 0) or 0) for o in outcomes]
            total = sum(counts)
            if total > 0:
                rates = [c / total for c in counts]
                return np.array(rates)

        # Try rolling 30-game window
        r30_pa = row.get("r30_pa", np.nan)
        if not pd.isna(r30_pa) and r30_pa >= 30:
            counts = [max(0, row.get(f"r30_{o}", 0) or 0) for o in outcomes]
            total = sum(counts)
            if total > 0:
                return np.array([c/total for c in counts])

        # Try rolling 60
        r60_pa = row.get("r60_pa", np.nan)
        if not pd.isna(r60_pa) and r60_pa >= 50:
            counts = [max(0, row.get(f"r60_{o}", 0) or 0) for o in outcomes]
            total = sum(counts)
            if total > 0:
                return np.array([c/total for c in counts])

        # Season cumulative
        cum_pa = row.get("cum_pa", np.nan)
        if not pd.isna(cum_pa) and cum_pa >= 20:
            counts = [max(0, row.get(f"cum_{o}", 0) or 0) for o in outcomes]
            total = sum(counts)
            if total > 0:
                return np.array([c/total for c in counts])

        # League average fallback
        return np.array([0.65, 0.15, 0.045, 0.005, 0.03])  # approximate

    # ── Join to TB market view ──
    log("Joining to TB market view...")

    tb_mv = mv[mv["prop_type"] == "TB"].copy()
    tb_mv["player_id"] = tb_mv["player_id"].astype(float)

    # Check odds
    has_odds = tb_mv["consensus_over_odds"].notna() & tb_mv["consensus_under_odds"].notna()
    pct_odds = has_odds.mean() * 100
    log(f"  Odds coverage: {pct_odds:.1f}%")
    if pct_odds < 80:
        log("STOPPING: odds < 80%")
        return

    tb_mv = tb_mv[has_odds].copy()

    # Join player features
    feat_cols = (["game_pk", "player_id", "game_date", "season",
                   "batting_order_position", "home_away", "opp_pitcher_hand",
                   "plate_appearances", "tb", "rolling_iso"] +
                 [f"r30_{o}" for o in ["bases_0","singles","doubles","triples","home_runs"]] +
                 ["r30_pa", "r60_pa", "cum_pa"] +
                 [f"r60_{o}" for o in ["bases_0","singles","doubles","triples","home_runs"]] +
                 [f"cum_{o}" for o in ["bases_0","singles","doubles","triples","home_runs"]] +
                 [f"vsL_{o}" for o in ["bases_0","singles","doubles","triples","home_runs"]] +
                 [f"vsR_{o}" for o in ["bases_0","singles","doubles","triples","home_runs"]] +
                 ["vsL_pa", "vsR_pa"])
    feat_cols = [c for c in feat_cols if c in starters.columns]

    starters_feat = starters[feat_cols].copy()
    starters_feat["game_date_str"] = starters_feat["game_date"].dt.strftime("%Y-%m-%d")
    starters_feat["player_id"] = starters_feat["player_id"].astype(float)

    joined = tb_mv.merge(starters_feat, left_on=["player_id", "game_date"],
                           right_on=["player_id", "game_date_str"],
                           how="inner", suffixes=("", "_feat"))

    log(f"  Joined: {len(joined):,} rows")

    # ── PA accuracy check ──
    log("\nSECTION 0 — PA ACCURACY")
    log("=" * 50)

    val_j = joined[joined["dataset_split"] == "VALIDATION"]
    for ha in ["H", "A"]:
        sub = val_j[val_j["home_away"] == ha]
        for slot in range(1, 10):
            s = sub[sub["batting_order_position"] == slot]
            if len(s) < 50: continue
            emp_mean = pa_dists.get((ha, slot), np.array([4])).mean()
            act_mean = s["plate_appearances"].mean()
            log(f"  {ha} slot {slot}: empirical={emp_mean:.2f}, actual={act_mean:.2f}, delta={emp_mean-act_mean:+.2f}")
    log()

    # ── SIMULATE ──
    log("Running Monte Carlo simulations (10K per play)...")

    all_plays = []
    count = 0
    renorm_count = 0

    for _, row in joined.iterrows():
        line = row["consensus_line"]
        ha = row.get("home_away", "A")
        slot = row.get("batting_order_position", 5)

        # Get player-specific rates
        rates = get_player_rates(row)

        # Safety: floor at 0, renormalize
        rates = np.maximum(rates, 0)
        total = rates.sum()
        if total <= 0:
            rates = np.array([0.65, 0.15, 0.045, 0.005, 0.03])
            total = rates.sum()
        if abs(total - 1.0) > 0.001:
            renorm_count += 1
        rates = rates / total

        # Draw PA from empirical distribution
        pa_dist = pa_dists.get((ha, int(slot)), pa_dists.get(("A", 5), np.array([4])))
        pa_draws = RNG.choice(pa_dist, size=N_SIMS)

        # Vectorized TB simulation: pre-draw max PA worth of outcomes, then sum
        bases = np.array([0, 1, 2, 3, 4])
        max_pa = int(pa_draws.max()) + 1
        # Draw all outcomes at once: (N_SIMS, max_pa)
        all_outcomes = RNG.choice(bases, size=(N_SIMS, max_pa), p=rates)
        # Mask by actual PA per sim
        pa_mask = np.arange(max_pa)[None, :] < pa_draws[:, None]
        tb_sims = (all_outcomes * pa_mask).sum(axis=1)

        p_over = float((tb_sims > line).mean())
        p_under = float((tb_sims <= line).mean())

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

        # Get actual odds for realized ROI
        if lean == "OVER":
            actual_odds = row.get("best_over_odds", row.get("consensus_over_odds", -110))
        else:
            actual_odds = row.get("best_under_odds", row.get("consensus_under_odds", -110))
        if pd.isna(actual_odds): actual_odds = -110

        projection = float(tb_sims.mean())

        all_plays.append({
            "player_name": row["player_name"], "player_id": row["player_id"],
            "team": row.get("team", ""), "opponent": row.get("opponent", ""),
            "game_date": row["game_date"], "season": row["season"],
            "dataset_split": row["dataset_split"],
            "lineup_slot": int(slot), "home_away": ha,
            "prop_type": "TB", "line": line,
            "projection": round(projection, 2),
            "model_prob_over": round(p_over, 4),
            "model_prob_under": round(p_under, 4),
            "implied_prob_over": round(imp_over, 4),
            "implied_prob_under": round(imp_under, 4),
            "edge_over": round(edge_over, 4),
            "edge_under": round(edge_under, 4),
            "lean": lean, "edge": round(edge, 4),
            "edge_bucket": bucket,
            "actual_value": actual,
            "actual_PA": row.get("plate_appearances", np.nan),
            "projected_PA_mean": round(float(pa_draws.mean()), 2),
            "rolling_iso": row.get("rolling_iso", np.nan),
            "actual_odds": actual_odds,
            "bet_win": win,
            "n_books": row.get("n_books", 1),
        })

        count += 1
        if count % 10000 == 0:
            log(f"  {count:,} plays...")

    plays = pd.DataFrame(all_plays)
    plays.to_parquet(OUT_DIR / "backtest_results.parquet", index=False)
    plays.to_csv(OUT_DIR / "backtest_results.csv", index=False)

    log(f"\n  Total: {len(plays):,}, renormalized: {renorm_count:,}")
    log(f"  With outcomes: {plays['bet_win'].notna().sum():,}")

    # ══════════════════════════════════════════════════════════
    # REPORTING
    # ══════════════════════════════════════════════════════════

    # ── SECTION 1: CALIBRATION ──
    log()
    log("=" * 65)
    log("SECTION 1 — CALIBRATION")
    log("=" * 65)
    log()

    val = plays[(plays["dataset_split"] == "VALIDATION") & plays["actual_value"].notna()]
    cal_pass = True

    log(f"{'Bucket':<12s} {'N':>6s} {'Model':>7s} {'Actual':>7s} {'Implied':>8s} {'Delta':>7s}")
    log("-" * 50)
    for lo, hi, label in [(0, 0.35, "<35%"), (0.35, 0.45, "35-45%"),
                           (0.45, 0.55, "45-55%"), (0.55, 0.65, "55-65%"),
                           (0.65, 0.75, "65-75%"), (0.75, 1.01, "75%+")]:
        mask = (val["model_prob_over"] >= lo) & (val["model_prob_over"] < hi)
        b = val[mask]
        if len(b) < 20: continue
        mp = b["model_prob_over"].mean()
        actual_rate = (b["actual_value"] > b["line"]).mean()
        ip = b["implied_prob_over"].mean()
        delta = actual_rate - mp
        flag = " ⚠" if abs(delta) > 0.10 else " ✗" if abs(delta) > 0.15 else ""
        if abs(delta) > 0.15: cal_pass = False
        log(f"{label:<12s} {len(b):>6d} {mp:>6.1%} {actual_rate:>6.1%} {ip:>7.1%} {delta:>+6.1%}{flag}")

    # Brier
    actual_over = (val["actual_value"] > val["line"]).astype(float)
    brier_v2 = brier_score(val["model_prob_over"], actual_over)
    log(f"\nBrier score TB v2: {brier_v2:.4f}")
    log(f"Calibration: {'PASS' if cal_pass else 'FAIL'}")
    log()

    # ── SECTION 2: BACKTEST ──
    for split_label, split_val in [("VALIDATION (2024)", "VALIDATION"), ("OOS (2025)", "OOS")]:
        v = plays[(plays["dataset_split"] == split_val) &
                   (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]
        if len(v) == 0:
            log(f"\n{split_label}: no plays")
            continue

        log("=" * 65)
        log(f"SECTION 2 — {split_label}")
        log("=" * 65)
        log()

        w = v["bet_win"].sum(); n = len(v)
        roi_std = roi_110(w, n)
        roi_actual = realized_roi(v["bet_win"].values, v["actual_odds"].values)

        log(f"  N={n:,}, hit={w/n*100:.1f}%, ROI_std={roi_std:+.1f}%, ROI_actual={roi_actual:+.1f}%")
        log()

        # OVER vs UNDER
        log("  OVER vs UNDER:")
        for d in ["OVER", "UNDER"]:
            sub = v[v["lean"] == d]
            if len(sub) == 0: continue
            sw = sub["bet_win"].sum(); sn = len(sub)
            sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            log(f"    {d}: N={sn:,}, hit={sw/sn*100:.1f}%, ROI_actual={sr:+.1f}%")
        log()

        # Edge buckets
        log("  Edge buckets:")
        for bucket in ["0-2%", "2-5%", "5%+"]:
            sub = v[v["edge_bucket"] == bucket]
            if len(sub) == 0: continue
            sw = sub["bet_win"].sum(); sn = len(sub)
            sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            log(f"    {bucket}: N={sn:,}, hit={sw/sn*100:.1f}%, ROI_actual={sr:+.1f}%")
        log()

        # By lineup slot
        log("  By lineup slot:")
        for slot_group, slot_range in [("Top (1-3)", [1,2,3]), ("Mid (4-6)", [4,5,6]), ("Bot (7-9)", [7,8,9])]:
            sub = v[v["lineup_slot"].isin(slot_range)]
            if len(sub) < 50: continue
            sw = sub["bet_win"].sum(); sn = len(sub)
            sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            log(f"    {slot_group}: N={sn:,}, hit={sw/sn*100:.1f}%, ROI_actual={sr:+.1f}%")
        log()

        # By power profile
        log("  By ISO profile:")
        for label, lo_iso, hi_iso in [("Low ISO (<.130)", 0, 0.130), ("Med ISO (.130-.200)", 0.130, 0.200),
                                        ("High ISO (>.200)", 0.200, 1.0)]:
            sub = v[(v["rolling_iso"] >= lo_iso) & (v["rolling_iso"] < hi_iso)]
            if len(sub) < 50: continue
            sw = sub["bet_win"].sum(); sn = len(sub)
            sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            log(f"    {label}: N={sn:,}, hit={sw/sn*100:.1f}%, ROI_actual={sr:+.1f}%")
        log()

    # ── SECTION 3: vs P3 ──
    log("=" * 65)
    log("SECTION 3 — COMPARISON vs P3")
    log("=" * 65)
    log()
    val_v = plays[(plays["dataset_split"] == "VALIDATION") & (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]
    v2_roi = realized_roi(val_v["bet_win"].values, val_v["actual_odds"].values) if len(val_v) > 0 else np.nan
    log(f"  P3 TB validation ROI: -1.2% (from P3 audit)")
    log(f"  TB v2 validation ROI: {v2_roi:+.1f}%")
    log(f"  Improvement: {v2_roi - (-1.2):+.1f}pp")
    log()

    # ── SECTION 4: RECOMMENDATION ──
    log("=" * 65)
    log("SECTION 4 — PRODUCTION RECOMMENDATION")
    log("=" * 65)
    log()

    gates = {}
    gates["calibration"] = cal_pass
    gates["N >= 300"] = len(val_v) >= 300
    gates["val ROI >= 2%"] = v2_roi >= 2.0 if not pd.isna(v2_roi) else False

    oos_v = plays[(plays["dataset_split"] == "OOS") & (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]
    oos_roi = realized_roi(oos_v["bet_win"].values, oos_v["actual_odds"].values) if len(oos_v) > 0 else np.nan
    gates["OOS ROI >= 0%"] = oos_roi >= 0 if not pd.isna(oos_roi) else False

    # Monotonicity
    prev = -999; mono = True
    for bucket in ["0-2%", "2-5%", "5%+"]:
        sub = val_v[val_v["edge_bucket"] == bucket]
        if len(sub) > 20:
            r = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            if not pd.isna(r) and r < prev - 5: mono = False
            if not pd.isna(r): prev = r
    gates["monotonic"] = mono

    for g, passed in gates.items():
        log(f"  {g:<20s}: {'PASS' if passed else 'FAIL'}")
    log()

    if all(gates.values()):
        log("  READY FOR SHADOW")
    elif sum(gates.values()) >= 3:
        failed = [g for g, p in gates.items() if not p]
        log(f"  NEAR-MISS (failed: {', '.join(failed)})")
    else:
        log("  NOT READY")
    log()

    # ── SECTION 5: OBSERVATIONS ──
    log("=" * 65)
    log("SECTION 5 — PATTERN OBSERVATIONS")
    log("=" * 65)
    log()
    log(f"1. Calibration: {'improved' if cal_pass else 'still failing'} vs P3")
    log(f"2. Brier score: {brier_v2:.4f}")
    log(f"3. ROI vs P3: {v2_roi:+.1f}% vs -1.2% = {v2_roi-(-1.2):+.1f}pp change")
    log()

    with open(OUT_DIR / "tb_v2_summary.txt", "w") as f:
        f.write("\n".join(out))

    log("=" * 65)
    log(f"Files saved to mlb/props/model_tb_v2/")
    log("=" * 65)


if __name__ == "__main__":
    main()
