#!/usr/bin/env python3
"""
B28: Apply Jeff's freeze rule on every date, including dates missing from schedule.

- Fetch freeze (5:30pm) for missing dates
- Add roles rows for them
- Rebuild game_asof with no fallback: freeze if published <= tip-30, else latest ok <= tip-30
- date_in_schedule column
- 2026-04-11 → not_game_date
"""
import hashlib, json, os, re, sys, time as time_mod
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")

from nba.pipeline.injury_report_parser import parse_report

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

MAIN = Path("/Users/jw115/mlb-model")
CDN = "https://ak-static.cms.nba.com/referee/injury"
NEW_FORMAT_DATE = date(2025, 12, 22)

MISSING_DATES = ["2024-12-17", "2025-04-15", "2025-04-16", "2025-04-19", "2026-03-28"]


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


def _season_tag(gd):
    return str(gd.year if gd.month >= 7 else gd.year - 1)


def _season_label(gd):
    yr = gd.year if gd.month >= 7 else gd.year - 1
    return f"{yr}-{str(yr+1)[-2:]}"


def get_freeze_report(gd):
    """Get the freeze (5:30pm / 5pm) report for a date. Returns (fname, url, sha, pub, status)."""
    stag = _season_tag(gd)
    pdf_dir = MAIN / "data/injury_archive/nba/history" / f"season={stag}"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    if gd >= NEW_FORMAT_DATE:
        url = new_report_url(gd, 17, 30)
    else:
        url = legacy_report_url(gd, 17)

    fname = url.split("/")[-1]
    pdf_path = pdf_dir / fname

    if not (pdf_path.exists() and pdf_path.stat().st_size > 0):
        b, sha = fetch_pdf(url, pdf_path)
        time_mod.sleep(0.5)
        if not b:
            return None, url, None, None, "not_found"

    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    rows, pub, slot_et, status, detail = parse_report(pdf_path)

    # Write parsed parquet if not exists
    hp_dir = ROOT / "data/injury_archive/nba/history_parsed" / f"season={stag}"
    hp_dir.mkdir(parents=True, exist_ok=True)
    pq_name = fname.replace(".pdf", ".parquet")
    pq_path = hp_dir / pq_name
    if not pq_path.exists():
        if rows:
            df = pd.DataFrame(rows)
            df["published_utc"] = pub.isoformat() if pub else ""
            df["slot_et"] = slot_et or ""
            df["pdf_sha256"] = sha
            df.to_parquet(pq_path, index=False)
        else:
            df = pd.DataFrame(columns=["game_date", "game_time", "matchup", "team", "player",
                                        "status", "reason", "published_utc", "slot_et", "pdf_sha256"])
            df.to_parquet(pq_path, index=False)

    return fname, url, sha, pub, status


def get_manifest_pub(manifest, fname):
    row = manifest[manifest.filename == fname]
    if len(row) > 0 and row.iloc[0].published_utc:
        return datetime.fromisoformat(row.iloc[0].published_utc)
    return None


def find_best_report(gd, cutoff_utc, manifest):
    """Find latest ok report with published_utc <= cutoff. Returns (fname, sha, pub)."""
    stag = _season_tag(gd)
    pdf_dir = MAIN / "data/injury_archive/nba/history" / f"season={stag}"

    if gd < NEW_FORMAT_DATE:
        cutoff_et = cutoff_utc.astimezone(ET)
        for h in range(min(cutoff_et.hour, 23), 9, -1):
            ampm = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            fname = f"Injury-Report_{gd.isoformat()}_{h12:02d}{ampm}.pdf"
            pub = get_manifest_pub(manifest, fname)
            if pub and pub <= cutoff_utc:
                pdf_path = pdf_dir / fname
                if pdf_path.exists():
                    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                    return fname, sha, pub
            elif not pub:
                pdf_path = pdf_dir / fname
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    rows, pub2, _, st, _ = parse_report(pdf_path)
                    if pub2 and pub2 <= cutoff_utc and st == "ok":
                        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                        return fname, sha, pub2
    else:
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
            pub = get_manifest_pub(manifest, fname)
            if pub and pub <= cutoff_utc:
                pdf_path = pdf_dir / fname
                if pdf_path.exists():
                    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                    return fname, sha, pub
            elif not pub:
                pdf_path = pdf_dir / fname
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    rows, pub2, _, st, _ = parse_report(pdf_path)
                    if pub2 and pub2 <= cutoff_utc and st == "ok":
                        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                        return fname, sha, pub2

    return None, None, None


def main():
    roles = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/roles.parquet")
    manifest = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet")

    # Load schedule dates
    sched_dates = set()
    for yr in [2024, 2025]:
        with open(ROOT / f"nba/pipeline/schedule/dates_{yr}.json") as f:
            sched_dates.update(json.load(f)["dates"])

    # Load events
    all_events = []
    for yr in [2024, 2025]:
        fpath = MAIN / f"data/odds_archive/nba/history/events/events_{yr}.parquet"
        if fpath.exists():
            ev = pd.read_parquet(fpath)
            all_events.append(ev)
    events = pd.concat(all_events, ignore_index=True)
    events["tip_utc"] = pd.to_datetime(events.commence_time, utc=True)
    events["game_date"] = events.tip_utc.dt.tz_convert(ET).dt.date.astype(str)

    # 1. Fix 2026-04-11 in roles
    roles.loc[roles.game_date == "2026-04-11", "status"] = "not_game_date"

    # 2. Fetch freeze reports for missing dates and add roles rows
    new_roles_rows = []
    fetch_count = 0
    for gd_str in MISSING_DATES:
        gd = date.fromisoformat(gd_str)
        print(f"\nMissing date: {gd_str}")

        # Get freeze
        fname, url, sha, pub, status = get_freeze_report(gd)
        fetch_count += 1
        print(f"  freeze: {fname} status={status} pub={pub}")

        if fname and status == "ok":
            # Add manifest row if missing
            if fname not in manifest.filename.values:
                nys = 0
                pdf_path = MAIN / "data/injury_archive/nba/history" / f"season={_season_tag(gd)}" / fname
                rows_p, _, _, _, _ = parse_report(pdf_path)
                nys = len([r for r in rows_p if r.get("status") == "NOT_YET_SUBMITTED"])
                new_mrow = pd.DataFrame([{
                    "filename": fname, "sha256": sha,
                    "published_utc": pub.isoformat() if pub else "",
                    "status": "ok", "n_rows": len(rows_p), "n_nys": nys,
                    "season": _season_tag(gd),
                }])
                manifest = pd.concat([manifest, new_mrow], ignore_index=True)

            # Get tip from events for this date
            date_events = events[events.game_date == gd_str]
            if len(date_events) > 0:
                first_tip = date_events.tip_utc.min().to_pydatetime()
                tip_source = "odds_events"
            else:
                first_tip = None
                tip_source = ""

            # Add roles rows
            new_roles_rows.append({
                "game_date": gd_str, "role": "freeze",
                "url": url, "sha256": sha,
                "slot_et": "17:30" if gd >= NEW_FORMAT_DATE else "17:00",
                "filename": fname, "season": _season_label(gd),
                "status": "ok",
                "first_tip_utc": first_tip.isoformat() if first_tip else "",
                "tip_source": tip_source,
                "published_utc": pub.isoformat() if pub else "",
            })

            # Also add pre_tip role
            if first_tip:
                cutoff = first_tip - timedelta(minutes=30)
                pt_fname, pt_sha, pt_pub = find_best_report(gd, cutoff, manifest)
                if pt_fname:
                    from nba.pipeline.injury_report_parser import slot_datetime_from_filename
                    try:
                        sdt = slot_datetime_from_filename(pt_fname)
                        slot_str = sdt.strftime("%H:%M")
                    except Exception:
                        slot_str = ""
                    new_roles_rows.append({
                        "game_date": gd_str, "role": "pre_tip",
                        "url": f"{CDN}/{pt_fname}", "sha256": pt_sha,
                        "slot_et": slot_str, "filename": pt_fname,
                        "season": _season_label(gd), "status": "ok",
                        "first_tip_utc": first_tip.isoformat(),
                        "tip_source": tip_source,
                        "published_utc": pt_pub.isoformat() if pt_pub else "",
                    })

    # Add new roles rows
    if new_roles_rows:
        roles = pd.concat([roles, pd.DataFrame(new_roles_rows)], ignore_index=True)

    # Add date_in_schedule
    roles["date_in_schedule"] = roles.game_date.isin(sched_dates)

    # Save updated roles
    roles.to_parquet(ROOT / "data/injury_archive/nba/history_parsed/roles.parquet", index=False)
    print(f"\nRoles: {len(roles)} rows")

    # Save updated manifest
    manifest.to_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet", index=False)
    print(f"Manifest: {len(manifest)} rows")

    # 3. Rebuild game_asof with no fallback
    # Build freeze lookup from ALL roles (including new dates)
    freeze_map = {}
    for _, r in roles[roles.role == "freeze"].iterrows():
        if r.filename:
            pub = get_manifest_pub(manifest, r.filename)
            freeze_map[r.game_date] = (r.filename, r.sha256, pub)

    asof_rows = []
    freeze_count = 0
    pre_game_count = 0
    no_asof_count = 0

    for _, ev in events.iterrows():
        gd_str = ev.game_date
        gd = date.fromisoformat(gd_str)
        tip_utc = ev.tip_utc.to_pydatetime()
        cutoff = tip_utc - timedelta(minutes=30)

        # Check freeze report
        freeze_info = freeze_map.get(gd_str)
        if freeze_info:
            f_fname, f_sha, f_pub = freeze_info
            if f_pub and f_pub <= cutoff:
                asof_rows.append({
                    "event_id": ev.event_id, "game_date": gd_str,
                    "home_team": ev.home_team, "away_team": ev.away_team,
                    "tip_utc": tip_utc.isoformat(), "tip_source": "odds_events",
                    "asof_role": "freeze", "asof_filename": f_fname,
                    "asof_sha256": f_sha,
                    "asof_published_utc": f_pub.isoformat(),
                    "date_in_schedule": gd_str in sched_dates,
                })
                freeze_count += 1
                continue

        # Freeze not available or too late — find pre_game
        fname, sha, pub = find_best_report(gd, cutoff, manifest)
        if fname and pub:
            asof_rows.append({
                "event_id": ev.event_id, "game_date": gd_str,
                "home_team": ev.home_team, "away_team": ev.away_team,
                "tip_utc": tip_utc.isoformat(), "tip_source": "odds_events",
                "asof_role": "pre_game", "asof_filename": fname,
                "asof_sha256": sha,
                "asof_published_utc": pub.isoformat(),
                "date_in_schedule": gd_str in sched_dates,
            })
            pre_game_count += 1
        else:
            asof_rows.append({
                "event_id": ev.event_id, "game_date": gd_str,
                "home_team": ev.home_team, "away_team": ev.away_team,
                "tip_utc": tip_utc.isoformat(), "tip_source": "odds_events",
                "asof_role": "no_asof", "asof_filename": "",
                "asof_sha256": "",
                "asof_published_utc": "",
                "date_in_schedule": gd_str in sched_dates,
            })
            no_asof_count += 1

    asof_df = pd.DataFrame(asof_rows)
    asof_df.to_parquet(ROOT / "data/injury_archive/nba/history_parsed/game_asof.parquet", index=False)

    print(f"\ngame_asof: {len(asof_df)} rows")
    print(f"  freeze: {freeze_count} ({100*freeze_count/len(asof_df):.1f}%)")
    print(f"  pre_game: {pre_game_count} ({100*pre_game_count/len(asof_df):.1f}%)")
    print(f"  no_asof: {no_asof_count}")
    print(f"Fetches: {fetch_count}")

    # Check: games with tip >= 18:30 ET and asof_role != freeze
    asof_df["tip_dt"] = pd.to_datetime(asof_df.tip_utc)
    asof_df["tip_et_h"] = asof_df.tip_dt.dt.tz_convert(ET).dt.hour
    asof_df["tip_et_m"] = asof_df.tip_dt.dt.tz_convert(ET).dt.minute
    late = asof_df[(asof_df.tip_et_h > 18) | ((asof_df.tip_et_h == 18) & (asof_df.tip_et_m >= 30))]
    non_freeze_late = late[late.asof_role != "freeze"]
    print(f"\nLate games (tip >= 18:30 ET): {len(late)}")
    print(f"  non-freeze: {len(non_freeze_late)}")
    if len(non_freeze_late) > 0:
        print(non_freeze_late[["game_date", "home_team", "away_team", "tip_utc", "asof_role"]].to_string())

    # Violations
    violations = 0
    for _, r in asof_df[asof_df.asof_published_utc != ""].iterrows():
        pub = datetime.fromisoformat(r.asof_published_utc)
        tip = datetime.fromisoformat(r.tip_utc)
        if pub > tip - timedelta(minutes=30):
            violations += 1
    print(f"\nViolations (published > tip-30): {violations}")

    # NULL: schedule dates keep same asof
    old_asof = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/game_asof.parquet")
    # Wait, we just overwrote it. Use git to get the old one.
    import subprocess, io
    try:
        old_bytes = subprocess.check_output(
            ["git", "show", "9beb9125d:data/injury_archive/nba/history_parsed/game_asof.parquet"],
            cwd=str(ROOT))
        old_asof = pd.read_parquet(io.BytesIO(old_bytes))
        sched_old = old_asof[old_asof.game_date.isin(sched_dates)]
        sched_new = asof_df[asof_df.game_date.isin(sched_dates)]
        merged = sched_old[["event_id", "asof_filename", "asof_sha256"]].merge(
            sched_new[["event_id", "asof_filename", "asof_sha256"]],
            on="event_id", suffixes=("_old", "_new"))
        changed = merged[(merged.asof_filename_old != merged.asof_filename_new) |
                         (merged.asof_sha256_old != merged.asof_sha256_new)]
        print(f"\nNULL: schedule-date games: {len(merged)}, changed: {len(changed)}")
    except Exception as e:
        print(f"\nNULL check error: {e}")


if __name__ == "__main__":
    main()
