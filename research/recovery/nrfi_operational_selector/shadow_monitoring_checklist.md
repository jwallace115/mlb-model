# NRFI Selector V1 — Shadow Monitoring Checklist

**Start date:** 2026-04-11
**Review cadence:** Daily grade, weekly summary review

---

## Daily Operations

### Morning (with 7 AM model run)
1. Run selector: `python3 mlb/pipeline/nrfi_daily_selector.py`
2. Verify output: 3 picks (or fewer if thin qualifying slate)
3. Check: F5 lines loaded (non-zero count)
4. Check: no runtime errors

### Evening (after games complete)
1. Grade: `python3 mlb/pipeline/nrfi_daily_selector.py --grade`
2. Verify: all top-3 picks graded (no None values)
3. Log any API failures

### Weekly Review
1. Run: `python3 mlb/pipeline/nrfi_daily_selector.py --summary`
2. Check cumulative hit rate vs 34.9% Phase 4 expectation
3. Check disqualifier is firing correctly on night/F5=4.0 games

---

## Health Checks

| Check | Expected | Action if failed |
|-------|----------|------------------|
| F5 lines loaded | >= 10 per slate | Check F5 pull ran; check parquet date |
| Schedule loaded | >= 1 game | Check MLB API; check date format |
| Qualifying games | >= 1 most days | Normal — some slates have 0 qualifiers |
| Grading completes | All picks graded | Check game status (postponed/suspended?) |
| Tracker dedup | 1 entry per date | File is idempotent; re-run is safe |

---

## Escalation Triggers (pause shadow)

- 0 qualifying games for 5+ consecutive days (check if F5 pull is broken)
- Hit rate below 20% after 30+ picks (significant underperformance vs 34.9%)
- Tracker file corruption or missing entries
- F5 parquet schema change (check column names)

---

## What NOT to Change

- Qualification threshold (F5 <= 4.0)
- Disqualifier rule (night AND F5 = 4.0)
- Ranking order (F5 asc, time asc, alpha)
- Card size (top 3)
- Any of these require full revalidation against historical data
