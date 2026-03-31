#!/usr/bin/env python3
"""
NBA Props Phase P5 — Threes UNDER Segmentation Lab
Finds where the Threes UNDER signal is concentrated.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NBA_DIR = PROJECT_ROOT / "nba"
PROPS_DIR = NBA_DIR / "props"
PROC_DIR = PROPS_DIR / "processed"
OUT_DIR = Path(__file__).resolve().parent

def roi_110(w, n):
    if n == 0: return np.nan
    return (w * (100/110) - (n - w)) / n * 100

def _to_implied(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def break_even_rate(odds):
    """Break-even hit rate at given American odds."""
    imp = _to_implied(odds)
    return imp if not pd.isna(imp) else 0.5

def segment_stats(df, label=""):
    """Compute both Method A and Method B stats."""
    n = len(df)
    if n == 0:
        return {"label": label, "N": 0}
    w = df["bet_win"].sum()
    hr = w / n * 100
    roi_a = roi_110(w, n)

    # Method B: realized ROI from actual odds
    # For under bets, use the actual under odds
    has_odds = df["actual_under_odds"].notna()
    if has_odds.any():
        b_sub = df[has_odds]
        winnings = 0
        losses = 0
        for _, r in b_sub.iterrows():
            odds = r["actual_under_odds"]
            if r["bet_win"] == 1:
                if odds > 0:
                    winnings += odds / 100
                else:
                    winnings += 100 / abs(odds)
            else:
                losses += 1
        total_b = len(b_sub)
        roi_b = (winnings - losses) / total_b * 100 if total_b > 0 else np.nan
        avg_be = b_sub["actual_under_odds"].apply(break_even_rate).mean() * 100
    else:
        roi_b = roi_a  # fallback
        avg_be = 52.4  # standard -110

    return {
        "label": label, "N": n, "hit_rate": round(hr, 1),
        "roi_a": round(roi_a, 1), "roi_b": round(roi_b, 1),
        "be_rate": round(avg_be, 1),
    }


def gate_check(val_stats, oos_stats):
    """Check 4 validation gates. Returns label."""
    gates = 0
    if val_stats["N"] >= 200: gates += 1
    if val_stats["hit_rate"] >= 54.0: gates += 1
    if val_stats["roi_b"] >= 3.0: gates += 1
    if oos_stats and oos_stats.get("roi_b", -999) > 0: gates += 1
    elif oos_stats is None: pass  # can't check

    if val_stats["N"] < 100: return "THIN"
    if gates >= 4: return "PROMISING"
    if gates >= 3: return "NEAR-MISS"
    return "FAIL"


def main():
    out = []
    def log(s=""):
        out.append(s)
        print(s)

    log("=" * 65)
    log("NBA PROPS PHASE P5 — THREES UNDER SEGMENTATION LAB")
    log("=" * 65)
    log()

    # Load P4 backtest results
    bt = pd.read_parquet(NBA_DIR / "props" / "model_p4" / "backtest_results.parquet")

    # Load market view for odds and line dispersion
    mv = pd.read_parquet(PROC_DIR / "props_market_view.parquet")
    mv_threes = mv[mv["prop_type"] == "THREES"].copy()

    # Load player game logs for 3PA data
    logs = pd.read_parquet(NBA_DIR / "model_c" / "player_game_logs.parquet")
    logs["FG3A"] = pd.to_numeric(logs["FG3A"], errors="coerce").fillna(0)
    logs["MIN"] = pd.to_numeric(logs["MIN"], errors="coerce").fillna(0)
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"])
    logs = logs[logs["MIN"] > 0].sort_values(["PLAYER_ID", "GAME_DATE"])

    # Compute rolling 3PA per game
    logs["FG3A_per_game"] = logs.groupby(["PLAYER_ID", "season"])["FG3A"].transform(
        lambda x: x.rolling(10, min_periods=3).mean().shift(1))

    # Lookup: player_id + game_date → rolling 3PA
    fg3a_lookup = logs[["PLAYER_ID", "GAME_DATE", "FG3A_per_game"]].copy()
    fg3a_lookup["GAME_DATE"] = fg3a_lookup["GAME_DATE"].dt.strftime("%Y-%m-%d")
    fg3a_lookup = fg3a_lookup.rename(columns={"PLAYER_ID": "player_id", "GAME_DATE": "game_date"})

    # Base population: Threes UNDER
    tu = bt[(bt["prop_type"] == "THREES") & (bt["lean"] == "UNDER") & bt["bet_win"].notna()].copy()

    # Enrich with market view data
    tu["player_id"] = tu["player_id"].astype(float)
    mv_threes["player_id"] = mv_threes["player_id"].astype(float)
    tu = tu.merge(
        mv_threes[["player_id", "game_date", "best_under_odds", "best_under_line",
                     "best_under_book", "best_over_line", "line_std"]].drop_duplicates(
            subset=["player_id", "game_date"]),
        on=["player_id", "game_date"], how="left", suffixes=("", "_mv"))
    tu["actual_under_odds"] = tu.get("best_under_odds", tu.get("implied_prob_under"))

    # If best_under_odds missing, estimate from implied
    # Convert implied back to American for ROI calc
    def implied_to_american(p):
        if pd.isna(p) or p <= 0 or p >= 1: return np.nan
        if p >= 0.5:
            return -(p / (1 - p)) * 100
        else:
            return ((1 - p) / p) * 100

    mask_no_odds = tu["actual_under_odds"].isna()
    tu.loc[mask_no_odds, "actual_under_odds"] = tu.loc[mask_no_odds, "implied_prob_under"].apply(
        lambda p: implied_to_american(p) if not pd.isna(p) else -110)
    tu["actual_under_odds"] = tu["actual_under_odds"].fillna(-110)

    # Enrich with 3PA per game
    fg3a_lookup["player_id"] = fg3a_lookup["player_id"].astype(float)
    tu = tu.merge(fg3a_lookup, on=["player_id", "game_date"], how="left")

    # Line dispersion from MV
    tu["line_dispersion"] = tu.get("line_std", 0).fillna(0)
    # Also compute from best_over_line vs best_under_line
    if "best_over_line" in tu.columns and "best_under_line" in tu.columns:
        tu["line_range"] = (tu["best_under_line"] - tu["best_over_line"]).fillna(0)
    else:
        tu["line_range"] = 0

    val = tu[tu["dataset_split"] == "VALIDATION"]
    oos = tu[tu["dataset_split"] == "OOS"]

    # ── SECTION 0: BASE CONFIRMATION ──
    log("=" * 65)
    log("SECTION 0 — BASE POPULATION CONFIRMATION")
    log("=" * 65)
    log()
    for lbl, data in [("VALIDATION", val), ("OOS", oos)]:
        s = segment_stats(data, lbl)
        log(f"  {lbl}: N={s['N']}, hit={s['hit_rate']}%, ROI_A={s['roi_a']:+.1f}%, "
            f"ROI_B={s['roi_b']:+.1f}%, BE={s['be_rate']:.1f}%")
    log()

    # ── SEGMENT ANALYSIS ──
    all_segments = []

    def run_segment(name, condition_fn, labels):
        log(f"\n{'─'*50}")
        log(f"SEGMENT: {name}")
        log(f"{'─'*50}")
        log(f"{'Condition':<25s} {'Val N':>6s} {'Hit%':>6s} {'BE%':>5s} {'ROI_A':>7s} {'ROI_B':>7s} "
            f"{'OOS N':>6s} {'OOS Hit':>7s} {'OOS B':>7s} {'Label':<10s}")
        log("-" * 95)

        for label, cond in labels:
            v = val[condition_fn(val, label)]
            o = oos[condition_fn(oos, label)]
            vs = segment_stats(v, label)
            os_stats = segment_stats(o, label) if len(o) > 0 else None
            gate = gate_check(vs, os_stats)

            oos_hr = f"{os_stats['hit_rate']:.1f}%" if os_stats else "N/A"
            oos_rb = f"{os_stats['roi_b']:+.1f}%" if os_stats else "N/A"
            oos_n = os_stats["N"] if os_stats else 0

            log(f"{label:<25s} {vs['N']:>6d} {vs['hit_rate']:>5.1f}% {vs['be_rate']:>4.1f}% "
                f"{vs['roi_a']:>+6.1f}% {vs['roi_b']:>+6.1f}% "
                f"{oos_n:>6d} {oos_hr:>7s} {oos_rb:>7s} {gate:<10s}")

            all_segments.append({
                "segment": name, "condition": label, "gate": gate,
                "val_n": vs["N"], "val_hr": vs["hit_rate"], "val_roi_a": vs["roi_a"],
                "val_roi_b": vs["roi_b"], "val_be": vs["be_rate"],
                "oos_n": oos_n, "oos_hr": os_stats["hit_rate"] if os_stats else np.nan,
                "oos_roi_b": os_stats["roi_b"] if os_stats else np.nan,
            })

    # S1: Line band
    run_segment("S1 — LINE BAND",
        lambda df, l: df["line"] == float(l.split("=")[1]) if "=" in l else
                       (df["line"] <= 1.5 if "<=" in l else df["line"] >= 4.5),
        [("line<=1.5", None), ("line=2.5", None), ("line=3.5", None), ("line>=4.5", None)])

    # Fix: proper lambda
    def line_cond(df, label):
        if label == "line<=1.5": return df["line"] <= 1.5
        if label == "line=2.5": return df["line"] == 2.5
        if label == "line=3.5": return df["line"] == 3.5
        if label == "line>=4.5": return df["line"] >= 4.5
        return pd.Series(False, index=df.index)

    # Redo S1 properly
    all_segments = []
    log()
    log("=" * 65)
    log("SECTION 1 — SEGMENT RESULTS")
    log("=" * 65)

    # S1
    log(f"\n{'─'*50}")
    log("S1 — LINE BAND")
    log(f"{'─'*50}")
    hdr = f"{'Condition':<25s} {'Val N':>6s} {'Hit%':>6s} {'BE%':>5s} {'ROI_B':>7s} {'OOS N':>6s} {'OOS Hit':>7s} {'OOS_B':>7s} {'Label':<10s}"
    log(hdr)
    log("-" * len(hdr))

    for label, cond_fn in [
        ("line<=1.5", lambda d: d["line"] <= 1.5),
        ("line=2.5", lambda d: d["line"] == 2.5),
        ("line=3.5", lambda d: d["line"] == 3.5),
        ("line>=4.5", lambda d: d["line"] >= 4.5),
    ]:
        v, o = val[cond_fn(val)], oos[cond_fn(oos)]
        vs, os_ = segment_stats(v), segment_stats(o) if len(o) > 0 else None
        g = gate_check(vs, os_)
        log(f"{label:<25s} {vs['N']:>6d} {vs['hit_rate']:>5.1f}% {vs['be_rate']:>4.1f}% {vs['roi_b']:>+6.1f}% "
            f"{os_['N'] if os_ else 0:>6d} {os_['hit_rate'] if os_ else 0:.1f}% {os_['roi_b'] if os_ else 0:+.1f}% {g}")
        all_segments.append({"segment": "S1_LINE", "condition": label, "gate": g,
                              "val_n": vs["N"], "val_hr": vs["hit_rate"], "val_roi_b": vs["roi_b"],
                              "oos_n": os_["N"] if os_ else 0, "oos_roi_b": os_["roi_b"] if os_ else np.nan})

    # S2: Player volume
    log(f"\n{'─'*50}")
    log("S2 — PLAYER VOLUME (rolling 3PA/game)")
    log(f"{'─'*50}")
    log(hdr)
    log("-" * len(hdr))

    for label, cond_fn in [
        ("LOW (<3 3PA)", lambda d: d["FG3A_per_game"] < 3),
        ("MED (3-6 3PA)", lambda d: (d["FG3A_per_game"] >= 3) & (d["FG3A_per_game"] <= 6)),
        ("HIGH (>6 3PA)", lambda d: d["FG3A_per_game"] > 6),
    ]:
        v, o = val[cond_fn(val)], oos[cond_fn(oos)]
        vs, os_ = segment_stats(v), segment_stats(o) if len(o) > 0 else None
        g = gate_check(vs, os_)
        log(f"{label:<25s} {vs['N']:>6d} {vs['hit_rate']:>5.1f}% {vs['be_rate']:>4.1f}% {vs['roi_b']:>+6.1f}% "
            f"{os_['N'] if os_ else 0:>6d} {os_['hit_rate'] if os_ else 0:.1f}% {os_['roi_b'] if os_ else 0:+.1f}% {g}")
        all_segments.append({"segment": "S2_VOLUME", "condition": label, "gate": g,
                              "val_n": vs["N"], "val_hr": vs["hit_rate"], "val_roi_b": vs["roi_b"],
                              "oos_n": os_["N"] if os_ else 0, "oos_roi_b": os_["roi_b"] if os_ else np.nan})

    # S3: Minutes volatility
    log(f"\n{'─'*50}")
    log("S3 — MINUTES VOLATILITY")
    log(f"{'─'*50}")
    log(hdr)
    log("-" * len(hdr))

    for label, cond_fn in [
        ("LOW (std<4)", lambda d: d["sim_min_std"] < 4),
        ("MED (std 4-7)", lambda d: (d["sim_min_std"] >= 4) & (d["sim_min_std"] <= 7)),
        ("HIGH (std>7)", lambda d: d["sim_min_std"] > 7),
    ]:
        v, o = val[cond_fn(val)], oos[cond_fn(oos)]
        vs, os_ = segment_stats(v), segment_stats(o) if len(o) > 0 else None
        g = gate_check(vs, os_)
        log(f"{label:<25s} {vs['N']:>6d} {vs['hit_rate']:>5.1f}% {vs['be_rate']:>4.1f}% {vs['roi_b']:>+6.1f}% "
            f"{os_['N'] if os_ else 0:>6d} {os_['hit_rate'] if os_ else 0:.1f}% {os_['roi_b'] if os_ else 0:+.1f}% {g}")
        all_segments.append({"segment": "S3_MINVOL", "condition": label, "gate": g,
                              "val_n": vs["N"], "val_hr": vs["hit_rate"], "val_roi_b": vs["roi_b"],
                              "oos_n": os_["N"] if os_ else 0, "oos_roi_b": os_["roi_b"] if os_ else np.nan})

    # S4: Odds band
    log(f"\n{'─'*50}")
    log("S4 — ODDS BAND (under odds)")
    log(f"{'─'*50}")
    log(hdr)
    log("-" * len(hdr))

    for label, cond_fn in [
        ("Juiced (<-120)", lambda d: d["actual_under_odds"] < -120),
        ("Near-even (-120 to -105)", lambda d: (d["actual_under_odds"] >= -120) & (d["actual_under_odds"] <= -105)),
        ("Plus-money (>-105)", lambda d: d["actual_under_odds"] > -105),
    ]:
        v, o = val[cond_fn(val)], oos[cond_fn(oos)]
        vs, os_ = segment_stats(v), segment_stats(o) if len(o) > 0 else None
        g = gate_check(vs, os_)
        log(f"{label:<25s} {vs['N']:>6d} {vs['hit_rate']:>5.1f}% {vs['be_rate']:>4.1f}% {vs['roi_b']:>+6.1f}% "
            f"{os_['N'] if os_ else 0:>6d} {os_['hit_rate'] if os_ else 0:.1f}% {os_['roi_b'] if os_ else 0:+.1f}% {g}")
        all_segments.append({"segment": "S4_ODDS", "condition": label, "gate": g,
                              "val_n": vs["N"], "val_hr": vs["hit_rate"], "val_roi_b": vs["roi_b"],
                              "oos_n": os_["N"] if os_ else 0, "oos_roi_b": os_["roi_b"] if os_ else np.nan})

    # S5: Spread / game script (use PLUS_MINUS as proxy since pre-game spread not available)
    # Use model edge as proxy for expected game dynamics
    log(f"\n{'─'*50}")
    log("S5 — EDGE SIZE (proxy for model confidence)")
    log(f"{'─'*50}")
    log(hdr)
    log("-" * len(hdr))

    for label, cond_fn in [
        ("Small edge (0-5%)", lambda d: d["edge"] < 0.05),
        ("Medium edge (5-15%)", lambda d: (d["edge"] >= 0.05) & (d["edge"] < 0.15)),
        ("Large edge (15%+)", lambda d: d["edge"] >= 0.15),
    ]:
        v, o = val[cond_fn(val)], oos[cond_fn(oos)]
        vs, os_ = segment_stats(v), segment_stats(o) if len(o) > 0 else None
        g = gate_check(vs, os_)
        log(f"{label:<25s} {vs['N']:>6d} {vs['hit_rate']:>5.1f}% {vs['be_rate']:>4.1f}% {vs['roi_b']:>+6.1f}% "
            f"{os_['N'] if os_ else 0:>6d} {os_['hit_rate'] if os_ else 0:.1f}% {os_['roi_b'] if os_ else 0:+.1f}% {g}")
        all_segments.append({"segment": "S5_EDGE", "condition": label, "gate": g,
                              "val_n": vs["N"], "val_hr": vs["hit_rate"], "val_roi_b": vs["roi_b"],
                              "oos_n": os_["N"] if os_ else 0, "oos_roi_b": os_["roi_b"] if os_ else np.nan})

    # S6: Book dispersion
    log(f"\n{'─'*50}")
    log("S6 — BOOK DISPERSION")
    log(f"{'─'*50}")
    log(hdr)
    log("-" * len(hdr))

    for label, cond_fn in [
        ("LOW disp (range<=0.5)", lambda d: d["line_range"] <= 0.5),
        ("HIGH disp (range>0.5)", lambda d: d["line_range"] > 0.5),
    ]:
        v, o = val[cond_fn(val)], oos[cond_fn(oos)]
        vs, os_ = segment_stats(v), segment_stats(o) if len(o) > 0 else None
        g = gate_check(vs, os_)
        log(f"{label:<25s} {vs['N']:>6d} {vs['hit_rate']:>5.1f}% {vs['be_rate']:>4.1f}% {vs['roi_b']:>+6.1f}% "
            f"{os_['N'] if os_ else 0:>6d} {os_['hit_rate'] if os_ else 0:.1f}% {os_['roi_b'] if os_ else 0:+.1f}% {g}")
        all_segments.append({"segment": "S6_DISP", "condition": label, "gate": g,
                              "val_n": vs["N"], "val_hr": vs["hit_rate"], "val_roi_b": vs["roi_b"],
                              "oos_n": os_["N"] if os_ else 0, "oos_roi_b": os_["roi_b"] if os_ else np.nan})

    # ── S7: COMBINED FILTER ──
    log()
    log("=" * 65)
    log("SECTION 2 — COMBINED FILTER (S7)")
    log("=" * 65)
    log()

    # Identify independently positive segments
    seg_df = pd.DataFrame(all_segments)
    positive = seg_df[(seg_df["val_roi_b"] > 0) & (seg_df["val_n"] >= 100)]
    log("Independently positive segments (val ROI_B > 0, N >= 100):")
    for _, s in positive.iterrows():
        log(f"  {s['segment']}/{s['condition']}: N={s['val_n']}, ROI_B={s['val_roi_b']:+.1f}%, gate={s['gate']}")
    log()

    # Find top 2-3 non-overlapping conditions
    # Take best from each independent segment type
    best_per_seg = positive.sort_values("val_roi_b", ascending=False).drop_duplicates(subset="segment")

    if len(best_per_seg) >= 2:
        top = best_per_seg.head(3)
        log("Selected conditions for combined filter:")
        conditions = []
        for _, s in top.iterrows():
            log(f"  {s['segment']}: {s['condition']}")
            conditions.append((s["segment"], s["condition"]))

        # Build combined mask
        def combined_mask(df):
            mask = pd.Series(True, index=df.index)
            for seg, cond in conditions:
                if "line<=1.5" in cond: mask &= df["line"] <= 1.5
                elif "line=2.5" in cond: mask &= df["line"] == 2.5
                elif "line=3.5" in cond: mask &= df["line"] == 3.5
                elif "line>=4.5" in cond: mask &= df["line"] >= 4.5
                elif "LOW (<3" in cond: mask &= df["FG3A_per_game"] < 3
                elif "MED (3-6" in cond: mask &= (df["FG3A_per_game"] >= 3) & (df["FG3A_per_game"] <= 6)
                elif "HIGH (>6" in cond: mask &= df["FG3A_per_game"] > 6
                elif "LOW (std<4" in cond: mask &= df["sim_min_std"] < 4
                elif "MED (std 4-7" in cond: mask &= (df["sim_min_std"] >= 4) & (df["sim_min_std"] <= 7)
                elif "HIGH (std>7" in cond: mask &= df["sim_min_std"] > 7
                elif "Juiced" in cond: mask &= df["actual_under_odds"] < -120
                elif "Near-even" in cond: mask &= (df["actual_under_odds"] >= -120) & (df["actual_under_odds"] <= -105)
                elif "Plus-money" in cond: mask &= df["actual_under_odds"] > -105
                elif "Small edge" in cond: mask &= df["edge"] < 0.05
                elif "Medium edge" in cond: mask &= (df["edge"] >= 0.05) & (df["edge"] < 0.15)
                elif "Large edge" in cond: mask &= df["edge"] >= 0.15
                elif "LOW disp" in cond: mask &= df["line_range"] <= 0.5
                elif "HIGH disp" in cond: mask &= df["line_range"] > 0.5
            return mask

        vc = val[combined_mask(val)]
        oc = oos[combined_mask(oos)]
        vcs = segment_stats(vc, "COMBINED")
        ocs = segment_stats(oc, "COMBINED OOS") if len(oc) > 0 else None

        log(f"\n  COMBINED FILTER:")
        log(f"  Val: N={vcs['N']}, hit={vcs['hit_rate']}%, BE={vcs['be_rate']:.1f}%, "
            f"ROI_B={vcs['roi_b']:+.1f}%")
        if ocs:
            log(f"  OOS: N={ocs['N']}, hit={ocs['hit_rate']}%, ROI_B={ocs['roi_b']:+.1f}%")

        g_combined = gate_check(vcs, ocs)
        log(f"  Gate: {g_combined}")
    else:
        log("  Insufficient independently positive segments for combination.")
        g_combined = "FAIL"

    log()

    # ── SECTION 3: OBSERVATIONS ──
    log("=" * 65)
    log("SECTION 3 — PATTERN OBSERVATIONS")
    log("=" * 65)
    log()

    # 1. Broadly distributed or concentrated?
    positive_count = len(seg_df[seg_df["val_roi_b"] > 0])
    total_count = len(seg_df)
    log(f"1. Signal distribution: {positive_count}/{total_count} segments positive")
    if positive_count > total_count * 0.6:
        log("   → BROADLY DISTRIBUTED — signal exists across many conditions")
    else:
        log("   → CONCENTRATED — signal lives in specific conditions")
    log()

    # 2. Strongest segment
    if len(seg_df[seg_df["val_n"] >= 100]) > 0:
        best = seg_df[seg_df["val_n"] >= 100].sort_values("val_roi_b", ascending=False).iloc[0]
        log(f"2. Strongest segment: {best['segment']}/{best['condition']}")
        log(f"   Val: N={best['val_n']}, ROI_B={best['val_roi_b']:+.1f}%")
        if not pd.isna(best["oos_roi_b"]):
            log(f"   OOS: ROI_B={best['oos_roi_b']:+.1f}%")
    log()

    # 3. OOS survival
    oos_positive = seg_df[(seg_df["oos_roi_b"] > 0) & (seg_df["val_roi_b"] > 0) & (seg_df["val_n"] >= 100)]
    log(f"3. OOS survival: {len(oos_positive)} segments positive on both val AND OOS")
    for _, s in oos_positive.iterrows():
        log(f"   {s['segment']}/{s['condition']}: val={s['val_roi_b']:+.1f}%, oos={s['oos_roi_b']:+.1f}%")
    log()

    # 4. Method A vs B
    log("4. Method A vs B agreement:")
    log("   (ROI_A uses standard -110; ROI_B uses actual recorded odds)")
    log("   Methods should agree directionally. Major divergence = odds mispricing.")
    log()

    # 5. Shadow promotion
    promising = seg_df[seg_df["gate"] == "PROMISING"]
    near_miss = seg_df[seg_df["gate"] == "NEAR-MISS"]
    log(f"5. PROMISING: {len(promising)}, NEAR-MISS: {len(near_miss)}")
    for _, s in promising.iterrows():
        log(f"   PROMISING: {s['segment']}/{s['condition']}")
    for _, s in near_miss.iterrows():
        log(f"   NEAR-MISS: {s['segment']}/{s['condition']}")
    log()

    log("6. Next hypothesis: opponent 3PT defense rating adjustment")
    log("   (teams that allow fewer 3PA or lower 3P% may create UNDER value)")
    log()

    # ── SECTION 4: RECOMMENDATION ──
    log("=" * 65)
    log("SECTION 4 — PRODUCTION RECOMMENDATION")
    log("=" * 65)
    log()

    if len(promising) > 0 or g_combined == "PROMISING":
        log("RECOMMENDATION: READY FOR SHADOW")
        log("Deploy Threes UNDER via existing Model C shadow system")
        if len(promising) > 0:
            log("Qualifying segments:")
            for _, s in promising.iterrows():
                log(f"  {s['condition']}: N={s['val_n']}, ROI_B={s['val_roi_b']:+.1f}%")
    elif len(near_miss) > 0:
        log("RECOMMENDATION: NEAR-MISS — consider full population Threes UNDER shadow")
        base_val = segment_stats(val)
        base_oos = segment_stats(oos)
        log(f"  Full Threes UNDER: Val ROI_B={base_val['roi_b']:+.1f}%, "
            f"OOS ROI_B={base_oos['roi_b']:+.1f}%")
        log("  The base population may be stronger than any single segment.")
    else:
        log("RECOMMENDATION: NOT READY")
        log("  Signal does not survive segmentation at required thresholds.")
    log()

    # Save
    seg_df.to_parquet(OUT_DIR / "segment_results.parquet", index=False)
    seg_df.to_csv(OUT_DIR / "segment_results.csv", index=False)
    with open(OUT_DIR / "p5_summary.txt", "w") as f:
        f.write("\n".join(out))

    log("=" * 65)
    log("Files saved: nba/props/model_p5/")
    log("=" * 65)


if __name__ == "__main__":
    main()
