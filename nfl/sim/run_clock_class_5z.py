#!/usr/bin/env python3
"""
5Z Item 0: Per-class clock comparison. Sim play_log vs PBP real side.
Classes (identical both sides): run, first_down_rush, complete_inbounds,
first_down_pass, incomplete, sack, timeout_followed, drive_ending, kneel, spike, eoh/fgs.
"""
import sys, time, gc
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed
from nfl.sim.actuals_k1 import PLAY_TYPES

SEASONS = [2021, 2022, 2023, 2024]
N_SIMS = 100


def load_sample_games():
    with open(ROOT / "research" / "nfl_sim" / "phase5z_sample.txt") as f:
        return [line.strip() for line in f if line.strip()]


def score_state(sd):
    if sd <= -9: return "trail9+"
    if sd <= -1: return "trail1-8"
    if sd == 0: return "tied"
    if sd <= 8: return "lead1-8"
    return "lead9+"


def build_real_snaps(game_ids=None):
    """Build real per-snap data from PBP 2021-24 REG.

    elapsed = time to the NEXT scrimmage snap, capped at the quarter end.
    Class from PBP fields."""
    frames = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        if game_ids is not None:
            df = df[df["game_id"].isin(game_ids)]

        # Exclude 2pt attempts
        two_pt = df.get("two_point_attempt", pd.Series(0, index=df.index)).fillna(0)
        scrim = df[df["play_type"].isin(PLAY_TYPES) & (two_pt == 0)].copy()
        scrim = scrim.sort_values(["game_id", "game_seconds_remaining"], ascending=[True, False])

        # Next scrimmage snap in the same game
        scrim["next_gsr"] = scrim.groupby("game_id")["game_seconds_remaining"].shift(-1)
        scrim["elapsed_raw"] = scrim["game_seconds_remaining"] - scrim["next_gsr"]

        # Cap at quarter end: elapsed = min(raw, time_left_in_quarter)
        scrim["qtr_sec_left"] = scrim["game_seconds_remaining"] - (4 - scrim["qtr"].clip(upper=4)) * 900
        scrim["qtr_sec_left"] = scrim["qtr_sec_left"].clip(lower=0)

        # For last play of game/half (next_gsr is NaN or crosses quarter): use remaining quarter time
        last_play = scrim["elapsed_raw"].isna() | (scrim["elapsed_raw"] < 0) | (scrim["elapsed_raw"] >= 120)
        scrim.loc[last_play, "elapsed_raw"] = scrim.loc[last_play, "qtr_sec_left"]

        scrim["elapsed_capped"] = scrim[["elapsed_raw", "qtr_sec_left"]].min(axis=1).clip(lower=0)
        scrim["elapsed"] = scrim["elapsed_capped"]

        # Filter: elapsed >= 0 (keep all, including last plays)
        scrim = scrim[scrim["elapsed"] >= 0].copy()

        # Classify
        # Default: based on play_type and outcome
        scrim["play_class"] = "run"  # default for run plays
        pass_mask = scrim["play_type"] == "pass"
        scrim.loc[pass_mask & (scrim["incomplete_pass"] == 1), "play_class"] = "incomplete"
        # Sacks are classified as complete_inbounds (matching sim's clock-table classification)
        scrim.loc[pass_mask & (scrim["sack"] == 1), "play_class"] = "complete_inbounds"
        scrim.loc[pass_mask & (scrim["complete_pass"] == 1), "play_class"] = "complete_inbounds"

        # First downs override
        fd = scrim["first_down_rush"].fillna(0) == 1
        fd_pass = (scrim["first_down_pass"].fillna(0) == 1)
        scrim.loc[fd, "play_class"] = "first_down_rush"
        scrim.loc[fd_pass, "play_class"] = "first_down_pass"

        # Kneels and spikes
        scrim.loc[scrim["play_type"] == "qb_kneel", "play_class"] = "kneel"
        scrim.loc[scrim["play_type"] == "qb_spike", "play_class"] = "spike"

        # Drive-ending: TD / INT / fumble_lost
        de = ((scrim["touchdown"].fillna(0) == 1) |
              (scrim["interception"].fillna(0) == 1) |
              (scrim["fumble_lost"].fillna(0) == 1))
        scrim.loc[de, "play_class"] = "drive_ending"

        # Timeout-followed: the NEXT PBP row is a timeout
        next_is_to = df.sort_values(["game_id", "play_id"])
        next_is_to["next_play_type"] = next_is_to.groupby("game_id")["play_type"].shift(-1)
        to_map = next_is_to.set_index(["game_id", "play_id"])["next_play_type"]
        scrim_keys = list(zip(scrim["game_id"], scrim["play_id"]))
        next_types = [to_map.get(k, "") for k in scrim_keys]
        timeout_mask = pd.Series(next_types, index=scrim.index) == "no_play"
        # Actually timeout is when next row has desc containing "Timeout"
        # Simpler: check if timeout column exists
        if "timeout" in df.columns:
            next_to = df.sort_values(["game_id", "play_id"]).groupby("game_id")["timeout"].shift(-1)
            # Map back
            to_df = df.sort_values(["game_id", "play_id"]).copy()
            to_df["next_timeout"] = to_df.groupby("game_id")["timeout"].shift(-1)
            to_map2 = to_df.set_index(["game_id", "play_id"])["next_timeout"]
            next_to_vals = [to_map2.get(k, 0) for k in scrim_keys]
            timeout_mask = pd.Series(next_to_vals, index=scrim.index).fillna(0) == 1

        scrim.loc[timeout_mask & (scrim["play_class"] != "drive_ending"), "play_class"] = "timeout_followed"

        # Score state
        scrim["score_state"] = scrim["score_differential"].apply(score_state)

        scrim["season"] = s
        frames.append(scrim[["game_id", "season", "qtr", "elapsed", "elapsed_capped",
                              "play_class", "score_state", "yardline_100"]])

    return pd.concat(frames, ignore_index=True)


def build_sim_snaps(play_log):
    """Classify sim play_log into the same classes."""
    pl = play_log.copy()
    pl["play_class"] = pl["event_class"]

    # Map sim event_class to the unified class names
    # Sim classes: run, first_down_rush, complete_inbounds, first_down_pass, incomplete,
    #              drive_ending, kneel, spike, eoh, fgs, timeout_stopped
    # Need to map: eoh/fgs -> "eoh_fgs", timeout_stopped -> "timeout_followed"
    pl.loc[pl["play_class"].isin(["eoh", "fgs"]), "play_class"] = "eoh_fgs"
    pl.loc[pl["play_class"] == "timeout_stopped", "play_class"] = "timeout_followed"

    # Score state from score_diff (already in offence's perspective)
    # Wait — the play_log has score_state column from the engine. But let me check...
    # Play log columns: sim_id, qtr, clock_before, elapsed, event_class, score_state, clock_period, pace_mult
    # score_state is already there! But it might be "" for some events.
    if "score_state" in pl.columns:
        # Use it directly (it's the engine's score_state key)
        pass
    else:
        pl["score_state"] = "unknown"

    return pl


def main():
    t0 = time.time()

    sample_gids = load_sample_games()
    print(f"Sample: {len(sample_gids)} games")

    # Load sim data (re-run to get play_log)
    print("Running sim...")
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    rng = np.random.default_rng(42)
    games = []
    for s in SEASONS:
        df = pd.read_parquet(ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet")
        df = df[(df["season_type"] == "REG") & (df["week"] <= 18)]
        gids = sorted(df["game_id"].unique())
        chosen = sorted(rng.choice(gids, 50, replace=False))
        gs = df[df["game_id"].isin(chosen)].drop_duplicates("game_id")[
            ["game_id", "home_team", "away_team", "week"]
        ].to_dict("records")
        games.extend([{**g, "season": s} for g in gs])

    all_play_logs = []
    all_drive_logs = []
    all_team = []
    for gi, g in enumerate(games):
        seed = stable_seed((g["home_team"], g["away_team"], g["season"], int(g["week"]), 42))
        r = simulate_game(g["home_team"], g["away_team"], g["season"], int(g["week"]),
                          n_sims=N_SIMS, seed=seed, team_r=team_r, tend=tend, sit=sit,
                          kicker=kicker, league=league, drive_log=True)
        r["game_id"] = g["game_id"]; r["season"] = g["season"]
        all_team.append(r[["game_id","season","home_score","away_score","plays","drives","ev_safeties","ev_punts","ev_tds","ot_flag"]].copy())

        pl = r.attrs.get("play_log")
        if pl is not None and len(pl) > 0:
            pl = pl.copy(); pl["game_id"] = g["game_id"]; pl["season"] = g["season"]
            all_play_logs.append(pl)

        dl = r.attrs.get("drive_log")
        if dl is not None:
            dldf = pd.DataFrame(dl) if not isinstance(dl, pd.DataFrame) else dl.copy()
            dldf["game_id"] = g["game_id"]; dldf["season"] = g["season"]
            all_drive_logs.append(dldf)

        if (gi+1) % 50 == 0:
            print(f"  {gi+1}/{len(games)} ({time.time()-t0:.0f}s)")
        gc.collect()

    team_df = pd.concat(all_team, ignore_index=True)
    sim_pl = pd.concat(all_play_logs, ignore_index=True) if all_play_logs else pd.DataFrame()
    sim_dl = pd.concat(all_drive_logs, ignore_index=True) if all_drive_logs else pd.DataFrame()
    n_sims_total = len(games) * N_SIMS

    print(f"\nSim: {len(sim_pl)} play_log rows, {len(sim_dl)} drive_log rows")

    # NULL CHECK: sim quarter sums
    print("\n=== NULL CHECK: sim quarter sums ===")
    if len(sim_pl) > 0:
        for q in [1, 2, 3, 4]:
            qp = sim_pl[sim_pl["qtr"] == q]
            q_total_pg = qp.groupby(["game_id", "sim_id"])["elapsed"].sum().mean()
            print(f"  Q{q}: sim mean {q_total_pg:.1f}s")

    # Real side: sample games
    print("\nLoading real snaps (sample)...")
    real_sample = build_real_snaps(game_ids=set(sample_gids))
    n_real_sample = real_sample["game_id"].nunique()
    print(f"  {len(real_sample)} snaps from {n_real_sample} games")

    # NULL CHECK: real quarter sums
    print("\n=== NULL CHECK: real quarter sums ===")
    for q in [1, 2, 3, 4]:
        qr = real_sample[real_sample["qtr"] == q]
        q_total_pg = qr.groupby("game_id")["elapsed_capped"].sum().mean()
        print(f"  Q{q}: real mean {q_total_pg:.1f}s")

    # Real side: all K1 games
    print("\nLoading real snaps (all K1)...")
    real_all = build_real_snaps()
    n_real_all = real_all["game_id"].nunique()
    print(f"  {len(real_all)} snaps from {n_real_all} games")

    # Classify sim
    sim_snaps = build_sim_snaps(sim_pl)

    # === TABLE (a): per class ===
    print(f"\n{'='*80}")
    print("TABLE (a): per class — snaps/game and mean elapsed")
    print(f"{'='*80}")
    # Note: sack merged into complete_inbounds on both sides (sim has no separate sack class)
    classes = ["run", "first_down_rush", "complete_inbounds", "first_down_pass",
               "incomplete", "timeout_followed", "drive_ending", "kneel", "spike", "eoh_fgs"]

    rows_a = []
    print(f"{'class':20s} {'sim_spg':>8s} {'real_spg':>9s} {'sim_el':>7s} {'real_el':>8s} {'el_diff':>8s}")
    for cls in classes:
        s_sub = sim_snaps[sim_snaps["play_class"] == cls]
        # Map "sack" — the sim play_log doesn't have a "sack" class; sacks are in "complete_inbounds" or "incomplete"
        # Actually, the sim play_log event_class is the clock-table outcome_type, which doesn't distinguish sacks
        # Sacks go through the pass path and get "complete_inbounds" or "incomplete" outcome_type
        # So the sim has NO "sack" class. Report as N/A for the sim side.

        r_sub_sample = real_sample[real_sample["play_class"] == cls]
        r_sub_all = real_all[real_all["play_class"] == cls]

        s_spg = len(s_sub) / n_sims_total if n_sims_total > 0 else 0
        r_spg = len(r_sub_sample) / n_real_sample if n_real_sample > 0 else 0
        s_el = s_sub["elapsed"].mean() if len(s_sub) > 0 else float("nan")
        r_el = r_sub_sample["elapsed_capped"].mean() if len(r_sub_sample) > 0 else float("nan")
        el_diff = s_el - r_el if not (np.isnan(s_el) or np.isnan(r_el)) else float("nan")

        print(f"{cls:20s} {s_spg:8.2f} {r_spg:9.2f} {s_el:7.1f} {r_el:8.1f} {el_diff:+8.1f}")
        rows_a.append({"class": cls, "sim_spg": round(s_spg, 2), "real_spg": round(r_spg, 2),
                        "sim_elapsed": round(s_el, 2) if not np.isnan(s_el) else None,
                        "real_elapsed": round(r_el, 2) if not np.isnan(r_el) else None})

    # === TABLE (b): by score state ===
    print(f"\n{'='*80}")
    print("TABLE (b): mean elapsed by score state")
    print(f"{'='*80}")
    states = ["trail9+", "trail1-8", "tied", "lead1-8", "lead9+"]
    rows_b = []
    for ss in states:
        s_sub = sim_snaps[sim_snaps["score_state"] == ss]
        r_sub = real_sample[real_sample["score_state"] == ss]
        s_el = s_sub["elapsed"].mean() if len(s_sub) > 0 else float("nan")
        r_el = r_sub["elapsed_capped"].mean() if len(r_sub) > 0 else float("nan")
        s_spg = len(s_sub) / n_sims_total
        r_spg = len(r_sub) / n_real_sample
        print(f"  {ss:12s}: sim {s_el:.1f}s ({s_spg:.1f}/g)  real {r_el:.1f}s ({r_spg:.1f}/g)  diff {s_el-r_el:+.1f}")
        rows_b.append({"score_state": ss, "sim_elapsed": round(s_el, 2), "real_elapsed": round(r_el, 2),
                        "sim_spg": round(s_spg, 1), "real_spg": round(r_spg, 1)})

    # === TABLE (c): MIX vs RATE decomposition ===
    print(f"\n{'='*80}")
    print("TABLE (c): MIX vs RATE decomposition")
    print(f"{'='*80}")
    total_mix = 0
    total_rate = 0
    rows_c = []
    for cls in classes:
        s_sub = sim_snaps[sim_snaps["play_class"] == cls]
        r_sub = real_sample[real_sample["play_class"] == cls]
        s_spg = len(s_sub) / n_sims_total
        r_spg = len(r_sub) / n_real_sample
        s_el = s_sub["elapsed"].mean() if len(s_sub) > 0 else 0
        r_el = r_sub["elapsed_capped"].mean() if len(r_sub) > 0 else 0
        mix = (s_spg - r_spg) * r_el  # extra snaps at real rate
        rate = r_spg * (s_el - r_el)  # real snaps at rate difference
        total_mix += mix
        total_rate += rate
        if abs(mix) > 0.5 or abs(rate) > 0.5:
            print(f"  {cls:20s}: MIX {mix:+6.1f}s  RATE {rate:+6.1f}s  ({s_spg-r_spg:+.1f} snaps x {r_el:.0f}s + {r_spg:.0f} x {s_el-r_el:+.1f}s)")
        rows_c.append({"class": cls, "mix_s": round(mix, 2), "rate_s": round(rate, 2)})

    print(f"\n  TOTAL: MIX {total_mix:+.1f}s  RATE {total_rate:+.1f}s  SUM {total_mix+total_rate:+.1f}s")
    print(f"  Sim total clock/game: {sim_snaps.groupby(['game_id','sim_id'])['elapsed'].sum().mean():.1f}")
    print(f"  Real total clock/game: {real_sample.groupby('game_id')['elapsed_capped'].sum().mean():.1f}")

    mix_frac = abs(total_mix) / (abs(total_mix) + abs(total_rate)) * 100 if (abs(total_mix) + abs(total_rate)) > 0 else 0
    rate_frac = 100 - mix_frac
    print(f"  MIX fraction: {mix_frac:.0f}%, RATE fraction: {rate_frac:.0f}%")

    # Save parquet (small summary)
    summary_df = pd.DataFrame(rows_a)
    summary_df.to_parquet(ROOT / "research" / "nfl_sim" / "phase5z_clock_class.parquet", index=False)

    # Save drive log summary for Item 2
    if len(sim_dl) > 0:
        # Per-drive summary: start_bucket, result, points, plays
        sim_dl["start_bucket"] = pd.cut(sim_dl["start_yardline"],
                                          bins=[0, 20, 40, 60, 80, 100],
                                          labels=["opp20-1", "opp40-21", "mid41-60", "own21-40", "own1-20"],
                                          right=True, include_lowest=True)
        drive_summary = sim_dl.groupby(["game_id", "start_bucket"]).agg(
            n_drives=("sim_id", "count"),
            n_td=("result", lambda x: (x == "TD").sum()),
            n_fg=("result", lambda x: x.isin(["FG_made"]).sum()),
            total_points=("points", "sum"),
        ).reset_index()
        drive_summary_pg = drive_summary.groupby("start_bucket").agg(
            drives_pg=("n_drives", "mean"),
            td_pg=("n_td", "mean"),
            fg_pg=("n_fg", "mean"),
            pts_pg=("total_points", "mean"),
        ).reset_index()
        print(f"\n=== DRIVE SUMMARY (sim) ===")
        print(drive_summary_pg.to_string())

    total = time.time() - t0
    print(f"\nTotal runtime: {total:.0f}s ({total/60:.1f} min)")


if __name__ == "__main__":
    main()
