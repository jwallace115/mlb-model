#!/usr/bin/env python3
"""
Phase 3b: Anchored backtest WITH player layer.
Usage: python3 nfl/sim/run_cal_players.py <season>

Uses anchor.run_anchored_chunked (shared solver, D46).
Reduces each game to team summary + player prop indicator summaries.
Writes incrementally to nfl/data/sim/outputs/cal_players_<season>.parquet.
Resumes from last written game if restarted.
"""
import sys, time, os, gc, numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nfl.sim.engine import _load_tables, _load_ratings
from nfl.sim.anchor import run_anchored_chunked
from nfl.sim.actuals import actual_player_game_stats
from nfl.sim.seed_util import stable_seed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "nfl", "data", "sim", "outputs")


def run_cal_season(season, n_sims=1000):
    """Run calibration for one season. Uses shared solver."""
    os.makedirs(OUT, exist_ok=True)

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(os.path.join(ROOT, "nfl/data/sim/ratings/player_usage_weekly.parquet"))
    au = pd.read_parquet(os.path.join(ROOT, "nfl/data/sim/ratings/active_universe_weekly.parquet"))
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
              player_usage=pu, active_uni=au)

    pbp = pd.read_parquet(os.path.join(ROOT, f"nfl/data/pbp/pbp_{season}.parquet"),
        columns=["game_id", "season", "week", "home_team", "away_team",
                 "home_score", "away_score", "spread_line", "total_line"])
    sg = pbp.drop_duplicates("game_id")
    sg = sg[sg["week"] <= 18].reset_index(drop=True)

    pbp_full = pd.read_parquet(os.path.join(ROOT, f"nfl/data/pbp/pbp_{season}.parquet"))

    out_team = os.path.join(OUT, f"cal_players_team_{season}.parquet")
    out_props = os.path.join(OUT, f"cal_players_props_{season}.parquet")
    done_ids = set()
    if os.path.exists(out_team):
        done = pd.read_parquet(out_team)
        done_ids = set(done["game_id"].values)
        print(f"Resuming: {len(done_ids)} games already done", flush=True)

    team_rows = []
    prop_rows = []
    t0 = time.time()

    for i, (_, g) in enumerate(sg.iterrows()):
        gid = g["game_id"]
        if gid in done_ids:
            continue
        spread = g["spread_line"]; tl = g["total_line"]
        if pd.isna(spread) or pd.isna(tl):
            continue

        # Use the shared anchoring solver
        td, pdf, dh, da, n_iter, converged, raw_m, raw_t, anch_m, anch_t = \
            run_anchored_chunked(
                g["home_team"], g["away_team"], season, int(g["week"]),
                float(spread), float(tl), n_sims=n_sims, **kw)

        margin = (td["home_score"] - td["away_score"]).values.astype(float)
        total = (td["home_score"] + td["away_score"]).values.astype(float)
        am = g["home_score"] - g["away_score"]
        at_ = g["home_score"] + g["away_score"]
        team_rows.append({
            "game_id": gid, "season": season, "week": int(g["week"]),
            "home_team": g["home_team"], "away_team": g["away_team"],
            "raw_m": raw_m, "raw_t": raw_t,
            "anch_m": margin.mean(), "anch_t": total.mean(),
            "mkt_m": float(spread), "mkt_t": float(tl),
            "actual_m": am, "actual_t": at_,
            "dh": dh, "da": da, "converged": converged, "n_iter": n_iter,
            "pts_h": td["home_score"].mean(), "pts_a": td["away_score"].mean(),
            "p_hc": (margin - spread > 0).mean(), "ahc": int(am - spread > 0),
            "p_ov": (total > tl).mean(), "aov": int(at_ > tl),
            "p_m3": (np.abs(margin) == 3).mean(),
            "p_m7": (np.abs(margin) == 7).mean(),
            "sd_m": margin.std(),
            "p_hw": (margin > 0).mean(), "ahw": int(am > 0),
        })

        if pdf is not None and len(pdf) > 0:
            game_pbp = pbp_full[pbp_full["game_id"] == gid]
            rec_stats, rush_stats, td_stats, pass_stats = actual_player_game_stats(game_pbp)

            pmeans = pdf.groupby(["player_id", "player_name", "position", "team"]).agg(
                mean_tgt=("targets", "mean")).reset_index()
            top_pids = pmeans.nlargest(12, "mean_tgt")["player_id"].values

            N_actual = len(td)
            for pid in top_pids:
                psims = pdf[pdf["player_id"] == pid]
                if len(psims) == 0:
                    continue
                pos = psims["position"].iloc[0]
                pname = psims["player_name"].iloc[0]
                team = psims["team"].iloc[0]

                stats = pd.DataFrame({"sim_id": np.arange(N_actual)}).merge(
                    psims[["sim_id", "receptions", "rec_yds", "carries", "rush_yds",
                           "pass_yds", "pass_td", "anytime_td"]],
                    on="sim_id", how="left").fillna(0)

                ar = rec_stats[rec_stats["player_id"] == pid]
                actual_rec = int(ar["actual_rec"].iloc[0]) if len(ar) else 0
                actual_ry = int(ar["actual_rec_yds"].iloc[0]) if len(ar) else 0
                arush = rush_stats[rush_stats["player_id"] == pid]
                actual_rushy = int(arush["actual_rush_yds"].iloc[0]) if len(arush) else 0
                actual_car = int(arush["actual_carries"].iloc[0]) if len(arush) else 0
                atd_row = td_stats[td_stats["player_id"] == pid]
                actual_atd = 1 if len(atd_row) > 0 else 0

                row = {
                    "game_id": gid, "season": season, "week": int(g["week"]),
                    "player_id": pid, "player_name": pname, "position": pos, "team": team,
                    "actual_rec": actual_rec, "actual_rec_yds": actual_ry,
                    "actual_rush_yds": actual_rushy, "actual_carries": actual_car,
                    "actual_atd": actual_atd,
                }
                for k in range(2, 11):
                    row[f"p_rec_ge{k}"] = float((stats["receptions"] >= k).mean())
                for y in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]:
                    row[f"p_rec_yds_ge{y}"] = float((stats["rec_yds"] >= y).mean())
                for k in [5, 10, 15, 20]:
                    row[f"p_rush_att_ge{k}"] = float((stats["carries"] >= k).mean())
                for y in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
                    row[f"p_rush_yds_ge{y}"] = float((stats["rush_yds"] >= y).mean())
                if pos == "QB":
                    for y in [150, 175, 200, 225, 250, 275, 300, 325, 350]:
                        row[f"p_pass_yds_ge{y}"] = float((stats["pass_yds"] >= y).mean())
                    for k in [1, 2, 3]:
                        row[f"p_pass_td_ge{k}"] = float((stats["pass_td"] >= k).mean())
                row["p_atd"] = float((stats["anytime_td"] >= 1).mean())
                prop_rows.append(row)

        del td, pdf
        gc.collect()

        if (i + 1) % 50 == 0 or i == len(sg) - 1:
            elapsed = time.time() - t0
            n_done = len(team_rows) + len(done_ids)
            print(f"  {n_done}/{len(sg)} ({elapsed:.0f}s)", flush=True)
            tdf = pd.DataFrame(team_rows)
            if os.path.exists(out_team) and done_ids:
                old = pd.read_parquet(out_team)
                tdf = pd.concat([old, tdf], ignore_index=True)
            tdf.to_parquet(out_team, index=False)
            if prop_rows:
                pdf_out = pd.DataFrame(prop_rows)
                if os.path.exists(out_props) and done_ids:
                    old_p = pd.read_parquet(out_props)
                    pdf_out = pd.concat([old_p, pdf_out], ignore_index=True)
                pdf_out.to_parquet(out_props, index=False)
            done_ids |= set(r["game_id"] for r in team_rows)
            team_rows = []
            prop_rows = []

    dt = time.time() - t0
    if team_rows:
        tdf = pd.DataFrame(team_rows)
        if os.path.exists(out_team):
            old = pd.read_parquet(out_team)
            tdf = pd.concat([old, tdf], ignore_index=True)
        tdf.to_parquet(out_team, index=False)
    if prop_rows:
        pdf_out = pd.DataFrame(prop_rows)
        if os.path.exists(out_props):
            old_p = pd.read_parquet(out_props)
            pdf_out = pd.concat([old_p, pdf_out], ignore_index=True)
        pdf_out.to_parquet(out_props, index=False)

    final = pd.read_parquet(out_team)
    n_conv = final["converged"].sum() if "converged" in final.columns else "?"
    print(f"\nSeason {season}: {len(final)} games, {dt:.0f}s, converged={n_conv}/{len(final)}", flush=True)


if __name__ == "__main__":
    season = int(sys.argv[1])
    run_cal_season(season)
