#!/usr/bin/env python3
"""Phase 1: NHL Defensive/Offensive Structure Archetypes + Matchup Cell Test."""
import os, sys
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

SEP = "=" * 70

ft = pd.read_parquet('nhl/nhl_feature_table.parquet')
# Use seasons 2021-2024 only (full seasons, exclude partial 2025)
ft = ft[ft['season_year'].isin([2021, 2022, 2023, 2024])].copy()
print(f"Feature table: {len(ft)} games, seasons {sorted(ft['season_year'].unique())}")

# ═══════════════════════════════════════════════════════════════
# STEP 1 — DEFENSIVE ARCHETYPES
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 1 — DEFENSIVE ARCHETYPES")
print(SEP)

# Build team-game defensive features (one row per team per game)
rows = []
for _, g in ft.iterrows():
    for side in ['home', 'away']:
        rows.append({
            'game_id': g['game_id'], 'game_date': g['game_date'],
            'season': g['season_year'], 'team': g[f'{side}_team'],
            'is_home': side == 'home',
            'sa_r20': g[f'{side}_shots_against_rolling_20'],
            'hd_sa_r20': g[f'{side}_hd_shots_against_rolling_20'],
            'xga_r20': g[f'{side}_xga_rolling_20'],
            'sf_r20': g[f'{side}_shots_for_rolling_20'],
            'hd_sf_r20': g[f'{side}_hd_shots_for_rolling_20'],
            'xgf_r20': g[f'{side}_xgf_rolling_20'],
            'closing_total': g['closing_total'],
            'total_goals': g['total_goals'],
            'backup': g.get(f'{side}_backup_flag', 0),
            'b2b': g.get(f'{side}_b2b', 0),
            'rest': g.get(f'{side}_days_rest', 3),
            'goals_for': g[f'{side}_score'],
            'goals_against': g[f'{"away" if side == "home" else "home"}_score'],
        })
tg = pd.DataFrame(rows)

# Derive defensive shape features
tg['hd_danger_rate_d'] = tg['hd_sa_r20'] / tg['sa_r20'].clip(lower=1)
def_feats = ['sa_r20', 'hd_sa_r20', 'xga_r20', 'hd_danger_rate_d']
def_clean = tg.dropna(subset=def_feats).copy()

sc_d = StandardScaler()
X_d = sc_d.fit_transform(def_clean[def_feats])

for k in [2, 3]:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    def_clean[f'def_cl_{k}'] = km.fit_predict(X_d)
    cent = pd.DataFrame(sc_d.inverse_transform(km.cluster_centers_), columns=def_feats)
    print(f"\nK={k} Defensive:")
    for i in range(k):
        n = (def_clean[f'def_cl_{k}'] == i).sum()
        print(f"  Cl {i}: N={n}  sa={cent.loc[i,'sa_r20']:.1f}  hd_sa={cent.loc[i,'hd_sa_r20']:.1f}  "
              f"xga={cent.loc[i,'xga_r20']:.2f}  hd_rate_d={cent.loc[i,'hd_danger_rate_d']:.3f}")

# Check K=3 balance
k3_min = def_clean['def_cl_3'].value_counts().min()
chosen_k_d = 3 if k3_min >= 500 else 2
print(f"\nK=3 min: {k3_min}. Chosen: K={chosen_k_d}")

km_d = KMeans(n_clusters=chosen_k_d, random_state=42, n_init=10)
def_clean['def_cl'] = km_d.fit_predict(X_d)
cent_d = pd.DataFrame(sc_d.inverse_transform(km_d.cluster_centers_), columns=def_feats)

# Label by interpretation
dlabels = {}
if chosen_k_d == 3:
    for i in range(3):
        sa = cent_d.loc[i, 'sa_r20']
        hdr = cent_d.loc[i, 'hd_danger_rate_d']
        if sa <= cent_d['sa_r20'].median() and hdr <= cent_d['hd_danger_rate_d'].median():
            dlabels[i] = 'SUPPRESSOR'
        elif sa > cent_d['sa_r20'].median() and hdr <= cent_d['hd_danger_rate_d'].median():
            dlabels[i] = 'BEND_NOT_BREAK'
        else:
            dlabels[i] = 'POROUS'
    # Deduplicate if needed
    if len(set(dlabels.values())) < 3:
        ranked = cent_d['xga_r20'].rank()
        for i in range(3):
            if ranked[i] == 1: dlabels[i] = 'SUPPRESSOR'
            elif ranked[i] == 3: dlabels[i] = 'POROUS'
            else: dlabels[i] = 'BEND_NOT_BREAK'
else:
    for i in range(2):
        dlabels[i] = 'TIGHT' if cent_d.loc[i, 'sa_r20'] < cent_d['sa_r20'].mean() else 'LOOSE'

def_clean['def_label'] = def_clean['def_cl'].map(dlabels)
print(f"\nDefensive labels: {dlabels}")
for lab in sorted(set(dlabels.values())):
    cl = [k for k, v in dlabels.items() if v == lab][0]
    n = (def_clean['def_label'] == lab).sum()
    ga_mean = def_clean[def_clean['def_label'] == lab]['goals_against'].mean()
    print(f"  {lab}: N={n}, mean GA={ga_mean:.2f} (sanity check)")
    for f in def_feats:
        print(f"    {f}: {cent_d.loc[cl, f]:.3f}")

# Season balance
print("\nDefensive clusters by season:")
for season in sorted(def_clean['season'].unique()):
    counts = def_clean[def_clean['season'] == season]['def_label'].value_counts()
    print(f"  {season}: {counts.to_dict()}")

# ═══════════════════════════════════════════════════════════════
# STEP 2 — OFFENSIVE ARCHETYPES
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 2 — OFFENSIVE ARCHETYPES")
print(SEP)

tg['hd_danger_rate_o'] = tg['hd_sf_r20'] / tg['sf_r20'].clip(lower=1)
off_feats = ['sf_r20', 'hd_sf_r20', 'xgf_r20', 'hd_danger_rate_o']
off_clean = tg.dropna(subset=off_feats).copy()

sc_o = StandardScaler()
X_o = sc_o.fit_transform(off_clean[off_feats])

for k in [2, 3]:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    off_clean[f'off_cl_{k}'] = km.fit_predict(X_o)
    cent = pd.DataFrame(sc_o.inverse_transform(km.cluster_centers_), columns=off_feats)
    print(f"\nK={k} Offensive:")
    for i in range(k):
        n = (off_clean[f'off_cl_{k}'] == i).sum()
        print(f"  Cl {i}: N={n}  sf={cent.loc[i,'sf_r20']:.1f}  hd_sf={cent.loc[i,'hd_sf_r20']:.1f}  "
              f"xgf={cent.loc[i,'xgf_r20']:.2f}  hd_rate_o={cent.loc[i,'hd_danger_rate_o']:.3f}")

k3_min_o = off_clean['off_cl_3'].value_counts().min()
chosen_k_o = 3 if k3_min_o >= 500 else 2
print(f"\nK=3 min: {k3_min_o}. Chosen: K={chosen_k_o}")

km_o = KMeans(n_clusters=chosen_k_o, random_state=42, n_init=10)
off_clean['off_cl'] = km_o.fit_predict(X_o)
cent_o = pd.DataFrame(sc_o.inverse_transform(km_o.cluster_centers_), columns=off_feats)

olabels = {}
if chosen_k_o == 3:
    ranked = cent_o['xgf_r20'].rank()
    vol_ranked = cent_o['sf_r20'].rank()
    for i in range(3):
        if vol_ranked[i] == 3 and cent_o.loc[i, 'hd_danger_rate_o'] < cent_o['hd_danger_rate_o'].median():
            olabels[i] = 'HIGH_VOLUME'
        elif cent_o.loc[i, 'hd_danger_rate_o'] == cent_o['hd_danger_rate_o'].max():
            olabels[i] = 'HIGH_DANGER'
        else:
            olabels[i] = 'BALANCED'
    if len(set(olabels.values())) < 3:
        for i in range(3):
            if ranked[i] == 3: olabels[i] = 'POTENT'
            elif ranked[i] == 1: olabels[i] = 'ANEMIC'
            else: olabels[i] = 'AVERAGE'
else:
    for i in range(2):
        olabels[i] = 'POTENT' if cent_o.loc[i, 'xgf_r20'] > cent_o['xgf_r20'].mean() else 'ANEMIC'

off_clean['off_label'] = off_clean['off_cl'].map(olabels)
print(f"\nOffensive labels: {olabels}")
for lab in sorted(set(olabels.values())):
    cl = [k for k, v in olabels.items() if v == lab][0]
    n = (off_clean['off_label'] == lab).sum()
    gf_mean = off_clean[off_clean['off_label'] == lab]['goals_for'].mean()
    print(f"  {lab}: N={n}, mean GF={gf_mean:.2f} (sanity check)")
    for f in off_feats:
        print(f"    {f}: {cent_o.loc[cl, f]:.3f}")

# ═══════════════════════════════════════════════════════════════
# STEP 3 — MATCHUP CELL TEST
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 3 — MATCHUP CELL TEST")
print(SEP)

# Merge labels back to game level
# Home offense + away defense
home_off = off_clean[off_clean['is_home']][['game_id', 'off_label']].rename(columns={'off_label': 'home_off'})
away_def = def_clean[~def_clean['is_home']][['game_id', 'def_label']].rename(columns={'def_label': 'away_def'})
# Away offense + home defense
away_off = off_clean[~off_clean['is_home']][['game_id', 'off_label']].rename(columns={'off_label': 'away_off'})
home_def = def_clean[def_clean['is_home']][['game_id', 'def_label']].rename(columns={'def_label': 'home_def'})

game_labels = ft[['game_id', 'game_date', 'season_year', 'closing_total', 'total_goals',
                   'home_backup_flag', 'away_backup_flag', 'home_b2b', 'away_b2b',
                   'home_days_rest', 'away_days_rest']].copy()
game_labels = game_labels.merge(home_off, on='game_id', how='left')
game_labels = game_labels.merge(away_def, on='game_id', how='left')
game_labels = game_labels.merge(away_off, on='game_id', how='left')
game_labels = game_labels.merge(home_def, on='game_id', how='left')

mkt = game_labels.dropna(subset=['closing_total', 'home_off', 'away_def', 'away_off', 'home_def']).copy()
mkt['residual'] = mkt['total_goals'] - mkt['closing_total']
base_resid = mkt['residual'].mean()
print(f"\nGames with complete labels + market: {len(mkt)}")
print(f"Base residual: {base_resid:+.2f}")

# Home offense vs Away defense
print(f"\n--- HOME OFFENSE vs AWAY DEFENSE ---")
off_labs = sorted(set(olabels.values()))
def_labs = sorted(set(dlabels.values()))

print(f"{'Home Off':<12} {'Away Def':<16} {'N':>5} {'Goals':>6} {'Close':>6} {'Resid':>6} {'SE':>5} {'Flag'}")
print("-" * 65)
cell_results = []
for ol in off_labs:
    for dl in def_labs:
        sub = mkt[(mkt['home_off'] == ol) & (mkt['away_def'] == dl)]
        if len(sub) < 10:
            continue
        goals = sub['total_goals'].mean()
        close = sub['closing_total'].mean()
        resid = goals - close
        se = sub['residual'].std() / np.sqrt(len(sub))
        flag = 'THIN' if len(sub) < 30 else ('***' if abs(resid) > 0.3 else '')
        cell_results.append({'side': 'HO_AD', 'off': ol, 'def': dl, 'n': len(sub),
                             'goals': goals, 'close': close, 'resid': resid, 'se': se, 'flag': flag})
        print(f"{ol:<12} {dl:<16} {len(sub):>5} {goals:>6.2f} {close:>6.2f} {resid:>+6.2f} {se:>5.2f}  {flag}")

# Away offense vs Home defense
print(f"\n--- AWAY OFFENSE vs HOME DEFENSE ---")
for ol in off_labs:
    for dl in def_labs:
        sub = mkt[(mkt['away_off'] == ol) & (mkt['home_def'] == dl)]
        if len(sub) < 10:
            continue
        goals = sub['total_goals'].mean()
        close = sub['closing_total'].mean()
        resid = goals - close
        se = sub['residual'].std() / np.sqrt(len(sub))
        flag = 'THIN' if len(sub) < 30 else ('***' if abs(resid) > 0.3 else '')
        cell_results.append({'side': 'AO_HD', 'off': ol, 'def': dl, 'n': len(sub),
                             'goals': goals, 'close': close, 'resid': resid, 'se': se, 'flag': flag})
        print(f"{ol:<12} {dl:<16} {len(sub):>5} {goals:>6.2f} {close:>6.2f} {resid:>+6.2f} {se:>5.2f}  {flag}")

# ═══════════════════════════════════════════════════════════════
# STEP 4 — CONTROL CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 4 — CONTROL CHECK")
print(SEP)

strong = [c for c in cell_results if abs(c['resid']) > 0.2 and c['n'] >= 30]
strong.sort(key=lambda x: abs(x['resid']), reverse=True)

for cell in strong[:5]:
    if cell['side'] == 'HO_AD':
        mask = (mkt['home_off'] == cell['off']) & (mkt['away_def'] == cell['def'])
    else:
        mask = (mkt['away_off'] == cell['off']) & (mkt['home_def'] == cell['def'])

    all_d = mkt.copy()
    all_d['in_cell'] = mask.astype(int)

    ctrl_cols = ['closing_total']
    for c in ['home_backup_flag', 'away_backup_flag', 'home_b2b', 'away_b2b']:
        if c in all_d.columns:
            ctrl_cols.append(c)

    ctrl_valid = all_d.dropna(subset=ctrl_cols)
    if len(ctrl_valid) < 100:
        continue

    lr = LinearRegression()
    lr.fit(ctrl_valid[ctrl_cols], ctrl_valid['residual'])
    ctrl_valid['ctrl_resid'] = ctrl_valid['residual'] - lr.predict(ctrl_valid[ctrl_cols])

    cell_ctrl = ctrl_valid[ctrl_valid['in_cell'] == 1]['ctrl_resid'].mean()
    survives = abs(cell_ctrl) > 0.15
    print(f"  {cell['side']}: {cell['off']} x {cell['def']} (N={cell['n']}): "
          f"raw={cell['resid']:+.2f}, controlled={cell_ctrl:+.2f}, survives={'YES' if survives else 'NO'}")

# ═══════════════════════════════════════════════════════════════
# STEP 5 — SEASON STABILITY
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 5 — SEASON STABILITY")
print(SEP)

for cell in strong[:4]:
    if cell['side'] == 'HO_AD':
        mask_fn = lambda df: (df['home_off'] == cell['off']) & (df['away_def'] == cell['def'])
    else:
        mask_fn = lambda df: (df['away_off'] == cell['off']) & (df['home_def'] == cell['def'])

    print(f"\n  {cell['side']}: {cell['off']} x {cell['def']}:")
    n_consistent = 0
    for season in sorted(mkt['season_year'].unique()):
        sub = mkt[(mkt['season_year'] == season) & mask_fn(mkt)]
        if len(sub) < 5:
            print(f"    {season}: N={len(sub)} — THIN")
            continue
        r = sub['residual'].mean()
        direction = '+' if r > 0 else '-'
        same_as_overall = (r > 0) == (cell['resid'] > 0)
        if same_as_overall:
            n_consistent += 1
        print(f"    {season}: N={len(sub)}, resid={r:+.2f} {'OK' if same_as_overall else 'FLIP'}")
    print(f"    Consistent seasons: {n_consistent}/4")

# ═══════════════════════════════════════════════════════════════
# STEP 6 — CONCENTRATION CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 6 — CONCENTRATION CHECK")
print(SEP)

for cell in strong[:3]:
    if cell['side'] == 'HO_AD':
        sub = mkt[(mkt['home_off'] == cell['off']) & (mkt['away_def'] == cell['def'])]
        team_col = 'home_off'
    else:
        sub = mkt[(mkt['away_off'] == cell['off']) & (mkt['home_def'] == cell['def'])]
        team_col = 'away_off'

    # Get team names from ft
    sub_with_teams = sub.merge(ft[['game_id', 'home_team', 'away_team']], on='game_id', how='left')
    all_teams = list(sub_with_teams['home_team']) + list(sub_with_teams['away_team'])
    tc = pd.Series(all_teams).value_counts()
    top5 = tc.head(5)

    print(f"\n  {cell['side']}: {cell['off']} x {cell['def']} (N={cell['n']}):")
    print(f"    Top 5: {dict(top5)}")
    print(f"    Top 2 share: {tc.head(2).sum()}/{len(all_teams)*1} = {tc.head(2).sum()/(len(all_teams))*100:.0f}%")

    # Remove top 2 teams
    top2 = set(tc.head(2).index)
    sub_no2 = sub_with_teams[~sub_with_teams['home_team'].isin(top2) & ~sub_with_teams['away_team'].isin(top2)]
    if len(sub_no2) > 10:
        r_no2 = sub_no2['residual'].mean()
        print(f"    After removing top 2: N={len(sub_no2)}, resid={r_no2:+.2f} (was {cell['resid']:+.2f})")

# ═══════════════════════════════════════════════════════════════
# DECISION
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("DECISION")
print(SEP)

strong_final = [c for c in cell_results if abs(c['resid']) > 0.3 and c['n'] >= 30]
near = [c for c in cell_results if 0.2 < abs(c['resid']) <= 0.3 and c['n'] >= 30]
print(f"\nStrong (|resid| > 0.3, N >= 30): {len(strong_final)}")
for c in strong_final:
    print(f"  {c['side']}: {c['off']} x {c['def']}: resid={c['resid']:+.2f} N={c['n']}")
print(f"Near miss (0.2 < |resid| <= 0.3, N >= 30): {len(near)}")
for c in near:
    print(f"  {c['side']}: {c['off']} x {c['def']}: resid={c['resid']:+.2f} N={c['n']}")
