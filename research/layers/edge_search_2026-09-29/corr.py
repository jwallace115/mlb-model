import pandas as pd, numpy as np
k=pd.read_parquet('/tmp/k4.parquet'); k=k[(k.hit_over+k.hit_under)==1]
# one line per player-family-game: the line closest to 50/50
k['d']=(k.devig_over-0.5).abs(); k=k.sort_values('d').groupby(['game_id','player_id','family']).head(1)
w=pd.concat([pd.read_parquet(f'/tmp/ev/w{y}.parquet',columns=['player_id','season','week','team','game_id'] if 'game_id' in pd.read_parquet(f'/tmp/ev/w{y}.parquet').columns else ['player_id','season','week','team']) for y in (23,24)])
k['week']=k.game_id.str.split('_').str[1].astype(int)
k=k.merge(w[['player_id','season','week','team']].drop_duplicates(['player_id','season','week']),on=['player_id','season','week'],how='left')
def pairs(fa,pa,fb,pb,same_team=True,sa='over',sb='over'):
    A=k[(k.family==fa)&(k.position==pa)]; B=k[(k.family==fb)&(k.position.isin(pb))]
    m=A.merge(B,on=['game_id'],suffixes=('_a','_b'))
    m=m[m.player_id_a!=m.player_id_b]
    m=m[(m.team_a==m.team_b)] if same_team else m[(m.team_a!=m.team_b)]
    pa_=m[f'devig_{sa}_a']; pb_=m[f'devig_{sb}_b']; ha=m[f'hit_{sa}_a']; hb=m[f'hit_{sb}_b']
    both=(ha*hb).mean(); prod=(pa_*pb_).mean()
    n=len(m); se=np.sqrt(both*(1-both)/n)
    return n, both, prod, both/prod, se/prod, ha.mean(), pa_.mean(), hb.mean(), pb_.mean()
tests=[('QB pass_yds O + same-team WR rec_yds O','pass_yds','QB','rec_yds',['WR'],True,'over','over'),
('QB pass_yds O + same-team TE rec_yds O','pass_yds','QB','rec_yds',['TE'],True,'over','over'),
('QB pass_cmp O + same-team WR receptions O','pass_cmp','QB','receptions',['WR'],True,'over','over'),
('QB pass_yds U + same-team WR rec_yds U','pass_yds','QB','rec_yds',['WR'],True,'under','under'),
('RB rush_att O + same-team QB pass_att U','rush_att','RB','pass_att',['QB'],True,'over','under'),
('RB rush_yds O + same-team QB pass_yds U','rush_yds','RB','pass_yds',['QB'],True,'over','under'),
('QB pass_yds O + OPP QB pass_yds O','pass_yds','QB','pass_yds',['QB'],False,'over','over'),
('QB pass_yds O + OPP WR rec_yds O','pass_yds','QB','rec_yds',['WR'],False,'over','over'),
('QB pass_att O + OPP RB rush_att O','pass_att','QB','rush_att',['RB'],False,'over','over'),
]
print(f"{'pair':48s} {'n':>6s} {'P(both)':>8s} {'mkt prod':>8s} {'lift':>6s} {'se':>5s}")
for t in tests:
    n,b,p,l,se,ha,pa,hb,pb=pairs(*t[1:])
    print(f'{t[0]:48s} {n:6d} {b:8.3f} {p:8.3f} {l:6.2f} {se:5.2f}   (leg A hit {ha:.3f} vs mkt {pa:.3f}; leg B hit {hb:.3f} vs mkt {pb:.3f})')
