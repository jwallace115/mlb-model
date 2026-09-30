#!/usr/bin/env python3
"""
NBA historical odds pull — work order NBA-D1.

Output root: ~/mlb-model/data/odds_archive/nba/history/
Code lives in worktree under nba/pipeline/.

Subcommands:
  probe     A10 Hard Rock discovery (before bulk calls)
  schedule  Item 0: date lists
  lines     Item 1: hourly + close snapshots
  props     Item 2: player props at T-24h, T-1h
  markets   Item 4: derivative markets at T-24h, T-1h
  inplay    Item 3: 5-min in-play snapshots
  null      A7 null control vs March-2026 backfill

Cost model (historical): 10 x markets x regions per call.
  bookmakers <= 10 = 1 region-equivalent.
  lines:  10 x 3 = 30 per snapshot.
  props:  10 x 8 = 80 per event-snapshot.
  deriv:  10 x 8 = 80 per event-snapshot.
"""

import argparse, gzip, hashlib, json, os, re, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta, date as Date
from pathlib import Path
from collections import defaultdict

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv

# Always load from main checkout (worktree won't have .env)
load_dotenv(Path.home() / "mlb-model" / ".env", override=True)

KEY = os.getenv("ODDS_API_KEY", "")
KEY_FP = hashlib.sha256(KEY.strip().encode()).hexdigest()[:8] if KEY else "UNSET"
BASE = "https://api.the-odds-api.com/v4"
SPORT = "basketball_nba"

# Output root in MAIN checkout (A1)
DATA_ROOT = Path.home() / "mlb-model" / "data" / "odds_archive" / "nba" / "history"
SCHED_DIR = Path(__file__).resolve().parent / "schedule"

# Default 9 books (no Hard Rock until probe confirms key)
DEFAULT_BOOKS = ["pinnacle", "draftkings", "fanduel", "betmgm",
                 "williamhill_us", "betrivers", "bovada", "betonlineag", "lowvig"]

SPEND_CAP = 2_400_000
GLOBAL_FLOOR = 5_000
MAX_WORKERS = 4

LINE_MKTS = "h2h,spreads,totals"
LINE_COST = 30

PROP_MKTS = ("player_points,player_rebounds,player_assists,player_threes,"
             "player_points_rebounds_assists,player_double_double,"
             "player_blocks,player_steals")
PROP_N = 8
PROP_COST = 80

DERIV_MKTS = ("h2h_h1,spreads_h1,totals_h1,h2h_q1,spreads_q1,totals_q1,"
              "team_totals,alternate_spreads")
DERIV_N = 8
DERIV_COST = 80

SEASONS = {
    2022: (Date(2022, 10, 18), Date(2023, 4, 9)),
    2023: (Date(2023, 10, 24), Date(2024, 4, 14)),
    2024: (Date(2024, 10, 22), Date(2025, 4, 13)),
    2025: (Date(2025, 10, 20), Date(2026, 4, 12)),
}

LINES_ORDER = [2024, 2025, 2023, 2022]
EVENT_ORDER = [2024, 2025, 2023]

EMPTY_COLS = ["snapshot_utc", "requested_utc", "event_id", "commence_time",
              "home_team", "away_team", "bookmaker", "market", "outcome_name",
              "description", "point", "price", "book_last_update"]


# ─── helpers ───────────────────────────────────────────────────────────

def _scrub(t):
    t = str(t)
    if KEY:
        t = t.replace(KEY, "<KEY>")
    return re.sub(r"(apiKey=)[^&\s'\"]+", r"\1<KEY>", t)

def _to_z(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def _parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))

def _date_range(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_books():
    probe = DATA_ROOT / "probe_results.json"
    if probe.exists():
        with open(probe) as f:
            return json.load(f).get("books", DEFAULT_BOOKS)
    return DEFAULT_BOOKS


def load_events(season):
    p = DATA_ROOT / "events" / f"events_{season}.parquet"
    if not p.exists():
        print(f"HALT: {p} not found — run 'lines' for season {season} first")
        sys.exit(1)
    return pd.read_parquet(p)


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.credits_used = 0
        self.remaining = None
        self.calls = 0
        self.stop = False
        self.t0 = time.time()
        self.cost_violations = []
        self.empty_charged = 0
        self.empty_free = 0
        self.books_by_season = defaultdict(set)

    def update(self, used, rem):
        with self.lock:
            self.credits_used += used
            self.remaining = rem
            self.calls += 1
            if self.credits_used >= SPEND_CAP:
                self.stop = True
                print(f"\nSPEND CAP: {self.credits_used} >= {SPEND_CAP}")
            if rem < GLOBAL_FLOOR:
                self.stop = True
                print(f"\nFLOOR: remaining={rem} < {GLOBAL_FLOOR}")

    def should_stop(self):
        with self.lock:
            return self.stop

    def rate(self):
        with self.lock:
            elapsed = time.time() - self.t0
            return self.calls / elapsed if elapsed > 0 else 0

    def summary(self):
        with self.lock:
            return (f"calls={self.calls} credits={self.credits_used} "
                    f"rem={self.remaining}")

    def report_rate_and_eta(self, total_tasks, label):
        with self.lock:
            elapsed = time.time() - self.t0
            if self.calls > 0 and elapsed > 0:
                r = self.calls / elapsed
                remain_tasks = total_tasks - self.calls
                eta_s = remain_tasks / r if r > 0 else 0
                eta = datetime.now(timezone.utc) + timedelta(seconds=eta_s)
                print(f"  {label}: {r:.2f} calls/s, ETA {eta.strftime('%Y-%m-%dT%H:%M:%SZ')}")


def api_get(url, params, state=None, retries=5):
    for attempt in range(retries):
        if state and state.should_stop():
            return None, {}
        try:
            r = requests.get(url, params=params, timeout=60)
        except requests.RequestException as e:
            w = min(2 * (2 ** attempt), 60)
            time.sleep(w)
            continue
        used = int(r.headers.get("x-requests-last", "0"))
        rem = int(r.headers.get("x-requests-remaining", "0"))
        if r.status_code in (429, 500, 502, 503, 504):
            w = min(2 * (2 ** attempt), 60)
            print(f"  HTTP {r.status_code}, backoff {w}s (rem={rem})")
            time.sleep(w)
            continue
        if state:
            state.update(used, rem)
        return r, {"used": used, "remaining": rem}
    return None, {}


def flatten_snap(data, req_utc, keep_inplay=False):
    """Sport-level response -> (rows, snapshot_utc, events_found)."""
    rows = []
    snap = data.get("timestamp", data.get("previous_timestamp", req_utc))
    games = data.get("data", [])
    if not isinstance(games, list):
        return rows, snap, []
    evts = []
    seen_eids = set()
    for g in games:
        ct = g.get("commence_time", "")
        if not keep_inplay:
            try:
                if _parse_utc(snap) >= _parse_utc(ct):
                    continue
            except (ValueError, TypeError):
                pass
        eid = g.get("id", "")
        home = g.get("home_team", "")
        away = g.get("away_team", "")
        if eid not in seen_eids:
            evts.append({"event_id": eid, "commence_time": ct,
                         "home_team": home, "away_team": away})
            seen_eids.add(eid)
        for bm in g.get("bookmakers", []):
            bk = bm.get("key", "")
            bm_upd = bm.get("last_update", "")
            for mkt in bm.get("markets", []):
                mk = mkt.get("key", "")
                mkt_upd = mkt.get("last_update", bm_upd)
                for oc in mkt.get("outcomes", []):
                    rows.append({
                        "snapshot_utc": snap, "requested_utc": req_utc,
                        "event_id": eid, "commence_time": ct,
                        "home_team": home, "away_team": away,
                        "bookmaker": bk, "market": mk,
                        "outcome_name": oc.get("name", ""),
                        "description": oc.get("description", ""),
                        "point": oc.get("point"), "price": oc.get("price"),
                        "book_last_update": mkt_upd,
                    })
    return rows, snap, evts


def flatten_ev(data, req_utc):
    """Event-level response -> rows."""
    rows = []
    if not data:
        return rows
    snap = data.get("timestamp", data.get("previous_timestamp", req_utc))
    ev = data.get("data", data)
    if not isinstance(ev, dict):
        return rows
    eid = ev.get("id", "")
    ct = ev.get("commence_time", "")
    home, away = ev.get("home_team", ""), ev.get("away_team", "")
    for bm in ev.get("bookmakers", []):
        bk = bm.get("key", "")
        bm_upd = bm.get("last_update", "")
        for mkt in bm.get("markets", []):
            mk = mkt.get("key", "")
            mkt_upd = mkt.get("last_update", bm_upd)
            for oc in mkt.get("outcomes", []):
                rows.append({
                    "snapshot_utc": snap, "requested_utc": req_utc,
                    "event_id": eid, "commence_time": ct,
                    "home_team": home, "away_team": away,
                    "bookmaker": bk, "market": mk,
                    "outcome_name": oc.get("name", ""),
                    "description": oc.get("description", ""),
                    "point": oc.get("point"), "price": oc.get("price"),
                    "book_last_update": mkt_upd,
                })
    return rows


def save_snap(rows, raw, pq_path, gz_path):
    pq_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        pd.DataFrame(rows).to_parquet(pq_path, index=False)
    else:
        pd.DataFrame(columns=EMPTY_COLS).to_parquet(pq_path, index=False)
    with gzip.open(gz_path, "wt") as f:
        json.dump(raw, f)


# ─── PROBE (A10) ──────────────────────────────────────────────────────

def cmd_probe(args):
    print(f"key fingerprint: {KEY_FP}")
    if not KEY:
        print("HALT: no key"); sys.exit(1)

    probe_slots = {
        2022: "2022-11-15T23:00:00Z",
        2023: "2023-11-14T23:00:00Z",
        2024: "2024-11-12T23:00:00Z",
        2025: "2025-11-11T23:00:00Z",
    }
    results = {"sport_level": {}, "event_level": {}, "hard_rock_keys": [], "cost": 0}

    # Check balance first
    r0, h0 = api_get(f"{BASE}/sports", {"apiKey": KEY})
    if r0:
        rem = int(r0.headers.get("x-requests-remaining", "0"))
        print(f"x-requests-remaining before probe: {rem}")
    else:
        print("HALT: cannot reach API"); sys.exit(1)

    # (a) Sport-level: regions=us2 then us, markets=h2h, per season
    print("\n=== Sport-level probe (h2h) ===")
    for season, dt in sorted(probe_slots.items()):
        results["sport_level"][str(season)] = {}
        for region in ["us2", "us"]:
            r, hdr = api_get(f"{BASE}/historical/sports/{SPORT}/odds",
                             {"apiKey": KEY, "regions": region, "markets": "h2h",
                              "oddsFormat": "american", "date": dt})
            results["cost"] += hdr.get("used", 0)
            if r and r.status_code == 200:
                books_found = set()
                for g in r.json().get("data", []):
                    for bm in g.get("bookmakers", []):
                        books_found.add(bm["key"])
                results["sport_level"][str(season)][region] = sorted(books_found)
                print(f"  {season} {region}: {sorted(books_found)}")
            else:
                code = r.status_code if r else "FAIL"
                results["sport_level"][str(season)][region] = []
                print(f"  {season} {region}: HTTP {code}")

    # (b) Event-level: regions=us2, markets=player_points, per season
    print("\n=== Event-level probe (player_points, us2) ===")
    for season, dt in sorted(probe_slots.items()):
        # Get one event ID (reuse a sport-level call with us, h2h — cheap)
        r, hdr = api_get(f"{BASE}/historical/sports/{SPORT}/odds",
                         {"apiKey": KEY, "regions": "us", "markets": "h2h",
                          "oddsFormat": "american", "date": dt})
        results["cost"] += hdr.get("used", 0)
        if not r or r.status_code != 200 or not r.json().get("data"):
            print(f"  {season}: no events found")
            continue
        eid = r.json()["data"][0]["id"]
        r2, h2 = api_get(f"{BASE}/historical/sports/{SPORT}/events/{eid}/odds",
                         {"apiKey": KEY, "regions": "us2", "markets": "player_points",
                          "oddsFormat": "american", "date": dt})
        results["cost"] += h2.get("used", 0)
        if r2 and r2.status_code == 200:
            ev = r2.json().get("data", r2.json())
            ev_books = set()
            if isinstance(ev, dict):
                for bm in ev.get("bookmakers", []):
                    ev_books.add(bm["key"])
            results["event_level"][str(season)] = sorted(ev_books)
            print(f"  {season}: {sorted(ev_books)}")
        else:
            code = r2.status_code if r2 else "FAIL"
            results["event_level"][str(season)] = []
            print(f"  {season}: HTTP {code}")

    # (c) Find Hard Rock keys
    all_hr = set()
    for sd in results["sport_level"].values():
        for books in sd.values():
            all_hr.update(b for b in books if "hardrock" in b.lower())
    for books in results["event_level"].values():
        all_hr.update(b for b in books if "hardrock" in b.lower())

    results["hard_rock_keys"] = sorted(all_hr)
    print(f"\nHard Rock keys found: {sorted(all_hr)}")

    # Build final BOOKS list
    books = list(DEFAULT_BOOKS)
    if all_hr:
        hr_key = sorted(all_hr)[0]
        if len(books) >= 10 and "lowvig" in books:
            books.remove("lowvig")
        books.append(hr_key)
    results["books"] = books
    print(f"Final BOOKS ({len(books)}): {books}")
    print(f"Total probe cost: {results['cost']} credits")

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    with open(DATA_ROOT / "probe_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved: {DATA_ROOT / 'probe_results.json'}")


# ─── SCHEDULE (Item 0) ────────────────────────────────────────────────

def cmd_schedule(args):
    gp = Path.home() / "mlb-model" / "nba" / "data" / "games.parquet"
    games = pd.read_parquet(gp) if gp.exists() else pd.DataFrame()
    mf_path = Path.home() / "mlb-model" / "data" / "odds_archive" / "nba" / "manifests" / "nba_event_manifest.parquet"
    manifest = pd.read_parquet(mf_path) if mf_path.exists() else pd.DataFrame()

    SCHED_DIR.mkdir(parents=True, exist_ok=True)
    for season, (start, end) in SEASONS.items():
        season_str = f"{season}-{(season + 1) % 100:02d}"
        sg = games[games["season"] == season_str] if len(games) > 0 else pd.DataFrame()
        if len(sg) > 0:
            dates = sorted(sg["date"].dt.strftime("%Y-%m-%d").unique().tolist())
            source = "games.parquet"
        elif len(manifest) > 0 and season in (2025,):
            mf_dates = sorted(set(
                (pd.to_datetime(manifest["commence_time"]).dt.tz_localize(None)
                 - timedelta(hours=5)).dt.strftime("%Y-%m-%d").unique()
            ))
            extra = [d.isoformat() for d in _date_range(Date(2026, 3, 29), end)]
            dates = sorted(set(mf_dates) | set(extra))
            source = "manifest+range"
        else:
            dates = [d.isoformat() for d in _date_range(start, end)]
            source = "full_range"
        out = {"season": season, "season_str": season_str,
               "dates": dates, "n_dates": len(dates), "source": source}
        p = SCHED_DIR / f"dates_{season}.json"
        with open(p, "w") as f:
            json.dump(out, f, indent=1)
        print(f"Season {season} ({season_str}): {len(dates)} dates [{source}] -> {p.name}")


# ─── LINES (Item 1) ───────────────────────────────────────────────────

def cmd_lines(args):
    print(f"key fingerprint: {KEY_FP}")
    if not KEY:
        print("HALT: no key"); sys.exit(1)

    books = load_books()
    books_str = ",".join(books)
    print(f"BOOKS ({len(books)}): {books}")

    seasons = [int(s) for s in args.season.split(",")]
    state = State()

    # Print initial remaining
    r0, h0 = api_get(f"{BASE}/sports", {"apiKey": KEY})
    if r0:
        init_rem = int(r0.headers.get("x-requests-remaining", "0"))
        print(f"x-requests-remaining: {init_rem}")
    else:
        print("HALT: cannot reach API"); sys.exit(1)

    for season in seasons:
        start, end = SEASONS[season]
        out_dir = DATA_ROOT / "lines_hourly" / f"season={season}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Load date list
        sched_file = SCHED_DIR / f"dates_{season}.json"
        if sched_file.exists():
            with open(sched_file) as f:
                dates = json.load(f)["dates"]
        else:
            dates = [d.isoformat() for d in _date_range(start, end)]

        # Build hourly task list
        tasks = []
        for d_str in dates:
            d = Date.fromisoformat(d_str)
            for h in range(24):
                dt = datetime(d.year, d.month, d.day, h, 0, tzinfo=timezone.utc)
                tag = dt.strftime("%Y%m%dT%H%M%SZ")
                pq = out_dir / f"snap_{tag}.parquet"
                if not pq.exists():
                    tasks.append((_to_z(dt), pq))

        total_hourly = len(tasks)
        print(f"\nSeason {season}: {len(dates)} dates, {total_hourly} hourly snapshots to pull")
        print(f"  estimated credits: {total_hourly} x {LINE_COST} = {total_hourly * LINE_COST}")

        if not tasks:
            print("  all done, skipping to events collection")
        else:
            # A5: first call cost check (use a known-good Tuesday 23:00Z)
            first_ts, first_pq = tasks[0]
            r, hdr = api_get(f"{BASE}/historical/sports/{SPORT}/odds",
                             {"apiKey": KEY, "bookmakers": books_str,
                              "markets": LINE_MKTS, "oddsFormat": "american",
                              "date": first_ts}, state)
            if hdr.get("used") != LINE_COST:
                print(f"STOP: first call cost {hdr.get('used')}, expected {LINE_COST}")
                sys.exit(1)
            if r and r.status_code == 200:
                data = r.json()
                rows, snap, evts = flatten_snap(data, first_ts)
                for row in rows:
                    row["kind"] = "hourly"
                save_snap(rows, data, first_pq,
                          first_pq.with_name(first_pq.stem + ".json.gz"))
            tasks = tasks[1:]
            print(f"  first call OK: used={hdr['used']} rem={hdr['remaining']}")

            # Parallel hourly grid
            def do_hourly(task):
                ts, pq = task
                if pq.exists() or state.should_stop():
                    return 0
                gz = pq.with_name(pq.stem + ".json.gz")
                r, hdr = api_get(f"{BASE}/historical/sports/{SPORT}/odds",
                                 {"apiKey": KEY, "bookmakers": books_str,
                                  "markets": LINE_MKTS, "oddsFormat": "american",
                                  "date": ts}, state)
                if r and r.status_code == 200:
                    data = r.json()
                    rows, snap, evts = flatten_snap(data, ts)
                    for row in rows:
                        row["kind"] = "hourly"
                    save_snap(rows, data, pq, gz)
                    return len(rows)
                return 0

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futs = {pool.submit(do_hourly, t): i for i, t in enumerate(tasks)}
                done = 0
                for fut in as_completed(futs):
                    done += 1
                    if done == 200:
                        state.report_rate_and_eta(total_hourly, f"season {season}")
                    if done % 500 == 0:
                        print(f"  [{done}/{len(tasks)}] {state.summary()}")
                    if state.should_stop():
                        pool.shutdown(wait=False, cancel_futures=True)
                        break

            print(f"  hourly done: {state.summary()}")

        if state.should_stop():
            _save_events_from_parquets(season, out_dir)
            break

        # Collect events
        events_df = _save_events_from_parquets(season, out_dir)
        if events_df is None or len(events_df) == 0:
            print(f"  no events found for season {season}")
            continue

        # A10(e): after first 50 bulk calls, count Hard Rock rows
        hr_keys = [b for b in books if "hardrock" in b.lower()]
        if hr_keys:
            _check_hardrock(season, out_dir, hr_keys)

        # Phase 2: close snapshots (A4)
        close_tasks = _build_close_tasks(events_df, out_dir)
        print(f"  close snapshots to pull: {len(close_tasks)}")

        if close_tasks:
            def do_close(task):
                ts, pq = task
                if pq.exists() or state.should_stop():
                    return 0
                gz = pq.with_name(pq.stem + ".json.gz")
                r, hdr = api_get(f"{BASE}/historical/sports/{SPORT}/odds",
                                 {"apiKey": KEY, "bookmakers": books_str,
                                  "markets": LINE_MKTS, "oddsFormat": "american",
                                  "date": ts}, state)
                if r and r.status_code == 200:
                    data = r.json()
                    rows, snap, evts = flatten_snap(data, ts)
                    for row in rows:
                        row["kind"] = "close"
                    save_snap(rows, data, pq, gz)
                    return len(rows)
                return 0

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futs = {pool.submit(do_close, t): i for i, t in enumerate(close_tasks)}
                done = 0
                for fut in as_completed(futs):
                    done += 1
                    if done % 200 == 0:
                        print(f"  close [{done}/{len(close_tasks)}] {state.summary()}")

        print(f"Season {season} complete: {state.summary()}")
        # Track books per season
        _report_books_per_season(season, out_dir, books)

    print(f"\nLINES total: {state.summary()}")


def _save_events_from_parquets(season, out_dir):
    """Scan hourly parquets, collect unique events, save events parquet."""
    events = {}
    for pq in sorted(out_dir.glob("snap_*.parquet")):
        try:
            df = pd.read_parquet(pq, columns=["event_id", "commence_time",
                                               "home_team", "away_team"])
            for _, row in df.drop_duplicates("event_id").iterrows():
                eid = row["event_id"]
                if eid and eid not in events:
                    events[eid] = {"event_id": eid,
                                   "commence_time": row["commence_time"],
                                   "home_team": row["home_team"],
                                   "away_team": row["away_team"]}
        except Exception:
            pass
    if not events:
        return None
    ev_dir = DATA_ROOT / "events"
    ev_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(list(events.values()))
    df.to_parquet(ev_dir / f"events_{season}.parquet", index=False)
    print(f"  events_{season}.parquet: {len(df)} events")
    return df


def _build_close_tasks(events_df, out_dir):
    """From events, compute close snapshot times (tip - 5 min), deduplicate."""
    close_times = set()
    for ct in events_df["commence_time"].unique():
        try:
            tip = _parse_utc(ct)
            close_dt = tip - timedelta(minutes=5)
            close_times.add(_to_z(close_dt))
        except (ValueError, TypeError):
            pass
    tasks = []
    for ts in sorted(close_times):
        tag = ts.replace("-", "").replace(":", "").replace("Z", "Z").replace("T", "T")
        # Format: 20241022T2355Z
        dt = _parse_utc(ts)
        fname = f"close_{dt.strftime('%Y%m%dT%H%M%SZ')}.parquet"
        pq = out_dir / fname
        if not pq.exists():
            tasks.append((ts, pq))
    return tasks


def _check_hardrock(season, out_dir, hr_keys):
    """A10(e): count Hard Rock rows after first 50 parquets."""
    parquets = sorted(out_dir.glob("snap_*.parquet"))[:50]
    hr_count = 0
    for pq in parquets:
        try:
            df = pd.read_parquet(pq, columns=["bookmaker"])
            hr_count += df["bookmaker"].isin(hr_keys).sum()
        except Exception:
            pass
    if hr_count == 0:
        print(f"  WARNING: 0 Hard Rock rows in first 50 parquets for season {season}")
    else:
        print(f"  Hard Rock rows in first 50: {hr_count}")


def _report_books_per_season(season, out_dir, books):
    """Report which books actually returned data."""
    sample = sorted(out_dir.glob("snap_*.parquet"))[:20]
    found = set()
    for pq in sample:
        try:
            df = pd.read_parquet(pq, columns=["bookmaker"])
            found.update(df["bookmaker"].unique())
        except Exception:
            pass
    missing = set(books) - found
    if missing:
        print(f"  season {season} missing books: {sorted(missing)}")
    else:
        print(f"  season {season}: all {len(books)} books present")


# ─── EVENT-LEVEL PULL (Items 2 & 4) ──────────────────────────────────

def cmd_event_pull(args, markets, expected_cost, n_markets, label, subdir):
    """Shared implementation for props (item 2) and derivative markets (item 4)."""
    print(f"key fingerprint: {KEY_FP}")
    if not KEY:
        print("HALT: no key"); sys.exit(1)

    books = load_books()
    books_str = ",".join(books)
    print(f"BOOKS ({len(books)}): {books}")

    seasons = [int(s) for s in args.season.split(",")]
    state = State()

    r0, h0 = api_get(f"{BASE}/sports", {"apiKey": KEY})
    if r0:
        print(f"x-requests-remaining: {int(r0.headers.get('x-requests-remaining', 0))}")

    for season in seasons:
        events_df = load_events(season)
        out_base = DATA_ROOT / subdir / f"season={season}"
        out_base.mkdir(parents=True, exist_ok=True)

        # Build task list: T-24h and T-1h per event
        tasks = []
        for _, ev in events_df.iterrows():
            eid = ev["event_id"]
            ct = ev["commence_time"]
            try:
                tip = _parse_utc(ct)
            except (ValueError, TypeError):
                continue
            for tag, delta in [("T-24h", timedelta(hours=24)),
                               ("T-1h", timedelta(hours=1))]:
                req_dt = tip - delta
                req_ts = _to_z(req_dt)
                pq = out_base / f"{eid}_{tag}.parquet"
                if not pq.exists():
                    tasks.append((eid, req_ts, pq))

        total = len(tasks)
        print(f"\n{label} season {season}: {len(events_df)} events, {total} calls to make")
        print(f"  estimated credits: {total} x {expected_cost} = {total * expected_cost}")

        if not tasks:
            print("  all done")
            continue

        # A5: cost check on first call
        first_eid, first_ts, first_pq = tasks[0]
        r, hdr = api_get(
            f"{BASE}/historical/sports/{SPORT}/events/{first_eid}/odds",
            {"apiKey": KEY, "bookmakers": books_str,
             "markets": markets, "oddsFormat": "american",
             "date": first_ts}, state)
        used = hdr.get("used", 0)
        if used > 10 * n_markets:
            print(f"STOP: first call cost {used} > {10 * n_markets} (10 x {n_markets} markets)")
            sys.exit(1)
        print(f"  first call: used={used} (expected {expected_cost})")
        # Track empty-but-charged
        if r and r.status_code == 200:
            rows = flatten_ev(r.json(), first_ts)
            first_pq.parent.mkdir(parents=True, exist_ok=True)
            if rows:
                pd.DataFrame(rows).to_parquet(first_pq, index=False)
            else:
                pd.DataFrame(columns=EMPTY_COLS).to_parquet(first_pq, index=False)
                if used > 0:
                    state.empty_charged += 1
        tasks = tasks[1:]

        def do_event(task):
            eid, ts, pq = task
            if pq.exists() or state.should_stop():
                return 0
            r, hdr = api_get(
                f"{BASE}/historical/sports/{SPORT}/events/{eid}/odds",
                {"apiKey": KEY, "bookmakers": books_str,
                 "markets": markets, "oddsFormat": "american",
                 "date": ts}, state)
            used = hdr.get("used", 0)
            if used > 10 * n_markets:
                with state.lock:
                    state.cost_violations.append((eid, ts, used))
                    state.stop = True
                print(f"  STOP: event {eid} cost {used} > {10 * n_markets}")
                return 0
            pq.parent.mkdir(parents=True, exist_ok=True)
            if r and r.status_code == 200:
                rows = flatten_ev(r.json(), ts)
                if rows:
                    pd.DataFrame(rows).to_parquet(pq, index=False)
                else:
                    pd.DataFrame(columns=EMPTY_COLS).to_parquet(pq, index=False)
                    if used > 0:
                        with state.lock:
                            state.empty_charged += 1
                return len(rows)
            else:
                pd.DataFrame(columns=EMPTY_COLS).to_parquet(pq, index=False)
                return 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = {pool.submit(do_event, t): i for i, t in enumerate(tasks)}
            done = 0
            for fut in as_completed(futs):
                done += 1
                if done == 200:
                    state.report_rate_and_eta(total, f"{label} season {season}")
                if done % 500 == 0:
                    print(f"  [{done}/{len(tasks)}] {state.summary()}")
                if state.should_stop():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

        print(f"  {label} season {season}: {state.summary()}")
        print(f"  empty-but-charged: {state.empty_charged}, cost violations: {len(state.cost_violations)}")
        _report_books_per_season(
            season,
            out_base,
            books
        )
        if state.should_stop():
            break

    print(f"\n{label} total: {state.summary()}")
    print(f"  empty-but-charged: {state.empty_charged}")
    if state.cost_violations:
        print(f"  cost violations: {state.cost_violations[:5]}")


def cmd_props(args):
    cmd_event_pull(args, PROP_MKTS, PROP_COST, PROP_N, "PROPS", "props")

def cmd_markets(args):
    cmd_event_pull(args, DERIV_MKTS, DERIV_COST, DERIV_N, "MARKETS", "event_markets")


# ─── INPLAY (Item 3) ─────────────────────────────────────────────────

def cmd_inplay(args):
    print(f"key fingerprint: {KEY_FP}")
    if not KEY:
        print("HALT: no key"); sys.exit(1)

    books = load_books()
    books_str = ",".join(books)
    print(f"BOOKS ({len(books)}): {books}")

    seasons = [int(s) for s in args.season.split(",")]
    state = State()

    r0, h0 = api_get(f"{BASE}/sports", {"apiKey": KEY})
    if r0:
        print(f"x-requests-remaining: {int(r0.headers.get('x-requests-remaining', 0))}")

    for season in seasons:
        events_df = load_events(season)
        out_dir = DATA_ROOT / "inplay" / f"season={season}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # A6: compute nights x snapshots
        # Group events by game night (UTC date of commence_time)
        events_df = events_df.copy()
        events_df["tip_utc"] = pd.to_datetime(events_df["commence_time"])
        # Game night = ET date = UTC date shifted back 5h
        events_df["night"] = (events_df["tip_utc"] - timedelta(hours=5)).dt.date.astype(str)

        tasks = []
        total_nights = 0
        for night, grp in events_df.groupby("night"):
            tips = grp["tip_utc"].sort_values()
            first_tip = tips.min()
            last_tip = tips.max()
            window_start = first_tip - timedelta(minutes=5)
            window_end = last_tip + timedelta(hours=3)
            total_nights += 1
            t = window_start
            while t <= window_end:
                ts = _to_z(t)
                tag = t.strftime("%Y%m%dT%H%M%SZ")
                pq = out_dir / f"snap_{tag}.parquet"
                if not pq.exists():
                    tasks.append((ts, pq))
                t += timedelta(minutes=5)

        total = len(tasks)
        est_credits = total * LINE_COST
        print(f"\nINPLAY season {season}: {total_nights} nights, {total} snapshots")
        print(f"  estimated credits: {total} x {LINE_COST} = {est_credits}")

        if not tasks:
            print("  all done")
            continue

        def do_inplay(task):
            ts, pq = task
            if pq.exists() or state.should_stop():
                return 0
            gz = pq.with_name(pq.stem + ".json.gz")
            r, hdr = api_get(f"{BASE}/historical/sports/{SPORT}/odds",
                             {"apiKey": KEY, "bookmakers": books_str,
                              "markets": LINE_MKTS, "oddsFormat": "american",
                              "date": ts}, state)
            if r and r.status_code == 200:
                data = r.json()
                rows, snap, evts = flatten_snap(data, ts, keep_inplay=True)
                for row in rows:
                    row["kind"] = "inplay"
                save_snap(rows, data, pq, gz)
                return len(rows)
            return 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = {pool.submit(do_inplay, t): i for i, t in enumerate(tasks)}
            done = 0
            for fut in as_completed(futs):
                done += 1
                if done == 200:
                    state.report_rate_and_eta(total, f"INPLAY season {season}")
                if done % 500 == 0:
                    print(f"  [{done}/{len(tasks)}] {state.summary()}")
                if state.should_stop():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

        print(f"  INPLAY season {season}: {state.summary()}")
        if state.should_stop():
            break

    print(f"\nINPLAY total: {state.summary()}")


# ─── NULL CONTROL (A7) ───────────────────────────────────────────────

def cmd_null(args):
    """A7: compare March 2026 backfill with item-1 hourly data."""
    backfill_path = (Path.home() / "mlb-model" / "data" / "odds_archive" / "nba"
                     / "game_markets" / "season=2026" / "month=03" / "data_2026_03.parquet")
    if not backfill_path.exists():
        print(f"HALT: backfill not found at {backfill_path}"); sys.exit(1)

    bf = pd.read_parquet(backfill_path)
    # Filter to draftkings only
    bf_dk = bf[bf["bookmaker"] == "draftkings"].copy()
    print(f"Backfill DraftKings rows: {len(bf_dk)}")

    # Load hourly data for season=2025 (covers 2025-26 season)
    hourly_dir = DATA_ROOT / "lines_hourly" / "season=2025"
    if not hourly_dir.exists():
        print(f"HALT: hourly dir not found at {hourly_dir}"); sys.exit(1)

    # Read all hourly parquets and filter to DraftKings + March 2026 events
    march_events = set(bf_dk["event_id"].unique())
    hourly_rows = []
    for pq in sorted(hourly_dir.glob("*.parquet")):
        try:
            df = pd.read_parquet(pq)
            dk = df[(df["bookmaker"] == "draftkings") & (df["event_id"].isin(march_events))]
            if len(dk) > 0:
                hourly_rows.append(dk)
        except Exception:
            pass

    if not hourly_rows:
        print("No matching hourly data found for March 2026 events")
        return

    hourly = pd.concat(hourly_rows, ignore_index=True)
    print(f"Hourly DraftKings rows matching March events: {len(hourly)}")

    # Reshape backfill for matching
    # Backfill has: event_id, market_key, last_update, over_price, under_price
    # Hourly has: event_id, market, outcome_name, book_last_update, price
    # Match on (event_id, market, outcome_name, last_update)
    # The backfill doesn't store outcome_name directly — we need to reconstruct

    # For h2h: backfill over_price = one team's ML (row per team?)
    # For spreads/totals: over_price = one side
    # Need to check the backfill structure more carefully

    # Try matching just on (event_id, market_key, last_update) and comparing all prices
    bf_dk = bf_dk.rename(columns={"market_key": "market"})

    # Merge on event_id, market, last_update == book_last_update
    merged = bf_dk.merge(
        hourly,
        left_on=["event_id", "market", "last_update"],
        right_on=["event_id", "market", "book_last_update"],
        how="inner",
        suffixes=("_bf", "_hr")
    )

    print(f"Matched rows (event, market, last_update): {len(merged)}")

    if len(merged) > 0:
        # Compare prices where both exist
        # backfill has over_price, hourly has price
        # They should match for the same outcome
        price_diff = (merged["over_price"] - merged["price"]).abs()
        valid_diffs = price_diff.dropna()
        if len(valid_diffs) > 0:
            print(f"Price comparisons: {len(valid_diffs)}")
            print(f"Max absolute difference: {valid_diffs.max()}")
            print(f"Mean absolute difference: {valid_diffs.mean():.6f}")
            exact_matches = (valid_diffs == 0).sum()
            print(f"Exact matches: {exact_matches}/{len(valid_diffs)}")
        else:
            print("No valid price comparisons (all NaN)")
    else:
        print("WARNING: zero matched rows — schemas may not align")


# ─── MAIN ─────────────────────────────────────────────────────────────

def main():
    print(f"key fingerprint: {KEY_FP}")
    ap = argparse.ArgumentParser(description="NBA historical odds pull (NBA-D1)")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("probe", help="A10 Hard Rock discovery")
    sub.add_parser("schedule", help="Item 0: date lists")

    p_lines = sub.add_parser("lines", help="Item 1: hourly + close")
    p_lines.add_argument("--season", required=True)

    p_props = sub.add_parser("props", help="Item 2: player props")
    p_props.add_argument("--season", required=True)

    p_mkts = sub.add_parser("markets", help="Item 4: derivative markets")
    p_mkts.add_argument("--season", required=True)

    p_inp = sub.add_parser("inplay", help="Item 3: in-play snapshots")
    p_inp.add_argument("--season", required=True)

    sub.add_parser("null", help="A7 null control")

    args = ap.parse_args()
    if args.cmd == "probe":
        cmd_probe(args)
    elif args.cmd == "schedule":
        cmd_schedule(args)
    elif args.cmd == "lines":
        cmd_lines(args)
    elif args.cmd == "props":
        cmd_props(args)
    elif args.cmd == "markets":
        cmd_markets(args)
    elif args.cmd == "inplay":
        cmd_inplay(args)
    elif args.cmd == "null":
        cmd_null(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
