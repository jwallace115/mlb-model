import sys, time, importlib.util, pandas as pd, contextlib, io
WT=sys.argv[1]; s=int(sys.argv[3])
spec=importlib.util.spec_from_file_location("O", sys.argv[2]); O=importlib.util.module_from_spec(spec); sys.path.insert(0,WT); spec.loader.exec_module(O)
from pathlib import Path
O.ROOT=Path(WT); O.EVENTS_DIR=O.ROOT/"nhl/data/sim/events"; O.BOX_DIR=O.ROOT/"nhl/cache"; O.XG_PATH=O.ROOT/"nhl/data/sim/xg_v2.json"
g=O.get_game_info([s])
sh=pd.read_parquet(O.EVENTS_DIR/f"season={s}"/"shots.parquet").merge(g[["game_id","date","season"]],on="game_id",how="left")
st=pd.read_parquet(O.EVENTS_DIR/f"season={s}"/"state_time.parquet").merge(g[["game_id","date","season"]],on="game_id",how="left")
t0=time.time()
with contextlib.redirect_stdout(io.StringIO()):
    old=O.build_game_stats(g,sh,st,O.load_xg_model())
old.to_parquet(f"{sys.argv[4]}/tgs_old_{s}.parquet",index=False); print(s,"rows",len(old),"s",round(time.time()-t0))
