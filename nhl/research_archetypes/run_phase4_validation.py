#!/usr/bin/env python3
"""Phase 4: Practical validation of Branch 7 (Special Teams Net) and Branch 8 (Process Dominance)."""
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
tg['hd_rate_d'] = tg['hd_sa_r20'] / tg['sa_r20'].clip(lower=1)
tg['hd_rate_o'] = tg['hd_sf_r20'] / tg['sf_r20'].clip(lower=1)
tg['xg_efficiency'] = tg['xgf_r20'] / tg['sf_r20'].clip(lower=1)
tg['xg_suppress'] = tg['xga_r20'] / tg['sa_r20'].clip(lower=1)
tg['danger_ratio'] = tg['hd_sf_r20'] / tg['hd_sa_r20'].clip(lower=0.1)
tg['pp_pk_net'] = tg['pp_pct_r20'].fillna(20) - (100 - tg['pk_pct_r20'].fillna(80))

# Odds from canonical
canon_odds = canon[['game_id', 'over_price', 'under_price', 'total_line']].dropna(subset=['over_price'])
def a2i(o):
    if pd.isna(o): return np.nan
    return abs(o) / (abs(o) + 100) if o < 0 else 100 / (o + 100)
canon_odds['impl_over'] = canon_odds['over_price'].apply(a2i)
canon_odds['impl_under'] = canon_odds['under_price'].apply(a2i)
canon_odds['fair_over'] = canon_odds['impl_over'] / (canon_odds['impl_over'] + canon_odds['impl_under'])

# Model outputs for edge
try:
    mo = pd.read_parquet('nhl/nhl_model_outputs.parquet')
    edge_col = 'edge_over' if 'edge_over' in mo.columns else 'edge'
    mo_slim = mo[['game_id', edge_col]].rename(columns={edge_col: 'model_edge'})
    has_edge = True
except Exception:
    has_edge = False
    mo_slim = pd.DataFrame()


def run_branch_validation(branch_name, off_features, def_features):
    """Run full 6-test validation for one branch."""
    print(f"\n{'#' * 70}")
    print(f"  BRANCH: {branch_name}")
    print(f"{'#' * 70}")

    # Build clusters
    off_v = tg.dropna(subset=off_features).copy()
    def_v = tg.dropna(subset=def_features).copy()
    sc_o = StandardScaler(); sc_d = StandardScaler()
    km_o = KMeans(n_clusters=2, random_state=42, n_init=10)
    km_d = KMeans(n_clusters=2, random_state=42, n_init=10)
    off_v['off_cl'] = km_o.fit_predict(sc_o.fit_transform(off_v[off_features]))
    def_v['def_cl'] = km_d.fit_predict(sc_d.fit_transform(def_v[def_features]))

    # Game-level merge
    ho = off_v[off_v['is_home']][['game_id', 'off_cl']].rename(columns={'off_cl': 'ho'})
    ad = def_v[~def_v['is_home']][['game_id', 'def_cl']].rename(columns={'def_cl': 'ad'})
    ao = off_v[~off_v['is_home']][['game_id', 'off_cl']].rename(columns={'off_cl': 'ao'})
    hd = def_v[def_v['is_home']][['game_id', 'def_cl']].rename(columns={'def_cl': 'hd'})
    hbk = tg[tg['is_home']][['game_id', 'backup', 'opp_backup']].rename(
        columns={'backup': 'h_bk', 'opp_backup': 'a_bk'}).drop_duplicates('game_id')

    gl = ft[['game_id', 'season_year', 'closing_total', 'total_goals',
             'home_team', 'away_team']].copy()
    gl = gl.merge(ho, on='game_id', how='left').merge(ad, on='game_id', how='left')
    gl = gl.merge(ao, on='game_id', how='left').merge(hd, on='game_id', how='left')
    gl = gl.merge(hbk, on='game_id', how='left')
    gl = gl.merge(canon_odds[['game_id', 'fair_over']], on='game_id', how='left')
    if has_edge:
        gl = gl.merge(mo_slim, on='game_id', how='left')

    mkt = gl.dropna(subset=['closing_total', 'ho', 'ad']).copy()
    mkt['over_hit'] = (mkt['total_goals'] > mkt['closing_total']).astype(int)
    mkt['under_hit'] = (mkt['total_goals'] < mkt['closing_total']).astype(int)
    mkt['push'] = (mkt['total_goals'] == mkt['closing_total']).astype(int)
    mkt['residual'] = mkt['total_goals'] - mkt['closing_total']
    mkt['both_starters'] = (mkt['h_bk'] == 0) & (mkt['a_bk'] == 0)

    # Find best confirmed-starter cell
    best = {'resid': 0, 'n': 0, 'side': None, 'oc': None, 'dc': None}
    for side_l, oc, dc in [('HO_AD', 'ho', 'ad'), ('AO_HD', 'ao', 'hd')]:
        v = mkt.dropna(subset=[oc, dc])
        for o in range(2):
            for d in range(2):
                s = v[(v[oc] == o) & (v[dc] == d) & v['both_starters']]
                if len(s) >= 20 and abs(s['residual'].mean()) > abs(best['resid']):
                    best = {'resid': s['residual'].mean(), 'n': len(s),
                            'side': side_l, 'oc': o, 'dc': d,
                            'over': s['over_hit'].mean(), 'under': s['under_hit'].mean()}

    if best['n'] == 0:
        print("  No qualifying cell found.")
        return {'name': branch_name, 'verdict': 'ARCHIVE'}

    # Build mask for best cell (confirmed starters)
    if best['side'] == 'HO_AD':
        cell_mask = (mkt['ho'] == best['oc']) & (mkt['ad'] == best['dc'])
    else:
        cell_mask = (mkt['ao'] == best['oc']) & (mkt['hd'] == best['dc'])
    starter_mask = cell_mask & mkt['both_starters']

    qual = mkt[starter_mask].copy()
    qual_all = mkt[cell_mask].copy()
    base_starters = mkt[mkt['both_starters']]

    direction = 'OVER' if best['resid'] > 0 else 'UNDER'

    # ── TEST 1: HIT RATE ──
    print(f"\n  TEST 1 — HIT RATE (confirmed starters, direction: {direction})")
    base_over = base_starters['over_hit'].mean()
    over = qual['over_hit'].mean()
    under = qual['under_hit'].mean()
    push_r = qual['push'].mean()
    se = np.sqrt(over * (1 - over) / len(qual)) if len(qual) > 0 else 0
    hit_rate = over if direction == 'OVER' else under
    base_hit = base_over if direction == 'OVER' else base_starters['under_hit'].mean()
    lift = hit_rate / base_hit if base_hit > 0 else 0

    print(f"    N={len(qual)}, Over={over:.3f}, Under={under:.3f}, Push={push_r:.3f}")
    print(f"    Base (starters): Over={base_over:.3f}")
    print(f"    {direction} hit rate: {hit_rate:.3f} (base={base_hit:.3f}, lift={lift:.2f}x, SE={se:.3f})")

    # By season
    print(f"    By season:")
    season_consistent = 0
    for season in [2021, 2022, 2023, 2024]:
        s = qual[qual['season_year'] == season]
        bs = base_starters[base_starters['season_year'] == season]
        if len(s) < 5:
            print(f"      {season}: N={len(s)} — THIN")
            continue
        s_hit = s['over_hit'].mean() if direction == 'OVER' else s['under_hit'].mean()
        b_hit = bs['over_hit'].mean() if direction == 'OVER' else bs['under_hit'].mean()
        ok = s_hit > b_hit
        if ok: season_consistent += 1
        print(f"      {season}: N={len(s)}, {direction}={s_hit:.3f} (base={b_hit:.3f}) {'OK' if ok else 'FLIP'}")
    print(f"    Consistent: {season_consistent}/4")

    # ── TEST 2: MARKET RESIDUAL ──
    print(f"\n  TEST 2 — MARKET RESIDUAL")
    qual_mkt = qual[qual['fair_over'].notna()]
    if len(qual_mkt) >= 20:
        actual = qual_mkt['over_hit'].mean() if direction == 'OVER' else qual_mkt['under_hit'].mean()
        implied = qual_mkt['fair_over'].mean() if direction == 'OVER' else (1 - qual_mkt['fair_over'].mean())
        resid_mkt = actual - implied
        # ROI at -110
        if direction == 'OVER':
            wins = qual_mkt['over_hit'].sum()
            losses = qual_mkt['under_hit'].sum()
        else:
            wins = qual_mkt['under_hit'].sum()
            losses = qual_mkt['over_hit'].sum()
        roi = (wins * (10/11) - losses) / (wins + losses) * 100 if (wins + losses) > 0 else 0
        print(f"    N={len(qual_mkt)}, actual_{direction}={actual:.3f}, fair_implied={implied:.3f}")
        print(f"    Residual: {resid_mkt:+.3f} ({resid_mkt*100:+.1f}pp)")
        print(f"    ROI at -110: {roi:+.1f}%")
    else:
        resid_mkt = 0
        roi = 0
        print(f"    Insufficient odds data (N={len(qual_mkt)})")

    # ── TEST 3: EDGE INTERACTION ──
    print(f"\n  TEST 3 — EDGE SIGNAL INTERACTION")
    if has_edge and 'model_edge' in qual.columns:
        qual_edge = qual[qual['model_edge'].notna()].copy()
        if len(qual_edge) > 20:
            qual_edge['high_edge'] = qual_edge['model_edge'] >= 0.12
            for label, mask in [('Archetype + edge>=0.12', qual_edge['high_edge']),
                                ('Archetype + edge<0.12', ~qual_edge['high_edge'])]:
                sub = qual_edge[mask]
                if len(sub) >= 10:
                    hr = sub['over_hit'].mean() if direction == 'OVER' else sub['under_hit'].mean()
                    print(f"    {label}: N={len(sub)}, {direction}={hr:.3f}")
            overlap = qual_edge['high_edge'].mean()
            all_high = mkt[mkt['model_edge'].notna()]['model_edge'].ge(0.12).mean()
            print(f"    Overlap: {overlap:.1%} of archetype games have edge>=0.12 (vs {all_high:.1%} all games)")
        else:
            print(f"    Insufficient edge data (N={len(qual_edge)})")
    else:
        print(f"    Edge data not available")

    # ── TEST 4: HEURISTIC COMPARISON ──
    print(f"\n  TEST 4 — HEURISTIC COMPARISON")
    med = base_starters['closing_total'].median()
    comparisons = [
        ('Random (all starters)', base_starters),
        ('Closing > median', base_starters[base_starters['closing_total'] > med]),
        ('Closing <= median', base_starters[base_starters['closing_total'] <= med]),
        (f'Archetype ({direction})', qual),
    ]
    print(f"    {'Method':<30} {'N':>5} {f'{direction}%':>7} {'Lift':>6}")
    print(f"    {'-'*52}")
    for label, sub in comparisons:
        if len(sub) < 20: continue
        hr = sub['over_hit'].mean() if direction == 'OVER' else sub['under_hit'].mean()
        l = hr / base_hit if base_hit > 0 else 0
        print(f"    {label:<30} {len(sub):>5} {hr:>7.3f} {l:>5.2f}x")

    # ── TEST 5: CONCENTRATION ──
    print(f"\n  TEST 5 — CONCENTRATION")
    # qual_all already has home_team/away_team from gl merge
    if 'home_team' in qual_all.columns:
        all_teams = list(qual_all['home_team']) + list(qual_all['away_team'])
    else:
        all_teams = list(qual['home_team']) + list(qual['away_team']) if 'home_team' in qual.columns else []
    if all_teams:
        tc = pd.Series(all_teams).value_counts()
        top5 = tc.head(5)
        print(f"    Top 5: {dict(top5)}")
        print(f"    Top 2 share: {tc.head(2).sum()}/{len(all_teams)} = {tc.head(2).sum()/len(all_teams)*100:.0f}%")
        top2_set = set(tc.head(2).index)
        no_top2 = qual[(~qual['home_team'].isin(top2_set)) & (~qual['away_team'].isin(top2_set))] if 'home_team' in qual.columns else qual
        if len(no_top2) >= 10:
            hr_no2 = no_top2['over_hit'].mean() if direction == 'OVER' else no_top2['under_hit'].mean()
            print(f"    After removing top 2: N={len(no_top2)}, {direction}={hr_no2:.3f} (was {hit_rate:.3f})")
    else:
        print(f"    Team data not available for concentration check")

    # ── TEST 6: FRAMING ──
    print(f"\n  TEST 6 — PRACTICAL FRAMING")
    if hit_rate > 0.55 and len(qual) >= 100 and resid_mkt > 0.03:
        framing = 'A) STANDALONE SIGNAL'
    elif hit_rate > 0.55 and len(qual) >= 50 and resid_mkt > 0.01:
        framing = 'B) OVERLAY ON EDGE SIGNAL'
    elif hit_rate > 0.52 and season_consistent >= 3:
        framing = 'C) CONTEXT BADGE'
    else:
        framing = 'D) NOT USABLE'
    print(f"    Recommended: {framing}")

    # Verdict
    if hit_rate > 0.55 and len(qual) >= 100 and resid_mkt > 0.03 and season_consistent >= 3:
        verdict = 'DEPLOY_TO_SHADOW'
    elif hit_rate > 0.52 and resid_mkt > 0.01 and season_consistent >= 3:
        verdict = 'CONTEXT_BADGE'
    else:
        verdict = 'ARCHIVE'

    print(f"\n  VERDICT: {verdict}")
    return {
        'name': branch_name, 'verdict': verdict, 'direction': direction,
        'hit_rate': hit_rate, 'n': len(qual), 'resid_mkt': resid_mkt, 'roi': roi,
        'seasons': season_consistent, 'framing': framing,
        'cell': f"{best['side']}: off={best['oc']} def={best['dc']}",
    }


# ═══════════════════════════════════════════════════════════════
# RUN BOTH BRANCHES
# ═══════════════════════════════════════════════════════════════

r8 = run_branch_validation(
    "Branch 8: Process Dominance",
    ['xgf_r20', 'danger_ratio'],
    ['xga_r20', 'danger_ratio'],
)

r7 = run_branch_validation(
    "Branch 7: Special Teams Net",
    ['pp_pk_net', 'pp_opp_r20'],
    ['pp_pk_net', 'pen_r20'],
)

# ═══════════════════════════════════════════════════════════════
# OVERLAP CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("OVERLAP CHECK")
print(SEP)

# Rebuild both sets of qualifying game_ids
def get_qual_ids(off_features, def_features):
    off_v = tg.dropna(subset=off_features).copy()
    def_v = tg.dropna(subset=def_features).copy()
    sc_o = StandardScaler(); sc_d = StandardScaler()
    km_o = KMeans(n_clusters=2, random_state=42, n_init=10)
    km_d = KMeans(n_clusters=2, random_state=42, n_init=10)
    off_v['oc'] = km_o.fit_predict(sc_o.fit_transform(off_v[off_features]))
    def_v['dc'] = km_d.fit_predict(sc_d.fit_transform(def_v[def_features]))

    ho = off_v[off_v['is_home']][['game_id', 'oc']].rename(columns={'oc': 'ho'})
    ad = def_v[~def_v['is_home']][['game_id', 'dc']].rename(columns={'dc': 'ad'})
    ao = off_v[~off_v['is_home']][['game_id', 'oc']].rename(columns={'oc': 'ao'})
    hd = def_v[def_v['is_home']][['game_id', 'dc']].rename(columns={'dc': 'hd'})
    hbk = tg[tg['is_home']][['game_id', 'backup', 'opp_backup']].rename(
        columns={'backup': 'h_bk', 'opp_backup': 'a_bk'}).drop_duplicates('game_id')

    gl = ft[['game_id', 'closing_total', 'total_goals']].copy()
    gl = gl.merge(ho, on='game_id', how='left').merge(ad, on='game_id', how='left')
    gl = gl.merge(ao, on='game_id', how='left').merge(hd, on='game_id', how='left')
    gl = gl.merge(hbk, on='game_id', how='left')
    gl = gl.dropna(subset=['closing_total', 'ho', 'ad'])
    gl['both_starters'] = (gl['h_bk'] == 0) & (gl['a_bk'] == 0)
    gl['residual'] = gl['total_goals'] - gl['closing_total']

    # Find best starter cell
    best_ids = set()
    for sl, oc, dc in [('HO_AD', 'ho', 'ad'), ('AO_HD', 'ao', 'hd')]:
        v = gl.dropna(subset=[oc, dc])
        for o in range(2):
            for d in range(2):
                s = v[(v[oc] == o) & (v[dc] == d) & v['both_starters']]
                if len(s) >= 20:
                    r = s['residual'].mean()
                    if abs(r) >= 0.2:
                        best_ids.update(s['game_id'].tolist())
    return best_ids

ids_8 = get_qual_ids(['xgf_r20', 'danger_ratio'], ['xga_r20', 'danger_ratio'])
ids_7 = get_qual_ids(['pp_pk_net', 'pp_opp_r20'], ['pp_pk_net', 'pen_r20'])

overlap = len(ids_8 & ids_7)
union = len(ids_8 | ids_7)
print(f"Branch 8 qualifying games: {len(ids_8)}")
print(f"Branch 7 qualifying games: {len(ids_7)}")
print(f"Overlap: {overlap} ({overlap/min(len(ids_8), len(ids_7))*100:.0f}% of smaller set)")
print(f"Union: {union}")
print(f"Additive? {'YES — low overlap' if overlap < 0.3 * min(len(ids_8), len(ids_7)) else 'PARTIAL — some overlap'}")

# Summary
print(f"\n{SEP}")
print("FINAL SUMMARY")
print(SEP)
for r in [r8, r7]:
    print(f"\n  {r['name']}:")
    print(f"    Direction: {r.get('direction','?')}")
    print(f"    Hit rate: {r.get('hit_rate',0):.3f} (N={r.get('n',0)})")
    print(f"    Market residual: {r.get('resid_mkt',0):+.3f}")
    print(f"    ROI: {r.get('roi',0):+.1f}%")
    print(f"    Seasons consistent: {r.get('seasons',0)}/4")
    print(f"    Framing: {r.get('framing','?')}")
    print(f"    VERDICT: {r['verdict']}")
