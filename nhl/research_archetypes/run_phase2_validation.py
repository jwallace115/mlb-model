#!/usr/bin/env python3
"""Phase 2: ANEMIC x BEND_NOT_BREAK Practical Validation."""
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

# ── Rebuild archetypes (exact Phase 1 pipeline) ──
rows = []
for _, g in ft.iterrows():
    for side in ['home', 'away']:
        opp = 'away' if side == 'home' else 'home'
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
            'opp_backup': g.get(f'{opp}_backup_flag', 0),
            'b2b': g.get(f'{side}_b2b', 0),
            'rest': g.get(f'{side}_days_rest', 3),
        })
tg = pd.DataFrame(rows)
tg['hd_danger_rate_d'] = tg['hd_sa_r20'] / tg['sa_r20'].clip(lower=1)
tg['hd_danger_rate_o'] = tg['hd_sf_r20'] / tg['sf_r20'].clip(lower=1)

def_feats = ['sa_r20', 'hd_sa_r20', 'xga_r20', 'hd_danger_rate_d']
off_feats = ['sf_r20', 'hd_sf_r20', 'xgf_r20', 'hd_danger_rate_o']

def_clean = tg.dropna(subset=def_feats).copy()
off_clean = tg.dropna(subset=off_feats).copy()

sc_d = StandardScaler()
km_d = KMeans(n_clusters=3, random_state=42, n_init=10)
def_clean['def_cl'] = km_d.fit_predict(sc_d.fit_transform(def_clean[def_feats]))
cent_d = pd.DataFrame(sc_d.inverse_transform(km_d.cluster_centers_), columns=def_feats)
# Label (same logic as Phase 1)
ranked_xga = cent_d['xga_r20'].rank()
dlabels = {}
for i in range(3):
    if ranked_xga[i] == 1: dlabels[i] = 'SUPPRESSOR'
    elif ranked_xga[i] == 3: dlabels[i] = 'BEND_NOT_BREAK'
    else: dlabels[i] = 'POROUS'
# Verify by checking SA — BNB should have highest SA
sa_ranked = cent_d['sa_r20'].rank()
if sa_ranked[list(dlabels.keys())[list(dlabels.values()).index('BEND_NOT_BREAK')]] != 3:
    # Relabel by SA + danger rate
    for i in range(3):
        sa = cent_d.loc[i, 'sa_r20']
        hdr = cent_d.loc[i, 'hd_danger_rate_d']
        if sa <= cent_d['sa_r20'].median() and hdr <= cent_d['hd_danger_rate_d'].median():
            dlabels[i] = 'SUPPRESSOR'
        elif sa > cent_d['sa_r20'].median() and hdr <= cent_d['hd_danger_rate_d'].median():
            dlabels[i] = 'BEND_NOT_BREAK'
        else:
            dlabels[i] = 'POROUS'
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

# Merge to game level
home_off = off_clean[off_clean['is_home']][['game_id', 'off_label']].rename(columns={'off_label': 'home_off'})
away_def = def_clean[~def_clean['is_home']][['game_id', 'def_label']].rename(columns={'def_label': 'away_def'})
away_off = off_clean[~off_clean['is_home']][['game_id', 'off_label']].rename(columns={'off_label': 'away_off'})
home_def = def_clean[def_clean['is_home']][['game_id', 'def_label']].rename(columns={'def_label': 'home_def'})
home_bk = def_clean[def_clean['is_home']][['game_id', 'backup', 'opp_backup']].rename(
    columns={'backup': 'home_backup', 'opp_backup': 'away_backup'})

gl = ft[['game_id', 'game_date', 'season_year', 'closing_total', 'total_goals',
         'home_team', 'away_team', 'market_available']].copy()
gl = gl.merge(home_off, on='game_id', how='left')
gl = gl.merge(away_def, on='game_id', how='left')
gl = gl.merge(away_off, on='game_id', how='left')
gl = gl.merge(home_def, on='game_id', how='left')
gl = gl.merge(home_bk, on='game_id', how='left')

mkt = gl.dropna(subset=['closing_total', 'home_off', 'away_def', 'away_off', 'home_def']).copy()
mkt['over_hit'] = (mkt['total_goals'] > mkt['closing_total']).astype(int)
mkt['under_hit'] = (mkt['total_goals'] < mkt['closing_total']).astype(int)
mkt['push'] = (mkt['total_goals'] == mkt['closing_total']).astype(int)

# Qualifying groups
mkt['ho_ad_qualifies'] = (mkt['home_off'] == 'ANEMIC') & (mkt['away_def'] == 'BEND_NOT_BREAK')
mkt['ao_hd_qualifies'] = (mkt['away_off'] == 'ANEMIC') & (mkt['home_def'] == 'BEND_NOT_BREAK')
mkt['either_qualifies'] = mkt['ho_ad_qualifies'] | mkt['ao_hd_qualifies']
mkt['both_qualify'] = mkt['ho_ad_qualifies'] & mkt['ao_hd_qualifies']

print(f"Total games with labels + market: {len(mkt)}")

# ═══════════════════════════════════════════════════════════════
# STEP 1 — OVER HIT RATE
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 1 — OVER HIT RATE")
print(SEP)

base_over = mkt['over_hit'].mean()
base_n = len(mkt)
print(f"Base: N={base_n}, over={base_over:.3f}")

groups = [
    ('A) Home ANEMIC x Away BNB', 'ho_ad_qualifies'),
    ('B) Away ANEMIC x Home BNB', 'ao_hd_qualifies'),
    ('C) Either side qualifies', 'either_qualifies'),
    ('D) Both sides qualify', 'both_qualify'),
]

print(f"\n{'Group':<35} {'N':>5} {'Over%':>6} {'Under%':>7} {'Push%':>6} {'Lift':>6}")
print("-" * 70)
for label, col in groups:
    sub = mkt[mkt[col]]
    if len(sub) < 5:
        print(f"{label:<35} {len(sub):>5} — TOO THIN")
        continue
    over = sub['over_hit'].mean()
    under = sub['under_hit'].mean()
    push = sub['push'].mean()
    lift = over / base_over
    se = np.sqrt(over * (1 - over) / len(sub))
    print(f"{label:<35} {len(sub):>5} {over:>6.3f} {under:>7.3f} {push:>6.3f} {lift:>5.2f}x")

# By season
print(f"\nBy season (Either qualifies):")
for season in sorted(mkt['season_year'].unique()):
    sub = mkt[(mkt['season_year'] == season) & mkt['either_qualifies']]
    base_s = mkt[mkt['season_year'] == season]['over_hit'].mean()
    if len(sub) >= 10:
        print(f"  {season}: N={len(sub)}, over={sub['over_hit'].mean():.3f} (base={base_s:.3f})")

# ═══════════════════════════════════════════════════════════════
# STEP 2 — MARKET RESIDUAL
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 2 — MARKET RESIDUAL")
print(SEP)

# Load odds data if available
try:
    dec = pd.read_parquet('nhl/nhl_decisions.parquet')
    has_odds = True
    print(f"Decisions: {len(dec)} rows")
    odds_cols = [c for c in dec.columns if 'over_price' in c or 'under_price' in c or 'implied' in c]
    print(f"Odds columns: {odds_cols}")
except Exception:
    has_odds = False

# Use canonical for odds
canon = pd.read_csv('nhl/nhl_games_canonical.csv')
canon_odds = canon[['game_id', 'over_price', 'under_price']].copy()
canon_odds = canon_odds.dropna(subset=['over_price', 'under_price'])

def american_to_implied(odds):
    if pd.isna(odds): return np.nan
    if odds < 0: return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)

canon_odds['impl_over'] = canon_odds['over_price'].apply(american_to_implied)
canon_odds['impl_under'] = canon_odds['under_price'].apply(american_to_implied)
# Remove vig
canon_odds['total_impl'] = canon_odds['impl_over'] + canon_odds['impl_under']
canon_odds['fair_over'] = canon_odds['impl_over'] / canon_odds['total_impl']

mkt = mkt.merge(canon_odds[['game_id', 'fair_over', 'over_price']], on='game_id', how='left')

for label, col in groups:
    sub = mkt[mkt[col] & mkt['fair_over'].notna()]
    if len(sub) < 20:
        continue
    actual_over = sub['over_hit'].mean()
    impl_over = sub['fair_over'].mean()
    resid = actual_over - impl_over
    # ROI at -110
    wins = sub['over_hit'].sum()
    losses = sub['under_hit'].sum()
    roi = (wins * (10/11) - losses) / (wins + losses) * 100 if (wins + losses) > 0 else 0
    print(f"  {label}:")
    print(f"    N={len(sub)}, actual_over={actual_over:.3f}, fair_implied={impl_over:.3f}")
    print(f"    Residual: {resid:+.3f} ({resid*100:+.1f}pp)")
    print(f"    ROI at -110: {roi:+.1f}%")

# ═══════════════════════════════════════════════════════════════
# STEP 3 — GOALIE STATE INTERACTION
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 3 — GOALIE STATE INTERACTION")
print(SEP)

qual = mkt[mkt['either_qualifies']].copy()
qual['goalie_state'] = 'unknown'
qual.loc[(qual['home_backup'] == 0) & (qual['away_backup'] == 0), 'goalie_state'] = 'both_starters'
qual.loc[(qual['home_backup'] == 1) | (qual['away_backup'] == 1), 'goalie_state'] = 'has_backup'

print(f"\n{'Goalie State':<20} {'N':>5} {'Over%':>7} {'Residual':>9}")
print("-" * 45)
for state in ['both_starters', 'has_backup', 'unknown']:
    sub = qual[qual['goalie_state'] == state]
    if len(sub) < 10:
        print(f"{state:<20} {len(sub):>5} — THIN")
        continue
    over = sub['over_hit'].mean()
    impl = sub['fair_over'].mean() if sub['fair_over'].notna().sum() > 5 else base_over
    resid = over - impl
    print(f"{state:<20} {len(sub):>5} {over:>7.3f} {resid:>+9.3f}")

# ═══════════════════════════════════════════════════════════════
# STEP 4 — INTERACTION WITH CURRENT EDGE SIGNAL
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 4 — EDGE SIGNAL INTERACTION")
print(SEP)

# Load model outputs to get edge
try:
    mo = pd.read_parquet('nhl/nhl_model_outputs.parquet')
    if 'edge' in mo.columns or 'model_edge' in mo.columns:
        edge_col = 'edge' if 'edge' in mo.columns else 'model_edge'
        mo_slim = mo[['game_id', edge_col]].rename(columns={edge_col: 'model_edge'})
        mkt = mkt.merge(mo_slim, on='game_id', how='left')
        print(f"Model edge coverage: {mkt['model_edge'].notna().mean():.0%}")

        qual_edge = mkt[mkt['either_qualifies'] & mkt['model_edge'].notna()].copy()
        qual_edge['edge_high'] = qual_edge['model_edge'] >= 0.12

        print(f"\nArchetype + edge interaction:")
        for label, mask in [('Archetype + edge >= 0.12', qual_edge['edge_high']),
                            ('Archetype + edge < 0.12', ~qual_edge['edge_high'])]:
            sub = qual_edge[mask]
            if len(sub) < 10:
                print(f"  {label}: N={len(sub)} — THIN")
                continue
            over = sub['over_hit'].mean()
            print(f"  {label}: N={len(sub)}, over={over:.3f}")

        # What fraction of archetype games also have high edge?
        pct_overlap = qual_edge['edge_high'].mean()
        print(f"\n  Fraction of archetype games with edge >= 0.12: {pct_overlap:.1%}")
        print(f"  Fraction of ALL games with edge >= 0.12: {mkt[mkt['model_edge'].notna()]['model_edge'].ge(0.12).mean():.1%}")
    else:
        print(f"Model outputs columns: {list(mo.columns)[:15]}")
except Exception as e:
    print(f"Could not load model outputs: {e}")

# ═══════════════════════════════════════════════════════════════
# STEP 5 — HEURISTIC COMPARISON
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 5 — HEURISTIC COMPARISON")
print(SEP)

median_total = mkt['closing_total'].median()
print(f"Closing total median: {median_total}")

comparisons = [
    ('Random (all games)', mkt),
    ('Closing total > median', mkt[mkt['closing_total'] > median_total]),
    ('Closing total <= median', mkt[mkt['closing_total'] <= median_total]),
    ('ANEMIC x BNB (either)', mkt[mkt['either_qualifies']]),
]

# High xG sum
mkt_with_xg = mkt.merge(
    ft[['game_id', 'home_xgf_rolling_20', 'away_xgf_rolling_20']].dropna(), on='game_id', how='left')
mkt_with_xg['xg_sum'] = mkt_with_xg['home_xgf_rolling_20'] + mkt_with_xg['away_xgf_rolling_20']
xg_q75 = mkt_with_xg['xg_sum'].quantile(0.75)
comparisons.append(('Top 25% xG sum', mkt_with_xg[mkt_with_xg['xg_sum'] >= xg_q75]))

# High shot sum
mkt_with_shots = mkt.merge(
    ft[['game_id', 'home_shots_for_rolling_20', 'away_shots_for_rolling_20']].dropna(), on='game_id', how='left')
mkt_with_shots['shot_sum'] = mkt_with_shots['home_shots_for_rolling_20'] + mkt_with_shots['away_shots_for_rolling_20']
shot_q75 = mkt_with_shots['shot_sum'].quantile(0.75)
comparisons.append(('Top 25% shot sum', mkt_with_shots[mkt_with_shots['shot_sum'] >= shot_q75]))

print(f"\n{'Method':<30} {'N':>6} {'Over%':>7} {'Lift':>6}")
print("-" * 52)
for label, sub in comparisons:
    if len(sub) < 20:
        continue
    over = sub['over_hit'].mean()
    lift = over / base_over
    print(f"{label:<30} {len(sub):>6} {over:>7.3f} {lift:>5.2f}x")

# ═══════════════════════════════════════════════════════════════
# DECISION
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("DECISION SUMMARY")
print(SEP)

either = mkt[mkt['either_qualifies']]
n = len(either)
over_rate = either['over_hit'].mean()
fair_impl = either[either['fair_over'].notna()]['fair_over'].mean()
resid = over_rate - fair_impl if not np.isnan(fair_impl) else 0

print(f"\nEither-side qualifying group:")
print(f"  N: {n}")
print(f"  Over rate: {over_rate:.3f}")
print(f"  Base rate: {base_over:.3f}")
print(f"  Residual vs implied: {resid:+.3f}")
print(f"\nCriteria check:")
print(f"  Over > 55% with N >= 100? {'PASS' if over_rate > 0.55 and n >= 100 else 'FAIL'} (over={over_rate:.3f}, N={n})")
print(f"  Residual > 3pp? {'PASS' if resid > 0.03 else 'FAIL'} (resid={resid:+.3f})")
