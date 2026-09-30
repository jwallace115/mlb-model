"""Market-conditioning grid for the engine (Cowork 2026-09-30). League-average inputs + two knobs:
strength s (home goal rate x e^s, away x e^-s via finishing/goalie_save) and pace m (all non-EN goals x m).
Per cell: 20,000 sims, seed = cell index. Output: joint final-score pmf 0..15 x 0..15 plus decided type."""
import sys, time, numpy as np
from multiprocessing import Pool
from nhl.sim.engine import league_average_inputs, simulate, TeamMultipliers
S = np.round(np.arange(-0.5, 0.5001, 0.125), 4)
M = np.round(np.arange(0.80, 1.1601, 0.06), 4)
NS = 20000

def cell(ij):
    i, j = ij
    s, m = S[i], M[j]
    inp = league_average_inputs()
    inp.home = TeamMultipliers(finishing=m * np.exp(s / 2), goalie_save=np.exp(-s / 2))
    inp.away = TeamMultipliers(finishing=m * np.exp(-s / 2), goalie_save=np.exp(s / 2))
    t = time.time()
    r = simulate(inp, NS, seed=i * 100 + j)
    h = np.clip(r["home_score"], 0, 15); a = np.clip(r["away_score"], 0, 15)
    J = np.zeros((16, 16)); np.add.at(J, (h, a), 1); J /= NS
    reg_tie = float((r["reg_home_score"] == r["reg_away_score"]).mean())
    print(f"cell s={s} m={m} {time.time()-t:.0f}s P(home)={(r['home_score']>r['away_score']).mean():.3f} tot={(r['home_score']+r['away_score']).mean():.2f}", flush=True)
    return i, j, J, reg_tie

if __name__ == "__main__":
    cells = [(i, j) for i in range(len(S)) for j in range(len(M))]
    with Pool(2) as p:
        res = p.map(cell, cells, chunksize=1)
    JJ = np.zeros((len(S), len(M), 16, 16)); RT = np.zeros((len(S), len(M)))
    for i, j, J, rt in res:
        JJ[i, j] = J; RT[i, j] = rt
    np.savez("/home/claude/nhl/eng/market_grid_v1.npz", S=S, M=M, J=JJ, reg_tie=RT, n_sims=NS)
    print("DONE", flush=True)
