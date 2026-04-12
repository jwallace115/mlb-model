import pandas as pd
import numpy as np
import os, json, warnings
warnings.filterwarnings('ignore')

OUT = '/root/mlb-model/research/recovery/mlb_sides_phase5_timing_mixed'

###############################################################################
# PHASE 0: Lock inputs
###############################################################################
ct = pd.read_csv('/root/mlb-model/research/recovery/mlb_sides_phase4_winpath/classification_table.csv')
ct['date'] = pd.to_datetime(ct['date'])
print(f'Classification table: {ct.shape}')
print(f'Columns: {list(ct.columns)}')
print(f'reason_class values (reason col): {ct["reason"].value_counts().to_dict()}')

# Rename for clarity
ct.rename(columns={'reason': 'reason_class'}, inplace=True)

# Branch A verdict
print('\n=== BRANCH A: SP-LED OPEN/CLOSE TIMING ===')
print('VERDICT: UNVERIFIABLE')
print('No opening ML prices in canonical odds or market_snapshots.')
print('Market snapshots contain totals open/noon/5pm/close but NO moneyline open prices.')
print('Cannot test whether SP-LED dogs offer better ROI at open vs close.')

###############################################################################
# PHASE 3: Branch B — MIXED overlay registry
###############################################################################
print('\n=== BRANCH B: MIXED OVERLAY HUNT ===')
mixed = ct[ct['reason_class'] == 'MIXED'].copy()
print(f'MIXED games total: {len(mixed)}')
print(f'By season: {mixed["season"].value_counts().sort_index().to_dict()}')

# Discovery / validation / OOS splits
disc = mixed[mixed['season'].isin([2022, 2023])].copy()
val  = mixed[mixed['season'] == 2024].copy()
oos  = mixed[mixed['season'] == 2025].copy()
print(f'Discovery: {len(disc)}, Validation: {len(val)}, OOS: {len(oos)}')

# Dog win rate baseline
print(f'\nBaseline dog WR:')
for label, df in [('Discovery', disc), ('Validation', val), ('OOS', oos)]:
    dwr = (df['fav_won'] == 0).mean()
    print(f'  {label}: {dwr:.4f} ({(df["fav_won"]==0).sum()}/{len(df)})')

###############################################################################
# Build overlay features (PIT-safe)
###############################################################################
# 1. Closing total environment
mixed['total_env'] = pd.cut(mixed['total_line'], bins=[0, 7.5, 8.5, 20], labels=['low', 'mid', 'high'])

# 2. Day vs night — need game time; approximate from date if not available
# Check if we have game time in game_table
try:
    gt = pd.read_parquet('/root/mlb-model/sim/data/game_table.parquet')
    if 'game_time' in gt.columns or 'start_time' in gt.columns:
        time_col = 'game_time' if 'game_time' in gt.columns else 'start_time'
        gt_merge = gt[['game_pk', time_col]].drop_duplicates('game_pk')
        mixed = mixed.merge(gt_merge, on='game_pk', how='left')
        if time_col in mixed.columns:
            mixed['hour'] = pd.to_datetime(mixed[time_col]).dt.hour
            mixed['day_night'] = np.where(mixed['hour'] < 17, 'day', 'night')
            print(f'Day/night from game_table: {mixed["day_night"].value_counts().to_dict()}')
    else:
        print(f'game_table cols: {[c for c in gt.columns if "time" in c.lower() or "hour" in c.lower()]}')
        mixed['day_night'] = 'unknown'
except Exception as e:
    print(f'game_table error: {e}')
    mixed['day_night'] = 'unknown'

# 3. Home dog vs away dog
mixed['dog_is_home'] = (~mixed['fav_is_home'].astype(bool)).astype(int)

# 4. SP length asymmetry — use fav/dog SP FIP as proxy (PIT-safe, already in table)
# Higher FIP diff = bigger SP gap; but we want IP asymmetry
# Use sp_fip_diff magnitude as proxy for SP quality gap
mixed['sp_gap_abs'] = mixed['sp_fip_diff'].abs()
mixed['sp_gap_tier'] = pd.cut(mixed['sp_gap_abs'], bins=[0, 0.5, 1.5, 20], labels=['tight', 'moderate', 'wide'])

# 5. Bullpen ERA asymmetry
mixed['bp_era_abs'] = mixed['bp_era_diff'].abs()
mixed['bp_adv_dog'] = (mixed['bp_era_diff'] < 0).astype(int)  # dog has BP advantage

# 6. Offense asymmetry
mixed['off_gap_abs'] = mixed['off_diff'].abs()
mixed['off_adv_dog'] = (mixed['off_diff'] < 0).astype(int)  # dog has offensive advantage

# 7. Fav implied prob tiers (price-based)
mixed['fav_imp_tier'] = pd.cut(mixed['fav_implied'], bins=[0.5, 0.55, 0.60, 0.65, 1.0], 
                                labels=['slight', 'moderate', 'heavy'])

# Re-split after feature engineering
disc = mixed[mixed['season'].isin([2022, 2023])].copy()
val  = mixed[mixed['season'] == 2024].copy()
oos  = mixed[mixed['season'] == 2025].copy()

###############################################################################
# PHASE 4: Discovery tests
###############################################################################
print('\n=== PHASE 4: DISCOVERY TESTS (2022-2023) ===')

def calc_roi(df_sub, label=''):
    """Calculate dog WR, implied prob, residual, ROI at actual ML prices."""
    n = len(df_sub)
    if n < 20:
        return {'label': label, 'n': n, 'dog_wr': np.nan, 'implied_dog': np.nan, 
                'residual': np.nan, 'roi_pct': np.nan, 'status': 'TOO_SMALL'}
    
    dog_wins = (df_sub['fav_won'] == 0).sum()
    dog_wr = dog_wins / n
    implied_dog = (1 - df_sub['fav_implied']).mean()
    residual = dog_wr - implied_dog
    
    # ROI at actual dog ML prices
    # dog_ml_price is in American odds format
    profits = []
    for _, row in df_sub.iterrows():
        price = row['dog_ml_price']
        if row['fav_won'] == 0:  # dog won
            if price > 0:
                profit = price / 100
            else:
                profit = 100 / abs(price)
        else:
            profit = -1
        profits.append(profit)
    roi = np.mean(profits) * 100
    
    return {'label': label, 'n': n, 'dog_wr': dog_wr, 'implied_dog': implied_dog,
            'residual': residual, 'roi_pct': roi, 'status': 'OK'}

results = []

# Baseline: all MIXED dogs
r = calc_roi(disc, 'MIXED_all')
results.append(r)
print(f"MIXED all: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 1. Total environment
for env in ['low', 'mid', 'high']:
    sub = disc[disc['total_env'] == env]
    r = calc_roi(sub, f'total_{env}')
    results.append(r)
    if r['status'] == 'OK':
        print(f"  total_{env}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 2. Day vs night
for dn in mixed['day_night'].unique():
    if dn == 'unknown':
        continue
    sub = disc[disc['day_night'] == dn]
    r = calc_roi(sub, f'daynight_{dn}')
    results.append(r)
    if r['status'] == 'OK':
        print(f"  daynight_{dn}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 3. Home dog vs away dog
for hd in [0, 1]:
    label = 'dog_home' if hd == 1 else 'dog_away'
    sub = disc[disc['dog_is_home'] == hd]
    r = calc_roi(sub, label)
    results.append(r)
    if r['status'] == 'OK':
        print(f"  {label}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 4. SP gap tiers
for tier in ['tight', 'moderate', 'wide']:
    sub = disc[disc['sp_gap_tier'] == tier]
    r = calc_roi(sub, f'sp_gap_{tier}')
    results.append(r)
    if r['status'] == 'OK':
        print(f"  sp_gap_{tier}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 5. BP advantage for dog
for bp in [0, 1]:
    label = f'bp_adv_dog_{bp}'
    sub = disc[disc['bp_adv_dog'] == bp]
    r = calc_roi(sub, label)
    results.append(r)
    if r['status'] == 'OK':
        print(f"  {label}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 6. Offense advantage for dog
for oa in [0, 1]:
    label = f'off_adv_dog_{oa}'
    sub = disc[disc['off_adv_dog'] == oa]
    r = calc_roi(sub, label)
    results.append(r)
    if r['status'] == 'OK':
        print(f"  {label}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 7. Fav implied tier
for tier in ['slight', 'moderate', 'heavy']:
    sub = disc[disc['fav_imp_tier'] == tier]
    r = calc_roi(sub, f'fav_imp_{tier}')
    results.append(r)
    if r['status'] == 'OK':
        print(f"  fav_imp_{tier}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# 8. Compound overlays — most promising combinations
# dog_home + BP advantage
sub = disc[(disc['dog_is_home'] == 1) & (disc['bp_adv_dog'] == 1)]
r = calc_roi(sub, 'dog_home+bp_adv')
results.append(r)
if r['status'] == 'OK':
    print(f"  dog_home+bp_adv: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# dog_home + off advantage  
sub = disc[(disc['dog_is_home'] == 1) & (disc['off_adv_dog'] == 1)]
r = calc_roi(sub, 'dog_home+off_adv')
results.append(r)
if r['status'] == 'OK':
    print(f"  dog_home+off_adv: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# slight fav + dog_home
sub = disc[(disc['fav_imp_tier'] == 'slight') & (disc['dog_is_home'] == 1)]
r = calc_roi(sub, 'slight_fav+dog_home')
results.append(r)
if r['status'] == 'OK':
    print(f"  slight_fav+dog_home: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# sp_tight + dog_home
sub = disc[(disc['sp_gap_tier'] == 'tight') & (disc['dog_is_home'] == 1)]
r = calc_roi(sub, 'sp_tight+dog_home')
results.append(r)
if r['status'] == 'OK':
    print(f"  sp_tight+dog_home: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# bp_adv + off_adv (dog has both edges)
sub = disc[(disc['bp_adv_dog'] == 1) & (disc['off_adv_dog'] == 1)]
r = calc_roi(sub, 'bp_adv+off_adv')
results.append(r)
if r['status'] == 'OK':
    print(f"  bp_adv+off_adv: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# low total + dog_home
sub = disc[(disc['total_env'] == 'low') & (disc['dog_is_home'] == 1)]
r = calc_roi(sub, 'low_total+dog_home')
results.append(r)
if r['status'] == 'OK':
    print(f"  low_total+dog_home: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

# Triple: dog_home + bp_adv + off_adv
sub = disc[(disc['dog_is_home'] == 1) & (disc['bp_adv_dog'] == 1) & (disc['off_adv_dog'] == 1)]
r = calc_roi(sub, 'dog_home+bp_adv+off_adv')
results.append(r)
if r['status'] == 'OK':
    print(f"  dog_home+bp_adv+off_adv: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")

results_df = pd.DataFrame(results)
results_df.to_csv(f'{OUT}/discovery_results.csv', index=False)

###############################################################################
# PHASE 5: Forensic check on discovery positives
###############################################################################
print('\n=== PHASE 5: FORENSIC CHECKS ===')
positives = results_df[(results_df['status'] == 'OK') & (results_df['residual'] > 0.02) & (results_df['n'] >= 30)]
print(f'Discovery-positive overlays (resid > 2%, N >= 30): {len(positives)}')
print(positives[['label', 'n', 'dog_wr', 'implied_dog', 'residual', 'roi_pct']].to_string(index=False))

# Concentration check: are positives driven by a single team or season?
for _, pos in positives.iterrows():
    label = pos['label']
    # Reconstruct the filter
    if label == 'MIXED_all':
        sub = disc
    elif label == 'total_low':
        sub = disc[disc['total_env'] == 'low']
    elif label == 'dog_home':
        sub = disc[disc['dog_is_home'] == 1]
    elif label == 'dog_away':
        sub = disc[disc['dog_is_home'] == 0]
    elif label == 'bp_adv_dog_1':
        sub = disc[disc['bp_adv_dog'] == 1]
    elif label == 'off_adv_dog_1':
        sub = disc[disc['off_adv_dog'] == 1]
    elif label == 'dog_home+bp_adv':
        sub = disc[(disc['dog_is_home'] == 1) & (disc['bp_adv_dog'] == 1)]
    elif label == 'dog_home+off_adv':
        sub = disc[(disc['dog_is_home'] == 1) & (disc['off_adv_dog'] == 1)]
    elif label == 'slight_fav+dog_home':
        sub = disc[(disc['fav_imp_tier'] == 'slight') & (disc['dog_is_home'] == 1)]
    elif label == 'sp_tight+dog_home':
        sub = disc[(disc['sp_gap_tier'] == 'tight') & (disc['dog_is_home'] == 1)]
    elif label == 'bp_adv+off_adv':
        sub = disc[(disc['bp_adv_dog'] == 1) & (disc['off_adv_dog'] == 1)]
    elif label == 'dog_home+bp_adv+off_adv':
        sub = disc[(disc['dog_is_home'] == 1) & (disc['bp_adv_dog'] == 1) & (disc['off_adv_dog'] == 1)]
    else:
        continue
    
    # Season balance
    season_counts = sub.groupby('season')['fav_won'].agg(['count', 'mean'])
    # Team concentration
    dog_teams = sub['dog_team'].value_counts()
    top_team_pct = dog_teams.iloc[0] / len(sub) if len(dog_teams) > 0 else 0
    
    print(f'\n  {label}:')
    print(f'    Season balance: {season_counts.to_dict()}')
    print(f'    Top dog team: {dog_teams.index[0]} ({dog_teams.iloc[0]}/{len(sub)}, {top_team_pct:.1%})')
    if top_team_pct > 0.15:
        print(f'    WARNING: concentration risk (>{15}%)')

###############################################################################
# PHASE 6: Freeze survivors — overlays with resid > 2%, N >= 30
###############################################################################
survivors = positives.copy()
print(f'\n=== PHASE 6: FROZEN SURVIVORS ===')
print(f'Survivors for validation: {len(survivors)}')
print(survivors[['label', 'n', 'dog_wr', 'residual', 'roi_pct']].to_string(index=False))

###############################################################################
# PHASE 7: Validation (2024)
###############################################################################
print('\n=== PHASE 7: VALIDATION (2024) ===')

def get_subset(df, label):
    if label == 'MIXED_all':
        return df
    elif label == 'total_low':
        return df[df['total_env'] == 'low']
    elif label == 'total_mid':
        return df[df['total_env'] == 'mid']
    elif label == 'total_high':
        return df[df['total_env'] == 'high']
    elif label == 'dog_home':
        return df[df['dog_is_home'] == 1]
    elif label == 'dog_away':
        return df[df['dog_is_home'] == 0]
    elif label.startswith('bp_adv_dog_'):
        v = int(label[-1])
        return df[df['bp_adv_dog'] == v]
    elif label.startswith('off_adv_dog_'):
        v = int(label[-1])
        return df[df['off_adv_dog'] == v]
    elif label.startswith('fav_imp_'):
        tier = label.replace('fav_imp_', '')
        return df[df['fav_imp_tier'] == tier]
    elif label.startswith('sp_gap_'):
        tier = label.replace('sp_gap_', '')
        return df[df['sp_gap_tier'] == tier]
    elif label == 'dog_home+bp_adv':
        return df[(df['dog_is_home'] == 1) & (df['bp_adv_dog'] == 1)]
    elif label == 'dog_home+off_adv':
        return df[(df['dog_is_home'] == 1) & (df['off_adv_dog'] == 1)]
    elif label == 'slight_fav+dog_home':
        return df[(df['fav_imp_tier'] == 'slight') & (df['dog_is_home'] == 1)]
    elif label == 'sp_tight+dog_home':
        return df[(df['sp_gap_tier'] == 'tight') & (df['dog_is_home'] == 1)]
    elif label == 'bp_adv+off_adv':
        return df[(df['bp_adv_dog'] == 1) & (df['off_adv_dog'] == 1)]
    elif label == 'low_total+dog_home':
        return df[(df['total_env'] == 'low') & (df['dog_is_home'] == 1)]
    elif label == 'dog_home+bp_adv+off_adv':
        return df[(df['dog_is_home'] == 1) & (df['bp_adv_dog'] == 1) & (df['off_adv_dog'] == 1)]
    elif label.startswith('daynight_'):
        dn = label.replace('daynight_', '')
        return df[df['day_night'] == dn]
    else:
        return pd.DataFrame()

val_results = []
for _, row in survivors.iterrows():
    label = row['label']
    sub = get_subset(val, label)
    r = calc_roi(sub, label)
    r['disc_resid'] = row['residual']
    r['disc_roi'] = row['roi_pct']
    val_results.append(r)
    if r['status'] == 'OK':
        print(f"  {label}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}% (disc: {row['residual']:.4f}/{row['roi_pct']:.2f}%)")
    else:
        print(f"  {label}: N={r['n']} — {r['status']}")

val_df = pd.DataFrame(val_results)

# Validation gate: resid > 0 AND same sign as discovery
val_pass = val_df[(val_df['status'] == 'OK') & (val_df['residual'] > 0)]
print(f'\nValidation passers (resid > 0): {len(val_pass)}')

###############################################################################
# PHASE 8: OOS (2025)
###############################################################################
print('\n=== PHASE 8: OOS (2025) ===')

oos_results = []
for _, row in val_pass.iterrows() if len(val_pass) > 0 else survivors.iterrows():
    label = row['label']
    sub = get_subset(oos, label)
    r = calc_roi(sub, label)
    r['disc_resid'] = row.get('disc_resid', row.get('residual'))
    r['disc_roi'] = row.get('disc_roi', row.get('roi_pct'))
    if 'residual' in row and label in val_df['label'].values:
        vr = val_df[val_df['label'] == label].iloc[0]
        r['val_resid'] = vr['residual']
        r['val_roi'] = vr['roi_pct']
    oos_results.append(r)
    if r['status'] == 'OK':
        print(f"  {label}: N={r['n']}, dog_wr={r['dog_wr']:.4f}, impl={r['implied_dog']:.4f}, resid={r['residual']:.4f}, ROI={r['roi_pct']:.2f}%")
    else:
        print(f"  {label}: N={r['n']} — {r['status']}")

oos_df = pd.DataFrame(oos_results)

###############################################################################
# PHASE 9: Final verdicts
###############################################################################
print('\n=== PHASE 9: FINAL VERDICTS ===')

# Build final table with all periods
final_rows = []
for _, row in results_df[results_df['status'] == 'OK'].iterrows():
    label = row['label']
    fr = {
        'overlay': label,
        'disc_n': row['n'],
        'disc_dog_wr': row['dog_wr'],
        'disc_implied': row['implied_dog'],
        'disc_resid': row['residual'],
        'disc_roi': row['roi_pct'],
    }
    
    # Validation
    v_sub = get_subset(val, label)
    vr = calc_roi(v_sub, label)
    fr['val_n'] = vr['n']
    fr['val_dog_wr'] = vr.get('dog_wr', np.nan)
    fr['val_resid'] = vr.get('residual', np.nan)
    fr['val_roi'] = vr.get('roi_pct', np.nan)
    
    # OOS
    o_sub = get_subset(oos, label)
    osr = calc_roi(o_sub, label)
    fr['oos_n'] = osr['n']
    fr['oos_dog_wr'] = osr.get('dog_wr', np.nan)
    fr['oos_resid'] = osr.get('residual', np.nan)
    fr['oos_roi'] = osr.get('roi_pct', np.nan)
    
    # Verdict
    disc_pos = row['residual'] > 0.02 and row['n'] >= 30
    val_pos = not np.isnan(fr['val_resid']) and fr['val_resid'] > 0
    oos_pos = not np.isnan(fr['oos_resid']) and fr['oos_resid'] > 0
    
    if disc_pos and val_pos and oos_pos:
        fr['verdict'] = 'CONFIRMED'
    elif disc_pos and val_pos:
        fr['verdict'] = 'VAL_PASS_OOS_FAIL'
    elif disc_pos:
        fr['verdict'] = 'DISC_ONLY'
    else:
        fr['verdict'] = 'NO_SIGNAL'
    
    final_rows.append(fr)

final_df = pd.DataFrame(final_rows)
final_df = final_df.sort_values('disc_resid', ascending=False)
final_df.to_csv(f'{OUT}/MLB_SIDES_PHASE5_FINAL_TABLE.csv', index=False)

print('\nFINAL TABLE:')
cols_show = ['overlay', 'disc_n', 'disc_resid', 'disc_roi', 'val_n', 'val_resid', 'val_roi', 'oos_n', 'oos_resid', 'oos_roi', 'verdict']
print(final_df[cols_show].to_string(index=False))

confirmed = final_df[final_df['verdict'] == 'CONFIRMED']
print(f'\nCONFIRMED overlays: {len(confirmed)}')
if len(confirmed) > 0:
    print(confirmed[cols_show].to_string(index=False))

###############################################################################
# Write exec summary
###############################################################################
summary = f"""# MLB SIDES PHASE 5 — EXEC SUMMARY
## SP-LED Timing + MIXED Overlay Hunt

**Date**: 2026-04-12

---

## Branch A: SP-LED Open/Close Timing

**VERDICT: UNVERIFIABLE**

No opening moneyline prices exist in the historical data. The canonical odds
parquet () contains only closing
prices. Market snapshots () track totals 
open/noon/5pm/close but do not include moneyline open prices.

Cannot test whether SP-LED dogs offer better ROI at open vs close.

---

## Branch B: MIXED Overlay Hunt

### Setup
- MIXED games (reason_class == MIXED): all games where no single factor gap 
  exceeded the median threshold from Phase 4.
- Total MIXED: {len(mixed)} games
- Discovery (2022-2023): {len(disc)}
- Validation (2024): {len(val)}
- OOS (2025): {len(oos)}

### Baseline
- MIXED dog win rate discovery: {disc['fav_won'].eq(0).mean():.4f}
- MIXED dog implied prob discovery: {(1 - disc['fav_implied']).mean():.4f}

### Overlays Tested ({len(results_df[results_df['status']=='OK'])} total)
1. Closing total environment (low/mid/high)
2. Day vs night (from game_table)
3. Home dog vs away dog orientation
4. SP FIP gap tiers (tight/moderate/wide)
5. Bullpen ERA advantage for dog
6. Offense advantage for dog
7. Favorite implied probability tier
8. Compound overlays (dog_home+bp_adv, dog_home+off_adv, etc.)

### Discovery-Positive Overlays (resid > 2%, N >= 30)
{positives[['label', 'n', 'dog_wr', 'implied_dog', 'residual', 'roi_pct']].to_string(index=False) if len(positives) > 0 else 'NONE'}

### Validation Results
{val_df[val_df['status']=='OK'][['label', 'n', 'dog_wr', 'residual', 'roi_pct']].to_string(index=False) if len(val_df[val_df['status']=='OK']) > 0 else 'No survivors to validate'}

### OOS Results
{oos_df[oos_df['status']=='OK'][['label', 'n', 'dog_wr', 'residual', 'roi_pct']].to_string(index=False) if len(oos_df[oos_df['status']=='OK']) > 0 else 'No survivors reached OOS'}

### CONFIRMED Overlays (disc + val + OOS all positive)
{confirmed[cols_show].to_string(index=False) if len(confirmed) > 0 else 'NONE — no overlay survived all three periods'}

---

## Final Verdict

- **Branch A (SP-LED timing)**: UNVERIFIABLE — no opening ML prices available.
- **Branch B (MIXED overlays)**: {len(confirmed)} overlay(s) confirmed across all periods.
{chr(10).join(f'  - {r["overlay"]}: disc ROI {r["disc_roi"]:.1f}%, val ROI {r["val_roi"]:.1f}%, OOS ROI {r["oos_roi"]:.1f}%' for _, r in confirmed.iterrows()) if len(confirmed) > 0 else '  No actionable MIXED overlays survived forensic validation.'}

## Files
-  — full overlay results across all periods
-  — detailed discovery-period results
-  — this file
"""

with open(f'{OUT}/MLB_SIDES_PHASE5_EXEC_SUMMARY.md', 'w') as f:
    f.write(summary)

print(f'\nFiles written to {OUT}/')
print('DONE')
