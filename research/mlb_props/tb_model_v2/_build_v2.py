"""
TB Model v2 — Hitter × Pitcher Archetype Interaction Engine
RESEARCH ONLY
"""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
from sklearn.calibration import calibration_curve
import warnings, importlib, sys
warnings.filterwarnings('ignore')

OUT = 'research/mlb_props/tb_model_v2'

# ═══════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════
print("Loading data...")
hl = pd.read_parquet('mlb/data/hitter_game_logs.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
ps = pd.read_parquet('research/statcast_enrichment/pitcher_statcast_per_start.parquet')
prot = pd.read_parquet('research/lineup_protection_study/followup_iso_mechanism/iso_mechanism_dataset.parquet')
td = pd.read_parquet('research/statcast_enrichment/team_defense.parquet')
tb_raw = pd.read_parquet('research/mlb_props/tb_props/tb_props_dataset.parquet')

# Park factors
sys.path.insert(0, '/Users/jw115/mlb-model')
spec = importlib.util.spec_from_file_location("config", "/Users/jw115/mlb-model/config.py")
config = importlib.util.module_from_spec(spec)
config.__file__ = "/Users/jw115/mlb-model/config.py"
spec.loader.exec_module(config)
STADIUMS = getattr(config, 'STADIUMS', {})
PARK_FACTORS = {t: info.get('park_factor', 100) / 100.0 for t, info in STADIUMS.items()}

ABB_TO_CONFIG = {
    'LAA': 'LAA', 'HOU': 'HOU', 'OAK': 'OAK', 'ATH': 'OAK',
    'TOR': 'TOR', 'ATL': 'ATL', 'MIL': 'MIL', 'STL': 'STL',
    'CHC': 'CHC', 'ARI': 'ARI', 'AZ': 'ARI',
    'LAD': 'LAD', 'SF': 'SF', 'CLE': 'CLE',
    'SEA': 'SEA', 'MIA': 'MIA', 'NYM': 'NYM', 'WSH': 'WSH',
    'BAL': 'BAL', 'SD': 'SD', 'PHI': 'PHI', 'PIT': 'PIT',
    'TEX': 'TEX', 'TB': 'TBR', 'TBR': 'TBR',
    'BOS': 'BOS', 'CIN': 'CIN', 'COL': 'COL',
    'KC': 'KC', 'KCR': 'KC', 'DET': 'DET', 'MIN': 'MIN',
    'CWS': 'CWS', 'CHW': 'CWS', 'NYY': 'NYY'
}
TEAM_ABB_TO_NAME = {
    'LAA': 'Angels', 'HOU': 'Astros', 'OAK': 'Athletics', 'ATH': 'Athletics',
    'TOR': 'Blue Jays', 'ATL': 'Braves', 'MIL': 'Brewers', 'STL': 'Cardinals',
    'CHC': 'Cubs', 'ARI': 'Diamondbacks', 'AZ': 'Diamondbacks',
    'LAD': 'Dodgers', 'SF': 'Giants', 'CLE': 'Guardians',
    'SEA': 'Mariners', 'MIA': 'Marlins', 'NYM': 'Mets', 'WSH': 'Nationals',
    'BAL': 'Orioles', 'SD': 'Padres', 'PHI': 'Phillies', 'PIT': 'Pirates',
    'TEX': 'Rangers', 'TB': 'Rays', 'BOS': 'Red Sox', 'CIN': 'Reds',
    'COL': 'Rockies', 'KC': 'Royals', 'DET': 'Tigers', 'MIN': 'Twins',
    'CWS': 'White Sox', 'CHW': 'White Sox', 'NYY': 'Yankees'
}

print(f"  Hitter logs: {len(hl)}, Pitcher logs: {len(pl)}, Pitcher statcast: {len(ps)}")

# ═══════════════════════════════════════════════════════════
# STEP 1 — BUILD MODELING DATASET
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 1 — BUILD DATASET")
print("="*60)

# Compute outcomes
hl['total_bases'] = hl['singles'] + 2*hl['doubles'] + 3*hl['triples'] + 4*hl['home_runs']
hl['tb_zero_flag'] = (hl['total_bases'] == 0).astype(int)
hl['tb_over_1_5'] = (hl['total_bases'] >= 2).astype(int)
hl['tb_over_2_5'] = (hl['total_bases'] >= 3).astype(int)
hl['tb_tail_flag'] = (hl['total_bases'] >= 4).astype(int)
hl['xbh'] = hl['doubles'] + hl['triples'] + hl['home_runs']
hl['tb_ge2'] = hl['tb_over_1_5']
hl['tb_ge4'] = hl['tb_tail_flag']

# Identify opposing starter for each batter-game
starters = pl[pl['starter_flag'] == 1][['game_pk', 'player_id', 'team', 'opponent']].copy()
starters = starters.rename(columns={'player_id': 'pitcher_id', 'team': 'pitcher_team'})
# For a batter, the opposing pitcher's opponent == batter's team
batter_pitcher = starters.rename(columns={'opponent': 'batter_team', 'pitcher_team': 'opp_team'})

df = hl[['player_id', 'game_pk', 'game_date', 'season', 'player_name', 'team', 'opponent',
          'home_away', 'batting_order_position', 'batter_hand', 'opp_pitcher_hand',
          'total_bases', 'tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag',
          'plate_appearances', 'at_bats', 'hits', 'singles', 'doubles', 'triples',
          'home_runs', 'walks', 'strikeouts', 'iso', 'slg', 'obp', 'xbh']].copy()
df = df.rename(columns={'batting_order_position': 'batting_order_slot'})

# Join opposing pitcher
df = df.merge(batter_pitcher[['game_pk', 'batter_team', 'pitcher_id']],
              left_on=['game_pk', 'team'], right_on=['game_pk', 'batter_team'], how='left')
print(f"  Pitcher ID joined: {df['pitcher_id'].notna().sum()}/{len(df)}")

# Park factor via home team
game_home = hl[hl['home_away'] == 'H'].drop_duplicates('game_pk')[['game_pk', 'team']].rename(
    columns={'team': 'home_team_code'})
df = df.merge(game_home, on='game_pk', how='left')
df['park_factor'] = df['home_team_code'].map(lambda x: PARK_FACTORS.get(ABB_TO_CONFIG.get(x, x), 1.0))

print(f"  Dataset: {len(df)} rows, {df['season'].value_counts().to_dict()}")

# ═══════════════════════════════════════════════════════════
# STEP 2 — HITTER ARCHETYPES (rolling pregame features + KMeans)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 2 — HITTER ARCHETYPES")
print("="*60)

hl_sorted = hl.sort_values(['player_id', 'game_date', 'game_pk'])

def build_hitter_rolling(grp):
    g = grp.sort_values(['game_date', 'game_pk'])
    o = pd.DataFrame(index=g.index)
    o['player_id'] = g['player_id'].values
    o['game_pk'] = g['game_pk'].values
    r, mp = 20, 10
    # TB distribution shape
    o['h_zero_tb_rate'] = g['tb_zero_flag'].rolling(r, min_periods=mp).mean().shift(1).values
    o['h_pct_2plus'] = g['tb_ge2'].rolling(r, min_periods=mp).mean().shift(1).values
    o['h_pct_4plus'] = g['tb_ge4'].rolling(r, min_periods=mp).mean().shift(1).values
    o['h_tb_var'] = g['total_bases'].rolling(r, min_periods=mp).var().shift(1).values
    # Power / contact
    o['h_iso'] = g['iso'].rolling(r, min_periods=mp).mean().shift(1).values
    o['h_slg'] = g['slg'].rolling(r, min_periods=mp).mean().shift(1).values
    o['h_obp'] = g['obp'].rolling(r, min_periods=mp).mean().shift(1).values
    o['h_k_rate'] = (g['strikeouts'].rolling(r, min_periods=mp).sum() /
                     g['plate_appearances'].rolling(r, min_periods=mp).sum()).shift(1).values
    o['h_bb_rate'] = (g['walks'].rolling(r, min_periods=mp).sum() /
                      g['plate_appearances'].rolling(r, min_periods=mp).sum()).shift(1).values
    o['h_hr_rate'] = (g['home_runs'].rolling(r, min_periods=mp).sum() /
                      g['at_bats'].rolling(r, min_periods=mp).sum().replace(0, np.nan)).shift(1).values
    o['h_xbh_rate'] = (g['xbh'].rolling(r, min_periods=mp).sum() /
                        g['at_bats'].rolling(r, min_periods=mp).sum().replace(0, np.nan)).shift(1).values
    # Season-level
    o['h_zero_tb_season'] = g['tb_zero_flag'].expanding(min_periods=mp).mean().shift(1).values
    return o

print("  Building hitter rolling features...")
hitter_feats = hl_sorted.groupby('player_id', group_keys=False).apply(build_hitter_rolling)
df = df.merge(hitter_feats, on=['player_id', 'game_pk'], how='left')
print(f"  Hitter features coverage: {df['h_iso'].notna().sum()}/{len(df)}")

# Cluster hitters into archetypes
hitter_cluster_cols = ['h_iso', 'h_k_rate', 'h_zero_tb_rate', 'h_pct_2plus', 'h_hr_rate', 'h_xbh_rate']
hf_for_cluster = df[hitter_cluster_cols].dropna()
print(f"  Rows for hitter clustering: {len(hf_for_cluster)}")

scaler_h = StandardScaler()
X_h = scaler_h.fit_transform(hf_for_cluster)
km_h = KMeans(n_clusters=6, random_state=42, n_init=10)
hf_for_cluster['h_cluster'] = km_h.fit_predict(X_h)

# Merge clusters back
df = df.merge(hf_for_cluster[['h_cluster']], left_index=True, right_index=True, how='left')

# Name the clusters based on their profiles
cluster_profiles = df.dropna(subset=['h_cluster']).groupby('h_cluster')[hitter_cluster_cols + ['batting_order_slot']].mean()
print("\n  Hitter cluster profiles:")
print(cluster_profiles.round(3).to_string())

# Assign descriptive names based on profiles
# Sort by h_iso to assign names
profiles_sorted = cluster_profiles.sort_values('h_iso')
archetype_names_h = {}
for i, (cidx, row) in enumerate(profiles_sorted.iterrows()):
    if row['h_k_rate'] > 0.28 and row['h_iso'] > 0.15:
        name = 'high_K_power'
    elif row['h_iso'] > 0.18:
        name = 'elite_power'
    elif row['h_iso'] > 0.13 and row['h_k_rate'] < 0.22:
        name = 'contact_power'
    elif row['h_zero_tb_rate'] > 0.50:
        name = 'low_impact'
    elif row['h_k_rate'] > 0.28:
        name = 'high_K_weak'
    elif row['h_iso'] < 0.10:
        name = 'slap_contact'
    else:
        name = f'balanced_{i}'
    # Deduplicate
    if name in archetype_names_h.values():
        name = f'{name}_{cidx}'
    archetype_names_h[cidx] = name

df['hitter_archetype'] = df['h_cluster'].map(archetype_names_h)
print("\n  Hitter archetype counts:")
print(df['hitter_archetype'].value_counts())

# ═══════════════════════════════════════════════════════════
# STEP 3 — PITCHER ARCHETYPES
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 3 — PITCHER ARCHETYPES")
print("="*60)

# Merge pitcher statcast with pitcher game logs for GB/FB data
starters_full = pl[pl['starter_flag'] == 1].copy()
starters_full['gb_rate'] = starters_full['ground_outs'] / (
    starters_full['ground_outs'] + starters_full['fly_outs'] + starters_full['air_outs']).replace(0, np.nan)
starters_full['fb_rate'] = starters_full['fly_outs'] / (
    starters_full['ground_outs'] + starters_full['fly_outs'] + starters_full['air_outs']).replace(0, np.nan)
starters_full['k_rate_pitcher'] = starters_full['strikeouts'] / starters_full['batters_faced'].replace(0, np.nan)
starters_full['bb_rate_pitcher'] = starters_full['walks'] / starters_full['batters_faced'].replace(0, np.nan)
starters_full['hr_rate_pitcher'] = starters_full['home_runs_allowed'] / starters_full['batters_faced'].replace(0, np.nan)

# Merge statcast onto starters
ps_sub = ps[['pitcher_id', 'game_pk', 'hard_hit_rate', 'barrel_rate', 'whiff_rate',
              'zone_rate', 'chase_rate', 'avg_exit_velo', 'avg_launch_angle']].copy()
pitcher_data = starters_full.merge(ps_sub, left_on=['player_id', 'game_pk'],
                                    right_on=['pitcher_id', 'game_pk'], how='inner')
pitcher_data = pitcher_data.sort_values(['player_id', 'game_date', 'game_pk'])

print(f"  Pitcher data with statcast: {len(pitcher_data)}")

def build_pitcher_rolling(grp):
    g = grp.sort_values(['game_date', 'game_pk'])
    o = pd.DataFrame(index=g.index)
    o['pitcher_id_r'] = g['player_id'].values
    o['game_pk'] = g['game_pk'].values
    r, mp = 5, 3  # 5-start rolling for pitchers
    o['p_barrel_rate'] = g['barrel_rate'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_hard_hit_rate'] = g['hard_hit_rate'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_whiff_rate'] = g['whiff_rate'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_zone_rate'] = g['zone_rate'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_chase_rate'] = g['chase_rate'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_gb_rate'] = g['gb_rate'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_fb_rate'] = g['fb_rate'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_k_rate'] = g['k_rate_pitcher'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_bb_rate'] = g['bb_rate_pitcher'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_hr_rate'] = g['hr_rate_pitcher'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_avg_ev'] = g['avg_exit_velo'].rolling(r, min_periods=mp).mean().shift(1).values
    o['p_avg_la'] = g['avg_launch_angle'].rolling(r, min_periods=mp).mean().shift(1).values
    return o

print("  Building pitcher rolling features...")
pitcher_feats = pitcher_data.groupby('player_id', group_keys=False).apply(build_pitcher_rolling)

# Join to main dataset via pitcher_id + game_pk
pf_join = pitcher_feats.rename(columns={'pitcher_id_r': 'pitcher_id'})
df = df.merge(pf_join, on=['pitcher_id', 'game_pk'], how='left', suffixes=('', '_pf'))
print(f"  Pitcher features coverage: {df['p_barrel_rate'].notna().sum()}/{len(df)}")

# Cluster pitchers
pitcher_cluster_cols = ['p_barrel_rate', 'p_hard_hit_rate', 'p_whiff_rate', 'p_gb_rate',
                         'p_fb_rate', 'p_k_rate', 'p_hr_rate']
pf_for_cluster = df[pitcher_cluster_cols].dropna()
print(f"  Rows for pitcher clustering: {len(pf_for_cluster)}")

scaler_p = StandardScaler()
X_p = scaler_p.fit_transform(pf_for_cluster)
km_p = KMeans(n_clusters=6, random_state=42, n_init=10)
pf_for_cluster['p_cluster'] = km_p.fit_predict(X_p)

df = df.merge(pf_for_cluster[['p_cluster']], left_index=True, right_index=True, how='left')

cluster_profiles_p = df.dropna(subset=['p_cluster']).groupby('p_cluster')[pitcher_cluster_cols].mean()
print("\n  Pitcher cluster profiles:")
print(cluster_profiles_p.round(4).to_string())

# Name pitcher archetypes
profiles_sorted_p = cluster_profiles_p.sort_values('p_whiff_rate')
archetype_names_p = {}
for cidx, row in cluster_profiles_p.iterrows():
    if row['p_gb_rate'] > 0.42 and row['p_barrel_rate'] < 0.04:
        name = 'gb_suppressor'
    elif row['p_whiff_rate'] > 0.27 and row['p_k_rate'] > 0.25:
        name = 'power_arm'
    elif row['p_barrel_rate'] > 0.05 and row['p_fb_rate'] > 0.22:
        name = 'flyball_damage'
    elif row['p_hard_hit_rate'] < 0.34 and row['p_barrel_rate'] < 0.035:
        name = 'barrel_suppressor'
    elif row['p_whiff_rate'] < 0.22:
        name = 'contact_mgr'
    elif row['p_gb_rate'] > 0.38:
        name = 'gb_leaner'
    else:
        name = f'average_{cidx}'
    if name in archetype_names_p.values():
        name = f'{name}_{cidx}'
    archetype_names_p[cidx] = name

df['pitcher_archetype'] = df['p_cluster'].map(archetype_names_p)
print("\n  Pitcher archetype counts:")
print(df['pitcher_archetype'].value_counts())

# ═══════════════════════════════════════════════════════════
# ADD V1 FEATURES (protection, defense, season-level)
# ═══════════════════════════════════════════════════════════
print("\n  Adding v1 features...")

# Protection
prot_sub = prot[['game_pk', 'player_id', 'ondeck_iso_last20', 'ondeck_woba_proxy_last20',
                  'protector_type']].drop_duplicates(subset=['game_pk', 'player_id'])
df = df.merge(prot_sub, on=['game_pk', 'player_id'], how='left')

# Defense
td_sub = td[['season', 'team_name', 'defensive_runs_saved']].rename(
    columns={'team_name': 'opp_team_name'})
df['opp_team_name'] = df['opponent'].map(TEAM_ABB_TO_NAME)
df = df.merge(td_sub, on=['season', 'opp_team_name'], how='left')
df = df.rename(columns={'defensive_runs_saved': 'opp_drs'})

print(f"  Protection: {df['ondeck_iso_last20'].notna().sum()}/{len(df)}")
print(f"  Defense: {df['opp_drs'].notna().sum()}/{len(df)}")

# ═══════════════════════════════════════════════════════════
# SAVE DATASET
# ═══════════════════════════════════════════════════════════
df.to_parquet(f'{OUT}/tb_model_v2_dataset.parquet', index=False)
print(f"\n  Dataset saved: {len(df)} rows")

# Save archetype tables
arch_h = df.dropna(subset=['hitter_archetype']).groupby('hitter_archetype')[
    hitter_cluster_cols + ['batting_order_slot', 'tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag']
].agg(['mean', 'count']).reset_index()
arch_h.columns = ['_'.join(c).strip('_') for c in arch_h.columns]
arch_h.to_parquet(f'{OUT}/hitter_archetypes.parquet', index=False)

arch_p = df.dropna(subset=['pitcher_archetype']).groupby('pitcher_archetype')[
    pitcher_cluster_cols + ['tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag']
].agg(['mean', 'count']).reset_index()
arch_p.columns = ['_'.join(c).strip('_') for c in arch_p.columns]
arch_p.to_parquet(f'{OUT}/pitcher_archetypes.parquet', index=False)

# ═══════════════════════════════════════════════════════════
# STEP 4 — ARCHETYPE INTERACTION MATRIX
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 4 — INTERACTION MATRIX")
print("="*60)

both = df.dropna(subset=['hitter_archetype', 'pitcher_archetype'])
print(f"  Rows with both archetypes: {len(both)}")

interaction_rows = []
for (ha, pa), grp in both.groupby(['hitter_archetype', 'pitcher_archetype']):
    interaction_rows.append({
        'hitter_archetype': ha, 'pitcher_archetype': pa,
        'N': len(grp),
        'mean_tb': round(grp['total_bases'].mean(), 3),
        'p_zero': round(grp['tb_zero_flag'].mean(), 4),
        'p_over_1_5': round(grp['tb_over_1_5'].mean(), 4),
        'p_over_2_5': round(grp['tb_over_2_5'].mean(), 4),
        'p_tail': round(grp['tb_tail_flag'].mean(), 4),
    })

imatrix = pd.DataFrame(interaction_rows)
imatrix.to_parquet(f'{OUT}/archetype_interaction_matrix.parquet', index=False)

# Print the matrix (pivot)
print("\n  P(TB=0) Interaction Matrix:")
pivot_zero = imatrix.pivot(index='hitter_archetype', columns='pitcher_archetype', values='p_zero')
print(pivot_zero.round(3).to_string())

print("\n  P(TB>=2) Interaction Matrix:")
pivot_over = imatrix.pivot(index='hitter_archetype', columns='pitcher_archetype', values='p_over_1_5')
print(pivot_over.round(3).to_string())

print("\n  N per cell:")
pivot_n = imatrix.pivot(index='hitter_archetype', columns='pitcher_archetype', values='N')
print(pivot_n.to_string())

# Strongest Under cells
print("\n  Top 10 Under-leaning cells (highest P(TB=0)):")
top_under = imatrix.nlargest(10, 'p_zero')
print(top_under[['hitter_archetype', 'pitcher_archetype', 'N', 'p_zero', 'p_over_1_5']].to_string(index=False))

print("\n  Top 10 Over-leaning cells (highest P(TB>=2)):")
top_over = imatrix.nlargest(10, 'p_over_1_5')
print(top_over[['hitter_archetype', 'pitcher_archetype', 'N', 'p_zero', 'p_over_1_5']].to_string(index=False))

# ═══════════════════════════════════════════════════════════
# STEP 5 — TEST VALUE BEYOND V1
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 5 — VALUE BEYOND V1")
print("="*60)

# Encode archetypes
ha_cats = sorted(df['hitter_archetype'].dropna().unique())
pa_cats = sorted(df['pitcher_archetype'].dropna().unique())
df['ha_enc'] = df['hitter_archetype'].map({n: i for i, n in enumerate(ha_cats)})
df['pa_enc'] = df['pitcher_archetype'].map({n: i for i, n in enumerate(pa_cats)})

# Interaction feature: ha_enc * 10 + pa_enc (unique combo ID)
df['hxp_interaction'] = df['ha_enc'] * 10 + df['pa_enc']

# Feature groups
v1_baseline = ['h_zero_tb_rate', 'h_zero_tb_season', 'h_iso', 'h_slg', 'h_k_rate',
                'h_pct_2plus', 'h_pct_4plus', 'h_tb_var',
                'batting_order_slot', 'park_factor',
                'ondeck_iso_last20', 'ondeck_woba_proxy_last20', 'opp_drs',
                'p_barrel_rate', 'p_hard_hit_rate', 'p_whiff_rate']

# For archetype features, one-hot encode
for cat in ha_cats:
    df[f'ha_{cat}'] = (df['hitter_archetype'] == cat).astype(float)
for cat in pa_cats:
    df[f'pa_{cat}'] = (df['pitcher_archetype'] == cat).astype(float)

ha_dummies = [f'ha_{c}' for c in ha_cats]
pa_dummies = [f'pa_{c}' for c in pa_cats]

# Create interaction dummies (top 15 cells by volume)
top_cells = imatrix.nlargest(15, 'N')[['hitter_archetype', 'pitcher_archetype']].values
for ha, pa in top_cells:
    col = f'hxp_{ha}_x_{pa}'
    df[col] = ((df['hitter_archetype'] == ha) & (df['pitcher_archetype'] == pa)).astype(float)
hxp_dummies = [f'hxp_{ha}_x_{pa}' for ha, pa in top_cells]

# Define model configs
model_configs = {
    'A_baseline': v1_baseline,
    'B_hitter_arch': v1_baseline + ha_dummies,
    'C_pitcher_arch': v1_baseline + pa_dummies,
    'D_full_interaction': v1_baseline + ha_dummies + pa_dummies + hxp_dummies,
}

# Train/val split
min_feats = ['h_zero_tb_rate', 'h_iso', 'batting_order_slot']
df_model = df.dropna(subset=min_feats + ['tb_zero_flag']).copy()
train_df = df_model[df_model['season'].isin([2022, 2023, 2024])].copy()
val_df = df_model[df_model['season'] == 2025].copy()
print(f"\n  Train: {len(train_df)}, Val: {len(val_df)}")

targets = {'tb_zero': 'tb_zero_flag', 'tb_over_1_5': 'tb_over_1_5', 'tb_over_2_5': 'tb_over_2_5'}

comparison_rows = []
for target_name, target_col in targets.items():
    print(f"\n  === {target_name} ===")
    y_train = train_df[target_col].values
    y_val = val_df[target_col].values

    for config_name, feats in model_configs.items():
        medians = train_df[feats].median()
        X_tr = train_df[feats].fillna(medians).values
        X_va = val_df[feats].fillna(medians).values

        gbm = GradientBoostingClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            min_samples_leaf=50, subsample=0.8, max_features=0.7, random_state=42
        )
        gbm.fit(X_tr, y_train)
        val_probs = gbm.predict_proba(X_va)[:, 1]

        auc = roc_auc_score(y_val, val_probs)
        ll = log_loss(y_val, val_probs)
        brier = brier_score_loss(y_val, val_probs)

        comparison_rows.append({
            'target': target_name, 'model': config_name,
            'n_features': len(feats),
            'val_auc': round(auc, 4), 'val_logloss': round(ll, 4), 'val_brier': round(brier, 4)
        })
        print(f"    {config_name:<25s}: AUC={auc:.4f} LL={ll:.4f} Brier={brier:.4f} ({len(feats)} feats)")

        # Save D model predictions for backtest
        if config_name == 'D_full_interaction':
            val_df[f'pred_{target_name}'] = val_probs
            # Also store A baseline for comparison
        if config_name == 'A_baseline':
            val_df[f'pred_{target_name}_v1'] = val_probs

comparison_df = pd.DataFrame(comparison_rows)

# ═══════════════════════════════════════════════════════════
# STEP 6 — TRAIN FINAL V2 MODEL
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 6 — FINAL V2 MODEL")
print("="*60)

v2_features = v1_baseline + ha_dummies + pa_dummies + hxp_dummies
medians_v2 = train_df[v2_features].median()
X_train_v2 = train_df[v2_features].fillna(medians_v2).values
X_val_v2 = val_df[v2_features].fillna(medians_v2).values

final_models = {}
final_importance = []
for target_name, target_col in targets.items():
    y_tr = train_df[target_col].values
    y_va = val_df[target_col].values

    gbm = GradientBoostingClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        min_samples_leaf=50, subsample=0.8, max_features=0.7, random_state=42
    )
    gbm.fit(X_train_v2, y_tr)
    val_probs = gbm.predict_proba(X_val_v2)[:, 1]
    final_models[target_name] = gbm
    val_df[f'v2_{target_name}'] = val_probs

    auc = roc_auc_score(y_va, val_probs)
    print(f"  {target_name}: AUC={auc:.4f}")

    # Feature importance
    imp = gbm.feature_importances_
    for rank, idx in enumerate(np.argsort(imp)[::-1][:15]):
        final_importance.append({
            'model': target_name, 'rank': rank + 1,
            'feature': v2_features[idx], 'importance': round(imp[idx], 4)
        })

importance_df = pd.DataFrame(final_importance)

# ═══════════════════════════════════════════════════════════
# STEP 7 — BACKTEST MARKET EDGE
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 7 — BACKTEST")
print("="*60)

# Join market data
name_to_id = hl.drop_duplicates('player_name')[['player_name', 'player_id']]
tb_raw2 = tb_raw.merge(name_to_id.rename(columns={'player_name': 'player_name_out'}),
                       on='player_name_out', how='left')

# Merge v2 predictions to market records
v2_preds = val_df[['player_id', 'game_pk', 'v2_tb_zero', 'v2_tb_over_1_5', 'v2_tb_over_2_5',
                     'pred_tb_zero_v1', 'pred_tb_over_1_5_v1', 'pred_tb_over_2_5_v1']].copy()
v2_preds['v2_p_under_1_5'] = 1 - v2_preds['v2_tb_over_1_5']
v2_preds['v2_p_under_2_5'] = 1 - v2_preds['v2_tb_over_2_5']
v2_preds['v1_p_under_1_5'] = 1 - v2_preds['pred_tb_over_1_5_v1']
v2_preds['v1_p_under_2_5'] = 1 - v2_preds['pred_tb_over_2_5_v1']

mkt = tb_raw2[['player_id', 'game_pk_out', 'line', 'book', 'implied_over', 'under_odds',
                'actual_tb', 'under_pnl']].rename(columns={'game_pk_out': 'game_pk'})
joined = mkt.merge(v2_preds, on=['player_id', 'game_pk'], how='inner')

print(f"  Joined market records: {len(joined)}")

backtest_rows = []
for line_val, p_col_v2, p_col_v1 in [
    (1.5, 'v2_p_under_1_5', 'v1_p_under_1_5'),
    (2.5, 'v2_p_under_2_5', 'v1_p_under_2_5')
]:
    sub = joined[(joined['line'] == line_val) & joined[p_col_v2].notna()].copy()
    sub['mkt_p_under'] = 1 - sub['implied_over']
    sub['v2_edge'] = sub[p_col_v2] - sub['mkt_p_under']
    sub['v1_edge'] = sub[p_col_v1] - sub['mkt_p_under']
    sub['won'] = (sub['actual_tb'] < (2 if line_val == 1.5 else 3)).astype(int)

    print(f"\n  === Under {line_val} ===")
    print(f"  N: {len(sub)}, with under_odds: {sub['under_odds'].notna().sum()}")
    print(f"  v2 mean edge: {sub['v2_edge'].mean():+.4f}")
    print(f"  v1 mean edge: {sub['v1_edge'].mean():+.4f}")
    print(f"  Win rate: {sub['won'].mean():.4f}")

    # By book
    for book, grp in sub.groupby('book'):
        if len(grp) < 50:
            continue
        wr = grp['won'].mean()
        v2e = grp['v2_edge'].mean()
        v1e = grp['v1_edge'].mean()
        with_odds = grp.dropna(subset=['under_odds'])
        roi = with_odds['under_pnl'].mean() if len(with_odds) > 0 else np.nan
        roi_str = f"{roi:+.4f}" if not np.isnan(roi) else "N/A"
        print(f"    {book:<16s}: N={len(grp):5d} win={wr:.3f} v2_edge={v2e:+.4f} v1_edge={v1e:+.4f} ROI={roi_str}")

        backtest_rows.append({
            'line': line_val, 'book': book, 'N': len(grp),
            'win_rate': round(wr, 4),
            'v2_edge': round(v2e, 4), 'v1_edge': round(v1e, 4),
            'roi': round(roi, 4) if not np.isnan(roi) else None,
        })

    # V2 vs V1 edge bucket comparison
    print(f"\n  V2 vs V1 edge buckets (Under {line_val}, all books):")
    for thresh in [0.03, 0.05, 0.07, 0.10]:
        v2_c = sub[sub['v2_edge'] >= thresh]
        v1_c = sub[sub['v1_edge'] >= thresh]
        v2_wr = v2_c['won'].mean() if len(v2_c) > 0 else np.nan
        v1_wr = v1_c['won'].mean() if len(v1_c) > 0 else np.nan
        print(f"    edge>={thresh}: v2 N={len(v2_c)} win={v2_wr:.3f if not np.isnan(v2_wr) else 0:.3f}  |  "
              f"v1 N={len(v1_c)} win={v1_wr:.3f if not np.isnan(v1_wr) else 0:.3f}")

backtest_df = pd.DataFrame(backtest_rows)

# ═══════════════════════════════════════════════════════════
# SAVE OUTPUT FILES
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("SAVING FILES")
print("="*60)

val_out = val_df[['player_id', 'game_pk', 'game_date', 'season', 'player_name',
                   'team', 'opponent', 'batting_order_slot', 'total_bases',
                   'tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag',
                   'hitter_archetype', 'pitcher_archetype',
                   'v2_tb_zero', 'v2_tb_over_1_5', 'v2_tb_over_2_5',
                   'v2_p_under_1_5', 'v2_p_under_2_5',
                   'pred_tb_zero_v1', 'pred_tb_over_1_5_v1', 'pred_tb_over_2_5_v1',
                   'v1_p_under_1_5', 'v1_p_under_2_5']].copy()
val_out.to_parquet(f'{OUT}/model_predictions_v2.parquet', index=False)
backtest_df.to_parquet(f'{OUT}/model_backtest_v2.parquet', index=False)
importance_df.to_parquet(f'{OUT}/feature_importance_v2.parquet', index=False)
comparison_df.to_parquet(f'{OUT}/model_comparison.parquet', index=False)

# ═══════════════════════════════════════════════════════════
# PRINT SUMMARY
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)

print("\n  Model Comparison (AUC on 2025 validation):")
for target in ['tb_zero', 'tb_over_1_5', 'tb_over_2_5']:
    sub = comparison_df[comparison_df['target'] == target]
    print(f"\n  {target}:")
    for _, row in sub.iterrows():
        print(f"    {row['model']:<25s}: AUC={row['val_auc']:.4f}")

print("\n  Top 15 Feature Importance (v2 full model):")
for model_name in ['tb_zero', 'tb_over_1_5', 'tb_over_2_5']:
    sub = importance_df[importance_df['model'] == model_name]
    print(f"\n  {model_name}:")
    for _, row in sub.iterrows():
        print(f"    {row['rank']:2d}. {row['feature']:<35s} {row['importance']:.4f}")

print("\nDone.")
