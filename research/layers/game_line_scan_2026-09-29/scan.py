import pandas as pd, numpy as np, itertools
from scipy.stats import norm
g=pd.read_parquet('/tmp/big/G.parquet')
S=g.spread_line; A=S.abs(); T=g.total_line
C={}
# line cells
for lo,hi,lab in [(0.5,2.5,'fav 0.5-2.5'),(3,3,'fav exactly 3'),(3.5,6.5,'fav 3.5-6.5'),(7,7,'fav exactly 7'),(7.5,9.5,'fav 7.5-9.5'),(10,40,'fav 10+')]:
    C[f'L home {lab}']=S.between(lo,hi); C[f'L away {lab}']=(-S).between(lo,hi)
C['L pick-em']=S==0
for k in [2.5,3.5,6.5,7.5,10,14]: C[f'L |spread| = {k}']=A==k
for lo,hi in [(0,36.5),(37,39.5),(40,42.5),(43,45.5),(46,48.5),(49,51.5),(52,99)]: C[f'L total {lo}-{hi}']=T.between(lo,hi)
C['L total on key 41/44/37/47']=T.isin([37,41,44,47]); C['L total half-point']=(T*2)%2==1
C['L home fav']=S>0; C['L away fav']=S<0
# juice (2006+)
C['J over juiced (<=-115, under >=-105)']=(g.over_odds<=-115)&(g.under_odds>=-105)
C['J under juiced']=(g.under_odds<=-115)&(g.over_odds>=-105)
C['J home spread juiced']=(g.home_spread_odds<=-115)&(g.away_spread_odds>=-105)
C['J away spread juiced']=(g.away_spread_odds<=-115)&(g.home_spread_odds>=-105)
# ML vs spread residual: fit on discovery 2006-2014
d=g[(g.split=='D')&g.ml_home_p.notna()]
b=np.polyfit(d.spread_line,np.log(d.ml_home_p/(1-d.ml_home_p)),3)
g['ml_resid']=np.log(g.ml_home_p/(1-g.ml_home_p))-np.polyval(b,g.spread_line)
q1,q2=np.nanquantile(g[g.split=='D'].ml_resid,[0.2,0.8])
C['M ML likes home more than spread (top 20%)']=g.ml_resid>q2; C['M ML likes home less than spread (bottom 20%)']=g.ml_resid<q1
# context
C['X divisional']=g.div_game==1; C['X dome/closed']=g.roof.isin(['dome','closed']); C['X outdoors']=g.roof=='outdoors'
C['X grass']=g.surface.fillna('').str.contains('grass'); C['X turf']=~g.surface.fillna('grass').str.contains('grass')
C['X temp < 32']=g.temp<32; C['X temp > 80']=g.temp>80
C['X Thursday']=g.weekday=='Thursday'; C['X Monday']=g.weekday=='Monday'; C['X Saturday']=g.weekday=='Saturday'
C['X early (<14h)']=g.hour<14; C['X late afternoon (15-17h)']=g.hour.between(15,17); C['X night (>=19h)']=g.hour>=19
for lo,hi,lab in [(1,1,'week 1'),(2,4,'weeks 2-4'),(5,9,'weeks 5-9'),(10,13,'weeks 10-13'),(14,16,'weeks 14-16'),(17,18,'weeks 17-18')]: C[f'X {lab}']=g.week.between(lo,hi)
C['X rest home - away >= 3']=(g.home_rest-g.away_rest)>=3; C['X rest home - away <= -3']=(g.home_rest-g.away_rest)<=-3
C['X away off bye']=g.away_rest>=13; C['X home off bye']=g.home_rest>=13
C['X away travels east 2+ h, early game']=(g.tz_move>=2)&(g.hour<14); C['X away travels west 2+ h']=g.tz_move<=-2
C['X away travels east 2+ h, night game']=(g.tz_move>=2)&(g.hour>=19)
# form (PIT)
for s in ['home','away']:
    C[f'F {s} lost last game by 21+']=g[f'{s}_prev_m']<=-21; C[f'F {s} won last game by 21+']=g[f'{s}_prev_m']>=21
    C[f'F {s} covered last game']=g[f'{s}_prev_ats']==1; C[f'F {s} failed to cover last game']=g[f'{s}_prev_ats']==0
    C[f'F {s} ATS to date >= 70% (4+ games)']=(g[f'{s}_ats_to_date']>=0.7)&(g[f'{s}_n_prev']>=4)
    C[f'F {s} ATS to date <= 30% (4+ games)']=(g[f'{s}_ats_to_date']<=0.3)&(g[f'{s}_n_prev']>=4)
    C[f'F {s} 2 straight covers']=g[f'{s}_streak_ats']==2; C[f'F {s} 2 straight non-covers']=g[f'{s}_streak_ats']==-2
    C[f'F {s} last game went over']=g[f'{s}_prev_over']==1; C[f'F {s} last game went under']=g[f'{s}_prev_over']==0
    C[f'F {s} revenge (lost to opp earlier this season)']=g[f'{s}_lost_to_opp_before']==1
C['R ref prior over >= 55% (60+ games)']=(g.ref_over_prior>=0.55)&(g.ref_n_prior>=60)
C['R ref prior over <= 45% (60+ games)']=(g.ref_over_prior<=0.45)&(g.ref_n_prior>=60)
C['R ref prior home cover >= 55% (60+)']=(g.ref_home_prior>=0.55)&(g.ref_n_prior>=60)
C['R ref prior home cover <= 45% (60+)']=(g.ref_home_prior<=0.45)&(g.ref_n_prior>=60)
C={k:v.fillna(False).astype(bool) for k,v in C.items()}
singles=list(C.keys())
# pairs: line cells x (context, form, referee, juice, ML)
Lk=[k for k in singles if k.startswith('L ')]; Ok=[k for k in singles if not k.startswith('L ')]
for a,b_ in itertools.product(Lk,Ok): C[f'{a} & {b_}']=C[a]&C[b_]
for a,b_ in itertools.combinations([k for k in Ok if k[0] in 'XF'],2): C[f'{a} & {b_}']=C[a]&C[b_]
outs=['home_cover','fav_cover','over']
rows=[]
for name,msk in C.items():
    for o in outs:
        y=g.loc[msk,[o,'split']].dropna()
        yd=y[y.split=='D'][o]
        if len(yd)<150: continue
        yv=y[y.split=='V'][o]
        zd=(yd.mean()-0.5)/np.sqrt(0.25/len(yd)); zv=(yv.mean()-0.5)/np.sqrt(0.25/len(yv)) if len(yv) else np.nan
        rows.append((name,o,len(yd),yd.mean(),zd,len(yv),yv.mean() if len(yv) else np.nan,zv))
R=pd.DataFrame(rows,columns=['cell','outcome','n_d','rate_d','z_d','n_v','rate_v','z_v'])
R['p_d']=2*(1-norm.cdf(R.z_d.abs()))
# Benjamini-Hochberg q=0.10 on discovery
R=R.sort_values('p_d').reset_index(drop=True); m=len(R); R['bh']=R.p_d<=(np.arange(1,m+1)/m*0.10)
last=R.index[R.bh].max() if R.bh.any() else -1; R['fdr_pass']=R.index<=last
R['val_pass']=R.fdr_pass&(np.sign(R.z_v)==np.sign(R.z_d))&(R.z_v.abs()>=1.645)
print('cells x outcomes tested in discovery:',m,'| FDR(10%) pass:',R.fdr_pass.sum(),'| also pass validation:',R.val_pass.sum())
print('expected false positives at p<0.01 by chance: %.0f ; observed p<0.01: %d'%(0.01*m,(R.p_d<0.01).sum()))
print(R.head(40).round(3).to_string(index=False))
R.to_csv('/tmp/big/scan_DV.csv',index=False)
import pickle; pickle.dump({k:v.values for k,v in C.items()},open('/tmp/big/cells.pkl','wb'))
