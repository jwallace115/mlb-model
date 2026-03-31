"""
TB Signal Discovery Study — RESEARCH ONLY
Identifies signal families that explain TB distribution shape
beyond mean-based sportsbook pricing.
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss, roc_auc_score
import warnings
warnings.filterwarnings('ignore')

OUT = 'research/mlb_props/tb_signal_discovery'

# ═══════════════════════════════════════════════════════════
# LOAD ALL DATA
# ═══════════════════════════════════════════════════════════
print("Loading datasets...")
tb = pd.read_parquet('research/mlb_props/tb_props/tb_props_dataset.parquet')
hl = pd.read_parquet('mlb/data/hitter_game_logs.parquet')
ps = pd.read_parquet('research/statcast_enrichment/pitcher_statcast_per_start.parquet')
prot = pd.read_parquet('research/lineup_protection_study/followup_iso_mechanism/iso_mechanism_dataset.parquet')
rl = pd.read_parquet('research/data_pulls/reliever_role_tracking.parquet')
td = pd.read_parquet('research/statcast_enrichment/team_defense.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')

print(f"TB props: {len(tb)}, Hitter logs: {len(hl)}, Pitcher statcast: {len(ps)}")
print(f"Protection: {len(prot)}, Reliever: {len(rl)}, Defense: {len(td)}, Pitcher logs: {len(pl)}")

# ═══════════════════════════════════════════════════════════
# STEP 1 — BUILD TB DISTRIBUTION TARGETS
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 1 — TB DISTRIBUTION TARGETS")
print("="*60)

tb['tb_zero_flag'] = (tb['actual_tb'] == 0).astype(int)
tb['tb_over_1_5'] = (tb['actual_tb'] > 1.5).astype(int)
tb['tb_over_2_5'] = (tb['actual_tb'] > 2.5).astype(int)
tb['tb_tail_flag'] = (tb['actual_tb'] >= 4).astype(int)

print(f"\nBaseline rates (N={len(tb)}):")
for col in ['tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag']:
    print(f"  {col}: {tb[col].mean():.4f}")

# ═══════════════════════════════════════════════════════════
# BUILD ROLLING HITTER FEATURES (from hitter_game_logs)
# ═══════════════════════════════════════════════════════════
print("\nBuilding rolling hitter features from hitter_game_logs...")

# Compute total_bases per game in hitter logs
hl['total_bases'] = hl['singles'] + 2*hl['doubles'] + 3*hl['triples'] + 4*hl['home_runs']
hl['xbh'] = hl['doubles'] + hl['triples'] + hl['home_runs']
hl['tb_zero'] = (hl['total_bases'] == 0).astype(int)
hl['tb_ge2'] = (hl['total_bases'] >= 2).astype(int)
hl['tb_ge4'] = (hl['total_bases'] >= 4).astype(int)

hl = hl.sort_values(['player_id', 'game_date', 'game_pk'])

# Rolling 20-game features per hitter
def build_hitter_rolling(grp):
    grp = grp.sort_values(['game_date', 'game_pk'])
    r = 20
    mp = 10
    out = pd.DataFrame(index=grp.index)
    out['player_id'] = grp['player_id']
    out['game_pk'] = grp['game_pk']
    out['game_date'] = grp['game_date']

    # Zero-TB rate last 20
    out['zero_tb_rate_last20'] = grp['tb_zero'].rolling(r, min_periods=mp).mean().values
    # Pct games 2+ TB
    out['pct_2plus_tb_last20'] = grp['tb_ge2'].rolling(r, min_periods=mp).mean().values
    # Pct games 4+ TB
    out['pct_4plus_tb_last20'] = grp['tb_ge4'].rolling(r, min_periods=mp).mean().values
    # TB variance last 20
    out['tb_var_last20'] = grp['total_bases'].rolling(r, min_periods=mp).var().values
    # Mean TB last 20
    out['mean_tb_last20'] = grp['total_bases'].rolling(r, min_periods=mp).mean().values
    # ISO last 20 (from hitter logs which has iso column)
    out['iso_last20'] = grp['iso'].rolling(r, min_periods=mp).mean().values
    # SLG last 20
    out['slg_last20'] = grp['slg'].rolling(r, min_periods=mp).mean().values
    # K rate
    out['k_rate_last20'] = (grp['strikeouts'].rolling(r, min_periods=mp).sum() /
                             grp['plate_appearances'].rolling(r, min_periods=mp).sum()).values

    # SHIFT by 1 to make these pre-game (avoid leakage)
    for col in ['zero_tb_rate_last20', 'pct_2plus_tb_last20', 'pct_4plus_tb_last20',
                'tb_var_last20', 'mean_tb_last20', 'iso_last20', 'slg_last20', 'k_rate_last20']:
        out[col] = out[col].shift(1)

    return out

hitter_feats = hl.groupby('player_id', group_keys=False).apply(build_hitter_rolling)
print(f"  Hitter rolling features: {len(hitter_feats)} rows, {hitter_feats['zero_tb_rate_last20'].notna().sum()} non-null")

# ═══════════════════════════════════════════════════════════
# BUILD ROLLING PITCHER FEATURES (from pitcher_statcast)
# ═══════════════════════════════════════════════════════════
print("Building rolling pitcher features from pitcher_statcast_per_start...")

# Only starters
starters = pl[pl['starter_flag'] == 1][['game_pk', 'player_id', 'player_name', 'team', 'opponent', 'home_away', 'innings_pitched']].copy()
starters = starters.rename(columns={'player_id': 'pitcher_id', 'player_name': 'pitcher_name_pl'})

# Merge statcast onto starters
ps_merged = starters.merge(ps[['pitcher_id', 'game_pk', 'hard_hit_rate', 'barrel_rate', 'whiff_rate', 'zone_rate', 'avg_exit_velo']],
                           on=['pitcher_id', 'game_pk'], how='inner')
ps_merged = ps_merged.merge(pl[pl['starter_flag']==1][['game_pk','player_id','game_date','hits_allowed','home_runs_allowed','batters_faced']].rename(
    columns={'player_id':'pitcher_id'}), on=['pitcher_id','game_pk'], how='left')

# XBH allowed rate
ps_merged['xbh_allowed_per_bf'] = ps_merged['home_runs_allowed'] / ps_merged['batters_faced'].replace(0, np.nan)

ps_merged = ps_merged.sort_values(['pitcher_id', 'game_date', 'game_pk'])

def build_pitcher_rolling(grp):
    grp = grp.sort_values(['game_date', 'game_pk'])
    r = 5  # last 5 starts for pitchers
    mp = 3
    out = pd.DataFrame(index=grp.index)
    out['pitcher_id'] = grp['pitcher_id']
    out['game_pk'] = grp['game_pk']
    out['game_date'] = grp['game_date']
    out['team'] = grp['team']
    out['opponent'] = grp['opponent']
    out['home_away'] = grp['home_away']
    out['innings_pitched'] = grp['innings_pitched']

    for col in ['hard_hit_rate', 'barrel_rate', 'whiff_rate', 'avg_exit_velo']:
        out[f'p_{col}_last5'] = grp[col].rolling(r, min_periods=mp).mean().shift(1).values

    out['p_avg_ip_last5'] = grp['innings_pitched'].rolling(r, min_periods=mp).mean().shift(1).values

    return out

pitcher_feats = ps_merged.groupby('pitcher_id', group_keys=False).apply(build_pitcher_rolling)
print(f"  Pitcher rolling features: {len(pitcher_feats)} rows, {pitcher_feats['p_barrel_rate_last5'].notna().sum()} non-null")

# ═══════════════════════════════════════════════════════════
# JOIN EVERYTHING TO TB PROPS
# ═══════════════════════════════════════════════════════════
print("\nJoining features to TB props dataset...")

# Join hitter features via player_name match to hitter_game_logs
# TB props has: player_name_out, game_pk_out
# Hitter logs has: player_name, game_pk, player_id
# First get player_id mapping from hitter logs
name_to_id = hl.drop_duplicates('player_name')[['player_name', 'player_id']]
tb2 = tb.merge(name_to_id.rename(columns={'player_name': 'player_name_out'}),
               on='player_name_out', how='left')
print(f"  Player ID match: {tb2['player_id'].notna().sum()}/{len(tb2)}")

# Join hitter rolling features
tb2 = tb2.merge(hitter_feats[['player_id', 'game_pk', 'zero_tb_rate_last20', 'pct_2plus_tb_last20',
                               'pct_4plus_tb_last20', 'tb_var_last20', 'mean_tb_last20',
                               'iso_last20', 'slg_last20', 'k_rate_last20']],
                left_on=['player_id', 'game_pk_out'],
                right_on=['player_id', 'game_pk'], how='left', suffixes=('', '_hl'))
print(f"  Hitter features joined: {tb2['zero_tb_rate_last20'].notna().sum()}/{len(tb2)}")

# Join pitcher features - need to identify opposing starter for each batter
# Pitcher feats has team/opponent/home_away. For a batter, the opposing pitcher
# is the starter whose opponent == batter's team and game_pk matches
pitcher_for_join = pitcher_feats[['game_pk', 'opponent', 'pitcher_id',
                                   'p_hard_hit_rate_last5', 'p_barrel_rate_last5',
                                   'p_whiff_rate_last5', 'p_avg_exit_velo_last5',
                                   'p_avg_ip_last5', 'innings_pitched']].copy()
pitcher_for_join = pitcher_for_join.rename(columns={'opponent': 'team_faced', 'innings_pitched': 'starter_ip'})

tb2 = tb2.merge(pitcher_for_join, left_on=['game_pk_out', 'team'],
                right_on=['game_pk', 'team_faced'], how='left', suffixes=('', '_p'))
print(f"  Pitcher features joined: {tb2['p_barrel_rate_last5'].notna().sum()}/{len(tb2)}")

# Join protection data
prot_cols = ['game_pk', 'player_id', 'ondeck_iso_last20', 'ondeck_woba_proxy_last20',
             'ondeck_k_rate_last20', 'ondeck_contact_rate_last20', 'protector_type',
             'opp_pitcher_barrel_rate', 'opp_pitcher_hh_rate']
prot_sub = prot[prot_cols].copy()
tb2 = tb2.merge(prot_sub, left_on=['game_pk_out', 'player_id'],
                right_on=['game_pk', 'player_id'], how='left', suffixes=('', '_prot'))
print(f"  Protection features joined: {tb2['ondeck_iso_last20'].notna().sum()}/{len(tb2)}")

# Join reliever data
rl2 = rl.copy()
# For each batter, get the opposing team's bullpen data
# If batter is home, opposing bullpen = away side; if away, opposing = home side
tb2 = tb2.merge(rl2.rename(columns={'date': 'game_date_rl'}),
                left_on='game_pk_out', right_on='game_pk', how='left', suffixes=('', '_rl'))

# Compute opposing bullpen metrics
tb2['opp_bp_high_lev_ip'] = np.where(
    tb2['home_away'] == 'home',
    tb2['away_bullpen_high_leverage_ip_last3d'],
    tb2['home_bullpen_high_leverage_ip_last3d']
)
tb2['opp_closer_fresh'] = np.where(
    tb2['home_away'] == 'home',
    1 - tb2['away_closer_pitched_last2days'],
    1 - tb2['home_closer_pitched_last2days']
)
print(f"  Reliever features joined: {tb2['opp_bp_high_lev_ip'].notna().sum()}/{len(tb2)}")

# Join team defense
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
tb2['opp_team_name'] = tb2['opponent'].map(TEAM_ABB_TO_NAME)
tb2 = tb2.merge(td.rename(columns={'team_name': 'opp_team_name'}),
                on=['season', 'opp_team_name'], how='left')
print(f"  Defense features joined: {tb2['outs_above_average_total'].notna().sum()}/{len(tb2)}")

# ═══════════════════════════════════════════════════════════
# STEP 1 TARGETS (on joined data)
# ═══════════════════════════════════════════════════════════
tb2['tb_zero_flag'] = (tb2['actual_tb'] == 0).astype(int)
tb2['tb_over_1_5'] = (tb2['actual_tb'] > 1.5).astype(int)
tb2['tb_over_2_5'] = (tb2['actual_tb'] > 2.5).astype(int)
tb2['tb_tail_flag'] = (tb2['actual_tb'] >= 4).astype(int)

# ═══════════════════════════════════════════════════════════
# HELPER: Bucket test with market edge
# ═══════════════════════════════════════════════════════════
def bucket_test(data, feature, target, n_buckets=5, line_filter=None):
    """Quintile bucket test. Returns DataFrame with bucket stats."""
    d = data.copy()
    if line_filter is not None:
        d = d[d['line'] == line_filter]
    d = d.dropna(subset=[feature, target])
    if len(d) < 100:
        return pd.DataFrame()

    d['bucket'] = pd.qcut(d[feature], n_buckets, labels=False, duplicates='drop')

    rows = []
    for b, grp in d.groupby('bucket'):
        feat_range = f"{grp[feature].min():.3f}-{grp[feature].max():.3f}"
        actual_rate = grp[target].mean()

        # Get implied rate for the corresponding market line
        if target == 'tb_zero_flag':
            implied = (1 - grp['implied_over']).mean() if line_filter == 0.5 else np.nan
        elif target == 'tb_over_1_5':
            implied = grp['implied_over'].mean() if line_filter == 1.5 else np.nan
        elif target == 'tb_over_2_5':
            implied = grp['implied_over'].mean() if line_filter == 2.5 else np.nan
        else:
            implied = np.nan

        roi_valid = grp.dropna(subset=['under_odds'])
        u_roi = roi_valid['under_pnl'].mean() if len(roi_valid) > 0 else np.nan

        rows.append({
            'bucket': int(b),
            'feature_range': feat_range,
            'N': len(grp),
            'actual_rate': round(actual_rate, 4),
            'implied_rate': round(implied, 4) if not np.isnan(implied) else None,
            'edge': round(actual_rate - implied, 4) if not np.isnan(implied) else None,
            'under_roi': round(u_roi, 4) if not np.isnan(u_roi) else None
        })
    return pd.DataFrame(rows)

# ═══════════════════════════════════════════════════════════
# HELPER: Logistic regression comparison
# ═══════════════════════════════════════════════════════════
def compare_models(data, baseline_feats, signal_feats, target, label=""):
    """Compare baseline vs signal vs combined logistic models."""
    d = data.dropna(subset=baseline_feats + signal_feats + [target]).copy()
    if len(d) < 200:
        return {'label': label, 'N': len(d), 'note': 'insufficient data'}

    y = d[target].values
    if y.sum() < 10 or (len(y) - y.sum()) < 10:
        return {'label': label, 'N': len(d), 'note': 'insufficient class balance'}

    scaler = StandardScaler()

    results = {}
    for name, feats in [('baseline', baseline_feats), ('signal', signal_feats), ('combined', baseline_feats + signal_feats)]:
        X = scaler.fit_transform(d[feats].values)
        lr = LogisticRegression(max_iter=1000, C=1.0)
        lr.fit(X, y)
        probs = lr.predict_proba(X)[:, 1]
        results[f'{name}_auc'] = round(roc_auc_score(y, probs), 4)
        results[f'{name}_logloss'] = round(log_loss(y, probs), 4)

    results['label'] = label
    results['N'] = len(d)
    results['auc_lift'] = round(results['combined_auc'] - results['baseline_auc'], 4)
    results['logloss_lift'] = round(results['baseline_logloss'] - results['combined_logloss'], 4)
    return results

# ═══════════════════════════════════════════════════════════
# STEP 2 — SIGNAL FAMILY A: ZERO-TB PROPENSITY
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 2 — FAMILY A: ZERO-TB PROPENSITY")
print("="*60)

family_a_results = []

# Bucket tests
for target, line in [('tb_zero_flag', 0.5), ('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5)]:
    bt = bucket_test(tb2, 'zero_tb_rate_last20', target, n_buckets=5, line_filter=line)
    if len(bt) > 0:
        bt['feature'] = 'zero_tb_rate_last20'
        bt['target'] = target
        bt['line'] = line
        family_a_results.append(bt)
        print(f"\n  {target} @ line {line} by zero_tb_rate_last20:")
        print(bt.to_string(index=False))

for target, line in [('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5)]:
    bt = bucket_test(tb2, 'tb_var_last20', target, n_buckets=5, line_filter=line)
    if len(bt) > 0:
        bt['feature'] = 'tb_var_last20'
        bt['target'] = target
        bt['line'] = line
        family_a_results.append(bt)
        print(f"\n  {target} @ line {line} by tb_var_last20:")
        print(bt.to_string(index=False))

for target, line in [('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5)]:
    bt = bucket_test(tb2, 'pct_2plus_tb_last20', target, n_buckets=5, line_filter=line)
    if len(bt) > 0:
        bt['feature'] = 'pct_2plus_tb_last20'
        bt['target'] = target
        bt['line'] = line
        family_a_results.append(bt)

family_a_df = pd.concat(family_a_results, ignore_index=True) if family_a_results else pd.DataFrame()

# Spread analysis: zero_tb_rate controlling for mean TB
print("\n  Spread analysis — zero_tb_rate after controlling for mean TB:")
d_a = tb2.dropna(subset=['zero_tb_rate_last20', 'mean_tb_last20', 'tb_over_1_5']).copy()
d_a = d_a[d_a['line'] == 1.5]
d_a['mean_tb_q'] = pd.qcut(d_a['mean_tb_last20'], 3, labels=['low','mid','high'], duplicates='drop')
d_a['zero_q'] = pd.qcut(d_a['zero_tb_rate_last20'], 3, labels=['low','mid','high'], duplicates='drop')
ct = d_a.groupby(['mean_tb_q', 'zero_q']).agg(
    N=('tb_over_1_5', 'count'),
    actual_over_1_5=('tb_over_1_5', 'mean'),
    implied_over=('implied_over', 'mean')
).reset_index()
ct['edge'] = ct['actual_over_1_5'] - ct['implied_over']
print(ct.to_string(index=False))

# ═══════════════════════════════════════════════════════════
# STEP 3 — FAMILY B: PITCHER BARREL/XBH SUPPRESSION
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 3 — FAMILY B: PITCHER XBH SUPPRESSION")
print("="*60)

family_b_results = []

for feature in ['p_barrel_rate_last5', 'p_hard_hit_rate_last5', 'p_avg_exit_velo_last5']:
    for target, line in [('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5)]:
        bt = bucket_test(tb2, feature, target, n_buckets=5, line_filter=line)
        if len(bt) > 0:
            bt['feature'] = feature
            bt['target'] = target
            bt['line'] = line
            family_b_results.append(bt)
            print(f"\n  {target} @ line {line} by {feature}:")
            print(bt.to_string(index=False))

family_b_df = pd.concat(family_b_results, ignore_index=True) if family_b_results else pd.DataFrame()

# ═══════════════════════════════════════════════════════════
# STEP 4 — FAMILY C: LINEUP PROTECTION COLLAPSE
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 4 — FAMILY C: LINEUP PROTECTION COLLAPSE")
print("="*60)

family_c_results = []

for feature in ['ondeck_iso_last20', 'ondeck_woba_proxy_last20']:
    for target, line in [('tb_zero_flag', 0.5), ('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5)]:
        bt = bucket_test(tb2, feature, target, n_buckets=5, line_filter=line)
        if len(bt) > 0:
            bt['feature'] = feature
            bt['target'] = target
            bt['line'] = line
            family_c_results.append(bt)
            print(f"\n  {target} @ line {line} by {feature}:")
            print(bt.to_string(index=False))

# Interaction: high-ISO batter x weak protection
print("\n  Interaction: high-ISO batter x weak protection")
d_c = tb2.dropna(subset=['iso_last20', 'ondeck_iso_last20', 'tb_over_1_5']).copy()
d_c = d_c[d_c['line'] == 1.5]
d_c['high_iso_batter'] = (d_c['iso_last20'] > d_c['iso_last20'].quantile(0.7)).astype(int)
d_c['weak_protection'] = (d_c['ondeck_iso_last20'] < d_c['ondeck_iso_last20'].quantile(0.3)).astype(int)
ct_c = d_c.groupby(['high_iso_batter', 'weak_protection']).agg(
    N=('tb_over_1_5', 'count'),
    actual_over_1_5=('tb_over_1_5', 'mean'),
    zero_tb_rate=('tb_zero_flag', 'mean'),
    implied_over=('implied_over', 'mean')
).reset_index()
ct_c['edge'] = ct_c['actual_over_1_5'] - ct_c['implied_over']
print(ct_c.to_string(index=False))

# Protector type test
print("\n  By protector_type:")
d_pt = tb2.dropna(subset=['protector_type']).copy()
d_pt = d_pt[d_pt['line'] == 1.5]
ct_pt = d_pt.groupby('protector_type').agg(
    N=('tb_over_1_5', 'count'),
    actual_over_1_5=('tb_over_1_5', 'mean'),
    zero_tb_rate=('tb_zero_flag', 'mean'),
    implied_over=('implied_over', 'mean')
).reset_index()
ct_pt['edge'] = ct_pt['actual_over_1_5'] - ct_pt['implied_over']
print(ct_pt.to_string(index=False))

family_c_df = pd.concat(family_c_results, ignore_index=True) if family_c_results else pd.DataFrame()

# ═══════════════════════════════════════════════════════════
# STEP 5 — FAMILY D: BULLPEN EXPOSURE QUALITY
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 5 — FAMILY D: BULLPEN EXPOSURE QUALITY")
print("="*60)

family_d_results = []

# Short starter flag: starter avg IP last 5 < 5.0
tb2['short_starter'] = (tb2['p_avg_ip_last5'] < 5.0).astype(int)
# Opposing bullpen quality: low high-leverage IP means fresh elite arms available
# opp_bp_high_lev_ip is opposing team's bullpen recent workload
# Low = fresh, available; High = fatigued

# Bucket by starter expected IP
for target, line in [('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5)]:
    bt = bucket_test(tb2, 'p_avg_ip_last5', target, n_buckets=5, line_filter=line)
    if len(bt) > 0:
        bt['feature'] = 'p_avg_ip_last5'
        bt['target'] = target
        bt['line'] = line
        family_d_results.append(bt)
        print(f"\n  {target} @ line {line} by p_avg_ip_last5 (starter durability):")
        print(bt.to_string(index=False))

# Interaction: short starter x fresh bullpen
print("\n  Interaction: short starter x fresh opposing bullpen")
d_d = tb2.dropna(subset=['p_avg_ip_last5', 'opp_bp_high_lev_ip', 'opp_closer_fresh']).copy()
d_d = d_d[d_d['line'] == 1.5]
d_d['short_starter'] = (d_d['p_avg_ip_last5'] < 5.0).astype(int)
d_d['fresh_bp'] = (d_d['opp_bp_high_lev_ip'] < d_d['opp_bp_high_lev_ip'].quantile(0.3)).astype(int)
ct_d = d_d.groupby(['short_starter', 'fresh_bp']).agg(
    N=('tb_over_1_5', 'count'),
    actual_over_1_5=('tb_over_1_5', 'mean'),
    zero_tb_rate=('tb_zero_flag', 'mean'),
    implied_over=('implied_over', 'mean')
).reset_index()
ct_d['edge'] = ct_d['actual_over_1_5'] - ct_d['implied_over']
print(ct_d.to_string(index=False))

# Bucket by opp bullpen workload
for target, line in [('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5)]:
    bt = bucket_test(tb2, 'opp_bp_high_lev_ip', target, n_buckets=5, line_filter=line)
    if len(bt) > 0:
        bt['feature'] = 'opp_bp_high_lev_ip'
        bt['target'] = target
        bt['line'] = line
        family_d_results.append(bt)

family_d_df = pd.concat(family_d_results, ignore_index=True) if family_d_results else pd.DataFrame()

# ═══════════════════════════════════════════════════════════
# STEP 6 — FAMILY E: DEFENSE AGAINST BATTER PROFILE
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 6 — FAMILY E: DEFENSE FIT")
print("="*60)

family_e_results = []

# Team defense: OAA and DRS
for feature in ['outs_above_average_total', 'defensive_runs_saved']:
    for target, line in [('tb_over_1_5', 1.5), ('tb_over_2_5', 2.5), ('tb_tail_flag', 2.5)]:
        bt = bucket_test(tb2, feature, target, n_buckets=5, line_filter=line)
        if len(bt) > 0:
            bt['feature'] = feature
            bt['target'] = target
            bt['line'] = line
            family_e_results.append(bt)
            print(f"\n  {target} @ line {line} by {feature}:")
            print(bt.to_string(index=False))

# Interaction: contact hitter (low ISO) x elite defense
print("\n  Interaction: contact hitter x elite defense")
d_e = tb2.dropna(subset=['iso_last20', 'outs_above_average_total', 'tb_over_1_5']).copy()
d_e = d_e[d_e['line'] == 1.5]
d_e['contact_hitter'] = (d_e['iso_last20'] < d_e['iso_last20'].quantile(0.3)).astype(int)
d_e['elite_defense'] = (d_e['outs_above_average_total'] > d_e['outs_above_average_total'].quantile(0.7)).astype(int)
ct_e = d_e.groupby(['contact_hitter', 'elite_defense']).agg(
    N=('tb_over_1_5', 'count'),
    actual_over_1_5=('tb_over_1_5', 'mean'),
    zero_tb_rate=('tb_zero_flag', 'mean'),
    implied_over=('implied_over', 'mean')
).reset_index()
ct_e['edge'] = ct_e['actual_over_1_5'] - ct_e['implied_over']
print(ct_e.to_string(index=False))

family_e_df = pd.concat(family_e_results, ignore_index=True) if family_e_results else pd.DataFrame()

# ═══════════════════════════════════════════════════════════
# STEP 7 — HEAD-TO-HEAD COMPARISON (Logistic Regression)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 7 — HEAD-TO-HEAD COMPARISON")
print("="*60)

baseline_feats = ['iso_last20', 'slg_last20', 'batting_order_slot']
signal_families = {
    'A: Zero-TB': ['zero_tb_rate_last20', 'tb_var_last20', 'pct_2plus_tb_last20'],
    'B: Pitcher XBH': ['p_barrel_rate_last5', 'p_hard_hit_rate_last5'],
    'C: Protection': ['ondeck_iso_last20', 'ondeck_woba_proxy_last20'],
    'D: Bullpen': ['p_avg_ip_last5', 'opp_bp_high_lev_ip'],
    'E: Defense': ['outs_above_average_total', 'defensive_runs_saved'],
}

comparison_rows = []
for target in ['tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5']:
    for family_name, signal_feats in signal_families.items():
        result = compare_models(tb2, baseline_feats, signal_feats, target,
                               label=f"{family_name} → {target}")
        comparison_rows.append(result)
        if 'baseline_auc' in result:
            print(f"  {result['label']}: N={result['N']}, baseline_AUC={result['baseline_auc']}, "
                  f"signal_AUC={result['signal_auc']}, combined_AUC={result['combined_auc']}, "
                  f"AUC_lift={result['auc_lift']}")
        else:
            print(f"  {result['label']}: {result.get('note', 'N/A')}")

comparison_df = pd.DataFrame(comparison_rows)

# ═══════════════════════════════════════════════════════════
# STEP 8 — SIGNAL RANKING
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 8 — SIGNAL RANKING")
print("="*60)

# Compute summary stats per family
ranking_rows = []
for family_name, signal_feats in signal_families.items():
    # Coverage
    coverage = tb2[signal_feats].notna().all(axis=1).mean()

    # Average AUC lift across targets
    family_comp = comparison_df[comparison_df['label'].str.startswith(family_name)]
    avg_auc_lift = family_comp['auc_lift'].mean() if 'auc_lift' in family_comp.columns else np.nan
    avg_logloss_lift = family_comp['logloss_lift'].mean() if 'logloss_lift' in family_comp.columns else np.nan

    # Determine bucket monotonicity (directional logic) from Family results
    # Check if highest bucket has highest/lowest rate consistently

    ranking_rows.append({
        'family': family_name,
        'coverage': round(coverage, 3),
        'avg_auc_lift': round(avg_auc_lift, 4) if not np.isnan(avg_auc_lift) else None,
        'avg_logloss_lift': round(avg_logloss_lift, 4) if not np.isnan(avg_logloss_lift) else None,
        'N_with_data': int(tb2[signal_feats].notna().all(axis=1).sum()),
    })

ranking_df = pd.DataFrame(ranking_rows)
ranking_df = ranking_df.sort_values('avg_auc_lift', ascending=False)
print(ranking_df.to_string(index=False))

# ═══════════════════════════════════════════════════════════
# SAVE ALL PARQUET FILES
# ═══════════════════════════════════════════════════════════
print("\nSaving output files...")
family_a_df.to_parquet(f'{OUT}/family_a_zero_tb.parquet', index=False)
family_b_df.to_parquet(f'{OUT}/family_b_xbh_suppression.parquet', index=False)
family_c_df.to_parquet(f'{OUT}/family_c_protection.parquet', index=False)
family_d_df.to_parquet(f'{OUT}/family_d_bullpen_exposure.parquet', index=False)
family_e_df.to_parquet(f'{OUT}/family_e_defense_fit.parquet', index=False)
ranking_df.to_parquet(f'{OUT}/signal_family_ranking.parquet', index=False)
comparison_df.to_parquet(f'{OUT}/logistic_comparison.parquet', index=False)

print("All parquet files saved.")

# ═══════════════════════════════════════════════════════════
# PRINT FULL RESULTS FOR REPORT GENERATION
# ═══════════════════════════════════════════════════════════
print("\n\n### REPORT DATA ###")
print("\n## RANKING TABLE ##")
print(ranking_df.to_markdown(index=False))
print("\n## COMPARISON TABLE ##")
print(comparison_df.to_markdown(index=False))
print("\n## BASELINE RATES ##")
for col in ['tb_zero_flag', 'tb_over_1_5', 'tb_over_2_5', 'tb_tail_flag']:
    print(f"  {col}: {tb2[col].mean():.4f}")
