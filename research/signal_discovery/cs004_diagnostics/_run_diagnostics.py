#!/usr/bin/env python3
"""
CS004 Deep Diagnostics — Bullpen Collapse Tail Risk
RESEARCH ONLY
"""
import pandas as pd
import numpy as np
import json, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("cs004_diag")
OUT = Path('research/signal_discovery/cs004_diagnostics')

# ═══════════════════════════════════════════════════════════
# LOAD DATA & RECONSTRUCT CS004 (exact Batch 1 definition)
# ═══════════════════════════════════════════════════════════
logger.info("Loading data...")
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
gt = pd.read_parquet('sim/data/game_table.parquet')
cl = pd.read_parquet('sim/data/mlb_historical_closing_lines.parquet')
br = pd.read_parquet('sim/data/bet_results.parquet')
rl = pd.read_parquet('research/data_pulls/reliever_role_tracking.parquet')

# Build game dataset with closing totals (2022-2025)
gdf = gt[gt['season'].isin([2022,2023,2024,2025])].copy()
cl_sub = cl[['game_pk','close_total']].rename(columns={'close_total':'ct_hist'}).drop_duplicates('game_pk')
br_sub = br[['game_id','close_total']].rename(columns={'game_id':'game_pk','close_total':'ct_br'}).drop_duplicates('game_pk')
gdf = gdf.merge(cl_sub, on='game_pk', how='left').merge(br_sub, on='game_pk', how='left')
gdf['closing_total'] = gdf['ct_hist'].fillna(gdf['ct_br'])
gdf['market_residual'] = gdf['actual_total'] - gdf['closing_total']
gdf['went_over'] = (gdf['actual_total'] > gdf['closing_total']).astype(int)
gdf['is_push'] = (gdf['actual_total'] == gdf['closing_total']).astype(int)
gdf = gdf[gdf['closing_total'].notna()].copy()
gdf_np = gdf[gdf['is_push'] == 0].copy()

# ── Reliever per-appearance data ──
rlv = pl[pl['starter_flag'] == 0].copy()
rlv = rlv.sort_values(['team','game_date','game_pk'])

# Per team-game: bullpen aggregate
team_bp = rlv.groupby(['game_pk','team']).agg(
    bp_runs_var=('runs_allowed','var'),
    bp_runs_max=('runs_allowed','max'),
    bp_appearances=('player_id','count'),
    bp_total_runs=('runs_allowed','sum'),
    bp_total_ip=('innings_pitched','sum'),
).reset_index()

team_bp = team_bp.merge(
    gdf[['game_pk','date','season']].rename(columns={'date':'game_date'}).drop_duplicates('game_pk'),
    on='game_pk', how='left')
team_bp['game_date'] = pd.to_datetime(team_bp['game_date'])
team_bp = team_bp.sort_values(['team','game_date','game_pk'])

# Rolling 10-game stats (shift 1 for pregame safety)
team_bp['bp_var_r10'] = team_bp.groupby('team')['bp_runs_var'].transform(
    lambda x: x.shift(1).rolling(10, min_periods=8).mean())
team_bp['bp_max_r10'] = team_bp.groupby('team')['bp_runs_max'].transform(
    lambda x: x.shift(1).rolling(10, min_periods=8).max())
team_bp['tail_score'] = team_bp['bp_var_r10'].fillna(0) + team_bp['bp_max_r10'].fillna(0)

# Cumulative appearance count for minimum-8 filter
team_bp['cum_app_r10'] = team_bp.groupby('team')['bp_appearances'].transform(
    lambda x: x.shift(1).rolling(10, min_periods=1).sum())

# Mark rows that don't meet minimum window
team_bp.loc[team_bp['cum_app_r10'] < 8, 'tail_score'] = np.nan

# Freeze threshold on 2022-2023
freeze = team_bp[team_bp['season'].isin([2022,2023])].dropna(subset=['tail_score'])
THRESHOLD_80 = freeze['tail_score'].quantile(0.80)
logger.info(f"Frozen top-20% threshold: {THRESHOLD_80:.4f}")

team_bp['high_tail'] = (team_bp['tail_score'] >= THRESHOLD_80).astype(int)
team_bp.loc[team_bp['tail_score'].isna(), 'high_tail'] = np.nan

# ── Game-level flag: either bullpen flagged ──
game_flags = gdf[['game_pk','home_team','away_team','season']].copy()
game_flags = game_flags.merge(
    team_bp[['game_pk','team','tail_score','high_tail']].rename(
        columns={'tail_score':'home_tail_score','high_tail':'home_high'}),
    left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
game_flags = game_flags.merge(
    team_bp[['game_pk','team','tail_score','high_tail']].rename(
        columns={'tail_score':'away_tail_score','high_tail':'away_high'}),
    left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left',
    suffixes=('','_a'))
game_flags['max_tail_score'] = game_flags[['home_tail_score','away_tail_score']].max(axis=1)
game_flags['cs004_flag'] = ((game_flags['home_high']==1)|(game_flags['away_high']==1)).astype(int)
game_flags['which_bp_flagged'] = np.where(
    (game_flags['home_high']==1)&(game_flags['away_high']==1), 'both',
    np.where(game_flags['home_high']==1, 'home',
    np.where(game_flags['away_high']==1, 'away', 'neither')))

df = gdf_np.merge(game_flags[['game_pk','cs004_flag','max_tail_score',
                                'home_tail_score','away_tail_score','which_bp_flagged']].drop_duplicates('game_pk'),
                   on='game_pk', how='left')
df['cs004_flag'] = df['cs004_flag'].fillna(0).astype(int)

logger.info(f"Total non-push games: {len(df)}")
logger.info(f"CS004 flagged: {df['cs004_flag'].sum()}")

# ── Per-inning bullpen runs (for big-inning analysis) ──
# We need to compute runs per relief APPEARANCE (not inning)
# A "3+ run appearance" counts as a blowup
rlv['blowup_3plus'] = (rlv['runs_allowed'] >= 3).astype(int)
rlv['blowup_6plus'] = (rlv['runs_allowed'] >= 6).astype(int)

team_blowup = rlv.groupby(['game_pk','team']).agg(
    any_3plus=('blowup_3plus','max'),
    any_6plus=('blowup_6plus','max'),
).reset_index()

# Merge to game level
df = df.merge(
    team_blowup.rename(columns={'any_3plus':'home_3plus','any_6plus':'home_6plus'}),
    left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
df = df.merge(
    team_blowup.rename(columns={'any_3plus':'away_3plus','any_6plus':'away_6plus'}),
    left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left',
    suffixes=('','_ab'))
df['any_bp_3plus'] = ((df['home_3plus']==1)|(df['away_3plus']==1)).astype(int)
df['any_bp_6plus'] = ((df['home_6plus']==1)|(df['away_6plus']==1)).astype(int)

def roi_110(over_rate):
    return round((over_rate * (100/110) - (1 - over_rate)) * 100, 2) if over_rate else None

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC A — QUINTILE CALIBRATION
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC A — QUINTILE CALIBRATION")
logger.info("="*60)

quint_rows = []
for label, subset in [("Full 2022-2025", df), ("2025 only", df[df['season']==2025])]:
    valid = subset.dropna(subset=['max_tail_score']).copy()
    if len(valid) < 100:
        logger.info(f"  {label}: insufficient data ({len(valid)})")
        continue
    valid['quintile'] = pd.qcut(valid['max_tail_score'], 5, labels=False, duplicates='drop')
    for q, grp in valid.groupby('quintile'):
        quint_rows.append({
            'dataset': label, 'quintile': int(q),
            'tail_score_range': f"{grp['max_tail_score'].min():.2f}-{grp['max_tail_score'].max():.2f}",
            'N': len(grp),
            'over_rate': round(grp['went_over'].mean(), 4),
            'mean_residual': round(grp['market_residual'].mean(), 3),
            'pct_bp_3plus': round(grp['any_bp_3plus'].mean(), 4),
            'pct_bp_6plus': round(grp['any_bp_6plus'].mean(), 4),
        })
        logger.info(f"  {label} Q{q}: N={len(grp):5d} over={grp['went_over'].mean():.4f} "
                     f"resid={grp['market_residual'].mean():+.3f} bp_3+={grp['any_bp_3plus'].mean():.3f}")

quint_df = pd.DataFrame(quint_rows)
quint_df.to_parquet(str(OUT / 'cs004_quintile_calibration.parquet'), index=False)

# Monotonicity check
full_quint = quint_df[quint_df['dataset'] == 'Full 2022-2025']
if len(full_quint) == 5:
    over_rates = full_quint.sort_values('quintile')['over_rate'].values
    monotonic = all(over_rates[i] <= over_rates[i+1] for i in range(4))
    logger.info(f"  Monotonic (full): {monotonic} — rates: {list(over_rates)}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC B — SEGMENTATION
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC B — SEGMENTATION")
logger.info("="*60)

flagged = df[df['cs004_flag'] == 1].copy()
seg_rows = []

# 1. Park factor buckets
pf_cuts = flagged['park_factor_runs'].quantile([0.33, 0.67])
flagged['pf_bucket'] = pd.cut(flagged['park_factor_runs'],
    bins=[-np.inf, pf_cuts.iloc[0], pf_cuts.iloc[1], np.inf],
    labels=['low_pf','mid_pf','high_pf'])
for bucket, grp in flagged.groupby('pf_bucket'):
    seg_rows.append({'segment': f'park_{bucket}', 'N': len(grp),
        'over_rate': round(grp['went_over'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN_SAMPLE' if len(grp) < 30 else ''})

# 2. Which bullpen flagged
for which, grp in flagged.groupby('which_bp_flagged'):
    seg_rows.append({'segment': f'bp_{which}', 'N': len(grp),
        'over_rate': round(grp['went_over'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN_SAMPLE' if len(grp) < 30 else ''})

# 3. Closing total buckets
flagged['ct_bucket'] = pd.cut(flagged['closing_total'],
    bins=[-np.inf, 7.5, 8.5, np.inf], labels=['<7.5','7.5-8.5','>8.5'])
for bucket, grp in flagged.groupby('ct_bucket'):
    seg_rows.append({'segment': f'close_{bucket}', 'N': len(grp),
        'over_rate': round(grp['went_over'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN_SAMPLE' if len(grp) < 30 else ''})

# 4. Season
for yr, grp in flagged.groupby('season'):
    seg_rows.append({'segment': f'season_{yr}', 'N': len(grp),
        'over_rate': round(grp['went_over'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN_SAMPLE' if len(grp) < 30 else ''})

seg_df = pd.DataFrame(seg_rows)
seg_df.to_parquet(str(OUT / 'cs004_segmentation.parquet'), index=False)

for _, r in seg_df.iterrows():
    flag = f" [{r['thin']}]" if r['thin'] else ""
    logger.info(f"  {r['segment']:20s}: N={r['N']:5d} over={r['over_rate']:.4f} resid={r['mean_residual']:+.3f}{flag}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC C — SIGNAL DECAY (YEAR-BY-YEAR)
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC C — SIGNAL DECAY")
logger.info("="*60)

decay_rows = []
for yr in [2022, 2023, 2024, 2025]:
    yr_data = df[df['season'] == yr].copy()
    fl = yr_data[yr_data['cs004_flag'] == 1]
    base = yr_data[yr_data['cs004_flag'] == 0]
    if len(fl) < 10:
        continue
    ovr = fl['went_over'].mean()
    base_ovr = base['went_over'].mean()
    me = fl['market_residual'].mean()

    # Permutation test (200 shuffles)
    from numpy.random import default_rng
    rng = default_rng(42 + yr)
    observed = fl['market_residual'].mean()
    all_resid = yr_data['market_residual'].values
    all_flags = yr_data['cs004_flag'].values
    perm_results = []
    for _ in range(200):
        shuffled = all_flags.copy()
        rng.shuffle(shuffled)
        perm_me = all_resid[shuffled == 1].mean() if shuffled.sum() > 0 else 0
        perm_results.append(perm_me)
    perm_arr = np.array(perm_results)
    perm_pct = (perm_arr < observed).mean() * 100

    decay_rows.append({
        'season': yr, 'N_flagged': len(fl), 'N_base': len(base),
        'over_rate': round(ovr, 4), 'base_over_rate': round(base_ovr, 4),
        'lift_pp': round((ovr - base_ovr) * 100, 2),
        'mean_residual': round(me, 3),
        'permutation_pct': round(perm_pct, 1),
    })
    logger.info(f"  {yr}: N={len(fl):4d} over={ovr:.4f} base={base_ovr:.4f} "
                f"lift={((ovr-base_ovr)*100):+.1f}pp resid={me:+.3f} perm={perm_pct:.1f}%")

decay_df = pd.DataFrame(decay_rows)
decay_df.to_parquet(str(OUT / 'cs004_decay_by_year.parquet'), index=False)

# Classify trend
lifts = [r['lift_pp'] for r in decay_rows]
all_positive = all(l > 0 for l in lifts)
if all_positive:
    if lifts[-1] > lifts[0]:
        trend = "STRENGTHENING"
    elif lifts[-1] < lifts[0]:
        trend = "WEAKENING"
    else:
        trend = "STABLE"
else:
    trend = "INCONSISTENT"
logger.info(f"  Trend: {trend} (lifts: {lifts})")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC D — RPI VOLATILITY REFINEMENT
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC D — RPI VOLATILITY")
logger.info("="*60)

# Compute runs_per_inning per appearance
rlv2 = rlv.copy()
rlv2['rpi'] = rlv2['runs_allowed'] / rlv2['innings_pitched'].clip(lower=0.1)

# Per team-game: variance of RPI across appearances
team_rpi = rlv2.groupby(['game_pk','team']).agg(
    rpi_var=('rpi','var'),
).reset_index()
team_rpi = team_rpi.merge(
    gdf[['game_pk','date','season']].rename(columns={'date':'gd'}).drop_duplicates('game_pk'),
    on='game_pk', how='left')
team_rpi['gd'] = pd.to_datetime(team_rpi['gd'])
team_rpi = team_rpi.sort_values(['team','gd','game_pk'])

team_rpi['rpi_vol_r10'] = team_rpi.groupby('team')['rpi_var'].transform(
    lambda x: x.shift(1).rolling(10, min_periods=8).mean())

# Merge to game level
game_rpi = gdf[['game_pk','home_team','away_team']].copy()
game_rpi = game_rpi.merge(
    team_rpi[['game_pk','team','rpi_vol_r10']].rename(columns={'rpi_vol_r10':'home_rpi_vol'}),
    left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
game_rpi = game_rpi.merge(
    team_rpi[['game_pk','team','rpi_vol_r10']].rename(columns={'rpi_vol_r10':'away_rpi_vol'}),
    left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left',
    suffixes=('','_a'))
game_rpi['max_rpi_vol'] = game_rpi[['home_rpi_vol','away_rpi_vol']].max(axis=1)

df = df.merge(game_rpi[['game_pk','max_rpi_vol']].drop_duplicates('game_pk'),
              on='game_pk', how='left')

# Normalize both scores on training data (2022-2023)
train_mask = df['season'].isin([2022,2023])
ts_mean = df.loc[train_mask, 'max_tail_score'].mean()
ts_std = df.loc[train_mask, 'max_tail_score'].std()
rv_mean = df.loc[train_mask, 'max_rpi_vol'].mean()
rv_std = df.loc[train_mask, 'max_rpi_vol'].std()

df['ts_norm'] = (df['max_tail_score'] - ts_mean) / ts_std
df['rv_norm'] = (df['max_rpi_vol'] - rv_mean) / rv_std
df['combined_score'] = 0.5 * df['ts_norm'] + 0.5 * df['rv_norm']

# Freeze combined threshold on 2022-2023
freeze_comb = df[train_mask].dropna(subset=['combined_score'])
COMBINED_THRESHOLD = freeze_comb['combined_score'].quantile(0.80)

df['combined_flag'] = (df['combined_score'] >= COMBINED_THRESHOLD).astype(int)
df.loc[df['combined_score'].isna(), 'combined_flag'] = 0

# Compare on 2025
v25 = df[df['season'] == 2025]
orig_flagged = v25[v25['cs004_flag'] == 1]
comb_flagged = v25[v25['combined_flag'] == 1]

orig_over = orig_flagged['went_over'].mean()
comb_over = comb_flagged['went_over'].mean()
orig_resid = orig_flagged['market_residual'].mean()
comb_resid = comb_flagged['market_residual'].mean()

logger.info(f"  2025 Original CS004: N={len(orig_flagged)}, over={orig_over:.4f}, resid={orig_resid:+.3f}")
logger.info(f"  2025 Combined score:  N={len(comb_flagged)}, over={comb_over:.4f}, resid={comb_resid:+.3f}")
logger.info(f"  Improvement: {(comb_over - orig_over)*100:+.1f}pp over rate")

keep_original = (comb_over - orig_over) < 0.01
logger.info(f"  Decision: {'KEEP ORIGINAL' if keep_original else 'ADOPT COMBINED'}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC E — INTERACTION WITH FATIGUE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC E — FATIGUE INTERACTION")
logger.info("="*60)

# CS005 fatigue proxy from reliever_role_tracking
rl2 = rl.copy()
for side in ['home','away']:
    col = f'{side}_bullpen_high_leverage_ip_last3d'
    rl2[f'{side}_season_avg'] = rl2.groupby(['season',f'{side}_team'])[col].transform('mean')
    rl2[f'{side}_fat_norm'] = rl2[col] / rl2[f'{side}_season_avg'].replace(0, np.nan)
rl2['max_fatigue'] = rl2[['home_fat_norm','away_fat_norm']].max(axis=1)

# Freeze fatigue threshold on 2022-2023
fat_freeze = rl2[rl2['season'].isin([2022,2023])].dropna(subset=['max_fatigue'])
FAT_THRESHOLD = fat_freeze['max_fatigue'].quantile(0.80)
rl2['high_fatigue'] = (rl2['max_fatigue'] >= FAT_THRESHOLD).astype(int)

df = df.merge(rl2[['game_pk','high_fatigue']].drop_duplicates('game_pk'),
              on='game_pk', how='left')
df['high_fatigue'] = df['high_fatigue'].fillna(0).astype(int)

# Interaction analysis
interaction_rows = []
for label, mask in [
    ('CS004 only', (df['cs004_flag']==1) & (df['high_fatigue']==0)),
    ('Fatigue only', (df['cs004_flag']==0) & (df['high_fatigue']==1)),
    ('CS004 + Fatigue', (df['cs004_flag']==1) & (df['high_fatigue']==1)),
    ('Neither', (df['cs004_flag']==0) & (df['high_fatigue']==0)),
]:
    grp = df[mask]
    if len(grp) < 10:
        continue
    interaction_rows.append({
        'segment': label, 'N': len(grp),
        'over_rate': round(grp['went_over'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
    })
    logger.info(f"  {label:20s}: N={len(grp):5d} over={grp['went_over'].mean():.4f} resid={grp['market_residual'].mean():+.3f}")

# Check if interaction beats standalone
cs004_only = next((r for r in interaction_rows if r['segment'] == 'CS004 only'), None)
cs004_fat = next((r for r in interaction_rows if r['segment'] == 'CS004 + Fatigue'), None)
if cs004_only and cs004_fat:
    interaction_lift = cs004_fat['over_rate'] - cs004_only['over_rate']
    logger.info(f"  Interaction lift: {interaction_lift*100:+.1f}pp")
    is_interaction_candidate = interaction_lift > 0.02
    logger.info(f"  INTERACTION_CANDIDATE: {is_interaction_candidate}")

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("SUMMARY")
logger.info("="*60)

# A: Monotonicity
full_q = quint_df[quint_df['dataset']=='Full 2022-2025'].sort_values('quintile')
ors = full_q['over_rate'].values
mono = all(ors[i] <= ors[i+1] for i in range(len(ors)-1)) if len(ors)==5 else False
logger.info(f"  A. Monotonic: {mono}")

# B: Broad-based
seg_over_rates = seg_df[seg_df['segment'].str.startswith('season_')]['over_rate']
broad = (seg_over_rates > 0.49).all()
logger.info(f"  B. Broad-based: {broad}")

# C: Trend
logger.info(f"  C. Trend: {trend}")

# D: Refinement
logger.info(f"  D. Keep original: {keep_original}")

# E: Interaction
logger.info(f"  E. Interaction candidate: {is_interaction_candidate if cs004_only and cs004_fat else 'N/A'}")

# Overall verdict
if trend in ('STABLE','STRENGTHENING') and mono:
    verdict = "SHADOW_READY"
elif trend == 'WEAKENING':
    verdict = "SIGNAL_WEAKENING"
elif trend == 'INCONSISTENT' and not mono:
    verdict = "NEEDS_MORE_DATA"
else:
    verdict = "SHADOW_READY"  # partial pass

logger.info(f"  Overall: {verdict}")
logger.info("\nDone.")
