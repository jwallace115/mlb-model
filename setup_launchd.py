#!/usr/bin/env python3
"""
Mac launchd scheduler setup.

Creates and loads a plist that runs run_model.py at 7:00 AM daily.
Also creates a second job that auto-logs yesterday's results at 11:30 PM.

Usage:
  python setup_launchd.py install    # install and start both jobs
  python setup_launchd.py uninstall  # unload and remove both jobs
  python setup_launchd.py status     # check if jobs are loaded
"""

import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PYTHON_BIN   = sys.executable
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

JOBS = {
    "com.mlbmodel.daily": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.daily.plist",
        "label": "com.mlbmodel.daily",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "run_model.py")],
        "hour": 7,
        "minute": 0,
        "description": "MLB Totals Model — 7 AM daily run",
    },
    "com.mlbmodel.refresh": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.refresh.plist",
        "label": "com.mlbmodel.refresh",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "refresh.py")],
        "hour": 11,   # 11 AM — catches confirmed lineups
        "minute": 0,
        "description": "MLB Totals Model — 11 AM lineup refresh",
    },
    "com.mlbmodel.results": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.results.plist",
        "label": "com.mlbmodel.results",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "results_tracker.py")],
        "hour": 23,
        "minute": 30,
        "description": "MLB Totals Model — 11:30 PM auto-log results",
    },
}


def _write_plist(job: dict) -> None:
    """Write a launchd plist file for a scheduled job."""
    plist_path = job["plist"]
    log_out    = os.path.join(SCRIPT_DIR, "logs", f"{job['label']}.stdout.log")
    log_err    = os.path.join(SCRIPT_DIR, "logs", f"{job['label']}.stderr.log")

    program_args = "\n".join(
        f"        <string>{arg}</string>" for arg in job["program"]
    )

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{job['label']}</string>

    <key>ProgramArguments</key>
    <array>
{program_args}
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{job['hour']}</integer>
        <key>Minute</key>
        <integer>{job['minute']}</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>{SCRIPT_DIR}</string>

    <key>StandardOutPath</key>
    <string>{log_out}</string>

    <key>StandardErrorPath</key>
    <string>{log_err}</string>

    <key>RunAtLoad</key>
    <false/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')}</string>
    </dict>
</dict>
</plist>
"""
    plist_path.write_text(content)
    print(f"  Written: {plist_path}")


def _launchctl(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        ["launchctl"] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def install() -> None:
    print("Installing MLB Model launchd jobs...\n")
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    for name, job in JOBS.items():
        print(f"[{name}] {job['description']}")
        print(f"  Schedule: {job['hour']:02d}:{job['minute']:02d} daily")

        # Unload if already loaded (ignore errors)
        _launchctl(["unload", str(job["plist"])])

        _write_plist(job)

        code, out = _launchctl(["load", str(job["plist"])])
        if code == 0:
            print(f"  {chr(10004)} Loaded successfully")
        else:
            print(f"  {chr(10006)} Load failed: {out}")
        print()

    print("Installation complete.")
    print(f"\nLog files will be written to: {SCRIPT_DIR}/logs/")
    print("\nTo test immediately:")
    print(f"  launchctl start com.mlbmodel.daily")


def uninstall() -> None:
    print("Uninstalling MLB Model launchd jobs...\n")
    for name, job in JOBS.items():
        plist = job["plist"]
        code, out = _launchctl(["unload", str(plist)])
        if code == 0:
            print(f"  [OK] Unloaded {name}")
        else:
            print(f"  [--] {name}: {out}")
        if plist.exists():
            plist.unlink()
            print(f"       Removed {plist}")
    print("\nDone.")


def status() -> None:
    print("MLB Model launchd job status:\n")
    for name, job in JOBS.items():
        code, out = _launchctl(["list", name])
        loaded  = "LOADED" if code == 0 else "NOT LOADED"
        exists  = "✓" if job["plist"].exists() else "✗"
        color   = "\033[32m" if code == 0 else "\033[31m"
        reset   = "\033[0m"
        print(f"  {color}{loaded}{reset}  plist={exists}  {name}")
        print(f"          → {job['hour']:02d}:{job['minute']:02d} daily")
        print(f"          → {job['description']}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "install":
        install()
    elif cmd == "uninstall":
        uninstall()
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python setup_launchd.py [install|uninstall|status]")
        sys.exit(1)
