#!/usr/bin/env python3
"""Phase 6: Original ANEMIC x BNB as conditional layer on live NHL model."""
import os, sys
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

SEP = "=" * 70

ft = pd.read_parquet('nhl/nhl_feature_table.parquet')
ft = ft[ft['season_year'].isin([2021, 2022, 2023, 2024])].copy()
mo = pd.read_parquet('nhl/nhl_model_outputs.parquet')
canon = pd.read_csv('nhl/nhl_games_canonical.csv')
canon = canon[canon['season_year'].isin([2021, 2022, 2023, 2024])].copy()

# ── Build team-game table (exact Phase 1 features) ──
rows = []
for _, g in ft.iterrows():
    for side in ['home', 'away']:
        opp = 'away' if side == 'home' else 'home'
        rows.append({
            'game_id': g['game_id'], 'season': g['season_year'],
            'team': g[f'{side}_team'], 'is_home': side == 'home',
            'sa_r20': g[f'{side}_shots_against_rolling_20'],
            'hd_sa_r20': g[f'{side}_hd_shots_against_rolling_20'],
            'xga_r20': g[f'{side}_xga_rolling_20'],
            'sf_r20': g[f'{side}_shots_for_rolling_20'],
            'hd_sf_r20': g[f'{side}_hd_shots_for_rolling_20'],
            'xgf_r20': g[f'{side}_xgf_rolling_20'],
            'backup': g.get(f'{side}_backup_flag', 0),
            'opp_backup': g.get(f'{opp}_backup_flag', 0),
        })
tg = pd.DataFrame(rows)
tg['hd_rate_d'] = tg['hd_sa_r20'] / tg['sa_r20'].clip(lower=1)
tg['hd_rate_o'] = tg['hd_sf_r20'] / tg['sf_r20'].clip(lower=1)

# ── Build EXACT Phase 1 archetypes ──
def_feats = ['sa_r20', 'hd_sa_r20', 'xga_r20', 'hd_rate_d']
off_feats = ['sf_r20', 'hd_sf_r20', 'xgf_r20', 'hd_rate_o']

def_clean = tg.dropna(subset=def_feats).copy()
off_clean = tg.dropna(subset=off_feats).copy()

sc_d = StandardScaler()
km_d = KMeans(n_clusters=3, random_state=42, n_init=10)
def_clean['def_cl'] = km_d.fit_predict(sc_d.fit_transform(def_clean[def_feats]))
cent_d = pd.DataFrame(sc_d.inverse_transform(km_d.cluster_centers_), columns=def_feats)

# Label by xGA rank (same as Phase 1)
ranked_xga = cent_d['xga_r20'].rank()
dlabels = {}
for i in range(3):
    sa = cent_d.loc[i, 'sa_r20']
    hdr = cent_d.loc[i, 'hd_rate_d']
    if sa <= cent_d['sa_r20'].median() and hdr <= cent_d['hd_rate_d'].median():
        dlabels[i] = 'SUPPRESSOR'
    elif sa > cent_d['sa_r20'].median() and hdr <= cent_d['hd_rate_d'].median():
        dlabels[i] = 'BEND_NOT_BREAK'
    else:
        dlabels[i] = 'POROUS'
if len(set(dlabels.values())) < 3:
    for i in range(3):
        if ranked_xga[i] == 1: dlabels[i] = 'SUPPRESSOR'
        elif ranked_xga[i] == 3: dlabels[i] = 'POROUS'
        else: dlabels[i] = 'BEND_NOT_BREAK'
def_clean['def_label'] = def_clean['def_cl'].map(dlabels)

sc_o = StandardScaler()
km_o = KMeans(n_clusters=3, random_state=42, n_init=10)
off_clean['off_cl'] = km_o.fit_predict(sc_o.fit_transform(off_clean[off_feats]))
cent_o = pd.DataFrame(sc_o.inverse_transform(km_o.cluster_centers_), columns=off_feats)
ranked_xgf = cent_o['xgf_r20'].rank()
olabels = {}
for i in range(3):
    if ranked_xgf[i] == 3: olabels[i] = 'POTENT'
    elif ranked_xgf[i] == 1: olabels[i] = 'ANEMIC'
    else: olabels[i] = 'AVERAGE'
off_clean['off_label'] = off_clean['off_cl'].map(olabels)

# ── STEP 0: Join audit ──
print(SEP)
print("STEP 0 — JOIN / LABEL AUDIT")
print(SEP)

print(f"Defensive labels: {dlabels}")
print(f"  Centroids:")
for i, lab in dlabels.items():
    print(f"    {lab}: sa={cent_d.loc[i,'sa_r20']:.1f} hd_sa={cent_d.loc[i,'hd_sa_r20']:.1f} "
          f"xga={cent_d.loc[i,'xga_r20']:.2f} hd_rate={cent_d.loc[i,'hd_rate_d']:.3f}")
print(f"Offensive labels: {olabels}")

# Merge to game level
ho = off_clean[off_clean['is_home']][['game_id', 'off_label']].rename(columns={'off_label': 'home_off'})
ad = def_clean[~def_clean['is_home']][['game_id', 'def_label']].rename(columns={'def_label': 'away_def'})
ao = off_clean[~off_clean['is_home']][['game_id', 'off_label']].rename(columns={'off_label': 'away_off'})
hd = def_clean[def_clean['is_home']][['game_id', 'def_label']].rename(columns={'def_label': 'home_def'})
hbk = tg[tg['is_home']][['game_id', 'backup', 'opp_backup']].rename(
    columns={'backup': 'h_bk', 'opp_backup': 'a_bk'}).drop_duplicates('game_id')

# Odds
canon_odds = canon[['game_id', 'over_price', 'under_price']].dropna(subset=['over_price'])
def a2i(o):
    if pd.isna(o): return np.nan
    return abs(o)/(abs(o)+100) if o < 0 else 100/(o+100)
canon_odds['impl_over'] = canon_odds['over_price'].apply(a2i)
canon_odds['impl_under'] = canon_odds['under_price'].apply(a2i)
canon_odds['fair_over'] = canon_odds['impl_over'] / (canon_odds['impl_over'] + canon_odds['impl_under'])

# Master table
gl = ft[['game_id', 'season_year', 'closing_total', 'total_goals']].copy()
gl = gl.merge(ho, on='game_id', how='left').merge(ad, on='game_id', how='left')
gl = gl.merge(ao, on='game_id', how='left').merge(hd, on='game_id', how='left')
gl = gl.merge(hbk, on='game_id', how='left')
gl = gl.merge(canon_odds[['game_id', 'fair_over']], on='game_id', how='left')
gl = gl.merge(mo[['game_id', 'edge_over']].rename(columns={'edge_over': 'model_edge'}), on='game_id', how='left')

gl['both_starters'] = (gl['h_bk'] == 0) & (gl['a_bk'] == 0)
gl['over_hit'] = (gl['total_goals'] > gl['closing_total']).astype(int)
gl['under_hit'] = (gl['total_goals'] < gl['closing_total']).astype(int)
gl['push'] = (gl['total_goals'] == gl['closing_total']).astype(int)

# ── STEP 1: Define layer states ──
gl['ho_ad_bnb'] = (gl['home_off'] == 'ANEMIC') & (gl['away_def'] == 'BEND_NOT_BREAK')
gl['ao_hd_bnb'] = (gl['away_off'] == 'ANEMIC') & (gl['home_def'] == 'BEND_NOT_BREAK')
gl['favorable'] = gl['ho_ad_bnb'] | gl['ao_hd_bnb']
gl['strong_fav'] = gl['ho_ad_bnb'] & gl['ao_hd_bnb']

starters = gl[gl['both_starters'] & gl['model_edge'].notna()].copy()

print(f"\nConfirmed-starter games with edge: {len(starters)}")
print(f"\nLayer state counts (confirmed starters):")
for season in sorted(starters['season_year'].unique()):
    s = starters[starters['season_year'] == season]
    print(f"  {season}: FAVORABLE={s['favorable'].sum()}, STRONG={s['strong_fav'].sum()}, "
          f"NONE={len(s) - s['favorable'].sum()}")

# ── STEP 2: Baseline ──
print(f"\n{SEP}")
print("STEP 2 — BASELINE (edge >= 0.12, confirmed starters)")
print(SEP)

# Also test lower thresholds to get more games
for thresh in [0.12, 0.10, 0.08, 0.06]:
    edge_g = starters[starters['model_edge'] >= thresh]
    if len(edge_g) < 5:
        continue
    ov = edge_g['over_hit'].mean()
    imp = edge_g[edge_g['fair_over'].notna()]['fair_over'].mean()
    r = ov - imp if not np.isnan(imp) else 0
    w = edge_g['over_hit'].sum()
    l = edge_g['under_hit'].sum()
    roi = (w*(10/11)-l)/(w+l)*100 if (w+l)>0 else 0
    print(f"  edge >= {thresh:.2f}: N={len(edge_g)}, Over={ov:.3f}, impl={imp:.3f}, resid={r:+.3f}, ROI={roi:+.1f}%")
    if thresh == 0.12:
        baseline_over = ov
        baseline_n = len(edge_g)

# ── STEP 3: Conditional layer ──
print(f"\n{SEP}")
print("STEP 3 — CONDITIONAL LAYER (edge >= 0.12)")
print(SEP)

edge_12 = starters[starters['model_edge'] >= 0.12]
for label, mask_fn in [
    ('FAVORABLE', lambda df: df['favorable']),
    ('STRONG FAVORABLE', lambda df: df['strong_fav']),
    ('NONE', lambda df: ~df['favorable']),
]:
    sub = edge_12[mask_fn(edge_12)]
    if len(sub) < 3:
        print(f"  {label}: N={len(sub)} — TOO THIN")
        continue
    ov = sub['over_hit'].mean()
    imp = sub[sub['fair_over'].notna()]['fair_over'].mean()
    r = ov - imp if not np.isnan(imp) else 0
    w = sub['over_hit'].sum(); l = sub['under_hit'].sum()
    roi = (w*(10/11)-l)/(w+l)*100 if (w+l)>0 else 0
    print(f"  {label}: N={len(sub)}, Over={ov:.3f}, resid={r:+.3f}, ROI={roi:+.1f}%")

# Since N=24 at edge>=0.12, also test at lower thresholds
print(f"\n  At edge >= 0.08:")
edge_08 = starters[starters['model_edge'] >= 0.08]
for label, mask_fn in [
    ('FAVORABLE', lambda df: df['favorable']),
    ('NONE', lambda df: ~df['favorable']),
]:
    sub = edge_08[mask_fn(edge_08)]
    if len(sub) < 5:
        print(f"    {label}: N={len(sub)} — THIN")
        continue
    ov = sub['over_hit'].mean()
    imp = sub[sub['fair_over'].notna()]['fair_over'].mean()
    r = ov - imp if not np.isnan(imp) else 0
    w = sub['over_hit'].sum(); l = sub['under_hit'].sum()
    roi = (w*(10/11)-l)/(w+l)*100 if (w+l)>0 else 0
    print(f"    {label}: N={len(sub)}, Over={ov:.3f}, resid={r:+.3f}, ROI={roi:+.1f}%")

print(f"\n  At edge >= 0.06:")
edge_06 = starters[starters['model_edge'] >= 0.06]
for label, mask_fn in [
    ('FAVORABLE', lambda df: df['favorable']),
    ('NONE', lambda df: ~df['favorable']),
]:
    sub = edge_06[mask_fn(edge_06)]
    if len(sub) < 10:
        print(f"    {label}: N={len(sub)} — THIN")
        continue
    ov = sub['over_hit'].mean()
    imp = sub[sub['fair_over'].notna()]['fair_over'].mean()
    r = ov - imp if not np.isnan(imp) else 0
    w = sub['over_hit'].sum(); l = sub['under_hit'].sum()
    roi = (w*(10/11)-l)/(w+l)*100 if (w+l)>0 else 0
    print(f"    {label}: N={len(sub)}, Over={ov:.3f}, resid={r:+.3f}, ROI={roi:+.1f}%")
    # Season consistency
    cons = 0
    for season in sorted(sub['season_year'].unique()):
        ss = sub[sub['season_year'] == season]
        if len(ss) >= 3 and ss['over_hit'].mean() > 0.5:
            cons += 1
    print(f"      Seasons over 50%: {cons}/{len(sub['season_year'].unique())}")

# ── STEP 4: Threshold modifier ──
print(f"\n{SEP}")
print("STEP 4 — THRESHOLD MODIFIER")
print(SEP)

for thresh in [0.10, 0.08, 0.06]:
    fav = starters[(starters['model_edge'] >= thresh) & starters['favorable']]
    base = starters[starters['model_edge'] >= 0.12]
    if len(fav) >= 10:
        ov_f = fav['over_hit'].mean()
        ov_b = base['over_hit'].mean() if len(base) > 0 else 0
        print(f"  edge >= {thresh:.2f} + FAVORABLE: N={len(fav)}, Over={ov_f:.3f} (baseline={ov_b:.3f})")

# ── STEP 5: Pass filter ──
print(f"\n{SEP}")
print("STEP 5 — PASS FILTER")
print(SEP)

for thresh in [0.12, 0.08, 0.06]:
    edge_t = starters[starters['model_edge'] >= thresh]
    fav = edge_t[edge_t['favorable']]
    none = edge_t[~edge_t['favorable']]
    if len(fav) >= 5 and len(none) >= 5:
        print(f"  edge >= {thresh:.2f}:")
        print(f"    FAVORABLE: N={len(fav)}, Over={fav['over_hit'].mean():.3f}")
        print(f"    NONE:      N={len(none)}, Over={none['over_hit'].mean():.3f}")
        print(f"    Delta:     {fav['over_hit'].mean() - none['over_hit'].mean():+.3f}")

# ── STEP 6: CLV ──
print(f"\n{SEP}")
print("STEP 6 — CLV CHECK")
print(SEP)

try:
    snaps = pd.read_parquet('nhl/nhl_market_snapshots.parquet')
    if 'opening_total' in snaps.columns and 'closing_total' in snaps.columns:
        snaps['line_move'] = snaps['closing_total'] - snaps['opening_total']
        gl_clv = gl.merge(snaps[['game_id', 'opening_total', 'line_move']], on='game_id', how='left')
        # For favorable edge games
        for thresh in [0.08, 0.06]:
            fav_clv = gl_clv[(gl_clv['both_starters']) & (gl_clv['model_edge'] >= thresh) &
                             gl_clv['favorable'] & gl_clv['opening_total'].notna()]
            none_clv = gl_clv[(gl_clv['both_starters']) & (gl_clv['model_edge'] >= thresh) &
                              ~gl_clv['favorable'] & gl_clv['opening_total'].notna()]
            if len(fav_clv) >= 5:
                print(f"  edge >= {thresh:.2f} + FAVORABLE: N={len(fav_clv)}, "
                      f"avg_line_move={fav_clv['line_move'].mean():+.2f}")
            if len(none_clv) >= 5:
                print(f"  edge >= {thresh:.2f} + NONE: N={len(none_clv)}, "
                      f"avg_line_move={none_clv['line_move'].mean():+.2f}")
    else:
        print("  opening_total or closing_total not in snapshots")
except Exception as e:
    print(f"  CLV check unavailable: {e}")

# ── DECISION ──
print(f"\n{SEP}")
print("DECISION SUMMARY")
print(SEP)

# Find the most informative threshold
best_thresh = None
best_result = None
for thresh in [0.06, 0.08, 0.10, 0.12]:
    fav = starters[(starters['model_edge'] >= thresh) & starters['favorable']]
    none = starters[(starters['model_edge'] >= thresh) & ~starters['favorable']]
    if len(fav) >= 30 and len(none) >= 30:
        delta = fav['over_hit'].mean() - none['over_hit'].mean()
        if best_result is None or delta > best_result:
            best_thresh = thresh
            best_result = delta

if best_thresh:
    fav = starters[(starters['model_edge'] >= best_thresh) & starters['favorable']]
    none = starters[(starters['model_edge'] >= best_thresh) & ~starters['favorable']]
    print(f"\nBest threshold for comparison: edge >= {best_thresh:.2f}")
    print(f"  FAVORABLE: N={len(fav)}, Over={fav['over_hit'].mean():.3f}")
    print(f"  NONE:      N={len(none)}, Over={none['over_hit'].mean():.3f}")
    print(f"  Delta:     {fav['over_hit'].mean() - none['over_hit'].mean():+.3f}")
else:
    print("\nNo threshold produces N >= 30 in both groups.")
    # Report at whatever threshold gives most data
    for thresh in [0.04, 0.02, 0.00]:
        fav = starters[(starters['model_edge'] >= thresh) & starters['favorable']]
        none = starters[(starters['model_edge'] >= thresh) & ~starters['favorable']]
        if len(fav) >= 20 and len(none) >= 20:
            print(f"\nAt edge >= {thresh:.2f}:")
            print(f"  FAVORABLE: N={len(fav)}, Over={fav['over_hit'].mean():.3f}")
            print(f"  NONE:      N={len(none)}, Over={none['over_hit'].mean():.3f}")
            break
