import pandas as pd, numpy as np, sys
ids=[l.strip() for l in open('/home/claude/wt6a/research/nfl_sim/phase5z_sample.txt') if l.strip()]
R=pd.read_parquet('/tmp/v6a/real_drives.parquet')
def bucket(y): return np.select([y>=80,y>=60,y>=40,y>=21],['own1-20','own21-40','mid41-60','opp40-21'],'opp20-1')
B=['own1-20','own21-40','mid41-60','opp40-21','opp20-1']
out={}
for tag in ['smain','s6a']:
    T=pd.read_parquet(f'/tmp/v6a/{tag}_team.parquet').reset_index(drop=True); D=pd.read_parquet(f'/tmp/v6a/{tag}_drives.parquet').reset_index(drop=True)
    ng=len(T)  # sim-games (200 games x 100 sims)
    print(f'==== {tag}: sim-games {ng}  plays {T.plays.mean():.2f} drives {T.drives.mean():.2f} pts/team {(T.home_score+T.away_score).mean()/2:.2f} saf/game {T.ev_safeties.mean():.4f}')
    # zones
    z=T[['vz90','vz95','vz98']].mean(); print('  zone snaps/game sim', z.round(3).to_dict())
    for c in ['saf_pre','saf_sack','saf_rush']:
        if c in T: print('  ',c, round(T[c].mean(),4))
    if 'ev_to_off' in T: print('  timeouts/game off %.2f def %.2f'%(T.ev_to_off.mean(),T.ev_to_def.mean()))
    D['bucket']=bucket(D.start_yardline)
    for scope,RR in [('sample',R[R.game_id.isin(ids)]),('all1087',R)]:
        rg=RR.game_id.nunique()
        rc=RR.groupby('bucket').size()/rg; rp=RR.groupby('bucket').pts.mean()
        sc=D.groupby('bucket').size()/ng; sp=D.groupby('bucket').points.mean()
        t=pd.DataFrame({'real_dpg':rc,'sim_dpg':sc,'real_ppd':rp,'sim_ppd':sp}).loc[B]
        real_pts=(rc*rp).sum(); sim_pts=(sc*sp).sum()
        mix=((sc-rc)*rp).sum(); eff=(rc*(sp-rp)).sum(); inter=((sc-rc)*(sp-rp)).sum()
        print(f'  [{scope}] real drives/g {rc.sum():.2f} sim {sc.sum():.2f} | off pts/game real {real_pts:.2f} sim {sim_pts:.2f} gap {sim_pts-real_pts:+.2f}')
        print(f'    START MIX {mix:+.2f}  EFFICIENCY {eff:+.2f}  interaction {inter:+.2f}  sum {mix+eff+inter:+.2f}')
        print(t.round(3).to_string())
        out[(tag,scope)]=t
    # sim drive outcome mix by bucket
    print(pd.crosstab(D.bucket,D.result,normalize='index').loc[B].round(3).to_string())
