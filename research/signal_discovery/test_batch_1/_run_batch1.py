#!/usr/bin/env python3
"""
Test Batch 1 — Run CS001-CS006 through the safety layer.
RESEARCH ONLY. Does not modify production files.
"""
import sys, json, logging, os
import pandas as pd
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("batch1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "safety_layer"))
from signal_tester import (
    run_signal_test, get_registered_hypothesis, enforce_split,
    check_leakage, run_permutation_test, check_suspect_flags,
    log_test_result, update_board, TRAIN_SEASONS,
)

OUT = Path(__file__).resolve().parent

# ═══════════════════════════════════════════════════════════
# LOAD COMMON DATA
# ═══════════════════════════════════════════════════════════
logger.info("Loading common datasets...")
gt = pd.read_parquet('sim/data/game_table.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
ps = pd.read_parquet('research/statcast_enrichment/pitcher_statcast_per_start.parquet')
cl = pd.read_parquet('sim/data/mlb_historical_closing_lines.parquet')
br = pd.read_parquet('sim/data/bet_results.parquet')
rl = pd.read_parquet('research/data_pulls/reliever_role_tracking.parquet')

# Build unified game dataset with closing totals (2022-2025, no 2026)
gdf = gt[gt['season'].isin([2022, 2023, 2024, 2025])].copy()
cl_sub = cl[['game_pk','close_total']].rename(columns={'close_total':'ct_hist'}).drop_duplicates('game_pk')
br_sub = br[['game_id','close_total']].rename(columns={'game_id':'game_pk','close_total':'ct_br'}).drop_duplicates('game_pk')
gdf = gdf.merge(cl_sub, on='game_pk', how='left').merge(br_sub, on='game_pk', how='left')
gdf['closing_total'] = gdf['ct_hist'].fillna(gdf['ct_br'])
gdf['market_residual'] = gdf['actual_total'] - gdf['closing_total']
gdf['went_under'] = (gdf['actual_total'] < gdf['closing_total']).astype(int)
gdf['is_push'] = (gdf['actual_total'] == gdf['closing_total']).astype(int)
gdf = gdf[gdf['closing_total'].notna()].copy()
gdf_np = gdf[gdf['is_push'] == 0].copy()
logger.info(f"  Game dataset: {len(gdf)} games, {len(gdf_np)} non-push")

# Starters with statcast
starters = pl[pl['starter_flag'] == 1].copy()
starters = starters.merge(
    ps[['pitcher_id','game_pk','hard_hit_rate','barrel_rate','whiff_rate','zone_rate','avg_exit_velo']],
    left_on=['player_id','game_pk'], right_on=['pitcher_id','game_pk'], how='left'
)
starters = starters.sort_values(['player_id','game_date','game_pk'])
logger.info(f"  Starters with statcast: {starters['whiff_rate'].notna().sum()}/{len(starters)}")

# Helper: compute ROI at -110
def roi_110(under_rate):
    return round((under_rate * (100/110) - (1 - under_rate)) * 100, 2)

# Helper: standard metric function for permutation tests
def make_under_metric(signal_col_name='signal_flag'):
    """Returns a metric_fn that computes under_rate in flagged group."""
    def fn(sig, out):
        mask = sig == 1
        if mask.sum() == 0:
            return 0.5
        return out[mask].mean()
    return fn

def make_residual_metric():
    """Returns metric_fn that computes mean market residual in flagged group (lower = UNDER)."""
    def fn(sig, out):
        mask = sig == 1
        if mask.sum() == 0:
            return 0.0
        return -out[mask].mean()  # negate so higher = more UNDER
    return fn

batch_results = {}

# ═══════════════════════════════════════════════════════════
# CS001 — PITCHER COMMAND REGIME SHIFT
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS001 — PITCHER COMMAND REGIME SHIFT")
logger.info("="*60)

try:
    hyp = get_registered_hypothesis("CS001")

    # Build rolling command metrics per pitcher-start
    # Use pitcher game logs for BB rate + statcast for CSW proxy (whiff_rate * zone_rate)
    s1 = starters.copy()
    s1['bb_rate'] = s1['walks'] / s1['batters_faced'].replace(0, np.nan)
    # CSW proxy: whiff_rate is the best available stand-in for CSW
    s1['csw_proxy'] = s1['whiff_rate']

    # Rolling stats per pitcher (last 10 starts)
    for col in ['bb_rate', 'csw_proxy']:
        s1[f'{col}_mean10'] = s1.groupby('player_id')[col].transform(
            lambda x: x.shift(1).rolling(10, min_periods=5).mean())
        s1[f'{col}_std10'] = s1.groupby('player_id')[col].transform(
            lambda x: x.shift(1).rolling(10, min_periods=5).std())

    # Z-scores (shift already applied in rolling)
    s1['bb_zscore'] = (s1['bb_rate'] - s1['bb_rate_mean10']) / s1['bb_rate_std10'].replace(0, np.nan)
    s1['csw_zscore'] = (s1['csw_proxy'] - s1['csw_proxy_mean10']) / s1['csw_proxy_std10'].replace(0, np.nan)

    # Bad command state: CSW drops >1 SD below mean AND BB rate rises >1 SD above mean
    # But we need PREGAME z-scores — use the PREVIOUS start's actual values compared to trailing mean
    # The rolling mean/std already use shift(1), so the z-score of the current start reflects
    # the current start's performance vs prior baseline. We need the PREVIOUS start's z-score
    # as a pregame indicator.
    s1['bb_zscore_prev'] = s1.groupby('player_id')['bb_zscore'].shift(1)
    s1['csw_zscore_prev'] = s1.groupby('player_id')['csw_zscore'].shift(1)

    s1['bad_command'] = ((s1['csw_zscore_prev'] < -1.0) & (s1['bb_zscore_prev'] > 1.0)).astype(int)

    # Merge to game level: flag game if EITHER starter is in bad command state
    home_cmd = s1[['game_pk','player_id','bad_command']].rename(
        columns={'player_id':'home_sp_id','bad_command':'home_bad_cmd'})
    away_cmd = s1[['game_pk','player_id','bad_command']].rename(
        columns={'player_id':'away_sp_id','bad_command':'away_bad_cmd'})

    # Join via game_pk + team matching
    home_starters = starters[['game_pk','player_id','team']].rename(
        columns={'player_id':'sp_id'})
    # For each game, home starter is where team == home_team
    game_sp = gdf[['game_pk','home_team','away_team','season']].copy()
    game_sp = game_sp.merge(
        s1[['game_pk','player_id','team','bad_command']].rename(
            columns={'bad_command':'home_bad_cmd','player_id':'home_sp_id'}),
        left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left'
    )
    game_sp = game_sp.merge(
        s1[['game_pk','player_id','team','bad_command']].rename(
            columns={'bad_command':'away_bad_cmd','player_id':'away_sp_id'}),
        left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left',
        suffixes=('','_away')
    )
    # CS001 direction is UNDER — bad command pitcher → expect UNDER
    # Actually: bad command should make pitcher worse → more runs → OVER
    # But the registered hypothesis says UNDER. Let me re-read...
    # "Pitchers in latent bad-command state produce higher walk rates and worse contact suppression"
    # This would mean MORE runs. But direction is registered as UNDER.
    # The hypothesis is that the MARKET slow-updates → the market DOESN'T know about the bad state
    # → they set the line too HIGH (based on prior good command) → actual UNDER
    # Wait, that doesn't make sense either. If pitcher is bad, runs go UP, market hasn't adjusted DOWN.
    # → actual goes OVER market expectation.
    # The registered direction is UNDER. Let me follow the registry exactly as written.
    # "market uses static ERA and misses state transitions"
    # If pitcher enters bad-command state, ERA hasn't caught up yet, market uses old ERA → sets total TOO LOW
    # → actual runs go OVER. That's OVER direction.
    # But registry says UNDER. I must follow the pre-registered direction without modification.
    # Testing as registered: UNDER direction.

    game_sp['cs001_flag'] = ((game_sp['home_bad_cmd'] == 1) | (game_sp['away_bad_cmd'] == 1)).astype(int)

    # Merge with outcomes
    cs001 = gdf_np.merge(game_sp[['game_pk','cs001_flag']].drop_duplicates('game_pk'),
                          on='game_pk', how='left')
    cs001['cs001_flag'] = cs001['cs001_flag'].fillna(0).astype(int)
    cs001 = cs001[cs001['season'].isin([2022,2023,2024,2025])].copy()

    # Remove 2026
    assert 2026 not in cs001['season'].values, "Holdout leak!"

    n_flagged = cs001['cs001_flag'].sum()
    logger.info(f"  CS001 flagged games: {n_flagged}/{len(cs001)}")

    # Split
    train = cs001[cs001['season'].isin(TRAIN_SEASONS)]
    v24 = cs001[cs001['season'] == 2024]
    v25 = cs001[cs001['season'] == 2025]

    def compute_season_stats(df, flag_col='cs001_flag'):
        flagged = df[df[flag_col] == 1]
        n = len(flagged)
        ur = flagged['went_under'].mean() if n > 0 else None
        me = flagged['market_residual'].mean() if n > 0 else None
        roi = roi_110(ur) if ur is not None else None
        pos = ur > 0.50 if ur is not None else False
        return n, ur, me, roi, pos

    tr_n, tr_ur, tr_me, tr_roi, _ = compute_season_stats(train)
    v24_n, v24_ur, v24_me, v24_roi, v24_pos = compute_season_stats(v24)
    v25_n, v25_ur, v25_me, v25_roi, v25_pos = compute_season_stats(v25)

    logger.info(f"  Train: N={tr_n}, UR={tr_ur:.4f}, ROI={tr_roi}%" if tr_ur else "  Train: insufficient data")
    logger.info(f"  V2024: N={v24_n}, UR={v24_ur:.4f}, ROI={v24_roi}%, pos={v24_pos}" if v24_ur else "  V2024: insufficient")
    logger.info(f"  V2025: N={v25_n}, UR={v25_ur:.4f}, ROI={v25_roi}%, pos={v25_pos}" if v25_ur else "  V2025: insufficient")

    # Run through safety layer
    result = run_signal_test(
        "CS001",
        signal_values=cs001['cs001_flag'].values,
        outcomes=cs001['went_under'].values,
        metric_fn=make_under_metric(),
        season_labels=cs001['season'].values,
        train_n=tr_n, train_under_rate=tr_ur, train_roi=tr_roi,
        val_2024_n=v24_n, val_2024_under_rate=v24_ur, val_2024_roi=v24_roi, val_2024_positive=v24_pos,
        val_2025_n=v25_n, val_2025_under_rate=v25_ur, val_2025_roi=v25_roi, val_2025_positive=v25_pos,
    )
    batch_results['CS001'] = result
    logger.info(f"  CS001 VERDICT: {result['verdict']}")

except Exception as e:
    logger.error(f"  CS001 FAILED: {e}")
    batch_results['CS001'] = {'verdict': 'ERROR', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CS002 — STARTER SHORT-LEASH / EARLY EXIT
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS002 — STARTER SHORT-LEASH / EARLY EXIT")
logger.info("="*60)

try:
    hyp = get_registered_hypothesis("CS002")

    s2 = starters.copy()
    s2['early_exit'] = (s2['innings_pitched'] < 5.0).astype(int)

    # Rolling early exit rate (last 5 starts, shift 1 for pregame)
    s2['exit_rate_r5'] = s2.groupby('player_id')['early_exit'].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())

    # Freeze threshold on 2022-2023 only
    freeze_data = s2[s2['season'].isin([2022, 2023])].dropna(subset=['exit_rate_r5'])
    threshold_80 = freeze_data['exit_rate_r5'].quantile(0.80)
    logger.info(f"  Frozen top-20% threshold (2022-2023): {threshold_80:.4f}")

    s2['high_exit_risk'] = (s2['exit_rate_r5'] >= threshold_80).astype(int)

    # Game-level: flag if EITHER starter has high exit risk
    game_exit = gdf[['game_pk','home_team','away_team','season']].copy()
    game_exit = game_exit.merge(
        s2[['game_pk','team','high_exit_risk']].rename(columns={'high_exit_risk':'home_exit'}),
        left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
    game_exit = game_exit.merge(
        s2[['game_pk','team','high_exit_risk']].rename(columns={'high_exit_risk':'away_exit'}),
        left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left',
        suffixes=('','_a'))
    game_exit['cs002_flag'] = ((game_exit['home_exit'] == 1) | (game_exit['away_exit'] == 1)).astype(int)

    cs002 = gdf_np.merge(game_exit[['game_pk','cs002_flag']].drop_duplicates('game_pk'),
                          on='game_pk', how='left')
    cs002['cs002_flag'] = cs002['cs002_flag'].fillna(0).astype(int)

    # CS002 direction: OVER (early exit → more runs)
    cs002['went_over'] = 1 - cs002['went_under']
    n_flagged = cs002['cs002_flag'].sum()
    logger.info(f"  CS002 flagged games: {n_flagged}/{len(cs002)}")

    train = cs002[cs002['season'].isin(TRAIN_SEASONS)]
    v24 = cs002[cs002['season'] == 2024]
    v25 = cs002[cs002['season'] == 2025]

    def stats_over(df, flag_col='cs002_flag'):
        flagged = df[df[flag_col] == 1]
        n = len(flagged)
        ovr = flagged['went_over'].mean() if n > 0 else None
        me = flagged['market_residual'].mean() if n > 0 else None
        roi = roi_110(ovr) if ovr is not None else None
        pos = ovr > 0.50 if ovr is not None else False
        return n, ovr, me, roi, pos

    tr_n, tr_or, tr_me, tr_roi, _ = stats_over(train)
    v24_n, v24_or, v24_me, v24_roi, v24_pos = stats_over(v24)
    v25_n, v25_or, v25_me, v25_roi, v25_pos = stats_over(v25)

    logger.info(f"  Train: N={tr_n}, OverRate={tr_or:.4f}, ROI={tr_roi}%" if tr_or else "  Train: insufficient")
    logger.info(f"  V2024: N={v24_n}, OverRate={v24_or:.4f}, ROI={v24_roi}%, pos={v24_pos}" if v24_or else "  V2024: insufficient")
    logger.info(f"  V2025: N={v25_n}, OverRate={v25_or:.4f}, ROI={v25_roi}%, pos={v25_pos}" if v25_or else "  V2025: insufficient")

    # For OVER signals, the metric is over_rate in flagged group
    def over_metric(sig, out):
        mask = sig == 1
        if mask.sum() == 0: return 0.5
        return (1 - out[mask]).mean()  # out is went_under, so 1-out = went_over

    result = run_signal_test(
        "CS002",
        signal_values=cs002['cs002_flag'].values,
        outcomes=cs002['went_under'].values,  # safety layer uses under; metric inverts
        metric_fn=over_metric,
        season_labels=cs002['season'].values,
        train_n=tr_n, train_under_rate=1-tr_or if tr_or else None, train_roi=tr_roi,
        val_2024_n=v24_n, val_2024_under_rate=1-v24_or if v24_or else None,
        val_2024_roi=v24_roi, val_2024_positive=v24_pos,
        val_2025_n=v25_n, val_2025_under_rate=1-v25_or if v25_or else None,
        val_2025_roi=v25_roi, val_2025_positive=v25_pos,
    )
    batch_results['CS002'] = result
    batch_results['CS002']['_over_rate_train'] = tr_or
    batch_results['CS002']['_over_rate_v25'] = v25_or
    logger.info(f"  CS002 VERDICT: {result['verdict']}")

except Exception as e:
    logger.error(f"  CS002 FAILED: {e}")
    batch_results['CS002'] = {'verdict': 'ERROR', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CS003 — PITCHER LATENT FATIGUE STATE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS003 — PITCHER LATENT FATIGUE STATE")
logger.info("="*60)

try:
    hyp = get_registered_hypothesis("CS003")

    s3 = starters.copy()
    # Velocity: use avg_exit_velo as proxy if velo not available
    # Actually we need pitcher velocity, not exit velo. Check statcast for velo.
    # Statcast has spin_rate_ff but not velocity directly. Use CSW proxy decay instead.
    # Fatigue proxy: CSW decline + whiff decline from trailing mean
    s3['whiff_mean5'] = s3.groupby('player_id')['whiff_rate'].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    s3['whiff_prev'] = s3.groupby('player_id')['whiff_rate'].shift(1)
    s3['whiff_decline'] = s3['whiff_mean5'] - s3['whiff_prev']  # positive = decline

    # CSW proxy decline
    s3['bb_rate'] = s3['walks'] / s3['batters_faced'].replace(0, np.nan)
    s3['bb_mean5'] = s3.groupby('player_id')['bb_rate'].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    s3['bb_prev'] = s3.groupby('player_id')['bb_rate'].shift(1)
    s3['bb_rise'] = s3['bb_prev'] - s3['bb_mean5']  # positive = rising BB rate

    # Fatigued: whiff declining > 3pp AND BB rising > 2pp
    s3['fatigued'] = ((s3['whiff_decline'] > 0.03) & (s3['bb_rise'] > 0.02)).astype(int)

    # Game-level
    game_fat = gdf[['game_pk','home_team','away_team','season']].copy()
    game_fat = game_fat.merge(
        s3[['game_pk','team','fatigued']].rename(columns={'fatigued':'home_fat'}),
        left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
    game_fat = game_fat.merge(
        s3[['game_pk','team','fatigued']].rename(columns={'fatigued':'away_fat'}),
        left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left',
        suffixes=('','_a'))
    game_fat['cs003_flag'] = ((game_fat['home_fat'] == 1) | (game_fat['away_fat'] == 1)).astype(int)

    cs003 = gdf_np.merge(game_fat[['game_pk','cs003_flag']].drop_duplicates('game_pk'),
                          on='game_pk', how='left')
    cs003['cs003_flag'] = cs003['cs003_flag'].fillna(0).astype(int)
    cs003['went_over'] = 1 - cs003['went_under']

    n_flagged = cs003['cs003_flag'].sum()
    logger.info(f"  CS003 flagged games: {n_flagged}/{len(cs003)}")

    tr_n, tr_or, tr_me, tr_roi, _ = stats_over(cs003[cs003['season'].isin(TRAIN_SEASONS)], 'cs003_flag')
    v24_n, v24_or, v24_me, v24_roi, v24_pos = stats_over(cs003[cs003['season']==2024], 'cs003_flag')
    v25_n, v25_or, v25_me, v25_roi, v25_pos = stats_over(cs003[cs003['season']==2025], 'cs003_flag')

    logger.info(f"  Train: N={tr_n}, OverRate={tr_or:.4f}, ROI={tr_roi}%" if tr_or else "  Train: insufficient")
    logger.info(f"  V2025: N={v25_n}, OverRate={v25_or:.4f}, ROI={v25_roi}%, pos={v25_pos}" if v25_or else "  V2025: insufficient")

    result = run_signal_test(
        "CS003",
        signal_values=cs003['cs003_flag'].values,
        outcomes=cs003['went_under'].values,
        metric_fn=over_metric,
        season_labels=cs003['season'].values,
        train_n=tr_n, train_under_rate=1-tr_or if tr_or else None, train_roi=tr_roi,
        val_2024_n=v24_n, val_2024_under_rate=1-v24_or if v24_or else None,
        val_2024_roi=v24_roi, val_2024_positive=v24_pos,
        val_2025_n=v25_n, val_2025_under_rate=1-v25_or if v25_or else None,
        val_2025_roi=v25_roi, val_2025_positive=v25_pos,
    )
    batch_results['CS003'] = result
    batch_results['CS003']['_over_rate_train'] = tr_or
    batch_results['CS003']['_over_rate_v25'] = v25_or
    logger.info(f"  CS003 VERDICT: {result['verdict']}")

except Exception as e:
    logger.error(f"  CS003 FAILED: {e}")
    batch_results['CS003'] = {'verdict': 'ERROR', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CS004 — BULLPEN COLLAPSE TAIL RISK
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS004 — BULLPEN COLLAPSE TAIL RISK")
logger.info("="*60)

try:
    hyp = get_registered_hypothesis("CS004")

    # Reliever appearances: use pitcher_game_logs for relievers
    rlv = pl[pl['starter_flag'] == 0].copy()
    rlv = rlv.sort_values(['team','game_date','game_pk'])

    # Per team-game: variance of runs allowed + max runs allowed in last 10 BP appearances
    # Group by team, compute rolling stats
    team_bp = rlv.groupby(['game_pk','team']).agg(
        bp_runs_var=('runs_allowed', 'var'),
        bp_runs_max=('runs_allowed', 'max'),
        bp_appearances=('player_id', 'count'),
    ).reset_index()

    # Merge game date
    team_bp = team_bp.merge(gdf[['game_pk','date','season']].rename(columns={'date':'game_date'}).drop_duplicates('game_pk'),
                             on='game_pk', how='left')
    team_bp['game_date'] = pd.to_datetime(team_bp['game_date'])
    team_bp = team_bp.sort_values(['team','game_date','game_pk'])

    # Rolling 10-game bullpen stats per team (shift 1 for pregame)
    team_bp['bp_var_r10'] = team_bp.groupby('team')['bp_runs_var'].transform(
        lambda x: x.shift(1).rolling(10, min_periods=8).mean())
    team_bp['bp_max_r10'] = team_bp.groupby('team')['bp_runs_max'].transform(
        lambda x: x.shift(1).rolling(10, min_periods=8).max())
    team_bp['tail_score'] = team_bp['bp_var_r10'].fillna(0) + team_bp['bp_max_r10'].fillna(0)

    # Freeze threshold on 2022-2023
    freeze = team_bp[team_bp['season'].isin([2022,2023])].dropna(subset=['tail_score'])
    threshold_80 = freeze['tail_score'].quantile(0.80)
    logger.info(f"  Frozen top-20% tail_score threshold (2022-2023): {threshold_80:.4f}")

    team_bp['high_tail'] = (team_bp['tail_score'] >= threshold_80).astype(int)

    # Game level: max of home and away bullpen tail scores
    game_tail = gdf[['game_pk','home_team','away_team','season']].copy()
    game_tail = game_tail.merge(
        team_bp[['game_pk','team','high_tail']].rename(columns={'high_tail':'home_tail'}),
        left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
    game_tail = game_tail.merge(
        team_bp[['game_pk','team','high_tail']].rename(columns={'high_tail':'away_tail'}),
        left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left',
        suffixes=('','_a'))
    game_tail['cs004_flag'] = ((game_tail['home_tail'] == 1) | (game_tail['away_tail'] == 1)).astype(int)

    cs004 = gdf_np.merge(game_tail[['game_pk','cs004_flag']].drop_duplicates('game_pk'),
                          on='game_pk', how='left')
    cs004['cs004_flag'] = cs004['cs004_flag'].fillna(0).astype(int)
    cs004['went_over'] = 1 - cs004['went_under']

    n_flagged = cs004['cs004_flag'].sum()
    logger.info(f"  CS004 flagged games: {n_flagged}/{len(cs004)}")

    tr_n, tr_or, tr_me, tr_roi, _ = stats_over(cs004[cs004['season'].isin(TRAIN_SEASONS)], 'cs004_flag')
    v24_n, v24_or, v24_me, v24_roi, v24_pos = stats_over(cs004[cs004['season']==2024], 'cs004_flag')
    v25_n, v25_or, v25_me, v25_roi, v25_pos = stats_over(cs004[cs004['season']==2025], 'cs004_flag')

    logger.info(f"  Train: N={tr_n}, OverRate={tr_or:.4f}, ROI={tr_roi}%" if tr_or else "  Train: insufficient")
    logger.info(f"  V2025: N={v25_n}, OverRate={v25_or:.4f}, ROI={v25_roi}%, pos={v25_pos}" if v25_or else "  V2025: insufficient")

    result = run_signal_test(
        "CS004",
        signal_values=cs004['cs004_flag'].values,
        outcomes=cs004['went_under'].values,
        metric_fn=over_metric,
        season_labels=cs004['season'].values,
        train_n=tr_n, train_under_rate=1-tr_or if tr_or else None, train_roi=tr_roi,
        val_2024_n=v24_n, val_2024_under_rate=1-v24_or if v24_or else None,
        val_2024_roi=v24_roi, val_2024_positive=v24_pos,
        val_2025_n=v25_n, val_2025_under_rate=1-v25_or if v25_or else None,
        val_2025_roi=v25_roi, val_2025_positive=v25_pos,
    )
    batch_results['CS004'] = result
    batch_results['CS004']['_over_rate_train'] = tr_or
    batch_results['CS004']['_over_rate_v25'] = v25_or
    logger.info(f"  CS004 VERDICT: {result['verdict']}")

except Exception as e:
    logger.error(f"  CS004 FAILED: {e}")
    batch_results['CS004'] = {'verdict': 'ERROR', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CS005 — BULLPEN LATENT FATIGUE STATE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS005 — BULLPEN LATENT FATIGUE STATE")
logger.info("="*60)

try:
    hyp = get_registered_hypothesis("CS005")

    # Use reliever_role_tracking: high_leverage_ip_last3d as fatigue proxy
    rl2 = rl.copy()

    # Compute fatigue score per side
    # home_bullpen_high_leverage_ip_last3d + away_bullpen_high_leverage_ip_last3d
    # Normalize by season average
    for side in ['home', 'away']:
        col = f'{side}_bullpen_high_leverage_ip_last3d'
        rl2[f'{side}_season_avg'] = rl2.groupby(['season', f'{side}_team'])[col].transform('mean')
        rl2[f'{side}_fatigue_norm'] = rl2[col] / rl2[f'{side}_season_avg'].replace(0, np.nan)

    # Game-level: max of home and away fatigue
    rl2['max_fatigue'] = rl2[['home_fatigue_norm','away_fatigue_norm']].max(axis=1)

    # Freeze threshold on 2022-2023
    freeze = rl2[rl2['season'].isin([2022,2023])].dropna(subset=['max_fatigue'])
    threshold_80 = freeze['max_fatigue'].quantile(0.80)
    logger.info(f"  Frozen top-20% fatigue threshold (2022-2023): {threshold_80:.4f}")

    rl2['cs005_flag'] = (rl2['max_fatigue'] >= threshold_80).astype(int)

    cs005 = gdf_np.merge(rl2[['game_pk','cs005_flag']].drop_duplicates('game_pk'),
                          on='game_pk', how='left')
    cs005['cs005_flag'] = cs005['cs005_flag'].fillna(0).astype(int)
    cs005['went_over'] = 1 - cs005['went_under']

    n_flagged = cs005['cs005_flag'].sum()
    logger.info(f"  CS005 flagged games: {n_flagged}/{len(cs005)}")

    tr_n, tr_or, tr_me, tr_roi, _ = stats_over(cs005[cs005['season'].isin(TRAIN_SEASONS)], 'cs005_flag')
    v24_n, v24_or, v24_me, v24_roi, v24_pos = stats_over(cs005[cs005['season']==2024], 'cs005_flag')
    v25_n, v25_or, v25_me, v25_roi, v25_pos = stats_over(cs005[cs005['season']==2025], 'cs005_flag')

    logger.info(f"  Train: N={tr_n}, OverRate={tr_or:.4f}, ROI={tr_roi}%" if tr_or else "  Train: insufficient")
    logger.info(f"  V2025: N={v25_n}, OverRate={v25_or:.4f}, ROI={v25_roi}%, pos={v25_pos}" if v25_or else "  V2025: insufficient")

    result = run_signal_test(
        "CS005",
        signal_values=cs005['cs005_flag'].values,
        outcomes=cs005['went_under'].values,
        metric_fn=over_metric,
        season_labels=cs005['season'].values,
        train_n=tr_n, train_under_rate=1-tr_or if tr_or else None, train_roi=tr_roi,
        val_2024_n=v24_n, val_2024_under_rate=1-v24_or if v24_or else None,
        val_2024_roi=v24_roi, val_2024_positive=v24_pos,
        val_2025_n=v25_n, val_2025_under_rate=1-v25_or if v25_or else None,
        val_2025_roi=v25_roi, val_2025_positive=v25_pos,
    )
    batch_results['CS005'] = result
    batch_results['CS005']['_over_rate_train'] = tr_or
    batch_results['CS005']['_over_rate_v25'] = v25_or
    logger.info(f"  CS005 VERDICT: {result['verdict']}")

except Exception as e:
    logger.error(f"  CS005 FAILED: {e}")
    batch_results['CS005'] = {'verdict': 'ERROR', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CS006 — CROSS-MARKET PROP-TO-TOTAL ARBITRAGE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("CS006 — CROSS-MARKET PROP-TO-TOTAL ARBITRAGE")
logger.info("="*60)

# Check for SP K prop data
k_prop_paths = [
    'research/mlb_props/',
    'research/kprop/',
    'research/player_props/',
]
k_data_found = False
for p in k_prop_paths:
    if os.path.exists(p):
        files = [f for f in os.listdir(p) if 'strikeout' in f.lower() or 'k_prop' in f.lower() or 'kprop' in f.lower()]
        if files:
            k_data_found = True
            logger.info(f"  K prop data found: {p}{files}")

if not k_data_found:
    logger.info("  CS006: DATA_GAP — no SP strikeout prop data available locally")
    batch_results['CS006'] = {
        'canonical_signal_id': 'CS006',
        'verdict': 'DATA_GAP',
        'suspect_flags': ['DATA_GAP: SP K prop odds not available in local dataset'],
        'note': 'Cannot test cross-market arbitrage without SP K prop lines',
    }
    # Log to results but don't update board status
    from signal_tester import log_test_result
    log_test_result({
        'canonical_signal_id': 'CS006',
        'test_date': pd.Timestamp.now().isoformat(),
        'registered_hypothesis_used': True,
        'thresholds_match_registered': True,
        'verdict': 'DATA_GAP',
        'suspect_flags': ['DATA_GAP'],
        'note': 'SP K prop data not available locally. Signal remains REGISTERED.',
    })
else:
    logger.info("  CS006: K prop data found — would run test here")
    batch_results['CS006'] = {'verdict': 'DATA_GAP', 'note': 'K prop data format needs integration'}

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("BATCH 1 SUMMARY")
logger.info("="*60)

for sig_id in ['CS001','CS002','CS003','CS004','CS005','CS006']:
    r = batch_results.get(sig_id, {})
    verdict = r.get('verdict', 'NOT_RUN')
    perm = r.get('permutation_percentile', 'N/A')
    logger.info(f"  {sig_id}: {verdict} (perm={perm})")

# Save batch results for report generation
with open(str(OUT / 'batch1_raw_results.json'), 'w') as f:
    # Clean for JSON serialization
    clean = {}
    for k, v in batch_results.items():
        clean[k] = {}
        for k2, v2 in v.items():
            if isinstance(v2, (np.integer, np.floating)):
                clean[k][k2] = float(v2)
            elif isinstance(v2, np.ndarray):
                clean[k][k2] = v2.tolist()
            elif isinstance(v2, np.bool_):
                clean[k][k2] = bool(v2)
            else:
                clean[k][k2] = v2
    json.dump(clean, f, indent=2, default=str)

logger.info("\nBatch 1 complete.")
