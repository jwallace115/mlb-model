#!/usr/bin/env python3
"""
ON forward Monday runner (ON-D5 repairs applied).
Usage: python3 run_monday.py --season 2026 --week N

HALTs:
- Not Monday-Tuesday ET
- Week file already exists (revision 0 only)
- Latest snapshot is > 3 h old
- Unmapped team name
- Ambiguous event match

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

from on_utils import (
    handicap_to_home_margin,
    compute_gap,
    is_confident,
    match_game_to_event,
    select_close_quote,
    select_decision_quote,
    stable_seed,
    kickoff_utc_from_nflverse,
    compute_prediction_cutoff,
    guard_2024,
)

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
    guard_2024(season, context="forward runner")
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

    # ─── Prediction cutoff (Monday 12:00 ET) ─────────────────────────
    cutoff_date = now_et.strftime("%Y-%m-%d")
    prediction_cutoff = compute_prediction_cutoff(cutoff_date)
    print(f"Prediction cutoff: {prediction_cutoff.isoformat()}")

    # ─── LOAD SCHEDULE ──────────────────────────────────────────────
    sched = nfl.load_schedules([season]).to_pandas()
    games = sched[(sched["game_type"] == "REG") & (sched["week"] == week)]
    if len(games) == 0:
        print(f"HALT: no REG games for {season} week {week}")
        sys.exit(1)

    # Ensure all requested games are still upcoming
    for _, g in games.iterrows():
        kick = kickoff_utc_from_nflverse(g["gameday"], g["gametime"])
        if kick < now_utc:
            print(f"WARNING: {g['game_id']} kicked off at {kick}, before now ({now_utc})")

    print(f"Games: {len(games)}")

    # ─── LOAD TAPE FOR THIS WEEK ────────────────────────────────────
    tape = pd.concat([pd.read_parquet(f) for f in snap_files], ignore_index=True)
    tape["snapshot_utc"] = pd.to_datetime(tape["snapshot_utc"], utc=True)
    tape["commence_time"] = pd.to_datetime(tape["commence_time"], utc=True)
    spreads = tape[tape["market"] == "spreads"].copy()
    totals = tape[tape["market"] == "totals"].copy()

    spreads["team_abbr"] = spreads["outcome_name"].map(FULL_TO_ABBR)
    unmapped = spreads[spreads["team_abbr"].isna()]["outcome_name"].unique()
    if len(unmapped) > 0:
        print(f"HALT: unmapped teams: {unmapped}")
        sys.exit(1)

    ABBR_TO_FULL = {v: k for k, v in FULL_TO_ABBR.items()}

    # ─── MATCH GAMES TO EVENTS (ON-D5 1b) ───────────────────────────
    results = []
    for _, g in games.iterrows():
        home = g["home_team"]
        away = g["away_team"]
        kick_utc = kickoff_utc_from_nflverse(g["gameday"], g["gametime"])

        event_id = match_game_to_event(home, away, kick_utc, season, spreads)

        # Get decision and close quotes for HR and Pinnacle
        hr_decision_h = hr_close_h = pin_decision_h = pin_close_h = None
        hr_decision_ts = hr_close_ts = pin_decision_ts = pin_close_ts = None
        hr_decision_price = hr_close_price = None
        close_flag_hr = close_flag_pin = None

        if event_id:
            for book, prefix in [("hardrockbet_fl", "hr"), ("pinnacle", "pin")]:
                sp = spreads[(spreads["event_id"] == event_id) &
                             (spreads["bookmaker"] == book) &
                             (spreads["team_abbr"] == home)]
                if len(sp) > 0:
                    # Decision quote: last before prediction cutoff
                    dq = select_decision_quote(sp, prediction_cutoff)
                    # Close quote: last before kickoff (ON-D5 1c)
                    cq, cflag = select_close_quote(sp, kick_utc)

                    if prefix == "hr":
                        if dq is not None:
                            hr_decision_h = dq["point"]
                            hr_decision_ts = str(dq["snapshot_utc"])
                            hr_decision_price = dq["price"]
                        if cq is not None:
                            hr_close_h = cq["point"]
                            hr_close_ts = str(cq["snapshot_utc"])
                            hr_close_price = cq["price"]
                            close_flag_hr = cflag
                    else:
                        if dq is not None:
                            pin_decision_h = dq["point"]
                            pin_decision_ts = str(dq["snapshot_utc"])
                        if cq is not None:
                            pin_close_h = cq["point"]
                            pin_close_ts = str(cq["snapshot_utc"])
                            close_flag_pin = cflag

        # Run sim with stable seeds (ON-D5/D6 2c)
        chunk_m, chunk_t = [], []
        for ci in range(2):
            seed = stable_seed(g["game_id"], ci, season, week)
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

        # Confident flag vs HR decision quote (ON-D5 1a: q = −h)
        confident = is_confident(ours_m, hr_decision_h, err_m)
        gap = compute_gap(ours_m, hr_decision_h)

        # Direction side, recorded at decision time (immutable)
        side = None
        if gap is not None and gap != 0:
            q = handicap_to_home_margin(hr_decision_h)
            side = "home" if ours_m > q else "away"

        results.append({
            "game_id": g["game_id"],
            "season": season,
            "week": week,
            "home_team": home,
            "away_team": away,
            "kickoff_utc": kick_utc.isoformat(),
            "prediction_cutoff_utc": prediction_cutoff.isoformat(),
            "ours_m": round(ours_m, 4),
            "ours_t": round(ours_t, 4),
            "err_m": round(err_m, 4),
            "err_t": round(err_t, 4),
            # HR decision quote (at cutoff)
            "hr_decision_handicap": hr_decision_h,
            "hr_decision_margin": handicap_to_home_margin(hr_decision_h),
            "hr_decision_price": hr_decision_price,
            "hr_decision_ts": hr_decision_ts,
            # HR close quote (last pre-kick)
            "hr_close_handicap": hr_close_h,
            "hr_close_margin": handicap_to_home_margin(hr_close_h),
            "hr_close_price": hr_close_price,
            "hr_close_ts": hr_close_ts,
            "hr_close_flag": close_flag_hr,
            # Pinnacle decision quote
            "pin_decision_handicap": pin_decision_h,
            "pin_decision_margin": handicap_to_home_margin(pin_decision_h),
            "pin_decision_ts": pin_decision_ts,
            # Pinnacle close quote
            "pin_close_handicap": pin_close_h,
            "pin_close_margin": handicap_to_home_margin(pin_close_h),
            "pin_close_ts": pin_close_ts,
            "pin_close_flag": close_flag_pin,
            # Selection
            "gap_vs_hr": round(gap, 4) if gap is not None else None,
            "confident": confident,
            "side": side,
            "event_id": event_id,
            "mode": "PILOT",
            "run_utc": now_utc.isoformat(),
        })

    out_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_df.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print(f"Games: {len(out_df)}, Confident: {out_df['confident'].sum()}")
    cols = ["game_id", "ours_m", "hr_decision_handicap", "hr_decision_margin", "gap_vs_hr", "err_m", "confident"]
    print(out_df[[c for c in cols if c in out_df.columns]].to_string(index=False))


if __name__ == "__main__":
    main()
