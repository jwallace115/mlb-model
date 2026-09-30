"""Market grid v2 (Cowork 2026-09-30): league-average engine + strength s + pace m (as grid.py v1), 20k sims/cell,
seed = i*100+j (same as v1). Stores: J final joint pmf 16x16; JR regulation joint pmf 16x16; J1 first-period joint
pmf 8x8; J2 two-period joint 12x12; P(decided) REG/OT/SO; P(home wins | OT/SO)."""
import sys, time, numpy as np
sys.path.insert(0, "/home/claude/hunt/work"); sys.path.insert(0, "/home/claude/hunt")
from multiprocessing import Pool
from engine_trace2 import league_average_inputs, simulate, TeamMultipliers
S = np.round(np.arange(-0.5, 0.5001, 0.125), 4)
M = np.round(np.arange(0.80, 1.1601, 0.06), 4)
NS = 20000

def pmf(h, a, k):
    h = np.clip(h, 0, k - 1); a = np.clip(a, 0, k - 1)
    J = np.zeros((k, k)); np.add.at(J, (h, a), 1); return J / len(h)

def cell(ij):
    i, j = ij; s, m = S[i], M[j]
    inp = league_average_inputs()
    inp.home = TeamMultipliers(finishing=m * np.exp(s / 2), goalie_save=np.exp(-s / 2))
    inp.away = TeamMultipliers(finishing=m * np.exp(-s / 2), goalie_save=np.exp(s / 2))
    t = time.time()
    r = simulate(inp, NS, seed=i * 100 + j, trace_secs=[1200, 2400])
    h1, a1 = r["trace"][1200]; h2, a2 = r["trace"][2400]
    dec = r["decided"]; ot = dec != "REG"
    out = dict(J=pmf(r["home_score"], r["away_score"], 16), JR=pmf(r["reg_home_score"], r["reg_away_score"], 16),
               J1=pmf(h1, a1, 8), J2=pmf(h2, a2, 12),
               p_reg=float((dec == "REG").mean()), p_ot=float((dec == "OT").mean()), p_so=float((dec == "SO").mean()),
               p_home_given_ot=float((r["home_score"][ot] > r["away_score"][ot]).mean()))
    print(f"cell s={s} m={m} {time.time()-t:.0f}s P(home)={(r['home_score']>r['away_score']).mean():.3f} draw={1-out['p_reg']:.3f}", flush=True)
    return i, j, out

if __name__ == "__main__":
    cells = [(i, j) for i in range(len(S)) for j in range(len(M))]
    with Pool(2) as p:
        res = p.map(cell, cells, chunksize=1)
    A = {k: np.zeros((len(S), len(M)) + v.shape) for k, v in res[0][2].items() if isinstance(v, np.ndarray)}
    Sc = {k: np.zeros((len(S), len(M))) for k, v in res[0][2].items() if not isinstance(v, np.ndarray)}
    for i, j, o in res:
        for k, v in o.items():
            (A if isinstance(v, np.ndarray) else Sc)[k][i, j] = v
    np.savez("/home/claude/hunt/work/market_grid_v2.npz", S=S, M=M, n_sims=NS, **A, **Sc)
    print("DONE", flush=True)
