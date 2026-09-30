#!/usr/bin/env python3
"""
E-WO2: Bulk NHL historical odds pull — in-play, derivatives, props, dense pre-match.
4 concurrent workers with exponential backoff. Resume-safe. Budget-tracked.

Usage:
  python3 nhl/pipeline/pull_nhl_bulk_history.py inplay   [--season 2024,2025,2023,2022] [--dry-run]
  python3 nhl/pipeline/pull_nhl_bulk_history.py deriv     [--season 2024,2025,2023] [--dry-run]
  python3 nhl/pipeline/pull_nhl_bulk_history.py props     [--season 2024,2025,2023] [--dry-run]
  python3 nhl/pipeline/pull_nhl_bulk_history.py dense     [--season 2024,2025,2023,2022] [--dry-run]
"""
import argparse, gzip, hashlib, json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta, date as _date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

KEY = os.getenv("ODDS_API_KEY", "")
KEY_FP = hashlib.sha256(KEY.strip().encode()).hexdigest()[:8] if KEY else "UNSET"
BASE = "https://api.the-odds-api.com/v4"

BOOKS = "pinnacle,draftkings,fanduel,betmgm,williamhill_us,betrivers,bovada,pointsbetus,unibet_us,betonlineag"
N_BOOKS = 10

SPEND_CAP = 2_400_000
GLOBAL_FLOOR = 5_000

BOX_DIR = ROOT / "nhl" / "cache"
HIST_BASE = ROOT / "data" / "odds_archive" / "nhl" / "history"
LINES_DIR = HIST_BASE / "lines"

GAMES_PER_SEASON = 1312
SEASONS_DATES = {
    2022: (_date(2022, 10, 7), _date(2023, 6, 15)),
    2023: (_date(2023, 10, 10), _date(2024, 6, 25)),
    2024: (_date(2024, 10, 4), _date(2025, 6, 25)),
    2025: (_date(2025, 10, 4), _date(2026, 6, 25)),
}

# Thread-safe budget tracker
_lock = threading.Lock()
_credits_used = 0
_remaining = 999_999
_call_count = 0
_t0 = time.time()
_stopped = False


def _update_budget(used, remaining):
    global _credits_used, _remaining, _call_count, _stopped
    with _lock:
        _credits_used += used
        _remaining = remaining
        _call_count += 1
        if _remaining < GLOBAL_FLOOR:
            _stopped = True
            print(f"  *** GLOBAL FLOOR reached: remaining={_remaining} < {GLOBAL_FLOOR}")
        if _credits_used >= SPEND_CAP:
            _stopped = True
            print(f"  *** SPEND CAP reached: used={_credits_used} >= {SPEND_CAP}")


def _budget_ok(next_cost):
    with _lock:
        if _stopped:
            return False
        if _remaining - next_cost < GLOBAL_FLOOR:
            return False
        if _credits_used + next_cost > SPEND_CAP:
            return False
        return True


def _status():
    with _lock:
        elapsed = time.time() - _t0
        rate = _call_count / elapsed if elapsed > 0 else 0
        return _call_count, _credits_used, _remaining, rate


def _parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _to_z(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _request_with_backoff(url, params, max_retries=5):
    """GET with exponential backoff on 429/5xx. Returns (response, used, remaining) or None."""
    delay = 2.0
    for attempt in range(max_retries + 1):
        if _stopped:
            return None
        try:
            r = requests.get(url, params=params, timeout=60)
            used = int(r.headers.get("x-requests-last", "0"))
            remaining = int(r.headers.get("x-requests-remaining", "0"))
            _update_budget(used, remaining)
            if r.status_code == 200:
                return r, used, remaining
            if r.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(min(delay, 60))
                delay *= 2
                continue
            # Non-retryable error
            return r, used, remaining
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                time.sleep(min(delay, 60))
                delay *= 2
            else:
                return None
    return None


def flatten_snapshot_inplay(data, requested_utc):
    """One row per outcome — KEEPS in-play events. Includes book_last_update."""
    rows = []
    snapshot_utc = data.get("timestamp", data.get("previous_timestamp", requested_utc))
    games = data.get("data", [])
    if not isinstance(games, list):
        return rows, snapshot_utc
    for g in games:
        eid = g.get("id", "")
        commence = g.get("commence_time", "")
        home = g.get("home_team", "")
        away = g.get("away_team", "")
        for bm in g.get("bookmakers", []):
            book = bm.get("key", "")
            bm_update = bm.get("last_update", "")
            for mkt in bm.get("markets", []):
                mk = mkt.get("key", "")
                mkt_update = mkt.get("last_update", bm_update)
                for oc in mkt.get("outcomes", []):
                    rows.append({
                        "snapshot_utc": snapshot_utc,
                        "requested_utc": requested_utc,
                        "event_id": eid,
                        "commence_time": commence,
                        "home_team": home,
                        "away_team": away,
                        "bookmaker": book,
                        "book_last_update": mkt_update,
                        "market": mk,
                        "outcome_name": oc.get("name", ""),
                        "description": oc.get("description", ""),
                        "point": oc.get("point"),
                        "price": oc.get("price"),
                    })
    return rows, snapshot_utc


def flatten_event_response(data, requested_utc):
    """One row per outcome for a single-event response. Includes book_last_update."""
    rows = []
    if not data:
        return rows
    snapshot_utc = data.get("timestamp", data.get("previous_timestamp", requested_utc))
    ev = data.get("data", data)
    if not isinstance(ev, dict):
        return rows
    eid = ev.get("id", "")
    commence = ev.get("commence_time", "")
    home = ev.get("home_team", "")
    away = ev.get("away_team", "")
    for bm in ev.get("bookmakers", []):
        book = bm.get("key", "")
        bm_update = bm.get("last_update", "")
        for mkt in bm.get("markets", []):
            mk = mkt.get("key", "")
            mkt_update = mkt.get("last_update", bm_update)
            for oc in mkt.get("outcomes", []):
                rows.append({
                    "snapshot_utc": snapshot_utc,
                    "requested_utc": requested_utc,
                    "event_id": eid,
                    "commence_time": commence,
                    "home_team": home,
                    "away_team": away,
                    "bookmaker": book,
                    "book_last_update": mkt_update,
                    "market": mk,
                    "outcome_name": oc.get("name", ""),
                    "description": oc.get("description", ""),
                    "point": oc.get("point"),
                    "price": oc.get("price"),
                })
    return rows


# ─── Game-night helpers ──────────────────────────────────────────────────

def game_nights(season):
    """Return list of (et_date_str, [(game_id, commence_utc), ...]) for all reg-season nights."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    nights = {}
    for i in range(1, GAMES_PER_SEASON + 1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists():
            continue
        with open(bp) as f:
            d = json.load(f)
        start_utc = d.get("startTimeUTC", d.get("gameDate", ""))
        if not start_utc or len(start_utc) < 10:
            continue
        try:
            dt = _parse_utc(start_utc)
            et_date = dt.astimezone(et).date().isoformat()
        except (ValueError, TypeError):
            et_date = start_utc[:10]
        nights.setdefault(et_date, []).append((gid, start_utc))
    return sorted(nights.items())


def event_ids_from_lines(season):
    """Get event IDs that have Pinnacle h2h from the lines data."""
    lines_dir = LINES_DIR / f"season={season}"
    if not lines_dir.exists():
        return []
    events = set()
    for f in sorted(lines_dir.glob("snap_*.parquet")):
        try:
            df = pd.read_parquet(f, columns=["event_id", "bookmaker", "market", "commence_time"])
            pin_h2h = df[(df["bookmaker"] == "pinnacle") & (df["market"] == "h2h")]
            for eid in pin_h2h["event_id"].unique():
                ct = pin_h2h[pin_h2h["event_id"] == eid]["commence_time"].iloc[0]
                events.add((eid, ct))
        except Exception:
            pass
    return sorted(events, key=lambda x: x[1])


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 1: IN-PLAY (E4)
# ═══════════════════════════════════════════════════════════════════════════

def inplay_snapshot_plan(season):
    """Build list of (requested_utc_str, output_path) for a season's in-play snapshots."""
    nights = game_nights(season)
    out_dir = HIST_BASE / "inplay" / f"season={season}"
    plan = []
    for et_date, games in nights:
        commence_times = []
        for gid, start_utc in games:
            try:
                commence_times.append(_parse_utc(start_utc))
            except (ValueError, TypeError):
                pass
        if not commence_times:
            continue
        earliest = min(commence_times)
        latest = max(commence_times)
        # From (earliest - 5 min) to (latest + 3h15m), every 5 min
        t = earliest - timedelta(minutes=5)
        t_end = latest + timedelta(hours=3, minutes=15)
        while t <= t_end:
            req_str = _to_z(t)
            fname = f"snap_{t.strftime('%Y%m%dT%H%M%SZ')}"
            pq = out_dir / f"{fname}.parquet"
            plan.append((req_str, pq))
            t += timedelta(minutes=5)
    return plan


def _pull_one_inplay(req_str, pq_path):
    """Pull a single inplay snapshot. Returns (success, used)."""
    gz_path = pq_path.with_suffix(".json.gz")
    if pq_path.exists():
        return True, 0
    if not _budget_ok(30):
        return False, 0
    result = _request_with_backoff(
        f"{BASE}/historical/sports/icehockey_nhl/odds",
        {"apiKey": KEY, "bookmakers": BOOKS, "markets": "h2h,spreads,totals",
         "oddsFormat": "american", "date": req_str})
    if result is None:
        return False, 0
    r, used, remaining = result
    if r.status_code != 200:
        return False, used
    data = r.json()
    rows, snap_utc = flatten_snapshot_inplay(data, req_str)
    pq_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        pd.DataFrame(rows).to_parquet(pq_path, index=False)
    with gzip.open(gz_path, "wt") as f:
        json.dump(data, f)
    return True, used


def cmd_inplay(seasons, dry_run):
    for season in seasons:
        plan = inplay_snapshot_plan(season)
        todo = [(r, p) for r, p in plan if not p.exists()]
        skip = len(plan) - len(todo)
        est_credits = len(todo) * 30
        nights = game_nights(season)
        print(f"\n  INPLAY season {season}: {len(nights)} nights, {len(plan)} snapshots total, "
              f"{skip} done, {len(todo)} to pull, est {est_credits:,} credits")
        if dry_run or not todo:
            continue
        # First call: verify cost
        if _call_count == 0 and todo:
            req_str, pq_path = todo[0]
            ok, used = _pull_one_inplay(req_str, pq_path)
            if used > 0 and used != 30:
                print(f"  STOP: first call x-requests-last={used}, expected 30 (10 books × 3 markets)")
                return
            if used == 30:
                print(f"  First call OK: x-requests-last=30")
            todo = [(r, p) for r, p in todo if not p.exists()]
        # Project finish
        cc, cu, rem, rate = _status()
        if rate > 0 and todo:
            secs = len(todo) / (rate * 4)  # 4 workers
            finish = datetime.now(timezone.utc) + timedelta(seconds=secs)
            print(f"  Rate: {rate:.2f} calls/s, projected finish: {finish.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        # Run with 4 workers
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {pool.submit(_pull_one_inplay, r, p): (r, p) for r, p in todo}
            done_count = 0
            for fut in as_completed(futs):
                ok, used = fut.result()
                done_count += 1
                if done_count % 200 == 0:
                    cc, cu, rem, rate = _status()
                    proj_remaining = len(todo) - done_count
                    proj_sec = proj_remaining / (rate * 4) if rate > 0 else 0
                    proj_finish = datetime.now(timezone.utc) + timedelta(seconds=proj_sec)
                    print(f"  [{done_count}/{len(todo)}] credits_used={cu:,} remaining={rem:,} "
                          f"rate={rate:.2f}/s proj_finish={proj_finish.strftime('%H:%M:%SZ')}")
                if _stopped:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
        cc, cu, rem, rate = _status()
        n_saved = len(list((HIST_BASE / "inplay" / f"season={season}").glob("*.parquet")))
        print(f"  Season {season} done: {n_saved} parquets saved, credits_used={cu:,}, remaining={rem:,}")
        if _stopped:
            break


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 2: DERIVATIVE MARKETS (E5)
# ═══════════════════════════════════════════════════════════════════════════

DERIV_MARKETS = "h2h_3_way,totals_p1,h2h_p1,spreads_p1,team_totals,alternate_totals,alternate_spreads,h2h_ot"
DERIV_N_MARKETS = 8
DERIV_COST = 10 * DERIV_N_MARKETS  # 80 per event-snapshot


def deriv_plan(season):
    """Build list of (event_id, commence, label, req_str, output_path) for derivative markets."""
    events = event_ids_from_lines(season)
    out_dir = HIST_BASE / "event_markets" / f"season={season}"
    plan = []
    for eid, ct in events:
        try:
            ct_dt = _parse_utc(ct)
        except (ValueError, TypeError):
            continue
        for label, delta in [("T-24h", timedelta(hours=24)), ("T-1h", timedelta(hours=1))]:
            req_dt = ct_dt - delta
            req_str = _to_z(req_dt)
            pq = out_dir / f"{eid}_{label}.parquet"
            plan.append((eid, ct, label, req_str, pq))
    return plan


def _pull_one_deriv(eid, req_str, pq_path):
    gz_path = pq_path.with_suffix(".json.gz")
    if pq_path.exists():
        return True, 0
    if not _budget_ok(DERIV_COST):
        return False, 0
    result = _request_with_backoff(
        f"{BASE}/historical/sports/icehockey_nhl/events/{eid}/odds",
        {"apiKey": KEY, "bookmakers": BOOKS, "markets": DERIV_MARKETS,
         "oddsFormat": "american", "date": req_str})
    if result is None:
        return False, 0
    r, used, remaining = result
    pq_path.parent.mkdir(parents=True, exist_ok=True)
    if r.status_code == 200:
        data = r.json()
        rows = flatten_event_response(data, req_str)
        if rows:
            pd.DataFrame(rows).to_parquet(pq_path, index=False)
        else:
            # Empty result — write empty marker
            pd.DataFrame(columns=["snapshot_utc", "requested_utc", "event_id", "commence_time",
                                   "home_team", "away_team", "bookmaker", "book_last_update",
                                   "market", "outcome_name", "description", "point", "price"]
                         ).to_parquet(pq_path, index=False)
        with gzip.open(gz_path, "wt") as f:
            json.dump(data, f)
    else:
        # Non-200: write empty marker so we don't retry
        pd.DataFrame(columns=["snapshot_utc"]).to_parquet(pq_path, index=False)
    return True, used


def cmd_deriv(seasons, dry_run):
    for season in seasons:
        plan = deriv_plan(season)
        todo = [(eid, ct, lbl, req, pq) for eid, ct, lbl, req, pq in plan if not pq.exists()]
        skip = len(plan) - len(todo)
        est = len(todo) * DERIV_COST
        print(f"\n  DERIV season {season}: {len(plan)//2} events, {len(plan)} snapshots, "
              f"{skip} done, {len(todo)} to pull, est {est:,} credits")
        if dry_run or not todo:
            continue
        # First call verify
        if _call_count == 0 and todo:
            eid, ct, lbl, req, pq = todo[0]
            ok, used = _pull_one_deriv(eid, req, pq)
            if used > 0 and used != DERIV_COST:
                print(f"  STOP: first call x-requests-last={used}, expected {DERIV_COST}")
                return
            if used == DERIV_COST:
                print(f"  First call OK: x-requests-last={DERIV_COST}")
            todo = [(e, c, l, r, p) for e, c, l, r, p in todo if not p.exists()]
        cc, cu, rem, rate = _status()
        if rate > 0 and todo:
            secs = len(todo) / (rate * 4)
            finish = datetime.now(timezone.utc) + timedelta(seconds=secs)
            print(f"  Rate: {rate:.2f} calls/s, projected finish: {finish.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {pool.submit(_pull_one_deriv, e, r, p): (e, r, p) for e, c, l, r, p in todo}
            done_count = 0
            for fut in as_completed(futs):
                ok, used = fut.result()
                done_count += 1
                if done_count % 200 == 0:
                    cc, cu, rem, rate = _status()
                    proj_remaining = len(todo) - done_count
                    proj_sec = proj_remaining / (rate * 4) if rate > 0 else 0
                    proj_finish = datetime.now(timezone.utc) + timedelta(seconds=proj_sec)
                    print(f"  [{done_count}/{len(todo)}] credits_used={cu:,} remaining={rem:,} "
                          f"rate={rate:.2f}/s proj_finish={proj_finish.strftime('%H:%M:%SZ')}")
                if _stopped:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
        cc, cu, rem, rate = _status()
        print(f"  Season {season} done: credits_used={cu:,}, remaining={rem:,}")
        if _stopped:
            break


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 3: PROPS (E6)
# ═══════════════════════════════════════════════════════════════════════════

PROP_MARKETS = "player_points,player_assists,player_shots_on_goal,player_goal_scorer_anytime,player_total_saves,player_blocked_shots"
PROP_N_MARKETS = 6
PROP_COST = 10 * PROP_N_MARKETS  # 60


def props_plan(season):
    events = event_ids_from_lines(season)
    out_dir = HIST_BASE / "props" / f"season={season}"
    plan = []
    for eid, ct in events:
        try:
            ct_dt = _parse_utc(ct)
        except (ValueError, TypeError):
            continue
        for label, delta in [("T-24h", timedelta(hours=24)), ("T-1h", timedelta(hours=1))]:
            req_dt = ct_dt - delta
            req_str = _to_z(req_dt)
            pq = out_dir / f"{eid}_{label}.parquet"
            plan.append((eid, ct, label, req_str, pq))
    return plan


def _pull_one_props(eid, req_str, pq_path):
    gz_path = pq_path.with_suffix(".json.gz")
    if pq_path.exists():
        return True, 0
    if not _budget_ok(PROP_COST):
        return False, 0
    result = _request_with_backoff(
        f"{BASE}/historical/sports/icehockey_nhl/events/{eid}/odds",
        {"apiKey": KEY, "bookmakers": BOOKS, "markets": PROP_MARKETS,
         "oddsFormat": "american", "date": req_str})
    if result is None:
        return False, 0
    r, used, remaining = result
    pq_path.parent.mkdir(parents=True, exist_ok=True)
    if r.status_code == 200:
        data = r.json()
        rows = flatten_event_response(data, req_str)
        if rows:
            pd.DataFrame(rows).to_parquet(pq_path, index=False)
        else:
            pd.DataFrame(columns=["snapshot_utc"]).to_parquet(pq_path, index=False)
        with gzip.open(gz_path, "wt") as f:
            json.dump(data, f)
    else:
        pd.DataFrame(columns=["snapshot_utc"]).to_parquet(pq_path, index=False)
    return True, used


def cmd_props(seasons, dry_run):
    for season in seasons:
        plan = props_plan(season)
        todo = [(eid, ct, lbl, req, pq) for eid, ct, lbl, req, pq in plan if not pq.exists()]
        skip = len(plan) - len(todo)
        est = len(todo) * PROP_COST
        print(f"\n  PROPS season {season}: {len(plan)//2} events, {len(plan)} snapshots, "
              f"{skip} done, {len(todo)} to pull, est {est:,} credits")
        if dry_run or not todo:
            continue
        if _call_count == 0 and todo:
            eid, ct, lbl, req, pq = todo[0]
            ok, used = _pull_one_props(eid, req, pq)
            if used > 0 and used != PROP_COST:
                print(f"  STOP: first call x-requests-last={used}, expected {PROP_COST}")
                return
            if used == PROP_COST:
                print(f"  First call OK: x-requests-last={PROP_COST}")
            todo = [(e, c, l, r, p) for e, c, l, r, p in todo if not p.exists()]
        cc, cu, rem, rate = _status()
        if rate > 0 and todo:
            secs = len(todo) / (rate * 4)
            finish = datetime.now(timezone.utc) + timedelta(seconds=secs)
            print(f"  Rate: {rate:.2f} calls/s, projected finish: {finish.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {pool.submit(_pull_one_props, e, r, p): (e, r, p) for e, c, l, r, p in todo}
            done_count = 0
            for fut in as_completed(futs):
                ok, used = fut.result()
                done_count += 1
                if done_count % 200 == 0:
                    cc, cu, rem, rate = _status()
                    print(f"  [{done_count}/{len(todo)}] credits_used={cu:,} remaining={rem:,} rate={rate:.2f}/s")
                if _stopped:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
        cc, cu, rem, rate = _status()
        print(f"  Season {season} done: credits_used={cu:,}, remaining={rem:,}")
        if _stopped:
            break


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 4: DENSE PRE-MATCH (E7)
# ═══════════════════════════════════════════════════════════════════════════

DENSE_COST = 30  # h2h,spreads,totals


def dense_plan(season):
    start, end = SEASONS_DATES[season]
    out_dir = HIST_BASE / "lines_hourly" / f"season={season}"
    plan = []
    d = start
    while d <= end:
        for hour in range(24):
            dt = datetime(d.year, d.month, d.day, hour, 0, tzinfo=timezone.utc)
            req_str = _to_z(dt)
            pq = out_dir / f"snap_{dt.strftime('%Y%m%dT%H%M%SZ')}.parquet"
            plan.append((req_str, pq))
        d += timedelta(days=1)
    return plan


def _pull_one_dense(req_str, pq_path):
    gz_path = pq_path.with_suffix(".json.gz")
    if pq_path.exists():
        return True, 0
    if not _budget_ok(DENSE_COST):
        return False, 0
    result = _request_with_backoff(
        f"{BASE}/historical/sports/icehockey_nhl/odds",
        {"apiKey": KEY, "bookmakers": BOOKS, "markets": "h2h,spreads,totals",
         "oddsFormat": "american", "date": req_str})
    if result is None:
        return False, 0
    r, used, remaining = result
    pq_path.parent.mkdir(parents=True, exist_ok=True)
    if r.status_code == 200:
        data = r.json()
        rows, snap_utc = flatten_snapshot_inplay(data, req_str)  # same schema
        if rows:
            pd.DataFrame(rows).to_parquet(pq_path, index=False)
        else:
            pd.DataFrame(columns=["snapshot_utc"]).to_parquet(pq_path, index=False)
        with gzip.open(gz_path, "wt") as f:
            json.dump(data, f)
    else:
        pd.DataFrame(columns=["snapshot_utc"]).to_parquet(pq_path, index=False)
    return True, used


def cmd_dense(seasons, dry_run):
    for season in seasons:
        plan = dense_plan(season)
        todo = [(r, p) for r, p in plan if not p.exists()]
        skip = len(plan) - len(todo)
        est = len(todo) * DENSE_COST
        n_days = (SEASONS_DATES[season][1] - SEASONS_DATES[season][0]).days + 1
        print(f"\n  DENSE season {season}: {n_days} days, {len(plan)} snapshots, "
              f"{skip} done, {len(todo)} to pull, est {est:,} credits")
        if dry_run or not todo:
            continue
        if _call_count == 0 and todo:
            req, pq = todo[0]
            ok, used = _pull_one_dense(req, pq)
            if used > 0 and used != DENSE_COST:
                print(f"  STOP: first call x-requests-last={used}, expected {DENSE_COST}")
                return
            if used == DENSE_COST:
                print(f"  First call OK: x-requests-last={DENSE_COST}")
            todo = [(r, p) for r, p in todo if not p.exists()]
        cc, cu, rem, rate = _status()
        if rate > 0 and todo:
            secs = len(todo) / (rate * 4)
            finish = datetime.now(timezone.utc) + timedelta(seconds=secs)
            print(f"  Rate: {rate:.2f} calls/s, projected finish: {finish.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {pool.submit(_pull_one_dense, r, p): (r, p) for r, p in todo}
            done_count = 0
            for fut in as_completed(futs):
                ok, used = fut.result()
                done_count += 1
                if done_count % 200 == 0:
                    cc, cu, rem, rate = _status()
                    print(f"  [{done_count}/{len(todo)}] credits_used={cu:,} remaining={rem:,} rate={rate:.2f}/s")
                if _stopped:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
        cc, cu, rem, rate = _status()
        print(f"  Season {season} done: credits_used={cu:,}, remaining={rem:,}")
        if _stopped:
            break


def main():
    print(f"key fingerprint: {KEY_FP}")
    print(f"books: {BOOKS} ({N_BOOKS} keys)")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inplay", "deriv", "props", "dense"])
    ap.add_argument("--season", default=None, help="comma-separated start years in priority order")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not KEY and not args.dry_run:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    default_seasons = {
        "inplay": [2024, 2025, 2023, 2022],
        "deriv":  [2024, 2025, 2023],
        "props":  [2024, 2025, 2023],
        "dense":  [2024, 2025, 2023, 2022],
    }
    seasons = [int(s) for s in args.season.split(",")] if args.season else default_seasons[args.cmd]
    print(f"command: {args.cmd}, seasons: {seasons}")
    print(f"SPEND_CAP: {SPEND_CAP:,}, GLOBAL_FLOOR: {GLOBAL_FLOOR:,}")

    # Print remaining before first call
    if not args.dry_run:
        r = requests.get(f"{BASE}/sports", params={"apiKey": KEY}, timeout=30)
        rem = int(r.headers.get("x-requests-remaining", "0"))
        print(f"\nx-requests-remaining BEFORE first call: {rem:,}")
        global _remaining
        _remaining = rem

    if args.cmd == "inplay":
        cmd_inplay(seasons, args.dry_run)
    elif args.cmd == "deriv":
        cmd_deriv(seasons, args.dry_run)
    elif args.cmd == "props":
        cmd_props(seasons, args.dry_run)
    elif args.cmd == "dense":
        cmd_dense(seasons, args.dry_run)

    cc, cu, rem, rate = _status()
    print(f"\n{'='*60}")
    print(f"FINAL: {cc} calls, {cu:,} credits used, {rem:,} remaining, {rate:.2f} calls/s")
    if _stopped:
        reason = "GLOBAL FLOOR" if rem < GLOBAL_FLOOR else "SPEND CAP"
        print(f"STOPPED: {reason}")


if __name__ == "__main__":
    main()
