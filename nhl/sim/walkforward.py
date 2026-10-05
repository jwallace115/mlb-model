#!/usr/bin/env python3
"""D6: walk-forward fit-window orchestrator.

For each target season T in 2012..2020:
  fit_window = [T-2, T-1]
  1. Build constants_v8 from events of the fit window
  2. Measure hyper (K, r) and carryover (w) from game stats of the fit window
  3. Build ratings for all_seasons = fit_window + [T]
  4. Write per-season outputs to nhl/data/sim/walkforward/season=T/

Structural breaks:
  - 2015-16: 3v3 OT starts. For T=2012..2014, OT is 4v4 (ot_base_skaters=4).
    For T=2015+, OT is 3v3 (ot_base_skaters=3). The fit window for T=2015 is
    [2013,2014] (all 4v4) and for T=2016 is [2014,2015] (mixed). Constants are
    from the fit window as-is; the engine's base-skater argument handles the
    structural difference.
  - 2012-13 lockout: 720 games. Weighted by games in measure_hyper/carryover
    naturally (no per-season weighting needed — the functions aggregate over rows).
"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

WF_DIR = ROOT / "nhl" / "data" / "sim" / "walkforward"


def run_target(T, verbose=True):
    """Build constants + ratings for target season T with fit window [T-2, T-1]."""
    from nhl.sim.build_constants_v7 import main as build_v7, main_v8 as build_v8
    from nhl.sim import ratings

    fit = [T - 2, T - 1]
    all_seasons = fit + [T]
    out_dir = WF_DIR / f"season={T}"
    out_dir.mkdir(parents=True, exist_ok=True)

    v7_path = out_dir / "constants_v7.json"
    v8_path = out_dir / "constants_v8.json"

    if verbose:
        print(f"\n{'='*60}")
        print(f"Target season {T}-{T+1}, fit window {fit[0]}-{fit[0]+1} + {fit[1]}-{fit[1]+1}")
        print(f"Output: {out_dir}")
        print(f"{'='*60}")

    # 1. Constants
    t0 = time.time()
    build_v7(fit_seasons=fit, out_path=str(v7_path))
    build_v8(fit_seasons=fit, v7_path=str(v7_path), out_path=str(v8_path))
    if verbose:
        print(f"  Constants: {time.time()-t0:.1f}s")

    # 2. Game stats + hyper + carryover + ratings
    t0 = time.time()
    hyper_path = out_dir / "shrinkage_K.json"
    carry_path = out_dir / "carryover_w.json"
    goalie_games_path = out_dir / "goalie_games.parquet"

    # Load data
    games_df = ratings.get_game_info(all_seasons)
    from nhl.sim.build_events import GAMES_PER_SEASON_MAP
    ev_dir = ROOT / "nhl" / "data" / "sim" / "events"
    import pandas as pd
    shots_all = pd.concat([pd.read_parquet(ev_dir / f"season={s}" / "shots.parquet") for s in all_seasons], ignore_index=True)
    state_all = pd.concat([pd.read_parquet(ev_dir / f"season={s}" / "state_time.parquet") for s in all_seasons], ignore_index=True)
    pens_all = pd.concat([pd.read_parquet(ev_dir / f"season={s}" / "penalties.parquet") for s in all_seasons], ignore_index=True)
    gd = games_df[["game_id", "date", "season"]].drop_duplicates("game_id")
    shots_all = shots_all.merge(gd, on="game_id", how="left")
    state_all = state_all.merge(gd, on="game_id", how="left")
    pens_all = pens_all.merge(gd, on="game_id", how="left")
    model = ratings.load_xg_model()

    tgs = ratings.build_game_stats_vectorised(games_df, shots_all, state_all, pens_all, model)
    tgs.to_parquet(out_dir / "team_game_stats.parquet", index=False)

    gdf = ratings.build_goalie_games(shots_all, games_df, model)
    gdf.to_parquet(goalie_games_path, index=False)

    # Measure hyper on fit seasons
    hyper = ratings.measure_hyper(tgs, fit_seasons=fit)
    hyper["goalie"] = ratings.measure_goalie_hyper(gdf, fit_seasons=fit)
    w = ratings.measure_carryover(tgs, fit_seasons=fit)
    w["goalie_gsax_per_att"] = ratings.measure_goalie_carryover(gdf, fit_seasons=fit)
    w["_fit_seasons"] = list(fit)
    w["_derivation"] = f"slope of {fit[1]}-{fit[1]+1:02d} on {fit[0]}-{fit[0]+1:02d}, ratio of sums, clipped to [0,1]"

    with open(hyper_path, "w") as f:
        json.dump(hyper, f, indent=2, sort_keys=True)
    with open(carry_path, "w") as f:
        json.dump(w, f, indent=2, sort_keys=True)

    # Build ratings
    team_ratings, _ = ratings.build_pit_ratings(tgs, fit_seasons=fit, hyper=hyper, carryover=w)
    team_ratings.to_parquet(out_dir / "team_ratings.parquet", index=False)

    goalie_ratings = ratings.goalie_ratings_from_games(gdf, hyper=hyper, carryover=w)
    goalie_ratings.to_parquet(out_dir / "goalie_ratings.parquet", index=False)

    finishing = ratings.finishing_term_from_games(gdf)
    finishing.to_parquet(out_dir / "finishing_term.parquet", index=False)

    elapsed = time.time() - t0
    if verbose:
        print(f"  Ratings: {elapsed:.1f}s, {len(team_ratings)} team_ratings, "
              f"{len(goalie_ratings)} goalie_ratings, {len(finishing)} finishing rows")

    # OT base skaters: 4v4 for T <= 2014, 3v3 for T >= 2015
    ot_base = 4 if T <= 2014 else 3
    meta = {
        "target_season": T, "fit_window": fit, "ot_base_skaters": ot_base,
        "team_ratings_rows": len(team_ratings),
        "goalie_ratings_rows": len(goalie_ratings),
    }

    # Extract r/K/w for the table
    result = {"T": T, "fit": fit, "ot_base": ot_base}
    for grp in ["ev_att", "ev_xg", "pp_xg", "pk_xg", "pen_taken", "pen_drawn"]:
        result[f"r_{grp}"] = round(hyper[grp]["r"], 4)
        result[f"K_{grp}"] = round(hyper[grp]["K"], 2)
    result["r_goalie"] = round(hyper["goalie"]["r"], 4)
    result["K_goalie"] = round(hyper["goalie"]["K"], 2)
    for k, v in w.items():
        if not k.startswith("_"):
            result[f"w_{k}"] = round(v, 4) if isinstance(v, float) else v

    with open(out_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    return result


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", type=str, default="2012,2013,2014,2015,2016,2017,2018,2019,2020",
                    help="comma-separated target seasons")
    args = ap.parse_args()
    targets = [int(s) for s in args.targets.split(",")]

    WF_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for T in targets:
        r = run_target(T)
        results.append(r)

    # Print summary table
    print(f"\n{'='*80}")
    print("Walk-forward hyperparameter table")
    print(f"{'='*80}")
    print(f"{'T':>6} | {'fit':>10} | {'OT':>3} | {'r_ev_att':>8} | {'K_ev_att':>8} | {'r_goalie':>8} | {'K_goalie':>8}")
    print("-" * 80)
    for r in results:
        fit_str = f"{r['fit'][0]},{r['fit'][1]}"
        print(f"{r['T']:>6} | {fit_str:>10} | {r['ot_base']:>3} | {r['r_ev_att']:>8.4f} | {r['K_ev_att']:>8.2f} | "
              f"{r['r_goalie']:>8.4f} | {r['K_goalie']:>8.2f}")

    # Save full results
    with open(WF_DIR / "walkforward_hyper_table.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull table saved to {WF_DIR / 'walkforward_hyper_table.json'}")


if __name__ == "__main__":
    main()
