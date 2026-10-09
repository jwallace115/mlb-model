#!/usr/bin/env python3
"""One command per window: pull → sheet → reader → freeze → verify → adapt → top-20 → commit.

Usage:
  python3 nfl/pipeline/run_window.py --sport nfl --window mid --commit main
  python3 nfl/pipeline/run_window.py --sport nfl --window prekick --auto-prekick --commit main
  python3 nfl/pipeline/run_window.py --sport nfl --window adhoc --reader-model claude-opus-5-5 --commit none
  python3 nfl/pipeline/run_window.py --sport nfl --window open --no-pull --commit none
  python3 nfl/pipeline/run_window.py --sport ncaaf --window adhoc --no-pull --commit none

Steps (each prints date -u, the command, its exit; non-zero STOPs):
  1. pull: props + game-line snapshot (--no-pull skips; ncaaf requires --no-pull)
  2. sheet → reader_v3 → freeze --window <w> --reader-model <m> --reader-file reader_v3.py
  3. verify
  4. picks_adapters.py → build_top20.py --sport <SPORT> --print-top 20
  5. commit + push (if --commit main or --commit branch:<name>)

P26: one command per window, zero API credits on --no-pull.
P28: --commit, --auto-prekick, --reader-model defaults to reader_v3, WINDOW_HOURS updated.
P38: --sport ncaaf; CFBD week; --no-pull required for ncaaf.
"""
import argparse
import glob as globmod
import hashlib
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
NFL_PIPELINE = ROOT / "nfl" / "pipeline"
SHARED_PIPELINE = ROOT / "shared" / "pipeline"

WINDOW_HOURS = {
    "open": 168,     # full week
    "mid": 168,      # full week
    "late": 72,      # 3 days
    "prekick": 6,    # within 6h
    "adhoc": 168,    # whole upcoming slate
}

NCAAF_WINDOW_HOURS = {
    "open": 120,
    "mid": 72,
    "late": 48,
    "prekick": 4,
    "adhoc": 48,
}

# Prekick gate: [now + 2h52m, now + 3h08m]
PREKICK_LOW = timedelta(hours=2, minutes=52)
PREKICK_HIGH = timedelta(hours=3, minutes=8)


def _check_prekick_slot(commence_times):
    """True if any game kicks in [now + 2h52m, now + 3h08m]."""
    now = datetime.now(timezone.utc)
    low = now + PREKICK_LOW
    high = now + PREKICK_HIGH
    for ct in commence_times:
        try:
            dt = datetime.fromisoformat(str(ct).replace("Z", "+00:00"))
            if low <= dt <= high:
                return True
        except (ValueError, TypeError):
            continue
    return False


def _run(desc, cmd, cwd=ROOT, env=None):
    """Run a command, print timestamp + exit code. Non-zero exits the process."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n{'='*60}")
    print(f"[{ts}] {desc}")
    print(f"  cmd: {' '.join(str(c) for c in cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=str(cwd), env=env or os.environ,
                            capture_output=False, text=True)
    print(f"  exit: {result.returncode}")
    if result.returncode != 0:
        print(f"STOP: {desc} failed with exit {result.returncode}")
        sys.exit(result.returncode)
    return result


def _current_week():
    """Infer the current NFL week from the calendar (rough heuristic)."""
    now = datetime.now(timezone.utc)
    from datetime import date
    season_start = date(2026, 9, 10)
    delta = (now.date() - season_start).days
    return max(1, delta // 7 + 1)


def _ncaaf_week():
    """CFBD week number. Week 0 contains the last Saturday in August."""
    now = datetime.now(timezone.utc)
    from datetime import date
    aug31 = date(now.year, 8, 31)
    # Last Saturday in August: weekday 5 = Saturday
    last_sat = aug31 - timedelta(days=(aug31.weekday() + 2) % 7)
    # Week 0 starts on Thursday before that Saturday
    week0_start = last_sat - timedelta(days=2)
    delta = (now.date() - week0_start).days
    if delta < 0:
        return 0
    return delta // 7


def _reader_sha(reader_file):
    return hashlib.sha256(Path(reader_file).read_bytes()).hexdigest()[:8]


def _newest_injury_report(root, season, week):
    """Find the newest injury report for this week, if it exists on disk."""
    pattern = str(root / "research" / "nfl_sim" / "official_injuries"
                  / f"{season}_w{week:02d}" / "*.json")
    files = sorted(globmod.glob(pattern))
    return files[-1] if files else None


def _newest_snapshot_commence_times(root, sport="nfl"):
    """Read commence_times from the newest game-line snapshot."""
    sport_folder = "ncaaf" if sport == "ncaaf" else "nfl"
    tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history"
    snaps = []
    for sd in tape_dir.glob("season=*"):
        for p in sd.glob("snap_*Z.parquet"):
            snaps.append(p)
    if not snaps:
        return []
    newest = max(snaps, key=lambda p: p.name)
    try:
        import pandas as pd
        df = pd.read_parquet(newest)
        return df["commence_time"].unique().tolist()
    except Exception:
        return []


def _write_unquoted_sidecar(sheet_path, week, root, sport):
    """Write a CSV of upcoming events not quoted by the book of record."""
    import pandas as pd
    sheet = pd.read_csv(sheet_path)
    quoted_eids = set(sheet["event_id"]) if not sheet.empty else set()

    sport_folder = "ncaaf" if sport == "ncaaf" else "nfl"
    tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history" / "season=2026"
    snaps = sorted(tape_dir.glob("snap_*.parquet"))
    if not snaps:
        print("unquoted sidecar: no snapshots")
        return
    newest = pd.read_parquet(snaps[-1])
    now = datetime.now(timezone.utc)
    upcoming = newest[pd.to_datetime(newest["commence_time"], utc=True) > now]
    all_eids = set(upcoming["event_id"])
    unquoted_eids = all_eids - quoted_eids
    if not unquoted_eids:
        print("unquoted sidecar: 0 unquoted events")
        return

    unq = upcoming[upcoming["event_id"].isin(unquoted_eids)].drop_duplicates("event_id")
    rows = []
    for _, r in unq.iterrows():
        rows.append({"event_id": r["event_id"],
                      "home_team": r["home_team"],
                      "away_team": r["away_team"],
                      "commence_time": r["commence_time"]})
    out = pd.DataFrame(rows).sort_values("commence_time")

    board_dir = "ncaaf" if sport == "ncaaf" else "nfl"
    freeze_dir = root / board_dir / "data" / "board" / f"week=2026_{week:02d}" / "ai_opinions"
    freeze_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = freeze_dir / f"unquoted_{ts}.csv"
    out.to_csv(dest, index=False)
    print(f"unquoted sidecar: {len(out)} events (no Hard Rock line yet) -> {dest}")


def _commit_and_push(commit_mode, window, root, env, sport="nfl"):
    """Commit the frozen file + manifest (+ mac props + snapshot) and push."""
    if commit_mode == "none":
        return

    week_fn = _ncaaf_week if sport == "ncaaf" else _current_week
    week = week_fn()
    sport_board = "ncaaf" if sport == "ncaaf" else "nfl"
    freeze_dir = root / sport_board / "data" / "board" / f"week=2026_{week:02d}" / "ai_opinions"
    manifest = freeze_dir / "manifest.json"
    files_to_add = []
    if freeze_dir.exists():
        for f in freeze_dir.glob("ai_opinions_*.parquet"):
            files_to_add.append(str(f.relative_to(root)))
        if manifest.exists():
            files_to_add.append(str(manifest.relative_to(root)))

    if sport == "nfl":
        # Mac props file
        props_dir = root / "data" / "odds_archive" / "nfl" / "props"
        for mac_file in props_dir.glob("season=*/month=*/data_*_mac.parquet"):
            files_to_add.append(str(mac_file.relative_to(root)))
        for manual_dir in props_dir.glob("season=*/manual"):
            for f in manual_dir.glob("scratch_*.parquet"):
                files_to_add.append(str(f.relative_to(root)))

        # Recent snapshot
        tape_dir = root / "data" / "odds_archive" / "nfl" / "line_history"
        for sd in tape_dir.glob("season=*"):
            for f in sd.glob("snap_*Z.parquet"):
                files_to_add.append(str(f.relative_to(root)))

    # Adapters + top20
    for f in (root / "shared" / "pipeline").glob("picks*.html"):
        files_to_add.append(str(f.relative_to(root)))

    if not files_to_add:
        print("commit: no files to add")
        return

    reader_file = NFL_PIPELINE / "reader_v3.py"
    sha8 = _reader_sha(reader_file)
    n_files = len(files_to_add)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    msg = f"{sport} window {window} freeze {ts}: {n_files} files, reader_v3 {sha8}"

    git_env = dict(env or os.environ)
    for f in files_to_add:
        subprocess.run(["git", "add", f], cwd=str(root), env=git_env,
                        capture_output=True)

    result = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(root), env=git_env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"commit failed: {result.stderr[:200]}")
        sys.exit(1)
    print(f"commit: {result.stdout.strip()}")

    if commit_mode == "main":
        push_result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=str(root), env=git_env, capture_output=True, text=True)
        if push_result.returncode != 0:
            print(f"push failed: {push_result.stderr[:200]}")
            sys.exit(1)
        print(f"push: {push_result.stdout.strip()}")
    elif commit_mode.startswith("branch:"):
        branch = commit_mode.split(":", 1)[1]
        push_result = subprocess.run(
            ["git", "push", "origin", f"HEAD:{branch}"],
            cwd=str(root), env=git_env, capture_output=True, text=True)
        if push_result.returncode != 0:
            print(f"push failed: {push_result.stderr[:200]}")
            sys.exit(1)
        print(f"push to {branch}: {push_result.stdout.strip()}")


def main():
    ap = argparse.ArgumentParser(description="One command per window")
    ap.add_argument("--sport", default="nfl", choices=["nfl", "ncaaf"])
    ap.add_argument("--window", required=True,
                    choices=["open", "mid", "late", "prekick", "adhoc"])
    ap.add_argument("--reader-model", default="reader_v3",
                    help="the model that forms the opinions (default: reader_v3)")
    ap.add_argument("--as-of", default=None,
                    help="UTC ISO timestamp for reproducible runs")
    ap.add_argument("--no-pull", action="store_true",
                    help="skip API pulls (steps 2-4 only)")
    ap.add_argument("--week", type=int, default=None,
                    help="NFL week (default: auto-detected)")
    ap.add_argument("--ledger-dir", default=None,
                    help="override PICKS_LEDGER_DIR")
    ap.add_argument("--commit", default="none",
                    help="none | main | branch:<name> — commit + push after verify")
    ap.add_argument("--auto-prekick", action="store_true",
                    help="exit 0 if no game kicks in [now+2h52m, now+3h08m]")
    ap.add_argument("--injury-report", default=None,
                    help="path to injury report JSON (passed to reader_v3)")
    ap.add_argument("--window-hours", type=int, default=None,
                    help="override WINDOW_HOURS[window]")
    args = ap.parse_args()

    # ── NCAAF: --no-pull is required (the tape is the source; 0 credits by construction) ──
    if args.sport == "ncaaf" and not args.no_pull:
        raise SystemExit("HALT: ncaaf: the tape is the source; use --no-pull")

    # ── Auto-prekick gate ──
    if args.auto_prekick:
        commence_times = _newest_snapshot_commence_times(ROOT, args.sport)
        if not _check_prekick_slot(commence_times):
            print("no game in the prekick slot")
            sys.exit(0)

    if args.sport == "ncaaf":
        week = args.week or _ncaaf_week()
        window_hours = args.window_hours or NCAAF_WINDOW_HOURS[args.window]
    else:
        week = args.week or _current_week()
        window_hours = args.window_hours or WINDOW_HOURS[args.window]

    reader_file = NFL_PIPELINE / "reader_v3.py"
    env = dict(os.environ)
    # Respect incoming MLB_REPO_ROOT if set (e.g. test fixtures); else use script's ROOT
    env.setdefault("MLB_REPO_ROOT", str(ROOT))
    effective_root = Path(env["MLB_REPO_ROOT"])
    if args.ledger_dir:
        env["PICKS_LEDGER_DIR"] = args.ledger_dir

    print(f"run_window: sport={args.sport} window={args.window} week={week} "
          f"reader_model={args.reader_model} commit={args.commit}")
    if args.as_of:
        print(f"  as-of: {args.as_of}")
    if args.no_pull:
        print(f"  --no-pull: skipping API pulls")

    # ── Injury report (NFL only) ──
    injury_path = args.injury_report
    if args.sport == "nfl":
        if not injury_path:
            injury_path = _newest_injury_report(effective_root, 2026, week)
            if injury_path:
                print(f"  injury report: {injury_path}")
            else:
                print(f"  no injury report found for season=2026 week={week}")

    # ── Step 0: Git pull (see Mac sim freeze before reader runs) ──
    _run("git pull",
         ["git", "pull", "--rebase", "--autostash"],
         env=env)

    # ── Step 1: Pull (NFL only; ncaaf HALTs without --no-pull above) ──
    if not args.no_pull:
        _run("props pull (--archive)",
             [PY, str(NFL_PIPELINE / "pull_hardrock_props.py"),
              "--window-hours", str(window_hours), "--tag", args.window,
              "--archive",
              "--out-dir", str(ROOT / "data" / "odds_archive" / "nfl" / "props"
                               / "season=2026" / "manual")],
             env=env)
        _run("game-line snapshot",
             [PY, str(SHARED_PIPELINE / "multi_book_open_capture.py"),
              "--sports", "americanfootball_nfl"],
             env=env)

    # ── Step 2: Sheet → Reader → Freeze ──
    sport_upper = args.sport.upper()
    with tempfile.TemporaryDirectory() as tmp:
        sheet_path = Path(tmp) / "sheet.csv"
        filled_path = Path(tmp) / "filled.csv"

        sheet_cmd = [PY, str(NFL_PIPELINE / "log_ai_opinions.py"),
                     "sheet", "--sport", args.sport,
                     "--week", str(week),
                     "--out", str(sheet_path)]
        if args.as_of:
            sheet_cmd += ["--as-of", args.as_of, "--pilot"]
        if args.window in ("prekick", "adhoc"):
            sheet_cmd += ["--window-hours", str(window_hours)]
        _run("sheet", sheet_cmd, env=env)

        reader_cmd = [PY, str(reader_file),
                      str(sheet_path), str(filled_path),
                      "--sport", args.sport,
                      "--root", env.get("MLB_REPO_ROOT", str(ROOT))]
        if args.as_of:
            reader_cmd += ["--as-of", args.as_of]
        if injury_path and args.sport == "nfl":
            reader_cmd += ["--injury-report", str(injury_path)]
        _run("reader_v3", reader_cmd, env=env)

        freeze_cmd = [PY, str(NFL_PIPELINE / "log_ai_opinions.py"),
                      "freeze", "--sport", args.sport,
                      "--week", str(week),
                      "--filled", str(filled_path),
                      "--reader-model", args.reader_model,
                      "--window", args.window,
                      "--reader-file", str(reader_file)]
        if args.as_of:
            freeze_cmd += ["--as-of", args.as_of, "--pilot"]
        if args.window in ("prekick", "adhoc"):
            freeze_cmd += ["--window-hours", str(window_hours)]
        _run("freeze", freeze_cmd, env=env)

        # ── Unquoted sidecar: events in the tape but not quoted by the book ──
        if args.sport == "ncaaf":
            _write_unquoted_sidecar(sheet_path, week, effective_root, args.sport)

    # ── Step 3: Verify ──
    _run("verify",
         [PY, str(NFL_PIPELINE / "log_ai_opinions.py"),
          "verify", "--sport", args.sport, "--week", str(week)],
         env=env)

    # ── Step 4: Adapters → Top-20 ──
    _run("picks_adapters",
         [PY, str(SHARED_PIPELINE / "picks_adapters.py")],
         env=env)

    _run("build_top20",
         [PY, str(SHARED_PIPELINE / "build_top20.py"),
          "--sport", sport_upper, "--print-top", "20"],
         env=env)

    # ── Step 5: Commit + Push ──
    _commit_and_push(args.commit, args.window, ROOT, env, sport=args.sport)

    print(f"\n{'='*60}")
    print(f"run_window COMPLETE: sport={args.sport} window={args.window}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
