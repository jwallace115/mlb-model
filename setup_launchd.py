#!/usr/bin/env python3
"""
Mac launchd scheduler setup.

Manages all scheduled model jobs:
  7:00 AM  — push_results.py  (MLB grade+model, NBA, NHL, Soccer initial run)
  7:00 AM  — nba/model_c_shadow.py --grade  (NBA props: grade yesterday)
  9:00 AM  — nba/model_c_shadow.py --collect (NBA props: collect + project)
  10:00 AM — soccer lineup refresh (catches 12:30pm+ kickoffs)
  11:00 AM — refresh.py       (MLB lineup/weather/umpire update)
  12:00 PM — soccer lineup refresh (catches afternoon kickoffs)
  5:00 PM  — nba/model_c_shadow.py --refresh (NBA props: pre-tip refresh)
  5:00 PM  — refresh_5pm.py  (MLB + NBA + NHL + Soccer late refresh)
  11:30 PM — results_tracker.py (auto-log MLB final scores)

Usage:
  python setup_launchd.py install    # install and load all jobs
  python setup_launchd.py uninstall  # unload and remove all jobs
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

_soccer_refresh_cmd = (
    f"{PYTHON_BIN} soccer/soccer_daily_pipeline.py --refresh-lineups"
    f" && {PYTHON_BIN} push_soccer.py"
)

JOBS = {
    "com.mlbmodel.daily": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.daily.plist",
        "label": "com.mlbmodel.daily",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "push_results.py")],
        "hour": 7,
        "minute": 0,
        "description": "7 AM — grade yesterday + MLB/NBA/NHL/Soccer model run",
    },
    "com.mlbmodel.soccer.10am": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.soccer.10am.plist",
        "label": "com.mlbmodel.soccer.10am",
        "program": ["/bin/sh", "-c", _soccer_refresh_cmd],
        "hour": 10,
        "minute": 0,
        "description": "10 AM — Soccer lineup refresh (catches 12:30pm+ kickoffs)",
    },
    "com.mlbmodel.refresh": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.refresh.plist",
        "label": "com.mlbmodel.refresh",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "refresh.py")],
        "hour": 11,
        "minute": 0,
        "description": "11 AM — MLB lineup/weather/umpire refresh",
    },
    "com.mlbmodel.soccer.noon": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.soccer.noon.plist",
        "label": "com.mlbmodel.soccer.noon",
        "program": ["/bin/sh", "-c", _soccer_refresh_cmd],
        "hour": 12,
        "minute": 0,
        "description": "12 PM — Soccer lineup refresh (catches afternoon kickoffs)",
    },
    "com.mlbmodel.results": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.results.plist",
        "label": "com.mlbmodel.results",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "results_tracker.py")],
        "hour": 23,
        "minute": 30,
        "description": "11:30 PM — auto-log MLB final scores",
    },
    "com.mlbmodel.nba.props.grade": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.nba.props.grade.plist",
        "label": "com.mlbmodel.nba.props.grade",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "nba", "model_c_shadow.py"), "--grade"],
        "hour": 7,
        "minute": 0,
        "description": "7 AM — NBA player props: grade yesterday's shadow plays",
    },
    "com.mlbmodel.nba.props.collect": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.nba.props.collect.plist",
        "label": "com.mlbmodel.nba.props.collect",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "nba", "model_c_shadow.py"), "--collect"],
        "hour": 9,
        "minute": 0,
        "description": "9 AM — NBA player props: collect lines + project + shadow card",
    },
    "com.mlbmodel.nba.props.refresh": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.nba.props.refresh.plist",
        "label": "com.mlbmodel.nba.props.refresh",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "nba", "model_c_shadow.py"), "--refresh"],
        "hour": 17,
        "minute": 0,
        "description": "5 PM — NBA player props: pre-tip line refresh",
    },
    "com.mlbmodel.mlb.hits.grade": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.mlb.hits.grade.plist",
        "label": "com.mlbmodel.mlb.hits.grade",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "mlb", "props_shadow.py"), "--grade"],
        "hour": 7,
        "minute": 5,
        "description": "7:05 AM — MLB HITS props: grade yesterday",
    },
    "com.mlbmodel.mlb.hits.collect": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.mlb.hits.collect.plist",
        "label": "com.mlbmodel.mlb.hits.collect",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "mlb", "props_shadow.py"), "--collect"],
        "hour": 9,
        "minute": 0,
        "description": "9 AM — MLB HITS props: collect + project + shadow card",
    },
    "com.mlbmodel.clv.capture": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.clv.capture.plist",
        "label": "com.mlbmodel.clv.capture",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "shared", "closing_line_runner.py")],
        "hour": 18,
        "minute": 30,
        "description": "6:30 PM — Capture closing lines for all sports (CLV tracking)",
    },
    "com.mlbmodel.mlb.hits.refresh": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.mlb.hits.refresh.plist",
        "label": "com.mlbmodel.mlb.hits.refresh",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "mlb", "props_shadow.py"), "--refresh"],
        "hour": 17,
        "minute": 5,
        "description": "5:05 PM — MLB HITS props: pre-game line refresh",
    },
    "com.mlbmodel.wnba.updater": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.wnba.updater.plist",
        "label": "com.mlbmodel.wnba.updater",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "wnba", "shadow", "season_updater.py")],
        "hour": 10,
        "minute": 0,
        "description": "10 AM — WNBA season updater (rolling features)",
    },
    "com.mlbmodel.wnba.daily": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.wnba.daily.plist",
        "label": "com.mlbmodel.wnba.daily",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "wnba", "shadow", "daily_runner.py")],
        "hour": 11,
        "minute": 0,
        "description": "11 AM — WNBA daily projections + shadow board",
    },
    "com.mlbmodel.wnba.clv": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.wnba.clv.plist",
        "label": "com.mlbmodel.wnba.clv",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "wnba", "shadow", "clv_runner.py")],
        "hour": 22,
        "minute": 30,
        "description": "10:30 PM — WNBA CLV capture (closing lines)",
    },
    "com.mlbmodel.wnba.grader": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.wnba.grader.plist",
        "label": "com.mlbmodel.wnba.grader",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "wnba", "shadow", "grader.py")],
        "hour": 8,
        "minute": 0,
        "description": "8 AM — WNBA results grader (grade yesterday)",
    },
    "com.mlbmodel.golf.open": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.golf.open.plist",
        "label": "com.mlbmodel.golf.open",
        "program": ["/bin/sh", "-c",
                     f"RUN_MODE=live {PYTHON_BIN} {os.path.join(SCRIPT_DIR, 'golf', 'shadow', 'golf_daily_runner.py')} --capture open --include-matchups"
                     f" && {PYTHON_BIN} {os.path.join(SCRIPT_DIR, 'push_golf.py')}"],
        "hour": 9,
        "minute": 0,
        "weekday": 2,
        "description": "Tue 9 AM — Golf opening odds + matchups capture",
    },
    "com.mlbmodel.golf.close": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.golf.close.plist",
        "label": "com.mlbmodel.golf.close",
        "program": ["/bin/sh", "-c",
                     f"RUN_MODE=live {PYTHON_BIN} {os.path.join(SCRIPT_DIR, 'golf', 'shadow', 'golf_daily_runner.py')} --capture close --include-matchups"
                     f" && {PYTHON_BIN} {os.path.join(SCRIPT_DIR, 'push_golf.py')}"],
        "hour": 8,
        "minute": 0,
        "weekday": 4,
        "description": "Thu 8 AM — Golf pre-R1 closing odds + candidates",
    },
    "com.mlbmodel.golf.grader": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.golf.grader.plist",
        "label": "com.mlbmodel.golf.grader",
        "program": ["/bin/sh", "-c",
                     f"RUN_MODE=live {PYTHON_BIN} {os.path.join(SCRIPT_DIR, 'golf', 'shadow', 'golf_grader.py')} --include-matchups"
                     f" && {PYTHON_BIN} {os.path.join(SCRIPT_DIR, 'push_golf.py')}"],
        "hour": 8,
        "minute": 0,
        "weekday": 1,
        "description": "Mon 8 AM — Golf grader (grade completed tournament)",
    },
    "com.mlbmodel.nba.refs": {
        "plist": LAUNCH_AGENTS_DIR / "com.mlbmodel.nba.refs.plist",
        "label": "com.mlbmodel.nba.refs",
        "program": [PYTHON_BIN, os.path.join(SCRIPT_DIR, "nba", "ref_scrape.py")],
        "hour": 18,
        "minute": 30,
        "description": "6:30 PM — NBA referee crew scrape (Board 5)",
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
    <dict>{"" if "weekday" not in job else f"""
        <key>Weekday</key>
        <integer>{job.get('weekday', 0)}</integer>"""}
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
    print("\nTo test a job immediately:")
    print(f"  launchctl start com.mlbmodel.daily")
    print(f"  launchctl start com.mlbmodel.soccer.10am")
    print(f"  launchctl start com.mlbmodel.soccer.noon")


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
