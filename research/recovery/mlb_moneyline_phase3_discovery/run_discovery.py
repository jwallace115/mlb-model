#!/usr/bin/env python3
"""
MLB Moneyline Phase 3 Bounded Discovery Engine
Discovery: 2022-2023 | Validation: 2024 | OOS: 2025
"""
import pandas as pd
import numpy as np
import warnings, os, json
warnings.filterwarnings("ignore")

OUT = "research/recovery/mlb_moneyline_phase3_discovery"
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────────────────────────
# PHASE 1+2: Ingest candidates + Safety audit
# ─────────────────────────────────────────────
print("=" * 70)
print("PHASE 2: FEATURE SAFETY AUDIT")
print("=" * 70)

pgl = pd.read_parquet("mlb/data/pitcher_game_logs.parquet")
sc_per = pd.read_parquet("research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet")
sc_raw = pd.read_parquet("research/statcast_enrichment/pitcher_statcast_2022_2025_raw.parquet")

audit = {}

# C1: Top-2 HLI Arm Availability — needs per-appearance leverage index
# PGL has no LI columns. No play-by-play LI data available.
# PROXY: use reliever workload (IP last 3 days) as availability proxy
audit["C1"] = "FEASIBLE WITH PROXY — no LI data, use reliever workload as availability proxy"

# C2: Pinned Closer No Bridge — needs bullpen role structure
# No closer/setup role labels in PGL. Can proxy via save opportunities from boxscores.
audit["C2"] = "BLOCKED — no role labels (closer/setup) in available data"

# C3: Post-Extras HLI Depletion — needs extras detection + reliever workload
# game_table has innings_played. PGL has reliever appearances. FEASIBLE.
audit["C3"] = "FEASIBLE — extras from game_table innings_played, reliever workload from PGL"

# C4: SPID (SP-Gap vs BP-Gap same price) — needs SP quality gap + BP quality gap
# PGL has starter ERA/K/BB. Reliever ERA computable. FEASIBLE.
audit["C4"] = "FEASIBLE — SP metrics from PGL, BP metrics from PGL relievers"

# C5: Same-Mean-Different-Volatility SP — needs SP start-to-start variance
# PGL has runs_allowed per start. Can compute rolling std. FEASIBLE.
audit["C5"] = "FEASIBLE — runs_allowed variance from PGL starter logs"

# C6: Short-Leash SP x Weak BP — needs SP innings per start + BP quality
# PGL has innings_pitched per start + reliever ERA. FEASIBLE.
audit["C6"] = "FEASIBLE — SP avg IP from PGL, BP ERA from PGL relievers"

# C7: Velocity Floor Breach — needs per-start fastball velocity
# Raw statcast has release_speed + pitch_type. Can compute FF avg velo per start. FEASIBLE.
audit["C7"] = "FEASIBLE — release_speed in raw Statcast, filter pitch_type for fastballs"

# C8: Command x Stuff Archetype Mismatch — needs whiff% + zone%
# Statcast per-start has whiff_rate, zone_rate, chase_rate. FEASIBLE.
audit["C8"] = "FEASIBLE — whiff_rate, zone_rate, chase_rate in Statcast per-start"

# C9: Low-Total Variance Compression — needs total line + close ML game
# Canon has total_line + ML prices. FEASIBLE.
audit["C9"] = "FEASIBLE — total_line in canonical odds"

# C10: Home Dog + HLI BP Edge — needs home/away designation + BP quality
# Canon has home/away + ML prices. PGL has reliever ERA. FEASIBLE.
audit["C10"] = "FEASIBLE — home_team designation + BP quality from PGL"

for k, v in sorted(audit.items()):
    status = "SAFE" if "FEASIBLE" in v else "BLOCKED"
    print(f"  {k}: [{status}] {v}")

blocked = [k for k,v in audit.items() if "BLOCKED" in v]
approved = [k for k,v in audit.items() if "BLOCKED" not in v]
print(f"\nBlocked: {blocked}")
print(f"Approved: {approved}")

# ─────────────────────────────────────────────
# PHASE 3: Lock approved candidates
# ─────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 3: APPROVED CANDIDATE BOARD")
print("=" * 70)
for c in approved:
    print(f"  {c}: {audit[c]}")

# ─────────────────────────────────────────────
# PHASE 4: Build discovery table
# ─────────────────────────────────────────────
print("\n" + "=" * 70)
print("PHASE 4: BUILD DISCOVERY TABLE")
print("=" * 70)

# Load core tables
canon = pd.read_parquet("mlb_sim/data/mlb_odds_closing_canonical.parquet")
gt = pd.read_parquet("sim/data/game_table.parquet")

canon["game_pk"] = canon["game_pk"].astype(str)
gt["game_pk"] = gt["game_pk"].astype(str)

# Merge
df = canon.merge(gt[["game_pk","home_score","away_score","home_rest_days","away_rest_days",
                      "local_start_hour","park_factor_runs","innings_played","temperature",
                      "wind_speed","wind_direction","roof_status"]], on="game_pk", how="inner")

# Remove ties (rain-shortened, etc.)
df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)
df = df[df["home_score"] != df["away_score"]].copy()

# De-vig
def to_imp(p):
    if pd.isna(p) or p == 0: return np.nan
    return 100/(p+100) if p > 0 else abs(p)/(abs(p)+100)

df["raw_h"] = df["ml_home_price"].apply(to_imp)
df["raw_a"] = df["ml_away_price"].apply(to_imp)
df["vig"] = df["raw_h"] + df["raw_a"]
df["p_home"] = df["raw_h"] / df["vig"]
df["p_away"] = df["raw_a"] / df["vig"]

# Close-game universe: both sides within 0.444-0.556 implied
df["close_game"] = df[["p_home","p_away"]].max(axis=1).between(0.512, 0.556)
close = df[df["close_game"]].copy()
close["game_date"] = pd.to_datetime(close["date"])
close["season"] = close["game_date"].dt.year

print(f"Total games with odds+results: {len(df)}")
print(f"Close games (fav -105 to -125): {len(close)}")
print(f"Close by season: {close.groupby('season').size().to_dict()}")

# ── Build PIT-safe features ──

# 4A: SP rolling features from PGL
pgl["game_date"] = pd.to_datetime(pgl["game_date"])
sp = pgl[pgl["starter_flag"] == True].copy()
sp = sp.sort_values(["player_id","game_date"])

# Rolling features (shift(1) for PIT safety)
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

# SP K rate and BB rate per 9
sp["sp_k9_r10"] = (sp["sp_k_r10"] / sp["sp_ip_r10"].clip(lower=0.1)) * 9
sp["sp_bb9_r10"] = (sp["sp_bb_r10"] / sp["sp_ip_r10"].clip(lower=0.1)) * 9
sp["sp_era9_r10"] = (sp["sp_era_r10"] / sp["sp_ip_r10"].clip(lower=0.1)) * 9

# Variance feature for C5
sp["sp_var_r10"] = sp["sp_runs_std_r10"]

# Short leash proxy for C6: avg IP < 5.0
sp["sp_short_leash"] = (sp["sp_ip_r10"] < 5.0).astype(int)

sp["game_pk"] = sp["game_pk"].astype(str)
sp_home = sp[sp["home_away"]=="home"][["game_pk","player_id","sp_era9_r10","sp_k9_r10","sp_bb9_r10",
    "sp_ip_r10","sp_var_r10","sp_short_leash","sp_runs_std_r5"]].rename(
    columns=lambda c: f"h_{c}" if c not in ["game_pk"] else c)
sp_away = sp[sp["home_away"]=="away"][["game_pk","player_id","sp_era9_r10","sp_k9_r10","sp_bb9_r10",
    "sp_ip_r10","sp_var_r10","sp_short_leash","sp_runs_std_r5"]].rename(
    columns=lambda c: f"a_{c}" if c not in ["game_pk"] else c)

close = close.merge(sp_home, on="game_pk", how="left")
close = close.merge(sp_away, on="game_pk", how="left")

# 4B: Team bullpen rolling ERA from PGL relievers
rel = pgl[pgl["starter_flag"] == False].copy()
rel["game_date"] = pd.to_datetime(rel["game_date"])
rel = rel.sort_values(["game_date"])

# Aggregate by team+date: total reliever ER and IP
rel_team = rel.groupby(["team","game_date"]).agg(
    bp_er=("earned_runs","sum"),
    bp_ip=("innings_pitched","sum"),
    bp_appearances=("player_id","count")
).reset_index()
rel_team = rel_team.sort_values(["team","game_date"])

# Rolling BP ERA (last 10 team games, shift(1))
rel_team["bp_era_r10"] = rel_team.groupby("team")["bp_er"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
rel_team["bp_ip_r10"] = rel_team.groupby("team")["bp_ip"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
rel_team["bp_era9_r10"] = (rel_team["bp_era_r10"] / rel_team["bp_ip_r10"].clip(lower=0.1)) * 9

# Rolling BP workload last 3 games (for C1 availability proxy)
rel_team["bp_ip_r3"] = rel_team.groupby("team")["bp_ip"].transform(
    lambda x: x.rolling(3, min_periods=1).sum().shift(1))

# C3: Post-extras flag — did team play extras yesterday?
gt_extras = gt[["game_pk","home_team","away_team","date","innings_played"]].copy()
gt_extras["date"] = pd.to_datetime(gt_extras["date"])
gt_extras["extras"] = (gt_extras["innings_played"] > 9).astype(int)

# For home team
home_ext = gt_extras[["home_team","date","extras"]].rename(columns={"home_team":"team"})
away_ext = gt_extras[["away_team","date","extras"]].rename(columns={"away_team":"team"})
all_ext = pd.concat([home_ext, away_ext]).sort_values(["team","date"])
all_ext["played_extras_prev"] = all_ext.groupby("team")["extras"].shift(1)

# Merge BP features to close games
close["game_date_dt"] = pd.to_datetime(close["date"])

# Home BP
h_bp = rel_team[["team","game_date","bp_era9_r10","bp_ip_r3"]].rename(
    columns={"team":"home_team","game_date":"game_date_dt","bp_era9_r10":"h_bp_era9","bp_ip_r3":"h_bp_workload"})
# Need to match on team + date — use game-level merge through gt
# Actually, let's merge through game_pk using the PGL team assignments

# Simpler: compute BP stats per game_pk
rel_gp = rel.groupby(["game_pk","team"]).agg(
    bp_er=("earned_runs","sum"),
    bp_ip=("innings_pitched","sum")
).reset_index()
rel_gp["game_pk"] = rel_gp["game_pk"].astype(str)

# Need the rolling version — let me merge via team+date from rel_team
# Match close games to rel_team via home_team + date
close_dt = close.copy()
h_bp_merge = rel_team[["team","game_date","bp_era9_r10","bp_ip_r3"]].copy()
h_bp_merge = h_bp_merge.rename(columns={"team":"home_team","game_date":"game_date_dt",
    "bp_era9_r10":"h_bp_era9","bp_ip_r3":"h_bp_workload"})
close_dt = close_dt.merge(h_bp_merge, on=["home_team","game_date_dt"], how="left")

a_bp_merge = rel_team[["team","game_date","bp_era9_r10","bp_ip_r3"]].copy()
a_bp_merge = a_bp_merge.rename(columns={"team":"away_team","game_date":"game_date_dt",
    "bp_era9_r10":"a_bp_era9","bp_ip_r3":"a_bp_workload"})
close_dt = close_dt.merge(a_bp_merge, on=["away_team","game_date_dt"], how="left")

# C3: Post-extras depletion
ext_h = all_ext[["team","date","played_extras_prev"]].rename(
    columns={"team":"home_team","date":"game_date_dt","played_extras_prev":"h_post_extras"})
ext_a = all_ext[["team","date","played_extras_prev"]].rename(
    columns={"team":"away_team","date":"game_date_dt","played_extras_prev":"a_post_extras"})
close_dt = close_dt.merge(ext_h, on=["home_team","game_date_dt"], how="left")
close_dt = close_dt.merge(ext_a, on=["away_team","game_date_dt"], how="left")

# 4C: Statcast velocity features for C7
print("Building velocity features from raw Statcast...")
# Filter fastballs only
fb_types = ["FF","SI","FC"]  # four-seam, sinker, cutter
sc_fb = sc_raw[sc_raw["pitch_type"].isin(fb_types)].copy()
sc_fb["game_date"] = pd.to_datetime(sc_fb["game_date"])

# Per-start average fastball velocity
velo_start = sc_fb.groupby(["pitcher","game_date","game_pk"]).agg(
    avg_fb_velo=("release_speed","mean"),
    n_fb=("release_speed","count")
).reset_index()
velo_start = velo_start[velo_start["n_fb"] >= 10]  # min 10 fastballs
velo_start = velo_start.sort_values(["pitcher","game_date"])

# Rolling baseline velo (20-start window, shift(1))
velo_start["baseline_velo"] = velo_start.groupby("pitcher")["avg_fb_velo"].transform(
    lambda x: x.rolling(20, min_periods=10).mean().shift(1))
velo_start["velo_delta"] = velo_start["avg_fb_velo"] - velo_start["baseline_velo"]

# For C7: we need PRE-GAME velo trend, not same-game velo
# Use last-3-start trend as predictor
velo_start["velo_last3"] = velo_start.groupby("pitcher")["avg_fb_velo"].transform(
    lambda x: x.rolling(3, min_periods=2).mean().shift(1))
velo_start["velo_trend"] = velo_start["velo_last3"] - velo_start["baseline_velo"]

# Merge to SP table via game_pk + pitcher_id
# Need to match pitcher_id in our SP table to pitcher in statcast (both are MLB IDs)
velo_merge = velo_start[["pitcher","game_pk","velo_trend","velo_last3","baseline_velo"]].copy()
velo_merge["game_pk"] = velo_merge["game_pk"].astype(str)

# Home SP velocity
close_dt = close_dt.merge(
    velo_merge.rename(columns={"pitcher":"h_player_id","velo_trend":"h_velo_trend",
                                "velo_last3":"h_velo_last3","baseline_velo":"h_baseline_velo"}),
    left_on=["game_pk","h_player_id"], right_on=["game_pk","h_player_id"], how="left")

close_dt = close_dt.merge(
    velo_merge.rename(columns={"pitcher":"a_player_id","velo_trend":"a_velo_trend",
                                "velo_last3":"a_velo_last3","baseline_velo":"a_baseline_velo"}),
    left_on=["game_pk","a_player_id"], right_on=["game_pk","a_player_id"], how="left")

# 4D: Statcast whiff/zone features for C8
sc_ps = sc_per.copy()
sc_ps["game_date"] = pd.to_datetime(sc_ps["game_date"])
sc_ps = sc_ps.sort_values(["pitcher_id","game_date"])

# Rolling whiff_rate and zone_rate (shift(1))
sc_ps["whiff_r10"] = sc_ps.groupby("pitcher_id")["whiff_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
sc_ps["zone_r10"] = sc_ps.groupby("pitcher_id")["zone_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
sc_ps["chase_r10"] = sc_ps.groupby("pitcher_id")["chase_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))
sc_ps["barrel_r10"] = sc_ps.groupby("pitcher_id")["barrel_rate"].transform(
    lambda x: x.rolling(10, min_periods=5).mean().shift(1))

sc_merge = sc_ps[["pitcher_id","game_pk","whiff_r10","zone_r10","chase_r10","barrel_r10"]].copy()
sc_merge["game_pk"] = sc_merge["game_pk"].astype(str)

close_dt = close_dt.merge(
    sc_merge.rename(columns={"pitcher_id":"h_player_id","whiff_r10":"h_whiff_r10",
        "zone_r10":"h_zone_r10","chase_r10":"h_chase_r10","barrel_r10":"h_barrel_r10"}),
    on=["game_pk","h_player_id"], how="left")
close_dt = close_dt.merge(
    sc_merge.rename(columns={"pitcher_id":"a_player_id","whiff_r10":"a_whiff_r10",
        "zone_r10":"a_zone_r10","chase_r10":"a_chase_r10","barrel_r10":"a_barrel_r10"}),
    on=["game_pk","a_player_id"], how="left")

# C9: Low-total close game — just total_line
# Already in close_dt from canon

# C10: Home dog flag
close_dt["home_is_dog"] = (close_dt["p_home"] < 0.5).astype(int)

# Feature coverage
print(f"\nFinal table: {close_dt.shape}")
feat_cols = ["h_sp_era9_r10","a_sp_era9_r10","h_sp_var_r10","a_sp_var_r10",
             "h_bp_era9","a_bp_era9","h_bp_workload","a_bp_workload",
             "h_post_extras","a_post_extras","h_sp_ip_r10","a_sp_ip_r10",
             "h_velo_trend","a_velo_trend","h_whiff_r10","a_whiff_r10",
             "h_zone_r10","a_zone_r10","total_line","home_is_dog"]
for c in feat_cols:
    if c in close_dt.columns:
        n = close_dt[c].notna().sum()
        print(f"  {c}: {n}/{len(close_dt)} ({100*n/len(close_dt):.0f}%)")

# ─────────────────────────────────────────────
# PHASE 5-8: Discovery → Validation → OOS
# ─────────────────────────────────────────────

def compute_ml_roi(sub, bet_col, price_col):
    """Compute ROI betting on the identified side at actual closing ML prices."""
    bets = sub[sub[bet_col] == 1].copy()
    if len(bets) == 0:
        return np.nan, 0
    prices = bets[price_col]
    wins = bets["bet_won"]
    profits = []
    for price, won in zip(prices, wins):
        if won:
            if price > 0:
                profits.append(price / 100)
            else:
                profits.append(100 / abs(price))
        else:
            profits.append(-1.0)
    roi = np.mean(profits) * 100
    return roi, len(bets)

def test_candidate(data, name, description, filter_fn, bet_side_fn, discovery_seasons=[2022,2023],
                   val_seasons=[2024], oos_seasons=[2025]):
    """
    Test a candidate signal.
    filter_fn(df) -> boolean mask for qualifying games
    bet_side_fn(df) -> 'home' or 'away' Series indicating which side to bet
    """
    results = {}
    
    for phase, seasons in [("discovery", discovery_seasons), ("validation", val_seasons), ("oos", oos_seasons)]:
        phase_data = data[data["season"].isin(seasons)].copy()
        mask = filter_fn(phase_data)
        qual = phase_data[mask].copy()
        
        if len(qual) == 0:
            results[phase] = {"N": 0, "msg": "No qualifying games"}
            continue
        
        bet_side = bet_side_fn(qual)
        qual["bet_home"] = (bet_side == "home").astype(int)
        qual["bet_won"] = ((qual["bet_home"] == 1) & (qual["home_win"] == 1)) | \
                          ((qual["bet_home"] == 0) & (qual["home_win"] == 0))
        
        # Actual win rate
        wr = qual["bet_won"].mean()
        
        # Implied win rate (what we'd need to break even)
        imp_list = []
        for _, row in qual.iterrows():
            if row["bet_home"] == 1:
                imp_list.append(row["p_home"])
            else:
                imp_list.append(row["p_away"])
        imp_wr = np.mean(imp_list)
        
        # Residual
        residual = wr - imp_wr
        
        # ROI at actual prices
        qual["bet_price"] = qual.apply(
            lambda r: r["ml_home_price"] if r["bet_home"] == 1 else r["ml_away_price"], axis=1)
        
        profits = []
        for _, row in qual.iterrows():
            price = row["bet_price"]
            won = row["bet_won"]
            if won:
                if price > 0:
                    profits.append(price / 100)
                else:
                    profits.append(100 / abs(price))
            else:
                profits.append(-1.0)
        roi = np.mean(profits) * 100
        
        # By season
        by_season = {}
        for s in seasons:
            sq = qual[qual["season"] == s]
            if len(sq) > 0:
                s_wr = sq["bet_won"].mean()
                s_imp = np.mean([r["p_home"] if r["bet_home"]==1 else r["p_away"] for _,r in sq.iterrows()])
                s_profits = []
                for _, row in sq.iterrows():
                    price = row["bet_price"]
                    won = row["bet_won"]
                    if won:
                        if price > 0: s_profits.append(price/100)
                        else: s_profits.append(100/abs(price))
                    else:
                        s_profits.append(-1.0)
                s_roi = np.mean(s_profits) * 100
                by_season[s] = {"N": len(sq), "WR": round(s_wr,4), "ImpWR": round(s_imp,4),
                                "Resid": round(s_wr-s_imp,4), "ROI": round(s_roi,2)}
            else:
                by_season[s] = {"N": 0}
        
        results[phase] = {
            "N": len(qual), "WR": round(wr,4), "ImpWR": round(imp_wr,4),
            "Resid": round(residual,4), "ROI": round(roi,2), "by_season": by_season
        }
    
    return {"name": name, "description": description, "results": results}


# ── CANDIDATE DEFINITIONS ──

# C1: BP Availability Proxy — bet against team with high recent BP workload
def c1_filter(d):
    return d["h_bp_workload"].notna() & d["a_bp_workload"].notna()

def c1_bet(d):
    # Bet against team with highest BP workload (most taxed pen)
    # If home BP more worked, bet away; vice versa
    diff = d["h_bp_workload"] - d["a_bp_workload"]
    # Only bet when gap is meaningful (top quartile of differences)
    threshold = diff.abs().quantile(0.65)
    # Bet against the more worked bullpen
    return pd.Series(np.where(diff > threshold, "away",
                              np.where(diff < -threshold, "home", "skip")),
                     index=d.index)

def c1_filter_strict(d):
    base = d["h_bp_workload"].notna() & d["a_bp_workload"].notna()
    diff = (d["h_bp_workload"] - d["a_bp_workload"]).abs()
    return base & (diff >= diff[base].quantile(0.65))

# C3: Post-Extras Depletion — bet against team that played extras yesterday
def c3_filter(d):
    h = d["h_post_extras"].fillna(0)
    a = d["a_post_extras"].fillna(0)
    return (h == 1) | (a == 1)  # at least one team played extras yesterday

def c3_bet(d):
    h = d["h_post_extras"].fillna(0)
    a = d["a_post_extras"].fillna(0)
    # Bet against the team that played extras (or if both, skip)
    return pd.Series(np.where((h==1) & (a==0), "away",
                              np.where((a==1) & (h==0), "home", "skip")),
                     index=d.index)

def c3_filter_strict(d):
    h = d["h_post_extras"].fillna(0)
    a = d["a_post_extras"].fillna(0)
    return ((h==1) & (a==0)) | ((a==1) & (h==0))  # exactly one team

# C4: SPID — bet the side where SP is better but BP is worse (hidden structure)
def c4_filter(d):
    return (d["h_sp_era9_r10"].notna() & d["a_sp_era9_r10"].notna() &
            d["h_bp_era9"].notna() & d["a_bp_era9"].notna())

def c4_bet(d):
    # SP gap: lower ERA = better
    sp_gap = d["h_sp_era9_r10"] - d["a_sp_era9_r10"]  # negative = home SP better
    bp_gap = d["h_bp_era9"] - d["a_bp_era9"]  # negative = home BP better
    
    # SPID: SP says one thing, BP says opposite — bet SP side (SP matters more for ML)
    # Home SP better but home BP worse
    home_spid = (sp_gap < -0.5) & (bp_gap > 0.5)
    # Away SP better but away BP worse
    away_spid = (sp_gap > 0.5) & (bp_gap < -0.5)
    
    return pd.Series(np.where(home_spid, "home",
                              np.where(away_spid, "away", "skip")),
                     index=d.index)

def c4_filter_strict(d):
    base = c4_filter(d)
    sp_gap = d["h_sp_era9_r10"] - d["a_sp_era9_r10"]
    bp_gap = d["h_bp_era9"] - d["a_bp_era9"]
    home_spid = (sp_gap < -0.5) & (bp_gap > 0.5)
    away_spid = (sp_gap > 0.5) & (bp_gap < -0.5)
    return base & (home_spid | away_spid)

# C5: Same-Mean-Different-Volatility SP — bet the MORE volatile SP (upside)
def c5_filter(d):
    return (d["h_sp_var_r10"].notna() & d["a_sp_var_r10"].notna() &
            d["h_sp_era9_r10"].notna() & d["a_sp_era9_r10"].notna())

def c5_bet(d):
    # Similar ERA but different variance
    era_diff = (d["h_sp_era9_r10"] - d["a_sp_era9_r10"]).abs()
    var_diff = d["h_sp_var_r10"] - d["a_sp_var_r10"]
    
    # Close ERA (within 1.0 ERA) but variance gap
    close_era = era_diff < 1.0
    var_threshold = var_diff.abs().quantile(0.65)
    
    # Bet the LOW variance side (more reliable pitcher wins more often)
    return pd.Series(np.where(close_era & (var_diff > var_threshold), "away",  # home more volatile, bet away
                              np.where(close_era & (var_diff < -var_threshold), "home", "skip")),
                     index=d.index)

def c5_filter_strict(d):
    base = c5_filter(d)
    era_diff = (d["h_sp_era9_r10"] - d["a_sp_era9_r10"]).abs()
    var_diff = (d["h_sp_var_r10"] - d["a_sp_var_r10"]).abs()
    close_era = era_diff < 1.0
    return base & close_era & (var_diff >= var_diff[base].quantile(0.65))

# C6: Short-Leash SP x Weak BP
def c6_filter(d):
    return (d["h_sp_short_leash"].notna() & d["a_sp_short_leash"].notna() &
            d["h_bp_era9"].notna() & d["a_bp_era9"].notna())

def c6_bet(d):
    # Short leash + bad bullpen = trouble
    h_trouble = (d["h_sp_short_leash"] == 1) & (d["h_bp_era9"] > 4.0)
    a_trouble = (d["a_sp_short_leash"] == 1) & (d["a_bp_era9"] > 4.0)
    
    return pd.Series(np.where(h_trouble & ~a_trouble, "away",
                              np.where(a_trouble & ~h_trouble, "home", "skip")),
                     index=d.index)

def c6_filter_strict(d):
    base = c6_filter(d)
    h_trouble = (d["h_sp_short_leash"] == 1) & (d["h_bp_era9"] > 4.0)
    a_trouble = (d["a_sp_short_leash"] == 1) & (d["a_bp_era9"] > 4.0)
    return base & ((h_trouble & ~a_trouble) | (a_trouble & ~h_trouble))

# C7: Velocity Floor Breach — bet against SP with declining velo
def c7_filter(d):
    return d["h_velo_trend"].notna() & d["a_velo_trend"].notna()

def c7_bet(d):
    # Negative velo trend = declining, bet against
    threshold = -0.5  # 0.5 mph decline from baseline
    h_breach = d["h_velo_trend"] < threshold
    a_breach = d["a_velo_trend"] < threshold
    
    return pd.Series(np.where(h_breach & ~a_breach, "away",
                              np.where(a_breach & ~h_breach, "home", "skip")),
                     index=d.index)

def c7_filter_strict(d):
    base = c7_filter(d)
    h_breach = d["h_velo_trend"] < -0.5
    a_breach = d["a_velo_trend"] < -0.5
    return base & ((h_breach & ~a_breach) | (a_breach & ~h_breach))

# C8: Command x Stuff Archetype Mismatch
def c8_filter(d):
    return (d["h_whiff_r10"].notna() & d["a_whiff_r10"].notna() &
            d["h_zone_r10"].notna() & d["a_zone_r10"].notna())

def c8_bet(d):
    # "Stuff" proxy: whiff_rate. "Command" proxy: zone_rate
    # High whiff + low zone = "stuff" pitcher (volatile, strikeout or walk)
    # Low whiff + high zone = "command" pitcher (reliable, paint corners)
    # In close games, bet command pitcher (more reliable outcomes)
    h_stuff = d["h_whiff_r10"] > d["h_whiff_r10"].median()
    h_command = d["h_zone_r10"] > d["h_zone_r10"].median()
    a_stuff = d["a_whiff_r10"] > d["a_whiff_r10"].median()
    a_command = d["a_zone_r10"] > d["a_zone_r10"].median()
    
    # Command pitcher (high zone, lower whiff) vs stuff pitcher (high whiff, lower zone)
    h_is_command = h_command & ~h_stuff
    a_is_command = a_command & ~a_stuff
    h_is_stuff = h_stuff & ~h_command
    a_is_stuff = a_stuff & ~a_command
    
    # Bet the command side
    return pd.Series(np.where(h_is_command & a_is_stuff, "home",
                              np.where(a_is_command & h_is_stuff, "away", "skip")),
                     index=d.index)

def c8_filter_strict(d):
    base = c8_filter(d)
    h_stuff = d["h_whiff_r10"] > d["h_whiff_r10"].median()
    h_command = d["h_zone_r10"] > d["h_zone_r10"].median()
    a_stuff = d["a_whiff_r10"] > d["a_whiff_r10"].median()
    a_command = d["a_zone_r10"] > d["a_zone_r10"].median()
    h_is_command = h_command & ~h_stuff
    a_is_command = a_command & ~a_stuff
    h_is_stuff = h_stuff & ~h_command
    a_is_stuff = a_stuff & ~a_command
    return base & ((h_is_command & a_is_stuff) | (a_is_command & h_is_stuff))

# C9: Low-Total Variance Compression — back the dog in low-total close games
def c9_filter(d):
    return d["total_line"].notna() & (d["total_line"] <= 7.5)

def c9_bet(d):
    # In low-total games, the dog has better value (compression)
    return pd.Series(np.where(d["p_home"] < 0.5, "home", "away"), index=d.index)

# C10: Home Dog + BP Edge
def c10_filter(d):
    return (d["home_is_dog"] == 1) & d["h_bp_era9"].notna() & d["a_bp_era9"].notna()

def c10_bet(d):
    # Home dog with better bullpen
    bp_edge = d["h_bp_era9"] < d["a_bp_era9"]
    return pd.Series(np.where(bp_edge, "home", "skip"), index=d.index)

def c10_filter_strict(d):
    base = c10_filter(d)
    bp_edge = d["h_bp_era9"] < d["a_bp_era9"]
    return base & bp_edge

# ── Run all candidates ──
candidates = [
    ("C1", "BP Availability Proxy (workload)", c1_filter_strict, 
     lambda d: pd.Series(np.where(d["h_bp_workload"] > d["a_bp_workload"], "away", "home"), index=d.index)),
    ("C3", "Post-Extras Depletion", c3_filter_strict, c3_bet),
    ("C4", "SPID (SP good, BP bad = bet SP side)", c4_filter_strict, c4_bet),
    ("C5", "Low-Variance SP Advantage", c5_filter_strict, c5_bet),
    ("C6", "Short-Leash SP x Weak BP", c6_filter_strict, c6_bet),
    ("C7", "Velocity Floor Breach", c7_filter_strict, c7_bet),
    ("C8", "Command vs Stuff Archetype", c8_filter_strict, c8_bet),
    ("C9", "Low-Total Dog Compression", c9_filter, c9_bet),
    ("C10", "Home Dog + BP Edge", c10_filter_strict, c10_bet),
]

print("\n" + "=" * 70)
print("PHASE 5: DISCOVERY-ONLY TESTS (2022-2023)")
print("=" * 70)

all_results = []
for cid, desc, filt_fn, bet_fn in candidates:
    try:
        res = test_candidate(close_dt, cid, desc, filt_fn, bet_fn)
        all_results.append(res)
        disc = res["results"]["discovery"]
        print(f"\n{cid}: {desc}")
        print(f"  Discovery N={disc['N']}, WR={disc.get('WR','')}, ImpWR={disc.get('ImpWR','')}, "
              f"Resid={disc.get('Resid','')}, ROI={disc.get('ROI','')}%")
        if "by_season" in disc:
            for s, sv in disc["by_season"].items():
                print(f"    {s}: N={sv['N']}, WR={sv.get('WR','')}, Resid={sv.get('Resid','')}, ROI={sv.get('ROI','')}%")
    except Exception as e:
        print(f"\n{cid}: ERROR — {e}")
        import traceback; traceback.print_exc()
        all_results.append({"name": cid, "description": desc, 
                           "results": {"discovery": {"N": 0, "msg": str(e)}}})

# ── PHASE 6: Freeze survivors ──
print("\n" + "=" * 70)
print("PHASE 6: FREEZE SURVIVORS")
print("=" * 70)

survivors = []
for r in all_results:
    disc = r["results"].get("discovery", {})
    n = disc.get("N", 0)
    resid = disc.get("Resid", 0)
    roi = disc.get("ROI", 0)
    if n >= 150 and resid > 0:
        survivors.append(r["name"])
        print(f"  PASS: {r['name']} — N={n}, Resid={resid:+.4f}, ROI={roi:+.2f}%")
    elif n >= 150:
        print(f"  FAIL: {r['name']} — N={n}, Resid={resid:+.4f} (negative residual)")
    elif n > 0:
        print(f"  SMALL: {r['name']} — N={n} (below 150 threshold), Resid={resid:+.4f}")
    else:
        print(f"  EMPTY: {r['name']} — no qualifying games")

# Also check with N>=50 for interesting small-sample signals
print("\n  --- Relaxed (N>=50) for monitoring ---")
for r in all_results:
    disc = r["results"].get("discovery", {})
    n = disc.get("N", 0)
    resid = disc.get("Resid", 0)
    if 50 <= n < 150 and resid > 0:
        print(f"  MONITOR: {r['name']} — N={n}, Resid={resid:+.4f}")

# ── PHASE 7: Validation pass (2024) ──
print("\n" + "=" * 70)
print("PHASE 7: VALIDATION PASS (2024)")
print("=" * 70)

val_survivors = []
for r in all_results:
    if r["name"] not in survivors:
        continue
    val = r["results"].get("validation", {})
    n = val.get("N", 0)
    resid = val.get("Resid", 0)
    roi = val.get("ROI", 0)
    print(f"\n  {r['name']}: {r['description']}")
    print(f"    Val N={n}, WR={val.get('WR','')}, ImpWR={val.get('ImpWR','')}, "
          f"Resid={resid:+.4f}, ROI={roi:+.2f}%")
    if "by_season" in val:
        for s, sv in val["by_season"].items():
            print(f"      {s}: N={sv['N']}, Resid={sv.get('Resid',''):+.4f}, ROI={sv.get('ROI',''):+.2f}%")
    if resid > 0:
        val_survivors.append(r["name"])
        print(f"    → VALIDATION PASS")
    else:
        print(f"    → VALIDATION FAIL (negative residual)")

# ── PHASE 8: OOS pass (2025) ──
print("\n" + "=" * 70)
print("PHASE 8: OOS PASS (2025)")
print("=" * 70)

oos_survivors = []
for r in all_results:
    if r["name"] not in val_survivors:
        continue
    oos = r["results"].get("oos", {})
    n = oos.get("N", 0)
    resid = oos.get("Resid", 0)
    roi = oos.get("ROI", 0)
    print(f"\n  {r['name']}: {r['description']}")
    print(f"    OOS N={n}, WR={oos.get('WR','')}, ImpWR={oos.get('ImpWR','')}, "
          f"Resid={resid:+.4f}, ROI={roi:+.2f}%")
    if "by_season" in oos:
        for s, sv in oos["by_season"].items():
            print(f"      {s}: N={sv['N']}, Resid={sv.get('Resid',''):+.4f}, ROI={sv.get('ROI',''):+.2f}%")
    if resid > 0:
        oos_survivors.append(r["name"])
        print(f"    → OOS PASS")
    else:
        print(f"    → OOS FAIL")

# ── PHASE 9: Regime diagnostic ──
print("\n" + "=" * 70)
print("PHASE 9: REGIME DIAGNOSTIC")
print("=" * 70)

for r in all_results:
    if r["name"] in val_survivors:  # Show all validation survivors
        print(f"\n  {r['name']}: {r['description']}")
        for phase in ["discovery","validation","oos"]:
            pr = r["results"].get(phase, {})
            if "by_season" in pr:
                seasons = pr["by_season"]
                resids = [sv.get("Resid",0) for sv in seasons.values() if sv.get("N",0) > 0]
                if len(resids) >= 2:
                    consistency = "CONSISTENT" if all(r > 0 for r in resids) else "MIXED"
                else:
                    consistency = "SINGLE"
                print(f"    {phase}: {consistency} — residuals: {[f'{r:+.4f}' for r in resids]}")
            else:
                print(f"    {phase}: N={pr.get('N',0)}")

# ── PHASE 10: Keep/Kill Board ──
print("\n" + "=" * 70)
print("PHASE 10: KEEP/KILL BOARD")
print("=" * 70)

board_rows = []
for r in all_results:
    disc = r["results"].get("discovery", {})
    val = r["results"].get("validation", {})
    oos = r["results"].get("oos", {})
    
    d_n = disc.get("N",0)
    d_resid = disc.get("Resid",0)
    d_roi = disc.get("ROI",0)
    v_n = val.get("N",0)
    v_resid = val.get("Resid",0)
    v_roi = val.get("ROI",0)
    o_n = oos.get("N",0)
    o_resid = oos.get("Resid",0)
    o_roi = oos.get("ROI",0)
    
    if r["name"] in oos_survivors:
        verdict = "KEEP"
    elif r["name"] in val_survivors:
        verdict = "MONITOR (val pass, OOS fail)"
    elif r["name"] in survivors:
        verdict = "KILL (disc pass, val fail)"
    elif d_n >= 50 and d_resid > 0:
        verdict = "WATCH (small sample discovery)"
    else:
        verdict = "KILL"
    
    board_rows.append({
        "Candidate": r["name"],
        "Description": r["description"],
        "D_N": d_n, "D_Resid": d_resid, "D_ROI": d_roi,
        "V_N": v_n, "V_Resid": v_resid, "V_ROI": v_roi,
        "O_N": o_n, "O_Resid": o_resid, "O_ROI": o_roi,
        "Verdict": verdict
    })
    
    emoji = {"KEEP":"✓","MONITOR":"~","KILL":"✗","WATCH":"?"}
    tag = verdict.split(" ")[0]
    sym = emoji.get(tag, "?")
    print(f"  [{sym}] {r['name']}: {verdict}")
    print(f"       Disc: N={d_n}, Resid={d_resid:+.4f}, ROI={d_roi:+.2f}%")
    if v_n > 0:
        print(f"       Val:  N={v_n}, Resid={v_resid:+.4f}, ROI={v_roi:+.2f}%")
    if o_n > 0:
        print(f"       OOS:  N={o_n}, Resid={o_resid:+.4f}, ROI={o_roi:+.2f}%")

board_df = pd.DataFrame(board_rows)
board_df.to_csv(f"{OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_FINAL_TABLE.csv", index=False)
print(f"\nFinal table saved to {OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_FINAL_TABLE.csv")

# ── PHASE 11: Executive Summary ──
print("\n" + "=" * 70)
print("PHASE 11: EXECUTIVE SUMMARY")
print("=" * 70)

keeps = [r for r in board_rows if r["Verdict"] == "KEEP"]
monitors = [r for r in board_rows if "MONITOR" in r["Verdict"]]
watches = [r for r in board_rows if "WATCH" in r["Verdict"]]
kills = [r for r in board_rows if "KILL" in r["Verdict"]]

print(f"\n  KEEP: {len(keeps)}")
for k in keeps:
    print(f"    {k['Candidate']}: {k['Description']}")
    print(f"      D={k['D_N']}g/{k['D_Resid']:+.4f}/{k['D_ROI']:+.2f}%  "
          f"V={k['V_N']}g/{k['V_Resid']:+.4f}/{k['V_ROI']:+.2f}%  "
          f"O={k['O_N']}g/{k['O_Resid']:+.4f}/{k['O_ROI']:+.2f}%")

print(f"\n  MONITOR: {len(monitors)}")
for m in monitors:
    print(f"    {m['Candidate']}: {m['Description']}")

print(f"\n  WATCH: {len(watches)}")
for w in watches:
    print(f"    {w['Candidate']}: {w['Description']}")

print(f"\n  KILL: {len(kills)}")
for k in kills:
    print(f"    {k['Candidate']}: {k['Description']} — D_Resid={k['D_Resid']:+.4f}")

# Write executive summary markdown
exec_md = f"""# MLB Moneyline Phase 3 Discovery — Executive Summary

## Date: 2026-04-11

## Universe
Close moneyline games (fav -105 to -125 implied), 2022-2025.

## 10 Candidates Evaluated
| ID | Name | Safety |
|----|------|--------|
| C1 | BP Availability Proxy (workload) | FEASIBLE |
| C2 | Pinned Closer No Bridge | BLOCKED (no role labels) |
| C3 | Post-Extras Depletion | FEASIBLE |
| C4 | SPID (SP good, BP bad) | FEASIBLE |
| C5 | Low-Variance SP Advantage | FEASIBLE |
| C6 | Short-Leash SP x Weak BP | FEASIBLE |
| C7 | Velocity Floor Breach | FEASIBLE |
| C8 | Command vs Stuff Archetype | FEASIBLE |
| C9 | Low-Total Dog Compression | FEASIBLE |
| C10 | Home Dog + BP Edge | FEASIBLE |

## Results Board
"""

for row in board_rows:
    exec_md += f"\n### {row['Candidate']}: {row['Description']}\n"
    exec_md += f"- **Verdict: {row['Verdict']}**\n"
    exec_md += f"- Discovery (2022-23): N={row['D_N']}, Resid={row['D_Resid']:+.4f}, ROI={row['D_ROI']:+.2f}%\n"
    if row['V_N'] > 0:
        exec_md += f"- Validation (2024): N={row['V_N']}, Resid={row['V_Resid']:+.4f}, ROI={row['V_ROI']:+.2f}%\n"
    if row['O_N'] > 0:
        exec_md += f"- OOS (2025): N={row['O_N']}, Resid={row['O_Resid']:+.4f}, ROI={row['O_ROI']:+.2f}%\n"

    # Add by-season detail from all_results
    for r in all_results:
        if r["name"] == row["Candidate"]:
            for phase_name, phase_key in [("Discovery","discovery"),("Validation","validation"),("OOS","oos")]:
                pr = r["results"].get(phase_key, {})
                if "by_season" in pr:
                    for s, sv in pr["by_season"].items():
                        if sv.get("N",0) > 0:
                            exec_md += f"  - {s}: N={sv['N']}, WR={sv.get('WR','')}, Resid={sv.get('Resid',''):+.4f}, ROI={sv.get('ROI',''):+.2f}%\n"

exec_md += f"""
## Summary Counts
- **KEEP (3-phase survivor):** {len(keeps)}
- **MONITOR (val pass, OOS fail):** {len(monitors)}
- **WATCH (small sample):** {len(watches)}
- **KILL:** {len(kills)}

## Key Takeaways
"""

if keeps:
    exec_md += "### Survivors\n"
    for k in keeps:
        exec_md += f"- **{k['Candidate']}** ({k['Description']}): Positive residual across all three phases. "
        exec_md += f"Discovery ROI {k['D_ROI']:+.2f}%, Validation ROI {k['V_ROI']:+.2f}%, OOS ROI {k['O_ROI']:+.2f}%.\n"
else:
    exec_md += "No candidates survived all three phases with N>=150 and positive residual.\n"

if monitors:
    exec_md += "\n### Monitor List\n"
    for m in monitors:
        exec_md += f"- **{m['Candidate']}** ({m['Description']}): Passed validation but failed OOS. "
        exec_md += f"Could be regime-dependent or sample-size issue.\n"

exec_md += """
## Methodology Notes
- All features PIT-safe (shift(1) or date < game_date)
- No lineup features used
- No FanGraphs/V1 contaminated tables
- Economic ROI computed at actual closing ML prices
- Minimum N=150 for promotion; smaller samples noted as WATCH
"""

with open(f"{OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_EXEC_SUMMARY.md", "w") as f:
    f.write(exec_md)

print(f"\nExecutive summary saved to {OUT}/MLB_MONEYLINE_PHASE3_DISCOVERY_EXEC_SUMMARY.md")
print("\n" + "=" * 70)
print("PHASE 3 DISCOVERY ENGINE COMPLETE")
print("=" * 70)

