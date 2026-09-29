import pandas as pd, numpy as np, glob, sys
sport=sys.argv[1]; TH=float(sys.argv[2]) if len(sys.argv)>2 else 0.02
fs=sorted(glob.glob(f'/tmp/ev/data/odds_archive/{sport}/line_history/season=2026/snap_*.parquet'))
d=pd.concat([pd.read_parquet(f) for f in fs],ignore_index=True)
d=d[d.bookmaker.isin(['pinnacle','hardrockbet_fl'])].copy()
d['snap']=pd.to_datetime(d.snapshot_utc,utc=True); d['kick']=pd.to_datetime(d.commence_time,utc=True)
d=d[d.snap<d.kick]
d['point']=d.point.fillna(0.0)
d['lk']=np.where(d.market=='spreads',np.where(d.outcome_name==d.home_team,d.point,-d.point),d.point)
d['imp']=np.where(d.price>0,100/(d.price+100),-d.price/(-d.price+100))
d['dec']=np.where(d.price>0,1+d.price/100,1+100/-d.price)
k=['snap','event_id','market','lk']
p=d[d.bookmaker=='pinnacle'].copy()
p['nout']=p.groupby(k).outcome_name.transform('size'); p=p[p.nout==2]
p['fair']=p.imp/p.groupby(k).imp.transform('sum')
h=d[d.bookmaker=='hardrockbet_fl']
m=h.merge(p[k+['outcome_name','fair']],on=k+['outcome_name'],how='inner')
m['ev']=m.fair*m.dec-1
m['hrs_to_kick']=(m.kick-m.snap).dt.total_seconds()/3600
print(sport,'HR quotes matched to a Pinnacle two-way at the same snapshot:',len(m),'| events',m.event_id.nunique())
print('share of matched quotes with EV>=0: %.3f  >=2%%: %.3f  >=4%%: %.3f'%((m.ev>=0).mean(),(m.ev>=0.02).mean(),(m.ev>=0.04).mean()))
# first detection per bet key
b=m[m.ev>=TH].sort_values('snap').groupby(['event_id','market','lk','outcome_name']).head(1).copy()
# Pinnacle close: last pre-kick fair for same key
pc=p.sort_values('snap').groupby(['event_id','market','lk','outcome_name']).tail(1)[['event_id','market','lk','outcome_name','fair','snap']].rename(columns={'fair':'fair_close','snap':'snap_close'})
b=b.merge(pc,on=['event_id','market','lk','outcome_name'],how='left')
b['clv']=b.fair_close-b.fair
b['close_age_h']=(b.kick-b.snap_close).dt.total_seconds()/3600
ok=b[b.fair_close.notna()&(b.close_age_h<=1.0)]
print(f'bets flagged at EV>={TH:.0%}: {len(b)} (close available within 1h of kick: {len(ok)})')
se=ok.clv.std()/np.sqrt(len(ok))
print('mean probability CLV vs Pinnacle close: %+.4f (se %.4f)  share CLV>0: %.3f  mean EV at bet: %.3f'%(ok.clv.mean(),se,(ok.clv>0).mean(),ok.ev.mean()))
# expected value at CLOSE: fair_close*dec-1 (what the bet is worth by the sharp close)
ok=ok.assign(ev_close=ok.fair_close*ok.dec-1)
print('mean EV at bet %.3f -> mean EV at the close %.3f'%(ok.ev.mean(),ok.ev_close.mean()))
print(ok.groupby('market').agg(n=('clv','size'),clv=('clv','mean'),ev_bet=('ev','mean'),ev_close=('ev_close','mean')).round(4))
ok['tk']=pd.cut(ok.hrs_to_kick,[0,3,12,48,1000])
print(ok.groupby('tk',observed=True).agg(n=('clv','size'),clv=('clv','mean'),ev_close=('ev_close','mean')).round(4))
ok['wk']=ok.kick.dt.isocalendar().week
print(ok.groupby('wk').agg(n=('clv','size'),ev_close=('ev_close','mean')).round(4))
ok.drop(columns=['tk']).to_parquet(f'/tmp/ev/bets_{sport}_{int(TH*100)}.parquet')
