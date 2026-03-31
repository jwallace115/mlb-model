# TB Market Efficiency Study — Report

## Verdict: CANNOT COMPLETE — INSUFFICIENT DATA

### What Was Requested
A historical market-efficiency study for MLB batter Total Bases props, comparing sportsbook-implied probability against actual outcomes to identify persistent pricing inefficiencies.

### What Is Missing
**No historical TB prop closing odds exist locally for 2024 or 2025.**

The project has:
- 1,171 TB prop projections in the database (model outputs only)
- Only 16 TB props with actual sportsbook lines (all from March 26-27, 2026)
- Zero historical TB prop lines from the 2024 or 2025 regular seasons

### Why This Matters
A market-efficiency study requires comparing **actual sportsbook prices** against outcomes. Without historical closing odds, we cannot:
- Calculate ROI against real lines
- Test calibration by implied probability band
- Compare opening vs closing odds
- Determine whether the market is efficient or mispriced

Testing against synthetic lines (-110/-110) would produce misleading results because real TB prop lines vary significantly by player, context, and book (typical range: -150 to +130 for O/U 1.5 TB).

### What CAN Be Done Now
1. **TB outcome distribution analysis**: what % of batters exceed 1.5 TB by context (available from boxscores)
2. **Feature importance ranking**: which pregame features best predict TB outcomes (ISO, park, pitcher, order slot)
3. **Model-building feasibility**: is there enough signal in the features to justify a TB prediction model

### What Is Needed to Complete the Study
1. **Historical TB prop lines from The Odds API** — requires a dedicated API pull for the `batter_total_bases` market for 2024-2025 seasons (~$50-100 in API credits for historical odds)
2. **OR** begin collecting TB lines daily starting now (the props shadow system could be extended to TB alongside its existing HITS collection)

### Recommendation

**INVESTIGATE — but pivot scope:**

1. **Immediate**: Extend the existing props shadow system (`mlb/props_shadow.py`) to collect TB lines daily alongside HITS. This begins accumulating the odds data needed for a proper efficiency study.

2. **After 4-6 weeks of TB line collection**: Run the full market-efficiency study against real closing odds.

3. **In parallel**: Build a TB outcome prediction model using the 174,870 batter-game boxscore observations already available. This model can be ready to deploy against real lines once they accumulate.

4. **Optional**: Pull historical TB odds from The Odds API if budget allows (would enable immediate backtesting).

### What NOT to Do
- Do not run a pseudo-efficiency study against synthetic -110 lines — this would produce misleading conclusions about market efficiency
- Do not deploy TB prop bets without real closing-line validation
- Do not guess at implied probabilities from the projections alone
