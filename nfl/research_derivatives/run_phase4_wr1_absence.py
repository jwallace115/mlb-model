#!/usr/bin/env python3
"""Phase 4: WR1 Absence → Reception Redistribution Test."""
import os, sys
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

import nflreadpy

SEP = "=" * 70

# ═══════════════════════════════════════════════════════════════
# LOAD ALL DATA
# ═══════════════════════════════════════════════════════════════
print("Loading data...")

# Player stats (actuals)
ps = nflreadpy.load_player_stats([2025]).to_pandas()

# Injury reports
inj = nflreadpy.load_injuries([2025]).to_pandas()

# Snap counts
snaps = nflreadpy.load_snap_counts([2025]).to_pandas()

# Schedule
sched = nflreadpy.load_schedules([2025]).to_pandas()

# Props archive
dfs = []
for root, dirs, files in os.walk('data/odds_archive/nfl/props'):
    for f in files:
        if f.endswith('.parquet'):
            dfs.append(pd.read_parquet(os.path.join(root, f)))
props = pd.concat(dfs, ignore_index=True)
rec_props = props[props['market_key'] == 'player_receptions'].copy()

# Derivative canonical (for event_id -> game_id mapping)
dc = pd.read_parquet('nfl/data/nfl_derivative_canonical_2025.parquet')
eid_map = dc[['event_id', 'game_id']].dropna().drop_duplicates('event_id')

print(f"Player stats: {len(ps)} rows")
print(f"Injuries: {len(inj)} rows")
print(f"Snap counts: {len(snaps)} rows")
print(f"Reception props: {len(rec_props)} rows")

# ═══════════════════════════════════════════════════════════════
# STEP 1 — DEFINE WR1
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 1 — DEFINE WR1")
print(SEP)

# WR1 = WR with highest rolling 4-week target share on each team
# This is pregame-safe because it uses prior weeks only.

wr_stats = ps[ps['position'] == 'WR'][['player_display_name', 'player_id', 'team',
                                        'week', 'season', 'targets', 'receptions',
                                        'receiving_yards']].copy()

# Compute team total targets per week
team_targets = ps.groupby(['team', 'week'])['targets'].sum().reset_index()
team_targets.columns = ['team', 'week', 'team_targets']
wr_stats = wr_stats.merge(team_targets, on=['team', 'week'], how='left')
wr_stats['target_share'] = wr_stats['targets'] / wr_stats['team_targets'].clip(lower=1)

# Rolling 4-week target share (shifted = prior only)
wr_stats = wr_stats.sort_values(['player_display_name', 'week'])
wr_stats['ts_r4'] = wr_stats.groupby('player_display_name')['target_share'].transform(
    lambda x: x.shift(1).rolling(4, min_periods=2).mean())

# WR1 = highest ts_r4 on team in that week
wr_valid = wr_stats.dropna(subset=['ts_r4']).copy()
wr1_idx = wr_valid.groupby(['team', 'week'])['ts_r4'].idxmax()
wr_valid['is_wr1'] = False
wr_valid.loc[wr1_idx, 'is_wr1'] = True

wr1_list = wr_valid[wr_valid['is_wr1']][['team', 'week', 'player_display_name', 'player_id', 'ts_r4']]
wr1_list.columns = ['team', 'week', 'wr1_name', 'wr1_id', 'wr1_ts_r4']

print(f"WR1 definitions: {len(wr1_list)} team-weeks")
print(f"Unique WR1 players: {wr1_list['wr1_name'].nunique()}")
print(f"Coverage: weeks {sorted(wr1_list['week'].unique())[:5]}...{sorted(wr1_list['week'].unique())[-3:]}")
print(f"Definition: WR with highest rolling 4-week target share (shifted/lagged)")

# ═══════════════════════════════════════════════════════════════
# STEP 2 — DEFINE ABSENCE STATE
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 2 — DEFINE WR1 ABSENCE")
print(SEP)

# Injury report: find WR1 who are OUT
# report_status values: Out, Questionable, Doubtful
# Simplest ground-truth absence: WR1 had 0 targets or didn't appear in game stats
out_set = set()
for _, row in wr1_list.iterrows():
    actual = ps[(ps['player_display_name'] == row['wr1_name']) & (ps['week'] == row['week'])]
    if len(actual) == 0 or actual['targets'].iloc[0] == 0:
        out_set.add((row['team'], row['week']))

# Also check injury report for OUT status (pregame-safe)
inj_out = inj[inj['report_status'] == 'Out'][['gsis_id', 'week']].drop_duplicates()
for _, row in wr1_list.iterrows():
    if len(inj_out[(inj_out['gsis_id'] == row['wr1_id']) & (inj_out['week'] == row['week'])]) > 0:
        out_set.add((row['team'], row['week']))

wr1_status = wr1_list.copy()
wr1_status['wr1_out'] = wr1_status.apply(lambda r: (r['team'], r['week']) in out_set, axis=1)

n_out = wr1_status['wr1_out'].sum()
n_active = len(wr1_status) - n_out
print(f"\nWR1 active: {n_active} team-weeks")
print(f"WR1 OUT: {n_out} team-weeks")
print(f"Absence rate: {n_out/len(wr1_status)*100:.1f}%")

# ═══════════════════════════════════════════════════════════════
# STEP 3 — DEFINE BENEFICIARY ROLES
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 3 — BENEFICIARY ROLES")
print(SEP)

# WR2 = second-highest ts_r4 WR on team
# TE1 = highest targets TE on team
# RB = any RB with receptions

# WR2
wr_no_wr1 = wr_valid[~wr_valid['is_wr1']].copy()
wr2_idx = wr_no_wr1.groupby(['team', 'week'])['ts_r4'].idxmax()
wr_no_wr1['is_wr2'] = False
wr_no_wr1.loc[wr2_idx, 'is_wr2'] = True
wr2_names = wr_no_wr1[wr_no_wr1['is_wr2']][['team', 'week', 'player_display_name']].rename(
    columns={'team': 'team', 'player_display_name': 'player_name'})
wr2_names['role'] = 'WR2'

# TE1
te_stats = ps[ps['position'] == 'TE'][['player_display_name', 'team', 'week', 'targets']].copy()
te_stats = te_stats.sort_values(['player_display_name', 'week'])
te_stats['tgt_r4'] = te_stats.groupby('player_display_name')['targets'].transform(
    lambda x: x.shift(1).rolling(4, min_periods=2).mean())
te_valid = te_stats.dropna(subset=['tgt_r4'])
te1_idx = te_valid.groupby(['team', 'week'])['tgt_r4'].idxmax()
te1_names = te_valid.loc[te1_idx][['team', 'week', 'player_display_name']].rename(
    columns={'team': 'team', 'player_display_name': 'player_name'})
te1_names['role'] = 'TE1'

# RB (any RB with reception props)
rb_in_props = set(rec_props[rec_props['player_name'].isin(
    ps[ps['position'] == 'RB']['player_display_name'].unique())]['player_name'].unique())
print(f"WR2 definitions: {len(wr2_names)} team-weeks")
print(f"TE1 definitions: {len(te1_names)} team-weeks")
print(f"RBs with reception props: {len(rb_in_props)} players")

# Combine roles
roles = pd.concat([wr2_names, te1_names], ignore_index=True)

# ═══════════════════════════════════════════════════════════════
# STEP 4 — BUILD TEST DATASET
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 4 — BUILD TEST DATASET")
print(SEP)

# Get closing lines
rec_close = rec_props.sort_values('last_update').groupby(
    ['event_id', 'player_name', 'bookmaker']).tail(1)
rec_med = rec_close.groupby(['event_id', 'player_name']).agg(
    close_line=('line', 'median'),
    close_over_price=('over_price', 'median'),
    close_under_price=('under_price', 'median'),
    n_books=('bookmaker', 'nunique'),
).reset_index()
rec_med = rec_med.merge(eid_map, on='event_id', how='left')
rec_med['week'] = rec_med['game_id'].str.split('_').str[1].astype(float)

# Get actuals
actuals = ps[['player_display_name', 'team', 'week', 'receptions', 'position']].rename(
    columns={'player_display_name': 'player_name', 'team': 'team'})

# Join props to actuals
test = rec_med.merge(actuals, on=['player_name', 'week'], how='inner')
print(f"Props+actuals matched: {len(test)}")

# Join role labels
test = test.merge(roles, on=['team', 'week', 'player_name'], how='left')

# RB role assignment
test.loc[(test['position'] == 'RB') & test['role'].isna(), 'role'] = 'RB'

# Join WR1 absence flag
test = test.merge(wr1_status[['team', 'week', 'wr1_out']], on=['team', 'week'], how='left')

# Filter to beneficiary roles only
beneficiaries = test[test['role'].isin(['WR2', 'TE1', 'RB'])].copy()
beneficiaries['over_hit'] = (beneficiaries['receptions'] > beneficiaries['close_line']).astype(int)

print(f"\nBeneficiary dataset: {len(beneficiaries)} player-games")
print(f"By role: {beneficiaries['role'].value_counts().to_dict()}")
print(f"WR1 out: {beneficiaries['wr1_out'].sum()} ({beneficiaries['wr1_out'].mean()*100:.1f}%)")

# Line buckets
beneficiaries['line_bucket'] = pd.cut(beneficiaries['close_line'],
    bins=[-0.1, 2.5, 4.5, 20], labels=['0.5-2.5', '3.0-4.5', '5.0+'])

# ═══════════════════════════════════════════════════════════════
# STEP 5 — HIT-RATE TEST
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 5 — HIT-RATE TEST")
print(SEP)

def print_comparison(label, active, out):
    n_a, n_o = len(active), len(out)
    if n_a < 10 or n_o < 5:
        print(f"  {label}: active N={n_a}, out N={n_o} — TOO THIN")
        return None
    or_a = active['over_hit'].mean()
    or_o = out['over_hit'].mean()
    delta = or_o - or_a
    line_a = active['close_line'].mean()
    line_o = out['close_line'].mean()
    print(f"  {label}:")
    print(f"    Active: N={n_a} line={line_a:.1f} over={or_a:.3f}")
    print(f"    WR1 Out: N={n_o} line={line_o:.1f} over={or_o:.3f}")
    print(f"    Delta: {delta:+.3f} ({delta*100:+.1f}pp)")
    return {'label': label, 'n_active': n_a, 'n_out': n_o, 'over_active': or_a,
            'over_out': or_o, 'delta': delta, 'line_active': line_a, 'line_out': line_o}

results = []

# Overall by role
print("\n--- Overall by role ---")
for role in ['WR2', 'TE1', 'RB']:
    sub = beneficiaries[beneficiaries['role'] == role]
    active = sub[sub['wr1_out'] == False]
    out = sub[sub['wr1_out'] == True]
    r = print_comparison(role, active, out)
    if r: results.append(r)

# By line bucket
print("\n--- By line bucket (all beneficiaries) ---")
for bucket in ['0.5-2.5', '3.0-4.5', '5.0+']:
    sub = beneficiaries[beneficiaries['line_bucket'] == bucket]
    active = sub[sub['wr1_out'] == False]
    out = sub[sub['wr1_out'] == True]
    r = print_comparison(f"Bucket {bucket}", active, out)
    if r: results.append(r)

# By role AND line bucket (most important)
print("\n--- By role AND line bucket ---")
for role in ['WR2', 'TE1', 'RB']:
    for bucket in ['0.5-2.5', '3.0-4.5', '5.0+']:
        sub = beneficiaries[(beneficiaries['role'] == role) & (beneficiaries['line_bucket'] == bucket)]
        active = sub[sub['wr1_out'] == False]
        out = sub[sub['wr1_out'] == True]
        r = print_comparison(f"{role} / {bucket}", active, out)
        if r: results.append(r)

# ═══════════════════════════════════════════════════════════════
# STEP 6 — MARKET-RELATIVE CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 6 — MARKET-RELATIVE CHECK")
print(SEP)

def american_to_implied(odds):
    if pd.isna(odds) or odds is None: return np.nan
    if odds < 0: return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)

beneficiaries['implied_over'] = beneficiaries['close_over_price'].apply(american_to_implied)

for r in results:
    if r['delta'] >= 0.02:  # Only check interesting ones
        label = r['label']
        sub = beneficiaries
        if '/' in label:
            parts = label.split(' / ')
            role_part = parts[0]
            bucket_part = parts[1]
            sub = sub[(sub['role'] == role_part) & (sub['line_bucket'] == bucket_part)]
        elif 'Bucket' in label:
            bucket_part = label.replace('Bucket ', '')
            sub = sub[sub['line_bucket'] == bucket_part]
        else:
            sub = sub[sub['role'] == label]

        out_sub = sub[sub['wr1_out'] == True]
        if len(out_sub) < 5:
            continue
        actual_over = out_sub['over_hit'].mean()
        implied_over = out_sub['implied_over'].mean()
        residual = actual_over - implied_over
        print(f"  {label} (WR1 out, N={len(out_sub)}):")
        print(f"    Actual over: {actual_over:.3f}")
        print(f"    Implied over: {implied_over:.3f}")
        print(f"    Residual: {residual:+.3f} ({residual*100:+.1f}pp)")

# ═══════════════════════════════════════════════════════════════
# STEP 7 — CONTROL CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 7 — CONTROL CHECK")
print(SEP)

# Add full-game total from archive
gm_dfs = []
for root, dirs, files in os.walk('data/odds_archive/nfl/game_markets'):
    for f in files:
        if f.endswith('.parquet'):
            gm_dfs.append(pd.read_parquet(os.path.join(root, f)))
gm = pd.concat(gm_dfs, ignore_index=True)
fg = gm[gm['market_key'] == 'totals'].groupby('event_id')['line'].median().reset_index()
fg.columns = ['event_id', 'fg_total']
fg = fg.merge(eid_map, on='event_id', how='left')
beneficiaries = beneficiaries.merge(fg[['game_id', 'fg_total']], on='game_id', how='left')

# Simple control: does WR1 absence still predict over_hit after controlling for game total + line?
from sklearn.linear_model import LogisticRegression

ctrl = beneficiaries.dropna(subset=['fg_total', 'close_line', 'wr1_out']).copy()
ctrl['wr1_out_int'] = ctrl['wr1_out'].astype(int)

if len(ctrl) > 100:
    X = ctrl[['close_line', 'fg_total', 'wr1_out_int']]
    y = ctrl['over_hit']
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X, y)
    coefs = dict(zip(X.columns, lr.coef_[0]))
    print(f"  Logistic regression (over_hit ~ line + fg_total + wr1_out):")
    for k, v in coefs.items():
        print(f"    {k}: {v:+.4f}")
    print(f"    wr1_out coefficient: {'POSITIVE (supports hypothesis)' if coefs['wr1_out_int'] > 0 else 'NEGATIVE (against hypothesis)'}")

# ═══════════════════════════════════════════════════════════════
# STEP 8 — CONCENTRATION CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 8 — CONCENTRATION CHECK")
print(SEP)

out_games = beneficiaries[beneficiaries['wr1_out'] == True]
if len(out_games) > 10:
    print(f"WR1-out beneficiary observations: {len(out_games)}")
    team_conc = out_games['team'].value_counts().head(10)
    print(f"\nTop 10 teams:")
    for t, n in team_conc.items():
        print(f"  {t}: {n} ({n/len(out_games)*100:.0f}%)")
    print(f"  Top 5 share: {team_conc.head(5).sum()/len(out_games)*100:.0f}%")

    player_conc = out_games['player_name'].value_counts().head(10)
    print(f"\nTop 10 players:")
    for p, n in player_conc.items():
        role = out_games[out_games['player_name'] == p]['role'].mode().iloc[0] if len(out_games[out_games['player_name'] == p]) > 0 else '?'
        over = out_games[out_games['player_name'] == p]['over_hit'].mean()
        print(f"  {p} ({role}): {n} games, over={over:.2f}")
    print(f"  Top 5 share: {player_conc.head(5).sum()/len(out_games)*100:.0f}%")

# ═══════════════════════════════════════════════════════════════
# DECISION
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("DECISION SUMMARY")
print(SEP)

strong = [r for r in results if r['delta'] >= 0.03 and r['n_out'] >= 15]
near = [r for r in results if 0.02 <= r['delta'] < 0.03 and r['n_out'] >= 10]
print(f"\nStrong candidates (delta >= +3pp, N_out >= 15): {len(strong)}")
for r in strong:
    print(f"  {r['label']}: delta={r['delta']:+.3f} N_out={r['n_out']}")
print(f"Near-miss candidates (delta +2-3pp, N_out >= 10): {len(near)}")
for r in near:
    print(f"  {r['label']}: delta={r['delta']:+.3f} N_out={r['n_out']}")
