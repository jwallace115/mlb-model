#!/usr/bin/env python3
"""
Pipeline health check — every scheduled job, judged against its real cadence.

Reads (no network, no API credits):
  * the VM crontab (``crontab -l``, or --crontab-file) — the single source of schedules
  * shared/pipeline/feeds_registry.json — what each job writes, which log it uses, its season
  * the output files themselves (timestamp in the filename, else mtime)
  * each job's log tail (did the last run crash?)
  * git (is the newest output pushed, or ignored?)
Writes status/pipeline_health.json (atomically). Exit code 0 always unless the
script itself fails — a red feed is reported in the file and on the website,
not by a cron mail nobody reads.

Status per job:
  FIRING    newest output is at or after the last due slot
  LATE      the last due slot has no output yet, the one before did (one cadence missed)
  SILENT    two or more due slots with no output
  ERRORING  the log changed after the last due slot and its tail shows a traceback / HARD STOP
  QUIET     ran on time (log moved), wrote nothing new, and the registry says that is normal
  OFF       outside the job's season and nothing new
  NOT_PUSHED newest output is git-tracked but has sat uncommitted/unpushed > 65 min
  IGNORED   newest output is matched by .gitignore (never reaches GitHub) and not marked local_only
"""

import argparse
import glob as _glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = ROOT / "shared" / "pipeline" / "feeds_registry.json"
OUT = ROOT / "status" / "pipeline_health.json"
TS_RE = re.compile(r"(\d{8}T\d{4}(?:\d{2})?Z)")
ERR_RE = re.compile(r"Traceback \(most recent call last\)|HARD STOP|invalid choice:|DatabaseError|\bFATAL\b")
LOOKBACK = timedelta(days=8)

# ---------------------------------------------------------------- cron parsing
_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


def _field(f, lo, hi):
    out = set()
    for part in f.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/")
            step = int(s)
            if part == "*":
                a, b = lo, hi
            elif "-" in part:
                a, b = map(int, part.split("-"))
            else:
                a, b = int(part), hi
        elif part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = map(int, part.split("-"))
        else:
            a = b = int(part)
        out.update(range(a, b + 1, step))
    return out


def parse_cron(expr):
    f = expr.split()
    sets = [_field(x, lo, hi) for x, (lo, hi) in zip(f, _RANGES)]
    sets[4] = {0 if d == 7 else d for d in sets[4]}
    return sets, f[2] == "*", f[4] == "*"


def cron_matches(p, t):
    (mi, h, dom, mo, dow), dom_star, dow_star = p
    if t.minute not in mi or t.hour not in h or t.month not in mo:
        return False
    cdow = (t.weekday() + 1) % 7
    if dom_star and dow_star:
        return True
    if dom_star:
        return cdow in dow
    if dow_star:
        return t.day in dom
    return t.day in dom or cdow in dow


def due_times(exprs, start, end):
    ps = [parse_cron(e) for e in exprs]
    t = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    out = []
    while t <= end:
        if any(cron_matches(p, t) for p in ps):
            out.append(t)
        t += timedelta(minutes=1)
    return out


def read_crontab(path=None):
    if path:
        text = Path(path).read_text()
    else:
        text = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    jobs = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or re.match(r"^[A-Z_]+=", line):
            continue
        m = re.match(r"^(\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+(.*)$", line)
        if m:
            jobs.append({"expr": m.group(1), "cmd": m.group(2)})
    return jobs


# ---------------------------------------------------------------- file evidence
def file_ts(p: Path, mode: str):
    if mode == "filename":
        m = TS_RE.search(p.name)
        if m:
            s = m.group(1)
            fmt = "%Y%m%dT%H%M%SZ" if len(s) == 16 else "%Y%m%dT%H%MZ"
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)


def newest_output(root: Path, globs, mode):
    best = None
    for g in globs:
        paths = (Path(x) for x in _glob.glob(g)) if g.startswith("/") else root.glob(g)
        for p in paths:
            if not p.is_file():
                continue
            ts = file_ts(p, mode)
            if best is None or ts > best[0]:
                best = (ts, p)
    return best


def log_state(log_path, since):
    """(ran_after_since, crashed_in_tail, last_line)."""
    if not log_path:
        return None, None, None
    p = Path(log_path)
    if not p.exists():
        return False, False, "log missing"
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    with open(p, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - 6000))
        tail = fh.read().decode("utf-8", "replace").splitlines()[-40:]
    crashed = any(ERR_RE.search(l) for l in tail)
    last = next((l.strip() for l in reversed(tail) if l.strip()), "")
    return (since is None or mtime >= since), crashed, last[:200]


def log_from_cmd(cmd):
    m = re.search(r">>\s*(\S+\.log)", cmd)
    return m.group(1) if m else None


class Git:
    def __init__(self, root):
        self.root = root
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        self.ok = (root / ".git").exists()
        self.pending = set()
        if self.ok:
            r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                               cwd=root, capture_output=True, text=True, env=env)
            for line in r.stdout.splitlines():
                path = line[3:].strip().strip('"')
                self.pending.add(path)
        self.env = env

    def ignored(self, rel):
        if not self.ok:
            return False
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=self.root, env=self.env)
        return r.returncode == 0


# ---------------------------------------------------------------- judging
def judge(job, reg, now, root, git):
    exprs = job["exprs"]
    grace = timedelta(minutes=reg.get("grace_min", 20))
    dues = due_times(exprs, now - LOOKBACK, now - grace) if exprs else []
    if not exprs and reg.get("cadence_min"):
        step = timedelta(minutes=reg["cadence_min"])
        dues = [now - grace - step, now - grace]
    last_due = dues[-1] if dues else None
    prev_due = dues[-2] if len(dues) > 1 else None
    in_season = now.month in reg.get("active_months", list(range(1, 13)))

    newest = newest_output(root, reg.get("outputs", []), reg.get("ts", "filename")) if reg.get("outputs") else None
    log_path = reg.get("log") or job.get("log")
    ran, crashed, last_line = log_state(log_path, last_due)

    out_ts = newest[0] if newest else None
    tol = timedelta(minutes=5)
    if ran and crashed:
        status = "ERRORING"
    elif reg.get("outputs") and newest is None:
        status = "QUIET" if (ran and reg.get("quiet_ok")) else ("SILENT" if in_season else "OFF")
    elif last_due is None:
        status = "FIRING" if out_ts or ran else "SILENT"
    elif out_ts and out_ts >= last_due - tol - timedelta(minutes=reg.get("write_lag_min", 0)):
        status = "FIRING"
    elif not in_season:
        status = "OFF"
    elif ran and reg.get("quiet_ok"):
        status = "QUIET"
    elif not reg.get("outputs"):
        if ran:
            status = "FIRING"
        else:
            ran_prev, _, _ = log_state(log_path, prev_due) if prev_due else (False, None, None)
            status = "LATE" if ran_prev else "SILENT"
    elif out_ts and prev_due and out_ts >= prev_due - tol:
        status = "LATE"
    else:
        status = "SILENT"

    push = None
    if newest is not None:
        try:
            rel = str(newest[1].relative_to(root))
        except ValueError:
            rel = None
        if rel and not reg.get("local_only"):
            if git.ignored(rel):
                push = "IGNORED"
            elif rel in git.pending and (now - out_ts) > timedelta(minutes=65):
                push = "NOT_PUSHED"
            else:
                push = "OK"
        elif reg.get("local_only"):
            push = "LOCAL_ONLY"
    if status == "FIRING" and push in ("IGNORED", "NOT_PUSHED"):
        status = push

    return {
        "id": reg["id"],
        "label": reg.get("label", reg["id"]),
        "sport": reg.get("sport", ""),
        "host": reg.get("host", "VM"),
        "schedule": exprs or ([f"every {reg['cadence_min']} min"] if reg.get("cadence_min") else []),
        "last_due_utc": last_due.isoformat() if last_due else None,
        "newest_file": str(newest[1].relative_to(root)) if newest and str(newest[1]).startswith(str(root)) else (str(newest[1]) if newest else None),
        "newest_utc": out_ts.isoformat() if out_ts else None,
        "age_min": round((now - out_ts).total_seconds() / 60) if out_ts else None,
        "log": log_path,
        "log_last_line": last_line,
        "push": push,
        "status": status,
        "note": reg.get("note", ""),
    }


# ---------------------------------------------------------------- host facts
def vm_facts():
    facts = {}
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            mem[k] = int(v.split()[0]) // 1024
        facts["ram_total_mb"] = mem.get("MemTotal")
        facts["ram_available_mb"] = mem.get("MemAvailable")
        facts["swap_used_mb"] = mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)
    except Exception:
        pass
    du = shutil.disk_usage("/")
    facts["disk_used_gb"] = round(du.used / 1e9, 1)
    facts["disk_total_gb"] = round(du.total / 1e9, 1)
    return facts


def push_daemon_facts(log="/root/logs/push_daemon.log", now=None):
    p = Path(log)
    if not p.exists():
        return None
    last_ok, fails = None, 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=24)
    for line in p.read_text(errors="replace").splitlines()[-4000:]:
        m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) — (.*)$", line)
        if not m:
            continue
        t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        msg = m.group(2)
        if "PUSH SUCCESS" in msg or "no changes" in msg:
            last_ok = t
        elif ("FAILED" in msg or "REFUSED" in msg) and t >= cutoff:
            fails += 1
    return {"last_ok_utc": last_ok.isoformat() if last_ok else None, "failures_24h": fails}


def credit_facts(logs=("/root/logs/capture_football.log", "/root/logs/capture_mlb.log"), plan=5_000_000):
    best = None
    for log in logs:
        p = Path(log)
        if not p.exists():
            continue
        with open(p, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 20000))
            for line in fh.read().decode("utf-8", "replace").splitlines():
                m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*remaining: (\d+)", line)
                if m:
                    t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    if best is None or t > best[0]:
                        best = (t, int(m.group(2)), log)
    if not best:
        return None
    return {"remaining": best[1], "used": plan - best[1], "plan": plan,
            "as_of_utc": best[0].isoformat(), "source": best[2]}


# ---------------------------------------------------------------- main
def build(now, root, crontab_file=None, registry=REGISTRY, with_host=True):
    reg = json.loads(Path(registry).read_text())
    cron = read_crontab(crontab_file)
    git = Git(root)
    feeds, used_cmds, retired_feeds = [], set(), []
    # cron_matches of retired feeds — these should not be flagged as "unregistered"
    retired_cron_matches = set()
    for r in reg["feeds"]:
        # Retired feeds are not judged
        if r.get("retired"):
            if r.get("cron_match"):
                retired_cron_matches.add(r["cron_match"])
                # Mark matching cron cmds as used so they don't show as unregistered
                for j in cron:
                    if r["cron_match"] in j["cmd"]:
                        used_cmds.add(j["cmd"])
            # Record last output time for the retired table
            newest = newest_output(root, r.get("outputs", []), r.get("ts", "filename")) if r.get("outputs") else None
            retired_feeds.append({
                "id": r["id"], "label": r.get("label", r["id"]), "sport": r.get("sport", ""),
                "newest_utc": newest[0].isoformat() if newest else None,
            })
            continue
        if r.get("host", "VM") == "VM" and r.get("cron_match"):
            matched = [j for j in cron if r["cron_match"] in j["cmd"]]
            exprs = [j["expr"] for j in matched]
            used_cmds.update(j["cmd"] for j in matched)
            log = log_from_cmd(matched[0]["cmd"]) if matched else None
            if not matched:
                feeds.append({"id": r["id"], "label": r.get("label", r["id"]), "sport": r.get("sport", ""),
                              "host": "VM", "schedule": [], "status": "NO_JOB",
                              "note": "registry expects a cron line containing: " + r["cron_match"]})
                continue
            feeds.append(judge({"exprs": exprs, "log": log}, r, now, root, git))
        else:
            feeds.append(judge({"exprs": [], "log": None}, r, now, root, git))
    # every crontab line not covered by the registry is still checked from its log
    for j in cron:
        if j["cmd"] in used_cmds or "push_daemon.sh" in j["cmd"]:
            continue
        log = log_from_cmd(j["cmd"])
        if not log:
            continue
        rid = "cron:" + re.sub(r"[^a-z0-9]+", "_", os.path.basename(log).lower()).strip("_")
        if any(f["id"] == rid for f in feeds):
            continue
        same = [k["expr"] for k in cron if log_from_cmd(k["cmd"]) == log]
        feeds.append(judge({"exprs": same, "log": log},
                           {"id": rid, "label": "unregistered job → " + os.path.basename(log), "quiet_ok": True},
                           now, root, git))
    order = {"ERRORING": 0, "SILENT": 1, "NO_JOB": 1, "NOT_PUSHED": 2, "IGNORED": 2, "LATE": 3,
             "QUIET": 4, "FIRING": 5, "OFF": 6}
    feeds.sort(key=lambda f: (order.get(f["status"], 9), f.get("sport", ""), f["id"]))
    counts = {}
    for f in feeds:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    out = {"generated_utc": now.isoformat(), "counts": counts, "feeds": feeds, "retired": retired_feeds}
    if with_host:
        out["vm"] = vm_facts()
        out["push_daemon"] = push_daemon_facts(now=now)
        out["credits"] = credit_facts()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crontab-file")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--now", help="ISO time, for tests")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    res = build(now, Path(a.root), a.crontab_file, a.registry, with_host=a.now is None)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(res, indent=1))
    os.replace(tmp, out)
    bad = {k: v for k, v in res["counts"].items() if k in ("ERRORING", "SILENT", "NO_JOB", "NOT_PUSHED", "IGNORED", "LATE")}
    print(f"pipeline_health {res['generated_utc']}  {res['counts']}  problems={bad}")


if __name__ == "__main__":
    main()
