#!/usr/bin/env python3
"""
NCAAF Portal Overcorrection — 2026 CLASSIFICATION FREEZE (one-time, pre-season)

Pulls CFBD portal + returning-production + FBS team data for 2026, computes the
Bucket B classification, and writes it ONCE to an immutable artifact.

WHY THIS EXISTS
---------------
The 2022-2025 backtest fails Check 1b (net_star_shock built from a completed
season's full portal list) and Check 2 (Bucket B selected as best-of-six on the
same data). See research/ncaaf_portal/ncaaf_portal_system_registry_v1.md.

A forward test escapes both ONLY IF the classification provably predates every
game it is scored against. That property is created here and destroyed by any
recomputation. Hence: WRITE ONCE, NEVER REGENERATE.

Governing spec: research/ncaaf_portal/NCAAF_PORTAL_2026_FROZEN_SPEC.md

RUN BEFORE THE FIRST WEEK 1 KICKOFF:
    python3 ncaaf/pipeline/portal_2026_freeze_snapshot.py

Output: ncaaf/data/portal_2026_classification_frozen.json
"""

import hashlib
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
load_dotenv(PROJECT_ROOT / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("portal_freeze")

CFBD_KEY = os.getenv("CFBD_API_KEY", "")
CFBD_BASE = "https://api.collegefootballdata.com"
CFBD_HEADERS = {"Authorization": f"Bearer {CFBD_KEY}", "Accept": "application/json"}

SEASON = 2026
OUT_PATH = PROJECT_ROOT / "ncaaf" / "data" / "portal_2026_classification_frozen.json"

# ── FROZEN PARAMETERS — see NCAAF_PORTAL_2026_FROZEN_SPEC.md §2.1 ────────────
# Source: research/ncaaf_portal/phase2_composite_test.md, Metric Definitions.
# NOTE: phase1 reports Q25 = -28.0 over 544 team-seasons; phase2 reports -29.0
# over 534. The two research docs disagree. -29.0 is frozen because it is the
# value in the artifact that produced the 56.4% headline under test.
NET_STAR_SHOCK_THRESHOLD = -29.0
RETURNING_PPA_THRESHOLD = 0.551

SPEC_VERSION = "NCAAF_PORTAL_2026_FROZEN_SPEC v1 (2026-08-28)"


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
        logger.error(f"  body: {r.text[:300]}")
        sys.exit(1)
    time.sleep(0.35)
    return r.json()


def main():
    # ── Rule 5: no silent overwrite of a frozen artifact ─────────────────────
    if OUT_PATH.exists():
        logger.error("HARD STOP: frozen classification already exists at")
        logger.error(f"  {OUT_PATH}")
        logger.error("This artifact is WRITE-ONCE by design. Regenerating it destroys the")
        logger.error("point-in-time guarantee that makes the 2026 forward test clean.")
        logger.error("If you genuinely need to rebuild it, move the existing file aside")
        logger.error("manually and record why in the spec. Do not add a --force flag.")
        sys.exit(1)

    if not CFBD_KEY:
        logger.error("HARD STOP: CFBD_API_KEY not set in .env")
        sys.exit(1)

    logger.info(f"Freezing {SEASON} portal classification...")
    logger.info(f"  thresholds: net_star_shock <= {NET_STAR_SHOCK_THRESHOLD}, "
                f"percentPPA >= {RETURNING_PPA_THRESHOLD}")

    # ── 1. FBS team universe (spec §2.4) ─────────────────────────────────────
    fbs_raw = cfbd_get("/teams/fbs", {"year": SEASON})
    if not fbs_raw:
        logger.error("HARD STOP: /teams/fbs returned no rows for 2026")
        sys.exit(1)
    fbs_teams = {t["school"]: (t.get("conference") or "") for t in fbs_raw if t.get("school")}
    logger.info(f"  FBS teams {SEASON}: {len(fbs_teams)}")

    # ── 2. Transfer portal ───────────────────────────────────────────────────
    transfers = cfbd_get("/player/portal", {"year": SEASON})
    if not transfers:
        logger.error("HARD STOP: /player/portal returned no rows for 2026.")
        logger.error("Either the portal class is not yet populated or the endpoint changed.")
        logger.error("Do NOT proceed with an empty portal set — every team would score 0.")
        sys.exit(1)
    logger.info(f"  portal transfers {SEASON}: {len(transfers)}")

    in_stars, out_stars, in_ct, out_ct = {}, {}, {}, {}
    stars_present = 0
    for t in transfers:
        stars = t.get("stars") or 0          # research convention: null -> 0
        if t.get("stars"):
            stars_present += 1
        dest, origin = t.get("destination"), t.get("origin")
        if dest:
            in_stars[dest] = in_stars.get(dest, 0) + stars
            in_ct[dest] = in_ct.get(dest, 0) + 1
        if origin:
            out_stars[origin] = out_stars.get(origin, 0) + stars
            out_ct[origin] = out_ct.get(origin, 0) + 1
    logger.info(f"  transfers with a star rating: {stars_present} "
                f"({stars_present / len(transfers):.1%})")

    # ── 3. Returning production ──────────────────────────────────────────────
    returning = cfbd_get("/player/returning", {"year": SEASON})
    if not returning:
        logger.error("HARD STOP: /player/returning returned no rows for 2026.")
        sys.exit(1)
    ppa_by_team = {}
    for r in returning:
        team, ppa = r.get("team"), r.get("percentPPA")
        if team and ppa is not None:
            ppa_by_team[team] = float(ppa)
    logger.info(f"  teams with percentPPA: {len(ppa_by_team)}")

    # ── 4. Classify (FBS only, spec §2.4) ────────────────────────────────────
    classification, missing_ppa = {}, []
    for team, conf in sorted(fbs_teams.items()):
        net = in_stars.get(team, 0) - out_stars.get(team, 0)
        ppa = ppa_by_team.get(team)
        if ppa is None:
            missing_ppa.append(team)
        neg_shock = net <= NET_STAR_SHOCK_THRESHOLD
        high_ret = (ppa is not None) and (ppa >= RETURNING_PPA_THRESHOLD)
        classification[team] = {
            "conference": conf,
            "portal_in_stars": in_stars.get(team, 0),
            "portal_out_stars": out_stars.get(team, 0),
            "portal_in_count": in_ct.get(team, 0),
            "portal_out_count": out_ct.get(team, 0),
            "net_star_shock": net,
            "returning_ppa": ppa,
            "negative_shock": neg_shock,
            "high_returning": high_ret,
            "tier_1_base": bool(neg_shock and high_ret),
        }

    qualifying = sorted(t for t, v in classification.items() if v["tier_1_base"])
    logger.info(f"  NEGATIVE_SHOCK teams: "
                f"{sum(1 for v in classification.values() if v['negative_shock'])}")
    logger.info(f"  TIER_1 (NEG_SHOCK + HIGH_RET): {len(qualifying)}")
    if missing_ppa:
        logger.warning(f"  {len(missing_ppa)} FBS teams missing percentPPA "
                       f"(cannot qualify): {', '.join(missing_ppa[:12])}"
                       f"{' ...' if len(missing_ppa) > 12 else ''}")

    # ── 5. Sanity gate — spec §6 expects ~34-107 qualifying team-seasons ─────
    if len(qualifying) == 0:
        logger.error("HARD STOP: zero qualifying teams. Thresholds or data are wrong.")
        sys.exit(1)
    if len(qualifying) > 60:
        logger.warning(f"  {len(qualifying)} qualifying teams is well above the "
                       f"2022-2025 range (9-27 teams/season). Verify before trusting.")

    payload_core = {
        "season": SEASON,
        "spec_version": SPEC_VERSION,
        "thresholds": {
            "net_star_shock_max": NET_STAR_SHOCK_THRESHOLD,
            "returning_ppa_min": RETURNING_PPA_THRESHOLD,
        },
        "classification": classification,
    }
    digest = hashlib.sha256(
        json.dumps(payload_core, sort_keys=True, default=str).encode()
    ).hexdigest()

    out = dict(payload_core)
    out["frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    out["sha256"] = digest
    out["source_endpoints"] = {
        "teams_fbs": f"{CFBD_BASE}/teams/fbs?year={SEASON}",
        "player_portal": f"{CFBD_BASE}/player/portal?year={SEASON}",
        "player_returning": f"{CFBD_BASE}/player/returning?year={SEASON}",
    }
    out["source_counts"] = {
        "fbs_teams": len(fbs_teams),
        "transfers": len(transfers),
        "returning_rows": len(returning),
    }
    out["tier_1_teams"] = qualifying
    out["immutability_note"] = (
        "WRITE ONCE. This artifact is the point-in-time guarantee for the 2026 "
        "forward test. Regenerating it after any Week 1-4 game has kicked off "
        "voids the out-of-sample status of the entire test."
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2, default=str))

    logger.info("")
    logger.info(f"FROZEN -> {OUT_PATH}")
    logger.info(f"  sha256: {digest}")
    logger.info(f"  TIER_1 teams ({len(qualifying)}): {', '.join(qualifying)}")
    logger.info("")
    logger.info("NEXT: commit and push this file BEFORE the first Week 1 kickoff.")
    logger.info("A frozen artifact that only exists locally is not a guarantee.")


if __name__ == "__main__":
    main()
