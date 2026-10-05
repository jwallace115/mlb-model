#!/usr/bin/env python3
"""
B25: Build game_asof.parquet — one row per game with as-of injury report.

Rule (Jeff decision 2026-10-05: "per-game cap with the 5:30 report"):
  - Freeze = date's 5:30pm ET report (_05_30PM new / _05PM legacy).
  - If freeze published_utc <= tip_utc - 30 min → asof = freeze (asof_role = freeze).
  - Otherwise → asof = latest report with published_utc <= tip_utc - 30 min (asof_role = pre_game).
  - Use published_utc (PDF header time), never the slot.
"""
import hashlib, os, re, sys, time as time_mod
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

MAIN_ROOT = Path("/Users/jw115/mlb-model")
CDN = "https://ak-static.cms.nba.com/referee/injury"
NEW_FORMAT_DATE = date(2025, 12, 22)
FETCH_CAP = 300

import requests


def legacy_report_url(d, hour24):
    ds = d.strftime("%Y-%m-%d")
    ampm = "AM" if hour24 < 12 else "PM"
    h12 = hour24 % 12 or 12
    return f"{CDN}/Injury-Report_{ds}_{h12:02d}{ampm}.pdf"


def new_report_url(d, hour24, minute):
    ds = d.strftime("%Y-%m-%d")
    ampm = "AM" if hour24 < 12 else "PM"
    h12 = hour24 % 12 or 12
    return f"{CDN}/Injury-Report_{ds}_{h12:02d}_{minute:02d}{ampm}.pdf"


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


def _season_dir(gd):
    yr = gd.year if gd.month >= 7 else gd.year - 1
    return f"season={yr}"


def get_published_utc_from_pdf(pdf_path):
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report
    rows, pub, slot_et, status, detail = parse_report(pdf_path)
    return pub, status


def find_best_pre_game_report(game_date, cutoff_utc, manifest_pub, fetch_counter):
    """Find latest report with published_utc <= cutoff_utc for a specific game."""
    gd = game_date
    season_dir = _season_dir(gd)
    pdf_base = MAIN_ROOT / "data/injury_archive/nba/history" / season_dir

    if gd < NEW_FORMAT_DATE:
        # Legacy: search backwards from cutoff hour
        cutoff_et = cutoff_utc.astimezone(ET)
        for h in range(min(cutoff_et.hour, 23), 9, -1):
            ampm = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            fname = f"Injury-Report_{gd.isoformat()}_{h12:02d}{ampm}.pdf"
            url = legacy_report_url(gd, h)

            # Check manifest
            pub = manifest_pub.get(fname)
            if pub and pub <= cutoff_utc:
                pdf_path = pdf_base / fname
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                    return fname, sha, pub, fetch_counter
                # Need to fetch
                if fetch_counter[0] >= FETCH_CAP:
                    return None, None, None, fetch_counter
                pdf_base.mkdir(parents=True, exist_ok=True)
                b, sha = fetch_pdf(url, pdf_path)
                fetch_counter[0] += 1
                time_mod.sleep(0.5)
                if b:
                    return fname, sha, pub, fetch_counter
            elif pub and pub > cutoff_utc:
                continue

            # Not in manifest — try fetching + parsing
            pdf_path = pdf_base / fname
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                pub, status = get_published_utc_from_pdf(pdf_path)
                if pub and pub <= cutoff_utc and status == "ok":
                    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                    return fname, sha, pub, fetch_counter
                continue

            if fetch_counter[0] >= FETCH_CAP:
                return None, None, None, fetch_counter
            pdf_base.mkdir(parents=True, exist_ok=True)
            b, sha = fetch_pdf(url, pdf_path)
            fetch_counter[0] += 1
            time_mod.sleep(0.5)
            if b:
                pub, status = get_published_utc_from_pdf(pdf_path)
                if pub and pub <= cutoff_utc and status == "ok":
                    return fname, sha, pub, fetch_counter
    else:
        # New format: search backwards
        cutoff_et = cutoff_utc.astimezone(ET)
        slots = []
        for h in range(10, 24):
            for m in (0, 15, 30, 45):
                slots.append((h, m))
        for h, m in reversed(slots):
            slot_et = datetime(gd.year, gd.month, gd.day, h, m, tzinfo=ET)
            if slot_et > cutoff_et:
                continue
            url = new_report_url(gd, h, m)
            fname = url.split("/")[-1]

            pub = manifest_pub.get(fname)
            if pub and pub <= cutoff_utc:
                pdf_path = pdf_base / fname
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                    return fname, sha, pub, fetch_counter

            pdf_path = pdf_base / fname
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                pub, status = get_published_utc_from_pdf(pdf_path)
                if pub and pub <= cutoff_utc and status == "ok":
                    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                    return fname, sha, pub, fetch_counter
                continue

            if fetch_counter[0] >= FETCH_CAP:
                return None, None, None, fetch_counter
            pdf_base.mkdir(parents=True, exist_ok=True)
            b, sha = fetch_pdf(url, pdf_path)
            fetch_counter[0] += 1
            time_mod.sleep(0.5)
            if b:
                pub, status = get_published_utc_from_pdf(pdf_path)
                if pub and pub <= cutoff_utc and status == "ok":
                    return fname, sha, pub, fetch_counter

    return None, None, None, fetch_counter


def main():
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")

    # Load roles (with B24 tips and published_utc)
    roles = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/roles.parquet")
    manifest = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet")

    # Build manifest published_utc lookup
    manifest_pub = {}
    for _, r in manifest.iterrows():
        if r.published_utc and r.published_utc != "":
            manifest_pub[r.filename] = datetime.fromisoformat(r.published_utc)

    # Load events
    all_events = []
    for yr in [2024, 2025]:
        fpath = MAIN_ROOT / f"data/odds_archive/nba/history/events/events_{yr}.parquet"
        if fpath.exists():
            ev = pd.read_parquet(fpath)
            ev["season"] = f"{yr}-{str(yr+1)[-2:]}"
            all_events.append(ev)
    events = pd.concat(all_events, ignore_index=True)
    events["tip_utc"] = pd.to_datetime(events.commence_time, utc=True)
    events["game_date"] = events.tip_utc.dt.tz_convert(ET).dt.date.astype(str)
    print(f"Total events: {len(events)}")

    # Build freeze lookup from roles
    freeze_map = {}  # game_date -> (filename, sha256, published_utc)
    for _, r in roles[roles.role == "freeze"].iterrows():
        if r.filename:
            pub = manifest_pub.get(r.filename)
            freeze_map[r.game_date] = (r.filename, r.sha256, pub)

    # Build game_asof rows
    asof_rows = []
    fetch_counter = [0]
    freeze_count = 0
    pre_game_count = 0
    violations = 0
    no_asof_count = 0

    for _, ev in events.iterrows():
        gd_str = ev.game_date
        gd = date.fromisoformat(gd_str)
        tip_utc = ev.tip_utc.to_pydatetime()
        cutoff = tip_utc - timedelta(minutes=30)
        tip_et = tip_utc.astimezone(ET)

        # Check freeze report
        freeze_info = freeze_map.get(gd_str)
        if freeze_info:
            f_fname, f_sha, f_pub = freeze_info
            if f_pub and f_pub <= cutoff:
                # Freeze works
                asof_rows.append({
                    "event_id": ev.event_id,
                    "game_date": gd_str,
                    "home_team": ev.home_team,
                    "away_team": ev.away_team,
                    "tip_utc": tip_utc.isoformat(),
                    "tip_source": "odds_events",
                    "asof_role": "freeze",
                    "asof_filename": f_fname,
                    "asof_sha256": f_sha,
                    "asof_published_utc": f_pub.isoformat(),
                })
                freeze_count += 1
                continue

        # Freeze doesn't work (published after cutoff or missing) — find pre_game
        fname, sha, pub, fetch_counter = find_best_pre_game_report(
            gd, cutoff, manifest_pub, fetch_counter
        )
        if fname and pub:
            if pub > cutoff:
                violations += 1
            asof_rows.append({
                "event_id": ev.event_id,
                "game_date": gd_str,
                "home_team": ev.home_team,
                "away_team": ev.away_team,
                "tip_utc": tip_utc.isoformat(),
                "tip_source": "odds_events",
                "asof_role": "pre_game",
                "asof_filename": fname,
                "asof_sha256": sha,
                "asof_published_utc": pub.isoformat(),
            })
            pre_game_count += 1
        else:
            no_asof_count += 1
            asof_rows.append({
                "event_id": ev.event_id,
                "game_date": gd_str,
                "home_team": ev.home_team,
                "away_team": ev.away_team,
                "tip_utc": tip_utc.isoformat(),
                "tip_source": "odds_events",
                "asof_role": "no_asof",
                "asof_filename": "",
                "asof_sha256": "",
                "asof_published_utc": "",
            })

        if fetch_counter[0] >= FETCH_CAP:
            print(f"FETCH CAP HIT at {fetch_counter[0]}. Stopping.")
            break

    df = pd.DataFrame(asof_rows)
    out_path = ROOT / "data/injury_archive/nba/history_parsed/game_asof.parquet"
    df.to_parquet(out_path, index=False)

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Total games: {len(df)}")
    print(f"  freeze: {freeze_count} ({100*freeze_count/len(df):.1f}%)")
    print(f"  pre_game: {pre_game_count} ({100*pre_game_count/len(df):.1f}%)")
    print(f"  no_asof: {no_asof_count}")
    print(f"Violations (published > tip-30): {violations}")
    print(f"Fetches: {fetch_counter[0]}")
    print(f"Output: {out_path} ({len(df)} rows)")

    # NULL check: every game with tip >= 18:30 ET should have freeze and same sha256
    df["tip_dt"] = pd.to_datetime(df.tip_utc)
    df["tip_et_h"] = df.tip_dt.dt.tz_convert(ET).dt.hour
    df["tip_et_m"] = df.tip_dt.dt.tz_convert(ET).dt.minute
    late_games = df[(df.tip_et_h > 18) | ((df.tip_et_h == 18) & (df.tip_et_m >= 30))]
    late_freeze = late_games[late_games.asof_role == "freeze"]
    print(f"\nNULL: games with tip >= 18:30 ET: {len(late_games)}")
    print(f"  of which freeze: {len(late_freeze)} ({100*len(late_freeze)/max(len(late_games),1):.1f}%)")

    # Verify sha256 matches roles freeze
    roles_freeze = {r.game_date: r.sha256 for _, r in
                    pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/roles.parquet").query("role == 'freeze'").iterrows()}
    mismatches = 0
    for _, g in late_freeze.iterrows():
        if g.game_date in roles_freeze and g.asof_sha256 != roles_freeze[g.game_date]:
            mismatches += 1
    print(f"  sha256 mismatches vs roles freeze: {mismatches}")
    non_freeze_late = late_games[late_games.asof_role != "freeze"]
    if len(non_freeze_late) > 0:
        print(f"  non-freeze late games: {len(non_freeze_late)}")
        print(non_freeze_late[["game_date", "tip_utc", "asof_role"]].head(5))


if __name__ == "__main__":
    main()
