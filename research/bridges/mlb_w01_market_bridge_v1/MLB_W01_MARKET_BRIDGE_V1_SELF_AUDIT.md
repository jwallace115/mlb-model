# MLB W01 MARKET BRIDGE V1 — SELF-AUDIT
**Date:** 2026-04-19

1. Built locally on Mac only? **YES**
2. MLB_RUNTIME_OBJECT_V1 preserved unchanged? **YES** (bridge is a separate file)
3. Only one explicitly authorized bridge source used? **YES** (mlb_odds_closing_canonical.parquet)
4. No other odds files used? **YES**
5. Selection rule frozen before evaluating join? **YES** (DK only → latest pull_timestamp → drop null)
6. Source coverage audited? **YES** (2022-2025, 96-99% per season)
7. W01-relevant coverage documented? **YES** (16,376 usable rows)
8. closing_total null rate audited? **YES** (2.2%, below 5% threshold)
9. Grain preserved? **YES** (0 duplicates at game_pk+team)
10. Bridge kept separate from runtime object? **YES**
11. Only authorized files written? **YES** (6 files in bridge directory)
12. VM writes? **NO**
13. Honest closing_total for W01B? **YES**

**Verdict:** PASS
