#!/usr/bin/env python3
"""
TB Props Market Efficiency Study.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent

def pnl(odds, won):
    """Compute P&L for a single bet at American odds."""
    if odds > 0: return odds / 100 if won else -1.0
    return 100 / abs(odds) if won else -1.0

def roi(pnls):
    if len(pnls) == 0: return np.nan
    return np.mean(pnls) * 100

# ── Load raw props ────────────────────────────────────────────────────
raw = pd.read_parquet(BASE / "tb_props_raw.parquet")
raw["game_date"] = pd.to_datetime(raw["game_date"])
print(f"Raw TB props: {len(raw)} records")
print(f"Date range: {raw.game_date.min().date()} to {raw.game_date.max().date()}")
print(f"By line: {raw.line.value_counts().sort_index().to_dict()}")
print(f"By book: {raw.book.value_counts().to_dict()}")

# ── Load actual outcomes ──────────────────────────────────────────────
lu = pd.read_parquet(BASE.parent.parent / "mlb_v3_lineup_model" / "historical_lineups_long.parquet")
lu["game_date"] = pd.to_datetime(lu["game_date"])
# Compute actual total bases
lu["actual_tb"] = (lu["h"] - lu["doubles"] - lu["triples"] - lu["hr"]) + \
                   lu["doubles"]*2 + lu["triples"]*3 + lu["hr"]*4

# Normalize player names for joining
def norm_name(s):
    if not isinstance(s, str): return ""
    s = s.strip().lower()
    # Remove accents (simple approach)
    for old, new in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n"),("ü","u")]:
        s = s.replace(old, new)
    # Remove Jr., Sr., III, II suffixes for matching
    for suffix in [" jr.", " sr.", " iii", " ii", " iv"]:
        s = s.replace(suffix, "")
    return s.strip()

raw["name_norm"] = raw["player_name"].apply(norm_name)
lu["name_norm"] = lu["player_name"].apply(norm_name)

# Join
# One prop record per player-line-game; one outcome per player-game
outcomes = lu[["game_pk", "game_date", "name_norm", "player_name", "actual_tb",
               "team", "batting_order_slot", "home_away", "opponent",
               "ab", "h", "doubles", "triples", "hr", "pa"]].copy()
outcomes = outcomes.rename(columns={"game_pk": "game_pk_out", "player_name": "player_name_out"})

# Merge by name + date
merged = raw.merge(outcomes, left_on=["name_norm", "game_date"],
                    right_on=["name_norm", "game_date"], how="left")

join_rate = merged["actual_tb"].notna().mean()
print(f"\nJoin rate: {join_rate:.1%} ({merged['actual_tb'].notna().sum()}/{len(merged)})")

# Show top unmatched
unmatched = merged[merged["actual_tb"].isna()]["player_name"].value_counts().head(20)
print(f"\nTop unmatched players:")
for name, count in unmatched.items():
    print(f"  {name}: {count}")

# Filter to matched
df = merged[merged["actual_tb"].notna()].copy()

# Compute outcomes
df["over_hit"] = (df["actual_tb"] > df["line"]).astype(int)
df["under_hit"] = (df["actual_tb"] < df["line"]).astype(int)
df["push"] = (df["actual_tb"] == df["line"]).astype(int)
df["over_pnl"] = df.apply(lambda r: pnl(r["over_odds"], r["over_hit"] == 1)
                           if pd.notna(r.get("over_odds")) and r["push"] == 0 else 0.0, axis=1)
df["under_pnl"] = df.apply(lambda r: pnl(r["under_odds"], r["under_hit"] == 1)
                            if pd.notna(r.get("under_odds")) and r["push"] == 0 else 0.0, axis=1)

df.to_parquet(BASE / "tb_props_dataset.parquet", index=False)
print(f"\nFinal dataset: {len(df)} matched props")
print(f"Push rate: {df['push'].mean():.1%}")

# =====================================================================
# STEP 3A — EFFICIENCY BY LINE
# =====================================================================
print("\n" + "="*60)
print("3A — EFFICIENCY BY LINE VALUE")
print("="*60)

results_3a = []
for line_val in sorted(df["line"].unique()):
    sub = df[(df["line"] == line_val) & (df["push"] == 0)]
    if len(sub) < 50: continue
    actual_over = sub["over_hit"].mean()
    implied_over = sub["implied_over"].mean()
    edge = actual_over - implied_over
    over_roi = roi(sub["over_pnl"])
    under_roi = roi(sub["under_pnl"])
    results_3a.append({
        "line": line_val, "N": len(sub),
        "actual_over": actual_over, "implied_over": implied_over,
        "edge": edge, "over_roi": over_roi, "under_roi": under_roi,
    })
    flag = " *** INEFFICIENT" if abs(edge) > 0.03 else ""
    print(f"  Line {line_val}: N={len(sub)}, actual_over={actual_over:.3f}, "
          f"implied={implied_over:.3f}, edge={edge:+.3f}, "
          f"over_ROI={over_roi:+.1f}%, under_ROI={under_roi:+.1f}%{flag}")

# By time window
for label, mask in [("Apr 2025", (df.game_date.dt.month == 4) & (df.season == 2025)),
                     ("Sep 2025", (df.game_date.dt.month == 9) & (df.season == 2025)),
                     ("Mar 2026", df.season == 2026)]:
    sub = df[mask & (df.line == 1.5) & (df.push == 0)]
    if len(sub) < 30: continue
    actual_over = sub["over_hit"].mean()
    implied_over = sub["implied_over"].mean()
    edge = actual_over - implied_over
    over_roi = roi(sub["over_pnl"])
    print(f"  O/U 1.5 {label}: N={len(sub)}, actual={actual_over:.3f}, "
          f"implied={implied_over:.3f}, edge={edge:+.3f}, over_ROI={over_roi:+.1f}%")

# =====================================================================
# 3B — BY BATTER PROFILE
# =====================================================================
print("\n" + "="*60)
print("3B — BY BATTER PROFILE")
print("="*60)

sub15 = df[(df.line == 1.5) & (df.push == 0)].copy()
for split_name, col, groups in [
    ("Order slot", "batting_order_slot",
     [("1-4", sub15.batting_order_slot <= 4), ("5-9", sub15.batting_order_slot > 4)]),
    ("Home/Away", "home_away",
     [("home", sub15.home_away == "home"), ("away", sub15.home_away == "away")]),
]:
    print(f"\n  {split_name}:")
    for label, mask in groups:
        s = sub15[mask]
        if len(s) < 50: continue
        actual = s.over_hit.mean()
        implied = s.implied_over.mean()
        edge = actual - implied
        r = roi(s.over_pnl)
        print(f"    {label}: N={len(s)}, actual={actual:.3f}, implied={implied:.3f}, "
              f"edge={edge:+.3f}, over_ROI={r:+.1f}%")

# =====================================================================
# 3D — INTERACTION TEST
# =====================================================================
print("\n" + "="*60)
print("3D — INTERACTION: HIGH ISO × HR PARK")
print("="*60)

# We don't have per-player ISO in the prop dataset, but we have actual TB
# Use batting_order_slot as power proxy (slots 1-4 are power hitters usually)
# and park from game context
gt = pd.read_parquet(BASE.parent.parent.parent / "sim" / "data" / "game_table.parquet")
gt["date"] = pd.to_datetime(gt["date"])
park_hr = gt[gt.season.isin([2025, 2026])].groupby("home_team")["park_factor_hr"].first()

sub15["park_hr"] = sub15["home_team"].map(park_hr)
sub15["power_hitter"] = sub15["batting_order_slot"] <= 4
sub15["hr_park"] = sub15["park_hr"] > sub15["park_hr"].quantile(0.67)

for label, mask in [
    ("Power hitter + HR park", sub15.power_hitter & sub15.hr_park),
    ("Power hitter + non-HR park", sub15.power_hitter & ~sub15.hr_park),
    ("Non-power + HR park", ~sub15.power_hitter & sub15.hr_park),
    ("Non-power + non-HR park", ~sub15.power_hitter & ~sub15.hr_park),
]:
    s = sub15[mask]
    if len(s) < 50: continue
    actual = s.over_hit.mean()
    implied = s.implied_over.mean()
    edge = actual - implied
    r = roi(s.over_pnl)
    print(f"  {label}: N={len(s)}, actual={actual:.3f}, implied={implied:.3f}, "
          f"edge={edge:+.3f}, over_ROI={r:+.1f}%")

# =====================================================================
# STEP 4 — DISTRIBUTION
# =====================================================================
print("\n" + "="*60)
print("STEP 4 — TB DISTRIBUTION")
print("="*60)

for tb_val in range(5):
    pct = (df.actual_tb == tb_val).mean()
    print(f"  P(TB={tb_val}): {pct:.3f}")
pct4 = (df.actual_tb >= 4).mean()
print(f"  P(TB>=4): {pct4:.3f}")
print(f"  Mean TB: {df.actual_tb.mean():.3f}")
print(f"  Var TB: {df.actual_tb.var():.3f}")

# Compare to Poisson
from scipy.stats import poisson
mu = df.actual_tb.mean()
print(f"\n  Poisson({mu:.3f}) comparison:")
for tb_val in range(5):
    print(f"    P(TB={tb_val}): actual={((df.actual_tb == tb_val).mean()):.3f}, "
          f"poisson={poisson.pmf(tb_val, mu):.3f}")

# =====================================================================
# WRITE REPORTS
# =====================================================================
print("\n" + "="*60)
print("WRITING REPORTS")
print("="*60)

# Efficiency report
R = []
R.append("# TB Props Market Efficiency Report")
R.append("")
R.append(f"Dataset: {len(df)} matched TB prop records")
R.append(f"Raw pulled: {len(raw)} records, join rate: {join_rate:.1%}")
R.append(f"Date range: {df.game_date.min().date()} to {df.game_date.max().date()}")
R.append(f"Credits used: ~9,153")
R.append("")

R.append("## Overall Efficiency by Line")
R.append("")
R.append("| Line | N | Actual Over% | Implied Over% | Edge | Over ROI | Under ROI |")
R.append("|------|---|-------------|--------------|------|----------|-----------|")
for r in results_3a:
    flag = " **" if abs(r["edge"]) > 0.03 else ""
    R.append(f"| {r['line']} | {r['N']} | {r['actual_over']:.3f} | {r['implied_over']:.3f} | "
             f"{r['edge']:+.3f}{flag} | {r['over_roi']:+.1f}% | {r['under_roi']:+.1f}% |")
R.append("")

R.append("## TB Distribution")
R.append("")
R.append("| TB | Actual | Poisson |")
R.append("|----|--------|---------|")
for tb_val in range(5):
    actual = (df.actual_tb == tb_val).mean()
    poiss = poisson.pmf(tb_val, mu)
    R.append(f"| {tb_val} | {actual:.3f} | {poiss:.3f} |")
R.append(f"| 4+ | {pct4:.3f} | {1-poisson.cdf(3, mu):.3f} |")
R.append(f"\nMean: {mu:.3f}, Variance: {df.actual_tb.var():.3f} (Poisson var would be {mu:.3f})")
R.append(f"Variance/Mean ratio: {df.actual_tb.var()/mu:.2f} (>1 = overdispersed)")
R.append("")

# Verdict
best_edge = max(results_3a, key=lambda r: abs(r["edge"]))
any_inefficient = any(abs(r["edge"]) > 0.03 for r in results_3a)

R.append("## Verdict")
R.append("")
if any_inefficient:
    R.append("**INVESTIGATE** — pricing inefficiencies detected at one or more line values.")
    R.append(f"Largest edge: line {best_edge['line']}, edge={best_edge['edge']:+.3f}")
else:
    R.append("**Market appears efficient** — no line shows edge > 3pp.")
R.append("")

out = BASE / "tb_efficiency_report.md"
with open(out, "w") as f:
    f.write("\n".join(R) + "\n")

# Coverage report
C = [
    "# TB Dataset Coverage", "",
    f"Raw records pulled: {len(raw)}",
    f"Matched with outcomes: {len(df)} ({join_rate:.1%} join rate)",
    f"Credits used: ~9,153",
    f"Credits remaining: ~3,991,500",
    "",
    f"## By date window",
    f"- April 2025: {len(df[(df.game_date.dt.month <= 4) & (df.season == 2025)])}",
    f"- Aug-Oct 2025: {len(df[(df.game_date.dt.month >= 8) & (df.season == 2025)])}",
    f"- March 2026: {len(df[df.season == 2026])}",
    "",
    f"## Line distribution",
]
for line_val, count in df.line.value_counts().sort_index().items():
    C.append(f"- Line {line_val}: {count} ({100*count/len(df):.1f}%)")
C.extend([
    "",
    f"## Book distribution",
])
for book, count in df.book.value_counts().items():
    C.append(f"- {book}: {count}")

with open(BASE / "tb_dataset_coverage.md", "w") as f:
    f.write("\n".join(C) + "\n")

print(f"Saved efficiency report and coverage report")
