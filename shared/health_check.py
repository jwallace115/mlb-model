#!/usr/bin/env python3
"""
Daily Health Check — iamnotuncertain.net
=========================================
Checks cron freshness, signal file health, API status, and more.
Writes shared/health_status.json for dashboard display.
Never crashes — every check wrapped in try/except.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

STATUS_PATH = ROOT / "shared" / "health_status.json"
NOW = datetime.now(timezone.utc)
TODAY = date.today().isoformat()

warnings_list = []
errors_list = []


def hours_ago(ts):
    return (NOW - ts).total_seconds() / 3600


def file_mtime(path):
    if not os.path.exists(path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)


# ── A. CRON JOB FRESHNESS ────────────────────────────────────────────────────

def check_cron_jobs():
    jobs = [
        ("mlb_prelim", "/root/logs/mlb_prelim.log", 26),
        ("mlb_confirm", "/root/logs/mlb_confirm.log", 26),
        ("nhl_morning", "/root/logs/nhl_morning.log", 26),
        ("nhl_evening", "/root/logs/nhl_evening.log", 26),
        ("soccer", "/root/logs/soccer.log", 26),
        ("results", "/root/logs/results.log", 26),
        ("lines_open", "/root/logs/lines_open.log", 26),
        ("lines_closing", "/root/logs/lines_closing.log", 26),
        ("scratch_check", "/root/logs/scratch_check.log", 26),
    ]
    details = []
    status = "GREEN"
    for name, path, max_hours in jobs:
        try:
            mt = file_mtime(path)
            if mt is None:
                details.append({"job": name, "status": "MISSING", "last_run": None, "hours_since_run": None})
                warnings_list.append(f"Cron log missing: {name}")
                status = "YELLOW" if status != "RED" else "RED"
            else:
                hrs = hours_ago(mt)
                st = "OK" if hrs <= max_hours else "STALE"
                details.append({"job": name, "status": st, "last_run": mt.isoformat(), "hours_since_run": round(hrs, 1)})
                if st == "STALE":
                    warnings_list.append(f"Cron stale: {name} ({hrs:.0f}h ago)")
                    status = "YELLOW" if status != "RED" else "RED"
        except Exception as e:
            details.append({"job": name, "status": "ERROR", "error": str(e)})
    return {"status": status, "details": details}


# ── B. SIGNAL FILE FRESHNESS ─────────────────────────────────────────────────

def check_signal_files():
    files = [
        ("mlb_v1", "mlb_sim/logs/signals_2026.json", 48),
        ("mlb_f5", "mlb_sim/logs/f5_signals_2026.json", 48),
        ("nhl", "nhl/nhl_decisions.parquet", 48),
        ("golf_shadow", "golf/shadow/golf_shadow_log.parquet", 168),  # weekly
    ]
    details = []
    status = "GREEN"
    for name, path, max_hours in files:
        try:
            full = ROOT / path
            if not full.exists():
                details.append({"file": name, "status": "MISSING"})
                continue
            mt = file_mtime(str(full))
            hrs = hours_ago(mt) if mt else 999
            sz = full.stat().st_size
            # Record count
            n = None
            try:
                if path.endswith(".json"):
                    n = len(json.load(open(full)))
                elif path.endswith(".parquet"):
                    import pandas as pd
                    n = len(pd.read_parquet(full))
            except:
                pass
            st = "OK" if hrs <= max_hours else "STALE"
            details.append({"file": name, "status": st, "size_kb": round(sz/1024, 1),
                             "last_modified": mt.isoformat() if mt else None,
                             "hours_since_modified": round(hrs, 1), "record_count": n})
            if st == "STALE":
                warnings_list.append(f"Signal file stale: {name} ({hrs:.0f}h)")
                status = "YELLOW"
        except Exception as e:
            details.append({"file": name, "status": "ERROR", "error": str(e)})
    return {"status": status, "details": details}


# ── C. UNGRADED SIGNAL GAPS ──────────────────────────────────────────────────

def check_ungraded():
    gaps = []
    status = "GREEN"
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # MLB V1
    try:
        sigs = json.load(open(ROOT / "mlb_sim/logs/signals_2026.json"))
        ungraded = [s for s in sigs if not s.get("result") and (s.get("date", "") or "") < yesterday
                    and not s.get("shadow_only")]
        if ungraded:
            gaps.append({"sport": "mlb_v1", "count": len(ungraded),
                          "dates": list(set(s.get("date") for s in ungraded))})
    except:
        pass

    # MLB F5
    try:
        sigs = json.load(open(ROOT / "mlb_sim/logs/f5_signals_2026.json"))
        ungraded = [s for s in sigs if not s.get("result") and (s.get("date", "") or "") < yesterday]
        if ungraded:
            gaps.append({"sport": "mlb_f5", "count": len(ungraded),
                          "dates": list(set(s.get("date") for s in ungraded))})
    except:
        pass

    # NBA
    try:
        import pandas as pd
        nba = pd.read_parquet(ROOT / "nba/data/nba_signal_log.parquet")
        ungraded = nba[(nba["result"].isna()) & (nba["game_date"] < yesterday)]
        if len(ungraded) > 0:
            gaps.append({"sport": "nba", "count": len(ungraded),
                          "dates": ungraded["game_date"].unique().tolist()})
    except:
        pass

    if gaps:
        status = "YELLOW"
        for g in gaps:
            warnings_list.append(f"Ungraded signals: {g['sport']} ({g['count']} gaps)")

    return {"status": status, "gaps": gaps}


# ── D. ZERO SCORE CHECK ──────────────────────────────────────────────────────

def check_zero_scores():
    errs = []
    recent_cutoff = (date.today() - timedelta(days=14)).isoformat()
    try:
        for fname in ["mlb_sim/logs/signals_2026.json", "mlb_sim/logs/f5_signals_2026.json"]:
            sigs = json.load(open(ROOT / fname))
            for s in sigs:
                sig_date = s.get("date", "") or ""
                if sig_date < recent_cutoff:
                    continue  # ignore historical zero-score bugs
                at = s.get("actual_total") or s.get("actual_f5_total")
                if at == 0 or at == 0.0:
                    if s.get("result"):  # graded with zero = bug
                        errs.append({"file": fname, "game_id": s.get("game_id"),
                                      "date": sig_date, "actual": at})
    except:
        pass

    status = "RED" if errs else "GREEN"
    if errs:
        errors_list.append(f"Zero-score grading errors: {len(errs)}")
    return {"status": status, "errors": errs}


# ── E. ODDS API HEALTH ───────────────────────────────────────────────────────

def check_odds_api():
    try:
        # Load key
        env_path = ROOT / ".env"
        key = None
        if env_path.exists():
            for line in open(env_path):
                line = line.strip()
                if line.startswith("ODDS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("'\"")
        if not key:
            return {"status": "YELLOW", "error": "No ODDS_API_KEY"}

        import requests
        r = requests.get("https://api.the-odds-api.com/v4/sports",
                         params={"apiKey": key}, timeout=10)
        cred = r.headers.get("x-requests-remaining")
        if r.status_code == 200:
            return {"status": "GREEN", "credits_remaining": int(cred) if cred else None}
        else:
            errors_list.append(f"Odds API returned {r.status_code}")
            return {"status": "RED", "http_status": r.status_code}
    except Exception as e:
        errors_list.append(f"Odds API unreachable: {e}")
        return {"status": "RED", "error": str(e)}


# ── F. DASHBOARD FRESHNESS (git last push) ────────────────────────────────────

def check_dashboard():
    try:
        import subprocess
        result = subprocess.run(["git", "log", "-1", "--format=%ci"],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"status": "YELLOW", "error": "git log failed"}
        last_commit = result.stdout.strip()
        # Parse git date format: "2026-04-05 20:41:32 -0400"
        from datetime import datetime as _dt
        ts = _dt.strptime(last_commit[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        hrs = hours_ago(ts)
        if hrs > 26:
            warnings_list.append(f"No recent git push — dashboard may be stale ({hrs:.0f}h)")
            return {"status": "YELLOW", "last_push": last_commit, "hours_ago": round(hrs, 1)}
        return {"status": "GREEN", "last_push": last_commit, "hours_ago": round(hrs, 1)}
    except Exception as e:
        return {"status": "YELLOW", "error": str(e)}


# ── G. SIGNAL ACTIVITY ───────────────────────────────────────────────────────

def check_signal_activity():
    cutoff_7d = (date.today() - timedelta(days=7)).isoformat()
    activity = {}

    # MLB
    try:
        v1 = json.load(open(ROOT / "mlb_sim/logs/signals_2026.json"))
        live = [s for s in v1 if not s.get("shadow_only")]
        activity["mlb"] = {
            "last_7_days": sum(1 for s in live if (s.get("date", "") or "") >= cutoff_7d),
            "today": sum(1 for s in live if (s.get("date", "") or "") == TODAY),
        }
    except:
        activity["mlb"] = {"last_7_days": 0, "today": 0}

    # NBA
    try:
        import pandas as pd
        nba = pd.read_parquet(ROOT / "nba/data/nba_signal_log.parquet")
        activity["nba"] = {
            "last_7_days": int((nba["game_date"] >= cutoff_7d).sum()),
            "today": int((nba["game_date"] == TODAY).sum()),
        }
    except:
        activity["nba"] = {"last_7_days": 0, "today": 0}

    # NHL
    try:
        import pandas as pd
        nhl = pd.read_parquet(ROOT / "nhl/nhl_decisions.parquet")
        if "game_date" in nhl.columns:
            activity["nhl"] = {
                "last_7_days": int((nhl["game_date"] >= cutoff_7d).sum()),
                "today": int((nhl["game_date"] == TODAY).sum()),
            }
        else:
            activity["nhl"] = {"last_7_days": 0, "today": 0}
    except:
        activity["nhl"] = {"last_7_days": 0, "today": 0}

    # Golf
    try:
        import pandas as pd
        golf = pd.read_parquet(ROOT / "golf/shadow/golf_shadow_log.parquet")
        if "run_timestamp" in golf.columns:
            activity["golf"] = {"last_7_days": int(len(golf[golf["run_timestamp"] >= cutoff_7d])), "today": 0}
        else:
            activity["golf"] = {"last_7_days": len(golf), "today": 0}
    except:
        activity["golf"] = {"last_7_days": 0, "today": 0}

    return activity


# ── H. NBA MACBOOK SYNC ──────────────────────────────────────────────────────

def check_nba_sync():
    try:
        path = ROOT / "nba/data/nba_signal_log.parquet"
        mt = file_mtime(str(path))
        if mt is None:
            return {"status": "YELLOW", "last_sync": None}
        hrs = hours_ago(mt)
        st = "GREEN" if hrs <= 48 else "YELLOW"
        if st == "YELLOW":
            warnings_list.append(f"NBA MacBook sync stale ({hrs:.0f}h)")
        return {"status": st, "last_sync": mt.isoformat(), "hours_ago": round(hrs, 1)}
    except Exception as e:
        return {"status": "YELLOW", "error": str(e)}


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Health Check — {NOW.isoformat()}")
    print("=" * 50)

    checks = {}
    checks["cron_jobs"] = check_cron_jobs()
    print(f"  Cron jobs: {checks['cron_jobs']['status']}")

    checks["signal_files"] = check_signal_files()
    print(f"  Signal files: {checks['signal_files']['status']}")

    checks["ungraded_gaps"] = check_ungraded()
    print(f"  Ungraded gaps: {checks['ungraded_gaps']['status']}")

    checks["zero_scores"] = check_zero_scores()
    print(f"  Zero scores: {checks['zero_scores']['status']}")

    checks["odds_api"] = check_odds_api()
    print(f"  Odds API: {checks['odds_api']['status']}")

    checks["dashboard"] = check_dashboard()
    print(f"  Dashboard: {checks['dashboard']['status']}")

    checks["signal_activity"] = check_signal_activity()
    for sport, act in checks["signal_activity"].items():
        print(f"  {sport}: {act['last_7_days']} signals (7d), {act['today']} today")

    checks["nba_macbook_sync"] = check_nba_sync()
    print(f"  NBA sync: {checks['nba_macbook_sync']['status']}")

    # Overall status
    all_statuses = [v.get("status", "GREEN") for k, v in checks.items()
                    if isinstance(v, dict) and "status" in v]
    if "RED" in all_statuses:
        overall = "RED"
    elif "YELLOW" in all_statuses:
        overall = "YELLOW"
    else:
        overall = "GREEN"

    result = {
        "generated_at": NOW.isoformat(),
        "overall_status": overall,
        "checks": checks,
        "warnings": warnings_list,
        "errors": errors_list,
    }

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\n  Overall: {overall}")
    if warnings_list:
        print(f"  Warnings: {warnings_list}")
    if errors_list:
        print(f"  Errors: {errors_list}")
    print(f"  Saved: {STATUS_PATH}")


if __name__ == "__main__":
    main()
