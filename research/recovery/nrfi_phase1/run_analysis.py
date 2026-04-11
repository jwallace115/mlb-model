#!/usr/bin/env python3
"""NRFI Phase 1 — Full analysis on fixed data."""
import pandas as pd
import numpy as np

OUT = "/root/mlb-model/research/recovery/nrfi_phase1"
df = pd.read_parquet(f"{OUT}/nrfi_research_table.parquet")
print(f"Loaded {len(df)} games, seasons {sorted(df['season'].unique())}")
nrfi_rate = df["nrfi"].mean()
has_total = df[df["closing_total"].notna()].copy()
has_f5 = df[df["closing_f5_total"].notna()].copy()
has_both = df[(df["closing_total"].notna()) & (df["closing_f5_total"].notna())].copy()

# ── PHASE 2 ──
daily = df.groupby("date").agg(games=("game_pk","count"), nrfi_count=("nrfi","sum")).reset_index()
daily["nrfi_rate"] = daily["nrfi_count"] / daily["games"]

p2 = []
p2.append("# Phase 2: Slate Frequency Analysis\n")
p2.append(f"Total games: {len(df)}")
p2.append(f"Total slates (days): {len(daily)}")
p2.append(f"Overall NRFI rate: {nrfi_rate:.4f} ({nrfi_rate*100:.1f}%)")
p2.append(f"Overall YRFI rate: {df['yrfi'].mean():.4f} ({df['yrfi'].mean()*100:.1f}%)")
p2.append(f"\nImplied fair NRFI price (no vig): {-100/nrfi_rate+100:+.0f}")
p2.append(f"Implied fair YRFI price (no vig): {-100/df['yrfi'].mean()+100:+.0f}")
p2.append(f"\nGames per day: mean={daily['games'].mean():.1f}, median={daily['games'].median():.0f}")
p2.append(f"NRFIs per day: mean={daily['nrfi_count'].mean():.1f}, median={daily['nrfi_count'].median():.0f}")
p2.append("\nNRFI rate by season:")
for s in sorted(df["season"].unique()):
    sub = df[df["season"]==s]
    p2.append(f"  {s}: {sub['nrfi'].mean():.4f} ({len(sub)} games)")
p2.append("\nDaily NRFI rate distribution:")
for pct in [10,25,50,75,90]:
    p2.append(f"  P{pct}: {daily['nrfi_rate'].quantile(pct/100):.3f}")
p2.append("\n## Half-inning breakdown")
p2.append(f"Top-1 clean (away scores 0): {(df['away_1st_runs']==0).mean():.4f}")
p2.append(f"Bot-1 clean (home scores 0): {(df['home_1st_runs']==0).mean():.4f}")
p2.append(f"Both clean (NRFI): {nrfi_rate:.4f}")
p2_text = "\n".join(p2)
print(p2_text)
open(f"{OUT}/phase2_report.md","w").write(p2_text)

# ── PHASE 3 ──
p3 = []
p3.append("# Phase 3: Market Baseline\n")
p3.append(f"Actual NRFI rate: {nrfi_rate:.4f} ({nrfi_rate*100:.1f}%)")
p3.append(f"Fair NRFI price (no vig): {-100/nrfi_rate+100:+.0f}")
p3.append("Typical market NRFI price: -130 to -150 (implied 56.5%-60.0%)")
p3.append("Typical market YRFI price: +105 to +120 (implied 45.5%-48.8%)")
if nrfi_rate > 0.56:
    p3.append("\nMarket pricing appears roughly fair")
elif nrfi_rate > 0.50:
    p3.append(f"\nNRFI actual ({nrfi_rate:.1%}) is BELOW typical market implied (~57-60%)")
    p3.append("Market OVERPRICES NRFI on average")
else:
    p3.append(f"\nNRFI actual ({nrfi_rate:.1%}) is well BELOW market implied")
p3.append("\n## Season trend:")
for s in sorted(df["season"].unique()):
    sub = df[df["season"]==s]; r = sub["nrfi"].mean()
    p3.append(f"  {s}: NRFI={r:.4f} fair={-100/r+100:+.0f}")
blind_roi = nrfi_rate * (100/135) - (1-nrfi_rate)
p3.append(f"\n## Blind NRFI bet at -135:")
p3.append(f"  Win rate needed: {135/(135+100):.1%}")
p3.append(f"  Actual rate: {nrfi_rate:.1%}")
p3.append(f"  Blind ROI: {blind_roi:+.1%}")
p3_text = "\n".join(p3)
print("\n" + "="*70 + "\n" + p3_text)
open(f"{OUT}/phase3_report.md","w").write(p3_text)

# ── PHASE 4 ──
p4 = []
p4.append("# Phase 4: NRFI Rate by Full-Game Closing Total\n")
p4.append(f"Games with closing total: {len(has_total)}/{len(df)}")
has_total["tb"] = pd.cut(has_total["closing_total"],
    bins=[0,7.0,7.5,8.0,8.5,9.0,9.5,10.0,10.5,11.0,25],
    labels=["<=7.0","7.5","8.0","8.5","9.0","9.5","10.0","10.5","11.0",">11.0"])
bs = has_total.groupby("tb",observed=False).agg(
    games=("game_pk","count"), nrfi_n=("nrfi","sum"), rate=("nrfi","mean"),
    avg1r=("total_1st_runs","mean")).reset_index()
hdr = f"\n{'Total':<8} {'Games':>6} {'NRFI':>6} {'Rate':>8} {'Avg1stR':>8}"
p4.append(hdr); p4.append("-"*42)
for _,r in bs.iterrows():
    if r["games"]>0:
        p4.append(f"{r['tb']:<8} {int(r['games']):>6} {int(r['nrfi_n']):>6} {r['rate']:>7.1%} {r['avg1r']:>8.3f}")
lo = has_total[has_total["closing_total"]<=8.0]["nrfi"].mean()
mi = has_total[(has_total["closing_total"]>8.0)&(has_total["closing_total"]<=9.5)]["nrfi"].mean()
hi = has_total[has_total["closing_total"]>9.5]["nrfi"].mean()
p4.append(f"\n## Key findings:")
p4.append(f"  Low (<=8.0): {lo:.1%}  Mid (8.5-9.5): {mi:.1%}  High (>9.5): {hi:.1%}")
p4.append(f"  Low-vs-High spread: {lo-hi:+.1%}")
p4_text = "\n".join(p4)
print("\n" + "="*70 + "\n" + p4_text)
open(f"{OUT}/phase4_report.md","w").write(p4_text)

# ── PHASE 5 ──
p5 = []
p5.append("# Phase 5: NRFI Rate by F5 Closing Total\n")
p5.append(f"Games with F5 closing total: {len(has_f5)}/{len(df)}")
has_f5["fb"] = pd.cut(has_f5["closing_f5_total"],
    bins=[0,3.5,4.0,4.5,5.0,5.5,6.0,6.5,20],
    labels=["<=3.5","4.0","4.5","5.0","5.5","6.0","6.5",">6.5"])
fs = has_f5.groupby("fb",observed=False).agg(
    games=("game_pk","count"), nrfi_n=("nrfi","sum"), rate=("nrfi","mean"),
    avg1r=("total_1st_runs","mean")).reset_index()
hdr5 = f"\n{'F5Tot':<8} {'Games':>6} {'NRFI':>6} {'Rate':>8} {'Avg1stR':>8}"
p5.append(hdr5); p5.append("-"*42)
for _,r in fs.iterrows():
    if r["games"]>0:
        p5.append(f"{r['fb']:<8} {int(r['games']):>6} {int(r['nrfi_n']):>6} {r['rate']:>7.1%} {r['avg1r']:>8.3f}")
lf = has_f5[has_f5["closing_f5_total"]<=4.0]["nrfi"].mean()
mf = has_f5[(has_f5["closing_f5_total"]>4.0)&(has_f5["closing_f5_total"]<=5.0)]["nrfi"].mean()
hf = has_f5[has_f5["closing_f5_total"]>5.0]["nrfi"].mean()
p5.append(f"\n## Key findings:")
p5.append(f"  Low F5 (<=4.0): {lf:.1%}  Mid (4.5-5.0): {mf:.1%}  High (>5.0): {hf:.1%}")
p5.append(f"  Low-vs-High spread: {lf-hf:+.1%}")
p5_text = "\n".join(p5)
print("\n" + "="*70 + "\n" + p5_text)
open(f"{OUT}/phase5_report.md","w").write(p5_text)

# ── PHASE 6 ──
p6 = []
p6.append("# Phase 6: Interaction Table (Full-Game x F5)\n")
p6.append(f"Games with both: {len(has_both)}/{len(df)}")
has_both["fg"] = pd.cut(has_both["closing_total"],
    bins=[0,7.5,8.0,8.5,9.0,9.5,10.0,25],
    labels=["<=7.5","8.0","8.5","9.0","9.5","10.0",">10.0"])
has_both["f5"] = pd.cut(has_both["closing_f5_total"],
    bins=[0,4.0,4.5,5.0,5.5,20], labels=["<=4.0","4.5","5.0","5.5",">5.5"])
ix = has_both.groupby(["fg","f5"],observed=False).agg(
    n=("game_pk","count"), rate=("nrfi","mean")).reset_index()
pv = ix.pivot(index="fg",columns="f5",values="rate")
pn = ix.pivot(index="fg",columns="f5",values="n")

hdr6 = f"{'FG\\F5':<10}"
for c in pv.columns: hdr6 += f" {c:>10}"
p6.append("\n" + hdr6); p6.append("-"*(10+11*len(pv.columns)))
for idx in pv.index:
    line = f"{idx:<10}"
    for c in pv.columns:
        rv = pv.loc[idx,c]; nv = pn.loc[idx,c]
        if pd.notna(rv) and nv>=10: line += f" {rv:>9.1%}"
        elif pd.notna(rv) and nv>0: line += f" {rv:>8.1%}*"
        else: line += f" {'--':>10}"
    p6.append(line)
p6.append("\n* = <10 games")

p6.append(f"\n## Sample sizes:")
hdr6n = f"{'FG\\F5':<10}"
for c in pn.columns: hdr6n += f" {c:>10}"
p6.append(hdr6n); p6.append("-"*(10+11*len(pn.columns)))
for idx in pn.index:
    line = f"{idx:<10}"
    for c in pn.columns:
        nv = pn.loc[idx,c]
        line += f" {int(nv):>10}" if pd.notna(nv) else f" {'--':>10}"
    p6.append(line)

p6.append(f"\n## Best NRFI pockets (n>=30):")
good = ix[ix["n"]>=30].sort_values("rate",ascending=False).head(5)
for _,r in good.iterrows():
    p6.append(f"  FG={r['fg']}, F5={r['f5']}: NRFI={r['rate']:.1%} (n={int(r['n'])})")
p6.append(f"\n## Worst NRFI pockets (n>=30):")
bad = ix[ix["n"]>=30].sort_values("rate").head(5)
for _,r in bad.iterrows():
    p6.append(f"  FG={r['fg']}, F5={r['f5']}: NRFI={r['rate']:.1%} (n={int(r['n'])})")
p6_text = "\n".join(p6)
print("\n" + "="*70 + "\n" + p6_text)
open(f"{OUT}/phase6_report.md","w").write(p6_text)

# ── PHASE 7 ──
p7 = []
p7.append("# Phase 7: Underpriced Pocket Identification\n")
mi_imp = 0.574
p7.append(f"Market NRFI implied: {mi_imp:.1%} (typical -135)\n")

p7.append("## By full-game closing total:")
has_total["tb2"] = pd.cut(has_total["closing_total"],
    bins=[0,7.5,8.0,8.5,9.0,9.5,10.0,10.5,25],
    labels=["<=7.5","8.0","8.5","9.0","9.5","10.0","10.5",">10.5"])
for bk in has_total["tb2"].cat.categories:
    sub = has_total[has_total["tb2"]==bk]
    if len(sub)<30: continue
    rt = sub["nrfi"].mean(); eg = rt - mi_imp
    fp = -100/rt+100 if rt>0 else 0
    st = "UNDERPRICED" if eg>0.02 else ("FAIR" if abs(eg)<=0.02 else "OVERPRICED")
    p7.append(f"  {bk:>6}: NRFI={rt:.1%}, edge={eg:+.1%}, fair={fp:+.0f} -- {st} (n={len(sub)})")

p7.append(f"\n## By F5 closing total:")
has_f5["fb2"] = pd.cut(has_f5["closing_f5_total"],
    bins=[0,3.5,4.0,4.5,5.0,5.5,6.0,20],
    labels=["<=3.5","4.0","4.5","5.0","5.5","6.0",">6.0"])
for bk in has_f5["fb2"].cat.categories:
    sub = has_f5[has_f5["fb2"]==bk]
    if len(sub)<20: continue
    rt = sub["nrfi"].mean(); eg = rt - mi_imp
    fp = -100/rt+100 if rt>0 else 0
    st = "UNDERPRICED" if eg>0.02 else ("FAIR" if abs(eg)<=0.02 else "OVERPRICED")
    p7.append(f"  {bk:>6}: NRFI={rt:.1%}, edge={eg:+.1%}, fair={fp:+.0f} -- {st} (n={len(sub)})")

p7.append(f"\n## Environment:")
dome = df[df["dome"]==1]; outdoor = df[df["dome"]==0]
p7.append(f"  Dome: NRFI={dome['nrfi'].mean():.1%} (n={len(dome)})")
p7.append(f"  Outdoor: NRFI={outdoor['nrfi'].mean():.1%} (n={len(outdoor)})")
ot = outdoor[outdoor["temperature"].notna()]
cold = ot[ot["temperature"]<55]; mild = ot[(ot["temperature"]>=55)&(ot["temperature"]<75)]; warm = ot[ot["temperature"]>=75]
p7.append(f"\n  Outdoor temperature:")
p7.append(f"    Cold (<55F): {cold['nrfi'].mean():.1%} (n={len(cold)})")
p7.append(f"    Mild (55-74F): {mild['nrfi'].mean():.1%} (n={len(mild)})")
p7.append(f"    Warm (>=75F): {warm['nrfi'].mean():.1%} (n={len(warm)})")

hpf = df[df["park_factor_runs"].notna()]
if len(hpf)>100:
    lpf = hpf[hpf["park_factor_runs"]<97]; mpf = hpf[(hpf["park_factor_runs"]>=97)&(hpf["park_factor_runs"]<=103)]; hpp = hpf[hpf["park_factor_runs"]>103]
    p7.append(f"\n## Park factor:")
    p7.append(f"  Pitcher (<97): {lpf['nrfi'].mean():.1%} (n={len(lpf)})")
    p7.append(f"  Neutral (97-103): {mpf['nrfi'].mean():.1%} (n={len(mpf)})")
    p7.append(f"  Hitter (>103): {hpp['nrfi'].mean():.1%} (n={len(hpp)})")
p7_text = "\n".join(p7)
print("\n" + "="*70 + "\n" + p7_text)
open(f"{OUT}/phase7_report.md","w").write(p7_text)

# ── PHASE 8 ──
p8 = []
p8.append("# Phase 8: Top-3 Selection Framework\n")
p8.append("## Objective: Identify best daily NRFI legs for parlay construction\n")
p8.append("### Signal hierarchy:")
p8.append("1. Combined p_yrfi rank -- bottom 10% of slate")
p8.append("2. Full-game closing total -- lower = higher NRFI")
p8.append("3. F5 closing total -- independent validation")
p8.append("4. Park factor -- pitcher parks boost NRFI")
p8.append("5. Starter archetype -- CONTACT_RISK exclusion")
p8.append("6. Top-3 lineup stability -- both-changed exclusion\n")

lt = has_total[has_total["closing_total"]<=8.0]; ht = has_total[has_total["closing_total"]>=10.0]
p8.append(f"### Filter values:")
p8.append(f"  FG <=8.0: NRFI={lt['nrfi'].mean():.1%} (n={len(lt)})")
p8.append(f"  FG >=10.0: NRFI={ht['nrfi'].mean():.1%} (n={len(ht)})")
p8.append(f"  Lift: {lt['nrfi'].mean()-ht['nrfi'].mean():+.1%}")

lf5 = has_f5[has_f5["closing_f5_total"]<=4.0]; hf5 = has_f5[has_f5["closing_f5_total"]>=5.5]
if len(lf5)>20 and len(hf5)>20:
    p8.append(f"\n  F5 <=4.0: NRFI={lf5['nrfi'].mean():.1%} (n={len(lf5)})")
    p8.append(f"  F5 >=5.5: NRFI={hf5['nrfi'].mean():.1%} (n={len(hf5)})")
    p8.append(f"  Lift: {lf5['nrfi'].mean()-hf5['nrfi'].mean():+.1%}")

best = has_both[(has_both["closing_total"]<=8.5)&(has_both["closing_f5_total"]<=5.0)]
p8.append(f"\n  Combined (FG<=8.5 & F5<=5.0): NRFI={best['nrfi'].mean():.1%} (n={len(best)})")
p8.append(f"  vs baseline {nrfi_rate:.1%} = {best['nrfi'].mean()-nrfi_rate:+.1%} lift")

tight = has_both[(has_both["closing_total"]<=7.5)&(has_both["closing_f5_total"]<=4.5)]
if len(tight)>10:
    p8.append(f"\n  Tightest (FG<=7.5 & F5<=4.5): NRFI={tight['nrfi'].mean():.1%} (n={len(tight)})")

p8.append(f"\n### Breakeven at -135 ({135/(135+100):.1%} implied):")
for lab, sub in [("Baseline", df), ("FG<=8.0", lt), ("FG<=8.5 & F5<=5.0", best)]:
    if len(sub)<10: continue
    rt = sub["nrfi"].mean(); roi = rt*(100/135)-(1-rt)
    p8.append(f"  {lab}: NRFI={rt:.1%}, ROI={roi:+.1%} (n={len(sub)})")
if len(tight)>10:
    rt=tight["nrfi"].mean(); roi=rt*(100/135)-(1-rt)
    p8.append(f"  FG<=7.5 & F5<=4.5: NRFI={rt:.1%}, ROI={roi:+.1%} (n={len(tight)})")

p8.append("\n### Recommended daily selection:")
p8.append("1. Closing total <= 8.5")
p8.append("2. F5 total <= 5.0")
p8.append("3. Micro-model p_yrfi bottom 10%")
p8.append("4. Exclude CONTACT_RISK starters")
p8.append("5. Exclude both-top-3-changed lineups")
p8.append("6. Pitcher park preferred")
p8_text = "\n".join(p8)
print("\n" + "="*70 + "\n" + p8_text)
open(f"{OUT}/phase8_report.md","w").write(p8_text)

# ── EXEC SUMMARY ──
es = []
es.append("# NRFI Phase 1 -- Executive Summary")
es.append(f"\nGenerated: 2026-04-11")
es.append(f"Data: {len(df)} MLB games, seasons {sorted(df['season'].unique())}\n")

es.append("## Key Findings\n")
es.append(f"1. **Overall NRFI rate: {nrfi_rate:.1%}** across {len(df)} games (2022-2026)")
es.append(f"   - Top-1 clean (away 0 in 1st): {(df['away_1st_runs']==0).mean():.1%}")
es.append(f"   - Bot-1 clean (home 0 in 1st): {(df['home_1st_runs']==0).mean():.1%}")
es.append(f"   - Fair price (no vig): {-100/nrfi_rate+100:+.0f}")
es.append(f"   - Blind ROI at -135: {(nrfi_rate*(100/135)-(1-nrfi_rate)):+.1%}")

es.append(f"\n2. **Full-game total is the strongest NRFI filter**")
es.append(f"   - Total <=8.0: NRFI = {lt['nrfi'].mean():.1%} (n={len(lt)})")
es.append(f"   - Total >=10.0: NRFI = {ht['nrfi'].mean():.1%} (n={len(ht)})")
es.append(f"   - Spread: {lt['nrfi'].mean()-ht['nrfi'].mean():+.1%}")

if len(lf5)>20:
    es.append(f"\n3. **F5 total provides independent confirmation**")
    es.append(f"   - F5 <=4.0: NRFI = {lf5['nrfi'].mean():.1%} (n={len(lf5)})")
    es.append(f"   - F5 >=5.5: NRFI = {hf5['nrfi'].mean():.1%} (n={len(hf5)})")

br = best["nrfi"].mean()
es.append(f"\n4. **Best combined filter (FG<=8.5 AND F5<=5.0):**")
es.append(f"   - NRFI = {br:.1%} (n={len(best)})")
es.append(f"   - Lift vs baseline: {br-nrfi_rate:+.1%}")
es.append(f"   - ROI at -135: {(br*(100/135)-(1-br)):+.1%}")

if len(tight)>10:
    tr = tight["nrfi"].mean()
    es.append(f"\n5. **Tightest filter (FG<=7.5 AND F5<=4.5):**")
    es.append(f"   - NRFI = {tr:.1%} (n={len(tight)})")
    es.append(f"   - ROI at -135: {(tr*(100/135)-(1-tr)):+.1%}")

es.append(f"\n6. **Environment effects are modest**")
es.append(f"   - Dome: {dome['nrfi'].mean():.1%}, Outdoor: {outdoor['nrfi'].mean():.1%}")
es.append(f"   - Cold (<55F): {cold['nrfi'].mean():.1%}, Mild: {mild['nrfi'].mean():.1%}, Warm: {warm['nrfi'].mean():.1%}")

es.append(f"\n## Season stability")
for s in sorted(df["season"].unique()):
    sub = df[df["season"]==s]
    es.append(f"  {s}: NRFI = {sub['nrfi'].mean():.1%} ({len(sub)} games)")

es.append(f"\n## Actionable framework")
es.append("Select top-3 NRFI legs daily using:")
es.append("1. Closing total <= 8.5")
es.append("2. F5 total <= 5.0")
es.append("3. Micro-model p_yrfi in bottom 10% of slate")
es.append("4. Exclude CONTACT_RISK archetype starters")
es.append("5. Exclude both-top-3-changed lineups")
es.append("6. Pitcher park preferred (PF < 100)")

es.append(f"\n## Files")
es.append(f"- nrfi_research_table.parquet -- {len(df)} rows")
es.append(f"- NRFI_PHASE1_FINAL_TABLE.csv -- same, CSV")
es.append(f"- first_inning_cache.json -- MLB API linescore cache")
es.append(f"- phase2-8_report.md -- detailed phase reports")
es_text = "\n".join(es)
print("\n" + "="*70 + "\n" + es_text)
open(f"{OUT}/NRFI_PHASE1_EXEC_SUMMARY.md","w").write(es_text)

print("\n\nDONE.")
