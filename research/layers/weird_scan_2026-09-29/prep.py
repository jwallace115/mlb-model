import pandas as pd, numpy as np
k=pd.read_parquet('/tmp/k4.parquet'); k=k[(k.hit_over+k.hit_under)==1].copy()
k['week']=k.game_id.str.split('_').str[1].astype(int)
w=pd.concat([pd.read_parquet(f'/tmp/ev/w{y}.parquet') for y in (23,24)])
w=w[['player_id','season','week','team','position','carries','attempts','targets']]
k=k.merge(w[['player_id','season','week','team']].drop_duplicates(['player_id','season','week']),on=['player_id','season','week'],how='left')
print('rows',len(k),'team matched %.3f'%k.team.notna().mean())
# main line per player-family-game: closest to 50/50
k['d']=(k.devig_over-0.5).abs()
m=k.sort_values('d').groupby(['game_id','player_id','family']).head(1).copy()
g=pd.read_csv('/tmp/mnf/games.csv'); g=g[g.season.isin([2023,2024])&(g.game_type=='REG')]
g['actual_total']=g.home_score+g.away_score; g['margin']=g.home_score-g.away_score
m.to_parquet('/tmp/weird/props_main.parquet'); k.to_parquet('/tmp/weird/props_all.parquet'); g.to_parquet('/tmp/weird/games.parquet')
print(m.family.value_counts()); print(len(g))
