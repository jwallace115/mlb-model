import pandas as pd, numpy as np
d=pd.read_parquet('/tmp/p09.parquet'); d=d[d.pull_timestamp.astype(str).str.startswith('2026-09-27T15:00')]
d=d[pd.to_datetime(d.commence_time,utc=True)<'2026-09-28T02:00Z']  # Sunday games
d=d[d.market_key!='player_anytime_td']
ps=pd.read_parquet('/tmp/ps.parquet'); ps=ps[ps.season_type=='REG']
col={'player_pass_attempts':'attempts','player_pass_completions':'completions','player_pass_yds':'passing_yards','player_pass_tds':'passing_tds',
 'player_pass_interceptions':'passing_interceptions','player_rush_yds':'rushing_yards','player_rush_attempts':'carries',
 'player_receptions':'receptions','player_reception_yds':'receiving_yards'}
def imp(a): return 100/(a+100) if a>0 else -a/(-a+100)
d['pi_over']=d.over_price.apply(imp); d['pi_under']=d.under_price.apply(imp); d['q_over']=d.pi_over/(d.pi_over+d.pi_under)
key=['event_id','player_name','market_key']
hr=d[d.bookmaker=='hardrockbet_fl'][key+['home_team','away_team','commence_time','line','over_price','under_price','q_over']]
cons=d[d.bookmaker!='hardrockbet_fl'].groupby(key).agg(cons_line=('line','median'),nbooks=('bookmaker','nunique')).reset_index()
pin=d[d.bookmaker=='pinnacle'][key+['line','q_over']].rename(columns={'line':'pin_line','q_over':'pin_q_over'})
t=hr.merge(cons,on=key,how='left').merge(pin,on=key,how='left')
# history
ps['nm']=ps.player_display_name
rows=[]
for _,r in t.iterrows():
    c=col.get(r.market_key); h=ps[ps.nm==r.player_name]
    if c is None or h.empty: rows.append((np.nan,np.nan,'',np.nan,'')); continue
    v=h.sort_values('week')[c].tolist(); rows.append((np.mean(v), sum(x>r.line for x in v), ','.join(str(int(x)) for x in v), len(v), h.team.iloc[-1]))
t[['h_mean','h_over','h_vals','h_n','team']]=pd.DataFrame(rows,index=t.index)
t['mkt_edge_over']=np.where(t.cons_line.notna(), t.cons_line-t.line, 0.0)   # >0: HR line below consensus -> over value
t['pin_edge_over']=np.where(t.pin_line==t.line, t.pin_q_over-t.q_over, np.nan)
t['hist_edge_over']=(t.h_mean-t.line)/t.line.clip(lower=1)
t['game']=t.away_team.str.split().str[-1]+'@'+t.home_team.str.split().str[-1]
t.to_parquet('/tmp/props_layers.parquet')
pd.set_option('display.width',260); pd.set_option('display.max_rows',400)
# candidates where market and history agree
t['dir_mkt']=np.sign(t.mkt_edge_over.fillna(0)+t.pin_edge_over.fillna(0)*20)
t['dir_hist']=np.sign(t.hist_edge_over.fillna(0))
a=t[(t.dir_mkt!=0)&(t.dir_mkt==t.dir_hist)&(t.h_n>=2)].copy()
a['score']=t.mkt_edge_over.abs()/t.line.clip(lower=1)*3+a.hist_edge_over.abs()+a.pin_edge_over.abs().fillna(0)*5
a['h_hit']=np.where(a.dir_hist>0,a.h_over,a.h_n-a.h_over)
print(a.sort_values('score',ascending=False)[['game','team','player_name','market_key','line','cons_line','pin_line','over_price','under_price','pin_edge_over','h_vals','h_mean','h_hit','h_n','dir_mkt','score']].head(45).to_string(index=False))
