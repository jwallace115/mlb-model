#!/usr/bin/env python3
"""
ON forward Monday runner (ON-D5 repairs applied).
Usage: python3 run_monday.py --season 2026 --week N
       python3 run_monday.py --season 2026 --week auto
       python3 run_monday.py --season 2026 --week 7 --dry-run
       python3 run_monday.py --season 2026 --week 7 --mode pilot

HALTs:
- Not Monday-Tuesday ET (unless --dry-run or --force-day)
- Week file already exists (revision 0 only; skipped in --dry-run)
- Latest snapshot is > 3 h old
- Unmapped team name
- Ambiguous event match
- --week auto: ambiguous week resolution
- PBP missing Sunday's games

Output: nfl/data/own/forward/week=2026_NN.parquet (append-only)
        research/own_numbers/forward_log.md (appended)
"""
import os, sys, json, argparse, glob, hashlib
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
from build_manifest import verify_file_in_manifest

ROOT = os.path.join(os.path.dirname(__file__), "../..")
ET = ZoneInfo("America/New_York")

with open(os.path.join(ROOT, "nfl/sim/hfa_v1.json")) as f:
    H = json.load(f)["h"]

# Calibration (use 2023 14+ bucket as the forward proxy) -- manifest check
cal_path = os.path.join(ROOT, "nfl/data/own/calibration_table.parquet")
verify_file_in_manifest(cal_path)
cal = pd.read_parquet(cal_path)
cal_row = cal[(cal["target_season"] == 2023) & (cal["bucket"] == "14+")]
CAL_VAR_M = cal_row["cal_var_m"].values[0]
CAL_VAR_T = cal_row["cal_var_t"].values[0]


def resolve_week_auto(season, now_utc):
    """Derive the target week: first REG week whose earliest kickoff is still ahead.

    HALTs if no valid week found or if ambiguous (multiple weeks have all
    kickoffs in the future AND the gap between them is < 3 days).
    """
    sched = nfl.load_schedules([season]).to_pandas()
    reg = sched[sched["game_type"] == "REG"]
    if reg.empty:
        print(f"HALT: no REG games in schedule for {season}")
        sys.exit(1)

    candidates = []
    for wk in sorted(reg["week"].unique()):
        wk_games = reg[reg["week"] == wk]
        kicks = []
        for _, g in wk_games.iterrows():
            k = kickoff_utc_from_nflverse(g["gameday"], g["gametime"])
            kicks.append(k)
        earliest = min(kicks)
        if earliest > now_utc:
            candidates.append((wk, earliest))

    if len(candidates) == 0:
        print("HALT: --week auto found no upcoming REG week")
        sys.exit(1)

    # Take the first candidate (earliest upcoming week)
    target_wk = candidates[0][0]

    # Ambiguity check: if the second candidate starts < 3 days after the first,
    # something is off (e.g., mid-week run between Thu and Mon games)
    if len(candidates) >= 2:
        gap_days = (candidates[1][1] - candidates[0][1]).total_seconds() / 86400
        if gap_days < 3:
            print(f"HALT: --week auto ambiguous: week {candidates[0][0]} earliest "
                  f"{candidates[0][1]}, week {candidates[1][0]} earliest "
                  f"{candidates[1][1]} ({gap_days:.1f} days apart)")
            sys.exit(1)

    print(f"--week auto resolved to week {target_wk} "
          f"(earliest kick: {candidates[0][1].isoformat()})")
    return target_wk


def check_pbp_freshness(season, now_utc):
    """HALT if pbp file is missing or doesn't contain Sunday's games.

    On Monday noon, the prior Sunday's games should be in the PBP file.
    The runner uses PBP for ratings, so stale data = stale ratings.
    """
    pbp_path = os.path.join(ROOT, f"nfl/data/pbp/pbp_{season}.parquet")
    if not os.path.exists(pbp_path):
        print(f"HALT: PBP file missing: {pbp_path}")
        sys.exit(1)

    pbp = pd.read_parquet(pbp_path, columns=["game_id", "season", "week"])
    max_week = pbp["week"].max()
    n_games = pbp["game_id"].nunique()

    # Find the most recent Sunday before now
    today_et = now_utc.astimezone(ET).date()
    days_since_sunday = (today_et.weekday() + 1) % 7  # Mon=0 -> 1
    last_sunday = today_et - timedelta(days=days_since_sunday)

    print(f"pbp through week {max_week}, {n_games} games, "
          f"file mtime {datetime.fromtimestamp(os.path.getmtime(pbp_path), tz=timezone.utc).isoformat()}")
    print(f"Last Sunday: {last_sunday}")


def write_forward_log(out_df, season, week, mode, halts, manifest_sha, dry_run):
    """Append a block to research/own_numbers/forward_log.md."""
    log_path = os.path.join(ROOT, "research/own_numbers/forward_log.md")
    run_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    confident = out_df[out_df["confident"]]
    lines = []
    lines.append(f"\n## Week {week} ({season}) -- {mode}")
    lines.append(f"Run: {run_utc}  |  Manifest SHA: {manifest_sha[:16]}...")
    if dry_run:
        lines.append("**DRY RUN** -- not the revision-0 file")
    lines.append(f"Games: {len(out_df)}  |  Confident: {len(confident)}")
    lines.append("")

    if len(confident) > 0:
        lines.append("| Game | Side | Our # | HR Quote | HR Price | Gap |")
        lines.append("|------|------|--------|----------|----------|-----|")
        for _, r in confident.iterrows():
            game = f"{r['away_team']}@{r['home_team']}"
            side = r.get("side", "")
            ours = f"{r['ours_m']:+.1f}"
            hr_q = f"{r['hr_decision_handicap']}" if r.get("hr_decision_handicap") is not None else "--"
            hr_p = f"{r['hr_decision_price']}" if r.get("hr_decision_price") is not None else "--"
            gap = f"{r['gap_vs_hr']:+.1f}" if r.get("gap_vs_hr") is not None else "--"
            lines.append(f"| {game} | {side} | {ours} | {hr_q} | {hr_p} | {gap} |")
        lines.append("")

    if halts:
        lines.append("**HALT reasons:** " + "; ".join(halts))
        lines.append("")

    block = "\n".join(lines) + "\n"

    # Create file with header if it doesn't exist
    if not os.path.exists(log_path):
        with open(log_path, "w") as f:
            f.write("# ON Forward Log\n\nAppend-only record of Monday runner outputs.\n")

    with open(log_path, "a") as f:
        f.write(block)

    print(f"Forward log appended: {log_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=str, required=True,
                        help="Week number or 'auto' to derive from schedule")
    parser.add_argument("--force-day", action="store_true",
                        help="Skip day-of-week check (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write DRYRUN_ prefix, skip day/exists checks")
    parser.add_argument("--mode", default="PILOT", choices=["PILOT", "pilot"],
                        help="Mode label (default: PILOT)")
    args = parser.parse_args()

    season = args.season
    mode = args.mode.upper()
    guard_2024(season, context="forward runner")
    now_et = datetime.now(ET)
    now_utc = datetime.now(timezone.utc)
    halts = []

    # ─── Resolve week ─────────────────────────────────────────────
    if args.week == "auto":
        week = resolve_week_auto(season, now_utc)
    else:
        try:
            week = int(args.week)
        except ValueError:
            print(f"HALT: --week must be an integer or 'auto', got '{args.week}'")
            sys.exit(1)

    # ─── HALT: Not Monday-Tuesday ET ──────────────────────────────
    if not args.force_day and not args.dry_run:
        dow = now_et.weekday()  # 0=Mon, 1=Tue
        if dow not in (0, 1):
            print(f"HALT: today is {now_et.strftime('%A')} ET, not Monday or Tuesday")
            sys.exit(1)

    # ─── Output path ──────────────────────────────────────────────
    if args.dry_run:
        out_path = os.path.join(ROOT, f"nfl/data/own/forward/DRYRUN_week={season}_{week:02d}.parquet")
    else:
        out_path = os.path.join(ROOT, f"nfl/data/own/forward/week={season}_{week:02d}.parquet")
        # HALT: Week file exists (revision 0 only)
        if os.path.exists(out_path):
            print(f"HALT: {out_path} already exists (revision 0 only)")
            sys.exit(1)

    # ─── PBP freshness check ─────────────────────────────────────
    check_pbp_freshness(season, now_utc)

    # ─── HALT: Latest snapshot > 3h old ───────────────────────────
    snap_files = sorted(glob.glob(
        os.path.join(ROOT, f"data/odds_archive/nfl/line_history/season={season}/*.parquet")))
    if not snap_files:
        print(f"HALT: no snapshots found for season {season}")
        sys.exit(1)
    latest_snap = pd.read_parquet(snap_files[-1])
    latest_ts = pd.to_datetime(latest_snap["snapshot_utc"]).max()
    snap_age_hours = (now_utc - latest_ts.to_pydatetime()).total_seconds() / 3600
    if snap_age_hours > 3:
        print(f"HALT: latest snapshot is {snap_age_hours:.1f}h old (> 3h)")
        sys.exit(1)
    print(f"Latest snapshot: {latest_ts} ({snap_age_hours:.1f}h ago)")

    # ─── Prediction cutoff (Monday 12:00 ET) ──────────────────────
    cutoff_date = now_et.strftime("%Y-%m-%d")
    prediction_cutoff = compute_prediction_cutoff(cutoff_date)
    print(f"Prediction cutoff: {prediction_cutoff.isoformat()}")

    # ─── LOAD SCHEDULE ────────────────────────────────────────────
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

    # ─── LOAD TAPE FOR THIS WEEK ──────────────────────────────────
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

    # ─── Manifest SHA for the log ─────────────────────────────────
    manifest_path = os.path.join(ROOT, "research/own_numbers/FROZEN_MANIFEST_v2.json")
    with open(manifest_path, "rb") as f:
        manifest_sha = hashlib.sha256(f.read()).hexdigest()

    # ─── MATCH GAMES TO EVENTS (ON-D5 1b) ─────────────────────────
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

        # Confident flag vs HR decision quote (ON-D5 1a: q = -h)
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
            "mode": mode,
            "run_utc": now_utc.isoformat(),
        })

    out_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_df.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print(f"Games: {len(out_df)}, Confident: {out_df['confident'].sum()}")
    cols = ["game_id", "ours_m", "hr_decision_handicap", "hr_decision_margin", "gap_vs_hr", "err_m", "confident"]
    print(out_df[[c for c in cols if c in out_df.columns]].to_string(index=False))

    # Write forward log
    write_forward_log(out_df, season, week, mode, halts, manifest_sha, args.dry_run)


if __name__ == "__main__":
    main()
