import pandas as pd, numpy as np
pd.set_option('display.width',250)
G=pd.read_parquet('/tmp/tot/games_feat.parquet')
M=G[(G.home_n_prior>=3)&(G.away_n_prior>=3)].copy()   # week-4+ style: both teams have 3+ prior games
D=M[M.disc]
q=lambda col,p: np.nanquantile(pd.concat([D['home_'+col],D['away_'+col]]),p)
ohi,olo=q('off_epa_pit',2/3),q('off_epa_pit',1/3); dlo,dhi=q('def_epa_pit',1/3),q('def_epa_pit',2/3)  # low def_epa = good defense
phi,plo=q('plays_pit',2/3),q('plays_pit',1/3)
print('cutoffs from discovery only: off top>%.3f bottom<%.3f | def good<%.3f bad>%.3f | pace fast>%.1f slow<%.1f'%(ohi,olo,dlo,dhi,phi,plo))
def gt(c,x): return (M['home_'+c]>x)&(M['away_'+c]>x)
def lt(c,x): return (M['home_'+c]<x)&(M['away_'+c]<x)
B={
 'F1 both offenses top third':gt('off_epa_pit',ohi),
 'F1 both offenses bottom third':lt('off_epa_pit',olo),
 'F2 both defenses top third (good)':lt('def_epa_pit',dlo),
 'F2 both defenses bottom third (bad)':gt('def_epa_pit',dhi),
 'F3 top-third O vs top-third D (either way)':((M.home_off_epa_pit>ohi)&(M.away_def_epa_pit<dlo))|((M.away_off_epa_pit>ohi)&(M.home_def_epa_pit<dlo)),
 'F4 both fast pace':gt('plays_pit',phi),
 'F4 both slow pace':lt('plays_pit',plo),
 'F5 line < 40':M.total_line<40,'F5 line 40-44.5':M.total_line.between(40,44.5),'F5 line 45-48.5':M.total_line.between(45,48.5),'F5 line 49+':M.total_line>=49,
 'F6 |spread| >= 7':M.spread_line.abs()>=7,'F6 |spread| < 3':M.spread_line.abs()<3,
 'F7 dome/closed':M.roof.isin(['dome','closed']),'F7 outdoors':M.roof.isin(['outdoors','open']),
 'F8 divisional':M.div_game==1,'F8 non-divisional':M.div_game==0,
 'F9 either team new QB':M.home_qb_new.fillna(False)|M.away_qb_new.fillna(False),
 'F10 ref prior over-rate >= 0.55 (n>=30)':(M.ref_n>=30)&(M.ref_over>=0.55),'F10 ref prior over-rate <= 0.45 (n>=30)':(M.ref_n>=30)&(M.ref_over<=0.45),
 'F11 weeks 4-9':M.week.between(4,9),'F11 weeks 10-14':M.week.between(10,14),'F11 weeks 15-18':M.week>=15,
 'F12 primetime (Thu/Mon or >=20:00)':M.weekday.isin(['Thursday','Monday'])|(M.gametime>='20:00'),
}
def stats(x):
    n=len(x); 
    if n==0: return dict(n=0)
    ov=(x.miss>0).mean(); se=np.sqrt(0.25/n)
    return dict(n=n,bias=x.miss.mean(),over=ov,z=(ov-0.5)/se,sd=x.miss.std(),mae=x.miss.abs().mean())
out=[]
allD=stats(M[M.disc]); allV=stats(M[~M.disc])
for k,m in B.items():
    d=stats(M[m & M.disc]); v=stats(M[m & ~M.disc])
    out.append({'bucket':k,'n_d':d['n'],'over_d':d.get('over'),'z_d':d.get('z'),'bias_d':d.get('bias'),'sd_d':d.get('sd'),'n_v':v['n'],'over_v':v.get('over'),'z_v':v.get('z'),'bias_v':v.get('bias'),'sd_v':v.get('sd')})
o=pd.DataFrame(out)
print('ALL discovery n=%d over %.3f bias %+.2f sd %.1f | validation n=%d over %.3f bias %+.2f sd %.1f'%(allD['n'],allD['over'],allD['bias'],allD['sd'],allV['n'],allV['over'],allV['bias'],allV['sd']))
print(o.round(3).to_string(index=False))
o.to_csv('/tmp/tot/buckets.csv',index=False)
