#!/usr/bin/env python3
"""
CS004 × UNDER Interaction Study
RESEARCH ONLY
"""
import pandas as pd
import numpy as np
import json, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("cs004_under")
OUT = Path('research/signal_discovery/cs004_under_interactions')

# ═══════════════════════════════════════════════════════════
# LOAD AND PREPARE DATA
# ═══════════════════════════════════════════════════════════
logger.info("Loading data...")
br = pd.read_parquet('sim/data/bet_results.parquet')
gt = pd.read_parquet('sim/data/game_table.parquet')
ft = pd.read_parquet('sim/data/feature_table.parquet')
pl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
ps = pd.read_parquet('research/statcast_enrichment/pitcher_statcast_per_start.parquet')
rl = pd.read_parquet('research/data_pulls/reliever_role_tracking.parquet')

# UNDER plays only (2024-2025)
under = br[br['bet_side'] == 'under'].copy()
under['market_residual'] = under['actual_total'] - under['close_total']
under['is_push'] = (under['actual_total'] == under['close_total']).astype(int)
under['under_win'] = (under['actual_total'] < under['close_total']).astype(int)
logger.info(f"UNDER plays: {len(under)} (2024: {(under['season']==2024).sum()}, 2025: {(under['season']==2025).sum()})")

# ═══════════════════════════════════════════════════════════
# RECONSTRUCT CS004 FLAG
# ═══════════════════════════════════════════════════════════
logger.info("Reconstructing CS004 flags...")
rlv = pl[pl['starter_flag'] == 0].copy()
rlv = rlv.sort_values(['team','game_date','game_pk'])

team_bp = rlv.groupby(['game_pk','team']).agg(
    bp_runs_var=('runs_allowed','var'),
    bp_runs_max=('runs_allowed','max'),
    bp_appearances=('player_id','count'),
).reset_index()
team_bp = team_bp.merge(
    gt[['game_pk','date','season']].rename(columns={'date':'game_date'}).drop_duplicates('game_pk'),
    on='game_pk', how='left')
team_bp['game_date'] = pd.to_datetime(team_bp['game_date'])
team_bp = team_bp.sort_values(['team','game_date','game_pk'])

team_bp['bp_var_r10'] = team_bp.groupby('team')['bp_runs_var'].transform(
    lambda x: x.shift(1).rolling(10, min_periods=8).mean())
team_bp['bp_max_r10'] = team_bp.groupby('team')['bp_runs_max'].transform(
    lambda x: x.shift(1).rolling(10, min_periods=8).max())
team_bp['tail_score'] = team_bp['bp_var_r10'].fillna(0) + team_bp['bp_max_r10'].fillna(0)
team_bp['cum_app_r10'] = team_bp.groupby('team')['bp_appearances'].transform(
    lambda x: x.shift(1).rolling(10, min_periods=1).sum())
team_bp.loc[team_bp['cum_app_r10'] < 8, 'tail_score'] = np.nan

# Frozen threshold (2022-2023)
freeze = team_bp[team_bp['season'].isin([2022,2023])].dropna(subset=['tail_score'])
THRESHOLD = freeze['tail_score'].quantile(0.80)
logger.info(f"  CS004 frozen threshold: {THRESHOLD:.4f}")
team_bp['high_tail'] = (team_bp['tail_score'] >= THRESHOLD).astype(int)
team_bp.loc[team_bp['tail_score'].isna(), 'high_tail'] = np.nan

# Game-level CS004 flag
game_cs004 = gt[['game_pk','home_team','away_team']].drop_duplicates('game_pk').copy()
game_cs004 = game_cs004.merge(
    team_bp[['game_pk','team','tail_score','high_tail']].rename(columns={'tail_score':'h_ts','high_tail':'h_flag'}),
    left_on=['game_pk','home_team'], right_on=['game_pk','team'], how='left')
game_cs004 = game_cs004.merge(
    team_bp[['game_pk','team','tail_score','high_tail']].rename(columns={'tail_score':'a_ts','high_tail':'a_flag'}),
    left_on=['game_pk','away_team'], right_on=['game_pk','team'], how='left', suffixes=('','_a'))
game_cs004['cs004_flag'] = ((game_cs004['h_flag']==1)|(game_cs004['a_flag']==1)).astype(int)
game_cs004['cs004_tail_score'] = game_cs004[['h_ts','a_ts']].max(axis=1)

# ═══════════════════════════════════════════════════════════
# RECONSTRUCT S12, P09, ST02, SHORT_EXIT FLAGS
# ═══════════════════════════════════════════════════════════
logger.info("Reconstructing overlay flags...")

# S12: CSW × xFIP interaction (from feature_table)
# S12 = (home_csw + away_csw)/2 - 5*(home_xfip + away_xfip)/2
# CSW not in feature_table — use whiff_rate from statcast as proxy
starters_all = pl[pl['starter_flag'] == 1].copy()
starters_sc = starters_all.merge(
    ps[['pitcher_id','game_pk','whiff_rate']], left_on=['player_id','game_pk'],
    right_on=['pitcher_id','game_pk'], how='left')
# Rolling 5-start whiff as CSW proxy
starters_sc = starters_sc.sort_values(['player_id','game_date','game_pk'])
starters_sc['csw_r5'] = starters_sc.groupby('player_id')['whiff_rate'].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())

# For S12, we need both starters' CSW + xFIP from feature_table
ft_sp = ft[['game_pk','home_sp_xfip','away_sp_xfip']].drop_duplicates('game_pk')
game_s12 = ft_sp.copy()
# Join home/away starter CSW proxies
for side, team_col in [('home','home_team'), ('away','away_team')]:
    side_csw = starters_sc[['game_pk','team','csw_r5']].rename(columns={'csw_r5':f'{side}_csw'})
    game_s12 = game_s12.merge(
        gt[['game_pk',team_col]].drop_duplicates('game_pk'),
        on='game_pk', how='left')
    game_s12 = game_s12.merge(
        side_csw, left_on=['game_pk',team_col], right_on=['game_pk','team'], how='left')

game_s12['s12_value'] = (
    (game_s12['home_csw'].fillna(0.25) + game_s12['away_csw'].fillna(0.25)) / 2 * 100 -
    5 * ((game_s12['home_sp_xfip'].fillna(4.0) + game_s12['away_sp_xfip'].fillna(4.0)) / 2)
)
# S12 threshold: top-20% from config (8.4468)
S12_CUTOFF = 8.4468
game_s12['s12_flag'] = (game_s12['s12_value'] >= S12_CUTOFF).astype(int)

# P09: avg hard-hit rate × park factor
# Get hard-hit from statcast
starters_sc['hh_r5'] = starters_sc.groupby('player_id')['hard_hit_rate'].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean()) if 'hard_hit_rate' in starters_sc.columns else np.nan

game_p09 = gt[['game_pk','home_team','away_team','park_factor_runs']].drop_duplicates('game_pk').copy()
for side, team_col in [('home','home_team'), ('away','away_team')]:
    hh_data = starters_sc[['game_pk','team','hh_r5']].rename(columns={'hh_r5':f'{side}_hh'})
    game_p09 = game_p09.merge(hh_data, left_on=['game_pk',team_col], right_on=['game_pk','team'], how='left')

game_p09['p09_value'] = ((game_p09['home_hh'].fillna(0.38) + game_p09['away_hh'].fillna(0.38)) / 2) * game_p09['park_factor_runs']
P09_CUTOFF = 31.7305
game_p09['p09_flag'] = (game_p09['p09_value'] <= P09_CUTOFF).astype(int)

# ST02: road trip game 6+
tg_list = []
for _, row in gt[gt['season'].isin([2022,2023,2024,2025])].iterrows():
    tg_list.append({"game_pk": row["game_pk"], "date": pd.to_datetime(row["date"]),
                    "season": row["season"], "team": row["away_team"], "is_away": True})
    tg_list.append({"game_pk": row["game_pk"], "date": pd.to_datetime(row["date"]),
                    "season": row["season"], "team": row["home_team"], "is_away": False})
tg = pd.DataFrame(tg_list).sort_values(["team","date","game_pk"]).reset_index(drop=True)
streak = np.zeros(len(tg), dtype=int)
pt, ps_, s_ = None, None, 0
for i, row in enumerate(tg.itertuples()):
    if row.team != pt or row.season != ps_:
        s_ = 0; pt = row.team; ps_ = row.season
    s_ = s_ + 1 if row.is_away else 0
    streak[i] = s_
tg["rtgn"] = streak
away_trips = tg[tg["is_away"]][["game_pk","rtgn"]].copy()
game_st02 = away_trips.rename(columns={'rtgn':'road_trip_game_num'})
game_st02['st02_flag'] = (game_st02['road_trip_game_num'] >= 6).astype(int)

# Combined short exit: IP < 5.0 rate
starters_ip = starters_all[['game_pk','player_id','team','innings_pitched','season','game_date']].copy()
starters_ip['early_exit'] = (starters_ip['innings_pitched'] < 5.0).astype(int)
starters_ip = starters_ip.sort_values(['player_id','game_date','game_pk'])
starters_ip['exit_r15'] = starters_ip.groupby('player_id')['early_exit'].transform(
    lambda x: x.shift(1).rolling(15, min_periods=5).mean())
game_cse = gt[['game_pk','home_team','away_team']].drop_duplicates('game_pk').copy()
for side, tcol in [('home','home_team'), ('away','away_team')]:
    se = starters_ip[['game_pk','team','exit_r15']].rename(columns={'exit_r15':f'{side}_exit'})
    game_cse = game_cse.merge(se, left_on=['game_pk',tcol], right_on=['game_pk','team'], how='left')
game_cse['cse_value'] = (game_cse['home_exit'].fillna(0.15) + game_cse['away_exit'].fillna(0.15)) / 2
CSE_CUTOFF = 0.133333
game_cse['cse_flag'] = (game_cse['cse_value'] <= CSE_CUTOFF).astype(int)
# Note: CSE favorable = low short exit rate (durable starters) = UNDER support

# ═══════════════════════════════════════════════════════════
# STEP 1 — MASTER INTERACTION DATASET
# ═══════════════════════════════════════════════════════════
logger.info("\nBuilding master interaction dataset...")

master = under.copy()
master = master.merge(game_cs004[['game_pk','cs004_flag','cs004_tail_score']].rename(columns={'game_pk':'game_id'}), on='game_id', how='left')
master = master.merge(game_s12[['game_pk','s12_flag','s12_value']].drop_duplicates('game_pk').rename(columns={'game_pk':'game_id'}), on='game_id', how='left')
master = master.merge(game_p09[['game_pk','p09_flag','p09_value']].drop_duplicates('game_pk').rename(columns={'game_pk':'game_id'}), on='game_id', how='left')
master = master.merge(game_st02[['game_pk','st02_flag']].rename(columns={'game_pk':'game_id'}), on='game_id', how='left')
master = master.merge(game_cse[['game_pk','cse_flag']].drop_duplicates('game_pk').rename(columns={'game_pk':'game_id'}), on='game_id', how='left')

# Fill NaN flags with 0
for col in ['cs004_flag','s12_flag','p09_flag','st02_flag','cse_flag']:
    master[col] = master[col].fillna(0).astype(int)

# Context labels
def assign_context(row):
    overlays = []
    if row['s12_flag']: overlays.append('S12')
    if row['p09_flag']: overlays.append('P09')
    if row['st02_flag']: overlays.append('ST02')
    if row['cse_flag']: overlays.append('CSE')
    if not overlays:
        return 'V1_ONLY'
    return 'V1_' + '_'.join(overlays)

master['under_context'] = master.apply(assign_context, axis=1)

# Non-push subset
master_np = master[master['is_push'] == 0].copy()

logger.info(f"Master dataset: {len(master)} total, {len(master_np)} non-push")
logger.info(f"CS004 flagged: {master['cs004_flag'].sum()}")
logger.info(f"Context distribution:\n{master_np['under_context'].value_counts().to_string()}")

master.to_parquet(str(OUT / 'under_interaction_dataset.parquet'), index=False)

# ═══════════════════════════════════════════════════════════
# STEP 2 — POOLED UNDER TEST
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("STEP 2 — POOLED UNDER TEST")
logger.info("="*60)

pooled_rows = []
for label, mask in [('CS004=TRUE', master_np['cs004_flag']==1), ('CS004=FALSE', master_np['cs004_flag']==0)]:
    grp = master_np[mask]
    pooled_rows.append({
        'group': label, 'N': len(grp),
        'under_win_rate': round(grp['under_win'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'median_residual': round(grp['market_residual'].median(), 3),
        'mean_clv': round(grp['clv'].mean(), 3) if grp['clv'].notna().any() else None,
    })
    logger.info(f"  {label}: N={len(grp)}, under_win={grp['under_win'].mean():.4f}, "
                f"resid={grp['market_residual'].mean():+.3f}, clv={grp['clv'].mean():+.3f}")

pooled_df = pd.DataFrame(pooled_rows)
pooled_df.to_parquet(str(OUT / 'cs004_pooled_under_results.parquet'), index=False)

delta_wr = pooled_rows[0]['under_win_rate'] - pooled_rows[1]['under_win_rate']
delta_res = pooled_rows[0]['mean_residual'] - pooled_rows[1]['mean_residual']
broad_caution = delta_wr < -0.02  # CS004 TRUE hurts UNDER by 2pp+
logger.info(f"  Delta under win rate: {delta_wr:+.4f}")
logger.info(f"  Delta residual: {delta_res:+.3f}")
logger.info(f"  CAUTION_BROAD: {broad_caution}")

# ═══════════════════════════════════════════════════════════
# STEP 3 — BY-CONTEXT TEST
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("STEP 3 — BY-CONTEXT TEST")
logger.info("="*60)

# Simplify contexts for grouping
def simple_context(row):
    if row['s12_flag'] and not row['p09_flag'] and not row['st02_flag']:
        return 'V1_S12'
    elif row['p09_flag'] and not row['s12_flag']:
        return 'V1_P09'
    elif row['st02_flag'] and not row['s12_flag'] and not row['p09_flag']:
        return 'V1_ST02'
    elif row['cse_flag'] and not row['s12_flag'] and not row['p09_flag'] and not row['st02_flag']:
        return 'V1_CSE'
    elif not row['s12_flag'] and not row['p09_flag'] and not row['st02_flag'] and not row['cse_flag']:
        return 'V1_ONLY'
    else:
        return 'OTHER_COMBO'

master_np['simple_context'] = master_np.apply(simple_context, axis=1)

context_rows = []
for ctx in ['V1_ONLY','V1_S12','V1_P09','V1_ST02','V1_CSE','OTHER_COMBO']:
    ctx_data = master_np[master_np['simple_context'] == ctx]
    if len(ctx_data) < 10:
        continue
    for cs_label, cs_mask in [('CS004=TRUE', ctx_data['cs004_flag']==1), ('CS004=FALSE', ctx_data['cs004_flag']==0)]:
        grp = ctx_data[cs_mask]
        thin = 'THIN_SAMPLE' if len(grp) < 30 else ''
        context_rows.append({
            'context': ctx, 'cs004': cs_label, 'N': len(grp),
            'under_win_rate': round(grp['under_win'].mean(), 4) if len(grp) > 0 else None,
            'mean_residual': round(grp['market_residual'].mean(), 3) if len(grp) > 0 else None,
            'mean_clv': round(grp['clv'].mean(), 3) if len(grp) > 0 and grp['clv'].notna().any() else None,
            'thin': thin,
        })

context_df = pd.DataFrame(context_rows)
context_df.to_parquet(str(OUT / 'cs004_context_results.parquet'), index=False)

# Print and compute deltas
logger.info(f"\n  {'Context':<15s} {'CS004':<13s} {'N':>5s} {'UndWR':>7s} {'Resid':>7s} {'CLV':>7s} {'Flag'}")
for ctx in ['V1_ONLY','V1_S12','V1_P09','V1_ST02','V1_CSE','OTHER_COMBO']:
    rows = context_df[context_df['context'] == ctx]
    for _, r in rows.iterrows():
        thin = f" [{r['thin']}]" if r['thin'] else ""
        _clv_str = "  N/A" if r['mean_clv'] is None else f"{r['mean_clv']:+.3f}"
        logger.info(f"  {r['context']:<15s} {r['cs004']:<13s} {r['N']:5d} "
                     f"{r['under_win_rate']:.4f} {r['mean_residual']:+.3f} "
                     f"{_clv_str}{thin}")


# ═══════════════════════════════════════════════════════════
# STEP 4 — KEY COMBINATIONS
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("STEP 4 — KEY COMBINATIONS")
logger.info("="*60)

combo_rows = []
for combo_name, combo_mask in [
    ('P09+CS004', (master_np['p09_flag']==1) & (master_np['cs004_flag']==1)),
    ('P09 only',  (master_np['p09_flag']==1) & (master_np['cs004_flag']==0)),
    ('ST02+CS004', (master_np['st02_flag']==1) & (master_np['cs004_flag']==1)),
    ('ST02 only',  (master_np['st02_flag']==1) & (master_np['cs004_flag']==0)),
    ('S12+CS004', (master_np['s12_flag']==1) & (master_np['cs004_flag']==1)),
    ('S12 only',  (master_np['s12_flag']==1) & (master_np['cs004_flag']==0)),
    ('CSE+CS004', (master_np['cse_flag']==1) & (master_np['cs004_flag']==1)),
    ('CSE only',  (master_np['cse_flag']==1) & (master_np['cs004_flag']==0)),
]:
    grp = master_np[combo_mask]
    if len(grp) < 5:
        continue
    thin = 'THIN_SAMPLE' if len(grp) < 30 else ''
    combo_rows.append({
        'combination': combo_name, 'N': len(grp),
        'under_win_rate': round(grp['under_win'].mean(), 4),
        'mean_residual': round(grp['market_residual'].mean(), 3),
        'thin': thin,
    })
    logger.info(f"  {combo_name:<18s}: N={len(grp):4d} UndWR={grp['under_win'].mean():.4f} "
                f"Resid={grp['market_residual'].mean():+.3f}{' [THIN]' if thin else ''}")

combo_df = pd.DataFrame(combo_rows)
combo_df.to_parquet(str(OUT / 'cs004_combination_results.parquet'), index=False)

# ═══════════════════════════════════════════════════════════
# STEP 5 — DEFENSIVE FILTER VALUE
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("STEP 5 — DEFENSIVE FILTER VALUE")
logger.info("="*60)

def defensive_test(df, label):
    all_plays = df.copy()
    excl = df[df['cs004_flag'] == 0]
    removed = len(all_plays) - len(excl)
    old_wr = all_plays['under_win'].mean()
    new_wr = excl['under_win'].mean() if len(excl) > 0 else None
    old_res = all_plays['market_residual'].mean()
    new_res = excl['market_residual'].mean() if len(excl) > 0 else None
    return {
        'segment': label, 'N_all': len(all_plays), 'N_removed': removed,
        'N_remaining': len(excl),
        'old_under_wr': round(old_wr, 4),
        'new_under_wr': round(new_wr, 4) if new_wr else None,
        'wr_improvement': round((new_wr - old_wr)*100, 2) if new_wr else None,
        'old_residual': round(old_res, 3),
        'new_residual': round(new_res, 3) if new_res else None,
        'resid_improvement': round(old_res - new_res, 3) if new_res else None,
    }

filter_rows = [defensive_test(master_np, 'ALL_UNDER')]
for ctx in ['V1_ONLY','V1_S12','V1_P09','V1_ST02','V1_CSE']:
    sub = master_np[master_np['simple_context'] == ctx]
    if len(sub) >= 30:
        filter_rows.append(defensive_test(sub, ctx))

filter_df = pd.DataFrame(filter_rows)
filter_df.to_parquet(str(OUT / 'cs004_defensive_filter_results.parquet'), index=False)

for _, r in filter_df.iterrows():
    logger.info(f"  {r['segment']:<15s}: N={r['N_all']}, removed={r['N_removed']}, "
                f"WR: {r['old_under_wr']:.4f}→{r['new_under_wr']:.4f} ({r['wr_improvement']:+.2f}pp), "
                f"Resid: {r['old_residual']:+.3f}→{r['new_residual']:+.3f}")

# ═══════════════════════════════════════════════════════════
# STEP 7 — SEASON STABILITY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("STEP 7 — SEASON STABILITY")
logger.info("="*60)

for yr in [2024, 2025]:
    yr_data = master_np[master_np['season'] == yr]
    cs_true = yr_data[yr_data['cs004_flag'] == 1]
    cs_false = yr_data[yr_data['cs004_flag'] == 0]
    if len(cs_true) > 0 and len(cs_false) > 0:
        delta = cs_true['under_win'].mean() - cs_false['under_win'].mean()
        logger.info(f"  {yr}: CS004=T N={len(cs_true)} UndWR={cs_true['under_win'].mean():.4f} | "
                     f"CS004=F N={len(cs_false)} UndWR={cs_false['under_win'].mean():.4f} | "
                     f"Delta={delta:+.4f}")

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
logger.info("\n" + "="*60)
logger.info("SUMMARY")
logger.info("="*60)
logger.info(f"  Pooled delta under WR: {delta_wr:+.4f}")
logger.info(f"  Broad caution: {broad_caution}")
logger.info(f"  Defensive filter WR improvement: {filter_rows[0]['wr_improvement']:+.2f}pp")
logger.info("\nDone.")
