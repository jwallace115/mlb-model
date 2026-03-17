#!/usr/bin/env python3
"""
NBA Injury Calibration Audit — 2023-24 Regular Season

STEPs 3-6:
  3. Key player = current_status == "Out" AND MIN >= 15 MPG
  4. Calibration: bucket by total_key_out count, avg actual_total
  5. Load management separation
  6. Print results + verdict

Diagnostic only — no model changes.
"""

import os, warnings
os.environ['JAVA_HOME'] = '/Users/jw115/jre21/Contents/Home'
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

REPO_DIR     = Path(__file__).parent.parent.parent
INJURY_DIR   = REPO_DIR / 'nba' / 'data' / 'injury_reports'
GAMES_PATH   = REPO_DIR / 'nba' / 'data' / 'games.parquet'
PLAYER_PATH  = REPO_DIR / 'nba' / 'data' / 'player_stats_2324.parquet'

MIN_MPG = 15.0   # key player threshold

# Full team name → abbreviation (30 NBA teams)
TEAM_ABBREV = {
    'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
    'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
    'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
    'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
    'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
    'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
    'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
    'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
    'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
    'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS',
}


def _reverse_name(name) -> str:
    """'Last, First' → 'First Last'"""
    if not name or not isinstance(name, str):
        return ''
    parts = name.strip().split(', ', 1)
    return (parts[1] + ' ' + parts[0]) if len(parts) == 2 else name


# ── STEP 3: build key player set ──────────────────────────────────────────────
players = pd.read_parquet(PLAYER_PATH)
key_players = set(
    players.loc[players['MIN'] >= MIN_MPG, 'PLAYER_NAME'].str.strip().str.lower()
)
print(f"Key players (MIN >= {MIN_MPG} MPG): {len(key_players)}")

# ── Load all injury reports ───────────────────────────────────────────────────
print("Loading injury reports...")
frames = []
for p in sorted(INJURY_DIR.glob("*.parquet")):
    # Skip 2026 test file
    if p.stem.startswith('2026'):
        continue
    d_str = p.stem[:10]   # YYYY-MM-DD
    df = pd.read_parquet(p)
    df['report_date'] = d_str
    frames.append(df)

all_reports = pd.concat(frames, ignore_index=True)
print(f"Total rows across all reports: {len(all_reports)}")

# Normalize player names (injury report uses "Last, First" → reverse to "First Last")
all_reports['player_lower'] = all_reports['Player Name'].apply(_reverse_name).str.strip().str.lower()
all_reports['is_out'] = all_reports['Current Status'].str.strip().str.lower() == 'out'
all_reports['is_key'] = all_reports['player_lower'].isin(key_players)

# ── STEP 5: load management flag ─────────────────────────────────────────────
LOAD_MGMT_KEYWORDS = ['rest', 'load management', 'not injury related', 'maintenance']
lm_pattern = '|'.join(LOAD_MGMT_KEYWORDS)
all_reports['is_load_mgmt'] = (
    all_reports['Reason'].str.lower().str.contains(lm_pattern, na=False)
)

# ── STEP 4: per-game injury counts ───────────────────────────────────────────
# For each (report_date, Matchup), count key Out players per team
out_key = all_reports[all_reports['is_out'] & all_reports['is_key']].copy()

# Matchup format: "AWAY @ HOME" — one row per player per game
# We want total key-out players PER GAME (both teams combined)
game_out_counts = (
    out_key.groupby(['report_date', 'Matchup'])
    ['player_lower'].nunique()
    .reset_index()
    .rename(columns={'player_lower': 'key_out_count'})
)
print(f"\nGames with ≥1 key Out player: {len(game_out_counts[game_out_counts['key_out_count'] > 0])}")

# ── Load games ────────────────────────────────────────────────────────────────
games = pd.read_parquet(GAMES_PATH)
games = games[games['season'] == '2023-24'].copy()
games['date_str'] = games['date'].astype(str).str[:10]
print(f"2023-24 games in game table: {len(games)}")

# Build matchup string from games to match injury report Matchup column
# Injury report Matchup: "AWAY @ HOME" (team abbreviations)
# games has home_team / away_team abbreviations
games['matchup_key'] = games['away_team'] + '@' + games['home_team']

# Join: injury report → games
merged = games.merge(
    game_out_counts,
    left_on=['date_str', 'matchup_key'],
    right_on=['report_date', 'Matchup'],
    how='left'
)
merged['key_out_count'] = merged['key_out_count'].fillna(0).astype(int)
print(f"Matched rows: {(~merged['key_out_count'].isna()).sum()} / {len(merged)}")
print(f"  key_out_count distribution: {merged['key_out_count'].value_counts().sort_index().to_dict()}")

# ── STEP 4: calibration table ─────────────────────────────────────────────────
def bucket(n):
    if n == 0: return 'ZERO'
    if n == 1: return 'ONE'
    if n == 2: return 'TWO'
    return 'THREE_PLUS'

merged['out_bucket'] = merged['key_out_count'].apply(bucket)
bucket_order = ['ZERO', 'ONE', 'TWO', 'THREE_PLUS']

calib = (
    merged.groupby('out_bucket')['actual_total']
    .agg(['count', 'mean', 'std', 'median'])
    .reindex(bucket_order)
    .round(2)
)
calib.columns = ['N_games', 'avg_total', 'std_total', 'median_total']

print("\n" + "="*60)
print("CALIBRATION TABLE — 2023-24 Regular Season")
print("Key player = Out AND MIN >= 15 MPG")
print("="*60)
print(f"{'Bucket':<12} {'N':>6} {'Avg Total':>10} {'Median':>8} {'Std':>6}")
print("-"*50)
for bucket_name in bucket_order:
    row = calib.loc[bucket_name]
    if pd.isna(row['N_games']):
        print(f"{bucket_name:<12} {'0':>6} {'N/A':>10} {'N/A':>8} {'N/A':>6}")
    else:
        print(f"{bucket_name:<12} {int(row['N_games']):>6} {row['avg_total']:>10.2f} {row['median_total']:>8.2f} {row['std_total']:>6.2f}")

# Check linearity
avgs = calib['avg_total'].dropna().values
print(f"\nMonotonically decreasing: {all(avgs[i] >= avgs[i+1] for i in range(len(avgs)-1))}")
if len(avgs) >= 2:
    slope = np.polyfit(range(len(avgs)), avgs, 1)[0]
    print(f"Linear slope across buckets: {slope:.2f} pts per bucket level")

# ── STEP 5: load management breakdown ────────────────────────────────────────
out_key_out = all_reports[all_reports['is_out'] & all_reports['is_key']].copy()
total_key_out_player_days = len(out_key_out)
lm_player_days = out_key_out['is_load_mgmt'].sum()
inj_player_days = total_key_out_player_days - lm_player_days

print("\n" + "="*60)
print("LOAD MANAGEMENT BREAKDOWN — Key Players (Out)")
print("="*60)
print(f"Total key-player Out player-days: {total_key_out_player_days}")
print(f"  Load management:  {lm_player_days:>5} ({100*lm_player_days/total_key_out_player_days:.1f}%)")
print(f"  True injury:      {inj_player_days:>5} ({100*inj_player_days/total_key_out_player_days:.1f}%)")

# Top reasons
print("\nTop 20 Reasons (key players, Out):")
top_reasons = out_key_out['Reason'].value_counts().head(20)
for reason, cnt in top_reasons.items():
    lm_flag = " [LOAD MGMT]" if any(k in str(reason).lower() for k in LOAD_MGMT_KEYWORDS) else ""
    print(f"  {cnt:>4}x  {reason}{lm_flag}")

# ── Team-level split ──────────────────────────────────────────────────────────
# home vs away key out impact
print("\n" + "="*60)
print("HOME vs AWAY KEY-OUT SPLIT")
print("="*60)

# Count home key-out and away key-out separately
# Injury report Team column has team abbreviation
# Match to home_team/away_team in games table

# Build per-game home/away out counts
# Flatten out_key by joining to games on date + checking if team is home or away
team_role = games[['game_id','date_str','matchup_key','home_team','away_team','actual_total']].copy()

# Explode: for each out_key player, get their team and date
out_key_teams = out_key[['report_date','Matchup','Team','player_lower']].drop_duplicates()
out_key_teams = out_key_teams.copy()
out_key_teams['team_abbrev'] = out_key_teams['Team'].map(TEAM_ABBREV)

game_team_map = team_role.rename(columns={'date_str':'report_date', 'matchup_key':'Matchup'})
out_with_role = out_key_teams.merge(game_team_map, on=['report_date','Matchup'], how='inner')
out_with_role['role'] = out_with_role.apply(
    lambda r: 'home' if r['team_abbrev'] == r['home_team'] else (
              'away' if r['team_abbrev'] == r['away_team'] else 'unknown'),
    axis=1
)

home_out = out_with_role[out_with_role['role']=='home'].groupby(['report_date','Matchup'])['player_lower'].nunique().reset_index().rename(columns={'player_lower':'home_key_out'})
away_out = out_with_role[out_with_role['role']=='away'].groupby(['report_date','Matchup'])['player_lower'].nunique().reset_index().rename(columns={'player_lower':'away_key_out'})

merged2 = merged.merge(home_out, left_on=['date_str','matchup_key'], right_on=['report_date','Matchup'], how='left')
merged2 = merged2.merge(away_out, left_on=['date_str','matchup_key'], right_on=['report_date','Matchup'], how='left')
merged2['home_key_out'] = merged2['home_key_out'].fillna(0).astype(int)
merged2['away_key_out'] = merged2['away_key_out'].fillna(0).astype(int)

def home_away_table(df, col, label):
    tbl = df.groupby(col)['actual_total'].agg(['count','mean']).round(2)
    print(f"\n  {label}:")
    for k, row in tbl.iterrows():
        print(f"    {k} key out: N={int(row['count']):>4}  avg_total={row['mean']:.2f}")

home_away_table(merged2, 'home_key_out', 'Home team key-out count')
home_away_table(merged2, 'away_key_out', 'Away team key-out count')

# ── STEP 6: VERDICT ──────────────────────────────────────────────────────────
print("\n" + "="*60)
print("VERDICT")
print("="*60)

zero_avg = calib.loc['ZERO','avg_total']
one_avg  = calib.loc['ONE','avg_total']
two_avg  = calib.loc['TWO','avg_total'] if not pd.isna(calib.loc['TWO','avg_total']) else None
n_one    = int(calib.loc['ONE','N_games'])
n_zero   = int(calib.loc['ZERO','N_games'])

delta_one = one_avg - zero_avg if not pd.isna(one_avg) else None
delta_two = two_avg - zero_avg if two_avg is not None and not pd.isna(two_avg) else None

if delta_one is not None:
    direction = "LOWER" if delta_one < 0 else "HIGHER"
    print(f"ONE key player out vs ZERO: avg_total {direction} by {abs(delta_one):.2f} pts "
          f"(N={n_one} vs N={n_zero})")
if delta_two is not None:
    direction2 = "LOWER" if delta_two < 0 else "HIGHER"
    print(f"TWO+ key players out vs ZERO: avg_total {direction2} by {abs(delta_two):.2f} pts")

print(f"\nLoad management share of key-Out absences: {100*lm_player_days/total_key_out_player_days:.1f}%")
print(f"  → Separating LM from injury is {'important' if lm_player_days/total_key_out_player_days > 0.2 else 'minor'}")

# Model recommendation
print("\nMODEL RECOMMENDATION:")
if delta_one is not None and abs(delta_one) >= 1.5 and n_one >= 100:
    print("  SIGNAL EXISTS — key-player Out count has measurable impact on totals.")
    print("  Recommend: Add injury_key_out_count (or home/away split) as a feature.")
    print("  Calibration: ~{:.2f} pts per additional key-Out player.".format(abs(delta_one)))
elif delta_one is not None and abs(delta_one) >= 0.8 and n_one >= 50:
    print("  WEAK SIGNAL — effect present but modest.")
    print("  Recommend: Track live and revisit with 2024-25 data before adding to model.")
else:
    print("  NO CLEAR SIGNAL — injury count does not meaningfully predict totals.")
    print("  Recommend: Do not add to model at this time.")
