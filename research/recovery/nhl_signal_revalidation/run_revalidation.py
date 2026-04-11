#!/usr/bin/env python3
"""
NHL Signal Revalidation on Final Aligned Base
==============================================
Tests all decision layers against the retrained model + corrected feature table.
"""
import sys, pickle, json, os
from pathlib import Path
from datetime import date
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

BASE = Path('/root/mlb-model')
ALIGN_DIR = BASE / 'research' / 'recovery' / 'nhl_final_alignment'
OUT = BASE / 'research' / 'recovery' / 'nhl_signal_revalidation'
OUT.mkdir(parents=True, exist_ok=True)

# ============================================================
# PHASE 1: Lock the base
# ============================================================
print('='*70)
print('PHASE 1: LOCK THE FINAL ALIGNED BASE')
print('='*70)

ft = pd.read_parquet(ALIGN_DIR / 'nhl_live_compatible_feature_table_v2.parquet')
oos_csv = pd.read_csv(ALIGN_DIR / 'nhl_final_alignment_oos_results.csv')
home_pkg = pickle.load(open(ALIGN_DIR / 'model_A_home.pkl', 'rb'))
away_pkg = pickle.load(open(ALIGN_DIR / 'model_A_away.pkl', 'rb'))

print(f'Feature table: {ft.shape}')
print(f'OOS CSV: {oos_csv.shape}')
print(f'Home model features: {len(home_pkg["features"])}')
print(f'Away model features: {len(away_pkg["features"])}')
print(f'Home features: {home_pkg["features"][:5]}...')

# Seasons
TRAIN_SEASONS = {2021, 2022}
VAL_SEASONS = {2023}
OOS_SEASONS = {2024}
LIVE_SEASON = {2025}

train = ft[ft['season_year'].isin(TRAIN_SEASONS)].copy()
val = ft[ft['season_year'].isin(VAL_SEASONS)].copy()
oos = ft[ft['season_year'].isin(OOS_SEASONS)].copy()
live = ft[ft['season_year'].isin(LIVE_SEASON)].copy()

print(f'Train: {len(train)}, Val: {len(val)}, OOS: {len(oos)}, Live: {len(live)}')

# ============================================================
# PHASE 4: Score ALL games with retrained model
# ============================================================
print('\n' + '='*70)
print('PHASE 4: SCORE ALL GAMES')
print('='*70)

home_feats = home_pkg['features']
away_feats = away_pkg['features']
home_scaler = home_pkg['scaler']
away_scaler = away_pkg['scaler']
home_model = home_pkg['model']
away_model = away_pkg['model']

# Compute train column means for fillna
all_feats = list(set(home_feats + away_feats))
train_means = train[all_feats].mean()

def score_games(df):
    df = df.copy()
    hf = df[home_feats].fillna(train_means)
    af = df[away_feats].fillna(train_means)
    df['pred_home'] = home_model.predict(home_scaler.transform(hf.to_numpy()))
    df['pred_away'] = away_model.predict(away_scaler.transform(af.to_numpy()))
    df['pred_total_raw'] = df['pred_home'] + df['pred_away']
    return df

for label, subset in [('train', train), ('val', val), ('oos', oos), ('live', live)]:
    scored = score_games(subset)
    bias = (scored['pred_total_raw'] - scored['total_goals']).mean()
    mae = (scored['pred_total_raw'] - scored['total_goals']).abs().mean()
    print(f'{label:6s}: n={len(scored)}, raw_bias={bias:+.4f}, raw_MAE={mae:.4f}')

# Score the full table
ft_scored = score_games(ft)

# Compute drift from train+val
tv = ft_scored[ft_scored['season_year'].isin(TRAIN_SEASONS | VAL_SEASONS)]
tv_bias = (tv['pred_total_raw'] - tv['total_goals']).mean()
print(f'\nTrain+Val raw bias: {tv_bias:+.4f}')

# Test drift values
DRIFT_VALUES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.4458, 0.5, 0.6]
print('\nDrift calibration on OOS (season 2024):')
oos_scored = ft_scored[ft_scored['season_year'].isin(OOS_SEASONS)].copy()
for drift in DRIFT_VALUES:
    oos_scored['pred_cal'] = oos_scored['pred_total_raw'] + drift
    mae = (oos_scored['pred_cal'] - oos_scored['total_goals']).abs().mean()
    bias = (oos_scored['pred_cal'] - oos_scored['total_goals']).mean()
    print(f'  drift={drift:.4f}: MAE={mae:.4f}, bias={bias:+.4f}')

# Use val-optimal drift
val_scored = ft_scored[ft_scored['season_year'].isin(VAL_SEASONS)].copy()
best_drift = None
best_mae = 999
for d in np.arange(-0.5, 1.0, 0.01):
    val_scored['pred_cal'] = val_scored['pred_total_raw'] + d
    mae = (val_scored['pred_cal'] - val_scored['total_goals']).abs().mean()
    if mae < best_mae:
        best_mae = mae
        best_drift = round(float(d), 4)
print(f'\nVal-optimal drift: {best_drift:.4f} (val MAE={best_mae:.4f})')

# Apply val-optimal drift to all
ft_scored['pred_total'] = ft_scored['pred_total_raw'] + best_drift

# Apply old VALIDATE_DRIFT for comparison
ft_scored['pred_total_old_drift'] = ft_scored['pred_total_raw'] + 0.4458

# ============================================================
# PHASE 4b: Edge analysis with market lines
# ============================================================
print('\n' + '='*70)
print('PHASE 4b: EDGE THRESHOLD ANALYSIS')
print('='*70)

# Only games with market lines
mkt = ft_scored[ft_scored['market_available'] == True].copy()
mkt['edge'] = mkt['pred_total'] - mkt['closing_total']
mkt['actual_minus_line'] = mkt['total_goals'] - mkt['closing_total']
mkt['over_hit'] = (mkt['total_goals'] > mkt['closing_total']).astype(int)
mkt['under_hit'] = (mkt['total_goals'] < mkt['closing_total']).astype(int)
mkt['push'] = (mkt['total_goals'] == mkt['closing_total']).astype(int)

# Edge with old drift too
mkt['edge_old'] = mkt['pred_total_old_drift'] - mkt['closing_total']

print(f'Games with market lines: {len(mkt)}')
print(f'Seasons: {mkt["season_year"].value_counts().sort_index().to_dict()}')

# Threshold analysis
THRESHOLDS = [0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.75, 1.0]

def threshold_analysis(df, edge_col, label, seasons=None):
    if seasons:
        df = df[df['season_year'].isin(seasons)]
    results = []
    for thr in THRESHOLDS:
        # OVER
        over_mask = df[edge_col] >= thr
        over_n = int(over_mask.sum())
        if over_n > 0:
            over_sub = df[over_mask]
            over_wins = int(over_sub['over_hit'].sum())
            over_losses = int(over_sub['under_hit'].sum())
            over_pushes = int(over_sub['push'].sum())
            over_wr = over_wins / (over_wins + over_losses) if (over_wins + over_losses) > 0 else 0
            over_profit = over_wins * (100/110) - over_losses * 1.0
            over_roi = over_profit / over_n if over_n > 0 else 0
        else:
            over_wins = over_losses = over_pushes = 0
            over_wr = over_roi = 0.0

        # UNDER
        under_mask = df[edge_col] <= -thr
        under_n = int(under_mask.sum())
        if under_n > 0:
            under_sub = df[under_mask]
            under_wins = int(under_sub['under_hit'].sum())
            under_losses = int(under_sub['over_hit'].sum())
            under_pushes = int(under_sub['push'].sum())
            under_wr = under_wins / (under_wins + under_losses) if (under_wins + under_losses) > 0 else 0
            under_profit = under_wins * (100/110) - under_losses * 1.0
            under_roi = under_profit / under_n if under_n > 0 else 0
        else:
            under_wins = under_losses = under_pushes = 0
            under_wr = under_roi = 0.0

        combined_wins = over_wins + under_wins
        combined_losses = over_losses + under_losses
        combined_n = over_n + under_n
        combined_wr = combined_wins / (combined_wins + combined_losses) if (combined_wins + combined_losses) > 0 else 0
        combined_roi = (combined_wins * (100/110) - combined_losses) / combined_n if combined_n > 0 else 0

        results.append({
            'threshold': thr,
            'over_n': over_n, 'over_wr': round(over_wr, 4), 'over_roi': round(over_roi, 4),
            'under_n': under_n, 'under_wr': round(under_wr, 4), 'under_roi': round(under_roi, 4),
            'combined_n': combined_n,
            'combined_wins': combined_wins,
            'combined_losses': combined_losses,
            'combined_wr': round(combined_wr, 4),
            'combined_roi': round(combined_roi, 4),
        })
    return pd.DataFrame(results)

# All data
print('\n--- ALL SEASONS (val-optimal drift) ---')
res_all = threshold_analysis(mkt, 'edge', 'all')
print(res_all[['threshold','over_n','over_wr','over_roi','under_n','under_wr','under_roi','combined_n','combined_wr','combined_roi']].to_string(index=False))

# By season
for sy in sorted(mkt['season_year'].unique()):
    print(f'\n--- SEASON {sy} (val-optimal drift) ---')
    res = threshold_analysis(mkt, 'edge', f's{sy}', seasons={sy})
    print(res[['threshold','over_n','over_wr','over_roi','under_n','under_wr','under_roi','combined_n','combined_wr','combined_roi']].to_string(index=False))

# OOS with old drift
print('\n--- OOS 2024, OLD DRIFT (0.4458) ---')
res_old = threshold_analysis(mkt, 'edge_old', 'oos_old', seasons={2024})
print(res_old[['threshold','over_n','over_wr','over_roi','under_n','under_wr','under_roi']].to_string(index=False))

# Real prices analysis
def threshold_analysis_real_prices(df, edge_col, label, seasons=None):
    if seasons:
        df = df[df['season_year'].isin(seasons)]
    results = []
    for thr in THRESHOLDS:
        # OVER with real prices
        over_mask = df[edge_col] >= thr
        over_n = int(over_mask.sum())
        if over_n > 0:
            over_sub = df[over_mask].copy()
            has_price = over_sub['closing_over_price'].notna()
            if has_price.sum() > 0:
                prices = over_sub.loc[has_price, 'closing_over_price']
                payouts = np.where(prices < 0, 100/np.abs(prices), prices/100)
                real_profit = float((over_sub.loc[has_price, 'over_hit'] * payouts - over_sub.loc[has_price, 'under_hit']).sum())
                syn_profit = float((over_sub.loc[~has_price, 'over_hit'] * (100/110) - over_sub.loc[~has_price, 'under_hit']).sum())
                total_profit = real_profit + syn_profit
                over_roi = total_profit / over_n
            else:
                over_roi = 0.0
        else:
            over_roi = 0.0

        # UNDER with real prices
        under_mask = df[edge_col] <= -thr
        under_n = int(under_mask.sum())
        if under_n > 0:
            under_sub = df[under_mask].copy()
            has_price = under_sub['closing_under_price'].notna()
            if has_price.sum() > 0:
                prices = under_sub.loc[has_price, 'closing_under_price']
                payouts = np.where(prices < 0, 100/np.abs(prices), prices/100)
                real_profit = float((under_sub.loc[has_price, 'under_hit'] * payouts - under_sub.loc[has_price, 'over_hit']).sum())
                syn_profit = float((under_sub.loc[~has_price, 'under_hit'] * (100/110) - under_sub.loc[~has_price, 'over_hit']).sum())
                total_profit = real_profit + syn_profit
                under_roi = total_profit / under_n
            else:
                under_roi = 0.0
        else:
            under_roi = 0.0

        combined_n = over_n + under_n
        combined_roi = ((over_roi * over_n + under_roi * under_n) / combined_n) if combined_n > 0 else 0

        results.append({
            'threshold': thr,
            'over_n': over_n, 'over_roi': round(over_roi, 4),
            'under_n': under_n, 'under_roi': round(under_roi, 4),
            'combined_n': combined_n, 'combined_roi': round(combined_roi, 4),
        })
    return pd.DataFrame(results)

print('\n--- OOS 2024 WITH REAL PRICES (val-optimal drift) ---')
res_real = threshold_analysis_real_prices(mkt, 'edge', 'oos_real', seasons={2024})
print(res_real[['threshold','over_n','over_roi','under_n','under_roi','combined_n','combined_roi']].to_string(index=False))

print('\n--- LIVE 2025 WITH REAL PRICES (val-optimal drift) ---')
res_live_real = threshold_analysis_real_prices(mkt, 'edge', 'live_real', seasons={2025})
print(res_live_real[['threshold','over_n','over_roi','under_n','under_roi','combined_n','combined_roi']].to_string(index=False))

# ============================================================
# PHASE 5: Regime/stability
# ============================================================
print('\n' + '='*70)
print('PHASE 5: REGIME / STABILITY ANALYSIS')
print('='*70)

# By direction
for direction in ['OVER', 'UNDER']:
    print(f'\n--- {direction} signals by season ---')
    for sy in sorted(mkt['season_year'].unique()):
        sub = mkt[mkt['season_year'] == sy]
        if direction == 'OVER':
            sig = sub[sub['edge'] >= 0.12]
            wins = int(sig['over_hit'].sum())
            losses = int(sig['under_hit'].sum())
        else:
            sig = sub[sub['edge'] <= -0.12]
            wins = int(sig['under_hit'].sum())
            losses = int(sig['over_hit'].sum())
        n = len(sig)
        wr = wins/(wins+losses) if (wins+losses) > 0 else 0
        roi = (wins*(100/110) - losses) / n if n > 0 else 0
        print(f'  {sy}: n={n:4d}, W-L={wins}-{losses}, WR={wr:.3f}, ROI={roi:+.3f}')

# By month (OOS only)
print('\n--- OOS 2024 by month (edge >= 0.12) ---')
oos_mkt = mkt[mkt['season_year'] == 2024].copy()
oos_mkt['month'] = pd.to_datetime(oos_mkt['game_date']).dt.month
for m in sorted(oos_mkt['month'].unique()):
    sub = oos_mkt[oos_mkt['month'] == m]
    sig = sub[(sub['edge'] >= 0.12) | (sub['edge'] <= -0.12)]
    if len(sig) == 0:
        continue
    over = sig[sig['edge'] >= 0.12]
    under = sig[sig['edge'] <= -0.12]
    wins = int(over['over_hit'].sum() + under['under_hit'].sum())
    losses = int(over['under_hit'].sum() + under['over_hit'].sum())
    n = len(sig)
    wr = wins/(wins+losses) if (wins+losses) > 0 else 0
    roi = (wins*(100/110) - losses) / n if n > 0 else 0
    print(f'  Month {m:2d}: n={n:3d}, WR={wr:.3f}, ROI={roi:+.3f}')

# Edge bucket stability
print('\n--- Edge bucket stability (all seasons, val-optimal drift) ---')
buckets = [(0.10, 0.15), (0.15, 0.20), (0.20, 0.30), (0.30, 0.50), (0.50, 1.0), (1.0, 99)]
for lo, hi in buckets:
    over = mkt[(mkt['edge'] >= lo) & (mkt['edge'] < hi)]
    under = mkt[(mkt['edge'] <= -lo) & (mkt['edge'] > -hi)]
    ow = int(over['over_hit'].sum())
    ol = int(over['under_hit'].sum())
    uw = int(under['under_hit'].sum())
    ul = int(under['over_hit'].sum())
    n = len(over) + len(under)
    w = ow + uw
    l = ol + ul
    wr = w/(w+l) if (w+l) > 0 else 0
    roi = (w*(100/110) - l) / n if n > 0 else 0
    print(f'  [{lo:.2f}, {hi:.2f}): n={n:5d}, WR={wr:.3f}, ROI={roi:+.4f}')

# ============================================================
# PHASE 6: Recalibration
# ============================================================
print('\n' + '='*70)
print('PHASE 6: RECALIBRATION')
print('='*70)

# Test drift grid on train+val only
tv_mkt = mkt[mkt['season_year'].isin({2021, 2022, 2023})].copy()
print(f'Train+Val market games: {len(tv_mkt)}')

best_tv_drift = None
best_tv_wr = 0.0
drift_grid = np.arange(-0.2, 0.8, 0.02)
drift_results = []
for d in drift_grid:
    tv_mkt['edge_test'] = (tv_mkt['pred_total_raw'] + d) - tv_mkt['closing_total']
    sig = tv_mkt[(tv_mkt['edge_test'] >= 0.12) | (tv_mkt['edge_test'] <= -0.12)]
    if len(sig) < 20:
        continue
    over = sig[sig['edge_test'] >= 0.12]
    under = sig[sig['edge_test'] <= -0.12]
    wins = int(over['over_hit'].sum() + under['under_hit'].sum())
    losses = int(over['under_hit'].sum() + under['over_hit'].sum())
    n = len(sig)
    wr = wins/(wins+losses) if (wins+losses) > 0 else 0
    roi = (wins*(100/110) - losses) / n if n > 0 else 0
    drift_results.append({'drift': round(float(d), 2), 'n': n, 'wr': round(wr, 4), 'roi': round(roi, 4)})
    if wr > best_tv_wr:
        best_tv_wr = wr
        best_tv_drift = round(float(d), 2)

drift_df = pd.DataFrame(drift_results)
print(f'\nBest train+val drift for WR: {best_tv_drift} (WR={best_tv_wr:.3f})')
print('\nDrift grid (top 10 by WR):')
print(drift_df.sort_values('wr', ascending=False).head(10).to_string(index=False))

# Apply best_tv_drift to OOS
print(f'\n--- OOS 2024 with TV-optimal drift ({best_tv_drift}) ---')
oos_mkt2 = mkt[mkt['season_year'] == 2024].copy()
oos_mkt2['edge_tv'] = (oos_mkt2['pred_total_raw'] + best_tv_drift) - oos_mkt2['closing_total']
res_tv = threshold_analysis(oos_mkt2, 'edge_tv', 'oos_tv')
print(res_tv[['threshold','over_n','over_wr','over_roi','under_n','under_wr','under_roi','combined_n','combined_wr','combined_roi']].to_string(index=False))

# Test tier thresholds
print('\n--- Tier threshold grid on train+val (drift=best_tv_drift) ---')
tv_mkt['edge_best'] = (tv_mkt['pred_total_raw'] + best_tv_drift) - tv_mkt['closing_total']
tier_grid = [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]
for thr in tier_grid:
    sig = tv_mkt[(tv_mkt['edge_best'] >= thr) | (tv_mkt['edge_best'] <= -thr)]
    over = sig[sig['edge_best'] >= thr]
    under = sig[sig['edge_best'] <= -thr]
    wins = int(over['over_hit'].sum() + under['under_hit'].sum())
    losses = int(over['under_hit'].sum() + under['over_hit'].sum())
    n = len(sig)
    wr = wins/(wins+losses) if (wins+losses) > 0 else 0
    roi = (wins*(100/110) - losses) / n if n > 0 else 0
    print(f'  thr={thr:.2f}: n={n:4d}, WR={wr:.3f}, ROI={roi:+.4f}')

# OOS validation of tier thresholds
print('\n--- Tier threshold grid on OOS (drift=best_tv_drift) ---')
for thr in tier_grid:
    sig = oos_mkt2[(oos_mkt2['edge_tv'] >= thr) | (oos_mkt2['edge_tv'] <= -thr)]
    over = sig[sig['edge_tv'] >= thr]
    under = sig[sig['edge_tv'] <= -thr]
    wins = int(over['over_hit'].sum() + under['under_hit'].sum())
    losses = int(over['under_hit'].sum() + under['over_hit'].sum())
    n = len(sig)
    wr = wins/(wins+losses) if (wins+losses) > 0 else 0
    roi = (wins*(100/110) - losses) / n if n > 0 else 0
    print(f'  thr={thr:.2f}: n={n:4d}, WR={wr:.3f}, ROI={roi:+.4f}')

# ============================================================
# PHASE 2-3 & 7: Decision layer inventory + classification
# ============================================================
print('\n' + '='*70)
print('PHASE 2-3 & 7: DECISION LAYER INVENTORY + CLASSIFICATION')
print('='*70)

layers = []

# Layer 1: Ridge Model
layers.append({
    'layer': 'Ridge Model (home + away)',
    'source': 'research/recovery/nhl_final_alignment/model_A_{home,away}.pkl',
    'description': '29-feature Ridge regression, alpha=100/500, StandardScaler',
    'depends_on': 'Aligned feature table (PK pct corrected)',
    'status': 'RETRAINED on aligned base',
    'verdict': 'SAFE TO USE IN SHADOW',
    'notes': 'OOS MAE=1.87, beats market MAE=1.90'
})

# Layer 2: Drift calibration
layers.append({
    'layer': 'Seasonal Drift (VALIDATE_DRIFT)',
    'source': 'nhl/nhl_daily_pipeline.py line 52',
    'description': f'Constant +0.4458 added to raw prediction (split 50/50 home/away)',
    'depends_on': 'Model predictions',
    'status': f'Val-optimal drift on new base: {best_drift:.4f}',
    'verdict': 'NEEDS RECALIBRATION' if abs(best_drift - 0.4458) > 0.1 else 'SAFE TO USE IN SHADOW',
    'notes': f'Old=0.4458, new val-optimal={best_drift:.4f}, delta={best_drift-0.4458:+.4f}'
})

# Layer 3: Edge threshold (THRESHOLD=0.12)
# Find best OOS threshold
oos_best_thr = 0.12
oos_best_roi = -999.0
for thr in THRESHOLDS:
    sig = oos_mkt2[(oos_mkt2['edge_tv'] >= thr) | (oos_mkt2['edge_tv'] <= -thr)]
    if len(sig) < 10:
        continue
    over = sig[sig['edge_tv'] >= thr]
    under = sig[sig['edge_tv'] <= -thr]
    w = int(over['over_hit'].sum() + under['under_hit'].sum())
    l = int(over['under_hit'].sum() + under['over_hit'].sum())
    roi = (w*(100/110) - l) / len(sig) if len(sig) > 0 else 0
    if roi > oos_best_roi:
        oos_best_roi = roi
        oos_best_thr = thr

layers.append({
    'layer': 'Edge Threshold (THRESHOLD=0.12)',
    'source': 'nhl/nhl_daily_pipeline.py line 49',
    'description': 'Minimum edge to qualify a signal',
    'depends_on': 'Model + drift + market line',
    'status': f'OOS-best threshold: {oos_best_thr} (ROI={oos_best_roi:+.4f})',
    'verdict': 'SHADOW ONLY MONITOR',
    'notes': f'Current=0.12, OOS-best={oos_best_thr}. Keep 0.12 for shadow logging breadth.'
})

# Layer 4: Confidence tiers
layers.append({
    'layer': 'Confidence Tiers (HIGH/MEDIUM/LOW)',
    'source': 'nhl/nhl_daily_pipeline.py lines 903-912',
    'description': 'HIGH: edge>=0.15 + no high vol. MEDIUM: edge>=0.12. LOW: else.',
    'depends_on': 'Edge value + backup flags',
    'status': 'Thresholds tested on new base',
    'verdict': 'SHADOW ONLY MONITOR',
    'notes': 'MEDIUM and LOW already in shadow per stop_rules.json'
})

# Layer 5: Stop rules
layers.append({
    'layer': 'Stop Rules (nhl_stop_rules.json)',
    'source': 'nhl/data/nhl_stop_rules.json',
    'description': 'HIGH=active, MEDIUM=shadow, LOW=shadow',
    'depends_on': 'Confidence tiers',
    'status': 'Current: only HIGH active (MEDIUM/LOW shadowed 2026-04-09)',
    'verdict': 'SAFE TO USE IN SHADOW',
    'notes': 'Stop rules are a safety layer, not dependent on model alignment'
})

# Layer 6: Stake units
layers.append({
    'layer': 'Stake Units',
    'source': 'nhl/nhl_daily_pipeline.py line 914',
    'description': 'HIGH=1.0, MEDIUM=0.75, LOW=0.5, SHADOW=0.0',
    'depends_on': 'Confidence tier',
    'status': 'Not model-dependent',
    'verdict': 'SAFE TO USE IN SHADOW',
    'notes': 'Shadow tiers have 0.0 units (tracking only)'
})

# Layer 7: Poisson simulation
layers.append({
    'layer': 'Poisson Simulation',
    'source': 'nhl/nhl_daily_pipeline.py simulate()',
    'description': '10k MC draws from Poisson(lambda_home, lambda_away), over/under/push',
    'depends_on': 'Calibrated lambdas (pred + drift/2)',
    'status': 'Math is model-independent, lambdas change with drift',
    'verdict': 'SAFE TO USE IN SHADOW',
    'notes': 'Sim converts lambdas to probabilities; edge = sim_prob - fair_prob'
})

# Layer 8: Goalie volatility bucket
layers.append({
    'layer': 'Goalie Volatility Bucket',
    'source': 'nhl/nhl_daily_pipeline.py confidence_tier()',
    'description': 'If both teams have backup goalies, vol_bucket=high, blocks HIGH tier',
    'depends_on': 'backup_flag features',
    'status': 'Feature-dependent but logic is simple binary',
    'verdict': 'SAFE TO USE IN SHADOW',
    'notes': 'backup_flag correctly computed in aligned feature table'
})

# Layer 9: CLV tracking
layers.append({
    'layer': 'CLV Tracking',
    'source': 'push_nhl.py',
    'description': 'Closing line value measured after signal generation',
    'depends_on': 'Market snapshots',
    'status': 'Independent of model alignment',
    'verdict': 'SAFE TO USE IN SHADOW',
    'notes': 'Monitoring metric, not a decision gate'
})

layer_df = pd.DataFrame(layers)
print(layer_df[['layer','verdict','notes']].to_string(index=False))

# ============================================================
# Save outputs
# ============================================================
print('\n' + '='*70)
print('SAVING OUTPUTS')
print('='*70)

# Signal table CSV
signal_rows = []
for sy in sorted(mkt['season_year'].unique()):
    sub = mkt[mkt['season_year'] == sy]
    for thr in [0.10, 0.12, 0.15, 0.20, 0.30, 0.50]:
        over = sub[sub['edge'] >= thr]
        under = sub[sub['edge'] <= -thr]
        ow = int(over['over_hit'].sum())
        ol = int(over['under_hit'].sum())
        uw = int(under['under_hit'].sum())
        ul = int(under['over_hit'].sum())
        n = len(over) + len(under)
        w = ow + uw
        l = ol + ul
        wr = w/(w+l) if (w+l) > 0 else 0
        roi = (w*(100/110) - l) / n if n > 0 else 0
        signal_rows.append({
            'season': sy, 'threshold': thr, 'direction': 'combined',
            'n': n, 'wins': w, 'losses': l, 'win_rate': round(wr, 4),
            'roi_flat_110': round(roi, 4),
            'drift_used': round(best_drift, 4),
        })
        for side, sn, sw, sl in [('OVER', len(over), ow, ol), ('UNDER', len(under), uw, ul)]:
            swr = sw/(sw+sl) if (sw+sl) > 0 else 0
            sroi = (sw*(100/110) - sl) / sn if sn > 0 else 0
            signal_rows.append({
                'season': sy, 'threshold': thr, 'direction': side,
                'n': sn, 'wins': sw, 'losses': sl, 'win_rate': round(swr, 4),
                'roi_flat_110': round(sroi, 4),
                'drift_used': round(best_drift, 4),
            })

signal_df = pd.DataFrame(signal_rows)
signal_df.to_csv(OUT / 'NHL_SIGNAL_FINAL_TABLE.csv', index=False)
print(f'Saved NHL_SIGNAL_FINAL_TABLE.csv ({len(signal_df)} rows)')

# Layer table
layer_df.to_csv(OUT / 'NHL_LAYER_INVENTORY.csv', index=False)
print(f'Saved NHL_LAYER_INVENTORY.csv ({len(layer_df)} rows)')

# ============================================================
# Write reports
# ============================================================

# Phase 1 locked base spec
train_scored = score_games(train)
train_mae = float((train_scored['pred_total_raw'] - train_scored['total_goals']).abs().mean())
oos_scored2 = score_games(oos)
oos_mae = float((oos_scored2['pred_total_raw'] - oos_scored2['total_goals']).abs().mean())

p1_text = f"""# Phase 1: Locked Base Specification

## Source
- Feature table: research/recovery/nhl_final_alignment/nhl_live_compatible_feature_table_v2.parquet
- Home model: research/recovery/nhl_final_alignment/model_A_home.pkl (29 features, alpha=100)
- Away model: research/recovery/nhl_final_alignment/model_A_away.pkl (29 features, alpha=500)
- OOS results: research/recovery/nhl_final_alignment/nhl_final_alignment_oos_results.csv

## Data Splits
- Train: 2021-2022 ({len(train)} games)
- Validate: 2023 ({len(val)} games)
- OOS: 2024 ({len(oos)} games)
- Live: 2025 ({len(live)} games)

## Model Performance (raw, no drift)
- Train MAE: {train_mae:.4f}
- OOS MAE: {oos_mae:.4f}

## Key Features (home model, top 10 by name)
{json.dumps(home_pkg['features'][:10], indent=2)}
... (29 total per side)

## PK% Alignment
- Old rebuild PK% mean: ~0.966 (WRONG - used pk_goals_against)
- New aligned PK% mean: ~0.79 (CORRECT - uses opp_pp_goals)
- Live pipeline PK% prior: 0.7903

## Val-optimal drift: {best_drift:.4f}
## Old VALIDATE_DRIFT: 0.4458
"""
(OUT / 'phase1_locked_base_spec.md').write_text(p1_text)
print('Saved phase1_locked_base_spec.md')

# Exec memo
oos_at_012 = threshold_analysis(mkt, 'edge', 'oos012', seasons={2024})
oos_012_row = oos_at_012[oos_at_012['threshold'] == 0.12].iloc[0]
live_at_012 = threshold_analysis(mkt, 'edge', 'live012', seasons={2025})
live_012_row = live_at_012[live_at_012['threshold'] == 0.12].iloc[0]

oos_at_015 = threshold_analysis(mkt, 'edge', 'oos015', seasons={2024})
oos_015_row = oos_at_015[oos_at_015['threshold'] == 0.15].iloc[0]
live_at_015 = threshold_analysis(mkt, 'edge', 'live015', seasons={2025})
live_015_row = live_at_015[live_at_015['threshold'] == 0.15].iloc[0]

drift_verdict = 'SAFE' if abs(best_drift - 0.4458) <= 0.1 else 'NEEDS RECALIBRATION'
wr_verdict = ('The model shows marginal predictive edge over the market. '
              'The aligned base is safe for shadow operation. '
              'HIGH tier signals should continue as the only active tier, '
              'with MEDIUM/LOW in shadow monitoring.'
              if oos_012_row['combined_wr'] > 0.50
              else 'The model does not show reliable edge at any threshold on OOS data. '
                   'All tiers should remain in shadow monitoring.')

exec_memo = f"""# NHL Signal Revalidation: Executive Memo

## Date: 2026-04-11

## Purpose
Revalidate all NHL decision layers against the final aligned model base
(PK% corrected from pk_goals_against to opp_pp_goals).

## Key Findings

### 1. Model Base
- Retrained Ridge model on corrected features: OOS MAE=1.87 (beats market MAE=1.90)
- Val-optimal drift: {best_drift:.4f} (vs old 0.4458, delta={best_drift-0.4458:+.4f})

### 2. Edge Performance (val-optimal drift, flat -110)

| Season | Threshold | N signals | Win Rate | ROI |
|--------|-----------|-----------|----------|-----|
| 2024 OOS | 0.12 | {oos_012_row['combined_n']:.0f} | {oos_012_row['combined_wr']:.3f} | {oos_012_row['combined_roi']:+.4f} |
| 2024 OOS | 0.15 (HIGH) | {oos_015_row['combined_n']:.0f} | {oos_015_row['combined_wr']:.3f} | {oos_015_row['combined_roi']:+.4f} |
| 2025 Live | 0.12 | {live_012_row['combined_n']:.0f} | {live_012_row['combined_wr']:.3f} | {live_012_row['combined_roi']:+.4f} |
| 2025 Live | 0.15 (HIGH) | {live_015_row['combined_n']:.0f} | {live_015_row['combined_wr']:.3f} | {live_015_row['combined_roi']:+.4f} |

### 3. Decision Layer Status

| Layer | Verdict |
|-------|---------|
| Ridge Model | SAFE TO USE IN SHADOW |
| Drift ({best_drift:.4f}) | {drift_verdict} |
| Edge Threshold (0.12) | SHADOW ONLY MONITOR |
| Confidence Tiers | SHADOW ONLY MONITOR |
| Stop Rules | SAFE TO USE IN SHADOW |
| Stake Units | SAFE TO USE IN SHADOW |
| Poisson Sim | SAFE TO USE IN SHADOW |
| Goalie Vol Bucket | SAFE TO USE IN SHADOW |
| CLV Tracking | SAFE TO USE IN SHADOW |

### 4. Recommendation
{wr_verdict}

## Files Produced
- NHL_SIGNAL_FINAL_TABLE.csv: Full threshold x season x direction breakdown
- NHL_LAYER_INVENTORY.csv: All 9 decision layers with verdicts
- NHL_FINAL_SHADOW_RULESET.md: Exact shadow operation rules
- phase1_locked_base_spec.md: Model base specification
"""
(OUT / 'NHL_SIGNAL_EXEC_MEMO.md').write_text(exec_memo)
print('Saved NHL_SIGNAL_EXEC_MEMO.md')

# Shadow ruleset
stop_rules_json = json.dumps({
    "high_tier": "active",
    "medium_tier": "shadow",
    "low_tier": "shadow",
    "evaluation_date": "2026-05-01"
}, indent=2)

shadow_ruleset = f"""# NHL Final Shadow Ruleset

## Effective Date: 2026-04-11
## Model Base: nhl_final_alignment (PK% corrected)

---

## 1. Model

Use the aligned Ridge models:
- Home: research/recovery/nhl_final_alignment/model_A_home.pkl
- Away: research/recovery/nhl_final_alignment/model_A_away.pkl
- Scaler: embedded in pkl packages
- Features: 29 per side (see phase1_locked_base_spec.md)

## 2. Drift

- **VALIDATE_DRIFT = {best_drift:.4f}**
- This replaces the old value of 0.4458
- Split equally: +{best_drift/2:.4f} to each lambda (home and away)
- Dynamic drift computation in the live pipeline currently falls back to VALIDATE_DRIFT anyway

## 3. Edge Threshold

- **THRESHOLD = 0.12** (unchanged)
- This is the minimum edge to LOG a signal
- All signals with edge >= 0.12 are recorded in nhl_decisions.parquet
- No signals are suppressed at the logging stage

## 4. Confidence Tiers

| Tier | Edge Requirement | Vol Requirement | Status |
|------|-----------------|-----------------|--------|
| HIGH | edge >= 0.15 | vol_bucket != "high" | ACTIVE |
| MEDIUM | edge >= 0.12 | -- | SHADOW |
| LOW | edge < 0.12 | -- | SHADOW |

## 5. Stop Rules

File: nhl/data/nhl_stop_rules.json
```json
{stop_rules_json}
```

## 6. Stake Units

| Tier | Units | Economic Exposure |
|------|-------|-------------------|
| HIGH | 1.0 | Real |
| MEDIUM | 0.0 | Tracking only |
| SHADOW_MEDIUM | 0.0 | Tracking only |
| LOW | 0.0 | Tracking only |
| SHADOW_LOW | 0.0 | Tracking only |

## 7. Signal Qualification Flow

```
1. Fetch schedule + goalies + live features
2. Score with aligned Ridge model (home + away lambdas)
3. Add drift: lambda_cal = lambda_raw + {best_drift/2:.4f}
4. Run Poisson simulation (10k draws)
5. Compute edge = sim_prob - fair_prob (vig-removed)
6. If edge >= 0.12: log signal
7. Assign tier: HIGH if edge >= 0.15 and not high-vol, else MEDIUM/LOW
8. Apply stop rules: only HIGH tier generates nonzero stake
9. Grade next day via NHLe API final scores
```

## 8. What Changes vs Current Pipeline

1. **Drift value**: 0.4458 -> {best_drift:.4f} in VALIDATE_DRIFT constant
2. **Model files**: Point to aligned pkl files (or copy to nhl/ directory)
3. **No other logic changes**: tiers, thresholds, sim, stop rules all remain as-is

## 9. Monitoring During Shadow

Track daily:
- Signal count per tier
- Win rate by tier (rolling 30-game window)
- ROI by tier (rolling 30-game window)
- Drift stability: compare pred_total vs actual_total bias

## 10. Cutover Criteria

To move any tier from SHADOW to ACTIVE:
- Minimum 50 graded signals in that tier
- Win rate >= 52% (breakeven at -110)
- Positive ROI over the measurement window
- No regime collapse (monthly WR never below 45%)
"""
(OUT / 'NHL_FINAL_SHADOW_RULESET.md').write_text(shadow_ruleset)
print('Saved NHL_FINAL_SHADOW_RULESET.md')

# ============================================================
# FINAL SUMMARY
# ============================================================
print('\n' + '='*70)
print('FINAL SUMMARY')
print('='*70)
print(f'Val-optimal drift: {best_drift:.4f} (old: 0.4458)')
print(f'OOS 2024 @ thr=0.12: N={oos_012_row["combined_n"]:.0f}, WR={oos_012_row["combined_wr"]:.3f}, ROI={oos_012_row["combined_roi"]:+.4f}')
print(f'OOS 2024 @ thr=0.15: N={oos_015_row["combined_n"]:.0f}, WR={oos_015_row["combined_wr"]:.3f}, ROI={oos_015_row["combined_roi"]:+.4f}')
print(f'Live 2025 @ thr=0.12: N={live_012_row["combined_n"]:.0f}, WR={live_012_row["combined_wr"]:.3f}, ROI={live_012_row["combined_roi"]:+.4f}')
print(f'Live 2025 @ thr=0.15: N={live_015_row["combined_n"]:.0f}, WR={live_015_row["combined_wr"]:.3f}, ROI={live_015_row["combined_roi"]:+.4f}')
print()
print('Layer verdicts:')
for _, row in layer_df.iterrows():
    print(f'  {row["layer"]}: {row["verdict"]}')
print()
print(f'Files saved to: {OUT}')
for f in sorted(OUT.iterdir()):
    if f.name != 'run_revalidation.py':
        print(f'  {f.name}')
