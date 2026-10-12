#!/usr/bin/env python3
"""
ON-1 ITEM 4: Monday runner for forward Own Numbers.
Usage: python3 run_monday.py --season 2026 --week N

HALTs:
- Not Monday-Tuesday ET
- Week file already exists (revision 0 only)
- Latest snapshot is > 3 h old
- Unmapped team name

Output: nfl/data/own/forward/week=2026_NN.parquet (append-only)
MODE=PILOT
"""
import os, sys, json, argparse, glob
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

os.environ["SSL_CERT_FILE"] = __import__("certifi").where()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from nfl.sim.engine import simulate_game
from nfl.sim.names import FULL_TO_ABBR
import nflreadpy as nfl

ROOT = os.path.join(os.path.dirname(__file__), "../..")
ET = ZoneInfo("America/New_York")

with open(os.path.join(ROOT, "nfl/sim/hfa_v1.json")) as f:
    H = json.load(f)["h"]

# Calibration (use 2023 14+ bucket as the forward proxy)
cal = pd.read_parquet(os.path.join(ROOT, "nfl/data/own/calibration_table.parquet"))
cal_row = cal[(cal["target_season"] == 2023) & (cal["bucket"] == "14+")]
CAL_VAR_M = cal_row["cal_var_m"].values[0]
CAL_VAR_T = cal_row["cal_var_t"].values[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--force-day", action="store_true", help="Skip day-of-week check (testing)")
    args = parser.parse_args()

    season = args.season
    week = args.week
    now_et = datetime.now(ET)

    # ─── HALT: Not Monday-Tuesday ET ────────────────────────────────
    if not args.force_day:
        dow = now_et.weekday()  # 0=Mon, 1=Tue
        if dow not in (0, 1):
            print(f"HALT: today is {now_et.strftime('%A')} ET, not Monday or Tuesday")
            sys.exit(1)

    # ─── HALT: Week file exists ─────────────────────────────────────
    out_path = os.path.join(ROOT, f"nfl/data/own/forward/week={season}_{week:02d}.parquet")
    if os.path.exists(out_path):
        print(f"HALT: {out_path} already exists (revision 0 only)")
        sys.exit(1)

    # ─── HALT: Latest snapshot > 3h old ─────────────────────────────
    snap_files = sorted(glob.glob(
        os.path.join(ROOT, f"data/odds_archive/nfl/line_history/season={season}/*.parquet")))
    if not snap_files:
        print(f"HALT: no snapshots found for season {season}")
        sys.exit(1)
    latest_snap = pd.read_parquet(snap_files[-1])
    latest_ts = pd.to_datetime(latest_snap["snapshot_utc"]).max()
    now_utc = datetime.now(timezone.utc)
    snap_age_hours = (now_utc - latest_ts.to_pydatetime()).total_seconds() / 3600
    if snap_age_hours > 3:
        print(f"HALT: latest snapshot is {snap_age_hours:.1f}h old (> 3h)")
        sys.exit(1)
    print(f"Latest snapshot: {latest_ts} ({snap_age_hours:.1f}h ago)")

    # ─── LOAD SCHEDULE ──────────────────────────────────────────────
    sched = nfl.load_schedules([season]).to_pandas()
    games = sched[(sched["game_type"] == "REG") & (sched["week"] == week)]
    if len(games) == 0:
        print(f"HALT: no REG games for {season} week {week}")
        sys.exit(1)
    print(f"Games: {len(games)}")

    # ─── LOAD TAPE FOR THIS WEEK ────────────────────────────────────
    tape = pd.concat([pd.read_parquet(f) for f in snap_files], ignore_index=True)
    tape["snapshot_utc"] = pd.to_datetime(tape["snapshot_utc"])
    spreads = tape[tape["market"] == "spreads"].copy()
    totals = tape[tape["market"] == "totals"].copy()

    spreads["team_abbr"] = spreads["outcome_name"].map(FULL_TO_ABBR)
    unmapped = spreads[spreads["team_abbr"].isna()]["outcome_name"].unique()
    if len(unmapped) > 0:
        print(f"HALT: unmapped teams: {unmapped}")
        sys.exit(1)

    ABBR_TO_FULL = {v: k for k, v in FULL_TO_ABBR.items()}

    # ─── MATCH GAMES TO EVENTS ──────────────────────────────────────
    results = []
    for _, g in games.iterrows():
        home = g["home_team"]
        away = g["away_team"]
        home_full = ABBR_TO_FULL.get(home, home)
        away_full = ABBR_TO_FULL.get(away, away)

        candidates = spreads[spreads["outcome_name"].isin([home_full, away_full])]["event_id"].unique()
        event_id = None
        for eid in candidates:
            evt = spreads[spreads["event_id"] == eid]
            if set(evt["team_abbr"].unique()) >= {home, away}:
                event_id = eid
                break

        # Get HR and Pinnacle openers
        hr_open_sp = hr_open_tot = pin_open_sp = pin_open_tot = None
        if event_id:
            for book, prefix in [("hardrockbet_fl", "hr"), ("pinnacle", "pin")]:
                sp = spreads[(spreads["event_id"] == event_id) &
                             (spreads["bookmaker"] == book) &
                             (spreads["team_abbr"] == home)].sort_values("snapshot_utc")
                if len(sp) > 0:
                    if prefix == "hr":
                        hr_open_sp = sp.iloc[0]["point"]
                    else:
                        pin_open_sp = sp.iloc[0]["point"]

                tot = totals[(totals["event_id"] == event_id) &
                             (totals["bookmaker"] == book) &
                             (totals["outcome_name"] == "Over")].sort_values("snapshot_utc")
                if len(tot) > 0:
                    if prefix == "hr":
                        hr_open_tot = tot.iloc[0]["point"]
                    else:
                        pin_open_tot = tot.iloc[0]["point"]

        # Run sim
        chunk_m, chunk_t = [], []
        for ci in range(2):
            seed = hash((g["game_id"], ci)) % (2**31)
            result = simulate_game(home, away, season, week,
                                    n_sims=2500, seed=seed,
                                    epa_home_offset=H, epa_away_offset=-H)
            m = (result["home_score"] - result["away_score"]).values
            t = (result["home_score"] + result["away_score"]).values
            chunk_m.append(m.mean())
            chunk_t.append(t.mean())

        ours_m = np.mean(chunk_m)
        ours_t = np.mean(chunk_t)
        mc_se_m = np.std(chunk_m, ddof=1) / np.sqrt(2)
        mc_se_t = np.std(chunk_t, ddof=1) / np.sqrt(2)
        err_m = np.sqrt(mc_se_m**2 + CAL_VAR_M)
        err_t = np.sqrt(mc_se_t**2 + CAL_VAR_T)

        # Confident flag vs HR open
        confident = False
        if hr_open_sp is not None:
            gap = abs(ours_m - hr_open_sp)
            confident = gap >= err_m and gap >= 1.0

        results.append({
            "game_id": g["game_id"],
            "season": season,
            "week": week,
            "home_team": home,
            "away_team": away,
            "ours_m": round(ours_m, 2),
            "ours_t": round(ours_t, 2),
            "err_m": round(err_m, 2),
            "err_t": round(err_t, 2),
            "hr_spread_open": hr_open_sp,
            "hr_total_open": hr_open_tot,
            "pin_spread_open": pin_open_sp,
            "pin_total_open": pin_open_tot,
            "confident": confident,
            "mode": "PILOT",
            "run_utc": now_utc.isoformat(),
        })

    out_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_df.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print(f"Games: {len(out_df)}, Confident: {out_df['confident'].sum()}")
    print(out_df[["game_id", "ours_m", "hr_spread_open", "err_m", "confident"]].to_string(index=False))


if __name__ == "__main__":
    main()
