#!/usr/bin/env python3
"""
Phase 5H verification (Cowork, D98) — recompute 5H's headline numbers from the committed
row-level artifacts and from PBP, and measure what real football does to yards-to-go after
an offensive penalty.

Report-only. Reads; writes nothing; imports the engine for nothing.

Inputs:
  research/nfl_sim/phase5h_metric_noise_rows.parquet                (on main)
  diag_5h_4th.parquet / diag_5h_late.parquet                        (on branch diag/5h; pass --diag-dir)
  nfl/data/pbp/pbp_{2021..2024}.parquet

Usage:
  python3 nfl/sim/run_verify_5h.py --diag-dir ~/mlb-model-diag/research/nfl_sim
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
SEASONS = (2021, 2022, 2023, 2024)


def pbp(cols):
    return pd.concat([pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet", columns=cols) for s in SEASONS])


def noise():
    from scipy.stats import binom, fisher_exact
    r = pd.read_parquet(ROOT / "research" / "nfl_sim" / "phase5h_metric_noise_rows.parquet")
    print("=== 1. NOISE ROWS (rebuilt from the parquet) ===")
    for src, g in r.groupby("noise_type"):
        print(f"-- {src} (n={len(g)})")
        print(g[["go_rate", "off_pen", "def_pen", "fd_pen_pt", "tied_expiry", "real_go_rate"]]
              .agg(["mean", "std", "min", "max"]).T.round(5).to_string())
    s = r[r.noise_type == "seed"]
    E, R = int(s.tied_n_expired.sum()), int(s.tied_n_reached.sum())
    print(f"tied-drive expiry pooled over seeds: {E}/{R} = {E/R:.4f}; real (D94 broad) 2/64")
    print(f"  P(real <= 2 of 64 | sim rate) = {binom.cdf(2, 64, E/R):.4f}; "
          f"Fisher exact = {fisher_exact([[2, 62], [E, R - E]])[1]:.4f}")
    m = r[r.noise_type != "seed"]
    d = m.go_rate - m.real_go_rate
    print(f"go rate, sim minus REAL IN THE SAME GAMES, 10 samples: mean {d.mean():+.4f}, "
          f"SD {d.std():.4f}, SE {d.std()/np.sqrt(len(d)):.4f} (samples overlap; SE is a floor)")


def decomposition(diag_dir):
    from nfl.sim.tables import fourth_down_keys
    print("\n=== 2. GO-RATE DECOMPOSITION (down == 4 only, both sides) ===")
    r = pbp(["week", "qtr", "down", "ydstogo", "yardline_100", "score_differential", "play_type",
             "quarter_seconds_remaining"])
    r = r[(r.week <= 18) & (r.down == 4) & r.play_type.isin(["pass", "run", "punt", "field_goal"])].copy()
    a, b, c, d_ = fourth_down_keys(r.ydstogo, r.yardline_100, r.score_differential, r.qtr,
                                   r.quarter_seconds_remaining)
    r["k"] = list(zip(np.asarray(a), np.asarray(b), np.asarray(c), np.asarray(d_)))
    r["yd"] = np.asarray(a)
    r["go"] = r.play_type.isin(["pass", "run"]).astype(int)
    s = pd.read_parquet(diag_dir / "diag_5h_4th.parquet",
                        columns=["ydstogo_b", "yl_b", "score_b", "qtr_b", "decision"])
    s["k"] = list(zip(s.ydstogo_b, s.yl_b, s.score_b, s.qtr_b))
    s["go"] = (s.decision == "go").astype(int)
    J = r.groupby("k").go.agg(["mean", "size"]).join(s.groupby("k").go.agg(["mean", "size"]),
                                                      how="outer", lsuffix="_r", rsuffix="_s")
    J[["size_r", "size_s"]] = J[["size_r", "size_s"]].fillna(0)
    wr, ws = J.size_r / J.size_r.sum(), J.size_s / J.size_s.sum()
    print(f"sim mass in cells with no real observation: {ws[J.mean_r.isna()].sum():.4f} "
          f"(those cells borrow the sim's own rate below)")
    mr, ms = J.mean_r.fillna(J.mean_s), J.mean_s.fillna(J.mean_r)
    rr, ss = (wr * mr).sum(), (ws * ms).sum()
    gap = ss - rr
    print(f"real {rr:.5f} (n={len(r)}) | sim {ss:.5f} (n={len(s)}) | gap {gap:+.5f}")
    print(f"  real rates @ sim mix: {(ws*mr).sum():.5f} -> state mix {(ws*mr).sum()-rr:+.5f} "
          f"({100*((ws*mr).sum()-rr)/gap:.1f}%)")
    print(f"  sim rates @ real mix: {(wr*ms).sum():.5f} -> within-cell {(wr*ms).sum()-rr:+.5f} "
          f"({100*((wr*ms).sum()-rr)/gap:.1f}%)")
    n_sim_games = 1087 * 500
    for yb in ["1-2", "3-5", "6-10", "11+"]:
        print(f"  4th-and-{yb:5s} per game: real {(r.yd == yb).sum()/1087:.2f}  "
              f"sim {(s.ydstogo_b == yb).sum()/n_sim_games:.2f} | go rate real "
              f"{r[r.yd == yb].go.mean():.3f} sim {s[s.ydstogo_b == yb].go.mean():.3f}")


def late_clock(diag_dir):
    print("\n=== 3. SECONDS PER PLAY, Q4 <= 300 s, OFFENCE TIED OR TRAILING BY 1-8 ===")
    L = pd.read_parquet(diag_dir / "diag_5h_late.parquet")
    L = L[L.play_type.isin(["pass", "rush"])].copy()
    L["el"] = L.clock_before - L.clock_after
    L["cb"] = pd.cut(L.clock_before, [0, 40, 120, 300], labels=["0-40", "41-120", "121-300"])
    L["pt"] = L.play_type.replace({"rush": "run"})
    p = pbp(["game_id", "week", "qtr", "play_id", "play_type", "half_seconds_remaining",
             "score_differential", "timeout", "qb_spike", "qb_kneel"])
    p = p[p.week <= 18].sort_values(["game_id", "play_id"])
    p["half_id"] = np.where(p.qtr <= 2, 1, np.where(p.qtr <= 4, 2, 3))
    # elapsed = time to the next clocked row of any type in the half; timeout rows skipped so the
    # elapsed spans them (the sim's step also contains its timeouts)
    q = p[p.play_type.notna() & p.half_seconds_remaining.notna() & (p.timeout != 1)].copy()
    q["next_sec"] = q.groupby(["game_id", "half_id"]).half_seconds_remaining.shift(-1)
    e = q[q.play_type.isin(["pass", "run"]) & (q.qb_spike != 1) & (q.qb_kneel != 1) & (q.qtr == 4)
          & (q.half_seconds_remaining <= 300) & q.score_differential.between(-8, 0)].copy()
    e["el"] = e.half_seconds_remaining - e.next_sec.fillna(0)
    e["cb"] = pd.cut(e.half_seconds_remaining, [0, 40, 120, 300], labels=["0-40", "41-120", "121-300"])
    out = pd.concat({"real": e.groupby(["play_type", "cb"], observed=True).el.agg(["mean", "size"]),
                     "sim": L.groupby(["pt", "cb"], observed=True).el.agg(["mean", "size"])}, axis=1)
    out[("diff", "sec")] = out[("sim", "mean")] - out[("real", "mean")]
    print(out.round(2).to_string())


def offensive_penalty_distance():
    print("\n=== 4. WHAT AN OFFENSIVE NO-PLAY PENALTY DOES TO YARDS-TO-GO (real) ===")
    p = pbp(["game_id", "week", "play_id", "down", "ydstogo", "play_type", "penalty", "penalty_team",
             "posteam", "penalty_yards", "drive"])
    scr = p[(p.week <= 18) & p.down.notna()].sort_values(["game_id", "play_id"]).copy()
    scr["nx_down"] = scr.groupby(["game_id", "drive"]).down.shift(-1)
    scr["nx_ytg"] = scr.groupby(["game_id", "drive"]).ydstogo.shift(-1)
    o = scr[(scr.play_type == "no_play") & (scr.penalty == 1) & (scr.penalty_team == scr.posteam)
            & scr.nx_down.notna()]
    same = o[o.nx_down == o.down]
    ch = same.nx_ytg - same.ydstogo
    print(f"offensive no-play penalties with a following snap: {len(o)} ({len(o)/1087:.2f}/game); "
          f"down replayed: {len(same)}")
    print(f"  yards-to-go change on the replayed down: mean {ch.mean():+.2f}, increased in "
          f"{(ch > 0).mean():.3f} of cases; mean penalty yards {same.penalty_yards.mean():.2f}")
    t = scr[(scr.down == 3) & scr.play_type.isin(["pass", "run"])]
    print(f"  real 3rd-down share at 11+ to go: {(t.ydstogo >= 11).mean():.3f}")
    print("  engine (main): grep -n 'dist\\[off_pen' nfl/sim/engine.py  -> no match: the ball moves "
          "back, yards-to-go does not change")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag-dir", type=Path, default=None,
                    help="directory holding diag_5h_4th.parquet and diag_5h_late.parquet (branch diag/5h)")
    a = ap.parse_args()
    noise()
    if a.diag_dir is not None:
        dd = a.diag_dir.expanduser()
        decomposition(dd)
        late_clock(dd)
    else:
        print("\n(sections 2-3 skipped: pass --diag-dir)")
    offensive_penalty_distance()
