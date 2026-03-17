#!/usr/bin/env python3
"""
MLB CLV Shadow Audit — 7 checks + SAFE / NOT SAFE verdict.

Validates the end-to-end MLB CLV pipeline before trusting the numbers:
  1. graded_results has CLV columns
  2. line_movement.csv has close_total values (at least some)
  3. clv_directional values are in plausible range (−3 to +3)
  4. CLV coverage ≥ 50% of was_a_play rows in the last 14d
  5. Decision line (graded_results.line) matches line_movement.csv open_total
  6. snapshot_source values are expected strings
  7. No duplicate game_pk+game_date in graded_results with CLV data

Usage:
  python mlb_shadow_clv_audit.py
  python mlb_shadow_clv_audit.py --days 30
  python mlb_shadow_clv_audit.py --date 2026-04-01
"""

import argparse
import csv
import os
import sys
from datetime import date, timedelta

import db
from config import DATA_DIR

LINE_CSV = os.path.join(DATA_DIR, "line_movement.csv")

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"


def _check(label: str, status: str, detail: str = "") -> dict:
    symbol = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}.get(status, "?")
    print(f"  {symbol} [{status}] {label}" + (f" — {detail}" if detail else ""))
    return {"label": label, "status": status, "detail": detail}


def run_audit(days: int = 14, target_date: str | None = None) -> bool:
    """
    Run all 7 CLV audit checks. Returns True if SAFE to trust CLV numbers.
    """
    db.init_db()
    results = []

    cutoff = (
        target_date
        if target_date
        else (date.today() - timedelta(days=days)).isoformat()
    )

    print(f"\n{'='*60}")
    print(f"  MLB CLV SHADOW AUDIT — since {cutoff}")
    print(f"{'='*60}\n")

    # ── Check 1: graded_results has CLV columns ───────────────────────────────
    try:
        with db.get_conn() as conn:
            cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(graded_results)"
            ).fetchall()]
        clv_cols = {"closing_line", "clv_raw", "clv_directional", "snapshot_source"}
        missing  = clv_cols - set(cols)
        if missing:
            results.append(_check("CLV columns in graded_results", FAIL,
                                  f"missing: {missing}"))
        else:
            results.append(_check("CLV columns in graded_results", PASS,
                                  "closing_line, clv_raw, clv_directional, snapshot_source"))
    except Exception as e:
        results.append(_check("CLV columns in graded_results", FAIL, str(e)))

    # ── Check 2: line_movement.csv has close_total ────────────────────────────
    try:
        if not os.path.exists(LINE_CSV):
            results.append(_check("line_movement.csv exists", FAIL, "file not found"))
        else:
            with open(LINE_CSV, newline="") as f:
                rows = list(csv.DictReader(f))
            recent = [r for r in rows if r.get("date", "") >= cutoff]
            with_close = [r for r in recent if r.get("close_total", "") not in ("", None)]
            if not recent:
                results.append(_check("line_movement.csv close_total", SKIP,
                                      f"no rows since {cutoff} — spring training?"))
            elif not with_close:
                results.append(_check("line_movement.csv close_total", WARN,
                                      f"{len(recent)} recent rows, 0 with close_total "
                                      f"— refresh.py not yet captured closing lines"))
            else:
                results.append(_check("line_movement.csv close_total", PASS,
                                      f"{len(with_close)}/{len(recent)} recent games have close_total"))
    except Exception as e:
        results.append(_check("line_movement.csv close_total", FAIL, str(e)))

    # ── Check 3: clv_directional in plausible range ───────────────────────────
    try:
        with db.get_conn() as conn:
            clv_rows = conn.execute("""
                SELECT clv_directional FROM graded_results
                WHERE game_date >= ? AND clv_directional IS NOT NULL
            """, (cutoff,)).fetchall()
        vals = [r[0] for r in clv_rows]
        if not vals:
            results.append(_check("CLV directional range", SKIP,
                                  "no CLV values yet (need closing lines from refresh.py)"))
        else:
            out_of_range = [v for v in vals if abs(v) > 3.0]
            if out_of_range:
                results.append(_check("CLV directional range", WARN,
                                      f"{len(out_of_range)} values outside ±3.0: "
                                      f"min={min(vals):.2f} max={max(vals):.2f}"))
            else:
                results.append(_check("CLV directional range", PASS,
                                      f"n={len(vals)} values, range [{min(vals):.2f}, {max(vals):.2f}]"))
    except Exception as e:
        results.append(_check("CLV directional range", FAIL, str(e)))

    # ── Check 4: CLV coverage ≥ 50% of plays ─────────────────────────────────
    try:
        with db.get_conn() as conn:
            n_plays = conn.execute("""
                SELECT COUNT(*) FROM graded_results
                WHERE game_date >= ? AND was_a_play = 1
            """, (cutoff,)).fetchone()[0]
            n_clv = conn.execute("""
                SELECT COUNT(*) FROM graded_results
                WHERE game_date >= ? AND was_a_play = 1
                  AND clv_directional IS NOT NULL
            """, (cutoff,)).fetchone()[0]
        if n_plays == 0:
            results.append(_check("CLV coverage ≥ 50%", SKIP, "no play rows yet"))
        elif n_clv == 0:
            # Check if close_total is also empty (spring training / pre-season)
            no_close_in_csv = not any(
                r.get("close_total", "") not in ("", None)
                for r in ([] if not os.path.exists(LINE_CSV) else
                          list(csv.DictReader(open(LINE_CSV, newline=""))))
                if r.get("date", "") >= cutoff
            )
            if no_close_in_csv:
                results.append(_check("CLV coverage ≥ 50%", WARN,
                                      f"0/{n_plays} plays have CLV — expected: "
                                      "no closing lines captured yet (spring training / pre-season)"))
            else:
                results.append(_check("CLV coverage ≥ 50%", FAIL,
                                      f"0/{n_plays} plays have CLV despite close_total present in CSV "
                                      "— grader join may be broken"))
        else:
            pct = n_clv / n_plays * 100
            if pct >= 50:
                results.append(_check("CLV coverage ≥ 50%", PASS,
                                      f"{n_clv}/{n_plays} plays = {pct:.1f}%"))
            elif pct >= 20:
                results.append(_check("CLV coverage ≥ 50%", WARN,
                                      f"{n_clv}/{n_plays} plays = {pct:.1f}% (below 50% target)"))
            else:
                results.append(_check("CLV coverage ≥ 50%", FAIL,
                                      f"{n_clv}/{n_plays} plays = {pct:.1f}%"))
    except Exception as e:
        results.append(_check("CLV coverage ≥ 50%", FAIL, str(e)))

    # ── Check 5: decision line matches line_movement.csv open_total ───────────
    try:
        if not os.path.exists(LINE_CSV):
            results.append(_check("Decision line vs open_total alignment", SKIP,
                                  "line_movement.csv not found"))
        else:
            with open(LINE_CSV, newline="") as f:
                csv_rows = {str(r["game_id"]): r for r in csv.DictReader(f)
                            if r.get("date", "") >= cutoff}
            with db.get_conn() as conn:
                gr_rows = conn.execute("""
                    SELECT game_pk, line FROM graded_results
                    WHERE game_date >= ? AND line IS NOT NULL
                """, (cutoff,)).fetchall()
            mismatches = 0
            compared   = 0
            for r in gr_rows:
                csv_r = csv_rows.get(str(r[0]))
                if not csv_r or not csv_r.get("open_total"):
                    continue
                try:
                    open_t = float(csv_r["open_total"])
                    gr_l   = float(r[1])
                    compared += 1
                    if abs(open_t - gr_l) > 0.25:
                        mismatches += 1
                except (ValueError, TypeError):
                    pass
            if compared == 0:
                results.append(_check("Decision line vs open_total alignment", SKIP,
                                      "no matching rows to compare"))
            elif mismatches == 0:
                results.append(_check("Decision line vs open_total alignment", PASS,
                                      f"{compared} rows checked, 0 mismatches"))
            else:
                results.append(_check("Decision line vs open_total alignment", WARN,
                                      f"{mismatches}/{compared} rows differ by >0.25 "
                                      f"(expected if refresh updated lines)"))
    except Exception as e:
        results.append(_check("Decision line vs open_total alignment", FAIL, str(e)))

    # ── Check 6: snapshot_source values are expected ──────────────────────────
    try:
        with db.get_conn() as conn:
            src_rows = conn.execute("""
                SELECT DISTINCT snapshot_source FROM graded_results
                WHERE game_date >= ? AND snapshot_source IS NOT NULL
            """, (cutoff,)).fetchall()
        found_sources = {r[0] for r in src_rows}
        # Valid: "missing", "line_movement_csv", "line_movement_csv@<ISO-timestamp>"
        unexpected = {s for s in found_sources
                      if s not in ("missing", "line_movement_csv")
                      and not s.startswith("line_movement_csv@")}
        if not found_sources:
            results.append(_check("snapshot_source values", SKIP,
                                  "no rows with snapshot_source yet"))
        elif unexpected:
            results.append(_check("snapshot_source values", WARN,
                                  f"unexpected values: {unexpected}"))
        else:
            ts_count = sum(1 for s in found_sources if "@" in s)
            results.append(_check("snapshot_source values", PASS,
                                  f"{len(found_sources)} distinct value(s); "
                                  f"{ts_count} with timestamp"))
    except Exception as e:
        results.append(_check("snapshot_source values", FAIL, str(e)))

    # ── Check 7: no duplicates in CLV data ───────────────────────────────────
    try:
        with db.get_conn() as conn:
            dup_rows = conn.execute("""
                SELECT game_pk, game_date, COUNT(*) AS cnt
                FROM graded_results
                WHERE game_date >= ?
                GROUP BY game_pk, game_date
                HAVING cnt > 1
            """, (cutoff,)).fetchall()
        if dup_rows:
            results.append(_check("No duplicate game_pk+game_date", FAIL,
                                  f"{len(dup_rows)} duplicate key(s) found"))
        else:
            results.append(_check("No duplicate game_pk+game_date", PASS,
                                  "UNIQUE constraint holding"))
    except Exception as e:
        results.append(_check("No duplicate game_pk+game_date", FAIL, str(e)))

    # ── Verdict ───────────────────────────────────────────────────────────────
    fails = [r for r in results if r["status"] == FAIL]
    warns = [r for r in results if r["status"] == WARN]
    skips = [r for r in results if r["status"] == SKIP]
    passes = [r for r in results if r["status"] == PASS]

    print(f"\n{'='*60}")
    print(f"  AUDIT SUMMARY: {len(passes)} PASS  {len(warns)} WARN  "
          f"{len(fails)} FAIL  {len(skips)} SKIP")
    print(f"{'='*60}")

    if fails:
        print("\n  ❌ NOT SAFE — fix failures before trusting CLV numbers.")
        for r in fails:
            print(f"     → {r['label']}: {r['detail']}")
        safe = False
    elif warns and all(r["status"] in (PASS, WARN, SKIP) for r in results):
        print("\n  ⚠️  SAFE WITH WARNINGS — CLV wiring is functional but coverage is low.")
        print("     Warnings resolve as the season progresses and refresh.py captures more closing lines.")
        safe = True
    else:
        print("\n  ✅ SAFE — CLV pipeline is correctly wired.")
        safe = True

    print()
    return safe


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLB CLV Shadow Audit")
    parser.add_argument("--days", type=int, default=14,
                        help="Lookback window in days (default: 14)")
    parser.add_argument("--date", default=None,
                        help="Custom cutoff date YYYY-MM-DD")
    args = parser.parse_args()
    ok = run_audit(days=args.days, target_date=args.date)
    sys.exit(0 if ok else 1)
