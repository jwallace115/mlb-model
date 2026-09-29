import pandas as pd, numpy as np
g=pd.read_csv('/tmp/mnf/games.csv'); g=g[(g.game_type=='REG')].dropna(subset=['total_line']).copy()
g['actual']=g.home_score+g.away_score; g['miss']=g.actual-g.total_line
# referee prior-seasons over rate (point-in-time: seasons < s only)
ref=g[g.season>=2012].dropna(subset=['home_score'])
def ref_prior(row):
    r=ref[(ref.referee==row.referee)&(ref.season<row.season)]
    return pd.Series({'ref_n':len(r),'ref_over':(r.miss>0).mean() if len(r) else np.nan})
G=g[(g.season.between(2020,2025))].dropna(subset=['home_score']).copy()
G=pd.concat([G,G.apply(ref_prior,axis=1)],axis=1)
# QB change vs team's previous game
qb=pd.concat([g[['season','week','game_id','home_team','home_qb_id']].rename(columns={'home_team':'team','home_qb_id':'qb'}),
              g[['season','week','game_id','away_team','away_qb_id']].rename(columns={'away_team':'team','away_qb_id':'qb'})]).sort_values(['team','season','week'])
qb['qb_prev']=qb.groupby(['team','season']).qb.shift(1); qb['qb_new']=(qb.qb!=qb.qb_prev)&qb.qb_prev.notna()
t=pd.read_parquet('/tmp/tot/team_pit.parquet')
for side in ['home','away']:
    G=G.merge(t[['game_id','team','off_epa_pit','def_epa_pit','plays_pit','n_prior']].rename(columns=lambda c: f'{side}_{c}' if c not in('game_id',) else c),left_on=['game_id',f'{side}_team'],right_on=['game_id',f'{side}_team'],how='left')
    G=G.merge(qb[['game_id','team','qb_new']].rename(columns={'team':f'{side}_team','qb_new':f'{side}_qb_new'}),on=['game_id',f'{side}_team'],how='left')
G['disc']=G.season<=2023
G.to_parquet('/tmp/tot/games_feat.parquet'); print(len(G), G.disc.sum())
