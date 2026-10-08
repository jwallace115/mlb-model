#!/usr/bin/env python3
"""One command per window: pull → sheet → reader → freeze → verify → adapt → top-20.

Usage:
  python3 nfl/pipeline/run_window.py --sport nfl --window adhoc --reader-model claude-opus-5-5
  python3 nfl/pipeline/run_window.py --sport nfl --window prekick --reader-model claude-opus-5-5 --no-pull
  python3 nfl/pipeline/run_window.py --sport nfl --window mid --reader-model claude-opus-5-5 --as-of 2026-10-08T20:00:00Z

Steps (each prints date -u, the command, its exit; non-zero STOPs):
  1. pull: props + game-line snapshot (--no-pull skips)
  2. sheet → reader_v3 → freeze --window <w> --reader-model <m> --reader-file reader_v3.py
  3. verify
  4. picks_adapters.py → build_top20.py --sport NFL --print-top 20

P26: one command per window, zero API credits on --no-pull.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
NFL_PIPELINE = ROOT / "nfl" / "pipeline"
SHARED_PIPELINE = ROOT / "shared" / "pipeline"

WINDOW_HOURS = {
    "open": 168,     # full week
    "mid": 168,      # full week
    "late": 24,      # day before
    "prekick": 6,    # within 6h
    "adhoc": 48,     # wide net
}


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
    # NFL 2026 week 1 starts ~Sep 10
    from datetime import date
    season_start = date(2026, 9, 10)
    delta = (now.date() - season_start).days
    return max(1, delta // 7 + 1)


def main():
    ap = argparse.ArgumentParser(description="One command per window")
    ap.add_argument("--sport", default="nfl", choices=["nfl"])
    ap.add_argument("--window", required=True,
                    choices=["open", "mid", "late", "prekick", "adhoc"])
    ap.add_argument("--reader-model", required=True,
                    help="the model that forms the opinions")
    ap.add_argument("--as-of", default=None,
                    help="UTC ISO timestamp for reproducible runs")
    ap.add_argument("--no-pull", action="store_true",
                    help="skip API pulls (steps 2-4 only)")
    ap.add_argument("--week", type=int, default=None,
                    help="NFL week (default: auto-detected)")
    ap.add_argument("--ledger-dir", default=None,
                    help="override PICKS_LEDGER_DIR")
    args = ap.parse_args()

    week = args.week or _current_week()
    window_hours = WINDOW_HOURS[args.window]
    reader_file = NFL_PIPELINE / "reader_v3.py"
    env = dict(os.environ)
    env["MLB_REPO_ROOT"] = str(ROOT)
    if args.ledger_dir:
        env["PICKS_LEDGER_DIR"] = args.ledger_dir

    print(f"run_window: sport={args.sport} window={args.window} week={week} "
          f"reader_model={args.reader_model}")
    if args.as_of:
        print(f"  as-of: {args.as_of}")
    if args.no_pull:
        print(f"  --no-pull: skipping API pulls")

    # ── Step 1: Pull ──
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
    with tempfile.TemporaryDirectory() as tmp:
        sheet_path = Path(tmp) / "sheet.csv"
        filled_path = Path(tmp) / "filled.csv"

        sheet_cmd = [PY, str(NFL_PIPELINE / "log_ai_opinions.py"),
                     "sheet", "--week", str(week),
                     "--out", str(sheet_path)]
        if args.as_of:
            sheet_cmd += ["--as-of", args.as_of, "--pilot"]
        if args.window in ("prekick", "adhoc"):
            sheet_cmd += ["--window-hours", str(window_hours)]
        _run("sheet", sheet_cmd, env=env)

        reader_cmd = [PY, str(reader_file),
                      str(sheet_path), str(filled_path)]
        if args.as_of:
            reader_cmd += ["--as-of", args.as_of]
        _run("reader_v3", reader_cmd, env=env)

        freeze_cmd = [PY, str(NFL_PIPELINE / "log_ai_opinions.py"),
                      "freeze", "--week", str(week),
                      "--filled", str(filled_path),
                      "--reader-model", args.reader_model,
                      "--window", args.window,
                      "--reader-file", str(reader_file)]
        if args.as_of:
            freeze_cmd += ["--as-of", args.as_of, "--pilot"]
        if args.window in ("prekick", "adhoc"):
            freeze_cmd += ["--window-hours", str(window_hours)]
        _run("freeze", freeze_cmd, env=env)

    # ── Step 3: Verify ──
    _run("verify",
         [PY, str(NFL_PIPELINE / "log_ai_opinions.py"),
          "verify", "--week", str(week)],
         env=env)

    # ── Step 4: Adapters → Top-20 ──
    _run("picks_adapters",
         [PY, str(SHARED_PIPELINE / "picks_adapters.py")],
         env=env)

    _run("build_top20",
         [PY, str(SHARED_PIPELINE / "build_top20.py"),
          "--sport", "NFL", "--print-top", "20"],
         env=env)

    print(f"\n{'='*60}")
    print(f"run_window COMPLETE: window={args.window}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
