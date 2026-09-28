import pandas as pd, numpy as np
P='/home/claude/mlb-model/nfl/data/pbp/pbp_%d.parquet'
cols=['game_id','play_id','season_type','play_type','timeout','game_seconds_remaining','half_seconds_remaining','qtr','score_differential']
df=pd.concat([pd.read_parquet(P%s,columns=cols) for s in range(2021,2025)]); df=df[df.season_type=='REG'].sort_values(['game_id','play_id'])
df['next_to']=df.groupby('game_id')['timeout'].shift(-1).fillna(0)
sc=df[df.play_type.isin(['pass','run','qb_kneel'])].copy()
sc['half']=np.where(sc.qtr<=2,1,np.where(sc.qtr<=4,2,3))
sc['next_hsr']=sc.groupby(['game_id','half'])['half_seconds_remaining'].shift(-1)
k=sc[sc.play_type=='qb_kneel'].copy()
k['final']=k.next_hsr.isna()
k['el']=np.where(k.final,k.half_seconds_remaining,k.half_seconds_remaining-k.next_hsr)
k=k[k.qtr<=4]
ng=df.game_id.nunique()
print('kneels/game %.2f'%(len(k)/ng))
for lab,g in [('all',k),('final',k[k.final]),('nonfinal',k[~k.final]),('nonfinal_noTO',k[~k.final&(k.next_to==0)]),('nonfinal_TO',k[~k.final&(k.next_to==1)])]:
    print(f'{lab:15s} n={len(g):5d} mean={g.el.mean():.1f}')
print(k[~k.final&(k.next_to==0)].groupby('qtr').el.agg(['count','mean']).round(1))
g=k[~k.final].iloc[:3].game_id.tolist()
x=sc[sc.game_id.isin(g[:2])&(sc.qtr==4)&(sc.game_seconds_remaining<200)][['game_id','play_id','play_type','game_seconds_remaining','half_seconds_remaining','next_hsr']]
print(x.to_string())
