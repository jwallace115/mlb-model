#!/usr/bin/env python3
"""
NBA WO1 Item 1: probe every NBA data source from this host.

Sections:
  a) Odds API — active basketball_nba* keys, events, dry-run capture
  b) Official injury report — HEAD probe for 4 dates, both URL formats
  c) ESPN injuries + scoreboard
  d) stats.nba.com via nba_api

Run on BOTH Mac and VM; compare outputs.
"""
import hashlib, json, os, sys, time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(Path.home() / "mlb-model" / ".env", override=True)

KEY = os.getenv("ODDS_API_KEY", "")
KEY_FP = hashlib.sha256(KEY.strip().encode()).hexdigest()[:8] if KEY else "UNSET"
BASE = "https://api.the-odds-api.com/v4"

PROBE_DATES = [
    date(2025, 10, 10),  # preseason
    date(2025, 12, 25),  # Christmas (early tips)
    date(2026, 1, 14),   # mid-season
    date(2026, 3, 16),   # late season
]


def section_a():
    """Odds API: active NBA keys, events, dry-run capture."""
    print("=" * 60)
    print("SECTION A: Odds API")
    print("=" * 60)

    # 1. All sports containing basketball_nba
    r = requests.get(f"{BASE}/sports", params={"apiKey": KEY, "all": "true"}, timeout=30)
    rem_before = r.headers.get("x-requests-remaining", "?")
    print(f"\nx-requests-remaining (before): {rem_before}")

    nba_keys = []
    for s in r.json():
        if "basketball_nba" in s.get("key", ""):
            nba_keys.append(s)
            print(f"  key={s['key']}  active={s.get('active')}  title={s.get('title')}")

    if not nba_keys:
        print("  NO basketball_nba keys found")
        return

    # 2. Events per active key
    for s in nba_keys:
        sk = s["key"]
        if not s.get("active"):
            print(f"\n  {sk}: inactive, skipping events")
            continue
        r2 = requests.get(f"{BASE}/sports/{sk}/events",
                          params={"apiKey": KEY}, timeout=30)
        events = r2.json() if r2.status_code == 200 else []
        if events:
            ct = [e.get("commence_time", "") for e in events]
            ct_sorted = sorted(ct)
            print(f"\n  {sk}: {len(events)} events, "
                  f"first={ct_sorted[0]}, last={ct_sorted[-1]}")
        else:
            print(f"\n  {sk}: 0 events — not posted as of {datetime.now(timezone.utc).isoformat()}")

    # 3. Dry-run capture for each key with events
    for s in nba_keys:
        sk = s["key"]
        if not s.get("active"):
            continue
        # Check events exist
        r2 = requests.get(f"{BASE}/sports/{sk}/events",
                          params={"apiKey": KEY}, timeout=30)
        events = r2.json() if r2.status_code == 200 else []
        if not events:
            print(f"\n  {sk}: 0 events, skipping dry-run")
            continue

        print(f"\n  DRY-RUN capture for {sk}:")
        # Record git status before
        import subprocess
        gs_before = subprocess.run(["git", "status", "--porcelain", "data/odds_archive"],
                                   capture_output=True, text=True, cwd=ROOT).stdout

        # Run capture script with --dry-run
        result = subprocess.run(
            [sys.executable, str(ROOT / "shared" / "pipeline" / "multi_book_open_capture.py"),
             "--sports", sk, "--dry-run"],
            capture_output=True, text=True, timeout=120, cwd=ROOT)
        print(f"  stdout (last 20 lines):")
        for line in result.stdout.strip().split("\n")[-20:]:
            print(f"    {line}")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[-10:]:
                print(f"    [err] {line}")

        # Record git status after
        gs_after = subprocess.run(["git", "status", "--porcelain", "data/odds_archive"],
                                  capture_output=True, text=True, cwd=ROOT).stdout
        # Check basketball_nba dir not created
        bball_dir = ROOT / "data" / "odds_archive" / "basketball_nba"
        print(f"\n  NULL CONTROL: git status data/odds_archive unchanged = {gs_before == gs_after}")
        print(f"  data/odds_archive/basketball_nba* exists = {bball_dir.exists()}")

        # Parse books from output
        for line in result.stdout.split("\n"):
            if "credits this call" in line.lower() or "x-requests" in line.lower():
                print(f"  >> {line.strip()}")
            if "books" in line.lower() or "pinnacle" in line.lower() or "hardrock" in line.lower():
                print(f"  >> {line.strip()}")

    r_after = requests.get(f"{BASE}/sports", params={"apiKey": KEY}, timeout=30)
    rem_after = r_after.headers.get("x-requests-remaining", "?")
    print(f"\nx-requests-remaining (after): {rem_after}")


def section_b():
    """Official injury report HEAD probe."""
    print("\n" + "=" * 60)
    print("SECTION B: Official NBA injury reports")
    print("=" * 60)

    CDN = "https://ak-static.cms.nba.com/referee/injury"
    FIXTURE_DIR = ROOT / "data" / "injury_archive" / "nba" / "season=2026" / "fixtures"
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    for probe_date in PROBE_DATES:
        print(f"\n--- {probe_date} ---")
        found = []
        ds = probe_date.strftime("%Y-%m-%d")

        # Quarter-hour slots 10:00-23:45 ET
        for hour in range(10, 24):
            for minute in (0, 15, 30, 45):
                ampm = "AM" if hour < 12 else "PM"
                h12 = hour if hour <= 12 else hour - 12
                if h12 == 0:
                    h12 = 12

                # Legacy format: Injury-Report_2025-10-10_05PM.pdf
                legacy_tag = f"{h12:02d}{ampm}"
                legacy_url = f"{CDN}/Injury-Report_{ds}_{legacy_tag}.pdf"

                # New format: Injury-Report_2025-10-10_17_00PM.pdf
                new_tag = f"{hour:02d}_{minute:02d}{ampm}"
                new_url = f"{CDN}/Injury-Report_{ds}_{new_tag}.pdf"

                for label, url in [("legacy", legacy_url), ("new", new_url)]:
                    try:
                        resp = requests.head(url, timeout=10, allow_redirects=True)
                        if resp.status_code == 200:
                            found.append({
                                "hour_et": f"{hour:02d}:{minute:02d}",
                                "format": label,
                                "url": url,
                                "status": 200,
                            })
                    except requests.RequestException:
                        pass
                    time.sleep(0.5)

        if found:
            print(f"  Found {len(found)} reports:")
            for f in found:
                print(f"    {f['hour_et']} ET  [{f['format']}]  {f['url']}")

            # Check 5:30pm
            has_530 = any(f["hour_et"] == "17:30" for f in found)
            print(f"  5:30pm ET report exists: {has_530}")

            # Latest report
            latest = found[-1]
            print(f"  Latest: {latest['hour_et']} ET")

            # Download ONE existing PDF as fixture
            dl_url = found[-1]["url"]
            fname = dl_url.split("/")[-1]
            out_path = FIXTURE_DIR / fname
            if not out_path.exists():
                r = requests.get(dl_url, timeout=30)
                if r.status_code == 200 and len(r.content) < 2 * 1024 * 1024:
                    out_path.write_bytes(r.content)
                    sha = hashlib.sha256(r.content).hexdigest()[:16]
                    print(f"  Downloaded: {fname} ({len(r.content)} bytes, sha256={sha})")
                else:
                    print(f"  Download failed or too large: {r.status_code}, {len(r.content)} bytes")
        else:
            print(f"  No reports found for {probe_date}")

    # Try nbainjuries gen_url
    print("\n--- nbainjuries package ---")
    try:
        from nbainjuries import injury as nba_injury
        test_dt = datetime(2026, 3, 16, 17, 0)
        url = nba_injury.gen_url(test_dt)
        print(f"  gen_url(2026-03-16 17:00) = {url}")
        print(f"  nbainjuries available: True")
    except ImportError:
        print(f"  nbainjuries not installed")
    except Exception as e:
        print(f"  nbainjuries error: {e}")

    # Try parsing a fixture PDF
    print("\n--- PDF parsing ---")
    fixtures = list(FIXTURE_DIR.glob("*.pdf"))
    if fixtures:
        try:
            from nbainjuries import injury as nba_injury
            df = nba_injury.get_reportdata(
                fixtures[0].stem.split("_")[2],  # date part
                local=True,
                localdir=str(FIXTURE_DIR),
                return_df=True
            )
            print(f"  Parsed {fixtures[0].name}: {len(df)} rows")
            print(f"  Columns: {list(df.columns)}")
            if len(df) > 0:
                print(f"  Statuses: {df['Current Status'].value_counts().to_dict()}")
        except Exception as e:
            print(f"  Parse failed (likely needs Java): {type(e).__name__}: {e}")
    else:
        print(f"  No fixture PDFs to parse")


def section_c():
    """ESPN injuries + scoreboard."""
    print("\n" + "=" * 60)
    print("SECTION C: ESPN")
    print("=" * 60)

    # Injuries
    print("\n--- ESPN Injuries ---")
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        r = requests.get(url, timeout=15)
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            # Field list of one item
            if data:
                first_team = data[0] if isinstance(data, list) else None
                if first_team:
                    print(f"  Top-level keys: {list(first_team.keys())}")
                    injuries = first_team.get("injuries", [])
                    if injuries:
                        print(f"  Injury item keys: {list(injuries[0].keys())}")
                        # Check for per-item date/time
                        sample = injuries[0]
                        has_date = any(k for k in sample.keys() if "date" in k.lower() or "time" in k.lower())
                        print(f"  Per-item date/time field: {has_date}")
                        if has_date:
                            date_keys = [k for k in sample.keys() if "date" in k.lower() or "time" in k.lower()]
                            print(f"    Date keys: {date_keys}")
                            for dk in date_keys:
                                print(f"    {dk} = {sample[dk]}")

                # Status counts
                status_counts = {}
                total_items = 0
                for team_data in (data if isinstance(data, list) else []):
                    for inj in team_data.get("injuries", []):
                        status = inj.get("status", "unknown")
                        status_counts[status] = status_counts.get(status, 0) + 1
                        total_items += 1
                print(f"\n  Total injury items: {total_items}")
                print(f"  Status counts: {json.dumps(status_counts, indent=4)}")
    except Exception as e:
        print(f"  ESPN injuries FAILED: {e}")

    # Scoreboard
    print("\n--- ESPN Scoreboard (2026-03-16) ---")
    url2 = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260316"
    try:
        r2 = requests.get(url2, timeout=15)
        print(f"  HTTP {r2.status_code}")
        if r2.status_code == 200:
            sb = r2.json()
            events = sb.get("events", [])
            print(f"  Games: {len(events)}")
            for ev in events[:3]:
                comp = ev.get("competitions", [{}])[0]
                status = comp.get("status", {}).get("type", {}).get("name", "?")
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    t1 = competitors[0]
                    t2 = competitors[1]
                    s1 = t1.get("score", "?")
                    s2 = t2.get("score", "?")
                    n1 = t1.get("team", {}).get("displayName", "?")
                    n2 = t2.get("team", {}).get("displayName", "?")
                    periods = len(comp.get("status", {}).get("period", 0).__class__.__mro__)
                    # Get period from status
                    period = comp.get("status", {}).get("period", "?")
                    print(f"    {n1} {s1} - {n2} {s2}  status={status}  periods={period}")
            if events:
                # Show full structure of first game
                ev0 = events[0]
                comp0 = ev0.get("competitions", [{}])[0]
                print(f"\n  Game structure keys: {list(ev0.keys())}")
                print(f"  Competition keys: {list(comp0.keys())}")
                print(f"  Status keys: {list(comp0.get('status', {}).keys())}")
    except Exception as e:
        print(f"  ESPN scoreboard FAILED: {e}")


def section_d():
    """stats.nba.com via nba_api."""
    print("\n" + "=" * 60)
    print("SECTION D: stats.nba.com (nba_api)")
    print("=" * 60)

    try:
        from nba_api.stats.endpoints import scoreboardv2
        sb = scoreboardv2.ScoreboardV2(game_date="03/16/2026")
        games = sb.get_data_frames()[0]
        print(f"  nba_api scoreboardv2 for 2026-03-16: {len(games)} games")
        if len(games) > 0:
            print(f"  Columns: {list(games.columns)}")
            print(f"  Sample: {games[['GAME_DATE_EST','HOME_TEAM_ID','VISITOR_TEAM_ID']].head(2).to_string()}")
        print(f"  Reachable from this host: True")
    except Exception as e:
        print(f"  nba_api FAILED: {type(e).__name__}: {e}")
        print(f"  Reachable from this host: False")


def main():
    import platform
    print(f"Host: {platform.node()}")
    print(f"Key fingerprint: {KEY_FP}")
    print(f"UTC: {datetime.now(timezone.utc).isoformat()}")

    section_a()
    section_b()
    section_c()
    section_d()


if __name__ == "__main__":
    main()
