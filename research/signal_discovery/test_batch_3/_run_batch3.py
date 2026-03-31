#!/usr/bin/env python3
"""Test Batch 3 — CS013-CS018 through the safety layer. RESEARCH ONLY."""
import sys, json, logging, os, glob
import pandas as pd, numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("batch3")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "safety_layer"))
from signal_tester import (run_signal_test, get_registered_hypothesis, TRAIN_SEASONS,
                            log_test_result, update_board)

OUT = Path('research/signal_discovery/test_batch_3')

# ── Load common data ─────────────────────────────────────
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
logger.info(f"  Games: {len(gdf)}, non-push: {len(gdf_np)}")

batch = {}
def roi_110(r): return round((r*(100/110)-(1-r))*100,2) if r else None

def run_std(sid, df, flag_col, direction):
    hyp = get_registered_hypothesis(sid)
    hit = 'went_over' if direction=='OVER' else 'went_under'
    def stats(d):
        f=d[d[flag_col]==1]; n=len(f)
        if n==0: return 0,None,None,None,False
        r=f[hit].mean(); return n,r,f['market_residual'].mean(),roi_110(r),r>0.50
    tr_n,tr_r,tr_me,tr_roi,_=stats(df[df['season'].isin(TRAIN_SEASONS)])
    v4_n,v4_r,v4_me,v4_roi,v4_pos=stats(df[df['season']==2024])
    v5_n,v5_r,v5_me,v5_roi,v5_pos=stats(df[df['season']==2025])
    logger.info(f"  Train: N={tr_n}, rate={tr_r:.4f}, ROI={tr_roi}%" if tr_r else "  Train: insuff")
    logger.info(f"  V2025: N={v5_n}, rate={v5_r:.4f}, ROI={v5_roi}%, pos={v5_pos}" if v5_r else "  V2025: insuff")
    def mfn(sig,out):
        m=sig==1
        return out[m].mean() if m.sum()>0 else 0.5
    res=run_signal_test(sid,df[flag_col].values,df[hit].values,mfn,df['season'].values,
        train_n=tr_n,train_under_rate=(1-tr_r if direction=='OVER' else tr_r) if tr_r else None,train_roi=tr_roi,
        val_2024_n=v4_n,val_2024_under_rate=(1-v4_r if direction=='OVER' else v4_r) if v4_r else None,
        val_2024_roi=v4_roi,val_2024_positive=v4_pos,
        val_2025_n=v5_n,val_2025_under_rate=(1-v5_r if direction=='OVER' else v5_r) if v5_r else None,
        val_2025_roi=v5_roi,val_2025_positive=v5_pos)
    res['_dir']=direction; res['_rate_v25']=v5_r
    return res

# ═══════════════════════════════════════════════════════════
# CS013 — BULLPEN BLOWUP STATE MODEL
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS013 — BULLPEN BLOWUP STATE MODEL")
logger.info("="*60)
try:
    rlv = pl[pl['starter_flag']==0].sort_values(['player_id','game_date','game_pk']).copy()
    rlv['rpa'] = rlv['runs_allowed']
    # Season baseline per reliever
    rlv['season_rpa'] = rlv.groupby(['player_id','season'])['rpa'].transform(
        lambda x: x.shift(1).expanding(min_periods=5).mean())
    # Trailing 5 appearances
    rlv['trail5_rpa'] = rlv.groupby('player_id')['rpa'].transform(
        lambda x: x.shift(1).rolling(5,min_periods=3).mean())
    # Degraded: trail5 > 1.5x season baseline in 2+ of last 5
    rlv['degraded_app'] = ((rlv['rpa'] > 1.5 * rlv['season_rpa']) & rlv['season_rpa'].notna()).astype(int)
    rlv['degraded_count5'] = rlv.groupby('player_id')['degraded_app'].transform(
        lambda x: x.shift(1).rolling(5,min_periods=3).sum())
    rlv['reliever_degraded'] = (rlv['degraded_count5'] >= 2).astype(int)
    # Per team-game: count degraded relievers
    rlv_game = rlv.merge(gt[['game_pk','date','season']].rename(columns={'date':'gd'}).drop_duplicates('game_pk'),
                          on='game_pk',how='left')
    team_deg = rlv_game.groupby(['game_pk','team']).agg(
        n_degraded=('reliever_degraded','sum'),n_relievers=('player_id','count')).reset_index()
    team_deg['bp_degraded'] = (team_deg['n_degraded'] >= 2).astype(int)
    # Game level
    game13 = gdf[['game_pk','home_team','away_team']].drop_duplicates('game_pk').copy()
    game13 = game13.merge(team_deg[['game_pk','team','bp_degraded']].rename(columns={'bp_degraded':'h_deg'}),
        left_on=['game_pk','home_team'],right_on=['game_pk','team'],how='left')
    game13 = game13.merge(team_deg[['game_pk','team','bp_degraded']].rename(columns={'bp_degraded':'a_deg'}),
        left_on=['game_pk','away_team'],right_on=['game_pk','team'],how='left',suffixes=('','_a'))
    game13['cs013_flag'] = ((game13['h_deg']==1)|(game13['a_deg']==1)).astype(int)
    df13 = gdf_np.merge(game13[['game_pk','cs013_flag']].drop_duplicates('game_pk'),on='game_pk',how='left')
    df13['cs013_flag'] = df13['cs013_flag'].fillna(0).astype(int)
    logger.info(f"  CS013 flagged: {df13['cs013_flag'].sum()}")
    batch['CS013'] = run_std('CS013',df13,'cs013_flag','OVER')
    logger.info(f"  CS013 VERDICT: {batch['CS013']['verdict']}")
except Exception as e:
    logger.error(f"  CS013 FAILED: {e}")
    batch['CS013'] = {'verdict':'ERROR','error':str(e)}

# ═══════════════════════════════════════════════════════════
# CS014A/B — UMPIRE ZONE REGIME
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS014A/B — UMPIRE ZONE REGIME")
logger.info("="*60)
try:
    ump = pd.read_parquet('research/signal_discovery/c041_umpire_zone_metrics.parquet')
    df14 = gdf_np.merge(ump[['game_pk','tight_zone_flag','loose_zone_flag']].drop_duplicates('game_pk'),
                         on='game_pk',how='left')
    df14['tight_zone_flag'] = df14['tight_zone_flag'].fillna(0).astype(int)
    df14['loose_zone_flag'] = df14['loose_zone_flag'].fillna(0).astype(int)
    logger.info(f"  Tight: {df14['tight_zone_flag'].sum()}, Loose: {df14['loose_zone_flag'].sum()}")
    batch['CS014A'] = run_std('CS014A',df14,'tight_zone_flag','UNDER')
    logger.info(f"  CS014A VERDICT: {batch['CS014A']['verdict']}")
    batch['CS014B'] = run_std('CS014B',df14,'loose_zone_flag','OVER')
    logger.info(f"  CS014B VERDICT: {batch['CS014B']['verdict']}")
except Exception as e:
    logger.error(f"  CS014 FAILED: {e}")
    batch['CS014A'] = batch['CS014B'] = {'verdict':'ERROR','error':str(e)}

# ═══════════════════════════════════════════════════════════
# CS015 — CROSS-MARKET PROP/TOTAL ARBITRAGE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS015 — CROSS-MARKET PROP/TOTAL")
logger.info("="*60)
try:
    # Check for K prop data
    kprop_files = glob.glob('research/kprop/*.parquet') + glob.glob('research/mlb_props/**/strikeout*.parquet',recursive=True)
    if not kprop_files:
        raise FileNotFoundError("No K prop parquet files found")
    logger.info(f"  K prop files: {kprop_files}")
    # If we get here, try to load
    kdf = pd.read_parquet(kprop_files[0])
    logger.info(f"  K prop data: {len(kdf)} rows, cols={list(kdf.columns)[:10]}")
except FileNotFoundError:
    logger.info("  CS015: DATA_GAP — K prop data not available")
    batch['CS015'] = {'canonical_signal_id':'CS015','verdict':'DATA_GAP',
        'suspect_flags':['DATA_GAP: SP K prop odds not available locally']}
    log_test_result({'canonical_signal_id':'CS015','test_date':pd.Timestamp.now().isoformat(),
        'registered_hypothesis_used':True,'thresholds_match_registered':True,
        'verdict':'DATA_GAP','suspect_flags':['DATA_GAP']})
except Exception as e:
    logger.error(f"  CS015 FAILED: {e}")
    batch['CS015'] = {'verdict':'ERROR','error':str(e)}

# ═══════════════════════════════════════════════════════════
# CS016A/B — PITCHER REPERTOIRE MIX CHANGE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS016A/B — PITCHER REPERTOIRE MIX CHANGE")
logger.info("="*60)
try:
    # Load statcast chunks for pitch_type per game
    chunks = sorted(glob.glob('mlb/props/data/statcast_chunk_*.parquet'))
    frames = []
    for f in chunks:
        try:
            d = pd.read_parquet(f, columns=['game_pk','pitcher','pitch_type','game_date'])
            frames.append(d)
        except: pass
    sc = pd.concat(frames, ignore_index=True)
    sc = sc.dropna(subset=['pitch_type'])
    # Join to starters only
    starters = pl[pl['starter_flag']==1][['game_pk','player_id','team','season','game_date']].copy()
    sc = sc.merge(starters.rename(columns={'player_id':'pitcher'}), on=['game_pk','pitcher'], how='inner')
    logger.info(f"  Starter pitches: {len(sc):,}")
    # Per-start pitch mix
    mix = sc.groupby(['game_pk','pitcher','season','game_date']).apply(
        lambda g: g['pitch_type'].value_counts(normalize=True).to_dict(), include_groups=False).reset_index(name='mix')
    mix = mix.sort_values(['pitcher','game_date','game_pk'])
    # Extract primary pitch usage and mix variance
    mix['primary_pct'] = mix['mix'].apply(lambda d: max(d.values()) if d else 0)
    mix['n_types'] = mix['mix'].apply(lambda d: len(d))
    # Season baseline
    mix['primary_season'] = mix.groupby(['pitcher','season'])['primary_pct'].transform(
        lambda x: x.shift(1).expanding(min_periods=5).mean())
    mix['primary_r3'] = mix.groupby('pitcher')['primary_pct'].transform(
        lambda x: x.shift(1).rolling(3,min_periods=2).mean())
    # CS016A: primary usage increased > 5pp
    mix['improvement'] = (mix['primary_r3'] - mix['primary_season'] > 0.05).astype(int)
    # CS016B: mix variance instability
    mix['mix_var_r3'] = mix.groupby('pitcher')['primary_pct'].transform(
        lambda x: x.shift(1).rolling(3,min_periods=2).var())
    mix['mix_var_season'] = mix.groupby(['pitcher','season'])['primary_pct'].transform(
        lambda x: x.shift(1).expanding(min_periods=5).var())
    mix['instability'] = ((mix['mix_var_r3'] > 1.5 * mix['mix_var_season']) & mix['mix_var_season'].notna()).astype(int)
    # Game level: either starter
    for flag_name, flag_col, sid, direction in [
        ('cs016a_flag','improvement','CS016A','UNDER'),
        ('cs016b_flag','instability','CS016B','OVER')]:
        gf = gdf[['game_pk','home_team','away_team']].drop_duplicates('game_pk').copy()
        gf = gf.merge(mix[['game_pk','pitcher',flag_col]].rename(columns={flag_col:'h_f','pitcher':'h_pid'}),
            left_on='game_pk',right_on='game_pk',how='left')
        # Need to match pitcher to team side — simplify: flag game if any starter has the flag
        game_flag = mix.groupby('game_pk')[flag_col].max().reset_index().rename(columns={flag_col:flag_name})
        df16 = gdf_np.merge(game_flag,on='game_pk',how='left')
        df16[flag_name] = df16[flag_name].fillna(0).astype(int)
        logger.info(f"  {sid} flagged: {df16[flag_name].sum()}")
        batch[sid] = run_std(sid,df16,flag_name,direction)
        logger.info(f"  {sid} VERDICT: {batch[sid]['verdict']}")
except Exception as e:
    logger.error(f"  CS016 FAILED: {e}")
    batch.setdefault('CS016A',{'verdict':'ERROR','error':str(e)})
    batch.setdefault('CS016B',{'verdict':'ERROR','error':str(e)})

# ═══════════════════════════════════════════════════════════
# CS017 — PITCHER DECEPTION / PITCH-MIX ENTROPY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS017 — PITCHER ENTROPY")
logger.info("="*60)
try:
    from scipy.stats import entropy as shannon_entropy
    # Reuse mix from CS016
    mix['entropy'] = mix['mix'].apply(lambda d: shannon_entropy(list(d.values())) if d and len(d)>1 else 0)
    mix['entropy_r3'] = mix.groupby('pitcher')['entropy'].transform(
        lambda x: x.shift(1).rolling(3,min_periods=2).mean())
    # Freeze top 20% on 2022-2023
    freeze_ent = mix[mix['season'].isin([2022,2023])].dropna(subset=['entropy_r3'])
    ENT_THRESH = freeze_ent['entropy_r3'].quantile(0.80)
    logger.info(f"  Entropy top-20% threshold: {ENT_THRESH:.4f}")
    mix['high_entropy'] = (mix['entropy_r3'] >= ENT_THRESH).astype(int)
    # Game level: both starters high entropy
    game_ent = mix.groupby('game_pk').agg(
        n_high=('high_entropy','sum'),n_starters=('pitcher','count')).reset_index()
    # Top-20% = at least one starter high entropy (broader); both = stricter
    game_ent['cs017_flag'] = (game_ent['n_high'] >= 2).astype(int)  # both starters
    df17 = gdf_np.merge(game_ent[['game_pk','cs017_flag']],on='game_pk',how='left')
    df17['cs017_flag'] = df17['cs017_flag'].fillna(0).astype(int)
    logger.info(f"  CS017 flagged (both starters high entropy): {df17['cs017_flag'].sum()}")
    if df17['cs017_flag'].sum() < 50:
        # Relax to either starter
        game_ent['cs017_flag_any'] = (game_ent['n_high'] >= 1).astype(int)
        df17 = gdf_np.merge(game_ent[['game_pk','cs017_flag_any']].rename(columns={'cs017_flag_any':'cs017_flag'}),
                             on='game_pk',how='left')
        df17['cs017_flag'] = df17['cs017_flag'].fillna(0).astype(int)
        logger.info(f"  Relaxed to either starter: {df17['cs017_flag'].sum()}")
    batch['CS017'] = run_std('CS017',df17,'cs017_flag','UNDER')
    logger.info(f"  CS017 VERDICT: {batch['CS017']['verdict']}")
except Exception as e:
    logger.error(f"  CS017 FAILED: {e}")
    batch['CS017'] = {'verdict':'ERROR','error':str(e)}

# ═══════════════════════════════════════════════════════════
# CS018 — INNING-LEVEL RUN CLUSTERING
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS018 — INNING-LEVEL RUN CLUSTERING")
logger.info("="*60)
try:
    # game_table has actual_total and actual_f5_total
    # We need per-inning scoring — check if linescore data is cached
    # Use home_score/away_score variance proxy: total runs variance across recent games
    # Better proxy: use the game_table innings_played + f5 total to estimate late-game variance
    # Simplest valid: use team's recent scoring variance as clustering proxy
    team_games = []
    for _,r in gdf.iterrows():
        team_games.append({'game_pk':r['game_pk'],'date':r['date'],'season':r['season'],
                           'team':r['home_team'],'runs':r['home_score']})
        team_games.append({'game_pk':r['game_pk'],'date':r['date'],'season':r['season'],
                           'team':r['away_team'],'runs':r['away_score']})
    tg = pd.DataFrame(team_games)
    tg['date'] = pd.to_datetime(tg['date'])
    tg = tg.sort_values(['team','date','game_pk'])
    # Within-game scoring clustering proxy: use high-scoring game frequency + variance
    tg['high_scoring'] = (tg['runs'] >= 7).astype(int)
    tg['var_r10'] = tg.groupby('team')['runs'].transform(lambda x: x.shift(1).rolling(10,min_periods=8).var())
    tg['high_pct_r10'] = tg.groupby('team')['high_scoring'].transform(lambda x: x.shift(1).rolling(10,min_periods=8).mean())
    # Combined clustering score
    tg['cluster_score'] = tg['var_r10'].fillna(0) * (1 + tg['high_pct_r10'].fillna(0))
    # Game level: max of home + away
    game18 = gdf[['game_pk','home_team','away_team']].drop_duplicates('game_pk').copy()
    for side,tc in [('home','home_team'),('away','away_team')]:
        game18 = game18.merge(tg[['game_pk','team','cluster_score']].rename(columns={'cluster_score':f'{side}_cs'}),
            left_on=['game_pk',tc],right_on=['game_pk','team'],how='left')
    game18['max_cluster'] = game18[['home_cs','away_cs']].max(axis=1)
    # Freeze top 20% on 2022-2023
    game18 = game18.merge(gdf[['game_pk','season']].drop_duplicates('game_pk'),on='game_pk',how='left')
    freeze18 = game18[game18['season'].isin([2022,2023])].dropna(subset=['max_cluster'])
    CLUST_THRESH = freeze18['max_cluster'].quantile(0.80)
    logger.info(f"  Clustering top-20% threshold: {CLUST_THRESH:.4f}")
    game18['cs018_flag'] = (game18['max_cluster'] >= CLUST_THRESH).astype(int)
    df18 = gdf_np.merge(game18[['game_pk','cs018_flag']].drop_duplicates('game_pk'),on='game_pk',how='left')
    df18['cs018_flag'] = df18['cs018_flag'].fillna(0).astype(int)
    logger.info(f"  CS018 flagged: {df18['cs018_flag'].sum()}")
    batch['CS018'] = run_std('CS018',df18,'cs018_flag','OVER')
    logger.info(f"  CS018 VERDICT: {batch['CS018']['verdict']}")
except Exception as e:
    logger.error(f"  CS018 FAILED: {e}")
    batch['CS018'] = {'verdict':'ERROR','error':str(e)}

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("BATCH 3 SUMMARY")
logger.info("="*60)
for sid in ['CS013','CS014A','CS014B','CS015','CS016A','CS016B','CS017','CS018']:
    r = batch.get(sid,{})
    v = r.get('verdict','NOT_RUN')
    p = r.get('permutation_percentile','N/A')
    rate = r.get('_rate_v25')
    rs = f"{rate:.4f}" if rate else "N/A"
    logger.info(f"  {sid:<8s}: {v:<12s} perm={p:>5} v25_rate={rs}")

with open(str(OUT/'batch3_raw.json'),'w') as f:
    def _s(o):
        if isinstance(o,(np.integer,)):return int(o)
        if isinstance(o,(np.floating,)):return float(o)
        if isinstance(o,(np.bool_,)):return bool(o)
        if isinstance(o,np.ndarray):return o.tolist()
        return str(o)
    json.dump(batch,f,indent=2,default=_s)
logger.info("\nBatch 3 complete.")
