import sys, time; sys.path.insert(0,'.')
import pandas as pd, numpy as np
from nfl.sim.engine import simulate_game,_load_tables,_load_ratings
from nfl.sim.seed_util import stable_seed
from nfl.sim.calibration import engine_fingerprint
out=sys.argv[1]
ids=[l.strip() for l in open('research/nfl_sim/phase5z_sample.txt') if l.strip()]
g=pd.concat([pd.read_parquet(f'nfl/data/pbp/pbp_{s}.parquet',columns=['game_id','home_team','away_team','week','season']) for s in range(2021,2025)]).drop_duplicates('game_id').set_index('game_id').loc[ids].reset_index()
print('fp',engine_fingerprint(),len(g)); _load_tables(); tr,te,si,ki,le=_load_ratings()
T=[];D=[];PL=[];t0=time.time()
for i,x in g.iterrows():
    r=simulate_game(x.home_team,x.away_team,int(x.season),int(x.week),n_sims=100,seed=stable_seed((x.home_team,x.away_team,int(x.season),int(x.week),42)),team_r=tr,tend=te,sit=si,kicker=ki,league=le,drive_log=True)
    t=r[list(dict.fromkeys(['home_score','away_score','plays','drives','ev_safeties','ev_clock_used','ot_flag']+[c for c in r.columns if c.startswith('ev_to') or c.startswith('_saf') or c.startswith('ev_saf')]))].copy(); t['game_id']=x.game_id
    vz=r.attrs.get('vz')
    if vz is not None: t['vz90'],t['vz95'],t['vz98']=vz
    for c in ('saf_pre','saf_sack','saf_rush'):
        if r.attrs.get(c) is not None: t[c]=r.attrs[c]
    T.append(t)
    d=r.attrs['drive_log']; d=pd.DataFrame(d) if not isinstance(d,pd.DataFrame) else d.copy(); d['game_id']=x.game_id; D.append(d)
    p=r.attrs['play_log'].copy(); p['game_id']=x.game_id; PL.append(p)
    if (i+1)%50==0: print(i+1,round(time.time()-t0))
pd.concat(T).to_parquet(f'{out}_team.parquet'); pd.concat(D).to_parquet(f'{out}_drives.parquet'); pd.concat(PL).to_parquet(f'{out}_plays.parquet')
print('done',round(time.time()-t0))
