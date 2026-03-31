# TB Market Efficiency Study — Report

## Verdict: CANNOT COMPLETE — HISTORICAL PROP ODDS NOT IN API ARCHIVE

### What We Found
**The Odds API historical archive does NOT carry player prop markets for regular-season MLB games.**

Tested across multiple dates in 2024 and 2025:

| Date | Events Found | TB Props Available |
|------|-------------|-------------------|
| 2024-03-28 (Opening Day) | 15 games | **0** |
| 2024-04-01 | 14 games | **0** |
| 2024-07-15 (All-Star) | 1 game | 30 outcomes (ASG only) |
| 2025-06-15 | 15 games | **0** |

The historical API returns moneyline only for regular games. Player props are not archived.

### Credits Used
~1,000 credits for diagnostic testing (0.025% of quota). No large pull executed.

### Recommendation: INVESTIGATE — pivot to forward collection

1. **Start daily TB line collection immediately** — extend props shadow to capture TB lines alongside HITS
2. **Build TB outcome model now** from 174,870 boxscore observations
3. **After 4-6 weeks of collected lines**: run efficiency study against real accumulated data
4. **Consider alternative providers** for historical prop archives if needed
