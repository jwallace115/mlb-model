#!/usr/bin/env python3
"""Phase 3: NHL Archetype Expansion — Generate 40 candidates, rank, test top 8."""
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

# ── Build team-game table ──
rows = []
for _, g in ft.iterrows():
    for side in ['home', 'away']:
        opp = 'away' if side == 'home' else 'home'
        c_row = canon[canon['game_id'] == g['game_id']]
        cr = c_row.iloc[0] if len(c_row) > 0 else {}
        rows.append({
            'game_id': g['game_id'], 'game_date': g['game_date'],
            'season': g['season_year'], 'team': g[f'{side}_team'],
            'is_home': side == 'home',
            # Defense
            'sa_r20': g[f'{side}_shots_against_rolling_20'],
            'hd_sa_r20': g[f'{side}_hd_shots_against_rolling_20'],
            'xga_r20': g[f'{side}_xga_rolling_20'],
            # Offense
            'sf_r20': g[f'{side}_shots_for_rolling_20'],
            'hd_sf_r20': g[f'{side}_hd_shots_for_rolling_20'],
            'xgf_r20': g[f'{side}_xgf_rolling_20'],
            # Context
            'closing_total': g['closing_total'],
            'total_goals': g['total_goals'],
            'backup': g.get(f'{side}_backup_flag', 0),
            'opp_backup': g.get(f'{opp}_backup_flag', 0),
            'b2b': g.get(f'{side}_b2b', 0),
            'rest': g.get(f'{side}_days_rest', 3),
            'goalie_fatigue': g.get(f'{side}_goalie_fatigue', 0),
            'goalie_b2b': g.get(f'{side}_goalie_b2b', 0),
            # Penalties / special teams
            'pp_pct_r20': g.get(f'{side}_pp_pct_rolling_20', np.nan),
            'pk_pct_r20': g.get(f'{side}_pk_pct_rolling_20', np.nan),
            'pen_r20': g.get(f'{side}_penalties_taken_rolling_20', np.nan),
            'pp_opp_r20': g.get(f'{side}_pp_opp_per_game_rolling_20', np.nan),
            'shot_pressure': g.get(f'{side}_shot_pressure', np.nan),
            'hd_pressure': g.get(f'{side}_hd_pressure', np.nan),
            # Per-game canonical
            'corsi_pct': cr.get(f'{side}_corsi_pct', np.nan) if isinstance(cr, dict) else getattr(cr, f'{side}_corsi_pct', np.nan),
            'fenwick_pct': cr.get(f'{side}_fenwick_pct', np.nan) if isinstance(cr, dict) else getattr(cr, f'{side}_fenwick_pct', np.nan),
            'hd_shots': cr.get(f'{side}_hd_shots', np.nan) if isinstance(cr, dict) else getattr(cr, f'{side}_hd_shots', np.nan),
            'shots_on_goal': cr.get(f'{side}_shots_on_goal', np.nan) if isinstance(cr, dict) else getattr(cr, f'{side}_shots_on_goal', np.nan),
        })
tg = pd.DataFrame(rows)

# Derived features
tg['hd_rate_d'] = tg['hd_sa_r20'] / tg['sa_r20'].clip(lower=1)
tg['hd_rate_o'] = tg['hd_sf_r20'] / tg['sf_r20'].clip(lower=1)
tg['xg_efficiency'] = tg['xgf_r20'] / tg['sf_r20'].clip(lower=1)  # xG per shot
tg['xg_suppress'] = tg['xga_r20'] / tg['sa_r20'].clip(lower=1)  # xGA per shot allowed
tg['volume_ratio'] = tg['sf_r20'] / tg['sa_r20'].clip(lower=1)  # shot dominance
tg['danger_ratio'] = tg['hd_sf_r20'] / tg['hd_sa_r20'].clip(lower=0.1)  # HD dominance
tg['pp_pk_net'] = tg['pp_pct_r20'].fillna(20) - (100 - tg['pk_pct_r20'].fillna(80))
tg['pen_diff'] = tg['pen_r20'].fillna(3) - tg['pp_opp_r20'].fillna(3)  # discipline imbalance

print(f"Team-game table: {len(tg)} rows, {len(tg.columns)} cols")

# ═══════════════════════════════════════════════════════════════
# FAST VALIDATION HARNESS
# ═══════════════════════════════════════════════════════════════

def run_archetype_test(name, off_features, def_features, k_off=2, k_def=2):
    """Fast-kill archetype test. Returns summary dict."""
    # Build clusters
    off_valid = tg.dropna(subset=off_features).copy()
    def_valid = tg.dropna(subset=def_features).copy()

    if len(off_valid) < 2000 or len(def_valid) < 2000:
        return {'name': name, 'verdict': 'SKIP', 'reason': 'insufficient coverage'}

    sc_o = StandardScaler()
    km_o = KMeans(n_clusters=k_off, random_state=42, n_init=10)
    off_valid['off_cl'] = km_o.fit_predict(sc_o.fit_transform(off_valid[off_features]))

    sc_d = StandardScaler()
    km_d = KMeans(n_clusters=k_def, random_state=42, n_init=10)
    def_valid['def_cl'] = km_d.fit_predict(sc_d.fit_transform(def_valid[def_features]))

    # Merge to game level
    ho = off_valid[off_valid['is_home']][['game_id', 'off_cl']].rename(columns={'off_cl': 'ho'})
    ad = def_valid[~def_valid['is_home']][['game_id', 'def_cl']].rename(columns={'def_cl': 'ad'})
    ao = off_valid[~off_valid['is_home']][['game_id', 'off_cl']].rename(columns={'off_cl': 'ao'})
    hd = def_valid[def_valid['is_home']][['game_id', 'def_cl']].rename(columns={'def_cl': 'hd'})
    hbk = tg[tg['is_home']][['game_id', 'backup', 'opp_backup']].rename(
        columns={'backup': 'h_bk', 'opp_backup': 'a_bk'}).drop_duplicates('game_id')

    gl = ft[['game_id', 'season_year', 'closing_total', 'total_goals']].copy()
    gl = gl.merge(ho, on='game_id', how='left').merge(ad, on='game_id', how='left')
    gl = gl.merge(ao, on='game_id', how='left').merge(hd, on='game_id', how='left')
    gl = gl.merge(hbk, on='game_id', how='left')

    mkt = gl.dropna(subset=['closing_total', 'ho', 'ad']).copy()
    mkt['residual'] = mkt['total_goals'] - mkt['closing_total']
    mkt['both_starters'] = (mkt['h_bk'] == 0) & (mkt['a_bk'] == 0)

    # Find best cell across all matchups (both sides)
    best = {'resid': 0, 'n': 0}
    best_starter = {'resid': 0, 'n': 0}

    for side_label, o_col, d_col in [('HO_AD', 'ho', 'ad'), ('AO_HD', 'ao', 'hd')]:
        valid = mkt.dropna(subset=[o_col, d_col])
        for oc in range(k_off):
            for dc in range(k_def):
                sub = valid[(valid[o_col] == oc) & (valid[d_col] == dc)]
                if len(sub) < 30:
                    continue
                resid = sub['residual'].mean()
                if abs(resid) > abs(best['resid']):
                    best = {'side': side_label, 'off_cl': oc, 'def_cl': dc,
                            'resid': resid, 'n': len(sub)}

                # Confirmed starters only
                starters = sub[sub['both_starters']]
                if len(starters) >= 20:
                    s_resid = starters['residual'].mean()
                    if abs(s_resid) > abs(best_starter['resid']):
                        best_starter = {'side': side_label, 'off_cl': oc, 'def_cl': dc,
                                        'resid': s_resid, 'n': len(starters), 'n_full': len(sub)}

    if best['n'] == 0:
        return {'name': name, 'verdict': 'ARCHIVE', 'reason': 'no cell with N>=30',
                'best_resid': 0, 'best_n': 0, 'starter_resid': 0, 'starter_n': 0}

    # Season consistency for best cell
    if best_starter['n'] >= 20:
        test_cell = best_starter
    else:
        test_cell = best

    consistent = 0
    for season in [2021, 2022, 2023, 2024]:
        if test_cell.get('side') == 'HO_AD':
            s = mkt[(mkt['season_year'] == season) & (mkt['ho'] == test_cell['off_cl']) & (mkt['ad'] == test_cell['def_cl'])]
        else:
            s = mkt[(mkt['season_year'] == season) & (mkt['ao'] == test_cell['off_cl']) & (mkt['hd'] == test_cell['def_cl'])]
        if len(s) >= 5 and (s['residual'].mean() > 0) == (test_cell['resid'] > 0):
            consistent += 1

    # Concentration
    if test_cell.get('side') == 'HO_AD':
        cell_games = mkt[(mkt['ho'] == test_cell['off_cl']) & (mkt['ad'] == test_cell['def_cl'])]
    else:
        cell_games = mkt[(mkt['ao'] == test_cell['off_cl']) & (mkt['hd'] == test_cell['def_cl'])]
    cell_with_teams = cell_games.merge(ft[['game_id', 'home_team', 'away_team']], on='game_id', how='left')
    all_t = list(cell_with_teams['home_team']) + list(cell_with_teams['away_team'])
    tc = pd.Series(all_t).value_counts()
    top2_share = tc.head(2).sum() / len(all_t) * 100 if len(all_t) > 0 else 100

    # Verdict
    s_resid = best_starter.get('resid', 0)
    s_n = best_starter.get('n', 0)

    if abs(s_resid) >= 0.25 and s_n >= 50 and consistent >= 3 and top2_share < 25:
        verdict = 'ADVANCE'
    elif abs(s_resid) >= 0.15 and s_n >= 30 and consistent >= 3:
        verdict = 'NEAR_MISS'
    else:
        verdict = 'ARCHIVE'

    return {
        'name': name,
        'verdict': verdict,
        'best_resid': best['resid'],
        'best_n': best['n'],
        'starter_resid': s_resid,
        'starter_n': s_n,
        'seasons_consistent': consistent,
        'top2_share': top2_share,
    }

# ═══════════════════════════════════════════════════════════════
# TOP 8 BRANCHES (selected from ranked 40 — see report for full list)
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("RUNNING TOP 8 ARCHETYPE BRANCHES")
print(SEP)

branches = [
    # 1. HD Pressure Asymmetry (off hd_pressure vs def hd_pressure)
    ("1. HD Pressure Asymmetry",
     ['hd_pressure', 'hd_rate_o'], ['hd_pressure', 'hd_rate_d']),

    # 2. Shot Volume vs xG Efficiency (quantity vs quality offense)
    ("2. Volume vs Efficiency",
     ['sf_r20', 'xg_efficiency'], ['sa_r20', 'xg_suppress']),

    # 3. Penalty Discipline Environment
    ("3. Penalty Environment",
     ['pen_r20', 'pp_pct_r20'], ['pen_r20', 'pk_pct_r20']),

    # 4. Shot Dominance Ratio (Corsi-style)
    ("4. Shot Dominance",
     ['volume_ratio', 'xgf_r20'], ['volume_ratio', 'xga_r20']),

    # 5. Danger Concentration Asymmetry
    ("5. Danger Concentration",
     ['hd_rate_o', 'xgf_r20'], ['hd_rate_d', 'xga_r20']),

    # 6. Goalie Workload Shape (fatigue + shots faced context)
    ("6. Goalie Workload",
     ['sf_r20', 'hd_sf_r20'], ['sa_r20', 'hd_sa_r20']),

    # 7. PP/PK Net + Penalty Load
    ("7. Special Teams Net",
     ['pp_pk_net', 'pp_opp_r20'], ['pp_pk_net', 'pen_r20']),

    # 8. xG Share + Danger Share (combined process dominance)
    ("8. Process Dominance",
     ['xgf_r20', 'danger_ratio'], ['xga_r20', 'danger_ratio']),
]

results = []
for name, off_f, def_f in branches:
    print(f"\n  Testing: {name}...")
    r = run_archetype_test(name, off_f, def_f, k_off=2, k_def=2)
    results.append(r)
    print(f"    Verdict: {r['verdict']} | best={r.get('best_resid',0):+.2f}(N={r.get('best_n',0)}) "
          f"starter={r.get('starter_resid',0):+.2f}(N={r.get('starter_n',0)}) "
          f"seasons={r.get('seasons_consistent',0)}/4 top2={r.get('top2_share',0):.0f}%")

# Summary
print(f"\n{SEP}")
print("SUMMARY TABLE")
print(SEP)
print(f"\n{'Branch':<30} {'Verdict':<12} {'Best':>6} {'N':>5} {'Starter':>8} {'N_s':>5} {'Seas':>5} {'Top2%':>6}")
print("-" * 82)
for r in results:
    print(f"{r['name']:<30} {r['verdict']:<12} {r.get('best_resid',0):>+6.2f} {r.get('best_n',0):>5} "
          f"{r.get('starter_resid',0):>+8.2f} {r.get('starter_n',0):>5} "
          f"{r.get('seasons_consistent',0):>4}/4 {r.get('top2_share',0):>5.0f}%")

advanced = [r for r in results if r['verdict'] == 'ADVANCE']
near_miss = [r for r in results if r['verdict'] == 'NEAR_MISS']
print(f"\nADVANCED: {len(advanced)}")
for r in advanced:
    print(f"  {r['name']}: starter_resid={r['starter_resid']:+.2f} N={r['starter_n']}")
print(f"NEAR MISS: {len(near_miss)}")
for r in near_miss:
    print(f"  {r['name']}: starter_resid={r['starter_resid']:+.2f} N={r['starter_n']}")
