#!/usr/bin/env python3
"""Test Batch 2 — CS007A-CS012 through the safety layer. RESEARCH ONLY."""
import sys, json, logging
import pandas as pd, numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("batch2")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "safety_layer"))
from signal_tester import (run_signal_test, get_registered_hypothesis, TRAIN_SEASONS,
                            log_test_result, update_board)

OUT = Path('research/signal_discovery/test_batch_2')

# ── Load common data ─────────────────────────────────────────────────
logger.info("Loading data...")
gt = pd.read_parquet('sim/data/game_table.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
cl = pd.read_parquet('sim/data/mlb_historical_closing_lines.parquet')
br = pd.read_parquet('sim/data/bet_results.parquet')
rl = pd.read_parquet('research/data_pulls/reliever_role_tracking.parquet')

# Build unified game dataset with closing totals (2022-2025, no 2026)
gdf = gt[gt['season'].isin([2022,2023,2024,2025])].copy()
cl_sub = cl[['game_pk','close_total']].rename(columns={'close_total':'ct_hist'}).drop_duplicates('game_pk')
br_sub = br[['game_id','close_total']].rename(columns={'game_id':'game_pk','close_total':'ct_br'}).drop_duplicates('game_pk')
gdf = gdf.merge(cl_sub, on='game_pk', how='left').merge(br_sub, on='game_pk', how='left')
gdf['closing_total'] = gdf['ct_hist'].fillna(gdf['ct_br'])
gdf['market_residual'] = gdf['actual_total'] - gdf['closing_total']
gdf['went_over'] = (gdf['actual_total'] > gdf['closing_total']).astype(int)
gdf['went_under'] = (gdf['actual_total'] < gdf['closing_total']).astype(int)
gdf['is_push'] = (gdf['actual_total'] == gdf['closing_total']).astype(int)
gdf = gdf[gdf['closing_total'].notna()].copy()
gdf_np = gdf[gdf['is_push'] == 0].copy()
logger.info(f"  Games: {len(gdf)}, non-push: {len(gdf_np)}")

batch_results = {}

def roi_110(rate): return round((rate * (100/110) - (1 - rate)) * 100, 2) if rate else None

def stats_dir(df, flag_col, direction):
    """Compute stats for flagged group. direction='OVER' or 'UNDER'."""
    fl = df[df[flag_col] == 1]
    bs = df[df[flag_col] == 0]
    n = len(fl)
    if n == 0: return 0, None, None, None, False
    hit_col = 'went_over' if direction == 'OVER' else 'went_under'
    rate = fl[hit_col].mean()
    me = fl['market_residual'].mean()
    roi = roi_110(rate)
    pos = rate > 0.50
    return n, rate, me, roi, pos

def run_test(sig_id, df, flag_col, direction):
    """Standard test runner through safety layer."""
    hyp = get_registered_hypothesis(sig_id)
    hit_col = 'went_over' if direction == 'OVER' else 'went_under'

    tr_n, tr_r, tr_me, tr_roi, _ = stats_dir(df[df['season'].isin(TRAIN_SEASONS)], flag_col, direction)
    v24_n, v24_r, v24_me, v24_roi, v24_pos = stats_dir(df[df['season']==2024], flag_col, direction)
    v25_n, v25_r, v25_me, v25_roi, v25_pos = stats_dir(df[df['season']==2025], flag_col, direction)

    logger.info(f"  Train: N={tr_n}, rate={tr_r:.4f}, ROI={tr_roi}%" if tr_r else "  Train: insufficient")
    logger.info(f"  V2025: N={v25_n}, rate={v25_r:.4f}, ROI={v25_roi}%, pos={v25_pos}" if v25_r else "  V2025: insufficient")

    def metric_fn(sig, out):
        mask = sig == 1
        if mask.sum() == 0: return 0.5
        return out[mask].mean()

    result = run_signal_test(
        sig_id,
        signal_values=df[flag_col].values,
        outcomes=df[hit_col].values,
        metric_fn=metric_fn,
        season_labels=df['season'].values,
        train_n=tr_n, train_under_rate=(1-tr_r if direction=='OVER' else tr_r) if tr_r else None, train_roi=tr_roi,
        val_2024_n=v24_n, val_2024_under_rate=(1-v24_r if direction=='OVER' else v24_r) if v24_r else None,
        val_2024_roi=v24_roi, val_2024_positive=v24_pos,
        val_2025_n=v25_n, val_2025_under_rate=(1-v25_r if direction=='OVER' else v25_r) if v25_r else None,
        val_2025_roi=v25_roi, val_2025_positive=v25_pos,
    )
    result['_direction'] = direction
    result['_rate_train'] = tr_r
    result['_rate_v25'] = v25_r
    return result

# ═══════════════════════════════════════════════════════════
# CS007A/B — RUN DISTRIBUTION TAIL SHAPE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS007A/B — RUN DISTRIBUTION TAIL SHAPE")
logger.info("="*60)
try:
    # Per team-game: recent run distribution stats
    # Use game_table actual scores for each team
    team_games = []
    for _, r in gdf.iterrows():
        team_games.append({'game_pk': r['game_pk'], 'date': r['date'], 'season': r['season'],
                           'team': r['home_team'], 'runs': r['home_score']})
        team_games.append({'game_pk': r['game_pk'], 'date': r['date'], 'season': r['season'],
                           'team': r['away_team'], 'runs': r['away_score']})
    tg = pd.DataFrame(team_games)
    tg['date'] = pd.to_datetime(tg['date'])
    tg = tg.sort_values(['team','date','game_pk'])
    tg['high_run'] = (tg['runs'] >= 7).astype(int)

    # Rolling 15-game stats with shift(1)
    tg['run_var_r15'] = tg.groupby('team')['runs'].transform(
        lambda x: x.shift(1).rolling(15, min_periods=10).var())
    tg['run_cv_r15'] = tg.groupby('team')['runs'].transform(
        lambda x: x.shift(1).rolling(15, min_periods=10).std()) / tg.groupby('team')['runs'].transform(
        lambda x: x.shift(1).rolling(15, min_periods=10).mean()).replace(0, np.nan)
    tg['pct_7plus_r15'] = tg.groupby('team')['high_run'].transform(
        lambda x: x.shift(1).rolling(15, min_periods=10).mean())

    # Game-level: combine home + away
    game_var = gdf[['game_pk','home_team','away_team','season']].copy()
    for side, tcol in [('home','home_team'), ('away','away_team')]:
        sub = tg[['game_pk','team','run_var_r15','pct_7plus_r15']].rename(
            columns={'run_var_r15':f'{side}_var','pct_7plus_r15':f'{side}_7plus'})
        game_var = game_var.merge(sub, left_on=['game_pk',tcol], right_on=['game_pk','team'], how='left')

    game_var['combined_var'] = (game_var['home_var'].fillna(0) + game_var['away_var'].fillna(0)) / 2
    game_var['combined_7plus'] = (game_var['home_7plus'].fillna(0) + game_var['away_7plus'].fillna(0)) / 2
    game_var['dist_score'] = game_var['combined_var'] + game_var['combined_7plus'] * 10

    # Freeze thresholds on 2022-2023
    freeze = game_var[game_var['season'].isin([2022,2023])].dropna(subset=['dist_score'])
    HIGH_THRESH = freeze['dist_score'].quantile(0.80)
    LOW_THRESH = freeze['dist_score'].quantile(0.20)
    logger.info(f"  Frozen thresholds: HIGH={HIGH_THRESH:.3f}, LOW={LOW_THRESH:.3f}")

    game_var['high_var_flag'] = (game_var['dist_score'] >= HIGH_THRESH).astype(int)
    game_var['low_var_flag'] = (game_var['dist_score'] <= LOW_THRESH).astype(int)

    df7 = gdf_np.merge(game_var[['game_pk','high_var_flag','low_var_flag']].drop_duplicates('game_pk'),
                        on='game_pk', how='left')
    df7['high_var_flag'] = df7['high_var_flag'].fillna(0).astype(int)
    df7['low_var_flag'] = df7['low_var_flag'].fillna(0).astype(int)

    logger.info(f"  CS007A flagged: {df7['high_var_flag'].sum()}, CS007B flagged: {df7['low_var_flag'].sum()}")

    batch_results['CS007A'] = run_test('CS007A', df7, 'high_var_flag', 'OVER')
    logger.info(f"  CS007A VERDICT: {batch_results['CS007A']['verdict']}")

    batch_results['CS007B'] = run_test('CS007B', df7, 'low_var_flag', 'UNDER')
    logger.info(f"  CS007B VERDICT: {batch_results['CS007B']['verdict']}")
except Exception as e:
    logger.error(f"  CS007 FAILED: {e}")
    batch_results['CS007A'] = {'verdict': 'ERROR', 'error': str(e)}
    batch_results['CS007B'] = {'verdict': 'ERROR', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CS008A/B — EXTREME WEATHER
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS008A/B — EXTREME WEATHER")
logger.info("="*60)
try:
    wx = gdf_np[['game_pk','season','temperature','wind_speed','wind_direction','roof_status',
                   'went_over','went_under','market_residual']].copy()

    # Exclude dome/retractable (weather irrelevant)
    wx_open = wx[wx['roof_status'] == 'open'].copy()
    logger.info(f"  Open-roof games: {len(wx_open)}")

    # CS008A: extreme heat (>90F) OR high out-wind (>15mph)
    # We don't have wind direction as "out" indicator directly — use wind_speed > 15 as proxy
    wx_open['extreme_heat'] = (wx_open['temperature'] > 90).astype(int)
    wx_open['extreme_wind'] = (wx_open['wind_speed'] > 15).astype(int)
    wx_open['cs008a_flag'] = ((wx_open['extreme_heat'] == 1) | (wx_open['extreme_wind'] == 1)).astype(int)

    # CS008B: extreme cold (<45F)
    wx_open['cs008b_flag'] = (wx_open['temperature'] < 45).astype(int)

    logger.info(f"  CS008A flagged (heat/wind): {wx_open['cs008a_flag'].sum()}")
    logger.info(f"  CS008B flagged (cold): {wx_open['cs008b_flag'].sum()}")

    batch_results['CS008A'] = run_test('CS008A', wx_open, 'cs008a_flag', 'OVER')
    logger.info(f"  CS008A VERDICT: {batch_results['CS008A']['verdict']}")

    batch_results['CS008B'] = run_test('CS008B', wx_open, 'cs008b_flag', 'UNDER')
    logger.info(f"  CS008B VERDICT: {batch_results['CS008B']['verdict']}")
except Exception as e:
    logger.error(f"  CS008 FAILED: {e}")
    batch_results['CS008A'] = {'verdict': 'ERROR', 'error': str(e)}
    batch_results['CS008B'] = {'verdict': 'ERROR', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CS009A/B — UMPIRE ZONE REGIME
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS009A/B — UMPIRE ZONE REGIME")
logger.info("="*60)
try:
    # Umpire data in game_table: umpire_name, umpire_over_rate, umpire_k_rate
    # We need rolling umpire zone state. umpire_k_rate is the best proxy for zone tightness.
    # Higher k_rate = tighter zone (more called strikes → more K's).
    ump = gdf[['game_pk','date','season','umpire_name','umpire_k_rate','umpire_over_rate']].copy()
    ump['date'] = pd.to_datetime(ump['date'])
    ump = ump.dropna(subset=['umpire_name','umpire_k_rate'])
    ump = ump.sort_values(['umpire_name','date','game_pk'])

    # Rolling 3-game umpire k_rate vs season expanding mean
    ump['ump_k_season_mean'] = ump.groupby(['umpire_name','season'])['umpire_k_rate'].transform(
        lambda x: x.shift(1).expanding(min_periods=3).mean())
    ump['ump_k_season_std'] = ump.groupby(['umpire_name','season'])['umpire_k_rate'].transform(
        lambda x: x.shift(1).expanding(min_periods=3).std())
    # This uses static umpire ratings, not per-game called strike data
    # The umpire_k_rate is a static season metric, not game-by-game
    # Without per-game called strike data, we can't build a rolling zone state
    # Flag as DATA_GAP: we need per-game umpire zone metrics, not static season ratings

    # Check if umpire_k_rate varies per game for the same umpire
    sample_ump = ump[ump['umpire_name'] == ump['umpire_name'].mode().iloc[0]]
    k_var = sample_ump['umpire_k_rate'].nunique()
    logger.info(f"  Sample umpire k_rate unique values: {k_var}")
    if k_var <= 2:
        logger.info("  DATA_GAP: umpire_k_rate is static (not per-game). Cannot build rolling zone state.")
        raise ValueError("Umpire data is static season ratings, not per-game zone metrics")

    # If we get here, the data varies per game — proceed
    ump['k_zscore'] = (ump['umpire_k_rate'] - ump['ump_k_season_mean']) / ump['ump_k_season_std'].replace(0, np.nan)
    # Use previous game's z-score as pregame indicator
    ump['k_z_prev'] = ump.groupby('umpire_name')['k_zscore'].shift(1)

    ump['tight_zone'] = (ump['k_z_prev'] > 1.0).astype(int)
    ump['loose_zone'] = (ump['k_z_prev'] < -1.0).astype(int)

    df9 = gdf_np.merge(ump[['game_pk','tight_zone','loose_zone']].drop_duplicates('game_pk'),
                        on='game_pk', how='left')
    df9['tight_zone'] = df9['tight_zone'].fillna(0).astype(int)
    df9['loose_zone'] = df9['loose_zone'].fillna(0).astype(int)

    batch_results['CS009A'] = run_test('CS009A', df9, 'tight_zone', 'UNDER')
    logger.info(f"  CS009A VERDICT: {batch_results['CS009A']['verdict']}")
    batch_results['CS009B'] = run_test('CS009B', df9, 'loose_zone', 'OVER')
    logger.info(f"  CS009B VERDICT: {batch_results['CS009B']['verdict']}")

except ValueError as e:
    logger.info(f"  CS009A/B: DATA_GAP — {e}")
    for sid in ['CS009A','CS009B']:
        batch_results[sid] = {'canonical_signal_id':sid,'verdict':'DATA_GAP',
            'suspect_flags':['DATA_GAP: per-game umpire zone metrics not available']}
        log_test_result({'canonical_signal_id':sid,'test_date':pd.Timestamp.now().isoformat(),
            'registered_hypothesis_used':True,'thresholds_match_registered':True,
            'verdict':'DATA_GAP','suspect_flags':['DATA_GAP']})
except Exception as e:
    logger.error(f"  CS009 FAILED: {e}")
    batch_results.setdefault('CS009A', {'verdict':'ERROR','error':str(e)})
    batch_results.setdefault('CS009B', {'verdict':'ERROR','error':str(e)})

# ═══════════════════════════════════════════════════════════
# CS010A/B — DYNAMIC PARK ENVIRONMENT
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS010A/B — DYNAMIC PARK ENVIRONMENT")
logger.info("="*60)
try:
    pk = gdf_np[['game_pk','season','home_team','park_factor_runs','temperature','wind_speed',
                   'roof_status','went_over','went_under','market_residual']].copy()
    pk_open = pk[pk['roof_status'] == 'open'].copy()

    # Compute park seasonal mean temp
    pk_open['date'] = pk_open.merge(gdf[['game_pk','date']], on='game_pk')['date']
    park_mean_temp = pk_open.groupby(['home_team','season'])['temperature'].transform('mean')
    pk_open['temp_dev'] = pk_open['temperature'] - park_mean_temp

    # Environment score: park_factor * (1 + temp_dev/100) * (1 + wind_speed/50)
    pk_open['env_score'] = (pk_open['park_factor_runs'] / 100) * (1 + pk_open['temp_dev']/100) * (1 + pk_open['wind_speed']/50)

    # Freeze thresholds on 2022-2023
    freeze_pk = pk_open[pk_open['season'].isin([2022,2023])].dropna(subset=['env_score'])
    HIGH_ENV = freeze_pk['env_score'].quantile(0.80)
    LOW_ENV = freeze_pk['env_score'].quantile(0.20)
    logger.info(f"  Frozen: HIGH_ENV={HIGH_ENV:.4f}, LOW_ENV={LOW_ENV:.4f}")

    pk_open['high_env'] = (pk_open['env_score'] >= HIGH_ENV).astype(int)
    pk_open['low_env'] = (pk_open['env_score'] <= LOW_ENV).astype(int)
    logger.info(f"  CS010A flagged: {pk_open['high_env'].sum()}, CS010B flagged: {pk_open['low_env'].sum()}")

    batch_results['CS010A'] = run_test('CS010A', pk_open, 'high_env', 'OVER')
    logger.info(f"  CS010A VERDICT: {batch_results['CS010A']['verdict']}")
    batch_results['CS010B'] = run_test('CS010B', pk_open, 'low_env', 'UNDER')
    logger.info(f"  CS010B VERDICT: {batch_results['CS010B']['verdict']}")
except Exception as e:
    logger.error(f"  CS010 FAILED: {e}")
    batch_results.setdefault('CS010A', {'verdict':'ERROR','error':str(e)})
    batch_results.setdefault('CS010B', {'verdict':'ERROR','error':str(e)})

# ═══════════════════════════════════════════════════════════
# CS011 — BULLPEN DEPLOYMENT OPTIMIZATION
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS011 — BULLPEN DEPLOYMENT OPTIMIZATION")
logger.info("="*60)
try:
    # Use reliever_role_tracking: closer/setup used recently + high-leverage IP
    # Proxy: closer used last 2 days AND setup used last 2 days = depleted high-leverage arms
    rl2 = rl.copy()
    rl2['home_depleted'] = ((rl2['home_closer_pitched_last2days']==1) &
                             (rl2['home_setup_pitcher_pitched_last2days']==1)).astype(int)
    rl2['away_depleted'] = ((rl2['away_closer_pitched_last2days']==1) &
                             (rl2['away_setup_pitcher_pitched_last2days']==1)).astype(int)
    rl2['cs011_flag'] = ((rl2['home_depleted']==1) | (rl2['away_depleted']==1)).astype(int)

    df11 = gdf_np.merge(rl2[['game_pk','cs011_flag']].drop_duplicates('game_pk'),
                         on='game_pk', how='left')
    df11['cs011_flag'] = df11['cs011_flag'].fillna(0).astype(int)
    logger.info(f"  CS011 flagged: {df11['cs011_flag'].sum()}")

    batch_results['CS011'] = run_test('CS011', df11, 'cs011_flag', 'OVER')
    logger.info(f"  CS011 VERDICT: {batch_results['CS011']['verdict']}")
except Exception as e:
    logger.error(f"  CS011 FAILED: {e}")
    batch_results['CS011'] = {'verdict':'ERROR','error':str(e)}

# ═══════════════════════════════════════════════════════════
# CS012 — TRAVEL UNCLUSTERED SIGNALS
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS012 — TRAVEL COMPRESSION")
logger.info("="*60)
try:
    # Build road trip + timezone data
    st_path = 'research/signal_scanner/derived_features/schedule_travel.parquet'
    import os
    if os.path.exists(st_path):
        st = pd.read_parquet(st_path)
        # schedule_travel covers 2024-2025 only
        logger.info(f"  Schedule travel: {len(st)} rows, seasons: {sorted(st['season'].unique())}")
        # Compressed: timezone_change >= 2 AND road_trip >= 5
        st['compressed'] = ((st['timezone_change_away'] >= 2) &
                             (st['road_trip_game_num_away'] >= 5)).astype(int)

        df12 = gdf_np.merge(st[['game_pk','compressed']].rename(columns={'compressed':'cs012_flag'}),
                             on='game_pk', how='left')
        df12['cs012_flag'] = df12['cs012_flag'].fillna(0).astype(int)
        # Only games with schedule data (2024-2025)
        df12 = df12[df12['season'].isin([2024,2025])].copy()
        logger.info(f"  CS012 flagged: {df12['cs012_flag'].sum()} (2024-2025 only)")

        if df12['cs012_flag'].sum() < 20:
            logger.info("  CS012: too few flagged games for reliable test")
            batch_results['CS012'] = {'canonical_signal_id':'CS012','verdict':'INVESTIGATE',
                'suspect_flags':['THIN_SAMPLE: very few compressed travel games'],
                'note': f"N flagged = {df12['cs012_flag'].sum()}"}
            log_test_result({'canonical_signal_id':'CS012','test_date':pd.Timestamp.now().isoformat(),
                'registered_hypothesis_used':True,'thresholds_match_registered':True,
                'verdict':'INVESTIGATE','suspect_flags':['THIN_SAMPLE']})
            update_board('CS012','INVESTIGATE',failure_reason='Thin sample — compressed travel is rare')
        else:
            batch_results['CS012'] = run_test('CS012', df12, 'cs012_flag', 'UNDER')
            logger.info(f"  CS012 VERDICT: {batch_results['CS012']['verdict']}")
    else:
        logger.info("  CS012: DATA_GAP — schedule_travel.parquet not found")
        batch_results['CS012'] = {'verdict':'DATA_GAP','suspect_flags':['DATA_GAP']}
        log_test_result({'canonical_signal_id':'CS012','test_date':pd.Timestamp.now().isoformat(),
            'registered_hypothesis_used':True,'thresholds_match_registered':True,
            'verdict':'DATA_GAP','suspect_flags':['DATA_GAP']})
except Exception as e:
    logger.error(f"  CS012 FAILED: {e}")
    batch_results['CS012'] = {'verdict':'ERROR','error':str(e)}

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("BATCH 2 SUMMARY")
logger.info("="*60)
for sid in ['CS007A','CS007B','CS008A','CS008B','CS009A','CS009B','CS010A','CS010B','CS011','CS012']:
    r = batch_results.get(sid, {})
    v = r.get('verdict','NOT_RUN')
    perm = r.get('permutation_percentile','N/A')
    rate = r.get('_rate_v25')
    rate_str = f"{rate:.4f}" if rate else "N/A"
    logger.info(f"  {sid:<8s}: {v:<12s} perm={perm:>5} v25_rate={rate_str}")

# Save raw results
with open(str(OUT / 'batch2_raw_results.json'), 'w') as f:
    def _ser(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return str(obj)
    json.dump(batch_results, f, indent=2, default=_ser)

logger.info("\nBatch 2 complete.")
