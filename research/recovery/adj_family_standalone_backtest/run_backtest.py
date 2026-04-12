"""
ADJ Family Standalone Clean Backtest
=====================================
For each of 5 ADJ metrics, apply standalone gate (combined > 0 → UNDER),
grade against actual_total vs closing_total, compute ROI at closing under prices.
Temporal split: Discovery 2022-2023, Validation 2024, OOS 2025.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json, sys, warnings
warnings.filterwarnings("ignore")

OUT = Path("/root/mlb-model/research/recovery/adj_family_standalone_backtest")

# ── Load data ──
prf = pd.read_parquet("/root/mlb-model/research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet")
gt  = pd.read_parquet("/root/mlb-model/sim/data/game_table.parquet")
canon = pd.read_parquet("/root/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet")

METRICS = [
    "adj_k_rate_last3",
    "adj_contact_rate_last3",
    "adj_hard_hit_last3",
    "adj_bb_rate_last3",
    "adj_run_suppression_last3",
]

SIGNAL_NAMES = {
    "adj_k_rate_last3": "ADJ_K_RATE",
    "adj_contact_rate_last3": "ADJ_CONTACT",
    "adj_hard_hit_last3": "ADJ_HH",
    "adj_bb_rate_last3": "ADJ_BB_RATE",
    "adj_run_suppression_last3": "ADJ_RUN_SUPP",
}

# ── Harmonize keys ──
gt["game_pk"] = gt["game_pk"].astype(str)
prf["game_pk"] = prf["game_pk"].astype(str)
canon["game_pk"] = canon["game_pk"].astype(str)

# ── Pivot PRF: for each game_pk, get home and away pitcher features ──
home = prf[prf["side"] == "home"].copy()
away = prf[prf["side"] == "away"].copy()

home_cols = {m: f"home_{m}" for m in METRICS}
away_cols = {m: f"away_{m}" for m in METRICS}

home_ren = home[["game_pk"] + METRICS].rename(columns=home_cols)
away_ren = away[["game_pk"] + METRICS].rename(columns=away_cols)

# Merge home + away on game_pk
game_features = home_ren.merge(away_ren, on="game_pk", how="inner")
print(f"Games with both home & away ADJ features: {len(game_features)}")

# ── Join to game_table for actual_total ──
gt_slim = gt[["game_pk", "season", "date", "home_team", "away_team", "actual_total"]].copy()
df = game_features.merge(gt_slim, on="game_pk", how="inner")
print(f"After joining game_table: {len(df)}")

# ── Join to canonical odds for closing total + under price ──
# Take best under price across books for each game
canon_best = canon.groupby("game_pk").agg(
    closing_total=("total_line", "first"),
    under_price=("total_under_price", "max"),  # best under price
).reset_index()

df = df.merge(canon_best, on="game_pk", how="inner")
print(f"After joining canonical odds: {len(df)}")
print(f"Under price coverage: {df['under_price'].notna().sum()}/{len(df)}")

# ── Compute combined signals ──
for m in METRICS:
    df[f"combined_{m}"] = (df[f"home_{m}"] + df[f"away_{m}"]) / 2
    df[f"gate_{m}"] = df[f"combined_{m}"] > 0

# ── Grade outcomes ──
df["result"] = np.where(
    df["actual_total"] < df["closing_total"], "WIN",
    np.where(df["actual_total"] > df["closing_total"], "LOSS", "PUSH")
)

# ── Temporal split ──
df["date"] = pd.to_datetime(df["date"])
df["split"] = np.where(
    df["season"].isin([2022, 2023]), "DISC",
    np.where(df["season"] == 2024, "VAL",
    np.where(df["season"] == 2025, "OOS", "OTHER"))
)

def american_to_decimal(price):
    """Convert American odds to decimal payout (profit per $1 risked)."""
    if pd.isna(price) or price == 0:
        return np.nan
    if price > 0:
        return price / 100.0
    else:
        return 100.0 / abs(price)

def compute_roi(sub):
    """Compute ROI for a bet set at actual closing under prices."""
    bets = sub[sub["result"] != "PUSH"].copy()
    if len(bets) == 0:
        return {"n_bets": 0, "wins": 0, "losses": 0, "pushes": 0, "win_rate": np.nan, "roi": np.nan, "units": np.nan}
    
    pushes = len(sub[sub["result"] == "PUSH"])
    wins = (bets["result"] == "WIN").sum()
    losses = (bets["result"] == "LOSS").sum()
    
    # Each bet risks 1 unit
    # Win: profit = decimal payout
    # Loss: lose 1 unit
    bets["decimal_payout"] = bets["under_price"].apply(american_to_decimal)
    bets["profit"] = np.where(bets["result"] == "WIN", bets["decimal_payout"], -1.0)
    
    total_risked = len(bets)
    total_profit = bets["profit"].sum()
    roi = total_profit / total_risked * 100
    
    return {
        "n_bets": len(bets),
        "wins": int(wins),
        "losses": int(losses),
        "pushes": int(pushes),
        "win_rate": wins / len(bets) * 100,
        "roi": roi,
        "units": total_profit,
    }

# ── Run backtest for each metric × split ──
results = []
for m in METRICS:
    sig_name = SIGNAL_NAMES[m]
    # Filter to games where signal fires (gate = True) and under_price exists
    sig_df = df[(df[f"gate_{m}"] == True) & (df["under_price"].notna())].copy()
    
    for split in ["DISC", "VAL", "OOS"]:
        sub = sig_df[sig_df["split"] == split]
        stats = compute_roi(sub)
        stats["signal"] = sig_name
        stats["metric"] = m
        stats["split"] = split
        results.append(stats)

results_df = pd.DataFrame(results)

# ── Also compute ALL split (full sample) ──
for m in METRICS:
    sig_name = SIGNAL_NAMES[m]
    sig_df = df[(df[f"gate_{m}"] == True) & (df["under_price"].notna())].copy()
    stats = compute_roi(sig_df)
    stats["signal"] = sig_name
    stats["metric"] = m
    stats["split"] = "ALL"
    results.append(stats)

results_df = pd.DataFrame(results)

# ── Print table ──
print("\n" + "="*90)
print("ADJ FAMILY STANDALONE BACKTEST — RESULTS")
print("="*90)
print(f"{'Signal':<16} {'Split':<6} {'Bets':>5} {'W':>4} {'L':>4} {'P':>3} {'Win%':>6} {'ROI%':>7} {'Units':>7}")
print("-"*90)
for _, r in results_df.sort_values(["signal", "split"]).iterrows():
    wr = f"{r['win_rate']:.1f}" if not np.isnan(r.get('win_rate', np.nan)) else "—"
    roi = f"{r['roi']:.1f}" if not np.isnan(r.get('roi', np.nan)) else "—"
    units = f"{r['units']:.1f}" if not np.isnan(r.get('units', np.nan)) else "—"
    print(f"{r['signal']:<16} {r['split']:<6} {r['n_bets']:>5} {r['wins']:>4} {r['losses']:>4} {r['pushes']:>3} {wr:>6} {roi:>7} {units:>7}")

# ── Signal firing rates ──
print("\n" + "="*90)
print("SIGNAL FIRING RATES")
print("="*90)
for m in METRICS:
    sig_name = SIGNAL_NAMES[m]
    valid = df[df[f"combined_{m}"].notna()]
    fires = valid[valid[f"gate_{m}"] == True]
    rate = len(fires) / len(valid) * 100 if len(valid) > 0 else 0
    print(f"  {sig_name:<16}: {len(fires):>5} / {len(valid):>5} ({rate:.1f}%)")

# ── Baseline under win rate (no signal) ──
print("\n" + "="*90)
print("BASELINE (ALL GAMES, BET UNDER BLINDLY)")
print("="*90)
for split in ["DISC", "VAL", "OOS", "ALL"]:
    if split == "ALL":
        sub = df[df["under_price"].notna()]
    else:
        sub = df[(df["split"] == split) & (df["under_price"].notna())]
    stats = compute_roi(sub)
    wr = f"{stats['win_rate']:.1f}" if not np.isnan(stats.get('win_rate', np.nan)) else "—"
    roi = f"{stats['roi']:.1f}" if not np.isnan(stats.get('roi', np.nan)) else "—"
    print(f"  {split:<6}: {stats['n_bets']:>5} bets, Win%={wr}, ROI={roi}%")

# ── Combined signal (all 5 fire) ──
print("\n" + "="*90)
print("COMBINED: ALL 5 ADJ SIGNALS FIRE SIMULTANEOUSLY")
print("="*90)
all_fire = df.copy()
for m in METRICS:
    all_fire = all_fire[all_fire[f"gate_{m}"] == True]
all_fire = all_fire[all_fire["under_price"].notna()]
for split in ["DISC", "VAL", "OOS", "ALL"]:
    if split == "ALL":
        sub = all_fire
    else:
        sub = all_fire[all_fire["split"] == split]
    stats = compute_roi(sub)
    wr = f"{stats['win_rate']:.1f}" if not np.isnan(stats.get('win_rate', np.nan)) else "—"
    roi = f"{stats['roi']:.1f}" if not np.isnan(stats.get('roi', np.nan)) else "—"
    print(f"  {split:<6}: {stats['n_bets']:>5} bets, Win%={wr}, ROI={roi}%")

# ── Per-signal OOS detail for exec summary decisions ──
print("\n" + "="*90)
print("DECISIONS")
print("="*90)
for m in METRICS:
    sig_name = SIGNAL_NAMES[m]
    disc_row = results_df[(results_df["metric"]==m) & (results_df["split"]=="DISC")].iloc[0]
    val_row = results_df[(results_df["metric"]==m) & (results_df["split"]=="VAL")].iloc[0]
    oos_row = results_df[(results_df["metric"]==m) & (results_df["split"]=="OOS")].iloc[0]
    
    # Decision logic: OOS ROI > 0 AND val ROI > 0 → RETAIN, else REJECT
    oos_roi = oos_row["roi"] if not np.isnan(oos_row["roi"]) else -999
    val_roi = val_row["roi"] if not np.isnan(val_row["roi"]) else -999
    disc_roi = disc_row["roi"] if not np.isnan(disc_row["roi"]) else -999
    
    if oos_roi > 0 and val_roi > 0:
        decision = "RETAIN"
    elif oos_roi > 0 and val_roi <= 0:
        decision = "WEAK-RETAIN (OOS+ but VAL-)"
    elif oos_roi <= 0 and val_roi > 0:
        decision = "WEAK-REJECT (VAL+ but OOS-)"
    else:
        decision = "REJECT"
    
    print(f"  {sig_name:<16}: DISC ROI={disc_roi:+.1f}%  VAL ROI={val_roi:+.1f}%  OOS ROI={oos_roi:+.1f}%  → {decision}")

# ── Save CSV ──
results_df.to_csv(OUT / "adj_family_backtest_results.csv", index=False)
print(f"\nSaved: {OUT / 'adj_family_backtest_results.csv'}")

# ── Save detailed bet log ──
bet_log_rows = []
for m in METRICS:
    sig_name = SIGNAL_NAMES[m]
    sig_df = df[(df[f"gate_{m}"] == True) & (df["under_price"].notna())].copy()
    sig_df["signal"] = sig_name
    sig_df["combined_value"] = sig_df[f"combined_{m}"]
    bet_log_rows.append(sig_df[["game_pk", "date", "season", "split", "signal", "combined_value",
                                 "home_team", "away_team", "closing_total", "under_price",
                                 "actual_total", "result"]])
bet_log = pd.concat(bet_log_rows, ignore_index=True)
bet_log.to_csv(OUT / "adj_family_bet_log.csv", index=False)
print(f"Saved: {OUT / 'adj_family_bet_log.csv'}")

# ── Build exec summary ──
lines = []
lines.append("# ADJ Family Standalone Clean Backtest — Executive Summary")
lines.append("")
lines.append(f"**Generated:** 2026-04-12")
lines.append(f"**Temporal Split:** Discovery 2022-2023 | Validation 2024 | OOS 2025")
lines.append(f"**Total games with dual-starter ADJ features + closing odds:** {len(df)}")
lines.append("")
lines.append("## Signal Definitions (locked from shadow_signals.py)")
lines.append("")
lines.append("Each ADJ metric is a rolling 3-start opponent-adjusted value per pitcher.")
lines.append("For each game: `combined = (home_val + away_val) / 2`")
lines.append("Signal fires when `combined > 0` → bet direction: **UNDER** at closing under price.")
lines.append("")
lines.append("| Signal | Metric | Meaning when > 0 |")
lines.append("|--------|--------|-------------------|")
lines.append("| ADJ_K_RATE | adj_k_rate_last3 | Both pitchers striking out more than opponent-expected |")
lines.append("| ADJ_CONTACT | adj_contact_rate_last3 | Both pitchers suppressing contact below opponent-expected |")
lines.append("| ADJ_HH | adj_hard_hit_last3 | Both pitchers suppressing hard contact below league avg |")
lines.append("| ADJ_BB_RATE | adj_bb_rate_last3 | Both pitchers walking fewer than opponent-expected |")
lines.append("| ADJ_RUN_SUPP | adj_run_suppression_last3 | Both pitchers suppressing runs below opponent-expected |")
lines.append("")
lines.append("## Results Table")
lines.append("")
lines.append("| Signal | Split | Bets | W | L | Push | Win% | ROI% | Units |")
lines.append("|--------|-------|------|---|---|------|------|------|-------|")
for _, r in results_df.sort_values(["signal", "split"]).iterrows():
    wr = f"{r['win_rate']:.1f}" if not np.isnan(r.get('win_rate', np.nan)) else "—"
    roi = f"{r['roi']:.1f}" if not np.isnan(r.get('roi', np.nan)) else "—"
    units = f"{r['units']:.1f}" if not np.isnan(r.get('units', np.nan)) else "—"
    lines.append(f"| {r['signal']} | {r['split']} | {r['n_bets']} | {r['wins']} | {r['losses']} | {r['pushes']} | {wr} | {roi} | {units} |")

lines.append("")
lines.append("## Baseline (bet under blindly on all games)")
lines.append("")
lines.append("| Split | Bets | Win% | ROI% |")
lines.append("|-------|------|------|------|")
for split in ["DISC", "VAL", "OOS", "ALL"]:
    if split == "ALL":
        sub = df[df["under_price"].notna()]
    else:
        sub = df[(df["split"] == split) & (df["under_price"].notna())]
    stats = compute_roi(sub)
    wr = f"{stats['win_rate']:.1f}" if not np.isnan(stats.get('win_rate', np.nan)) else "—"
    roi = f"{stats['roi']:.1f}" if not np.isnan(stats.get('roi', np.nan)) else "—"
    lines.append(f"| {split} | {stats['n_bets']} | {wr} | {roi} |")

lines.append("")
lines.append("## Decisions")
lines.append("")
lines.append("| Signal | DISC ROI% | VAL ROI% | OOS ROI% | Decision |")
lines.append("|--------|-----------|----------|----------|----------|")
for m in METRICS:
    sig_name = SIGNAL_NAMES[m]
    disc_row = results_df[(results_df["metric"]==m) & (results_df["split"]=="DISC")].iloc[0]
    val_row = results_df[(results_df["metric"]==m) & (results_df["split"]=="VAL")].iloc[0]
    oos_row = results_df[(results_df["metric"]==m) & (results_df["split"]=="OOS")].iloc[0]
    oos_roi = oos_row["roi"] if not np.isnan(oos_row["roi"]) else -999
    val_roi = val_row["roi"] if not np.isnan(val_row["roi"]) else -999
    disc_roi = disc_row["roi"] if not np.isnan(disc_row["roi"]) else -999
    if oos_roi > 0 and val_roi > 0:
        decision = "RETAIN"
    elif oos_roi > 0 and val_roi <= 0:
        decision = "WEAK-RETAIN"
    elif oos_roi <= 0 and val_roi > 0:
        decision = "WEAK-REJECT"
    else:
        decision = "REJECT"
    lines.append(f"| {sig_name} | {disc_roi:+.1f} | {val_roi:+.1f} | {oos_roi:+.1f} | **{decision}** |")

lines.append("")
lines.append("## Methodology Notes")
lines.append("")
lines.append("- Feature source: `research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet`")
lines.append("- Features are rolling 3-start values computed PRIOR to each game (no look-ahead)")
lines.append("- Closing odds from `mlb_sim/data/mlb_odds_closing_canonical.parquet` (best under price across books)")
lines.append("- ROI computed at actual closing American odds, risk $1/bet, profit = decimal payout on wins")
lines.append("- Pushes excluded from bet count and ROI")
lines.append("- No production files modified")

summary_text = "\n".join(lines)
(OUT / "ADJ_FAMILY_STANDALONE_BACKTEST_EXEC_SUMMARY.md").write_text(summary_text)
print(f"Saved: {OUT / 'ADJ_FAMILY_STANDALONE_BACKTEST_EXEC_SUMMARY.md'}")
print("\nDONE.")
