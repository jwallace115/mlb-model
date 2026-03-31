# Source Audit — TB Props Historical Dataset

## Credit Audit

| Metric | Value |
|--------|-------|
| Credits before pull | 4,006,600 |
| Estimated cost | ~55,000 credits (1.4% of quota) |
| Events calls | ~366 (1 credit each) |
| Per-event odds calls | ~5,490 (10 credits each) |
| Cost well under 1,000,000 limit | YES |

## API Endpoint Structure

- Historical events: `GET /v4/historical/sports/baseball_mlb/events?date=YYYY-MM-DDT12:00:00Z`
  - Returns events scheduled near that date
  - 1 credit per call

- Per-event odds: `GET /v4/historical/sports/baseball_mlb/events/{id}/odds?date=YYYY-MM-DDT23:00:00Z&markets=batter_total_bases`
  - Returns closing TB prop odds near game time
  - ~10 credits per call
  - Books: FanDuel, DraftKings

## Sample Data Verified

Successfully pulled TB props for 2025 All-Star Game:
- 30 outcomes per bookmaker
- Player name, line (1.5), Over/Under odds in American format
- Example: Shohei Ohtani Over 1.5 TB @ +240

## Outcome Data Available Locally

- 174,870 batter-game rows with actual H, 2B, 3B, HR, total_bases
- Source: research/lineup_protection_study/protection_pa_dataset.parquet
- Also: research/mlb_v3_lineup_model/historical_lineups_long.parquet
- Covers 2022-2025 (9,715 games)

## Pull Result: HISTORICAL PLAYER PROPS NOT AVAILABLE

**The Odds API historical archive does NOT carry player prop markets for regular-season MLB games.**

Verified by testing multiple dates across 2024 and 2025:
- 2024-03-28 (Opening Day): 15 events found, 0 TB prop outcomes
- 2024-04-01: 14 events found, 0 TB prop outcomes
- 2024-07-15: 1 event (All-Star only), TB props available for ASG only
- 2025-06-15: 15 events found, 0 TB prop outcomes

The historical API returns h2h/moneyline only for regular games. Player prop markets (batter_total_bases, batter_hits, pitcher_strikeouts) are not archived.

Credits used in diagnostic: ~1,000 (from test calls)
Credits remaining: ~4,005,600

## Alternative Paths
1. Extend daily props_shadow.py to collect TB lines going forward
2. Build TB outcome model from boxscore data now, validate later against collected lines
3. Consider a different data provider for historical player prop archives
