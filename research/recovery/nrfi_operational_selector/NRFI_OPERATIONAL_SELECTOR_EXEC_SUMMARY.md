# NRFI Operational Selector — Executive Summary

**Date:** 2026-04-11
**Object ID:** `mlb_nrfi_selector_v1_20260411`
**Ruleset:** `frozen_v1`
**Status:** READY FOR SHADOW

---

## What Was Built

A daily NRFI (No Run First Inning) selector that picks the top 3 MLB games most likely
to have a scoreless first inning, using only the F5 closing total and day/night flag.

### Frozen Rules

| Rule | Logic |
|------|-------|
| QUALIFY | F5 closing total <= 4.0 |
| DISQUALIFY | Night game AND F5 = 4.0 exactly |
| RANK | F5 ascending, tie-break by start time, then matchup alphabetical |
| CARD | Top 3 |

### Evidence (Phase 4-5)

- **Top-3 hit rate:** 34.9% (+9.7pp vs 25.2% random baseline)
- **Top-4 hit rate:** 23.5% (+7.5pp vs 16.0% random baseline)
- Adding ML engines or extra disqualifiers hurt performance (Phase 5)
- Data: 9,900 games (2022-2026), 6,635 with F5 lines

---

## Files Created

| File | Purpose |
|------|---------|
| `mlb/pipeline/nrfi_daily_selector.py` | Selector script (run daily) |
| `mlb/logs/nrfi_selector_v1_2026.json` | Tracker (auto-created, append-only) |
| `research/recovery/nrfi_operational_selector/phase0_locked_selector_spec.md` | Frozen spec |
| `research/recovery/nrfi_operational_selector/shadow_monitoring_checklist.md` | Monitoring rules |
| `research/recovery/nrfi_operational_selector/NRFI_OPERATIONAL_SELECTOR_EXEC_SUMMARY.md` | This file |

---

## Usage

```bash
# Select today's NRFI card
python3 mlb/pipeline/nrfi_daily_selector.py

# Select for a specific date
python3 mlb/pipeline/nrfi_daily_selector.py --date 2026-04-12

# Grade completed games
python3 mlb/pipeline/nrfi_daily_selector.py --grade

# Grade a specific date
python3 mlb/pipeline/nrfi_daily_selector.py --grade --date 2026-04-11

# Season summary
python3 mlb/pipeline/nrfi_daily_selector.py --summary
```

---

## Dry Run Results (2026-04-11)

```
Slate: 15 games | F5 lines: 15 | Qualified: 2 | Disqualified: 2

TOP 3 NRFI CARD:
  #1  PIT @ CHC      F5=3.5  [D]  -> NRFI  W
  #2  MIA @ DET      F5=4.0  [D]  -> YRFI  L

DISQUALIFIED:
  NYY @ TBR      F5=4.0  night_and_f5_4.0
  SFG @ BAL      F5=4.0  night_and_f5_4.0

Day 1 Record: 1-1
```

- Qualification logic correct: only F5 <= 4.0 pass
- Disqualifier correct: 2 night games at F5=4.0 blocked
- Ranking correct: F5=3.5 ranked above F5=4.0
- Grading correct: first-inning scores fetched and matched
- Tracker logging correct: idempotent, all 15 games logged

---

## Input Dependencies

| Input | Source | Refresh |
|-------|--------|---------|
| F5 closing total | `mlb_sim_f5/data/f5_lines_2026.parquet` | Updated by F5 pull pipeline |
| Day/night flag | MLB Stats API `dayNight` field | Live API call |
| First-inning scores | MLB Stats API live feed linescore | Live API call (grading) |

---

## Verdict: READY FOR SHADOW

All components operational. Begin daily shadow tracking immediately.
No production files were modified.
