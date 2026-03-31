# NHL Phase 1 — Data Sources

## 1. NHL Stats API (canonical spine + boxscore + PP stats)

### Schedule
- Endpoint: `https://api-web.nhle.com/v1/schedule/{date}`
- Returns: game week containing the date; walk weekly
- Filter: `gameType == 2` for regular season only
- Fields used: `id`, `gameType`, `homeTeam.abbrev`, `awayTeam.abbrev`

### Boxscore
- Endpoint: `https://api-web.nhle.com/v1/gamecenter/{gameId}/boxscore`
- Fields used:
  - `homeTeam.score`, `awayTeam.score` — final scores
  - `gameOutcome.lastPeriodType` — "REG" | "OT" | "SO"
  - `playerByGameStats.{homeTeam,awayTeam}.goalies` — goalie stats
- Rate limit: ~15 req/s sustained; 0.15s sleep between schedule pages

### Power Play Stats
- Endpoint: `https://api.nhle.com/stats/rest/en/team/powerplay`
- Params: `isAggregate=false&isGame=true&cayenneExp=gameId={id}`
- Returns: 2 rows per game (homeRoad: H or R)
- Fields used: `ppOpportunities`, `powerPlayGoalsFor`, `shGoalsAgainst`
- PP pct: null when ppOpportunities == 0 (not 0.0)
- PK pct: null when times_shorthanded == 0

## 2. MoneyPuck (advanced stats)

- URL: `https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv`
- Download: single bulk CSV (~124 MB)
- Filter: `situation == "all"` for full-game stats
- Join: `gameId` (string) == NHL API game_id
- Required headers: `User-Agent` (browser), `Referer: https://moneypuck.com/data.htm`
- Seasons available: 2011-12 through current
- Fields used: `xGoalsFor`, `xGoalsAgainst`, `corsiPercentage`, `fenwickPercentage`,
  `shotsOnGoalFor`, `highDangerShotsFor`, `highDangerShotsAgainst`
- Coverage notes: some very recent games may lag by 1-2 days

## 3. The Odds API (closing market lines)

- Endpoint: `https://api.the-odds-api.com/v4/historical/sports/icehockey_nhl/odds/`
- API key: stored in `.env` as `ODDS_API_KEY`
- Query strategy: D+1 at 04:00 UTC to capture closing lines for date D
- Cost: ~10 requests per call (~720 calls needed for 4 seasons = ~7,200 requests)
- Markets: `totals` only; regions: `us`; bookmakers: `draftkings`, `fanduel`
- Preference: DraftKings > FanDuel when both available
- Data goes back to at least 2021-22 season
- Fields used: `point` (total line), `price` (over/under American odds)

## Regulation Score Derivation

- REG games: `home_goals_reg = homeTeam.score`, `away_goals_reg = awayTeam.score`
- OT games: winner scored exactly 1 OT goal; subtract from winner's final score
- SO games: same subtraction as OT, but `ot_goals = 0` (no goals in OT period)
- `ot_goals`: 1 for OT games, 0 for SO and REG games

## ARI → UTA Transition (2024-25)

- Arizona Coyotes (ARI) played their last season in 2023-24
- Utah Hockey Club (UTA) began play in 2024-25
- These are separate franchises with separate team codes in the NHL API
- No remapping is performed; ARI and UTA appear as distinct teams in the canonical table

## Caching

- All API responses cached as JSON in `nhl/cache/`
- MoneyPuck CSV cached in `nhl/cache/moneypuck_all_teams.csv`
- Odds API responses cached per game date
- Delete cache files to force re-fetch
