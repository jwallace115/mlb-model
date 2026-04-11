#!/usr/bin/env python3
"""NHL Signal Revalidation on Final Aligned Base"""
import pandas as pd
import numpy as np
import pickle, json, sys
from pathlib import Path

OUT = Path("research/recovery/nhl_signal_revalidation")
OUT.mkdir(parents=True, exist_ok=True)

# ── Load aligned base ──
ft = pd.read_parquet("research/recovery/nhl_final_alignment/nhl_live_compatible_feature_table_v2.parquet")
home_pkg = pickle.load(open("research/recovery/nhl_final_alignment/model_A_home.pkl", "rb"))
away_pkg = pickle.load(open("research/recovery/nhl_final_alignment/model_A_away.pkl", "rb"))
oos_raw = pd.read_csv("research/recovery/nhl_final_alignment/nhl_final_alignment_oos_results.csv")

# Market snapshots for closing prices
ms = pd.read_parquet("nhl/nhl_market_snapshots.parquet")

print(f"Feature table: {ft.shape}")
print(f"OOS results: {oos_raw.shape}")
print(f"Market snapshots: {ms.shape}")

# ── Score full feature table ──
# Need to predict for all games in ft that have market data
ft_scored = ft.dropna(subset=['closing_total']).copy()
ft_scored = ft_scored[ft_scored['market_available']==True].copy() if 'market_available' in ft_scored.columns else ft_scored[ft_scored['closing_total'].notna()].copy()

print(f"Scoreable games: {len(ft_scored)}")

# Get train column means
train_means = pd.Series(home_pkg['col_means'])

# Score
all_home_feats = home_pkg['features']
all_away_feats = away_pkg['features']
all_feats = list(set(all_home_feats + all_away_feats))

feat_df = ft_scored[all_feats].copy()
for col in all_feats:
    if col not in feat_df.columns:
        feat_df[col] = train_means.get(col, 0.0)
feat_df = feat_df.fillna(train_means)

lh = home_pkg['model'].predict(home_pkg['scaler'].transform(feat_df[all_home_feats].to_numpy()))
la = away_pkg['model'].predict(away_pkg['scaler'].transform(feat_df[all_away_feats].to_numpy()))

DRIFT = 0.4458
ft_scored['pred_home'] = lh + DRIFT/2
ft_scored['pred_away'] = la + DRIFT/2
ft_scored['pred_total'] = ft_scored['pred_home'] + ft_scored['pred_away']
ft_scored['actual_total'] = ft_scored['total_goals']
ft_scored['model_edge_raw'] = ft_scored['pred_total'] - ft_scored['closing_total']

# Season assignment
ft_scored['season'] = ft_scored['season_year'].astype(int)

print(f"Scored: {len(ft_scored)}")
print(f"Seasons: {ft_scored['season'].value_counts().sort_index().to_dict()}")

# ── Merge closing prices ──
ms_prices = ms[['game_id','closing_over_price','closing_under_price']].drop_duplicates(subset='game_id')
ft_scored = ft_scored.merge(ms_prices, on='game_id', how='left')
has_prices = ft_scored['closing_over_price'].notna()
print(f"Games with closing prices: {has_prices.sum()} / {len(ft_scored)}")

# ── Poisson simulation for edge computation ──
from scipy.stats import poisson

def sim_edges(pred_home, pred_away, line, over_price, under_price, n=10000, seed=42):
    rng = np.random.default_rng(seed)
    lh = max(0.5, min(8.0, pred_home))
    la = max(0.5, min(8.0, pred_away))
    sims = rng.poisson(lh, n) + rng.poisson(la, n)
    over_p = float((sims > line).mean())
    under_p = float((sims < line).mean())
    
    # Fair probs from market prices
    def american_to_implied(price):
        if pd.isna(price): return np.nan
        return abs(price)/(abs(price)+100) if price < 0 else 100/(100+price)
    
    imp_o = american_to_implied(over_price)
    imp_u = american_to_implied(under_price)
    if pd.isna(imp_o) or pd.isna(imp_u): return np.nan, np.nan, np.nan, np.nan
    vig = imp_o + imp_u
    fair_o = imp_o / vig
    fair_u = imp_u / vig
    
    edge_over = over_p - fair_o
    edge_under = under_p - fair_u
    return edge_over, edge_under, over_p, under_p

# Vectorized would be slow game-by-game but we need it
print("Computing sim edges for all games...")
edges = []
for i, row in ft_scored.iterrows():
    eo, eu, po, pu = sim_edges(
        row['pred_home'], row['pred_away'], row['closing_total'],
        row.get('closing_over_price', np.nan), row.get('closing_under_price', np.nan),
        n=10000, seed=42
    )
    edges.append({'idx': i, 'edge_over': eo, 'edge_under': eu, 'sim_over': po, 'sim_under': pu})

edge_df = pd.DataFrame(edges).set_index('idx')
ft_scored = ft_scored.join(edge_df)
print(f"Edges computed: {ft_scored['edge_over'].notna().sum()} games with valid edges")

# ── Define seasons ──
TRAIN_SEASONS = [2021, 2022, 2023]
OOS_SEASON = 2024  # 2024-25 season

# ── PHASE 4: Historical re-test ──
# Apply signal logic: edge >= threshold → signal fires
# Grade: OVER signal wins if actual > closing_total; UNDER wins if actual < closing_total

def grade_signals(df, edge_threshold, side_col='signal_side'):
    """Given a df with edge_over, edge_under, actual_total, closing_total, grade."""
    signals = []
    for _, row in df.iterrows():
        at = row['actual_total']
        ct = row['closing_total']
        # Check OVER
        if row['edge_over'] >= edge_threshold:
            result = 'WIN' if at > ct else ('LOSS' if at < ct else 'PUSH')
            signals.append({
                'game_id': row['game_id'], 'season': row['season'],
                'signal_side': 'OVER', 'edge': row['edge_over'],
                'closing_total': ct, 'actual_total': at,
                'pred_total': row['pred_total'],
                'over_price': row.get('closing_over_price', np.nan),
                'result': result,
            })
        # Check UNDER
        if row['edge_under'] >= edge_threshold:
            result = 'WIN' if at < ct else ('LOSS' if at > ct else 'PUSH')
            signals.append({
                'game_id': row['game_id'], 'season': row['season'],
                'signal_side': 'UNDER', 'edge': row['edge_under'],
                'closing_total': ct, 'actual_total': at,
                'pred_total': row['pred_total'],
                'under_price': row.get('closing_under_price', np.nan),
                'result': result,
            })
    return pd.DataFrame(signals) if signals else pd.DataFrame()

def compute_roi(sigs, price_col):
    """Compute flat-bet ROI at actual closing prices."""
    if len(sigs) == 0: return np.nan, 0, 0, 0, np.nan
    wins = (sigs['result']=='WIN').sum()
    losses = (sigs['result']=='LOSS').sum()
    pushes = (sigs['result']=='PUSH').sum()
    
    # Use actual prices
    profit = 0.0
    n_priced = 0
    for _, r in sigs.iterrows():
        if r['result']=='PUSH': continue
        price = r.get(price_col, np.nan)
        if pd.isna(price):
            # Default -110
            price = -110
        if r['result']=='WIN':
            if price > 0: profit += price/100
            else: profit += 100/abs(price)
        else:
            profit -= 1.0
        n_priced += 1
    
    roi = profit/n_priced if n_priced > 0 else np.nan
    wr = wins/(wins+losses) if (wins+losses)>0 else np.nan
    return roi, wins, losses, pushes, wr

# ── Run for multiple thresholds ──
valid = ft_scored[ft_scored['edge_over'].notna()].copy()
train = valid[valid['season'].isin(TRAIN_SEASONS)]
oos = valid[valid['season']==OOS_SEASON]

print(f"\nTrain games: {len(train)}, OOS games: {len(oos)}")
print(f"Train seasons: {train['season'].value_counts().sort_index().to_dict()}")
print(f"OOS season: {oos['season'].value_counts().to_dict()}")

thresholds = [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25]
results_table = []

for thr in thresholds:
    for label, subset in [('TRAIN', train), ('OOS', oos)]:
        sigs = grade_signals(subset, thr)
        if len(sigs)==0:
            results_table.append({'threshold': thr, 'split': label, 'n_signals': 0})
            continue
        
        # All signals
        over_sigs = sigs[sigs['signal_side']=='OVER']
        under_sigs = sigs[sigs['signal_side']=='UNDER']
        
        roi_all, w, l, p, wr = compute_roi(sigs, 'over_price')  # mixed, approx
        roi_over, wo, lo, po, wr_o = compute_roi(over_sigs, 'over_price')
        roi_under, wu, lu, pu, wr_u = compute_roi(under_sigs, 'under_price')
        
        results_table.append({
            'threshold': thr, 'split': label,
            'n_signals': len(sigs), 'wins': w, 'losses': l, 'pushes': p,
            'win_rate': wr, 'roi': roi_all,
            'n_over': len(over_sigs), 'wr_over': wr_o, 'roi_over': roi_over,
            'n_under': len(under_sigs), 'wr_under': wr_u, 'roi_under': roi_under,
        })

results_df = pd.DataFrame(results_table)
print("\n" + "="*80)
print("PHASE 4: Signal Threshold Analysis")
print("="*80)
for split in ['TRAIN', 'OOS']:
    print(f"\n--- {split} ---")
    sub = results_df[results_df['split']==split]
    for _, r in sub.iterrows():
        print(f"  thr={r['threshold']:.2f}  n={int(r.get('n_signals',0)):4d}  "
              f"WR={r.get('win_rate',0):.3f}  ROI={r.get('roi',0):+.3f}  "
              f"OVER: n={int(r.get('n_over',0))} WR={r.get('wr_over',0):.3f}  "
              f"UNDER: n={int(r.get('n_under',0))} WR={r.get('wr_under',0):.3f}")

# ── PHASE 5: Regime/stability by season, month, direction, edge bucket ──
print("\n" + "="*80)
print("PHASE 5: Regime/Stability Check")
print("="*80)

# Use threshold=0.12 (current production)
all_sigs = grade_signals(valid, 0.12)
all_sigs['game_date'] = all_sigs['game_id'].map(dict(zip(ft_scored['game_id'], ft_scored['game_date'])))
all_sigs['month'] = pd.to_datetime(all_sigs['game_date']).dt.month

# By season
print("\nBy Season (thr=0.12):")
for s in sorted(all_sigs['season'].unique()):
    sub = all_sigs[all_sigs['season']==s]
    w = (sub['result']=='WIN').sum()
    l = (sub['result']=='LOSS').sum()
    wr = w/(w+l) if w+l>0 else 0
    print(f"  {s}: {len(sub)} signals, {w}W-{l}L, WR={wr:.3f}")

# By direction
print("\nBy Direction (thr=0.12):")
for side in ['OVER','UNDER']:
    sub = all_sigs[all_sigs['signal_side']==side]
    w = (sub['result']=='WIN').sum()
    l = (sub['result']=='LOSS').sum()
    wr = w/(w+l) if w+l>0 else 0
    print(f"  {side}: {len(sub)} signals, {w}W-{l}L, WR={wr:.3f}")

# By edge bucket
print("\nBy Edge Bucket (thr=0.12):")
all_sigs['edge_bucket'] = pd.cut(all_sigs['edge'], bins=[0.12, 0.15, 0.20, 0.25, 1.0], 
                                  labels=['0.12-0.15','0.15-0.20','0.20-0.25','0.25+'])
for eb in ['0.12-0.15','0.15-0.20','0.20-0.25','0.25+']:
    sub = all_sigs[all_sigs['edge_bucket']==eb]
    w = (sub['result']=='WIN').sum()
    l = (sub['result']=='LOSS').sum()
    wr = w/(w+l) if w+l>0 else 0
    print(f"  {eb}: {len(sub)} signals, {w}W-{l}L, WR={wr:.3f}")

# By month (OOS only)
print("\nBy Month (OOS, thr=0.12):")
oos_sigs = all_sigs[all_sigs['season']==OOS_SEASON]
for m in sorted(oos_sigs['month'].unique()):
    sub = oos_sigs[oos_sigs['month']==m]
    w = (sub['result']=='WIN').sum()
    l = (sub['result']=='LOSS').sum()
    wr = w/(w+l) if w+l>0 else 0
    print(f"  Month {m:2d}: {len(sub)} signals, {w}W-{l}L, WR={wr:.3f}")

# ── Confidence tier simulation on aligned base ──
print("\n" + "="*80)
print("PHASE 5b: Confidence Tier Analysis on Aligned Base")
print("="*80)

def assign_tier(edge, backup_h=0, backup_a=0):
    vol = 'high' if (backup_h + backup_a) >= 2 else 'normal'
    if edge >= 0.15 and vol != 'high': return 'HIGH'
    if edge >= 0.12: return 'MEDIUM'
    return 'LOW'

all_sigs['tier'] = all_sigs['edge'].apply(assign_tier)

for split_label, split_sigs in [('ALL', all_sigs), ('OOS', oos_sigs)]:
    print(f"\n--- {split_label} (thr=0.12) ---")
    for tier in ['HIGH','MEDIUM','LOW']:
        sub = split_sigs[split_sigs['tier']==tier]
        if len(sub)==0: continue
        w = (sub['result']=='WIN').sum()
        l = (sub['result']=='LOSS').sum()
        wr = w/(w+l) if w+l>0 else 0
        print(f"  {tier}: {len(sub)} signals, {w}W-{l}L, WR={wr:.3f}")

# ── PHASE 6: Recalibration on train data ──
print("\n" + "="*80)
print("PHASE 6: Threshold Recalibration (Train Only)")
print("="*80)

fine_thresholds = [0.08, 0.10, 0.12, 0.14, 0.15, 0.16, 0.18, 0.20, 0.22, 0.25]
print("\nTrain-only grid search:")
best_roi = -999
best_thr = 0.12
for thr in fine_thresholds:
    sigs = grade_signals(train, thr)
    if len(sigs) < 20: continue
    roi, w, l, p, wr = compute_roi(sigs, 'over_price')
    print(f"  thr={thr:.2f}  n={len(sigs):4d}  WR={wr:.3f}  ROI={roi:+.4f}")
    if roi > best_roi:
        best_roi = roi
        best_thr = thr

print(f"\nBest train threshold: {best_thr:.2f} (ROI={best_roi:+.4f})")

# Validate best on OOS
oos_sigs_best = grade_signals(oos, best_thr)
if len(oos_sigs_best)>0:
    roi_oos, w, l, p, wr = compute_roi(oos_sigs_best, 'over_price')
    print(f"OOS at best train thr={best_thr:.2f}: n={len(oos_sigs_best)}, WR={wr:.3f}, ROI={roi_oos:+.4f}")

# Also check 0.12 on OOS for comparison
oos_sigs_12 = grade_signals(oos, 0.12)
if len(oos_sigs_12)>0:
    roi_oos_12, w12, l12, p12, wr12 = compute_roi(oos_sigs_12, 'over_price')
    print(f"OOS at thr=0.12: n={len(oos_sigs_12)}, WR={wr12:.3f}, ROI={roi_oos_12:+.4f}")

# ── Model base stats ──
print("\n" + "="*80)
print("Model Accuracy Stats")
print("="*80)
for label, subset in [('TRAIN', train), ('OOS', oos), ('ALL', valid)]:
    mae = np.abs(subset['pred_total'] - subset['actual_total']).mean()
    rmse = np.sqrt(((subset['pred_total'] - subset['actual_total'])**2).mean())
    mkt_mae = np.abs(subset['closing_total'] - subset['actual_total']).mean()
    mkt_rmse = np.sqrt(((subset['closing_total'] - subset['actual_total'])**2).mean())
    bias = (subset['pred_total'] - subset['actual_total']).mean()
    print(f"  {label:5s}: MAE={mae:.3f} RMSE={rmse:.3f} bias={bias:+.3f} | Market MAE={mkt_mae:.3f} RMSE={mkt_rmse:.3f}")

# ── DRIFT analysis ──
print("\n" + "="*80)
print("DRIFT Analysis")
print("="*80)
# Check if VALIDATE_DRIFT=0.4458 is still appropriate for new model
for label, subset in [('TRAIN', train), ('OOS', oos)]:
    raw_pred = subset['pred_total'] - DRIFT  # remove drift
    raw_bias = (raw_pred - subset['actual_total']).mean()
    cal_bias = (subset['pred_total'] - subset['actual_total']).mean()
    print(f"  {label}: Raw bias (no drift)={raw_bias:+.3f}, Calibrated bias (drift={DRIFT})={cal_bias:+.3f}")
    
    # Optimal drift
    optimal_drift = subset['actual_total'].mean() - raw_pred.mean()
    print(f"  {label}: Optimal drift = {optimal_drift:.4f}")

# ── Save results ──
results_df.to_csv(OUT / 'NHL_SIGNAL_FINAL_TABLE.csv', index=False)

# Save all scored signals for reference
all_sigs.to_csv(OUT / 'all_scored_signals.csv', index=False)

print("\nDone. Files saved to", OUT)
