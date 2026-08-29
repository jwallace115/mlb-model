#!/usr/bin/env python3
"""
MULTI-BOOK OPEN CAPTURE — the foundation for getting in early.

WHY
---
Everything measured in the 2026-08-28 assessment says the edge is in the NUMBER,
not the side, and that it is ~4.6x larger at the open than at the close:

    cross-book dispersion   1.213 pts at open   vs 0.711 at close
    value of best number   +0.96pp at open      vs +0.21pp at close
    key-number straddles    11.60% at open      vs  7.71% at close

None of that is capturable with one book, and none of it exists in the repo today —
every football odds asset is a single closing snapshot ~5 min before kickoff.
This script starts the tape that makes the finding actionable.

DESIGN
------
* Uses the `bookmakers` parameter, NOT `regions`. Every 10 bookmakers = 1 region
  equivalent, so naming 10 specific books costs the same as one region — and it is
  the only way to reach hardrockbet_fl, which lives in us2 and which every pull in
  this repo has silently missed by requesting regions="us".
* Append-only. Never rewrites a prior snapshot. The tape is the asset.
* Records the snapshot timestamp on every row so any later analysis is PIT-safe
  by construction.

COST
----
3 markets x 1 region-equivalent = 3 credits per sport per call.
Two calls/day x two sports = 12 credits/day ~= 360/month. Negligible.

    python3 shared/pipeline/multi_book_open_capture.py
    python3 shared/pipeline/multi_book_open_capture.py --sports americanfootball_nfl
    python3 shared/pipeline/multi_book_open_capture.py --dry-run
"""

import argparse, json, logging, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv
# override=True: .env is authoritative. Without it python-dotenv silently defers
# to any ODDS_API_KEY already exported in the shell, so a stale key wins and the
# run looks fine while using the wrong account.
load_dotenv(ROOT / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("open_capture")

KEY  = os.getenv("ODDS_API_KEY", "")
_KEY_FP = __import__("hashlib").sha256(KEY.strip().encode()).hexdigest()[:8] if KEY else "UNSET"

BASE = "https://api.the-odds-api.com/v4"

# baseball_mlb added 2026-08-28: it is the only sport with BOTH liquid Kalshi game
# markets and the Tier-1 re-scored signals, so the cross-venue test depends on it.
SPORTS  = ["baseball_mlb", "americanfootball_nfl", "americanfootball_ncaaf"]
MARKETS = ["h2h", "spreads", "totals"]

# Exactly 10 books = 1 region equivalent. hardrockbet_fl is the whole point: it is
# the only book Jeff can bet legally and it has never appeared in any capture.
# pinnacle is the CLV benchmark and may sit outside the us region — the bookmakers
# parameter reaches it regardless. The script reports which books actually returned.
BOOKS = ["hardrockbet_fl", "pinnacle", "draftkings", "fanduel", "betmgm",
         "betonlineag", "bovada", "betrivers", "williamhill_us", "lowvig"]

OUT_ROOT = ROOT / "data" / "odds_archive"


def _scrub(text):
    """Never let the API key reach a log file. requests embeds the full URL —
    including apiKey — in its exception text, and this script runs on a cron
    writing to disk in a public repo."""
    t = str(text)
    if KEY:
        t = t.replace(KEY, "<APIKEY-REDACTED>")
    return re.sub(r"(apiKey=)[^&\s'\"]+", r"\1<APIKEY-REDACTED>", t)


def pull(sport):
    p = {"apiKey": KEY, "markets": ",".join(MARKETS),
         "bookmakers": ",".join(BOOKS), "oddsFormat": "american"}
    try:
        r = requests.get(f"{BASE}/sports/{sport}/odds/", params=p, timeout=45)
    except requests.RequestException as e:
        log.error(f"HARD STOP: network error on {sport}: {type(e).__name__}: {_scrub(e)}")
        log.error("Nothing written. Safe to re-run."); sys.exit(1)
    if r.status_code != 200:
        log.error(f"HARD STOP: {sport} -> HTTP {r.status_code}: {_scrub(r.text[:250])}")
        sys.exit(1)
    used = r.headers.get("x-requests-last")
    rem  = r.headers.get("x-requests-remaining")
    return r.json(), used, rem


def flatten(games, sport, snap_iso):
    rows = []
    for g in games:
        for b in g.get("bookmakers", []):
            for m in b.get("markets", []):
                for oc in m.get("outcomes", []):
                    rows.append({
                        "snapshot_utc": snap_iso,
                        "sport": sport,
                        "event_id": g.get("id"),
                        "commence_time": g.get("commence_time"),
                        "home_team": g.get("home_team"),
                        "away_team": g.get("away_team"),
                        "bookmaker": b.get("key"),
                        "book_last_update": b.get("last_update"),
                        "market": m.get("key"),
                        "outcome_name": oc.get("name"),
                        "point": oc.get("point"),
                        "price": oc.get("price"),
                    })
    return pd.DataFrame(rows)


def main():
    log.info(f"key fingerprint {_KEY_FP} (sha256[:8]) — compare against .env if quota looks wrong")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", nargs="*", default=SPORTS)
    ap.add_argument("--dry-run", action="store_true", help="pull and report, write nothing")
    a = ap.parse_args()

    if not KEY:
        log.error("HARD STOP: ODDS_API_KEY not set in .env (the key lapsed — reactivate first)")
        sys.exit(1)

    snap = datetime.now(timezone.utc)
    snap_iso = snap.isoformat()
    total_rows = 0

    for sport in a.sports:
        games, used, rem = pull(sport)
        log.info(f"{sport}: {len(games)} games | credits this call: {used} | remaining: {rem}")
        if not games:
            log.warning(f"  {sport}: no games returned (off-season or no upcoming card)")
            continue

        df = flatten(games, sport, snap_iso)
        if df.empty:
            log.warning(f"  {sport}: no odds rows"); continue

        got = sorted(df["bookmaker"].unique())
        missing = [b for b in BOOKS if b not in got]
        log.info(f"  books returned ({len(got)}): {', '.join(got)}")
        if missing:
            log.warning(f"  books NOT returned: {', '.join(missing)}")
        if "hardrockbet_fl" in got:
            n_hr = df[df["bookmaker"] == "hardrockbet_fl"]["event_id"].nunique()
            log.info(f"  *** hardrockbet_fl PRESENT on {n_hr} games ***")
        else:
            # If Hard Rock returned on ANY sport this run, us2 access is proven and an
            # absence here is coverage timing (they post close to game week), not creds.
            log.warning("   *** hardrockbet_fl ABSENT on this sport — coverage, not credentials, if it appeared on another sport this run ***")

        # dispersion right now, so you can see the edge as it is captured
        for mk in ("spreads", "totals"):
            s = df[(df["market"] == mk) & df["point"].notna()]
            if s.empty: continue
            g = s.groupby(["event_id", "outcome_name"])["point"].agg(["min", "max", "nunique"])
            g = g[g["nunique"] >= 3]
            if len(g):
                d = (g["max"] - g["min"])
                log.info(f"  {mk}: median cross-book spread {d.median():.2f} pts, "
                         f"p90 {d.quantile(.9):.2f}, {(d >= 1).mean():.0%} of sides >= 1 pt apart")

        if a.dry_run:
            log.info("  DRY RUN — nothing written"); continue

        season = snap.year if snap.month >= 3 else snap.year - 1
        out = OUT_ROOT / sport.replace("americanfootball_", "") / "line_history" / f"season={season}"
        out.mkdir(parents=True, exist_ok=True)
        f = out / f"snap_{snap.strftime('%Y%m%dT%H%M%SZ')}.parquet"
        df.to_parquet(f)
        total_rows += len(df)
        log.info(f"  wrote {len(df):,} rows -> {f}")

    if not a.dry_run:
        log.info(f"\ntotal rows captured this run: {total_rows:,}")
        log.info("APPEND-ONLY: this snapshot is now part of the tape. Never overwrite it.")
        log.info("Run 2x/day. The open is ~5-6 days before kickoff — that is where the edge is.")


if __name__ == "__main__":
    main()
