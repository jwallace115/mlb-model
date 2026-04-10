"""
MLB Side Engine — Baseline Research Pipeline
Phases 1-8: Data audit, model build, calibration, residual map

RESEARCH ONLY — does not modify any live pipelines.
Output: research/mlb_side_engine/phase2_baseline_side_engine.md
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss, log_loss
from scipy.stats import norm
import warnings, os, json
warnings.filterwarnings('ignore')

OUT_DIR = 'research/mlb_side_engine'
os.makedirs(OUT_DIR, exist_ok=True)

report_lines = []
def rprint(s=''):
    print(s)
    report_lines.append(str(s))

# ─────────────────────────────────────────────────────────
# PHASE 1: Data Audit & Feature Inventory
# ─────────────────────────────────────────────────────────
rprint("=" * 70)
rprint("PHASE 1: DATA AUDIT & FEATURE INVENTORY")
rprint("=" * 70)

# Load all sources
ft = pd.read_parquet('sim/data/feature_table.parquet')
gt = pd.read_parquet('sim/data/game_table.parquet')
si_hist = pd.read_parquet('mlb_sim/data/sim_inputs_historical_2022_2024.parquet')
si_2025 = pd.read_parquet('mlb_sim/data/sim_inputs_2025.parquet')
odds_raw = pd.read_parquet('mlb_sim/data/mlb_odds_closing_canonical.parquet')

# Combine sim_inputs
si = pd.concat([si_hist, si_2025], ignore_index=True)
rprint(f"feature_table: {ft.shape[0]} games, {ft.shape[1]} cols")
rprint(f"game_table: {gt.shape[0]} games")
rprint(f"sim_inputs combined: {si.shape[0]} rows ({si['game_pk'].nunique()} games)")
rprint(f"odds_canonical: {odds_raw.shape[0]} rows ({odds_raw['game_pk'].nunique()} games)")

# Pivot sim_inputs to one row per game
si_home = si[si['is_home'] == 1].copy()
si_away = si[si['is_home'] == 0].copy()

home_cols = {
    'sp_xfip': 'home_sp_xfip_si', 'sp_siera': 'home_sp_siera_si',
    'bullpen_xfip': 'home_bp_xfip_si', 'opp_lineup_woba': 'away_lineup_woba',
    'park_factor': 'park_factor_si', 'umpire_runs_factor': 'umpire_runs_factor_si',
    'weather_run_modifier': 'weather_run_mod_si', 'days_rest': 'home_rest_si',
    'sp_csw_pct': 'home_sp_csw', 'sp_whiff_pct': 'home_sp_whiff',
    'sp_fstrike_pct': 'home_sp_fstrike', 'sp_recent_pc': 'home_sp_recent_pc'
}
away_cols = {
    'sp_xfip': 'away_sp_xfip_si', 'sp_siera': 'away_sp_siera_si',
    'bullpen_xfip': 'away_bp_xfip_si', 'opp_lineup_woba': 'home_lineup_woba',
    'days_rest': 'away_rest_si',
    'sp_csw_pct': 'away_sp_csw', 'sp_whiff_pct': 'away_sp_whiff',
    'sp_fstrike_pct': 'away_sp_fstrike', 'sp_recent_pc': 'away_sp_recent_pc'
}

si_h = si_home[['game_pk', 'date', 'season'] + list(home_cols.keys())].rename(columns=home_cols)
si_a = si_away[['game_pk'] + list(away_cols.keys())].rename(columns=away_cols)
si_wide = si_h.merge(si_a, on='game_pk', how='inner')
rprint(f"sim_inputs pivoted: {si_wide.shape[0]} games")

# Feature classification
feature_classification = {
    'SP xFIP differential': 'LIKELY_INCLUDED',
    'SP SIERA differential': 'LIKELY_INCLUDED',
    'Park factor': 'LIKELY_INCLUDED',
    'Temperature': 'LIKELY_INCLUDED',
    'Wind (effective)': 'LIKELY_INCLUDED',
    'Umpire over rate': 'LIKELY_EXCLUDED — subtle, not all books model',
    'Rest differential': 'LIKELY_INCLUDED',
    'Bullpen xFIP differential': 'LIKELY_INCLUDED',
    'Lineup wOBA differential': 'LIKELY_INCLUDED',
    'SP CSW/Whiff/Fstrike': 'LIKELY_EXCLUDED — granular pitch-level',
    'Closing total (context)': 'LIKELY_INCLUDED — Vegas consensus',
    'DH flag': 'LIKELY_INCLUDED',
    'Flyball x wind interaction': 'LIKELY_EXCLUDED — custom feature',
}
rprint("\nFeature Classification (Vegas likely includes / excludes):")
for feat, cls in feature_classification.items():
    rprint(f"  {feat}: {cls}")

# ─────────────────────────────────────────────────────────
# PHASE 2: Build Baseline Side Dataset
# ─────────────────────────────────────────────────────────
rprint("\n" + "=" * 70)
rprint("PHASE 2: BUILD BASELINE SIDE DATASET")
rprint("=" * 70)

# Use feature_table as primary (has SP stats, wRC+, weather, park, umpire, bullpen)
# Limit to 2022-2025 (seasons with odds)
ft = ft[ft['season'].isin([2022, 2023, 2024, 2025])].copy()

# De-vig odds: use DraftKings as primary book
odds_dk = odds_raw[odds_raw['book_key'] == 'draftkings'].copy()
# For games missing DK, try FanDuel
odds_fd = odds_raw[odds_raw['book_key'] == 'fanduel'].copy()

# De-vig ML: multiplicative method
def devig_ml(imp_home, imp_away):
    """Multiplicative de-vig."""
    total = imp_home + imp_away
    return imp_home / total, imp_away / total

odds_dk['p_home_ml'], odds_dk['p_away_ml'] = devig_ml(
    odds_dk['ml_home_implied'], odds_dk['ml_away_implied']
)

# De-vig RL prices (American odds to implied)
def american_to_implied(price):
    """Convert American odds to implied probability."""
    price = pd.to_numeric(price, errors='coerce')
    pos = price >= 0
    imp = np.where(pos, 100 / (price + 100), -price / (-price + 100))
    return imp

odds_dk['rl_home_imp'] = american_to_implied(odds_dk['rl_home_price'])
odds_dk['rl_away_imp'] = american_to_implied(odds_dk['rl_away_price'])
rl_total = odds_dk['rl_home_imp'] + odds_dk['rl_away_imp']
odds_dk['p_home_rl'] = odds_dk['rl_home_imp'] / rl_total
odds_dk['p_away_rl'] = odds_dk['rl_away_imp'] / rl_total

# Select one row per game from odds
odds_game = odds_dk[['game_pk', 'p_home_ml', 'p_away_ml', 'total_line',
                      'rl_home_line', 'p_home_rl', 'p_away_rl',
                      'ml_home_price', 'ml_away_price']].copy()
odds_game = odds_game[odds_game['game_pk'] != '']  # drop empty game_pk
odds_game = odds_game.drop_duplicates(subset='game_pk', keep='first')

rprint(f"DK odds (one per game): {odds_game.shape[0]}")

# Build master dataset from feature_table
df = ft[['game_pk', 'date', 'season', 'home_team', 'away_team',
         'home_score', 'away_score', 'actual_total',
         'home_sp_xfip', 'away_sp_xfip', 'home_sp_siera', 'away_sp_siera',
         'home_sp_k_pct', 'away_sp_k_pct', 'home_sp_bb_pct', 'away_sp_bb_pct',
         'home_sp_avg_ip', 'away_sp_avg_ip',
         'home_wrc_plus', 'away_wrc_plus',
         'home_bp_xfip', 'away_bp_xfip',
         'park_factor_runs', 'temperature', 'wind_speed', 'wind_factor_effective',
         'umpire_over_rate',
         'home_rest_days', 'away_rest_days',
         'doubleheader_flag']].copy()

# Compute targets
df['home_win'] = (df['home_score'] > df['away_score']).astype(int)
df['actual_margin'] = df['home_score'] - df['away_score']

# Drop ties (very rare in MLB but possible if game suspended)
ties = df['home_score'] == df['away_score']
rprint(f"Ties dropped: {ties.sum()}")
df = df[~ties].copy()

# Join odds
df['game_pk'] = df['game_pk'].astype(str)
odds_game['game_pk'] = odds_game['game_pk'].astype(str)
df = df.merge(odds_game, on='game_pk', how='left')

rprint(f"Dataset after join: {df.shape[0]} games")
rprint(f"ML odds coverage: {df['p_home_ml'].notna().sum()} / {df.shape[0]} ({df['p_home_ml'].notna().mean()*100:.1f}%)")
rprint(f"RL odds coverage: {df['p_home_rl'].notna().sum()} / {df.shape[0]} ({df['p_home_rl'].notna().mean()*100:.1f}%)")
rprint(f"Total line coverage: {df['total_line'].notna().sum()} / {df.shape[0]}")

# Compute derived features
df['sp_xfip_diff'] = df['home_sp_xfip'] - df['away_sp_xfip']  # negative = home SP better
df['sp_siera_diff'] = df['home_sp_siera'] - df['away_sp_siera']
df['sp_k_diff'] = df['home_sp_k_pct'] - df['away_sp_k_pct']  # positive = home K% higher (better)
df['sp_bb_diff'] = df['home_sp_bb_pct'] - df['away_sp_bb_pct']  # negative = home BB% lower (better)
df['wrc_diff'] = df['home_wrc_plus'] - df['away_wrc_plus']
df['bp_xfip_diff'] = df['home_bp_xfip'] - df['away_bp_xfip']
df['rest_diff'] = df['home_rest_days'] - df['away_rest_days']

# Feature coverage
rprint("\nFeature coverage:")
feature_cols = ['sp_xfip_diff', 'wrc_diff', 'bp_xfip_diff', 'park_factor_runs',
                'temperature', 'wind_factor_effective', 'umpire_over_rate',
                'rest_diff', 'total_line']
for c in feature_cols:
    n = df[c].notna().sum()
    rprint(f"  {c}: {n} / {df.shape[0]} ({n/df.shape[0]*100:.1f}%)")

# ─────────────────────────────────────────────────────────
# PHASE 3: Build Baseline Models
# ─────────────────────────────────────────────────────────
rprint("\n" + "=" * 70)
rprint("PHASE 3: BUILD BASELINE MODELS")
rprint("=" * 70)

# Model features
model_features = [
    'sp_xfip_diff',       # SP quality differential (lower = home better)
    'wrc_diff',           # Offense differential
    'bp_xfip_diff',       # Bullpen differential
    'park_factor_runs',   # Park factor
    'temperature',        # Temperature
    'wind_factor_effective',  # Wind (signed run units)
    'umpire_over_rate',   # Umpire run environment
    'rest_diff',          # Rest differential
    'total_line',         # Closing total as context
]

# Require ML odds and all features
df_model = df.dropna(subset=model_features + ['p_home_ml', 'home_win']).copy()
rprint(f"Modeling dataset: {df_model.shape[0]} games (after dropping nulls)")
rprint(f"Season breakdown: {df_model.groupby('season')['game_pk'].count().to_dict()}")

# Train/val/OOS split
train = df_model[df_model['season'].isin([2022, 2023])].copy()
val = df_model[df_model['season'] == 2024].copy()
oos = df_model[df_model['season'] == 2025].copy()
rprint(f"Train: {len(train)}, Val: {len(val)}, OOS: {len(oos)}")

# Standardize features
scaler = StandardScaler()
X_train = scaler.fit_transform(train[model_features])
X_val = scaler.transform(val[model_features])
X_oos = scaler.transform(oos[model_features])

y_train = train['home_win'].values
y_val = val['home_win'].values
y_oos = oos['home_win'].values

# MODEL A: Logistic Regression
rprint("\n--- MODEL A: Logistic Regression (home_win) ---")
model_a = LogisticRegression(C=1.0, max_iter=1000, solver='lbfgs')
model_a.fit(X_train, y_train)

# Predictions
train['prob_a'] = model_a.predict_proba(X_train)[:, 1]
val['prob_a'] = model_a.predict_proba(X_val)[:, 1]
oos['prob_a'] = model_a.predict_proba(X_oos)[:, 1]

# Feature importances
rprint("\nModel A coefficients (standardized):")
for feat, coef in sorted(zip(model_features, model_a.coef_[0]), key=lambda x: abs(x[1]), reverse=True):
    rprint(f"  {feat:30s}: {coef:+.4f}")

# MODEL B: Ridge Regression on margin
rprint("\n--- MODEL B: Ridge Regression (actual_margin) ---")

# Try several alpha values
best_alpha = None
best_val_brier = 1.0

for alpha in [0.1, 1.0, 10.0, 50.0, 100.0, 500.0]:
    model_b = Ridge(alpha=alpha)
    model_b.fit(X_train, train['actual_margin'].values)

    margin_pred_val = model_b.predict(X_val)
    # Convert margin to win prob via logistic CDF
    # Calibrate sigma on training set
    train_margin_pred = model_b.predict(X_train)
    train_resid = train['actual_margin'].values - train_margin_pred
    sigma_cal = np.std(train_resid)

    prob_b_val = norm.cdf(margin_pred_val / sigma_cal)
    brier_val = brier_score_loss(y_val, prob_b_val)

    if brier_val < best_val_brier:
        best_val_brier = brier_val
        best_alpha = alpha
        best_sigma = sigma_cal

rprint(f"Best Ridge alpha: {best_alpha} (val Brier: {best_val_brier:.6f})")

model_b = Ridge(alpha=best_alpha)
model_b.fit(X_train, train['actual_margin'].values)

# Calibration sigma
train_margin_pred = model_b.predict(X_train)
train_resid = train['actual_margin'].values - train_margin_pred
sigma_b = np.std(train_resid)
rprint(f"Calibration sigma: {sigma_b:.3f}")

# Predictions
train['margin_b'] = model_b.predict(X_train)
val['margin_b'] = model_b.predict(X_val)
oos['margin_b'] = model_b.predict(X_oos)

train['prob_b'] = norm.cdf(train['margin_b'] / sigma_b)
val['prob_b'] = norm.cdf(val['margin_b'] / sigma_b)
oos['prob_b'] = norm.cdf(oos['margin_b'] / sigma_b)

rprint("\nModel B coefficients (standardized):")
for feat, coef in sorted(zip(model_features, model_b.coef_), key=lambda x: abs(x[1]), reverse=True):
    rprint(f"  {feat:30s}: {coef:+.4f}")

# ─────────────────────────────────────────────────────────
# PHASE 4: Calibration vs Market
# ─────────────────────────────────────────────────────────
rprint("\n" + "=" * 70)
rprint("PHASE 4: CALIBRATION VS MARKET")
rprint("=" * 70)

def eval_model(label, y_true, y_prob, split_name):
    brier = brier_score_loss(y_true, y_prob)
    ll = log_loss(y_true, np.clip(y_prob, 0.001, 0.999))
    corr = np.corrcoef(y_true, y_prob)[0, 1]
    return {'label': label, 'split': split_name, 'brier': brier, 'logloss': ll, 'corr': corr}

results = []
for split_name, split_df in [('Train', train), ('Val', val), ('OOS', oos)]:
    y = split_df['home_win'].values
    results.append(eval_model('Market ML', y, split_df['p_home_ml'].values, split_name))
    results.append(eval_model('Model A (Logistic)', y, split_df['prob_a'].values, split_name))
    results.append(eval_model('Model B (Ridge)', y, split_df['prob_b'].values, split_name))

res_df = pd.DataFrame(results)
rprint("\n--- Evaluation Metrics ---")
for split in ['Train', 'Val', 'OOS']:
    rprint(f"\n  {split}:")
    sub = res_df[res_df['split'] == split]
    for _, row in sub.iterrows():
        rprint(f"    {row['label']:25s}  Brier={row['brier']:.6f}  LogLoss={row['logloss']:.4f}  Corr={row['corr']:.4f}")

# Calibration by decile (OOS)
rprint("\n--- OOS Calibration by Decile ---")
for label, prob_col in [('Market ML', 'p_home_ml'), ('Model A', 'prob_a'), ('Model B', 'prob_b')]:
    oos_sorted = oos.copy()
    oos_sorted['decile'] = pd.qcut(oos_sorted[prob_col], 10, labels=False, duplicates='drop')
    cal = oos_sorted.groupby('decile').agg(
        n=('home_win', 'count'),
        pred_mean=(prob_col, 'mean'),
        actual_mean=('home_win', 'mean')
    ).reset_index()
    rprint(f"\n  {label}:")
    rprint(f"  {'Decile':>7} {'N':>5} {'Pred':>7} {'Actual':>7} {'Gap':>7}")
    for _, r in cal.iterrows():
        gap = r['actual_mean'] - r['pred_mean']
        rprint(f"  {int(r['decile']):>7} {int(r['n']):>5} {r['pred_mean']:>7.3f} {r['actual_mean']:>7.3f} {gap:>+7.3f}")

# ─────────────────────────────────────────────────────────
# PHASE 5: RL Feasibility
# ─────────────────────────────────────────────────────────
rprint("\n" + "=" * 70)
rprint("PHASE 5: RL FEASIBILITY")
rprint("=" * 70)

# Use Model B margin predictions to compute P(home wins by 2+)
# Standard RL is -1.5 (home team -1.5)
oos_rl = oos.dropna(subset=['p_home_rl', 'rl_home_line']).copy()
rprint(f"Games with RL data: {len(oos_rl)}")

if len(oos_rl) > 100:
    # P(margin >= 1.5) using normal approximation
    oos_rl['p_cover_rl_model'] = 1 - norm.cdf(1.5, loc=oos_rl['margin_b'], scale=sigma_b)
    oos_rl['actual_cover_rl'] = (oos_rl['actual_margin'] >= 2).astype(int)  # home covers -1.5

    brier_rl_model = brier_score_loss(oos_rl['actual_cover_rl'], oos_rl['p_cover_rl_model'])
    brier_rl_market = brier_score_loss(oos_rl['actual_cover_rl'], oos_rl['p_home_rl'])

    rprint(f"\nRL (-1.5) Calibration (OOS 2025):")
    rprint(f"  Model B  Brier: {brier_rl_model:.6f}")
    rprint(f"  Market   Brier: {brier_rl_market:.6f}")
    rprint(f"  Gap: {brier_rl_model - brier_rl_market:+.6f} (positive = market better)")

    # Calibration
    rprint(f"\n  Actual cover rate: {oos_rl['actual_cover_rl'].mean():.3f}")
    rprint(f"  Model mean P(cover): {oos_rl['p_cover_rl_model'].mean():.3f}")
    rprint(f"  Market mean P(cover): {oos_rl['p_home_rl'].mean():.3f}")

# ─────────────────────────────────────────────────────────
# PHASE 6: Residual Map
# ─────────────────────────────────────────────────────────
rprint("\n" + "=" * 70)
rprint("PHASE 6: RESIDUAL MAP (CRITICAL)")
rprint("=" * 70)

# Use OOS (2025) for residual analysis
oos['model_resid'] = oos['home_win'] - oos['prob_b']
oos['market_resid'] = oos['home_win'] - oos['p_home_ml']
oos['disagreement'] = oos['prob_b'] - oos['p_home_ml']

rprint(f"\nOverall OOS stats:")
rprint(f"  Model residual std: {oos['model_resid'].std():.4f}")
rprint(f"  Market residual std: {oos['market_resid'].std():.4f}")
rprint(f"  Disagreement std: {oos['disagreement'].std():.4f}")
rprint(f"  Disagreement mean: {oos['disagreement'].mean():.4f}")

def bucket_analysis(df, bucket_col, bucket_name, n_buckets=3):
    """Analyze model/market performance by buckets."""
    rprint(f"\n--- {bucket_name} ---")

    if df[bucket_col].nunique() <= n_buckets:
        df['_bucket'] = df[bucket_col]
    else:
        df['_bucket'] = pd.qcut(df[bucket_col], n_buckets, labels=['Low', 'Mid', 'High'], duplicates='drop')

    rprint(f"  {'Bucket':>10} {'N':>5} {'Model_Br':>10} {'Mkt_Br':>10} {'Disagree':>10} {'Model-Mkt':>10}")

    findings = []
    for bkt, grp in df.groupby('_bucket'):
        if len(grp) < 20:
            continue
        model_br = brier_score_loss(grp['home_win'], grp['prob_b'])
        mkt_br = brier_score_loss(grp['home_win'], grp['p_home_ml'])
        disagree_mean = grp['disagreement'].mean()
        gap = model_br - mkt_br
        rprint(f"  {str(bkt):>10} {len(grp):>5} {model_br:>10.6f} {mkt_br:>10.6f} {disagree_mean:>+10.4f} {gap:>+10.6f}")
        findings.append({'bucket': str(bkt), 'n': len(grp), 'model_brier': model_br,
                        'market_brier': mkt_br, 'gap': gap, 'disagree': disagree_mean})

    df.drop(columns=['_bucket'], inplace=True)
    return findings

# A) SP quality differential buckets
findings_sp = bucket_analysis(oos, 'sp_xfip_diff', 'A) SP Quality Differential (xFIP)')

# B) Total band
findings_total = bucket_analysis(oos, 'total_line', 'B) Total Band')

# C) ML favorite strength
oos['fav_strength'] = oos['p_home_ml'].apply(lambda p: abs(p - 0.5))
findings_fav = bucket_analysis(oos, 'fav_strength', 'C) ML Favorite Strength')

# D) Home vs Away favorite
oos['home_fav'] = (oos['p_home_ml'] > 0.5).map({True: 'Home Fav', False: 'Away Fav'})
findings_ha = bucket_analysis(oos, 'home_fav', 'D) Home vs Away Favorite', n_buckets=2)

# E) Park type
findings_park = bucket_analysis(oos, 'park_factor_runs', 'E) Park Factor')

# F) Rest differential
oos['rest_bucket'] = oos['rest_diff'].clip(-2, 2)
findings_rest = bucket_analysis(oos, 'rest_bucket', 'F) Rest Differential', n_buckets=5)

# ─────────────────────────────────────────────────────────
# PHASE 7: Correction-Direction Test
# ─────────────────────────────────────────────────────────
rprint("\n" + "=" * 70)
rprint("PHASE 7: CORRECTION-DIRECTION TEST")
rprint("=" * 70)

# When model and market disagree, who is right?
oos['disagree_abs'] = oos['disagreement'].abs()

# Tertiles of disagreement magnitude
oos['disagree_tertile'] = pd.qcut(oos['disagree_abs'], 3, labels=['Small', 'Medium', 'Large'], duplicates='drop')

rprint("\n--- Disagreement Magnitude Analysis ---")
rprint(f"  {'Tertile':>10} {'N':>5} {'Model_Br':>10} {'Mkt_Br':>10} {'Gap':>10}")
for tert, grp in oos.groupby('disagree_tertile'):
    model_br = brier_score_loss(grp['home_win'], grp['prob_b'])
    mkt_br = brier_score_loss(grp['home_win'], grp['p_home_ml'])
    rprint(f"  {str(tert):>10} {len(grp):>5} {model_br:>10.6f} {mkt_br:>10.6f} {model_br - mkt_br:>+10.6f}")

# Direction test: when model says "more home" than market, is home win rate higher?
oos['model_says_more_home'] = oos['disagreement'] > 0
rprint("\n--- Direction Test ---")
rprint("When model says 'more home' vs 'less home' than market:")
for direction, grp in oos.groupby('model_says_more_home'):
    label = 'Model > Market (more home)' if direction else 'Model < Market (less home)'
    hw_rate = grp['home_win'].mean()
    mkt_mean = grp['p_home_ml'].mean()
    model_mean = grp['prob_b'].mean()
    n = len(grp)
    rprint(f"  {label}: N={n}, actual HW rate={hw_rate:.3f}, model mean={model_mean:.3f}, market mean={mkt_mean:.3f}")

# Bigger disagreements — top/bottom quartile
q75 = oos['disagreement'].quantile(0.75)
q25 = oos['disagreement'].quantile(0.25)

rprint("\n--- Strong Disagreement Test ---")
strong_home = oos[oos['disagreement'] > q75]
strong_away = oos[oos['disagreement'] < q25]

rprint(f"Model strongly favors home (top 25%, disagree > {q75:.3f}):")
rprint(f"  N={len(strong_home)}, actual HW={strong_home['home_win'].mean():.3f}, model={strong_home['prob_b'].mean():.3f}, market={strong_home['p_home_ml'].mean():.3f}")

rprint(f"Model strongly favors away (bottom 25%, disagree < {q25:.3f}):")
rprint(f"  N={len(strong_away)}, actual HW={strong_away['home_win'].mean():.3f}, model={strong_away['prob_b'].mean():.3f}, market={strong_away['p_home_ml'].mean():.3f}")

# Contextual direction test
rprint("\n--- Contextual Correction Direction ---")
for context_col, context_name, n_bkts in [
    ('sp_xfip_diff', 'SP Diff', 2),
    ('total_line', 'Total', 2),
    ('fav_strength', 'Fav Strength', 2),
]:
    oos['_ctx'] = pd.qcut(oos[context_col], n_bkts, labels=False, duplicates='drop')
    rprint(f"\n  {context_name}:")
    for ctx_val, ctx_grp in oos.groupby('_ctx'):
        ctx_label = 'Low' if ctx_val == 0 else 'High'
        # Among disagreements in this context
        more_home = ctx_grp[ctx_grp['disagreement'] > 0.02]
        less_home = ctx_grp[ctx_grp['disagreement'] < -0.02]
        if len(more_home) > 20 and len(less_home) > 20:
            rprint(f"    {ctx_label}: model>mkt N={len(more_home)} HW={more_home['home_win'].mean():.3f} | model<mkt N={len(less_home)} HW={less_home['home_win'].mean():.3f}")
    oos.drop(columns=['_ctx'], inplace=True)

# ─────────────────────────────────────────────────────────
# PHASE 8: Project Implications
# ─────────────────────────────────────────────────────────
rprint("\n" + "=" * 70)
rprint("PHASE 8: PROJECT IMPLICATIONS")
rprint("=" * 70)

# Collect key metrics
oos_model_a_brier = brier_score_loss(y_oos, oos['prob_a'].values)
oos_model_b_brier = brier_score_loss(y_oos, oos['prob_b'].values)
oos_market_brier = brier_score_loss(y_oos, oos['p_home_ml'].values)

brier_gap_a = oos_model_a_brier - oos_market_brier
brier_gap_b = oos_model_b_brier - oos_market_brier

# Find top residual structure findings
all_findings = []
for findings, name in [(findings_sp, 'SP Diff'), (findings_total, 'Total Band'),
                        (findings_fav, 'Fav Strength'), (findings_ha, 'Home/Away Fav'),
                        (findings_park, 'Park Factor'), (findings_rest, 'Rest Diff')]:
    for f in findings:
        f['context'] = name
        all_findings.append(f)

# Sort by gap (where model beats market = negative gap)
all_findings.sort(key=lambda x: x['gap'])
top_model_wins = [f for f in all_findings if f['gap'] < 0 and f['n'] >= 50]

rprint("\n--- Key Metrics ---")
rprint(f"Model A (Logistic) OOS Brier: {oos_model_a_brier:.6f}")
rprint(f"Model B (Ridge)    OOS Brier: {oos_model_b_brier:.6f}")
rprint(f"Market ML          OOS Brier: {oos_market_brier:.6f}")
rprint(f"Gap A vs Market: {brier_gap_a:+.6f}")
rprint(f"Gap B vs Market: {brier_gap_b:+.6f}")

rprint("\n--- Residual Structure Findings ---")
if top_model_wins:
    rprint("Buckets where model outperforms market:")
    for i, f in enumerate(top_model_wins[:5]):
        rprint(f"  {i+1}. {f['context']} = {f['bucket']}: model Brier {f['model_brier']:.6f} vs market {f['market_brier']:.6f} (gap={f['gap']:+.6f}, N={f['n']})")
else:
    rprint("No buckets where model consistently outperforms market.")

# Also report buckets with largest structural disagreement
rprint("\nLargest systematic disagreement (model vs market):")
all_findings.sort(key=lambda x: abs(x['disagree']), reverse=True)
for i, f in enumerate(all_findings[:5]):
    rprint(f"  {i+1}. {f['context']} = {f['bucket']}: disagree={f['disagree']:+.4f}, N={f['n']}")

# Verdict
rprint("\n--- VERDICT ---")
if brier_gap_b < -0.001:
    verdict = "ADVANCE"
    reason = "Model B outperforms market on Brier — genuine signal detected"
elif brier_gap_b < 0.003:
    verdict = "NEAR MISS"
    reason = "Model B close to market — residual structure may yield targeted signals"
elif any(f['gap'] < -0.005 and f['n'] >= 100 for f in all_findings):
    verdict = "NEAR MISS"
    reason = "Overall gap exists but specific contexts show model advantage"
else:
    verdict = "CLOSE"
    reason = "Market dominates overall; limited structural opportunity"

# Check if any contextual corrections show promise
strong_home_hw = strong_home['home_win'].mean()
strong_home_model = strong_home['prob_b'].mean()
strong_home_market = strong_home['p_home_ml'].mean()
correction_signal = abs(strong_home_hw - strong_home_model) < abs(strong_home_hw - strong_home_market)

if correction_signal:
    rprint(f"Verdict: {verdict}")
    rprint(f"Reason: {reason}")
    rprint("Correction-direction signal detected: model is closer to truth in strong disagreements")
else:
    rprint(f"Verdict: {verdict}")
    rprint(f"Reason: {reason}")
    rprint("No correction-direction signal in strong disagreements")

# Recommended next branch
rprint("\n--- RECOMMENDED NEXT BRANCH ---")
recommendations = []
if top_model_wins:
    best = top_model_wins[0]
    recommendations.append(f"1. Deep-dive on {best['context']}={best['bucket']} context — model shows Brier advantage")

if brier_gap_b < 0.005:
    recommendations.append("2. Add pitcher matchup features (L/R splits, platoon advantage) — biggest missing input")
    recommendations.append("3. Add recent form / momentum features (last 10 game wRC+, SP last 3 starts)")

if len(oos_rl) > 100:
    rl_gap = brier_rl_model - brier_rl_market if 'brier_rl_model' in dir() else None
    if rl_gap is not None and rl_gap < 0.005:
        recommendations.append("4. RL margin model shows promise — investigate run-line specific features")

if not recommendations:
    recommendations.append("1. Incorporate pitcher handedness matchup (platoon splits)")
    recommendations.append("2. Add travel/schedule difficulty features")
    recommendations.append("3. Consider ensemble with market as a feature (blend)")

for r in recommendations:
    rprint(r)

# ─────────────────────────────────────────────────────────
# Write report
# ─────────────────────────────────────────────────────────
report_path = os.path.join(OUT_DIR, 'phase2_baseline_side_engine.md')
with open(report_path, 'w') as f:
    f.write("# MLB Side Engine — Baseline Research Report\n\n")
    f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    f.write("```\n")
    f.write('\n'.join(report_lines))
    f.write("\n```\n")

print(f"\n\nReport written to: {report_path}")
