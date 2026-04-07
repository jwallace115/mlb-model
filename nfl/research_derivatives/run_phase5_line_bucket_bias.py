#!/usr/bin/env python3
"""Phase 5: Receptions Props Line-Bucket Structural Bias Test."""
import os, sys
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

import nflreadpy

SEP = "=" * 70

# ═══════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════
print("Loading data...")

# Props archive (all seasons)
dfs = []
for root, dirs, files in os.walk('data/odds_archive/nfl/props'):
    for f in files:
        if f.endswith('.parquet'):
            dfs.append(pd.read_parquet(os.path.join(root, f)))
props_all = pd.concat(dfs, ignore_index=True)
rec = props_all[props_all['market_key'] == 'player_receptions'].copy()

# Player stats (actuals) — 3 seasons
ps_list = []
for yr in [2023, 2024, 2025]:
    try:
        ps_yr = nflreadpy.load_player_stats([yr]).to_pandas()
        ps_yr['stat_season'] = yr
        ps_list.append(ps_yr)
    except Exception as e:
        print(f"  Warning: could not load {yr} stats: {e}")
ps = pd.concat(ps_list, ignore_index=True)

# Schedule (for game_id mapping)
sched_list = []
for yr in [2023, 2024, 2025]:
    try:
        s = nflreadpy.load_schedules([yr]).to_pandas()
        sched_list.append(s)
    except Exception:
        pass
sched = pd.concat(sched_list, ignore_index=True)

print(f"Props (receptions): {len(rec):,} rows")
print(f"Player stats: {len(ps):,} rows")
print(f"Schedule: {len(sched)} games")

# ═══════════════════════════════════════════════════════════════
# STEP 1 — BUILD CLEAN DATASET
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 1 — BUILD DATASET")
print(SEP)

# Closing line per player-game: latest snapshot per bookmaker, then median across books
rec_close = rec.sort_values('last_update').groupby(
    ['event_id', 'player_name', 'bookmaker']).tail(1)
rec_med = rec_close.groupby(['event_id', 'player_name']).agg(
    close_line=('line', 'median'),
    close_over_price=('over_price', 'median'),
    close_under_price=('under_price', 'median'),
    n_books=('bookmaker', 'nunique'),
).reset_index()

# NFL season from game_date
rec_med_with_date = rec_close[['event_id', 'game_date']].drop_duplicates('event_id')
rec_med = rec_med.merge(rec_med_with_date, on='event_id', how='left')
rec_med['nfl_season'] = rec_med['game_date'].str[:4].astype(int)
rec_med.loc[rec_med['game_date'].str[5:7].astype(int) <= 2, 'nfl_season'] -= 1

# Match to actuals via player_name + approximate week
# Build week from game_date
sched['game_date_str'] = pd.to_datetime(sched['gameday']).dt.strftime('%Y-%m-%d')
# Map event_id -> game_date -> week via schedule
sched_map = sched[['game_id', 'game_date_str', 'week', 'season', 'home_team', 'away_team']].drop_duplicates('game_id')

# For events, get home/away from props
event_teams = rec_close[['event_id', 'home_team', 'away_team', 'game_date']].drop_duplicates('event_id')
rec_med = rec_med.merge(event_teams[['event_id', 'home_team', 'away_team']], on='event_id', how='left')

# Match to schedule via home_team + game_date (with +/- 1 day tolerance)
sched_lookup = {}
for _, r in sched_map.iterrows():
    for delta in [0, -1, 1]:
        d = (pd.Timestamp(r['game_date_str']) + pd.Timedelta(days=delta)).strftime('%Y-%m-%d')
        sched_lookup[(r['home_team'], d)] = (r['game_id'], r['week'], r['season'])

# Normalize Odds API team names to nflverse abbreviations
TEAM_MAP = {
    'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL',
    'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
    'Los Angeles Rams': 'LA', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
    'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS',
    'Washington Football Team': 'WAS',
}

rec_med['home_abbr'] = rec_med['home_team'].map(TEAM_MAP)
rec_med['game_info'] = rec_med.apply(
    lambda r: sched_lookup.get((r['home_abbr'], r['game_date'])), axis=1)
rec_med['game_id'] = rec_med['game_info'].apply(lambda x: x[0] if x else None)
rec_med['week'] = rec_med['game_info'].apply(lambda x: x[1] if x else None)

# Join actuals
actuals = ps[['player_display_name', 'week', 'stat_season', 'receptions', 'position', 'team']].copy()
actuals = actuals.rename(columns={'player_display_name': 'player_name', 'stat_season': 'nfl_season'})

matched = rec_med.merge(actuals, on=['player_name', 'week', 'nfl_season'], how='inner')
print(f"Matched player-game-weeks: {len(matched):,}")
print(f"Name match rate: {len(matched) / len(rec_med) * 100:.0f}%")

# Compute derived fields
def american_to_implied(odds):
    if pd.isna(odds) or odds is None:
        return np.nan
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)

matched['implied_over'] = matched['close_over_price'].apply(american_to_implied)
matched['over_hit'] = (matched['receptions'] > matched['close_line']).astype(int)
matched['under_hit'] = (matched['receptions'] < matched['close_line']).astype(int)

# Line buckets
matched['bucket'] = pd.cut(matched['close_line'], bins=[-0.1, 2.5, 4.5, 20],
                            labels=['LOW (0.5-2.5)', 'MID (3.0-4.5)', 'HIGH (5.0+)'])

# Role assignment: WR1/WR2/WR3/TE1/RB based on position
# For WRs, rank by target share within team-week
wr_mask = matched['position'] == 'WR'
te_mask = matched['position'] == 'TE'
rb_mask = matched['position'] == 'RB'
matched['role'] = 'OTHER'
matched.loc[te_mask, 'role'] = 'TE'
matched.loc[rb_mask, 'role'] = 'RB'

# WR ranking by line (proxy for team's WR hierarchy)
wr_data = matched[wr_mask].copy()
wr_data['wr_rank'] = wr_data.groupby(['game_id', 'team'])['close_line'].rank(ascending=False, method='first')
matched.loc[wr_data.index, 'role'] = wr_data['wr_rank'].map({1: 'WR1', 2: 'WR2', 3: 'WR3'}).fillna('WR4+')

print(f"\nBy season: {matched.groupby('nfl_season')['over_hit'].agg(['count', 'mean']).to_dict()}")
print(f"By bucket: {matched.groupby('bucket')['over_hit'].agg(['count', 'mean']).to_dict()}")
print(f"By role: {matched.groupby('role')['over_hit'].agg(['count', 'mean']).to_dict()}")

# ═══════════════════════════════════════════════════════════════
# STEP 2 — RAW HIT RATE BY BUCKET
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 2 — RAW HIT RATE BY BUCKET")
print(SEP)

print(f"\n{'Bucket':<20} {'N':>6} {'Line':>6} {'Over%':>7} {'Impl%':>7} {'Resid':>7}")
print("-" * 58)
for bucket in ['LOW (0.5-2.5)', 'MID (3.0-4.5)', 'HIGH (5.0+)']:
    sub = matched[matched['bucket'] == bucket]
    n = len(sub)
    line = sub['close_line'].mean()
    over = sub['over_hit'].mean()
    impl = sub['implied_over'].mean()
    resid = over - impl
    print(f"{bucket:<20} {n:>6} {line:>6.1f} {over:>7.3f} {impl:>7.3f} {resid:>+7.3f}")

# By season
print(f"\nBy season:")
for season in sorted(matched['nfl_season'].unique()):
    print(f"\n  {season}:")
    for bucket in ['LOW (0.5-2.5)', 'MID (3.0-4.5)', 'HIGH (5.0+)']:
        sub = matched[(matched['bucket'] == bucket) & (matched['nfl_season'] == season)]
        if len(sub) < 20:
            continue
        over = sub['over_hit'].mean()
        impl = sub['implied_over'].mean()
        resid = over - impl
        print(f"    {bucket:<20} N={len(sub):>5} over={over:.3f} impl={impl:.3f} resid={resid:+.3f}")

# ═══════════════════════════════════════════════════════════════
# STEP 3 — ROLE x BUCKET INTERACTION
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 3 — ROLE x BUCKET INTERACTION")
print(SEP)

print(f"\n{'Role':<8} {'Bucket':<20} {'N':>5} {'Over%':>7} {'Impl%':>7} {'Resid':>7} {'Flag'}")
print("-" * 62)
interaction_results = []
for role in ['WR1', 'WR2', 'WR3', 'TE', 'RB']:
    for bucket in ['LOW (0.5-2.5)', 'MID (3.0-4.5)', 'HIGH (5.0+)']:
        sub = matched[(matched['role'] == role) & (matched['bucket'] == bucket)]
        if len(sub) < 10:
            continue
        over = sub['over_hit'].mean()
        impl = sub['implied_over'].mean()
        resid = over - impl
        flag = 'THIN' if len(sub) < 30 else ('STRONG' if resid > 0.03 else '')
        interaction_results.append({'role': role, 'bucket': bucket, 'n': len(sub),
                                     'over': over, 'impl': impl, 'resid': resid, 'flag': flag})
        print(f"{role:<8} {bucket:<20} {len(sub):>5} {over:>7.3f} {impl:>7.3f} {resid:>+7.3f}  {flag}")

# ═══════════════════════════════════════════════════════════════
# STEP 4 — MARKET CALIBRATION (2025 multi-snapshot)
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 4 — MARKET CALIBRATION")
print(SEP)

# Check book-level consistency for strongest cell
strong = [r for r in interaction_results if r['resid'] > 0.02 and r['n'] >= 30]
if strong:
    best = max(strong, key=lambda x: x['resid'])
    print(f"\nBest cell: {best['role']} / {best['bucket']} (resid={best['resid']:+.3f})")

    # Book-level check
    best_sub = matched[(matched['role'] == best['role']) & (matched['bucket'] == best['bucket'])]
    # Get per-book closing lines for these player-games
    best_events = set(zip(best_sub['event_id'], best_sub['player_name']))
    book_data = rec_close[rec_close.apply(lambda r: (r['event_id'], r['player_name']) in best_events, axis=1)]
    book_summary = book_data.groupby('bookmaker').agg(
        n_lines=('line', 'count'),
        mean_over_price=('over_price', 'mean'),
    )
    print(f"  By bookmaker:")
    for bk, row in book_summary.iterrows():
        print(f"    {bk}: {int(row['n_lines'])} lines, avg_over_price={row['mean_over_price']:.0f}")

# ═══════════════════════════════════════════════════════════════
# STEP 5 — CONTROL CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 5 — CONTROL CHECK")
print(SEP)

# Get full-game totals from game_markets archive
gm_dfs = []
for root, dirs, files in os.walk('data/odds_archive/nfl/game_markets'):
    for f in files:
        if f.endswith('.parquet'):
            gm_dfs.append(pd.read_parquet(os.path.join(root, f)))
if gm_dfs:
    gm = pd.concat(gm_dfs, ignore_index=True)
    fg = gm[gm['market_key'] == 'totals'].groupby('event_id')['line'].median().reset_index()
    fg.columns = ['event_id', 'fg_total']
    sp = gm[gm['market_key'] == 'spreads'].groupby('event_id')['line'].median().reset_index()
    sp.columns = ['event_id', 'spread']
    matched = matched.merge(fg, on='event_id', how='left')
    matched = matched.merge(sp, on='event_id', how='left')

# For strongest cells, logistic regression with controls
for cell in strong[:3] if strong else []:
    sub = matched[(matched['role'] == cell['role']) & (matched['bucket'] == cell['bucket'])]
    all_d = matched[matched['bucket'] == cell['bucket']].copy()
    all_d['in_cell'] = ((all_d['role'] == cell['role'])).astype(int)

    ctrl_cols = ['close_line', 'implied_over']
    ctrl_valid = all_d.dropna(subset=ctrl_cols + ['fg_total'])
    if len(ctrl_valid) < 50:
        ctrl_valid = all_d.dropna(subset=ctrl_cols)

    if len(ctrl_valid) > 50:
        X = ctrl_valid[['close_line', 'implied_over', 'in_cell']]
        y = ctrl_valid['over_hit']
        lr = LogisticRegression(max_iter=1000)
        lr.fit(X, y)
        coefs = dict(zip(X.columns, lr.coef_[0]))
        print(f"\n  {cell['role']} / {cell['bucket']}:")
        print(f"    in_cell coef: {coefs['in_cell']:+.4f}")
        print(f"    Survives: {'YES' if coefs['in_cell'] > 0 else 'NO'}")

# ═══════════════════════════════════════════════════════════════
# STEP 6 — CONCENTRATION CHECK
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 6 — CONCENTRATION CHECK")
print(SEP)

for cell in strong[:2] if strong else []:
    sub = matched[(matched['role'] == cell['role']) & (matched['bucket'] == cell['bucket'])]
    player_conc = sub['player_name'].value_counts().head(10)
    team_conc = sub['team'].value_counts().head(5)
    print(f"\n  {cell['role']} / {cell['bucket']} (N={cell['n']}):")
    print(f"  Top 10 players:")
    for p, n in player_conc.items():
        over = sub[sub['player_name'] == p]['over_hit'].mean()
        print(f"    {p}: {n} games, over={over:.2f}")
    print(f"  Top 5 teams: {dict(team_conc)}")
    print(f"  Top 3 players share: {player_conc.head(3).sum()}/{cell['n']} = {player_conc.head(3).sum()/cell['n']*100:.0f}%")

    # Remove top 3 and recheck
    top3_players = set(player_conc.head(3).index)
    sub_no_top3 = sub[~sub['player_name'].isin(top3_players)]
    if len(sub_no_top3) > 15:
        print(f"  After removing top 3: N={len(sub_no_top3)}, over={sub_no_top3['over_hit'].mean():.3f} "
              f"(was {sub['over_hit'].mean():.3f})")

# ═══════════════════════════════════════════════════════════════
# STEP 7 — SEASON-SPLIT STABILITY
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("STEP 7 — SEASON-SPLIT STABILITY")
print(SEP)

for cell in strong[:3] if strong else []:
    print(f"\n  {cell['role']} / {cell['bucket']}:")
    for season in sorted(matched['nfl_season'].unique()):
        sub = matched[(matched['role'] == cell['role']) & (matched['bucket'] == cell['bucket'])
                      & (matched['nfl_season'] == season)]
        if len(sub) < 10:
            print(f"    {season}: N={len(sub)} — THIN")
            continue
        over = sub['over_hit'].mean()
        impl = sub['implied_over'].mean()
        resid = over - impl
        print(f"    {season}: N={len(sub)}, over={over:.3f}, impl={impl:.3f}, resid={resid:+.3f}")

# ═══════════════════════════════════════════════════════════════
# DECISION
# ═══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("DECISION SUMMARY")
print(SEP)

strong_final = [r for r in interaction_results if r['resid'] > 0.03 and r['n'] >= 50]
near = [r for r in interaction_results if 0.02 < r['resid'] <= 0.03 and r['n'] >= 30]
print(f"\nStrong (resid > 3pp, N >= 50): {len(strong_final)}")
for r in strong_final:
    print(f"  {r['role']}/{r['bucket']}: resid={r['resid']:+.3f} N={r['n']}")
print(f"Near miss (resid 2-3pp, N >= 30): {len(near)}")
for r in near:
    print(f"  {r['role']}/{r['bucket']}: resid={r['resid']:+.3f} N={r['n']}")
