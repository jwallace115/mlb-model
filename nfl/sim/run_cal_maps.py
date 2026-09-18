#!/usr/bin/env python3
"""
D74: Build calibration maps from fit checkpoints.

Reads fit_<dir>/games/*.parquet (team + player checkpoints), assembles
the structure fit_calibration_maps() expects, fits isotonic maps, and
writes calibration_v1.json via save_calibration (the stamp writer).

Usage:
  python3 nfl/sim/run_cal_maps.py --fit-dir fit_5d2
  python3 nfl/sim/run_cal_maps.py --fit-dir fit_5d1 --output /tmp/cal_check.json
"""

import argparse, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.calibration import save_calibration

PBP_DIR = ROOT / "nfl" / "data" / "pbp"
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"


def _legacy_actuals(game_pbp):
    """Pre-D62 actuals for faithfulness reproduction."""
    from nfl.sim.run_k4 import _legacy_actual_player_game_stats
    return _legacy_actual_player_game_stats(game_pbp)


def build_maps_from_checkpoints(fit_dir, legacy_actuals=False):
    """Read checkpoints and fit isotonic maps. Returns (cal_maps, census)."""
    if legacy_actuals:
        actuals_fn = _legacy_actuals
    else:
        from nfl.sim.actuals import actual_player_game_stats
        actuals_fn = actual_player_game_stats

    FIT_PATH = ROOT / "nfl" / "data" / "sim" / "outputs" / fit_dir
    GAMES = FIT_PATH / "games"
    census = pd.read_parquet(FIT_PATH / "fit_census.parquet")

    pbp_cache = {}
    game_scores = {}
    for s in sorted(census["season"].unique()):
        p = PBP_DIR / f"pbp_{int(s)}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            pbp_cache[int(s)] = df
            g = df.drop_duplicates("game_id")[
                ["game_id", "home_score", "away_score", "spread_line", "total_line"]
            ].dropna()
            for _, r in g.iterrows():
                game_scores[r["game_id"]] = {
                    "actual_home": r["home_score"], "actual_away": r["away_score"],
                    "spread_line": r["spread_line"], "total_line": r["total_line"],
                }

    game_data = []
    prop_data = []
    t0 = time.time()

    for n, (_, row) in enumerate(census.iterrows()):
        gid = row["game_id"]
        season = int(row["season"])
        if gid not in game_scores:
            continue
        gs = game_scores[gid]

        cp = pd.read_parquet(GAMES / f"{gid}.parquet")
        margin = cp["margin"].values.astype(float)
        total = cp["total"].values.astype(float)
        home_score = cp["home_score"].values.astype(float)
        away_score = cp["away_score"].values.astype(float)
        N = len(cp)

        actual_margin = gs["actual_home"] - gs["actual_away"]
        actual_total = gs["actual_home"] + gs["actual_away"]

        for sp in np.arange(-14, 14.5, 0.5):
            p = float((margin + sp > 0).mean())
            game_data.append({"family": "margin_side", "pred": p,
                              "hit": int(actual_margin + sp > 0), "season": season})

        for off in np.arange(-5, 5.5, 0.5):
            line = gs["total_line"] + off
            p = float((total > line).mean())
            game_data.append({"family": "total_side", "pred": p,
                              "hit": int(actual_total > line), "season": season})

        for ts_arr, actual_ts in [(home_score, gs["actual_home"]),
                                   (away_score, gs["actual_away"])]:
            for line in np.arange(10, 40, 0.5):
                p = float((ts_arr > line).mean())
                game_data.append({"family": "team_total", "pred": p,
                                  "hit": int(actual_ts > line), "season": season})

        pp = GAMES / f"{gid}_players.parquet"
        if not pp.exists():
            continue
        pdf = pd.read_parquet(pp)
        gpbp = pbp_cache.get(season)
        if gpbp is None:
            continue
        game_pbp = gpbp[gpbp["game_id"] == gid]
        if len(game_pbp) == 0:
            continue
        rec_stats, rush_stats, td_stats, pass_stats = actuals_fn(game_pbp)

        pmeans = pdf.groupby(["player_id", "position"]).agg(
            mean_tgt=("targets", "mean"), mean_pa=("pass_att", "mean")
        ).reset_index()
        top_tgt = set(pmeans.nlargest(10, "mean_tgt")["player_id"])
        top_pa = set(pmeans.nlargest(2, "mean_pa")["player_id"])
        selected = top_tgt | top_pa

        for pid in selected:
            psims = pdf[pdf["player_id"] == pid]
            if psims.empty:
                continue
            pos = psims["position"].iloc[0]
            stats = pd.DataFrame({"sim_id": np.arange(N)}).merge(
                psims[["sim_id", "receptions", "rec_yds", "rush_yds", "carries",
                        "pass_att", "pass_cmp", "pass_yds", "pass_td", "anytime_td"]],
                on="sim_id", how="left").fillna(0)

            ar = rec_stats[rec_stats["player_id"] == pid]
            actual_rec = int(ar["actual_rec"].iloc[0]) if len(ar) else 0
            actual_ry = int(ar["actual_rec_yds"].iloc[0]) if len(ar) else 0
            arush = rush_stats[rush_stats["player_id"] == pid]
            actual_rushy = int(arush["actual_rush_yds"].iloc[0]) if len(arush) else 0
            atd = td_stats[td_stats["player_id"] == pid]
            actual_atd = 1 if len(atd) > 0 else 0
            apass = pass_stats[pass_stats["player_id"] == pid]
            actual_pa = int(apass["actual_pass_att"].iloc[0]) if len(apass) else 0
            actual_py = int(apass["actual_pass_yds"].iloc[0]) if len(apass) else 0
            actual_pc = int(apass["actual_completions"].iloc[0]) if len(apass) else 0
            actual_ptd = int(apass["actual_pass_td"].iloc[0]) if len(apass) else 0

            for k in [3, 5, 7]:
                prop_data.append({"family": f"prop_rec_{pos}",
                    "pred": float((stats["receptions"] >= k).mean()),
                    "hit": int(actual_rec >= k), "season": season})
            for y in [20, 40, 60, 80, 100]:
                prop_data.append({"family": f"prop_rec_yds_{pos}",
                    "pred": float((stats["rec_yds"] >= y).mean()),
                    "hit": int(actual_ry >= y), "season": season})
            for y in [20, 40, 60, 80]:
                prop_data.append({"family": f"prop_rush_yds_{pos}",
                    "pred": float((stats["rush_yds"] >= y).mean()),
                    "hit": int(actual_rushy >= y), "season": season})
            prop_data.append({"family": f"prop_atd_{pos}",
                "pred": float((stats["anytime_td"] >= 1).mean()),
                "hit": actual_atd, "season": season})

            if pos == "QB":
                for k in [20, 25, 30, 35]:
                    prop_data.append({"family": "prop_pass_att_QB",
                        "pred": float((stats["pass_att"] >= k).mean()),
                        "hit": int(actual_pa >= k), "season": season})
                for k in [15, 20, 25]:
                    prop_data.append({"family": "prop_pass_cmp_QB",
                        "pred": float((stats["pass_cmp"] >= k).mean()),
                        "hit": int(actual_pc >= k), "season": season})
                for y in [150, 200, 250, 300]:
                    prop_data.append({"family": "prop_pass_yds_QB",
                        "pred": float((stats["pass_yds"] >= y).mean()),
                        "hit": int(actual_py >= y), "season": season})
                for k in [1, 2, 3]:
                    prop_data.append({"family": "prop_pass_td_QB",
                        "pred": float((stats["pass_td"] >= k).mean()),
                        "hit": int(actual_ptd >= k), "season": season})
                for y in [20, 40, 60]:
                    prop_data.append({"family": "prop_rush_yds_QB",
                        "pred": float((stats["rush_yds"] >= y).mean()),
                        "hit": int(actual_rushy >= y), "season": season})
                actual_ra = int(arush["actual_carries"].iloc[0]) if len(arush) else 0
                for k in [5, 8]:
                    prop_data.append({"family": "prop_rush_att_QB",
                        "pred": float((stats["carries"] >= k).mean()),
                        "hit": int(actual_ra >= k), "season": season})

        if (n + 1) % 200 == 0:
            print(f"  {n+1}/{len(census)} games ({time.time()-t0:.0f}s)")

    dt = time.time() - t0
    print(f"Assembled {len(game_data)} game + {len(prop_data)} prop rows in {dt:.0f}s")

    # Fit isotonic maps
    gdf = pd.DataFrame(game_data)
    pdf_all = pd.DataFrame(prop_data)
    cal_maps = {}

    for family in gdf["family"].unique():
        fd = gdf[(gdf.family == family) & (gdf.pred > 0.02) & (gdf.pred < 0.98)]
        if len(fd) < 100:
            continue
        ir = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
        ir.fit(fd.pred.values, fd.hit.values)
        xs = np.linspace(0.01, 0.99, 200)
        ys = ir.predict(xs)
        cal_maps[family] = {"x": xs.tolist(), "y": ys.tolist(), "n": int(len(fd))}

    for family in sorted(pdf_all["family"].unique()):
        fd = pdf_all[(pdf_all.family == family) & (pdf_all.pred > 0.02) & (pdf_all.pred < 0.98)]
        if len(fd) < 50:
            continue
        ir = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
        ir.fit(fd.pred.values, fd.hit.values)
        xs = np.linspace(0.01, 0.99, 200)
        ys = ir.predict(xs)
        cal_maps[family] = {"x": xs.tolist(), "y": ys.tolist(), "n": int(len(fd))}

    print(f"Fitted {len(cal_maps)} families")
    return cal_maps, census


def main():
    parser = argparse.ArgumentParser(description="Build calibration maps from fit checkpoints")
    parser.add_argument("--fit-dir", required=True, help="e.g. fit_5d2")
    parser.add_argument("--output", help="Write to this path instead of calibration_v1.json")
    parser.add_argument("--legacy-actuals", action="store_true",
                        help="Use pre-D62 actuals for faithfulness reproduction")
    args = parser.parse_args()

    cal_maps, census = build_maps_from_checkpoints(args.fit_dir, legacy_actuals=args.legacy_actuals)

    params = json.load(open(PARAMS_PATH))
    anchor = params.get("anchor", {})
    fit_n_games = int(census["converged"].sum())
    unconverged_share = float(1 - census["converged"].mean())

    output_path = Path(args.output) if args.output else None
    save_calibration(
        cal_maps,
        path=output_path,
        fit_dir=args.fit_dir,
        fit_n_games=fit_n_games,
        unconverged_share=unconverged_share,
        anchor=anchor,
    )


if __name__ == "__main__":
    main()
