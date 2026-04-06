#!/usr/bin/env python3
"""LaunchAgent Watchdog — verify and reload critical MacBook LaunchAgents."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HOME = os.path.expanduser("~")
AGENTS_DIR = Path(HOME) / "Library" / "LaunchAgents"
LOG_PATH = Path(HOME) / "Library" / "Logs" / "watchdog.log"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_label(plist_path):
    """Extract Label from plist filename."""
    return plist_path.stem


def is_loaded(label):
    """Check if a LaunchAgent is loaded."""
    try:
        r = subprocess.run(["launchctl", "list", label],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def reload_agent(plist_path, label):
    """Unload then load a LaunchAgent."""
    try:
        subprocess.run(["launchctl", "unload", str(plist_path)],
                        capture_output=True, timeout=5)
        subprocess.run(["launchctl", "load", str(plist_path)],
                        capture_output=True, timeout=5)
        import time; time.sleep(2)
        return is_loaded(label)
    except Exception:
        return False


def main():
    log("Watchdog started")

    if not AGENTS_DIR.exists():
        log(f"ERROR: {AGENTS_DIR} not found")
        return

    # Find all mlbmodel plists
    plists = sorted(AGENTS_DIR.glob("com.mlbmodel.*.plist"))
    if not plists:
        log("WARNING: no com.mlbmodel.*.plist files found")
        return

    loaded = 0
    reloaded = 0
    failed = 0

    for plist in plists:
        label = get_label(plist)
        try:
            if is_loaded(label):
                loaded += 1
            else:
                log(f"NOT LOADED: {label} — reloading...")
                if reload_agent(plist, label):
                    log(f"RELOADED: {label}")
                    reloaded += 1
                else:
                    log(f"FAILED TO RELOAD: {label}")
                    failed += 1
        except Exception as e:
            log(f"ERROR checking {label}: {e}")
            failed += 1

    total = loaded + reloaded + failed
    log(f"Summary: {total} agents checked, {loaded} already loaded, "
        f"{reloaded} reloaded, {failed} failed")
    log("Watchdog complete")


if __name__ == "__main__":
    main()
