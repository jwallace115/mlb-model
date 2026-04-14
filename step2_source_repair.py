import pandas as pd
import shutil

print("=== STEP 2: SOURCE REPAIR ===")

shutil.copy('mlb/data/hitter_game_logs.parquet', 'mlb/data/hitter_game_logs_pre_ha_fix_backup.parquet')
print("Backup created: mlb/data/hitter_game_logs_pre_ha_fix_backup.parquet")

hgl = pd.read_parquet('mlb/data/hitter_game_logs.parquet')
gt = pd.read_parquet('sim/data/game_table.parquet')

print(f"HGL rows: {len(hgl)}")
print(f"HGL columns: {list(hgl.columns)}")
print(f"GT columns: {list(gt.columns)}")
print(f"home_away value counts BEFORE: {hgl['home_away'].value_counts().to_dict()}")

TEAM_MAP = {
    'AZ': 'ARI', 'ARI': 'ARI',
    'CWS': 'CHW', 'CHW': 'CHW',
    'KC': 'KCR', 'KCR': 'KCR',
    'SD': 'SDP', 'SDP': 'SDP',
    'SF': 'SFG', 'SFG': 'SFG',
    'TB': 'TBR', 'TBR': 'TBR',
    'WSH': 'WSN', 'WSN': 'WSN',
    'ATH': 'OAK', 'OAK': 'OAK',
}

hgl['team_norm'] = hgl['team'].map(lambda x: TEAM_MAP.get(x, x))
gt['home_norm'] = gt['home_team'].map(lambda x: TEAM_MAP.get(x, x))
gt['away_norm'] = gt['away_team'].map(lambda x: TEAM_MAP.get(x, x))

# Check both-A games before
by_game_before = hgl.groupby('game_pk')['home_away'].apply(lambda x: set(x.tolist()))
both_a_before = (by_game_before.apply(lambda x: 'H' not in x and 'A' in x)).sum()
both_h_before = (by_game_before.apply(lambda x: 'H' in x and 'A' not in x)).sum()
both_ha_before = (by_game_before.apply(lambda x: 'H' in x and 'A' in x)).sum()
print(f"Before fix - both-A games: {both_a_before}, only-H games: {both_h_before}, both H+A: {both_ha_before}")

# Vectorized merge
hgl = hgl.merge(gt[['game_pk','home_norm','away_norm']].drop_duplicates(), on='game_pk', how='left')

unresolved_before = hgl['home_norm'].isna().sum()
print(f"Unresolved (no game_pk match): {unresolved_before}")

# Compute correct home_away
hgl['ha_fixed'] = 'UNRESOLVED'
hgl.loc[hgl['team_norm'] == hgl['home_norm'], 'ha_fixed'] = 'H'
hgl.loc[hgl['team_norm'] == hgl['away_norm'], 'ha_fixed'] = 'A'

unresolved_after = (hgl['ha_fixed'] == 'UNRESOLVED').sum()
print(f"UNRESOLVED after fix attempt: {unresolved_after} ({100*unresolved_after/len(hgl):.2f}%)")

changed = (hgl['home_away'] != hgl['ha_fixed']) & (hgl['ha_fixed'] != 'UNRESOLVED')
print(f"Rows changed: {changed.sum()}")

print(f"Before fix: H={( hgl['home_away']=='H').sum()}, A={(hgl['home_away']=='A').sum()}")
print(f"After fix:  H={(hgl['ha_fixed']=='H').sum()}, A={(hgl['ha_fixed']=='A').sum()}, UNRESOLVED={(hgl['ha_fixed']=='UNRESOLVED').sum()}")

# Apply fix
hgl['home_away'] = hgl['ha_fixed']

# Check both-A games after
by_game_after = hgl.groupby('game_pk')['home_away'].apply(lambda x: set(x.tolist()))
both_a_after = (by_game_after.apply(lambda x: 'H' not in x and 'A' in x)).sum()
both_h_after = (by_game_after.apply(lambda x: 'H' in x and 'A' not in x)).sum()
both_ha_after = (by_game_after.apply(lambda x: 'H' in x and 'A' in x)).sum()
print(f"After fix  - both-A games: {both_a_after}, only-H games: {both_h_after}, both H+A: {both_ha_after}")

# Drop temp columns and save
hgl = hgl.drop(columns=['team_norm', 'home_norm', 'away_norm', 'ha_fixed'])
hgl.to_parquet('mlb/data/hitter_game_logs.parquet', index=False)
print(f"Saved repaired hitter_game_logs.parquet. Total rows: {len(hgl)}")
print("=== SOURCE REPAIR COMPLETE ===")
