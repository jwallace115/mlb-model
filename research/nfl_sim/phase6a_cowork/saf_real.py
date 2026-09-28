import pandas as pd, numpy as np
P='/home/claude/mlb-model/nfl/data/pbp/pbp_%d.parquet'
cols=['game_id','season_type','play_type','yardline_100','safety','penalty','play_id']
df=pd.concat([pd.read_parquet(P%s,columns=cols) for s in range(2021,2025)]); df=df[df.season_type=='REG']
ng=df.game_id.nunique()
sc=df[df.play_type.isin(['pass','run'])]
for lo,hi,lab in [(90,94,'90-94'),(95,97,'95-97'),(98,100,'98-100')]:
    z=sc[(sc.yardline_100>=lo)&(sc.yardline_100<=hi)]
    print(lab,'snaps/game %.3f'%(len(z)/ng),'safeties',int(z.safety.sum()),'rate %.4f'%(z.safety.mean()),'saf/game %.4f'%(z.safety.sum()/ng))
print('all pass/run safeties',int(sc.safety.sum()),'/game %.4f'%(sc.safety.sum()/ng),'; all safeties',int(df.safety.sum()), df[df.safety==1].play_type.value_counts().to_dict())
