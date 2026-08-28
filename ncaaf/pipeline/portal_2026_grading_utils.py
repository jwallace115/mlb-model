#!/usr/bin/env python3
"""
NCAAF Portal Overcorrection — 2026 GRADER

UPDATE-ONLY. Never appends a row. Never re-grades a row already marked graded.
Grades ATS against the spread CAPTURED AT LOG TIME, never a re-fetched line.

This is the fix for the defect in ncaaf/pipeline/portal_shock_signal.py, whose
(game_id, team) dedup meant a pre-game row could never be updated with a result.
See registry §3 and spec §5.

Governing spec: research/ncaaf_portal/NCAAF_PORTAL_2026_FROZEN_SPEC.md

    python3 ncaaf/pipeline/portal_2026_grading_utils.py
    python3 ncaaf/pipeline/portal_2026_grading_utils.py --dry-run
    python3 ncaaf/pipeline/portal_2026_grading_utils.py --summary-only
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("portal_2026_grade")

CFBD_KEY = os.getenv("CFBD_API_KEY", "")
CFBD_BASE = "https://api.collegefootballdata.com"
CFBD_HEADERS = {"Authorization": f"Bearer {CFBD_KEY}", "Accept": "application/json"}

SEASON = 2026
LOG_PATH = PROJECT_ROOT / "ncaaf" / "logs" / "portal_2026_shadow.json"

# Flat -110 is TRIAGE ONLY (ops v9 §7 Check 4). CFBD supplies no spread vig.
FLAT_110_WIN = round(100 / 110, 4)   # 0.9091


def cfbd_get(endpoint, params=None):
    url = f"{CFBD_BASE}/{endpoint.lstrip('/')}"
    try:
        r = requests.get(url, headers=CFBD_HEADERS, params=params or {}, timeout=30)
    except requests.RequestException as e:
        logger.error(f"HARD STOP: network error calling {endpoint}: {type(e).__name__}: {e}")
        logger.error("No partial state was written. Safe to re-run once connectivity returns.")
        sys.exit(1)
    if r.status_code != 200:
        logger.error(f"HARD STOP: {endpoint} params={params} -> HTTP {r.status_code}")
        sys.exit(1)
    time.sleep(0.35)
    return r.json()


def summarize(log):
    """Report TIER_1 (the object under test) plus descriptive tier splits."""
    def block(rows, label):
        graded = [r for r in rows if r.get("graded")]
        dec = [r for r in graded if r.get("ats_result") in ("COVER", "NO_COVER")]
        push = sum(1 for r in graded if r.get("ats_result") == "PUSH")
        if not dec:
            logger.info(f"  {label:16s} logged={len(rows):3d} graded={len(graded):3d} "
                        f"(no decided results yet)")
            return
        cov = sum(1 for r in dec if r["ats_result"] == "COVER")
        rate = cov / len(dec)
        prof = sum(FLAT_110_WIN if r["ats_result"] == "COVER" else -1.0 for r in dec)
        logger.info(f"  {label:16s} logged={len(rows):3d} graded={len(graded):3d} "
                    f"ATS {cov}-{len(dec) - cov} (push {push})  cover={rate:.1%}  "
                    f"flat-110 ROI={prof / len(dec):+.1%}  [TRIAGE ONLY]")
        return rate, len(dec)

    logger.info("")
    logger.info("=" * 74)
    logger.info("2026 PORTAL OVERCORRECTION — SHADOW SUMMARY")
    logger.info("=" * 74)
    t1 = [r for r in log if r.get("tier_1_base")]
    res = block(t1, "TIER_1 (TEST)")
    block([r for r in log if r.get("tier_2_strong")], "  tier_2 (desc)")
    block([r for r in log if r.get("tier_3_premium")], "  tier_3 (desc)")

    by_week = {}
    for r in t1:
        if r.get("ats_result") in ("COVER", "NO_COVER"):
            w = by_week.setdefault(r["week"], [0, 0])
            w[0] += 1 if r["ats_result"] == "COVER" else 0
            w[1] += 1
    if by_week:
        logger.info("  by week (spec §5 regime breakdown):")
        for w in sorted(by_week):
            c, n = by_week[w]
            logger.info(f"    week {w}: {c}-{n - c}  cover={c / n:.1%}  N={n}")

    # Pre-registered interpretation — spec §6. Fixed before the season.
    if res:
        rate, n = res
        if n < 20:
            verdict = "TOO EARLY — under 20 decided results"
        elif rate <= 0.45:
            verdict = "FALSIFIED — archive the branch (spec §6)"
        elif rate <= 0.524:
            verdict = "CONSISTENT WITH NO EDGE (spec §6)"
        elif rate <= 0.58:
            verdict = "UNINFORMATIVE at this N — NOT confirmation (spec §6)"
        else:
            verdict = "ENCOURAGING but still uninformative at this N (spec §6)"
        logger.info("")
        logger.info(f"  PRE-REGISTERED READING: {verdict}")
    logger.info("")
    logger.info("  NO CELL IN THE SPEC §6 TABLE AUTHORISES A BET. Shadow only.")
    logger.info("=" * 74)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="compute but do not write")
    ap.add_argument("--summary-only", action="store_true", help="no API calls, report only")
    args = ap.parse_args()

    if not LOG_PATH.exists():
        logger.error(f"HARD STOP: shadow log not found at {LOG_PATH}")
        sys.exit(1)
    log = json.loads(LOG_PATH.read_text())
    logger.info(f"Loaded {len(log)} shadow rows")

    if args.summary_only:
        summarize(log)
        return

    if not CFBD_KEY:
        logger.error("HARD STOP: CFBD_API_KEY not set in .env")
        sys.exit(1)

    ungraded = [r for r in log if not r.get("graded")]
    if not ungraded:
        logger.info("Nothing ungraded.")
        summarize(log)
        return
    logger.info(f"Ungraded rows: {len(ungraded)}")

    # One /games call per distinct week — not per row.
    scores = {}
    for week in sorted({r["week"] for r in ungraded}):
        for g in cfbd_get("/games", {"year": SEASON, "seasonType": "regular", "week": week}):
            hp = g.get("homePoints") if g.get("homePoints") is not None else g.get("home_points")
            ap_ = g.get("awayPoints") if g.get("awayPoints") is not None else g.get("away_points")
            completed = g.get("completed")
            if completed and hp is not None and ap_ is not None:
                scores[g.get("id")] = (hp, ap_)
        logger.info(f"  week {week}: {len(scores)} completed games cached so far")

    now = datetime.now(timezone.utc).isoformat()
    graded_n = skipped_n = 0

    for row in log:
        if row.get("graded"):
            continue                                  # idempotent: never re-grade
        sc = scores.get(row["game_id"])
        if sc is None:
            skipped_n += 1
            continue                                  # not final yet — retry next run
        hp, ap_ = sc
        # ATS from the spread CAPTURED AT LOG TIME (spec §2.7), team perspective.
        team_margin = (hp - ap_) if row["side"] == "home" else (ap_ - hp)
        ats_margin = team_margin + row["spread_captured"]

        if ats_margin > 0:
            result, profit = "COVER", FLAT_110_WIN
        elif ats_margin < 0:
            result, profit = "NO_COVER", -1.0
        else:
            result, profit = "PUSH", 0.0              # research excluded pushes from rates

        row.update({
            "graded": True,
            "graded_at_utc": now,
            "home_points": hp,
            "away_points": ap_,
            "ats_margin": round(ats_margin, 1),
            "ats_result": result,
            "profit_units_flat110": profit,
            "profit_basis": "FLAT_110_TRIAGE_ONLY_NOT_REAL_PRICE",
        })
        graded_n += 1

    logger.info(f"Graded {graded_n} rows; {skipped_n} still awaiting final scores")

    if args.dry_run:
        logger.info("DRY RUN — no write performed")
    elif graded_n:
        LOG_PATH.write_text(json.dumps(log, indent=2, default=str))
        logger.info(f"Updated in place -> {LOG_PATH}")

    summarize(log)


if __name__ == "__main__":
    main()
