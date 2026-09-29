import sys; sys.path.insert(0,'.')
import pandas as pd, numpy as np
from nfl.sim.engine import simulate_game,_load_tables,_load_ratings,_CACHE
from nfl.sim.seed_util import stable_seed
rows=pd.read_parquet('research/nfl_sim/phase6e_k1_after_rows.parquet')
pick=rows.sample(12,random_state=7)
_CACHE.clear(); _load_tables(); tr,tend,sit,kicker,league=_load_ratings()
act=pd.concat([pd.read_parquet(f'nfl/data/pbp/pbp_{s}.parquet',columns=['game_id','home_team','away_team']).drop_duplicates('game_id') for s in [2021,2022,2023,2024]])
mx=0
for _,r in pick.iterrows():
    g=act[act.game_id==r.game_id].iloc[0]
    sim=simulate_game(g.home_team,g.away_team,int(r.season),int(r.week),n_sims=500,seed=stable_seed((r.game_id,42)),team_r=tr,tend=tend,sit=sit,kicker=kicker,league=league,drive_log=True)
    d=[abs(sim.home_score.mean()-r.sim_home),abs(sim.away_score.mean()-r.sim_away),abs(sim.plays.mean()-r.plays),abs(sim.ev_fd_penalty.mean()-r.ev_fd_penalty)]
    mx=max(mx,max(d)); print(r.game_id, [round(x,6) for x in d], flush=True)
print('MAXDIFF',mx)
