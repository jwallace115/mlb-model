#!/usr/bin/env python3
"""
Signal B HOME - Clean PIT-safe Historical Backtest v2
F5 run line home -0.5, threshold: away_sp_xfip - home_sp_xfip >= 1.5
PIT-safe: expanding mean FIP from pitcher_game_logs with shift(1), min 3 starts
"""
import pandas as pd, numpy as np, json, os
from pathlib import Path
import urllib.request, time

OUT = Path('/root/mlb-model/research/recovery/signal_b_clean_backtest')
os.chdir('/root/mlb-model')

# Load data
print("Loading data...")
pgl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
gt = pd.read_parquet('sim/data/game_table.parquet')

# PHASE 1: Build PIT-safe expanding FIP
print("Building PIT-safe expanding FIP...")
sp = pgl[pgl['starter_flag'] == 1].copy()
sp = sp.sort_values(['player_id', 'season', 'game_date'])

sp['cum_k']  = sp.groupby(['player_id','season'])['strikeouts'].transform(lambda x: x.shift(1).expanding().sum())
sp['cum_bb'] = sp.groupby(['player_id','season'])['walks'].transform(lambda x: x.shift(1).expanding().sum())
sp['cum_hr'] = sp.groupby(['player_id','season'])['home_runs_allowed'].transform(lambda x: x.shift(1).expanding().sum())
sp['cum_ip'] = sp.groupby(['player_id','season'])['innings_pitched'].transform(lambda x: x.shift(1).expanding().sum())
sp['cum_starts'] = sp.groupby(['player_id','season'])['game_pk'].transform(lambda x: x.shift(1).expanding().count())

sp['fip_pit'] = np.where(sp['cum_ip'] > 0,
    (13 * sp['cum_hr'] + 3 * sp['cum_bb'] - 2 * sp['cum_k']) / sp['cum_ip'] + 3.10,
    np.nan)
sp['fip_pit'] = np.where(sp['cum_starts'] >= 3, sp['fip_pit'], np.nan)

print(f"Starters with valid FIP: {sp['fip_pit'].notna().sum()}/{len(sp)}")

# home_away uses H/A not home/away
sp_home = sp[sp['home_away'] == 'H'][['game_pk','player_name','fip_pit']].copy()
sp_away = sp[sp['home_away'] == 'A'][['game_pk','player_name','fip_pit']].copy()

sp_home = sp_home.rename(columns={'fip_pit':'home_sp_fip','player_name':'home_sp_name'})
sp_away = sp_away.rename(columns={'fip_pit':'away_sp_fip','player_name':'away_sp_name'})

# Keep game_pk as int64 for merge
merged = gt.merge(sp_home[['game_pk','home_sp_fip','home_sp_name']], on='game_pk', how='left')
merged = merged.merge(sp_away[['game_pk','away_sp_fip','away_sp_name']], on='game_pk', how='left')

print(f"Merged: {len(merged)} games")
print(f"Both SP FIP present: {(merged['home_sp_fip'].notna() & merged['away_sp_fip'].notna()).sum()}")

# Compute xFIP gap
both_valid = merged[merged['home_sp_fip'].notna() & merged['away_sp_fip'].notna()].copy()
both_valid['xfip_gap'] = both_valid['away_sp_fip'] - both_valid['home_sp_fip']
both_valid['qualifies'] = both_valid['xfip_gap'] >= 1.5

print(f"\nTotal games with both SP FIP: {len(both_valid)}")
qualifying = both_valid[both_valid['qualifies']].copy()
print(f"Qualifying (gap >= 1.5): {len(qualifying)}")
print(f"By season:\n{qualifying.groupby('season').size()}")

# Exclude 2026 (in-progress season)
qualifying = qualifying[qualifying['season'] <= 2025].copy()
print(f"Qualifying (2022-2025 only): {len(qualifying)}")

# PHASE 3: Fetch F5 home/away scores from MLB Stats API
print(f"\nFetching F5 scores for {len(qualifying)} qualifying games...")

def get_f5_scores(game_pk):
    url = f'https://statsapi.mlb.com/api/v1/game/{game_pk}/linescore'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        innings = data.get('innings', [])
        home_f5 = 0
        away_f5 = 0
        for inn in innings:
            if inn['num'] <= 5:
                home_f5 += inn.get('home', {}).get('runs', 0)
                away_f5 += inn.get('away', {}).get('runs', 0)
        return home_f5, away_f5
    except Exception as e:
        return None, None

# Check cache
cache_path = OUT / 'f5_scores_cache.json'
if cache_path.exists():
    with open(cache_path) as f:
        f5_cache = json.load(f)
    print(f"Loaded {len(f5_cache)} cached F5 scores")
else:
    f5_cache = {}

# Fetch missing
game_pks = qualifying['game_pk'].tolist()
missing = [str(gpk) for gpk in game_pks if str(gpk) not in f5_cache]
print(f"Need to fetch: {len(missing)} games")

for i, gpk in enumerate(missing):
    if i % 100 == 0 and i > 0:
        print(f"  Fetched {i}/{len(missing)}...", flush=True)
        time.sleep(0.5)
    h, a = get_f5_scores(gpk)
    if h is not None:
        f5_cache[str(gpk)] = {'home_f5': h, 'away_f5': a}
    else:
        f5_cache[str(gpk)] = {'home_f5': None, 'away_f5': None}
    if i % 30 == 0 and i > 0:
        time.sleep(0.2)

with open(cache_path, 'w') as f:
    json.dump(f5_cache, f)
print(f"Cached {len(f5_cache)} F5 scores")

# Attach F5 scores
qualifying = qualifying.copy()
qualifying['home_f5'] = qualifying['game_pk'].astype(str).map(lambda x: f5_cache.get(x, {}).get('home_f5'))
qualifying['away_f5'] = qualifying['game_pk'].astype(str).map(lambda x: f5_cache.get(x, {}).get('away_f5'))

has_f5 = qualifying[qualifying['home_f5'].notna() & qualifying['away_f5'].notna()].copy()
print(f"Games with F5 scores: {len(has_f5)}/{len(qualifying)}")

# F5 run line outcome: home -0.5
has_f5['home_f5'] = has_f5['home_f5'].astype(float)
has_f5['away_f5'] = has_f5['away_f5'].astype(float)
has_f5['home_rl_win'] = (has_f5['home_f5'] > has_f5['away_f5']).astype(int)
has_f5['f5_margin'] = has_f5['home_f5'] - has_f5['away_f5']

# PHASE 4: Performance
print("\n" + "="*70)
print("SIGNAL B HOME - CLEAN PIT-SAFE BACKTEST RESULTS")
print("="*70)
print(f"Market: F5 Run Line HOME -0.5")
print(f"Trigger: away_sp_FIP - home_sp_FIP >= 1.5 (PIT-safe expanding mean)")
print(f"Stake: 0.5u flat")
print(f"Price assumption: -135 (approx typical F5 RL favorite)")
print()

n = len(has_f5)
wins = int(has_f5['home_rl_win'].sum())
losses = n - wins
hit_rate = wins / n if n > 0 else 0
print(f"OVERALL: {n} bets, {wins}W-{losses}L, hit rate {hit_rate:.1%}")

juice = -135
risk_per_bet = 0.5
win_profit = risk_per_bet * (100 / abs(juice))
loss_cost = risk_per_bet

total_profit = wins * win_profit - losses * loss_cost
total_risked = n * risk_per_bet
roi = total_profit / total_risked if total_risked > 0 else 0

print(f"ROI @ -135: {roi:.1%} (profit: {total_profit:+.2f}u on {total_risked:.1f}u risked)")
print()

be = abs(juice) / (abs(juice) + 100)
print(f"Breakeven hit rate @ -135: {be:.1%}")
print(f"Actual hit rate: {hit_rate:.1%}")
print(f"Edge over breakeven: {(hit_rate - be)*100:+.1f}pp")
print()

# By season
print("BY SEASON:")
season_stats = {}
for season, grp in has_f5.groupby('season'):
    sn = len(grp)
    sw = int(grp['home_rl_win'].sum())
    sl = sn - sw
    shr = sw / sn if sn > 0 else 0
    sp_val = sw * win_profit - sl * loss_cost
    sr = sp_val / (sn * risk_per_bet) if sn > 0 else 0
    print(f"  {int(season)}: {sn} bets, {sw}W-{sl}L, {shr:.1%} hit rate, ROI {sr:.1%} ({sp_val:+.2f}u)")
    season_stats[int(season)] = {'n': sn, 'w': sw, 'l': sl, 'hit_rate': round(shr, 4), 'roi': round(sr, 4), 'profit': round(sp_val, 2)}

print()

# By gap bucket
print("BY GAP BUCKET:")
has_f5_bucketed = has_f5.copy()
has_f5_bucketed['gap_bucket'] = pd.cut(has_f5_bucketed['xfip_gap'], bins=[1.5, 2.0, 2.5, 3.0, 10.0],
                               labels=['1.5-2.0', '2.0-2.5', '2.5-3.0', '3.0+'],
                               right=False)
bucket_stats = {}
for bucket, grp in has_f5_bucketed.groupby('gap_bucket', observed=True):
    bn = len(grp)
    bw = int(grp['home_rl_win'].sum())
    bl = bn - bw
    bhr = bw / bn if bn > 0 else 0
    bp = bw * win_profit - bl * loss_cost
    br = bp / (bn * risk_per_bet) if bn > 0 else 0
    print(f"  {bucket}: {bn} bets, {bw}W-{bl}L, {bhr:.1%} hit rate, ROI {br:.1%} ({bp:+.2f}u)")
    bucket_stats[str(bucket)] = {'n': bn, 'w': bw, 'l': bl, 'hit_rate': round(bhr, 4), 'roi': round(br, 4)}

print()

# Monthly breakdown
print("BY MONTH (all seasons):")
has_f5_m = has_f5.copy()
has_f5_m['month'] = pd.to_datetime(has_f5_m['date']).dt.month
for month, grp in has_f5_m.groupby('month'):
    mn = len(grp)
    mw = int(grp['home_rl_win'].sum())
    ml = mn - mw
    mhr = mw / mn if mn > 0 else 0
    mp = mw * win_profit - ml * loss_cost
    mr = mp / (mn * risk_per_bet) if mn > 0 else 0
    month_name = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct'][month]
    print(f"  {month_name}: {mn} bets, {mw}W-{ml}L, {mhr:.1%} hit rate, ROI {mr:.1%}")

# Save CSV
export = has_f5[['game_pk','date','season','home_team','away_team',
                  'home_sp_name','away_sp_name','home_sp_fip','away_sp_fip',
                  'xfip_gap','home_f5','away_f5','f5_margin','home_rl_win']].copy()
export.to_csv(OUT / 'signal_b_home_backtest.csv', index=False)
print(f"\nSaved {len(export)} rows to signal_b_home_backtest.csv")

# Save stats JSON
stats = {
    'total_bets': n,
    'wins': wins,
    'losses': losses,
    'hit_rate': round(hit_rate, 4),
    'roi_at_135': round(roi, 4),
    'profit_units': round(total_profit, 2),
    'risked_units': round(total_risked, 1),
    'breakeven_rate': round(be, 4),
    'edge_over_be': round(hit_rate - be, 4),
    'by_season': season_stats,
    'by_bucket': bucket_stats,
}
with open(OUT / 'backtest_stats.json', 'w') as f:
    json.dump(stats, f, indent=2)

print("\nDone.")
