#!/usr/bin/env python3
"""Phase 5: NHL Archetypes as Conditional Layers on Existing Edge Signal."""
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
canon = pd.read_csv('nhl/nhl_games_canonical.csv')
canon = canon[canon['season_year'].isin([2021, 2022, 2023, 2024])].copy()
mo = pd.read_parquet('nhl/nhl_model_outputs.parquet')

print(f"Feature table: {len(ft)} games")
print(f"Model outputs: {len(mo)} rows")
print(f"Model output columns: {sorted(mo.columns)}")

# ── Build team-game features ──
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
            'pp_pct_r20': g.get(f'{side}_pp_pct_rolling_20', np.nan),
            'pk_pct_r20': g.get(f'{side}_pk_pct_rolling_20', np.nan),
            'pen_r20': g.get(f'{side}_penalties_taken_rolling_20', np.nan),
            'pp_opp_r20': g.get(f'{side}_pp_opp_per_game_rolling_20', np.nan),
            'backup': g.get(f'{side}_backup_flag', 0),
            'opp_backup': g.get(f'{opp}_backup_flag', 0),
        })
tg = pd.DataFrame(rows)
tg['danger_ratio'] = tg['hd_sf_r20'] / tg['hd_sa_r20'].clip(lower=0.1)
tg['pp_pk_net'] = tg['pp_pct_r20'].fillna(20) - (100 - tg['pk_pct_r20'].fillna(80))

# ── Build archetype labels ──
def build_labels(off_feats, def_feats, prefix):
    """Build K=2 clusters and assign FAVORABLE/UNFAVORABLE labels per game."""
    off_v = tg.dropna(subset=off_feats).copy()
    def_v = tg.dropna(subset=def_feats).copy()
    sc_o = StandardScaler(); sc_d = StandardScaler()
    km_o = KMeans(n_clusters=2, random_state=42, n_init=10)
    km_d = KMeans(n_clusters=2, random_state=42, n_init=10)
    off_v['oc'] = km_o.fit_predict(sc_o.fit_transform(off_v[off_feats]))
    def_v['dc'] = km_d.fit_predict(sc_d.fit_transform(def_v[def_feats]))

    ho = off_v[off_v['is_home']][['game_id', 'oc']].rename(columns={'oc': f'{prefix}_ho'})
    ad = def_v[~def_v['is_home']][['game_id', 'dc']].rename(columns={'dc': f'{prefix}_ad'})
    ao = off_v[~off_v['is_home']][['game_id', 'oc']].rename(columns={'oc': f'{prefix}_ao'})
    hd = def_v[def_v['is_home']][['game_id', 'dc']].rename(columns={'dc': f'{prefix}_hd'})

    gl = ft[['game_id', 'closing_total', 'total_goals']].copy()
    gl = gl.merge(ho, on='game_id', how='left').merge(ad, on='game_id', how='left')
    gl = gl.merge(ao, on='game_id', how='left').merge(hd, on='game_id', how='left')

    # Determine which cells are favorable (highest residual) vs unfavorable
    hbk = tg[tg['is_home']][['game_id', 'backup', 'opp_backup']].rename(
        columns={'backup': 'h_bk', 'opp_backup': 'a_bk'}).drop_duplicates('game_id')
    gl = gl.merge(hbk, on='game_id', how='left')
    gl['both_starters'] = (gl['h_bk'] == 0) & (gl['a_bk'] == 0)
    gl['residual'] = gl['total_goals'] - gl['closing_total']

    starters = gl[gl['both_starters']].dropna(subset=[f'{prefix}_ho', f'{prefix}_ad'])

    # Score each 2x2 cell
    cell_resids = {}
    for oc in [0, 1]:
        for dc in [0, 1]:
            for sl, ocol, dcol in [('HO_AD', f'{prefix}_ho', f'{prefix}_ad'),
                                    ('AO_HD', f'{prefix}_ao', f'{prefix}_hd')]:
                s = starters.dropna(subset=[ocol, dcol])
                sub = s[(s[ocol] == oc) & (s[dcol] == dc)]
                if len(sub) >= 20:
                    cell_resids[(sl, oc, dc)] = sub['residual'].mean()

    if not cell_resids:
        gl[f'{prefix}_label'] = 'NEUTRAL'
        return gl[['game_id', f'{prefix}_label']]

    # Best and worst cells
    best_cell = max(cell_resids, key=lambda x: cell_resids[x])
    worst_cell = min(cell_resids, key=lambda x: cell_resids[x])

    def label_game(row):
        for sl, ocol, dcol in [('HO_AD', f'{prefix}_ho', f'{prefix}_ad'),
                                ('AO_HD', f'{prefix}_ao', f'{prefix}_hd')]:
            oc_val = row.get(ocol)
            dc_val = row.get(dcol)
            if pd.notna(oc_val) and pd.notna(dc_val):
                key = (sl, int(oc_val), int(dc_val))
                if key == best_cell:
                    return 'FAVORABLE'
                if key == worst_cell:
                    return 'UNFAVORABLE'
        return 'NEUTRAL'

    gl[f'{prefix}_label'] = gl.apply(label_game, axis=1)
    return gl[['game_id', f'{prefix}_label']]


print(f"\n{SEP}")
print("STEP 0+1 — BUILD ARCHETYPE LABELS")
print(SEP)

b8_labels = build_labels(['xgf_r20', 'danger_ratio'], ['xga_r20', 'danger_ratio'], 'b8')
b7_labels = build_labels(['pp_pk_net', 'pp_opp_r20'], ['pp_pk_net', 'pen_r20'], 'b7')

print(f"Branch 8 labels: {b8_labels['b8_label'].value_counts().to_dict()}")
print(f"Branch 7 labels: {b7_labels['b7_label'].value_counts().to_dict()}")

# ── Build master game table ──
canon_odds = canon[['game_id', 'over_price', 'under_price']].dropna(subset=['over_price'])
def a2i(o):
    if pd.isna(o): return np.nan
    return abs(o)/(abs(o)+100) if o < 0 else 100/(o+100)
canon_odds['impl_over'] = canon_odds['over_price'].apply(a2i)
canon_odds['impl_under'] = canon_odds['under_price'].apply(a2i)
canon_odds['fair_over'] = canon_odds['impl_over'] / (canon_odds['impl_over'] + canon_odds['impl_under'])

hbk = tg[tg['is_home']][['game_id', 'backup', 'opp_backup']].rename(
    columns={'backup': 'h_bk', 'opp_backup': 'a_bk'}).drop_duplicates('game_id')

gl = ft[['game_id', 'season_year', 'closing_total', 'total_goals']].copy()
gl = gl.merge(b8_labels, on='game_id', how='left')
gl = gl.merge(b7_labels, on='game_id', how='left')
gl = gl.merge(canon_odds[['game_id', 'fair_over']], on='game_id', how='left')
gl = gl.merge(hbk, on='game_id', how='left')

# Join model edge
edge_col = 'edge_over' if 'edge_over' in mo.columns else 'edge'
gl = gl.merge(mo[['game_id', edge_col]].rename(columns={edge_col: 'model_edge'}), on='game_id', how='left')

gl['both_starters'] = (gl['h_bk'] == 0) & (gl['a_bk'] == 0)
gl['over_hit'] = (gl['total_goals'] > gl['closing_total']).astype(int)
gl['under_hit'] = (gl['total_goals'] < gl['closing_total']).astype(int)
gl['residual'] = gl['total_goals'] - gl['closing_total']

starters = gl[gl['both_starters'] & gl['model_edge'].notna()].copy()
print(f"\nConfirmed-starter games with edge: {len(starters)}")
print(f"Edge >= 0.12: {(starters['model_edge'] >= 0.12).sum()}")

# ═══════════════════════════════════════════════════════════════
# STEP 2 — BASELINE
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 2 — BASELINE (edge >= 0.12, confirmed starters)")
print(SEP)

edge_games = starters[starters['model_edge'] >= 0.12].copy()
print(f"N: {len(edge_games)}")
if len(edge_games) > 10:
    over = edge_games['over_hit'].mean()
    impl = edge_games[edge_games['fair_over'].notna()]['fair_over'].mean()
    resid = over - impl if not np.isnan(impl) else 0
    wins = edge_games['over_hit'].sum()
    losses = edge_games['under_hit'].sum()
    roi = (wins*(10/11) - losses) / (wins+losses) * 100 if (wins+losses) > 0 else 0
    print(f"Over: {over:.3f}, Fair implied: {impl:.3f}, Residual: {resid:+.3f}, ROI: {roi:+.1f}%")
    for season in sorted(edge_games['season_year'].unique()):
        s = edge_games[edge_games['season_year'] == season]
        if len(s) >= 3:
            print(f"  {season}: N={len(s)}, Over={s['over_hit'].mean():.3f}")
else:
    print("Too few edge games")

# ═══════════════════════════════════════════════════════════════
# STEP 3 — EDGE CONDITIONING
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 3 — EDGE CONDITIONING")
print(SEP)

for branch, col in [('Branch 8', 'b8_label'), ('Branch 7', 'b7_label')]:
    print(f"\n  {branch}:")
    print(f"  {'Context':<15} {'N':>5} {'Over%':>7} {'Resid':>7} {'ROI':>7}")
    print(f"  {'-'*45}")
    for label in ['FAVORABLE', 'NEUTRAL', 'UNFAVORABLE']:
        sub = edge_games[edge_games[col] == label]
        if len(sub) < 5:
            print(f"  {label:<15} {len(sub):>5} — THIN")
            continue
        ov = sub['over_hit'].mean()
        imp = sub[sub['fair_over'].notna()]['fair_over'].mean()
        r = ov - imp if not np.isnan(imp) else 0
        w = sub['over_hit'].sum()
        l = sub['under_hit'].sum()
        roi_v = (w*(10/11)-l)/(w+l)*100 if (w+l)>0 else 0
        print(f"  {label:<15} {len(sub):>5} {ov:>7.3f} {r:>+7.3f} {roi_v:>+7.1f}%")

# ═══════════════════════════════════════════════════════════════
# STEP 4 — THRESHOLD MODIFIER
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 4 — THRESHOLD MODIFIER")
print(SEP)

for branch, col in [('Branch 8', 'b8_label'), ('Branch 7', 'b7_label')]:
    print(f"\n  {branch}:")
    # A) Lower threshold + FAVORABLE
    fav_low = starters[(starters['model_edge'] >= 0.10) & (starters[col] == 'FAVORABLE')]
    baseline = starters[starters['model_edge'] >= 0.12]
    if len(fav_low) >= 10:
        ov_fl = fav_low['over_hit'].mean()
        ov_bl = baseline['over_hit'].mean()
        print(f"  A) edge>=0.10 + FAVORABLE: N={len(fav_low)}, Over={ov_fl:.3f} (baseline edge>=0.12: {ov_bl:.3f})")
    # B) Edge >= 0.12 but UNFAVORABLE — should we pass?
    unfav = starters[(starters['model_edge'] >= 0.12) & (starters[col] == 'UNFAVORABLE')]
    rest = starters[(starters['model_edge'] >= 0.12) & (starters[col] != 'UNFAVORABLE')]
    if len(unfav) >= 5 and len(rest) >= 10:
        print(f"  B) edge>=0.12 + UNFAVORABLE: N={len(unfav)}, Over={unfav['over_hit'].mean():.3f}")
        print(f"     edge>=0.12 excl UNFAVORABLE: N={len(rest)}, Over={rest['over_hit'].mean():.3f}")

# ═══════════════════════════════════════════════════════════════
# STEP 5 — PASS FILTER
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 5 — PASS FILTER")
print(SEP)

for branch, col in [('Branch 8', 'b8_label'), ('Branch 7', 'b7_label')]:
    unfav = edge_games[edge_games[col] == 'UNFAVORABLE']
    if len(unfav) >= 5:
        ov = unfav['over_hit'].mean()
        print(f"  {branch} UNFAVORABLE in edge>=0.12: N={len(unfav)}, Over={ov:.3f}")
        print(f"    Below 48%? {'YES' if ov < 0.48 else 'NO'}")
        # Season consistency
        cons = 0
        for season in sorted(unfav['season_year'].unique()):
            s = unfav[unfav['season_year'] == season]
            if len(s) >= 3 and s['over_hit'].mean() < 0.48:
                cons += 1
        print(f"    Consistent seasons: {cons}/{len(unfav['season_year'].unique())}")

# ═══════════════════════════════════════════════════════════════
# STEP 6 — COMBINED LAYER
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 6 — COMBINED LAYER")
print(SEP)

both_fav = edge_games[(edge_games['b8_label'] == 'FAVORABLE') & (edge_games['b7_label'] == 'FAVORABLE')]
either_unfav = edge_games[(edge_games['b8_label'] == 'UNFAVORABLE') | (edge_games['b7_label'] == 'UNFAVORABLE')]

print(f"Edge>=0.12 + FAVORABLE both: N={len(both_fav)}")
if len(both_fav) >= 5:
    print(f"  Over: {both_fav['over_hit'].mean():.3f}")
print(f"Edge>=0.12 + UNFAVORABLE either: N={len(either_unfav)}")
if len(either_unfav) >= 5:
    print(f"  Over: {either_unfav['over_hit'].mean():.3f}")

# ═══════════════════════════════════════════════════════════════
# STEP 7 — CLV CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 7 — CLV CHECK")
print(SEP)

# Check if multi-snapshot line history exists
try:
    mkt_snaps = pd.read_parquet('nhl/nhl_market_snapshots.parquet')
    print(f"Market snapshots: {len(mkt_snaps)} rows")
    print(f"Columns: {sorted(mkt_snaps.columns)}")
    if len(mkt_snaps) > 0:
        # Check if we can compute CLV
        snap_cols = [c for c in mkt_snaps.columns if 'open' in c.lower() or 'close' in c.lower() or 'line' in c.lower()]
        print(f"Line columns: {snap_cols}")
except Exception:
    print("No multi-snapshot line history available. CLV check omitted.")

# ═══════════════════════════════════════════════════════════════
# DECISION
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("DECISION SUMMARY")
print(SEP)

print(f"\nBaseline edge >= 0.12 (starters): N={len(edge_games)}, Over={edge_games['over_hit'].mean():.3f}")
