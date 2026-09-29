"""Big pre-registered scan. Splits: discovery 1999-2014, validation 2015-2019, holdout 2020-2025 (opened once, at the end).
All features pre-game / point-in-time. Outcomes: home_cover, fav_cover, over (pushes dropped)."""
import pandas as pd, numpy as np
g=pd.read_csv('/tmp/mnf/games.csv'); g=g[(g.game_type=='REG')&g.season.between(1999,2025)].dropna(subset=['home_score','spread_line','total_line']).copy()
g['margin']=g.home_score-g.away_score; g['tot']=g.home_score+g.away_score
g['home_cover']=np.where(g.margin==g.spread_line,np.nan,(g.margin>g.spread_line).astype(float))
g['over']=np.where(g.tot==g.total_line,np.nan,(g.tot>g.total_line).astype(float))
g['home_fav']=g.spread_line>0
g['fav_cover']=np.where(g.spread_line==0,np.nan,np.where(g.home_fav,g.home_cover,1-g.home_cover))
g['split']=np.where(g.season<=2014,'D',np.where(g.season<=2019,'V','H'))
# --- team timezone (current franchises; relocations handled by abbreviations in data) ---
tz={'SEA':-8,'SF':-8,'LA':-8,'LAR':-8,'LAC':-8,'SD':-8,'OAK':-8,'LV':-8,'ARI':-7,'DEN':-7,'KC':-6,'DAL':-6,'HOU':-6,'MIN':-6,'CHI':-6,'GB':-6,'NO':-6,'TEN':-6,'STL':-6}
g['home_tz']=g.home_team.map(tz).fillna(-5); g['away_tz']=g.away_team.map(tz).fillna(-5)
g['tz_move']=g.home_tz-g.away_tz  # >0: away team travels east
g['hour']=pd.to_numeric(g.gametime.str[:2],errors='coerce')
# --- team-game long table for PIT form ---
h=g[['game_id','season','week','home_team','away_team','margin','spread_line','home_cover','over','tot','total_line']].copy()
A=pd.concat([h.assign(team=h.home_team,opp=h.away_team,m=h.margin,ats=h.home_cover,is_home=1),
             h.assign(team=h.away_team,opp=h.home_team,m=-h.margin,ats=1-h.home_cover,is_home=0)])
A=A.sort_values(['team','season','week'])
grp=A.groupby(['team','season'])
A['prev_m']=grp.m.shift(1); A['prev_ats']=grp.ats.shift(1); A['prev_over']=grp.over.shift(1)
A['ats_to_date']=grp.ats.transform(lambda x: x.shift(1).expanding().mean()); A['n_prev']=grp.cumcount()
A['prev2_ats']=grp.ats.shift(2)
A['streak_ats']=np.where((A.prev_ats==1)&(A.prev2_ats==1),2,np.where((A.prev_ats==0)&(A.prev2_ats==0),-2,0))
# revenge: lost to this opponent earlier this season
A['lost_to_opp_before']=A.groupby(['team','season','opp']).m.transform(lambda x: (x.shift(1)<0).astype(float).cummax()).fillna(0)
F=A[['game_id','team','prev_m','prev_ats','prev_over','ats_to_date','n_prev','streak_ats','lost_to_opp_before']]
for s in ['home','away']:
    g=g.merge(F.rename(columns={c:f'{s}_{c}' for c in F.columns if c!='game_id'}),left_on=['game_id',f'{s}_team'],right_on=['game_id',f'{s}_team'],how='left')
# referee prior-season rates (PIT)
refstats=g.groupby(['referee','season']).agg(r_over=('over','mean'),r_home=('home_cover','mean'),r_n=('over','size')).reset_index()
rows=[]
for (ref),x in refstats.groupby('referee'):
    x=x.sort_values('season'); 
    cum_o=(x.r_over*x.r_n).cumsum().shift(1); cum_h=(x.r_home*x.r_n).cumsum().shift(1); cum_n=x.r_n.cumsum().shift(1)
    rows.append(pd.DataFrame({'referee':ref,'season':x.season,'ref_over_prior':cum_o/cum_n,'ref_home_prior':cum_h/cum_n,'ref_n_prior':cum_n}))
g=g.merge(pd.concat(rows),on=['referee','season'],how='left')
# ML vs spread (2006+): de-vigged ML home prob
def imp(a): return np.where(a>0,100/(a+100),-a/(-a+100))
ih,ia=imp(g.home_moneyline),imp(g.away_moneyline); g['ml_home_p']=ih/(ih+ia)
g.to_parquet('/tmp/big/G.parquet'); print(len(g), g.split.value_counts().to_dict())
