# MLB Single-Game Market Inventory — Odds API Historical Endpoint

## 1. Test Game Details

- **Event ID**: `57684090148fa9ebfa94ae9e9e78e9fb`
- **Matchup**: Chicago Cubs @ Pittsburgh Pirates
- **Commence**: 2025-09-15T22:41:00Z
- **Season**: 2025 regular season

## 2. Confirmed Working Endpoint

```
GET /v4/historical/sports/baseball_mlb/events/{eventId}/odds
  apiKey={key}
  regions=us
  markets={market_key}
  oddsFormat=american
  date={commence_time}
```

Key behaviors:
- The `date` parameter must be near the game's commence_time
- Events older than ~12 months return 404
- Multiple markets can be requested in a single call (comma-separated)
- Credits: ~10 per call regardless of market count

## 3. Player Prop Market Results

| Market Key | Available | Players Priced | Books | Sample |
|-----------|-----------|---------------|-------|--------|
| **batter_total_bases** | YES | 21 | 9 | Michael Busch Over 3.5 @ +290 |
| **batter_hits** | YES | 21 | 7 | Nico Hoerner Over 2.5 @ +500 |
| **batter_home_runs** | YES | 21 | 5 | Michael Busch Over 0.5 @ +420 |
| **batter_runs_scored** | YES | 18 | 4 | Michael Busch Over 0.5 @ -130 |
| **batter_rbis** | YES | 18 | 5 | Ballesteros Over 1.5 @ +430 |
| **batter_hits_runs_rbis** | YES | 19 | 6 | Michael Busch Over 1.5 @ -130 |
| **batter_stolen_bases** | YES | 18 | 4 | Crow-Armstrong Over 0.5 @ +350 |
| **pitcher_strikeouts** | YES | 2 | 8 | Taillon Over 4.5 @ +114 |
| **pitcher_outs** | YES | 1 | 7 | Taillon Over 15.5 @ -110 |
| **pitcher_hits_allowed** | YES | 2 | 5 | Taillon Over 4.5 @ -152 |
| **pitcher_walks** | YES | 2 | 2 | Taillon Over 1.5 @ -105 |
| **pitcher_earned_runs** | YES | 2 | 5 | Taillon Over 3.5 @ +250 |

**All 12 player prop markets return data.** Every market uses Over/Under format with American odds and point values.

## 4. Core Game Markets

| Market Key | Available | Books | Sample |
|-----------|-----------|-------|--------|
| **totals** | YES | 11 | O/U 8.0 @ -108/-112 |
| **spreads** | YES | 11 | CHC -1.5 @ +126 / PIT +1.5 @ -152 |
| **h2h** | YES | 11 | CHC -124 / PIT +106 |
| **team_totals** | YES | 6 | CHC O/U 4.5 @ +114/-148 |
| **totals_1st_5_innings** | YES | 6 | O/U 4.5 @ -102/-128 |
| **spreads_1st_5_innings** | YES | 6 | CHC -0.5 @ +114 / PIT +0.5 @ -148 |
| **h2h_1st_5_innings** | YES | 9 | CHC -118 / PIT -106 |

**All 7 core game markets return data.**

## 5. Complete Market Inventory

**19 total markets available** for a single MLB game via the historical per-event endpoint:

- 7 batter prop markets
- 5 pitcher prop markets
- 4 game-level markets (totals, spreads, h2h, team_totals)
- 3 first-5-innings markets

## 6. Credits Used in This Diagnostic

| Step | Calls | Credits |
|------|-------|---------|
| Event discovery | 1 | ~1 |
| Baseline confirmation | 1 | ~10 |
| Prop market discovery (11 markets) | 11 | ~120 |
| Core market check (7 markets) | 7 | ~70 |
| **Total** | **20** | **~200** |

Credits remaining: ~3,988,800

## 7. Backfill Recommendation

### Priority Ranking

| Rank | Market | Research Value | Edge Potential | Urgency |
|------|--------|---------------|---------------|---------|
| 1 | **batter_total_bases** | HIGH — efficiency study shows 5pp mispricing | HIGH — Under TB systematically underpriced | MEDIUM — already pulled Apr/Sep 2025 |
| 2 | **pitcher_strikeouts** | HIGH — most liquid pitcher prop | HIGH — K prop modeling is a primary market | HIGH — pull before events expire |
| 3 | **batter_hits** | HIGH — most liquid batter prop | MEDIUM — needs efficiency testing | HIGH — pull alongside TB |
| 4 | **team_totals** | HIGH — direct application to totals model | HIGH — team total vs game total edge | MEDIUM |
| 5 | **batter_home_runs** | MEDIUM — low frequency event | MEDIUM — heavy vig on HR props | LOW |
| 6 | **batter_rbis** | LOW — highly correlated with TB/hits | LOW — noisy market | LOW |
| 7 | **pitcher_hits_allowed** | MEDIUM — inverse of batter hits | MEDIUM — pitcher-centric modeling | LOW |

### Estimated Credit Cost for Full Backfill

**Per-game cost**: ~10 credits per market per game (but multiple markets can be combined in one call)

**Optimized approach**: Request multiple markets in a single API call:
```
markets=batter_total_bases,batter_hits,pitcher_strikeouts,team_totals
```
This should cost ~10 credits per game regardless of market count.

| Scope | Est. Games | Credits/Game | Total Credits |
|-------|-----------|-------------|---------------|
| 2025 full season (available window) | ~2,000 | 10 | ~20,000 |
| 2024 season | UNAVAILABLE (events expired) | — | — |
| 2022-2023 closing lines | UNAVAILABLE (events expired) | — | — |

**Recommended pull**: All available 2025 games with `batter_total_bases,batter_hits,pitcher_strikeouts,team_totals` in a single call per game. Estimated cost: **~20,000 credits** (0.5% of remaining quota).

### Time Sensitivity

Events expire from the archive after ~12 months. The earliest available 2025 games (late March/early April 2025) will start expiring in late March/early April 2026 — **within days**. A full 2025 backfill should be prioritized before these events disappear.
