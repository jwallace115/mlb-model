#!/usr/bin/env python3
"""
One-time backfill: ADJ_BB_RATE + ADJ_RUN_SUPP for March 30 – April 10, 2026.

Uses the same pitcher adjusted form cache as the live pipeline.
Matches existing ADJ_CONTACT/ADJ_HH rows to identify games + starters,
then computes the two new signals and appends to shadow_signals_2026.json.

This script should run exactly once. A guard prevents re-execution.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "mlb_sim" / "logs"
SHADOW_PATH = LOG_DIR / "shadow_signals_2026.json"
GT_PATH = PROJECT_ROOT / "sim" / "data" / "game_table.parquet"

# ── Guard: refuse to run twice ──────────────────────────────────────
def _already_backfilled():
    if not SHADOW_PATH.exists():
        return False
    data = json.loads(SHADOW_PATH.read_text())
    return any(r.get("backfilled") and r.get("signal_name") in ("ADJ_BB_RATE", "ADJ_RUN_SUPP")
               for r in data)


def main():
    if _already_backfilled():
        print("Backfill already complete — refusing to run twice.")
        return

    # ── Load existing shadow signals ────────────────────────────────
    records = json.loads(SHADOW_PATH.read_text()) if SHADOW_PATH.exists() else []

    # ── Load adj form cache (same as live pipeline) ─────────────────
    from mlb_sim.pipeline.shadow_signals import _build_adj_form_lookup
    cache = _build_adj_form_lookup()
    print(f"Adj form cache: {len(cache)} pitchers")
    bb_avail = sum(1 for v in cache.values() if v.get("adj_bb_rate_last3") is not None)
    rs_avail = sum(1 for v in cache.values() if v.get("adj_run_suppression_last3") is not None)
    print(f"  adj_bb_rate_last3 available: {bb_avail}")
    print(f"  adj_run_suppression_last3 available: {rs_avail}")

    # ── Find games to backfill from existing ADJ_CONTACT rows ───────
    # Each ADJ_CONTACT row represents a game that was already processed.
    # We use these as the reference for which games exist in the date range.
    date_range = ("2026-03-30", "2026-04-10")
    contact_rows = [r for r in records
                    if r.get("signal_name") == "ADJ_CONTACT"
                    and date_range[0] <= r.get("date", "") <= date_range[1]]
    print(f"ADJ_CONTACT reference rows: {len(contact_rows)}")

    # ── Load V1 signals to identify which games had V1 fire ─────────
    v1_path = LOG_DIR / "signals_2026.json"
    v1_data = json.loads(v1_path.read_text()) if v1_path.exists() else []
    v1_games = {}  # game_id → v1 row
    for v in v1_data:
        d = v.get("date", "")
        if date_range[0] <= d <= date_range[1]:
            v1_games[str(v.get("game_id", ""))] = v

    # ── Load game_table for grading ─────────────────────────────────
    gt = pd.read_parquet(GT_PATH)
    actuals = dict(zip(gt["game_pk"].astype(str), gt["actual_total"]))

    # ── Resolve pitcher IDs from MLB Stats API schedule ────────────
    import requests, time
    starter_map = {}  # game_pk (str) → {"home_pid": int, "away_pid": int}
    unique_dates = sorted(set(r.get("date", "") for r in contact_rows))
    for d in unique_dates:
        try:
            r = requests.get("https://statsapi.mlb.com/api/v1/schedule", params={
                "sportId": 1, "date": d, "hydrate": "probablePitcher"
            }, timeout=15)
            for g in r.json().get("dates", [{}])[0].get("games", []):
                gpk = str(g["gamePk"])
                hp = g.get("teams", {}).get("home", {}).get("probablePitcher", {})
                ap = g.get("teams", {}).get("away", {}).get("probablePitcher", {})
                if hp.get("id") and ap.get("id"):
                    starter_map[gpk] = {"home_pid": hp["id"], "away_pid": ap["id"]}
            time.sleep(0.3)
        except Exception as e:
            print(f"  Schedule fetch failed for {d}: {e}")
    print(f"Starter map from MLB API: {len(starter_map)} games")

    # ── Build backfill rows ─────────────────────────────────────────
    new_rows = []
    skipped = {"no_starters": 0, "no_cache": 0, "no_v1": 0}
    now = datetime.utcnow().isoformat()

    for ref in contact_rows:
        gid = str(ref.get("game_id", ""))
        game_date = ref.get("date", "")
        home_team = ref.get("home_team", "")
        away_team = ref.get("away_team", "")
        closing_total = ref.get("closing_total")
        market_line = ref.get("market_line")
        model_proj = ref.get("model_projection")
        v1_ctx = ref.get("v1_direction_context", "NONE")

        # Get starter pitcher IDs
        starters = starter_map.get(gid, {})
        home_pid = starters.get("home_pid")
        away_pid = starters.get("away_pid")

        if not home_pid or not away_pid:
            skipped["no_starters"] += 1
            continue

        # Look up adj metrics from cache
        home_form = cache.get(home_pid, {})
        away_form = cache.get(away_pid, {})

        for metric, display_name in [
            ("adj_bb_rate_last3", "ADJ_BB_RATE"),
            ("adj_run_suppression_last3", "ADJ_RUN_SUPP"),
        ]:
            h_val = home_form.get(metric)
            a_val = away_form.get(metric)

            if h_val is None or a_val is None:
                skipped["no_cache"] += 1
                continue

            combined = (h_val + a_val) / 2
            favorable = combined > 0

            # Grade from actuals
            actual = actuals.get(gid)
            actual_ou = None
            result = None
            resolved = actual is not None and closing_total is not None

            if resolved:
                actual = float(actual)
                if actual < closing_total:
                    actual_ou = "UNDER"
                elif actual > closing_total:
                    actual_ou = "OVER"
                else:
                    actual_ou = "PUSH"
                if favorable:
                    result = ("WIN" if actual_ou == "UNDER"
                              else "LOSS" if actual_ou == "OVER"
                              else "PUSH")

            row = {
                "game_id": int(gid) if gid.isdigit() else gid,
                "date": game_date,
                "signal_name": display_name,
                "signal_value": round(combined, 6),
                "favorable_zone_flag": favorable,
                "v1_direction_context": v1_ctx,
                "closing_total": closing_total,
                "home_team": home_team,
                "away_team": away_team,
                "market_line": market_line,
                "model_projection": model_proj,
                "home_pitcher_value": h_val,
                "away_pitcher_value": a_val,
                "logged_at": now,
                "actual_total": actual if resolved else None,
                "actual_over_under": actual_ou,
                "result": result,
                "resolved": resolved,
                "shadow_only": True,
                "backfilled": True,
                "backfill_date": "2026-04-10",
                "price_source": "assumed_-110",
            }
            new_rows.append(row)

    # ── Append to existing records (do NOT modify existing rows) ────
    records.extend(new_rows)
    records.sort(key=lambda r: (r.get("date", ""), r.get("game_id", 0), r.get("signal_name", "")))
    SHADOW_PATH.write_text(json.dumps(records, indent=2, default=str))

    # ── Report ──────────────────────────────────────────────────────
    bb_rows = [r for r in new_rows if r["signal_name"] == "ADJ_BB_RATE"]
    rs_rows = [r for r in new_rows if r["signal_name"] == "ADJ_RUN_SUPP"]

    def _report(name, rows):
        fired = [r for r in rows if r["favorable_zone_flag"]]
        graded = [r for r in fired if r["result"] in ("WIN", "LOSS", "PUSH")]
        w = sum(1 for r in graded if r["result"] == "WIN")
        l = sum(1 for r in graded if r["result"] == "LOSS")
        p = sum(1 for r in graded if r["result"] == "PUSH")
        n = w + l
        roi = ((w - l) / n * 100 / 1.1) if n > 0 else 0
        print(f"  {name}: {len(rows)} total, {len(fired)} fired, {len(graded)} graded")
        print(f"    W-L: {w}-{l} (push: {p})")
        print(f"    ROI: {roi:+.1f}% (flat -110 assumption, flagged)")

    print(f"\n{'='*60}")
    print("BACKFILL RESULTS")
    print(f"{'='*60}")
    print(f"Total rows added: {len(new_rows)}")
    _report("ADJ_BB_RATE", bb_rows)
    _report("ADJ_RUN_SUPP", rs_rows)
    print(f"\nSkipped: {skipped}")
    print(f"Date range: {date_range[0]} to {date_range[1]}")
    print(f"Reference games (ADJ_CONTACT rows): {len(contact_rows)}")


if __name__ == "__main__":
    main()
