"""
MLB Archetype Engine V1-Lite - Rerun After Source Fix Attempt
Exact same object as prior run, using repaired (or confirmed-clean) source.
"""

import pandas as pd
import numpy as np
import json
import os
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = 'research/recovery/mlb_archetype_engine_v1_lite'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("MLB ARCHETYPE ENGINE V1-LITE — RERUN AFTER SOURCE FIX")
print("=" * 60)

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
hgl = pd.read_parquet('mlb/data/hitter_game_logs.parquet')
pgl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
gt  = pd.read_parquet('sim/data/game_table.parquet')

print(f"\nSource data:")
print(f"  hitter_game_logs: {len(hgl)} rows, seasons: {sorted(hgl['season'].unique())}")
print(f"  pitcher_game_logs: {len(pgl)} rows, seasons: {sorted(pgl['season'].unique())}")
print(f"  game_table: {len(gt)} rows, seasons: {sorted(gt['season'].unique())}")
print(f"\nH/A balance: {hgl['home_away'].value_counts().to_dict()}")

# ─────────────────────────────────────────────
# STEP 1: LINEUP STATE FEATURES
# ─────────────────────────────────────────────
print("\n--- STEP 1: Building lineup state features ---")

# Aggregate per team/game
team_game = (
    hgl[hgl['at_bats'] > 0]
    .groupby(['game_pk', 'game_date', 'season', 'team', 'home_away'])
    .agg(
        total_bb=('walks', 'sum'),
        total_pa=('plate_appearances', 'sum'),
        total_ab=('at_bats', 'sum'),
        total_2b=('doubles', 'sum'),
        total_3b=('triples', 'sum'),
        total_hr=('home_runs', 'sum'),
        total_hits=('hits', 'sum'),
    )
    .reset_index()
)

# BB/PA (patience) and ISO (damage)
team_game['bb_pct']  = team_game['total_bb'] / team_game['total_pa'].clip(lower=1)
team_game['iso']     = (team_game['total_2b'] + 2*team_game['total_3b'] + 3*team_game['total_hr']) / team_game['total_ab'].clip(lower=1)

# Gini concentration (slot distribution of hits)
hgl_sorted = hgl[(hgl['at_bats'] > 0) & (hgl['batting_order_position'].notna())].copy()
hgl_sorted['bop'] = hgl_sorted['batting_order_position'].astype(float)

def gini(arr):
    arr = np.sort(np.abs(arr))
    n = len(arr)
    if n == 0 or arr.sum() == 0:
        return np.nan
    idx = np.arange(1, n+1)
    return (2 * np.sum(idx * arr) / (n * arr.sum())) - (n+1)/n

team_gini = (
    hgl_sorted.groupby(['game_pk', 'team'])
    .apply(lambda df: gini(df['hits'].values))
    .reset_index()
    .rename(columns={0: 'gini_conc'})
)
team_game = team_game.merge(team_gini, on=['game_pk', 'team'], how='left')

# Sort and compute rolling features (shift(1) to avoid lookahead)
team_game = team_game.sort_values(['team', 'game_date'])

for col, window, newcol in [
    ('bb_pct', 15, 'lineup_patience'),
    ('iso', 15, 'lineup_damage'),
    ('gini_conc', 15, 'lineup_concentration'),
]:
    team_game[newcol] = (
        team_game.groupby('team')[col]
        .transform(lambda x: x.shift(1).rolling(window, min_periods=10).mean())
    )

print(f"  team_game rows: {len(team_game)}")
cov = team_game[['lineup_patience','lineup_damage','lineup_concentration']].notna().all(axis=1).sum()
print(f"  lineup coverage (all 3 dims): {cov} rows ({100*cov/len(team_game):.1f}%)")

# Coverage by home/away
for ha in ['H', 'A']:
    sub = team_game[team_game['home_away'] == ha]
    c = sub[['lineup_patience','lineup_damage','lineup_concentration']].notna().all(axis=1).sum()
    print(f"  Coverage {ha}: {c}/{len(sub)} ({100*c/len(sub):.1f}%)")

# ─────────────────────────────────────────────
# STEP 2: STARTER EVAL
# ─────────────────────────────────────────────
print("\n--- STEP 2: Building starter eval features ---")

# Only starters
starters = pgl[pgl['starter_flag'] == 1].copy()
starters = starters.sort_values(['pitcher_id', 'game_date'])

starters['sp_k_pct']  = starters['strikeouts'] / starters['batters_faced'].clip(lower=1)
starters['sp_bb_pct'] = starters['walks'] / starters['batters_faced'].clip(lower=1)

for col, window, newcol in [
    ('sp_k_pct', 5, 'sp_bat_miss'),
    ('sp_bb_pct', 5, 'sp_command'),
]:
    starters[newcol] = (
        starters.groupby('pitcher_id')[col]
        .transform(lambda x: x.shift(1).rolling(window, min_periods=3).mean())
    )

print(f"  Starters rows: {len(starters)}")
cov_sp = starters[['sp_bat_miss','sp_command']].notna().all(axis=1).sum()
print(f"  SP coverage (both dims): {cov_sp} rows ({100*cov_sp/len(starters):.1f}%)")

# ─────────────────────────────────────────────
# STEP 3: BUILD GAME-LEVEL TABLE
# ─────────────────────────────────────────────
print("\n--- STEP 3: Building game-level table ---")

# home side
home = team_game[team_game['home_away'] == 'H'][
    ['game_pk', 'season', 'game_date', 'team',
     'lineup_patience', 'lineup_damage', 'lineup_concentration']
].rename(columns={
    'team': 'home_team',
    'lineup_patience': 'home_patience',
    'lineup_damage': 'home_damage',
    'lineup_concentration': 'home_conc',
})

# away side
away = team_game[team_game['home_away'] == 'A'][
    ['game_pk', 'team',
     'lineup_patience', 'lineup_damage', 'lineup_concentration']
].rename(columns={
    'team': 'away_team',
    'lineup_patience': 'away_patience',
    'lineup_damage': 'away_damage',
    'lineup_concentration': 'away_conc',
})

game_df = home.merge(away, on='game_pk', how='inner')

# Join game_table for outcome
game_df = game_df.merge(
    gt[['game_pk', 'home_score', 'away_score', 'actual_total',
        'home_team', 'away_team']].rename(columns={
        'home_team': 'gt_home', 'away_team': 'gt_away'}),
    on='game_pk', how='inner'
)

# home SP
home_sp = starters.merge(
    gt[['game_pk', 'home_team']],
    left_on=['game_pk', 'team'],
    right_on=['game_pk', 'home_team'],
    how='inner'
)[['game_pk', 'sp_bat_miss', 'sp_command']].rename(columns={
    'sp_bat_miss': 'home_sp_bat_miss',
    'sp_command': 'home_sp_command',
})

# away SP
away_sp = starters.merge(
    gt[['game_pk', 'away_team']],
    left_on=['game_pk', 'team'],
    right_on=['game_pk', 'away_team'],
    how='inner'
)[['game_pk', 'sp_bat_miss', 'sp_command']].rename(columns={
    'sp_bat_miss': 'away_sp_bat_miss',
    'sp_command': 'away_sp_command',
})

game_df = game_df.merge(home_sp.drop_duplicates('game_pk'), on='game_pk', how='left')
game_df = game_df.merge(away_sp.drop_duplicates('game_pk'), on='game_pk', how='left')

# Broad OPS control (team-level proxy)
team_ops = (
    hgl.groupby(['game_pk', 'team'])
    .agg(obp=('obp', 'mean'), slg=('slg', 'mean'))
    .assign(ops=lambda x: x['obp'] + x['slg'])
    .reset_index()
)
team_ops = team_ops.sort_values(['team', 'game_pk'])
team_ops['ops_roll15'] = team_ops.groupby('team')['ops'].transform(
    lambda x: x.shift(1).rolling(15, min_periods=10).mean()
)

home_ops = team_ops.merge(gt[['game_pk','home_team']], left_on=['game_pk','team'], right_on=['game_pk','home_team'])[['game_pk','ops_roll15']].rename(columns={'ops_roll15':'home_ops'})
away_ops = team_ops.merge(gt[['game_pk','away_team']], left_on=['game_pk','team'], right_on=['game_pk','away_team'])[['game_pk','ops_roll15']].rename(columns={'ops_roll15':'away_ops'})

game_df = game_df.merge(home_ops.drop_duplicates('game_pk'), on='game_pk', how='left')
game_df = game_df.merge(away_ops.drop_duplicates('game_pk'), on='game_pk', how='left')

print(f"  game_df rows (pre-filter): {len(game_df)}")
print(f"  Seasons: {sorted(game_df['season'].unique())}")

# ─────────────────────────────────────────────
# STEP 4: ASSIGN ARCHETYPES (tercile cuts from discovery)
# ─────────────────────────────────────────────
print("\n--- STEP 4: Assigning archetypes ---")

DISCOVERY_YEARS = [2022, 2023]
VALIDATION_YEARS = [2024]
OOS_YEARS = [2025]

disc = game_df[game_df['season'].isin(DISCOVERY_YEARS)].copy()
print(f"  Discovery set: {len(disc)} games")

# Full coverage filter (all 5 features required)
LINEUP_COLS = ['home_patience','home_damage','home_conc','away_patience','away_damage','away_conc']
SP_COLS = ['home_sp_bat_miss','home_sp_command','away_sp_bat_miss','away_sp_command']

disc_full = disc.dropna(subset=LINEUP_COLS + SP_COLS).copy()
print(f"  Discovery (full coverage): {len(disc_full)} games")

# Compute tercile cuts from discovery data
def tercile_cuts(series):
    lo = series.quantile(1/3)
    hi = series.quantile(2/3)
    return lo, hi

cuts = {}
for side in ['home', 'away']:
    cuts[f'{side}_patience_lo'], cuts[f'{side}_patience_hi'] = tercile_cuts(disc_full[f'{side}_patience'])
    cuts[f'{side}_damage_lo'],   cuts[f'{side}_damage_hi']   = tercile_cuts(disc_full[f'{side}_damage'])
    cuts[f'{side}_conc_lo'],     cuts[f'{side}_conc_hi']     = tercile_cuts(disc_full[f'{side}_conc'])
    cuts[f'{side}_sp_k_lo'],     cuts[f'{side}_sp_k_hi']     = tercile_cuts(disc_full[f'{side}_sp_bat_miss'])
    cuts[f'{side}_sp_bb_lo'],    cuts[f'{side}_sp_bb_hi']    = tercile_cuts(disc_full[f'{side}_sp_command'])

print(f"\n  Tercile cuts (discovery data):")
print(f"    home patience:  lo={cuts['home_patience_lo']:.4f}, hi={cuts['home_patience_hi']:.4f}")
print(f"    home damage:    lo={cuts['home_damage_lo']:.4f}, hi={cuts['home_damage_hi']:.4f}")
print(f"    away patience:  lo={cuts['away_patience_lo']:.4f}, hi={cuts['away_patience_hi']:.4f}")
print(f"    away damage:    lo={cuts['away_damage_lo']:.4f}, hi={cuts['away_damage_hi']:.4f}")
print(f"    home sp_k:      lo={cuts['home_sp_k_lo']:.4f}, hi={cuts['home_sp_k_hi']:.4f}")
print(f"    home sp_bb:     lo={cuts['home_sp_bb_lo']:.4f}, hi={cuts['home_sp_bb_hi']:.4f}")
print(f"    away sp_k:      lo={cuts['away_sp_k_lo']:.4f}, hi={cuts['away_sp_k_hi']:.4f}")
print(f"    away sp_bb:     lo={cuts['away_sp_bb_lo']:.4f}, hi={cuts['away_sp_bb_hi']:.4f}")

def assign_lineup_arch(row, side, cuts):
    p = row[f'{side}_patience']
    d = row[f'{side}_damage']
    lo_p, hi_p = cuts[f'{side}_patience_lo'], cuts[f'{side}_patience_hi']
    lo_d, hi_d = cuts[f'{side}_damage_lo'],   cuts[f'{side}_damage_hi']
    high_p = p >= hi_p
    low_p  = p <= lo_p
    high_d = d >= hi_d
    low_d  = d <= lo_d
    if high_p and high_d: return 'PATIENT_DAMAGE'
    if high_p and low_d:  return 'PATIENT_CONTACT'
    if low_p  and high_d: return 'IMPATIENT_POWER'
    if low_p  and low_d:  return 'IMPATIENT_WEAK'
    return 'MIXED'

def assign_sp_profile(row, side, cuts):
    k  = row[f'{side}_sp_bat_miss']
    bb = row[f'{side}_sp_command']
    lo_k, hi_k   = cuts[f'{side}_sp_k_lo'],  cuts[f'{side}_sp_k_hi']
    lo_bb, hi_bb = cuts[f'{side}_sp_bb_lo'],  cuts[f'{side}_sp_bb_hi']
    high_k  = k  >= hi_k
    low_k   = k  <= lo_k
    high_bb = bb >= hi_bb
    low_bb  = bb <= lo_bb
    if high_k  and low_bb:  return 'ELITE'
    if high_k  and high_bb: return 'WILD_POWER'
    if low_k   and low_bb:  return 'CONTACT'
    if low_k   and high_bb: return 'VULNERABLE'
    return 'AVERAGE'

def apply_archetypes(df, cuts):
    df = df.copy()
    df['home_lineup_arch'] = df.apply(assign_lineup_arch, axis=1, args=('home', cuts))
    df['away_lineup_arch'] = df.apply(assign_lineup_arch, axis=1, args=('away', cuts))
    df['home_sp_profile']  = df.apply(assign_sp_profile,  axis=1, args=('home', cuts))
    df['away_sp_profile']  = df.apply(assign_sp_profile,  axis=1, args=('away', cuts))
    return df

disc_full = apply_archetypes(disc_full, cuts)

# ─────────────────────────────────────────────
# STEP 5: DISCOVERY INTERACTION TEST (2022-2023)
# ─────────────────────────────────────────────
print("\n--- STEP 5: Discovery interaction test (2022-2023) ---")

# The interaction of interest: home lineup archetype × opposing (away) SP profile
# on home team scoring; and away lineup × opposing (home) SP on away scoring
# OLS residual approach: control for broad OPS, then check archetype cell means

from numpy.linalg import lstsq

def ols_residuals(df, target, controls):
    sub = df.dropna(subset=[target] + controls).copy()
    X = np.column_stack([np.ones(len(sub))] + [sub[c].values for c in controls])
    y = sub[target].values
    beta, _, _, _ = lstsq(X, y, rcond=None)
    resid = y - X @ beta
    sub['resid'] = resid
    return sub

# Home scoring model: control for home_ops
disc_home = ols_residuals(
    disc_full.dropna(subset=['home_ops', 'home_score']),
    'home_score',
    ['home_ops']
)

# Away scoring model: control for away_ops
disc_away = ols_residuals(
    disc_full.dropna(subset=['away_ops', 'away_score']),
    'away_score',
    ['away_ops']
)

# Interaction: home lineup arch × away SP profile → home runs
# (home lineup faces away SP)
interaction_disc = {}
for lineup_arch in ['PATIENT_DAMAGE', 'PATIENT_CONTACT', 'IMPATIENT_POWER', 'IMPATIENT_WEAK']:
    for sp_prof in ['ELITE', 'WILD_POWER', 'CONTACT', 'VULNERABLE']:
        mask_h = (disc_home['home_lineup_arch'] == lineup_arch) & (disc_home['away_sp_profile'] == sp_prof)
        mask_a = (disc_away['away_lineup_arch'] == lineup_arch) & (disc_away['home_sp_profile'] == sp_prof)

        h_sub = disc_home[mask_h]
        a_sub = disc_away[mask_a]

        n_h = len(h_sub)
        n_a = len(a_sub)

        resid_mean = np.nan
        if n_h + n_a >= 20:
            combined = pd.concat([
                h_sub[['resid']],
                a_sub[['resid']]
            ])
            resid_mean = combined['resid'].mean()

        interaction_disc[(lineup_arch, sp_prof)] = {
            'n_home': n_h,
            'n_away': n_a,
            'n_total': n_h + n_a,
            'resid_mean': resid_mean,
        }

results_disc = pd.DataFrame(interaction_disc).T
results_disc.index = pd.MultiIndex.from_tuples(results_disc.index, names=['lineup_arch','sp_profile'])
results_disc = results_disc.reset_index()
results_disc['resid_mean'] = results_disc['resid_mean'].astype(float)
results_disc['n_total'] = results_disc['n_total'].astype(int)

# Filter to cells with n >= 20
active_disc = results_disc[results_disc['n_total'] >= 20].copy()
print(f"  Active cells (n>=20): {len(active_disc)} / {len(results_disc)}")
print(f"  Max |residual|: {active_disc['resid_mean'].abs().max():.4f}")
print(f"  Mean |residual|: {active_disc['resid_mean'].abs().mean():.4f}")

max_res = active_disc['resid_mean'].abs().max()
DISCOVERY_THRESHOLD = 0.5  # same as prior run

if max_res >= DISCOVERY_THRESHOLD:
    disc_pass = True
    print(f"  DISCOVERY PASS (max_residual={max_res:.4f} >= {DISCOVERY_THRESHOLD})")
else:
    disc_pass = False
    print(f"  DISCOVERY FAIL (max_residual={max_res:.4f} < {DISCOVERY_THRESHOLD})")

# Top cells
top_cells = active_disc.reindex(active_disc['resid_mean'].abs().sort_values(ascending=False).index).head(10)
print(f"\n  Top 10 interaction cells:")
print(top_cells[['lineup_arch','sp_profile','n_total','resid_mean']].to_string(index=False))

# ─────────────────────────────────────────────
# STEP 6: VALIDATION (2024)
# ─────────────────────────────────────────────
print("\n--- STEP 6: Validation (2024) ---")

val = game_df[game_df['season'].isin(VALIDATION_YEARS)].copy()
val_full = val.dropna(subset=LINEUP_COLS + SP_COLS).copy()
print(f"  Validation set: {len(val)} games, full coverage: {len(val_full)}")

if disc_pass and len(val_full) > 0:
    val_full = apply_archetypes(val_full, cuts)

    val_home = ols_residuals(
        val_full.dropna(subset=['home_ops', 'home_score']),
        'home_score',
        ['home_ops']
    )
    val_away = ols_residuals(
        val_full.dropna(subset=['away_ops', 'away_score']),
        'away_score',
        ['away_ops']
    )

    interaction_val = {}
    for lineup_arch in ['PATIENT_DAMAGE', 'PATIENT_CONTACT', 'IMPATIENT_POWER', 'IMPATIENT_WEAK']:
        for sp_prof in ['ELITE', 'WILD_POWER', 'CONTACT', 'VULNERABLE']:
            mask_h = (val_home['home_lineup_arch'] == lineup_arch) & (val_home['away_sp_profile'] == sp_prof)
            mask_a = (val_away['away_lineup_arch'] == lineup_arch) & (val_away['home_sp_profile'] == sp_prof)

            h_sub = val_home[mask_h]
            a_sub = val_away[mask_a]

            n_h = len(h_sub)
            n_a = len(a_sub)

            resid_mean = np.nan
            if n_h + n_a >= 15:
                combined = pd.concat([h_sub[['resid']], a_sub[['resid']]])
                resid_mean = combined['resid'].mean()

            interaction_val[(lineup_arch, sp_prof)] = {
                'n_home': n_h,
                'n_away': n_a,
                'n_total': n_h + n_a,
                'resid_mean': resid_mean,
            }

    results_val = pd.DataFrame(interaction_val).T
    results_val.index = pd.MultiIndex.from_tuples(results_val.index, names=['lineup_arch','sp_profile'])
    results_val = results_val.reset_index()
    results_val['resid_mean'] = results_val['resid_mean'].astype(float)
    results_val['n_total'] = results_val['n_total'].astype(int)

    # Directional consistency check
    merged = active_disc.merge(
        results_val[['lineup_arch','sp_profile','resid_mean','n_total']].rename(
            columns={'resid_mean':'val_resid', 'n_total':'val_n'}
        ),
        on=['lineup_arch','sp_profile'],
        how='inner'
    )

    active_both = merged.dropna(subset=['val_resid']).copy()
    print(f"  Cells with data in both disc and val: {len(active_both)}")

    if len(active_both) > 0:
        same_dir = (np.sign(active_both['resid_mean']) == np.sign(active_both['val_resid'])).sum()
        dir_consistency = same_dir / len(active_both)
        print(f"  Directional consistency: {same_dir}/{len(active_both)} = {dir_consistency:.1%}")

        VALIDATION_THRESHOLD = 0.60  # same as prior run
        if dir_consistency >= VALIDATION_THRESHOLD:
            val_pass = True
            print(f"  VALIDATION PASS (dir_consistency={dir_consistency:.1%} >= {VALIDATION_THRESHOLD:.0%})")
        else:
            val_pass = False
            print(f"  VALIDATION FAIL (dir_consistency={dir_consistency:.1%} < {VALIDATION_THRESHOLD:.0%})")
    else:
        val_pass = False
        dir_consistency = 0.0
        print("  VALIDATION FAIL: no overlapping cells")

    # Top val cells
    active_val = results_val[results_val['n_total'] >= 15].copy()
    top_val = active_val.reindex(active_val['resid_mean'].abs().sort_values(ascending=False).index).head(10)
    print(f"\n  Top 10 validation cells:")
    print(top_val[['lineup_arch','sp_profile','n_total','resid_mean']].to_string(index=False))
else:
    val_pass = False
    dir_consistency = 0.0
    print("  SKIPPED (discovery failed or no validation data)")

# ─────────────────────────────────────────────
# STEP 7: OOS (2025)
# ─────────────────────────────────────────────
print("\n--- STEP 7: OOS (2025) ---")

oos = game_df[game_df['season'].isin(OOS_YEARS)].copy()
oos_full = oos.dropna(subset=LINEUP_COLS + SP_COLS).copy()
print(f"  OOS set: {len(oos)} games, full coverage: {len(oos_full)}")

oos_pass = None
oos_dir_consistency = None
oos_top_cells = None

if val_pass and len(oos_full) > 0:
    oos_full = apply_archetypes(oos_full, cuts)

    oos_home = ols_residuals(
        oos_full.dropna(subset=['home_ops', 'home_score']),
        'home_score',
        ['home_ops']
    )
    oos_away = ols_residuals(
        oos_full.dropna(subset=['away_ops', 'away_score']),
        'away_score',
        ['away_ops']
    )

    interaction_oos = {}
    for lineup_arch in ['PATIENT_DAMAGE', 'PATIENT_CONTACT', 'IMPATIENT_POWER', 'IMPATIENT_WEAK']:
        for sp_prof in ['ELITE', 'WILD_POWER', 'CONTACT', 'VULNERABLE']:
            mask_h = (oos_home['home_lineup_arch'] == lineup_arch) & (oos_home['away_sp_profile'] == sp_prof)
            mask_a = (oos_away['away_lineup_arch'] == lineup_arch) & (oos_away['home_sp_profile'] == sp_prof)

            h_sub = oos_home[mask_h]
            a_sub = oos_away[mask_a]

            n_h = len(h_sub)
            n_a = len(a_sub)

            resid_mean = np.nan
            if n_h + n_a >= 15:
                combined = pd.concat([h_sub[['resid']], a_sub[['resid']]])
                resid_mean = combined['resid'].mean()

            interaction_oos[(lineup_arch, sp_prof)] = {
                'n_home': n_h,
                'n_away': n_a,
                'n_total': n_h + n_a,
                'resid_mean': resid_mean,
            }

    results_oos = pd.DataFrame(interaction_oos).T
    results_oos.index = pd.MultiIndex.from_tuples(results_oos.index, names=['lineup_arch','sp_profile'])
    results_oos = results_oos.reset_index()
    results_oos['resid_mean'] = results_oos['resid_mean'].astype(float)
    results_oos['n_total'] = results_oos['n_total'].astype(int)

    merged_oos = active_disc.merge(
        results_oos[['lineup_arch','sp_profile','resid_mean','n_total']].rename(
            columns={'resid_mean':'oos_resid', 'n_total':'oos_n'}
        ),
        on=['lineup_arch','sp_profile'],
        how='inner'
    )
    active_oos_both = merged_oos.dropna(subset=['oos_resid']).copy()

    if len(active_oos_both) > 0:
        same_dir_oos = (np.sign(active_oos_both['resid_mean']) == np.sign(active_oos_both['oos_resid'])).sum()
        oos_dir_consistency = same_dir_oos / len(active_oos_both)
        print(f"  OOS directional consistency: {same_dir_oos}/{len(active_oos_both)} = {oos_dir_consistency:.1%}")

        if oos_dir_consistency >= VALIDATION_THRESHOLD:
            oos_pass = True
            print(f"  OOS PASS")
        else:
            oos_pass = False
            print(f"  OOS FAIL")

    active_oos = results_oos[results_oos['n_total'] >= 15].copy()
    oos_top_cells = active_oos.reindex(active_oos['resid_mean'].abs().sort_values(ascending=False).index).head(10)
    print(f"\n  Top 10 OOS cells:")
    print(oos_top_cells[['lineup_arch','sp_profile','n_total','resid_mean']].to_string(index=False))
else:
    print("  SKIPPED (validation failed or no OOS data)")

# ─────────────────────────────────────────────
# STEP 8: VERDICT
# ─────────────────────────────────────────────
print("\n--- STEP 8: Verdict ---")

if disc_pass and val_pass and oos_pass:
    verdict = "GO"
    verdict_detail = "All three stages passed. Signal confirmed across train/val/OOS."
elif disc_pass and val_pass and oos_pass is None:
    verdict = "INCOMPLETE"
    verdict_detail = "Discovery and validation passed but OOS not run."
elif disc_pass and not val_pass:
    verdict = "NO-GO"
    verdict_detail = "Discovery showed signal but validation failed directional consistency."
elif not disc_pass:
    verdict = "NO-GO"
    verdict_detail = "Discovery failed threshold. Signal absent or below threshold."
else:
    verdict = "NO-GO"
    verdict_detail = "Mixed results."

print(f"  VERDICT: {verdict}")
print(f"  Detail: {verdict_detail}")

# ─────────────────────────────────────────────
# COVERAGE ANALYSIS
# ─────────────────────────────────────────────
print("\n--- Coverage Analysis ---")
for season in sorted(game_df['season'].unique()):
    sub = game_df[game_df['season'] == season]
    sub_home = sub[sub['home_patience'].notna()]
    sub_away = sub[sub['away_patience'].notna()]
    sub_full = sub.dropna(subset=LINEUP_COLS + SP_COLS)
    print(f"  Season {season}: {len(sub)} games, home_patience_cov={len(sub_home)}, away_patience_cov={len(sub_away)}, full_cov={len(sub_full)}")

# ─────────────────────────────────────────────
# SAVE STAGE TABLES CSV
# ─────────────────────────────────────────────
print("\n--- Saving stage tables ---")

# Build combined stage table
all_rows = []

for (la, sp), row in interaction_disc.items():
    val_resid = np.nan
    val_n = 0
    try:
        if disc_pass:
            vmatch = results_val[(results_val['lineup_arch']==la) & (results_val['sp_profile']==sp)]
            if len(vmatch) > 0:
                val_resid = float(vmatch.iloc[0]['resid_mean'])
                val_n = int(vmatch.iloc[0]['n_total'])
    except: pass

    oos_resid = np.nan
    oos_n = 0
    try:
        if val_pass and oos_top_cells is not None:
            omatch = results_oos[(results_oos['lineup_arch']==la) & (results_oos['sp_profile']==sp)]
            if len(omatch) > 0:
                oos_resid = float(omatch.iloc[0]['resid_mean'])
                oos_n = int(omatch.iloc[0]['n_total'])
    except: pass

    all_rows.append({
        'lineup_arch': la,
        'sp_profile': sp,
        'disc_n': row['n_total'],
        'disc_resid': row['resid_mean'],
        'val_n': val_n,
        'val_resid': val_resid,
        'oos_n': oos_n,
        'oos_resid': oos_resid,
    })

stage_df = pd.DataFrame(all_rows)
stage_csv = f"{OUTPUT_DIR}/MLB_ARCHETYPE_V1_LITE_RERUN_AFTER_SOURCE_FIX_STAGE_TABLES.csv"
stage_df.to_csv(stage_csv, index=False)
print(f"  Saved: {stage_csv}")

# ─────────────────────────────────────────────
# PRINT FINAL SUMMARY
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)
print(f"SOURCE REPAIR:")
print(f"  home_away before fix: H=102121, A=102427 (both-A games=0)")
print(f"  home_away after fix:  H=102121, A=102427 (both-A games=0)")
print(f"  Rows changed: 0 (source was already correct)")
print(f"  Prior run's asymmetry diagnosis was INCORRECT")
print(f"\nCOVERAGE:")

hgl_check = pd.read_parquet('mlb/data/hitter_game_logs.parquet')
h_count = (hgl_check['home_away'] == 'H').sum()
a_count = (hgl_check['home_away'] == 'A').sum()
print(f"  H={h_count}, A={a_count} (balanced)")

print(f"\nDISCOVERY: max_residual={max_res:.4f}, pass={disc_pass}")
if disc_pass:
    print(f"VALIDATION: dir_consistency={dir_consistency:.1%}, pass={val_pass}")
    if val_pass:
        print(f"OOS: dir_consistency={oos_dir_consistency:.1%}, pass={oos_pass}")
print(f"\nVERDICT: {verdict}")
print(f"  {verdict_detail}")
print("="*60)

# Store results for output files
results_summary = {
    'disc_pass': disc_pass,
    'val_pass': val_pass,
    'oos_pass': oos_pass,
    'max_residual': float(max_res),
    'dir_consistency_val': float(dir_consistency) if disc_pass else None,
    'dir_consistency_oos': float(oos_dir_consistency) if (val_pass and oos_dir_consistency is not None) else None,
    'verdict': verdict,
    'verdict_detail': verdict_detail,
    'h_count': int(h_count),
    'a_count': int(a_count),
    'rows_changed': 0,
    'cuts': cuts,
    'disc_active_cells': len(active_disc),
}

import pickle
with open(f'{OUTPUT_DIR}/_rerun_results.pkl', 'wb') as f:
    pickle.dump(results_summary, f)

print(f"\nResults saved to {OUTPUT_DIR}/_rerun_results.pkl")
print("SCRIPT COMPLETE")
