import pandas as pd, numpy as np
p=pd.concat([pd.read_parquet('/tmp/ev/props09.parquet'),pd.read_parquet('/tmp/ev/props_mnf.parquet')],ignore_index=True)
p=p[p.market_key!='player_anytime_td'].dropna(subset=['over_price','under_price'])
p['ts']=pd.to_datetime(p.pull_timestamp,utc=True); p['kick']=pd.to_datetime(p.commence_time,utc=True)
p=p[(p.ts<p.kick)&(p.ts>='2026-09-27')]
imp=lambda a: np.where(a>0,100/(a+100),-a/(-a+100)); dec=lambda a: np.where(a>0,1+a/100,1+100/-a)
p['io'],p['iu']=imp(p.over_price),imp(p.under_price)
p['fo']=p.io/(p.io+p.iu)
k=['ts','event_id','market_key','player_name','line']
pin=p[p.bookmaker=='pinnacle'][k+['fo']].rename(columns={'fo':'pin_fo'})
# consensus of all non-HR books at same line (median fair)
cons=p[p.bookmaker!='hardrockbet_fl'].groupby(k).agg(cons_fo=('fo','median'),nb=('fo','size')).reset_index()
hr=p[p.bookmaker=='hardrockbet_fl'].merge(pin,on=k,how='left').merge(cons,on=k,how='left')
rows=[]
for side in ['over','under']:
    x=hr.copy(); x['side']=side
    x['dec']=dec(x[f'{side}_price'])
    x['f_pin']=x.pin_fo if side=='over' else 1-x.pin_fo
    x['f_cons']=x.cons_fo if side=='over' else 1-x.cons_fo
    rows.append(x)
h=pd.concat(rows)
h['ev_pin']=h.f_pin*h.dec-1; h['ev_cons']=h.f_cons*h.dec-1
print('HR prop sides with a Pinnacle same-line quote:',h.f_pin.notna().sum(),' with >=3 other books:',(h.nb>=3).sum())
for col in ['ev_pin','ev_cons']:
    v=h[col].dropna(); print(col,'share >=0: %.3f >=2%%: %.3f >=5%%: %.3f'%((v>=0).mean(),(v>=0.02).mean(),(v>=0.05).mean()))
# bets: first time ev_pin>=2%
key=['event_id','market_key','player_name','line','side']
b=h[h.ev_pin>=0.02].sort_values('ts').groupby(key).head(1)
# close = last Pinnacle fair before kick at same line
pc=pin.merge(p[['event_id','kick']].drop_duplicates(),on='event_id').sort_values('ts').groupby(['event_id','market_key','player_name','line']).tail(1)
pc=pc.rename(columns={'pin_fo':'pin_fo_close','ts':'ts_close'})[['event_id','market_key','player_name','line','pin_fo_close','ts_close']]
b=b.merge(pc,on=['event_id','market_key','player_name','line'],how='left')
b['f_close']=np.where(b.side=='over',b.pin_fo_close,1-b.pin_fo_close)
b['same_pull']=b.ts_close==b.ts
nb=b[~b.same_pull & b.f_close.notna()]
print('bets flagged EV>=2%% vs Pinnacle: %d; with a LATER Pinnacle close: %d'%(len(b),len(nb)))
print('mean EV at bet %.3f -> EV at Pinnacle close %.3f ; CLV>0 share %.2f'%(nb.ev_pin.mean(),(nb.f_close*nb.dec-1).mean(),((nb.f_close-nb.f_pin)>0).mean()))
print(b.groupby('market_key').size())
b.to_parquet('/tmp/ev/prop_bets.parquet')
