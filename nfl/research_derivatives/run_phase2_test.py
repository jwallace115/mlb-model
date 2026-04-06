#!/usr/bin/env python3
"""Phase 2: Offensive Script Shape Regime Matchup Test."""
import os, sys
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

import nflreadpy
import polars as pl

pbp = nflreadpy.load_pbp([2025])
sched = nflreadpy.load_schedules([2025]).to_pandas()
dc = pd.read_parquet('nfl/data/nfl_derivative_canonical_2025.parquet')

h1 = pbp.filter(pl.col('game_half') == 'Half1')
plays = h1.filter(pl.col('play_type').is_in(['pass', 'run', 'qb_kneel', 'qb_spike']))

off = plays.group_by(['game_id', 'posteam']).agg([
    pl.col('epa').count().alias('h1_plays'),
    pl.col('pass_attempt').sum().alias('h1_pass_att'),
    pl.col('rush_attempt').sum().alias('h1_rush_att'),
    pl.col('epa').mean().alias('h1_epa'),
    pl.col('success').mean().alias('h1_success'),
    pl.col('no_huddle').mean().alias('h1_no_huddle'),
    (pl.col('yards_gained') >= 20).sum().alias('h1_explosive'),
    pl.col('sack').sum().alias('h1_sacks'),
]).to_pandas()

off['h1_pass_rate'] = off['h1_pass_att'] / (off['h1_pass_att'] + off['h1_rush_att']).clip(lower=1)
off['h1_explosive_rate'] = off['h1_explosive'] / off['h1_plays'].clip(lower=1)
off['h1_sack_rate'] = off['h1_sacks'] / off['h1_plays'].clip(lower=1)

game_order = sched[['game_id', 'season', 'week', 'game_type']].drop_duplicates('game_id')
off = off.merge(game_order, on='game_id', how='left').sort_values(['posteam', 'season', 'week'])

regime_feats = ['h1_pass_rate', 'h1_explosive_rate', 'h1_epa', 'h1_no_huddle', 'h1_sack_rate']
for c in regime_feats:
    off[f'{c}_r4'] = off.groupby('posteam')[c].transform(lambda x: x.shift(1).rolling(4, min_periods=2).mean())

r4_feats = [f'{c}_r4' for c in regime_feats]
off_clean = off.dropna(subset=r4_feats).copy()

# STEP 1
print("=" * 70)
print("STEP 1 — K=2 vs K=3")
print("=" * 70)

sc = StandardScaler()
X = sc.fit_transform(off_clean[r4_feats])

for k in [2, 3]:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    off_clean[f'cl_{k}'] = km.fit_predict(X)
    cent = pd.DataFrame(sc.inverse_transform(km.cluster_centers_), columns=r4_feats)
    print(f"\nK={k}:")
    for i in range(k):
        n = (off_clean[f'cl_{k}'] == i).sum()
        print(f"  Cl {i}: N={n}  epa={cent.loc[i,'h1_epa_r4']:.3f}  pass={cent.loc[i,'h1_pass_rate_r4']:.3f}  "
              f"expl={cent.loc[i,'h1_explosive_rate_r4']:.3f}  nh={cent.loc[i,'h1_no_huddle_r4']:.3f}  "
              f"sack={cent.loc[i,'h1_sack_rate_r4']:.3f}")

k3_min = off_clean['cl_3'].value_counts().min()
chosen_k = 2 if k3_min < 20 else 3
print(f"\nK=3 min cluster: {k3_min}. Chosen: K={chosen_k}")

km_final = KMeans(n_clusters=chosen_k, random_state=42, n_init=10)
off_clean['cluster'] = km_final.fit_predict(X)
cent_final = pd.DataFrame(sc.inverse_transform(km_final.cluster_centers_), columns=r4_feats)

labels = {}
if chosen_k == 2:
    for i in range(2):
        labels[i] = 'EFFICIENT' if cent_final.loc[i, 'h1_epa_r4'] > cent_final['h1_epa_r4'].mean() else 'STRUGGLING'
else:
    epa_rank = cent_final['h1_epa_r4'].rank()
    for i in range(3):
        if cent_final.loc[i, 'h1_no_huddle_r4'] > 0.2:
            labels[i] = 'TEMPO'
        elif epa_rank[i] == 3:
            labels[i] = 'EFFICIENT'
        elif epa_rank[i] == 1:
            labels[i] = 'STRUGGLING'
        else:
            labels[i] = 'BALANCED'

off_clean['label'] = off_clean['cluster'].map(labels)
print(f"Labels: {labels}")
for lab in sorted(set(labels.values())):
    print(f"  {lab}: N={len(off_clean[off_clean['label'] == lab])}")

# STEP 2
print("\n" + "=" * 70)
print("STEP 2 — MATCHUP CELL TEST")
print("=" * 70)

sched_teams = sched[['game_id', 'home_team', 'away_team']].drop_duplicates('game_id')
home_lab = off_clean[['game_id', 'posteam', 'label']].merge(
    sched_teams, left_on=['game_id', 'posteam'], right_on=['game_id', 'home_team']
).rename(columns={'label': 'home_off'})[['game_id', 'home_off']]
away_lab = off_clean[['game_id', 'posteam', 'label']].merge(
    sched_teams, left_on=['game_id', 'posteam'], right_on=['game_id', 'away_team']
).rename(columns={'label': 'away_off'})[['game_id', 'away_off']]

cells = dc[['game_id', 'h1_total_close', 'total_points_h1']].copy()
cells = cells.merge(home_lab, on='game_id', how='left')
cells = cells.merge(away_lab, on='game_id', how='left')
cells = cells.merge(game_order[['game_id', 'week', 'game_type']], on='game_id', how='left')
reg = cells[(cells['game_type'] == 'REG') & cells['home_off'].notna() & cells['away_off'].notna()].copy()
mkt = reg[reg['h1_total_close'].notna()].copy()
mkt['residual'] = mkt['total_points_h1'] - mkt['h1_total_close']

print(f"Regular season with labels + market: {len(mkt)}")
label_vals = sorted(set(labels.values()))
cell_results = []
print(f"\n{'Home':<12} {'Away':<12} {'N':>4} {'Actual':>7} {'Close':>7} {'Resid':>7} {'Flag'}")
print("-" * 58)
for hl in label_vals:
    for al in label_vals:
        sub = mkt[(mkt['home_off'] == hl) & (mkt['away_off'] == al)]
        if len(sub) < 5:
            continue
        act = sub['total_points_h1'].mean()
        cl = sub['h1_total_close'].mean()
        r = act - cl
        flag = ''
        if len(sub) < 15:
            flag = 'THIN'
        elif abs(r) >= 1.5:
            flag = 'STRONG'
        elif abs(r) >= 1.0:
            flag = 'NEAR MISS'
        cell_results.append({'home': hl, 'away': al, 'n': len(sub), 'actual': act, 'close': cl, 'residual': r, 'flag': flag})
        print(f"{hl:<12} {al:<12} {len(sub):>4} {act:>7.1f} {cl:>7.1f} {r:>+7.1f}  {flag}")

# STEP 3
print("\n" + "=" * 70)
print("STEP 3 — CONTROL CHECK")
print("=" * 70)

# Get full-game total from archive
dfs = []
for root, dirs, files in os.walk('data/odds_archive/nfl/game_markets'):
    for f in files:
        if f.endswith('.parquet'):
            dfs.append(pd.read_parquet(os.path.join(root, f)))
gm = pd.concat(dfs, ignore_index=True)
fg = gm[gm['market_key'] == 'totals'].groupby('event_id')['line'].median().reset_index()
fg.columns = ['event_id', 'fg_total']
dc_eid = dc[['game_id', 'event_id']].dropna()
fg = fg.merge(dc_eid, on='event_id', how='left')
mkt = mkt.merge(fg[['game_id', 'fg_total']], on='game_id', how='left')

strong = sorted(cell_results, key=lambda x: abs(x['residual']), reverse=True)[:4]
ctrl_mkt = mkt.dropna(subset=['fg_total'])
for cell in strong:
    all_d = ctrl_mkt.copy()
    all_d['in_cell'] = ((all_d['home_off'] == cell['home']) & (all_d['away_off'] == cell['away'])).astype(int)
    if all_d['in_cell'].sum() < 5:
        continue
    lr = LinearRegression()
    lr.fit(all_d[['fg_total']], all_d['residual'])
    all_d['ctrl_resid'] = all_d['residual'] - lr.predict(all_d[['fg_total']])
    cell_ctrl = all_d[all_d['in_cell'] == 1]['ctrl_resid'].mean()
    survives = "YES" if abs(cell_ctrl) > 0.5 else "NO"
    print(f"  {cell['home']} x {cell['away']} (N={cell['n']}): raw={cell['residual']:+.1f}, controlled={cell_ctrl:+.1f}, survives={survives}")

# STEP 4
print("\n" + "=" * 70)
print("STEP 4 — STABILITY CHECK")
print("=" * 70)
fh = mkt[mkt['week'] <= 9]
sh = mkt[(mkt['week'] >= 10) & (mkt['week'] <= 18)]
for cell in strong[:4]:
    s_fh = fh[(fh['home_off'] == cell['home']) & (fh['away_off'] == cell['away'])]
    s_sh = sh[(sh['home_off'] == cell['home']) & (sh['away_off'] == cell['away'])]
    r_fh = s_fh['residual'].mean() if len(s_fh) >= 3 else float('nan')
    r_sh = s_sh['residual'].mean() if len(s_sh) >= 3 else float('nan')
    cons = "YES" if (not np.isnan(r_fh) and not np.isnan(r_sh) and r_fh * r_sh > 0) else "NO"
    thin = "THIN" if (len(s_fh) < 10 or len(s_sh) < 10) else ""
    print(f"  {cell['home']} x {cell['away']}: 1H={r_fh:+.1f}(N={len(s_fh)}) 2H={r_sh:+.1f}(N={len(s_sh)}) consistent={cons} {thin}")

# STEP 5
print("\n" + "=" * 70)
print("STEP 5 — CONCENTRATION CHECK")
print("=" * 70)
for cell in strong[:3]:
    sub = mkt[(mkt['home_off'] == cell['home']) & (mkt['away_off'] == cell['away'])]
    sub = sub.merge(sched_teams, on='game_id', how='left')
    all_t = list(sub['home_team']) + list(sub['away_team'])
    tc = pd.Series(all_t).value_counts()
    top5 = tc.head(5)
    print(f"  {cell['home']} x {cell['away']} (N={cell['n']}): top5={dict(top5)}, share={top5.sum()/len(all_t)*100:.0f}%")

# DECISION
print("\n" + "=" * 70)
print("DECISION")
print("=" * 70)
max_r = max(abs(c['residual']) for c in cell_results if c['n'] >= 15) if cell_results else 0
n_strong = sum(1 for c in cell_results if abs(c['residual']) >= 1.5 and c['n'] >= 15)
n_near = sum(1 for c in cell_results if 1.0 <= abs(c['residual']) < 1.5 and c['n'] >= 15)
print(f"Max |residual| (N>=15): {max_r:.1f}")
print(f"STRONG cells (|r|>=1.5, N>=15): {n_strong}")
print(f"NEAR MISS cells (1.0<=|r|<1.5, N>=15): {n_near}")
