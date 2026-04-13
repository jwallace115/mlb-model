#!/usr/bin/env python3
"""
MLB TOTALS P1B — Cold-Climate Warm-Day Child Object
Discovery 2023 / Validation 2024 / OOS 2025
"""
import pandas as pd, numpy as np, os, json, warnings
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

# ── Join ───────────────────────────────────────────────────────────────────
gt["game_pk"] = gt["game_pk"].astype(str)
canon["game_pk"] = canon["game_pk"].astype(str)
f5_canon["game_id"] = f5_canon["game_id"].astype(str)

df = gt.merge(canon[["game_pk", "total_line", "total_over_price", "total_under_price"]],
              on="game_pk", how="inner")
df = df.merge(f5_canon, left_on="game_pk", right_on="game_id", how="inner")
print(f"Joined (gt+canon+f5): {len(df)} rows")

# ── Compute F5 ratio + EARLY_HEAVY threshold from 2023 discovery ──────────
df["f5_ratio"] = df["f5_total"] / df["total_line"]
disc_2023 = df[df["season"] == 2023]
f5r_p67 = disc_2023["f5_ratio"].quantile(0.67)
print(f"2023 f5_ratio p67 (EARLY_HEAVY threshold): {f5r_p67:.4f}")

df["early_heavy"] = df["f5_ratio"] > f5r_p67

# ── Cold-climate outdoor parks (geographic definition) ─────────────────────
# North of ~40°N, outdoor stadiums only (roof_status == "open")
# Exclude dome/retractable: MIL, HOU, ARI, TOR, MIA, TEX, TBR
COLD_CLIMATE_OUTDOOR = {
    "BOS", "NYY", "NYM", "CHC", "CHW", "CLE", "DET", "PIT",
    "PHI", "BAL", "WSN", "CIN", "COL", "SFG", "SEA", "KCR", "STL", "MIN",
}
# Verify all are actually "open" roof_status
outdoor_check = gt.groupby("home_team")["roof_status"].apply(lambda x: x.mode()[0]).to_dict()
verified = {t for t in COLD_CLIMATE_OUTDOOR if outdoor_check.get(t) == "open"}
excluded = COLD_CLIMATE_OUTDOOR - verified
if excluded:
    print(f"WARNING: excluded from cold set (not outdoor): {excluded}")
COLD_CLIMATE_OUTDOOR = verified
print(f"Cold-climate outdoor parks: {sorted(COLD_CLIMATE_OUTDOOR)}")

df["cold_park"] = df["home_team"].isin(COLD_CLIMATE_OUTDOOR)
df["date_dt"] = pd.to_datetime(df["date"])
df["month"] = df["date_dt"].dt.month
df["jun_sep"] = df["month"].between(6, 9)
df["warm_day"] = df["temperature"] >= 75
df["actual_total"] = df["home_score"] + df["away_score"]
df["over_result"] = (df["actual_total"] > df["total_line"]).astype(int)
df["push"] = (df["actual_total"] == df["total_line"])
df["juiced_over"] = df["total_over_price"] <= -105

# ── Diagnostics: how many pass each filter ─────────────────────────────────
print(f"\n── Filter funnel (all years) ──")
print(f"All joined games:           {len(df)}")
print(f"  cold_park:                {df['cold_park'].sum()}")
print(f"  cold_park + jun_sep:      {(df['cold_park'] & df['jun_sep']).sum()}")
print(f"  + warm_day (>=75F):       {(df['cold_park'] & df['jun_sep'] & df['warm_day']).sum()}")
print(f"  + early_heavy:            {(df['cold_park'] & df['jun_sep'] & df['warm_day'] & df['early_heavy']).sum()}")
print(f"  + juiced_over (<=−105):   {(df['cold_park'] & df['jun_sep'] & df['warm_day'] & df['early_heavy'] & df['juiced_over']).sum()}")

# ── Also check without warm_day to see full cold-park population ──────────
cold_jun_sep = df[df["cold_park"] & df["jun_sep"] & ~df["push"]]
print(f"\n── Temperature distribution at cold parks, Jun-Sep ──")
print(f"  N={len(cold_jun_sep)}")
print(f"  temp percentiles: {cold_jun_sep['temperature'].describe().to_dict()}")
print(f"  >=75F: {(cold_jun_sep['temperature'] >= 75).sum()}")
print(f"  >=70F: {(cold_jun_sep['temperature'] >= 70).sum()}")
print(f"  >=65F: {(cold_jun_sep['temperature'] >= 65).sum()}")

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
                "clv": np.nan, "avg_implied": np.nan}
    wins = int(subset["over_result"].sum())
    losses = len(subset) - wins
    win_pct = wins / len(subset)
    avg_price = subset["total_over_price"].mean()
    
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
            "win_pct": round(win_pct, 4), "avg_price": round(avg_price, 1),
            "roi": round(roi, 2), "clv": round(clv, 4), "avg_implied": round(avg_implied, 4)}

stats = []
for sub, lbl in [(disc, "Discovery 2023"), (val, "Validation 2024"), 
                  (oos, "OOS 2025"), (child_nopush, "ALL")]:
    s = compute_stats(sub, lbl)
    stats.append(s)
    if s["N"] > 0:
        print(f"\n{lbl}:")
        print(f"  N={s['N']}, W={s['wins']}, L={s['losses']}")
        print(f"  Win%={s['win_pct']:.4f}, Implied%={s['avg_implied']:.4f}")
        print(f"  ROI={s['roi']:+.2f}%, CLV={s['clv']:+.4f}")
        print(f"  Avg price={s['avg_price']:.1f}")
    else:
        print(f"\n{lbl}: N=0")

# ── Fragility checks ──────────────────────────────────────────────────────
if len(child_nopush) > 0:
    print(f"\n{'='*60}")
    print("FRAGILITY ANALYSIS")
    print(f"{'='*60}")

    print("\nBy park (all years, graded):")
    for park in sorted(child_nopush["home_team"].unique()):
        sub = child_nopush[child_nopush["home_team"] == park]
        s = compute_stats(sub, park)
        print(f"  {park}: N={s['N']:3d}, Win%={s['win_pct']:.4f}, ROI={s['roi']:+.2f}%")

    print("\nBy temperature band (all years, graded):")
    for lo, hi, lbl in [(75, 80, "75-79F"), (80, 85, "80-84F"), (85, 90, "85-89F"), (90, 120, "90F+")]:
        sub = child_nopush[(child_nopush["temperature"] >= lo) & (child_nopush["temperature"] < hi)]
        if len(sub) > 0:
            s = compute_stats(sub, lbl)
            print(f"  {lbl}: N={s['N']:3d}, Win%={s['win_pct']:.4f}, ROI={s['roi']:+.2f}%")

    print("\nBy month (all years, graded):")
    for m in [6, 7, 8, 9]:
        sub = child_nopush[child_nopush["month"] == m]
        if len(sub) > 0:
            s = compute_stats(sub, m)
            print(f"  Month {m}: N={s['N']:3d}, Win%={s['win_pct']:.4f}, ROI={s['roi']:+.2f}%")

# ── Baseline: cold + warm + juiced WITHOUT early_heavy ────────────────────
baseline_mask = df["cold_park"] & df["warm_day"] & df["jun_sep"] & df["juiced_over"] & ~df["push"]
baseline = df[baseline_mask]
print(f"\n{'='*60}")
print("BASELINE (cold park + warm day + juiced, NO early_heavy filter)")
print(f"{'='*60}")
for yr in [2023, 2024, 2025]:
    sub = baseline[baseline["season"] == yr]
    s = compute_stats(sub, f"Baseline {yr}")
    if s["N"] > 0:
        print(f"  {s['label']}: N={s['N']:3d}, Win%={s['win_pct']:.4f}, ROI={s['roi']:+.2f}%")
    else:
        print(f"  Baseline {yr}: N=0")
s_all = compute_stats(baseline, "Baseline ALL")
if s_all["N"] > 0:
    print(f"  ALL: N={s_all['N']:3d}, Win%={s_all['win_pct']:.4f}, ROI={s_all['roi']:+.2f}%")

# ── Also check: relax early_heavy, just cold+warm+juiced over result ──────
print(f"\n{'='*60}")
print("EXPANDED: cold + Jun-Sep + juiced (no temp or EH filter)")
print(f"{'='*60}")
exp_mask = df["cold_park"] & df["jun_sep"] & df["juiced_over"] & ~df["push"]
exp = df[exp_mask]
for yr in [2023, 2024, 2025]:
    sub = exp[exp["season"] == yr]
    s = compute_stats(sub, f"Expanded {yr}")
    if s["N"] > 0:
        print(f"  {s['label']}: N={s['N']:3d}, Win%={s['win_pct']:.4f}, ROI={s['roi']:+.2f}%")

# ── Save CSV ──────────────────────────────────────────────────────────────
out_cols = ["game_pk", "date", "season", "home_team", "away_team",
            "temperature", "total_line", "f5_total", "f5_ratio",
            "total_over_price", "actual_total", "over_result",
            "month", "early_heavy", "cold_park", "warm_day"]
if len(child_nopush) > 0:
    child_nopush[out_cols].to_csv(f"{OUT}/p1b_child_table.csv", index=False)
    print(f"\nSaved: {OUT}/p1b_child_table.csv")

pd.DataFrame(stats).to_csv(f"{OUT}/p1b_stats.csv", index=False)

# ── Decision ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("DECISION")
print(f"{'='*60}")

disc_s = stats[0]
val_s = stats[1]
oos_s = stats[2]

if disc_s["N"] < 30:
    decision = "TOO_THIN"
    print(f"TOO THIN: Discovery N={disc_s['N']} < 30 minimum")
elif disc_s["roi"] > 0 and val_s["N"] > 0 and val_s["roi"] > 0 and oos_s["N"] > 0 and oos_s["roi"] > 0:
    decision = "CANDIDATE"
    print("ALL THREE PERIODS POSITIVE — candidate for shadow deployment")
elif disc_s["roi"] > 0 and val_s["N"] > 0 and val_s["roi"] > 0:
    decision = "MONITOR"
    print("Discovery + Validation positive, OOS negative — MONITOR")
else:
    decision = "NO_DEPLOY"
    print("Signal does not persist — NO DEPLOY")

meta = {
    "f5r_p67": float(f5r_p67),
    "cold_parks": sorted(list(COLD_CLIMATE_OUTDOOR)),
    "decision": decision,
    "disc_n": int(disc_s["N"]), "val_n": int(val_s["N"]), "oos_n": int(oos_s["N"]),
}
with open(f"{OUT}/p1b_meta.json", "w") as f:
    json.dump(meta, f, indent=2)

print(f"\nDone. All output in {OUT}/")
