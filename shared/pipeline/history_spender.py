#!/usr/bin/env python3
"""
History spender — turns the month's unused Odds API credits into historical archive, every night.

Works down shared/pipeline/history_jobs.json in order. Each request is identified by a key; a key
that has a file on disk or a line in the ledger is never bought twice (resume-safe across nights).

Budget (re-read from the API every night, so it can never eat the scheduled pulls):
    reserve = --reserve-floor + --reserve-per-day x days left in the month (today included)
    spend   = remaining - reserve           (stop the moment remaining <= reserve)
Also stops at --until (UTC clock) and when free disk drops under --min-free-gb.

Writes (append-only, VM-local, gitignored — too big for git):
    data/odds_archive/<folder>/history/<job>/season=<S>/<key>.parquet
    data/odds_archive/<folder>/history/events/<sport>_<S>.parquet       (schedule used for event jobs)
    data/odds_archive/_history_ledger.jsonl                              (one line per paid request)
    status/history_spender.json                                          (progress, for the website)
HALT rules: a non-200 writes nothing for that request; HTTP 401 stops the run; HTTP 422 (market not
offered for this sport) marks the job unsupported and moves on; 429/5xx back off and retry.

Cost model (historical): 10 x markets x region-equivalents; 10 books = 1 region-equivalent.
    grid / inplay call = 30 credits; event call = 10 x len(markets); events list = 1.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
JOBS = ROOT / "shared" / "pipeline" / "history_jobs.json"
ARCHIVE = ROOT / "data" / "odds_archive"
LEDGER = ARCHIVE / "_history_ledger.jsonl"
STATUS = ROOT / "status" / "history_spender.json"
BASE = "https://api.the-odds-api.com/v4"


def utc(s):
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def z(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def zk(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


# ------------------------------------------------------------------ HTTP layer (swappable in tests)
class Api:
    def __init__(self, key, session=None):
        import requests
        self.key = key
        self.s = session or requests.Session()
        self.fp = hashlib.sha256(key.strip().encode()).hexdigest()[:8] if key else "UNSET"

    def get(self, path, params):
        """-> (status, json_or_None, remaining:int|None, last:int|None)"""
        p = dict(params, apiKey=self.key)
        for attempt in range(6):
            try:
                r = self.s.get(f"{BASE}{path}", params=p, timeout=40)
            except Exception:
                time.sleep(min(60, 2 ** (attempt + 1)))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(min(60, 2 ** (attempt + 1)))
                continue
            rem = r.headers.get("x-requests-remaining")
            last = r.headers.get("x-requests-last")
            body = None
            if r.status_code == 200:
                try:
                    body = r.json()
                except ValueError:
                    body = None
            return r.status_code, body, (int(float(rem)) if rem else None), (int(float(last)) if last else None)
        return 599, None, None, None


# ------------------------------------------------------------------ flatten
COLS = ["snapshot_utc", "requested_utc", "event_id", "commence_time", "home_team", "away_team",
        "bookmaker", "book_last_update", "market", "outcome_name", "description", "point", "price"]


def flatten(events, snapshot, requested):
    rows = []
    for ev in events:
        for bm in ev.get("bookmakers", []) or []:
            for mk in bm.get("markets", []) or []:
                for o in mk.get("outcomes", []) or []:
                    rows.append({
                        "snapshot_utc": snapshot, "requested_utc": requested, "event_id": ev.get("id"),
                        "commence_time": ev.get("commence_time"), "home_team": ev.get("home_team"),
                        "away_team": ev.get("away_team"), "bookmaker": bm.get("key"),
                        "book_last_update": mk.get("last_update") or bm.get("last_update"),
                        "market": mk.get("key"), "outcome_name": o.get("name"),
                        "description": o.get("description"), "point": o.get("point"), "price": o.get("price"),
                    })
    return rows


def write_parquet(rows, path):
    import pandas as pd
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    pd.DataFrame(rows, columns=COLS).to_parquet(tmp, index=False)
    os.replace(tmp, path)


# ------------------------------------------------------------------ the run
class Run:
    def __init__(self, api, cfg, args, now):
        self.api, self.cfg, self.a, self.now = api, cfg, args, now
        self.lock = threading.Lock()
        self.remaining = None
        self.spent = 0
        self.calls = 0
        self.stop_reason = None
        self.reserve = None
        self.done_keys = set()
        self.books = ",".join(cfg["books"])
        self.progress = {}
        if LEDGER.exists():
            for line in LEDGER.read_text().splitlines():
                try:
                    self.done_keys.add(json.loads(line)["key"])
                except Exception:
                    pass

    # -- budget
    def days_left(self):
        return monthrange(self.now.year, self.now.month)[1] - self.now.day + 1

    def check_stop(self):
        if self.stop_reason:
            return True
        if self.remaining is not None and self.remaining <= self.reserve:
            self.stop_reason = f"reserve reached (remaining {self.remaining} <= reserve {self.reserve})"
        elif self.a.max_credits and self.spent >= self.a.max_credits:
            self.stop_reason = f"--max-credits {self.a.max_credits} reached"
        elif datetime.now(timezone.utc).strftime("%H:%M") >= self.a.until and not self.a.ignore_clock:
            self.stop_reason = f"clock {self.a.until} UTC reached"
        elif shutil.disk_usage(str(ROOT)).free / 1e9 < self.a.min_free_gb:
            self.stop_reason = f"free disk under {self.a.min_free_gb} GB"
        return bool(self.stop_reason)

    def record(self, key, job, status, rows, last, rem, path):
        with self.lock:
            if rem is not None:
                self.remaining = rem
            self.spent += last or 0
            self.calls += 1
            self.done_keys.add(key)
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with open(LEDGER, "a") as fh:
                fh.write(json.dumps({"key": key, "job": job, "status": status, "rows": rows, "credits": last,
                                     "remaining": rem, "file": str(path.relative_to(ROOT)) if path else None,
                                     "utc": z(datetime.now(timezone.utc))}) + "\n")

    # -- one paid request
    def fetch(self, job, key, path_api, params, out_path, snapshot_requested):
        if self.check_stop() or key in self.done_keys or out_path.exists():
            return "skip"
        status, body, rem, last = self.api.get(path_api, params)
        if status == 401:
            self.stop_reason = "HTTP 401 — key rejected; nothing written"
            return "halt"
        if status == 422:
            return "unsupported"
        if status != 200 or body is None:
            with self.lock:
                if rem is not None:
                    self.remaining = rem
            return f"http {status}"
        data = body.get("data")
        events = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        rows = flatten(events, body.get("timestamp"), snapshot_requested)
        if rows:
            write_parquet(rows, out_path)
        self.record(key, job["id"], "ok" if rows else "empty", len(rows), last, rem, out_path if rows else None)
        return "ok" if rows else "empty"

    # -- schedules
    def season_days(self, sport, season):
        a, b = self.cfg["seasons"][sport][season]
        d, end = date.fromisoformat(a), min(date.fromisoformat(b), self.now.date() - timedelta(days=1))
        while d <= end:
            yield d
            d += timedelta(days=1)

    def events_for(self, sport, season):
        """Season schedule from the historical events endpoint (1 credit per day), cached on disk."""
        import pandas as pd
        folder = self.cfg["folders"][sport]
        path = ARCHIVE / folder / "history" / "events" / f"{sport}_{season}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        seen = {}
        for d in self.season_days(sport, season):
            if self.check_stop():
                return None  # incomplete schedule is never saved
            ts = datetime(d.year, d.month, d.day, 8, 0, tzinfo=timezone.utc)
            status, body, rem, last = self.api.get(f"/historical/sports/{sport}/events", {"date": z(ts)})
            if status == 401:
                self.stop_reason = "HTTP 401 — key rejected"
                return None
            if status != 200 or body is None:
                self.stop_reason = f"events list HTTP {status} on {d} — schedule not saved"
                return None
            with self.lock:
                self.remaining = rem if rem is not None else self.remaining
                self.spent += last or 0
                self.calls += 1
            for ev in body.get("data") or []:
                ct = utc(ev["commence_time"])
                if ct.date() <= date.fromisoformat(self.cfg["seasons"][sport][season][1]):
                    seen[ev["id"]] = {"event_id": ev["id"], "commence_time": ev["commence_time"],
                                      "home_team": ev.get("home_team"), "away_team": ev.get("away_team")}
        df = pd.DataFrame(list(seen.values()), columns=["event_id", "commence_time", "home_team", "away_team"])
        if df.empty:
            self.stop_reason = f"events list for {sport} {season} came back empty — not saved"
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return df

    def tasks(self, job):
        sport, folder = job["sport"], self.cfg["folders"][job["sport"]]
        root = ARCHIVE / folder / "history" / job["id"]
        for season in job["seasons"]:
            if job["kind"] == "grid":
                step = timedelta(minutes=job["step_min"])
                for d in self.season_days(sport, season):
                    t = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                    while t.date() == d:
                        if t.hour not in job.get("skip_utc_hours", []) or t.minute != 0:
                            key = f"{job['id']}|{zk(t)}"
                            yield (key, f"/historical/sports/{sport}/odds",
                                   {"bookmakers": self.books, "markets": "h2h,spreads,totals", "oddsFormat": "american", "date": z(t)},
                                   root / f"season={season}" / f"snap_{zk(t)}.parquet", z(t))
                        t += step
                continue
            ev = self.events_for(sport, season)
            if ev is None:
                return
            if job["kind"] == "event":
                mk = ",".join(job["markets"])
                for r in ev.sort_values("commence_time").itertuples():
                    ct = utc(r.commence_time)
                    for h in job["offsets_h"]:
                        t = ct - timedelta(hours=h)
                        key = f"{job['id']}|{r.event_id}|T-{h}h"
                        yield (key, f"/historical/sports/{sport}/events/{r.event_id}/odds",
                               {"bookmakers": self.books, "markets": mk, "oddsFormat": "american", "date": z(t)},
                               root / f"season={season}" / f"{r.event_id}_T-{h}h.parquet", z(t))
            elif job["kind"] == "inplay":
                ev = ev.assign(ct=ev.commence_time.map(utc))
                ev["day"] = ev.ct.map(lambda x: (x - timedelta(hours=10)).date())  # US evening slate = one day
                step = timedelta(minutes=job["step_min"])
                for day, g in sorted(ev.groupby("day"), key=lambda kv: kv[0]):
                    t = min(g.ct).replace(second=0, microsecond=0)
                    t -= timedelta(minutes=t.minute % job["step_min"])
                    end = max(g.ct) + timedelta(hours=job["window_h"])
                    while t <= end:
                        key = f"{job['id']}|{zk(t)}"
                        yield (key, f"/historical/sports/{sport}/odds",
                               {"bookmakers": self.books, "markets": "h2h,spreads,totals", "oddsFormat": "american", "date": z(t)},
                               root / f"season={season}" / f"snap_{zk(t)}.parquet", z(t))
                        t += step

    def run_job(self, job):
        counts = {"ok": 0, "empty": 0, "skip": 0, "unsupported": 0, "other": 0}
        it = self.tasks(job)
        with ThreadPoolExecutor(max_workers=self.a.workers) as pool:
            while not self.check_stop():
                batch = []
                for _ in range(self.a.workers * 8):
                    try:
                        batch.append(next(it))
                    except StopIteration:
                        break
                if not batch:
                    break
                for res in pool.map(lambda t: self.fetch(job, *t), batch):
                    counts[res if res in counts else "other"] += 1
                if counts["unsupported"]:
                    break
        self.progress[job["id"]] = counts
        return counts

    def main(self):
        st, body, rem, last = self.api.get("/sports", {})
        if st != 200 or rem is None:
            print(f"HALT: /sports returned {st}; key fingerprint {self.api.fp}")
            return 1
        self.remaining = rem
        self.reserve = self.a.reserve_floor + self.a.reserve_per_day * self.days_left()
        start_rem = rem
        print(f"key {self.api.fp} | remaining {rem:,} | reserve {self.reserve:,} | spendable {max(0, rem - self.reserve):,}")
        for job in self.cfg["jobs"]:
            if self.check_stop():
                break
            if self.a.only and job["id"] not in self.a.only:
                continue
            c = self.run_job(job)
            print(f"{job['id']}: {c} | spent so far {self.spent:,} | remaining {self.remaining:,}")
        out = {"run_utc": z(self.now), "finished_utc": z(datetime.now(timezone.utc)), "key_fp": self.api.fp,
               "remaining_start": start_rem, "remaining_end": self.remaining, "reserve": self.reserve,
               "spent": self.spent, "calls": self.calls, "stop_reason": self.stop_reason or "queue finished",
               "jobs": self.progress}
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        hist = []
        if STATUS.exists():
            try:
                hist = json.loads(STATUS.read_text()).get("runs", [])[-60:]
            except Exception:
                hist = []
        tmp = STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps({"latest": out, "runs": hist + [out]}, indent=1))
        os.replace(tmp, STATUS)
        print(f"done: {self.stop_reason or 'queue finished'} | spent {self.spent:,} in {self.calls:,} calls")
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reserve-floor", type=int, default=50_000)
    ap.add_argument("--reserve-per-day", type=int, default=8_000)
    ap.add_argument("--max-credits", type=int, default=0, help="extra cap for this run (0 = none)")
    ap.add_argument("--until", default="13:00", help="stop at this UTC clock time (HH:MM)")
    ap.add_argument("--ignore-clock", action="store_true")
    ap.add_argument("--min-free-gb", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", nargs="*", help="job ids")
    a = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
    key = os.getenv("ODDS_API_KEY", "")
    if not key:
        print("HALT: ODDS_API_KEY not set")
        return 1
    cfg = json.loads(JOBS.read_text())
    return Run(Api(key), cfg, a, datetime.now(timezone.utc)).main()


if __name__ == "__main__":
    sys.exit(main())
