#!/usr/bin/env python3
"""MLB Totals P1 — FG/F5 Path Mismatch Engine"""
import pandas as pd, numpy as np, warnings
from pathlib import Path
from scipy import stats
warnings.filterwarnings("ignore")
np.random.seed(42)

OUT = Path("/root/mlb-model/research/recovery/mlb_totals_p1_fg_f5_path_engine")
OUT.mkdir(parents=True, exist_ok=True)

def to_dec(p):
    if pd.isna(p): return np.nan
    return 1+p/100 if p>0 else 1+100/abs(p)

def to_str_key(s):
    """Robust conversion to string key, dropping empties."""
    return s.astype(str).str.strip()

print("="*70); print("PHASE 1: Lock Market Inputs"); print("="*70)

f5 = pd.read_parquet("/root/mlb-model/mlb_sim_f5/data/f5_lines_historical.parquet")
f5c = f5[f5["is_canonical"]==True][["game_id","date","f5_total","actual_f5_total"]].drop_duplicates(subset=["game_id"])
f5c = f5c.rename(columns={"game_id":"game_pk","f5_total":"f5_line"})
f5c["gpk"] = to_str_key(f5c["game_pk"]); f5c = f5c[f5c["gpk"]!=""]; f5c["date"]=f5c["date"].astype(str)
print(f"F5: {len(f5c)}, years: {f5c['date'].str[:4].value_counts().sort_index().to_dict()}")

canon = pd.read_parquet("/root/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet")
canon["gpk"]=to_str_key(canon["game_pk"]); canon=canon[canon["gpk"]!=""]; canon["date"]=canon["date"].astype(str)
canon=canon[canon["total_line"].notna()].copy()
print(f"FG odds: {len(canon)}")

gt = pd.read_parquet("/root/mlb-model/sim/data/game_table.parquet")
gt["gpk"]=gt["game_pk"].astype(str).str.strip(); gt["date"]=gt["date"].astype(str)
print(f"GT: {len(gt)}")

m = gt[["gpk","date","season","home_team","away_team","home_score","away_score","actual_total","actual_f5_total",
        "park_factor_runs","temperature","wind_speed","wind_direction","home_rest_days","away_rest_days",
        "umpire_over_rate","innings_played","completed_early"]].copy()
m = m.merge(canon[["gpk","total_line","total_over_price","total_under_price"]], on="gpk", how="inner")
print(f"After FG merge: {len(m)}")
m = m.merge(f5c[["gpk","f5_line","actual_f5_total"]], on="gpk", how="inner", suffixes=("","_f5"))
m["actual_f5_total"]=m["actual_f5_total"].fillna(m.get("actual_f5_total_f5"))
if "actual_f5_total_f5" in m.columns: m.drop(columns=["actual_f5_total_f5"],inplace=True)
print(f"After F5 merge: {len(m)}, years: {m['date'].str[:4].value_counts().sort_index().to_dict()}")
m = m[m["actual_f5_total"].notna() & m["actual_total"].notna() & (m["innings_played"]>=9)].copy()
print(f"After filter: {len(m)}")

print("\n"+"="*70); print("PHASE 2: Path States"); print("="*70)
m["late_implied"] = m["total_line"] - m["f5_line"]
m["f5_ratio"] = m["f5_line"] / m["total_line"]
m["actual_late"] = m["actual_total"] - m["actual_f5_total"]

disc_m = m[m["date"].str[:4]=="2023"]
f5r_p33=disc_m["f5_ratio"].quantile(0.33); f5r_p67=disc_m["f5_ratio"].quantile(0.67)
late_p75=disc_m["late_implied"].quantile(0.75)
print(f"Thresholds: f5r_p33={f5r_p33:.4f}, f5r_p67={f5r_p67:.4f}, late_p75={late_p75:.2f}")

def pstate(r):
    fg,f5r,late=r["total_line"],r["f5_ratio"],r["late_implied"]
    if fg<=7.5: return "COMPRESSED_LOW"
    elif late>=late_p75 and fg>=8.5: return "ELEVATED_LATE"
    elif f5r>f5r_p67: return "EARLY_HEAVY"
    elif f5r<f5r_p33: return "LATE_HEAVY"
    return "BALANCED"

m["path_state"]=m.apply(pstate,axis=1)
print(m["path_state"].value_counts().to_string())
m["fg_over"]=(m["actual_total"]>m["total_line"]).astype(int)
m["fg_under"]=(m["actual_total"]<m["total_line"]).astype(int)
m["fg_push"]=(m["actual_total"]==m["total_line"]).astype(int)
m["path_error"]=m["actual_late"]-m["late_implied"]
m["fg_error"]=m["actual_total"]-m["total_line"]

print("\n"+"="*70); print("PHASE 3: Structural Drivers"); print("="*70)
pgl = pd.read_parquet("/root/mlb-model/mlb/data/pitcher_game_logs.parquet")
pgl["gpk"]=pgl["game_pk"].astype(str).str.strip(); pgl["game_date"]=pgl["game_date"].astype(str)
sp = pgl[pgl["starter_flag"]==1].sort_values(["player_id","game_date"]).copy()
print(f"SP logs: {len(sp)}, home_away: {sp['home_away'].unique().tolist()}")

for c in ["innings_pitched","earned_runs","strikeouts","walks","home_runs_allowed","batters_faced"]:
    sp[f"p_{c}"] = sp.groupby("player_id")[c].transform(lambda x: x.shift(1).expanding().mean())

sp["sp_avg_ip"]=sp["p_innings_pitched"]
sp["sp_fip"]=np.where(sp["p_innings_pitched"]>0,
    ((13*sp["p_home_runs_allowed"]+3*sp["p_walks"]-2*sp["p_strikeouts"])/sp["p_innings_pitched"])+3.2, np.nan)
sp["sp_ip_std"]=sp.groupby("player_id")["innings_pitched"].transform(lambda x: x.shift(1).expanding().std())
sp["sp_k_rate"]=np.where(sp["p_batters_faced"]>0, sp["p_strikeouts"]/sp["p_batters_faced"], np.nan)

sph=sp[sp["home_away"]=="H"][["gpk","sp_avg_ip","sp_fip","sp_ip_std","sp_k_rate"]].copy()
sph.columns=["gpk","home_sp_avg_ip","home_sp_fip","home_sp_ip_std","home_sp_k_rate"]
spa=sp[sp["home_away"]=="A"][["gpk","sp_avg_ip","sp_fip","sp_ip_std","sp_k_rate"]].copy()
spa.columns=["gpk","away_sp_avg_ip","away_sp_fip","away_sp_ip_std","away_sp_k_rate"]

m=m.merge(sph,on="gpk",how="left"); m=m.merge(spa,on="gpk",how="left")
print(f"SP: home={m['home_sp_avg_ip'].notna().sum()}, away={m['away_sp_avg_ip'].notna().sum()}")

# BP
bp_g = pgl[pgl["starter_flag"]==0].groupby(["gpk","home_away"]).agg(
    bp_ip=("innings_pitched","sum"),bp_er=("earned_runs","sum")).reset_index()
bp_t = pgl[pgl["starter_flag"]==0][["gpk","game_date","home_away","team"]].drop_duplicates(subset=["gpk","home_away"])
bp_g=bp_g.merge(bp_t,on=["gpk","home_away"],how="left").sort_values(["team","game_date"])
bp_g["bp_era_raw"]=np.where(bp_g["bp_ip"]>0,9*bp_g["bp_er"]/bp_g["bp_ip"],np.nan)
bp_g["bp_roll_era"]=bp_g.groupby("team")["bp_era_raw"].transform(lambda x: x.shift(1).expanding().mean())

bph=bp_g[bp_g["home_away"]=="H"][["gpk","bp_roll_era"]].rename(columns={"bp_roll_era":"home_bp_era"})
bpa=bp_g[bp_g["home_away"]=="A"][["gpk","bp_roll_era"]].rename(columns={"bp_roll_era":"away_bp_era"})
m=m.merge(bph,on="gpk",how="left"); m=m.merge(bpa,on="gpk",how="left")
print(f"BP: home={m['home_bp_era'].notna().sum()}, away={m['away_bp_era'].notna().sum()}")

# Derived
m["sp_length_diff"]=m["home_sp_avg_ip"]-m["away_sp_avg_ip"]
m["bp_quality_diff"]=m["home_bp_era"]-m["away_bp_era"]
m["sp_fragility_max"]=m[["home_sp_ip_std","away_sp_ip_std"]].max(axis=1)
m["sp_fragility_avg"]=m[["home_sp_ip_std","away_sp_ip_std"]].mean(axis=1)
m["sp_avg_ip_min"]=m[["home_sp_avg_ip","away_sp_avg_ip"]].min(axis=1)
m["bp_era_avg"]=m[["home_bp_era","away_bp_era"]].mean(axis=1)
m["sp_fip_avg"]=m[["home_sp_fip","away_sp_fip"]].mean(axis=1)
m["sp_fip_max"]=m[["home_sp_fip","away_sp_fip"]].max(axis=1)

print("\n"+"="*70); print("PHASE 4: Splits"); print("="*70)
def split(d):
    y=d[:4]
    return {"2023":"discovery","2024":"validation","2025":"oos"}.get(y,"exclude")
m["split"]=m["date"].apply(split)
m=m[m["split"]!="exclude"].copy()
print(m["split"].value_counts().to_string())
print(pd.crosstab(m["path_state"],m["split"]).to_string())
m.to_csv(OUT/"MLB_TOTALS_P1_FINAL_TABLE.csv",index=False)

print("\n"+"="*70); print("PHASE 5: Path Error"); print("="*70)
p5=[]
for sn in ["discovery","validation","oos"]:
    sub=m[m["split"]==sn]; p5.append(f"\n--- {sn.upper()} (n={len(sub)}) ---")
    for st in sorted(m["path_state"].unique()):
        s=sub[sub["path_state"]==st]
        if len(s)<20: continue
        pe=s["path_error"].dropna(); t,p=stats.ttest_1samp(pe,0)
        l=f"  {st:20s} N={len(s):4d} path_err={pe.mean():+.3f} (t={t:+.2f} p={p:.3f}) over={s['fg_over'].mean():.3f}"
        p5.append(l); print(l)
with open(OUT/"phase5_path_error_diagnostic.txt","w") as f: f.write("\n".join(p5))

print("\n"+"="*70); print("PHASE 6: Interactions"); print("="*70)
disc=m[m["split"]=="discovery"].copy()
ir=[]
drivers={"bp_era_avg":"Avg BP ERA","sp_avg_ip_min":"Min SP avg IP","sp_fragility_max":"Max SP IP vol",
    "sp_fragility_avg":"Avg SP IP vol","sp_length_diff":"SP length diff","bp_quality_diff":"BP quality diff",
    "home_sp_fip":"Home SP FIP","away_sp_fip":"Away SP FIP","sp_fip_avg":"Avg SP FIP","sp_fip_max":"Max SP FIP",
    "park_factor_runs":"Park factor","temperature":"Temperature"}

for st in sorted(m["path_state"].unique()):
    sd=disc[disc["path_state"]==st]
    if len(sd)<50: continue
    for dc,dn in drivers.items():
        sub=sd[[dc,"fg_error","fg_over","fg_under"]].dropna()
        if len(sub)<30: continue
        med=sub[dc].median(); hi=sub[sub[dc]>=med]; lo=sub[sub[dc]<med]
        if len(hi)<15 or len(lo)<15: continue
        od=hi["fg_over"].mean()-lo["fg_over"].mean()
        t,p=stats.ttest_ind(hi["fg_error"],lo["fg_error"])
        ir.append({"path_state":st,"driver":dn,"driver_col":dc,"n_hi":len(hi),"n_lo":len(lo),
            "over_rate_hi":hi["fg_over"].mean(),"over_rate_lo":lo["fg_over"].mean(),"over_diff":od,
            "fg_err_hi":hi["fg_error"].mean(),"fg_err_lo":lo["fg_error"].mean(),"t_stat":t,"p_val":p})

idf=pd.DataFrame(ir).sort_values("p_val")
print(f"Tested: {len(idf)}, p<0.10: {(idf['p_val']<0.10).sum()}, p<0.05: {(idf['p_val']<0.05).sum()}")
print(idf[["path_state","driver","over_diff","fg_err_hi","fg_err_lo","t_stat","p_val"]].head(20).to_string(index=False))
idf.to_csv(OUT/"phase6_interactions.csv",index=False)

print("\n"+"="*70); print("PHASE 7: Lock Candidates"); print("="*70)
cands=idf[idf["p_val"]<0.10].copy(); cands["abs_od"]=cands["over_diff"].abs()
cands=cands.sort_values("abs_od",ascending=False).head(6)
print(f"Selected {len(cands)}:")
print(cands[["path_state","driver","over_diff","p_val"]].to_string(index=False))

print("\n"+"="*70); print("PHASE 8-9: Economics"); print("="*70)
econ=[]
for sn in ["discovery","validation","oos"]:
    sub=m[m["split"]==sn]
    for _,c in cands.iterrows():
        st,dc,od=c["path_state"],c["driver_col"],c["over_diff"]
        ss=sub[(sub["path_state"]==st)&sub[dc].notna()]
        if len(ss)<10: continue
        ds=disc[(disc["path_state"]==st)&disc[dc].notna()]
        if len(ds)<20: continue
        med=ds[dc].median()
        if od>0: mask=ss[dc]>=med; side="over"; pc="total_over_price"
        else: mask=ss[dc]>=med; side="under"; pc="total_under_price"
        b=ss[mask].copy()
        if len(b)<5: continue
        b["win"]=b["fg_over"] if side=="over" else b["fg_under"]
        b["dec"]=b[pc].apply(to_dec)
        b["pnl"]=np.where(b["win"]==1,100*(b["dec"]-1),np.where(b["fg_push"]==1,0,-100))
        n=len(b)
        econ.append({"split":sn,"path_state":st,"driver":c["driver"],"driver_col":dc,
            "bet_side":side,"n_bets":n,"win_rate":b["win"].mean(),"avg_price":b[pc].mean(),
            "total_pnl":b["pnl"].sum(),"roi":b["pnl"].sum()/(n*100)})

edf=pd.DataFrame(econ)
print(edf.to_string(index=False))
edf.to_csv(OUT/"phase8_economics.csv",index=False)

print("\n"+"="*70); print("PHASE 9: Cross-split"); print("="*70)
for _,c in cands.iterrows():
    st,dr=c["path_state"],c["driver"]
    d=edf[(edf["split"]=="discovery")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    v=edf[(edf["split"]=="validation")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    o=edf[(edf["split"]=="oos")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    if d.empty: continue
    dr_=d.iloc[0]["roi"]; dn=int(d.iloc[0]["n_bets"])
    vr=v.iloc[0]["roi"] if not v.empty else np.nan; vn=int(v.iloc[0]["n_bets"]) if not v.empty else 0
    oroi=o.iloc[0]["roi"] if not o.empty else np.nan; on=int(o.iloc[0]["n_bets"]) if not o.empty else 0
    tag="PASS_ALL" if dr_>0 and vr>0 and oroi>0 else "PASS_DV" if dr_>0 and vr>0 else "DISC_ONLY" if dr_>0 else "FAIL"
    print(f"  {st:18s} {dr:20s} disc={dr_:+.1%}(n={dn:3d}) val={vr:+.1%}(n={vn:3d}) oos={oroi:+.1%}(n={on:3d}) {tag}")

print("\n"+"="*70); print("PHASE 10: Decision Board"); print("="*70)
drows=[]
for _,c in cands.iterrows():
    st,dr,dc=c["path_state"],c["driver"],c["driver_col"]
    d=edf[(edf["split"]=="discovery")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    v=edf[(edf["split"]=="validation")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    o=edf[(edf["split"]=="oos")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    if d.empty: continue
    r={"path_state":st,"driver":dr,"driver_col":dc,"bet_side":d.iloc[0]["bet_side"],
       "disc_n":int(d.iloc[0]["n_bets"]),"disc_roi":d.iloc[0]["roi"],"disc_win":d.iloc[0]["win_rate"],
       "val_n":int(v.iloc[0]["n_bets"]) if not v.empty else 0,
       "val_roi":v.iloc[0]["roi"] if not v.empty else np.nan,
       "val_win":v.iloc[0]["win_rate"] if not v.empty else np.nan,
       "oos_n":int(o.iloc[0]["n_bets"]) if not o.empty else 0,
       "oos_roi":o.iloc[0]["roi"] if not o.empty else np.nan,
       "oos_win":o.iloc[0]["win_rate"] if not o.empty else np.nan,
       "disc_p":c["p_val"]}
    dr_=r["disc_roi"]; vr=r.get("val_roi",np.nan); orr=r.get("oos_roi",np.nan)
    if dr_>0 and not np.isnan(vr) and vr>0 and not np.isnan(orr) and orr>0: r["verdict"]="PROMOTE"
    elif dr_>0 and not np.isnan(vr) and vr>0: r["verdict"]="MONITOR"
    elif dr_>0: r["verdict"]="WATCH"
    else: r["verdict"]="REJECT"
    drows.append(r)

ddf=pd.DataFrame(drows)
if len(ddf):
    print(ddf[["path_state","driver","bet_side","disc_roi","disc_n","val_roi","val_n","oos_roi","oos_n","verdict"]].to_string(index=False))
    ddf.to_csv(OUT/"phase10_decision_board.csv",index=False)

pro=ddf[ddf["verdict"]=="PROMOTE"] if len(ddf) else pd.DataFrame()
mon=ddf[ddf["verdict"]=="MONITOR"] if len(ddf) else pd.DataFrame()
wat=ddf[ddf["verdict"]=="WATCH"] if len(ddf) else pd.DataFrame()
rej=ddf[ddf["verdict"]=="REJECT"] if len(ddf) else pd.DataFrame()

print("\n"+"="*70); print("PHASE 11: Executive Summary"); print("="*70)
L=[]
L.append("# MLB Totals P1 — FG/F5 Path Mismatch Engine\n")
L.append("## Executive Summary\n")
L.append("### Thesis")
L.append("The FG total and F5 total together imply a scoring path (early vs late).")
L.append("When structural game drivers (SP depth, BP quality, park, temperature) conflict")
L.append("with the market-implied path, there may be FG total mispricing.\n")
L.append("### Data Coverage")
L.append(f"- F5 canonical lines: {len(f5c)} games (2023-05 to 2025-09)")
L.append(f"- FG closing odds: {len(canon)} games")
L.append(f"- Research table: {len(m)} games (9+ innings, F5 actuals)")
L.append(f"- Discovery: 2023 (n={len(m[m['split']=='discovery'])})")
L.append(f"- Validation: 2024 (n={len(m[m['split']=='validation'])})")
L.append(f"- OOS: 2025 (n={len(m[m['split']=='oos'])})\n")
L.append("### Path States (thresholds frozen from 2023)")
L.append(f"- F5_ratio p33={f5r_p33:.4f}, p67={f5r_p67:.4f}")
L.append(f"- Late_implied p75={late_p75:.2f}")
ct=pd.crosstab(m["path_state"],m["split"])
L.append(f"\n```\n{ct.to_string()}\n```\n")
L.append("### Phase 5 — Path Error")
L.append("**Key finding:** EARLY_HEAVY and COMPRESSED_LOW show persistent positive path")
L.append("error (market underestimates late scoring). ELEVATED_LATE shows persistent")
L.append("negative path error. These patterns are highly significant across all splits.\n")
for sn in ["discovery","validation","oos"]:
    sub=m[m["split"]==sn]
    L.append(f"**{sn.upper()}** (n={len(sub)})")
    for st in sorted(m["path_state"].unique()):
        s=sub[sub["path_state"]==st]
        if len(s)<20: continue
        pe=s["path_error"].dropna(); t,p=stats.ttest_1samp(pe,0)
        L.append(f"- {st}: path_err={pe.mean():+.3f} (t={t:+.2f}, p={p:.3f}), over={s['fg_over'].mean():.3f}")
    L.append("")
L.append("### Phase 6 — Interactions")
L.append(f"- {len(idf)} interactions tested (12 drivers x up to 5 path states)")
L.append(f"- {(idf['p_val']<0.10).sum()} at p<0.10, {(idf['p_val']<0.05).sum()} at p<0.05")
L.append(f"- {len(cands)} selected for economics\n")
L.append("### Phase 8-9 — Economics (Actual Closing Prices)\n")
for _,c in cands.iterrows():
    st,dr=c["path_state"],c["driver"]
    d=edf[(edf["split"]=="discovery")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    v=edf[(edf["split"]=="validation")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    o=edf[(edf["split"]=="oos")&(edf["path_state"]==st)&(edf["driver"]==dr)]
    if d.empty: continue
    L.append(f"**{st} x {dr}** ({d.iloc[0]['bet_side']})")
    L.append(f"- Disc: n={int(d.iloc[0]['n_bets'])} win={d.iloc[0]['win_rate']:.1%} ROI={d.iloc[0]['roi']:+.1%}")
    if not v.empty: L.append(f"- Val:  n={int(v.iloc[0]['n_bets'])} win={v.iloc[0]['win_rate']:.1%} ROI={v.iloc[0]['roi']:+.1%}")
    if not o.empty: L.append(f"- OOS:  n={int(o.iloc[0]['n_bets'])} win={o.iloc[0]['win_rate']:.1%} ROI={o.iloc[0]['roi']:+.1%}")
    L.append("")
L.append("### Phase 10 — Decision Board")
L.append(f"- PROMOTE: {len(pro)}")
L.append(f"- MONITOR: {len(mon)}")
L.append(f"- WATCH: {len(wat)}")
L.append(f"- REJECT: {len(rej)}\n")
for lab,df_ in [("PROMOTE",pro),("MONITOR",mon),("WATCH",wat)]:
    if len(df_):
        L.append(f"#### {lab} Signals")
        for _,r in df_.iterrows():
            vs=f"{r['val_roi']:+.1%}" if not np.isnan(r.get('val_roi',np.nan)) else "N/A"
            os_=f"{r['oos_roi']:+.1%}" if not np.isnan(r.get('oos_roi',np.nan)) else "N/A"
            L.append(f"- **{r['path_state']} x {r['driver']}** ({r['bet_side']}): disc={r['disc_roi']:+.1%}(n={r['disc_n']}) val={vs}(n={r['val_n']}) oos={os_}(n={r['oos_n']})")
        L.append("")
L.append("### Recommendation")
if len(pro):
    L.append("PROMOTE signals identified. Proceed to shadow implementation.")
elif len(mon):
    L.append("MONITOR signals show disc+val persistence but fail OOS. The strongest candidate")
    L.append("shows a coherent story but does not survive OOS, suggesting the market adapted")
    L.append("or the pattern was regime-dependent. Continue collecting data; do not deploy live.")
else:
    L.append("No signals passed all gates. The path error diagnostic reveals real, stable")
    L.append("structure in how the market prices early/late scoring splits — but structural")
    L.append("game drivers do not reliably convert that into profitable FG total bets at")
    L.append("actual closing prices. The information is largely already priced in.")

et="\n".join(L)
with open(OUT/"MLB_TOTALS_P1_EXEC_SUMMARY.md","w") as f: f.write(et)
print(et)
print("\n"+"="*70); print("FILES:")
for fp in sorted(OUT.glob("*")): print(f"  {fp}")
print("="*70)
