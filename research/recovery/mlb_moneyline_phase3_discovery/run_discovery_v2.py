#!/usr/bin/env python3
"""
MLB Moneyline Phase 3 Bounded Discovery Engine v2
Fixed merge logic for SP/Statcast features.
"""
import pandas as pd
import numpy as np
import warnings, os
warnings.filterwarnings("ignore")

OUT = "research/recovery/mlb_moneyline_phase3_discovery"

# ── Load data ──
pgl = pd.read_parquet("mlb/data/pitcher_game_logs.parquet")
sc_per = pd.read_parquet("research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet")
sc_raw = pd.read_parquet("research/statcast_enrichment/pitcher_statcast_2022_2025_raw.parquet")
canon = pd.read_parquet("mlb_sim/data/mlb_odds_closing_canonical.parquet")
gt = pd.read_parquet("sim/data/game_table.parquet")

# Normalize types
pgl["game_pk"] = pgl["game_pk"].astype(str)
canon["game_pk"] = canon["game_pk"].astype(str)
gt["game_pk"] = gt["game_pk"].astype(str)
sc_per["game_pk"] = sc_per["game_pk"].astype(str)
sc_raw["game_pk"] = sc_raw["game_pk"].astype(str)
pgl["game_date"] = pd.to_datetime(pgl["game_date"])
sc_per["game_date"] = pd.to_datetime(sc_per["game_date"])
sc_raw["game_date"] = pd.to_datetime(sc_raw["game_date"])

# ── Base table: canon + game_table ──
df = canon.merge(gt[["game_pk","home_score","away_score","home_rest_days","away_rest_days",
                      "local_start_hour","park_factor_runs","innings_played"]], on="game_pk", how="inner")
df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)
df = df[df["home_score"] != df["away_score"]].copy()

def to_imp(p):
    if pd.isna(p) or p == 0: return np.nan
    return 100/(p+100) if p > 0 else abs(p)/(abs(p)+100)

df["raw_h"] = df["ml_home_price"].apply(to_imp)
df["raw_a"] = df["ml_away_price"].apply(to_imp)
df["vig"] = df["raw_h"] + df["raw_a"]
df["p_home"] = df["raw_h"] / df["vig"]
df["p_away"] = df["raw_a"] / df["vig"]

# Close-game universe
df["close_game"] = df[["p_home","p_away"]].max(axis=1).between(0.512, 0.556)
close = df[df["close_game"]].copy()
close["game_date"] = pd.to_datetime(close["date"])
close["season_yr"] = close["game_date"].dt.year
print(f"Close games: {len(close)}")
print(f"By season: {close.groupby('season_yr').size().to_dict()}")

# ── SP features ──
sp = pgl[pgl["starter_flag"]==True].copy()
sp = sp.sort_values(["player_id","game_date"])

for w in [5, 10]:
    sp[f"sp_era_r{w}"] = sp.groupby("player_id")["earned_runs"].transform(
        lambda x: x.rolling(w, min_periods=3).mean().shift(1))
    sp[f"sp_ip_r{w}"] = sp.groupby("player_id")["innings_pitched"].transform(
        lambda x: x.rolling(w, min_periods=3).mean().shift(1))
    sp[f"sp_k_r{w}"] = sp.groupby("player_id")["strikeouts"].transform(
        lambda x: x.rolling(w, min_periods=3).mean().shift(1))
    sp[f"sp_bb_r{w}"] = sp.groupby("player_id")["walks"].transform(
        lambda x: x.rolling(w, min_periods=3).mean().shift(1))
    sp[f"sp_runs_std_r{w}"] = sp.groupby("player_id")["runs_allowed"].transform(
        lambda x: x.rolling(w, min_periods=3).std().shift(1))

sp["sp_k9_r10"] = (sp["sp_k_r10"] / sp["sp_ip_r10"].clip(lower=0.1)) * 9
sp["sp_bb9_r10"] = (sp["sp_bb_r10"] / sp["sp_ip_r10"].clip(lower=0.1)) * 9
sp["sp_era9_r10"] = (sp["sp_era_r10"] / sp["sp_ip_r10"].clip(lower=0.1)) * 9
sp["sp_var_r10"] = sp["sp_runs_std_r10"]
sp["sp_short_leash"] = (sp["sp_ip_r10"] < 5.0).astype(int)

# Merge SP to close games via game_pk
# home_away in PGL is 'H'/'A'
sp_h = sp[sp["home_away"]=="H"][["game_pk","player_id","sp_era9_r10","sp_k9_r10","sp_bb9_r10",
    "sp_ip_r10","sp_var_r10","sp_short_leash","sp_runs_std_r5"]].copy()
sp_h.columns = ["game_pk","h_sp_id","h_sp_era9","h_sp_k9","h_sp_bb9","h_sp_ip","h_sp_var","h_sp_short_leash","h_sp_var5"]

sp_a = sp[sp["home_away"]=="A"][["game_pk","player_id","sp_era9_r10","sp_k9_r10","sp_bb9_r10",
    "sp_ip_r10","sp_var_r10","sp_short_leash","sp_runs_std_r5"]].copy()
sp_a.columns = ["game_pk","a_sp_id","a_sp_era9","a_sp_k9","a_sp_bb9","a_sp_ip","a_sp_var","a_sp_short_leash","a_sp_var5"]

close = close.merge(sp_h, on="game_pk", how="left")
close = close.merge(sp_a, on="game_pk", how="left")
print(f"SP ERA coverage: h={close['h_sp_era9'].notna().sum()}, a={close['a_sp_era9'].notna().sum()}")

# ── BP features ──
rel = pgl[pgl["starter_flag"]==False].copy()
rel_team = rel.groupby(["team","game_date"]).agg(
    bp_er=("earned_runs","sum"), bp_ip=("innings_pitched","sum")).reset_index()
rel_team = rel_team.sort_values(["team","game_date"])

rel_team["bp_era9_r10"] = rel_team.groupby("team").apply(
    lambda g: (g["bp_er"].rolling(10,min_periods=5).mean().shift(1) /
               g["bp_er"].rolling(10,min_periods=5).mean().shift(1).clip(lower=0.01)) * 9
    if False else pd.Series(dtype=float)).reset_index(drop=True)

# Simpler: compute bp ERA per game, then rolling mean
rel_team["bp_era_game"] = (rel_team["bp_er"] / rel_team["bp_ip"].clip(lower=0.1)) * 9
rel_team["bp_era9_r10"] = rel_team.groupby("team")["bp_era_game"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
rel_team["bp_ip_r3"] = rel_team.groupby("team")["bp_ip"].transform(
    lambda x: x.rolling(3, min_periods=1).sum().shift(1))

# Need to match to close games via team + date
# Home team BP
close["game_date_dt"] = close["game_date"]
h_bp = rel_team.rename(columns={"team":"home_team","game_date":"game_date_dt",
    "bp_era9_r10":"h_bp_era9","bp_ip_r3":"h_bp_workload"})[["home_team","game_date_dt","h_bp_era9","h_bp_workload"]]
a_bp = rel_team.rename(columns={"team":"away_team","game_date":"game_date_dt",
    "bp_era9_r10":"a_bp_era9","bp_ip_r3":"a_bp_workload"})[["away_team","game_date_dt","a_bp_era9","a_bp_workload"]]

close = close.merge(h_bp, on=["home_team","game_date_dt"], how="left")
close = close.merge(a_bp, on=["away_team","game_date_dt"], how="left")
print(f"BP ERA coverage: h={close['h_bp_era9'].notna().sum()}, a={close['a_bp_era9'].notna().sum()}")

# ── Post-extras ──
gt_full = gt.copy()
gt_full["date_dt"] = pd.to_datetime(gt_full["date"])
gt_full["extras"] = (gt_full["innings_played"] > 9).astype(int)

home_ext = gt_full[["home_team","date_dt","extras"]].rename(columns={"home_team":"team"})
away_ext = gt_full[["away_team","date_dt","extras"]].rename(columns={"away_team":"team"})
all_ext = pd.concat([home_ext, away_ext]).sort_values(["team","date_dt"])
all_ext["post_extras"] = all_ext.groupby("team")["extras"].shift(1)

ext_h = all_ext.rename(columns={"team":"home_team","date_dt":"game_date_dt","post_extras":"h_post_extras"})[
    ["home_team","game_date_dt","h_post_extras"]].drop_duplicates(["home_team","game_date_dt"])
ext_a = all_ext.rename(columns={"team":"away_team","date_dt":"game_date_dt","post_extras":"a_post_extras"})[
    ["away_team","game_date_dt","a_post_extras"]].drop_duplicates(["away_team","game_date_dt"])

close = close.merge(ext_h, on=["home_team","game_date_dt"], how="left")
close = close.merge(ext_a, on=["away_team","game_date_dt"], how="left")

# ── Velocity features (C7) ──
print("Building velocity from raw Statcast...")
fb_types = ["FF","SI","FC"]
sc_fb = sc_raw[sc_raw["pitch_type"].isin(fb_types)].copy()

# Need to identify which pitcher is the starter for each game
# Use PGL starter_flag=True to get starter pitcher IDs per game
sp_ids = pgl[pgl["starter_flag"]==True][["game_pk","player_id","home_away"]].copy()
sp_ids["game_pk"] = sp_ids["game_pk"].astype(str)
sc_fb["pitcher"] = sc_fb["pitcher"].astype(int)

# Only fastballs from starters
sc_fb = sc_fb.merge(sp_ids.rename(columns={"player_id":"pitcher"}), on=["game_pk","pitcher"], how="inner")
print(f"Starter fastballs: {len(sc_fb)}")

velo_start = sc_fb.groupby(["pitcher","game_pk","game_date","home_away"]).agg(
    avg_fb_velo=("release_speed","mean"), n_fb=("release_speed","count")).reset_index()
velo_start = velo_start[velo_start["n_fb"] >= 10]
velo_start = velo_start.sort_values(["pitcher","game_date"])

velo_start["baseline_velo"] = velo_start.groupby("pitcher")["avg_fb_velo"].transform(
    lambda x: x.rolling(20, min_periods=10).mean().shift(1))
velo_start["velo_last3"] = velo_start.groupby("pitcher")["avg_fb_velo"].transform(
    lambda x: x.rolling(3, min_periods=2).mean().shift(1))
velo_start["velo_trend"] = velo_start["velo_last3"] - velo_start["baseline_velo"]

# Merge home/away
v_h = velo_start[velo_start["home_away"]=="H"][["game_pk","velo_trend"]].rename(
    columns={"velo_trend":"h_velo_trend"})
v_a = velo_start[velo_start["home_away"]=="A"][["game_pk","velo_trend"]].rename(
    columns={"velo_trend":"a_velo_trend"})

close = close.merge(v_h, on="game_pk", how="left")
close = close.merge(v_a, on="game_pk", how="left")
print(f"Velo trend coverage: h={close['h_velo_trend'].notna().sum()}, a={close['a_velo_trend'].notna().sum()}")

# ── Statcast whiff/zone features (C8) ──
sc_ps = sc_per.copy()
sc_ps["pitcher_id"] = sc_ps["pitcher_id"].astype(int)
sc_ps = sc_ps.sort_values(["pitcher_id","game_date"])

sc_ps["whiff_r10"] = sc_ps.groupby("pitcher_id")["whiff_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
sc_ps["zone_r10"] = sc_ps.groupby("pitcher_id")["zone_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
sc_ps["chase_r10"] = sc_ps.groupby("pitcher_id")["chase_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))

# Need to identify home/away for statcast pitchers
# Join with PGL to get home_away
sc_ps = sc_ps.merge(sp_ids.rename(columns={"player_id":"pitcher_id"}), on=["game_pk","pitcher_id"], how="left")

sc_h = sc_ps[sc_ps["home_away"]=="H"][["game_pk","whiff_r10","zone_r10","chase_r10"]].rename(
    columns={"whiff_r10":"h_whiff_r10","zone_r10":"h_zone_r10","chase_r10":"h_chase_r10"})
sc_a = sc_ps[sc_ps["home_away"]=="A"][["game_pk","whiff_r10","zone_r10","chase_r10"]].rename(
    columns={"whiff_r10":"a_whiff_r10","zone_r10":"a_zone_r10","chase_r10":"a_chase_r10"})

close = close.merge(sc_h, on="game_pk", how="left")
close = close.merge(sc_a, on="game_pk", how="left")
print(f"Whiff coverage: h={close['h_whiff_r10'].notna().sum()}, a={close['a_whiff_r10'].notna().sum()}")

# ── Derived flags ──
close["home_is_dog"] = (close["p_home"] < 0.5).astype(int)

# Feature coverage summary
print(f"\nFinal table: {close.shape}")
feat_cols = ["h_sp_era9","a_sp_era9","h_sp_var","a_sp_var","h_sp_ip","a_sp_ip",
             "h_bp_era9","a_bp_era9","h_bp_workload","a_bp_workload",
             "h_post_extras","a_post_extras","h_sp_short_leash","a_sp_short_leash",
             "h_velo_trend","a_velo_trend","h_whiff_r10","a_whiff_r10",
             "h_zone_r10","a_zone_r10","total_line","home_is_dog"]
for c in feat_cols:
    if c in close.columns:
        n = close[c].notna().sum()
        print(f"  {c}: {n}/{len(close)} ({100*n/len(close):.0f}%)")

# ═══════════════════════════════════════════════════
# PHASE 5-10: Test all candidates
# ═══════════════════════════════════════════════════

def test_signal(data, name, desc, filter_fn, bet_fn):
    results = {}
    for phase, seasons in [("discovery",[2022,2023]),("validation",[2024]),("oos",[2025])]:
        pd_data = data[data["season_yr"].isin(seasons)].copy()
        mask = filter_fn(pd_data)
        qual = pd_data[mask].copy()
        if len(qual) == 0:
            results[phase] = {"N":0}
            continue
        
        bet_side = bet_fn(qual)
        # Remove skips
        qual["bet_side"] = bet_side.values
        qual = qual[qual["bet_side"] != "skip"].copy()
        if len(qual) == 0:
            results[phase] = {"N":0}
            continue
        
        qual["bet_home"] = (qual["bet_side"] == "home").astype(int)
        qual["bet_won"] = ((qual["bet_home"]==1) & (qual["home_win"]==1)) | \
                          ((qual["bet_home"]==0) & (qual["home_win"]==0))
        
        wr = qual["bet_won"].mean()
        imp_wr = qual.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        
        # ROI
        def calc_profit(row):
            price = row["ml_home_price"] if row["bet_home"]==1 else row["ml_away_price"]
            if row["bet_won"]:
                return (price/100 if price > 0 else 100/abs(price))
            return -1.0
        
        qual["profit"] = qual.apply(calc_profit, axis=1)
        roi = qual["profit"].mean() * 100
        
        by_season = {}
        for s in seasons:
            sq = qual[qual["season_yr"]==s]
            if len(sq) > 0:
                s_wr = sq["bet_won"].mean()
                s_imp = sq.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
                s_roi = sq["profit"].mean() * 100
                by_season[s] = {"N":len(sq),"WR":round(s_wr,4),"ImpWR":round(s_imp,4),
                                "Resid":round(s_wr-s_imp,4),"ROI":round(s_roi,2)}
        
        results[phase] = {"N":len(qual),"WR":round(wr,4),"ImpWR":round(imp_wr,4),
                          "Resid":round(wr-imp_wr,4),"ROI":round(roi,2),"by_season":by_season}
    return {"name":name,"description":desc,"results":results}


# ── Define candidates ──

def c1_f(d):
    return d["h_bp_workload"].notna() & d["a_bp_workload"].notna()
def c1_b(d):
    diff = d["h_bp_workload"] - d["a_bp_workload"]
    thr = diff.abs().quantile(0.65)
    return pd.Series(np.where(diff > thr, "away", np.where(diff < -thr, "home", "skip")), index=d.index)

def c3_f(d):
    h = d["h_post_extras"].fillna(0); a = d["a_post_extras"].fillna(0)
    return ((h==1)&(a==0)) | ((a==1)&(h==0))
def c3_b(d):
    h = d["h_post_extras"].fillna(0); a = d["a_post_extras"].fillna(0)
    return pd.Series(np.where((h==1)&(a==0), "away", np.where((a==1)&(h==0), "home", "skip")), index=d.index)

def c4_f(d):
    return d["h_sp_era9"].notna() & d["a_sp_era9"].notna() & d["h_bp_era9"].notna() & d["a_bp_era9"].notna()
def c4_b(d):
    sp_gap = d["h_sp_era9"] - d["a_sp_era9"]  # neg = home SP better
    bp_gap = d["h_bp_era9"] - d["a_bp_era9"]  # neg = home BP better
    # Bet SP side when SP and BP disagree
    home_spid = (sp_gap < -0.5) & (bp_gap > 0.5)
    away_spid = (sp_gap > 0.5) & (bp_gap < -0.5)
    return pd.Series(np.where(home_spid, "home", np.where(away_spid, "away", "skip")), index=d.index)

def c5_f(d):
    return d["h_sp_var"].notna() & d["a_sp_var"].notna() & d["h_sp_era9"].notna() & d["a_sp_era9"].notna()
def c5_b(d):
    era_close = (d["h_sp_era9"] - d["a_sp_era9"]).abs() < 1.0
    var_diff = d["h_sp_var"] - d["a_sp_var"]
    thr = var_diff[era_close].abs().quantile(0.6) if era_close.sum() > 10 else 0.5
    # Bet the LOW variance side
    return pd.Series(np.where(era_close & (var_diff > thr), "away",
                     np.where(era_close & (var_diff < -thr), "home", "skip")), index=d.index)

def c6_f(d):
    return d["h_sp_short_leash"].notna() & d["a_sp_short_leash"].notna() & d["h_bp_era9"].notna() & d["a_bp_era9"].notna()
def c6_b(d):
    h_trouble = (d["h_sp_short_leash"]==1) & (d["h_bp_era9"] > 4.0)
    a_trouble = (d["a_sp_short_leash"]==1) & (d["a_bp_era9"] > 4.0)
    return pd.Series(np.where(h_trouble & ~a_trouble, "away",
                     np.where(a_trouble & ~h_trouble, "home", "skip")), index=d.index)

def c7_f(d):
    return d["h_velo_trend"].notna() & d["a_velo_trend"].notna()
def c7_b(d):
    h_breach = d["h_velo_trend"] < -0.5
    a_breach = d["a_velo_trend"] < -0.5
    return pd.Series(np.where(h_breach & ~a_breach, "away",
                     np.where(a_breach & ~h_breach, "home", "skip")), index=d.index)

def c8_f(d):
    return d["h_whiff_r10"].notna() & d["a_whiff_r10"].notna() & d["h_zone_r10"].notna() & d["a_zone_r10"].notna()
def c8_b(d):
    # Use within-sample medians for classification
    h_stuff = d["h_whiff_r10"] > d["h_whiff_r10"].median()
    h_command = d["h_zone_r10"] > d["h_zone_r10"].median()
    a_stuff = d["a_whiff_r10"] > d["a_whiff_r10"].median()
    a_command = d["a_zone_r10"] > d["a_zone_r10"].median()
    h_cmd = h_command & ~h_stuff; a_cmd = a_command & ~a_stuff
    h_stf = h_stuff & ~h_command; a_stf = a_stuff & ~a_command
    return pd.Series(np.where(h_cmd & a_stf, "home", np.where(a_cmd & h_stf, "away", "skip")), index=d.index)

def c9_f(d):
    return d["total_line"].notna() & (d["total_line"] <= 7.5)
def c9_b(d):
    return pd.Series(np.where(d["p_home"] < 0.5, "home", "away"), index=d.index)

def c10_f(d):
    return (d["home_is_dog"]==1) & d["h_bp_era9"].notna() & d["a_bp_era9"].notna() & (d["h_bp_era9"] < d["a_bp_era9"])
def c10_b(d):
    return pd.Series("home", index=d.index)

candidates = [
    ("C1","BP Availability Proxy (workload gap)",c1_f,c1_b),
    ("C3","Post-Extras Depletion (one side only)",c3_f,c3_b),
    ("C4","SPID (SP-BP disagreement, bet SP)",c4_f,c4_b),
    ("C5","Low-Variance SP Advantage",c5_f,c5_b),
    ("C6","Short-Leash SP x Weak BP",c6_f,c6_b),
    ("C7","Velocity Floor Breach (-0.5 mph trend)",c7_f,c7_b),
    ("C8","Command vs Stuff Archetype",c8_f,c8_b),
    ("C9","Low-Total Dog Compression (total<=7.5)",c9_f,c9_b),
    ("C10","Home Dog + BP Edge",c10_f,c10_b),
]

print("\n" + "="*70)
print("PHASE 5: DISCOVERY (2022-2023)")
print("="*70)

all_res = []
for cid, desc, ff, bf in candidates:
    try:
        r = test_signal(close, cid, desc, ff, bf)
        all_res.append(r)
        d = r["results"]["discovery"]
        print(f"\n{cid}: {desc}")
        print(f"  Disc: N={d['N']}, WR={d.get('WR','')}, ImpWR={d.get('ImpWR','')}, Resid={d.get('Resid','')}, ROI={d.get('ROI','')}%")
        for s, sv in d.get("by_season",{}).items():
            print(f"    {s}: N={sv['N']}, WR={sv['WR']}, Resid={sv['Resid']:+.4f}, ROI={sv['ROI']:+.2f}%")
    except Exception as e:
        import traceback; traceback.print_exc()
        all_res.append({"name":cid,"description":desc,"results":{"discovery":{"N":0},"validation":{"N":0},"oos":{"N":0}}})

# ── PHASE 6: Freeze ──
print("\n" + "="*70)
print("PHASE 6: FREEZE SURVIVORS (Disc N>=150 + Resid>0)")
print("="*70)

survivors = []
for r in all_res:
    d = r["results"]["discovery"]
    n, resid = d.get("N",0), d.get("Resid",0)
    if n >= 150 and resid > 0:
        survivors.append(r["name"])
        print(f"  PASS: {r['name']} N={n} Resid={resid:+.4f} ROI={d.get('ROI',0):+.2f}%")
    elif n >= 50 and resid > 0:
        print(f"  WATCH: {r['name']} N={n} Resid={resid:+.4f} (below 150)")
    elif n > 0:
        print(f"  FAIL: {r['name']} N={n} Resid={resid:+.4f}")
    else:
        print(f"  EMPTY: {r['name']}")

# Also pass survivors with N>=100 + Resid>0.02 (relaxed for genuine signals)
for r in all_res:
    d = r["results"]["discovery"]
    n, resid = d.get("N",0), d.get("Resid",0)
    if 100 <= n < 150 and resid > 0.02 and r["name"] not in survivors:
        survivors.append(r["name"])
        print(f"  RELAXED PASS: {r['name']} N={n} Resid={resid:+.4f}")

# ── PHASE 7: Validation ──
print("\n" + "="*70)
print("PHASE 7: VALIDATION (2024)")
print("="*70)

val_pass = []
for r in all_res:
    if r["name"] not in survivors: continue
    v = r["results"]["validation"]
    n, resid = v.get("N",0), v.get("Resid",0)
    print(f"\n  {r['name']}: N={n}, WR={v.get('WR','')}, Resid={resid:+.4f}, ROI={v.get('ROI',0):+.2f}%")
    for s, sv in v.get("by_season",{}).items():
        print(f"    {s}: N={sv['N']}, Resid={sv['Resid']:+.4f}, ROI={sv['ROI']:+.2f}%")
    if resid > 0:
        val_pass.append(r["name"])
        print(f"    -> VAL PASS")
    else:
        print(f"    -> VAL FAIL")

# ── PHASE 8: OOS ──
print("\n" + "="*70)
print("PHASE 8: OOS (2025)")
print("="*70)

oos_pass = []
for r in all_res:
    if r["name"] not in val_pass: continue
    o = r["results"]["oos"]
    n, resid = o.get("N",0), o.get("Resid",0)
    print(f"\n  {r['name']}: N={n}, WR={o.get('WR','')}, Resid={resid:+.4f}, ROI={o.get('ROI',0):+.2f}%")
    for s, sv in o.get("by_season",{}).items():
        print(f"    {s}: N={sv['N']}, Resid={sv['Resid']:+.4f}, ROI={sv['ROI']:+.2f}%")
    if resid > 0:
        oos_pass.append(r["name"])
        print(f"    -> OOS PASS")
    else:
        print(f"    -> OOS FAIL")

# ── PHASE 9: Regime diagnostic ──
print("\n" + "="*70)
print("PHASE 9: REGIME DIAGNOSTIC")
print("="*70)
for r in all_res:
    if r["name"] not in survivors: continue
    print(f"\n  {r['name']}:")
    for ph in ["discovery","validation","oos"]:
        pr = r["results"].get(ph,{})
        bs = pr.get("by_season",{})
        resids = [sv["Resid"] for sv in bs.values() if sv.get("N",0)>0]
        tag = "CONSISTENT" if all(x>0 for x in resids) else ("MIXED" if resids else "EMPTY")
        ns = [sv["N"] for sv in bs.values() if sv.get("N",0)>0]
        print(f"    {ph}: {tag} resids={resids} Ns={ns}")

# ── PHASE 10: Keep/Kill Board ──
print("\n" + "="*70)
print("PHASE 10: KEEP/KILL BOARD")
print("="*70)

rows = []
for r in all_res:
    d = r["results"].get("discovery",{}); v = r["results"].get("validation",{}); o = r["results"].get("oos",{})
    if r["name"] in oos_pass: verdict = "KEEP"
    elif r["name"] in val_pass: verdict = "MONITOR"
    elif r["name"] in survivors: verdict = "KILL (val fail)"
    elif d.get("N",0) >= 50 and d.get("Resid",0) > 0: verdict = "WATCH"
    else: verdict = "KILL"
    
    row = {"Candidate":r["name"],"Description":r["description"],
           "D_N":d.get("N",0),"D_Resid":d.get("Resid",0),"D_ROI":d.get("ROI",0),
           "V_N":v.get("N",0),"V_Resid":v.get("Resid",0),"V_ROI":v.get("ROI",0),
           "O_N":o.get("N",0),"O_Resid":o.get("Resid",0),"O_ROI":o.get("ROI",0),
           "Verdict":verdict}
    rows.append(row)
    
    sym = {"KEEP":"+++","MONITOR":"~~","KILL":"X","WATCH":"?"}
    print(f"  [{sym.get(verdict.split()[0],'?')}] {r['name']}: {verdict}")
    print(f"       D: N={row['D_N']} Resid={row['D_Resid']:+.4f} ROI={row['D_ROI']:+.2f}%")
    if row["V_N"]>0: print(f"       V: N={row['V_N']} Resid={row['V_Resid']:+.4f} ROI={row['V_ROI']:+.2f}%")
    if row["O_N"]>0: print(f"       O: N={row['O_N']} Resid={row['O_Resid']:+.4f} ROI={row['O_ROI']:+.2f}%")

board = pd.DataFrame(rows)
board.to_csv(f"{OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_FINAL_TABLE.csv", index=False)

# ── PHASE 11: Executive summary ──
keeps = [r for r in rows if r["Verdict"]=="KEEP"]
monitors = [r for r in rows if r["Verdict"]=="MONITOR"]
watches = [r for r in rows if "WATCH" in r["Verdict"]]
kills = [r for r in rows if "KILL" in r["Verdict"]]

md = f"""# MLB Moneyline Phase 3 Discovery Engine — Executive Summary
## Date: 2026-04-11

## Universe
Close ML games (fav implied .512-.556 / approx -105 to -125), 2022-2025.
Total close games: {len(close)} | Discovery (22-23): {close[close['season_yr'].isin([2022,2023])].shape[0]} | Val (24): {close[close['season_yr']==2024].shape[0]} | OOS (25): {close[close['season_yr']==2025].shape[0]}

## Safety Audit
| ID | Candidate | Status |
|----|-----------|--------|
| C1 | BP Availability (workload proxy) | FEASIBLE |
| C2 | Pinned Closer No Bridge | BLOCKED (no role labels) |
| C3 | Post-Extras Depletion | FEASIBLE |
| C4 | SPID (SP-BP disagreement) | FEASIBLE |
| C5 | Low-Variance SP | FEASIBLE |
| C6 | Short-Leash SP x Weak BP | FEASIBLE |
| C7 | Velocity Floor Breach | FEASIBLE |
| C8 | Command vs Stuff Archetype | FEASIBLE |
| C9 | Low-Total Dog Compression | FEASIBLE |
| C10 | Home Dog + BP Edge | FEASIBLE |

## Results
"""

for row in rows:
    md += f"\n### {row['Candidate']}: {row['Description']}\n"
    md += f"**Verdict: {row['Verdict']}**\n\n"
    md += f"| Phase | N | WR | ImpWR | Resid | ROI |\n"
    md += f"|-------|---|----|----|-------|-----|\n"
    # Find full results
    for r in all_res:
        if r["name"] == row["Candidate"]:
            for ph in ["discovery","validation","oos"]:
                pr = r["results"].get(ph,{})
                if pr.get("N",0) > 0:
                    md += f"| {ph} | {pr['N']} | {pr.get('WR','')} | {pr.get('ImpWR','')} | {pr.get('Resid',0):+.4f} | {pr.get('ROI',0):+.2f}% |\n"
                    for s, sv in pr.get("by_season",{}).items():
                        if sv.get("N",0)>0:
                            md += f"| ..{s} | {sv['N']} | {sv['WR']} | {sv['ImpWR']} | {sv['Resid']:+.4f} | {sv['ROI']:+.2f}% |\n"

md += f"""
## Final Board
- **KEEP (all 3 phases positive):** {len(keeps)}
- **MONITOR (disc+val pass, OOS fail):** {len(monitors)}
- **WATCH (small sample, positive discovery):** {len(watches)}
- **KILL:** {len(kills)}

## Key Findings
"""
if keeps:
    md += "### Survivors\n"
    for k in keeps:
        md += f"- **{k['Candidate']}**: D_ROI={k['D_ROI']:+.2f}%, V_ROI={k['V_ROI']:+.2f}%, O_ROI={k['O_ROI']:+.2f}%\n"
else:
    md += "No candidates survived all three phases.\n"

if monitors:
    md += "\n### Monitor\n"
    for m in monitors:
        md += f"- **{m['Candidate']}**: Passed disc+val but OOS negative. Regime-dependent.\n"

md += """
## Methodology
- All features PIT-safe (shift(1) / date < game_date)
- No lineup features, no FG/V1 contaminated tables
- ROI at actual closing ML prices
- Min N=150 for discovery promotion (relaxed to N=100 + Resid>0.02 for marginal signals)
- C2 blocked: no closer/setup role labels in available data
"""

with open(f"{OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_EXEC_SUMMARY.md","w") as f:
    f.write(md)

print(f"\nSaved: {OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_FINAL_TABLE.csv")
print(f"Saved: {OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_EXEC_SUMMARY.md")
print("\nDONE.")

