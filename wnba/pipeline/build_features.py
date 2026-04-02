#!/usr/bin/env python3
"""WNBA Feature Builder — updates feature table from raw data."""
import sys, os
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

def main():
    pgl = pd.read_parquet("wnba/data/player_game_logs.parquet")
    tgl = pd.read_parquet("wnba/data/team_game_logs.parquet")
    gi = pd.read_parquet("wnba/data/game_index.parquet")

    for df in [pgl, tgl, gi]:
        df['game_id'] = df['game_id'].astype(str).str.split('.').str[0]

    # Exclude 2020
    pgl = pgl[pgl['season'] != 2020]; tgl = tgl[tgl['season'] != 2020]; gi = gi[gi['season'] != 2020]

    # Team stats from player logs
    team_stats = pgl.groupby(['game_id','team_abbreviation','season']).agg(
        fg3a=('fg3a','sum'), fta=('fta','sum'), oreb=('rebounds_offensive','sum'),
        tov=('turnovers','sum'), fga=('fga','sum'),
    ).reset_index()

    tf = tgl[['game_id','team_abbreviation','season','home_away','points_scored','points_allowed']].copy()
    tf = tf.merge(team_stats, on=['game_id','team_abbreviation','season'], how='left')
    tf = tf.merge(gi[['game_id','game_date']].drop_duplicates(), on='game_id', how='left')
    tf['pace'] = tf['fga'] + 0.44*tf['fta'] + tf['tov']
    tf['tpa_rate'] = tf['fg3a'] / tf['fga'].clip(lower=1)
    tf['oreb_rate'] = tf['oreb']
    tf['fta_rate'] = tf['fta']

    tf = tf.sort_values(['team_abbreviation','season','game_date']).reset_index(drop=True)

    # Rolling features
    for raw, roll in [('points_scored','rolling_pts'),('points_allowed','rolling_opp_pts'),
                       ('pace','rolling_pace'),('tpa_rate','rolling_3pa_rate'),
                       ('oreb_rate','rolling_oreb_rate'),('fta_rate','rolling_fta_rate')]:
        rv = []
        for (t,y), g in tf.groupby(['team_abbreviation','season']):
            g=g.sort_values('game_date'); vals=[]
            for idx, row in g.iterrows():
                rv.append(np.mean(vals[-10:]) if len(vals)>=5 else np.nan)
                vals.append(row[raw])
        tf[roll] = rv

    # Home premium
    hp = []
    for (t,y), g in tf.groupby(['team_abbreviation','season']):
        g=g.sort_values('game_date'); h=[]; a=[]
        for idx, row in g.iterrows():
            ha=np.mean(h[-10:]) if len(h)>=3 else np.nan
            aa=np.mean(a[-10:]) if len(a)>=3 else np.nan
            hp.append(ha-aa if pd.notna(ha) and pd.notna(aa) else np.nan)
            if row['home_away']=='HOME': h.append(row['points_scored'])
            else: a.append(row['points_scored'])
    tf['home_premium'] = hp

    tf['early_season'] = 0
    gn = []
    for (t,y), g in tf.groupby(['team_abbreviation','season']):
        g=g.sort_values('game_date')
        for i, (idx, row) in enumerate(g.iterrows()):
            gn.append(i)
    tf['game_num'] = gn
    tf['early_season'] = (tf['game_num']<10).astype(int)

    # Build game-level
    home = tgl[tgl['home_away']=='HOME'][['game_id','team_abbreviation','points_scored','points_allowed',
        'rest_days','back_to_back','season']].copy()
    home.columns = ['game_id','home_team','home_pts','home_opp_pts','home_rest','home_b2b','season']
    away = tgl[tgl['home_away']=='AWAY'][['game_id','team_abbreviation','points_scored','points_allowed',
        'rest_days','back_to_back']].copy()
    away.columns = ['game_id','away_team','away_pts','away_opp_pts','away_rest','away_b2b']

    games = home.merge(away, on='game_id', how='inner')
    games = games.merge(gi[['game_id','game_date']].drop_duplicates(), on='game_id', how='left')
    games['actual_total'] = games['home_pts'] + games['away_pts']
    games['home_b2b'] = games['home_b2b'].astype(int)
    games['away_b2b'] = games['away_b2b'].astype(int)
    games['rest_diff'] = games['home_rest'].fillna(2) - games['away_rest'].fillna(2)

    # Join features
    hf = tf[tf['home_away']=='HOME'][['game_id','rolling_pts','rolling_opp_pts','rolling_pace',
        'rolling_3pa_rate','rolling_oreb_rate','rolling_fta_rate','home_premium','early_season']].copy()
    hf.columns = ['game_id','home_rolling_pts','home_rolling_opp_pts','home_rolling_pace',
                   'home_rolling_3pa_rate','home_rolling_oreb_rate','home_rolling_fta_rate',
                   'home_premium','home_early_season']
    af = tf[tf['home_away']=='AWAY'][['game_id','rolling_pts','rolling_opp_pts','rolling_pace',
        'rolling_3pa_rate','rolling_oreb_rate','rolling_fta_rate','early_season']].copy()
    af.columns = ['game_id','away_rolling_pts','away_rolling_opp_pts','away_rolling_pace',
                   'away_rolling_3pa_rate','away_rolling_oreb_rate','away_rolling_fta_rate','away_early_season']

    feat = games.merge(hf, on='game_id', how='left').merge(af, on='game_id', how='left')
    feat['early_season_flag'] = ((feat['home_early_season']==1)|(feat['away_early_season']==1)).astype(int)

    core = ['home_rolling_pts','away_rolling_pts','home_rolling_opp_pts','away_rolling_opp_pts']
    feat = feat.dropna(subset=core)

    feat.to_parquet("wnba/data/canonical/wnba_feature_table.parquet", index=False)
    print(f"Feature table updated: {feat.shape}, date range: {feat['game_date'].min()} to {feat['game_date'].max()}")

if __name__ == "__main__":
    main()
