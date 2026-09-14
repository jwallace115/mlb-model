#!/usr/bin/env python3
"""
Phase 3b: Anchored backtest WITH player layer.
Usage: python3 nfl/sim/run_cal_players.py <season>

Per game: up to 4 anchoring iterations (stop at |Δm|<0.25, |Δt|<0.5).
Reduces each game to team summary + player prop indicator summaries.
Writes incrementally to nfl/data/sim/outputs/cal_players_<season>.parquet.
Resumes from last written game if restarted.
"""
import sys, time, os, gc, numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "nfl", "data", "sim", "outputs")
os.makedirs(OUT, exist_ok=True)

_load_tables()
team_r, tend, sit, kicker, league = _load_ratings()
pu = pd.read_parquet(os.path.join(ROOT, "nfl/data/sim/ratings/player_usage_weekly.parquet"))
au = pd.read_parquet(os.path.join(ROOT, "nfl/data/sim/ratings/active_universe_weekly.parquet"))
kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
          player_usage=pu, active_uni=au)
J_inv = np.array([[0.07450484, 0.10168527], [-0.08895527, 0.1277827]])

season = int(sys.argv[1])
N_SIMS = 1000

pbp = pd.read_parquet(os.path.join(ROOT, f"nfl/data/pbp/pbp_{season}.parquet"),
    columns=["game_id", "season", "week", "home_team", "away_team",
             "home_score", "away_score", "spread_line", "total_line"])
sg = pbp.drop_duplicates("game_id")
sg = sg[sg["week"] <= 18].reset_index(drop=True)

# Load actual player stats for scoring
pbp_full = pd.read_parquet(os.path.join(ROOT, f"nfl/data/pbp/pbp_{season}.parquet"))
passes_all = pbp_full[(pbp_full["play_type"] == "pass") & pbp_full["down"].notna() & (pbp_full["sack"] != 1)]
rushes_all = pbp_full[(pbp_full["play_type"] == "run") & pbp_full["down"].notna() & pbp_full["rusher_player_id"].notna()]

# Resume: check which games already done
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
    seed = hash((gid, 42)) % (2**31)
    mkt_margin = float(spread)
    mkt_total = float(tl)

    # Anchoring: up to 4 iterations
    dh, da = 0.0, 0.0
    raw_m = raw_t = None
    converged = False
    n_iter = 0
    for it in range(4):
        result = simulate_game(
            g["home_team"], g["away_team"], season, int(g["week"]),
            n_sims=N_SIMS, seed=seed,
            epa_home_offset=dh, epa_away_offset=da, **kw)
        if isinstance(result, tuple):
            td, pdf = result
        else:
            td, pdf = result, None
        m = (td["home_score"] - td["away_score"]).mean()
        t_val = (td["home_score"] + td["away_score"]).mean()
        if it == 0:
            raw_m, raw_t = m, t_val
        me = mkt_margin - m
        te = mkt_total - t_val
        n_iter = it + 1
        if abs(me) < 0.25 and abs(te) < 0.5:
            converged = True
            break
        step = J_inv @ np.array([me, te])
        dh += step[0]; da += step[1]
        if it < 3:
            del td, pdf

    # Team summary
    margin = (td["home_score"] - td["away_score"]).values.astype(float)
    total = (td["home_score"] + td["away_score"]).values.astype(float)
    am = g["home_score"] - g["away_score"]
    at_ = g["home_score"] + g["away_score"]
    team_rows.append({
        "game_id": gid, "season": season, "week": int(g["week"]),
        "home_team": g["home_team"], "away_team": g["away_team"],
        "raw_m": raw_m, "raw_t": raw_t,
        "anch_m": margin.mean(), "anch_t": total.mean(),
        "mkt_m": mkt_margin, "mkt_t": mkt_total,
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

    # Player prop summaries
    if pdf is not None and len(pdf) > 0:
        # Actual stats for this game
        gp = passes_all[passes_all["game_id"] == gid]
        gr = rushes_all[rushes_all["game_id"] == gid]
        act_rec = gp[gp["receiver_player_id"].notna()].groupby("receiver_player_id").agg(
            actual_rec=("complete_pass", "sum"),
            actual_rec_yds=("yards_gained", lambda x: x[gp.loc[x.index, "complete_pass"] == 1].sum() if len(x) > 0 else 0),
        ).reset_index().rename(columns={"receiver_player_id": "player_id"})
        act_rush = gr.groupby("rusher_player_id").agg(
            actual_rush_yds=("yards_gained", "sum"),
            actual_carries=("play_id", "count"),
        ).reset_index().rename(columns={"rusher_player_id": "player_id"})
        # Check for TDs
        td_players = set()
        td_plays = pbp_full[(pbp_full["game_id"] == gid) & (pbp_full["touchdown"] == 1)]
        for col in ["rusher_player_id", "receiver_player_id"]:
            if col in td_plays.columns:
                td_players |= set(td_plays[col].dropna().values)

        # Per-player summaries (top players by sim targets/carries)
        pmeans = pdf.groupby(["player_id", "player_name", "position", "team"]).agg(
            mean_tgt=("targets", "mean")).reset_index()
        top_pids = pmeans.nlargest(12, "mean_tgt")["player_id"].values

        for pid in top_pids:
            psims = pdf[pdf["player_id"] == pid]
            if len(psims) == 0:
                continue
            pos = psims["position"].iloc[0]
            pname = psims["player_name"].iloc[0]
            team = psims["team"].iloc[0]

            stats = pd.DataFrame({"sim_id": np.arange(N_SIMS)}).merge(
                psims[["sim_id", "receptions", "rec_yds", "carries", "rush_yds",
                       "pass_yds", "pass_td", "anytime_td"]],
                on="sim_id", how="left").fillna(0)

            ar = act_rec[act_rec["player_id"] == pid]
            actual_rec = int(ar["actual_rec"].iloc[0]) if len(ar) else 0
            actual_ry = int(ar["actual_rec_yds"].iloc[0]) if len(ar) else 0
            arush = act_rush[act_rush["player_id"] == pid]
            actual_rushy = int(arush["actual_rush_yds"].iloc[0]) if len(arush) else 0
            actual_car = int(arush["actual_carries"].iloc[0]) if len(arush) else 0
            actual_atd = 1 if pid in td_players else 0

            row = {
                "game_id": gid, "season": season, "week": int(g["week"]),
                "player_id": pid, "player_name": pname, "position": pos, "team": team,
                "actual_rec": actual_rec, "actual_rec_yds": actual_ry,
                "actual_rush_yds": actual_rushy, "actual_carries": actual_car,
                "actual_atd": actual_atd,
            }
            # Prop indicators
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
        # Incremental save
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
# Final save
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
dm = (final["anch_m"] - final["mkt_m"]).abs()
dt_r = (final["anch_t"] - final["mkt_t"]).abs()
print(f"  Margin residual: median={dm.median():.3f}, p90={dm.quantile(0.9):.3f}, <0.25={((dm<0.25).mean()*100):.0f}%", flush=True)
print(f"  Total residual:  median={dt_r.median():.3f}, p90={dt_r.quantile(0.9):.3f}, <0.5={((dt_r<0.5).mean()*100):.0f}%", flush=True)
print(f"  pts/team: {(final['pts_h'].mean()+final['pts_a'].mean())/2:.1f}", flush=True)
