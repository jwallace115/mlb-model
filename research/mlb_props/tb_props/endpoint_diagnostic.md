# TB Props Endpoint Diagnostic

## What Was Wrong With the Previous Pull

Two errors:

1. **Wrong market key**: Used `player_total_bases` — correct key is `batter_total_bases`
   - `player_total_bases` returns 422 "Invalid market"
   - `batter_total_bases` returns 200 with data

2. **Per-event odds endpoint requires LIVE event IDs**: The historical events endpoint returns event IDs, but not all of these IDs work on the historical per-event odds endpoint. Events expire from the odds archive after approximately 12 months.

## Correct Working Endpoint

```
GET /v4/historical/sports/baseball_mlb/events/{eventId}/odds
params:
  apiKey: [key]
  regions: us
  markets: batter_total_bases
  oddsFormat: american
  date: YYYY-MM-DDTHH:MM:SSZ  (timestamp near game time)
```

## Verified Working Call

```
Event: NYY @ SFG (2026-03-27)
ID: 487285d7a2811bab184f43dff7b4f563
Result: 120 TB prop outcomes across multiple books
Credits: 10 per call
```

## Historical Availability Window

| Date Range | Available? | TB Outcomes |
|-----------|-----------|-------------|
| 2026-03-25 to 2026-03-27 | YES | 78-288 per day |
| 2025-09-15 | YES | 402 |
| 2025-04-01 to 2025-04-15 | YES | 243-255 per day |
| 2025-04-30 to 2025-09-14 | NO | Events expired (404) |
| 2025-03-27 | NO | Spring Training (no TB props) |
| 2024 (all dates) | NO | Events expired (404) |

The archive appears to use a rolling ~12-month retention window for per-event odds. Events older than approximately 12 months return 404.

## Available Data Estimate

- ~15 days in April 2025: ~225 games × ~18 TB props/game ≈ **4,000 prop records**
- ~15 days in September 2025: ~225 games × ~25 TB props/game ≈ **5,600 prop records**
- March 2026: ~30 games × ~20 TB props/game ≈ **600 prop records**
- **Total available: ~10,000 TB prop records**

## Credits Used in Diagnostic
~1,000 credits (test calls)

## Recommendation

Pull TB props for all available dates (April 2025 + September 2025 + March 2026). This gives ~10,000 records — enough for a meaningful efficiency study on one season of data, though not the full 2024+2025 originally planned.

Estimated cost: ~2,500 credits (250 games × 10 credits each)
