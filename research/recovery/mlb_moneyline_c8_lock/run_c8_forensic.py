#!/usr/bin/env python3
"""
C8 Forensic Lock + Shadow Design
Complete rebuild, fragility audit, interaction diagnostic, micro-band, feasibility.
"""
import pandas as pd
import numpy as np
import warnings, os, json
warnings.filterwarnings("ignore")

OUT = "research/recovery/mlb_moneyline_c8_lock"
os.makedirs(OUT, exist_ok=True)

# ═══════════════════════════════════════════════════
# PHASE 0: REBUILD DATA (exact replica of discovery v2)
# ═══════════════════════════════════════════════════
print("="*70)
print("PHASE 0: REBUILDING DATA")
print("="*70)

pgl = pd.read_parquet("mlb/data/pitcher_game_logs.parquet")
sc_per = pd.read_parquet("research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet")
canon = pd.read_parquet("mlb_sim/data/mlb_odds_closing_canonical.parquet")
gt = pd.read_parquet("sim/data/game_table.parquet")

pgl["game_pk"] = pgl["game_pk"].astype(str)
canon["game_pk"] = canon["game_pk"].astype(str)
gt["game_pk"] = gt["game_pk"].astype(str)
sc_per["game_pk"] = sc_per["game_pk"].astype(str)
pgl["game_date"] = pd.to_datetime(pgl["game_date"])
sc_per["game_date"] = pd.to_datetime(sc_per["game_date"])

# Base table
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

df["close_game"] = df[["p_home","p_away"]].max(axis=1).between(0.512, 0.556)
close = df[df["close_game"]].copy()
close["game_date"] = pd.to_datetime(close["date"])
close["season_yr"] = close["game_date"].dt.year
print(f"Close games: {len(close)}")
print(f"By season: {close.groupby('season_yr').size().to_dict()}")

# SP features for pitcher IDs (needed for statcast merge)
sp = pgl[pgl["starter_flag"]==True].copy()
sp = sp.sort_values(["player_id","game_date"])
sp_ids = sp[["game_pk","player_id","home_away"]].copy()

# Statcast whiff/zone features (exact C8 method)
sc_ps = sc_per.copy()
sc_ps["pitcher_id"] = sc_ps["pitcher_id"].astype(int)
sc_ps = sc_ps.sort_values(["pitcher_id","game_date"])

sc_ps["whiff_r10"] = sc_ps.groupby("pitcher_id")["whiff_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
sc_ps["zone_r10"] = sc_ps.groupby("pitcher_id")["zone_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))

sp_ids_sc = sp_ids.rename(columns={"player_id":"pitcher_id"})
sp_ids_sc["pitcher_id"] = sp_ids_sc["pitcher_id"].astype(int)
sc_ps = sc_ps.merge(sp_ids_sc, on=["game_pk","pitcher_id"], how="left")

sc_h = sc_ps[sc_ps["home_away"]=="H"][["game_pk","pitcher_id","whiff_r10","zone_r10"]].rename(
    columns={"whiff_r10":"h_whiff_r10","zone_r10":"h_zone_r10","pitcher_id":"h_pitcher_id"})
sc_a = sc_ps[sc_ps["home_away"]=="A"][["game_pk","pitcher_id","whiff_r10","zone_r10"]].rename(
    columns={"whiff_r10":"a_whiff_r10","zone_r10":"a_zone_r10","pitcher_id":"a_pitcher_id"})

close = close.merge(sc_h, on="game_pk", how="left")
close = close.merge(sc_a, on="game_pk", how="left")
close["home_is_dog"] = (close["p_home"] < 0.5).astype(int)

print(f"Whiff coverage: h={close['h_whiff_r10'].notna().sum()}, a={close['a_whiff_r10'].notna().sum()}")
print(f"Zone  coverage: h={close['h_zone_r10'].notna().sum()}, a={close['a_zone_r10'].notna().sum()}")

# C8 filter + bet logic (exact replica)
def c8_filter(d):
    return d["h_whiff_r10"].notna() & d["a_whiff_r10"].notna() & d["h_zone_r10"].notna() & d["a_zone_r10"].notna()

def c8_bet(d):
    h_stuff = d["h_whiff_r10"] > d["h_whiff_r10"].median()
    h_command = d["h_zone_r10"] > d["h_zone_r10"].median()
    a_stuff = d["a_whiff_r10"] > d["a_whiff_r10"].median()
    a_command = d["a_zone_r10"] > d["a_zone_r10"].median()
    h_cmd = h_command & ~h_stuff
    a_cmd = a_command & ~a_stuff
    h_stf = h_stuff & ~h_command
    a_stf = a_stuff & ~a_command
    return pd.Series(np.where(h_cmd & a_stf, "home",
                     np.where(a_cmd & h_stf, "away", "skip")), index=d.index)

# ═══════════════════════════════════════════════════
# PHASE 1: REBUILD MATCHED SAMPLE
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("PHASE 1: REBUILD MATCHED SAMPLE")
print("="*70)

def run_c8(data, label):
    mask = c8_filter(data)
    qual = data[mask].copy()
    bet_side = c8_bet(qual)
    qual["bet_side"] = bet_side.values
    qual = qual[qual["bet_side"] != "skip"].copy()
    qual["bet_home"] = (qual["bet_side"] == "home").astype(int)
    qual["bet_won"] = ((qual["bet_home"]==1) & (qual["home_win"]==1)) | \
                      ((qual["bet_home"]==0) & (qual["home_win"]==0))
    
    def calc_profit(row):
        price = row["ml_home_price"] if row["bet_home"]==1 else row["ml_away_price"]
        if row["bet_won"]:
            return (price/100 if price > 0 else 100/abs(price))
        return -1.0
    qual["profit"] = qual.apply(calc_profit, axis=1)
    
    if len(qual) == 0:
        return None
    
    wr = qual["bet_won"].mean()
    imp = qual.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
    roi = qual["profit"].mean() * 100
    
    print(f"  {label}: N={len(qual)}, WR={wr:.4f}, ImpWR={imp:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")
    return qual

# Full sample
c8_all = run_c8(close, "ALL")

# By phase
for phase, seasons in [("Discovery 22-23",[2022,2023]),("Val 24",[2024]),("OOS 25",[2025])]:
    run_c8(close[close["season_yr"].isin(seasons)], phase)

# By season
for yr in [2022, 2023, 2024, 2025]:
    run_c8(close[close["season_yr"]==yr], f"  {yr}")

# By side
for side in ["home","away"]:
    sub = c8_all[c8_all["bet_side"]==side]
    if len(sub) > 0:
        wr = sub["bet_won"].mean()
        imp = sub.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = sub["profit"].mean() * 100
        print(f"  Side={side}: N={len(sub)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# By orientation (home fav/dog)
for ori_label, cond in [("HomeFav+BetHome", (c8_all["home_is_dog"]==0) & (c8_all["bet_home"]==1)),
                         ("HomeFav+BetAway", (c8_all["home_is_dog"]==0) & (c8_all["bet_home"]==0)),
                         ("HomeDog+BetHome", (c8_all["home_is_dog"]==1) & (c8_all["bet_home"]==1)),
                         ("HomeDog+BetAway", (c8_all["home_is_dog"]==1) & (c8_all["bet_home"]==0))]:
    sub = c8_all[cond]
    if len(sub) > 5:
        wr = sub["bet_won"].mean()
        imp = sub.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = sub["profit"].mean() * 100
        print(f"  {ori_label}: N={len(sub)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# ═══════════════════════════════════════════════════
# PHASE 2: FRAGILITY AUDIT
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("PHASE 2: FRAGILITY AUDIT")
print("="*70)

# By team
print("\n--- By team (command side being bet on) ---")
c8_all["bet_team"] = np.where(c8_all["bet_home"]==1, c8_all["home_team"], c8_all["away_team"])
team_stats = c8_all.groupby("bet_team").agg(
    N=("bet_won","count"), wins=("bet_won","sum"), roi=("profit","mean")).reset_index()
team_stats["wr"] = team_stats["wins"] / team_stats["N"]
team_stats["roi"] = team_stats["roi"] * 100
team_stats = team_stats.sort_values("N", ascending=False)
print(team_stats.head(15).to_string(index=False))

# Concentration: top 5 teams share of total
top5_n = team_stats.head(5)["N"].sum()
print(f"\nTop 5 teams: {top5_n}/{len(c8_all)} = {100*top5_n/len(c8_all):.1f}%")
print(f"Total unique teams: {c8_all['bet_team'].nunique()}")

# By pitcher (command side pitcher)
print("\n--- By pitcher (command-side pitcher) ---")
c8_all["cmd_pitcher"] = np.where(c8_all["bet_home"]==1, c8_all["h_pitcher_id"], c8_all["a_pitcher_id"])
pitcher_stats = c8_all.groupby("cmd_pitcher").agg(
    N=("bet_won","count"), wins=("bet_won","sum"), roi=("profit","mean")).reset_index()
pitcher_stats["wr"] = pitcher_stats["wins"] / pitcher_stats["N"]
pitcher_stats["roi"] = pitcher_stats["roi"] * 100
pitcher_stats = pitcher_stats.sort_values("N", ascending=False)
print(f"Unique command-side pitchers: {len(pitcher_stats)}")
print(f"Top 10 by N:")
print(pitcher_stats.head(10).to_string(index=False))
top5_p = pitcher_stats.head(5)["N"].sum()
print(f"\nTop 5 pitchers: {top5_p}/{len(c8_all)} = {100*top5_p/len(c8_all):.1f}%")

# ═══════════════════════════════════════════════════
# PHASE 3: INTERACTION DIAGNOSTIC
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("PHASE 3: INTERACTION DIAGNOSTIC")
print("="*70)

# Does the signal come from the interaction or just one component?
mask_all = c8_filter(close)
qual_full = close[mask_all].copy()

# Test 1: Command-side only (bet the pitcher with higher zone_r10, regardless of opponent)
print("\n--- Command-only: bet higher zone_r10 side ---")
qual_t1 = qual_full.copy()
qual_t1["bet_home"] = (qual_t1["h_zone_r10"] > qual_t1["a_zone_r10"]).astype(int)
qual_t1["bet_won"] = ((qual_t1["bet_home"]==1) & (qual_t1["home_win"]==1)) | \
                      ((qual_t1["bet_home"]==0) & (qual_t1["home_win"]==0))
def calc_p(row):
    price = row["ml_home_price"] if row["bet_home"]==1 else row["ml_away_price"]
    if row["bet_won"]: return (price/100 if price > 0 else 100/abs(price))
    return -1.0
qual_t1["profit"] = qual_t1.apply(calc_p, axis=1)
for ph, ss in [("All",list(range(2022,2026))),("Disc",[2022,2023]),("Val",[2024]),("OOS",[2025])]:
    sub = qual_t1[qual_t1["season_yr"].isin(ss)]
    if len(sub) > 0:
        wr = sub["bet_won"].mean()
        imp = sub.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = sub["profit"].mean() * 100
        print(f"  {ph}: N={len(sub)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# Test 2: Stuff-only: bet against the higher whiff_r10 side
print("\n--- Anti-stuff: bet against higher whiff_r10 side ---")
qual_t2 = qual_full.copy()
qual_t2["bet_home"] = (qual_t2["h_whiff_r10"] < qual_t2["a_whiff_r10"]).astype(int)
qual_t2["bet_won"] = ((qual_t2["bet_home"]==1) & (qual_t2["home_win"]==1)) | \
                      ((qual_t2["bet_home"]==0) & (qual_t2["home_win"]==0))
qual_t2["profit"] = qual_t2.apply(calc_p, axis=1)
for ph, ss in [("All",list(range(2022,2026))),("Disc",[2022,2023]),("Val",[2024]),("OOS",[2025])]:
    sub = qual_t2[qual_t2["season_yr"].isin(ss)]
    if len(sub) > 0:
        wr = sub["bet_won"].mean()
        imp = sub.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = sub["profit"].mean() * 100
        print(f"  {ph}: N={len(sub)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# Test 3: Zone rate gap as continuous predictor
print("\n--- Zone gap (top quartile gap, bet higher zone) ---")
qual_t3 = qual_full.copy()
qual_t3["zone_gap"] = qual_t3["h_zone_r10"] - qual_t3["a_zone_r10"]
q75 = qual_t3["zone_gap"].abs().quantile(0.75)
qual_t3_big = qual_t3[qual_t3["zone_gap"].abs() >= q75].copy()
qual_t3_big["bet_home"] = (qual_t3_big["zone_gap"] > 0).astype(int)
qual_t3_big["bet_won"] = ((qual_t3_big["bet_home"]==1) & (qual_t3_big["home_win"]==1)) | \
                          ((qual_t3_big["bet_home"]==0) & (qual_t3_big["home_win"]==0))
qual_t3_big["profit"] = qual_t3_big.apply(calc_p, axis=1)
for ph, ss in [("All",list(range(2022,2026))),("Disc",[2022,2023]),("Val",[2024]),("OOS",[2025])]:
    sub = qual_t3_big[qual_t3_big["season_yr"].isin(ss)]
    if len(sub) > 0:
        wr = sub["bet_won"].mean()
        imp = sub.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = sub["profit"].mean() * 100
        print(f"  {ph}: N={len(sub)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# Test 4: Whiff gap as continuous predictor
print("\n--- Whiff gap (top quartile gap, bet lower whiff) ---")
qual_t4 = qual_full.copy()
qual_t4["whiff_gap"] = qual_t4["h_whiff_r10"] - qual_t4["a_whiff_r10"]
q75w = qual_t4["whiff_gap"].abs().quantile(0.75)
qual_t4_big = qual_t4[qual_t4["whiff_gap"].abs() >= q75w].copy()
qual_t4_big["bet_home"] = (qual_t4_big["whiff_gap"] < 0).astype(int)  # bet lower whiff
qual_t4_big["bet_won"] = ((qual_t4_big["bet_home"]==1) & (qual_t4_big["home_win"]==1)) | \
                          ((qual_t4_big["bet_home"]==0) & (qual_t4_big["home_win"]==0))
qual_t4_big["profit"] = qual_t4_big.apply(calc_p, axis=1)
for ph, ss in [("All",list(range(2022,2026))),("Disc",[2022,2023]),("Val",[2024]),("OOS",[2025])]:
    sub = qual_t4_big[qual_t4_big["season_yr"].isin(ss)]
    if len(sub) > 0:
        wr = sub["bet_won"].mean()
        imp = sub.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = sub["profit"].mean() * 100
        print(f"  {ph}: N={len(sub)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# ═══════════════════════════════════════════════════
# PHASE 4: MICRO-BAND STABILITY
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("PHASE 4: MICRO-BAND STABILITY")
print("="*70)

c8_all["fav_imp"] = c8_all[["p_home","p_away"]].max(axis=1)
bands = [(0.512, 0.525, "0.512-0.525"), (0.525, 0.540, "0.525-0.540"), (0.540, 0.556, "0.540-0.556")]
for lo, hi, label in bands:
    sub = c8_all[(c8_all["fav_imp"] >= lo) & (c8_all["fav_imp"] < hi)]
    if len(sub) > 3:
        wr = sub["bet_won"].mean()
        imp = sub.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = sub["profit"].mean() * 100
        print(f"  {label}: N={len(sub)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# ═══════════════════════════════════════════════════
# PHASE 5: LIVE FEASIBILITY
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("PHASE 5: LIVE FEASIBILITY")
print("="*70)

# Check what's in pitcher_game_logs
print("\n--- pitcher_game_logs columns ---")
for c in sorted(pgl.columns):
    if any(x in c.lower() for x in ['whiff', 'zone', 'swing', 'strike', 'called', 'chase',
                                      'k_pct', 'bb_pct', 'k_rate', 'bb_rate']):
        print(f"  {c}: non-null={pgl[c].notna().sum()}")

# Check statcast per-start columns
print("\n--- statcast per_start columns ---")
for c in sorted(sc_per.columns):
    print(f"  {c}: non-null={sc_per[c].notna().sum()}")

# Can we derive from PGL?
print("\n--- PGL basic columns ---")
for c in ['strikeouts','walks','batters_faced','innings_pitched','pitches']:
    if c in pgl.columns:
        print(f"  {c}: non-null={pgl[c].notna().sum()}")

# Key question: can whiff_rate and zone_rate be computed from PGL?
# whiff_rate = swinging_strikes / swings (needs pitch-level data)
# zone_rate = in-zone pitches / total pitches (needs pitch-level data)
# These are Statcast-only metrics

# Check statcast per-start data availability by year
print("\n--- Statcast per-start coverage by year ---")
sc_per["year"] = sc_per["game_date"].dt.year
for yr in [2022, 2023, 2024, 2025]:
    n = sc_per[sc_per["year"]==yr].shape[0]
    print(f"  {yr}: {n} starts")

# Check if we can use PGL K% and BB% as proxy
if "batters_faced" in pgl.columns:
    sp_pgl = pgl[pgl["starter_flag"]==True].copy()
    sp_pgl["k_pct"] = sp_pgl["strikeouts"] / sp_pgl["batters_faced"]
    sp_pgl["bb_pct"] = sp_pgl["walks"] / sp_pgl["batters_faced"]
    print("\n--- PGL K%/BB% proxy stats ---")
    print(f"  K% mean={sp_pgl['k_pct'].mean():.3f}, std={sp_pgl['k_pct'].std():.3f}")
    print(f"  BB% mean={sp_pgl['bb_pct'].mean():.3f}, std={sp_pgl['bb_pct'].std():.3f}")
    
    # Check correlation between PGL K% and Statcast whiff_rate
    # Merge on game_pk + pitcher_id
    sp_pgl["pitcher_id"] = sp_pgl["player_id"].astype(int)
    sc_check = sc_per[["game_pk","pitcher_id","whiff_rate","zone_rate"]].copy()
    sc_check["pitcher_id"] = sc_check["pitcher_id"].astype(int)
    merged = sp_pgl.merge(sc_check, on=["game_pk","pitcher_id"], how="inner")
    print(f"\n--- PGL vs Statcast correlation (N={len(merged)}) ---")
    print(f"  corr(K%, whiff_rate) = {merged['k_pct'].corr(merged['whiff_rate']):.3f}")
    print(f"  corr(BB%, zone_rate) = {merged['bb_pct'].corr(merged['zone_rate']):.3f}")
    print(f"  corr(BB%, 1-zone_rate) = {merged['bb_pct'].corr(1-merged['zone_rate']):.3f}")

# ═══════════════════════════════════════════════════
# PHASE 5b: ALTERNATIVE C8 USING PGL K%/BB% PROXY
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("PHASE 5b: PGL K%/BB% PROXY C8")
print("="*70)

if "batters_faced" in pgl.columns:
    sp2 = pgl[pgl["starter_flag"]==True].copy()
    sp2 = sp2.sort_values(["player_id","game_date"])
    sp2["k_pct"] = sp2["strikeouts"] / sp2["batters_faced"].clip(lower=1)
    sp2["bb_pct"] = sp2["walks"] / sp2["batters_faced"].clip(lower=1)
    
    sp2["k_pct_r10"] = sp2.groupby("player_id")["k_pct"].transform(
        lambda x: x.rolling(10, min_periods=5).mean().shift(1))
    sp2["bb_pct_r10"] = sp2.groupby("player_id")["bb_pct"].transform(
        lambda x: x.rolling(10, min_periods=5).mean().shift(1))
    
    # Home/away split
    sp2_h = sp2[sp2["home_away"]=="H"][["game_pk","player_id","k_pct_r10","bb_pct_r10"]].rename(
        columns={"k_pct_r10":"h_kpct_r10","bb_pct_r10":"h_bbpct_r10","player_id":"h_sp_pid"})
    sp2_a = sp2[sp2["home_away"]=="A"][["game_pk","player_id","k_pct_r10","bb_pct_r10"]].rename(
        columns={"k_pct_r10":"a_kpct_r10","bb_pct_r10":"a_bbpct_r10","player_id":"a_sp_pid"})
    
    close2 = close.copy()
    close2 = close2.merge(sp2_h, on="game_pk", how="left")
    close2 = close2.merge(sp2_a, on="game_pk", how="left")
    
    # C8-proxy: "command" = low BB%, "stuff" = high K%
    # Bet command side when facing stuff side
    def c8_proxy_filter(d):
        return d["h_kpct_r10"].notna() & d["a_kpct_r10"].notna() & d["h_bbpct_r10"].notna() & d["a_bbpct_r10"].notna()
    
    def c8_proxy_bet(d):
        # Command = low BB% (below median), Stuff = high K% (above median)
        h_stuff = d["h_kpct_r10"] > d["h_kpct_r10"].median()
        h_command = d["h_bbpct_r10"] < d["h_bbpct_r10"].median()  # low BB% = command
        a_stuff = d["a_kpct_r10"] > d["a_kpct_r10"].median()
        a_command = d["a_bbpct_r10"] < d["a_bbpct_r10"].median()
        h_cmd = h_command & ~h_stuff
        a_cmd = a_command & ~a_stuff
        h_stf = h_stuff & ~h_command
        a_stf = a_stuff & ~a_command
        return pd.Series(np.where(h_cmd & a_stf, "home",
                         np.where(a_cmd & h_stf, "away", "skip")), index=d.index)
    
    print("\n--- C8 Proxy (PGL K%/BB%) ---")
    for ph, ss in [("Disc",[2022,2023]),("Val",[2024]),("OOS",[2025])]:
        sub = close2[close2["season_yr"].isin(ss)].copy()
        mask = c8_proxy_filter(sub)
        qual = sub[mask].copy()
        bet_side = c8_proxy_bet(qual)
        qual["bet_side"] = bet_side.values
        qual = qual[qual["bet_side"] != "skip"].copy()
        if len(qual) == 0:
            print(f"  {ph}: N=0")
            continue
        qual["bet_home"] = (qual["bet_side"] == "home").astype(int)
        qual["bet_won"] = ((qual["bet_home"]==1) & (qual["home_win"]==1)) | \
                          ((qual["bet_home"]==0) & (qual["home_win"]==0))
        qual["profit"] = qual.apply(calc_p, axis=1)
        wr = qual["bet_won"].mean()
        imp = qual.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
        roi = qual["profit"].mean() * 100
        print(f"  {ph}: N={len(qual)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# ═══════════════════════════════════════════════════
# PHASE 6: MEDIAN LEAK DIAGNOSTIC
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("PHASE 6: MEDIAN LEAK DIAGNOSTIC")
print("="*70)

# C8 uses within-sample medians — a leak concern
# Test with FIXED thresholds from discovery only
disc_data = close[close["season_yr"].isin([2022,2023])].copy()
disc_mask = c8_filter(disc_data)
disc_qual = disc_data[disc_mask]
whiff_med = disc_qual["h_whiff_r10"].median()  # proxy: use home side median
zone_med = disc_qual["h_zone_r10"].median()
print(f"Discovery medians: whiff={whiff_med:.4f}, zone={zone_med:.4f}")

# Also get all-data medians per side
for side in ['h','a']:
    w = close[c8_filter(close)][f"{side}_whiff_r10"].median()
    z = close[c8_filter(close)][f"{side}_zone_r10"].median()
    print(f"  All-data {side} medians: whiff={w:.4f}, zone={z:.4f}")

# Re-run C8 with FROZEN discovery medians
def c8_frozen_bet(d, w_med, z_med):
    h_stuff = d["h_whiff_r10"] > w_med
    h_command = d["h_zone_r10"] > z_med
    a_stuff = d["a_whiff_r10"] > w_med
    a_command = d["a_zone_r10"] > z_med
    h_cmd = h_command & ~h_stuff
    a_cmd = a_command & ~a_stuff
    h_stf = h_stuff & ~h_command
    a_stf = a_stuff & ~a_command
    return pd.Series(np.where(h_cmd & a_stf, "home",
                     np.where(a_cmd & h_stf, "away", "skip")), index=d.index)

print("\n--- C8 with FROZEN discovery medians ---")
for ph, ss in [("Disc",[2022,2023]),("Val",[2024]),("OOS",[2025])]:
    sub = close[close["season_yr"].isin(ss)].copy()
    mask = c8_filter(sub)
    qual = sub[mask].copy()
    bet_side = c8_frozen_bet(qual, whiff_med, zone_med)
    qual["bet_side"] = bet_side.values
    qual = qual[qual["bet_side"] != "skip"].copy()
    if len(qual) == 0:
        print(f"  {ph}: N=0")
        continue
    qual["bet_home"] = (qual["bet_side"] == "home").astype(int)
    qual["bet_won"] = ((qual["bet_home"]==1) & (qual["home_win"]==1)) | \
                      ((qual["bet_home"]==0) & (qual["home_win"]==0))
    qual["profit"] = qual.apply(calc_p, axis=1)
    wr = qual["bet_won"].mean()
    imp = qual.apply(lambda r: r["p_home"] if r["bet_home"]==1 else r["p_away"], axis=1).mean()
    roi = qual["profit"].mean() * 100
    print(f"  {ph}: N={len(qual)}, WR={wr:.4f}, Resid={wr-imp:+.4f}, ROI={roi:+.2f}%")

# ═══════════════════════════════════════════════════
# SAVE FINAL TABLE
# ═══════════════════════════════════════════════════
print("\n" + "="*70)
print("SAVING OUTPUTS")
print("="*70)

if c8_all is not None:
    save_cols = ["game_pk","date","home_team","away_team","season_yr",
                 "ml_home_price","ml_away_price","p_home","p_away",
                 "home_win","h_whiff_r10","a_whiff_r10","h_zone_r10","a_zone_r10",
                 "bet_side","bet_home","bet_won","profit","fav_imp"]
    save_cols = [c for c in save_cols if c in c8_all.columns]
    c8_all[save_cols].to_csv(f"{OUT}/C8_SHADOW_FINAL_TABLE.csv", index=False)
    print(f"Saved C8_SHADOW_FINAL_TABLE.csv: {len(c8_all)} rows")

print("\nDONE")
