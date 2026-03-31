#!/usr/bin/env python3
"""CS013 Deep Diagnostics — Bullpen Blowup State Model. RESEARCH ONLY."""
import pandas as pd, numpy as np, json, logging
from pathlib import Path
from numpy.random import default_rng
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("cs013")
OUT = Path('research/signal_discovery/cs013_diagnostics')

# ── Load data ─────────────────────────────────────────────
logger.info("Loading data...")
gt = pd.read_parquet('sim/data/game_table.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
cl = pd.read_parquet('sim/data/mlb_historical_closing_lines.parquet')
br = pd.read_parquet('sim/data/bet_results.parquet')

gdf = gt[gt['season'].isin([2022,2023,2024,2025])].copy()
cl_sub = cl[['game_pk','close_total']].rename(columns={'close_total':'ct_h'}).drop_duplicates('game_pk')
br_sub = br[['game_id','close_total']].rename(columns={'game_id':'game_pk','close_total':'ct_b'}).drop_duplicates('game_pk')
gdf = gdf.merge(cl_sub,on='game_pk',how='left').merge(br_sub,on='game_pk',how='left')
gdf['closing_total'] = gdf['ct_h'].fillna(gdf['ct_b'])
gdf['market_residual'] = gdf['actual_total'] - gdf['closing_total']
gdf['went_over'] = (gdf['actual_total'] > gdf['closing_total']).astype(int)
gdf['went_under'] = (gdf['actual_total'] < gdf['closing_total']).astype(int)
gdf['is_push'] = (gdf['actual_total'] == gdf['closing_total']).astype(int)
gdf = gdf[gdf['closing_total'].notna()].copy()
gdf_np = gdf[gdf['is_push']==0].copy()

# ── Reconstruct CS013 with degraded count ─────────────────
logger.info("Reconstructing CS013...")
rlv = pl[pl['starter_flag']==0].sort_values(['player_id','game_date','game_pk']).copy()
rlv['rpa'] = rlv['runs_allowed']
rlv['season_rpa'] = rlv.groupby(['player_id','season'])['rpa'].transform(
    lambda x: x.shift(1).expanding(min_periods=5).mean())
rlv['degraded_app'] = ((rlv['rpa'] > 1.5 * rlv['season_rpa']) & rlv['season_rpa'].notna()).astype(int)
rlv['degraded_count5'] = rlv.groupby('player_id')['degraded_app'].transform(
    lambda x: x.shift(1).rolling(5,min_periods=3).sum())
rlv['reliever_degraded'] = (rlv['degraded_count5'] >= 2).astype(int)

# Per team-game: count degraded relievers
team_deg = rlv.groupby(['game_pk','team']).agg(
    n_degraded=('reliever_degraded','sum'),
    n_relievers=('player_id','count')).reset_index()

# Game level: get home/away degraded counts
game13 = gdf[['game_pk','home_team','away_team','season']].drop_duplicates('game_pk').copy()
game13 = game13.merge(team_deg[['game_pk','team','n_degraded']].rename(columns={'n_degraded':'h_deg'}),
    left_on=['game_pk','home_team'],right_on=['game_pk','team'],how='left')
game13 = game13.merge(team_deg[['game_pk','team','n_degraded']].rename(columns={'n_degraded':'a_deg'}),
    left_on=['game_pk','away_team'],right_on=['game_pk','team'],how='left',suffixes=('','_a'))
game13['h_deg'] = game13['h_deg'].fillna(0).astype(int)
game13['a_deg'] = game13['a_deg'].fillna(0).astype(int)
game13['max_deg'] = game13[['h_deg','a_deg']].max(axis=1)
game13['total_deg'] = game13['h_deg'] + game13['a_deg']
game13['cs013_flag'] = (game13['max_deg'] >= 2).astype(int)
game13['which_bp'] = np.where((game13['h_deg']>=2)&(game13['a_deg']>=2),'both',
    np.where(game13['h_deg']>=2,'home',np.where(game13['a_deg']>=2,'away','neither')))

df = gdf_np.merge(game13[['game_pk','cs013_flag','max_deg','total_deg','h_deg','a_deg','which_bp']].drop_duplicates('game_pk'),
                   on='game_pk',how='left')
df['cs013_flag'] = df['cs013_flag'].fillna(0).astype(int)
df['max_deg'] = df['max_deg'].fillna(0).astype(int)
logger.info(f"  Total non-push: {len(df)}, CS013 flagged: {df['cs013_flag'].sum()}")

# ── Also reconstruct CS004 for interaction ────────────────
logger.info("Reconstructing CS004...")
team_bp = rlv.groupby(['game_pk','team']).agg(
    bp_runs_var=('runs_allowed','var'),bp_runs_max=('runs_allowed','max'),
    bp_apps=('player_id','count')).reset_index()
team_bp = team_bp.merge(gt[['game_pk','date','season']].rename(columns={'date':'gd'}).drop_duplicates('game_pk'),
                         on='game_pk',how='left')
team_bp['gd'] = pd.to_datetime(team_bp['gd'])
team_bp = team_bp.sort_values(['team','gd','game_pk'])
team_bp['var_r10'] = team_bp.groupby('team')['bp_runs_var'].transform(lambda x: x.shift(1).rolling(10,min_periods=8).mean())
team_bp['max_r10'] = team_bp.groupby('team')['bp_runs_max'].transform(lambda x: x.shift(1).rolling(10,min_periods=8).max())
team_bp['tail'] = team_bp['var_r10'].fillna(0) + team_bp['max_r10'].fillna(0)
team_bp['cum'] = team_bp.groupby('team')['bp_apps'].transform(lambda x: x.shift(1).rolling(10,min_periods=1).sum())
team_bp.loc[team_bp['cum']<8,'tail'] = np.nan
T4 = team_bp[team_bp['season'].isin([2022,2023])].dropna(subset=['tail'])['tail'].quantile(0.80)
team_bp['cs004'] = (team_bp['tail'] >= T4).astype(int)
team_bp.loc[team_bp['tail'].isna(),'cs004'] = np.nan
g4 = gdf[['game_pk','home_team','away_team']].drop_duplicates('game_pk').copy()
g4 = g4.merge(team_bp[['game_pk','team','cs004']].rename(columns={'cs004':'h4'}),
    left_on=['game_pk','home_team'],right_on=['game_pk','team'],how='left')
g4 = g4.merge(team_bp[['game_pk','team','cs004']].rename(columns={'cs004':'a4'}),
    left_on=['game_pk','away_team'],right_on=['game_pk','team'],how='left',suffixes=('','_a'))
g4['cs004_flag'] = ((g4['h4']==1)|(g4['a4']==1)).astype(int)
df = df.merge(g4[['game_pk','cs004_flag']].drop_duplicates('game_pk'),on='game_pk',how='left')
df['cs004_flag'] = df['cs004_flag'].fillna(0).astype(int)

# ── Bullpen runs allowed per game (for blowup rates) ─────
bp_game_runs = rlv.groupby(['game_pk','team'])['runs_allowed'].sum().reset_index().rename(columns={'runs_allowed':'bp_runs'})
for side,tc in [('home','home_team'),('away','away_team')]:
    df = df.merge(bp_game_runs.rename(columns={'bp_runs':f'{side}_bp_runs'}),
        left_on=['game_pk',tc],right_on=['game_pk','team'],how='left')
df['max_bp_runs'] = df[['home_bp_runs','away_bp_runs']].max(axis=1)

def roi_110(r): return round((r*(100/110)-(1-r))*100,2) if r and not np.isnan(r) else None

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC A — SEVERITY MONOTONICITY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC A — SEVERITY MONOTONICITY")
logger.info("="*60)

sev_rows = []
for label, subset in [("Full 2022-2025", df), ("2025 only", df[df['season']==2025])]:
    for count in [0, 1, 2, 3]:
        if count < 3:
            grp = subset[subset['max_deg']==count]
        else:
            grp = subset[subset['max_deg']>=3]
        if len(grp) < 10: continue
        ovr = grp['went_over'].mean()
        me = grp['market_residual'].mean()
        bp3 = (grp['max_bp_runs']>=3).mean() if grp['max_bp_runs'].notna().any() else None
        bp5 = (grp['max_bp_runs']>=5).mean() if grp['max_bp_runs'].notna().any() else None
        sev_rows.append({
            'dataset':label,'degraded_count':f'{count}+' if count==3 else str(count),
            'N':len(grp),'over_rate':round(ovr,4),'mean_residual':round(me,3),
            'roi_110':roi_110(ovr),
            'pct_bp_3plus_runs':round(bp3,4) if bp3 else None,
            'pct_bp_5plus_runs':round(bp5,4) if bp5 else None,
        })
        logger.info(f"  {label} deg={count}{'+'if count==3 else ''}: N={len(grp):5d} over={ovr:.4f} "
                     f"resid={me:+.3f} ROI={roi_110(ovr)}% bp3+={bp3:.3f}" if bp3 else
                     f"  {label} deg={count}: N={len(grp):5d} over={ovr:.4f} resid={me:+.3f}")

sev_df = pd.DataFrame(sev_rows)
sev_df.to_parquet(str(OUT/'cs013_severity_calibration.parquet'),index=False)

full_sev = sev_df[sev_df['dataset']=='Full 2022-2025'].sort_values('degraded_count')
ors = full_sev['over_rate'].values
mono = all(ors[i] <= ors[i+1] for i in range(len(ors)-1))
logger.info(f"  Monotonic: {mono} — rates: {list(ors)}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC B — SEGMENTATION
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC B — SEGMENTATION")
logger.info("="*60)

flagged = df[df['cs013_flag']==1].copy()
seg_rows = []

# 1. Which bullpen
for w, grp in flagged.groupby('which_bp'):
    seg_rows.append({'segment':f'bp_{w}','N':len(grp),'over_rate':round(grp['went_over'].mean(),4),
        'mean_residual':round(grp['market_residual'].mean(),3),'roi':roi_110(grp['went_over'].mean()),
        'thin':'THIN' if len(grp)<30 else ''})

# 2. Closing total
flagged['ct_bkt'] = pd.cut(flagged['closing_total'],bins=[-np.inf,7.5,8.5,np.inf],labels=['<7.5','7.5-8.5','>8.5'])
for bkt, grp in flagged.groupby('ct_bkt',observed=True):
    seg_rows.append({'segment':f'close_{bkt}','N':len(grp),'over_rate':round(grp['went_over'].mean(),4),
        'mean_residual':round(grp['market_residual'].mean(),3),'roi':roi_110(grp['went_over'].mean()),'thin':''})

# 3. Season
for yr, grp in flagged.groupby('season'):
    seg_rows.append({'segment':f'season_{yr}','N':len(grp),'over_rate':round(grp['went_over'].mean(),4),
        'mean_residual':round(grp['market_residual'].mean(),3),'roi':roi_110(grp['went_over'].mean()),'thin':''})

# 4. Park factor
pf_cuts = [0,98,102,200]
flagged['pf_bkt'] = pd.cut(flagged['park_factor_runs'],bins=pf_cuts,labels=['pitcher','neutral','hitter'])
for bkt, grp in flagged.groupby('pf_bkt',observed=True):
    seg_rows.append({'segment':f'park_{bkt}','N':len(grp),'over_rate':round(grp['went_over'].mean(),4),
        'mean_residual':round(grp['market_residual'].mean(),3),'roi':roi_110(grp['went_over'].mean()),'thin':''})

seg_df = pd.DataFrame(seg_rows)
seg_df.to_parquet(str(OUT/'cs013_segmentation.parquet'),index=False)
for _,r in seg_df.iterrows():
    t = f" [{r['thin']}]" if r['thin'] else ""
    logger.info(f"  {r['segment']:20s}: N={r['N']:5d} over={r['over_rate']:.4f} resid={r['mean_residual']:+.3f} ROI={r['roi']}%{t}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC C — DECAY + YEAR_DOMINANT
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC C — DECAY BY YEAR")
logger.info("="*60)

decay_rows = []
for yr in [2022,2023,2024,2025]:
    yd = df[df['season']==yr]
    fl = yd[yd['cs013_flag']==1]; bs = yd[yd['cs013_flag']==0]
    if len(fl)<10: continue
    ovr = fl['went_over'].mean(); b_ovr = bs['went_over'].mean()
    me = fl['market_residual'].mean(); b_me = bs['market_residual'].mean()
    # Permutation
    rng = default_rng(42+yr)
    all_r = yd['market_residual'].values; all_f = yd['cs013_flag'].values
    perm = []
    for _ in range(200):
        sh = all_f.copy(); rng.shuffle(sh)
        perm.append(all_r[sh==1].mean() if sh.sum()>0 else 0)
    perm_arr = np.array(perm)
    perm_pct = (perm_arr < me).mean()*100  # higher = more OVER
    # Contribution to total residual improvement
    contrib = (me - b_me) * len(fl)
    decay_rows.append({'season':yr,'N':len(fl),'over_rate':round(ovr,4),'base_over':round(b_ovr,4),
        'lift_pp':round((ovr-b_ovr)*100,2),'mean_residual':round(me,3),'base_residual':round(b_me,3),
        'roi':roi_110(ovr),'perm_pct':round(perm_pct,1),'residual_contribution':round(contrib,1)})
    logger.info(f"  {yr}: N={len(fl):4d} over={ovr:.4f} base={b_ovr:.4f} lift={((ovr-b_ovr)*100):+.1f}pp "
                f"resid={me:+.3f} ROI={roi_110(ovr)}% perm={perm_pct:.1f}%")

decay_df = pd.DataFrame(decay_rows)
decay_df.to_parquet(str(OUT/'cs013_decay_by_year.parquet'),index=False)

lifts = [r['lift_pp'] for r in decay_rows]
all_pos = all(l>0 for l in lifts)
if all_pos:
    trend = "STRENGTHENING" if lifts[-1]>lifts[0] else ("WEAKENING" if lifts[-1]<lifts[0] else "STABLE")
else:
    trend = "INCONSISTENT"
logger.info(f"  Trend: {trend} (lifts: {lifts})")

# Year dominant test
total_contrib = sum(abs(r['residual_contribution']) for r in decay_rows)
for r in decay_rows:
    pct = abs(r['residual_contribution'])/total_contrib*100 if total_contrib>0 else 0
    r['contrib_pct'] = round(pct,1)
    logger.info(f"  {r['season']}: contribution={r['residual_contribution']:.1f} ({pct:.1f}%)")

dominant = any(r['contrib_pct']>60 for r in decay_rows)
dominant_yr = max(decay_rows, key=lambda r: r['contrib_pct'])['season'] if dominant else None
logger.info(f"  YEAR_DOMINANT: {dominant}" + (f" (season {dominant_yr})" if dominant else ""))

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC D — CS004 INTERACTION
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC D — CS004 INTERACTION")
logger.info("="*60)

inter_rows = []
for label, mask in [
    ('Neither',      (df['cs013_flag']==0)&(df['cs004_flag']==0)),
    ('CS004 only',   (df['cs013_flag']==0)&(df['cs004_flag']==1)),
    ('CS013 only',   (df['cs013_flag']==1)&(df['cs004_flag']==0)),
    ('Both',         (df['cs013_flag']==1)&(df['cs004_flag']==1)),
]:
    grp = df[mask]
    if len(grp)<5: continue
    ovr = grp['went_over'].mean(); me = grp['market_residual'].mean()
    inter_rows.append({'segment':label,'N':len(grp),'over_rate':round(ovr,4),
        'mean_residual':round(me,3),'roi':roi_110(ovr)})
    logger.info(f"  {label:15s}: N={len(grp):5d} over={ovr:.4f} resid={me:+.3f} ROI={roi_110(ovr)}%")

inter_df = pd.DataFrame(inter_rows)
inter_df.to_parquet(str(OUT/'cs013_cs004_interaction.parquet'),index=False)

# Classify
cs13_only = next((r for r in inter_rows if r['segment']=='CS013 only'),{})
cs04_only = next((r for r in inter_rows if r['segment']=='CS004 only'),{})
both_r = next((r for r in inter_rows if r['segment']=='Both'),{})
if both_r.get('over_rate',0) > max(cs13_only.get('over_rate',0),cs04_only.get('over_rate',0)):
    pair_class = "ADDITIVE_PAIR"
elif cs13_only.get('over_rate',0) > cs04_only.get('over_rate',0) + 0.02:
    pair_class = "CS013_DOMINANT"
else:
    pair_class = "REDUNDANT_PAIR"
logger.info(f"  Classification: {pair_class}")

# ═══════════════════════════════════════════════════════════
# DIAGNOSTIC E — UNDER STACK INTERACTION
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("DIAGNOSTIC E — UNDER INTERACTION")
logger.info("="*60)

under_gids = set(br[br['bet_side']=='under']['game_id'])
df['v1_under'] = df['game_pk'].isin(under_gids).astype(int)

und_rows = []
for label, mask in [
    ('UNDER + CS013',    (df['v1_under']==1)&(df['cs013_flag']==1)),
    ('UNDER no CS013',   (df['v1_under']==1)&(df['cs013_flag']==0)),
    ('CS013 no UNDER',   (df['v1_under']==0)&(df['cs013_flag']==1)),
    ('Neither',          (df['v1_under']==0)&(df['cs013_flag']==0)),
]:
    grp = df[mask]
    if len(grp)<5: continue
    ur = grp['went_under'].mean(); me = grp['market_residual'].mean()
    und_rows.append({'segment':label,'N':len(grp),'under_rate':round(ur,4),
        'mean_residual':round(me,3)})
    logger.info(f"  {label:20s}: N={len(grp):5d} under={ur:.4f} resid={me:+.3f}")

und_df = pd.DataFrame(und_rows)
und_df.to_parquet(str(OUT/'cs013_under_interaction.parquet'),index=False)

# Caution classification
u_with = next((r for r in und_rows if r['segment']=='UNDER + CS013'),{})
u_without = next((r for r in und_rows if r['segment']=='UNDER no CS013'),{})
delta_ur = (u_with.get('under_rate',0.5) - u_without.get('under_rate',0.5)) * 100
logger.info(f"  UNDER win rate delta when CS013 active: {delta_ur:+.1f}pp")
if delta_ur < -2:
    caution = "GENERAL_UNDER_CAUTION_FLAG"
elif delta_ur < -1:
    caution = "CONTEXT_SPECIFIC_CAUTION_FLAG"
else:
    caution = "NO_EFFECT"
logger.info(f"  Classification: {caution}")

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("SUMMARY")
logger.info("="*60)

broad = all(r['over_rate']>0.50 for r in seg_rows if r['segment'].startswith('season_'))
logger.info(f"  A. Monotonic: {mono}")
logger.info(f"  B. Broad-based (all seasons > 50% over): {broad}")
logger.info(f"  C. Trend: {trend}, Year dominant: {dominant}")
logger.info(f"  D. CS004 interaction: {pair_class}")
logger.info(f"  E. Under caution: {caution}")

if trend in ('STABLE','STRENGTHENING') and mono and not dominant:
    if pair_class == 'CS013_DOMINANT':
        verdict = "SHADOW_READY_REPLACE_CS004"
    else:
        verdict = "SHADOW_READY"
elif trend == 'INCONSISTENT' or dominant:
    verdict = "NEEDS_MORE_DATA"
else:
    verdict = "SHADOW_READY"

logger.info(f"  Overall: {verdict}")

# Update board
try:
    bp = Path('research/signal_discovery/safety_layer/signal_board.json')
    with open(bp) as f: board = json.load(f)
    board = [b for b in board if b.get('canonical_signal_id')!='CS013']
    board.append({
        'canonical_signal_id':'CS013','canonical_name':'Bullpen blowup tail risk state model',
        'domain':'BULLPEN','framework_type':'STATE_MODEL','market_target':'FULL_GAME_TOTAL',
        'status':'PASS','diagnostic_status':verdict,
        'diagnostic_findings':{
            'monotonic':bool(mono),'broad_based':broad,'trend':trend,
            'year_dominant':dominant,'pair_class':pair_class,'under_caution':caution,
            'lifts_by_year':lifts,'permutations_by_year':[r['perm_pct'] for r in decay_rows],
        },
        'advancement_path':'Shadow monitor in 2026. '+
            ('Consider replacing CS004.' if 'REPLACE' in verdict else 'Track alongside CS004.'),
        'last_updated':datetime.now().isoformat(),
    })
    with open(bp,'w') as f: json.dump(board,f,indent=2)
    logger.info("  Board updated.")
except Exception as e:
    logger.warning(f"  Board update failed: {e}")

logger.info("\nDone.")
