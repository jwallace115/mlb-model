import sys; sys.path.insert(0,'.')
import pandas as pd, numpy as np
from nfl.sim.engine import simulate_game,_load_tables,_load_ratings,_CACHE
from nfl.sim.seed_util import stable_seed
ids=[l.strip() for l in open('research/nfl_sim/phase5z_sample.txt') if l.strip()][:int(sys.argv[1])]
_CACHE.clear(); _load_tables(); tr,tend,sit,kicker,league=_load_ratings()
act=pd.concat([pd.read_parquet(f'nfl/data/pbp/pbp_{s}.parquet',columns=['game_id','season','week','home_team','away_team']).drop_duplicates('game_id') for s in [2021,2022,2023,2024]]).set_index('game_id')
out=[]
for g in ids:
    r=act.loc[g]
    sim=simulate_game(r.home_team,r.away_team,int(r.season),int(r.week),n_sims=500,seed=stable_seed((g,42)),team_r=tr,tend=tend,sit=sit,kicker=kicker,league=league)
    out.append(dict(game_id=g,margin=(sim.home_score-sim.away_score).mean(),hwin=(sim.home_score>sim.away_score).mean(),tot=(sim.home_score+sim.away_score).mean()))
pd.DataFrame(out).to_parquet(sys.argv[2])
