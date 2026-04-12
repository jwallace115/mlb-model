import pandas as pd
import numpy as np
import os, warnings
warnings.filterwarnings('ignore')

OUT = os.path.dirname(os.path.abspath(__file__))

###############################################################################
# PHASE 0: Lock inputs
###############################################################################
BASE = os.path.dirname(os.path.dirname(os.path.dirname(OUT)))
ct = pd.read_csv(os.path.join(BASE, 'research/recovery/mlb_sides_phase4_winpath/classification_table.csv'))
ct['date'] = pd.to_datetime(ct['date'])
ct.rename(columns={'reason': 'reason_class'}, inplace=True)
print("Classification table:", ct.shape)
print("Classes:", ct["reason_class"].value_counts().to_dict())

print("\n=== BRANCH A: SP-LED OPEN/CLOSE TIMING ===")
print("VERDICT: UNVERIFIABLE -- no opening ML prices in any data source.")

###############################################################################
# PHASE 3: MIXED overlay features
###############################################################################
print("\n=== BRANCH B: MIXED OVERLAY HUNT ===")
mixed = ct[ct['reason_class'] == 'MIXED'].copy()
print("MIXED total:", len(mixed))

# 1. Total environment
mixed['total_env'] = pd.cut(mixed['total_line'], bins=[0, 7.5, 8.5, 20], labels=['low', 'mid', 'high'])

# 2. Day vs night from game_table
gt = pd.read_parquet(os.path.join(BASE, 'sim/data/game_table.parquet'))
gt_time = gt[['game_pk', 'local_start_hour']].drop_duplicates('game_pk')
mixed = mixed.merge(gt_time, on='game_pk', how='left')
mixed['day_night'] = np.where(mixed['local_start_hour'] < 17, 'day', 'night')
print("Day/night:", mixed["day_night"].value_counts().to_dict())

# 3. Dog orientation
mixed['dog_is_home'] = (~mixed['fav_is_home'].astype(bool)).astype(int)

# 4. SP gap tiers
mixed['sp_gap_abs'] = mixed['sp_fip_diff'].abs()
mixed['sp_gap_tier'] = pd.qcut(mixed['sp_gap_abs'], q=3, labels=['tight', 'moderate', 'wide'])

# 5. BP advantage for dog
# bp_era_diff = fav_bp_era - dog_bp_era; positive means fav has worse BP
mixed['bp_adv_dog'] = (mixed['bp_era_diff'] > 0).astype(int)

# 6. Offense advantage for dog
# off_diff = fav_off - dog_off; negative means dog has better offense
mixed['off_adv_dog'] = (mixed['off_diff'] < 0).astype(int)

# 7. Fav implied tiers (range is 0.51-0.555)
mixed['fav_imp_tier'] = np.where(mixed['fav_implied'] < 0.53, 'slight',
                         np.where(mixed['fav_implied'] < 0.545, 'moderate', 'heavy'))

# 8. Rest differential from game_table
gt_rest = gt[['game_pk', 'home_rest_days', 'away_rest_days']].drop_duplicates('game_pk')
mixed = mixed.merge(gt_rest, on='game_pk', how='left')
mixed['dog_rest_adv'] = np.where(
    mixed['fav_is_home'].astype(bool),
    mixed['away_rest_days'] - mixed['home_rest_days'],
    mixed['home_rest_days'] - mixed['away_rest_days']
)
mixed['dog_rested'] = (mixed['dog_rest_adv'] > 0).astype(int)

# Splits
disc = mixed[mixed['season'].isin([2022, 2023])].copy()
val  = mixed[mixed['season'] == 2024].copy()
oos  = mixed[mixed['season'] == 2025].copy()
print("Discovery: %d, Validation: %d, OOS: %d" % (len(disc), len(val), len(oos)))

###############################################################################
# Helper
###############################################################################
def calc_roi(df_sub, label=''):
    n = len(df_sub)
    if n < 20:
        return {'label': label, 'n': n, 'dog_wr': np.nan, 'implied_dog': np.nan,
                'residual': np.nan, 'roi_pct': np.nan, 'status': 'TOO_SMALL'}
    dog_wins = (df_sub['fav_won'] == 0).sum()
    dog_wr = dog_wins / n
    implied_dog = (1 - df_sub['fav_implied']).mean()
    residual = dog_wr - implied_dog
    profits = []
    for _, row in df_sub.iterrows():
        price = row['dog_ml_price']
        if row['fav_won'] == 0:
            profit = price / 100 if price > 0 else 100 / abs(price)
        else:
            profit = -1
        profits.append(profit)
    roi = np.mean(profits) * 100
    return {'label': label, 'n': n, 'dog_wr': dog_wr, 'implied_dog': implied_dog,
            'residual': residual, 'roi_pct': roi, 'status': 'OK'}

def get_subset(df, label):
    filters = {
        'MIXED_all': lambda d: d,
        'total_low': lambda d: d[d['total_env'] == 'low'],
        'total_mid': lambda d: d[d['total_env'] == 'mid'],
        'total_high': lambda d: d[d['total_env'] == 'high'],
        'daynight_day': lambda d: d[d['day_night'] == 'day'],
        'daynight_night': lambda d: d[d['day_night'] == 'night'],
        'dog_home': lambda d: d[d['dog_is_home'] == 1],
        'dog_away': lambda d: d[d['dog_is_home'] == 0],
        'sp_gap_tight': lambda d: d[d['sp_gap_tier'] == 'tight'],
        'sp_gap_moderate': lambda d: d[d['sp_gap_tier'] == 'moderate'],
        'sp_gap_wide': lambda d: d[d['sp_gap_tier'] == 'wide'],
        'bp_adv_dog_0': lambda d: d[d['bp_adv_dog'] == 0],
        'bp_adv_dog_1': lambda d: d[d['bp_adv_dog'] == 1],
        'off_adv_dog_0': lambda d: d[d['off_adv_dog'] == 0],
        'off_adv_dog_1': lambda d: d[d['off_adv_dog'] == 1],
        'fav_imp_slight': lambda d: d[d['fav_imp_tier'] == 'slight'],
        'fav_imp_moderate': lambda d: d[d['fav_imp_tier'] == 'moderate'],
        'fav_imp_heavy': lambda d: d[d['fav_imp_tier'] == 'heavy'],
        'dog_rested_1': lambda d: d[d['dog_rested'] == 1],
        'dog_rested_0': lambda d: d[d['dog_rested'] == 0],
        'dog_home+bp_adv': lambda d: d[(d['dog_is_home'] == 1) & (d['bp_adv_dog'] == 1)],
        'dog_home+off_adv': lambda d: d[(d['dog_is_home'] == 1) & (d['off_adv_dog'] == 1)],
        'slight_fav+dog_home': lambda d: d[(d['fav_imp_tier'] == 'slight') & (d['dog_is_home'] == 1)],
        'sp_tight+dog_home': lambda d: d[(d['sp_gap_tier'] == 'tight') & (d['dog_is_home'] == 1)],
        'bp_adv+off_adv': lambda d: d[(d['bp_adv_dog'] == 1) & (d['off_adv_dog'] == 1)],
        'low_total+dog_home': lambda d: d[(d['total_env'] == 'low') & (d['dog_is_home'] == 1)],
        'dog_home+bp_adv+off_adv': lambda d: d[(d['dog_is_home'] == 1) & (d['bp_adv_dog'] == 1) & (d['off_adv_dog'] == 1)],
        'dog_home+rested': lambda d: d[(d['dog_is_home'] == 1) & (d['dog_rested'] == 1)],
        'day+dog_home': lambda d: d[(d['day_night'] == 'day') & (d['dog_is_home'] == 1)],
        'night+bp_adv': lambda d: d[(d['day_night'] == 'night') & (d['bp_adv_dog'] == 1)],
    }
    if label in filters:
        return filters[label](df)
    return pd.DataFrame()

###############################################################################
# PHASE 4: Discovery
###############################################################################
print("\n=== PHASE 4: DISCOVERY (2022-2023) ===")
test_labels = [
    'MIXED_all',
    'total_low', 'total_mid', 'total_high',
    'daynight_day', 'daynight_night',
    'dog_home', 'dog_away',
    'sp_gap_tight', 'sp_gap_moderate', 'sp_gap_wide',
    'bp_adv_dog_0', 'bp_adv_dog_1',
    'off_adv_dog_0', 'off_adv_dog_1',
    'fav_imp_slight', 'fav_imp_moderate', 'fav_imp_heavy',
    'dog_rested_1', 'dog_rested_0',
    'dog_home+bp_adv', 'dog_home+off_adv',
    'slight_fav+dog_home', 'sp_tight+dog_home',
    'bp_adv+off_adv', 'low_total+dog_home',
    'dog_home+bp_adv+off_adv', 'dog_home+rested',
    'day+dog_home', 'night+bp_adv',
]

results = []
for label in test_labels:
    sub = get_subset(disc, label)
    r = calc_roi(sub, label)
    results.append(r)
    if r['status'] == 'OK':
        marker = ' ***' if r['residual'] > 0.02 and r['n'] >= 30 else ''
        print("  %-30s N=%4d  dogWR=%.4f  impl=%.4f  resid=%+.4f  ROI=%+.2f%%%s" % (
            label, r['n'], r['dog_wr'], r['implied_dog'], r['residual'], r['roi_pct'], marker))

results_df = pd.DataFrame(results)
results_df.to_csv(os.path.join(OUT, 'discovery_results.csv'), index=False)

###############################################################################
# PHASE 5: Forensics on discovery positives
###############################################################################
print("\n=== PHASE 5: FORENSICS ===")
positives = results_df[(results_df['status'] == 'OK') & (results_df['residual'] > 0.02) & (results_df['n'] >= 30)]
print("Discovery-positive (resid > 2%%, N >= 30): %d" % len(positives))

forensic_notes = []
for _, pos in positives.iterrows():
    label = pos['label']
    sub = get_subset(disc, label)
    if len(sub) == 0:
        continue
    s_wr = sub.groupby('season').agg(n=('fav_won', 'count'), fav_wr=('fav_won', 'mean'))
    dog_teams = sub['dog_team'].value_counts()
    top_pct = dog_teams.iloc[0] / len(sub)
    print("\n  %s (N=%d):" % (label, len(sub)))
    for yr, row in s_wr.iterrows():
        print("    %d: N=%d, fav_wr=%.3f, dog_wr=%.3f" % (yr, row['n'], row['fav_wr'], 1-row['fav_wr']))
    print("    Top dog team: %s (%d/%d, %.1f%%)" % (dog_teams.index[0], dog_teams.iloc[0], len(sub), top_pct*100))
    note = 'CLEAN' if top_pct <= 0.15 else 'CONCENTRATION_RISK'
    # Check season stability
    if len(s_wr) >= 2:
        dog_wrs = [1 - r['fav_wr'] for _, r in s_wr.iterrows()]
        if max(dog_wrs) - min(dog_wrs) > 0.15:
            note = 'SEASON_INSTABILITY'
            print("    *** SEASON INSTABILITY (spread > 15pp) ***")
    if top_pct > 0.15:
        print("    *** CONCENTRATION WARNING ***")
    forensic_notes.append({'label': label, 'forensic': note})

###############################################################################
# PHASE 6: Freeze survivors
###############################################################################
survivors = positives.copy()
borderline = results_df[(results_df['status'] == 'OK') & (results_df['residual'] > 0) &
                         (results_df['residual'] <= 0.02) & (results_df['n'] >= 30)]
all_candidates = pd.concat([survivors, borderline]).drop_duplicates('label')
print("\n=== PHASE 6: FROZEN (%d strong, %d borderline) ===" % (len(survivors), len(borderline)))

###############################################################################
# PHASE 7: Validation (2024)
###############################################################################
print("\n=== PHASE 7: VALIDATION (2024) ===")
for _, row in all_candidates.iterrows():
    label = row['label']
    sub = get_subset(val, label)
    r = calc_roi(sub, label)
    if r['status'] == 'OK':
        d_resid = row['residual']
        marker = ' PASS' if r['residual'] > 0 else ' FAIL'
        print("  %-30s N=%4d  resid=%+.4f  ROI=%+.2f%%  (disc: %+.4f)%s" % (
            label, r['n'], r['residual'], r['roi_pct'], d_resid, marker))

###############################################################################
# PHASE 8: OOS (2025)
###############################################################################
print("\n=== PHASE 8: OOS (2025) ===")
for _, row in all_candidates.iterrows():
    label = row['label']
    sub = get_subset(oos, label)
    r = calc_roi(sub, label)
    if r['status'] == 'OK':
        marker = ' PASS' if r['residual'] > 0 else ' FAIL'
        print("  %-30s N=%4d  resid=%+.4f  ROI=%+.2f%%%s" % (
            label, r['n'], r['residual'], r['roi_pct'], marker))

###############################################################################
# PHASE 9: Final verdicts + output
###############################################################################
print("\n=== PHASE 9: FINAL TABLE ===")
final_rows = []
for label in test_labels:
    dr = results_df[results_df['label'] == label]
    if len(dr) == 0 or dr.iloc[0]['status'] != 'OK':
        continue
    dr = dr.iloc[0]

    vr = calc_roi(get_subset(val, label), label)
    osr = calc_roi(get_subset(oos, label), label)

    fr = {
        'overlay': label,
        'disc_n': int(dr['n']), 'disc_dog_wr': round(dr['dog_wr'], 4),
        'disc_resid': round(dr['residual'], 4), 'disc_roi': round(dr['roi_pct'], 2),
        'val_n': int(vr['n']) if vr['status'] == 'OK' else 0,
        'val_dog_wr': round(vr['dog_wr'], 4) if vr['status'] == 'OK' else None,
        'val_resid': round(vr['residual'], 4) if vr['status'] == 'OK' else None,
        'val_roi': round(vr['roi_pct'], 2) if vr['status'] == 'OK' else None,
        'oos_n': int(osr['n']) if osr['status'] == 'OK' else 0,
        'oos_dog_wr': round(osr['dog_wr'], 4) if osr['status'] == 'OK' else None,
        'oos_resid': round(osr['residual'], 4) if osr['status'] == 'OK' else None,
        'oos_roi': round(osr['roi_pct'], 2) if osr['status'] == 'OK' else None,
    }

    disc_pos = dr['residual'] > 0.02 and dr['n'] >= 30
    val_pos = fr['val_resid'] is not None and fr['val_resid'] > 0
    oos_pos = fr['oos_resid'] is not None and fr['oos_resid'] > 0

    if disc_pos and val_pos and oos_pos:
        fr['verdict'] = 'CONFIRMED'
    elif disc_pos and val_pos:
        fr['verdict'] = 'VAL_PASS_OOS_FAIL'
    elif disc_pos:
        fr['verdict'] = 'DISC_ONLY'
    elif dr['residual'] > 0 and val_pos and oos_pos:
        fr['verdict'] = 'WEAK_CONFIRMED'
    else:
        fr['verdict'] = 'NO_SIGNAL'

    final_rows.append(fr)

final_df = pd.DataFrame(final_rows).sort_values('disc_resid', ascending=False)
final_df.to_csv(os.path.join(OUT, 'MLB_SIDES_PHASE5_FINAL_TABLE.csv'), index=False)

cols = ['overlay', 'disc_n', 'disc_resid', 'disc_roi', 'val_n', 'val_resid', 'val_roi', 'oos_n', 'oos_resid', 'oos_roi', 'verdict']
print(final_df[cols].to_string(index=False))

confirmed = final_df[final_df['verdict'].isin(['CONFIRMED', 'WEAK_CONFIRMED'])]
n_conf = len(confirmed[confirmed['verdict'] == 'CONFIRMED'])
n_weak = len(confirmed[confirmed['verdict'] == 'WEAK_CONFIRMED'])
print("\nCONFIRMED: %d, WEAK_CONFIRMED: %d" % (n_conf, n_weak))

###############################################################################
# Write exec summary
###############################################################################
disc_base = results_df[results_df['label'] == 'MIXED_all'].iloc[0]

lines = []
lines.append('# MLB SIDES PHASE 5 -- EXEC SUMMARY')
lines.append('## SP-LED Timing + MIXED Overlay Hunt')
lines.append('')
lines.append('**Date**: 2026-04-12')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## Branch A: SP-LED Open/Close Timing')
lines.append('')
lines.append('**VERDICT: UNVERIFIABLE**')
lines.append('')
lines.append('No opening moneyline prices exist in the historical data.')
lines.append('The canonical odds parquet contains only closing prices.')
lines.append('Market snapshots track totals open/noon/5pm/close but no ML open prices.')
lines.append('Cannot test whether SP-LED dogs offer better ROI at open vs close.')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## Branch B: MIXED Overlay Hunt')
lines.append('')
lines.append('### Setup')
lines.append('- MIXED games total: %d' % len(mixed))
lines.append('- Discovery (2022-2023): %d' % len(disc))
lines.append('- Validation (2024): %d' % len(val))
lines.append('- OOS (2025): %d' % len(oos))
lines.append('')
lines.append('### Baseline MIXED Dog Performance')
lines.append('- Discovery dog WR: %.4f (implied: %.4f, resid: %+.4f)' % (
    disc_base['dog_wr'], disc_base['implied_dog'], disc_base['residual']))
lines.append('- Discovery ROI: %+.2f%%' % disc_base['roi_pct'])
lines.append('')
lines.append('### Overlays Tested (%d total)' % len(test_labels))
lines.append('Dimensions: total environment, day/night, dog orientation, SP gap,')
lines.append('BP advantage, offense advantage, fav implied tier, rest differential,')
lines.append('plus compound overlays.')
lines.append('')
lines.append('### Discovery-Positive (%d overlays, resid > 2%%, N >= 30)' % len(positives))
if len(positives) > 0:
    lines.append('```')
    lines.append(positives[['label', 'n', 'dog_wr', 'implied_dog', 'residual', 'roi_pct']].to_string(index=False))
    lines.append('```')
else:
    lines.append('NONE')
lines.append('')

lines.append('### Full Results Table (all periods)')
lines.append('```')
lines.append(final_df[cols].to_string(index=False))
lines.append('```')
lines.append('')

lines.append('### CONFIRMED Overlays (disc + val + OOS all positive residual)')
if len(confirmed) > 0:
    lines.append('```')
    lines.append(confirmed[cols].to_string(index=False))
    lines.append('```')
    for _, r in confirmed.iterrows():
        lines.append('- **%s**: disc ROI %+.1f%%, val ROI %+.1f%%, OOS ROI %+.1f%%' % (
            r['overlay'], r['disc_roi'], r['val_roi'], r['oos_roi']))
else:
    lines.append('NONE -- no overlay survived all three periods.')
lines.append('')

lines.append('---')
lines.append('')
lines.append('## Final Verdict')
lines.append('')
lines.append('- **Branch A (SP-LED timing)**: UNVERIFIABLE -- no opening ML prices available.')
lines.append('- **Branch B (MIXED overlays)**: %d CONFIRMED, %d WEAK_CONFIRMED.' % (n_conf, n_weak))
if n_conf == 0 and n_weak == 0:
    lines.append('  No actionable MIXED overlays survived forensic validation.')
lines.append('')
lines.append('## Files')
lines.append('- `MLB_SIDES_PHASE5_FINAL_TABLE.csv` -- full overlay results across all periods')
lines.append('- `discovery_results.csv` -- detailed discovery-period results')
lines.append('- `phase5_analysis.py` -- reproducible analysis script')
lines.append('- `MLB_SIDES_PHASE5_EXEC_SUMMARY.md` -- this file')

with open(os.path.join(OUT, 'MLB_SIDES_PHASE5_EXEC_SUMMARY.md'), 'w') as f:
    f.write('\n'.join(lines))

print("\nFiles written to %s/" % OUT)
print("DONE")
