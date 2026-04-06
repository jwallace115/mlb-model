#!/usr/bin/env python3
"""Phase 3: NFL Player Props Audit."""
import os, sys
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

import nflreadpy

SEP = "=" * 70

# STEP 1
print(SEP)
print("STEP 1 — PROPS ARCHIVE AUDIT")
print(SEP)

dfs = []
for root, dirs, files in os.walk('data/odds_archive/nfl/props'):
    for f in files:
        if f.endswith('.parquet'):
            dfs.append(pd.read_parquet(os.path.join(root, f)))
props = pd.concat(dfs, ignore_index=True)
print(f'Total props rows: {len(props):,}')

focus = ['player_receptions', 'player_reception_yds', 'player_rush_yds',
         'player_rush_attempts', 'player_pass_yds', 'player_pass_tds',
         'player_pass_attempts', 'player_pass_completions',
         'player_pass_interceptions', 'player_anytime_td']

print(f'\n{"Market":<35} {"Rows":>8} {"Games":>6} {"Plyr":>6} {"Books":>5} '
      f'{"Med":>6} {"Min":>6} {"Max":>6}')
print("-" * 85)
for mk in focus:
    s = props[props['market_key'] == mk]
    if len(s) == 0: continue
    print(f'{mk:<35} {len(s):>8,} {s["event_id"].nunique():>6} '
          f'{s["player_name"].nunique():>6} {s["bookmaker"].nunique():>5} '
          f'{s["line"].median():>6.1f} {s["line"].min():>6.1f} {s["line"].max():>6.1f}')

# Snapshot depth
print("\nSnapshot depth (per player-game):")
for mk in ['player_receptions', 'player_reception_yds', 'player_rush_yds']:
    s = props[props['market_key'] == mk]
    snaps = s.groupby(['event_id', 'player_name']).size()
    print(f'  {mk}: mean={snaps.mean():.1f} med={snaps.median():.0f} '
          f'min={snaps.min()} max={snaps.max()} player_games={len(snaps)}')

# STEP 2
print(f"\n{SEP}")
print("STEP 2 — ACTUAL OUTCOMES AUDIT")
print(SEP)

ps = nflreadpy.load_player_stats([2025]).to_pandas()
print(f'Player stats: {len(ps)} rows, {ps["player_display_name"].nunique()} players')

for stat in ['receptions', 'receiving_yards', 'targets', 'rushing_yards',
             'rushing_attempts', 'passing_yards', 'completions', 'attempts']:
    if stat in ps.columns:
        n = ps[stat].notna().sum()
        print(f'  {stat}: {n}/{len(ps)} ({n/len(ps)*100:.0f}%)')

# Name matching
props_names = set(props[props['market_key'] == 'player_receptions']['player_name'].unique())
actual_names = set(ps['player_display_name'].unique())
overlap = len(props_names & actual_names)
print(f'\nName match: {overlap}/{len(props_names)} ({overlap/len(props_names)*100:.0f}%)')
miss = sorted(props_names - actual_names)[:5]
if miss:
    print(f'  Unmatched sample: {miss}')

# STEP 3
print(f"\n{SEP}")
print("STEP 3 — MARKET EFFICIENCY BASELINE (player_receptions)")
print(SEP)

dc = pd.read_parquet('nfl/data/nfl_derivative_canonical_2025.parquet')
eid_map = dc[['event_id', 'game_id']].dropna().drop_duplicates('event_id')

rec = props[props['market_key'] == 'player_receptions'].copy()
rec_close = rec.sort_values('last_update').groupby(['event_id', 'player_name', 'bookmaker']).tail(1)
rec_med = rec_close.groupby(['event_id', 'player_name']).agg(
    close_line=('line', 'median'), n_books=('bookmaker', 'nunique'),
).reset_index()
rec_med = rec_med.merge(eid_map, on='event_id', how='left')
rec_med['week'] = rec_med['game_id'].str.split('_').str[1].astype(float)

act = ps[['player_display_name', 'week', 'receptions']].rename(
    columns={'player_display_name': 'player_name'})
matched = rec_med.merge(act, on=['player_name', 'week'], how='inner')
print(f'Matched: {len(matched)} player-game-weeks')

if len(matched) > 100:
    matched['over'] = (matched['receptions'] > matched['close_line']).astype(int)
    matched['under'] = (matched['receptions'] < matched['close_line']).astype(int)
    matched['push'] = (matched['receptions'] == matched['close_line']).astype(int)
    matched['err'] = matched['receptions'] - matched['close_line']

    print(f'  Over:  {matched["over"].mean():.3f}')
    print(f'  Under: {matched["under"].mean():.3f}')
    print(f'  Push:  {matched["push"].mean():.3f}')
    print(f'  MAE:   {matched["err"].abs().mean():.2f}')
    print(f'  Bias:  {matched["err"].mean():+.3f}')

    print("\n  By line bucket:")
    matched['bucket'] = pd.cut(matched['close_line'], bins=[0, 2, 3, 4, 5, 7, 15],
                               labels=['0-2', '2-3', '3-4', '4-5', '5-7', '7+'])
    for b in ['0-2', '2-3', '3-4', '4-5', '5-7', '7+']:
        sub = matched[matched['bucket'] == b]
        if len(sub) >= 20:
            print(f'    {b}: N={len(sub)} over={sub["over"].mean():.3f} '
                  f'mae={sub["err"].abs().mean():.2f} bias={sub["err"].mean():+.2f}')

# receiving yards
print(f'\n--- player_reception_yds baseline ---')
ryds = props[props['market_key'] == 'player_reception_yds'].copy()
ryds_cl = ryds.sort_values('last_update').groupby(['event_id', 'player_name', 'bookmaker']).tail(1)
ryds_med = ryds_cl.groupby(['event_id', 'player_name']).agg(
    close_line=('line', 'median'), n_books=('bookmaker', 'nunique')).reset_index()
ryds_med = ryds_med.merge(eid_map, on='event_id', how='left')
ryds_med['week'] = ryds_med['game_id'].str.split('_').str[1].astype(float)
act_r = ps[['player_display_name', 'week', 'receiving_yards']].rename(
    columns={'player_display_name': 'player_name'})
m_r = ryds_med.merge(act_r, on=['player_name', 'week'], how='inner')
if len(m_r) > 100:
    m_r['err'] = m_r['receiving_yards'] - m_r['close_line']
    print(f'  N={len(m_r)}, MAE={m_r["err"].abs().mean():.1f}yds, '
          f'bias={m_r["err"].mean():+.1f}yds, '
          f'over_rate={(m_r["receiving_yards"] > m_r["close_line"]).mean():.3f}')

# STEP 4
print(f"\n{SEP}")
print("STEP 4 — PARTICIPATION / ROLE DATA")
print(SEP)

try:
    inj = nflreadpy.load_injuries([2025]).to_pandas()
    print(f'Injury reports: {len(inj)} rows, {inj["gsis_id"].nunique()} players')
    if 'report_status' in inj.columns:
        print(f'  Statuses: {inj["report_status"].value_counts().head(5).to_dict()}')
except Exception as e:
    print(f'Injuries: {e}')

try:
    snaps = nflreadpy.load_snap_counts([2025]).to_pandas()
    print(f'\nSnap counts: {len(snaps)} rows, {snaps["player"].nunique()} players')
    snap_cols = [c for c in snaps.columns if 'snap' in c.lower() or 'pct' in c.lower()]
    print(f'  Snap columns: {snap_cols[:8]}')
except Exception as e:
    print(f'Snaps: {e}')

# Target share from player stats
if 'targets' in ps.columns and 'target_share' in ps.columns:
    wr = ps[ps['position'].isin(['WR', 'TE', 'RB'])]
    print(f'\nWR/TE/RB with target data: {len(wr)} player-games')
    print(f'  target_share coverage: {wr["target_share"].notna().mean():.0%}')
elif 'targets' in ps.columns:
    print(f'\ntargets column present, target_share: {"target_share" in ps.columns}')
    # Compute team targets per game to derive share
    wr = ps[ps['position'].isin(['WR', 'TE', 'RB'])].copy()
    team_targets = wr.groupby(['recent_team', 'week'])['targets'].transform('sum')
    wr['target_share_derived'] = wr['targets'] / team_targets.clip(lower=1)
    print(f'  Derived target_share: {wr["target_share_derived"].notna().mean():.0%}')
    print(f'  Mean target_share for WR1-type (share > 0.20): {wr[wr["target_share_derived"] > 0.20]["target_share_derived"].mean():.3f}')
