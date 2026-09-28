"""Real points per drive by start bucket, K1 definition (fixed_drive with >=1 pass/run/kneel/spike play, 2021-24 REG)."""
import pandas as pd, numpy as np
P='/home/claude/mlb-model/nfl/data/pbp/pbp_%d.parquet'
cols=['game_id','season_type','week','play_id','play_type','fixed_drive','posteam','yardline_100','posteam_score','posteam_score_post','two_point_attempt','qtr']
df=pd.concat([pd.read_parquet(P%s,columns=cols) for s in range(2021,2025)])
df=df[df.season_type=='REG']
PT={'pass','run','qb_kneel','qb_spike'}
sc=df[df.play_type.isin(PT)&(df.two_point_attempt.fillna(0)==0)].dropna(subset=['fixed_drive'])
first=sc.sort_values('play_id').groupby(['game_id','fixed_drive']).first()
# points: posteam score change over ALL rows of the drive (incl. PAT/2pt and FG rows) for that posteam
d=df.dropna(subset=['fixed_drive']).merge(first[['posteam']].reset_index().rename(columns={'posteam':'dpos'}),on=['game_id','fixed_drive'])
d=d[d.posteam==d.dpos]
pts=d.groupby(['game_id','fixed_drive']).apply(lambda x: x.posteam_score_post.max()-x.posteam_score.min())
first['pts']=pts
first=first.dropna(subset=['pts'])
def bucket(y):  # yardline_100 = yards to opponent goal
    return np.select([y>=80,y>=60,y>=40,y>=21],['own1-20','own21-40','mid41-60','opp40-21'],'opp20-1')
first['bucket']=bucket(first.yardline_100)
first=first.reset_index()
first.to_parquet('/tmp/v6a/real_drives.parquet')
ng=first.game_id.nunique()
t=first.groupby('bucket').pts.agg(['count','mean']); t['per_game']=t['count']/ng
print('games',ng,'drives/game %.3f'%(len(first)/ng),'pts/drive %.3f'%first.pts.mean(),'pts/game %.2f'%(first.pts.sum()/ng))
print(t.round(3))
