import numpy as np, pandas as pd
from scipy.stats import norm, binom
g=pd.read_parquet('/tmp/mnf/rbcar.parquet')
rng=np.random.default_rng(1); N=200000
m=rng.normal(3.5,13.5,N)  # PHI margin, market-implied mean
# team RB carries: sample from real games with a similar own margin (+-3), plus team adjustment
gm=g.margin.values; car=g.rb_car.values
order=np.argsort(gm); gm_s=gm[order]; car_s=car[order]
def draw(own_margin, adj):
    lo=np.searchsorted(gm_s,own_margin-3); hi=np.searchsorted(gm_s,own_margin+3,side='right')
    idx=lo+(rng.random(len(own_margin))*(hi-lo)).astype(int)
    return np.clip(car_s[np.minimum(idx,len(car_s)-1)]+adj,0,None).round().astype(int)
chi=draw(-m,+3.0); phi=draw(m,0.0)
for sh,lab in [(0.63,'Swift O14.5'),(0.37,'Monangai O9.5')]:
    line=14.5 if 'Swift' in lab else 9.5
    p=1-binom.cdf(np.floor(line),chi,sh); print(lab,'overall %.3f'%p.mean(),' | PHI wins by 7+: %.3f  close/CHI ahead: %.3f'%(p[m>=7].mean(),p[m<7].mean()))
for sh in (0.65,0.70,0.75):
    p=binom.cdf(17,phi,sh); print('Barkley U17.5 share',sh,'overall %.3f | PHI by 7+: %.3f  else %.3f'%(p.mean(),p[m>=7].mean(),p[m<7].mean()))
print('P(PHI by 7+) %.2f'%(m>=7).mean())
# joint of the three, same draws
s=1-binom.cdf(14,chi,0.63); mo=1-binom.cdf(9,chi,0.37); b=binom.cdf(17,phi,0.70)
# approximate independent share draws within game
u1,u2,u3=rng.random((3,N)); hit=(u1<s)&(u2<mo)&(u3<b)
print('joint Swift&Monangai&Barkley %.3f vs product of marginals %.3f'%(hit.mean(), s.mean()*mo.mean()*b.mean()))
sb=(u1<s)&(u3<b); print('Swift&Barkley joint %.3f'%sb.mean())
for k in (0.62,):
  j4=sb.mean()*k*0.53; j3=sb.mean()*k
  for lab,j in (('3-leg Swift/Barkley/Keenum',j3),('4-leg +under',j4)):
    print(lab,'joint %.3f  boosted breakeven shown price +%.0f'%(j,100*((1/j-1)/1.25)))
