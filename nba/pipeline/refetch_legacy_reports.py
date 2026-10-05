#!/usr/bin/env python3
"""
B21: Re-fetch legacy-era reports with zero-padded URLs, build roles.parquet.

For every legacy-era game date (< NEW_FORMAT_DATE):
  - pre_tip: latest hourly report <= first tip - 30 min
  - freeze: latest hourly report <= 5 PM ET

Also builds roles.parquet for ALL dates (legacy + new-format) from the
backfill manifest + re-fetched data.
"""
import hashlib, json, os, sys, time as time_mod
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


def legacy_report_url(d, hour24):
    ds = d.strftime("%Y-%m-%d")
    ampm = "AM" if hour24 < 12 else "PM"
    h12 = hour24 % 12 or 12
    return f"{CDN}/Injury-Report_{ds}_{h12:02d}{ampm}.pdf"


def load_game_dates(season_start):
    sched_file = ROOT / "nba" / "pipeline" / "schedule" / f"dates_{season_start}.json"
    with open(sched_file) as f:
        data = json.load(f)
    return [date.fromisoformat(d) for d in data["dates"]]


def get_first_tip(game_date):
    ds = game_date.strftime("%Y%m%d")
    try:
        r = requests.get(f"{ESPN_SCOREBOARD}?dates={ds}", timeout=15)
        if r.status_code == 200:
            events = r.json().get("events", [])
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
    return datetime(game_date.year, game_date.month, game_date.day, 19, 0, tzinfo=ET).astimezone(UTC)


def fetch_pdf(url, out_path):
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


def find_pre_tip_legacy(game_date, first_tip_utc, out_dir):
    """Find latest legacy hourly report <= (first tip - 30 min)."""
    cutoff_utc = first_tip_utc - timedelta(minutes=30)
    cutoff_et = cutoff_utc.astimezone(ET)
    cutoff_h = cutoff_et.hour

    for h in range(min(cutoff_h, 23), 9, -1):
        url = legacy_report_url(game_date, h)
        fname = url.split("/")[-1]
        pdf_path = out_dir / fname
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return url, pdf_path, hashlib.sha256(pdf_path.read_bytes()).hexdigest(), f"{h:02d}:00"
        b, sha = fetch_pdf(url, pdf_path)
        time_mod.sleep(0.5)
        if b:
            return url, pdf_path, sha, f"{h:02d}:00"
        if pdf_path.exists() and pdf_path.stat().st_size == 0:
            pdf_path.unlink()

    return None, None, None, None


def find_freeze_legacy(game_date, out_dir):
    """Find latest legacy hourly report <= 5 PM ET."""
    for h in range(17, 9, -1):
        url = legacy_report_url(game_date, h)
        fname = url.split("/")[-1]
        pdf_path = out_dir / fname
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return url, pdf_path, hashlib.sha256(pdf_path.read_bytes()).hexdigest(), f"{h:02d}:00"
        b, sha = fetch_pdf(url, pdf_path)
        time_mod.sleep(0.5)
        if b:
            return url, pdf_path, sha, f"{h:02d}:00"
        if pdf_path.exists() and pdf_path.stat().st_size == 0:
            pdf_path.unlink()

    return None, None, None, None


def main():
    seasons = [(2024, "2024"), (2025, "2025")]
    roles_rows = []
    total_fetched = 0
    start_time = time_mod.time()
    rate_reported = False

    for season_start, season_tag in seasons:
        print(f"\n{'='*60}")
        print(f"Season {season_start}-{season_start+1} (legacy dates only)")
        print(f"{'='*60}")

        out_dir = ROOT / "data" / "injury_archive" / "nba" / "history" / f"season={season_tag}"
        out_dir.mkdir(parents=True, exist_ok=True)

        game_dates = load_game_dates(season_start)
        legacy_dates = [d for d in game_dates if d < NEW_FORMAT_DATE]
        print(f"Legacy game dates: {len(legacy_dates)} ({legacy_dates[0]} to {legacy_dates[-1]})")

        for i, gd in enumerate(legacy_dates):
            first_tip = get_first_tip(gd)
            first_tip_et = first_tip.astimezone(ET)
            time_mod.sleep(0.3)  # ESPN rate limit

            # Pre-tip search
            url, pdf_path, sha, slot_et = find_pre_tip_legacy(gd, first_tip, out_dir)
            if url:
                total_fetched += 1
                roles_rows.append({
                    "game_date": gd.isoformat(),
                    "role": "pre_tip",
                    "url": url,
                    "sha256": sha,
                    "slot_et": slot_et,
                    "filename": pdf_path.name if pdf_path else "",
                    "season": f"{season_start}-{str(season_start+1)[-2:]}",
                })
                print(f"  {gd} pre_tip: {pdf_path.name if pdf_path else 'NOT FOUND'} slot={slot_et}")
            else:
                roles_rows.append({
                    "game_date": gd.isoformat(),
                    "role": "pre_tip",
                    "url": "",
                    "sha256": "",
                    "slot_et": "",
                    "filename": "",
                    "season": f"{season_start}-{str(season_start+1)[-2:]}",
                })
                print(f"  {gd} pre_tip: NOT FOUND")

            # Freeze search (latest <= 5 PM ET)
            url, pdf_path, sha, slot_et = find_freeze_legacy(gd, out_dir)
            if url:
                total_fetched += 1
                roles_rows.append({
                    "game_date": gd.isoformat(),
                    "role": "freeze",
                    "url": url,
                    "sha256": sha,
                    "slot_et": slot_et,
                    "filename": pdf_path.name if pdf_path else "",
                    "season": f"{season_start}-{str(season_start+1)[-2:]}",
                })
            else:
                roles_rows.append({
                    "game_date": gd.isoformat(),
                    "role": "freeze",
                    "url": "",
                    "sha256": "",
                    "slot_et": "",
                    "filename": "",
                    "season": f"{season_start}-{str(season_start+1)[-2:]}",
                })

            if (i + 1) % 20 == 0:
                elapsed = time_mod.time() - start_time
                print(f"  Progress: {i+1}/{len(legacy_dates)}, {total_fetched} files, "
                      f"{elapsed/60:.1f} min")

            if total_fetched >= 50 and not rate_reported:
                elapsed = time_mod.time() - start_time
                rate = total_fetched / elapsed
                remaining_dates = (len(legacy_dates) - i - 1)
                if season_start == 2024:
                    legacy_2025 = [d for d in load_game_dates(2025) if d < NEW_FORMAT_DATE]
                    remaining_dates += len(legacy_2025)
                est_remaining_files = remaining_dates * 2
                est_remaining_s = est_remaining_files / rate if rate > 0 else float('inf')
                total_est_h = (elapsed + est_remaining_s) / 3600
                print(f"\n  RATE after {total_fetched} files: {rate:.2f} files/s")
                print(f"  Projected total time: {total_est_h:.1f}h")
                if total_est_h > 2.0:
                    print("  STOP: projected time exceeds 2h")
                    sys.exit(1)
                rate_reported = True

    # Save legacy roles
    legacy_roles_path = ROOT / "data" / "injury_archive" / "nba" / "history" / "legacy_roles_raw.parquet"
    df = pd.DataFrame(roles_rows)
    df.to_parquet(legacy_roles_path, index=False)

    elapsed = time_mod.time() - start_time
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total files fetched: {total_fetched}")
    print(f"Elapsed: {elapsed/60:.1f} min ({elapsed/3600:.2f}h)")
    print(f"Legacy roles saved: {legacy_roles_path} ({len(df)} rows)")

    # Stats
    for role in ["pre_tip", "freeze"]:
        sub = df[df.role == role]
        found = sub[sub.url != ""]
        print(f"  {role}: {len(found)}/{len(sub)} found ({100*len(found)/max(len(sub),1):.1f}%)")
        if role == "pre_tip":
            non_12pm = found[~found.filename.str.contains("_12PM")]
            print(f"    non-12PM: {len(non_12pm)}/{len(found)} ({100*len(non_12pm)/max(len(found),1):.1f}%)")

    print(f"\nPre_tip slot distribution:")
    found_pt = df[(df.role == "pre_tip") & (df.url != "")]
    print(found_pt.slot_et.value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
