#!/usr/bin/env python3
"""
MLB TOTALS P1B — Cold-Climate Warm-Day Child Object
Discovery 2023 / Validation 2024 / OOS 2025
"""
import pandas as pd, numpy as np, os, sys, warnings
warnings.filterwarnings("ignore")

OUT = "/root/mlb-model/research/recovery/mlb_totals_p1b_coldwarm_child"

# ── Load data ──────────────────────────────────────────────────────────────
gt = pd.read_parquet("/root/mlb-model/sim/data/game_table.parquet")
canon = pd.read_parquet("/root/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet")
f5 = pd.read_parquet("/root/mlb-model/mlb_sim_f5/data/f5_lines_historical.parquet")
f5_canon = f5[f5["is_canonical"] == True][["game_id", "f5_total"]].drop_duplicates(subset=["game_id"])

print(f"game_table: {len(gt)} rows, seasons: {sorted(gt['season'].unique())}")
print(f"canon: {len(canon)} rows")
print(f"f5_canon: {len(f5_canon)} rows")
print(f"F5 by year: {f5_canon['game_id'].astype(str).str[:4].value_counts().sort_index().to_dict()}")

# ── Join ───────────────────────────────────────────────────────────────────
gt["game_pk"] = gt["game_pk"].astype(str)
canon["game_pk"] = canon["game_pk"].astype(str)
f5_canon["game_id"] = f5_canon["game_id"].astype(str)

df = gt.merge(canon[["game_pk", "total_line", "total_over_price", "total_under_price"]],
              on="game_pk", how="inner")
df = df.merge(f5_canon, left_on="game_pk", right_on="game_id", how="inner")
print(f"\nJoined (gt+canon+f5): {len(df)} rows")

# ── Compute F5 ratio + EARLY_HEAVY threshold from 2023 discovery ──────────
df["f5_ratio"] = df["f5_total"] / df["total_line"]
disc_2023 = df[df["season"] == 2023]
f5r_p67 = disc_2023["f5_ratio"].quantile(0.67)
print(f"\n2023 discovery f5_ratio p67 (EARLY_HEAVY threshold): {f5r_p67:.4f}")

df["early_heavy"] = df["f5_ratio"] > f5r_p67

# ── Cold-climate outdoor parks (geographic definition) ─────────────────────
# North of ~40°N, outdoor stadiums. Exclude dome/retractable.
# Check roof_status in game_table to verify outdoor classification
print("\n── Roof status by home_team ──")
roof_teams = gt.groupby(["home_team", "roof_status"]).size().reset_index(name="n")
print(roof_teams.to_string(index=False))

# Define cold-climate teams with OUTDOOR parks only
# Using game_table roof_status to confirm
outdoor_check = gt.groupby("home_team")["roof_status"].apply(
    lambda x: x.mode()[0] if len(x) > 0 else "unknown"
).to_dict()
print("\n── Modal roof status per team ──")
for t, r in sorted(outdoor_check.items()):
    print(f"  {t}: {r}")

# Cold-climate outdoor: north of ~40°N, modal roof_status = "outdoor"
COLD_CLIMATE_OUTDOOR = set()
COLD_CANDIDATES = {
    "BOS", "NYY", "NYM", "CHC", "CHW", "CLE", "DET", "PIT",
    "PHI", "BAL", "WSH", "CIN", "COL", "SF", "SEA", "KC", "STL", "MIN",
    # Also check alternate abbreviations
    "SFG", "KCR", "WSN",
}
for t in COLD_CANDIDATES:
    if outdoor_check.get(t, "unknown") == "outdoor":
        COLD_CLIMATE_OUTDOOR.add(t)

print(f"\nCold-climate outdoor parks: {sorted(COLD_CLIMATE_OUTDOOR)}")

df["cold_park"] = df["home_team"].isin(COLD_CLIMATE_OUTDOOR)
df["date_dt"] = pd.to_datetime(df["date"])
df["month"] = df["date_dt"].dt.month
df["jun_sep"] = df["month"].between(6, 9)
df["warm_day"] = df["temperature"] >= 75
df["actual_total"] = df["home_score"] + df["away_score"]
df["over_result"] = (df["actual_total"] > df["total_line"]).astype(int)
df["push"] = (df["actual_total"] == df["total_line"])
df["juiced_over"] = df["total_over_price"] <= -105

# ── Filter to child object universe ───────────────────────────────────────
mask = (
    df["cold_park"] &
    df["warm_day"] &
    df["jun_sep"] &
    df["early_heavy"] &
    df["juiced_over"]
)
child = df[mask].copy()
child_nopush = child[~child["push"]].copy()

print(f"\n{'='*60}")
print("CHILD OBJECT UNIVERSE")
print(f"{'='*60}")
print(f"Total qualifying games: {len(child)}")
print(f"  Pushes: {child['push'].sum()}")
print(f"  Graded (no push): {len(child_nopush)}")
print(f"  By year: {child_nopush.groupby('season').size().to_dict()}")

# ── Splits ─────────────────────────────────────────────────────────────────
disc = child_nopush[child_nopush["season"] == 2023]
val  = child_nopush[child_nopush["season"] == 2024]
oos  = child_nopush[child_nopush["season"] == 2025]

print(f"\nDiscovery 2023: N={len(disc)}")
print(f"Validation 2024: N={len(val)}")
print(f"OOS 2025: N={len(oos)}")

def compute_stats(subset, label):
    if len(subset) == 0:
        return {"label": label, "N": 0, "wins": 0, "losses": 0,
                "win_pct": np.nan, "avg_price": np.nan, "roi": np.nan,
                "clv": np.nan}
    wins = subset["over_result"].sum()
    losses = len(subset) - wins
    win_pct = wins / len(subset)
    avg_price = subset["total_over_price"].mean()
    
    # ROI: unit bet on over at closing price
    profit = 0
    for _, row in subset.iterrows():
        price = row["total_over_price"]
        if row["over_result"] == 1:
            if price > 0:
                profit += price / 100
            else:
                profit += 100 / abs(price)
        else:
            profit -= 1
    roi = profit / len(subset) * 100
    
    # CLV: compare over_result rate to implied prob from price
    implied_probs = []
    for _, row in subset.iterrows():
        p = row["total_over_price"]
        if p < 0:
            implied_probs.append(abs(p) / (abs(p) + 100))
        else:
            implied_probs.append(100 / (p + 100))
    avg_implied = np.mean(implied_probs)
    clv = win_pct - avg_implied
    
    return {"label": label, "N": len(subset), "wins": wins, "losses": losses,
            "win_pct": win_pct, "avg_price": avg_price, "roi": roi,
            "clv": clv, "avg_implied": avg_implied}

stats = []
for sub, lbl in [(disc, "Discovery 2023"), (val, "Validation 2024"), 
                  (oos, "OOS 2025"), (child_nopush, "ALL")]:
    s = compute_stats(sub, lbl)
    stats.append(s)
    print(f"\n{lbl}:")
    print(f"  N={s['N']}, W={s['wins']}, L={s['losses']}")
    print(f"  Win%={s['win_pct']:.3f}, Implied%={s.get('avg_implied', np.nan):.3f}")
    print(f"  ROI={s['roi']:.1f}%, CLV={s['clv']:.3f}")
    print(f"  Avg price={s['avg_price']:.0f}")

# ── Fragility checks ──────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("FRAGILITY ANALYSIS")
print(f"{'='*60}")

# By park
print("\nBy park (all years, graded):")
for park in sorted(child_nopush["home_team"].unique()):
    sub = child_nopush[child_nopush["home_team"] == park]
    s = compute_stats(sub, park)
    print(f"  {park}: N={s['N']:3d}, Win%={s['win_pct']:.3f}, ROI={s['roi']:+.1f}%")

# Temperature bands
print("\nBy temperature band (all years, graded):")
for lo, hi, lbl in [(75, 80, "75-79F"), (80, 85, "80-84F"), (85, 100, "85F+")]:
    sub = child_nopush[(child_nopush["temperature"] >= lo) & (child_nopush["temperature"] < hi)]
    if len(sub) > 0:
        s = compute_stats(sub, lbl)
        print(f"  {lbl}: N={s['N']:3d}, Win%={s['win_pct']:.3f}, ROI={s['roi']:+.1f}%")

# By month
print("\nBy month (all years, graded):")
for m in [6, 7, 8, 9]:
    sub = child_nopush[child_nopush["month"] == m]
    if len(sub) > 0:
        s = compute_stats(sub, lbl)
        print(f"  Month {m}: N={s['N']:3d}, Win%={s['win_pct']:.3f}, ROI={s['roi']:+.1f}%")

# ── Baseline comparison (cold park + warm day WITHOUT early_heavy) ────────
baseline_mask = df["cold_park"] & df["warm_day"] & df["jun_sep"] & df["juiced_over"] & ~df["push"]
baseline = df[baseline_mask]
baseline_disc = baseline[baseline["season"] == 2023]
baseline_val = baseline[baseline["season"] == 2024]
baseline_oos = baseline[baseline["season"] == 2025]

print(f"\n{'='*60}")
print("BASELINE (cold park + warm day + juiced, NO early_heavy filter)")
print(f"{'='*60}")
for sub, lbl in [(baseline_disc, "Baseline 2023"), (baseline_val, "Baseline 2024"),
                  (baseline_oos, "Baseline 2025"), (baseline, "Baseline ALL")]:
    s = compute_stats(sub, lbl)
    print(f"  {lbl}: N={s['N']:3d}, Win%={s['win_pct']:.3f}, ROI={s['roi']:+.1f}%")

# ── Save CSV ──────────────────────────────────────────────────────────────
out_cols = ["game_pk", "date", "season", "home_team", "away_team",
            "temperature", "total_line", "f5_total", "f5_ratio",
            "total_over_price", "actual_total", "over_result",
            "month", "early_heavy", "cold_park", "warm_day"]
child_nopush[out_cols].to_csv(f"{OUT}/p1b_child_table.csv", index=False)
print(f"\nSaved: {OUT}/p1b_child_table.csv")

# ── Save stats for report ─────────────────────────────────────────────────
pd.DataFrame(stats).to_csv(f"{OUT}/p1b_stats.csv", index=False)

# ── Decision ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("DECISION")
print(f"{'='*60}")

thin = len(disc) < 30
disc_s = stats[0]
val_s = stats[1]
oos_s = stats[2]

if thin:
    print(f"TOO THIN: Discovery N={len(disc)} < 30 minimum")
    print("Cannot draw reliable conclusions from this sample size.")
    decision = "TOO_THIN"
elif disc_s["roi"] > 0 and val_s["roi"] > 0 and oos_s["roi"] > 0:
    print("ALL THREE PERIODS POSITIVE — candidate for shadow deployment")
    decision = "CANDIDATE"
elif disc_s["roi"] > 0 and val_s["roi"] > 0:
    print("Discovery + Validation positive, OOS negative — MONITOR")
    decision = "MONITOR"
else:
    print("Signal does not persist — NO DEPLOY")
    decision = "NO_DEPLOY"

# Store for report
import json
meta = {
    "f5r_p67": float(f5r_p67),
    "cold_parks": sorted(list(COLD_CLIMATE_OUTDOOR)),
    "decision": decision,
    "disc_n": len(disc), "val_n": len(val), "oos_n": len(oos),
}
with open(f"{OUT}/p1b_meta.json", "w") as f:
    json.dump(meta, f, indent=2)

print(f"\nDone. All output in {OUT}/")
