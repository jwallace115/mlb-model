import sys; sys.path.insert(0,'.')
import pandas as pd
from nfl.sim.engine import simulate_game,_load_tables,_load_ratings
from nfl.sim.seed_util import stable_seed
_load_tables(); tr,te,si,ki,le=_load_ratings()
r=simulate_game('KC','BUF',2024,11,n_sims=200,seed=stable_seed(('KC','BUF',2024,11,42)),team_r=tr,tend=te,sit=si,kicker=ki,league=le,drive_log=True)
pl=r.attrs['play_log']
k=pl[pl.event_class=='kneel'].copy(); fin=k.elapsed>=k.clock_before-0.01
print('kneels',len(k),'final (ran out the clock)',fin.sum(),' mean all %.1f  non-final %.1f  final %.1f'%(k.elapsed.mean(),k[~fin].elapsed.mean(),k[fin].elapsed.mean()))
print(k[~fin].groupby(['qtr','score_state','clock_period']).elapsed.agg(['count','mean']).round(1))
print((k.elapsed==3.0).sum(),'kneels at the 3.0 s floor')
