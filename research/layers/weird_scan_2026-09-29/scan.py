import pandas as pd, numpy as np
pd.set_option('display.width',250); pd.set_option('display.max_rows',200)
G=pd.read_parquet('/tmp/weird/G.parquet'); P=pd.read_parquet('/tmp/weird/props_all.parquet')
D23=lambda df: df.season==2023
res=[]
def z(h,p):  # hits vs expected probability
    n=len(h); return (h.mean()-p.mean())/np.sqrt((p*(1-p)).sum())*n if n else np.nan
def zrate(h,p0=0.5): n=len(h); return (h.mean()-p0)/np.sqrt(p0*(1-p0)/n) if n else np.nan
def resid_test(name,X,ycol,base,outcome):
    d=G.assign(X=X).dropna(subset=['X',ycol,outcome]); dd=d[D23(d)]
    b=np.polyfit(dd.X,dd[ycol],1); d['r']=np.polyval(b,d.X)-d[ycol]   # >0 : props imply MORE than the line
    cuts=np.quantile(d[D23(d)].r,[1/3,2/3]); d['t']=np.digitize(d.r,cuts)
    for t,lab in enumerate(['props imply LESS','middle','props imply MORE']):
        a=d[(d.t==t)&D23(d)][outcome]; v=d[(d.t==t)&~D23(d)][outcome]
        res.append(dict(test=name,cell=lab,n_d=len(a),rate_d=a.mean(),z_d=zrate(a),n_v=len(v),rate_v=v.mean(),z_v=zrate(v)))
Gs=G
X_yds=G.home_qb_pyds+G.away_qb_pyds+G.home_rush_yds_sum+G.away_rush_yds_sum
resid_test('T1 prop yards (QB pass + all rush) vs total -> OVER',X_yds,'total_line',None,'over')
X_td=(G.home_qb_td_line-0.5+G.home_qb_td_over_p)+(G.away_qb_td_line-0.5+G.away_qb_td_over_p)
resid_test('T2 QB pass-TD props vs total -> OVER',X_td,'total_line',None,'over')
resid_test('T3 receiving yards props vs total -> OVER',G.home_rec_yds_sum+G.away_rec_yds_sum,'total_line',None,'over')
resid_test('T4 both RB1 carries lines vs total -> OVER',G.home_rb1_ratt+G.away_rb1_ratt,'total_line',None,'over')
resid_test('S1 RB1 carries diff (home-away) vs spread -> HOME COVER',G.home_rb1_ratt-G.away_rb1_ratt,'spread_line',None,'home_cover')
resid_test('S2 QB pass att diff (away-home) vs spread -> HOME COVER',G.away_qb_patt-G.home_qb_patt,'spread_line',None,'home_cover')
resid_test('S3 QB pass yds diff (home-away) vs spread -> HOME COVER',G.home_qb_pyds-G.away_qb_pyds,'spread_line',None,'home_cover')
resid_test('S4 rush yds diff (home-away) vs spread -> HOME COVER',G.home_rush_yds_sum-G.away_rush_yds_sum,'spread_line',None,'home_cover')
# props: line level quintiles and juice buckets, outcome = over hit vs de-vigged expectation
P['resid']=P.hit_over-P.devig_over
for fam,f in P.groupby('family'):
    cuts=np.quantile(f[f.season==2023].line,[.2,.4,.6,.8]); f=f.assign(q=np.digitize(f.line,cuts))
    for q in range(5):
        a=f[(f.q==q)&(f.season==2023)]; v=f[(f.q==q)&(f.season==2024)]
        lo=f[f.q==q].line.min(); hi=f[f.q==q].line.max()
        res.append(dict(test=f'P1 {fam} line quintile',cell=f'{lo:g}-{hi:g}',n_d=len(a),rate_d=a.hit_over.mean(),z_d=z(a.hit_over,a.devig_over),n_v=len(v),rate_v=v.hit_over.mean(),z_v=z(v.hit_over,v.devig_over),exp_d=a.devig_over.mean(),exp_v=v.devig_over.mean()))
    for lab,(lo,hi) in {'over juiced (fair>0.55)':(0.55,1),'near even':(0.45,0.55),'under juiced (fair<0.45)':(0,0.45)}.items():
        a=f[(f.devig_over>=lo)&(f.devig_over<hi)&(f.season==2023)]; v=f[(f.devig_over>=lo)&(f.devig_over<hi)&(f.season==2024)]
        res.append(dict(test=f'P2 {fam} juice',cell=lab,n_d=len(a),rate_d=a.hit_over.mean(),z_d=z(a.hit_over,a.devig_over),n_v=len(v),rate_v=v.hit_over.mean(),z_v=z(v.hit_over,v.devig_over),exp_d=a.devig_over.mean(),exp_v=v.devig_over.mean()))
R=pd.DataFrame(res)
R['survives']=(R.z_d.abs()>=2.58)&(np.sign(R.z_d)==np.sign(R.z_v))&(R.z_v.abs()>=1.65)
print('cells tested:',len(R),' discovery |z|>=2.58:',(R.z_d.abs()>=2.58).sum(),' survivors:',R.survives.sum())
print(R.round(3).to_string(index=False))
R.to_csv('/tmp/weird/scan_results.csv',index=False)
