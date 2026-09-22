#!/usr/bin/env python3
"""
5L Item 2: player dispersion comparison — old (1-draw) vs new (per-sim) engine.

200 seeded games 2021-24. For each:
  - Anchor with the NEW engine (per-sim draws) → pooled player stats, offsets (dh, da)
  - Re-run ONE simulate_game at (dh, da) with OLD engine (monkey-patched scalar draw)
    → pooled player stats
  - Record per-player sim_p at standard rungs and actual outcomes

Output: per-position/family Brier scores, extreme-probability shares, dispersion stats.
"""

import sys, time, gc
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _build_player_context
from nfl.sim.anchor import run_anchored_chunked
from nfl.sim.calibration import engine_fingerprint
from nfl.sim.seed_util import stable_seed

SEASONS = [2021, 2022, 2023, 2024]
N_GAMES = 200
N_SIMS = 5000
SEED = 42


def load_actuals():
    """Load per-player per-game actual receptions and carries from PBP."""
    frames = []
    for s in SEASONS:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        df = pd.read_parquet(p)
        scrimmage = df[df["play_type"].isin(["pass", "run"])].copy()
        # Receptions: receiver_player_id where complete_pass == 1
        rec = (scrimmage[scrimmage["complete_pass"] == 1]
               .groupby(["game_id", "receiver_player_id"])
               .size().reset_index(name="receptions"))
        rec.rename(columns={"receiver_player_id": "player_id"}, inplace=True)
        # Carries: rusher_player_id (non-QB scrambles)
        rush = scrimmage[scrimmage["play_type"] == "run"].copy()
        if "qb_scramble" in rush.columns:
            rush = rush[rush["qb_scramble"] != 1]
        car = (rush.groupby(["game_id", "rusher_player_id"])
               .size().reset_index(name="carries"))
        car.rename(columns={"rusher_player_id": "player_id"}, inplace=True)
        # Scores for each game
        scores = (df.drop_duplicates("game_id")[["game_id", "season", "week",
                   "home_team", "away_team", "home_score", "away_score"]]
                  .dropna(subset=["home_score"]))
        scores["margin"] = scores["home_score"] - scores["away_score"]
        scores["total"] = scores["home_score"] + scores["away_score"]
        frames.append({"rec": rec, "car": car, "scores": scores})
    return {
        "rec": pd.concat([f["rec"] for f in frames], ignore_index=True),
        "car": pd.concat([f["car"] for f in frames], ignore_index=True),
        "scores": pd.concat([f["scores"] for f in frames], ignore_index=True),
    }


def main():
    print(f"engine_fingerprint: {engine_fingerprint()}")

    t0 = time.time()
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
              player_usage=pu, active_uni=au)

    actuals = load_actuals()
    scores = actuals["scores"]
    act_rec = actuals["rec"]
    act_car = actuals["car"]

    # Select 200 games (seeded)
    rng_sel = np.random.default_rng(SEED)
    sample_idx = rng_sel.choice(len(scores), size=N_GAMES, replace=False)
    sample = scores.iloc[sample_idx].copy().reset_index(drop=True)
    print(f"Sample: {N_GAMES} games from {SEASONS}")
    print(f"Games per season: {sample['season'].value_counts().sort_index().to_dict()}")
    for _, g in sample.head(5).iterrows():
        print(f"  {g['game_id']}: {g['away_team']}@{g['home_team']} "
              f"spread={g['margin']:.0f} total={g['total']:.0f}")
    print(f"  ...")

    # Prepare monkey-patch for old (scalar) _disperse via rng wrapper
    import nfl.sim.engine as _eng
    _orig_build = _eng._build_player_context

    class _ScalarBetaRng:
        """Wraps a numpy Generator so beta() ignores size= and broadcasts."""
        def __init__(self, real):
            object.__setattr__(self, '_real', real)
        def beta(self, a, b, size=None):
            val = self._real.beta(a, b)
            return np.full(size, val) if size is not None else val
        def __getattr__(self, name):
            return getattr(self._real, name)

    def _old_build(home, away, season, week, player_usage, active_uni,
                   qb_ratings=None, n_sims=1, rng=None):
        wrapped = _ScalarBetaRng(rng) if rng is not None else None
        return _orig_build(home, away, season, week, player_usage, active_uni,
                           qb_ratings=qb_ratings, n_sims=n_sims, rng=wrapped)

    # Run
    results_new = []
    results_old = []

    for gi, (_, game) in enumerate(sample.iterrows()):
        home = game["home_team"]
        away = game["away_team"]
        season = int(game["season"])
        week = int(game["week"])
        spread = float(game["margin"])
        total_line = float(game["total"])
        gid = game["game_id"]

        if gi % 20 == 0:
            print(f"  Game {gi+1}/{N_GAMES}: {away}@{home} s{season}w{week} "
                  f"({time.time()-t0:.0f}s elapsed)")

        seed = stable_seed((home, away, season, week, 42))

        # NEW engine: anchored
        try:
            td_n, pdf_n, dh, da, n_iter, conv, *_ = run_anchored_chunked(
                home, away, season, week, spread, total_line, **kw)
        except Exception as e:
            print(f"    SKIP (anchor fail): {e}")
            continue

        if pdf_n is None or pdf_n.empty:
            continue

        N = len(td_n)
        # Compute per-player stats from NEW engine
        for team in [home, away]:
            team_pdf = pdf_n[pdf_n["team"] == team]
            for pid in team_pdf["player_id"].unique():
                pp = team_pdf[team_pdf["player_id"] == pid]
                pname = pp["player_name"].iloc[0]
                pos = pp["position"].iloc[0]
                # Merge with all sim_ids to fill missing with 0
                stats = pd.DataFrame({"sim_id": np.arange(N)}).merge(
                    pp[["sim_id", "receptions", "carries"]], on="sim_id",
                    how="left").fillna(0)
                rec_vals = stats["receptions"].values
                car_vals = stats["carries"].values
                # Actual
                a_rec = act_rec[(act_rec["game_id"] == gid) & (act_rec["player_id"] == pid)]
                a_car = act_car[(act_car["game_id"] == gid) & (act_car["player_id"] == pid)]
                actual_rec = int(a_rec["receptions"].iloc[0]) if len(a_rec) > 0 else 0
                actual_car = int(a_car["carries"].iloc[0]) if len(a_car) > 0 else 0

                results_new.append({
                    "game_id": gid, "player_id": pid, "player_name": pname,
                    "position": pos, "team": team,
                    "mean_rec": float(rec_vals.mean()),
                    "sd_rec": float(rec_vals.std()),
                    "mean_car": float(car_vals.mean()),
                    "sd_car": float(car_vals.std()),
                    "actual_rec": actual_rec, "actual_car": actual_car,
                    # sim_p at standard rungs
                    "sp_rec3": float((rec_vals >= 3).mean()),
                    "sp_rec4": float((rec_vals >= 4).mean()),
                    "sp_rec5": float((rec_vals >= 5).mean()),
                    "sp_car10": float((car_vals >= 10).mean()),
                    "sp_car15": float((car_vals >= 15).mean()),
                })

        # OLD engine: one simulate_game at same offsets with scalar beta
        _eng._build_player_context = _old_build
        try:
            td_o, pdf_o = simulate_game(
                home, away, season, week, n_sims=N_SIMS, seed=seed,
                epa_home_offset=dh, epa_away_offset=da, **kw)
        except Exception as e:
            print(f"    SKIP old sim: {e}")
            _eng._build_player_context = _orig_build
            continue
        _eng._build_player_context = _orig_build

        if pdf_o is None or pdf_o.empty:
            continue

        N_o = len(td_o)
        for team in [home, away]:
            team_pdf = pdf_o[pdf_o["team"] == team]
            for pid in team_pdf["player_id"].unique():
                pp = team_pdf[team_pdf["player_id"] == pid]
                pname = pp["player_name"].iloc[0]
                pos = pp["position"].iloc[0]
                stats = pd.DataFrame({"sim_id": np.arange(N_o)}).merge(
                    pp[["sim_id", "receptions", "carries"]], on="sim_id",
                    how="left").fillna(0)
                rec_vals = stats["receptions"].values
                car_vals = stats["carries"].values
                a_rec = act_rec[(act_rec["game_id"] == gid) & (act_rec["player_id"] == pid)]
                a_car = act_car[(act_car["game_id"] == gid) & (act_car["player_id"] == pid)]
                actual_rec = int(a_rec["receptions"].iloc[0]) if len(a_rec) > 0 else 0
                actual_car = int(a_car["carries"].iloc[0]) if len(a_car) > 0 else 0

                results_old.append({
                    "game_id": gid, "player_id": pid, "player_name": pname,
                    "position": pos, "team": team,
                    "mean_rec": float(rec_vals.mean()),
                    "sd_rec": float(rec_vals.std()),
                    "mean_car": float(car_vals.mean()),
                    "sd_car": float(car_vals.std()),
                    "actual_rec": actual_rec, "actual_car": actual_car,
                    "sp_rec3": float((rec_vals >= 3).mean()),
                    "sp_rec4": float((rec_vals >= 4).mean()),
                    "sp_rec5": float((rec_vals >= 5).mean()),
                    "sp_car10": float((car_vals >= 10).mean()),
                    "sp_car15": float((car_vals >= 15).mean()),
                })

        del td_n, pdf_n, td_o, pdf_o
        gc.collect()

    df_new = pd.DataFrame(results_new)
    df_old = pd.DataFrame(results_old)

    print(f"\n{'='*70}")
    print(f"RESULTS: {len(df_new)} player-games (new), {len(df_old)} (old)")
    print(f"Runtime: {(time.time()-t0)/60:.1f} min")
    print(f"{'='*70}\n")

    # Per position x family analysis
    for pos in ["WR", "TE", "RB"]:
        for family, sp_cols, actual_col in [
            ("receptions", ["sp_rec3", "sp_rec4", "sp_rec5"], "actual_rec"),
            ("rush_attempts", ["sp_car10", "sp_car15"], "actual_car"),
        ]:
            if family == "rush_attempts" and pos != "RB":
                continue

            pn = df_new[df_new["position"] == pos]
            po = df_old[df_old["position"] == pos]
            if len(pn) < 10:
                continue

            print(f"--- {pos} {family} (n={len(pn)}) ---")

            for sp_col in sp_cols:
                k = int(sp_col.replace("sp_rec", "").replace("sp_car", ""))
                thresh = k

                # Extreme-probability share: fraction with sim_p < 0.05 or > 0.95
                ext_new = ((pn[sp_col] < 0.05) | (pn[sp_col] > 0.95)).mean()
                ext_old = ((po[sp_col] < 0.05) | (po[sp_col] > 0.95)).mean()

                # Brier score: (sim_p - actual_outcome)^2
                if family == "receptions":
                    actual_binary_n = (pn[actual_col] >= thresh).astype(float)
                    actual_binary_o = (po[actual_col] >= thresh).astype(float)
                else:
                    actual_binary_n = (pn[actual_col] >= thresh).astype(float)
                    actual_binary_o = (po[actual_col] >= thresh).astype(float)

                brier_new = ((pn[sp_col] - actual_binary_n) ** 2).mean()
                brier_old = ((po[sp_col] - actual_binary_o) ** 2).mean()

                print(f"  >= {thresh:2d}: extreme_share old={ext_old:.3f} new={ext_new:.3f} "
                      f"(ratio {ext_new/max(ext_old,1e-9):.2f}) | "
                      f"Brier old={brier_old:.4f} new={brier_new:.4f} "
                      f"({'BETTER' if brier_new < brier_old else 'WORSE'})")
            print()

    # Save raw data
    out_dir = ROOT / "research" / "nfl_sim"
    df_new.to_parquet(out_dir / "phase5l_dispersion_new.parquet", index=False)
    df_old.to_parquet(out_dir / "phase5l_dispersion_old.parquet", index=False)
    print(f"Saved to {out_dir}/phase5l_dispersion_{{new,old}}.parquet")
    print(f"Total runtime: {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
