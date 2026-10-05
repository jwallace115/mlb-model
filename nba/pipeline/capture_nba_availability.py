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
            if entry.get("feed") == feed and entry.get("status") in ("ok", "unchanged"):
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
    """Fetch all new official injury report PDFs published since last run.

    Uses the B14 A7-standard parser (two independent parsers, consumed-set
    agreement, context binding). Non-ok parse status: PDF still archived,
    pull-log carries the status, function returns the status string.
    """
    from nba.pipeline.injury_report_parser import parse_report as a7_parse

    retrieval_utc = _utcnow()
    urls = _report_urls_for_now()
    existing = _existing_pdfs()
    pdf_dir = SEASON_DIR / "reports"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    fetched = 0
    non_ok_status = None  # track first non-ok for exit code
    for url, ds, time_et in urls:
        fname = url.split("/")[-1]
        if fname in existing:
            continue
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            if r.status_code != 200:
                continue
            r2 = requests.get(url, timeout=30)
            if r2.status_code != 200:
                continue
            pdf_bytes = r2.content
            sha = _sha256(pdf_bytes)

            # Always archive the raw PDF first
            out_pdf = pdf_dir / fname
            out_pdf.write_bytes(pdf_bytes)
            fetched += 1

            # A7 parse: two parsers, consumed-set agreement, context binding
            parsed_rows, published_utc, slot_et, status, detail = a7_parse(out_pdf)

            if status == "ok" or status == "verified_empty":
                import pandas as pd
                if parsed_rows:
                    # Add published_utc and slot_et to each row
                    for row in parsed_rows:
                        row["published_utc"] = published_utc.isoformat() if published_utc else ""
                        row["slot_et"] = slot_et or ""
                    pq_path = pdf_dir / fname.replace(".pdf", ".parquet")
                    pd.DataFrame(parsed_rows).to_parquet(pq_path, index=False)
                n_rows = len(parsed_rows)
            else:
                n_rows = 0
                non_ok_status = status

            _log_pull(
                feed="official_report",
                url=url,
                rows=n_rows,
                sha=sha,
                status=status,
                retrieval_utc=retrieval_utc,
            )
            print(f"  fetched: {fname} ({len(pdf_bytes)} bytes, {n_rows} rows, status={status})")
            if status not in ("ok", "verified_empty"):
                print(f"    detail: {detail}")
        except Exception as e:
            print(f"  error on {fname}: {e}")
            _log_pull(feed="official_report", url=url, rows=0, sha="", status=f"error: {e}",
                      retrieval_utc=retrieval_utc)
        time.sleep(0.5)

    if fetched == 0:
        print("  no new official reports")
    return fetched, non_ok_status


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
    data = json.loads(raw)

    # B15: hash canonical JSON with top-level "timestamp" removed, sorted keys.
    # This prevents false-negative dedup from the timestamp changing every response.
    canonical = {k: v for k, v in data.items() if k != "timestamp"}
    content_sha = _sha256(json.dumps(canonical, sort_keys=True).encode())
    last_sha = _last_sha("espn_injuries")

    if content_sha == last_sha:
        _log_pull("espn_injuries", ESPN_URL, 0, content_sha, "unchanged", retrieval_utc)
        print("  ESPN injuries: content unchanged, skipped")
        return 0

    # Save gzipped JSON
    espn_dir = SEASON_DIR / "espn"
    espn_dir.mkdir(parents=True, exist_ok=True)
    ts_tag = retrieval_utc.strftime("%Y%m%dT%H%M%SZ")
    gz_path = espn_dir / f"injuries_{ts_tag}.json.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(raw)

    # Count rows (all statuses kept) and write parsed parquet
    import re as _re
    total_rows = 0
    parsed = []
    teams_data = data.get("injuries", data if isinstance(data, list) else [])
    if isinstance(teams_data, list):
        for team in teams_data:
            team_id = str(team.get("id", ""))
            for inj in team.get("injuries", []):
                total_rows += 1
                ath = inj.get("athlete", {})
                # athlete_id: prefer athlete.id, fall back to /id/<n>/ in playercard link
                ath_id = ""
                if isinstance(ath, dict):
                    if ath.get("id"):
                        ath_id = str(ath["id"])
                    else:
                        for link in ath.get("links", []):
                            m = _re.search(r"/id/(\d+)/", link.get("href", ""))
                            if m:
                                ath_id = m.group(1)
                                break
                parsed.append({
                    "team_id": team_id,
                    "athlete_id": ath_id,
                    "athlete_id_source": "athlete.id" if (isinstance(ath, dict) and ath.get("id")) else "playercard_link",
                    "status": inj.get("status", ""),
                    "date_utc": inj.get("date", ""),
                    "retrieval_utc": retrieval_utc.isoformat(),
                })

    if parsed:
        import pandas as pd
        pq_path = espn_dir / f"injuries_{ts_tag}.parquet"
        pd.DataFrame(parsed).to_parquet(pq_path, index=False)

    _log_pull("espn_injuries", ESPN_URL, total_rows, content_sha, "ok", retrieval_utc)
    print(f"  ESPN injuries: {total_rows} items -> {gz_path.name}")
    return total_rows


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    import platform
    print(f"Host: {platform.node()}")
    print(f"UTC: {_utcnow().isoformat()}")
    SEASON_DIR.mkdir(parents=True, exist_ok=True)

    print("\n--- Official reports ---")
    fetched, non_ok_status = capture_official_reports()

    print("\n--- ESPN injuries ---")
    capture_espn_injuries()

    if non_ok_status:
        print(f"\nHALT: official report parse status = {non_ok_status}")
        sys.exit(2)

    print("\nDone.")


if __name__ == "__main__":
    main()
