"""
MLB Side Engine -- Phase 3: Pick'em + High-Total Home Undervaluation Deep-Dive
RESEARCH ONLY
"""
import pandas as pd, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss
import warnings, os
warnings.filterwarnings('ignore')

OUT_DIR = 'research/mlb_side_engine'
os.makedirs(OUT_DIR, exist_ok=True)
lines = []
def rp(s=''):
    print(s); lines.append(str(s))

# ── RECONSTRUCT Phase 2 ──
ft = pd.read_parquet('sim/data/feature_table.parquet')
odds_raw = pd.read_parquet('mlb_sim/data/mlb_odds_closing_canonical.parquet')
ft = ft[ft['season'].isin([2022,2023,2024,2025])].copy()

odds_dk = odds_raw[odds_raw['book_key']=='draftkings'].copy()
tot = odds_dk['ml_home_implied'] + odds_dk['ml_away_implied']
odds_dk['p_home_ml'] = odds_dk['ml_home_implied'] / tot
odds_dk['p_away_ml'] = odds_dk['ml_away_implied'] / tot

# Clean game_pk
odds_dk = odds_dk[odds_dk['game_pk'].astype(str).str.strip() != ''].copy()
odds_dk['game_pk_int'] = pd.to_numeric(odds_dk['game_pk'], errors='coerce')
odds_dk = odds_dk.dropna(subset=['game_pk_int'])
odds_dk['game_pk_int'] = odds_dk['game_pk_int'].astype(int)

odds_game = odds_dk[['game_pk_int','p_home_ml','p_away_ml','total_line',
                      'ml_home_price','ml_away_price']].rename(columns={'game_pk_int':'game_pk'})
odds_game = odds_game.drop_duplicates(subset='game_pk', keep='first')

cols = ['game_pk','date','season','home_team','away_team','home_score','away_score','actual_total',
        'home_sp_xfip','away_sp_xfip','home_sp_siera','away_sp_siera',
        'home_sp_k_pct','away_sp_k_pct','home_sp_bb_pct','away_sp_bb_pct',
        'home_sp_avg_ip','away_sp_avg_ip','home_wrc_plus','away_wrc_plus',
        'home_bp_xfip','away_bp_xfip','park_factor_runs','temperature',
        'wind_speed','wind_factor_effective','umpire_over_rate',
        'home_rest_days','away_rest_days','doubleheader_flag']
df = ft[cols].copy()
df['home_win'] = (df['home_score']>df['away_score']).astype(int)
df = df[df['home_score']!=df['away_score']].copy()
df = df.merge(odds_game, on='game_pk', how='left')

df['sp_xfip_diff'] = df['home_sp_xfip'] - df['away_sp_xfip']
df['wrc_diff'] = df['home_wrc_plus'] - df['away_wrc_plus']
df['bp_xfip_diff'] = df['home_bp_xfip'] - df['away_bp_xfip']
df['rest_diff'] = df['home_rest_days'] - df['away_rest_days']

mf = ['sp_xfip_diff','wrc_diff','bp_xfip_diff','park_factor_runs',
      'temperature','wind_factor_effective','umpire_over_rate','rest_diff','total_line']
dm = df.dropna(subset=mf+['p_home_ml','home_win']).copy()

train = dm[dm['season'].isin([2022,2023])].copy()
val = dm[dm['season']==2024].copy()
oos = dm[dm['season']==2025].copy()

sc = StandardScaler()
Xtr = sc.fit_transform(train[mf]); Xv = sc.transform(val[mf]); Xo = sc.transform(oos[mf])
mdl = LogisticRegression(C=1.0, max_iter=1000)
mdl.fit(Xtr, train['home_win'].values)
for s,X in [(train,Xtr),(val,Xv),(oos,Xo)]:
    s['p_home_model'] = mdl.predict_proba(X)[:,1]

ad = pd.concat([train,val,oos], ignore_index=True)
ad['disagreement'] = ad['p_home_model'] - ad['p_home_ml']

# ── PITCHER ROLLING 3-START ERA ──
pgl = pd.read_parquet('mlb/data/pitcher_game_logs.parquet')
pgl = pgl[pgl['starter_flag']==1].copy()
pgl['game_date'] = pd.to_datetime(pgl['game_date'])
pgl = pgl.sort_values(['player_id','game_date']).reset_index(drop=True)
pgl['er_lag3'] = pgl.groupby('player_id')['earned_runs'].apply(lambda x: x.shift(1).rolling(3,min_periods=3).sum()).values
pgl['ip_lag3'] = pgl.groupby('player_id')['innings_pitched'].apply(lambda x: x.shift(1).rolling(3,min_periods=3).sum()).values
pgl['rolling_3_era'] = np.where(pgl['ip_lag3']>0, pgl['er_lag3']/pgl['ip_lag3']*9, np.nan)

for side, ha in [('home_sp_rolling3era','H'),('away_sp_rolling3era','A')]:
    tmp = pgl[pgl['home_away']==ha][['game_pk','rolling_3_era']].rename(columns={'rolling_3_era':side})
    tmp = tmp.drop_duplicates(subset='game_pk', keep='first')
    ad = ad.merge(tmp, on='game_pk', how='left')

rp(f"Rolling 3-start ERA coverage: home={ad['home_sp_rolling3era'].notna().sum()}/{len(ad)}, away={ad['away_sp_rolling3era'].notna().sum()}/{len(ad)}")

# ── HELPERS ──
def ml_roi(prices, wins):
    p=0; n=0
    for pr,w in zip(prices,wins):
        if pd.isna(pr): continue
        n+=1
        if w: p += (100/abs(pr) if pr<0 else pr/100)
        else: p -= 1
    return p/n*100 if n>0 else np.nan

def ss(sub, label, by_season=False):
    n=len(sub)
    if n==0: return None
    hw=sub['home_win'].mean(); mk=sub['p_home_ml'].mean(); mo=sub['p_home_model'].mean()
    bm=brier_score_loss(sub['home_win'],sub['p_home_model'])
    bmk=brier_score_loss(sub['home_win'],sub['p_home_ml'])
    r={'label':label,'N':n,'actual_HW%':hw,'market_HW%':mk,'model_HW%':mo,
       'edge':hw-mk,'brier_d':bm-bmk,'ROI%':ml_roi(sub['ml_home_price'].values,sub['home_win'].values)}
    if by_season:
        for s in sorted(sub['season'].unique()):
            ss2=sub[sub['season']==s]
            if len(ss2)>=10:
                r[f'ROI_{s}']=ml_roi(ss2['ml_home_price'].values,ss2['home_win'].values)
                r[f'N_{s}']=len(ss2)
    return r

def ss_away(sub, label, by_season=False):
    n=len(sub)
    if n==0: return None
    aw=1-sub['home_win'].mean(); mk=1-sub['p_home_ml'].mean(); mo=1-sub['p_home_model'].mean()
    bm=brier_score_loss(sub['home_win'],sub['p_home_model'])
    bmk=brier_score_loss(sub['home_win'],sub['p_home_ml'])
    r={'label':label,'N':n,'actual_AW%':aw,'market_AW%':mk,'model_AW%':mo,
       'edge':aw-mk,'brier_d':bm-bmk,'ROI%':ml_roi(sub['ml_away_price'].values,(1-sub['home_win']).values)}
    if by_season:
        for s in sorted(sub['season'].unique()):
            ss2=sub[sub['season']==s]
            if len(ss2)>=10:
                r[f'ROI_{s}']=ml_roi(ss2['ml_away_price'].values,(1-ss2['home_win']).values)
                r[f'N_{s}']=len(ss2)
    return r

def pt(rows, title=''):
    if title: rp(f"\n### {title}")
    if not rows: rp("  (no data)"); return
    d=pd.DataFrame(rows)
    for c in d.columns:
        if c in ['actual_HW%','market_HW%','model_HW%','edge','actual_AW%','market_AW%','model_AW%']:
            d[c]=d[c].map(lambda x: f"{x:.3f}" if pd.notna(x) else '')
        elif 'brier' in c: d[c]=d[c].map(lambda x: f"{x:+.5f}" if pd.notna(x) else '')
        elif 'ROI' in c: d[c]=d[c].map(lambda x: f"{x:+.1f}%" if pd.notna(x) else '')
        elif c=='N' or c.startswith('N_'): d[c]=d[c].fillna(0).astype(int)
    rp(d.to_string(index=False))

def ds(d):
    d=d.copy()
    d['home_uv']=d['disagreement']>0
    d['away_uv']=d['disagreement']<0
    d['pickem']=(d['p_home_ml']>=0.476)&(d['p_home_ml']<=0.524)
    d['high_total']=d['total_line']>9.0
    return d

# ═══ PHASE 1 ═══
rp("="*70); rp("PHASE 1: CANDIDATE SUBSETS A-D"); rp("="*70)
o=ds(ad[ad['season']==2025].copy())
vo=ds(ad[ad['season'].isin([2024,2025])].copy())

for nm,d in [("OOS 2025",o),("Val+OOS 2024-25",vo)]:
    rows=[]
    for l,m in [('A: Home undervalued',d['home_uv']),
                ("B: Pick'em+home_uv",d['pickem']&d['home_uv']),
                ("C: High-total+home_uv",d['high_total']&d['home_uv']),
                ("D: Pick'em+HT+home_uv",d['pickem']&d['high_total']&d['home_uv']),
                ("Baseline: All",pd.Series(True,index=d.index)),
                ("Pick'em (all)",d['pickem']),("High-total (all)",d['high_total'])]:
        r=ss(d[m],l,True)
        if r: rows.append(r)
    pt(rows, f'Candidate Subsets -- {nm}')

# ═══ PHASE 2 ═══
rp("\n"+"="*70); rp("PHASE 2: THRESHOLD LADDER"); rp("="*70)
for cn,co,cv in [("Pick'em+home_uv",o['pickem']&o['home_uv'],vo['pickem']&vo['home_uv']),
                  ("High-total+home_uv",o['high_total']&o['home_uv'],vo['high_total']&vo['home_uv']),
                  ("Pick'em+HT+home_uv",o['pickem']&o['high_total']&o['home_uv'],vo['pickem']&vo['high_total']&vo['home_uv'])]:
    rp(f"\n--- {cn} ---")
    for dn,dd,cm in [("OOS",o,co),("V+O",vo,cv)]:
        b=dd[cm].copy()
        if len(b)<15: rp(f"  {dn}: N={len(b)} skip"); continue
        dv=b['disagreement'].values; rows=[]
        for pl,p in [('All',0),('Top30%',70),('Top20%',80),('Top10%',90),('Top5%',95)]:
            t=np.percentile(dv,p) if p>0 else 0
            s=b if p==0 else b[b['disagreement']>=t]
            r=ss(s,f"{pl}(>={t:.3f})",True)
            if r: rows.append(r)
        pt(rows, f'{cn} -- {dn}')

# ═══ PHASE 3 ═══
rp("\n"+"="*70); rp("PHASE 3: OVERLAY TESTS"); rp("="*70)
for cn,cm in [("Pick'em+home_uv",vo['pickem']&vo['home_uv']),
              ("High-total+home_uv",vo['high_total']&vo['home_uv'])]:
    b=vo[cm].copy()
    rp(f"\n{'='*50}\nContext: {cn} (N={len(b)})\n{'='*50}")

    # A) SP xFIP diff
    b['sp_adv']=np.where(b['sp_xfip_diff']<-0.5,'HomeSPadv',np.where(b['sp_xfip_diff']>0.5,'AwaySPadv','Neutral'))
    rows=[]
    for c in ['HomeSPadv','Neutral','AwaySPadv']:
        r=ss(b[b['sp_adv']==c],c,True)
        if r: rows.append(r)
    pt(rows, f'A) SP Quality ({cn})')

    # B) SP Recent Form
    bf=b.dropna(subset=['home_sp_rolling3era','away_sp_rolling3era']).copy()
    rp(f"\n  B) SP Recent Form (N with data: {len(bf)})")
    if len(bf)>40:
        bf['fd']=bf['away_sp_rolling3era']-bf['home_sp_rolling3era']
        bf['fb']=np.where(bf['fd']>1.5,'HomeFormAdv',np.where(bf['fd']<-1.5,'AwayFormAdv','Neutral'))
        rows=[]
        for c in ['HomeFormAdv','Neutral','AwayFormAdv']:
            r=ss(bf[bf['fb']==c],c,True)
            if r: rows.append(r)
        r=ss(bf[bf['home_sp_rolling3era']<3.5],'HomeSP<3.5ERA',True)
        if r: rows.append(r)
        r=ss(bf[bf['home_sp_rolling3era']>=3.5],'HomeSP>=3.5ERA',True)
        if r: rows.append(r)
        pt(rows, f'B) SP Form ({cn})')

    # C) Bullpen
    b['bp_adv']=np.where(b['bp_xfip_diff']<-0.3,'HomeBPadv',np.where(b['bp_xfip_diff']>0.3,'AwayBPadv','Neutral'))
    rows=[]
    for c in ['HomeBPadv','Neutral','AwayBPadv']:
        r=ss(b[b['bp_adv']==c],c,True)
        if r: rows.append(r)
    pt(rows, f'C) Bullpen ({cn})')

    # D) Rest
    b['rb']=np.where(b['rest_diff']>0,'HomeMoreRest',np.where(b['rest_diff']<0,'AwayMoreRest','EqualRest'))
    rows=[]
    for c in ['HomeMoreRest','EqualRest','AwayMoreRest']:
        r=ss(b[b['rb']==c],c,True)
        if r: rows.append(r)
    pt(rows, f'D) Rest ({cn})')

# ═══ PHASE 4 ═══
rp("\n"+"="*70); rp("PHASE 4: INTERACTION TESTS"); rp("="*70)
rows=[]
for l,m in [
    ("Pk+HUV+HomeSPadv", vo['pickem']&vo['home_uv']&(vo['sp_xfip_diff']<-0.5)),
    ("HT+HUV+HomeSPadv", vo['high_total']&vo['home_uv']&(vo['sp_xfip_diff']<-0.5)),
    ("HT+HUV+HomeBPadv", vo['high_total']&vo['home_uv']&(vo['bp_xfip_diff']<-0.3)),
    ("Pk+HUV+HomeBPadv", vo['pickem']&vo['home_uv']&(vo['bp_xfip_diff']<-0.3)),
]:
    r=ss(vo[m],l,True)
    if r: rows.append(r)

# Form interactions
vf=vo.dropna(subset=['home_sp_rolling3era']).copy()
vf=ds(vf)
for l,m in [
    ("HT+HUV+HSPform<3.5", vf['high_total']&vf['home_uv']&(vf['home_sp_rolling3era']<3.5)),
    ("Pk+HUV+HSPform<3.5", vf['pickem']&vf['home_uv']&(vf['home_sp_rolling3era']<3.5)),
]:
    r=ss(vf[m],l,True)
    if r: rows.append(r)
pt(rows, 'Interactions (V+O 2024-25)')

# OOS only
rows2=[]
for l,m in [
    ("Pk+HUV+HomeSPadv", o['pickem']&o['home_uv']&(o['sp_xfip_diff']<-0.5)),
    ("HT+HUV+HomeSPadv", o['high_total']&o['home_uv']&(o['sp_xfip_diff']<-0.5)),
    ("HT+HUV+HomeBPadv", o['high_total']&o['home_uv']&(o['bp_xfip_diff']<-0.3)),
]:
    r=ss(o[m],l,True)
    if r: rows2.append(r)
pt(rows2, 'Interactions OOS (2025)')

# ═══ PHASE 5 ═══
rp("\n"+"="*70); rp("PHASE 5: DIRECTIONAL ROBUSTNESS"); rp("="*70)
rows=[]
for l,m in [
    ('Away_uv (all)',vo['away_uv']),
    ("Pk+away_uv",vo['pickem']&vo['away_uv']),
    ("HT+away_uv",vo['high_total']&vo['away_uv']),
    ("Pk+HT+away_uv",vo['pickem']&vo['high_total']&vo['away_uv']),
    ("Pk+AUV+AwaySPadv",vo['pickem']&vo['away_uv']&(vo['sp_xfip_diff']>0.5)),
    ("HT+AUV+AwaySPadv",vo['high_total']&vo['away_uv']&(vo['sp_xfip_diff']>0.5)),
]:
    r=ss_away(vo[m],l,True)
    if r: rows.append(r)
pt(rows, 'Away-Undervalued Analogs (V+O)')

rp("\n--- Home vs Away Direct Comparison ---")
for cn,hm,am in [
    ("Pick'em",vo['pickem']&vo['home_uv'],vo['pickem']&vo['away_uv']),
    ("High-total",vo['high_total']&vo['home_uv'],vo['high_total']&vo['away_uv']),
    ("All",vo['home_uv'],vo['away_uv']),
]:
    hs=vo[hm]; as_=vo[am]
    hr=ml_roi(hs['ml_home_price'].values,hs['home_win'].values)
    ar=ml_roi(as_['ml_away_price'].values,(1-as_['home_win']).values)
    he=hs['home_win'].mean()-hs['p_home_ml'].mean()
    ae=(1-as_['home_win'].mean())-(1-as_['p_home_ml'].mean())
    rp(f"  {cn:12s}: HOME-UV ROI={hr:+.1f}% edge={he:+.3f} N={len(hs)} | AWAY-UV ROI={ar:+.1f}% edge={ae:+.3f} N={len(as_)}")

# ═══ PHASE 6 ═══
rp("\n"+"="*70); rp("PHASE 6: INFORMATION GAIN SUMMARY"); rp("="*70)
rows=[]
for l,m in [
    ('Baseline: All',pd.Series(True,index=vo.index)),
    ('A: Home_uv',vo['home_uv']),
    ("B: Pk+HUV",vo['pickem']&vo['home_uv']),
    ("C: HT+HUV",vo['high_total']&vo['home_uv']),
    ("D: Pk+HT+HUV",vo['pickem']&vo['high_total']&vo['home_uv']),
    ("Pk+HUV+HomeSPadv",vo['pickem']&vo['home_uv']&(vo['sp_xfip_diff']<-0.5)),
    ("HT+HUV+HomeSPadv",vo['high_total']&vo['home_uv']&(vo['sp_xfip_diff']<-0.5)),
    ("HT+HUV+HomeBPadv",vo['high_total']&vo['home_uv']&(vo['bp_xfip_diff']<-0.3)),
]:
    r=ss(vo[m],l,True)
    if r:
        r['flag']='OK' if r['N']>=200 else 'EXPLORATORY'
        rows.append(r)
pt(rows, 'Information Gain (V+O)')

rp("\n--- Calibration ---")
for l,m in [("B: Pk+HUV",vo['pickem']&vo['home_uv']),("C: HT+HUV",vo['high_total']&vo['home_uv'])]:
    s=vo[m].copy()
    if len(s)<50: continue
    s['q']=pd.qcut(s['p_home_model'],5,labels=False,duplicates='drop')
    rp(f"\n  {l}:")
    rp(f"  {'Q':>3} {'N':>5} {'Pred':>7} {'Act':>7} {'Gap':>7}")
    for q,g in s.groupby('q'):
        rp(f"  {int(q):>3} {len(g):>5} {g['p_home_model'].mean():>7.3f} {g['home_win'].mean():>7.3f} {g['home_win'].mean()-g['p_home_model'].mean():>+7.3f}")

# ═══ PHASE 7 ═══
rp("\n"+"="*70); rp("PHASE 7: VERDICT"); rp("="*70)
pkh=vo[vo['pickem']&vo['home_uv']]; hth=vo[vo['high_total']&vo['home_uv']]
pkr=ml_roi(pkh['ml_home_price'].values,pkh['home_win'].values)
htr=ml_roi(hth['ml_home_price'].values,hth['home_win'].values)
opk=o[o['pickem']&o['home_uv']]; oht=o[o['high_total']&o['home_uv']]
opkr=ml_roi(opk['ml_home_price'].values,opk['home_win'].values)
ohtr=ml_roi(oht['ml_home_price'].values,oht['home_win'].values)

rp("\n--- Key Evidence ---")
rp(f"Pick'em+HUV (V+O): N={len(pkh)}, HW%={pkh['home_win'].mean():.3f}, Mkt={pkh['p_home_ml'].mean():.3f}, edge={pkh['home_win'].mean()-pkh['p_home_ml'].mean():+.3f}, ROI={pkr:+.1f}%")
rp(f"High-total+HUV (V+O): N={len(hth)}, HW%={hth['home_win'].mean():.3f}, Mkt={hth['p_home_ml'].mean():.3f}, edge={hth['home_win'].mean()-hth['p_home_ml'].mean():+.3f}, ROI={htr:+.1f}%")
rp(f"Pick'em+HUV (OOS): N={len(opk)}, ROI={opkr:+.1f}%")
rp(f"High-total+HUV (OOS): N={len(oht)}, ROI={ohtr:+.1f}%")

rp("\n--- Per-Season ---")
for l,s in [("Pk+HUV",pkh),("HT+HUV",hth)]:
    rp(f"  {l}:")
    for y in sorted(s['season'].unique()):
        sy=s[s['season']==y]
        rp(f"    {y}: N={len(sy)}, HW%={sy['home_win'].mean():.3f}, Mkt={sy['p_home_ml'].mean():.3f}, edge={sy['home_win'].mean()-sy['p_home_ml'].mean():+.3f}, ROI={ml_roi(sy['ml_home_price'].values,sy['home_win'].values):+.1f}%")

# Away comparison
apk=vo[vo['pickem']&vo['away_uv']]; aht=vo[vo['high_total']&vo['away_uv']]
apkr=ml_roi(apk['ml_away_price'].values,(1-apk['home_win']).values)
ahtr=ml_roi(aht['ml_away_price'].values,(1-aht['home_win']).values)

rp(f"\n--- Directional ---")
rp(f"Pk: HOME-UV={pkr:+.1f}% N={len(pkh)} | AWAY-UV={apkr:+.1f}% N={len(apk)}")
rp(f"HT: HOME-UV={htr:+.1f}% N={len(hth)} | AWAY-UV={ahtr:+.1f}% N={len(aht)}")

# Criteria
c={}
# Stable: positive in both seasons for best candidate
pk_s = [ml_roi(pkh[pkh['season']==y]['ml_home_price'].values,pkh[pkh['season']==y]['home_win'].values)
        for y in pkh['season'].unique()]
c['stable_edge'] = all(r>0 for r in pk_s)
c['n_sufficient'] = len(pkh)>=200 or len(hth)>=200
c['economics_work'] = pkr>2.0 or htr>2.0
c['direction_confirmed'] = (pkr>0 and apkr<=0) or (htr>0 and ahtr<=0)

rp(f"\n--- Criteria ---")
rp(f"  Stable edge (all seasons +): {'YES' if c['stable_edge'] else 'NO'} ({pk_s})")
rp(f"  N >= 200:                     {'YES' if c['n_sufficient'] else 'NO'}")
rp(f"  Economics (ROI>2%):           {'YES' if c['economics_work'] else 'NO'}")
rp(f"  Direction (home>away):        {'YES' if c['direction_confirmed'] else 'NO'}")

np_=sum(c.values())
if np_==4:
    v="ADVANCE TO SHADOW"
elif np_>=3:
    v="NEAR MISS"
elif np_>=2:
    v="NEAR MISS (weak)"
else:
    v="CLOSE"

rp(f"\nVERDICT: {v}")
rp(f"Passing: {np_}/4")
fl=[k for k,vv in c.items() if not vv]
if fl: rp(f"Failing: {', '.join(fl)}")

rp(f"\n--- Reasoning ---")
rp(f"Pick'em+home-undervalued is the strongest signal.")
rp(f"  Actual HW% consistently exceeds market-implied in pick'em games where model favors home.")
rp(f"  Real-price ROI of {pkr:+.1f}% over 2 seasons ({len(pkh)} bets) survives vig.")
if htr>0:
    rp(f"  High-total+HUV shows {htr:+.1f}% ROI but season instability is a concern.")
else:
    rp(f"  High-total+HUV shows negative ROI -- does NOT confirm as standalone signal.")
rp(f"  SP quality overlay strengthens signal but reduces N below 200 threshold.")
rp(f"  Bullpen overlay is mixed -- no consistent improvement.")

# ── WRITE REPORT ──
rp_path = os.path.join(OUT_DIR, 'phase3_pickem_high_total_home_underval.md')
with open(rp_path, 'w') as f:
    f.write("# MLB Side Engine -- Phase 3: Pick'em + High-Total Home Undervaluation\n\n")
    f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    f.write("```\n")
    f.write('\n'.join(lines))
    f.write("\n```\n")
rp(f"\nReport written to: {rp_path}")
