import pandas as pd, numpy as np
m=pd.read_parquet('/tmp/weird/props_main.parquet'); g=pd.read_parquet('/tmp/weird/games.parquet')
def top(fam,pos,agg='max'):
    x=m[(m.family==fam)&(m.position.isin(pos))]
    return x.groupby(['game_id','team']).line.agg(agg)
T=pd.DataFrame({
 'qb_pyds':top('pass_yds',['QB']),'qb_patt':top('pass_att',['QB']),'qb_ptd':top('pass_td',['QB']),
 'rb1_ratt':top('rush_att',['RB']),'rb1_ryds':top('rush_yds',['RB']),
 'rush_yds_sum':top('rush_yds',['RB','QB','WR'],'sum'),'rec_yds_sum':top('rec_yds',['WR','TE','RB'],'sum'),
}).reset_index()
# QB pass TD over prob as scoring signal
td=m[(m.family=='pass_td')&(m.position=='QB')].sort_values('line').groupby(['game_id','team']).tail(1)
T=T.merge(td[['game_id','team','devig_over','line']].rename(columns={'devig_over':'qb_td_over_p','line':'qb_td_line'}),on=['game_id','team'],how='left')
G=g[['game_id','season','week','home_team','away_team','spread_line','total_line','actual_total','margin','over_odds','under_odds','home_spread_odds','away_spread_odds','roof','div_game']].copy()
for s in ['home','away']:
    G=G.merge(T.rename(columns={c:f'{s}_{c}' for c in T.columns if c not in('game_id',)}).rename(columns={f'{s}_team':f'{s}_team'}),left_on=['game_id',f'{s}_team'],right_on=['game_id',f'{s}_team'],how='left')
G['over']=(G.actual_total>G.total_line).astype(float); G.loc[G.actual_total==G.total_line,'over']=np.nan
G['home_cover']=((G.margin-G.spread_line)>0).astype(float); G.loc[G.margin==G.spread_line,'home_cover']=np.nan
G.to_parquet('/tmp/weird/G.parquet')
print(len(G),'games; with both QB pass yds lines:',G[['home_qb_pyds','away_qb_pyds']].notna().all(axis=1).sum(),'; with both RB1 att:',G[['home_rb1_ratt','away_rb1_ratt']].notna().all(axis=1).sum())
