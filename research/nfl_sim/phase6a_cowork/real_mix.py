import pandas as pd, numpy as np
P='/home/claude/mlb-model/nfl/data/pbp/pbp_%d.parquet'
df=pd.concat([pd.read_parquet(P%s,columns=['game_id','season_type','fixed_drive','fixed_drive_result']) for s in range(2021,2025)]); df=df[df.season_type=='REG']
res=df.dropna(subset=['fixed_drive']).groupby(['game_id','fixed_drive']).fixed_drive_result.first()
R=pd.read_parquet('/tmp/v6a/real_drives.parquet').set_index(['game_id','fixed_drive'])
R['res']=res
B=['own1-20','own21-40','mid41-60','opp40-21','opp20-1']
print(pd.crosstab(R.bucket,R.res,normalize='index').loc[B].round(3).to_string())
print((pd.crosstab(R.bucket,R.res).loc[B]/R.reset_index().game_id.nunique()).round(3).to_string())
