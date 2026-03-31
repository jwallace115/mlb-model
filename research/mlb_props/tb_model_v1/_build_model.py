"""
TB Distribution Model v1 — RESEARCH ONLY
Predicts P(TB=0), P(TB>=2), P(TB>=3) using distribution-shape signals.
Train: 2022-2024, Validate: 2025 (with market odds overlay)
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
from sklearn.calibration import calibration_curve
import warnings
warnings.filterwarnings('ignore')
import importlib, sys

OUT = 'research/mlb_props/tb_model_v1'

# ═══════════════════════════════════════════════════════════
# LOAD ALL DATA
# ═══════════════════════════════════════════════════════════
print("Loading datasets...")
hl = pd.read_parquet('mlb/data/hitter_game_logs.parquet')
tb = pd.read_parquet('research/mlb_props/tb_props/tb_props_dataset.parquet')
prot = pd.read_parquet('research/lineup_protection_study/followup_iso_mechanism/iso_mechanism_dataset.parquet')
ps = pd.read_parquet('research/statcast_enrichment/pitcher_statcast_per_start.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
td = pd.read_parquet('research/statcast_enrichment/team_defense.parquet')

# Park factors
sys.path.insert(0, '/Users/jw115/mlb-model')
spec = importlib.util.spec_from_file_location("config", "/Users/jw115/mlb-model/config.py")
config = importlib.util.module_from_spec(spec)
config.__file__ = "/Users/jw115/mlb-model/config.py"
spec.loader.exec_module(config)
STADIUMS = getattr(config, 'STADIUMS', {})
PARK_FACTORS = {t: info.get('park_factor', 100) / 100.0 for t, info in STADIUMS.items()}

# Team abbreviation mapping for defense
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

# Stadium team code mapping (config uses franchise codes like TBR, config keys)
STADIUM_TO_TEAM = {}
for code in STADIUMS:
    STADIUM_TO_TEAM[code] = code

print(f"Hitter logs: {len(hl)}, TB props: {len(tb)}, Protection: {len(prot)}")

# ═══════════════════════════════════════════════════════════
# STEP 1 — BUILD BASE DATASET FROM HITTER GAME LOGS
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 1 — DATASET BUILD")
print("="*60)

# Compute total bases
hl['total_bases'] = hl['singles'] + 2*hl['doubles'] + 3*hl['triples'] + 4*hl['home_runs']
hl['tb_zero_flag'] = (hl['total_bases'] == 0).astype(int)
hl['tb_over_1_5'] = (hl['total_bases'] >= 2).astype(int)
hl['tb_over_2_5'] = (hl['total_bases'] >= 3).astype(int)
hl['tb_tail_flag'] = (hl['total_bases'] >= 4).astype(int)
hl['xbh'] = hl['doubles'] + hl['triples'] + hl['home_runs']
hl['tb_ge2'] = hl['tb_over_1_5']
hl['tb_ge4'] = hl['tb_tail_flag']

print(f"Base dataset: {len(hl)} batter-games")
print(f"Baseline rates:")
for c in ['tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag']:
    print(f"  {c}: {hl[c].mean():.4f}")

# ═══════════════════════════════════════════════════════════
# STEP 2 — FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 2 — FEATURE ENGINEERING")
print("="*60)

hl = hl.sort_values(['player_id', 'game_date', 'game_pk'])

# --- GROUP A: Zero-TB Propensity ---
print("  Building Group A: Zero-TB propensity features...")

def build_hitter_features(grp):
    grp = grp.sort_values(['game_date', 'game_pk'])
    idx = grp.index
    out = pd.DataFrame(index=idx)
    out['player_id'] = grp['player_id'].values
    out['game_pk'] = grp['game_pk'].values
    out['game_date'] = grp['game_date'].values
    out['season'] = grp['season'].values

    # Rolling windows with shift(1) for pregame
    for col, src in [
        ('zero_tb_rate_last10', 'tb_zero_flag'),
        ('zero_tb_rate_last20', 'tb_zero_flag'),
        ('pct_2plus_tb_last20', 'tb_ge2'),
        ('pct_4plus_tb_last20', 'tb_ge4'),
    ]:
        win = 10 if 'last10' in col else 20
        mp = 5 if win == 10 else 10
        out[col] = grp[src].rolling(win, min_periods=mp).mean().shift(1).values

    # TB variance last 20
    out['tb_variance_last20'] = grp['total_bases'].rolling(20, min_periods=10).var().shift(1).values

    # Zero-TB rate season (expanding with shift)
    out['zero_tb_rate_season'] = grp['tb_zero_flag'].expanding(min_periods=10).mean().shift(1).values

    # GROUP E: Baseline controls
    out['batter_iso_last20'] = grp['iso'].rolling(20, min_periods=10).mean().shift(1).values
    out['batter_slg_last20'] = grp['slg'].rolling(20, min_periods=10).mean().shift(1).values
    out['batter_k_rate_last20'] = (
        grp['strikeouts'].rolling(20, min_periods=10).sum() /
        grp['plate_appearances'].rolling(20, min_periods=10).sum()
    ).shift(1).values
    out['batter_obp_last20'] = grp['obp'].rolling(20, min_periods=10).mean().shift(1).values

    return out

hitter_feats = hl.groupby('player_id', group_keys=False).apply(build_hitter_features)
print(f"  Hitter features: {hitter_feats['zero_tb_rate_last20'].notna().sum()}/{len(hitter_feats)} non-null")

# Merge back to main
df = hl[['player_id', 'game_pk', 'game_date', 'season', 'player_name', 'team', 'opponent',
          'home_away', 'batting_order_position', 'total_bases',
          'tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag']].copy()
df = df.rename(columns={'batting_order_position': 'batting_order_slot'})

df = df.merge(hitter_feats[['player_id', 'game_pk',
    'zero_tb_rate_last10', 'zero_tb_rate_last20', 'zero_tb_rate_season',
    'pct_2plus_tb_last20', 'pct_4plus_tb_last20', 'tb_variance_last20',
    'batter_iso_last20', 'batter_slg_last20', 'batter_k_rate_last20', 'batter_obp_last20']],
    on=['player_id', 'game_pk'], how='left')

# --- GROUP B: Protection Interaction ---
print("  Building Group B: Protection features...")
prot_cols = ['game_pk', 'player_id', 'ondeck_iso_last20', 'ondeck_woba_proxy_last20',
             'protector_type']
prot_sub = prot[prot_cols].drop_duplicates(subset=['game_pk', 'player_id'])
df = df.merge(prot_sub, on=['game_pk', 'player_id'], how='left')

# Create flags
df['weak_protection_flag'] = (df['ondeck_iso_last20'] < 0.080).astype(float)
df.loc[df['ondeck_iso_last20'].isna(), 'weak_protection_flag'] = np.nan

df['high_iso_flag'] = (df['batter_iso_last20'] > 0.180).astype(float)
df.loc[df['batter_iso_last20'].isna(), 'high_iso_flag'] = np.nan

df['high_iso_x_weak_protection'] = df['high_iso_flag'] * df['weak_protection_flag']

# Encode protector_type
prot_map = {'weak': 0, 'contact_only': 1, 'average': 2, 'high_k_power': 3, 'elite_damage': 4}
df['protector_type_enc'] = df['protector_type'].map(prot_map)

print(f"  Protection joined: {df['ondeck_iso_last20'].notna().sum()}/{len(df)}")

# --- GROUP C: Defense ---
print("  Building Group C: Defense features...")
df['opp_team_name'] = df['opponent'].map(TEAM_ABB_TO_NAME)
td_sub = td[['season', 'team_name', 'defensive_runs_saved']].rename(
    columns={'team_name': 'opp_team_name'})
df = df.merge(td_sub, on=['season', 'opp_team_name'], how='left')
df = df.rename(columns={'defensive_runs_saved': 'opp_drs'})
print(f"  Defense joined: {df['opp_drs'].notna().sum()}/{len(df)}")

# --- GROUP D: Pitcher XBH Suppression ---
print("  Building Group D: Pitcher features...")

# Identify opposing starter for each batter
starters = pl[pl['starter_flag'] == 1][['game_pk', 'player_id', 'team', 'opponent', 'innings_pitched', 'game_date']].copy()
starters = starters.rename(columns={'player_id': 'pitcher_id', 'team': 'pitcher_team',
                                     'opponent': 'pitcher_opponent'})

# Merge statcast onto starters
ps_sub = ps[['pitcher_id', 'game_pk', 'hard_hit_rate', 'barrel_rate', 'whiff_rate', 'avg_exit_velo']].copy()
starter_stat = starters.merge(ps_sub, on=['pitcher_id', 'game_pk'], how='inner')
starter_stat = starter_stat.sort_values(['pitcher_id', 'game_date', 'game_pk'])

# Build rolling pitcher features (last 5 starts, shift 1)
def build_pitcher_features(grp):
    grp = grp.sort_values(['game_date', 'game_pk'])
    out = pd.DataFrame(index=grp.index)
    out['pitcher_id'] = grp['pitcher_id'].values
    out['game_pk'] = grp['game_pk'].values
    out['pitcher_opponent'] = grp['pitcher_opponent'].values
    out['pitcher_ip'] = grp['innings_pitched'].values

    for col in ['hard_hit_rate', 'barrel_rate', 'whiff_rate', 'avg_exit_velo']:
        out[f'p_{col}_last5'] = grp[col].rolling(5, min_periods=3).mean().shift(1).values

    out['p_avg_ip_last5'] = grp['innings_pitched'].rolling(5, min_periods=3).mean().shift(1).values
    return out

pitcher_feats = starter_stat.groupby('pitcher_id', group_keys=False).apply(build_pitcher_features)

# Join to batter dataset: opposing pitcher = pitcher whose pitcher_opponent == batter's team
pitcher_for_join = pitcher_feats[['game_pk', 'pitcher_opponent',
    'p_hard_hit_rate_last5', 'p_barrel_rate_last5', 'p_whiff_rate_last5',
    'p_avg_exit_velo_last5', 'p_avg_ip_last5']].copy()

df = df.merge(pitcher_for_join,
              left_on=['game_pk', 'team'],
              right_on=['game_pk', 'pitcher_opponent'],
              how='left')
print(f"  Pitcher features joined: {df['p_barrel_rate_last5'].notna().sum()}/{len(df)}")

# --- GROUP E: Park factor ---
print("  Adding park factor...")
# Map home team to park factor
# Need home_team for each game
game_home = hl.drop_duplicates('game_pk')[['game_pk', 'team', 'home_away']].copy()
game_home = game_home[game_home['home_away'] == 'H'][['game_pk', 'team']].rename(columns={'team': 'home_team_code'})
df = df.merge(game_home, on='game_pk', how='left')

# Map team codes to park factor codes (config uses franchise codes)
TEAM_TO_PF = {}
for code, pf_val in PARK_FACTORS.items():
    TEAM_TO_PF[code] = pf_val
# Also map common abbreviations
ABB_TO_CONFIG = {
    'LAA': 'LAA', 'HOU': 'HOU', 'OAK': 'OAK', 'ATH': 'OAK',
    'TOR': 'TOR', 'ATL': 'ATL', 'MIL': 'MIL', 'STL': 'STL',
    'CHC': 'CHC', 'ARI': 'ARI', 'AZ': 'ARI',
    'LAD': 'LAD', 'SF': 'SF', 'CLE': 'CLE',
    'SEA': 'SEA', 'MIA': 'MIA', 'NYM': 'NYM', 'WSH': 'WSH',
    'BAL': 'BAL', 'SD': 'SD', 'PHI': 'PHI', 'PIT': 'PIT',
    'TEX': 'TEX', 'TB': 'TBR', 'TBR': 'TBR',
    'BOS': 'BOS', 'CIN': 'CIN',
    'COL': 'COL', 'KC': 'KC', 'KCR': 'KC',
    'DET': 'DET', 'MIN': 'MIN',
    'CWS': 'CWS', 'CHW': 'CWS',
    'NYY': 'NYY'
}

def get_park_factor(team_code):
    cfg_code = ABB_TO_CONFIG.get(team_code, team_code)
    return PARK_FACTORS.get(cfg_code, 1.0)

df['park_factor'] = df['home_team_code'].map(get_park_factor)
print(f"  Park factor coverage: {df['park_factor'].notna().sum()}/{len(df)}")

# ═══════════════════════════════════════════════════════════
# MERGE MARKET DATA (TB PROPS) FOR 2025 VALIDATION
# ═══════════════════════════════════════════════════════════
print("\n  Merging TB prop market data for 2025...")

# TB props: deduplicate to one row per batter-game-line (use best book priority)
# We want one market line per batter-game for each line value
# Priority: draftkings > fanduel > betonlineag > betmgm
book_priority = {'draftkings': 0, 'fanduel': 1, 'betonlineag': 2, 'betmgm': 3,
                 'bovada': 4, 'fanatics': 5, 'williamhill_us': 6, 'mybookieag': 7, 'betrivers': 8}
tb['book_rank'] = tb['book'].map(book_priority).fillna(9)

# Get name-to-player_id mapping
name_to_id = hl.drop_duplicates('player_name')[['player_name', 'player_id']]
tb2 = tb.merge(name_to_id.rename(columns={'player_name': 'player_name_out'}),
               on='player_name_out', how='left')

# For each line, get best book per batter-game
market_data = []
for line_val in [0.5, 1.5, 2.5]:
    sub = tb2[tb2['line'] == line_val].sort_values('book_rank')
    sub = sub.drop_duplicates(subset=['player_id', 'game_pk_out'], keep='first')
    sub = sub[['player_id', 'game_pk_out', 'line', 'over_odds', 'under_odds',
               'implied_over', 'implied_under', 'book', 'over_pnl', 'under_pnl']].copy()
    sub = sub.rename(columns={'game_pk_out': 'game_pk'})
    market_data.append(sub)

market_all = pd.concat(market_data, ignore_index=True)
# Pivot to wide format: one row per batter-game with columns for each line
for line_val in [0.5, 1.5, 2.5]:
    suffix = str(line_val).replace('.', '_')
    sub = market_all[market_all['line'] == line_val].copy()
    sub = sub.rename(columns={
        'over_odds': f'over_odds_{suffix}',
        'under_odds': f'under_odds_{suffix}',
        'implied_over': f'implied_over_{suffix}',
        'implied_under': f'implied_under_{suffix}',
        'book': f'book_{suffix}',
        'over_pnl': f'over_pnl_{suffix}',
        'under_pnl': f'under_pnl_{suffix}',
    })
    sub = sub.drop(columns=['line'])
    df = df.merge(sub, on=['player_id', 'game_pk'], how='left')

print(f"  Market data coverage (2025, line 1.5): {df['implied_over_1_5'].notna().sum()}")

# ═══════════════════════════════════════════════════════════
# SAVE DATASET
# ═══════════════════════════════════════════════════════════
df.to_parquet(f'{OUT}/tb_model_dataset.parquet', index=False)
print(f"\n  Dataset saved: {len(df)} rows")

# Coverage diagnostics
print("\n  Coverage diagnostics:")
feature_cols = [
    'zero_tb_rate_last10', 'zero_tb_rate_last20', 'zero_tb_rate_season',
    'pct_2plus_tb_last20', 'pct_4plus_tb_last20', 'tb_variance_last20',
    'batter_iso_last20', 'batter_slg_last20', 'batter_k_rate_last20',
    'ondeck_iso_last20', 'ondeck_woba_proxy_last20', 'high_iso_x_weak_protection',
    'opp_drs', 'p_barrel_rate_last5', 'p_hard_hit_rate_last5', 'p_whiff_rate_last5',
    'park_factor', 'batting_order_slot', 'protector_type_enc'
]
for col in feature_cols:
    pct = df[col].notna().mean() * 100
    print(f"    {col}: {pct:.1f}%")

# ═══════════════════════════════════════════════════════════
# STEP 3 — MODEL TRAINING
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 3 — MODEL TRAINING")
print("="*60)

# Define feature sets
# Core features (high coverage, used for all seasons)
core_features = [
    # Group A: Zero-TB propensity
    'zero_tb_rate_last10', 'zero_tb_rate_last20', 'zero_tb_rate_season',
    'pct_2plus_tb_last20', 'pct_4plus_tb_last20', 'tb_variance_last20',
    # Group B: Protection
    'ondeck_iso_last20', 'ondeck_woba_proxy_last20',
    'weak_protection_flag', 'high_iso_flag', 'high_iso_x_weak_protection',
    'protector_type_enc',
    # Group C: Defense
    'opp_drs',
    # Group D: Pitcher
    'p_barrel_rate_last5', 'p_hard_hit_rate_last5', 'p_whiff_rate_last5',
    'p_avg_ip_last5',
    # Group E: Baseline
    'batter_iso_last20', 'batter_slg_last20', 'batter_k_rate_last20',
    'batter_obp_last20',
    'batting_order_slot', 'park_factor',
]

targets = {
    'tb_zero': 'tb_zero_flag',
    'tb_over_1_5': 'tb_over_1_5',
    'tb_over_2_5': 'tb_over_2_5',
}

# Time-based split: train on 2022-2024, validate on 2025
train_mask = df['season'].isin([2022, 2023, 2024])
val_mask = df['season'] == 2025

# Drop rows missing all core features
df_model = df.dropna(subset=['tb_zero_flag'])  # need target
feat_coverage = df_model[core_features].notna().mean()
print(f"\n  Feature coverage in full dataset:")
print(feat_coverage.to_string())

# For training, require at least the Group A features (highest coverage)
min_features = ['zero_tb_rate_last20', 'batter_iso_last20', 'batting_order_slot']
train_df = df_model[train_mask].dropna(subset=min_features).copy()
val_df = df_model[val_mask].dropna(subset=min_features).copy()
print(f"\n  Train: {len(train_df)} rows ({train_df['season'].value_counts().to_dict()})")
print(f"  Val: {len(val_df)} rows")

# Fill NaN in features with median (for missing pitcher/defense data)
medians = train_df[core_features].median()
train_filled = train_df[core_features].fillna(medians)
val_filled = val_df[core_features].fillna(medians)

models = {}
results = {}

for model_name, target_col in targets.items():
    print(f"\n  Training {model_name} model...")
    y_train = train_df[target_col].values
    y_val = val_df[target_col].values

    X_train = train_filled.values
    X_val = val_filled.values

    # GBT with conservative hyperparameters to avoid overfitting
    gbm = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        min_samples_leaf=50,
        subsample=0.8,
        max_features=0.7,
        random_state=42
    )
    gbm.fit(X_train, y_train)

    # Predictions
    train_probs = gbm.predict_proba(X_train)[:, 1]
    val_probs = gbm.predict_proba(X_val)[:, 1]

    # Metrics
    train_auc = roc_auc_score(y_train, train_probs)
    val_auc = roc_auc_score(y_val, val_probs)
    train_ll = log_loss(y_train, train_probs)
    val_ll = log_loss(y_val, val_probs)
    val_brier = brier_score_loss(y_val, val_probs)

    print(f"    Train AUC: {train_auc:.4f}, Val AUC: {val_auc:.4f}")
    print(f"    Train LogLoss: {train_ll:.4f}, Val LogLoss: {val_ll:.4f}")
    print(f"    Val Brier: {val_brier:.4f}")

    # Calibration
    cal_prob, cal_frac = calibration_curve(y_val, val_probs, n_bins=10, strategy='quantile')
    print(f"    Calibration (predicted vs actual):")
    for p, f in zip(cal_prob, cal_frac):
        print(f"      pred={f:.3f} actual={p:.3f}")

    models[model_name] = gbm
    results[model_name] = {
        'train_auc': train_auc, 'val_auc': val_auc,
        'train_logloss': train_ll, 'val_logloss': val_ll,
        'val_brier': val_brier
    }

    # Store predictions
    val_df[f'pred_{model_name}'] = val_probs
    train_df[f'pred_{model_name}'] = train_probs

# ═══════════════════════════════════════════════════════════
# STEP 4 — FAIR ODDS ENGINE
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 4 — FAIR ODDS ENGINE")
print("="*60)

# P(TB=0) = pred_tb_zero
# P(TB>=2) = pred_tb_over_1_5 => P(Under 1.5) = 1 - pred_tb_over_1_5
# P(TB>=3) = pred_tb_over_2_5 => P(Under 2.5) = 1 - pred_tb_over_2_5

val_df['model_p_under_1_5'] = 1 - val_df['pred_tb_over_1_5']
val_df['model_p_under_2_5'] = 1 - val_df['pred_tb_over_2_5']
val_df['model_p_over_0_5'] = 1 - val_df['pred_tb_zero']
val_df['model_p_over_1_5'] = val_df['pred_tb_over_1_5']

# Fair odds (American)
def prob_to_american(p):
    if p <= 0 or p >= 1:
        return np.nan
    if p >= 0.5:
        return -100 * p / (1 - p)
    else:
        return 100 * (1 - p) / p

val_df['fair_under_1_5'] = val_df['model_p_under_1_5'].apply(prob_to_american)
val_df['fair_under_2_5'] = val_df['model_p_under_2_5'].apply(prob_to_american)
val_df['fair_over_0_5'] = val_df['model_p_over_0_5'].apply(prob_to_american)
val_df['fair_over_1_5'] = val_df['model_p_over_1_5'].apply(prob_to_american)

# Edge vs market
val_df['edge_under_1_5'] = val_df['model_p_under_1_5'] - (1 - val_df['implied_over_1_5'])
val_df['edge_under_2_5'] = val_df['model_p_under_2_5'] - (1 - val_df['implied_over_2_5'])
val_df['edge_over_1_5'] = val_df['model_p_over_1_5'] - val_df['implied_over_1_5']

print(f"\n  Edge distributions (2025 validation):")
for edge_col in ['edge_under_1_5', 'edge_under_2_5', 'edge_over_1_5']:
    valid = val_df[edge_col].dropna()
    if len(valid) > 0:
        print(f"    {edge_col}: mean={valid.mean():.4f}, median={valid.median():.4f}, "
              f"std={valid.std():.4f}, >0: {(valid>0).mean()*100:.1f}%")

# ═══════════════════════════════════════════════════════════
# STEP 5 — BACKTEST
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 5 — BACKTEST")
print("="*60)

backtest_rows = []

for market, edge_col, pnl_col, under_odds_col in [
    ('Under 1.5', 'edge_under_1_5', 'under_pnl_1_5', 'under_odds_1_5'),
    ('Under 2.5', 'edge_under_2_5', 'under_pnl_2_5', 'under_odds_2_5'),
]:
    print(f"\n  === {market} Backtest ===")

    # Need records with both edge and PnL data
    bt = val_df.dropna(subset=[edge_col]).copy()

    # Actual outcome for win rate
    if market == 'Under 1.5':
        bt['won'] = (bt['total_bases'] < 2).astype(int)
    elif market == 'Under 2.5':
        bt['won'] = (bt['total_bases'] < 3).astype(int)

    print(f"  Total records with edge: {len(bt)}")
    print(f"  Records with closing odds: {bt[under_odds_col].notna().sum()}")

    # Overall stats
    print(f"  Win rate (all): {bt['won'].mean():.4f}")
    print(f"  Mean edge: {bt[edge_col].mean():.4f}")

    # ROI where under_odds available
    bt_with_odds = bt.dropna(subset=[under_odds_col])
    if len(bt_with_odds) > 0:
        overall_roi = bt_with_odds[pnl_col].mean()
        print(f"  Overall ROI (all, w/ odds): {overall_roi:.4f} (N={len(bt_with_odds)})")

    # Edge bucket analysis
    for threshold in [0.0, 0.02, 0.05, 0.08, 0.10]:
        filtered = bt[bt[edge_col] >= threshold]
        n = len(filtered)
        if n < 10:
            continue
        win_rate = filtered['won'].mean()
        # ROI from actual PnL
        with_odds = filtered.dropna(subset=[under_odds_col])
        roi = with_odds[pnl_col].mean() if len(with_odds) > 0 else np.nan
        n_odds = len(with_odds)

        # Flat-bet ROI estimate using edge
        # Approximate: if fair prob > implied prob by edge, flat bet ROI ≈ edge / implied_under
        avg_edge = filtered[edge_col].mean()

        backtest_rows.append({
            'market': market, 'edge_threshold': threshold,
            'N': n, 'N_with_odds': n_odds,
            'win_rate': round(win_rate, 4),
            'avg_edge': round(avg_edge, 4),
            'roi_actual': round(roi, 4) if not np.isnan(roi) else None,
        })

        roi_str = f"{roi:.4f}" if not np.isnan(roi) else "N/A"
        print(f"    edge>={threshold:.2f}: N={n}, win={win_rate:.4f}, "
              f"avg_edge={avg_edge:.4f}, ROI={roi_str} (N_odds={n_odds})")

    # ROI by probability decile
    print(f"\n  {market} by model probability decile:")
    if market == 'Under 1.5':
        prob_col = 'model_p_under_1_5'
    else:
        prob_col = 'model_p_under_2_5'

    bt['prob_decile'] = pd.qcut(bt[prob_col], 10, labels=False, duplicates='drop')
    for dec, grp in bt.groupby('prob_decile'):
        wr = grp['won'].mean()
        avg_p = grp[prob_col].mean()
        with_odds = grp.dropna(subset=[under_odds_col])
        roi = with_odds[pnl_col].mean() if len(with_odds) > 0 else np.nan
        roi_str2 = f"{roi:.4f}" if not np.isnan(roi) else "N/A"
        print(f"    D{int(dec)}: N={len(grp)}, model_p={avg_p:.3f}, actual={wr:.3f}, ROI={roi_str2}")

backtest_df = pd.DataFrame(backtest_rows)

# ═══════════════════════════════════════════════════════════
# STEP 6 — FEATURE IMPORTANCE
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 6 — FEATURE IMPORTANCE")
print("="*60)

importance_rows = []
for model_name, gbm in models.items():
    imp = gbm.feature_importances_
    sorted_idx = np.argsort(imp)[::-1]

    print(f"\n  {model_name} — Top 15 features:")
    for rank, i in enumerate(sorted_idx[:15]):
        feat = core_features[i]
        importance = imp[i]
        importance_rows.append({
            'model': model_name, 'rank': rank + 1,
            'feature': feat, 'importance': round(importance, 4)
        })
        print(f"    {rank+1:2d}. {feat:<35s} {importance:.4f}")

importance_df = pd.DataFrame(importance_rows)

# ═══════════════════════════════════════════════════════════
# SAVE ALL OUTPUT FILES
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("SAVING OUTPUT FILES")
print("="*60)

# Model predictions (validation set)
pred_cols = ['player_id', 'game_pk', 'game_date', 'season', 'player_name',
             'team', 'opponent', 'batting_order_slot', 'total_bases',
             'tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag',
             'pred_tb_zero', 'pred_tb_over_1_5', 'pred_tb_over_2_5',
             'model_p_under_1_5', 'model_p_under_2_5', 'model_p_over_0_5', 'model_p_over_1_5',
             'fair_under_1_5', 'fair_under_2_5', 'fair_over_0_5', 'fair_over_1_5',
             'edge_under_1_5', 'edge_under_2_5', 'edge_over_1_5',
             'implied_over_1_5', 'implied_over_2_5',
             'under_odds_1_5', 'under_odds_2_5',
             'under_pnl_1_5', 'under_pnl_2_5',
             'book_1_5', 'book_2_5']
# Only save columns that exist
pred_cols_exist = [c for c in pred_cols if c in val_df.columns]
val_df[pred_cols_exist].to_parquet(f'{OUT}/model_predictions.parquet', index=False)
print(f"  model_predictions.parquet: {len(val_df)} rows")

backtest_df.to_parquet(f'{OUT}/tb_model_backtest.parquet', index=False)
print(f"  tb_model_backtest.parquet: {len(backtest_df)} rows")

importance_df.to_parquet(f'{OUT}/feature_importance.parquet', index=False)
print(f"  feature_importance.parquet: {len(importance_df)} rows")

# Print final summary for report
print("\n\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)
print("\nModel Performance:")
for name, r in results.items():
    print(f"  {name}: train_AUC={r['train_auc']:.4f}, val_AUC={r['val_auc']:.4f}, "
          f"val_LogLoss={r['val_logloss']:.4f}, val_Brier={r['val_brier']:.4f}")

print("\nBacktest Summary:")
print(backtest_df.to_string(index=False))

print("\nDone.")
