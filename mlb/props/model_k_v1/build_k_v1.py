#!/usr/bin/env python3
"""MLB Props — Pitcher Strikeouts K v1: Innings-bounded + Statcast."""

import warnings; warnings.filterwarnings("ignore")
import sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats as sp_stats

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA = ROOT/"mlb"/"data"; PROC = ROOT/"mlb"/"props"/"processed"
OUT = Path(__file__).resolve().parent
SC_FILE = ROOT/"mlb"/"props"/"data"/"statcast_pitchers.parquet"

N_SIMS=5000; RNG=np.random.default_rng(42); CLIP=0.72

def _imp(o):
    if pd.isna(o) or o==0: return np.nan
    return 100/(o+100) if o>0 else abs(o)/(abs(o)+100)
def devig(ov,un):
    ro,ru=_imp(ov),_imp(un)
    if pd.isna(ro) or pd.isna(ru): return np.nan,np.nan
    t=ro+ru; return (ro/t,ru/t) if t>0 else (np.nan,np.nan)
def realized_roi(w,odds):
    n=len(odds); return sum((o/100 if o>0 else 100/abs(o)) if ww==1 else -1 for ww,o in zip(w,odds))/n*100 if n else np.nan
def brier(p,o):
    m=pd.notna(p)&pd.notna(o); return float(((np.array(p[m])-np.array(o[m]))**2).mean()) if m.sum()>0 else np.nan

out=[]; log=lambda s="": (out.append(s), print(s, flush=True))
log("="*65); log("MLB PROPS — PITCHER STRIKEOUTS K v1"); log("="*65); log()

# ── LOAD DATA ──
plogs = pd.read_parquet(DATA/"pitcher_game_logs.parquet")
tgi = pd.read_parquet(DATA/"team_game_index.parquet")
mv = pd.read_parquet(PROC/"props_market_view.parquet")
hlogs = pd.read_parquet(DATA/"hitter_game_logs.parquet")

sp = plogs[plogs["starter_flag"]==1].copy().sort_values(["player_id","game_date"])
sp["game_date"] = pd.to_datetime(sp["game_date"])

# ── STEP 0: STATCAST AGGREGATION ──
log("STEP 0 — Statcast aggregation...")
sc = pd.read_parquet(SC_FILE)
sc["game_date"] = pd.to_datetime(sc["game_date"])

# Aggregate per pitcher-game
sc["is_swing"] = sc["description"].isin(["swinging_strike","swinging_strike_blocked","foul","foul_tip",
    "foul_bunt","missed_bunt","hit_into_play","bunt_foul_tip"])
sc["is_whiff"] = sc["description"].isin(["swinging_strike","swinging_strike_blocked"])
sc["is_csw"] = sc["description"].isin(["called_strike","swinging_strike","swinging_strike_blocked"])
sc["in_zone"] = sc["zone"].between(1,9)
sc["out_zone"] = ~sc["in_zone"] & sc["zone"].notna()
sc["chase"] = sc["out_zone"] & sc["is_swing"]

sc_agg = sc.groupby(["pitcher","game_date"]).agg(
    total_pitches=("description","count"),
    swings=("is_swing","sum"),
    whiffs=("is_whiff","sum"),
    csw=("is_csw","sum"),
    chases=("chase","sum"),
    out_zone_pitches=("out_zone","sum"),
    in_zone_pitches=("in_zone","sum"),
    avg_velo=("release_speed","mean"),
).reset_index()

sc_agg["whiff_rate"] = np.where(sc_agg["swings"]>0, sc_agg["whiffs"]/sc_agg["swings"], 0)
sc_agg["csw_rate"] = np.where(sc_agg["total_pitches"]>0, sc_agg["csw"]/sc_agg["total_pitches"], 0)
sc_agg["chase_rate"] = np.where(sc_agg["out_zone_pitches"]>0, sc_agg["chases"]/sc_agg["out_zone_pitches"], 0)
sc_agg["zone_rate"] = np.where(sc_agg["total_pitches"]>0, sc_agg["in_zone_pitches"]/sc_agg["total_pitches"], 0)

# Match to our pitcher logs
sc_agg = sc_agg.rename(columns={"pitcher":"mlbam_id"})
# sp has player_id which is mlbam_id
sp_sc = sp.merge(sc_agg, left_on=["player_id","game_date"], right_on=["mlbam_id","game_date"], how="left")

sc_coverage = sp_sc["csw_rate"].notna().mean()*100
log(f"  Statcast coverage: {sc_coverage:.1f}%")
log(f"  Pitchers with Statcast: {sp_sc[sp_sc['csw_rate'].notna()]['player_id'].nunique()}")
log()

# ── ROLLING FEATURES ──
log("Building rolling features...")

def sp_rolling(g):
    g = g.copy()
    # IP
    for w, nm in [(3,"L3"),(5,"L5"),(10,"L10")]:
        g[f"ip_{nm}"] = g["innings_pitched"].rolling(w, min_periods=max(2,w//2)).mean().shift(1)
    g["ip_szn"] = g["innings_pitched"].expanding(min_periods=2).mean().shift(1)
    g["ip_std"] = g["innings_pitched"].rolling(10, min_periods=4).std().shift(1)

    # BF/IP
    g["bf_ip"] = np.where(g["innings_pitched"]>0, g["batters_faced"]/g["innings_pitched"], 4.2)
    g["bf_ip_L5"] = g["bf_ip"].rolling(5, min_periods=3).mean().shift(1)
    g["bf_ip_L10"] = g["bf_ip"].rolling(10, min_periods=5).mean().shift(1)
    g["bf_ip_szn"] = g["bf_ip"].expanding(min_periods=3).mean().shift(1)

    # K/TBF
    g["k_tbf"] = np.where(g["batters_faced"]>0, g["strikeouts"]/g["batters_faced"], 0)
    for w, nm in [(3,"L3"),(5,"L5"),(10,"L10")]:
        g[f"k_tbf_{nm}"] = g["k_tbf"].rolling(w, min_periods=max(2,w//2)).mean().shift(1)
    g["k_tbf_szn"] = g["k_tbf"].expanding(min_periods=2).mean().shift(1)

    # Statcast rolling
    for stat in ["csw_rate","whiff_rate","avg_velo"]:
        g[f"{stat}_L5"] = g[stat].rolling(5, min_periods=3).mean().shift(1)
        g[f"{stat}_L10"] = g[stat].rolling(10, min_periods=5).mean().shift(1)

    # Days rest
    g["days_rest"] = g["game_date"].diff().dt.days
    g["start_num"] = range(1, len(g)+1)
    return g

sp_sc = sp_sc.groupby(["player_id","season"], group_keys=False).apply(sp_rolling)

# League averages for modifiers
league_csw = sp_sc["csw_rate"].mean()
league_whiff = sp_sc["whiff_rate"].mean()
league_k_tbf = sp_sc["k_tbf"].mean()

log(f"  League avg CSW: {league_csw:.3f}, Whiff: {league_whiff:.3f}, K/TBF: {league_k_tbf:.3f}")

# ── OPPONENT K% ──
log("Computing opponent K%...")
hlogs_st = hlogs[hlogs["starter_flag"]==1].copy()
hlogs_st["game_date"] = pd.to_datetime(hlogs_st["game_date"])
hlogs_st["k_pct"] = np.where(hlogs_st["plate_appearances"]>0, hlogs_st["strikeouts"]/hlogs_st["plate_appearances"], 0)

team_k = hlogs_st.groupby(["team","season"]).apply(
    lambda g: pd.Series({"team_k_pct": g["strikeouts"].sum()/g["plate_appearances"].sum()})
).reset_index()

league_k_pct = hlogs_st["strikeouts"].sum()/hlogs_st["plate_appearances"].sum()
team_k["opp_k_mod"] = (team_k["team_k_pct"]/league_k_pct).clip(0.82, 1.18)

log(f"  League K%: {league_k_pct:.3f}")
log(f"  Opp K modifier range: {team_k['opp_k_mod'].min():.3f} - {team_k['opp_k_mod'].max():.3f}")
log()

# ── JOIN TO MARKET ──
log("Joining to K market view...")
k_mv = mv[mv["prop_type"]=="K"].copy()
has_odds = k_mv["consensus_over_odds"].notna() & k_mv["consensus_under_odds"].notna()
log(f"  K props with odds: {has_odds.sum():,}/{len(k_mv):,} ({has_odds.mean()*100:.1f}%)")
k_mv = k_mv[has_odds].copy()
k_mv["player_id"] = k_mv["player_id"].astype(float)

# Join pitcher features
feat_cols = ["game_pk","player_id","game_date","season","team","opponent",
    "innings_pitched","batters_faced","strikeouts",
    "ip_L3","ip_L5","ip_L10","ip_szn","ip_std",
    "bf_ip_L5","bf_ip_L10","bf_ip_szn",
    "k_tbf_L3","k_tbf_L5","k_tbf_L10","k_tbf_szn",
    "csw_rate_L5","whiff_rate_L5","avg_velo_L5","avg_velo_L10",
    "days_rest","start_num"]
feat_cols = [c for c in feat_cols if c in sp_sc.columns]
sp_feat = sp_sc[feat_cols].copy()
sp_feat["game_date_str"] = sp_feat["game_date"].dt.strftime("%Y-%m-%d")
sp_feat["player_id"] = sp_feat["player_id"].astype(float)

joined = k_mv.merge(sp_feat, left_on=["player_id","game_date"],
                      right_on=["player_id","game_date_str"], how="inner",
                      suffixes=("","_sp"))
# Clean
for c in list(joined.columns):
    if c.endswith("_sp") and c.replace("_sp","") in joined.columns:
        joined.drop(columns=[c], inplace=True)

# Add opponent K modifier
joined = joined.merge(team_k[["team","season","opp_k_mod"]].rename(columns={"team":"opponent_team"}),
                        left_on=["opponent","season"], right_on=["opponent_team","season"], how="left")
joined["opp_k_mod"] = joined["opp_k_mod"].fillna(1.0)

log(f"  Joined: {len(joined):,} rows")
log()

# ── COMPUTE PROJECTIONS + SIMULATE ──
log("Computing projections and simulating...")

all_plays = []
count = 0

for _, row in joined.iterrows():
    line = row["consensus_line"]

    # Component 1: Innings projection
    ip_l3 = row.get("ip_L3", np.nan)
    ip_l5 = row.get("ip_L5", np.nan)
    ip_l10 = row.get("ip_L10", np.nan)
    ip_szn = row.get("ip_szn", np.nan)

    if not pd.isna(ip_l3):
        proj_ip = 0.40*ip_l3 + 0.30*(ip_l5 if not pd.isna(ip_l5) else ip_l3) + \
                  0.20*(ip_l10 if not pd.isna(ip_l10) else ip_szn if not pd.isna(ip_szn) else 5.5) + \
                  0.10*(ip_szn if not pd.isna(ip_szn) else 5.5)
    elif not pd.isna(ip_szn):
        proj_ip = ip_szn
    else:
        continue  # skip if no IP data

    # Days rest modifier
    dr = row.get("days_rest", 5)
    if not pd.isna(dr):
        if dr == 3: proj_ip *= 0.93
        elif dr >= 6: proj_ip *= 1.02

    # Early season cap
    if row.get("start_num", 99) <= 5:
        proj_ip = min(proj_ip, 5.0)

    proj_ip = max(2.0, min(proj_ip, 8.0))
    ip_std = row.get("ip_std", np.nan)
    if pd.isna(ip_std) or ip_std < 0.5: ip_std = 1.0

    # Component 2: BF/IP
    _bf5 = row.get("bf_ip_L5", np.nan)
    _bf10 = row.get("bf_ip_L10", np.nan)
    _bfs = row.get("bf_ip_szn", np.nan)
    _bfd = 4.2  # league default
    bf_ip = 0.40*(float(_bf5) if not pd.isna(_bf5) else _bfd) + \
            0.35*(float(_bf10) if not pd.isna(_bf10) else _bfd) + \
            0.25*(float(_bfs) if not pd.isna(_bfs) else _bfd)

    if pd.isna(bf_ip): bf_ip = 4.2
    proj_tbf = proj_ip * bf_ip

    # Component 3: K rate
    k_l3 = row.get("k_tbf_L3", np.nan)
    k_l5 = row.get("k_tbf_L5", np.nan)
    k_l10 = row.get("k_tbf_L10", np.nan)
    k_szn = row.get("k_tbf_szn", np.nan)

    if not pd.isna(k_l3):
        k_rate = 0.35*k_l3 + 0.30*(k_l5 if not pd.isna(k_l5) else k_l3) + \
                 0.25*(k_l10 if not pd.isna(k_l10) else k_szn if not pd.isna(k_szn) else league_k_tbf) + \
                 0.10*(k_szn if not pd.isna(k_szn) else league_k_tbf)
    elif not pd.isna(k_szn):
        k_rate = k_szn
    else:
        k_rate = league_k_tbf

    # Statcast modifiers
    csw_mod = 1.0; whiff_mod = 1.0; velo_mod = 1.0
    has_sc = False

    csw_l5 = row.get("csw_rate_L5", np.nan)
    if not pd.isna(csw_l5) and league_csw > 0:
        csw_mod = max(0.90, min(1.10, 1 + 0.5*(csw_l5-league_csw)/league_csw))
        has_sc = True

    whiff_l5 = row.get("whiff_rate_L5", np.nan)
    if not pd.isna(whiff_l5) and league_whiff > 0:
        whiff_mod = max(0.92, min(1.08, 1 + 0.5*(whiff_l5-league_whiff)/league_whiff))
        has_sc = True

    velo_l5 = row.get("avg_velo_L5", np.nan)
    velo_l10 = row.get("avg_velo_L10", np.nan)
    if not pd.isna(velo_l5) and not pd.isna(velo_l10):
        if velo_l10 - velo_l5 > 1.5:
            velo_mod = 0.93; has_sc = True

    combined_sc = max(0.85, min(1.15, csw_mod * whiff_mod * velo_mod))
    if has_sc:
        k_rate *= combined_sc

    # Opponent modifier
    opp_mod = row.get("opp_k_mod", 1.0)
    k_rate *= opp_mod

    # Final projection
    proj_k = k_rate * proj_tbf
    k_ceiling = int(round(proj_tbf))

    # Component 7: Simulation (innings-distributed)
    ip_draws = RNG.normal(proj_ip, ip_std, N_SIMS).clip(0, 9)
    tbf_draws = (ip_draws * bf_ip).clip(1, 40).astype(int)

    k_sims = np.zeros(N_SIMS, dtype=int)
    for i in range(N_SIMS):
        lam = max(0.1, k_rate * tbf_draws[i])
        cap = tbf_draws[i]
        k_draw = min(RNG.poisson(lam), cap)
        k_sims[i] = k_draw

    p_over = float((k_sims > line).mean())
    p_under = float((k_sims <= line).mean())

    # Clip
    p_over = min(p_over, CLIP); p_under = min(p_under, CLIP)
    t = p_over + p_under; p_over /= t; p_under /= t

    # Analytical (for comparison on first batch)
    lam_a = max(0.5, proj_k)
    cap_a = max(1, k_ceiling)
    probs_a = np.array([sp_stats.poisson.pmf(k, lam_a) for k in range(cap_a+1)])
    probs_a = probs_a / probs_a.sum()
    thresh = int(np.floor(line))+1
    p_over_a = float(probs_a[thresh:].sum()) if thresh < len(probs_a) else 0
    p_under_a = float(probs_a[:thresh].sum()) if thresh >= 0 else 0

    # Devig
    imp_over, imp_under = devig(row["consensus_over_odds"], row["consensus_under_odds"])
    if pd.isna(imp_over): continue

    edge_over = p_over - imp_over; edge_under = p_under - imp_under
    lean = "OVER" if edge_over > edge_under and edge_over > 0 else \
           "UNDER" if edge_under > 0 else "NO_PLAY"
    edge = edge_over if lean == "OVER" else edge_under if lean == "UNDER" else 0
    bucket = "5%+" if abs(edge)>=0.05 else "2-5%" if abs(edge)>=0.02 else "0-2%"

    actual_k = row.get("actual_value", np.nan)
    win = np.nan
    if lean == "OVER" and not pd.isna(actual_k): win = 1.0 if actual_k > line else 0.0
    elif lean == "UNDER" and not pd.isna(actual_k): win = 1.0 if actual_k < line else 0.0

    act_odds = row.get("best_over_odds" if lean=="OVER" else "best_under_odds",
                        row.get("consensus_over_odds" if lean=="OVER" else "consensus_under_odds", -110))
    if pd.isna(act_odds): act_odds = -110

    # Segments (predefined)
    seg_A = not pd.isna(csw_l5) and csw_l5 >= 0.30
    seg_B = not pd.isna(velo_l5) and not pd.isna(velo_l10) and (velo_l10 - velo_l5) <= 0.5
    seg_D = opp_mod >= 1.05
    seg_E = seg_A and seg_B and seg_D

    all_plays.append({
        "player_name": row["player_name"], "player_id": row["player_id"],
        "team": row.get("team",""), "opponent": row.get("opponent",""),
        "game_date": row["game_date"], "season": row["season"],
        "dataset_split": row["dataset_split"],
        "proj_ip": round(proj_ip,2), "actual_ip": row.get("innings_pitched",np.nan),
        "proj_tbf": round(proj_tbf,1), "actual_tbf": row.get("batters_faced",np.nan),
        "proj_k": round(proj_k,2), "actual_k": actual_k,
        "k_rate": round(k_rate,4), "bf_ip": round(bf_ip,2),
        "statcast_available": has_sc,
        "csw_mod": round(csw_mod,3), "whiff_mod": round(whiff_mod,3), "velo_mod": round(velo_mod,3),
        "opp_k_mod": round(opp_mod,3),
        "line": line, "lean": lean, "edge": round(edge,4), "edge_bucket": bucket,
        "model_prob_over": round(p_over,4), "model_prob_under": round(p_under,4),
        "model_prob_over_analytical": round(p_over_a,4),
        "implied_prob_over": round(imp_over,4), "implied_prob_under": round(imp_under,4),
        "actual_odds": act_odds, "bet_win": win,
        "seg_A": seg_A, "seg_B": seg_B, "seg_D": seg_D, "seg_E": seg_E,
        "n_books": row.get("n_books",1),
    })

    count += 1
    if count % 2000 == 0: log(f"  {count:,}...")

plays = pd.DataFrame(all_plays)
plays.to_parquet(OUT/"backtest_results.parquet", index=False)
plays.to_csv(OUT/"backtest_results.csv", index=False)
log(f"\n  Total: {len(plays):,}, outcomes: {plays['bet_win'].notna().sum():,}")

# ═══════════════════════ REPORTING ═══════════════════════════

# Section 0: Coverage
log(f"\n{'='*65}\nSECTION 0 — DATA COVERAGE\n{'='*65}")
log(f"  Statcast coverage: {plays['statcast_available'].mean()*100:.1f}%")
log(f"  Umpire data: NOT AVAILABLE (skipped)")
log()

# Section 1: Innings accuracy
log(f"{'='*65}\nSECTION 1 — INNINGS PROJECTION ACCURACY\n{'='*65}")
has_actual = plays[plays["actual_ip"].notna()]
ip_mae = (has_actual["proj_ip"]-has_actual["actual_ip"]).abs().mean()
ip_corr = has_actual["proj_ip"].corr(has_actual["actual_ip"])
tbf_mae = (has_actual["proj_tbf"]-has_actual["actual_tbf"]).abs().mean()
k_mae = (has_actual["proj_k"]-has_actual["actual_k"]).abs().mean()
log(f"  IP: MAE={ip_mae:.2f}, corr={ip_corr:.3f}")
log(f"  TBF: MAE={tbf_mae:.2f}")
log(f"  K projection: MAE={k_mae:.2f}")
if ip_mae > 1.5: log(f"  ⚠ IP MAE > 1.5 — innings is primary bottleneck")
log()

# Section 2: Calibration
log(f"{'='*65}\nSECTION 2 — CALIBRATION\n{'='*65}")
vc = plays[(plays["dataset_split"]=="VALIDATION") & plays["actual_k"].notna()]
cal_pass = True
log(f"{'Bucket':<10s} {'N':>5s} {'Model':>6s} {'Actual':>7s} {'Delta':>6s}")
for lo,hi,lb in [(0,0.35,"<35%"),(0.35,0.45,"35-45"),(0.45,0.55,"45-55"),
                  (0.55,0.65,"55-65"),(0.65,0.75,"65-75")]:
    m = (vc["model_prob_over"]>=lo)&(vc["model_prob_over"]<hi)
    b = vc[m]
    if len(b)<20: continue
    mp=b["model_prob_over"].mean(); ar=(b["actual_k"]>b["line"]).mean(); d=ar-mp
    if abs(d)>0.15: cal_pass=False
    f=" ⚠" if abs(d)>0.10 else ""
    log(f"{lb:<10s} {len(b):>5d} {mp:>5.1%} {ar:>6.1%} {d:>+5.1%}{f}")

ao = (vc["actual_k"]>vc["line"]).astype(float)
b_sim = brier(vc["model_prob_over"], ao)
b_ana = brier(vc["model_prob_over_analytical"], ao)
log(f"\nBrier (sim): {b_sim:.4f}, Brier (analytical): {b_ana:.4f}")
log(f"→ {'Simulation' if b_sim<=b_ana else 'Analytical'} is better calibrated")
log(f"Calibration: {'PASS' if cal_pass else 'FAIL'}")
log()

# Sections 3+: Results
for sv in ["VALIDATION","OOS"]:
    data = plays[(plays["dataset_split"]==sv)&(plays["lean"]!="NO_PLAY")&plays["bet_win"].notna()]
    if len(data)==0: continue
    log(f"{'='*65}\n{sv}\n{'='*65}")
    w=data["bet_win"].sum(); n=len(data)
    roi=realized_roi(data["bet_win"].values, data["actual_odds"].values)
    log(f"  Overall: N={n:,}, hit={w/n*100:.1f}%, ROI={roi:+.1f}%")
    for d in ["OVER","UNDER"]:
        s=data[data["lean"]==d]
        if len(s)>0:
            sr=realized_roi(s["bet_win"].values,s["actual_odds"].values)
            log(f"  {d}: N={len(s):,}, hit={s['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

    log("  Edge buckets:")
    for bk in ["0-2%","2-5%","5%+"]:
        s=data[data["edge_bucket"]==bk]
        if len(s)>20:
            sr=realized_roi(s["bet_win"].values,s["actual_odds"].values)
            log(f"    {bk}: N={len(s):,}, hit={s['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

    # Statcast impact
    sc_yes = data[data["statcast_available"]]
    sc_no = data[~data["statcast_available"]]
    if len(sc_yes)>50 and len(sc_no)>50:
        log(f"\n  Statcast impact:")
        log(f"    With SC: N={len(sc_yes)}, hit={sc_yes['bet_win'].mean()*100:.1f}%, "
            f"ROI={realized_roi(sc_yes['bet_win'].values,sc_yes['actual_odds'].values):+.1f}%")
        log(f"    W/o SC:  N={len(sc_no)}, hit={sc_no['bet_win'].mean()*100:.1f}%, "
            f"ROI={realized_roi(sc_no['bet_win'].values,sc_no['actual_odds'].values):+.1f}%")

    # Segments
    log(f"\n  SEGMENTS:")
    for seg,col in [("A:High CSW","seg_A"),("B:Velo stable","seg_B"),
                     ("D:High K opp","seg_D"),("E:All aligned","seg_E")]:
        s=data[data[col]]
        if len(s)<20: continue
        sr=realized_roi(s["bet_win"].values,s["actual_odds"].values)
        be=s["actual_odds"].apply(_imp).mean()*100
        log(f"    {seg}: N={len(s):,}, hit={s['bet_win'].mean()*100:.1f}%, BE={be:.1f}%, ROI={sr:+.1f}%{' THIN' if len(s)<100 else ''}")
    log()

# Recommendation
log(f"{'='*65}\nRECOMMENDATION\n{'='*65}")
vd = plays[(plays["dataset_split"]=="VALIDATION")&(plays["lean"]!="NO_PLAY")&plays["bet_win"].notna()]
od = plays[(plays["dataset_split"]=="OOS")&(plays["lean"]!="NO_PLAY")&plays["bet_win"].notna()]

if len(vd)>0:
    v_roi = realized_roi(vd["bet_win"].values, vd["actual_odds"].values)
    o_roi = realized_roi(od["bet_win"].values, od["actual_odds"].values) if len(od)>0 else np.nan
    log(f"  Overall: val ROI={v_roi:+.1f}%, oos ROI={o_roi:+.1f}%")

    gates = {"calibration": cal_pass, "N>=200": len(vd)>=200, "val_roi>=2%": v_roi>=2.0,
             "oos>=0%": o_roi>=0 if not pd.isna(o_roi) else False}
    for g,p in gates.items(): log(f"  {g}: {'PASS' if p else 'FAIL'}")

    if all(gates.values()): log("\n  READY FOR SHADOW")
    elif sum(gates.values())>=3: log(f"\n  NEAR-MISS")
    else: log(f"\n  NOT READY")
log()

# Observations
log(f"{'='*65}\nOBSERVATIONS\n{'='*65}")
log(f"1. IP MAE: {ip_mae:.2f} — {'bottleneck' if ip_mae>1.5 else 'acceptable'}")
log(f"2. Statcast coverage: {plays['statcast_available'].mean()*100:.0f}%")
log(f"3. K projection MAE: {k_mae:.2f}")
log(f"4. Calibration: {'PASS' if cal_pass else 'FAIL'}")

with open(OUT/"k_v1_summary.txt","w") as f: f.write("\n".join(out))
log(f"\nFiles saved to mlb/props/model_k_v1/")
PYEOF