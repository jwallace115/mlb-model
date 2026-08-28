#!/usr/bin/env python3
"""
NCAAF Portal Overcorrection — 2026 SHADOW RUNNER (Weeks 1-4)

APPEND-ONLY. This script never grades and never modifies an existing row.
Grading is handled separately by portal_2026_grading_utils.py.

That separation is deliberate. The previous runner
(ncaaf/pipeline/portal_shock_signal.py) deduped on (game_id, team) and wrote
`existing + all_new`, so any row logged pre-game with a null result was filtered
out of `new` on every later run and never updated — it could not grade a forward
shadow at all. See registry §3.

Reads the FROZEN classification. Never recomputes it. If the frozen artifact is
missing, this HARD STOPS (ops v9 Rule 5 — no silent rebuild of prerequisites).

Governing spec: research/ncaaf_portal/NCAAF_PORTAL_2026_FROZEN_SPEC.md

    python3 ncaaf/pipeline/portal_2026_shadow_daily.py            # all weeks 1-4
    python3 ncaaf/pipeline/portal_2026_shadow_daily.py --week 2
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
logger = logging.getLogger("portal_2026_shadow")

CFBD_KEY = os.getenv("CFBD_API_KEY", "")
CFBD_BASE = "https://api.collegefootballdata.com"
CFBD_HEADERS = {"Authorization": f"Bearer {CFBD_KEY}", "Accept": "application/json"}

SEASON = 2026
FROZEN_PATH = PROJECT_ROOT / "ncaaf" / "data" / "portal_2026_classification_frozen.json"
LOG_PATH = PROJECT_ROOT / "ncaaf" / "logs" / "portal_2026_shadow.json"

# ── FROZEN — spec §2.3 / §2.6. Week 0 EXCLUDED (research used week >= 1). ────
DEPLOYMENT_WEEKS = {1, 2, 3, 4}
POWER_CONFERENCES_2026 = {"SEC", "Big Ten", "Big 12", "ACC"}
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
        sys.exit(1)
    time.sleep(0.35)
    return r.json()


def load_frozen():
    if not FROZEN_PATH.exists():
        logger.error("HARD STOP: frozen classification not found at")
        logger.error(f"  {FROZEN_PATH}")
        logger.error("Run portal_2026_freeze_snapshot.py first. This script will NOT")
        logger.error("compute the classification on the fly — doing so would destroy the")
        logger.error("point-in-time guarantee the whole test depends on.")
        sys.exit(1)
    try:
        frozen = json.loads(FROZEN_PATH.read_text())
    except json.JSONDecodeError as e:
        logger.error(f"HARD STOP: frozen artifact is not valid JSON: {e}")
        sys.exit(1)
    required = ("season", "classification", "thresholds", "sha256", "frozen_at_utc")
    missing = [k for k in required if k not in frozen]
    if missing:
        logger.error(f"HARD STOP: frozen artifact is missing required keys: {missing}")
        logger.error("Refusing to run against a malformed classification.")
        sys.exit(1)
    if frozen.get("season") != SEASON:
        logger.error(f"HARD STOP: frozen artifact is for season "
                     f"{frozen.get('season')}, expected {SEASON}")
        sys.exit(1)
    if not isinstance(frozen.get("classification"), dict) or not frozen["classification"]:
        logger.error("HARD STOP: frozen classification is empty or not a mapping")
        sys.exit(1)
    logger.info(f"Frozen classification loaded (frozen_at={frozen.get('frozen_at_utc')})")
    logger.info(f"  sha256={frozen.get('sha256', '')[:16]}...  "
                f"TIER_1 teams={len(frozen.get('tier_1_teams', []))}")
    return frozen


def pick_spread(entry):
    """Replicates the research line rule EXACTLY (phase2_composite_analysis.py
    lines 202-215): prefer any provider containing 'consensus', else the first
    line carrying a spread. Returns (spread, provider, spread_open)."""
    best, best_prov, best_open = None, None, None
    for line in entry.get("lines", []) or []:
        spread = line.get("spread")
        if spread is None:
            continue
        prov = (line.get("provider") or "")
        if best is None or "consensus" in prov.lower():
            best, best_prov = spread, prov
            best_open = line.get("spreadOpen")
    return best, best_prov, best_open


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, default=None, help="single week (default: 1-4)")
    args = ap.parse_args()

    if not CFBD_KEY:
        logger.error("HARD STOP: CFBD_API_KEY not set in .env")
        sys.exit(1)

    # NOTE: `is not None`, not truthiness — week 0 is falsy in Python, so
    # `if args.week` would silently swallow `--week 0` and run 1-4 instead
    # of rejecting it. Week 0 is exactly the identity break (registry R1)
    # this spec exists to close, so it must fail loudly.
    weeks = [args.week] if args.week is not None else sorted(DEPLOYMENT_WEEKS)
    for w in weeks:
        if w not in DEPLOYMENT_WEEKS:
            logger.error(f"HARD STOP: week {w} is outside the frozen window "
                         f"{sorted(DEPLOYMENT_WEEKS)}. Spec §2.3. Refusing.")
            sys.exit(1)

    frozen = load_frozen()
    classification = frozen["classification"]

    existing = json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else []
    existing_keys = {(r["game_id"], r["team"]) for r in existing}
    logger.info(f"Existing shadow log: {len(existing)} rows")

    captured_at = datetime.now(timezone.utc).isoformat()
    new_rows = []

    for week in weeks:
        games = cfbd_get("/games", {"year": SEASON, "seasonType": "regular", "week": week})
        lines_raw = cfbd_get("/lines", {"year": SEASON, "week": week})
        lines_by_game = {}
        for entry in lines_raw:
            sp, prov, sp_open = pick_spread(entry)
            if sp is not None:
                lines_by_game[entry.get("id")] = (sp, prov, sp_open)

        wk_new = 0
        for g in games:
            gid = g.get("id")
            if g.get("week") != week:
                continue
            if gid not in lines_by_game:
                continue                                  # spec §2.4: no spread -> not logged
            spread_home, provider, spread_open_home = lines_by_game[gid]

            home = g.get("homeTeam") or g.get("home_team")
            away = g.get("awayTeam") or g.get("away_team")
            cls_home = (g.get("homeClassification") or g.get("home_classification") or "").lower()
            cls_away = (g.get("awayClassification") or g.get("away_classification") or "").lower()

            for side, team, opp, team_cls in (
                ("home", home, away, cls_home),
                ("away", away, home, cls_away),
            ):
                if not team or (gid, team) in existing_keys:
                    continue
                if team_cls != "fbs":                     # spec §2.4 FBS-only filter
                    continue
                meta = classification.get(team)
                if not meta or not meta.get("tier_1_base"):
                    continue                              # only TIER_1 qualifiers logged

                team_spread = spread_home if side == "home" else -spread_home
                team_open = (spread_open_home if side == "home"
                             else (-spread_open_home if spread_open_home is not None else None))
                favored = team_spread < 0
                abs_spread = abs(team_spread)
                conf = meta.get("conference") or ""
                power = conf in POWER_CONFERENCES_2026
                tier_2 = favored
                tier_3 = tier_2 and power and 3.0 <= abs_spread <= 14.0

                new_rows.append({
                    "game_id": gid,
                    "season": SEASON,
                    "week": week,
                    "kickoff_utc": g.get("startDate") or g.get("start_date"),
                    "team": team,
                    "opponent": opp,
                    "side": side,
                    "conference": conf,
                    # ── frozen classification, copied not recomputed ──
                    "net_star_shock": meta.get("net_star_shock"),
                    "returning_ppa": meta.get("returning_ppa"),
                    "negative_shock_flag": True,
                    "high_returning_flag": True,
                    # ── tiers (spec §2.5) ──
                    "tier_1_base": True,
                    "tier_2_strong": bool(tier_2),
                    "tier_3_premium": bool(tier_3),
                    "highest_tier": ("TIER_3_PREMIUM" if tier_3
                                     else "TIER_2_STRONG" if tier_2 else "TIER_1_BASE"),
                    "favored_flag": bool(favored),
                    "power_tier_flag": bool(power),
                    # ── line capture (spec §2.7) ──
                    "spread_captured": round(float(team_spread), 1),
                    "spread_open": (round(float(team_open), 1)
                                    if team_open is not None else None),
                    "line_provider": provider,
                    "line_captured_at_utc": captured_at,
                    "price_source": "CFBD_NO_JUICE",
                    "price_spread": None,
                    # ── grading fields, populated ONLY by the grader ──
                    "graded": False,
                    "graded_at_utc": None,
                    "home_points": None,
                    "away_points": None,
                    "ats_margin": None,
                    "ats_result": None,
                    "profit_units_flat110": None,
                    # ── provenance ──
                    "spec_version": SPEC_VERSION,
                    "frozen_sha256": frozen.get("sha256"),
                    "logged_at_utc": captured_at,
                })
                existing_keys.add((gid, team))
                wk_new += 1

        logger.info(f"  week {week}: {len(games)} games, "
                    f"{len(lines_by_game)} with spreads, {wk_new} new TIER_1 rows")

    if not new_rows:
        logger.info("No new qualifying rows. Log unchanged.")
    else:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(json.dumps(existing + new_rows, indent=2, default=str))
        logger.info(f"Appended {len(new_rows)} rows -> {LOG_PATH} "
                    f"({len(existing) + len(new_rows)} total)")

    log = json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else []
    t1 = [r for r in log if r.get("tier_1_base")]
    graded = [r for r in t1 if r.get("graded")]
    cov = sum(1 for r in graded if r.get("ats_result") == "COVER")
    nocov = sum(1 for r in graded if r.get("ats_result") == "NO_COVER")
    logger.info(f"TIER_1 rows: {len(t1)} logged, {len(graded)} graded, ATS {cov}-{nocov}")
    logger.info("SHADOW ONLY — no capital, no promotion. Spec §6: this test cannot confirm.")


if __name__ == "__main__":
    main()
