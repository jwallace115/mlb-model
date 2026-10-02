#!/usr/bin/env python3
"""D271: the weekly input refresh for the forward run (run on the Mac before each window).

    python3 nfl/sim/refresh_inputs.py --week 4

Why it exists. D271 found the forward run consuming a usage table and an active universe
built on 2026-09-19 (week-1 games only), and QB/kicker ratings that never had a row for
the week being predicted. The documented refresh (pull_nflverse_inputs + ratings.py)
never ran usage.py, and the freshness gate accepted copied-forward rows.

What it does, in order (any failure restores the ratings directory and exits non-zero):
 0. preflight: the ratings tables' fit-window fingerprint equals FREEZE_v1's
    usage_fingerprint (the calibration was fitted on exactly those rows);
 1. pull_nflverse_inputs.py  (rosters_weekly, depth_charts, injuries);
 2. PBP for the CURRENT season only (pbp_2026.parquet) — earlier seasons are never re-pulled;
 3. usage.py   (player_usage_weekly, active_universe_weekly);
 4. ratings.py (team ratings, tendencies, situational tendencies, QB, kickers, baselines),
    never with --write-params; params_v1.json and the engine fingerprint must be unchanged;
 5. SPLICE: every table keeps its pre-refresh rows for every season except the current
    one, and takes the rebuilt rows for the current season only. nflverse revises
    historical rosters (positions, names), and a full rebuild moves 2021-2025 rows
    (D271: verified on the 2026-09-30 rosters). Historical rows are the fitted object and
    never change here;
 6. the fit-window fingerprint must still equal FREEZE_v1's;
 7. report: run_forward_v1._team_freshness — the forward run's own gate — for every team
    playing in --week, on the refreshed files. Exit 1 if any team fails.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SEASON = 2026
RATINGS = ROOT / "nfl" / "data" / "sim" / "ratings"
PBP = ROOT / "nfl" / "data" / "pbp"
PARAMS = ROOT / "nfl" / "sim" / "params_v1.json"
FREEZE = ROOT / "research" / "nfl_sim" / "FREEZE_v1.json"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _run(script):
    print(f"\n── {script} ──", flush=True)
    subprocess.run([sys.executable, str(ROOT / "nfl" / "sim" / script)], cwd=str(ROOT),
                   check=True)


def splice(old, new, season=SEASON):
    """Rows of `old` for every season but `season`, rows of `new` for `season` only, with
    the old column order and dtypes."""
    keep = old[old["season"] != season]
    cur = new[new["season"] == season].copy()
    for c in old.columns:
        if c not in cur.columns:
            cur[c] = pd.NA
    cur = cur[list(old.columns)]
    for c in old.columns:
        try:
            cur[c] = cur[c].astype(old[c].dtype)
        except (TypeError, ValueError):
            pass
    return pd.concat([keep, cur], ignore_index=True)


def freshness_report(week):
    """The forward run's own gate on the refreshed files, for every team playing `week`."""
    from nfl.sim.run_forward_v1 import (_team_freshness, _last_played_weeks, _load_schedule,
                                        RATINGS_FILES)
    sched, src = _load_schedule(SEASON, ROOT)
    games = sched[(sched["week"] == week) & (sched["game_type"] == "REG")]
    teams = sorted(set(games["home_team"]) | set(games["away_team"]))
    last_week = _last_played_weeks(PBP / f"pbp_{SEASON}.parquet", week)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        for f in RATINGS_FILES:
            shutil.copy2(RATINGS / f, d / f)
        for f in ("rosters_weekly.parquet", "injuries.parquet"):
            shutil.copy2(PBP / f, d / f)
        try:
            table = _team_freshness(d, SEASON, week, teams, last_week)
        except SystemExit as e:
            print(f"\nFRESHNESS FAILED for week {week} (schedule: {src}):\n{e}")
            return False
    print(f"\nFreshness for week {week} ({len(teams)} teams, schedule: {src}): PASS")
    for t, row in table.items():
        print(f"  {t}: " + ", ".join(f"{k}={v}" for k, v in row.items()))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True, help="the week about to be predicted")
    ap.add_argument("--report-only", action="store_true",
                    help="skip the refresh; only run the freshness report")
    a = ap.parse_args(argv)
    if a.report_only:
        return 0 if freshness_report(a.week) else 1

    from nfl.sim.calibration import FIT_INPUT_FILES, usage_fingerprint, engine_fingerprint
    freeze = json.loads(FREEZE.read_text())
    fp0 = usage_fingerprint()
    if fp0 != freeze["usage_fingerprint"]:
        raise SystemExit(f"HALT: the ratings tables' fit window ({fp0}) is not FREEZE_v1's "
                         f"({freeze['usage_fingerprint']}) BEFORE the refresh — not touching them")
    eng0, params0 = engine_fingerprint(), _sha(PARAMS)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT.parent / "mlb-model-archive" / "nfl_ratings_backups" / ts   # outside git
    backup.mkdir(parents=True)
    for f in FIT_INPUT_FILES:
        shutil.copy2(RATINGS / f, backup / f)
    print(f"Backed up {len(FIT_INPUT_FILES)} tables to {backup}")

    try:
        _run("pull_nflverse_inputs.py")
        print(f"\n── PBP {SEASON} only ──", flush=True)
        from nfl.sim.pull_pbp import pull_season, write_safe
        df = pull_season(SEASON)
        write_safe(df, PBP / f"pbp_{SEASON}.parquet")
        print(f"  pbp_{SEASON}: {len(df):,} rows, weeks {sorted(df['week'].unique())}")
        _run("usage.py")
        _run("ratings.py")
        if _sha(PARAMS) != params0:
            raise SystemExit("HALT: params_v1.json changed during the refresh")
        if engine_fingerprint() != eng0:
            raise SystemExit("HALT: the engine fingerprint changed during the refresh")
        print(f"\n── splice: rows for seasons != {SEASON} kept from before the refresh ──")
        for f in FIT_INPUT_FILES:
            old, new = pd.read_parquet(backup / f), pd.read_parquet(RATINGS / f)
            out = splice(old, new)
            out.to_parquet(RATINGS / f, index=False)
            print(f"  {f}: {SEASON} weeks {sorted(out.loc[out['season'] == SEASON, 'week'].unique()) if 'week' in out.columns else '-'}")
        fp1 = usage_fingerprint()
        if fp1 != freeze["usage_fingerprint"]:
            raise SystemExit(f"HALT: fit-window fingerprint after the splice is {fp1}, not "
                             f"FREEZE_v1's {freeze['usage_fingerprint']}")
        print(f"\nFit-window fingerprint unchanged: {fp1}")
    except BaseException:
        for f in FIT_INPUT_FILES:
            shutil.copy2(backup / f, RATINGS / f)
        print(f"\nRESTORED the ratings tables from {backup}")
        raise
    return 0 if freshness_report(a.week) else 1


if __name__ == "__main__":
    sys.exit(main())
