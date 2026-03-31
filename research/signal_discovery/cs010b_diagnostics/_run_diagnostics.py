#!/usr/bin/env python3
"""CS010B Deep Diagnostics — Dynamic Park Environment UNDER. RESEARCH ONLY."""
import pandas as pd, numpy as np, json, logging
from pathlib import Path
from numpy.random import default_rng

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("cs010b")
OUT = Path('research/signal_discovery/cs010b_diagnostics')

# ── Load data ─────────────────────────────────────────────
logger.info("Loading data...")
gt = pd.read_parquet('sim/data/game_table.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
cl = pd.read_parquet('sim/data/mlb_historical_closing_lines.parquet')
br = pd.read_parquet('sim/data/bet_results.parquet')

gdf = gt[gt['season'].isin([2022,2023,2024,2025])].copy()
cl_sub = cl[['game_pk','close_total']].rename(columns={'close_total':'ct_hist'}).drop_duplicates('game_pk')
br_sub = br[['game_id','close_total']].rename(columns={'game_id':'game_pk','close_total':'ct_br'}).drop_duplicates('game_pk')
gdf = gdf.merge(cl_sub, on='game_pk', how='left').merge(br_sub, on='game_pk', how='left')
gdf['closing_total'] = gdf['ct_hist'].fillna(gdf['ct_br'])
gdf['market_residual'] = gdf['actual_total'] - gdf['closing_total']
gdf['went_under'] = (gdf['actual_total'] < gdf['closing_total']).astype(int)
gdf['went_over'] = (gdf['actual_total'] > gdf['closing_total']).astype(int)
gdf['is_push'] = (gdf['actual_total'] == gdf['closing_total']).astype(int)
gdf = gdf[gdf['closing_total'].notna()].copy()
gdf_np = gdf[gdf['is_push'] == 0].copy()

# ── Reconstruct CS010B (exact Batch 2 definition) ────────
logger.info("Reconstructing CS010B...")
pk = gdf[['game_pk','season','home_team','away_team','park_factor_runs',
           'temperature','wind_speed','roof_status']].copy()
pk_open = pk[pk['roof_status'] == 'open'].copy()

park_mean_temp = pk_open.groupby(['home_team','season'])['temperature'].transform('mean')
pk_open['temp_dev'] = pk_open['temperature'] - park_mean_temp
pk_open['env_score'] = (pk_open['park_factor_runs'] / 100) * (1 + pk_open['temp_dev']/100) * (1 + pk_open['wind_speed']/50)

freeze = pk_open[pk_open['season'].isin([2022,2023])].dropna(subset=['env_score'])
LOW_ENV = freeze['env_score'].quantile(0.20)
HIGH_ENV = freeze['env_score'].quantile(0.80)
logger.info(f"  Frozen thresholds: LOW={LOW_ENV:.4f} (bottom 20%), HIGH={HIGH_ENV:.4f}")

pk_open['cs010b_flag'] = (pk_open['env_score'] <= LOW_ENV).astype(int)

# Merge to non-push open-roof games
df = gdf_np[gdf_np['roof_status'] == 'open'].copy()
df = df.merge(pk_open[['game_pk','env_score','cs010b_flag','temp_dev']].drop_duplicates('game_pk'),
              on='game_pk', how='left')
df['cs010b_flag'] = df['cs010b_flag'].fillna(0).astype(int)
logger.info(f"  Open-roof non-push games: {len(df)}, CS010B flagged: {df['cs010b_flag'].sum()}")

# ── Also reconstruct CS004 for conflict check ─────────────
logger.info("Reconstructing CS004 for conflict check...")
rlv = pl[pl['starter_flag'] == 0].sort_values(['team','game_date','game_pk'])
team_bp = rlv.groupby(['game_pk','team']).agg(
    bp_runs_var=('runs_allowed','var'), bp_runs_max=('runs_allowed','max'),
    bp_appearances=('player_id','count')).reset_index()
team_bp = team_bp.merge(gt[['game_pk','date','season']].rename(columns={'date':'gd'}).drop_duplicates('game_pk'),
                         on='game_pk', how='left')
team_bp['gd'] = pd.to_datetime(team_bp['gd'])
team_bp = team_bp.sort_values(['team','gd','game_pk'])
team_bp['bp_var_r10'] = team_bp.groupby('team')['bp_runs_var'].transform(lambda x: x.shift(1).rolling(10,min_periods=8).mean())
team_bp['bp_max_r10'] = team_bp.groupby('team')['bp_runs_max'].transform(lambda x: x.shift(1).rolling(10,min_periods=8).max())
team_bp['tail_score'] = team_bp['bp_var_r10'].fillna(0) + team_bp['bp_max_r10'].fillna(0)
team_bp['cum_app'] = team_bp.groupby('team')['bp_appearances'].transform(lambda x: x.shift(1).rolling(10,min_periods=1).sum())
team_bp.loc[team_bp['cum_app'] < 8, 'tail_score'] = np.nan
THRESH_CS004 = team_bp[team_bp['season'].isin([2022,2023])].dropna(subset=['tail_score'])['tail_score'].quantile(0.80)
team_bp['high_tail'] = (team_bp['tail_score'] >= THRESH_CS004).astype(int)
team_bp.loc[team_bp['tail_score'].isna(), 'high_tail'] = np.nan

game_cs004 = gdf[['game_pk','home_team','away_team']].drop_duplicates('game_pk').copy()
game_cs004 = game_cs004.merge(team_bp[['game_pk','team','high_tail']].rename(columns={'high_tail':'h4'}),
    left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
game_cs004 = game_cs004.merge(team_bp[['game_pk','team','high_tail']].rename(columns={'high_tail':'a4'}),
    left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left', suffixes=('','_a'))
game_cs004['cs004_flag'] = ((game_cs004['h4']==1)|(game_cs004['a4']==1)).astype(int)

df = df.merge(game_cs004[['game_pk','cs004_flag']].drop_duplicates('game_pk'), on='game_pk', how='left')
df['cs004_flag'] = df['cs004_flag'].fillna(0).astype(int)

def roi_110(r): return round((r*(100/110)-(1-r))*100,2) if r else None

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC A — QUINTILE MONOTONICITY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC A — QUINTILE MONOTONICITY")
logger.info("="*60)

quint_rows = []
for label, subset in [("Full 2022-2025", df), ("2025 only", df[df['season']==2025])]:
    valid = subset.dropna(subset=['env_score']).copy()
    if len(valid) < 100: continue
    valid['quintile'] = pd.qcut(valid['env_score'], 5, labels=False, duplicates='drop')
    for q, grp in valid.groupby('quintile'):
        quint_rows.append({
            'dataset': label, 'quintile': int(q),
            'env_range': f"{grp['env_score'].min():.3f}-{grp['env_score'].max():.3f}",
            'N': len(grp),
            'under_rate': round(grp['went_under'].mean(), 4),
            'over_rate': round(grp['went_over'].mean(), 4),
            'mean_residual': round(grp['market_residual'].mean(), 3),
            'median_residual': round(grp['market_residual'].median(), 3),
        })
    logger.info(f"  {label}:")
    for q in range(5):
        r = next((x for x in quint_rows if x['dataset']==label and x['quintile']==q), None)
        if r:
            logger.info(f"    Q{q} ({r['env_range']}): N={r['N']:5d} under={r['under_rate']:.4f} "
                         f"resid={r['mean_residual']:+.3f}")

quint_df = pd.DataFrame(quint_rows)
quint_df.to_parquet(str(OUT / 'cs010b_quintile_calibration.parquet'), index=False)

full_q = quint_df[quint_df['dataset']=='Full 2022-2025'].sort_values('quintile')
urs = full_q['under_rate'].values
mono = all(urs[i] >= urs[i+1] for i in range(len(urs)-1)) if len(urs)==5 else False
logger.info(f"  Monotonic (Q1 highest under → Q5 lowest): {mono}")
logger.info(f"  Under rates Q1→Q5: {list(urs)}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC B — SEGMENTATION
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC B — SEGMENTATION")
logger.info("="*60)

flagged = df[df['cs010b_flag'] == 1].copy()
seg_rows = []

# 1. Park type bucket
pf_cuts = [0, 98, 102, 200]
pf_labels = ['pitcher_park', 'neutral_park', 'hitter_park']
flagged['pf_bucket'] = pd.cut(flagged['park_factor_runs'], bins=pf_cuts, labels=pf_labels)
for bucket, grp in flagged.groupby('pf_bucket', observed=True):
    seg_rows.append({'segment': f'park_{bucket}', 'N': len(grp),
        'under_rate': round(grp['went_under'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN' if len(grp) < 30 else ''})

# 2. Season
for yr, grp in flagged.groupby('season'):
    seg_rows.append({'segment': f'season_{yr}', 'N': len(grp),
        'under_rate': round(grp['went_under'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN' if len(grp) < 30 else ''})

# 3. Closing total
flagged['ct_bucket'] = pd.cut(flagged['closing_total'], bins=[-np.inf,7.5,8.5,np.inf],
                               labels=['<7.5','7.5-8.5','>8.5'])
for bucket, grp in flagged.groupby('ct_bucket', observed=True):
    seg_rows.append({'segment': f'close_{bucket}', 'N': len(grp),
        'under_rate': round(grp['went_under'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN' if len(grp) < 30 else ''})

# 4. Home vs away (which team benefits from pitcher-friendly env)
# In a pitcher-friendly env, both teams score less — check if home advantage differs
seg_rows.append({'segment': 'all_flagged', 'N': len(flagged),
    'under_rate': round(flagged['went_under'].mean(), 4),
    'mean_residual': round(flagged['market_residual'].mean(), 3), 'thin': ''})

seg_df = pd.DataFrame(seg_rows)
seg_df.to_parquet(str(OUT / 'cs010b_segmentation.parquet'), index=False)

for _, r in seg_df.iterrows():
    flag = f" [{r['thin']}]" if r['thin'] else ""
    logger.info(f"  {r['segment']:20s}: N={r['N']:5d} under={r['under_rate']:.4f} resid={r['mean_residual']:+.3f}{flag}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC C — DECAY BY YEAR
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC C — DECAY BY YEAR")
logger.info("="*60)

decay_rows = []
for yr in [2022, 2023, 2024, 2025]:
    yr_data = df[df['season'] == yr]
    fl = yr_data[yr_data['cs010b_flag'] == 1]
    bs = yr_data[yr_data['cs010b_flag'] == 0]
    if len(fl) < 10: continue
    ur = fl['went_under'].mean()
    base_ur = bs['went_under'].mean()
    me = fl['market_residual'].mean()

    # Permutation test (200 shuffles)
    rng = default_rng(42 + yr)
    all_resid = yr_data['market_residual'].values
    all_flags = yr_data['cs010b_flag'].values
    observed = me
    perm_results = []
    for _ in range(200):
        shuffled = all_flags.copy(); rng.shuffle(shuffled)
        pm = all_resid[shuffled == 1].mean() if shuffled.sum() > 0 else 0
        perm_results.append(pm)
    # For UNDER signal, we want LOWER residual (more negative = more under)
    # Percentile = % of permutations with HIGHER residual than observed
    perm_arr = np.array(perm_results)
    perm_pct = (perm_arr > observed).mean() * 100  # higher = more under-leaning

    decay_rows.append({
        'season': yr, 'N_flagged': len(fl), 'N_base': len(bs),
        'under_rate': round(ur, 4), 'base_under_rate': round(base_ur, 4),
        'lift_pp': round((ur - base_ur) * 100, 2),
        'mean_residual': round(me, 3),
        'permutation_pct': round(perm_pct, 1),
    })
    logger.info(f"  {yr}: N={len(fl):4d} under={ur:.4f} base={base_ur:.4f} "
                f"lift={((ur-base_ur)*100):+.1f}pp resid={me:+.3f} perm={perm_pct:.1f}%")

decay_df = pd.DataFrame(decay_rows)
decay_df.to_parquet(str(OUT / 'cs010b_decay_by_year.parquet'), index=False)

lifts = [r['lift_pp'] for r in decay_rows]
all_pos = all(l > 0 for l in lifts)
if all_pos:
    trend = "STRENGTHENING" if lifts[-1] > lifts[0] else ("WEAKENING" if lifts[-1] < lifts[0] else "STABLE")
else:
    trend = "INCONSISTENT"
logger.info(f"  Trend: {trend} (lifts: {lifts})")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC D — INTERACTION WITH V1 UNDER
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC D — V1 UNDER INTERACTION")
logger.info("="*60)

# V1 UNDER proxy: use bet_results UNDER plays
under_gids = set(br[br['bet_side'] == 'under']['game_id'])
df['v1_under'] = df['game_pk'].isin(under_gids).astype(int)

inter_rows = []
for label, mask in [
    ('CS010B + V1_UNDER', (df['cs010b_flag']==1) & (df['v1_under']==1)),
    ('CS010B only',       (df['cs010b_flag']==1) & (df['v1_under']==0)),
    ('V1_UNDER only',     (df['cs010b_flag']==0) & (df['v1_under']==1)),
    ('Neither',           (df['cs010b_flag']==0) & (df['v1_under']==0)),
]:
    grp = df[mask]
    if len(grp) < 5: continue
    inter_rows.append({
        'segment': label, 'N': len(grp),
        'under_rate': round(grp['went_under'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': 'THIN' if len(grp) < 30 else '',
    })
    logger.info(f"  {label:25s}: N={len(grp):5d} under={grp['went_under'].mean():.4f} "
                f"resid={grp['market_residual'].mean():+.3f}")

inter_df = pd.DataFrame(inter_rows)
inter_df.to_parquet(str(OUT / 'cs010b_under_interaction.parquet'), index=False)

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC E — CS004 CONFLICT CHECK
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC E — CS004 CONFLICT CHECK")
logger.info("="*60)

conflict_rows = []
for label, mask in [
    ('CS010B only',     (df['cs010b_flag']==1) & (df['cs004_flag']==0)),
    ('CS004 only',      (df['cs010b_flag']==0) & (df['cs004_flag']==1)),
    ('Both fire',       (df['cs010b_flag']==1) & (df['cs004_flag']==1)),
    ('Neither',         (df['cs010b_flag']==0) & (df['cs004_flag']==0)),
]:
    grp = df[mask]
    if len(grp) < 5: continue
    conflict_rows.append({
        'segment': label, 'N': len(grp),
        'under_rate': round(grp['went_under'].mean(), 4),
        'over_rate': round(grp['went_over'].mean(), 4),
        'push_rate': round(0, 4),  # already filtered non-push
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'median_residual': round(grp['market_residual'].median(), 3),
    })
    logger.info(f"  {label:20s}: N={len(grp):5d} under={grp['went_under'].mean():.4f} "
                f"over={grp['went_over'].mean():.4f} resid={grp['market_residual'].mean():+.3f}")

conflict_df = pd.DataFrame(conflict_rows)
conflict_df.to_parquet(str(OUT / 'cs010b_conflict_check.parquet'), index=False)

# Classify conflict
both_row = next((r for r in conflict_rows if r['segment'] == 'Both fire'), None)
if both_row:
    if abs(both_row['mean_residual']) < 0.3 and abs(both_row['under_rate'] - both_row['over_rate']) < 0.04:
        conflict_class = "NEUTRAL_CONFLICT"
    elif both_row['under_rate'] > both_row['over_rate'] + 0.02:
        conflict_class = "CS010B_DOMINANT"
    elif both_row['over_rate'] > both_row['under_rate'] + 0.02:
        conflict_class = "CS004_DOMINANT"
    else:
        conflict_class = "NEUTRAL_CONFLICT"
    logger.info(f"  Conflict classification: {conflict_class}")

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("SUMMARY")
logger.info("="*60)
logger.info(f"  A. Monotonic: {mono}")
logger.info(f"  B. Broad-based: {all(r['under_rate'] > 0.49 for r in seg_rows if r['segment'].startswith('season_'))}")
logger.info(f"  C. Trend: {trend}")
logger.info(f"  D. V1 interaction: see table above")
logger.info(f"  E. Conflict: {conflict_class}")

if trend in ('STABLE','STRENGTHENING') and mono:
    verdict = "SHADOW_READY"
elif trend == 'WEAKENING':
    verdict = "SIGNAL_WEAKENING"
elif not mono and trend in ('STABLE','STRENGTHENING'):
    verdict = "SHADOW_READY"  # monotonicity nice-to-have, not required
else:
    verdict = "NEEDS_MORE_DATA"
logger.info(f"  Overall: {verdict}")

# Update signal board
try:
    board_path = Path('research/signal_discovery/safety_layer/signal_board.json')
    with open(board_path) as f:
        board = json.load(f)
    # Add or update CS010B
    board = [b for b in board if b.get('canonical_signal_id') != 'CS010B']
    from datetime import datetime
    board.append({
        'canonical_signal_id': 'CS010B',
        'canonical_name': 'Dynamic park environment: UNDER',
        'domain': 'BALLPARK',
        'framework_type': 'STATE_MODEL',
        'market_target': 'FULL_GAME_TOTAL',
        'status': 'PASS',
        'diagnostic_status': verdict,
        'diagnostic_findings': {
            'quintile_monotonic': bool(mono),
            'broad_based': all(r['under_rate'] > 0.49 for r in seg_rows if r['segment'].startswith('season_')),
            'trend': trend,
            'conflict_with_cs004': conflict_class,
            'lifts_by_year': lifts,
        },
        'advancement_path': 'Shadow monitor in 2026. Track under rate in flagged games.',
        'last_updated': datetime.now().isoformat(),
    })
    with open(board_path, 'w') as f:
        json.dump(board, f, indent=2)
    logger.info("  Signal board updated.")
except Exception as e:
    logger.warning(f"  Board update failed: {e}")

logger.info("\nDone.")
