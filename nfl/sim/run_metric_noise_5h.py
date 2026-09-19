#!/usr/bin/env python3
"""
Phase 5H Item 1 — sim-side noise floor of the four test metrics.

Replicates:
  - Seed noise: same games, 10 seed salts (0 = test's own seed, 1-10 = perturbed)
  - Sample noise: 10 different game samples (rng keys 0-9; the tests use 42)

Metrics:
  - go_rate: 5A-3 construction (50 games of 2023, N=500, drive_log=True)
  - off_pen, def_pen, fd_pen_pt: 5A-4 construction (80 games, N=500)
  - tied_expiry: 5A-9 construction (12 SAMPLE_GAMES, N=500, drive_log=True)

Outputs:
  - research/nfl_sim/phase5h_metric_noise_rows.parquet
  - research/nfl_sim/phase5h_metric_noise.md
"""

import sys, time, json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _CACHE
from nfl.sim.seed_util import stable_seed
from nfl.sim.calibration import engine_fingerprint

PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "research" / "nfl_sim"

# ── 5A-9 SAMPLE_GAMES (must match test_engine_5a9.py exactly) ──
SAMPLE_GAMES = [("KC", "BUF", 2023, 6), ("PHI", "DAL", 2022, 10), ("SF", "SEA", 2024, 12),
                ("DET", "GB", 2023, 4), ("BAL", "CIN", 2022, 14), ("MIA", "NYJ", 2024, 8),
                ("LA", "ARI", 2023, 12), ("MIN", "CHI", 2022, 6), ("TB", "ATL", 2024, 15),
                ("DEN", "LV", 2023, 17), ("CLE", "PIT", 2022, 2), ("HOU", "IND", 2024, 5)]


def _load_2023_games():
    games = pd.read_parquet(PBP_DIR / "pbp_2023.parquet",
                            columns=["game_id", "season", "week", "home_team",
                                     "away_team", "home_score", "away_score"])
    return games.drop_duplicates("game_id").query("week <= 18")


def _seed_go(game_id, salt):
    """Seed for go-rate metric. salt=0 uses the test's own seed."""
    if salt == 0:
        return stable_seed((game_id, 42))
    return stable_seed((game_id, 42, salt))


def _seed_pen(game_id, salt):
    if salt == 0:
        return stable_seed((game_id, 42))
    return stable_seed((game_id, 42, salt))


def _seed_5a9(home, away, season, week, salt):
    if salt == 0:
        return stable_seed(f"5a9_{season}_{week}_{away}_{home}")
    return stable_seed((f"5a9_{season}_{week}_{away}_{home}", salt))


def compute_go_rate(games_df, salt, ratings):
    """Run 5A-3 go-rate sample: 50 games, N=500, drive_log=True."""
    tr, tend, sit, kicker, league = ratings
    results = []
    for _, g in games_df.iterrows():
        s = _seed_go(g["game_id"], salt)
        r = simulate_game(g["home_team"], g["away_team"], 2023, int(g["week"]),
                          n_sims=500, seed=s,
                          team_r=tr, tend=tend, sit=sit, kicker=kicker, league=league,
                          drive_log=True)
        r["game_id"] = g["game_id"]
        results.append(r)
    sim = pd.concat(results, ignore_index=True)
    total = sim["ev_4th_go"].sum() + sim["ev_punts"].sum() + sim["ev_fg_att"].sum()
    go_rate = float(sim["ev_4th_go"].sum() / max(total, 1))
    return {"go_rate": go_rate}


def compute_penalties(games_df, salt, ratings):
    """Run 5A-4 penalty sample: 80 games, N=500."""
    tr, tend, sit, kicker, league = ratings
    results = []
    for _, g in games_df.iterrows():
        s = _seed_pen(g["game_id"], salt)
        r = simulate_game(g["home_team"], g["away_team"], 2023, int(g["week"]),
                          n_sims=500, seed=s,
                          team_r=tr, tend=tend, sit=sit, kicker=kicker, league=league)
        r["game_id"] = g["game_id"]
        results.append(r)
    sim = pd.concat(results, ignore_index=True)
    off_pg = float(sim["ev_pen_offense"].mean())
    def_pg = float(sim["ev_pen_defense"].mean())
    fd_pg = float(sim["ev_fd_penalty"].mean())
    return {"off_pen": off_pg, "def_pen": def_pg, "fd_pen_pt": fd_pg / 2}


def compute_tied_expiry(salt, ratings):
    """Run 5A-9 tied-drive sample: 12 games, N=500, drive_log=True."""
    drives_list = []
    for home, away, season, week in SAMPLE_GAMES:
        s = _seed_5a9(home, away, season, week, salt)
        r = simulate_game(home, away, season, week, n_sims=500,
                          seed=s, drive_log=True, **ratings)
        if isinstance(r, tuple):
            r = r[0]
        dl = r.attrs["drive_log"]
        drives_list.append(dl[(dl.start_quarter == 4) & (dl.start_clock <= 300)])
    d = pd.concat(drives_list, ignore_index=True)
    x = d[d.sd_start == 0]
    reached = (x.start_yardline - x.yards <= 35) | x.result.isin(["TD"]) | (x.end_yardline <= 35)
    xr = x[reached]
    n_reached = len(xr)
    n_expired = int(xr.result.isin(["end_game", "end_half"]).sum())
    rate = n_expired / n_reached if n_reached > 0 else 0.0
    return {"tied_expiry": rate, "tied_n_reached": n_reached, "tied_n_expired": n_expired}


def derive_real_go_rate(game_ids):
    """Real 4th-down go rate in the given games (from PBP)."""
    pbp = pd.read_parquet(PBP_DIR / "pbp_2023.parquet")
    pbp = pbp[pbp["game_id"].isin(game_ids) & (pbp["down"] == 4) & (pbp["week"] <= 18)]
    decisions = pbp[pbp["play_type"].isin({"run", "pass", "punt", "field_goal"})]
    n = len(decisions)
    if n == 0:
        return 0.0, 0
    go = decisions["play_type"].isin({"run", "pass"}).sum()
    return float(go / n), n


def main():
    print(f"engine_fingerprint: {engine_fingerprint()}")
    print()

    _CACHE.clear()
    _load_tables()
    ratings_tuple = _load_ratings()
    ratings_dict = dict(team_r=ratings_tuple[0], tend=ratings_tuple[1],
                        sit=ratings_tuple[2], kicker=ratings_tuple[3],
                        league=ratings_tuple[4])

    all_2023 = _load_2023_games()

    # ── Test game samples (salt=0 must reproduce pytest) ──
    go_games_42 = all_2023.iloc[np.random.default_rng(42).choice(len(all_2023), 50, replace=False)]
    pen_games_42 = all_2023.iloc[np.random.default_rng(42).choice(len(all_2023), 80, replace=False)]

    # ── Step 1: Replicate 0 must reproduce pytest ──
    print("=== REPLICATE 0: reproducing pytest values ===")
    t0 = time.time()
    go_r0 = compute_go_rate(go_games_42, salt=0, ratings=ratings_tuple)
    t_go = time.time() - t0
    print(f"  go_rate = {go_r0['go_rate']:.15f}  [{t_go:.1f}s]")

    t0 = time.time()
    pen_r0 = compute_penalties(pen_games_42, salt=0, ratings=ratings_tuple)
    t_pen = time.time() - t0
    print(f"  off_pen = {pen_r0['off_pen']:.4f}, def_pen = {pen_r0['def_pen']:.4f}, "
          f"fd_pen_pt = {pen_r0['fd_pen_pt']:.4f}  [{t_pen:.1f}s]")

    t0 = time.time()
    exp_r0 = compute_tied_expiry(salt=0, ratings=ratings_dict)
    t_exp = time.time() - t0
    print(f"  tied_expiry = {exp_r0['tied_expiry']:.15f} "
          f"({exp_r0['tied_n_expired']}/{exp_r0['tied_n_reached']})  [{t_exp:.1f}s]")

    print()
    print(f"=== WALL TIMES: go={t_go:.0f}s, pen={t_pen:.0f}s, tied={t_exp:.0f}s ===")
    print(f"Projected total: seed_noise(11x go + 11x pen + 11x tied) + "
          f"sample_noise(10x go + 10x pen) = "
          f"{11*t_go + 11*t_pen + 11*t_exp + 10*t_go + 10*t_pen:.0f}s "
          f"= {(11*t_go + 11*t_pen + 11*t_exp + 10*t_go + 10*t_pen)/60:.0f}min")
    print()

    rows = []

    # ── Step 3: Seed noise (salts 0-10, same games) ──
    print("=== SEED NOISE (salts 0-10) ===")
    for salt in range(11):
        go = compute_go_rate(go_games_42, salt=salt, ratings=ratings_tuple)
        pen = compute_penalties(pen_games_42, salt=salt, ratings=ratings_tuple)
        exp = compute_tied_expiry(salt=salt, ratings=ratings_dict)
        row = {"noise_type": "seed", "replicate": salt, **go, **pen, **exp}
        rows.append(row)
        print(f"  salt={salt:>2d}: go={go['go_rate']:.4f} off_pen={pen['off_pen']:.3f} "
              f"def_pen={pen['def_pen']:.3f} fd_pen_pt={pen['fd_pen_pt']:.4f} "
              f"tied={exp['tied_expiry']:.4f} ({exp['tied_n_expired']}/{exp['tied_n_reached']})")

    # ── Step 4: Sample noise (rng keys 0-9, test seeds) ──
    print()
    print("=== SAMPLE NOISE (rng keys 0-9, 42=test default) ===")
    for k in range(10):
        rng = np.random.default_rng(k)
        go_games = all_2023.iloc[rng.choice(len(all_2023), 50, replace=False)]
        pen_rng = np.random.default_rng(k)
        pen_games = all_2023.iloc[pen_rng.choice(len(all_2023), 80, replace=False)]

        go = compute_go_rate(go_games, salt=0, ratings=ratings_tuple)
        pen = compute_penalties(pen_games, salt=0, ratings=ratings_tuple)
        real_go, real_n = derive_real_go_rate(go_games["game_id"])
        row = {"noise_type": "sample", "replicate": k, **go, **pen,
               "tied_expiry": np.nan, "tied_n_reached": np.nan, "tied_n_expired": np.nan,
               "real_go_rate": real_go, "real_go_n": real_n}
        rows.append(row)
        print(f"  k={k:>2d}: go={go['go_rate']:.4f} (real={real_go:.4f},n={real_n}) "
              f"off_pen={pen['off_pen']:.3f} fd_pen_pt={pen['fd_pen_pt']:.4f}")

    # ── Save ──
    df = pd.DataFrame(rows)
    parquet_path = OUT_DIR / "phase5h_metric_noise_rows.parquet"
    df.to_parquet(parquet_path, index=False)
    print(f"\nSaved {len(df)} rows to {parquet_path}")

    # ── Build report ──
    report_lines = ["# Phase 5H — Metric Noise Floor\n"]
    for noise_type in ["seed", "sample"]:
        sub = df[df["noise_type"] == noise_type]
        report_lines.append(f"\n## {noise_type.title()} noise\n")
        for col in ["go_rate", "off_pen", "def_pen", "fd_pen_pt", "tied_expiry"]:
            vals = sub[col].dropna()
            if vals.empty:
                continue
            report_lines.append(f"- **{col}**: mean={vals.mean():.5f} SD={vals.std():.5f} "
                                f"min={vals.min():.5f} max={vals.max():.5f} N={len(vals)}")
        if noise_type == "sample" and "real_go_rate" in sub.columns:
            rv = sub["real_go_rate"].dropna()
            report_lines.append(f"- **real_go_rate** (in those games): mean={rv.mean():.5f} "
                                f"SD={rv.std():.5f} min={rv.min():.5f} max={rv.max():.5f}")

    report_path = OUT_DIR / "phase5h_metric_noise.md"
    report_path.write_text("\n".join(report_lines) + "\n")
    print(f"Report: {report_path}")

    # ── Null control ──
    print(f"\n=== NULL CONTROL ===")
    print(f"engine_fingerprint: {engine_fingerprint()}")


if __name__ == "__main__":
    main()
