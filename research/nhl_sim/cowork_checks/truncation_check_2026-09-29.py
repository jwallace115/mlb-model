# Cowork reference check (S-WO3c verification). Usage: python3 <this> <worktree> <ratings.py to test> <tag>
# Truncation + same-day-garbage test: ratings on date D must not change when rows after D are dropped and D's own stats are corrupted.
import sys, time, contextlib, io, importlib.util, numpy as np, pandas as pd
WT = sys.argv[1]; modpath = sys.argv[2]; tag = sys.argv[3]
spec = importlib.util.spec_from_file_location("R", modpath); R = importlib.util.module_from_spec(spec)
sys.path.insert(0, WT); spec.loader.exec_module(R)
R.CARRYOVER_PATH = __import__('pathlib').Path(WT)/"nhl/data/sim/ratings/carryover_w.json"
tgs = pd.read_parquet(f"{WT}/nhl/data/sim/ratings/team_game_stats.parquet")
cols = ["ev_att_for_per60","ev_att_against_per60","ev_xg_per_att_for","ev_xg_per_att_against"]
def run(t):
    with contextlib.redirect_stdout(io.StringIO()):
        out = R.build_pit_ratings(t)[0]
    return out.set_index(["game_id","team"])[cols]
t0=time.time(); full = run(tgs); print(tag, "full build s", round(time.time()-t0,1), flush=True)
rng = np.random.RandomState(20260929)
dates = sorted(tgs[tgs.season==2023].date.unique())
pick = sorted(rng.choice(dates, 20, replace=False))
num = [c for c in tgs.columns if c.startswith(("ev_","pp_","pk_","pen")) and pd.api.types.is_numeric_dtype(tgs[c])]
worst = 0.0; fails = 0
for D in pick:
    t = tgs[tgs.date <= D].copy()
    m = t.date == D
    t.loc[m, num] = t.loc[m, num] * 7 + 3        # garbage on day D's own stats
    tr = run(t)
    idx = tgs[tgs.date == D].set_index(["game_id","team"]).index
    diff = (tr.loc[idx] - full.loc[idx]).abs().to_numpy().max()
    worst = max(worst, diff); fails += diff > 1e-12
    print(tag, D, "max diff", diff, flush=True)
print(tag, "RESULT: dates", len(pick), "failing", fails, "worst", worst, flush=True)
