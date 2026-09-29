"""Totals miss deep dive — point-in-time team features. Discovery 2020-23, validation 2024-25 (set before looking)."""
import pandas as pd, numpy as np
P='/home/claude/mlb-model/nfl/data/pbp/pbp_%d.parquet'
cols=['game_id','season','week','season_type','posteam','defteam','play_type','epa','home_team','away_team']
rows=[]
for s in range(2020,2026):
    d=pd.read_parquet(P%s,columns=cols); d=d[(d.season_type=='REG')&d.play_type.isin(['pass','run'])&d.epa.notna()]
    o=d.groupby(['season','week','game_id','posteam']).agg(off_epa=('epa','mean'),plays=('epa','size')).reset_index().rename(columns={'posteam':'team'})
    df=d.groupby(['season','week','game_id','defteam']).agg(def_epa=('epa','mean')).reset_index().rename(columns={'defteam':'team'})
    rows.append(o.merge(df,on=['season','week','game_id','team']))
tg=pd.concat(rows).sort_values(['team','season','week'])
# season-to-date means of PRIOR games only (point-in-time), and games played before
for c in ['off_epa','def_epa','plays']:
    tg[c+'_pit']=tg.groupby(['team','season'])[c].transform(lambda x: x.shift(1).expanding().mean())
tg['n_prior']=tg.groupby(['team','season']).cumcount()
tg.to_parquet('/tmp/tot/team_pit.parquet'); print(tg.shape)
