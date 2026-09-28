import pandas as pd, numpy as np
P='/home/claude/mlb-model/nfl/data/pbp/pbp_%d.parquet'
cols=['game_id','season_type','play_id','timeout','timeout_team','posteam','qtr','half_seconds_remaining','game_seconds_remaining','play_type']
df=pd.concat([pd.read_parquet(P%s,columns=cols) for s in range(2021,2025)]); df=df[df.season_type=='REG'].sort_values(['game_id','play_id'])
ng=df.game_id.nunique()
# posteam at the timeout row may be blank; use next scrimmage posteam
df['nxt_pos']=df.posteam.where(df.play_type.isin(['pass','run','qb_kneel','qb_spike','punt','field_goal'])).groupby(df.game_id).bfill()
t=df[df.timeout==1].copy()
t['side']=np.where(t.timeout_team==t.nxt_pos,'off','def')
t['half']=np.where(t.qtr<=2,'H1',np.where(t.qtr<=4,'H2','OT'))
print('team timeouts/game %.2f'%(len(t)/ng))
print((t.groupby(['half','side']).size()/ng).round(2))
