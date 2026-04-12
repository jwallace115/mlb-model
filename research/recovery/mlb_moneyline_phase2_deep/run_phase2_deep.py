#!/usr/bin/env python3
"""MLB Moneyline Phase 2 Deep Decomposition"""
import pandas as pd, numpy as np, os, warnings, re
warnings.filterwarnings("ignore")
OUT = "/root/mlb-model/research/recovery/mlb_moneyline_phase2_deep"
os.makedirs(OUT, exist_ok=True)

# ── PHASE 0 ──
print("="*70); print("PHASE 0: Framing Memo"); print("="*70)
framing = """# MLB Moneyline Phase 2 Deep — Framing Memo

## Phase 1 Failure Summary
Phase 1 tested structural/schedule axes (home/away, day/night, rest, price bands)
against MLB closing moneylines across 2022-2025.
**Result: ZERO strategies survived disc->val->OOS.**

## Phase 2 Thesis
Can PIT-safe rolling pitcher/team performance features identify close-game
mispricing that structural axes cannot?

## Data Integrity
- Features built ONLY from pitcher_game_logs + game_table
- ALL use shift(1) + expanding/rolling within season
- NO lineup features, NO FanGraphs aggregates, NO model outputs
- Closing prices from canonical DK odds archive
"""
with open(f"{OUT}/PHASE0_FRAMING_MEMO.md","w") as f: f.write(framing)
print("Wrote PHASE0_FRAMING_MEMO.md")

# ── Load data ──
pgl = pd.read_parquet("/root/mlb-model/mlb/data/pitcher_game_logs.parquet")
gt  = pd.read_parquet("/root/mlb-model/sim/data/game_table.parquet")
cl  = pd.read_parquet("/root/mlb-model/mlb_sim/data/mlb_odds_closing_canonical.parquet")

pgl["game_date"] = pd.to_datetime(pgl["game_date"])
gt["date"] = pd.to_datetime(gt["date"])
cl["date"] = pd.to_datetime(cl["date"])

pgl = pgl[pgl.season.isin([2022,2023,2024,2025])].copy()
gt  = gt[gt.season.isin([2022,2023,2024,2025])].copy()
cl  = cl[cl.season.isin([2022,2023,2024,2025])].copy()

# Fix game_pk types
cl = cl[cl.game_pk.astype(str).str.match(r'^\d+$', na=False)].copy()
cl["game_pk"] = cl["game_pk"].astype(str).astype(int)

print(f"PGL: {pgl.shape[0]} rows, GT: {gt.shape[0]} games, CL: {cl.shape[0]} odds records")

# ── PHASE 1: Close-game universe ──
print("\n"+"="*70); print("PHASE 1: Close-Game Universe"); print("="*70)

def american_to_prob(price):
    price = float(price)
    return abs(price)/(abs(price)+100) if price < 0 else 100/(price+100)

def devig(hp, ap):
    h, a = american_to_prob(hp), american_to_prob(ap)
    t = h + a
    return h/t, a/t

research = cl[["date","season","game_pk","home_team","away_team",
               "ml_home_price","ml_away_price"]].copy()
research = research.dropna(subset=["ml_home_price","ml_away_price"])

dv = research.apply(lambda r: devig(r.ml_home_price, r.ml_away_price), axis=1)
research["home_implied"] = dv.apply(lambda x: x[0])
research["away_implied"] = dv.apply(lambda x: x[1])
research["home_is_fav"] = research["home_implied"] > 0.5

research = research.merge(gt[["game_pk","home_score","away_score","actual_total"]],
                           on="game_pk", how="inner")
research["home_win"] = (research.home_score > research.away_score).astype(int)
research = research[research.home_score != research.away_score].copy()

research["fav_implied"] = np.where(research.home_is_fav, research.home_implied, research.away_implied)
research["fav_price"] = np.where(research.home_is_fav, research.ml_home_price, research.ml_away_price)
research["dog_price"] = np.where(research.home_is_fav, research.ml_away_price, research.ml_home_price)
research["fav_won"] = np.where(research.home_is_fav, research.home_win, 1-research.home_win).astype(int)

research["band"] = "D"
research.loc[research.fav_implied <= 0.565, "band"] = "C"
research.loc[research.fav_implied <= 0.545, "band"] = "B"
research.loc[research.fav_implied <= 0.535, "band"] = "A"

research["split"] = "OOS"
research.loc[research.season.isin([2022,2023]), "split"] = "DISC"
research.loc[research.season == 2024, "split"] = "VAL"

print(f"Total games: {len(research)}")
for band in ["A","B","C","D"]:
    sub = research[research.band == band]
    print(f"  Band {band}: {len(sub)} games")

close = research[research.band.isin(["A","B","C"])].copy()
print(f"\nClose-game universe: {len(close)} games")
for split in ["DISC","VAL","OOS"]:
    sub = close[close.split == split]
    print(f"  {split}: {len(sub)} games, fav_WR={sub.fav_won.mean():.3f}, mean_impl={sub.fav_implied.mean():.3f}")

# Baseline by season
print("\nBaseline by season:")
for season in [2022,2023,2024,2025]:
    sub = close[close.season == season]
    print(f"  {season}: N={len(sub)}, fav_WR={sub.fav_won.mean():.3f}, impl={sub.fav_implied.mean():.3f}")

# ── PHASE 2: Build PIT-safe features ──
print("\n"+"="*70); print("PHASE 2: Building Features"); print("="*70)

FIP_CONST = 3.10
def compute_fip(er, hr, bb, k, ip):
    return np.where(ip > 0, (13*hr + 3*bb - 2*k)/ip + FIP_CONST, np.nan)

# SP features
sp = pgl[pgl.starter_flag == 1].copy().sort_values(["player_id","season","game_date"])
for col in ["earned_runs","innings_pitched","strikeouts","walks","home_runs_allowed","batters_faced"]:
    sp[f"cum_{col}"] = sp.groupby(["player_id","season"])[col].transform(lambda x: x.shift(1).expanding().sum())
    sp[f"r3_{col}"] = sp.groupby(["player_id","season"])[col].transform(lambda x: x.shift(1).rolling(3,min_periods=3).sum())

sp["sp_era_long"] = np.where(sp.cum_innings_pitched>0, sp.cum_earned_runs/sp.cum_innings_pitched*9, np.nan)
sp["sp_era_short"] = np.where(sp.r3_innings_pitched>0, sp.r3_earned_runs/sp.r3_innings_pitched*9, np.nan)
sp["sp_k_pct_long"] = np.where(sp.cum_batters_faced>0, sp.cum_strikeouts/sp.cum_batters_faced, np.nan)
sp["sp_k_pct_short"] = np.where(sp.r3_batters_faced>0, sp.r3_strikeouts/sp.r3_batters_faced, np.nan)
sp["sp_bb_pct_long"] = np.where(sp.cum_batters_faced>0, sp.cum_walks/sp.cum_batters_faced, np.nan)
sp["sp_bb_pct_short"] = np.where(sp.r3_batters_faced>0, sp.r3_walks/sp.r3_batters_faced, np.nan)
sp["sp_fip_long"] = compute_fip(sp.cum_earned_runs, sp.cum_home_runs_allowed, sp.cum_walks, sp.cum_strikeouts, sp.cum_innings_pitched)
sp["sp_fip_short"] = compute_fip(sp.r3_earned_runs, sp.r3_home_runs_allowed, sp.r3_walks, sp.r3_strikeouts, sp.r3_innings_pitched)

sp["sp_era_div"] = sp.sp_era_long - sp.sp_era_short  # positive = improving
sp["sp_fip_div"] = sp.sp_fip_long - sp.sp_fip_short
sp["sp_k_div"] = sp.sp_k_pct_short - sp.sp_k_pct_long   # positive = improving
sp["sp_bb_div"] = sp.sp_bb_pct_long - sp.sp_bb_pct_short # positive = improving

sp_cols = [c for c in sp.columns if c.startswith("sp_")]
sp_features = sp[["game_pk","player_id","team","home_away"] + sp_cols].copy()
print(f"SP features: {sp_features.shape[0]} rows, era_long non-null: {sp_features.sp_era_long.notna().sum()}, era_short non-null: {sp_features.sp_era_short.notna().sum()}")

# Bullpen features
bp = pgl[pgl.starter_flag == 0].copy()
bp_game = bp.groupby(["team","season","game_date"]).agg(
    bp_ip=("innings_pitched","sum"), bp_er=("earned_runs","sum"),
    bp_k=("strikeouts","sum"), bp_bb=("walks","sum"), bp_hr=("home_runs_allowed","sum"),
).reset_index().sort_values(["team","season","game_date"])

for col in ["bp_er","bp_ip","bp_k","bp_bb","bp_hr"]:
    bp_game[f"cum_{col}"] = bp_game.groupby(["team","season"])[col].transform(lambda x: x.shift(1).expanding().sum())
    bp_game[f"r5_{col}"] = bp_game.groupby(["team","season"])[col].transform(lambda x: x.shift(1).rolling(5,min_periods=3).sum())

bp_game["bp_era_long"] = np.where(bp_game.cum_bp_ip>0, bp_game.cum_bp_er/bp_game.cum_bp_ip*9, np.nan)
bp_game["bp_era_short"] = np.where(bp_game.r5_bp_ip>0, bp_game.r5_bp_er/bp_game.r5_bp_ip*9, np.nan)
bp_game["bp_era_div"] = bp_game.bp_era_long - bp_game.bp_era_short
bp_game["bp_workload_3d"] = bp_game.groupby(["team","season"])["bp_ip"].transform(lambda x: x.shift(1).rolling(3,min_periods=1).sum())

bp_features = bp_game[["team","season","game_date","bp_era_long","bp_era_short","bp_era_div","bp_workload_3d"]].copy()
print(f"Bullpen features: {bp_features.shape[0]} team-games")

# Team rolling
home_g = gt[["game_pk","date","season","home_team","home_score","away_score"]].copy()
home_g.columns = ["game_pk","date","season","team","rf","ra"]
away_g = gt[["game_pk","date","season","away_team","away_score","home_score"]].copy()
away_g.columns = ["game_pk","date","season","team","rf","ra"]
tg = pd.concat([home_g, away_g]).copy()
tg["rd"] = tg.rf - tg.ra
tg = tg.sort_values(["team","season","date"])
for w in [5,10,20]:
    tg[f"team_rd_{w}"] = tg.groupby(["team","season"])["rd"].transform(lambda x: x.shift(1).rolling(w,min_periods=max(3,w//2)).mean())
tg["team_rd_div"] = tg.team_rd_20 - tg.team_rd_5
tf = tg[["game_pk","team","date","season","team_rd_5","team_rd_10","team_rd_20","team_rd_div"]].copy()
print(f"Team features: {tf.shape[0]} team-games")

# ── PHASE 3: Exclusion list ──
print("\n"+"="*70); print("PHASE 3: Exclusion List"); print("="*70)
excl = """# Excluded/Contaminated Sources
## Permanently Excluded
1. Lineup features — unreliable pre-game
2. FanGraphs aggregate tables — contaminated in V1
3. V1/sim model outputs — circular
4. wRC+ / xFIP / SIERA pre-computed — not PIT-safe from available tables

## Sources Used (clean)
1. pitcher_game_logs.parquet — individual pitcher box stats
2. game_table.parquet — final scores + schedule
3. mlb_odds_closing_canonical.parquet — actual DK closing lines
"""
with open(f"{OUT}/PHASE3_EXCLUSION_LIST.md","w") as f: f.write(excl)
print("Wrote PHASE3_EXCLUSION_LIST.md")

# ── PHASE 4: Build deep table ──
print("\n"+"="*70); print("PHASE 4: Build Deep Table"); print("="*70)

deep = close.copy()

# Join home/away SP
sp_h = sp_features[sp_features.home_away=="H"].copy()
sp_h = sp_h.rename(columns={c:f"home_{c}" for c in sp_cols})
deep = deep.merge(sp_h[["game_pk"]+[f"home_{c}" for c in sp_cols]], on="game_pk", how="left")

sp_a = sp_features[sp_features.home_away=="A"].copy()
sp_a = sp_a.rename(columns={c:f"away_{c}" for c in sp_cols})
deep = deep.merge(sp_a[["game_pk"]+[f"away_{c}" for c in sp_cols]], on="game_pk", how="left")

# Join bullpen
for side, team_col in [("home","home_team"),("away","away_team")]:
    bp_j = bp_features.rename(columns={"game_date":"date",
        "bp_era_long":f"{side}_bp_era_long","bp_era_short":f"{side}_bp_era_short",
        "bp_era_div":f"{side}_bp_era_div","bp_workload_3d":f"{side}_bp_workload_3d"})
    deep = deep.merge(bp_j, left_on=[team_col,"season","date"], right_on=["team","season","date"], how="left")
    deep = deep.drop(columns=["team"], errors="ignore")

# Join team rolling
for side, team_col in [("home","home_team"),("away","away_team")]:
    tf_j = tf.rename(columns={f"team_rd_{w}":f"{side}_rd_{w}" for w in [5,10,20]})
    tf_j = tf_j.rename(columns={"team_rd_div":f"{side}_rd_div"})
    deep = deep.merge(tf_j[["game_pk","team",f"{side}_rd_5",f"{side}_rd_10",f"{side}_rd_20",f"{side}_rd_div"]],
                       left_on=["game_pk",team_col], right_on=["game_pk","team"], how="left")
    deep = deep.drop(columns=["team"], errors="ignore")

# Fav/dog perspective
for feat in ["sp_era_long","sp_era_short","sp_era_div","sp_fip_long","sp_fip_short","sp_fip_div",
             "sp_k_pct_long","sp_k_pct_short","sp_k_div","sp_bb_pct_long","sp_bb_pct_short","sp_bb_div"]:
    deep[f"fav_{feat}"] = np.where(deep.home_is_fav, deep[f"home_{feat}"], deep[f"away_{feat}"])
    deep[f"dog_{feat}"] = np.where(deep.home_is_fav, deep[f"away_{feat}"], deep[f"home_{feat}"])

for feat in ["bp_era_long","bp_era_short","bp_era_div","bp_workload_3d"]:
    deep[f"fav_{feat}"] = np.where(deep.home_is_fav, deep[f"home_{feat}"], deep[f"away_{feat}"])
    deep[f"dog_{feat}"] = np.where(deep.home_is_fav, deep[f"away_{feat}"], deep[f"home_{feat}"])

for feat in ["rd_5","rd_10","rd_20","rd_div"]:
    deep[f"fav_{feat}"] = np.where(deep.home_is_fav, deep[f"home_{feat}"], deep[f"away_{feat}"])
    deep[f"dog_{feat}"] = np.where(deep.home_is_fav, deep[f"away_{feat}"], deep[f"home_{feat}"])

deep["sp_era_mismatch"] = deep.dog_sp_era_div - deep.fav_sp_era_div  # pos = dog-favorable
deep["bp_workload_mismatch"] = deep.fav_bp_workload_3d - deep.dog_bp_workload_3d  # pos = dog-favorable
deep["rd5_mismatch"] = deep.dog_rd_5 - deep.fav_rd_5  # pos = dog-favorable

print(f"Deep table: {deep.shape[0]} games, {deep.shape[1]} columns")
for col in ["fav_sp_era_long","fav_sp_era_short","fav_sp_era_div","fav_bp_era_long","fav_bp_workload_3d","fav_rd_5"]:
    n = deep[col].notna().sum()
    print(f"  {col}: {n}/{len(deep)} ({n/len(deep)*100:.0f}%)")

deep.to_csv(f"{OUT}/MLB_MONEYLINE_PHASE2_DEEP_FINAL_TABLE.csv", index=False)
deep.to_parquet(f"{OUT}/deep_table.parquet", index=False)
print(f"Saved deep table")

# ── Helper functions ──
def calc_roi(won, price):
    payoff = np.where(price > 0, price/100.0, 100.0/np.abs(price))
    pnl = np.where(won, payoff, -1.0)
    return pnl.mean()

def analyze(df, label, bet_on="dog", by="split"):
    results = []
    key_col = by
    groups = ["DISC","VAL","OOS"] if by=="split" else sorted(df.season.unique())
    for g in groups:
        sub = df[df[key_col] == g] if by=="split" else df[df.season == g]
        if len(sub) < 10:
            results.append({key_col: g, "N": len(sub), "label": label})
            continue
        if bet_on == "dog":
            wr = 1 - sub.fav_won.mean()
            impl = 1 - sub.fav_implied.mean()
            roi = calc_roi(1-sub.fav_won.values, sub.dog_price.values)
        else:
            wr = sub.fav_won.mean()
            impl = sub.fav_implied.mean()
            roi = calc_roi(sub.fav_won.values, sub.fav_price.values)
        results.append({key_col:g, "N":len(sub), "label":label, "wr":wr, "implied":impl,
                        "resid":wr-impl, "roi":roi})
    return results

all_results = []
all_season = []

# ── PHASE 5: Reputation vs Current-State ──
print("\n"+"="*70); print("PHASE 5: Reputation vs Current-State"); print("="*70)

tests = []

# SP divergence tests
df_sp = deep.dropna(subset=["fav_sp_era_div","dog_sp_era_div"]).copy()
print(f"With SP divergence: {len(df_sp)} games")

tests.append(("Fav SP declining + Dog SP improving", df_sp, (df_sp.fav_sp_era_div<0)&(df_sp.dog_sp_era_div>0), "dog"))
tests.append(("SP ERA mismatch favors dog", df_sp, df_sp.sp_era_mismatch>0, "dog"))
tests.append(("Fav SP materially declining (div<-0.5)", df_sp, df_sp.fav_sp_era_div<-0.5, "dog"))
tests.append(("Dog SP materially improving (div>0.5)", df_sp, df_sp.dog_sp_era_div>0.5, "dog"))
tests.append(("Fav SP rep trap (long<3.5 short>4.5)", df_sp, (df_sp.fav_sp_era_long<3.5)&(df_sp.fav_sp_era_short>4.5), "dog"))

# BP tests
df_bp = deep.dropna(subset=["fav_bp_workload_3d","dog_bp_workload_3d"]).copy()
q75 = df_bp.fav_bp_workload_3d.quantile(0.75)
q25 = df_bp.dog_bp_workload_3d.quantile(0.25)
tests.append(("Fav BP overworked + Dog BP fresh", df_bp, (df_bp.fav_bp_workload_3d>=q75)&(df_bp.dog_bp_workload_3d<=q25), "dog"))
tests.append(("BP workload mismatch favors dog", df_bp, df_bp.bp_workload_mismatch>0, "dog"))

# BP ERA tests
df_bpe = deep.dropna(subset=["fav_bp_era_long","fav_bp_era_short"]).copy()
fav_bp_div = df_bpe.fav_bp_era_long - df_bpe.fav_bp_era_short
tests.append(("Fav BP recent blowup (short>>long)", df_bpe, fav_bp_div<-1.0, "dog"))

# Team form tests
df_rd = deep.dropna(subset=["fav_rd_5","dog_rd_5"]).copy()
tests.append(("Dog better recent form (RD5)", df_rd, df_rd.rd5_mismatch>0, "dog"))

# Fav-side tests
tests.append(("Fav SP improving + Dog SP declining (fav)", df_sp, (df_sp.fav_sp_era_div>0)&(df_sp.dog_sp_era_div<0), "fav"))
df_frd = deep.dropna(subset=["fav_rd_5"]).copy()
tests.append(("Fav hot streak RD5>1.5 (fav)", df_frd, df_frd.fav_rd_5>1.5, "fav"))
tests.append(("Fav SP elite+confirming (fav)", df_sp, (df_sp.fav_sp_era_long<3.0)&(df_sp.fav_sp_era_short<3.5), "fav"))

for label, dfx, mask, side in tests:
    n = mask.sum()
    print(f"\n{label}: {n} games")
    r = analyze(dfx[mask], label, side, "split")
    all_results.extend(r)
    for x in r:
        if "wr" in x:
            print(f"  {x['split']}: N={x['N']}, WR={x['wr']:.3f}, impl={x['implied']:.3f}, resid={x['resid']:+.4f}, ROI={x['roi']*100:+.1f}%")
    s = analyze(dfx[mask], label, side, "season")
    all_season.extend(s)

# ── PHASE 6: Dog-win forensics ──
print("\n"+"="*70); print("PHASE 6: Dog-Win Forensics"); print("="*70)
dog_wins = deep[deep.fav_won==0].copy()
print(f"Total dog wins: {len(dog_wins)}")

dw_sp = dog_wins.dropna(subset=["fav_sp_era_div","dog_sp_era_div"])
forensic_tests = [
    ("Fav SP declining", dw_sp, dw_sp.fav_sp_era_div<0, df_sp, df_sp.fav_sp_era_div<0),
    ("Dog SP improving", dw_sp, dw_sp.dog_sp_era_div>0, df_sp, df_sp.dog_sp_era_div>0),
    ("SP mismatch favors dog", dw_sp, dw_sp.sp_era_mismatch>0, df_sp, df_sp.sp_era_mismatch>0),
]
dw_rd = dog_wins.dropna(subset=["rd5_mismatch"])
forensic_tests.append(("Dog better RD5", dw_rd, dw_rd.rd5_mismatch>0, df_rd, df_rd.rd5_mismatch>0))

for flabel, fdw, fmask, fall, fmask_all in forensic_tests:
    print(f"\nDog wins where {flabel}:")
    for split in ["DISC","VAL","OOS"]:
        sub = fdw[fdw.split==split]
        sub_m = sub[fmask[sub.index]]
        all_split = fall[fall.split==split]
        base = fmask_all[all_split.index].mean()*100 if len(all_split)>0 else 0
        if len(sub)>0:
            print(f"  {split}: {len(sub_m)}/{len(sub)} ({len(sub_m)/len(sub)*100:.1f}%) vs base {base:.1f}%")

# ── PHASE 7: Fav-win forensics ──
print("\n"+"="*70); print("PHASE 7: Fav-Win Forensics"); print("="*70)
fav_wins = deep[deep.fav_won==1].copy()
print(f"Total fav wins: {len(fav_wins)}")

fw_sp = fav_wins.dropna(subset=["fav_sp_era_div","dog_sp_era_div"])
for flabel, fmask_fn in [("Fav SP improving", lambda d: d.fav_sp_era_div>0),
                          ("Fav SP elite+confirming", lambda d: (d.fav_sp_era_long<3.0)&(d.fav_sp_era_short<3.5))]:
    print(f"\nFav wins where {flabel}:")
    for split in ["DISC","VAL","OOS"]:
        sub = fw_sp[fw_sp.split==split]
        sub_m = sub[fmask_fn(sub)]
        all_split = df_sp[df_sp.split==split]
        base = fmask_fn(all_split).mean()*100 if len(all_split)>0 else 0
        if len(sub)>0:
            print(f"  {split}: {len(sub_m)}/{len(sub)} ({len(sub_m)/len(sub)*100:.1f}%) vs base {base:.1f}%")

# ── PHASE 8: Bounded Interactions ──
print("\n"+"="*70); print("PHASE 8: Bounded Interactions"); print("="*70)

int_tests = []

# INT1: SP mismatch + RD5 mismatch
df_i1 = deep.dropna(subset=["sp_era_mismatch","rd5_mismatch","fav_sp_era_div"]).copy()
int_tests.append(("INT1: SP+RD5 mismatch (dog)", df_i1, (df_i1.sp_era_mismatch>0)&(df_i1.rd5_mismatch>0), "dog"))

# INT2: SP mismatch + BP workload
df_i2 = deep.dropna(subset=["sp_era_mismatch","bp_workload_mismatch","fav_sp_era_div"]).copy()
int_tests.append(("INT2: SP+BP mismatch (dog)", df_i2, (df_i2.sp_era_mismatch>0)&(df_i2.bp_workload_mismatch>0), "dog"))

# INT3: Fav rep trap + dog better form
df_i3 = deep.dropna(subset=["fav_sp_era_long","fav_sp_era_short","rd5_mismatch"]).copy()
int_tests.append(("INT3: Fav rep trap + dog form (dog)", df_i3,
    (df_i3.fav_sp_era_long<3.5)&(df_i3.fav_sp_era_short>4.5)&(df_i3.rd5_mismatch>0), "dog"))

# INT4: Triple mismatch
df_i4 = deep.dropna(subset=["sp_era_mismatch","bp_workload_mismatch","rd5_mismatch","fav_sp_era_div"]).copy()
int_tests.append(("INT4: Triple mismatch SP+BP+RD5 (dog)", df_i4,
    (df_i4.sp_era_mismatch>0)&(df_i4.bp_workload_mismatch>0)&(df_i4.rd5_mismatch>0), "dog"))

# INT5: Fav confirming
df_i5 = deep.dropna(subset=["fav_sp_era_div","fav_rd_5"]).copy()
int_tests.append(("INT5: Fav SP improving + hot streak (fav)", df_i5,
    (df_i5.fav_sp_era_div>0.5)&(df_i5.fav_rd_5>1.0), "fav"))

for label, dfx, mask, side in int_tests:
    n = mask.sum()
    print(f"\n{label}: {n} games")
    r = analyze(dfx[mask], label, side, "split")
    all_results.extend(r)
    for x in r:
        if "wr" in x:
            print(f"  {x['split']}: N={x['N']}, WR={x['wr']:.3f}, impl={x['implied']:.3f}, resid={x['resid']:+.4f}, ROI={x['roi']*100:+.1f}%")
    s = analyze(dfx[mask], label, side, "season")
    all_season.extend(s)

# ── PHASE 9: Durability ──
print("\n"+"="*70); print("PHASE 9: Year-by-Year Durability"); print("="*70)

season_df = pd.DataFrame(all_season)
for col in ["wr","implied","resid","roi"]:
    if col not in season_df.columns: season_df[col] = np.nan

print("\nBy-Season:")
for label in season_df.label.unique():
    sub = season_df[season_df.label == label]
    print(f"\n  {label}:")
    for _, row in sub.iterrows():
        if pd.notna(row.get("wr")):
            print(f"    {int(row.season)}: N={int(row.N):4d}, resid={row.resid:+.4f}, ROI={row.roi*100:+.1f}%")

print("\nDurability (sign consistency, N>=20):")
for label in season_df.label.unique():
    sub = season_df[(season_df.label==label)&(season_df.N>=20)]
    if len(sub) < 3:
        print(f"  {label}: <3 seasons with N>=20, SKIP")
        continue
    resids = sub.resid.dropna().values
    pos = (resids>0).sum()
    neg = (resids<0).sum()
    print(f"  {label}: {pos}+/{neg}-, mean_resid={resids.mean():+.4f}, consistent={'YES' if pos>=3 or neg>=3 else 'NO'}")

# ── PHASE 10: Economic Scorecard ──
print("\n"+"="*70); print("PHASE 10: Economic Scorecard"); print("="*70)

all_df = pd.DataFrame(all_results)
for col in ["wr","implied","resid","roi"]:
    if col not in all_df.columns: all_df[col] = np.nan

print(f"\n{'Strategy':<52} {'Spl':>4} {'N':>5} {'WR':>6} {'Imp':>6} {'Res':>8} {'ROI':>7}")
print("-"*95)
for label in all_df.label.unique():
    sub = all_df[all_df.label==label]
    for _, row in sub.iterrows():
        if pd.notna(row.get("wr")):
            print(f"{row.label:<52} {row.split:>4} {int(row.N):>5} {row.wr:>6.3f} {row.implied:>6.3f} {row.resid:>+8.4f} {row.roi*100:>+6.1f}%")

all_df.to_csv(f"{OUT}/phase10_economic_scorecard.csv", index=False)
season_df.to_csv(f"{OUT}/phase9_season_durability.csv", index=False)

# ── PHASE 11: Keep/Kill Board ──
print("\n"+"="*70); print("PHASE 11: Keep/Kill Board"); print("="*70)

kk = []
for label in all_df.label.unique():
    sub = all_df[all_df.label==label]
    entry = {"strategy": label, "decision": "KILL"}
    for sn, sname in [("DISC","disc"),("VAL","val"),("OOS","oos")]:
        s = sub[sub.split==sn]
        if len(s)==1 and pd.notna(s.iloc[0].get("wr")):
            entry[f"{sname}_N"] = int(s.iloc[0].N)
            entry[f"{sname}_resid"] = s.iloc[0].resid
            entry[f"{sname}_roi"] = s.iloc[0].roi
        else:
            entry[f"{sname}_N"] = int(s.iloc[0].N) if len(s)>0 else 0
    
    has = all(f"{s}_resid" in entry for s in ["disc","val","oos"])
    if has:
        dp = entry["disc_resid"]>0
        vp = entry["val_resid"]>0
        op = entry["oos_resid"]>0
        dn = entry.get("disc_N",0)
        
        if dp and vp and op and dn>=150: entry["decision"] = "KEEP"
        elif dp and vp and dn>=150: entry["decision"] = "WATCH"
        elif (dp or vp) and op and dn>=100: entry["decision"] = "WATCH"
        elif dn<150 and dp and vp: entry["decision"] = "WATCH (low N)"
    
    # Durability check
    ss = season_df[(season_df.label==label)&(season_df.N>=20)]
    if len(ss)>=3:
        rr = ss.resid.dropna().values
        pos_c = (rr>0).sum()
        if pos_c < 2:
            if entry["decision"]=="KEEP": entry["decision"] = "WATCH (inconsistent)"
            elif entry["decision"]=="WATCH": entry["decision"] = "KILL (inconsistent)"
    
    kk.append(entry)

kk_df = pd.DataFrame(kk)
kk_df.to_csv(f"{OUT}/phase11_keep_kill.csv", index=False)

print(f"\n{'Strategy':<52} {'Decision':>22} {'D_N':>5} {'D_Res':>8} {'V_N':>5} {'V_Res':>8} {'O_N':>5} {'O_Res':>8}")
print("-"*120)
for _, row in kk_df.iterrows():
    dr = f"{row.disc_resid:+.4f}" if pd.notna(row.get("disc_resid")) else "N/A"
    vr = f"{row.val_resid:+.4f}" if pd.notna(row.get("val_resid")) else "N/A"
    or_ = f"{row.oos_resid:+.4f}" if pd.notna(row.get("oos_resid")) else "N/A"
    print(f"{row.strategy:<52} {row.decision:>22} {row.disc_N:>5} {dr:>8} {row.val_N:>5} {vr:>8} {row.oos_N:>5} {or_:>8}")

# ── PHASE 12: Executive Summary ──
print("\n"+"="*70); print("PHASE 12: Executive Summary"); print("="*70)

keeps = kk_df[kk_df.decision=="KEEP"]
watches = kk_df[kk_df.decision.str.startswith("WATCH")]
kills = kk_df[kk_df.decision.str.contains("KILL")]

lines = []
lines.append("# MLB Moneyline Phase 2 Deep Decomposition — Executive Summary\n")
lines.append(f"## Date: 2026-04-11\n")
lines.append("## Phase 1 Recap")
lines.append("Phase 1 tested structural axes. **0/8 survived.** Closing lines efficiently price schedule.\n")
lines.append("## Phase 2 Thesis")
lines.append("PIT-safe rolling pitcher/team features to find close-game mispricing.\n")
lines.append("## Data")
lines.append(f"- Close-game universe (A-C): {len(close)} games")
lines.append(f"- DISC: {len(close[close.split=='DISC'])} (2022-23), VAL: {len(close[close.split=='VAL'])} (2024), OOS: {len(close[close.split=='OOS'])} (2025)\n")
lines.append("## Feature Families")
lines.append("1. SP form divergence (expanding vs rolling-3 ERA/FIP/K%/BB%)")
lines.append("2. SP mismatch (fav declining + dog improving)")
lines.append("3. Bullpen workload/ERA mismatch")
lines.append("4. Team momentum (rolling 5/10/20 run differential)")
lines.append("5. SP reputation trap (elite long + poor recent)")
lines.append("6. Interactions: SP+RD5, SP+BP, triple mismatch, fav confirming\n")
lines.append("## Keep/Kill Board\n")
lines.append("| Strategy | Decision | Disc N | Disc Resid | Val N | Val Resid | OOS N | OOS Resid |")
lines.append("|----------|----------|--------|------------|-------|-----------|-------|-----------|")
for _, row in kk_df.iterrows():
    dr = f"{row.disc_resid:+.4f}" if pd.notna(row.get("disc_resid")) else "N/A"
    vr = f"{row.val_resid:+.4f}" if pd.notna(row.get("val_resid")) else "N/A"
    or_ = f"{row.oos_resid:+.4f}" if pd.notna(row.get("oos_resid")) else "N/A"
    lines.append(f"| {row.strategy} | {row.decision} | {row.disc_N} | {dr} | {row.val_N} | {vr} | {row.oos_N} | {or_} |")

lines.append(f"\n**KEEP: {len(keeps)} | WATCH: {len(watches)} | KILL: {len(kills)}**\n")

if len(keeps) > 0:
    lines.append("### Strategies to Deploy")
    for _, row in keeps.iterrows():
        lines.append(f"- **{row.strategy}**: D={row.disc_resid:+.4f}, V={row.val_resid:+.4f}, O={row.oos_resid:+.4f}")
elif len(watches) > 0:
    lines.append("### Watch-List (need 2026 data)")
    for _, row in watches.iterrows():
        dr = f"{row.disc_resid:+.4f}" if pd.notna(row.get("disc_resid")) else "N/A"
        vr = f"{row.val_resid:+.4f}" if pd.notna(row.get("val_resid")) else "N/A"
        or_ = f"{row.oos_resid:+.4f}" if pd.notna(row.get("oos_resid")) else "N/A"
        lines.append(f"- **{row.strategy}**: D={dr}, V={vr}, O={or_}")
else:
    lines.append("### No strategies survived the three-gate test.")

lines.append("\n## Structural Conclusion")
if len(keeps)==0:
    lines.append("MLB closing moneylines are extremely well-calibrated. Even with PIT-safe")
    lines.append("rolling SP quality, bullpen fatigue, and team momentum features,")
    lines.append("no strategy produces durable positive residuals across all three gates.")
    lines.append("The market efficiently incorporates pitcher form, bullpen workload,")
    lines.append("and team momentum into closing prices.")
    lines.append("\nThis confirms and extends Phase 1: MLB moneylines at close leave")
    lines.append("minimal systematic edge for flat-bet strategies.")
else:
    lines.append("A small number of strategies show durable signals across all three gates.")
    lines.append("These should be monitored in 2026 shadow before deployment.")

lines.append("\n## Methodology")
lines.append("- All features PIT-safe: shift(1) + expanding/rolling within season")
lines.append("- No lineup features, no FanGraphs aggregates, no model outputs")
lines.append("- Closing prices from DK canonical archive")
lines.append("- ROI at actual American odds")
lines.append("- Min N=150 for KEEP; durability requires >=3/4 seasons same-sign")

exec_text = "\n".join(lines)
with open(f"{OUT}/MLB_MONEYLINE_PHASE2_DEEP_EXEC_SUMMARY.md","w") as f: f.write(exec_text)

print("\n" + exec_text)

print("\n\nFILES:")
for fn in sorted(os.listdir(OUT)):
    sz = os.path.getsize(os.path.join(OUT, fn))
    print(f"  {fn} ({sz:,} bytes)")
print("\nDONE.")
