#!/usr/bin/env python3
"""
B16: Backfill official injury reports, regular seasons 2024-25 and 2025-26.

For each regular-season game date (from schedule files + ESPN tip times):
  (a) latest report at or before (first tip - 30 min)
  (b) 5:30 PM ET report (new format _HH_MMAM|PM from 2025-12-22 on;
      before that, legacy hourly _HHAM|PM -> latest hourly <= 5 PM ET)

Raw PDFs: data/injury_archive/nba/history/season=<yr>/ — kept OUT of git.
Only parsed parquet + manifest committed.

Both parsers on every file; disagreements listed, never patched.
Mac only (CDN blocks the VM with 403).
"""
import hashlib, json, os, subprocess, sys, time as time_mod
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

CDN = "https://ak-static.cms.nba.com/referee/injury"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

NEW_FORMAT_DATE = date(2025, 12, 22)


def official_report_url(d, hour24, minute):
    ds = d.strftime("%Y-%m-%d")
    ampm = "AM" if hour24 < 12 else "PM"
    h12 = hour24 % 12 or 12
    return f"{CDN}/Injury-Report_{ds}_{h12:02d}_{minute:02d}{ampm}.pdf"


def legacy_report_url(d, hour24):
    ds = d.strftime("%Y-%m-%d")
    ampm = "AM" if hour24 < 12 else "PM"
    h12 = hour24 % 12 or 12
    return f"{CDN}/Injury-Report_{ds}_{h12:02d}{ampm}.pdf"


def load_game_dates(season_start):
    """Load game dates from schedule files."""
    sched_file = ROOT / "nba" / "pipeline" / "schedule" / f"dates_{season_start}.json"
    with open(sched_file) as f:
        data = json.load(f)
    return [date.fromisoformat(d) for d in data["dates"]]


def get_first_tip(game_date):
    """Get earliest tip time for a date from ESPN scoreboard."""
    ds = game_date.strftime("%Y%m%d")
    try:
        r = requests.get(f"{ESPN_SCOREBOARD}?dates={ds}", timeout=15)
        if r.status_code == 200:
            events = r.json().get("events", [])
            # Report season type
            if events:
                st = events[0].get("season", {}).get("type", 0)
                slug = events[0].get("season", {}).get("slug", "")
            tips = []
            for ev in events:
                tip_str = ev.get("date", "")
                if tip_str:
                    tip_utc = datetime.fromisoformat(tip_str.replace("Z", "+00:00"))
                    tips.append(tip_utc)
            if tips:
                return min(tips)
    except Exception:
        pass
    # Fallback: assume 7:00 PM ET
    return datetime(game_date.year, game_date.month, game_date.day, 19, 0, tzinfo=ET).astimezone(UTC)


def fetch_pdf(url, out_path):
    """Download a PDF. Returns (bytes, sha256) or (None, None)."""
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        if r.status_code != 200:
            return None, None
        r2 = requests.get(url, timeout=30)
        if r2.status_code != 200:
            return None, None
        out_path.write_bytes(r2.content)
        return r2.content, hashlib.sha256(r2.content).hexdigest()
    except Exception:
        return None, None


def find_pre_tip_report(game_date, first_tip_utc, out_dir):
    """Find the latest report at or before (first tip - 30 min). Searches backwards."""
    cutoff_utc = first_tip_utc - timedelta(minutes=30)
    cutoff_et = cutoff_utc.astimezone(ET)
    cutoff_h = cutoff_et.hour
    cutoff_m = cutoff_et.minute

    if game_date >= NEW_FORMAT_DATE:
        slots = []
        for h in range(10, min(cutoff_h + 1, 24)):
            for m in (0, 15, 30, 45):
                if h == cutoff_h and m > cutoff_m:
                    break
                slots.append((h, m))
        for h, m in reversed(slots):
            url = official_report_url(game_date, h, m)
            fname = url.split("/")[-1]
            pdf_path = out_dir / fname
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return url, pdf_path, hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            b, sha = fetch_pdf(url, pdf_path)
            time_mod.sleep(0.5)
            if b:
                return url, pdf_path, sha
            if pdf_path.exists() and pdf_path.stat().st_size == 0:
                pdf_path.unlink()
    else:
        for h in range(min(cutoff_h, 23), 9, -1):
            url = legacy_report_url(game_date, h)
            fname = url.split("/")[-1]
            pdf_path = out_dir / fname
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return url, pdf_path, hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            b, sha = fetch_pdf(url, pdf_path)
            time_mod.sleep(0.5)
            if b:
                return url, pdf_path, sha
            if pdf_path.exists() and pdf_path.stat().st_size == 0:
                pdf_path.unlink()

    return None, None, None


def find_530_report(game_date, out_dir):
    """Find the 5:30 PM ET report."""
    if game_date >= NEW_FORMAT_DATE:
        url = official_report_url(game_date, 17, 30)
        fname = url.split("/")[-1]
        pdf_path = out_dir / fname
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return url, pdf_path, hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        b, sha = fetch_pdf(url, pdf_path)
        time_mod.sleep(0.5)
        if b:
            return url, pdf_path, sha
        if pdf_path.exists() and pdf_path.stat().st_size == 0:
            pdf_path.unlink()
        return None, None, None
    else:
        # Legacy: latest hourly <= 5 PM ET
        for h in range(17, 9, -1):
            url = legacy_report_url(game_date, h)
            fname = url.split("/")[-1]
            pdf_path = out_dir / fname
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return url, pdf_path, hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            b, sha = fetch_pdf(url, pdf_path)
            time_mod.sleep(0.5)
            if b:
                return url, pdf_path, sha
            if pdf_path.exists() and pdf_path.stat().st_size == 0:
                pdf_path.unlink()
        return None, None, None


def main():
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report

    # Add history path to git exclude
    git_common = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"],
        text=True, cwd=str(ROOT),
    ).strip()
    exclude_file = Path(git_common) / "info" / "exclude"
    history_pattern = "data/injury_archive/nba/history/"

    if exclude_file.exists():
        existing = exclude_file.read_text()
        if history_pattern not in existing:
            with open(exclude_file, "a") as f:
                f.write(f"\n{history_pattern}\n")
            print(f"Added {history_pattern} to {exclude_file}")
        else:
            print(f"{history_pattern} already in {exclude_file}")
    else:
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        exclude_file.write_text(f"{history_pattern}\n")

    # Verify git exclude works
    test_path = ROOT / "data" / "injury_archive" / "nba" / "history" / "test"
    result = subprocess.run(
        ["git", "check-ignore", str(test_path)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode == 0:
        print(f"git check-ignore confirms: history path is excluded")
    else:
        print(f"WARNING: history path is NOT excluded by git")
        sys.exit(1)

    seasons = [(2024, "2024"), (2025, "2025")]
    manifest_rows = []
    total_files = 0
    start_time = time_mod.time()
    disagree_count = 0
    season_types_seen = set()
    rate_reported = False

    for season_start, season_tag in seasons:
        print(f"\n{'='*60}")
        print(f"Season {season_start}-{season_start+1}")
        print(f"{'='*60}")

        out_dir = ROOT / "data" / "injury_archive" / "nba" / "history" / f"season={season_tag}"
        out_dir.mkdir(parents=True, exist_ok=True)

        game_dates = load_game_dates(season_start)
        print(f"Game dates: {len(game_dates)} ({game_dates[0]} to {game_dates[-1]})")

        for i, gd in enumerate(game_dates):
            first_tip = get_first_tip(gd)
            first_tip_et = first_tip.astimezone(ET)
            time_mod.sleep(0.3)  # ESPN rate limit

            for report_type, find_fn in [
                ("pre_tip", lambda: find_pre_tip_report(gd, first_tip, out_dir)),
                ("530pm", lambda: find_530_report(gd, out_dir)),
            ]:
                url, pdf_path, sha = find_fn()
                if pdf_path and pdf_path.exists():
                    total_files += 1
                    parsed, pub, slot, status, detail = parse_report(pdf_path)
                    rows_n = len(parsed)
                    pub_str = pub.isoformat() if pub else ""
                    if status == "parse_disagree":
                        disagree_count += 1
                        print(f"  DISAGREE {gd} {report_type}: {pdf_path.name}: {detail[:100]}")
                    manifest_rows.append({
                        "season": f"{season_start}-{str(season_start+1)[-2:]}",
                        "game_date": gd.isoformat(),
                        "report_type": report_type,
                        "url": url or "",
                        "filename": pdf_path.name,
                        "sha256": sha or "",
                        "published_utc": pub_str,
                        "status": status,
                        "rows": rows_n,
                    })
                else:
                    manifest_rows.append({
                        "season": f"{season_start}-{str(season_start+1)[-2:]}",
                        "game_date": gd.isoformat(),
                        "report_type": report_type,
                        "url": "",
                        "filename": "",
                        "sha256": "",
                        "published_utc": "",
                        "status": "not_found",
                        "rows": 0,
                    })

            if (i + 1) % 20 == 0:
                elapsed = time_mod.time() - start_time
                rate = total_files / elapsed if elapsed > 0 else 0
                print(f"  {gd}: {i+1}/{len(game_dates)}, {total_files} files, "
                      f"{elapsed/60:.1f} min, {rate:.2f} files/s")

            if total_files >= 50 and not rate_reported:
                elapsed = time_mod.time() - start_time
                rate = total_files / elapsed
                remaining_dates = (len(game_dates) - i - 1)
                if season_start == 2024:
                    remaining_dates += len(load_game_dates(2025))
                est_remaining_files = remaining_dates * 2
                est_remaining_s = est_remaining_files / rate if rate > 0 else float('inf')
                total_est_h = (elapsed + est_remaining_s) / 3600
                print(f"\n  RATE after {total_files} files: {rate:.2f} files/s")
                print(f"  Projected total time: {total_est_h:.1f}h")
                if total_est_h > 2.0:
                    print("  STOP: projected time exceeds 2h")
                    # Save what we have
                    df = pd.DataFrame(manifest_rows)
                    manifest_path = ROOT / "data" / "injury_archive" / "nba" / "history" / "backfill_manifest.parquet"
                    df.to_parquet(manifest_path, index=False)
                    print(f"  Partial manifest saved: {len(df)} rows")
                    sys.exit(1)
                rate_reported = True

    # Write manifest
    manifest_path = ROOT / "data" / "injury_archive" / "nba" / "history" / "backfill_manifest.parquet"
    df = pd.DataFrame(manifest_rows)
    df.to_parquet(manifest_path, index=False)

    elapsed = time_mod.time() - start_time
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total files fetched+parsed: {total_files}")
    print(f"Elapsed: {elapsed/60:.1f} min ({elapsed/3600:.2f}h)")
    print(f"Disagreements: {disagree_count}")
    print(f"Manifest: {manifest_path} ({len(df)} rows)")

    for season_start, _ in seasons:
        stag = f"{season_start}-{str(season_start+1)[-2:]}"
        sdf = df[df.season == stag]
        for rt in ["pre_tip", "530pm"]:
            sub = sdf[sdf.report_type == rt]
            found = sub[sub.status != "not_found"]
            ok = sub[sub.status == "ok"]
            print(f"  {stag} {rt}: {len(found)}/{len(sub)} found ({100*len(found)/len(sub):.1f}%), "
                  f"{len(ok)} ok, A==B on {100*len(ok)/max(len(found),1):.1f}%")


if __name__ == "__main__":
    main()
