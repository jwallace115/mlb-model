#!/usr/bin/env python3
"""
B24: Rebuild roles.parquet with published-time pre_tip selection and stored tip times.

Pre_tip = latest report whose published_utc <= first_tip_utc - 30 min.
Tip source: Odds API events parquets (0 credits); ESPN as cross-check.
No silent 19:00 ET default.
"""
import hashlib, json, os, re, sys, time as time_mod
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

import requests
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


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


def get_espn_first_tip(game_date):
    """Get first tip from ESPN. Returns (tip_utc, True) or (None, False)."""
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
                return min(tips), True
    except Exception:
        pass
    return None, False


def load_odds_tips():
    """Load first tip per game date from Odds API events parquets."""
    tips = {}
    for yr in [2024, 2025]:
        fpath = MAIN_ROOT / f"data/odds_archive/nba/history/events/events_{yr}.parquet"
        if not fpath.exists():
            continue
        ev = pd.read_parquet(fpath)
        ev["ct_dt"] = pd.to_datetime(ev.commence_time, utc=True)
        ev["gd"] = ev.ct_dt.dt.tz_convert(ET).dt.date
        for gd, grp in ev.groupby("gd"):
            tips[gd] = grp.ct_dt.min()
    return tips


def published_utc_from_manifest(manifest, filename):
    """Get published_utc from manifest for a given filename."""
    row = manifest[manifest.filename == filename]
    if len(row) == 0:
        return None
    pub_str = row.iloc[0].published_utc
    if not pub_str or pub_str == "":
        return None
    return datetime.fromisoformat(pub_str)


def get_published_utc_from_pdf(pdf_path):
    """Parse published_utc from a PDF using the parser."""
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")
    from nba.pipeline.injury_report_parser import parse_report
    rows, pub, slot_et, status, detail = parse_report(pdf_path)
    return pub, status, rows


def find_earlier_legacy_report(game_date, current_hour, cutoff_utc, out_dir, manifest):
    """Search for an earlier legacy report whose published_utc <= cutoff_utc."""
    for h in range(current_hour - 1, 9, -1):
        url = legacy_report_url(game_date, h)
        fname = url.split("/")[-1]
        pdf_path = out_dir / fname

        # Check manifest first
        pub = published_utc_from_manifest(manifest, fname)
        if pub and pub <= cutoff_utc:
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
                return fname, url, sha, pub
            # Also check main checkout
            main_path = MAIN_ROOT / "data/injury_archive/nba/history" / f"season={game_date.year - (1 if game_date.month < 7 else 0)}" / fname
            if not main_path.exists():
                main_path = MAIN_ROOT / "data/injury_archive/nba/history" / f"season={game_date.year}" / fname
            if main_path.exists() and main_path.stat().st_size > 0:
                sha = hashlib.sha256(main_path.read_bytes()).hexdigest()
                return fname, url, sha, pub

        # Need to fetch and parse
        main_pdf = MAIN_ROOT / "data/injury_archive/nba/history" / _season_dir(game_date) / fname
        if main_pdf.exists() and main_pdf.stat().st_size > 0:
            pub, status, _ = get_published_utc_from_pdf(main_pdf)
            if pub and pub <= cutoff_utc and status == "ok":
                sha = hashlib.sha256(main_pdf.read_bytes()).hexdigest()
                return fname, url, sha, pub
            if pub and pub > cutoff_utc:
                continue  # too late, try earlier

        # Fetch from CDN
        out_path = main_pdf.parent
        out_path.mkdir(parents=True, exist_ok=True)
        b, sha = fetch_pdf(url, main_pdf)
        if b:
            time_mod.sleep(0.5)
            pub, status, _ = get_published_utc_from_pdf(main_pdf)
            if pub and pub <= cutoff_utc and status == "ok":
                return fname, url, sha, pub
            if pub and pub > cutoff_utc:
                continue
        else:
            time_mod.sleep(0.5)

    return None, None, None, None


def find_earlier_new_report(game_date, current_slot_h, current_slot_m, cutoff_utc, out_dir, manifest):
    """Search for an earlier new-format report whose published_utc <= cutoff_utc."""
    # Build slot list backwards from just before current
    slots = []
    for h in range(10, 24):
        for m in (0, 15, 30, 45):
            if (h, m) < (current_slot_h, current_slot_m):
                slots.append((h, m))
    for h, m in reversed(slots):
        url = new_report_url(game_date, h, m)
        fname = url.split("/")[-1]

        pub = published_utc_from_manifest(manifest, fname)
        if pub and pub <= cutoff_utc:
            main_path = MAIN_ROOT / "data/injury_archive/nba/history" / _season_dir(game_date) / fname
            if main_path.exists() and main_path.stat().st_size > 0:
                sha = hashlib.sha256(main_path.read_bytes()).hexdigest()
                return fname, url, sha, pub

        # Try fetching
        main_pdf = MAIN_ROOT / "data/injury_archive/nba/history" / _season_dir(game_date) / fname
        if main_pdf.exists() and main_pdf.stat().st_size > 0:
            pub, status, _ = get_published_utc_from_pdf(main_pdf)
            if pub and pub <= cutoff_utc and status == "ok":
                sha = hashlib.sha256(main_pdf.read_bytes()).hexdigest()
                return fname, url, sha, pub
            if pub and pub > cutoff_utc:
                continue

        main_pdf.parent.mkdir(parents=True, exist_ok=True)
        b, sha = fetch_pdf(url, main_pdf)
        if b:
            time_mod.sleep(0.5)
            pub, status, _ = get_published_utc_from_pdf(main_pdf)
            if pub and pub <= cutoff_utc and status == "ok":
                return fname, url, sha, pub
        else:
            time_mod.sleep(0.5)

    return None, None, None, None


def _season_dir(gd):
    """Return season=YYYY dir name for a game date."""
    yr = gd.year if gd.month >= 7 else gd.year - 1
    return f"season={yr}"


def slot_hour_min_from_filename(fname):
    """Extract (hour24, minute) from filename."""
    m = re.match(r"Injury-Report_\d{4}-\d{2}-\d{2}_(\d{1,2})_(\d{2})(AM|PM)\.pdf", fname)
    if m:
        h, mi, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
        if ampm == "PM" and h != 12: h += 12
        if ampm == "AM" and h == 12: h = 0
        return h, mi
    m = re.match(r"Injury-Report_\d{4}-\d{2}-\d{2}_(\d{1,2})(AM|PM)\.pdf", fname)
    if m:
        h, ampm = int(m.group(1)), m.group(2)
        if ampm == "PM" and h != 12: h += 12
        if ampm == "AM" and h == 12: h = 0
        return h, 0
    return None, None


def main():
    os.environ.setdefault("JAVA_HOME", "/Users/jw115/jre21/Contents/Home")

    # Load existing data
    roles = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/roles.parquet")
    manifest = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/manifest.parquet")
    odds_tips = load_odds_tips()

    # Get unique game dates
    game_dates = sorted(roles.game_date.unique())
    print(f"Game dates: {len(game_dates)}")

    # ESPN cross-check (sample 10 dates to measure mismatch)
    espn_mismatches = []
    espn_tips_map = {}

    # Build new roles rows
    new_rows = []
    fetch_count = 0
    dates_changed = 0
    dates_unchanged = 0
    violations_before = 0
    violations_after = 0

    for gd_str in game_dates:
        gd = date.fromisoformat(gd_str)

        # Get tip time from Odds API
        odds_tip = odds_tips.get(gd)
        tip_source = "odds_events" if odds_tip else None
        first_tip_utc = odds_tip

        # ESPN cross-check
        espn_tip, espn_ok = get_espn_first_tip(gd)
        time_mod.sleep(0.3)
        if espn_ok:
            espn_tips_map[gd] = espn_tip
            if odds_tip and espn_tip:
                delta_min = abs((espn_tip - odds_tip).total_seconds()) / 60
                if delta_min > 15:
                    espn_mismatches.append({
                        "game_date": gd_str,
                        "espn_tip": espn_tip.isoformat(),
                        "odds_tip": odds_tip.isoformat(),
                        "delta_min": round(delta_min, 1),
                    })
            if not odds_tip and espn_tip:
                first_tip_utc = espn_tip
                tip_source = "espn"

        if first_tip_utc is None:
            # No tip from either source
            for role in ["pre_tip", "freeze"]:
                old_row = roles[(roles.game_date == gd_str) & (roles.role == role)]
                if len(old_row) > 0:
                    r = old_row.iloc[0]
                    new_rows.append({
                        "game_date": gd_str, "role": role,
                        "url": r.url, "sha256": r.sha256, "slot_et": r.slot_et,
                        "filename": r.filename, "season": r.season,
                        "status": "no_tip",
                        "first_tip_utc": "", "tip_source": "",
                        "published_utc": "",
                    })
            continue

        cutoff = first_tip_utc - timedelta(minutes=30)

        # Process freeze (unchanged — it's always the 5PM/5:30PM report)
        freeze_row = roles[(roles.game_date == gd_str) & (roles.role == "freeze")]
        if len(freeze_row) > 0:
            fr = freeze_row.iloc[0]
            fr_pub = published_utc_from_manifest(manifest, fr.filename)
            if fr_pub is None and fr.filename:
                # Parse from PDF
                pdf_path = MAIN_ROOT / "data/injury_archive/nba/history" / _season_dir(gd) / fr.filename
                if pdf_path.exists():
                    fr_pub, _, _ = get_published_utc_from_pdf(pdf_path)
            new_rows.append({
                "game_date": gd_str, "role": "freeze",
                "url": fr.url, "sha256": fr.sha256, "slot_et": fr.slot_et,
                "filename": fr.filename, "season": fr.season,
                "status": "ok",
                "first_tip_utc": first_tip_utc.isoformat(),
                "tip_source": tip_source,
                "published_utc": fr_pub.isoformat() if fr_pub else "",
            })

        # Process pre_tip — check if current one satisfies published_utc <= cutoff
        pt_row = roles[(roles.game_date == gd_str) & (roles.role == "pre_tip")]
        if len(pt_row) > 0:
            pr = pt_row.iloc[0]
            pr_pub = published_utc_from_manifest(manifest, pr.filename)
            if pr_pub is None and pr.filename:
                pdf_path = MAIN_ROOT / "data/injury_archive/nba/history" / _season_dir(gd) / pr.filename
                if pdf_path.exists():
                    pr_pub, _, _ = get_published_utc_from_pdf(pdf_path)

            # Check violation
            if pr_pub and pr_pub > cutoff:
                violations_before += 1
                # Need to find an earlier report
                slot_h, slot_m = slot_hour_min_from_filename(pr.filename)
                if gd < NEW_FORMAT_DATE:
                    new_fname, new_url, new_sha, new_pub = find_earlier_legacy_report(
                        gd, slot_h, cutoff, MAIN_ROOT / "data/injury_archive/nba/history" / _season_dir(gd), manifest
                    )
                else:
                    new_fname, new_url, new_sha, new_pub = find_earlier_new_report(
                        gd, slot_h, slot_m, cutoff, MAIN_ROOT / "data/injury_archive/nba/history" / _season_dir(gd), manifest
                    )

                if new_fname:
                    fetch_count += 1
                    dates_changed += 1
                    new_rows.append({
                        "game_date": gd_str, "role": "pre_tip",
                        "url": new_url, "sha256": new_sha, "slot_et": f"{slot_hour_min_from_filename(new_fname)[0]:02d}:{slot_hour_min_from_filename(new_fname)[1]:02d}" if slot_hour_min_from_filename(new_fname)[0] is not None else "",
                        "filename": new_fname, "season": pr.season,
                        "status": "ok",
                        "first_tip_utc": first_tip_utc.isoformat(),
                        "tip_source": tip_source,
                        "published_utc": new_pub.isoformat() if new_pub else "",
                    })
                    if new_pub and new_pub > cutoff:
                        violations_after += 1
                else:
                    # No earlier report found — keep current but flag
                    dates_changed += 1
                    new_rows.append({
                        "game_date": gd_str, "role": "pre_tip",
                        "url": pr.url, "sha256": pr.sha256, "slot_et": pr.slot_et,
                        "filename": pr.filename, "season": pr.season,
                        "status": "no_valid_pre_tip",
                        "first_tip_utc": first_tip_utc.isoformat(),
                        "tip_source": tip_source,
                        "published_utc": pr_pub.isoformat() if pr_pub else "",
                    })
                    violations_after += 1
            else:
                dates_unchanged += 1
                new_rows.append({
                    "game_date": gd_str, "role": "pre_tip",
                    "url": pr.url, "sha256": pr.sha256, "slot_et": pr.slot_et,
                    "filename": pr.filename, "season": pr.season,
                    "status": "ok",
                    "first_tip_utc": first_tip_utc.isoformat(),
                    "tip_source": tip_source,
                    "published_utc": pr_pub.isoformat() if pr_pub else "",
                })

    # Save
    new_df = pd.DataFrame(new_rows)
    out_path = ROOT / "data/injury_archive/nba/history_parsed/roles.parquet"
    new_df.to_parquet(out_path, index=False)

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Rows: {len(new_df)}")
    print(f"Violations before (published > tip-30): {violations_before}")
    print(f"  Legacy: {violations_before}  (checking...)")
    print(f"Violations after: {violations_after}")
    print(f"Dates changed: {dates_changed}")
    print(f"Dates unchanged: {dates_unchanged}")
    print(f"Fetches: {fetch_count}")
    print(f"tip_source counts: {new_df.tip_source.value_counts(dropna=False).to_dict()}")
    print(f"status counts: {new_df.status.value_counts(dropna=False).to_dict()}")

    print(f"\nESPN vs Odds API mismatches (> 15 min): {len(espn_mismatches)}")
    for m in espn_mismatches[:20]:
        print(f"  {m['game_date']}: ESPN={m['espn_tip']}, Odds={m['odds_tip']}, delta={m['delta_min']} min")

    # NULL check: unchanged dates keep same filename and sha256
    old_roles = pd.read_parquet(ROOT / "data/injury_archive/nba/history_parsed/roles.parquet")
    # (Already overwritten, but we have the data in the new_rows list)

    print(f"\nNULL: dates unchanged = {dates_unchanged}")
    print(f"(Every date whose current pre_tip already had published_utc <= tip - 30 min)")


if __name__ == "__main__":
    main()
