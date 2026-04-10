#!/usr/bin/env python3
"""
ADJ Standalone Signal Rebuild & Backtest
=========================================
Reconstructs the exact live ADJ signals historically (2022-2025) and backtests
against actual closing prices from canonical odds.

Live code identity (from shadow_signals.py):
- combined = (home_val + away_val) / 2
- favorable_zone_flag = combined > 0
- Direction: ALL ADJ signals are UNDER-leaning when favorable
- V1 direction is logged as context but does NOT gate firing
- Feature source: pitcher_recent_adjusted_features.parquet (per-start, shift(1) lagged rolling)

5 signals: ADJ_CONTACT, ADJ_HH, adj_k_rate_last3, ADJ_BB_RATE, ADJ_RUN_SUPP
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path("/root/mlb-model")
OUT = BASE / "research" / "recovery" / "adj_standalone_rebuild"
OUT.mkdir(parents=True, exist_ok=True)

# Signal name mapping (internal metric → display name)
SIGNAL_MAP = {
    "adj_contact_rate_last3": "ADJ_CONTACT",
    "adj_hard_hit_last3": "ADJ_HH",
    "adj_k_rate_last3": "adj_k_rate_last3",
    "adj_bb_rate_last3": "ADJ_BB_RATE",
    "adj_run_suppression_last3": "ADJ_RUN_SUPP",
}
METRICS = list(SIGNAL_MAP.keys())

# ── Odds helpers ──────────────────────────────────────────────────────
def american_to_decimal(price):
    """Convert American odds to decimal payout (includes stake)."""
    if price is None or np.isnan(price):
        return np.nan
    if price >= 100:
        return 1.0 + price / 100.0
    elif price <= -100:
        return 1.0 + 100.0 / abs(price)
    return np.nan

def compute_roi(wins, losses, pushes, avg_dec_payout):
    """Flat $1 bet ROI. Wins pay (dec-1), losses lose $1, pushes return $0."""
    n = wins + losses + pushes
    if n == 0:
        return np.nan
    profit = wins * (avg_dec_payout - 1) - losses * 1.0
    return profit / (wins + losses)  # ROI on risked capital (exclude pushes)


# ══════════════════════════════════════════════════════════════════════
# PHASE 1: Load data
# ══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("PHASE 1: Loading data")
print("=" * 70)

# Pitcher recent adjusted features (per-start, lagged rolling)
prf = pd.read_parquet(BASE / "research" / "opponent_adjusted_engine_v2" / "pitcher_recent_adjusted_features.parquet")
prf["game_date"] = pd.to_datetime(prf["game_date"])
prf = prf.sort_values(["pitcher_id", "game_date"]).reset_index(drop=True)
print(f"  pitcher_recent_adjusted_features: {prf.shape[0]} rows, {prf['pitcher_id'].nunique()} pitchers")
print(f"  Date range: {prf['game_date'].min().date()} – {prf['game_date'].max().date()}")

# Game table
gt = pd.read_parquet(BASE / "sim" / "data" / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
gt["game_pk"] = gt["game_pk"].astype(int)
print(f"  game_table: {gt.shape[0]} games")

# Canonical odds
canon = pd.read_parquet(BASE / "mlb_sim" / "data" / "mlb_odds_closing_canonical.parquet")
canon = canon[canon["game_pk"].astype(str).str.strip() != ""]
canon["game_pk"] = canon["game_pk"].astype(int)
print(f"  canonical odds: {canon.shape[0]} rows")

# Pitcher game logs (for starter identification)
pgl = pd.read_parquet(BASE / "mlb" / "data" / "pitcher_game_logs.parquet")
pgl["game_date"] = pd.to_datetime(pgl["game_date"])
pgl["game_pk"] = pgl["game_pk"].astype(int)
starters = pgl[pgl["starter_flag"] == 1][["game_pk", "player_id", "team", "home_away", "game_date", "season"]].copy()
print(f"  starters: {starters.shape[0]} starts")

# Split starters into home/away
home_sp = starters[starters["home_away"] == "home"][["game_pk", "player_id"]].rename(
    columns={"player_id": "home_sp_id"})
away_sp = starters[starters["home_away"] == "away"][["game_pk", "player_id"]].rename(
    columns={"player_id": "away_sp_id"})

# Merge to get both starters per game
games = gt[["game_pk", "date", "season", "home_team", "away_team", "actual_total"]].copy()
games = games.merge(home_sp, on="game_pk", how="left")
games = games.merge(away_sp, on="game_pk", how="left")

# Merge closing odds (take first per game_pk — use best available book)
canon_dedup = canon.sort_values("pull_timestamp").groupby("game_pk").last().reset_index()
games = games.merge(
    canon_dedup[["game_pk", "total_line", "total_under_price", "total_over_price"]],
    on="game_pk", how="left"
)

# Filter to 2022-2025 with both starters identified
games = games[games["season"].isin([2022, 2023, 2024, 2025])].copy()
games = games.dropna(subset=["home_sp_id", "away_sp_id"])
games["home_sp_id"] = games["home_sp_id"].astype(int)
games["away_sp_id"] = games["away_sp_id"].astype(int)
print(f"\n  Games with both starters (2022-2025): {len(games)}")


# ══════════════════════════════════════════════════════════════════════
# PHASE 2: Historical signal reconstruction
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 2: Historical signal reconstruction")
print("=" * 70)

# Build lookup: for each pitcher + game_date, get the most recent feature row
# where feature game_date < target game_date (to avoid lookahead)
# Since prf is already shift(1) lagged in build_v2.py, we use the row
# with game_date <= target_date (the row IS the as-of-that-start values)
# BUT: we need the row from the pitcher's LAST START before this game,
# which is exactly what the live code does (groupby pitcher, .last())
# For historical: we need the most recent prf row where prf.game_date < game.date

# Index prf for fast lookup
prf_indexed = prf.set_index(["pitcher_id", "game_date"]).sort_index()

# For each game, find each pitcher's most recent feature row
# This is O(N*log(M)) with searchsorted approach
print("  Building as-of feature lookups...")

# Group prf by pitcher_id for efficient lookup
pitcher_features = {}
for pid, grp in prf.groupby("pitcher_id"):
    grp = grp.sort_values("game_date").reset_index(drop=True)
    pitcher_features[pid] = grp

def get_pitcher_features_asof(pitcher_id, game_date, metrics):
    """Get the most recent feature values for a pitcher BEFORE game_date."""
    grp = pitcher_features.get(pitcher_id)
    if grp is None:
        return {m: None for m in metrics}
    # Find rows before game_date
    mask = grp["game_date"] < game_date
    valid = grp[mask]
    if len(valid) == 0:
        return {m: None for m in metrics}
    last_row = valid.iloc[-1]
    return {m: last_row[m] if pd.notna(last_row.get(m)) else None for m in metrics}

# Compute signals for all games
print("  Computing signals for all games...")
signal_records = []

for _, game in games.iterrows():
    gdate = game["date"]
    gpk = game["game_pk"]
    
    home_feats = get_pitcher_features_asof(game["home_sp_id"], gdate, METRICS)
    away_feats = get_pitcher_features_asof(game["away_sp_id"], gdate, METRICS)
    
    for metric in METRICS:
        h_val = home_feats[metric]
        a_val = away_feats[metric]
        
        if h_val is not None and a_val is not None:
            combined = (h_val + a_val) / 2.0
            favorable = combined > 0
        else:
            combined = None
            favorable = False
        
        signal_records.append({
            "game_pk": gpk,
            "date": gdate,
            "season": game["season"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "signal_name": SIGNAL_MAP[metric],
            "metric": metric,
            "home_value": h_val,
            "away_value": a_val,
            "combined": combined,
            "favorable_zone_flag": favorable,
            "actual_total": game["actual_total"],
            "total_line": game["total_line"],
            "total_under_price": game["total_under_price"],
            "total_over_price": game["total_over_price"],
        })

signals_df = pd.DataFrame(signal_records)
print(f"  Total signal records: {len(signals_df)}")
print(f"  Records with combined value: {signals_df['combined'].notna().sum()}")
print(f"  Favorable fires: {signals_df['favorable_zone_flag'].sum()}")

# Save
signals_df.to_parquet(OUT / "adj_standalone_historical_signals.parquet", index=False)
print(f"  Saved adj_standalone_historical_signals.parquet")


# ══════════════════════════════════════════════════════════════════════
# PHASE 3 & 4: Backtest — grade and compute ROI
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 3-4: Backtest — grading and ROI")
print("=" * 70)

# Filter to favorable fires with valid odds
fires = signals_df[
    (signals_df["favorable_zone_flag"]) &
    (signals_df["actual_total"].notna()) &
    (signals_df["total_line"].notna())
].copy()

# Grade: UNDER signal wins when actual < line
fires["result"] = np.where(
    fires["actual_total"] < fires["total_line"], "WIN",
    np.where(fires["actual_total"] > fires["total_line"], "LOSS", "PUSH")
)

# Decimal payout
fires["dec_payout"] = fires["total_under_price"].apply(american_to_decimal)

print(f"\n  Gradeable fires (favorable + line + actual): {len(fires)}")
print()

# ── Per-signal results ────────────────────────────────────────────────
results_table = []

for sig_name in SIGNAL_MAP.values():
    sig_fires = fires[fires["signal_name"] == sig_name]
    
    print(f"\n{'─' * 60}")
    print(f"  {sig_name}")
    print(f"{'─' * 60}")
    
    for season in [2022, 2023, 2024, 2025, "ALL"]:
        if season == "ALL":
            sf = sig_fires
        else:
            sf = sig_fires[sig_fires["season"] == season]
        
        if len(sf) == 0:
            continue
        
        w = (sf["result"] == "WIN").sum()
        l = (sf["result"] == "LOSS").sum()
        p = (sf["result"] == "PUSH").sum()
        n = w + l + p
        hit_rate = w / (w + l) if (w + l) > 0 else np.nan
        
        # ROI at actual closing under prices
        has_price = sf["dec_payout"].notna()
        if has_price.sum() > 0:
            avg_payout = sf.loc[has_price, "dec_payout"].mean()
            roi_n = has_price.sum()
            roi_w = ((sf["result"] == "WIN") & has_price).sum()
            roi_l = ((sf["result"] == "LOSS") & has_price).sum()
            roi_p = ((sf["result"] == "PUSH") & has_price).sum()
            # Compute actual profit using individual payouts
            profit = 0.0
            risked = 0
            for _, row in sf[has_price].iterrows():
                if row["result"] == "WIN":
                    profit += (row["dec_payout"] - 1)
                    risked += 1
                elif row["result"] == "LOSS":
                    profit -= 1.0
                    risked += 1
                # PUSH: no profit, no risk
            roi = profit / risked if risked > 0 else np.nan
        else:
            avg_payout = np.nan
            roi = np.nan
        
        label = str(season)
        print(f"    {label:>4}: N={n:>4}  W={w:>4}  L={l:>4}  P={p:>3}  "
              f"Hit={hit_rate:.1%}  ROI={roi:+.1%}" if not np.isnan(roi) else
              f"    {label:>4}: N={n:>4}  W={w:>4}  L={l:>4}  P={p:>3}  "
              f"Hit={hit_rate:.1%}  ROI=N/A")
        
        results_table.append({
            "signal_name": sig_name,
            "season": season,
            "N": n, "W": w, "L": l, "P": p,
            "hit_rate": round(hit_rate, 4) if not np.isnan(hit_rate) else None,
            "ROI": round(roi, 4) if not np.isnan(roi) else None,
            "avg_under_price": round(avg_payout, 4) if not np.isnan(avg_payout) else None,
        })


# ── Non-firing baseline ──────────────────────────────────────────────
print(f"\n\n{'=' * 60}")
print("  BASELINE: All games, blind under bet")
print(f"{'=' * 60}")
all_graded = signals_df[
    (signals_df["signal_name"] == "ADJ_CONTACT") &  # just use one signal to avoid duplication
    (signals_df["actual_total"].notna()) &
    (signals_df["total_line"].notna())
].copy()
all_graded["result"] = np.where(
    all_graded["actual_total"] < all_graded["total_line"], "WIN",
    np.where(all_graded["actual_total"] > all_graded["total_line"], "LOSS", "PUSH")
)
for season in [2022, 2023, 2024, 2025]:
    ag = all_graded[all_graded["season"] == season]
    w = (ag["result"] == "WIN").sum()
    l = (ag["result"] == "LOSS").sum()
    p = (ag["result"] == "PUSH").sum()
    hr = w / (w + l) if (w + l) > 0 else np.nan
    print(f"  {season}: N={len(ag)}  W={w}  L={l}  P={p}  Under-hit={hr:.1%}")


# ══════════════════════════════════════════════════════════════════════
# PHASE 5: Identity comparison — V1 interaction vs standalone
# ══════════════════════════════════════════════════════════════════════
print(f"\n\n{'=' * 70}")
print("PHASE 5: Identity comparison — V1 interaction vs standalone")
print("=" * 70)

print("""
LIVE CODE IDENTITY (from shadow_signals.py):
  Gate:     combined = (home_val + away_val) / 2
            favorable_zone_flag = combined > 0
  V1 gate:  NONE — v1_direction_context is logged but does NOT gate firing
  Direction: UNDER when favorable_zone_flag = True

OLD RESEARCH (V1 interaction from scanner):
  Gate:     combined > 0 AND v1_p_under > 0.57
  This was the original scanner design that required V1 UNDER agreement

DIFFERENCE:
  Live standalone fires on combined > 0 ALONE.
  The old research required V1 p_under > 0.57 as an additional filter.
  This means live fires MORE often (no V1 gate) but may have lower precision.
""")


# ══════════════════════════════════════════════════════════════════════
# PHASE 6: Stability analysis
# ══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("PHASE 6: Stability analysis")
print("=" * 70)

# Season stability
print("\n  Season stability (hit rate by year):")
for sig_name in SIGNAL_MAP.values():
    sf = fires[fires["signal_name"] == sig_name]
    rates = []
    for s in [2022, 2023, 2024, 2025]:
        ss = sf[sf["season"] == s]
        if len(ss) > 0:
            w = (ss["result"] == "WIN").sum()
            l = (ss["result"] == "LOSS").sum()
            rates.append(w / (w + l) if (w + l) > 0 else np.nan)
        else:
            rates.append(np.nan)
    valid_rates = [r for r in rates if not np.isnan(r)]
    spread = max(valid_rates) - min(valid_rates) if len(valid_rates) >= 2 else np.nan
    print(f"    {sig_name:<20}: {' → '.join(f'{r:.1%}' if not np.isnan(r) else 'N/A' for r in rates)}  "
          f"spread={spread:.1%}" if not np.isnan(spread) else
          f"    {sig_name:<20}: insufficient data")

# Monthly stability
print("\n  Monthly fire counts (across all years):")
fires["month"] = fires["date"].dt.month
for sig_name in SIGNAL_MAP.values():
    sf = fires[fires["signal_name"] == sig_name]
    monthly = sf.groupby("month").size()
    months_str = " ".join(f"M{m}:{c:>3}" for m, c in sorted(monthly.items()))
    print(f"    {sig_name:<20}: {months_str}")

# Overlap structure
print("\n  Overlap structure (how often signals fire together):")
# Pivot: for each game, which signals fired
fire_pivot = fires[["game_pk", "signal_name"]].drop_duplicates()
fire_pivot["fired"] = 1
overlap = fire_pivot.pivot_table(index="game_pk", columns="signal_name", values="fired", fill_value=0)

for s1 in SIGNAL_MAP.values():
    if s1 not in overlap.columns:
        continue
    for s2 in SIGNAL_MAP.values():
        if s2 not in overlap.columns or s2 <= s1:
            continue
        both = ((overlap[s1] == 1) & (overlap[s2] == 1)).sum()
        either = ((overlap[s1] == 1) | (overlap[s2] == 1)).sum()
        jaccard = both / either if either > 0 else 0
        print(f"    {s1} ∩ {s2}: {both} games ({jaccard:.0%} Jaccard)")


# ══════════════════════════════════════════════════════════════════════
# PHASE 7-8: Verdicts
# ══════════════════════════════════════════════════════════════════════
print(f"\n\n{'=' * 70}")
print("PHASE 7-8: Verdicts")
print("=" * 70)

results_df = pd.DataFrame(results_table)

# Classification criteria:
# SURVIVES: ALL-years hit rate > 52% AND positive ROI AND stable across seasons
# DIMINISHED: some signal but inconsistent or negative ROI
# COLLAPSES: hit rate <= 50% or large negative ROI
# NEVER-MATCHED: insufficient fires or no edge at all

verdicts = {}
for sig_name in SIGNAL_MAP.values():
    sig_all = results_df[(results_df["signal_name"] == sig_name) & (results_df["season"] == "ALL")]
    if len(sig_all) == 0:
        verdicts[sig_name] = "NEVER-MATCHED"
        continue
    
    row = sig_all.iloc[0]
    n = row["N"]
    hr = row["hit_rate"]
    roi = row["ROI"]
    
    # Season-by-season
    season_rows = results_df[(results_df["signal_name"] == sig_name) & (results_df["season"] != "ALL")]
    season_hrs = season_rows["hit_rate"].dropna().values
    season_rois = season_rows["ROI"].dropna().values
    
    if n < 50:
        verdicts[sig_name] = "NEVER-MATCHED"
        reason = f"Insufficient fires (N={n})"
    elif hr is None or hr <= 0.500:
        verdicts[sig_name] = "COLLAPSES"
        reason = f"Hit rate {hr:.1%} <= 50%"
    elif roi is not None and roi < -0.05:
        verdicts[sig_name] = "COLLAPSES"
        reason = f"ROI {roi:+.1%} deeply negative"
    elif roi is not None and roi > 0.0 and hr > 0.52:
        # Check season stability
        if len(season_hrs) >= 3 and all(h > 0.48 for h in season_hrs if h is not None):
            verdicts[sig_name] = "SURVIVES"
            reason = f"Hit={hr:.1%}, ROI={roi:+.1%}, stable across seasons"
        else:
            verdicts[sig_name] = "DIMINISHED"
            reason = f"Hit={hr:.1%}, ROI={roi:+.1%}, but unstable across seasons"
    elif hr > 0.50:
        verdicts[sig_name] = "DIMINISHED"
        reason = f"Hit={hr:.1%}, ROI={roi:+.1%} — marginal edge"
    else:
        verdicts[sig_name] = "COLLAPSES"
        reason = f"No clear edge"
    
    print(f"\n  {sig_name}: {verdicts[sig_name]}")
    print(f"    N={n}, Hit={hr:.1%}, ROI={roi:+.1%}" if roi is not None else f"    N={n}, Hit={hr:.1%}, ROI=N/A")
    print(f"    Reason: {reason}")
    if len(season_hrs) > 0:
        print(f"    Season hit rates: {[f'{h:.1%}' for h in season_hrs]}")


# ══════════════════════════════════════════════════════════════════════
# OUTPUT: ADJ_FINAL_TABLE.csv
# ══════════════════════════════════════════════════════════════════════
print(f"\n\n{'=' * 70}")
print("OUTPUT: Writing files")
print("=" * 70)

# Add verdicts to results table
results_df["verdict"] = results_df["signal_name"].map(verdicts)
results_df.to_csv(OUT / "ADJ_FINAL_TABLE.csv", index=False)
print(f"  Wrote ADJ_FINAL_TABLE.csv ({len(results_df)} rows)")

# ── Master memo ──────────────────────────────────────────────────────
memo_lines = [
    "# ADJ Standalone Signal — Keep/Kill Memo",
    "",
    "## Live Code Identity",
    "- Source: `mlb_sim/pipeline/shadow_signals.py`",
    "- Feature source: `research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet`",
    "- Features: per-start, shift(1) lagged rolling(3, min_periods=2) of opponent-adjusted metrics",
    "- Gate: `combined = (home_val + away_val) / 2; favorable = combined > 0`",
    "- V1 p_under: logged as context ONLY, does NOT gate firing",
    "- Direction: UNDER when favorable_zone_flag = True",
    "",
    "## Key Difference from Old Research",
    "- Old scanner required V1 p_under > 0.57 as co-filter (interaction signal)",
    "- Live standalone fires on combined > 0 alone (no V1 gate)",
    "- This means more fires but potentially lower precision vs original scanner results",
    "",
    "## Backtest Methodology",
    "- Period: 2022-2025 regular season",
    "- Starter identification: pitcher_game_logs.parquet (starter_flag=1)",
    "- Feature lookup: most recent prf row where prf.game_date < game.date (no lookahead)",
    "- Closing odds: mlb_odds_closing_canonical.parquet (last pull per game)",
    "- ROI: flat $1 bet at actual closing under price",
    "",
    "## Signal Verdicts",
    "",
]

for sig_name in SIGNAL_MAP.values():
    v = verdicts.get(sig_name, "UNKNOWN")
    sig_all = results_df[(results_df["signal_name"] == sig_name) & (results_df["season"] == "ALL")]
    if len(sig_all) > 0:
        row = sig_all.iloc[0]
        memo_lines.append(f"### {sig_name}: **{v}**")
        memo_lines.append(f"- N={row['N']}, Hit={row['hit_rate']:.1%}, ROI={row['ROI']:+.1%}" 
                         if row['ROI'] is not None else
                         f"- N={row['N']}, Hit={row['hit_rate']:.1%}, ROI=N/A")
        # Season breakdown
        for s in [2022, 2023, 2024, 2025]:
            sr = results_df[(results_df["signal_name"] == sig_name) & (results_df["season"] == s)]
            if len(sr) > 0:
                r = sr.iloc[0]
                memo_lines.append(f"  - {s}: N={r['N']}, Hit={r['hit_rate']:.1%}, ROI={r['ROI']:+.1%}"
                                 if r['ROI'] is not None else
                                 f"  - {s}: N={r['N']}, Hit={r['hit_rate']:.1%}, ROI=N/A")
    else:
        memo_lines.append(f"### {sig_name}: **{v}**")
        memo_lines.append("- No fires")
    memo_lines.append("")

# Final recommendation
memo_lines.extend([
    "## Recommendation",
    "",
])

surviving = [s for s, v in verdicts.items() if v == "SURVIVES"]
diminished = [s for s, v in verdicts.items() if v == "DIMINISHED"]
collapsed = [s for s, v in verdicts.items() if v == "COLLAPSES"]

if surviving:
    memo_lines.append(f"**KEEP**: {', '.join(surviving)}")
if diminished:
    memo_lines.append(f"**MONITOR**: {', '.join(diminished)} — continue shadow, do not weight in overlay")
if collapsed:
    memo_lines.append(f"**KILL**: {', '.join(collapsed)} — no standalone edge, remove from shadow")

memo_text = "\n".join(memo_lines)
(OUT / "ADJ_MASTER_KEEP_KILL_MEMO.md").write_text(memo_text)
print(f"  Wrote ADJ_MASTER_KEEP_KILL_MEMO.md")

print(f"\n\n{'=' * 70}")
print("SUMMARY")
print("=" * 70)
for sig_name in SIGNAL_MAP.values():
    v = verdicts.get(sig_name, "UNKNOWN")
    sig_all = results_df[(results_df["signal_name"] == sig_name) & (results_df["season"] == "ALL")]
    if len(sig_all) > 0:
        row = sig_all.iloc[0]
        roi_str = f"ROI={row['ROI']:+.1%}" if row['ROI'] is not None else "ROI=N/A"
        print(f"  {sig_name:<20}: {v:<15} N={row['N']:>4}  Hit={row['hit_rate']:.1%}  {roi_str}")
    else:
        print(f"  {sig_name:<20}: {v}")

print("\nDone.")
