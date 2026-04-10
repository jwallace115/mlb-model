#!/usr/bin/env python3
"""
Team Total Identity Audit
==========================
Tests whether the live TT signal is the same object as the original backtest.
Applies the LIVE formula to historical data and compares results.
"""
import json
import sys
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
PROJECT = Path('/root/mlb-model')
OUT = PROJECT / 'research' / 'recovery'

# Live formula constants (from mlb/pipeline/team_total_signal.py)
HOME_SHARE = 0.5015
TRUNCATION_ADJ = 0.248
LEAGUE_AVG_ERA = 4.50
SP_INNINGS_FACTOR = 0.621
GAP_THRESHOLD = 0.25

# Phase 6 report constants
REPORT_LEAGUE_AVG_XFIP = 4.231

results = []

def log(msg):
    results.append(msg)
    print(msg)

def grade(sub, line_col, actual_col):
    w = int((sub[actual_col] < sub[line_col]).sum())
    l = int((sub[actual_col] > sub[line_col]).sum())
    p = int((sub[actual_col] == sub[line_col]).sum())
    n = w + l
    if n == 0:
        return 0, 0, 0, 0, 0
    roi = (w * (100/110) - l) / n * 100
    wr = w / n * 100
    return n, p, wr, roi, w * (100/110) - l

# ===================================================================
# PHASE 1: CODE PATH COMPARISON
# ===================================================================
log('=' * 70)
log('PHASE 1: CODE PATH COMPARISON')
log('=' * 70)

log('')
log('PARAMETER COMPARISON:')
log('  %-30s %-20s %-20s %-20s' % ('Parameter', 'Phase 6 Report', 'Live Signal', 'Backtest v1/v2'))
log('  ' + '-' * 90)
log('  %-30s %-20s %-20s %-20s' % ('HOME_SHARE', '0.5015', '0.5015', 'N/A (sim-based)'))
log('  %-30s %-20s %-20s %-20s' % ('TRUNCATION_ADJ', '0.248', '0.248', 'N/A (sim-based)'))
log('  %-30s %-20s %-20s %-20s' % ('SP metric', 'xFIP', 'ERA', 'xFIP (via sim)'))
log('  %-30s %-20s %-20s %-20s' % ('League avg baseline', '4.231 (xFIP)', '4.50 (ERA)', 'per-pitcher xFIP'))
log('  %-30s %-20s %-20s %-20s' % ('SP_INNINGS_FACTOR', '0.621', '0.621', 'N/A'))
log('  %-30s %-20s %-20s %-20s' % ('GAP_THRESHOLD', '0.25', '0.25', 'N/A (run_gap)'))
log('  %-30s %-20s %-20s %-20s' % ('Direction: home under', 'YES', 'YES', 'suppressed under'))
log('  %-30s %-20s %-20s %-20s' % ('Direction: away under', 'YES', 'YES', 'suppressed under'))
log('  %-30s %-20s %-20s %-20s' % ('Direction: home over', 'YES', 'YES', 'no'))
log('  %-30s %-20s %-20s %-20s' % ('Direction: away over', 'NO (weak)', 'NO', 'no'))
log('  %-30s %-20s %-20s %-20s' % ('Starter source', 'feature_table xFIP', 'MLB API + PGL ERA', 'sim_inputs xFIP'))
log('  %-30s %-20s %-20s %-20s' % ('Min starts gate', 'none stated', 'none (shift(1))', 'sim coverage'))
log('  %-30s %-20s %-20s %-20s' % ('Degraded fallback', 'N/A', 'league avg ERA', 'N/A'))
log('  %-30s %-20s %-20s %-20s' % ('Price in log', 'real TT prices', 'NO prices', 'real TT prices'))

log('')
log('KEY FORMULA DIFFERENCES:')
log('  1. SP metric: Phase 6 report used xFIP (pitcher skill metric).')
log('     Live signal uses ERA (results-based). These are DIFFERENT stats.')
log('     xFIP avg ~4.23, ERA avg ~4.50 in the study period.')
log('  2. League avg baseline: 4.231 (xFIP) vs 4.50 (ERA).')
log('  3. Backtest v1/v2 used SIMULATION-DERIVED per-team projections,')
log('     not the formula at all. They use Monte Carlo with S2 starter')
log('     path model + neg-binomial draws. They identify "suppressed team"')
log('     (lower mu) and bet THAT team TT under.')
log('     This is a COMPLETELY DIFFERENT methodology from the live formula.')

# ===================================================================
# PHASE 2: LIVE FORMULA APPLIED TO HISTORICAL DATA
# ===================================================================
log('')
log('=' * 70)
log('PHASE 2: LIVE FORMULA APPLIED TO HISTORICAL DATA')
log('=' * 70)

canon = pd.read_parquet(PROJECT / 'mlb_sim' / 'data' / 'mlb_odds_closing_canonical.parquet')
canon = canon[canon['home_total_line'].notna()].copy()

ft = pd.read_parquet(PROJECT / 'sim' / 'data' / 'feature_table.parquet')
ft['game_pk'] = ft['game_pk'].astype(str)

pgl = pd.read_parquet(PROJECT / 'mlb' / 'data' / 'pitcher_game_logs.parquet')
sp = pgl[pgl['starter_flag'] == 1].copy()
sp = sp.sort_values(['player_id', 'season', 'game_date'])

# Build PIT-safe expanding ERA (shift(1))
sp['cum_er'] = sp.groupby('player_id')['earned_runs'].transform(
    lambda x: x.shift(1).expanding().sum())
sp['cum_ip'] = sp.groupby('player_id')['innings_pitched'].transform(
    lambda x: x.shift(1).expanding().sum())
sp['pregame_era'] = np.where(sp['cum_ip'] > 0, sp['cum_er'] / sp['cum_ip'] * 9, np.nan)
sp['start_num'] = sp.groupby('player_id').cumcount() + 1

sp_lookup = sp[['game_pk', 'player_id', 'pregame_era', 'start_num', 'home_away']].copy()
sp_lookup['game_pk'] = sp_lookup['game_pk'].astype(str)

canon['game_pk'] = canon['game_pk'].astype(str)

# Only keep FT columns we need (avoid collisions)
ft_cols = ft[['game_pk', 'season', 'home_score', 'away_score', 'actual_total',
              'home_sp_id', 'away_sp_id', 'date', 'home_team', 'away_team']].copy()
ft_cols = ft_cols.drop_duplicates(subset=['game_pk'])

# Drop canon's own season/date to avoid collisions
canon_slim = canon.drop(columns=['season', 'date'], errors='ignore')
df = canon_slim.merge(ft_cols, on='game_pk', how='inner')

log('  Games with TT lines + scores: %d' % len(df))
log('  By season: %s' % df.groupby('season').size().to_dict())

# PGL uses 'H'/'A' for home_away
home_sp = sp_lookup[sp_lookup['home_away'] == 'H'][
    ['game_pk', 'player_id', 'pregame_era', 'start_num']]
home_sp = home_sp.rename(columns={
    'player_id': 'home_sp_pid', 'pregame_era': 'home_sp_era',
    'start_num': 'home_sp_starts'})
df = df.merge(home_sp, on='game_pk', how='left')

away_sp = sp_lookup[sp_lookup['home_away'] == 'A'][
    ['game_pk', 'player_id', 'pregame_era', 'start_num']]
away_sp = away_sp.rename(columns={
    'player_id': 'away_sp_pid', 'pregame_era': 'away_sp_era',
    'start_num': 'away_sp_starts'})
df = df.merge(away_sp, on='game_pk', how='left')

log('  Home SP ERA available: %d/%d' % (df['home_sp_era'].notna().sum(), len(df)))
log('  Away SP ERA available: %d/%d' % (df['away_sp_era'].notna().sum(), len(df)))
log('  Both available: %d/%d' % (
    (df['home_sp_era'].notna() & df['away_sp_era'].notna()).sum(), len(df)))

df['h_era'] = df['home_sp_era'].fillna(LEAGUE_AVG_ERA)
df['a_era'] = df['away_sp_era'].fillna(LEAGUE_AVG_ERA)

closing_total = df['home_total_line'] + df['away_total_line']
df['closing_total'] = closing_total

sp_adj_home = (df['a_era'] - LEAGUE_AVG_ERA) * SP_INNINGS_FACTOR
sp_adj_away = (df['h_era'] - LEAGUE_AVG_ERA) * SP_INNINGS_FACTOR

df['fair_home'] = closing_total * HOME_SHARE - TRUNCATION_ADJ + sp_adj_home
df['fair_away'] = closing_total * (1 - HOME_SHARE) + sp_adj_away

df['gap_home'] = df['home_total_line'] - df['fair_home']
df['gap_away'] = df['away_total_line'] - df['fair_away']

df['home_tt_under'] = df['gap_home'] > GAP_THRESHOLD
df['away_tt_under'] = df['gap_away'] > GAP_THRESHOLD
df['home_tt_over'] = df['gap_home'] < -GAP_THRESHOLD

full = df[df['home_sp_era'].notna() & df['away_sp_era'].notna()].copy()
log('  Non-degraded games: %d' % len(full))

log('')
log('LIVE FORMULA RESULTS (non-degraded, ERA-based):')
log('')

for season in [2022, 2023, 2024, 2025, 'ALL']:
    if season == 'ALL':
        sub = full
    else:
        sub = full[full['season'] == season]
    if len(sub) == 0:
        continue

    h_under = sub[sub['home_tt_under']]
    a_under = sub[sub['away_tt_under']]
    h_over = sub[sub['home_tt_over']]

    log('  Season %s (N=%d):' % (season, len(sub)))
    log('    Fire rates: H_UNDER=%d (%.1f%%), A_UNDER=%d (%.1f%%), H_OVER=%d (%.1f%%)' % (
        len(h_under), len(h_under)/len(sub)*100,
        len(a_under), len(a_under)/len(sub)*100,
        len(h_over), len(h_over)/len(sub)*100))

    for label, sig_df, line_col, actual_col in [
        ('H_UNDER', h_under, 'home_total_line', 'home_score'),
        ('A_UNDER', a_under, 'away_total_line', 'away_score'),
        ('H_OVER', h_over, 'home_total_line', 'home_score'),
    ]:
        n, p, wr, roi, net = grade(sig_df, line_col, actual_col)
        if n > 0:
            log('    %s: N=%d+%dpush, win%%=%.1f%%, ROI=%+.1f%%, net=%+.1fu' % (
                label, n, p, wr, roi, net))

# Fire rate by month
log('')
log('FIRE RATE BY MONTH (non-degraded):')
full['month'] = pd.to_datetime(full['date']).dt.month
for m in range(3, 11):
    sub = full[full['month'] == m]
    if len(sub) == 0:
        continue
    h_u = sub['home_tt_under'].sum()
    a_u = sub['away_tt_under'].sum()
    log('  Month %d: N=%d, H_UNDER=%d (%.1f%%), A_UNDER=%d (%.1f%%)' % (
        m, len(sub), h_u, h_u/len(sub)*100, a_u, a_u/len(sub)*100))

# Fire rate by starter prior-start count
log('')
log('FIRE RATE BY SP START COUNT (non-degraded, both SP):')
for start_gate in [1, 2, 3, 5, 10]:
    sub = full[(full['home_sp_starts'] >= start_gate) & (full['away_sp_starts'] >= start_gate)]
    if len(sub) == 0:
        continue
    h_under_sub = sub[sub['home_tt_under']]
    a_under_sub = sub[sub['away_tt_under']]
    n_h, _, wr_h, roi_h, _ = grade(h_under_sub, 'home_total_line', 'home_score')
    n_a, _, wr_a, roi_a, _ = grade(a_under_sub, 'away_total_line', 'away_score')
    log('  Starts >= %d: N_games=%d, H_UNDER: N=%d wr=%.1f%% roi=%+.1f%% | A_UNDER: N=%d wr=%.1f%% roi=%+.1f%%' % (
        start_gate, len(sub), n_h, wr_h, roi_h, n_a, wr_a, roi_a))

# ===================================================================
# PHASE 6 REPORT FORMULA (xFIP-based) FOR COMPARISON
# ===================================================================
log('')
log('=' * 70)
log('PHASE 6 REPORT FORMULA (xFIP-based) FOR COMPARISON')
log('=' * 70)

ft_cols2 = ft[['game_pk', 'season', 'home_score', 'away_score', 'actual_total',
               'home_sp_xfip', 'away_sp_xfip', 'date', 'home_team', 'away_team']].drop_duplicates(subset=['game_pk'])
df2 = canon_slim.merge(ft_cols2, on='game_pk', how='inner')

full2 = df2[df2['home_sp_xfip'].notna() & df2['away_sp_xfip'].notna()].copy()
log('  Games with TT lines + xFIP: %d' % len(full2))

closing_total2 = full2['home_total_line'] + full2['away_total_line']
sp_adj_home2 = (full2['away_sp_xfip'] - REPORT_LEAGUE_AVG_XFIP) * SP_INNINGS_FACTOR
sp_adj_away2 = (full2['home_sp_xfip'] - REPORT_LEAGUE_AVG_XFIP) * SP_INNINGS_FACTOR

full2['fair_home'] = closing_total2 * HOME_SHARE - TRUNCATION_ADJ + sp_adj_home2
full2['fair_away'] = closing_total2 * (1 - HOME_SHARE) + sp_adj_away2
full2['gap_home'] = full2['home_total_line'] - full2['fair_home']
full2['gap_away'] = full2['away_total_line'] - full2['fair_away']
full2['home_tt_under'] = full2['gap_home'] > GAP_THRESHOLD
full2['away_tt_under'] = full2['gap_away'] > GAP_THRESHOLD
full2['home_tt_over'] = full2['gap_home'] < -GAP_THRESHOLD

log('')
log('PHASE 6 REPORT FORMULA RESULTS (xFIP-based):')
for season in [2023, 2024, 2025, 'ALL']:
    if season == 'ALL':
        sub = full2
    else:
        sub = full2[full2['season'] == season]
    if len(sub) == 0:
        continue

    h_under = sub[sub['home_tt_under']]
    a_under = sub[sub['away_tt_under']]
    h_over = sub[sub['home_tt_over']]

    log('  Season %s (N=%d):' % (season, len(sub)))
    log('    Fire rates: H_UNDER=%d (%.1f%%), A_UNDER=%d (%.1f%%), H_OVER=%d (%.1f%%)' % (
        len(h_under), len(h_under)/len(sub)*100,
        len(a_under), len(a_under)/len(sub)*100,
        len(h_over), len(h_over)/len(sub)*100))

    for label, sig_df, line_col, actual_col in [
        ('H_UNDER', h_under, 'home_total_line', 'home_score'),
        ('A_UNDER', a_under, 'away_total_line', 'away_score'),
        ('H_OVER', h_over, 'home_total_line', 'home_score'),
    ]:
        n, p, wr, roi, net = grade(sig_df, line_col, actual_col)
        if n > 0:
            log('    %s: N=%d+%dpush, win%%=%.1f%%, ROI=%+.1f%%, net=%+.1fu' % (
                label, n, p, wr, roi, net))

# ===================================================================
# PHASE 3: LOOK-AHEAD / PIT SAFETY CHECK
# ===================================================================
log('')
log('=' * 70)
log('PHASE 3: LOOK-AHEAD / PIT SAFETY CHECK')
log('=' * 70)

log('')
log('Feature table xFIP check (is it look-ahead?):')
ft_sp = ft[ft['home_sp_xfip'].notna()].copy()
ft_sp['month'] = pd.to_datetime(ft_sp['date']).dt.month

sp_var = ft_sp.groupby(['season', 'home_sp_id'])['home_sp_xfip'].agg(['std', 'count'])
sp_var = sp_var[sp_var['count'] >= 10]
log('  Avg within-pitcher-season std of xFIP: %.4f' % sp_var['std'].mean())
log('  Pitchers with std=0 (constant = look-ahead): %d/%d' % (
    (sp_var['std'] == 0).sum(), len(sp_var)))
if sp_var['std'].mean() < 0.01:
    log('  *** WARNING: xFIP appears CONSTANT within season -> likely END-OF-SEASON (LOOK-AHEAD)')
else:
    log('  xFIP appears to vary within season -> likely game-day or rolling')

# ===================================================================
# PHASE 4: PRICE CONSISTENCY
# ===================================================================
log('')
log('=' * 70)
log('PHASE 4: PRICE CONSISTENCY')
log('=' * 70)

log('')
log('Live signal: NO prices logged (confirmed from shadow log keys)')
log('')
log('Phase 6 report: All ROI computed at FLAT -110')
log('  Quote: "No juice adjustment. All ROI computed at flat -110."')
log('')
log('Backtest v1/v2: Real TT prices available but ROI also computed at flat -110')
log('')

tt_hist = pd.read_parquet(PROJECT / 'research' / 'team_totals' / 'data' / 'team_totals_historical.parquet')
ok = tt_hist[tt_hist['pull_status'] == 'ok']
log('Actual TT under juice (from research historical):')
for col in ['home_under_price', 'away_under_price']:
    vals = ok[col].dropna()
    imp = np.where(vals < 0, -vals / (-vals + 100), 100 / (vals + 100))
    log('  %s: mean American=%.0f, mean implied prob=%.4f' % (col, vals.mean(), imp.mean()))

log('')
log('Canonical TT under prices:')
tt_canon = canon[canon['home_total_line'].notna()]
for col in ['home_total_under_price', 'away_total_under_price']:
    vals = tt_canon[col].dropna()
    imp = np.where(vals < 0, -vals / (-vals + 100), 100 / (vals + 100))
    log('  %s: mean American=%.0f, mean implied prob=%.4f' % (col, vals.mean(), imp.mean()))

# ===================================================================
# PHASE 5: FINAL VERDICT
# ===================================================================
log('')
log('=' * 70)
log('PHASE 5: FINAL VERDICT')
log('=' * 70)

log('')
log('FINDING 1 -- THREE DIFFERENT OBJECTS:')
log('  A. Phase 6 report (the "58%%/56%%" claims):')
log('     - Formula: HOME_SHARE=0.5015, TRUNCATION=0.248, SP=xFIP, baseline=4.231')
log('     - Used feature_table xFIP (potentially look-ahead)')
log('     - Hit rates reported: 56-58%% at various thresholds')
log('     - Against: posted TT lines from team_totals_historical.parquet')
log('')
log('  B. Backtest v1/v2 scripts (research/team_totals/):')
log('     - Completely different methodology: Monte Carlo simulation')
log('     - Uses S2 starter-path model + negative binomial draws')
log('     - Identifies "suppressed team" by sim-derived expected runs')
log('     - Bets suppressed team TT under when run_gap >= threshold')
log('     - This is NOT the same formula as Phase 6 or live')
log('')
log('  C. Live signal (mlb/pipeline/team_total_signal.py):')
log('     - Formula: HOME_SHARE=0.5015, TRUNCATION=0.248, SP=ERA, baseline=4.50')
log('     - Uses pitcher_game_logs expanding ERA (PIT-safe, shift(1))')
log('     - Gets starter identity from MLB Stats API probablePitcher')
log('     - No prices logged')
log('     - Degraded mode: falls back to league avg ERA when pitcher unknown')
log('')
log('FINDING 2 -- FORMULA DRIFT (Phase 6 Report -> Live):')
log('  - SP metric changed: xFIP -> ERA (different stat entirely)')
log('  - League baseline changed: 4.231 -> 4.50')
log('  - These changes were NOT validated with a backtest')
log('  - The 58%%/56%% claims from Phase 6 report CANNOT be attributed to')
log('    the live formula because the live formula uses different inputs')
log('')
log('FINDING 3 -- POTENTIAL LOOK-AHEAD in Phase 6:')
log('  - Feature table xFIP may be end-of-season (check std analysis above)')
log('  - If look-ahead, the 58%%/56%% claims are inflated')
log('')
log('FINDING 4 -- PRICE GAP:')
log('  - All backtests used flat -110 ROI')
log('  - Live signal logs NO prices')
log('  - Real TT under prices may carry heavier juice')
log('  - At true vig, break-even is higher than 52.4%%')

log('')
log('=' * 70)
log('VERDICT: NEVER-MATCHED')
log('=' * 70)
log('')
log('The live TT signal was NEVER the same object as the original backtest.')
log('Three distinct methodologies exist:')
log('  1. Phase 6 formula (xFIP-based, possibly look-ahead)')
log('  2. Backtest v1/v2 (simulation-based suppressed team)')
log('  3. Live signal (ERA-based formula, different baseline)')
log('')
log('The 58%%/56%% hit rates from Phase 6 were generated with xFIP (baseline')
log('4.231). The live signal uses ERA (baseline 4.50). These are different')
log('stats with different distributions. No backtest validated the ERA switch.')
log('')
log('Additionally, the backtest scripts in research/team_totals/ use an')
log('entirely different approach (Monte Carlo simulation) that has NO')
log('connection to the formula used in the live signal.')

# Save report
with open(OUT / 'tt_identity_audit_report.txt', 'w') as f:
    f.write('\n'.join(results))
print('\nReport saved to %s' % (OUT / 'tt_identity_audit_report.txt'))
