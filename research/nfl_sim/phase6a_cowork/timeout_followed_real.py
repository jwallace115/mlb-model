import pandas as pd, numpy as np
P='/home/claude/mlb-model/nfl/data/pbp/pbp_%d.parquet'
cols=['game_id','play_id','season_type','play_type','timeout','timeout_team','posteam','defteam','incomplete_pass','out_of_bounds','complete_pass','sack','first_down','touchdown','interception','fumble_lost','game_seconds_remaining','half_seconds_remaining','qtr','score_differential','qb_spike']
dfs=[]
for s in range(2021,2025):
    d=pd.read_parquet(P%s,columns=cols); dfs.append(d[d.season_type=='REG'])
df=pd.concat(dfs).sort_values(['game_id','play_id'])
ng=df.game_id.nunique()
df['next_to']=df.groupby('game_id')['timeout'].shift(-1).fillna(0)
df['next_to_team']=df.groupby('game_id')['timeout_team'].shift(-1)
sc=df[df.play_type.isin(['pass','run'])].copy()
sc['next_gsr']=sc.groupby('game_id')['game_seconds_remaining'].shift(-1)
sc['el']=sc.game_seconds_remaining-sc.next_gsr
de=(sc.touchdown==1)|(sc.interception==1)|(sc.fumble_lost==1)
sc=sc[~de & sc.el.notna() & (sc.el>0)&(sc.el<120)]
to=sc[sc.next_to==1].copy()
stopped=(to.incomplete_pass==1)|(to.out_of_bounds==1)|(to.qb_spike==1)
to['clk']=np.where(to.incomplete_pass==1,'incomplete',np.where(to.out_of_bounds==1,'oob','running'))
to['side']=np.where(to.next_to_team==to.posteam,'off','def')
to['per']=np.where((to.qtr==2)&(to.half_seconds_remaining<=120),'Q2_late',np.where((to.qtr==4)&(to.game_seconds_remaining<=120),'Q4_late',np.where(to.qtr==4,'Q4_other','other')))
print('games',ng,'timeout-followed scrim plays',len(to),'per game %.2f'%(len(to)/ng))
g=to.groupby('clk').el.agg(['count','mean']); g['per_game']=g['count']/ng; print(g.round(2))
g=to[to.clk=='running'].groupby(['per','side']).el.agg(['count','mean']); g['per_game']=g['count']/ng; print(g.round(3))
# running-clock plays NOT followed by timeout, late periods, mean elapsed
sc['per']=np.where((sc.qtr==2)&(sc.half_seconds_remaining<=120),'Q2_late',np.where((sc.qtr==4)&(sc.game_seconds_remaining<=120),'Q4_late','other'))
run=(sc.incomplete_pass!=1)&(sc.out_of_bounds!=1)
print(sc[run].groupby(['per',sc[run].next_to==1]).el.agg(['count','mean']).round(1))
