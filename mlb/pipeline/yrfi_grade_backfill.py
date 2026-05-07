#!/usr/bin/env python3
"""
One-time backfill grader for yrfi_shadow_2026.json.
Safe to re-run — skips already graded entries.
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from mlb.pipeline.yrfi_grading_utils import grade_entry

LOG_PATH = PROJECT_ROOT / "mlb" / "logs" / "yrfi_shadow_2026.json"


def main():
    with open(LOG_PATH) as f:
        entries = json.load(f)

    total = len(entries)
    already = sum(1 for e in entries if e.get("result_graded") is True)
    print(f"Total: {total} | Already graded: {already} | To attempt: {total - already}")

    graded = skipped = errors = 0

    for i, entry in enumerate(entries):
        if entry.get("result_graded") is True:
            continue
        gd = entry.get("game_date", "?")
        home = entry.get("home_team", "?")
        away = entry.get("away_team", "?")
        print(f"  [{i+1}/{total}] {away}@{home} {gd}", end="")
        try:
            entries[i] = grade_entry(entry, sleep_secs=0.5)
            if entries[i].get("result_graded") is True:
                r = entries[i].get("result_yrfi")
                p = entries[i].get("yrfi_profit_units")
                print(f" → YRFI={r}, profit={p}")
                graded += 1
            else:
                notes = entries[i].get("notes", [])
                reason = notes[-1] if notes else "unknown"
                print(f" → {reason}")
                skipped += 1
        except Exception as e:
            print(f" → ERROR: {e}")
            errors += 1

    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2, default=str)

    print(f"\nBackfill complete: graded={graded}, pending={skipped}, errors={errors}")

    graded_entries = [e for e in entries if e.get("result_graded") is True]

    if not graded_entries:
        print("\nZero graded — all entries are same-day or future. This is expected.")
    else:
        hits = sum(1 for e in graded_entries if e.get("result_yrfi") == 1)
        print(f"\nGraded summary: N={len(graded_entries)}, "
              f"YRFI hit rate: {hits}/{len(graded_entries)} = {hits/len(graded_entries):.1%}")
        for tier, field in [("2+", "yrfi_2plus"), ("3+", "yrfi_3plus")]:
            t = [e for e in graded_entries
                 if e.get(field) is True and e.get("fd_yrfi_price") is not None]
            if t:
                h = sum(1 for e in t if e.get("result_yrfi") == 1)
                roi = sum(e.get("yrfi_profit_units", 0) for e in t) / len(t)
                print(f"  {tier}: N={len(t)}, hit={h/len(t):.1%}, ROI={roi:.1%}")


if __name__ == "__main__":
    main()
