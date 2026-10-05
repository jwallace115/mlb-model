#!/usr/bin/env python3
"""
NBA WO1 Item 2: capture NBA availability (L2) — point-in-time, append-only.

Each run writes into data/injury_archive/nba/season=2026/:
  - Official NBA injury report PDFs (all published since last run) + parsed parquet
  - ESPN injuries JSON (gzip, all statuses), skipped if content hash unchanged
  - One line per feed in _pulls.jsonl

Host decisions from B2:
  - Official reports: Mac only (CDN blocks VM)
  - ESPN: VM (both work)

Does NOT import or change nba/modules/fetch_injuries.py or nba/run_nba.py.
"""
import gzip, hashlib, json, os, sys, time
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

SEASON_DIR = ROOT / "data" / "injury_archive" / "nba" / "season=2026"
PULLS_LOG = SEASON_DIR / "_pulls.jsonl"
CDN = "https://ak-static.cms.nba.com/referee/injury"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def _utcnow():
    return datetime.now(timezone.utc)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _log_pull(feed, url, rows, sha, status, retrieval_utc=None):
    """Append one line to _pulls.jsonl."""
    SEASON_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "feed": feed,
        "retrieval_utc": (retrieval_utc or _utcnow()).isoformat(),
        "source_url": url,
        "rows": rows,
        "sha256": sha,
        "status": status,
    }
    with open(PULLS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _last_sha(feed):
    """Read the last sha256 for a given feed from _pulls.jsonl."""
    if not PULLS_LOG.exists():
        return None
    last = None
    for line in PULLS_LOG.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("feed") == feed and entry.get("status") == "ok":
                last = entry.get("sha256")
        except json.JSONDecodeError:
            pass
    return last


# ─── Official injury reports ──────────────────────────────────────────

def official_report_url(d, hour24, minute):
    """Build the CDN URL for an official NBA injury report.

    Uses 12-hour format: 13:00 -> _01_00PM, 17:30 -> _05_30PM, 12:45 -> _12_45PM.
    """
    ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
    ampm = "AM" if hour24 < 12 else "PM"
    h12 = hour24 % 12
    if h12 == 0:
        h12 = 12
    tag = f"{h12:02d}_{minute:02d}{ampm}"
    return f"{CDN}/Injury-Report_{ds}_{tag}.pdf"


def _report_urls_for_now():
    """Generate report URLs for today, every q15 from 10:00 ET through
    the day's last tip (from ESPN scoreboard), or 23:45 as fallback."""
    from zoneinfo import ZoneInfo
    now_et = _utcnow().astimezone(ZoneInfo("America/New_York"))
    today = now_et.date()

    # Determine end hour: try ESPN scoreboard for today's last tip
    last_hour_et = 23  # fallback: poll through 23:45
    try:
        ds_espn = today.strftime("%Y%m%d")
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={ds_espn}",
            timeout=10)
        if r.status_code == 200:
            events = r.json().get("events", [])
            if events:
                from zoneinfo import ZoneInfo as ZI
                tip_hours = []
                for ev in events:
                    tip_str = ev.get("date", "")
                    if tip_str:
                        from datetime import datetime as DT
                        tip_utc = DT.fromisoformat(tip_str.replace("Z", "+00:00"))
                        tip_et = tip_utc.astimezone(ZI("America/New_York"))
                        tip_hours.append(tip_et.hour)
                if tip_hours:
                    last_hour_et = max(tip_hours)
    except Exception:
        pass

    urls = []
    for hour in range(10, last_hour_et + 1):
        for minute in (0, 15, 30, 45):
            ds = today.strftime("%Y-%m-%d")
            url = official_report_url(today, hour, minute)
            urls.append((url, ds, f"{hour:02d}:{minute:02d}"))
    return urls


def _existing_pdfs():
    """Set of PDF filenames already archived."""
    pdf_dir = SEASON_DIR / "reports"
    if not pdf_dir.exists():
        return set()
    return {p.name for p in pdf_dir.glob("*.pdf")}


def capture_official_reports():
    """Fetch all new official injury report PDFs published since last run."""
    retrieval_utc = _utcnow()
    urls = _report_urls_for_now()
    existing = _existing_pdfs()
    pdf_dir = SEASON_DIR / "reports"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    fetched = 0
    for url, ds, time_et in urls:
        fname = url.split("/")[-1]
        if fname in existing:
            continue
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            if r.status_code != 200:
                continue
            # Download
            r2 = requests.get(url, timeout=30)
            if r2.status_code != 200:
                continue
            pdf_bytes = r2.content
            sha = _sha256(pdf_bytes)

            # Save PDF
            out_pdf = pdf_dir / fname
            out_pdf.write_bytes(pdf_bytes)
            fetched += 1

            # Parse to parquet
            parsed_rows = _parse_report(out_pdf, ds, time_et)
            if parsed_rows is not None:
                import pandas as pd
                pq_path = pdf_dir / fname.replace(".pdf", ".parquet")
                pd.DataFrame(parsed_rows).to_parquet(pq_path, index=False)
                n_rows = len(parsed_rows)
            else:
                n_rows = 0

            _log_pull(
                feed="official_report",
                url=url,
                rows=n_rows,
                sha=sha,
                status="ok",
                retrieval_utc=retrieval_utc,
            )
            print(f"  fetched: {fname} ({len(pdf_bytes)} bytes, {n_rows} parsed rows)")
        except Exception as e:
            print(f"  error on {fname}: {e}")
            _log_pull(feed="official_report", url=url, rows=0, sha="", status=f"error: {e}",
                      retrieval_utc=retrieval_utc)
        time.sleep(0.5)

    if fetched == 0:
        print("  no new official reports")
    return fetched


def _parse_report(pdf_path, date_str, time_et):
    """Parse an official injury report PDF. Returns list of dicts or None on failure."""
    try:
        os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
        from nbainjuries import injury as nba_injury
        df = nba_injury.get_reportdata(
            date_str,
            local=True,
            localdir=str(pdf_path.parent),
            return_df=True,
        )
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "report_date": date_str,
                "report_time_et": time_et,
                "report_timestamp": f"{date_str}T{time_et}:00",
                "game_date": str(r.get("Game Date", "")),
                "game_time": str(r.get("Game Time", "")),
                "matchup": str(r.get("Matchup", "")),
                "team": str(r.get("Team", "")),
                "player": str(r.get("Player Name", "")),
                "status": str(r.get("Current Status", "")),
                "reason": str(r.get("Reason", "")),
                "post_tip": False,  # computed downstream
            })
        return rows
    except Exception as e:
        print(f"  parse error ({pdf_path.name}): {e}")
        return None


# ─── ESPN injuries ────────────────────────────────────────────────────

def capture_espn_injuries():
    """Fetch ESPN injuries JSON. Skip if content hash unchanged."""
    retrieval_utc = _utcnow()
    try:
        r = requests.get(ESPN_URL, timeout=15)
        if r.status_code != 200:
            _log_pull("espn_injuries", ESPN_URL, 0, "", f"http_{r.status_code}",
                      retrieval_utc)
            print(f"  ESPN injuries: HTTP {r.status_code}")
            return 0
    except Exception as e:
        _log_pull("espn_injuries", ESPN_URL, 0, "", f"error: {e}", retrieval_utc)
        print(f"  ESPN injuries error: {e}")
        return 0

    raw = r.content
    sha = _sha256(raw)
    last_sha = _last_sha("espn_injuries")

    if sha == last_sha:
        print("  ESPN injuries: content unchanged, skipped")
        return 0

    # Save gzipped JSON
    espn_dir = SEASON_DIR / "espn"
    espn_dir.mkdir(parents=True, exist_ok=True)
    ts_tag = retrieval_utc.strftime("%Y%m%dT%H%M%SZ")
    gz_path = espn_dir / f"injuries_{ts_tag}.json.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(raw)

    # Count rows (all statuses kept)
    data = r.json()
    total_rows = 0
    teams_data = data.get("injuries", data if isinstance(data, list) else [])
    if isinstance(teams_data, list):
        for team in teams_data:
            total_rows += len(team.get("injuries", []))

    _log_pull("espn_injuries", ESPN_URL, total_rows, sha, "ok", retrieval_utc)
    print(f"  ESPN injuries: {total_rows} items -> {gz_path.name}")
    return total_rows


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    import platform
    print(f"Host: {platform.node()}")
    print(f"UTC: {_utcnow().isoformat()}")
    SEASON_DIR.mkdir(parents=True, exist_ok=True)

    print("\n--- Official reports ---")
    capture_official_reports()

    print("\n--- ESPN injuries ---")
    capture_espn_injuries()

    print("\nDone.")


if __name__ == "__main__":
    main()
