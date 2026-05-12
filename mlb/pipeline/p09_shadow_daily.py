#!/usr/bin/env python3
"""
P09 Standalone Shadow Runner — Contact Suppression UNDER
==========================================================
Computes P09 = avg(home_hh_r5, away_hh_r5) * park_run_factor for today's
MLB slate.  LOW P09 scores (<= 31.7305) predict UNDER.

Shadow-only.  No live betting.  No promotion.  No V1 dependency.

Usage:
  python3 mlb/pipeline/p09_shadow_daily.py --dry-run
  python3 mlb/pipeline/p09_shadow_daily.py --date 2026-05-10 --dry-run
  python3 mlb/pipeline/p09_shadow_daily.py --date 2026-05-12          # production
"""

# ═══════════════════════════════════════════════════════════════════════════════
# P09 IMPORT / DEPENDENCY CONTRACT
# ═══════════════════════════════════════════════════════════════════════════════
# Every non-stdlib import is listed here with justification.
#
#   pandas          — DataFrame ops for Statcast rolling features
#   config.STADIUMS — park_factor lookup (static dict, no V1 dependency)
#   config.ODDS_API_TEAM_MAP — map Odds API full names to team abbreviations
#   modules.schedule.fetch_schedule — MLB Stats API schedule + probable starters
#   mlb_sim.pipeline.p09_overlay.compute_p09 — canonical P09 formula
#       (pure function: (home_hh, away_hh, park_rf) -> float; no V1 imports)
#   mlb_sim.pipeline.p09_overlay._load_config — loads p09_overlay_config.json
#       (reads cutoff from frozen config; no V1 imports)
#
# PROHIBITED (must never appear):
#   mlb_sim.pipeline.daily_signal_generator
#   mlb_sim.pipeline.line_snapshot_store
#   any V1 Ridge / edge module
# ═══════════════════════════════════════════════════════════════════════════════

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("p09_shadow")

# ── Paths (from pre-flight verification artifact) ────────────────────────────
STATCAST_PATH = PROJECT_ROOT / "research" / "statcast_enrichment" / "pitcher_statcast_per_start.parquet"
ODDS_CACHE_DIR = PROJECT_ROOT / "data" / "cache"
PRODUCTION_LOG = PROJECT_ROOT / "mlb" / "logs" / "p09_shadow_2026.json"
DRYRUN_LOG = PROJECT_ROOT / "mlb" / "logs" / "p09_shadow_2026_dryrun.json"

# ── Constants ─────────────────────────────────────────────────────────────────
CANONICAL_SPORTSBOOK = "DraftKings"
FROZEN_CUTOFF = 31.7305


def _load_cutoff():
    """Load cutoff from p09_overlay_config.json and verify it matches frozen value."""
    from mlb_sim.pipeline.p09_overlay import _load_config
    cfg = _load_config()
    return cfg["p09_cutoff_bottom20"]


def _load_statcast():
    """Load pitcher Statcast aggregate and sort for rolling computation."""
    df = pd.read_parquet(STATCAST_PATH)
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values(["pitcher_id", "game_date"])
    return df


def _compute_rolling_hh(statcast_df, pitcher_id, before_date):
    """
    Compute PIT-safe rolling 5-start hard-hit rate for a pitcher.

    Uses shift(1).rolling(5, min_periods=3).mean() on all appearances
    with game_date < before_date.

    Returns (float_value, pit_flags_dict) or (None, pit_flags_dict).
    """
    pdf = statcast_df[
        (statcast_df["pitcher_id"] == pitcher_id) &
        (statcast_df["game_date"] < before_date)
    ]

    pit_flags = {
        "shift1_applied": True,
        "rolling_window": 5,
        "min_periods": 3,
        "prior_starts_only": True,
        "appearances_available": len(pdf),
    }

    if len(pdf) < 3:
        pit_flags["insufficient_history"] = True
        return None, pit_flags

    # shift(1) excludes the most recent row; rolling(5,3) averages
    rolled = pdf["hard_hit_rate"].shift(1).rolling(5, min_periods=3).mean()
    val = rolled.iloc[-1]

    if pd.isna(val):
        pit_flags["rolled_to_nan"] = True
        return None, pit_flags

    return float(val), pit_flags


def _load_dk_market(game_date_str):
    """
    Load DraftKings full-game totals from raw odds cache.

    Source: data/cache/odds_full_YYYY-MM-DD.json
    Filter: bookmakers[].key == "draftkings" -> markets[].key == "totals"

    Returns dict keyed by (home_abb, away_abb) with market data.
    Also returns alt-book data (fanduel, pinnacle) if found.
    """
    cache_file = ODDS_CACHE_DIR / f"odds_full_{game_date_str}.json"
    if not cache_file.exists():
        logger.warning(f"Raw odds cache not found: {cache_file}")
        return {}, str(cache_file)

    from config import ODDS_API_TEAM_MAP

    with open(cache_file) as f:
        games = json.load(f)

    market_map = {}
    for g in games:
        home_full = g.get("home_team", "")
        away_full = g.get("away_team", "")
        home_abb = ODDS_API_TEAM_MAP.get(home_full, home_full)
        away_abb = ODDS_API_TEAM_MAP.get(away_full, away_full)
        key = (home_abb, away_abb)

        entry = {
            "dk_total": None, "dk_over": None, "dk_under": None,
            "dk_timestamp": None, "alt_books": [],
        }

        for bm in g.get("bookmakers", []):
            book_key = bm.get("key", "")
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "totals":
                    continue
                total_line = None
                over_price = None
                under_price = None
                for oc in mkt.get("outcomes", []):
                    if oc["name"] == "Over":
                        total_line = oc.get("point")
                        over_price = oc.get("price")
                    elif oc["name"] == "Under":
                        under_price = oc.get("price")

                if total_line is None:
                    continue

                if book_key == "draftkings":
                    entry["dk_total"] = total_line
                    entry["dk_over"] = over_price
                    entry["dk_under"] = under_price
                    entry["dk_timestamp"] = bm.get("last_update")
                else:
                    entry["alt_books"].append({
                        "book": book_key,
                        "total_line": total_line,
                        "over_price": over_price,
                        "under_price": under_price,
                        "last_update": bm.get("last_update"),
                    })

        market_map[key] = entry

    return market_map, str(cache_file)


def _load_shadow_log(path):
    """Load existing shadow log entries."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return []
    return []


def _save_shadow_log(entries, path):
    """Save shadow log entries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, default=str))


def _selfcheck(cutoff, odds_cache_path, output_path, dry_run):
    """
    Runtime self-checks. Returns list of failure messages (empty = pass).
    """
    failures = []

    if cutoff != FROZEN_CUTOFF:
        failures.append(f"Cutoff mismatch: config={cutoff}, frozen={FROZEN_CUTOFF}")

    if not STATCAST_PATH.exists():
        failures.append(f"Statcast file missing: {STATCAST_PATH}")

    if dry_run and output_path == PRODUCTION_LOG:
        failures.append("Dry-run targeting production log path")

    return failures


def main():
    parser = argparse.ArgumentParser(description="P09 Standalone Shadow Runner")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Write to dryrun path only")
    parser.add_argument("--output", default=None, help="Override output path")
    args = parser.parse_args()

    game_date_str = args.date or date.today().isoformat()
    game_date_ts = pd.Timestamp(game_date_str)
    run_ts = datetime.now(timezone.utc).isoformat()

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    elif args.dry_run:
        output_path = DRYRUN_LOG
    else:
        output_path = PRODUCTION_LOG

    logger.info(f"P09 Shadow Runner — {game_date_str} ({'DRY-RUN' if args.dry_run else 'PRODUCTION'})")

    # ── Load cutoff from config ──
    cutoff = _load_cutoff()

    # ── Self-checks ──
    failures = _selfcheck(cutoff, ODDS_CACHE_DIR, output_path, args.dry_run)
    if failures:
        for f in failures:
            logger.error(f"SELF-CHECK FAIL: {f}")
        sys.exit(1)

    # ── Load schedule ──
    from modules.schedule import fetch_schedule
    games = fetch_schedule(game_date_str)
    if not games:
        logger.warning("No games today.")
        return

    logger.info(f"Games on slate: {len(games)}")

    # ── Load Statcast ──
    sc = _load_statcast()
    sc_max_date = sc["game_date"].max()
    logger.info(f"Statcast max date: {sc_max_date.date()}")

    # ── Load DraftKings market ──
    dk_map, odds_cache_file = _load_dk_market(game_date_str)

    # ── Load park factors ──
    from config import STADIUMS
    park_factors = {team: info["park_factor"] for team, info in STADIUMS.items()}

    # ── Import compute_p09 ──
    from mlb_sim.pipeline.p09_overlay import compute_p09

    # ── Build data_version ──
    data_version = (
        f"runner:p09_shadow_daily_v1"
        f"|config_cutoff:{cutoff}"
        f"|statcast:{sc_max_date.date()}"
        f"|odds_cache:{Path(odds_cache_file).name}"
    )

    # ── Process games ──
    new_entries = []
    stats = {"processed": 0, "signals": 0, "dk_found": 0, "dk_missing": 0,
             "pit_skipped": 0, "starter_unavailable": 0}

    for g in games:
        home = g["home_team"]
        away = g["away_team"]
        game_pk = g["game_pk"]
        home_sp = g.get("home_probable_pitcher") or {}
        away_sp = g.get("away_probable_pitcher") or {}
        home_sp_id = home_sp.get("id")
        away_sp_id = away_sp.get("id")
        home_sp_name = home_sp.get("name", "TBD")
        away_sp_name = away_sp.get("name", "TBD")

        notes = []

        # Skip if either starter unavailable
        if home_sp_id is None or away_sp_id is None:
            notes.append("STARTER_UNAVAILABLE")
            stats["starter_unavailable"] += 1
            logger.info(f"  {away}@{home}: SKIP — starter unavailable")
            continue

        # Park factor
        park_rf = park_factors.get(home)
        if park_rf is None:
            park_rf = 100
            notes.append("PARK_FACTOR_MISSING_USED_100")

        # Rolling hard-hit features
        home_hh, home_pit = _compute_rolling_hh(sc, home_sp_id, game_date_ts)
        away_hh, away_pit = _compute_rolling_hh(sc, away_sp_id, game_date_ts)

        if home_hh is None or away_hh is None:
            stats["pit_skipped"] += 1
            skip_who = []
            if home_hh is None:
                skip_who.append(f"home:{home_sp_name}")
            if away_hh is None:
                skip_who.append(f"away:{away_sp_name}")
            notes.append(f"INSUFFICIENT_HISTORY:{','.join(skip_who)}")
            logger.info(f"  {away}@{home}: SKIP — insufficient hard-hit history for {', '.join(skip_who)}")
            continue

        # Compute P09
        p09_score = compute_p09(home_hh, away_hh, park_rf)
        signal_fired = p09_score is not None and p09_score <= cutoff

        # DraftKings market
        dk = dk_map.get((home, away), {})
        dk_total = dk.get("dk_total")
        dk_over = dk.get("dk_over")
        dk_under = dk.get("dk_under")
        dk_ts = dk.get("dk_timestamp")
        alt_books = dk.get("alt_books", [])

        if dk_total is not None:
            market_status = "OK"
            stats["dk_found"] += 1
        else:
            market_status = "DRAFTKINGS_MISSING"
            stats["dk_missing"] += 1

        # selected_side logic
        if signal_fired and dk_total is not None:
            selected_side = "UNDER"
        else:
            selected_side = None

        # PIT safety flags
        pit_safety_flags = {
            "shift1_applied": True,
            "rolling_window": 5,
            "min_periods": 3,
            "starter_source": "schedule_api_probable_pitcher_id",
            "home_starter_pit": home_pit,
            "away_starter_pit": away_pit,
        }

        entry = {
            "date": game_date_str,
            "game_id": str(game_pk),
            "away_team": away,
            "home_team": home,
            "away_starter": away_sp_name,
            "home_starter": home_sp_name,
            "away_hard_hit_rate_rolling5": round(away_hh, 6),
            "home_hard_hit_rate_rolling5": round(home_hh, 6),
            "park_run_factor": park_rf,
            "p09_score": round(p09_score, 4) if p09_score is not None else None,
            "cutoff": cutoff,
            "signal_fired": signal_fired,
            "canonical_sportsbook": CANONICAL_SPORTSBOOK,
            "market_total": dk_total,
            "price_over": dk_over,
            "price_under": dk_under,
            "market_timestamp": dk_ts,
            "market_status": market_status,
            "alt_books": alt_books,
            "selected_side": selected_side,
            "actual_total": None,
            "result": None,
            "graded": False,
            "created_at": run_ts,
            "updated_at": None,
            "data_version": data_version,
            "pit_safety_flags": pit_safety_flags,
            "source_files": {
                "statcast": str(STATCAST_PATH),
                "odds_cache": odds_cache_file,
            },
            "notes": notes,
        }
        new_entries.append(entry)
        stats["processed"] += 1
        if signal_fired:
            stats["signals"] += 1

        fire_tag = " *** SIGNAL ***" if signal_fired else ""
        logger.info(f"  {away}@{home}: p09={p09_score:.4f} dk={dk_total}{fire_tag}")

    # ── Merge with existing log (dedup by date+game_id) ──
    existing = _load_shadow_log(output_path)
    new_keys = {(e["date"], e["game_id"]) for e in new_entries}

    # Handle late DK fill: if existing row has DRAFTKINGS_MISSING and new has DK data
    updated_existing = []
    for ex in existing:
        ex_key = (ex.get("date"), ex.get("game_id"))
        if ex_key in new_keys:
            new_match = next(n for n in new_entries if (n["date"], n["game_id"]) == ex_key)
            if (ex.get("market_status") == "DRAFTKINGS_MISSING"
                    and new_match.get("market_status") == "OK"):
                # Fill late DK data into existing row
                ex["market_total"] = new_match["market_total"]
                ex["price_over"] = new_match["price_over"]
                ex["price_under"] = new_match["price_under"]
                ex["market_timestamp"] = new_match["market_timestamp"]
                ex["market_status"] = "FILLED_LATE"
                ex["updated_at"] = run_ts
                if ex.get("signal_fired") and ex["market_total"] is not None:
                    ex["selected_side"] = "UNDER"
                ex.setdefault("notes", []).append("DRAFTKINGS_FILLED_LATE")
                updated_existing.append(ex)
                new_keys.discard(ex_key)
                new_entries = [n for n in new_entries if (n["date"], n["game_id"]) != ex_key]
            # else: new entry replaces existing (dedup)
        else:
            updated_existing.append(ex)

    combined = updated_existing + new_entries

    # ── Write output ──
    _save_shadow_log(combined, output_path)
    logger.info(f"Output: {output_path} ({len(combined)} total entries)")

    # ── Summary ──
    print(f"\n=== P09 SHADOW {'DRY-RUN' if args.dry_run else 'CARD'} [{game_date_str}] ===\n")
    print(f"Games on slate:      {len(games)}")
    print(f"Processed:           {stats['processed']}")
    print(f"Signals fired:       {stats['signals']}")
    print(f"DraftKings market:   {stats['dk_found']}")
    print(f"DK missing:          {stats['dk_missing']}")
    print(f"PIT skipped:         {stats['pit_skipped']}")
    print(f"Starter unavailable: {stats['starter_unavailable']}")
    print(f"Data version:        {data_version}")

    if stats["signals"] > 0:
        print("\nSignals:")
        for e in new_entries:
            if e["signal_fired"]:
                dk_str = f"DK total={e['market_total']}" if e["market_total"] else "no DK"
                print(f"  {e['away_team']}@{e['home_team']} | p09={e['p09_score']:.4f} | {dk_str}")

    print(f"\nOutput: {output_path}")


if __name__ == "__main__":
    main()
